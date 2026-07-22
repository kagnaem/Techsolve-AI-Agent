# TechSolve Ticket Data — Data Dictionary

Grounding reference for the NL analytics agent. Generated from the Power BI
semantic model (`TechSolve - Ticket Data Report.SemanticModel`). Model type:
**Import mode**, sourced from an Excel workbook (`TechSolve - Ticket Data.xlsx`),
transformed via Power Query. No Premium/Fabric capacity detected — plan the
agent around a copy of the data, not a live XMLA connection (see notes at
the bottom).

Report pages already built: **Executive Overview**, **Issues & Performance**,
**Holiday & Weather Context** — useful hints for what a manager will ask about.

---

## Tables

### `tbl_TicketData` (fact table — one row per support ticket)
Core columns an agent will query most:

| Column | Type | Notes |
|---|---|---|
| `ticket_id` | int64 | Primary key |
| `customer_id`, `customer_name`, `company_name` | string | Customer identity |
| `account_type`, `customer_segment`, `industry` | string | Customer attributes |
| `account_manager` | string | |
| `monthly_contract_value` | double | Revenue value of the account |
| `account_created_date` | dateTime | |
| `region` | string | Links to `dim_Region` |
| `subscription_type` | string | |
| `customer_tenure_months` | int64 | |
| `service_area`, `category`, `issue_category`, `issue_subcategory` | string | What the ticket is about |
| `priority` | string | |
| `sla_target_hours` | int64 | |
| `status`, `status_standard` | string | Raw vs. cleaned status |
| `team`, `assigned_to` | string | **Who handled it — used for team performance questions** |
| `channel` | string | How the ticket came in |
| `ticket_created_date`, `ticket_resolved_date`, `created_date` | dateTime | Three separate date roles (see Relationships) |
| `first_response_time_hours`, `resolution_time_hours` | double | Core SLA metrics |
| `escalated`, `is_escalated` | string/boolean | |
| `sla_breached`, `is_sla_breached`, `calculated_sla_breach`, `sla_flag_mismatch` | string/boolean | Note: raw flag vs. recalculated flag — a mismatch column exists, worth asking about if answers seem off |
| `csat_score` | int64 | Customer satisfaction |
| `issue_complexity_score` | int64 | |
| `previous_tickets` | int64 | |
| `operating_system`, `browser` | string | |
| `is_closed` | boolean | |
| `created_year`, `created_month`, `validation_flag` | string | Housekeeping/derived columns |

### `dim_Issue`
Lookup: `issue_category` ↔ `issue_subcategory` (`Index`, `issue_category`, `issue_subcategory`).

### `dim_Region`
`region`, `representative_location`, `latitude`, `longitude` — also joined to weather data.

### `dim_Date` (standard date dimension, joined via `created_date`)
`Date`, `Year`, `Quarter`, `Month Number`, `Month`, `Month Short`, `Month Year`,
`Year Month`, `Month Start`, `Day`, `Day of Week`, `Is Weekend`, `Reporting Period`,
plus computed: `Holiday Name`, `Is Public Holiday`, `Day Type` (Public holiday /
Weekend / Weekday, derived from `dim_NZPublicHoliday`).

### `issue_mapping`
Keyword → `Category` / `Subcategory` / `Priority` lookup, used upstream in Power
Query to classify free-text issue descriptions. Not typically queried directly by
the agent, but useful if it needs to explain *how* a ticket got its category.

### `tbl_WeatherDaily`
Daily weather by region: `weather_date`, `temperature_max_c`, `temperature_min_c`,
`temperature_mean_c`, `precipitation_mm`, `precipitation_hours`,
`wind_speed_max_kmh`, `wind_gust_max_kmh`, `is_rain_day`, `is_heavy_rain_day`,
`rain_category`. Sourced live from the Open-Meteo API per region (see
`fn_GetWeather` in `expressions.tmdl`) — powers the "Holiday & Weather Context"
page (e.g. "do ticket volumes spike on rain days?").

