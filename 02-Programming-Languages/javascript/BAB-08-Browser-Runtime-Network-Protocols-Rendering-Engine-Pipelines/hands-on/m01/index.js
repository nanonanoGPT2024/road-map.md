/**
 * Production-Grade High-Throughput Stream Pipeline
 * Menggabungkan Network Streaming Engine, Mutex Rendering Queue,
 * dan Compositor-Optimized Virtual DOM update.
 */

class HighFrequencyTradingDashboard {
  constructor(containerElement) {
    this.container = containerElement;
    this.renderQueue = [];
    this.isFrameScheduled = false;
    this.maxBufferedItems = 500;
    
    // Inisialisasi High Performance Observer
    this.initObserver();
  }

  initObserver() {
    // Memantau layout shift secara programmatic via Layout Instability API
    if ('PerformanceObserver' in window) {
      const clsObserver = new PerformanceObserver((entryList) => {
        for (const entry of entryList.getEntries()) {
          if (!entry.hadRecentInput) {
            console.warn(`[PERF ALERT] Unwanted Layout Shift detected: ${entry.value}`);
          }
        }
      });
      clsObserver.observe({ type: 'layout-shift', buffered: true });
    }
  }

  /**
   * Menghubungkan ke back-end menggunakan HTTP/2 atau HTTP/3 Byte Stream
   * Menggunakan Fetch Streams API alih-alih parsing JSON massal di memori
   */
  async connectOrderStream(streamUrl) {
    try {
      const response = await fetch(streamUrl);
      if (!response.body) throw new Error('ReadableStream tidak didukung');

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let partialBuffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        // Streaming chunk processing: parsing token tanpa menunggu request selesai
        partialBuffer += decoder.decode(value, { stream: true });
        const lines = partialBuffer.split('\n');
        
        // Simpan token yang belum selesai di buffer
        partialBuffer = lines.pop();

        for (const line of lines) {
          if (line.trim()) {
            const transaction = JSON.parse(line);
            this.pushTransactionToQueue(transaction);
          }
        }
      }
    } catch (err) {
      console.error('[NETWORK CRITICAL] Stream disconnected:', err);
    }
  }

  /**
   * Push data ke Antrean Thread-Safe (In-Memory Ring Buffer)
   */
  pushTransactionToQueue(transaction) {
    this.renderQueue.push(transaction);

    // Mencegah Memory Bloat jika background tab tidak merender
    if (this.renderQueue.length > this.maxBufferedItems) {
      this.renderQueue.splice(0, this.renderQueue.length - this.maxBufferedItems);
    }

    // Jadwalkan rendering batch jika belum ada frame yang aktif
    if (!this.isFrameScheduled) {
      this.isFrameScheduled = true;
      requestAnimationFrame(this.flushQueueToPipeline.bind(this));
    }
  }

  /**
   * FLUSH PIPELINE: Memproses data tepat sebelum V-Sync.
   * Tidak ada percampuran Read/Write geometri di Main Thread.
   */
  flushQueueToPipeline() {
    this.isFrameScheduled = false;

    if (this.renderQueue.length === 0) return;

    // Ambil seluruh snapshot data saat ini dan bersihkan antrean
    const itemsToRender = [...this.renderQueue];
    this.renderQueue = [];

    // FASE MENULIS MURNI (Batch Write DOM via DocumentFragment)
    const fragment = document.createDocumentFragment();

    for (let i = 0; i < itemsToRender.length; i++) {
      const item = itemsToRender[i];
      const row = document.createElement('div');
      
      // Menggunakan inline styling berbasis GPU Compositor primitives
      row.className = 'trade-row';
      row.style.cssText = `
        contain: strict;
        will-change: transform;
        height: 24px;
        color: ${item.side === 'BUY' ? '#10b981' : '#ef4444'};
      `;
      row.textContent = `[${item.timestamp}] ${item.symbol} | Vol: ${item.volume} @ ${item.price}`;
      fragment.appendChild(row);
    }

    // Mutasi DOM Tunggal: Layout Engine hanya mengevaluasi fragment sekali
    this.container.appendChild(fragment);

    // Pangkas node lama di luar viewport untuk menjaga ukuran DOM Tree tetap konstan
    const totalChildren = this.container.children.length;
    if (totalChildren > this.maxBufferedItems) {
      const deleteCount = totalChildren - this.maxBufferedItems;
      for (let i = 0; i < deleteCount; i++) {
        this.container.removeChild(this.container.firstElementChild);
      }
    }
  }
}

// Inisialisasi pada container
const dashboard = new HighFrequencyTradingDashboard(document.getElementById('ticker-mount'));
// Simulasi stream masuk
// dashboard.connectOrderStream('https://api.apextrade.internal/v3/feed/stream');
