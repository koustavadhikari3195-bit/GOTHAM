import json
import base64
import logging
import uuid
import contextvars
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pathlib import Path
import os

from backend.config import config
from backend.agent.agent_router       import AgentRouter
from backend.voice.stt                import transcribe
from backend.voice.tts                import speak
from backend.voice.twilio_handler     import get_twilio_xml, validate_twilio_signature
from backend.voice.audio_converter    import mulaw_to_wav, wav_to_mulaw
from backend.webhooks.post_session_hook import run_hook

# ==============================================================================
# LOGGING SETUP
# ==============================================================================
# Use a simple format for the root logger — no %(session_id)s here
# because third-party loggers (uvicorn, etc.) would crash.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("gotham-agent")

# Per-request session ID via contextvars (thread/async safe)
_session_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "session_id", default="no-session"
)


class _SessionFormatter(logging.Formatter):
    """Formatter that injects the current session ID from contextvars."""
    def format(self, record):
        record.session_id = _session_id.get("no-session")
        return super().format(record)


# Replace the root handler's formatter only for our logger
_handler = logging.StreamHandler()
_handler.setFormatter(_SessionFormatter(
    '%(asctime)s - %(name)s - %(levelname)s - [%(session_id)s] - %(message)s'
))
logger.handlers = [_handler]
logger.propagate = False


# ==============================================================================
# APP LIFESPAN
# ==============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    config.validate()
    
    async def warm_up():
        # Small delay to let the server start and pass healthcheck
        import asyncio
        await asyncio.sleep(2)
        try:
            from backend.voice.stt import _load as load_stt
            from backend.voice.tts import _load as load_tts
            logger.info("Warming up AI models in background...")
            
            # Load Whisper first (smaller footprint than Kokoro initially)
            await asyncio.to_thread(load_stt)
            logger.info("STT ready. Waiting 10s to stagger memory load...")
            await asyncio.sleep(10)
            
            # Load Kokoro after a breather
            await asyncio.to_thread(load_tts)
            logger.info("AI models warmed up and ready")
        except Exception as e:
            logger.error(f"Error during background model warm-up: {e}")

    # Kick off warm-up without blocking startup
    import asyncio
    asyncio.create_task(warm_up())
    logger.info("=== Gotham Fitness AI Agent -- Web + Phone ready ===")
    logger.info(f"    Environment : {config.ENVIRONMENT}")
    logger.info(f"    CORS origins: {config.get_allowed_origins()}")
    yield
    logger.info("Shutting down")


app = FastAPI(title="Gotham Fitness AI Agent", lifespan=lifespan)

# -- CORS Configuration --------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins   = config.get_allowed_origins(),
    allow_methods   = ["*"],
    allow_headers   = ["*"],
    allow_credentials = True,
)

# -- Serve built frontend at the BOTTOM ----------------------------------------
# This must be defined last so it doesn't intercept /health, /ws/*, etc.
def setup_frontend(app: FastAPI):
    _dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    if _dist.is_dir() and (_dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=str(_dist / "assets")), name="assets")

        @app.get("/{path:path}")
        async def serve_spa(path: str):
            """Serve the React SPA for any non-API route."""
            file = _dist / path
            if file.is_file():
                return Response(content=file.read_bytes(),
                                media_type="application/octet-stream")
            return Response(content=(_dist / "index.html").read_bytes(),
                            media_type="text/html")


# ==============================================================================
# HEALTH
# ==============================================================================
@app.get("/health")
def health():
    return {
        "status":  "ok",
        "channels": ["web", "phone"],
        "env":      config.ENVIRONMENT,
    }


# ==============================================================================
# WEB CHANNEL — browser voice session
# ==============================================================================
MAX_MESSAGE_SIZE = 5 * 1024 * 1024  # 5 MB safety cap on audio chunks

