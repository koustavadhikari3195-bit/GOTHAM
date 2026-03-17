const STATUS_CONFIG = {
  idle:         { label: "Ready",           icon: "●" },
  connecting:   { label: "Connecting...",   icon: "◌" },
  connected:    { label: "Connected",       icon: "●" },
  listening:    { label: "Listening",       icon: "🎙" },
  transcribing: { label: "Transcribing...", icon: "✍️" },
  thinking:     { label: "Thinking...",     icon: "⚡" },
  speaking:     { label: "Speaking",        icon: "🔊" },
}

export default function StatusBadge({ status }) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.idle
  const isActive = status !== "idle" && status !== "connecting"

  return (
    <div className="status-badge">
      <div className={`status-dot ${isActive ? "active" : ""}`} />
      <span style={{ fontSize: "14px", marginRight: "4px" }}>{cfg.icon}</span>
      {cfg.label}

      <style>{`
        .status-badge {
          transition: all 0.3s ease;
        }
      `}</style>
    </div>
  )
}
