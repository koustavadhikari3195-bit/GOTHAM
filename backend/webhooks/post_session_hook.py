import logging
from datetime import datetime
from supabase import create_client

logger = logging.getLogger("gotham-agent.hooks")


async def run_hook(transcript: list[dict],
                   lead_data:  dict,
                   summary:    str,
                   channel:    str = "web"):
    """
    Runs automatically after every session (web or phone).
    1. Updates lead record with trainer summary
    2. Saves full session transcript
    3. Tags the lead with which channel they came from
    """
    try:
        from backend.config import config
        if not config.SUPABASE_URL or not config.SUPABASE_SERVICE_KEY:
            logger.warning("Skipping post-session hook: Supabase credentials missing (URL or Service Key)")
            return

        db = create_client(
            config.SUPABASE_URL,
            config.SUPABASE_SERVICE_KEY
        )

        # Format transcript as readable text
        transcript_text = "\n".join(
            f"[{t['role'].upper()}]: {t['text']}"
            for t in transcript
        )

        # Update lead record
        update_payload = {
            "session_summary": summary,
            "source":          f"voice_agent_{channel}",
            "updated_at":      datetime.utcnow().isoformat(),
        }

        if lead_data.get("email"):
            db.table("leads").update(update_payload) \
              .eq("email", lead_data["email"]).execute()
        elif lead_data.get("name"):
            db.table("leads").update(update_payload) \
              .eq("name", lead_data["name"]).execute()

        # Save session log
        db.table("sessions").insert({
            "transcript": transcript_text,
            "model_used": "gemini-2.5-flash/groq-fallback",
            "channel":    channel,
        }).execute()

        logger.info(
            f"[{channel.upper()}] Session saved | "
            f"Lead: {lead_data.get('name', 'Unknown')} | "
            f"Turns: {len(transcript)}"
        )

    except Exception as e:
        logger.error(f"Post-session hook error: {e}", exc_info=True)
