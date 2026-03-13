import { useRef, useCallback } from "react"

export default function useWebSocket(url) {
  const wsRef = useRef(null)

  const connect = useCallback(({ onMessage, onOpen, onError, onClose }) => {
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      if (onOpen) onOpen(ws)
    }
    ws.onclose = (e) => {
      if (onClose) onClose(e)
    }
    ws.onerror = (e) => {
      console.error("WS error:", e)
      if (onError) onError(e)
    }
    ws.onmessage = (e) => {
      try {
        onMessage(JSON.parse(e.data))
      } catch (err) {
        console.error("WS parse error:", err)
      }
    }
    return ws
  }, [url])

  const sendJson = useCallback((data) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
    }
  }, [])

  const sendBytes = useCallback((blob) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(blob)
    }
  }, [])

  const close = useCallback(() => {
    sendJson({ type: "end_session" })
    wsRef.current?.close()
    wsRef.current = null
  }, [sendJson])

  return { connect, sendJson, sendBytes, close }
}
