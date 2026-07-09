from transformer import transformer
from extractor import extractor
import datetime

data = extractor()

issue_date = datetime.datetime.now(datetime.timezone.utc)
schema_location, readings = transformer(data, issue_date)

print(schema_location)
print(readings)