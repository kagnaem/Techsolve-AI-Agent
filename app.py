"""Streamlit interface for the TechSolve support-operations agent."""

from __future__ import annotations

import os
from pathlib import Path

import duckdb
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

PROJECT_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_DIR / ".env")

st.set_page_config(
    page_title="TechSolve Operations Agent",
    page_icon="🤖",
    layout="wide",
)

# Streamlit Community Cloud injects credentials through st.secrets. Local
# development continues to use the ignored .env file.
try:
    if "OPENAI_API_KEY" in st.secrets:
        os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
    if "OPENAI_MODEL" in st.secrets:
        os.environ["OPENAI_MODEL"] = st.secrets["OPENAI_MODEL"]
except FileNotFoundError:
    pass

from nl_agent import DB_PATH, MODEL, ask_agent, build_database

st.markdown(
    """
    <style>
    .stApp { background-color: #0f172a; }
    [data-testid="stSidebar"] { background-color: #1e293b; }
    .agent-kicker {
        color: #2dd4bf;
        font-size: 0.82rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 0.35rem;
    }
    .agent-subtitle {
        color: #cbd5e1;
        font-size: 1.05rem;
        max-width: 880px;
        margin-top: -0.45rem;
        margin-bottom: 0.35rem;
    }
    .agent-byline {
        display: inline-block;
        color: #dbeafe;
        font-size: 0.95rem;
        background: linear-gradient(90deg, #172554, #164e63);
        border: 1px solid #2dd4bf;
        border-radius: 12px;
        padding: 0.65rem 1rem;
        margin-top: 0.35rem;
        margin-bottom: 1.25rem;
        box-shadow: 0 5px 18px rgba(20, 184, 166, 0.12);
    }
    .agent-author-name {
        color: #5eead4;
        font-size: 1.12rem;
        font-weight: 800;
    }
    .agent-footer {
        color: #94a3b8;
        font-size: 0.82rem;
        text-align: center;
        padding: 0.6rem 0 0.2rem 0;
    }
    h1 { color: #f8fafc !important; }
    h2, h3 { color: #5eead4 !important; }
    [data-testid="stMetric"] {
        background: linear-gradient(145deg, #172554, #164e63);
        border: 1px solid #2dd4bf;
        border-radius: 12px;
        padding: 14px 16px;
    }
    [data-testid="stMetricLabel"] { color: #bfdbfe; }
    [data-testid="stMetricValue"] { color: #f8fafc; }
    [data-testid="stDataFrame"] {
        border: 1px solid #334155;
        border-radius: 10px;
        overflow: hidden;
    }
    div.stButton > button {
        background: linear-gradient(90deg, #14b8a6, #0ea5e9);
        border: none;
        color: white;
        font-weight: 700;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def prepare_database() -> str:
    build_database()
    return str(DB_PATH)


@st.cache_data
def headline_metrics(database_path: str) -> dict[str, object]:
    con = duckdb.connect(database_path, read_only=True)
    try:
        row = con.execute(
            """
            SELECT
                COUNT(DISTINCT ticket_id) AS tickets,
                100.0 * COUNT(*) FILTER (
                    WHERE status_standard NOT IN ('Closed', 'Resolved')
                ) / COUNT(*) AS unresolved_share,
                100.0 * AVG(
                    CASE WHEN is_sla_breached THEN 1.0 ELSE 0.0 END
                ) AS sla_breach_rate,
                AVG(resolution_time_hours) AS average_resolution
            FROM tbl_TicketData
            WHERE CAST(created_date AS DATE) >= DATE '2024-01-01'
              AND CAST(created_date AS DATE) < DATE '2026-01-01'
            """
        ).fetchone()
        return {
            "tickets": int(row[0]),
            "unresolved_share": float(row[1]),
            "sla_breach_rate": float(row[2]),
            "average_resolution": float(row[3]),
        }
    finally:
        con.close()


database_path = prepare_database()
metrics = headline_metrics(database_path)


def display_result_evidence(result_df) -> None:
    """Show the executed result as a table and an appropriate simple chart."""
    if result_df is None or result_df.empty:
        st.info("The validated query returned no rows to visualise.")
        return

    st.subheader("📋 Evidence table")
    st.dataframe(result_df, width="stretch", hide_index=True)

    numeric_columns = list(result_df.select_dtypes(include="number").columns)
    dimension_columns = [
        column for column in result_df.columns if column not in numeric_columns
    ]
    if len(result_df) < 2 or not numeric_columns or not dimension_columns:
        return

    st.subheader("📊 Visual summary")
    measure = numeric_columns[0]
    if len(numeric_columns) > 1:
        measure = st.selectbox(
            "Measure to chart",
            numeric_columns,
            index=0,
            key="result_chart_measure",
        )

    dimension = dimension_columns[0]
    chart_data = result_df[[dimension, measure]].dropna().copy()
    if chart_data.empty:
        return
    chart_data[dimension] = chart_data[dimension].astype(str)
    chart_data = chart_data.set_index(dimension)

    temporal_words = ("date", "month", "year", "week", "quarter", "time")
    is_time_series = any(word in dimension.lower() for word in temporal_words)
    if is_time_series:
        st.line_chart(chart_data, color="#2dd4bf", width="stretch")
        st.caption(f"Line chart: {measure.replace('_', ' ').title()} by {dimension.replace('_', ' ').title()}")
    else:
        st.bar_chart(chart_data, color="#38bdf8", width="stretch")
        st.caption(f"Bar chart: {measure.replace('_', ' ').title()} by {dimension.replace('_', ' ').title()}")

st.markdown(
    '<div class="agent-kicker">Data & AI Specialist Practical Assessment</div>',
    unsafe_allow_html=True,
)
st.title("🤖 TechSolve Support Operations AI Agent")
st.markdown(
    '<div class="agent-subtitle">Ask questions about ticket demand, service '
    'performance, SLA results, public holidays and regional weather.</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="agent-byline">&#128100; &nbsp; Developed by '
    '<span class="agent-author-name">Kagna Em</span><br>'
    '<span>Data & AI Specialist · Evidence-based analysis using the validated '
    '2024–2025 reporting model</span></div>',
    unsafe_allow_html=True,
)

st.warning(
    "The reporting label covers 2024–2025, but the 2025 ticket extract is "
    "incomplete. Treat results primarily as a 2024 operational baseline."
)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Reporting tickets", f"{metrics['tickets']:,}")
col2.metric("Outside Closed/Resolved", f"{metrics['unresolved_share']:.1f}%")
col3.metric("SLA breach rate", f"{metrics['sla_breach_rate']:.1f}%")
col4.metric("Average resolution", f"{metrics['average_resolution']:.1f} h")

st.divider()

with st.sidebar:
    st.header("✅ Agent status")
    if os.getenv("OPENAI_API_KEY"):
        st.success("OpenAI key configured")
    else:
        st.error("OpenAI key missing")
    st.caption(f"Model: {os.getenv('OPENAI_MODEL', MODEL)}")
    st.caption("Query engine: DuckDB (read-only)")
    st.caption("📅 Default scope: 1 Jan 2024–31 Dec 2025")

    st.header("🛡️ Analytical controls")
    st.markdown(
        "- Approved analytical tables only\n"
        "- SELECT/WITH queries only\n"
        "- One statement per request\n"
        "- Maximum 200 result rows\n"
        "- Weather interpreted as association"
    )

suggested_questions = [
    "How many tickets are in the 2024-2025 reporting period?",
    "How did monthly ticket demand change during 2024?",
    "Which issue categories generated the most tickets?",
    "Which issue subcategories generated the most tickets?",
    "Which service areas received the most tickets?",
    "Which channels were used most often?",
    "Which teams had the highest SLA breach rates?",
    "Which priorities had the highest SLA breach rates?",
    "What percentage of urgent tickets breached SLA?",
    "Which teams currently have the largest open backlog?",
    "Which issue categories have the largest open backlog?",
    "Are urgent tickets resolved faster than low-priority tickets?",
    "Which teams had the longest average resolution time?",
    "Which issue categories had the longest average resolution time?",
    "Which teams had the highest escalation rates?",
    "Which issue categories had the lowest average CSAT scores?",
    "Which regions generated the greatest ticket demand?",
    "Which regions had the highest SLA breach rates?",
    "Which regions had the longest average resolution time?",
    "Did public holidays have higher average daily ticket volume?",
    "Which public holidays had the highest ticket volume?",
    "How does demand compare between rainy and dry region-days?",
    "Which regions had the most tickets on heavy-rain days?",
    "What are the three most important operational risks?",
]

st.subheader("💬 Ask an operational question")
selected = st.selectbox(
    "Start with a suggested question",
    ["Write my own question"] + suggested_questions,
)

default_question = "" if selected == "Write my own question" else selected
question = st.text_area(
    "Question",
    value=default_question,
    height=90,
    placeholder="For example: Which teams have the highest SLA breach rates?",
)

submit = st.button("Analyse", type="primary", width="content")

if submit:
    if not question.strip():
        st.error("Enter a question before selecting Analyse.")
    elif not os.getenv("OPENAI_API_KEY"):
        st.error(
            "The OpenAI API key is not configured. Add it to the local .env "
            "file or Streamlit Community Cloud Secrets."
        )
    else:
        try:
            with st.spinner("Planning and validating the analytical query..."):
                client = OpenAI()
                sql, answer, result_df = ask_agent(client, question.strip())

            st.subheader("💡 Answer and insight")
            st.markdown(answer)

            display_result_evidence(result_df)

            with st.expander("🔍 Generated query and analytical controls"):
                st.code(sql, language="sql")
                st.caption(
                    "The query was validated before execution and ran against "
                    "the local DuckDB database in read-only mode."
                )
        except Exception as exc:
            message = str(exc)
            if "insufficient_quota" in message or "429" in message:
                st.error(
                    "The interface is working, but the OpenAI API account has no "
                    "available credit. Add API credit and try again."
                )
            elif "authentication" in message.lower() or "401" in message:
                st.error("OpenAI authentication failed. Check the local API key.")
            else:
                st.error(f"The request could not be completed: {message}")

st.divider()
st.markdown(
    '<div class="agent-footer">Developed by <strong>Kagna Em</strong> | '
    'TechSolve assessment prototype<br>Synthetic data · AI-generated insights '
    'should be validated against the governed Power BI measures</div>',
    unsafe_allow_html=True,
)