### `dim_NZPublicHoliday`
`holiday_date`, `holiday_name`, `is_public_holiday`, `is_national_holiday`,
`regional_codes` — NZ public holiday calendar.

---

## Relationships

| From | To | Purpose |
|---|---|---|
| `tbl_TicketData.created_date` | `dim_Date.Date` | **Primary active date relationship** — most measures filter through this |
| `tbl_TicketData.account_created_date` | Local date table | Inactive/secondary — account creation timeline |
| `tbl_TicketData.ticket_created_date` | Local date table | Inactive/secondary |
| `tbl_TicketData.ticket_resolved_date` | Local date table | Inactive/secondary |
| `tbl_TicketData.issue_subcategory` | `dim_Issue.issue_subcategory` | Issue classification |
| `tbl_TicketData.region` | `dim_Region.region` | Region attributes |
| `tbl_WeatherDaily.region` | `dim_Region.region` | Region attributes |
| `tbl_WeatherDaily.weather_date` | `dim_Date.Date` | Weather by day |
| `dim_NZPublicHoliday.holiday_date` | Local date table | Holiday calendar |

**Important for the agent:** there are three date columns on `tbl_TicketData`
(`created_date`, `ticket_created_date`, `ticket_resolved_date`) but only
`created_date` → `dim_Date` is the active relationship most measures use. If a
question is really about *resolution* dates specifically, the agent needs to
know to use `ticket_resolved_date` directly rather than assume `dim_Date`
filters apply to it.

---

## Key measures (existing DAX — reuse this logic, don't reinvent it)

| Measure | Logic |
|---|---|
| `Ticket Count` | `COUNTROWS(tbl_TicketData)` |
| `Open Tickets` / `Closed Tickets` | Ticket Count filtered by `status_standard` |
| `Average Resolution Hours` | `AVERAGE(resolution_time_hours)` |
| `SLA Breach Count` / `SLA Breach Rate` | Filtered by `is_sla_breached`, rate = breach ÷ total |
| `Escalated Tickets` / `Escalation Rate` | Filtered by `is_escalated` |
| `Tickets on Public Holidays` | Filtered by `dim_Date[Is Public Holiday]` |
| `Reporting Ticket Count` | Ticket Count constrained to **2024-01-01 to 2025-12-31** — the report's fixed reporting window |
| `Reporting Open Backlog` | Reporting Ticket Count, open and not cancelled |
| `Reporting Average Resolution/First Response Hours` | Averages within the reporting window |
| `Reporting SLA Breach/Compliance Rate` | Within reporting window |
| `Reporting Escalation Rate` | Within reporting window |
| `Reporting Average CSAT` | Within reporting window |
| `Reporting Public Holiday Tickets` | Within reporting window |
| `Reporting Rain Day Tickets` | Tickets in a region/day where `tbl_WeatherDaily.is_rain_day = TRUE`, joined via `TREATAS` on region + date |

**Note the "Reporting ___" pattern**: nearly every headline measure has a
version hard-filtered to Jan 2024–Dec 2025. If a manager asks about a date
outside that window, the plain measures (`Ticket Count`, `Average Resolution
Hours`, etc.) are the ones to use instead — the agent should know both exist
and pick the right one.

---

## Notes for building the agent (your step 2 decision)

- This model is **Import mode from a local Excel file**, not a live database,
  and there's no sign of Premium/Fabric capacity. That rules out a persistent
  XMLA/DAX connection unless you buy capacity later.
- Two realistic paths:
  1. **Fastest to prototype**: while Power BI Desktop has this file open, it
     hosts a local Analysis Services instance you can query with DAX (via
     `pyadomd` or ADOMD.NET) — great for testing, but only works while
     Desktop is open on your machine, not for a deployed agent.
  2. **For something that actually runs standalone**: export the model's
     tables to a small local database (SQLite/DuckDB) and reimplement the
     measures above as SQL. This is the path the prototype script uses.
