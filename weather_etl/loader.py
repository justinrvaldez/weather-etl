import psycopg
import datetime
import os

from transformer import transformer
from extractor import extractor
from dotenv import load_dotenv

load_dotenv()

# issue_date = datetime.datetime.now(datetime.timezone.utc)
# schema_location, readings = transformer(extractor(), issue_date)

connection = psycopg.connect(
    host=os.getenv("DB_HOST"),
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    port=os.getenv("DB_PORT")
)

cursor = connection.cursor()
cursor.execute("SELECT version();")
print(cursor.fetchone())

cursor.close()
connection.close()