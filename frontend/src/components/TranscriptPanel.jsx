import { useEffect, useRef } from "react"

export default function TranscriptPanel({ messages }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  if (!messages.length) return null

  return (
    <div style={{
      marginTop:    24,
      maxHeight:    340,
      overflowY:    "auto",
      borderRadius: 10,
      border:       "1px solid #1e1e1e",
      background:   "#0c0c0c",
      padding:      "12px 4px",
    }}>
      {messages.map((msg, i) => (
        <div key={i} style={{
          display:      "flex",
          gap:          10,
          padding:      "10px 14px",
          borderRadius: 8,
          marginBottom: 4,
          background:   msg.role === "assistant" ? "#111827" : "#0f1f0f",
          borderLeft:   `3px solid ${msg.role === "assistant" ? "#4361ee" : "#2dc653"}`,
          animation:    "messageSlideIn 0.25s ease-out",
        }}>
          <span style={{
            fontSize:      11,
            fontWeight:    700,
            color:         msg.role === "assistant" ? "#4361ee" : "#2dc653",
            minWidth:      36,
            paddingTop:    1,
            fontFamily:    "'Barlow Condensed', sans-serif",
            letterSpacing: 1,
            textTransform: "uppercase",
          }}>
            {msg.role === "assistant" ? "AI" : "You"}
          </span>
          <span style={{ fontSize: 14, lineHeight: 1.6, color: "#ccc" }}>
            {msg.text}
          </span>
        </div>
      ))}
      <div ref={bottomRef} />
      <style>{`
        @keyframes messageSlideIn {
          from { opacity: 0; transform: translateX(-6px); }
          to   { opacity: 1; transform: translateX(0); }
        }
      `}</style>
    </div>
  )
}
