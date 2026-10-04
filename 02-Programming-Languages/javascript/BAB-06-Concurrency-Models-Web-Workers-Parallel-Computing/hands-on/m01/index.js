// image-pipeline.js
import { WorkerPool } from './worker-pool.js';

export async function processImageParallel(imageData, kernel, kernelSize) {
  // Validasi prasyarat Cross-Origin Isolation untuk SharedArrayBuffer
  if (!window.crossOriginIsolated) {
    throw new Error('Eksekusi dibatalkan: Lingkungan tidak mendukung window.crossOriginIsolated.');
  }

  const { width, height, data } = imageData;
  const totalBytes = data.byteLength;

  // 1. Buat SharedArrayBuffer untuk input dan output
  const inputSharedBuffer = new SharedArrayBuffer(totalBytes);
  const outputSharedBuffer = new SharedArrayBuffer(totalBytes);

  // Buat view dan salin data piksel asal ke shared buffer
  new Uint8ClampedArray(inputSharedBuffer).set(data);

  // 2. Inisialisasi pool sesuai jumlah physical/logical core perangkat
  const concurrency = navigator.hardwareConcurrency || 4;
  const pool = new WorkerPool('./shared-worker-core.js', concurrency);

  const chunkHeight = Math.ceil(height / concurrency);
  const promises = [];

  console.time('Parallel Image Processing Time');

  // 3. Distribusikan beban kerja secara seimbang (Chunking Partition)
  for (let i = 0; i < concurrency; i++) {
    const startY = i * chunkHeight;
    const endY = Math.min(startY + chunkHeight, height);

    if (startY >= height) break;

    const payload = {
      taskId: i,
      inputBuffer: inputSharedBuffer,
      outputBuffer: outputSharedBuffer,
      width,
      height,
      startY,
      endY,
      kernel,
      kernelSize,
    };

    promises.push(pool.exec(payload));
  }

  // 4. Sinkronisasi eksekusi semua parallel workers
  await Promise.all(promises);
  console.timeEnd('Parallel Image Processing Time');

  // Bersihkan pool setelah eksekusi
  pool.destroy();

  // 5. Kembalikan data hasil konvolusi yang baru
  return new ImageData(
    new Uint8ClampedArray(outputSharedBuffer),
    width,
    height
  );
}
