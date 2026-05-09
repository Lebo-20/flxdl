import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.environ.get("DATABASE_URL")

def check_db():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    # Check columns
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'processed_dramas';")
    cols = [c[0] for c in cur.fetchall()]
    print(f"Columns: {cols}")
    
    cur.execute("SELECT * FROM processed_dramas ORDER BY created_at DESC LIMIT 10;")
    rows = cur.fetchall()
    for row in rows:
        print(row)
    cur.close()
    conn.close()

if __name__ == "__main__":
    check_db()
