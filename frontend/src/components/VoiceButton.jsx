export default function VoiceButton({ active, onClick, disabled }) {
  return (
    <div className="voice-btn-container">
      <button
        onClick={onClick}
        disabled={disabled}
        className={`voice-btn ${active ? "active" : ""} ${disabled ? "disabled" : ""}`}
      >
        <div className="glow-effect" />
        <span className="btn-content">
          {active ? (
            <><span className="icon">⏹</span> Stop Session</>
          ) : disabled ? (
            <><span className="icon loading">⏳</span> Connecting...</>
          ) : (
            <><span className="icon">▶</span> Start Free Consultation</>
          )}
        </span>
      </button>

      <style>{`
        .voice-btn-container {
          width: 100%;
          display: flex;
          justify-content: center;
          perspective: 1000px;
        }

        .voice-btn {
          width: 100%;
          height: 64px;
          border-radius: 18px;
          border: none;
          cursor: pointer;
          position: relative;
          overflow: hidden;
          background: linear-gradient(135deg, #ff3e4e, #c1121f);
          color: #fff;
          font-family: 'Barlow Condensed', sans-serif;
          font-size: 18px;
          font-weight: 800;
          letter-spacing: 2px;
          text-transform: uppercase;
          transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
          box-shadow: 0 10px 30px rgba(255, 62, 78, 0.3);
        }

        .voice-btn:hover:not(.disabled) {
          transform: translateY(-2px) scale(1.01);
          box-shadow: 0 15px 40px rgba(255, 62, 78, 0.4);
        }

        .voice-btn:active:not(.disabled) {
          transform: translateY(0) scale(0.98);
        }

        .voice-btn.active {
          background: rgba(255, 255, 255, 0.05);
          color: rgba(255, 255, 255, 0.6);
          border: 1px solid rgba(255, 255, 255, 0.1);
          box-shadow: none;
        }

        .voice-btn.disabled {
          opacity: 0.6;
          cursor: not-allowed;
          background: #222;
        }

        .btn-content {
          position: relative;
          z-index: 2;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 12px;
        }

        .icon { font-size: 20px; }
        .icon.loading { animation: spin 2s linear infinite; }

        .glow-effect {
          position: absolute;
          inset: 0;
          background: radial-gradient(circle at var(--x, 50%) var(--y, 50%), rgba(255,255,255,0.2) 0%, transparent 70%);
          opacity: 0;
          transition: opacity 0.3s;
          pointer-events: none;
        }

        .voice-btn:hover .glow-effect { opacity: 1; }

        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }

        @keyframes pulse-ring {
          0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(255, 62, 78, 0.4); }
          70% { transform: scale(1); box-shadow: 0 0 0 20px rgba(255, 62, 78, 0); }
          100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(255, 62, 78, 0); }
        }

        .voice-btn:not(.active):not(.disabled) {
          animation: pulse-ring 2s infinite;
        }
      `}</style>
    </div>
  )
}
