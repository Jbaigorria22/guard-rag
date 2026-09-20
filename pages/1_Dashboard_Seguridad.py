"""
Guard-RAG - Dashboard de eventos de seguridad.
Lee security_events.log y lo muestra en tabla y grafico.
"""

import re
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Guard-RAG - Dashboard", page_icon="📊", layout="wide")

st.title("📊 Dashboard de Seguridad")
st.caption("Eventos de deteccion registrados en security_events.log")

LOG_PATH = Path("security_events.log")

LINE_PATTERN = re.compile(
    r"\[(?P<timestamp>[\d\-: ]+)\] archivo=(?P<archivo>.+?) \| patrones_detectados=\"(?P<patrones>.*)\""
)


def load_events() -> pd.DataFrame:
    if not LOG_PATH.exists():
        return pd.DataFrame(columns=["timestamp", "archivo", "patrones"])

    rows = []
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            match = LINE_PATTERN.match(line.strip())
            if match:
                rows.append(match.groupdict())

    df = pd.DataFrame(rows)
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


events_df = load_events()

if events_df.empty:
    st.info("Todavia no se registraron eventos de seguridad. Procesa un PDF con contenido sospechoso para ver datos aca.")
else:
    col1, col2 = st.columns(2)
    col1.metric("Total de eventos", len(events_df))
    col2.metric("Archivos distintos afectados", events_df["archivo"].nunique())

    st.subheader("Eventos por archivo")
    st.bar_chart(events_df["archivo"].value_counts())

    st.subheader("Historial completo")
    st.dataframe(events_df.sort_values("timestamp", ascending=False), use_container_width=True)