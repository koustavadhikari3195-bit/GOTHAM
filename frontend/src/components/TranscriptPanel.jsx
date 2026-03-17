import { useEffect, useRef } from "react"

export default function TranscriptPanel({ messages }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  if (!messages.length) return null

  return (
    <div className="transcript-container">
      {messages.map((msg, i) => (
        <div 
          key={i} 
          className={`msg-bubble ${msg.role === "assistant" ? "ai" : "user"}`}
        >
          <div className="msg-header">
            {msg.role === "assistant" ? "AI COACH" : "YOU"}
          </div>
          <div className="msg-content">
            {msg.text}
          </div>
        </div>
      ))}
      <div ref={bottomRef} />
      
      <style>{`
        .transcript-container {
          margin-top: 32px;
          max-height: 400px;
          overflow-y: auto;
          display: flex;
          flex-direction: column;
          gap: 16px;
          padding: 8px;
          scrollbar-width: thin;
        }

        .msg-bubble {
          max-width: 85%;
          padding: 16px 20px;
          border-radius: 20px;
          animation: messageEntrance 0.3s ease-out;
          border: 1px solid rgba(255, 255, 255, 0.05);
          backdrop-filter: blur(10px);
        }

        .msg-bubble.ai {
          align-self: flex-start;
          background: rgba(255, 255, 255, 0.03);
          border-bottom-left-radius: 4px;
        }

        .msg-bubble.user {
          align-self: flex-end;
          background: rgba(255, 255, 255, 0.07);
          border-bottom-right-radius: 4px;
          border-color: rgba(255, 255, 255, 0.1);
        }

        .msg-header {
          font-family: 'Barlow Condensed', sans-serif;
          font-size: 10px;
          font-weight: 800;
          letter-spacing: 1.5px;
          margin-bottom: 6px;
          opacity: 0.5;
        }

        .msg-bubble.ai .msg-header { color: #ff3e4e; opacity: 0.8; }

        .msg-content {
          font-size: 15px;
          line-height: 1.5;
          color: rgba(255, 255, 255, 0.9);
        }

        @keyframes messageEntrance {
          from { opacity: 0; transform: translateY(10px) scale(0.98); }
          to   { opacity: 1; transform: translateY(0) scale(1); }
        }
      `}</style>
    </div>
  )
}
