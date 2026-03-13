import os
from supabase import create_client
from datetime import datetime


def run(name: str, email: str = None, phone: str = None,
        fitness_goals: str = None, booked_slot: str = None) -> dict:
    try:
        db = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_SERVICE_KEY")
        )

        record = {
            k: v for k, v in {
                "name":          name,
                "email":         email,
                "phone":         phone,
                "fitness_goals": fitness_goals,
                "booked_slot":   booked_slot,
                "updated_at":    datetime.utcnow().isoformat(),
            }.items() if v is not None
        }

        # Upsert on email to avoid duplicates
        if email:
            resp = db.table("leads").upsert(
                record, on_conflict="email"
            ).execute()
        else:
            resp = db.table("leads").insert(record).execute()

        lead_id = resp.data[0].get("id") if resp.data else None
        return {"success": True, "lead_id": lead_id, "name": name}

    except Exception as e:
        return {"success": False, "error": str(e)}
