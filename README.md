# Weather ETL Pipeline

An automated ETL pipeline that extracts weather forecasts and historical observations from the Open-Meteo API, transforms them into a normalized relational schema, and loads them into PostgreSQL for forecast-accuracy analysis.

Framed against Ralph Kimball's *The Data Warehouse Toolkit*, this project is the **data warehousing (DW)** half of the DW/BI (business intelligence) lifecycle: it builds the clean, queryable, dimensionally-modeled store that analysis is run against. The **BI** half — dashboards, reporting, and other deliverables — is a separate process with its own set of questions and design principles, and is intentionally out of scope here. It will be explored in a future project.

## Overview

This is a self-directed project built to learn modern data engineering patterns end to end. Like I mentioned in the previous heading, this is the DW portion of the DW/BI framwork outlined in The Data Warehousing Toolkit. It collects two complementary datasets on a schedule — **forecasts** (what the model predicts) and **actuals** (what was actually observed) — so that forecast accuracy can be measured over time. Without domain specific knowledge I was not able to design a BI question that may be answered with this information that would be meaningful.

The project deliberately targets a REST API rather than PDFs or web scraping. Presentation formats (PDFs, docx, ppt, etc) require data scientist reverse-engineering their structure and break whenever a layout changes; an API provides a documented, stable contract. That choice drives most of what follows.

The pipeline runs unattended every six hours, is safe to re-run without duplicating data, logs to a file for debugging, and has automated tests covering its transformation logic.

## Architecture

The ETL pipeline has two extract paths that share a single load target.

**Extraction** — Two endpoints. The forecast API returns a 7-day hourly outlook; the archive API (ERA5 reanalysis) returns observed historical weather. Both use plain `requests` with a timeout, status checking, and fail-loud error handling that logs context before re-raising.

**Transform** — The API returns *columnar* data (parallel arrays of times, temperatures, and precipitation). A database table is *row-oriented*, so the transform pivots columns into rows. Before pivoting, it validates that all parallel arrays are the same length and raises a `ValueError` if not — misaligned arrays would silently pair the wrong temperature with the wrong hour.

Row dictionaries (row-oriented, ready to insert). These are parallel arrays and if the len() of the returned data differs betweem any array then a ValueError fires.
┌───────────────────────────────────────────────────────────┐
│ { "time": 00:00, "temperature_2m": 75.0, "precipitation": 0.0 } │
│ { "time": 01:00, "temperature_2m": 72.5, "precipitation": 0.1 } │
│ { "time": 02:00, "temperature_2m": 70.2, "precipitation": 0.0 } │
└───────────────────────────────────────────────────────────┘

**Load** — The location is upserted first (`ON CONFLICT ... DO UPDATE ... RETURNING location_id`) to obtain its database-generated id, which is then stamped onto every reading as a foreign key. Readings are bulk-inserted with `ON CONFLICT ... DO NOTHING` so re-runs are safe.

### A note on late-arriving data

The two paths operate on different timelines. Forecasts describe the future; the ERA5 archive lags real time by several days. This means the actual for a given hour only becomes available well after the forecast for it was made, so the two datasets converge gradually as the pipeline runs. The archived data lags behind forcasted data by ten days. So from runtime start, 10 days had to pass before we could join datasets together in any meaningful way.

### Idempotency

Re-running the pipeline within the same forecast window does not create duplicate rows. Two mechanisms make this work:

1. `forecast_issued` is snapped to the nearest 6-hour window (00/06/12/18 UTC) rather than the exact instant of execution, so repeated runs in the same window produce an identical key value. These 6 hour windows come from the fact that the weather data is updated in 6 hour intervals. The original idea was to run the program at 1 hour intervals. This caused a large volume of records to be returned and many of these records were duplicates of records that were part of the 6 hour window.
2. Unique constraints on the fact tables give the `ON CONFLICT` clauses creates a check so that duplicates are not created.

## Tech Stack

| Component | Choice |
|---|---|
| Language | Python 3.14 |
| HTTP | `requests` |
| Database | PostgreSQL |
| DB driver | `psycopg` (v3) |
| Config / secrets | `python-dotenv` |
| Testing | `pytest` |
| Scheduling | Windows Task Scheduler |
| Data source | Open-Meteo API (no key required) |

## Database Schema

A dimensional model: one dimension table (`locations`) referenced by two fact tables (`readings` and `actuals`).

**`locations`** — one row per location. Surrogate primary key, plus a unique constraint on the natural key.

| Column | Type | Notes |
|---|---|---|
| `location_id` | `INT` identity | Primary key, database-generated |
| `latitude` | `DOUBLE PRECISION` | `NOT NULL` |
| `longitude` | `DOUBLE PRECISION` | `NOT NULL` |
| `elevation` | `DOUBLE PRECISION` | |
| `timezone` | `TEXT` | |
| `utc_offset_seconds` | `INTEGER` | |
| `unit_time` | `TEXT` | |
| `unit_temp` | `TEXT` | |

`UNIQUE (latitude, longitude)` — prevents duplicate locations and enables the upsert.

**`readings`** — forecast data.

| Column | Type | Notes |
|---|---|---|
| `reading_id` | `INT` identity | Primary key |
| `location_id` | `INT` | Foreign key → `locations` |
| `forecast_issued` | `TIMESTAMPTZ` | When the forecast was made |
| `time` | `TIMESTAMP` | Target hour being forecast |
| `temperature_2m` | `DOUBLE PRECISION` | |
| `precipitation_probability` | `INTEGER` | Percent chance |

`UNIQUE (location_id, time, forecast_issued)` — three columns, because the same target hour can be forecast on multiple issue dates.

**`actuals`** — observed data.

