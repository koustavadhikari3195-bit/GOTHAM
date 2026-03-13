"""
Prevents Supabase free tier from pausing after 7 days of inactivity.

Setup (Linux/Mac crontab):
  crontab -e
  Add line: 0 9 * * * /path/to/venv/bin/python /path/to/scripts/keep_db_alive.py

Setup (Windows Task Scheduler):
  Action: python C:\\path\\to\\scripts\\keep_db_alive.py
  Trigger: Daily at 9:00 AM
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from supabase import create_client
from datetime import datetime


def ping():
    db = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_KEY")
    )
    result = db.table("leads").select("id").limit(1).execute()
    count  = len(result.data)
    print(f"[{datetime.now().isoformat()}] ✅ Supabase alive — {count} lead(s) in DB")


if __name__ == "__main__":
    ping()
