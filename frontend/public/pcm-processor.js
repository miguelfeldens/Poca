/**
 * AudioWorkletProcessor that converts Float32 audio samples to Int16 PCM
 * and posts the raw bytes back to the main thread for streaming to the backend.
 *
 * Runs at the native sample rate of the AudioContext (set to 16000 Hz).
 */
class PCMProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const channel = inputs[0]?.[0]
    if (!channel || channel.length === 0) return true

    const pcm16 = new Int16Array(channel.length)
    for (let i = 0; i < channel.length; i++) {
      // Clamp to [-1, 1] then scale to Int16 range
      const clamped = Math.max(-1, Math.min(1, channel[i]))
      pcm16[i] = clamped < 0 ? clamped * 32768 : clamped * 32767
    }

    // Transfer the buffer (zero-copy) to the main thread
    this.port.postMessage(pcm16.buffer, [pcm16.buffer])
    return true
  }
}

registerProcessor('pcm-processor', PCMProcessor)