| Column | Type | Notes |
|---|---|---|
| `reading_id` | `INT` identity | Primary key |
| `location_id` | `INT` | Foreign key → `locations` |
| `time` | `TIMESTAMP` | Observed hour |
| `temperature_2m` | `DOUBLE PRECISION` | |
| `precipitation` | `DOUBLE PRECISION` | Amount in mm |

`UNIQUE (location_id, time)` — two columns, because observed reality happens exactly once per hour.

### Why the two fact tables differ

Forecasts and observations are not symmetric as explained below:

- A forecast reports a **probability** of precipitation which is reported as a percentage (%); an observation reports an **amount** (millimeters or inches). These are different measurements and cannot be compared directly through dimensional analysis.
- A forecast for a given hour can be issued repeatedly as the date approaches, so it needs `forecast_issued` to be uniquely identified. An observation happens once, so it does not.

Temperature is symmetric (°F in both), which makes it the clean basis for accuracy comparison.

### `forecast_accuracy` view

A view joins the two fact tables on `location_id` **and** `time`, pairing each forecast with the observation for the same hour and computing the temperature error. Joining on location alone would produce a Cartesian product of unrelated hours.

All timestamps are stored in UTC (`TIMESTAMPTZ`) and converted only for display.

## Setup

**Prerequisites:** Python 3.11+, PostgreSQL, and Git.

```bash
# 1. Clone
git clone https://github.com/<your-username>/weather-etl.git
cd weather-etl

# 2. Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1     # Windows PowerShell
# source .venv/bin/activate      # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt
```

**4. Create the database and schema**

```sql
CREATE DATABASE weather_etl;
```

Then run `schema.sql` against it to create the tables and view. Order matters — `locations` must exist before the fact tables that reference it.

**5. Configure credentials**

Copy `.env.example` to `.env` and fill in your database password:

```dotenv
DB_PASSWORD=your_password_here
DB_USER=postgres
DB_NAME=weather_etl
DB_HOST=localhost
DB_PORT=5432
```

`.env` is git-ignored and never committed. The Open-Meteo API requires no key.

**6. Configure the location**

Edit `config.py` to set the coordinates you want to collect:

```python
LOCATIONS = [
    {"name": "Los Alamos", "latitude": 35.824086, "longitude": -106.791974},
]

ARCHIVE_LAG_DAYS = 10
```

`ARCHIVE_LAG_DAYS` controls how far back the archive extract reaches. It must exceed the ERA5 publication lag.

## Usage

Run the pipeline manually:

```bash
python weather_etl/loader.py
```

Run the tests:

```bash
pytest -v
```

Check the results:

```sql
SELECT COUNT(*) FROM readings;
SELECT COUNT(*) FROM actuals;
SELECT * FROM forecast_accuracy ORDER BY time;
```

Each run appends to `weather_etl.log` with timestamps, severity levels, and full tracebacks on failure — so unattended runs leave a diagnosable record.

### Scheduling

The pipeline is scheduled to run every six hours, shortly after Open-Meteo publishes new model output (00/06/12/18 UTC). On Windows, Task Scheduler invokes the virtual environment's interpreter directly:

- **Program:** `<project>\.venv\Scripts\python.exe`
- **Arguments:** `<project>\weather_etl\loader.py`
- **Start in:** `<project>`

The `forecast_window()` function floors the run time to its 6-hour bucket, so the schedule does not need to fire at the exact boundary.

## Roadmap

**Done**
- Forecast extract, transform, and load
- Historical actuals extract via the ERA5 archive
- Normalized three-table schema with foreign keys and unique constraints
- Idempotent upserts safe against re-runs
- Fail-loud error handling with contextual logging
- File-based logging for unattended runs
- Unit tests for transformation and window logic
- Config and secrets separated from code
- Scheduled execution every six hours

**Planned**
- Multiple locations in a single run, with per-location error isolation
- Precipitation accuracy analysis (probability vs. observed occurrence)
- Orchestration with Prefect or Dagster — retries, dependency management, run observability
- dbt for the transformation and analytics layer
- Mocked API responses in tests, removing the network dependency
- Containerization with Docker
- Aggregate accuracy metrics by forecast lead time
- Multi user git and version control to price workiung within a team

## What I Learned

I built this to learn the basics of data warehousing and to put a real framework behind workflow processes I'd already been doing informally at a previous job. The main things I picked up:

**Schema design** — modeling data as facts and dimensions instead of one flat table, and thinking about what a single row represents before choosing columns.
**Relational keys** — the difference between surrogate keys (for referencing) and natural keys (for uniqueness), why a table often needs both, and how foreign keys tie the tables together. A surrogate primary key alone doesn't stop duplicates; a unique constraint on the natural key does.
**Idempotency** — making the pipeline safe to re-run without duplicating data, using unique constraints, ON CONFLICT upserts, and snapping the forecast time to a fixed window.
**ETL architecture** — splitting the work into separate extract, transform, and load stages, and reshaping the API's parallel arrays into rows.
**API connections** — pulling from a REST API with timeouts, status checks, and fail-loud error handling, instead of relying on fragile PDF or scraping approaches.
**SQL** — writing inserts, upserts, and the join that compares forecasts to actuals, and saving it as a view. Also learned why table order matters after a DROP ... CASCADE took out more than I expected.
**Windows Task Scheduler** — running the pipeline unattended on a schedule, and the practical details that come with it: using the venv's interpreter, setting the working directory, and logging to a file so a failed run leaves a record.
**Project setup** — .gitignore for secrets and generated files, .env with a committed .env.example, requirements.txt for dependencies, and Git for version control on a solo project.
**Documentation** — writing this README in Markdown so the project makes sense to someone seeing it for the first time.

## License

MIT
