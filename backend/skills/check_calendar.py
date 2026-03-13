import os
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

logger = logging.getLogger("gotham-agent.calendar")

SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Gym timezone — defaults to Eastern Time (Fleetwood, NY)
GYM_TZ = ZoneInfo(os.getenv("GYM_TIMEZONE", "America/New_York"))


def _service():
    creds = service_account.Credentials.from_service_account_file(
        os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"), scopes=SCOPES
    )
    return build("calendar", "v3", credentials=creds)


def _resolve_date(pref: str) -> datetime:
    """Resolve a natural-language date preference to a datetime in gym timezone."""
    now  = datetime.now(GYM_TZ)
    p    = pref.lower()
    days = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6}

    if "today"    in p: return now
    if "tomorrow" in p: return now + timedelta(days=1)

    for name, weekday in days.items():
        if name in p:
            delta = (weekday - now.weekday()) % 7 or 7
            return now + timedelta(days=delta)

    try:
        parsed = datetime.fromisoformat(pref)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=GYM_TZ)
        return parsed
    except ValueError:
        return now + timedelta(days=1)   # default: tomorrow


def run(date_preference: str, time_preference: str = "any") -> dict:
    try:
        svc  = _service()
        base = _resolve_date(date_preference)

        # Build time range in gym timezone then convert to UTC for API
        day_start = base.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end   = base.replace(hour=23, minute=59, second=59, microsecond=0)
        tmin = day_start.astimezone(ZoneInfo("UTC")).isoformat()
        tmax = day_end.astimezone(ZoneInfo("UTC")).isoformat()

        items = svc.events().list(
            calendarId   = os.getenv("GOOGLE_CALENDAR_ID"),
            timeMin      = tmin,
            timeMax      = tmax,
            maxResults   = 10,
            singleEvents = True,
            orderBy      = "startTime",
            q            = "Introductory Session"
        ).execute().get("items", [])

        slots = []
        for e in items:
            raw_start = e["start"].get("dateTime", e["start"].get("date"))
            dt        = datetime.fromisoformat(raw_start.replace("Z", "+00:00"))
            dt_local  = dt.astimezone(GYM_TZ)
            hour      = dt_local.hour

            # Filter by time preference
            if time_preference == "morning"   and not (6  <= hour < 12): continue
            if time_preference == "afternoon" and not (12 <= hour < 17): continue
            if time_preference == "evening"   and not (17 <= hour < 21): continue

            slots.append({
                "id":      e["id"],
                "title":   e.get("summary", "Introductory Session"),
                "start":   raw_start,
                "display": dt_local.strftime("%A, %B %d at %I:%M %p").replace(" 0", " "),
            })

        if not slots:
            return {
                "available": False,
                "message":   "No slots found for that day. Try a different date.",
                "slots":     []
            }

        return {"available": True, "slots": slots, "count": len(slots)}

    except Exception as e:
        logger.error(f"Calendar check error: {e}")
        return {"error": str(e), "available": False, "slots": []}
