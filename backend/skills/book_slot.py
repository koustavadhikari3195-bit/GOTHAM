import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def run(event_id: str, lead_name: str,
        lead_email: str = None, lead_phone: str = None) -> dict:
    try:
        creds = service_account.Credentials.from_service_account_file(
            os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"), scopes=SCOPES
        )
        svc    = build("calendar", "v3", credentials=creds)
        cal_id = os.getenv("GOOGLE_CALENDAR_ID")

        # Fetch existing event
        event = svc.events().get(calendarId=cal_id, eventId=event_id).execute()

        # Add attendee if email provided
        if lead_email:
            attendees = event.get("attendees", [])
            attendees.append({"email": lead_email, "displayName": lead_name})
            event["attendees"] = attendees

        # Update description with lead info
        event["description"] = (
            f"BOOKED VIA AI AGENT\n"
            f"Name:   {lead_name}\n"
            f"Email:  {lead_email or 'Not provided'}\n"
            f"Phone:  {lead_phone or 'Not provided'}\n"
            f"Source: Gotham Fitness AI Concierge"
        )

        updated = svc.events().update(
            calendarId  = cal_id,
            eventId     = event_id,
            body        = event,
            sendUpdates = "all"
        ).execute()

        return {
            "success":   True,
            "event_id":  updated["id"],
            "start":     updated["start"].get("dateTime"),
            "html_link": updated.get("htmlLink"),
        }

    except Exception as e:
        return {"success": False, "error": str(e)}
