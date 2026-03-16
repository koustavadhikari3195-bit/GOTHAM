import { useRef } from "react"

export default function useAudioStream() {
  const streamRef      = useRef(null)
  const timerRef       = useRef(null)
  const isRecordingRef = useRef(false)

  const start = async (onChunk) => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount:      1,
          sampleRate:        16000,
          echoCancellation:  true,
          noiseSuppression:  true,
          autoGainControl:   true,
        }
      })
      streamRef.current      = stream
      isRecordingRef.current = true

      const startRecorder = () => {
        if (!isRecordingRef.current || !streamRef.current) return

        console.log("[Mic] Starting MediaRecorder...")
        const recorder = new MediaRecorder(streamRef.current, {
          mimeType: MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
            ? "audio/webm;codecs=opus"
            : "audio/webm"
        })

        let chunks = []
        recorder.ondataavailable = (e) => {
          if (e.data && e.data.size > 0) chunks.push(e.data)
        }

        recorder.onstop = async () => {
          console.log(`[Mic] Stopped. Collected ${chunks.length} chunks.`)
          if (chunks.length > 0) {
            const blob = new Blob(chunks, { type: "audio/webm" })
            // Convert Blob to ArrayBuffer for reliable binary transfer
            const buffer = await blob.arrayBuffer()
            console.log(`[Mic] Emitting buffer: ${buffer.byteLength} bytes`)
            onChunk(buffer)
          }
          if (isRecordingRef.current) {
            startRecorder()
          }
        }

        recorder.start()

        // Stop every 800ms to emit a fully valid WebM file for lower latency
        timerRef.current = setTimeout(() => {
          if (recorder.state === "recording") {
            recorder.stop()
          }
        }, 2000)
      }

      startRecorder()
    } catch (err) {
      console.error("Microphone access error:", err)
      throw err
    }
  }

  const stop = () => {
    isRecordingRef.current = false
    if (timerRef.current) clearTimeout(timerRef.current)
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop())
      streamRef.current = null
    }
  }

  return { start, stop }
}
