import { useState, useRef, useEffect } from "react"
import useWebSocket    from "./hooks/useWebSocket"
import useAudioStream  from "./hooks/useAudioStream"
import StatusBadge     from "./components/StatusBadge"
import VoiceButton     from "./components/VoiceButton"
import TranscriptPanel from "./components/TranscriptPanel"
import "./styles/globals.css"

// Validate WS_URL at load time (fail fast)
const WS_URL = import.meta.env.VITE_WS_URL
if (!WS_URL) {
  throw new Error(
    "VITE_WS_URL environment variable is required. " +
    "Set it in .env: VITE_WS_URL=wss://api.example.com/ws/session"
  )
}

// Constants
const MAX_INPUT_LENGTH = 5000
const GREETING_TIMEOUT_MS = 3000
const MAX_BUFFER_SIZE = 10 * 1024 * 1024 // 10MB audio buffer limit

export default function App() {
  const [status,     setStatus]     = useState("idle")
  const [transcript, setTranscript] = useState([])
  const [active,     setActive]     = useState(false)
  const activeRef = useRef(false)
  const [error,      setError]      = useState(null)
  const [inputValue, setInputValue] = useState("")
  const audioQueueRef = useRef([])
  const playingRef    = useRef(false)
  const greetingTimeoutRef = useRef(null)

  const { connect, sendJson, sendBytes, close } = useWebSocket(WS_URL)
  const { start, stop } = useAudioStream()

  /**
   * Play audio queue sequentially with re-entry guard
   * Prevents race condition where multiple onended events trigger simultaneously
   */
  const playNext = async () => {
    // Guard: if already playing or no audio in queue, exit
    if (playingRef.current || !audioQueueRef.current.length) {
      if (!audioQueueRef.current.length) {
        playingRef.current = false
        setStatus("listening")
      }
      return
    }

    playingRef.current = true
    setStatus("speaking")

    const { bytes } = audioQueueRef.current.shift()
    const blob = new Blob([bytes], { type: "audio/wav" })
    const url = URL.createObjectURL(blob)
    const audio = new Audio(url)

    const cleanup = () => {
      try {
        URL.revokeObjectURL(url)
      } catch (e) {
        console.warn("Failed to revoke object URL:", e)
      }
      playingRef.current = false
    }

    audio.onended = () => {
      cleanup()
      playNext() // Recursively play next in queue
    }

    audio.onerror = (err) => {
      console.error("Audio playback error:", err)
      cleanup()
      playNext()
    }

    try {
      await audio.play()
    } catch (err) {
      console.error("Audio play() failed:", err)
      cleanup()
      playNext()
    }
  }

  /**
   * Handle incoming messages from WebSocket
   * Validates message structure and handles each type
   */
  const handleMessage = (msg) => {
    // Clear greeting timeout on ANY response
    if (greetingTimeoutRef.current) {
      clearTimeout(greetingTimeoutRef.current)
      greetingTimeoutRef.current = null
    }

    // TTS response: audio from agent
    if (msg.type === "tts" && typeof msg.text === "string") {
      setTranscript(t => [...t, { role: "assistant", text: msg.text }])
      
      if (msg.audio && typeof msg.audio === "string") {
        try {
          // Decode base64 audio
          const binaryString = atob(msg.audio)
          const bytes = new Uint8Array(binaryString.length)
          for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i)
          }

          // Check buffer size limit
          const totalBufferSize = audioQueueRef.current.reduce(
            (sum, item) => sum + item.bytes.length,
            0
          ) + bytes.length

          if (totalBufferSize > MAX_BUFFER_SIZE) {
            console.error("Audio buffer exceeded limit. Dropping oldest audio.")
            audioQueueRef.current.shift()
          }

          audioQueueRef.current.push({ bytes })
          if (!playingRef.current) {
            playNext()
          }
        } catch (e) {
          console.error("Audio decode error:", e)
          setStatus("listening")
        }
      } else {
        setStatus("listening")
      }
    }

    // STT response: user speech transcription
    if (msg.type === "stt" && typeof msg.text === "string") {
      setTranscript(t => [...t, { role: "user", text: msg.text }])
      setInputValue(msg.text) // Auto-fill text input
      setStatus("thinking")
    }

    // Error response from server
    if (msg.type === "error") {
      const errorMessage = msg.message || "Unknown error from server"
      setError(errorMessage)
      // Don't reset to idle - let the user keep talking
      if (errorMessage.includes("timeout") || errorMessage.includes("expired")) {
        setStatus("idle")
      }
    }

    // Background TTS audio (e.g. greeting audio arriving after text was already shown)
    if (msg.type === "tts_audio" && msg.audio && typeof msg.audio === "string") {
      try {
        const binaryString = atob(msg.audio)
        const bytes = new Uint8Array(binaryString.length)
        for (let i = 0; i < binaryString.length; i++) {
          bytes[i] = binaryString.charCodeAt(i)
        }
        audioQueueRef.current.push({ bytes })
        if (!playingRef.current) {
          playNext()
        }
      } catch (e) {
        console.error("Background audio decode error:", e)
      }
    }
  }

  /**
   * Handle text input submission
   * Validates input before sending to server
   */
  const handleSend = (text) => {
    const trimmed = text.trim()

    // Validation
    if (!trimmed) {
      setError("Message cannot be empty")
      return
    }

    if (trimmed.length > MAX_INPUT_LENGTH) {
      setError(`Message must be under ${MAX_INPUT_LENGTH} characters`)
      return
    }

    // Optional: filter control characters (keep letters, numbers, punctuation, whitespace)
    if (!/^[\p{L}\p{N}\s\p{P}]*$/u.test(trimmed)) {
      setError("Invalid characters in message")
      return
    }

    // Clear input and send
    setError(null)
    setInputValue("")
    sendJson({ type: "text_input", content: trimmed })
    setTranscript(t => [...t, { role: "user", text: trimmed }])
  }

  /**
   * Start voice session
   * Connects to WebSocket and begins audio capture
   */
  const startSession = async () => {
    setError(null)
    setTranscript([])
    setActive(true)
    activeRef.current = true
    setStatus("connecting")

    try {
      connect({
        onMessage: handleMessage,
        onOpen: async () => {
          setStatus("listening")

          // Set timeout for initial greeting
          greetingTimeoutRef.current = setTimeout(() => {
            console.log("Greeting timeout - checking connection...")
            sendJson({ type: "text_input", content: "[PING]" })
          }, GREETING_TIMEOUT_MS)

          try {
            // Start microphone stream
            await start((chunk) => {
              if (!activeRef.current) return

              // Efficient base64 encoding
              try {
                const uint8 = new Uint8Array(chunk)
                // Use apply for smaller buffers, fallback for larger
                let binary
                if (uint8.length > 50000) {
                  // For large buffers, use a loop to avoid stack overflow
                  binary = Array.from(uint8).map(b => String.fromCharCode(b)).join("")
                } else {
                  binary = String.fromCharCode.apply(null, Array.from(uint8))
                }
                const base64 = btoa(binary)

                console.log(`[Mic] Sending ${chunk.byteLength} bytes...`)
                sendJson({ type: "audio", bytes: base64 })
              } catch (e) {
                console.error("Audio encoding error:", e)
                setError("Failed to encode audio")
              }
            })
          } catch (err) {
            console.error("Microphone error:", err)
            setError("Microphone access denied. Please allow mic and try again.")
            setActive(false)
            activeRef.current = false
            setStatus("idle")
          }
        },
        onError: (err) => {
          console.error("WebSocket error:", err)
          setError("Could not connect to AI. Make sure the backend is running.")
          setActive(false)
          activeRef.current = false
          setStatus("idle")
        },
        onClose: () => {
          setStatus("idle")
          setActive(false)
          activeRef.current = false
          stop()
          if (greetingTimeoutRef.current) {
            clearTimeout(greetingTimeoutRef.current)
            greetingTimeoutRef.current = null
          }
        },
      })
    } catch (err) {
      console.error("Session start error:", err)
      setError("Connection failed. Please check your network and try again.")
      setActive(false)
      activeRef.current = false
      setStatus("idle")
    }
  }

  /**
   * End voice session
   * Closes WebSocket and cleanup resources
   */
  const endSession = () => {
    stop()
    close()
    setActive(false)
    activeRef.current = false
    setStatus("idle")
    playingRef.current = false
    audioQueueRef.current = []
    if (greetingTimeoutRef.current) {
      clearTimeout(greetingTimeoutRef.current)
      greetingTimeoutRef.current = null
    }
  }

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      endSession()
    }
  }, [])

  return (
    <div className="page">
      <div className="card">

        {/* Header */}
        <div className="header">
          <div className="logo-block">
            <span className="logo-icon">🏋️</span>
            <div>
              <h1 className="title">GOTHAM FITNESS</h1>
              <p className="subtitle">AI Concierge · Fleetwood, NY</p>
            </div>
          </div>
          <StatusBadge status={status} />
        </div>

        <div className="divider" />

        {/* CTA text */}
        {!active && (
          <p className="cta">
            Talk to our AI concierge to book your <strong>free introductory session</strong>.
            No forms. No waiting. Just speak.
          </p>
        )}

        {/* Error */}
        {error && (
          <div className="error-box">
            <span className="error-icon">⚠</span>
            {error}
          </div>
        )}

        {/* Main button */}
        <VoiceButton
          active   = {active}
          onClick  = {active ? endSession : startSession}
          disabled = {status === "connecting"}
        />

        {/* Text fallback input */}
        {active && (
          <form
            className="text-row"
            onSubmit={(e) => {
              e.preventDefault()
              handleSend(inputValue)
            }}
          >
            <input
              type="text"
              placeholder="Type your message..."
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              className="text-input"
              onKeyDown={(e) => e.key === "Enter" && handleSend(inputValue)}
            />
            <button type="submit" className="send-btn">Send</button>
          </form>
        )}

        {/* Transcript */}
        <TranscriptPanel messages={transcript} />

        {/* Footer */}
        <p className="footer-text">
          Powered by Gemini · Groq · Whisper · Kokoro
        </p>
      </div>
    </div>
  )
}