@app.websocket("/ws/session")
async def web_session(ws: WebSocket):
    """
    WebSocket handler for browser-based voice sessions.
    Handles: greeting, STT/TTS, user input, session logging.
    """
    session_id = str(uuid.uuid4())[:8]
    _session_id.set(session_id)

    await ws.accept()
    log = []
    agent = None

    async def send_response(text: str):
        """Synthesize speech and send to client."""
        try:
            logger.info(f"Synthesizing speech: {text[:50]}...")
            audio = await speak(text)
            if not audio:
                logger.warning("TTS returned EMPTY audio bytes")
                await ws.send_json({
                    "type":  "tts",
                    "text":  text,
                    "audio": ""
                })
            else:
                audio_size = len(audio)
                logger.info(f"Speech synthesized: {audio_size} bytes")
                await ws.send_json({
                    "type":  "tts",
                    "text":  text,
                    "audio": base64.b64encode(audio).decode()
                })
            log.append({"role": "assistant", "text": text})
        except Exception as e:
            logger.error(f"Error in send_response: {e}", exc_info=True)
            try:
                await ws.send_json({"type": "error", "message": "Failed to synthesize speech"})
            except Exception:
                pass

    try:
        logger.info("Initializing AgentRouter...")
        agent = AgentRouter()
        logger.info("AgentRouter ready")

        # Fast Opening Greeting (Hardcoded to avoid latency/429s)
        import random
        greetings = [
            "Welcome to Gotham Fitness! I'm your AI concierge. What brings you in today?",
            "Hey there! Welcome to Gotham. I'm here to help you get started. What are your fitness goals?",
            "Welcome to Gotham Fitness! Ready to crush some goals? I'm your AI concierge—how can I help you today?"
        ]
        greeting = random.choice(greetings)
        logger.info(f"Using fast greeting: {greeting}")
        await send_response(greeting)

        while True:
            data = await ws.receive()
            user_text = None

            # Voice audio bytes from browser mic
            if data.get("bytes"):
                raw = data["bytes"]
                logger.info(f"Received audio chunk: {len(raw)} bytes")
                if len(raw) > MAX_MESSAGE_SIZE:
                    logger.warning(f"Audio chunk too large ({len(raw)} bytes), skipping")
                    continue
                try:
                    user_text = transcribe(raw)
                    if user_text:
                        logger.info(f"STT result: '{user_text}'")
                        await ws.send_json({"type": "stt", "text": user_text})
                    else:
                        # Only log empty if it's not just a tiny blip
                        if len(raw) > 1000:
                            logger.debug("STT returned empty text for chunk")
                except Exception as e:
                    logger.error(f"Transcription error: {e}", exc_info=True)
                    continue

            # Text message (fallback / control signals)
            elif data.get("text"):
                try:
                    msg = json.loads(data["text"])
                    if msg.get("type") == "end_session":
                        logger.info("Client requested session end")
                        break
                    elif msg.get("type") == "text_input":
                        content = msg.get("content", "")
                        if content == "[PING]":
                            logger.info("Received reliability PING from frontend")
                            # If we already have a log, don't re-greet
                            if not log:
                                await send_response(greeting)
                            continue

                        if len(content) > 2000:
                            logger.warning("Text input too long, truncating")
                            content = content[:2000]
                        user_text = content.strip()
                        if user_text:
                            logger.info(f"Text input: {user_text}")
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}")
                    continue

            # Process user input if we have it
            if user_text:
                log.append({"role": "user", "text": user_text})
                try:
                    response = agent.chat(user_text)
                    await send_response(response)
                except Exception as e:
                    logger.error(f"Agent chat error: {e}", exc_info=True)
                    try:
                        await ws.send_json({"type": "error", "message": "Agent error"})
                    except Exception:
                        pass

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"Web session error: {e}", exc_info=True)
    finally:
        if agent and log:
            try:
                summary = agent.get_session_summary()
                await run_hook(log, agent.lead_data, summary, channel="web")
                logger.info("Post-session hook completed")
            except Exception as e:
                logger.error(f"Hook execution failed: {e}", exc_info=True)
        try:
            await ws.close()
        except Exception:
            pass


