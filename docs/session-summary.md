# Session Summary — Open-Meteo Pipeline & Data Modeling

A recap of today's work on the `weather-etl` project. Two topics (git setup and the extractor) have their own dedicated reference docs — this focuses on the arc of the day and goes deep on the **new** material: choosing a data source, the design questions, and the two-table data model.

---

## The arc of today

1. Reviewed ETL core concepts and concluded PDF sourcing is too fragile — decided to move to an API.
2. Evaluated API options and **locked in Open-Meteo**.
3. Worked through the **design questions** you should ask before building a pipeline.
4. Chose a practice target: **forecast vs. actual**.
5. Built the **extractor** (own reference doc): plain `requests`, venv, error handling, fail-loud, logging.
6. Started the **transformer**: array-length validation + the two-table data model.

---

## Why Open-Meteo, and the source-selection principle

**Guiding principle:** prefer sources *designed to be read by machines*. PDFs and web scraping are presentation formats — you reverse-engineer their structure and it breaks on layout changes. APIs have a documented contract (endpoints, JSON, versioning).

Ranked options considered:
- **APIs (REST/JSON)** — highest transfer value; teaches pagination, auth, rate limits, retries, nested JSON. (Chose Open-Meteo here.)
- **CSV/flat files** — trivial but unavoidable; teaches encoding + schema drift.
- **Another database as source** — very common in real jobs; good for incremental extraction.
- **Spreadsheets (Google Sheets/Excel)** — lots of small-business data.
- *Skipped web scraping* — fragile in the same way as PDFs.

Open-Meteo specifics: free, **no API key**, 10,000 calls/day for non-commercial use.

---

## The design questions (ask these before any code)

1. **What is this data *for*?** Drives grain, keys, and tables. Even a *practice* target is needed so decisions aren't arbitrary.
2. **Extract:** which endpoint/params? What does one record represent, and what makes it unique (the natural key)? Full or incremental load, and how do you detect "new"?
3. **Load:** what schema/types/keys? Is the load safe to re-run (idempotent)?
4. **Transform:** what's the gap between raw JSON shape and your schema? (timezones, units, nulls, flattening)
5. **Operational:** how do you validate a run, know when it breaks (logging), and run it (orchestration later)?

---

## The chosen target: forecast vs. actual

Compare what was *forecast* against what *actually happened*.

**Why it's the richest learning target:** it forces using **two endpoints with different behavior**:
- **Forecast API** (`/v1/forecast`) — data is **mutable** (forecasts get revised each model run) → teaches **upsert**.
- **Historical/Archive API** (`/v1/archive`, ERA5) — data is **immutable** (past actuals never change) → teaches **append-only**.

**The key wrinkle — late-arriving data:** the archive runs ~2+ days behind real time, so you can't fetch an "actual" immediately. You forecast Tuesday today but can't get Tuesday's actual until later in the week. This is a real, named data-engineering problem most tutorials never expose.

**Trap avoided:** the forecast API's `past_days` param returns *past forecasts*, NOT actuals — the archive endpoint is the true ground truth.

