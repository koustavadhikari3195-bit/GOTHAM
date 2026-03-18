import json
import base64
import logging
import uuid
import random
import contextvars
import asyncio
from typing import Optional, Dict, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Response
from starlette.websockets import WebSocketState
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
# CONSTANTS & CONFIG
# ==============================================================================
MAX_MESSAGE_SIZE = 5 * 1024 * 1024  # 5 MB safety cap on audio chunks
MAX_BUFFER_SIZE = 10 * 1024 * 1024  # 10 MB audio buffer limit
MAX_INPUT_LENGTH = 5000  # Max user text length
CHUNK_SIZE = 8000  # ~1 second of 8kHz audio
SILENCE_THRESHOLD = 2  # Minimum transcription length
SESSION_TIMEOUT_SECONDS = 30 * 60  # 30 minute session timeout
AGENT_CHAT_TIMEOUT = 30  # 30 second timeout for LLM responses
MODEL_WARMUP_DELAY_SECONDS = 2

# ==============================================================================
# LOGGING SETUP
# ==============================================================================
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

# Signal when models are ready
_models_ready: asyncio.Event = None


# ==============================================================================
# APP LIFESPAN
# ==============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _models_ready
    _models_ready = asyncio.Event()
    
    config.validate()
    
    async def warm_up():
        """Load TTS model in background without blocking startup.
        STT uses Groq API (primary) so no local model needed on startup.
        Local Whisper only lazy-loads if Groq fails."""
        try:
            await asyncio.sleep(MODEL_WARMUP_DELAY_SECONDS)
            from backend.voice.tts import _load as load_tts
            
            logger.info("Warming up TTS model in background...")
            
            # Only load TTS (Kokoro) — STT uses Groq API, no local model needed
            await asyncio.to_thread(load_tts)
            logger.info("TTS (Kokoro) ready")
            
            # Signal models are ready
            _models_ready.set()
            logger.info("AI models warmed up and ready")
        except Exception as e:
            logger.error(f"Error during background model warm-up: {e}", exc_info=True)
            _models_ready.set()  # Still signal ready to unblock clients

    # Kick off warm-up without blocking startup
    asyncio.create_task(warm_up())
    logger.info("=== Gotham Fitness AI Agent -- Web + Phone ready ===")
    logger.info(f"    Environment : {config.ENVIRONMENT}")
    logger.info(f"    CORS origins: {config.get_allowed_origins()}")
    yield
    logger.info("Shutting down")


app = FastAPI(title="Gotham Fitness AI Agent", lifespan=lifespan)

# -- CORS Configuration --------------------------------------------------------
# Define explicit allowed origins instead of "*"
allowed_origins = config.get_allowed_origins()
if isinstance(allowed_origins, str) and allowed_origins == "*":
    # If wildcard is required, disable credentials
    allow_credentials = False
    logger.warning("CORS: Using wildcard origin. Credentials disabled for security.")
