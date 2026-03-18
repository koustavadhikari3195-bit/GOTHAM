import { useRef } from "react"

export default function useAudioStream() {
  const streamRef      = useRef(null)
  const timerRef       = useRef(null)
  const isRecordingRef = useRef(false)
  const isPausedRef    = useRef(false)
  const audioCtxRef    = useRef(null)
  const analyserRef    = useRef(null)
  const maxVolumeRef   = useRef(0)

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
      isPausedRef.current    = false

      // Setup audio analyzer for silence detection
      audioCtxRef.current = new (window.AudioContext || window.webkitAudioContext)()
      analyserRef.current = audioCtxRef.current.createAnalyser()
      analyserRef.current.fftSize = 256
      
      const source = audioCtxRef.current.createMediaStreamSource(stream)
      source.connect(analyserRef.current)

      const startRecorder = () => {
        if (!isRecordingRef.current || !streamRef.current) return

        // Don't start a new recording cycle if paused — wait and retry
        if (isPausedRef.current) {
          timerRef.current = setTimeout(startRecorder, 500)
          return
        }

        console.log("[Mic] Starting MediaRecorder...")
        const recorder = new MediaRecorder(streamRef.current, {
          mimeType: MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
            ? "audio/webm;codecs=opus"
            : "audio/webm"
        })

        let chunks = []
        let checkVolumeInterval
        const SILENCE_THRESHOLD = 5 // Adjust between 1-10 depending on mic sensitivity
        let hasSpoken = false
        let silenceCount = 0

        recorder.ondataavailable = (e) => {
          if (e.data && e.data.size > 0) chunks.push(e.data)
        }

        recorder.onstop = async () => {
          clearInterval(checkVolumeInterval)

          // If paused (agent speaking) or never spoke, discard chunk
          if (isPausedRef.current || !hasSpoken) {
            if (isPausedRef.current) {
              console.log("[Mic] Discarding chunk (agent speaking)")
            } else {
              console.log("[Mic] Discarding chunk (SILENCE detected)")
            }
            chunks = []
            if (isRecordingRef.current) {
              startRecorder() // Will loop back and wait
            }
            return
          }

          console.log(`[Mic] Stopped. Collected ${chunks.length} chunks. User spoke: ${hasSpoken}`)
          if (chunks.length > 0) {
            const blob = new Blob(chunks, { type: "audio/webm" })
            const buffer = await blob.arrayBuffer()
            console.log(`[Mic] Emitting buffer: ${buffer.byteLength} bytes`)
            onChunk(buffer)
          }
          if (isRecordingRef.current) {
            startRecorder()
          }
        }

        recorder.start()

        // Check volume every 100ms
        const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount)
        checkVolumeInterval = setInterval(() => {
          if (!isRecordingRef.current || isPausedRef.current || recorder.state !== "recording") return
          analyserRef.current.getByteFrequencyData(dataArray)
          
          let sum = 0
          for (let i = 0; i < dataArray.length; i++) {
            sum += dataArray[i]
          }
          const avg = sum / dataArray.length
          
          if (avg >= SILENCE_THRESHOLD) {
            hasSpoken = true
            silenceCount = 0 // Reset silence counter while user is speaking
          } else {
            silenceCount++
            
            // If user previously spoke and has now been silent for 1.5s (15 * 100ms), stop to send chunk
            if (hasSpoken && silenceCount >= 15) {
              recorder.stop()
            }
            // If user never spoke, keep running but drop empty buffer after 10s to clear memory
            else if (!hasSpoken && silenceCount >= 100) {
              recorder.stop()
            }
          }
        }, 100)
      }

      startRecorder()
    } catch (err) {
      console.error("Microphone access error:", err)
      throw err
    }
  }

  /** Pause recording — used when agent is speaking to prevent echo */
  const pause = () => {
    isPausedRef.current = true
    console.log("[Mic] Paused (agent speaking)")
    // Mute the mic tracks to prevent any audio capture
    if (streamRef.current) {
      streamRef.current.getAudioTracks().forEach(t => { t.enabled = false })
    }
  }

  /** Resume recording — used after agent finishes speaking */
  const resume = () => {
    isPausedRef.current = false
    console.log("[Mic] Resumed (agent done)")
    // Un-mute the mic tracks
    if (streamRef.current) {
      streamRef.current.getAudioTracks().forEach(t => { t.enabled = true })
    }
  }

  const stop = () => {
    isRecordingRef.current = false
    isPausedRef.current = false
    if (timerRef.current) clearTimeout(timerRef.current)
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop())
      streamRef.current = null
    }
    if (audioCtxRef.current) {
      audioCtxRef.current.close()
      audioCtxRef.current = null
      analyserRef.current = null
    }
  }

  return { start, stop, pause, resume }
}
