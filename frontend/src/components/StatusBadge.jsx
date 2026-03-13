const STATUS_CONFIG = {
  idle:       { label: "Ready",         color: "#555",    bg: "#111" },
  connecting: { label: "Connecting...", color: "#888",    bg: "#1a1a1a" },
  connected:  { label: "Connected",     color: "#2dc653", bg: "#0d1f14" },
  listening:  { label: "Listening",     color: "#2dc653", bg: "#0d1f14" },
  thinking:   { label: "Thinking",      color: "#4361ee", bg: "#0d0d2e" },
  speaking:   { label: "Speaking",      color: "#e63946", bg: "#1f0d0e" },
}

const STATUS_ICON = {
  idle:       "●",
  connecting: "◌",
  connected:  "●",
  listening:  "🎙",
  thinking:   "⚡",
  speaking:   "🔊",
}

export default function StatusBadge({ status }) {
  const cfg  = STATUS_CONFIG[status] || STATUS_CONFIG.idle
  const icon = STATUS_ICON[status]   || "●"

  return (
    <div style={{
      display:       "inline-flex",
      alignItems:    "center",
      gap:           8,
      padding:       "6px 14px",
      borderRadius:  20,
      background:    cfg.bg,
      border:        `1px solid ${cfg.color}33`,
      color:         cfg.color,
      fontSize:      13,
      fontWeight:    600,
      letterSpacing: 0.5,
      transition:    "all 0.3s ease",
      userSelect:    "none",
    }}>
      {(status === "listening" || status === "connecting") && (
        <span style={{
          animation: status === "listening"
            ? "pulse 1.2s infinite"
            : "pulse 0.8s infinite",
        }}>●</span>
      )}
      <span>{icon}</span>
      {cfg.label}
    </div>
  )
}
