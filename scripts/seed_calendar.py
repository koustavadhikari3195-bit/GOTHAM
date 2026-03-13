"""
Populates your Google Calendar with test Introductory Session slots
so you can test the check_calendar and book_slot skills.

Usage:
  python scripts/seed_calendar.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta

SCOPES = ["https://www.googleapis.com/auth/calendar"]

def seed():
    creds = service_account.Credentials.from_service_account_file(
        os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"), scopes=SCOPES
    )
    svc    = build("calendar", "v3", credentials=creds)
    cal_id = os.getenv("GOOGLE_CALENDAR_ID")

    # Create slots for the next 14 days
    base   = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
    times  = [9, 10, 11, 14, 15, 17]   # hours
    created = 0

    print(f"Seeding calendar: {cal_id}")

    for day_offset in range(1, 15):
        date = base + timedelta(days=day_offset)

        # Skip Sundays
        if date.weekday() == 6:
            continue

        for hour in times:
            start_dt = date.replace(hour=hour)
            end_dt   = start_dt + timedelta(hours=1)

            event = {
                "summary":     "Introductory Session",
                "description": "Free 60-minute intro session for new Gotham Fitness members.",
                "start": {"dateTime": start_dt.isoformat(), "timeZone": "America/New_York"},
                "end":   {"dateTime": end_dt.isoformat(),   "timeZone": "America/New_York"},
                "colorId": "2",   # green
            }

            try:
                result = svc.events().insert(calendarId=cal_id, body=event).execute()
                print(f"  [+] Created: {start_dt.strftime('%a %b %d at %I:%M %p').lstrip('0')}")
                created += 1
            except Exception as e:
                print(f"  [!] Failed to create slot at {start_dt.isoformat()}: {e}")

    print(f"\nDone - {created} slots created on your calendar")


if __name__ == "__main__":
    seed()