# ==============================================================================
# PHONE CHANNEL — Twilio integration
# ==============================================================================
@app.post("/voice/incoming")
async def handle_phone_call(request: Request):
    """
    Twilio calls this when someone dials the gym number.
    Returns TwiML that opens a WebSocket audio stream.
    """
    try:
        form   = await request.form()
        caller = form.get("From", "Unknown")

        # Validate Twilio signature in production
        if config.is_production():
            sig = request.headers.get("X-Twilio-Signature", "")
            url = str(request.url)
            if not validate_twilio_signature(url, dict(form), sig):
                logger.warning(f"Invalid Twilio signature from {caller}")
                return Response(status_code=403, content="Forbidden")

        logger.info(f"Incoming call from {caller}")
        xml = get_twilio_xml()
        return Response(content=xml, media_type="application/xml")

    except Exception as e:
        logger.error(f"Error handling incoming call: {e}", exc_info=True)
        error_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Say>Sorry, we encountered an error. Please try again later.</Say>
        </Response>"""
        return Response(content=error_xml, media_type="application/xml")


@app.websocket("/ws/phone")
async def phone_session(ws: WebSocket):
    """
    Twilio streams mulaw audio here in real time.
    We: decode -> Whisper -> AgentRouter -> Kokoro -> encode -> send back.
    """
    session_id = str(uuid.uuid4())[:8]
    _session_id.set(session_id)

    await ws.accept()
    logger.info("Phone WebSocket connected")

    agent: Optional[AgentRouter] = None
    log = []
    stream_sid: Optional[str] = None
    audio_buffer = bytearray()
    CHUNK_SIZE   = 8000   # ~1 second of 8kHz audio
    SILENCE_THRESHOLD = 2

    async def send_audio(text: str):
        """Convert agent text to mulaw audio and send to Twilio."""
        if not stream_sid:
            logger.error("stream_sid not set - cannot send audio")
            return
        try:
            wav_bytes   = await speak(text)
            if not wav_bytes:
                logger.warning("TTS returned empty audio")
                return
            mulaw_bytes = wav_to_mulaw(wav_bytes)
            payload     = base64.b64encode(mulaw_bytes).decode()
            await ws.send_json({
                "event":     "media",
                "streamSid": stream_sid,
                "media":     {"payload": payload}
            })
            log.append({"role": "assistant", "text": text})
        except Exception as e:
            logger.error(f"Error in send_audio: {e}", exc_info=True)

    try:
        agent = AgentRouter()

        while True:
            try:
                raw = await ws.receive_text()
            except WebSocketDisconnect:
                logger.info("Twilio WebSocket disconnected")
                break
            except Exception as e:
                logger.error(f"Error receiving from Twilio: {e}", exc_info=True)
                break

            try:
                event = json.loads(raw)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON from Twilio: {e}")
                continue

            etype = event.get("event")

            if etype == "start":
                stream_sid = event.get("start", {}).get("streamSid")
                logger.info(f"Phone stream started: {stream_sid}")
                if agent:
                    try:
                        greeting = agent.chat(
                            "Customer just called the gym by phone. "
                            "Greet them warmly and professionally."
                        )
                        await send_audio(greeting)
                    except Exception as e:
                        logger.error(f"Error generating greeting: {e}", exc_info=True)

            elif etype == "media":
                try:
                    payload = event.get("media", {}).get("payload")
                    if not payload:
                        continue
                    chunk = base64.b64decode(payload)
                    audio_buffer.extend(chunk)

                    if len(audio_buffer) >= CHUNK_SIZE and agent:
                        raw_audio = bytes(audio_buffer)
                        audio_buffer.clear()
                        try:
                            wav = mulaw_to_wav(raw_audio)
                            user_text = transcribe(wav)
                            if user_text and len(user_text.strip()) > SILENCE_THRESHOLD:
                                logger.info(f"Caller: {user_text}")
                                log.append({"role": "user", "text": user_text})
                                response = agent.chat(user_text)
                                await send_audio(response)
                        except Exception as e:
                            logger.error(f"Error processing audio chunk: {e}", exc_info=True)
                except Exception as e:
                    logger.error(f"Error handling media event: {e}", exc_info=True)

            elif etype == "stop":
                logger.info(f"Call ended: {stream_sid}")
                break

    except Exception as e:
        logger.error(f"Phone session error: {e}", exc_info=True)
    finally:
        if agent and log:
            try:
                summary = agent.get_session_summary()
                await run_hook(log, agent.lead_data, summary, channel="phone")
                logger.info("Post-session hook completed")
            except Exception as e:
                logger.error(f"Hook execution failed: {e}", exc_info=True)
        try:
            await ws.close()
        except Exception:
            pass


# ==============================================================================
# FRONTEND INITIALIZATION
# ==============================================================================
# Must be at the very end to not intercept other routes
setup_frontend(app)
