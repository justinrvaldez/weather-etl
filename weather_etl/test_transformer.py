import pytest
from transformer import transformer

def test_transformer_raises_on_mismatched_arrays():
    # Build fake API data where the arrays are DIFFERENT lengths
    bad_data = {
        "latitude": 35.0, "longitude": -106.0, "elevation": 100.0,
        "timezone": "GMT", "utc_offset_seconds": 0,
        "hourly_units": {"time": "iso8601", "temperature_2m": "°F", "precipitation_probability": "%"},
        "hourly": {
            "time": ["2026-07-11T00:00", "2026-07-11T01:00"],   # 2 items
            "temperature_2m": [75.0],                            # 1 item -- MISMATCH
            "precipitation_probability": [10, 20],               # 2 items
        }
    }
    # Assert that calling the transformer with this raises ValueError
    with pytest.raises(ValueError):
        transformer(bad_data, "dummy")