**Scope chosen:** 3–5 locations, temperature + precipitation, "rich" forecast capture (stamp each forecast's issue-date so you can ask "how good was the 3-day-ahead forecast?").

---

## Reading the Open-Meteo response

Two kinds of content in the JSON:
- **Metadata** (one value each): `latitude`, `longitude`, `elevation`, `timezone`, `utc_offset_seconds`, `hourly_units`.
- **Measurements** under `hourly`: **parallel arrays** (`time`, `temperature_2m`, `precipitation_probability`) aligned by index.

Data arrives **columnar** (lists); a DB table is **row-oriented**. The transform's core job is pivoting columns → rows.

---

## Data modeling — the two-table design (today's main new topic)

Decided to **split into two related tables** (normalized) rather than one flat table, specifically to learn multi-table management and dimensional modeling.

### Why split
Sorting fields by what varies:
- **Per-timestamp** (changes every row): `time`, `temperature_2m`, `precipitation_probability`.
- **Per-location** (identical across all 168 rows): lat, long, elevation, timezone, offset, units.

A flat table repeats the per-location fields 168 times. Splitting stores each fact **once** and references it by key.

### The key concepts
- **Primary key** — uniquely identifies each row in a table.
- **Foreign key** — a column in one table holding the primary key value of a row in another, creating the link.
- **Surrogate key** — a meaningless auto-generated integer id (chosen here). Pros: single clean column to reference, stable, decoupled from the data, DB-generated.
- **Natural key** — real-world attributes that identify a row (e.g. `(latitude, longitude)`).

### The crucial insight
**A surrogate key alone does NOT prevent duplicates.** Running the pipeline twice would insert the same location as id 1 *and* id 2. To prevent this you also declare a **UNIQUE constraint on the natural key** — this is what makes upsert/idempotency possible. The surrogate is the *primary* key; the natural key is what enforces real-world uniqueness. A table needs both.

### The load ordering dependency
Because the surrogate id is generated *by the database*:
insert **location first** → capture its generated `id` → stamp that `id` onto all readings as their foreign key → insert readings.
"Insert parent, get key, insert children" — a fundamental multi-table pattern. Also: the parent table must be **created** before the child (can't point a foreign key at a table that doesn't exist).

### The final model

**`locations`**
- `location_id` — surrogate primary key (Postgres `INT GENERATED ALWAYS AS IDENTITY`)
- `latitude`, `longitude`, `elevation`, `timezone`, `utc_offset_seconds`, unit fields
- **UNIQUE (latitude, longitude)** — prevents duplicate locations

**`readings`**
- `reading_id` — surrogate primary key
- `location_id` — **foreign key** → `locations`
- `forecast_issued_date` — when the forecast was made (required for forecast-vs-actual)
- `time`, `temperature_2m`, `precipitation_probability`
- **UNIQUE (location_id, time, forecast_issued_date)** — the idempotency mechanism

**Why that 3-column unique key:** `location_id` distinguishes cities, `time` distinguishes target hours, `forecast_issued_date` distinguishes Monday's forecast from Sunday's forecast for the same target. Together they pin down exactly one prediction → enables `INSERT ... ON CONFLICT (...) DO UPDATE` so re-runs stay clean.

---

## Transformer progress

**Done:**
- Array-length **validation** up front — compares all three lengths to each other, `raise ValueError` with actual lengths on mismatch. Validating first also guarantees the pivot loop is safe.
- **Location record build** — pulls each field from the correct JSON spot (top-level metadata vs. nested `hourly_units`). `location_id` correctly left `None` (Postgres fills it on insert).

**Design notes learned:**
- A schema dict full of `None` is a *sketch of shape*, not data. The transform must *build filled-in rows*.
- Removed the `else:`/`print` test scaffolding — if validation doesn't raise, execution falls through; no `else` needed.
- Define/fetch `data` before building things from it (order matters).

**Parked for next time:** the **readings pivot loop** — walk the parallel arrays by index, build one dict per timestamp, append to a list, return it. The pattern (proven on toy data):
```python
readings = []
for i in range(temp_length):
    readings.append({
        "time": data["hourly"]["time"][i],
        "temperature_2m": data["hourly"]["temperature_2m"][i],
        "precipitation_probability": data["hourly"]["precipitation_probability"][i],
    })
```

---

## What's next

1. Finish the **readings pivot loop** and wrap the transformer in `def transformer(data):` returning its output.
2. Source `forecast_issued_date` (generate in Python, e.g. `datetime.date.today()`).
3. Confirm Postgres connection, create the `weather_etl` database.
4. Write `CREATE TABLE` statements (locations first, then readings) with identity PKs, the foreign key, and both UNIQUE constraints.
5. Build the **load** layer with upsert logic (`INSERT ... ON CONFLICT`).
6. Later: orchestration (Prefect/Dagster), dbt, additional locations.

---

## Commits made today
- Extractor with error handling / fail-loud / logging.
- Transformer: validate arrays + build location record.
