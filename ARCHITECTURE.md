# 🦇 Gotham Fitness AI Concierge — The Complete Blueprint

This document is the **master blueprint** for the Gotham Fitness AI Voice Agent. It contains the full architecture, the exact "Zero-Cost" technology stack, and step-by-step instructions for cloning and rebuilding this exact system for *any* other client or business.

---

## 🏗 1. System Architecture & The "Zero-Cost" Stack

This project is engineered to handle enterprise-grade real-time voice conversations with **$0 monthly running costs** using highly optimized API tiering.

### A. The "Ears" (Speech-to-Text / STT)
*   **Primary:** **Groq API (`whisper-large-v3`)**
    *   *Why:* Blazing fast inference, 95%+ accuracy even with background noise.
    *   *Cost:* $0 (Free tier provides 14,400 audio requests/day).
*   **Fallback:** **Local Whisper (`base.en`)**
    *   *Why:* If the external API goes down or hits rate limits, the system falls back to processing audio locally on the server CPU. 

### B. The "Brain" (Large Language Models / LLM)
*   **Layer 1 & 2:** **Google Gemini 2.0 Flash**
    *   *Why:* Incredibly fast, handles complex tool-calling (calendar checking, database saving), and understands nuanced human conversation.
    *   *Cost:* $0 (Free tier gives 1,500 requests/day).
*   **Layer 3 (The Fallback):** **Groq API (`llama-3.3-70b-versatile`)**
    *   *Why:* If the gym gets a massive spike in traffic and Gemini hits its rate limit, the `AgentRouter` silently switches the conversation over to Groq's Llama 3 model. The user never notices the switch.
    *   *Cost:* $0 (14,400 requests/day buffer).

### C. The "Voice" (Text-to-Speech / TTS)
*   **Engine:** **Kokoro ONNX (`af_heart` voice profile)**
    *   *Why:* Runs 100% locally in-memory. No API limits, no latency from network requests, and sounds incredibly human and emotive.
    *   *Cost:* $0 forever.

### D. The Integrations (Memory & Actions)
*   **Database/CRM:** **Supabase (PostgreSQL)**. Stores leads and chat histories via Edge Webhooks.
*   **Scheduling:** **Google Calendar API**. Checks real-time availability and books slots.
*   **Notifications:** **Twilio SMS**. Texts the gym owner when a new high-intent lead is captured.

---

## 🛠 2. Cloning for a New Client (Step-by-Step Rebuild)

To deploy this exact voice agent for a *new* business (e.g., a dental clinic, a real estate agency, or another gym), follow these exact steps.

### Step 1: Clone the Repository
```bash
git clone https://github.com/koustavadhikari3195-bit/GOTHAM.git new-client-agent
cd new-client-agent
```

### Step 2: Set Up the Environment Variables (`.env`)
You need to generate free API keys for the new client. Create a `.env` file in the root directory:

```env
# AI APIs (Free Tiers)
GEMINI_API_KEY=your_gemini_key_here
GROQ_API_KEY=your_groq_key_here

# Supabase (Free Tier)
SUPABASE_URL=your_supabase_project_url
SUPABASE_SERVICE_KEY=your_supabase_service_role_key

# Google Calendar (Free Tier)
GOOGLE_CALENDAR_ID=client_email@gmail.com
GOOGLE_SERVICE_ACCOUNT_JSON={"type": "service_account", "project_id": "...", ...}

# Twilio (Trial/Pay-as-you-go)
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_token
TWILIO_PHONE_NUMBER=+1234567890
```

### Step 3: Modify the "Brain" (Prompt Engineering)
The *entire* personality of the AI lives in `backend/agent/system_prompt.py`. 
To rebrand the AI for a new client:
1.  Change the **Persona** (e.g., from "High-energy fitness coach" to "Calm, professional dental receptionist").
2.  Change the **Knowledge Base** (Location, Hours, Services offered, Pricing).
3.  Change the **Objective Flow** (What data do they need to collect? For a gym, it's fitness goals. For a dentist, it's insurance info and tooth pain symptoms).

### Step 4: Update the Tools/Skills
If the new client needs different actions performed, edit the files in `backend/skills/`:
*   `save_lead_to_db.py` (Update the JSON schema if the client wants to collect "budget" instead of "experience level").
*   `book_slot.py` (Update the calendar durations—e.g., a dental cleaning might be 60 mins instead of a 30 min gym intro).

### Step 5: Build & Run Locally
```bash
# Terminal 1: Build Frontend
cd frontend
npm install
npm run build

# Terminal 2: Run Backend
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## 🤫 3. "Secret Sauce" Details (Why this build is special)

When selling this architecture to clients, these are the technical marvels you should highlight:

### A. The "Greeting-First" Illusion & Latency Hiding
Most voice AI agents have a 3-5 second delay when you first connect. This build uses an asynchronous **Greeting-First Flow**:
1.  The instant the WebSocket opens, the backend fires the greeting text to the UI. The user reads it instantly (0ms latency).
2.  The TTS audio generates in the background (`asyncio.to_thread`) and arrives 1-2 seconds later.
3.  **Crucial:** The frontend microphone is explicitly locked and *never* turns on until the backend sends a `start_listening` signal (which ONLY fires after the audio finishes).

### B. Triple-Layer Echo Prevention (The Hardest Problem in Voice AI)
If the microphone stays on while the AI speaks, the AI will transcribe its own voice and "hallucinate" an infinite loop. This build solves it flawlessly in `App.jsx` and `useAudioStream.js`:
1.  **Hardware Mute:** The `streamRef.current.getAudioTracks()[0].enabled = false` physically mutes the mic during AI playback.
2.  **Chunk Discard:** Any audio chunks generated while `isPausedRef` is true are thrown in the trash.
3.  **Sender Guard:** The WebSocket absolutely refuses to send outgoing audio if `playingRef.current` is active.

### C. The 3.5-Second Whisper Window
Out of the box, `MediaRecorder` chunks audio arbitrarily. We explicitly set the chunking window to `3.5 seconds`. This is the "Goldilocks Zone" — it is long enough for the user to speak a complete, coherent sentence so Whisper has enough context to transcribe it accurately, but short enough that the conversation feels real-time.

### D. Out-Of-Memory (OOM) Protection
Hugging Face free spaces only provide 16GB of RAM. If you load Kokoro TTS (1GB) and Whisper (1GB) into memory simultaneously, the app crashes. 
**The Hack:** We offloaded the heavy STT lifting to the Groq API. We *removed* the local Whisper pre-load on server startup. Local Whisper is now wrapped in a lazy-loading function (`_load()`). It stays at 0MB RAM usage forever, unless Groq goes down, at which point it dynamically loads into memory as a failsafe.

---

## 🚀 4. Deployment to Production

The architecture is container-ready. 

**To deploy to Hugging Face Spaces (or Render/Heroku/AWS):**
1.  Ensure you have a `Dockerfile` that installs Linux audio dependencies:
    ```dockerfile
    RUN apt-get update && apt-get install -y ffmpeg libsndfile1
    ```
2.  Ensure your `requirements.txt` has `kokoro-onnx`, `soundfile`, `pydub`, and `groq`.
3.  Push to your remote host. The `FastAPI` instance will automatically serve the built `/frontend/dist` folder on the root `/` domain, meaning you don't need a complex Nginx setup or a separate Vercel frontend. It is an "All-in-One" monolithic deployment.
