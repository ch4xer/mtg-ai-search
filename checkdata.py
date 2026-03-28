import sqlite3
import json

conn = sqlite3.connect("backend/cards.db")
row = conn.execute("SELECT data FROM cards WHERE name LIKE ?", ("%Ur-dragon%",)).fetchone()
if row:
    print(json.dumps(json.loads(row[0]), indent=2, ensure_ascii=False))
conn.close()
