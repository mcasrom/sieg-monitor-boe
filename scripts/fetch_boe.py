#!/usr/bin/env python3
"""
fetch_boe.py
SIEG Monitor Legislativo España

Ingesta diaria del BOE — todas las secciones.
Clasifica por tipo, detecta términos políticos clave
y almacena en DuckDB.

Cron: diario 06:00
0 6 * * * cd ~/sieg-monitor-boe && source venv/bin/activate && python3 scripts/fetch_boe.py >> logs/pipeline.log 2>&1

Autor : M. Castillo · mybloggingnotes@gmail.com
© 2026 M. Castillo
"""

import os
import hashlib
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, date

import duckdb

BASE_DIR = os.path.expanduser("~/sieg-monitor-boe")
DB_PATH  = os.path.join(BASE_DIR, "data", "processed", "boe.duckdb")
LOG_PATH = os.path.join(BASE_DIR, "logs", "pipeline.log")

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

# Secciones BOE
SECCIONES = {
    1: "Disposiciones generales",
    2: "Autoridades y personal",
    3: "Otras disposiciones",
    4: "Administración Local",
    5: "Anuncios",
}

# Términos políticos de interés para clasificación
TERMINOS_POLITICOS = {
    "corrupcion":    ["corrupción", "malversación", "soborno", "fraude", "prevaricación"],
    "contratos":     ["contrato", "licitación", "adjudicación", "concurso público"],
    "subvenciones":  ["subvención", "ayuda", "beca", "convocatoria"],
    "personal":      ["nombramiento", "cese", "ascenso", "excedencia"],
    "normativa":     ["ley", "decreto", "resolución", "orden ministerial", "reglamento"],
    "electoral":     ["elecciones", "electoral", "convocatoria electoral", "junta electoral"],
    "territorial":   ["comunidad autónoma", "autonomía", "transferencia", "competencias"],
    "economica":     ["presupuesto", "gasto", "inversión", "déficit", "deuda pública"],
    "social":        ["pensiones", "seguridad social", "sanidad", "educación", "vivienda"],
    "judicial":      ["sentencia", "tribunal", "juzgado", "auto", "resolución judicial"],
}

# Organismos por partido/ideología
ORGANISMOS_POLITICOS = {
    "Ministerio de Presidencia":     "PSOE",
    "Ministerio de Hacienda":        "PSOE",
    "Ministerio del Interior":       "PSOE",
    "Ministerio de Defensa":         "PSOE",
    "Generalitat de Catalunya":      "independentismo",
    "Gobierno Vasco":                "PNV",
    "Junta de Andalucía":            "PP",
    "Comunidad de Madrid":           "PP",
    "Comunitat Valenciana":          "PSOE",
    "Junta de Castilla y León":      "PP",
    "Xunta de Galicia":              "PP",
}

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)

