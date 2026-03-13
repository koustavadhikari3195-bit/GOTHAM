# 🏋️ Gotham Fitness AI Voice Agent

Voice-enabled AI concierge for fitness gyms. Handles both web visitors and phone calls.
Book intro sessions, capture leads, and manage calendar — entirely hands-free.

## Architecture

```
┌─────────────┐    WebSocket     ┌─────────────────────┐
│   Browser    │ ◄──────────────► │   FastAPI Backend    │
│  (React/Vite)│                  │                      │
└─────────────┘                  │  ┌─ AgentRouter ────┐│
                                 │  │ Gemini 2.5 Flash  ││
┌─────────────┐    TwiML/WS      │  │ Gemini Flash-Lite ││
│   Twilio     │ ◄──────────────► │  │ Groq Llama 3.3   ││
│  (Phone)     │                  │  └──────────────────┘│
└─────────────┘                  │                      │
                                 │  Tools:              │
                                 │  • check_calendar    │
                                 │  • book_slot         │
                                 │  • save_lead_to_db   │
                                 │                      │
                                 │  Voice:              │
                                 │  • Whisper STT       │
                                 │  • Kokoro TTS        │
                                 └──────────┬───────────┘
                                            │
                                 ┌──────────▼───────────┐
                                 │  Supabase (leads,     │
                                 │  sessions) + Google   │
                                 │  Calendar             │
                                 └──────────────────────┘
```

## Quick Start

```bash
# 1. Clone and set up
git clone https://github.com/yourname/gotham-fitness-agent
cd gotham-fitness-agent
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Copy env and fill in your keys
cp .env.example .env
# Edit .env with your API keys (see Environment Variables below)

# 3. Download TTS model files (one-time)
# Get kokoro-v0_19.onnx and voices.bin from:
# https://github.com/thewh1teagle/kokoro-onnx/releases

# 4. Set up Supabase tables
python scripts/setup_db.py

# 5. Test the agent brain (no voice needed)
python scripts/test_agent.py

# 6. Run backend
uvicorn backend.main:app --reload --port 8000

# 7. Run frontend (new terminal)
cd frontend && npm install && npm run dev

# 8. Open http://localhost:5173
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | ✅ | Google AI Studio API key |
| `GROQ_API_KEY` | ✅ | Groq console API key |
| `SUPABASE_URL` | ✅ | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | ✅ | Supabase service role key |
| `GOOGLE_CALENDAR_ID` | ✅ | Google Calendar ID for bookings |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | ✅ | Path to service account JSON |
| `TWILIO_ACCOUNT_SID` | Phone only | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | Phone only | Twilio auth token |
| `TWILIO_PHONE_NUMBER` | Phone only | Your Twilio phone number |
| `ENVIRONMENT` | No | `development` (default) or `production` |
| `ALLOWED_ORIGINS` | Production | Comma-separated CORS origins |
| `GYM_TIMEZONE` | No | Default: `America/New_York` |

## Phone Integration (Twilio)

```bash
# Test locally with ngrok
ngrok http 8000
# Set Twilio webhook to: https://YOUR-NGROK-URL/voice/incoming
```

## Deploy (Fly.io)

```bash
fly auth login
fly launch
fly secrets set GEMINI_API_KEY=... GROQ_API_KEY=... SUPABASE_URL=... \
  SUPABASE_SERVICE_KEY=... ENVIRONMENT=production \
  ALLOWED_ORIGINS=https://yourdomain.com
fly deploy
```

## Stack

| Layer    | Tool                        | Cost     |
|----------|-----------------------------|----------|
| AI       | Gemini 2.5 Flash + Groq 3.3 | $0/month |
| Database | Supabase                    | $0/month |
| STT      | Whisper (local)             | $0/month |
| TTS      | Kokoro (local)              | $0/month |
| Hosting  | Fly.io                      | $0/month |
| Phone    | Twilio (trial credit)       | $0 now   |
| **Total**|                             | **$0**   |

## Testing

```bash
# Agent brain test (CLI)
python scripts/test_agent.py

# Voice pipeline test (TTS + STT round-trip)
python scripts/test_audio_pipeline.py

# Individual module tests
python scripts/test_tts.py
python scripts/test_stt.py
```
