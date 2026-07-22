"""Safe command-line prototype for the TechSolve natural-language agent."""

from __future__ import annotations

import os
import re
from pathlib import Path

import duckdb
from dotenv import load_dotenv
from openai import OpenAI


PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"
DB_PATH = PROJECT_DIR / "techsolve.duckdb"

TABLE_FILES = {
    "tbl_TicketData": "tbl_TicketData.csv",
    "dim_Issue": "dim_Issue.csv",
    "dim_Region": "dim_Region.csv",
    "dim_Date": "dim_Date.csv",
    "tbl_WeatherDaily": "tbl_WeatherDaily.csv",
    "dim_NZPublicHoliday": "dim_NZPublicHoliday.csv",
}

MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6")
MAX_RESULT_ROWS = 200

SCHEMA_CONTEXT = """
You are a SQL analyst for TechSolve support operations. Generate DuckDB SQL.

Approved tables:
- tbl_TicketData: one row per support ticket. Important columns include
  ticket_id, region, team, category, issue_category, issue_subcategory,
  priority, status_standard, channel, created_date, ticket_resolved_date,
  first_response_time_hours, resolution_time_hours, is_closed,
  is_escalated, is_sla_breached and csat_score.
- dim_Date: "Date", "Year", "Quarter", "Month Number", "Month",
  "Month Year", "Day of Week", "Is Weekend", "Is Public Holiday" and
  "Day Type". Quote column names containing spaces.
- dim_Region: region, representative_location, latitude and longitude.
- dim_Issue: issue_category and issue_subcategory.
- tbl_WeatherDaily: region, weather_date, precipitation_mm,
  precipitation_hours, temperature_mean_c, is_rain_day,
  is_heavy_rain_day and rain_category.
- dim_NZPublicHoliday: holiday_date, holiday_name and holiday flags.

Join rules:
- CAST(tbl_TicketData.created_date AS DATE) = CAST(dim_Date."Date" AS DATE).
- tbl_TicketData.region = tbl_WeatherDaily.region AND
  CAST(tbl_TicketData.created_date AS DATE) =
  CAST(tbl_WeatherDaily.weather_date AS DATE).
- Join weather on BOTH region and date. Never join ticket and weather data on
  date alone.
- Use ticket_resolved_date directly for questions specifically about the date
  on which tickets were resolved.

Business definitions:
- Ticket count = COUNT(DISTINCT ticket_id).
- Open backlog = is_closed = FALSE and status_standard <> 'Cancelled'.
- SLA breach rate = breached tickets divided by tickets in scope.
- Escalation rate = escalated tickets divided by tickets in scope.
- Average resolution hours excludes null resolution_time_hours.
- Unless the user gives a different period, filter created_date from
  2024-01-01 inclusive to 2026-01-01 exclusive.
- The 2025 extract is incomplete. Do not describe it as a complete year.
- Weather and holiday results show association, not causation.
- For rainy-versus-dry demand, start from tbl_WeatherDaily so every observed
  region-day is represented, LEFT JOIN tickets on both region and date, count
  distinct ticket_id per region-day, then compare the average daily count by
  is_rain_day. Keep the SQL concise.

Rules:
- Return exactly one read-only SELECT query. A WITH query is allowed.
- Use only the approved tables and columns.
- Prefer aggregated results and return no more than 100 rows.
- Do not return customer names, email addresses, free text notes or individual
  employee details.
- Return SQL only, without markdown fences or explanation.
"""

PROHIBITED_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|create|copy|attach|detach|install|"
    r"load|pragma|call|export|import|truncate|replace|vacuum)\b",
    re.IGNORECASE,
)

PROHIBITED_COLUMNS = re.compile(
    r"\b(customer_id|customer_name|customer_email|billing_contact_email|"
    r"account_manager|assigned_to|issue_description|resolution_notes)\b",
    re.IGNORECASE,
)


def sql_path(path: Path) -> str:
    return str(path).replace("'", "''")


def build_database() -> None:
    missing = [filename for filename in TABLE_FILES.values() if not (DATA_DIR / filename).exists()]
    if missing:
        raise FileNotFoundError(f"Missing data files: {', '.join(missing)}")

    con = duckdb.connect(str(DB_PATH))
    try:
        for table, filename in TABLE_FILES.items():
            path = DATA_DIR / filename
            con.execute(
                f'CREATE OR REPLACE TABLE "{table}" AS '
                f"SELECT * FROM read_csv_auto('{sql_path(path)}', header=true)"
            )
    finally:
        con.close()


