---
title: GOTHAM FITNESS
emoji: 🏋️
colorFrom: red
colorTo: black
sdk: docker
app_port: 7860
pinned: false
---

# Gotham Fitness AI Agent — Voice Concierge

A production-ready AI voice agent for gym lead generation and booking. Runs fully locally (Whisper/Kokoro) with LLM orchestration via Gemini and Groq.

## 🚀 Key Features
- **Voice-to-Voice Interaction**: Real-time STT and TTS using local models.
- **Gym-Specific Skills**: Checks Google Calendar for availability and books sessions.
- **Lead Capture**: Automatically saves visitor info (name, email, goals) to Supabase.
- **Resilient AI**: 3-layer routing (Gemini 1.5 → Gemini 2.0 → Groq Fallback).
- **Multi-Channel**: Supports Web (WebSocket) and Phone (Twilio/Mulaw).

## 🛠 Tech Stack
- **Backend**: FastAPI (Python 3.11)
- **STT**: OpenAI Whisper (`base.en`) — Local
- **TTS**: Kokoro TTS (ONNX) — Local
- **LLM**: Google Gemini 1.5/2.0 Flash & Groq Llama 3.3
- **Database**: Supabase (PostgreSQL)
- **Calendar**: Google Calendar API

## 💻 Local Setup

1. **Clone & Install**:
   ```bash
   git clone https://github.com/koustavadhikari3195-bit/GOTHAM.git
   cd GOTHAM/gotham-fitness-agent
   pip install -r requirements.txt
   ```

2. **Configure Environment**:
   Copy `.env.example` to `.env` and fill in your API keys.

3. **Install Dependencies**:
   - Install **FFmpeg** (required for Whisper).
   - Download models: `python scripts/download_models.py`

4. **Run Backend**:
   ```bash
   uvicorn backend.main:app --port 8000
   ```

5. **Run Frontend**:
   ```bash
   cd frontend
   npm install && npm run dev
   ```

## 🚢 Deployment

### Hugging Face Spaces (Backend)
The Space is configured to run via the included `Dockerfile`. Ensure all secrets are set in the HF Settings.

### Vercel (Frontend)
Point Vercel to the `frontend/` directory. Set `VITE_WS_URL` to your HF Space WebSocket URL.

## 📄 License
MIT
