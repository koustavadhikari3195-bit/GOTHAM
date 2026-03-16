import { useState, useRef } from "react"
import useWebSocket    from "./hooks/useWebSocket"
import useAudioStream  from "./hooks/useAudioStream"
import StatusBadge     from "./components/StatusBadge"
import VoiceButton     from "./components/VoiceButton"
import TranscriptPanel from "./components/TranscriptPanel"
import "./styles/globals.css"

const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8000/ws/session"

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

  // Play audio queue sequentially
  const playNext = () => {
    if (!audioQueueRef.current.length) {
      playingRef.current = false
      setStatus("listening")
      return
    }
    playingRef.current = true
    setStatus("speaking")
    const { bytes } = audioQueueRef.current.shift()
    const blob  = new Blob([bytes], { type: "audio/wav" })
    const url   = URL.createObjectURL(blob)
    const audio = new Audio(url)
    audio.onended = () => { URL.revokeObjectURL(url); playNext() }
    audio.onerror = () => { URL.revokeObjectURL(url); playNext() }
    audio.play().catch(() => playNext())
  }

  const handleMessage = (msg) => {
    if (msg.type === "tts") {
      // Clear greeting timeout if we get a response
      if (greetingTimeoutRef.current) {
        clearTimeout(greetingTimeoutRef.current)
        greetingTimeoutRef.current = null
      }

      setTranscript(t => [...t, { role: "assistant", text: msg.text }])
      if (msg.audio) {
        try {
          const bytes = Uint8Array.from(atob(msg.audio), c => c.charCodeAt(0))
          audioQueueRef.current.push({ bytes })
          if (!playingRef.current) playNext()
        } catch (e) {
          console.error("Audio decode error:", e)
          setStatus("listening")
        }
      } else {
        setStatus("listening")
      }
    }
    if (msg.type === "stt") {
      setTranscript(t => [...t, { role: "user", text: msg.text }])
      setInputValue(msg.text) // Fill the chat box as requested!
      setStatus("thinking")
    }
    if (msg.type === "error") {
      setError(msg.message || "Something went wrong")
      setStatus("idle")
    }
  }

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
          
          // Set a timeout for the initial greeting
          greetingTimeoutRef.current = setTimeout(() => {
            console.log("Greeting timeout - checking connection...")
            sendJson({ type: "text_input", content: "[PING]" })
          }, 3000)

          try {
            await start((chunk) => {
              if (activeRef.current) {
                console.log(`[Mic] Sending ${chunk.byteLength} bytes to server...`)
                sendBytes(chunk)
              }
            })
          } catch {
            setError("Microphone access denied. Please allow mic and try again.")
            setActive(false)
            setStatus("idle")
          }
        },
        onError: () => {
          setError("Could not connect to AI. Make sure the backend is running.")
          setActive(false)
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
      setError("Connection failed. Please check your network and try again.")
      setActive(false)
      setStatus("idle")
    }
  }

  const endSession = () => {
    stop()
    close()
    setActive(false)
    setStatus("idle")
    playingRef.current = false
    audioQueueRef.current = []
  }

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
              className="flex-1 bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-red-500/50 transition-colors"
              onKeyPress={(e) => e.key === "Enter" && handleSend(inputValue)}
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
