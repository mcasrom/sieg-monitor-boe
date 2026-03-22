#!/usr/bin/env python3
"""
app.py
SIEG Monitor Legislativo España

Dashboard de seguimiento del BOE y actividad legislativa.

Autor : M. Castillo · mybloggingnotes@gmail.com
© 2026 M. Castillo
"""

import os
import warnings
warnings.filterwarnings("ignore")

import streamlit as st
import pandas as pd
import duckdb
import altair as alt
from datetime import datetime, date, timedelta

# ── Configuración ─────────────────────────────────────────
st.set_page_config(
    page_title="SIEG Monitor Legislativo · BOE España",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Detección de entorno ──────────────────────────────────
_local   = os.path.expanduser("~/sieg-monitor-boe")
_cloud   = "/mount/src/sieg-monitor-boe"
_script  = os.path.dirname(os.path.abspath(__file__))
_parent  = os.path.dirname(_script)
BASE_DIR = next(
    (p for p in [_local, _cloud, _parent]
     if os.path.exists(os.path.join(p, "data", "exports"))),
    _parent
)
DB_PATH  = os.path.join(BASE_DIR, "data", "processed", "boe.duckdb")
EXP_DIR  = os.path.join(BASE_DIR, "data", "exports")

# ── Logo OSINT ────────────────────────────────────────────
st.markdown("""
<svg width='100%' viewBox='0 0 680 120' xmlns='http://www.w3.org/2000/svg'>
<style>
@keyframes scan{0%{opacity:.1}50%{opacity:.35}100%{opacity:.1}}
@keyframes blink{0%,100%{opacity:1}49%{opacity:1}50%{opacity:0}99%{opacity:0}}
.sc{animation:scan 3s ease-in-out infinite}
.cu{animation:blink 1.1s step-end infinite}
</style>
<rect width='680' height='120' rx='4' fill='#0a0e0a' stroke='#1a2e1a'/>
<rect width='680' height='120' rx='4' fill='none' stroke='#00ff41' stroke-width='0.5' opacity='0.25'/>
<line x1='0' y1='26' x2='680' y2='26' stroke='#00ff41' stroke-width='0.3' opacity='0.15'/>
<circle cx='16' cy='13' r='4' fill='#ff5f57'/>
<circle cx='30' cy='13' r='4' fill='#febc2e'/>
<circle cx='44' cy='13' r='4' fill='#28c840'/>
<text x='340' y='18' text-anchor='middle' font-family='monospace' font-size='9' fill='#00ff41' opacity='0.35'>sieg-monitor-legislativo — boe-espana-osint</text>
<rect x='14' y='36' width='652' height='1' fill='#00ff41' opacity='0.06' class='sc'/>
<rect x='14' y='62' width='652' height='1' fill='#00ff41' opacity='0.06' class='sc' style='animation-delay:.8s'/>
<text x='18' y='50' font-family='monospace' font-size='9' fill='#00ff41' opacity='0.45'>root@sieg:~$</text>
<text x='100' y='50' font-family='monospace' font-size='9' fill='#00ff41'>./monitor --fuente=BOE --secciones=1,2,3,4,5 --alertas=ON</text>
<text x='18' y='66' font-family='monospace' font-size='8' fill='#4ade80' opacity='0.65'>[+] Secciones monitorizadas: 5 | Items hoy: LIVE | Retención: 90 días</text>
<text x='18' y='90' font-family='monospace' font-size='18' font-weight='bold' fill='#00ff41' letter-spacing='3'>SIEG MONITOR LEGISLATIVO</text>
<text x='310' y='90' font-family='monospace' font-size='11' fill='#00cc33' letter-spacing='2'>BOE · España · OSINT</text>
<text x='310' y='106' font-family='monospace' font-size='9' fill='#009922' opacity='0.7'>Vigilancia legislativa automatizada 24/7</text>
<text x='18' y='112' font-family='monospace' font-size='7' fill='#00ff41' opacity='0.3'>© 2026 M.Castillo · mybloggingnotes@gmail.com</text>
</svg>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────
st.sidebar.markdown("""
<div style='padding:0.4rem 0 0.8rem 0; border-bottom:1px solid rgba(0,255,65,0.15); margin-bottom:0.8rem'>
    <div style='font-size:0.65rem; color:#00cc33; font-weight:600; letter-spacing:2px'>SIEG OSINT</div>
    <div style='font-size:0.95rem; font-weight:600; color:#00ff41'>Monitor Legislativo</div>
    <div style='font-size:0.65rem; color:#4a7a4a'>BOE · España</div>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("""
<div style='font-size:0.75rem; line-height:1.9; opacity:0.75; margin-bottom:8px'>
    <div style='font-weight:600; margin-bottom:6px; font-size:0.8rem; color:#00ff41'>🛰️ Red SIEG OSINT</div>
    <a href='https://mcasrom.github.io/sieg-osint' target='_blank' style='display:block; color:#4ade80; text-decoration:none; margin-bottom:4px'>🌐 Portal SIEG OSINT</a>
    <a href='https://politica-nacional-osint.streamlit.app' target='_blank' style='display:block; color:#4ade80; text-decoration:none; margin-bottom:4px'>📊 SIEG Política Nacional</a>
    <a href='https://fake-news-narrative.streamlit.app' target='_blank' style='display:block; color:#4ade80; text-decoration:none; margin-bottom:4px'>📡 Narrative Radar</a>
    <a href='https://sieg-radar-electoral.streamlit.app' target='_blank' style='display:block; color:#4ade80; text-decoration:none; margin-bottom:4px'>🗳️ España Vota 2026</a>
    <a href='https://t.me/sieg_politica' target='_blank' style='display:block; color:#4ade80; text-decoration:none; margin-bottom:4px'>📢 Canal @sieg_politica</a>
    <a href='https://sieg-energia.streamlit.app' target='_blank' style='display:block; color:#4ade80; text-decoration:none'>⚡ Monitor Energético</a>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("""
<div style='text-align:center; padding:6px 0; margin-bottom:8px'>
    <a href='https://ko-fi.com/m_castillo' target='_blank'
       style='display:inline-block; background:#FF5E5B; color:white;
              font-weight:600; font-size:0.75rem; padding:6px 14px;
              border-radius:16px; text-decoration:none'>
        ☕ Buy me a coffee
    </a>
    <div style='font-size:0.65rem; opacity:0.4; margin-top:3px'>Apoya SIEG OSINT</div>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("---")

# Filtros
st.sidebar.subheader("🔧 Filtros")
seccion_sel = st.sidebar.multiselect(
    "Secciones BOE",
    options=[1, 2, 3, 4, 5],
    default=[1, 2, 3],
    format_func=lambda x: {
        1: "1 · Disposiciones generales",
        2: "2 · Autoridades y personal",
        3: "3 · Otras disposiciones",
        4: "4 · Administración Local",
        5: "5 · Anuncios"
    }.get(x, str(x))
)

dias_sel = st.sidebar.slider("Últimos días", 1, 30, 7)
relev_min = st.sidebar.slider("Relevancia mínima", 0, 10, 0)

st.sidebar.markdown("---")
st.sidebar.markdown("""
<div style='font-size:0.65rem; opacity:0.35; text-align:center; font-family:monospace'>
    © 2026 M. Castillo<br>
    <a href='mailto:mybloggingnotes@gmail.com' style='color:inherit'>mybloggingnotes@gmail.com</a>
</div>
""", unsafe_allow_html=True)

# ── Carga de datos ────────────────────────────────────────
@st.cache_data(ttl=1800)
def cargar_datos(dias, secciones, relev):
    fecha_desde = date.today() - timedelta(days=dias)
    try:
        if os.path.exists(DB_PATH):
            conn = duckdb.connect(DB_PATH, read_only=True)
            df = conn.execute(f"""
                SELECT * FROM boe_items
                WHERE fecha >= '{fecha_desde}'
                AND seccion IN ({','.join(map(str, secciones))})
                AND relevancia >= {relev}
                ORDER BY fecha DESC, relevancia DESC
            """).df()
            df_tend = conn.execute(f"""
                SELECT * FROM boe_tendencias
                WHERE fecha >= '{fecha_desde}'
                ORDER BY fecha DESC, count DESC
            """).df()
            conn.close()
        else:
            # Streamlit Cloud — leer parquet
            df_path = os.path.join(EXP_DIR, "boe_items.parquet")
            df = pd.read_parquet(df_path) if os.path.exists(df_path) else pd.DataFrame()
            df = df[df["seccion"].isin(secciones)] if not df.empty else df
            tend_path = os.path.join(EXP_DIR, "boe_tendencias.parquet")
            df_tend = pd.read_parquet(tend_path) if os.path.exists(tend_path) else pd.DataFrame()

        if not df.empty:
            df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
        return df, df_tend

    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        return pd.DataFrame(), pd.DataFrame()

df, df_tend = cargar_datos(dias_sel, seccion_sel if seccion_sel else [1,2,3,4,5], relev_min)

# ── Tabs ──────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📋 Resumen diario",
    "📈 Tendencias legislativas",
    "🔍 Buscador BOE",
    "🏛️ Por sección",
    "📖 Guía"
])

# ── Tab 1: Resumen diario ─────────────────────────────────
with tab1:
    st.header("📋 Resumen diario del BOE")

    if df.empty:
        st.info("Sin datos disponibles. Ejecuta el pipeline primero.")
    else:
        hoy = date.today()
        df_hoy = df[df["fecha"].dt.date == hoy] if not df.empty else pd.DataFrame()
        if df_hoy.empty and not df.empty:
            ultimo_dia = df["fecha"].dt.date.max()
            df_hoy = df[df["fecha"].dt.date == ultimo_dia]
            hoy = ultimo_dia
            st.info(f"El BOE no publica hoy — mostrando último día disponible: {ultimo_dia.strftime('%d/%m/%Y')}")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("📄 Items hoy", len(df_hoy))
        c2.metric("⭐ Relevantes", len(df_hoy[df_hoy["relevancia"] >= 4]) if not df_hoy.empty else 0)
        c3.metric("📅 Días cubiertos", df["fecha"].dt.date.nunique())
        c4.metric("📊 Total registros", len(df))

        st.markdown("---")

        # Items más relevantes del día
        st.subheader(f"⭐ Más relevantes — {hoy.strftime('%d/%m/%Y')}")
        if not df_hoy.empty:
            df_relev = df_hoy.sort_values("relevancia", ascending=False).head(20)
            for _, row in df_relev.iterrows():
                relev = int(row.get("relevancia", 0))
                stars = "⭐" * min(relev, 5)
                cats  = str(row.get("terminos", ""))
                org   = str(row.get("organismo", ""))
                url   = str(row.get("url", ""))
                titulo = str(row.get("titulo", ""))

                with st.expander(f"{stars} {titulo[:80]}"):
                    col1, col2 = st.columns([2,1])
                    with col1:
                        st.markdown(f"**Organismo:** {org}")
                        st.markdown(f"**Categorías:** {cats}")
                        st.markdown(f"**Sección:** {row.get('seccion_nombre','')}")
                    with col2:
                        st.markdown(f"**Relevancia:** {relev}/10")
                        if url:
                            st.markdown(f"[📄 Ver en BOE]({url})")
        else:
            st.info("Sin datos para hoy todavía.")

# ── Tab 2: Tendencias ─────────────────────────────────────
with tab2:
    st.header("📈 Tendencias legislativas")

    if df.empty:
        st.info("Sin datos disponibles.")
    else:
        # Categorías por día
        df_cats = df.copy()
        df_cats["fecha_str"] = df_cats["fecha"].dt.date.astype(str)

        cat_counts = []
        for _, row in df_cats.iterrows():
            for cat in str(row.get("terminos","")).split(","):
                cat = cat.strip()
                if cat and cat != "general":
                    cat_counts.append({"fecha": row["fecha_str"], "categoria": cat})

        if cat_counts:
            df_cat = pd.DataFrame(cat_counts)
            df_cat_g = df_cat.groupby(["fecha", "categoria"]).size().reset_index(name="count")

            chart = alt.Chart(df_cat_g).mark_line(point=True).encode(
                x=alt.X("fecha:T", title="Fecha"),
                y=alt.Y("count:Q", title="Menciones"),
                color=alt.Color("categoria:N", title="Categoría"),
                tooltip=["fecha:T", "categoria:N", "count:Q"]
            ).properties(height=350, title="Categorías legislativas por día")
            st.altair_chart(chart, use_container_width=True)

        st.markdown("---")

        # Top categorías período
        st.subheader("🏆 Top categorías del período")
        if cat_counts:
            df_top = pd.DataFrame(cat_counts)["categoria"].value_counts().head(10).reset_index()
            df_top.columns = ["Categoría", "Menciones"]
            bar = alt.Chart(df_top).mark_bar(color="#00cc33").encode(
                x=alt.X("Menciones:Q"),
                y=alt.Y("Categoría:N", sort="-x"),
                tooltip=["Categoría:N", "Menciones:Q"]
            ).properties(height=300)
            st.altair_chart(bar, use_container_width=True)

# ── Tab 3: Buscador ───────────────────────────────────────
with tab3:
    st.header("🔍 Buscador BOE")
    query = st.text_input("Buscar en títulos del BOE:", placeholder="ej: pensiones, contratos, nombramiento...")

    if query and not df.empty:
        mask = df["titulo"].str.lower().str.contains(query.lower(), na=False)
        df_res = df[mask].sort_values("fecha", ascending=False)
        st.markdown(f"**{len(df_res)} resultados** para '{query}'")

        if not df_res.empty:
            for _, row in df_res.head(30).iterrows():
                url = str(row.get("url", ""))
                titulo = str(row.get("titulo", ""))
                fecha  = str(row.get("fecha", ""))[:10]
                org    = str(row.get("organismo", ""))
                relev  = int(row.get("relevancia", 0))
                st.markdown(
                    f"**{fecha}** · {titulo[:100]} "
                    f"{'— ' + org if org else ''} "
                    f"{'[↗](' + url + ')' if url else ''} "
                    f"⭐{relev}"
                )
    elif not query:
        st.info("Introduce un término para buscar en el BOE.")

# ── Tab 4: Por sección ────────────────────────────────────
with tab4:
    st.header("🏛️ Actividad por sección")

    if not df.empty:
        sec_counts = df.groupby(["seccion_nombre"]).size().reset_index(name="items")
        pie = alt.Chart(sec_counts).mark_arc().encode(
            theta=alt.Theta("items:Q"),
            color=alt.Color("seccion_nombre:N", title="Sección"),
            tooltip=["seccion_nombre:N", "items:Q"]
        ).properties(height=300, title="Distribución por sección")
        st.altair_chart(pie, use_container_width=True)

        st.markdown("---")

        for sec_num in sorted(df["seccion"].unique()):
            df_sec = df[df["seccion"] == sec_num].head(10)
            if not df_sec.empty:
                sec_nom = df_sec.iloc[0]["seccion_nombre"]
                with st.expander(f"**Sección {sec_num} — {sec_nom}** ({len(df[df['seccion']==sec_num])} items)"):
                    st.dataframe(
                        df_sec[["fecha", "titulo", "organismo", "relevancia", "terminos"]].head(10),
                        use_container_width=True
                    )

# ── Tab 5: Guía ───────────────────────────────────────────
with tab5:
    st.header("📖 Guía de uso")
    st.markdown("""
## SIEG Monitor Legislativo España

Sistema de vigilancia automatizada del Boletín Oficial del Estado (BOE).

### Secciones monitorizadas
| Sección | Contenido |
|---|---|
| 1 | Disposiciones generales (leyes, decretos, RD-Ley) |
| 2 | Autoridades y personal (nombramientos, ceses) |
| 3 | Otras disposiciones (resoluciones, instrucciones) |
| 4 | Administración Local (ayuntamientos, diputaciones) |
| 5 | Anuncios (licitaciones, adjudicaciones, subvenciones) |

### Metodología
- **Ingesta:** diaria a las 06:00 desde BOE RSS
- **Clasificación:** detección automática de 10 categorías temáticas
- **Relevancia:** score 0-10 basado en tipo de disposición y contenido político
- **Retención:** 90 días de histórico
- **Motor:** DuckDB + Parquet (optimizado para ARM Odroid C2)

### Categorías detectadas
`normativa` · `contratos` · `subvenciones` · `personal` · `electoral`
`territorial` · `economica` · `social` · `judicial` · `corrupcion`

### Red SIEG OSINT
Este monitor forma parte del ecosistema SIEG OSINT España junto con
SIEG Política Nacional, Narrative Radar y España Vota 2026.

---
© 2026 M. Castillo · mybloggingnotes@gmail.com · [Portal SIEG OSINT](https://mcasrom.github.io/sieg-osint)
    """)

st.markdown("---")
st.markdown("""
<div style='text-align:center; font-size:0.72rem; opacity:0.35; font-family:monospace'>
    SIEG Monitor Legislativo · BOE España · © 2026 M. Castillo ·
    <a href='https://mcasrom.github.io/sieg-osint' target='_blank' style='color:inherit'>SIEG OSINT</a>
</div>
""", unsafe_allow_html=True)