def extract_sql(text: str) -> str:
    sql = text.strip()
    if sql.startswith("```sql"):
        sql = sql[len("```sql") :]
    elif sql.startswith("```"):
        sql = sql[3:]
    if sql.endswith("```"):
        sql = sql[:-3]
    return sql.strip()


def validate_sql(sql: str) -> None:
    cleaned = re.sub(r"--.*?$|/\*.*?\*/", "", sql, flags=re.MULTILINE | re.DOTALL).strip()
    if not re.match(r"^(select|with)\b", cleaned, flags=re.IGNORECASE):
        raise ValueError("Only SELECT or WITH queries are permitted.")
    if PROHIBITED_SQL.search(cleaned):
        raise ValueError("The generated query contains a prohibited operation.")
    if PROHIBITED_COLUMNS.search(cleaned):
        raise ValueError("The generated query references a restricted field.")
    if ";" in cleaned.rstrip(";"):
        raise ValueError("Multiple SQL statements are not permitted.")
    if not re.search(r"\b(tbl_TicketData|dim_Date|dim_Region|dim_Issue|tbl_WeatherDaily|dim_NZPublicHoliday)\b", cleaned):
        raise ValueError("The query does not use an approved analytical table.")


def ask_agent(client: OpenAI, question: str):
    generation_input = question
    sql = ""
    result_df = None

    # A model can occasionally return incomplete or invalid SQL. Give it one
    # controlled repair attempt using DuckDB's exact error message.
    for attempt in range(2):
        sql_response = client.responses.create(
            model=MODEL,
            instructions=SCHEMA_CONTEXT,
            input=generation_input,
            max_output_tokens=1200,
        )
        sql = extract_sql(sql_response.output_text)

        try:
            validate_sql(sql)
            con = duckdb.connect(str(DB_PATH), read_only=True)
            try:
                result_df = con.execute(sql).fetchdf()
            finally:
                con.close()
            break
        except Exception as exc:
            if attempt == 1:
                raise ValueError(
                    "The generated query was invalid after one automatic repair. "
                    "Please try the question again or use simpler wording."
                ) from exc
            generation_input = (
                f"Original question: {question}\n\n"
                f"The previous SQL was invalid:\n{sql}\n\n"
                f"DuckDB or validation error:\n{exc}\n\n"
                "Return one corrected, complete SQL query only."
            )

    if result_df is None:
        raise ValueError("The analytical query did not return a result.")

    if len(result_df) > MAX_RESULT_ROWS:
        raise ValueError(
            f"The query returned {len(result_df)} rows; ask a more summarised question."
        )

    answer_response = client.responses.create(
        model=MODEL,
        max_output_tokens=600,
        instructions=(
            "You are a concise support-operations analyst. Use only the supplied "
            "query result. Structure the response as Answer, Evidence, "
            "Interpretation, Scope and Caveat. Do not invent values. State that "
            "2025 is incomplete whenever it is relevant. Describe weather or "
            "holiday relationships as associations, not causation."
        ),
        input=(
            f"Question: {question}\n\n"
            f"Executed SQL:\n{sql}\n\n"
            f"Query result:\n{result_df.to_string(index=False)}"
        ),
    )
    return sql, answer_response.output_text.strip(), result_df


def main() -> None:
    load_dotenv(PROJECT_DIR / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit(
            "OPENAI_API_KEY is missing. Copy .env.example to .env and add your key."
        )

    global MODEL
    MODEL = os.getenv("OPENAI_MODEL", MODEL)

    print("Preparing the local analytical database...")
    build_database()
    client = OpenAI()

    print("\nTechSolve analytical agent. Enter 'quit' to stop.")
    while True:
        question = input("\nQuestion> ").strip()
        if question.lower() in {"quit", "exit"}:
            break
        if not question:
            continue
        try:
            sql, answer, _ = ask_agent(client, question)
            print(f"\nGenerated SQL:\n{sql}\n\n{answer}")
        except Exception as exc:
            print(f"\nThe request could not be completed: {exc}")


if __name__ == "__main__":
    main()
