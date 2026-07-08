# Extractor Reference

Concepts covered while building the Open-Meteo extractor for the `weather-etl` project. Grouped by topic, with the reasoning behind each decision — not just the code.

---

## 1. Why plain `requests` instead of the vendor SDK

Open-Meteo publishes example code using their `openmeteo_requests` SDK plus `requests_cache` and `retry_requests`. We deliberately **didn't** use it. Reasons:

- The SDK returns data in a **binary format (FlatBuffers)** read via method calls (`response.Hourly()`), which *hides* the raw structure — but seeing the raw shape is the whole point of a first extract.
- Plain `requests` returns readable **JSON** you can inspect directly.
- The SDK pulls in **4 dependencies**; plain `requests` needs **1**.
- REST concepts (endpoint, params, JSON, status codes) are **transferable** to every data job. The SDK only helps with Open-Meteo.

**Lesson:** a vendor's example is often more than you need. Recognizing that is a skill.

---

## 2. Virtual environments

A venv isolates a project's dependencies so they don't leak between projects or get corrupted by conflicts.

```
python -m venv .venv                    # create, INSIDE the project folder
.\.venv\Scripts\Activate.ps1            # activate (PowerShell)
```

- Prompt shows `(.venv)` when active.
- **Per-project** venv (inside `weather-etl`) is cleaner than a shared one — it keeps `requirements.txt` meaningful and prevents cross-project contamination.
- PowerShell gotcha: if activation is blocked ("running scripts is disabled"), run once:
  `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`

### The interpreter trap (important)
The **terminal** and VS Code's **Run button** use interpreters set *independently*. Activating in the terminal does NOT change the Run button.
- Fix the Run button: `Ctrl+Shift+P` → **Python: Select Interpreter** → pick the one whose path contains `weather-etl\.venv`.
- Check which interpreter runs: bottom **status bar** in VS Code (Run button), or in the terminal:
  ```
  python -c "import sys; print(sys.executable)"   # exact python.exe in use
  where python                                     # Windows: PATH priority
  ```
- **Diagnostic instinct:** when a script misbehaves, check *which environment* first. Half of "why is this broken" is "which env am I in."

---

## 3. Dependency management

```
pip install requests              # install into the active venv
pip freeze > requirements.txt     # record exact versions for reproducibility
```

- `requirements.txt` lets anyone (or future-you) recreate the environment.
- Commit it when dependencies change: `git commit -m "Add requests dependency"`.
- **Warning vs error:** pip's `Cache entry deserialization failed` is a *warning* (harmless, re-fetches). The `Successfully installed ...` line is what matters. Learn to tell warnings (proceed) from errors (stop).

---

## 4. Diagnosing environment errors

We hit a series of dependency errors and learned to read them **bottom-up**:

- `cannot import name 'filepost' from 'urllib3'` and `No module named 'urllib3.contrib'` — a library failing to import *its own* pieces = **corrupted/conflicting install**, not your code.
- Fix: don't play whack-a-mole with versions — **rebuild a clean venv** and install only what you need.
- `No module named 'requests'` — the *good* kind of error: an empty env honestly saying it's empty. Fixable with one `pip install`.

**Lesson:** errors get *cleaner* as you fix the environment. Gauging "is this my code, my environment, or a missing install?" is a core diagnostic skill.

---

## 5. Making the request

```python
url = "https://api.open-meteo.com/v1/forecast"
params = {
    "latitude": 35.924086,
    "longitude": -106.791974,
    "hourly": ["temperature_2m", "precipitation_probability"],
    "temperature_unit": "fahrenheit",
}
response = requests.get(url, params=params)   # params MUST be passed in
```

- **The bug we caught:** building a `params` dict but calling `requests.get(url)` — the params never get sent. Must be `requests.get(url, params=params)`.
- `requests` builds the query string for you. Print `response.url` to *confirm* params landed.
- `response.status_code` — `200` = OK.
- `response.json()` — parses the JSON body into a Python dict. This is what shows you the data.

---

## 6. Reading the Open-Meteo response structure

