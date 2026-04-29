import { useState, useRef, useCallback, useEffect } from 'react'

const BATCH_INTERVAL_MS = 100  // send audio in ~100ms batches

export function useVoiceInput({ onChunk, onEnd }) {
  const [listening, setListening] = useState(false)
  const [supported] = useState(
    typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia
  )

  const inputCtxRef = useRef(null)
  const streamRef = useRef(null)
  const workletRef = useRef(null)
  const sourceRef = useRef(null)
  const batchRef = useRef([])    // accumulated Int16Array chunks between flushes
  const intervalRef = useRef(null)

  const flushBatch = useCallback((callback) => {
    const chunks = batchRef.current
    if (chunks.length === 0) return
    batchRef.current = []

    const totalLen = chunks.reduce((s, c) => s + c.length, 0)
    const combined = new Int16Array(totalLen)
    let offset = 0
    for (const c of chunks) { combined.set(c, offset); offset += c.length }

    // Convert to base64
    const bytes = new Uint8Array(combined.buffer)
    let binary = ''
    for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i])
    callback?.(btoa(binary))
  }, [])

  const startListening = useCallback(async () => {
    if (listening) return
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false })
      streamRef.current = stream

      // Create a 16kHz AudioContext — the browser resamples the mic's native rate for us
      const ctx = new AudioContext({ sampleRate: 16000 })
      inputCtxRef.current = ctx

      await ctx.audioWorklet.addModule('/pcm-processor.js')

      const source = ctx.createMediaStreamSource(stream)
      sourceRef.current = source

      const worklet = new AudioWorkletNode(ctx, 'pcm-processor')
      workletRef.current = worklet

      // Collect raw Int16 chunks from the worklet
      worklet.port.onmessage = (e) => {
        batchRef.current.push(new Int16Array(e.data))
      }

      // Connect graph: mic → worklet → destination (worklet outputs silence, no feedback)
      source.connect(worklet)
      worklet.connect(ctx.destination)

      // Send batched audio every 100ms
      intervalRef.current = setInterval(() => flushBatch(onChunk), BATCH_INTERVAL_MS)

      setListening(true)
    } catch (err) {
      console.error('[voice] Failed to start:', err)
    }
  }, [listening, onChunk, flushBatch])

  const stopListening = useCallback(() => {
    if (!listening) return

    clearInterval(intervalRef.current)
    intervalRef.current = null

    // Flush any remaining audio before signaling end
    flushBatch(onChunk)
    batchRef.current = []

    try { sourceRef.current?.disconnect() } catch {}
    try { workletRef.current?.disconnect() } catch {}
    try { workletRef.current?.port.close() } catch {}
    streamRef.current?.getTracks().forEach(t => t.stop())
    inputCtxRef.current?.close()

    inputCtxRef.current = null
    streamRef.current = null
    workletRef.current = null
    sourceRef.current = null

    setListening(false)
    onEnd?.()
  }, [listening, onChunk, onEnd, flushBatch])

  const toggleListening = useCallback(() => {
    if (listening) stopListening()
    else startListening()
  }, [listening, startListening, stopListening])

  useEffect(() => {
    return () => {
      clearInterval(intervalRef.current)
      try { sourceRef.current?.disconnect() } catch {}
      try { workletRef.current?.disconnect() } catch {}
      streamRef.current?.getTracks().forEach(t => t.stop())
      inputCtxRef.current?.close()
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return { listening, supported, toggleListening, startListening, stopListening }
}