else:
    allow_credentials = True
    logger.info(f"CORS: Allowing origins: {allowed_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins   = allowed_origins,
    allow_methods   = ["GET", "POST", "OPTIONS"],  # Explicit methods instead of "*"
    allow_headers   = ["Content-Type", "Authorization"],  # Explicit headers instead of "*"
    allow_credentials = allow_credentials,
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
    """Health check endpoint. Returns ready=false until models are loaded."""
    ready = _models_ready.is_set() if _models_ready else False
    return {
        "status": "ok",
        "channels": ["web", "phone"],
        "env": config.ENVIRONMENT,
        "models_ready": ready,
        "ready": ready
    }


# ==============================================================================
# HELPERS
# ==============================================================================
def validate_input_text(text: str) -> tuple[bool, Optional[str]]:
    """
    Validate user input text.
    Returns (is_valid, error_message)
    """
    if not text or not isinstance(text, str):
        return False, "Input must be non-empty string"
    
    trimmed = text.strip()
    
    if not trimmed:
        return False, "Input cannot be empty"
    
    if len(trimmed) > MAX_INPUT_LENGTH:
        return False, f"Input exceeds maximum length of {MAX_INPUT_LENGTH}"
    
    return True, None


def redact_phone_number(phone: str) -> str:
    """Redact phone number for logging (show only last 4 digits)."""
    if not phone:
        return "unknown"
    phone_str = str(phone)
    if len(phone_str) >= 4:
        return f"****{phone_str[-4:]}"
    return "****"


# ==============================================================================
# WEB CHANNEL — browser voice session
# ==============================================================================
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
    session_start_time = asyncio.get_event_loop().time()

    async def send_response(text: str) -> None:
        """Synthesize speech and send to client."""
        if not text or not isinstance(text, str):
            logger.warning("send_response called with invalid text")
            return
        
        try:
            logger.info(f"Synthesizing speech: {text[:50]}...")
            audio = await asyncio.to_thread(speak, text)
            
            if ws.client_state == WebSocketState.CONNECTED:
                if not audio:
                    logger.warning("TTS returned empty audio bytes")
                    await ws.send_json({
                        "type": "tts",
                        "text": text,
                        "audio": ""
                    })
                else:
                    audio_size = len(audio)
                    logger.info(f"Speech synthesized: {audio_size} bytes")
                    await ws.send_json({
                        "type": "tts",
                        "text": text,
                        "audio": base64.b64encode(audio).decode()
                    })
            else:
                logger.warning("WebSocket closed before TTS response could be sent")
            log.append({"role": "assistant", "text": text})
        except asyncio.TimeoutError:
            logger.error("TTS timeout")
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_json({"type": "error", "message": "TTS timeout. Please try again."})
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Error in send_response: {e}", exc_info=True)
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_json({"type": "error", "message": "TTS error"})
            except Exception:
                pass

    try:
        # Wait for models to be ready before initializing agent
        if _models_ready:
            try:
                await asyncio.wait_for(_models_ready.wait(), timeout=60)
            except asyncio.TimeoutError:
                logger.error("Models took too long to warm up")
                await ws.send_json({"type": "error", "message": "System still warming up. Please try again."})
                await ws.close()
                return

        # Fast Opening Greeting — send text IMMEDIATELY, then TTS in background
        greetings = [
            "Welcome to Gotham Fitness! I'm your AI concierge. What brings you in today?",
            "Hey there! Welcome to Gotham. I'm here to help you get started. What are your fitness goals?",
            "Welcome to Gotham Fitness! Ready to crush some goals? I'm your AI concierge—how can I help you today?"
        ]
        greeting = random.choice(greetings)
        logger.info("Sending instant greeting text")

        # 1) Send text immediately so the user sees a greeting within milliseconds
        if ws.client_state == WebSocketState.CONNECTED:
            await ws.send_json({"type": "tts", "text": greeting, "audio": ""})
            log.append({"role": "assistant", "text": greeting})

        # 2) Generate and send audio in the background, then signal start_listening
        async def _send_greeting_audio():
            try:
                audio = await asyncio.to_thread(speak, greeting)
                if audio and ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_json({
                        "type": "tts_audio",
                        "audio": base64.b64encode(audio).decode()
                    })
                    logger.info(f"Greeting audio sent: {len(audio)} bytes")
            except Exception as e:
                logger.warning(f"Greeting TTS failed (text was already sent): {e}")
            finally:
                # Signal frontend to start the microphone AFTER greeting
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_json({"type": "start_listening"})
                    logger.info("Sent start_listening signal")

        asyncio.create_task(_send_greeting_audio())

        logger.info("Initializing AgentRouter...")
        agent = AgentRouter()
        logger.info("AgentRouter ready")

        while True:
            # Check session timeout
            elapsed = asyncio.get_event_loop().time() - session_start_time
            if elapsed > SESSION_TIMEOUT_SECONDS:
                logger.info("Session timeout reached")
                await ws.send_json({"type": "error", "message": "Session expired due to inactivity"})
                break

            user_text = None
            
            try:
                # Wait for message from client (audio chunk or text chunk), with regular timeout
                message = await asyncio.wait_for(ws.receive(), timeout=SESSION_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                continue
            except WebSocketDisconnect:
                logger.info("Client disconnected normally")
                break
            except Exception as e:
                logger.error(f"Error receiving from client: {e}", exc_info=True)
                break
            
            if message["type"] == "websocket.disconnect":
                logger.info("Client disconnected")
                break

            # All messages should be JSON text
            inner_text = message.get("text")
            if not inner_text:
                continue

            try:
                msg = json.loads(inner_text)
                mtype = msg.get("type")
                
                if mtype == "end_session":
                    logger.info("Client requested session end")
                    break
                    
                elif mtype == "audio":
                    raw_b64 = msg.get("bytes", "")
                    if not raw_b64 or not isinstance(raw_b64, str):
                        logger.warning("Received invalid audio message")
                        continue
                    
                    if len(raw_b64) > MAX_MESSAGE_SIZE:
                        logger.warning(f"Audio message too large: {len(raw_b64)} bytes")
                        await ws.send_json({"type": "error", "message": "Audio chunk too large"})
                        continue
                    
                    try:
                        raw = base64.b64decode(raw_b64)
                        logger.info(f"Received audio: {len(raw)} bytes")
                        
                        # Tell client we're transcribing
                        if ws.client_state == WebSocketState.CONNECTED:
                            await ws.send_json({"type": "status", "status": "transcribing"})
                        
                        # Transcribe with timeout
                        stt_text = await asyncio.wait_for(
                            asyncio.to_thread(transcribe, raw),
                            timeout=15
                        )
                        
                        # Filter common hallucinations & noise
                        hallucinations = [
                            "you", "thank you.", "subtitles by", "thanks for watching",
                            "thank you for watching", "bye", "okay", "um", "uh",
                            "hmm", "huh", "oh", "ah", "yeah", "yes", "no",
                            ".", "..", "...", "the", "i", "a",
                            "thanks", "thank you", "goodbye", "bye bye",
                            "subscribe", "like and subscribe",
                            "silence", "applause", "music", "laughter",
                            "two hosheh", "so", "and", "but",
                            "right", "like", "just", "well"
                        ]
                        trimmed_stt = stt_text.lower().strip().rstrip('.')
                        if stt_text and len(trimmed_stt) > 2 and trimmed_stt not in hallucinations:
                            user_text = stt_text.strip()
                            logger.info(f"STT complete sentence: '{user_text}'")
                            
                            if ws.client_state == WebSocketState.CONNECTED:
                                await ws.send_json({"type": "stt", "text": user_text})
                        else:
                            # Resume listening if it was just noise
                            if ws.client_state == WebSocketState.CONNECTED:
                                await ws.send_json({"type": "status", "status": "listening"})
                    except asyncio.TimeoutError:
                        logger.warning("STT timeout — skipping chunk")
                        if ws.client_state == WebSocketState.CONNECTED:
                            await ws.send_json({"type": "status", "status": "listening"})
                    except Exception as e:
                        logger.error(f"STT or processing error: {e}")
                        if ws.client_state == WebSocketState.CONNECTED:
                            await ws.send_json({"type": "status", "status": "listening"})
                            
                elif mtype == "text_input":
                    content = msg.get("content", "")
                    
                    # Validation
                    is_valid, error_msg = validate_input_text(content)
                    if not is_valid:
                        logger.warning(f"Invalid text input: {error_msg}")
                        await ws.send_json({"type": "error", "message": error_msg})
                        continue
                    
                    if content == "[PING]":
                        logger.info("Received reliability PING")
                        continue
                    
                    user_text = content.strip()
                    logger.info(f"Text Input: {user_text[:50]}...")

            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode JSON from client: {e}")
                continue
            except Exception as e:
                if "close message" in str(e).lower():
                    logger.warning("Socket closed unexpectedly")
                    break
                logger.error(f"Error in message loop: {e}", exc_info=True)
                continue

            # Process user input
            if user_text and agent:
                log.append({"role": "user", "text": user_text})
                try:
                    # Tell client we're thinking
                    if ws.client_state == WebSocketState.CONNECTED:
                        await ws.send_json({"type": "status", "status": "thinking"})
                    
                    response = await asyncio.wait_for(
                        asyncio.to_thread(agent.chat, user_text),
                        timeout=AGENT_CHAT_TIMEOUT
                    )
                    await send_response(response)
                except asyncio.TimeoutError:
                    logger.error(f"Agent chat timed out after {AGENT_CHAT_TIMEOUT}s")
                    try:
                        if ws.client_state == WebSocketState.CONNECTED:
                            await ws.send_json({
                                "type": "error",
                                "message": "I took too long to think! Could you try rephrasing that?"
                            })
                    except Exception:
                        pass
                except Exception as e:
                    error_str = str(e).lower()
                    logger.error(f"Agent chat error: {e}", exc_info=True)
                    try:
                        if ws.client_state == WebSocketState.CONNECTED:
                            # Provide user-friendly messages based on error type
                            if any(s in error_str for s in ["429", "quota", "rate_limit", "resource_exhausted"]):
                                user_msg = "I'm getting a lot of visitors right now. Please try again in a moment."
                            elif any(s in error_str for s in ["connection", "timeout", "network"]):
                                user_msg = "I had a connection hiccup. Could you say that again?"
                            else:
                                user_msg = "Sorry, I had a brief hiccup. Could you repeat that?"
                            await ws.send_json({"type": "error", "message": user_msg})
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
    ALWAYS validates Twilio signature for security.
    """
    try:
        form = await request.form()
        caller = form.get("From", "Unknown")
        redacted_caller = redact_phone_number(caller)

        # Validate Twilio signature (required for production, always enforced)
        sig = request.headers.get("X-Twilio-Signature", "")
        url = str(request.url)
        
        if not validate_twilio_signature(url, dict(form), sig):
            logger.warning(f"Invalid Twilio signature from {redacted_caller}")
            return Response(status_code=403, content="Forbidden")

        logger.info(f"Incoming call from {redacted_caller}")
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
    buffer_size = 0
    session_start_time = asyncio.get_event_loop().time()

    async def send_audio(text: str) -> None:
        """Convert agent text to mulaw audio and send to Twilio."""
        if not stream_sid:
            logger.error("stream_sid not set - cannot send audio")
            return
        try:
            wav_bytes = await asyncio.to_thread(speak, text)
            if not wav_bytes:
                logger.warning("TTS returned empty audio")
                return
            
            mulaw_bytes = await asyncio.to_thread(wav_to_mulaw, wav_bytes)
            payload = base64.b64encode(mulaw_bytes).decode()
            
            if ws.client_state == WebSocketState.CONNECTED:
                await ws.send_json({
                    "event": "media",
                    "streamSid": stream_sid,
                    "media": {"payload": payload}
                })
            log.append({"role": "assistant", "text": text})
        except asyncio.TimeoutError:
            logger.error("TTS timeout on phone channel")
        except Exception as e:
            logger.error(f"Error in send_audio: {e}", exc_info=True)

    try:
        # Wait for models to be ready
        if _models_ready:
            try:
                await asyncio.wait_for(_models_ready.wait(), timeout=60)
            except asyncio.TimeoutError:
                logger.error("Models took too long to warm up")
                await ws.close()
                return

        agent = AgentRouter()

        while True:
            # Check session timeout
            elapsed = asyncio.get_event_loop().time() - session_start_time
            if elapsed > SESSION_TIMEOUT_SECONDS:
                logger.info("Phone session timeout")
                break

            try:
                raw = await asyncio.wait_for(ws.receive_text(), timeout=SESSION_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                logger.info("Phone WebSocket timeout")
                break
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
                        greeting = await asyncio.to_thread(
                            agent.chat,
                            "Customer just called the gym by phone. Greet them warmly and professionally."
                        )
                        await send_audio(greeting)
                    except Exception as e:
                        logger.error(f"Error generating greeting: {e}", exc_info=True)

            elif etype == "media":
                try:
                    payload = event.get("media", {}).get("payload")
                    if not payload or not isinstance(payload, str):
                        continue
                    
                    chunk = base64.b64decode(payload)
                    audio_buffer.extend(chunk)
                    buffer_size += len(chunk)

                    # Check buffer size limit
                    if buffer_size > MAX_BUFFER_SIZE:
                        logger.warning(f"Audio buffer exceeded {MAX_BUFFER_SIZE} bytes, clearing")
                        audio_buffer.clear()
                        buffer_size = 0
                        continue

                    if len(audio_buffer) >= CHUNK_SIZE and agent:
                        raw_audio = bytes(audio_buffer)
                        audio_buffer.clear()
                        buffer_size = 0
                        
                        try:
                            wav = await asyncio.to_thread(mulaw_to_wav, raw_audio)
                            user_text = await asyncio.to_thread(transcribe, wav)
                            
                            if user_text and len(user_text.strip()) > SILENCE_THRESHOLD:
                                logger.info(f"Caller: {user_text[:50]}...")
                                log.append({"role": "user", "text": user_text})
                                response = await asyncio.to_thread(agent.chat, user_text)
                                await send_audio(response)
                        except asyncio.TimeoutError:
                            logger.error("STT or agent timeout")
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