def init_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS boe_items (
            id           VARCHAR PRIMARY KEY,
            titulo       VARCHAR,
            seccion      INTEGER,
            seccion_nombre VARCHAR,
            organismo    VARCHAR,
            partido_ref  VARCHAR,
            fecha        DATE,
            url          VARCHAR,
            categoria    VARCHAR,
            terminos     VARCHAR,
            relevancia   INTEGER DEFAULT 0,
            ingestion_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS boe_tendencias (
            fecha        DATE,
            termino      VARCHAR,
            categoria    VARCHAR,
            count        INTEGER,
            PRIMARY KEY (fecha, termino)
        )
    """)
    log("DB inicializada OK")

def detectar_terminos(texto):
    """Detecta categorías temáticas en el texto."""
    texto_lower = texto.lower()
    cats = []
    for cat, terminos in TERMINOS_POLITICOS.items():
        for t in terminos:
            if t in texto_lower:
                cats.append(cat)
                break
    return ",".join(cats) if cats else "general"

def calcular_relevancia(titulo, seccion):
    """Calcula score de relevancia política."""
    score = 0
    titulo_lower = titulo.lower()

    # Sección 1 (leyes) = más relevante
    if seccion == 1:
        score += 3
    elif seccion == 3:
        score += 2

    # Términos de alta relevancia
    for term in ["ley", "decreto-ley", "decreto real", "resolución", "nombramiento"]:
        if term in titulo_lower:
            score += 2

    # Términos políticos
    for terms in TERMINOS_POLITICOS.values():
        for t in terms:
            if t in titulo_lower:
                score += 1

    return min(score, 10)

def detectar_organismo(titulo, descripcion):
    """Detecta el organismo emisor."""
    texto = f"{titulo} {descripcion}".lower()
    for org, partido in ORGANISMOS_POLITICOS.items():
        if org.lower() in texto:
            return org, partido
    # Detectar ministerios genéricos
    if "ministerio" in texto:
        import re
        m = re.search(r"ministerio de (\w+(?:\s+\w+)?)", texto)
        if m:
            return f"Ministerio de {m.group(1).title()}", "gobierno"
    return "", ""

def fetch_seccion(conn, seccion_num, fecha_hoy):
    """Descarga e indexa una sección del BOE."""
    url = f"https://boe.es/rss/boe.php?s={seccion_num}"
    seccion_nombre = SECCIONES.get(seccion_num, f"Sección {seccion_num}")

    try:
        r = requests.get(url, timeout=30, headers={"User-Agent": "SIEG-Monitor/1.0"})

        # BOE usa ISO-8859-1
        content = r.content.decode("iso-8859-1", errors="replace")
        root = ET.fromstring(content.encode("utf-8"))

        insertados = 0
        tendencias = {}

        for item in root.findall(".//item"):
            titulo = item.findtext("title", "").strip()
            link   = item.findtext("link", "").strip()
            desc   = item.findtext("description", "").strip()
            guid   = item.findtext("guid", link).strip()

            if not titulo or titulo == "Sumario":
                continue

            uid = hashlib.md5(guid.encode()).hexdigest()
            organismo, partido = detectar_organismo(titulo, desc)
            cats     = detectar_terminos(f"{titulo} {desc}")
            relev    = calcular_relevancia(titulo, seccion_num)

            # Leer fecha real del item RSS
            pub_date = item.findtext("pubDate", "")
            try:
                from email.utils import parsedate_to_datetime
                fecha_item = parsedate_to_datetime(pub_date).date() if pub_date else fecha_hoy
            except:
                fecha_item = fecha_hoy

            conn.execute("""
                INSERT OR IGNORE INTO boe_items
                (id, titulo, seccion, seccion_nombre, organismo, partido_ref,
                 fecha, url, categoria, terminos, relevancia)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (uid, titulo[:400], seccion_num, seccion_nombre,
                  organismo[:200], partido[:50],
                  str(fecha_item), link[:500],
                  cats.split(",")[0] if cats else "general",
                  cats, relev))
            insertados += 1

            # Acumular tendencias
            for cat in cats.split(","):
                if cat:
                    tendencias[cat] = tendencias.get(cat, 0) + 1

        # Guardar tendencias del día
        for cat, cnt in tendencias.items():
            conn.execute("""
                INSERT OR REPLACE INTO boe_tendencias (fecha, termino, categoria, count)
                VALUES (?, ?, ?, ?)
            """, (str(fecha_hoy), cat, cat, cnt))

        log(f"[BOE S{seccion_num}] {insertados} items · {len(tendencias)} categorías")
        return insertados

    except Exception as e:
        log(f"[BOE S{seccion_num}] Error: {e}")
        return 0

def exportar_parquet(conn):
    """Exporta a Parquet para Streamlit Cloud."""
    import pandas as pd
    export_dir = os.path.join(BASE_DIR, "data", "exports")
    os.makedirs(export_dir, exist_ok=True)

    tablas = {
        "boe_items":      "SELECT * FROM boe_items ORDER BY fecha DESC, relevancia DESC LIMIT 5000",
        "boe_tendencias": "SELECT * FROM boe_tendencias ORDER BY fecha DESC, count DESC",
        "boe_hoy":        "SELECT * FROM boe_items WHERE fecha = CURRENT_DATE ORDER BY relevancia DESC",
        "boe_relevantes": "SELECT * FROM boe_items WHERE relevancia >= 4 ORDER BY fecha DESC LIMIT 1000",
    }

    for nombre, query in tablas.items():
        try:
            df = conn.execute(query).df()
            path = os.path.join(export_dir, f"{nombre}.parquet")
            df.to_parquet(path, index=False, engine="pyarrow")
            log(f"[PARQUET] {nombre}: {len(df)} filas")
        except Exception as e:
            log(f"[PARQUET] Error {nombre}: {e}")

def main():
    log("=" * 50)
    log("SIEG Monitor BOE — Inicio ingesta")

    conn = duckdb.connect(DB_PATH)
    init_db(conn)

    fecha_hoy = date.today()
    total = 0

    for seccion in [1, 2, 3, 4, 5]:
        total += fetch_seccion(conn, seccion, fecha_hoy)

    # Estadísticas
    n_total  = conn.execute("SELECT COUNT(*) FROM boe_items").fetchone()[0]
    n_hoy    = conn.execute("SELECT COUNT(*) FROM boe_items WHERE fecha = CURRENT_DATE").fetchone()[0]
    n_relev  = conn.execute("SELECT COUNT(*) FROM boe_items WHERE relevancia >= 4 AND fecha = CURRENT_DATE").fetchone()[0]

    log(f"BD: {n_total} total · {n_hoy} hoy · {n_relev} relevantes")

    # Retención 90 días
    conn.execute("DELETE FROM boe_items WHERE fecha < CURRENT_DATE - INTERVAL 90 DAY")
    conn.execute("DELETE FROM boe_tendencias WHERE fecha < CURRENT_DATE - INTERVAL 90 DAY")
    conn.execute("VACUUM")
    log("Retención 90 días aplicada")

    exportar_parquet(conn)
    conn.close()

    log(f"Ingesta completada — {total} items procesados")
    log("=" * 50)

if __name__ == "__main__":
    main()
