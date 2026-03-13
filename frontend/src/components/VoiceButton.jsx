export default function VoiceButton({ active, onClick, disabled }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        position:      "relative",
        width:         "100%",
        padding:       "18px 0",
        borderRadius:  12,
        border:        "none",
        cursor:        disabled ? "not-allowed" : "pointer",
        fontSize:      17,
        fontWeight:    800,
        fontFamily:    "'Barlow Condensed', sans-serif",
        letterSpacing: 2,
        textTransform: "uppercase",
        background:    active
          ? "linear-gradient(135deg, #1a1a1a, #222)"
          : "linear-gradient(135deg, #e63946, #c1121f)",
        color:         active ? "#666" : "#fff",
        boxShadow:     active
          ? "none"
          : "0 4px 24px rgba(230, 57, 70, 0.35)",
        transition:    "all 0.25s ease",
        overflow:      "hidden",
        opacity:       disabled ? 0.5 : 1,
      }}
    >
      {active && (
        <span style={{
          position:   "absolute",
          inset:      0,
          background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.04), transparent)",
          animation:  "shimmer 2s infinite",
        }} />
      )}
      {!active && !disabled && (
        <span style={{
          position:    "absolute",
          inset:       0,
          borderRadius: 12,
          animation:   "breathe 2.5s ease-in-out infinite",
        }} />
      )}
      {active ? "⏹  End Session" : disabled ? "⏳  Connecting..." : "▶  Start Free Consultation"}
    </button>
  )
}
