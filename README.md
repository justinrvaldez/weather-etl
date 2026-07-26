# Weather ETL Pipeline

An automated ETL pipeline that extracts weather forecasts and historical observations from the Open-Meteo API, transforms them into a normalized relational schema, and loads them into PostgreSQL for forecast-accuracy analysis.

## Overview

This is a self-directed project built to learn modern data engineering patterns end to end. It collects two complementary datasets on a schedule — **forecasts** (what the model predicts) and **actuals** (what was actually observed) — so that forecast accuracy can be measured over time.

The project deliberately targets a REST API rather than PDFs or web scraping. Presentation formats require reverse-engineering their structure and break whenever a layout changes; an API provides a documented, stable contract. That choice drives most of what follows.

The pipeline runs unattended every six hours, is safe to re-run without duplicating data, logs to a file for debugging, and has automated tests covering its transformation logic.

## Architecture

The ETL pipeline has two extract paths that share a single load target.

```
                    ┌─────────────────────┐
                    │   Open-Meteo API    │
                    └──────────┬──────────┘
                               │
              ┌────────────────┴────────────────┐
              │                                 │
     /v1/forecast (7-day)              /v1/archive (ERA5)
       looks FORWARD                     looks BACKWARD
              │                                 │
              ▼                                 ▼
        extractor()                    extractor_actual()
              │                                 │
              ▼                                 ▼
       transformer()                  transformer_actual()
   validate → pivot to rows        validate → pivot to rows
              │                                 │
              └────────────────┬────────────────┘
                               ▼
                          loader.py
                  upsert location → capture id
                   → stamp id onto readings
                               │
                               ▼
                    ┌─────────────────────┐
                    │     PostgreSQL      │
                    │ locations           │
                    │ readings │ actuals  │
                    └─────────────────────┘
```

**Extraction** — Two endpoints. The forecast API returns a 7-day hourly outlook; the archive API (ERA5 reanalysis) returns observed historical weather. Both use plain `requests` with a timeout, status checking, and fail-loud error handling that logs context before re-raising.

**Transform** — The API returns *columnar* data (parallel arrays of times, temperatures, and precipitation). A database table is *row-oriented*, so the transform pivots columns into rows. Before pivoting, it validates that all parallel arrays are the same length and raises a `ValueError` if not — misaligned arrays would silently pair the wrong temperature with the wrong hour.

**Load** — The location is upserted first (`ON CONFLICT ... DO UPDATE ... RETURNING location_id`) to obtain its database-generated id, which is then stamped onto every reading as a foreign key. Readings are bulk-inserted with `ON CONFLICT ... DO NOTHING` so re-runs are safe.

### A note on late-arriving data

The two paths operate on different timelines. Forecasts describe the future; the ERA5 archive lags real time by several days. This means the actual for a given hour only becomes available well after the forecast for it was made, so the two datasets converge gradually as the pipeline runs. Comparison is a long-run payoff, not an immediate one.

### Idempotency

Re-running the pipeline within the same forecast window does not create duplicate rows. Two mechanisms make this work:

1. `forecast_issued` is snapped to the nearest 6-hour window (00/06/12/18 UTC) rather than the exact instant of execution, so repeated runs in the same window produce an identical key value.
2. Unique constraints on the fact tables give the `ON CONFLICT` clauses something to collide against.

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

Forecasts and observations are not symmetric, and the schema reflects that rather than forcing them into the same shape:

- A forecast reports a **probability** of precipitation (a percentage); an observation reports an **amount** (millimeters or inches). These are different measurements and cannot be compared directly because of differing dimensions.
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

## What I Learned

<!--
    Write this yourself — it's the section an interviewer is most likely to ask about,
    and it should sound like you. Some prompts, using things you actually worked through:

    - Why you moved from PDF extraction to an API, and what that taught you about
      choosing data sources.
    - What idempotency actually means in practice, and the bug that taught it to you
      (microsecond timestamps meant nothing ever collided).
    - Discovering the forecast/actual asymmetry by reading the API response instead of
      assuming the two datasets matched.
    - Why a surrogate key alone doesn't prevent duplicates.
    - What `DROP ... CASCADE` does, learned the hard way.
    - Why `ON CONFLICT DO NOTHING` was wrong for locations but right for readings.
    - How to test code that depends on the current time.
-->

## License

MIT
