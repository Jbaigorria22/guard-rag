"""
Guard-RAG - Security events dashboard.
Reads security_events.log and shows it as a table and a chart.
"""

import re
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Guard-RAG - Dashboard", page_icon="📊", layout="wide")

st.title("📊 Security Dashboard")
st.caption("Detection events recorded in security_events.log")

LOG_PATH = Path("security_events.log")

# Accepts the current English keys and the older Spanish ones (archivo= / patrones_detectados=).
LINE_PATTERN = re.compile(
    r"\[(?P<timestamp>[\d\-: ]+)\] (?:file|archivo)=(?P<file>.+?) \| "
    r"(?:detected_patterns|patrones_detectados)=\"(?P<patterns>.*)\""
)


def load_events() -> pd.DataFrame:
    if not LOG_PATH.exists():
        return pd.DataFrame(columns=["timestamp", "file", "patterns"])

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
    st.info("No security events recorded yet. Process a PDF with suspicious content to see data here.")
else:
    col1, col2 = st.columns(2)
    col1.metric("Total events", len(events_df))
    col2.metric("Distinct files affected", events_df["file"].nunique())

    st.subheader("Events per file")
    st.bar_chart(events_df["file"].value_counts())

    st.subheader("Full history")
    st.dataframe(events_df.sort_values("timestamp", ascending=False), use_container_width=True)
