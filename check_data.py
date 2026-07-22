from pathlib import Path

import duckdb


PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"

EXPECTED_FILES = {
    "tbl_TicketData": "tbl_TicketData.csv",
    "dim_Date": "dim_Date.csv",
    "dim_Issue": "dim_Issue.csv",
    "dim_Region": "dim_Region.csv",
    "tbl_WeatherDaily": "tbl_WeatherDaily.csv",
    "dim_NZPublicHoliday": "dim_NZPublicHoliday.csv",
}


def qpath(path: Path) -> str:
    return str(path).replace("'", "''")


def main() -> None:
    missing = [name for name in EXPECTED_FILES.values() if not (DATA_DIR / name).exists()]
    if missing:
        raise FileNotFoundError(f"Missing required data files: {', '.join(missing)}")

    con = duckdb.connect()

    print("TechSolve agent data validation")
    print("=" * 38)

    for table, filename in EXPECTED_FILES.items():
        path = DATA_DIR / filename
        con.execute(
            f'CREATE OR REPLACE VIEW "{table}" AS '
            f"SELECT * FROM read_csv_auto('{qpath(path)}', header=true)"
        )
        rows = con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        columns = len(con.execute(f'DESCRIBE "{table}"').fetchall())
        print(f"[OK] {filename}: {rows:,} rows, {columns} columns")

    ticket_summary = con.execute(
        """
        SELECT
            COUNT(*) AS rows,
            COUNT(DISTINCT ticket_id) AS distinct_tickets,
            MIN(CAST(created_date AS DATE)) AS minimum_date,
            MAX(CAST(created_date AS DATE)) AS maximum_date,
            COUNT(*) FILTER (
                WHERE CAST(created_date AS DATE) >= DATE '2024-01-01'
                  AND CAST(created_date AS DATE) < DATE '2026-01-01'
            ) AS reporting_tickets
        FROM tbl_TicketData
        """
    ).fetchone()

    date_summary = con.execute(
        """
        SELECT
            COUNT(*) AS rows,
            COUNT(DISTINCT CAST(Date AS DATE)) AS distinct_dates,
            MIN(CAST(Date AS DATE)) AS minimum_date,
            MAX(CAST(Date AS DATE)) AS maximum_date
        FROM dim_Date
        """
    ).fetchone()

    weather_duplicates = con.execute(
        """
        SELECT COUNT(*)
        FROM (
            SELECT region, CAST(weather_date AS DATE), COUNT(*) AS records
            FROM tbl_WeatherDaily
            GROUP BY region, CAST(weather_date AS DATE)
            HAVING COUNT(*) > 1
        )
        """
    ).fetchone()[0]

    print("\nReconciliation")
    print("-" * 38)
    print(f"Ticket rows:             {ticket_summary[0]:,}")
    print(f"Distinct ticket IDs:     {ticket_summary[1]:,}")
    print(f"Ticket date range:       {ticket_summary[2]} to {ticket_summary[3]}")
    print(f"2024-2025 tickets:       {ticket_summary[4]:,}")
    print(f"Date rows/distinct:      {date_summary[0]:,} / {date_summary[1]:,}")
    print(f"Date dimension range:    {date_summary[2]} to {date_summary[3]}")
    print(f"Duplicate region-dates:  {weather_duplicates:,}")

    checks = {
        "Ticket IDs are unique": ticket_summary[0] == ticket_summary[1],
        "Reporting ticket count is 67,167": ticket_summary[4] == 67167,
        "Date dimension contains 731 rows": date_summary[0] == 731,
        "Date dimension dates are unique": date_summary[0] == date_summary[1],
        "Date dimension starts 2024-01-01": str(date_summary[2]) == "2024-01-01",
        "Date dimension ends 2025-12-31": str(date_summary[3]) == "2025-12-31",
        "Weather region-date keys are unique": weather_duplicates == 0,
    }

    print("\nAcceptance checks")
    print("-" * 38)
    for label, passed in checks.items():
        print(f"[{'PASS' if passed else 'FAIL'}] {label}")

    if not all(checks.values()):
        raise SystemExit("Validation failed. Correct the failed checks before running the agent.")

    print("\nAll local data checks passed.")


if __name__ == "__main__":
    main()
