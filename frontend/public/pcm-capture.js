// PCM encoder runs off the UI thread. Resamples the actual hardware rate to 24 kHz.
class PcmCapture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.previous = 0;
    this.position = 0;
    this.packet = new Int16Array(480);
    this.offset = 0;
  }
  process(inputs) {
    const samples = inputs[0]?.[0];
    if (!samples?.length) return true;
    const ratio = sampleRate / 24000;
    while (this.position < samples.length - 1) {
      const left = Math.floor(this.position);
      const a = left < 0 ? this.previous : samples[left];
      const b = samples[left + 1];
      const value = Math.max(
        -1,
        Math.min(1, a + (b - a) * (this.position - left)),
      );
      this.packet[this.offset++] = Math.round(
        value * (value < 0 ? 32768 : 32767),
      );
      if (this.offset === this.packet.length) {
        // Explicit little endian, regardless of host architecture.
        const bytes = new ArrayBuffer(960);
        const view = new DataView(bytes);
        for (let i = 0; i < 480; i++)
          view.setInt16(i * 2, this.packet[i], true);
        this.port.postMessage(bytes, [bytes]);
        this.offset = 0;
      }
      this.position += ratio;
    }
    this.position -= samples.length;
    this.previous = samples[samples.length - 1];
    return true;
  }
}
registerProcessor("pcm-capture", PcmCapture);
