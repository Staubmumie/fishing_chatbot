
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LANCE_DB_URI = DATA_DIR / "lance_db"
TABLE_NAME = "fishing_regulations"
import lancedb

db = lancedb.connect(str(LANCE_DB_URI))

#print(db.table_names())
table = db.open_table(TABLE_NAME)

print(table.schema)