The JSON has two kinds of content:

- **Metadata** (one value each): `latitude`, `longitude`, `elevation`, `timezone`, `utc_offset_seconds`, `hourly_units`.
- **Measurements** under `hourly`: **parallel arrays** — `time`, `temperature_2m`, `precipitation_probability` — aligned **by index** (temp[0] belongs to time[0]).

Key takeaways that drive the schema:
- Data arrives **columnar** (lists); a DB table is **row-oriented**. The transform pivots columns → rows.
- **Natural key** = `location + timestamp` (each timestamp appears once per location).
- **Timezone gotcha:** default is GMT/UTC with no offset marker. Decide to store everything in UTC, convert for display later.
- **Units live in the data** (`hourly_units`) — store them rather than assume.
- The API snaps coordinates to its grid (you send `13.41`, it echoes `13.419998`) — store the location you *asked for* as the key.

---

## 7. Structuring as a function

```python
def extractor():
    ...
    return response.json()      # RETURN data, don't print inside
```

- A function that **returns** data (vs printing internally) is **composable** — the caller decides what to do. This is what lets the transformer consume it: `transformer(data)`.
- Separation of concerns: the extractor's job is fetch-and-return; printing/logging config belong elsewhere.

---

## 8. Error handling

Three distinct failure categories, each handled differently:

1. **Request never completes** (network down, timeout) → `requests.get()` raises.
2. **Server says no** (4xx/5xx) → response returns, but `.json()` on an error body = silent bad data. Guard with `response.raise_for_status()`.
3. **Body isn't what you expect** (malformed JSON) → `.json()` raises a *decode* error (NOT a `RequestException` — a seam left for later).

Tools:
- `timeout=10` on the request — without it, a hung server hangs forever.
- `response.raise_for_status()` — turns bad statuses into catchable exceptions.
- `requests.exceptions.RequestException` — the parent that catches connection/timeout/HTTP errors in one net.

---

## 9. Fail loud vs fail soft

The core design decision when a fetch fails:

- **Fail soft** (`return None`): pipeline continues, but every caller must check for `None` — pushes complexity outward.
- **Fail loud** (`raise`): pipeline **stops** with a traceback. For ETL feeding a database, this is usually right — silently loading bad/missing data is worse than stopping.

We chose **fail loud**. Bonus: it *removes* the defensive `None`-checking that fail-soft forces on callers.

A bare `raise` re-throws the caught exception (preserving type + traceback). The `except` block earns its place only if it does something useful first — like logging context.

---

## 10. Logging

```python
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# inside except:
logging.error(f"Extraction failed for ({lat}, {lon}): {e}")
```

- `logging` beats `print`: severity levels, timestamps, filterable, routable to files.
- **`basicConfig` goes at module/entry level, NOT inside a function** — it's meant to run once; calls after the first are ignored.
- Include **context** in messages (location, the exception `e`) — a bare "failed" is useless at 2am.
- `logging.exception(...)` inside an `except` auto-includes the traceback — useful when you log-and-don't-raise.

---

## 11. Testing failure deliberately

Set `timeout=0.01` to *force* a timeout and confirm the error path fires — you should see your formatted `ERROR` log line **and** a traceback (fail-loud working). Then set it back to `10` for real use.

**Lesson:** don't trust error handling you haven't watched fire.

### Reading a traceback
- Read the **exception type at the very bottom** first.
- Find the frames mentioning **your file** (`extractor.py`) — skip the library internals.
- That scan turns a 60-line traceback into the 2 lines that matter.

---

## Final extractor (reference)

```python
import requests
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

def extractor():
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": 35.924086,
        "longitude": -106.791974,
        "hourly": ["temperature_2m", "precipitation_probability"],
        "temperature_unit": "fahrenheit",
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Extraction failed: {e}")
        raise
```

### Open seams for later hardening
- Catch JSON decode errors separately (category 3 above).
- Retry logic for transient failures (`429`, blips) — pairs with orchestration.
- Lift `params` (location, variables) out to config to support multiple cities.
