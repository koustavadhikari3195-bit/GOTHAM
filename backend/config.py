import os
from dotenv import load_dotenv
load_dotenv()


class Config:
    # --- AI ---
    GEMINI_API_KEY       = os.getenv("GEMINI_API_KEY")
    GROQ_API_KEY         = os.getenv("GROQ_API_KEY")

    # --- Database ---
    SUPABASE_URL         = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

    # --- Google Calendar ---
    GOOGLE_CALENDAR_ID   = os.getenv("GOOGLE_CALENDAR_ID")
    GOOGLE_SA_JSON       = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")

    # --- Twilio ---
    TWILIO_ACCOUNT_SID   = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN    = os.getenv("TWILIO_AUTH_TOKEN")
    TWILIO_PHONE_NUMBER  = os.getenv("TWILIO_PHONE_NUMBER")

    # --- Server ---
    APP_DOMAIN           = os.getenv("APP_DOMAIN", "localhost:8000")
    PORT                 = int(os.getenv("PORT", 8000))
    FRONTEND_URL         = os.getenv("FRONTEND_URL", "http://localhost:5173")
    ENVIRONMENT          = os.getenv("ENVIRONMENT", "development")

    # --- CORS ---
    # Comma-separated list of allowed origins for production
    ALLOWED_ORIGINS      = os.getenv("ALLOWED_ORIGINS", "")

    # --- Gym timezone (Fleetwood, NY) ---
    GYM_TIMEZONE         = os.getenv("GYM_TIMEZONE", "America/New_York")

    @classmethod
    def get_allowed_origins(cls) -> list[str]:
        """Build the full list of allowed CORS origins."""
        origins = []
        if cls.FRONTEND_URL:
            # Trim trailing slashes for exact matching
            origins.append(cls.FRONTEND_URL.rstrip("/"))
        
        if cls.ALLOWED_ORIGINS:
            origins.extend([o.strip().rstrip("/") for o in cls.ALLOWED_ORIGINS.split(",") if o.strip()])
        
        # Add common local origins if in development
        if cls.ENVIRONMENT.lower() != "production":
            origins.extend([
                "http://localhost:5173",
                "http://localhost:5174",
                "http://127.0.0.1:5173",
            ])
        
        # Ensure we return a unique list
        return list(set(origins))

    @classmethod
    def is_production(cls) -> bool:
        return cls.ENVIRONMENT == "production"

    @classmethod
    def validate(cls):
        required = ["GEMINI_API_KEY", "GROQ_API_KEY",
                    "SUPABASE_URL", "SUPABASE_SERVICE_KEY"]
        missing = [k for k in required if not getattr(cls, k)]
        if missing:
            raise ValueError(f"[!] Missing env vars: {missing}")
        print(f"[+] Config validated (env={cls.ENVIRONMENT})")


config = Config()
