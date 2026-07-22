"""Deterministic reconciliation tests for the TechSolve analytical layer."""

from pathlib import Path

import duckdb


PROJECT_DIR = Path(__file__).resolve().parent
DB_PATH = PROJECT_DIR / "techsolve.duckdb"

REPORTING_FILTER = """
CAST(created_date AS DATE) >= DATE '2024-01-01'
AND CAST(created_date AS DATE) < DATE '2026-01-01'
"""


def assert_equal(label: str, actual, expected) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, received {actual!r}")
    print(f"[PASS] {label}: {actual}")


def assert_close(label: str, actual: float, expected: float, tolerance: float) -> None:
    if abs(actual - expected) > tolerance:
        raise AssertionError(
            f"{label}: expected approximately {expected}, received {actual}"
        )
    print(f"[PASS] {label}: {actual:.2f}")


def main() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            "techsolve.duckdb is missing. Run nl_agent.py once to build it."
        )

    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        ticket_count = con.execute(
            f"""
            SELECT COUNT(DISTINCT ticket_id)
            FROM tbl_TicketData
            WHERE {REPORTING_FILTER}
            """
        ).fetchone()[0]

        unresolved_share = con.execute(
            f"""
            SELECT
                100.0 * COUNT(*) FILTER (
                    WHERE status_standard NOT IN ('Closed', 'Resolved')
                ) / COUNT(*)
            FROM tbl_TicketData
            WHERE {REPORTING_FILTER}
            """
        ).fetchone()[0]

        sla_breach_rate = con.execute(
            f"""
            SELECT
                100.0 * AVG(
                    CASE WHEN is_sla_breached THEN 1.0 ELSE 0.0 END
                )
            FROM tbl_TicketData
            WHERE {REPORTING_FILTER}
            """
        ).fetchone()[0]

        average_resolution = con.execute(
            f"""
            SELECT AVG(resolution_time_hours)
            FROM tbl_TicketData
            WHERE {REPORTING_FILTER}
            """
        ).fetchone()[0]

        largest_region = con.execute(
            f"""
            SELECT region
            FROM tbl_TicketData
            WHERE {REPORTING_FILTER}
            GROUP BY region
            ORDER BY COUNT(*) DESC, region
            LIMIT 1
            """
        ).fetchone()[0]

        largest_issue = con.execute(
            f"""
            SELECT issue_subcategory
            FROM tbl_TicketData
            WHERE {REPORTING_FILTER}
            GROUP BY issue_subcategory
            ORDER BY COUNT(*) DESC, issue_subcategory
            LIMIT 1
            """
        ).fetchone()[0]

        public_holiday_share = con.execute(
            f"""
            SELECT
                100.0 * COUNT(*) FILTER (
                    WHERE d."Is Public Holiday" = TRUE
                ) / COUNT(*)
            FROM tbl_TicketData AS t
            INNER JOIN dim_Date AS d
                ON CAST(t.created_date AS DATE) = CAST(d."Date" AS DATE)
            WHERE {REPORTING_FILTER}
            """
        ).fetchone()[0]

        print("TechSolve metric reconciliation")
        print("=" * 42)
        assert_equal("Reporting ticket count", ticket_count, 67167)
        assert_close("Outside Closed or Resolved (%)", unresolved_share, 60.0, 0.1)
        assert_close("SLA breach rate (%)", sla_breach_rate, 50.1, 0.1)
        assert_close("Average resolution hours", average_resolution, 120.6, 0.1)
        assert_equal("Largest region", largest_region, "Auckland")
        assert_equal("Largest issue", largest_issue, "Login Issue")
        assert_close("Public-holiday ticket share (%)", public_holiday_share, 3.0, 0.1)
        print("=" * 42)
        print("All deterministic metric checks passed.")
    finally:
        con.close()


if __name__ == "__main__":
    main()
