"""
Create Supabase tables for Gotham Fitness AI Agent.
Run: python scripts/setup_db.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import psycopg2

# Try multiple host formats
hosts = [
    f"db.{os.getenv('SUPABASE_URL', '').replace('https://', '').replace('.supabase.co', '')}.supabase.co",
    "db.dnchrsbxpsvijgerhqpu.supabase.co",
    "aws-0-us-east-1.pooler.supabase.com",
]

password = os.getenv("SUPABASE_DB_PASSWORD", "")
if not password:
    print("[!] SUPABASE_DB_PASSWORD not set in environment.")
    print("    Add it to your .env file or set it as an environment variable.")
    sys.exit(1)

conn = None
for host in hosts:
    try:
        print(f"Trying host: {host}")
        conn = psycopg2.connect(
            host=host,
            port=5432,
            dbname="postgres",
            user="postgres",
            password=password,
            connect_timeout=10,
        )
        print(f"Connected to {host}!")
        break
    except Exception as e:
        print(f"  Failed: {e}")

if not conn:
    print("\n[!] Could not connect to any host.")
    print("Please run the following SQL manually in your Supabase Dashboard > SQL Editor:")
    print("-" * 60)
    print("""
CREATE TABLE IF NOT EXISTS leads (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    email           TEXT UNIQUE,
    phone           TEXT,
    fitness_goals   TEXT,
    booked_slot     TEXT,
    session_summary TEXT,
    source          TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sessions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transcript  TEXT,
    model_used  TEXT,
    channel     TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE leads ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role full access on leads" ON leads FOR ALL USING (true);
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role full access on sessions" ON sessions FOR ALL USING (true);
""")
    sys.exit(1)

cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS leads (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    email           TEXT UNIQUE,
    phone           TEXT,
    fitness_goals   TEXT,
    booked_slot     TEXT,
    session_summary TEXT,
    source          TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS sessions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transcript  TEXT,
    model_used  TEXT,
    channel     TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
""")

# Enable RLS
try:
    cur.execute("ALTER TABLE leads ENABLE ROW LEVEL SECURITY;")
    cur.execute("ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;")
except Exception:
    pass  # May already be enabled

# Create policies (ignore if already exist)
try:
    cur.execute("""CREATE POLICY "Service role full access on leads" ON leads FOR ALL USING (true);""")
except Exception:
    conn.rollback()

try:
    cur.execute("""CREATE POLICY "Service role full access on sessions" ON sessions FOR ALL USING (true);""")
except Exception:
    conn.rollback()

conn.commit()
cur.close()
conn.close()
print("Tables created successfully!")
