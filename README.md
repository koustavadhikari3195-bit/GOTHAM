---
title: GOTHAM Fitness AI Agent
emoji: 🦾
colorFrom: red
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# Gotham Fitness AI Agent - Backend

This is the Python-only backend for the Gotham Fitness AI Agent.
It provides a WebSocket endpoint for real-time voice interaction using Whisper (STT) and Kokoro (TTS).

## Deployment

This Space is configured to run the backend via Docker. 
Port: 7860
RAM: 16GB (HF Spaces Default)

### Environment Variables Required:
- `GEMINI_API_KEY`
- `GROQ_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `GOOGLE_SERVICE_ACCOUNT_JSON`
- `FRONTEND_URL`
- `ALLOWED_ORIGINS`
