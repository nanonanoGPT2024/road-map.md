// File: src/components/TradingChartBoundary.tsx
import React, {
  useRef,
  useEffect,
  useLayoutEffect,
  useImperativeHandle,
  forwardRef,
  memo,
} from 'react';

// 1. Kontrak Antarmuka Komponen & Tipe Engine Eksternal
export interface CandleData {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface ChartImperativeHandle {
  resetZoom: () => void;
  exportChartAsBlob: () => Promise<Blob | null>;
}

interface TradingChartProps {
  data: CandleData[];
  theme: 'dark' | 'light';
  onCrosshairMove?: (price: number | null) => void;
}

// Mocking External Imperative Engine API (seperti Lightweight Charts)
class ImperativeChartEngine {
  private container: HTMLElement;
  private options: { theme: string };
  private isDestroyed = false;

  constructor(container: HTMLElement, options: { theme: string }) {
    this.container = container;
    this.options = options;
    this.initCanvas();
  }

  private initCanvas() {
    this.container.innerHTML = `<div class="chart-canvas-mock" style="width: 100%; height: 400px; background: ${
      this.options.theme === 'dark' ? '#1e1e1e' : '#f5f5f5'
    };"></div>`;
  }

  public setData(data: CandleData[]) {
    if (this.isDestroyed) return;
    // Logika transmisi buffer ke WebGL/Canvas
  }

  public applyOptions(options: { theme: string }) {
    if (this.isDestroyed) return;
    this.options = { ...this.options, ...options };
    this.initCanvas();
  }

  public resetViewport() {
    // Logika kalkulasi matriks kamera chart
  }

  public capture(): Promise<Blob | null> {
    return Promise.resolve(new Blob([], { type: 'image/png' }));
  }

  public destroy() {
    this.isDestroyed = true;
    this.container.innerHTML = '';
  }
}

// 2. Komponen Batas Imperatif (Imperative Boundary Component)
export const TradingChartBoundary = memo(
  forwardRef<ChartImperativeHandle, TradingChartProps>(
    ({ data, theme, onCrosshairMove }, ref) => {
      // Simpul DOM yang akan "diserahkan" kepemilikannya ke Engine Imperatif
      const containerRef = useRef<HTMLDivElement | null>(null);
      
      // Instance engine disimpan dalam Ref murni: BUKAN STATE (tidak memicu re-render)
      const engineInstanceRef = useRef<ImperativeChartEngine | null>(null);

      // Callback ref mutable untuk memotong dependensi effect yang volatil
      const crosshairCallbackRef = useRef(onCrosshairMove);
      useLayoutEffect(() => {
        crosshairCallbackRef.current = onCrosshairMove;
      });

      // 3. Batas Lifecycle & Instansiasi Engine (Mount / Destroy Boundary)
      useEffect(() => {
        const hostElement = containerRef.current;
        if (!hostElement) return;

        // Inisialisasi Engine Imperatif
        const engine = new ImperativeChartEngine(hostElement, { theme });
        engineInstanceRef.current = engine;

        // Strict Cleanup Phase
        return () => {
          engine.destroy();
          engineInstanceRef.current = null;
        };
      }, []); // Dependency kosong: Engine hanya dibuat 1x sepanjang masa hidup elemen host

      // 4. Sinkronisasi Data Properti Reaktif Terpisah
      useEffect(() => {
        if (engineInstanceRef.current) {
          engineInstanceRef.current.setData(data);
        }
      }, [data]);

      // 5. Sinkronisasi Konfigurasi UI (Theme)
      useEffect(() => {
        if (engineInstanceRef.current) {
          engineInstanceRef.current.applyOptions({ theme });
        }
      }, [theme]);

      // 6. Mengabstraksikan dan Membatasi Antarmuka via useImperativeHandle
      useImperativeHandle(
        ref,
        () => ({
          resetZoom: () => {
            if (engineInstanceRef.current) {
              engineInstanceRef.current.resetViewport();
            }
          },
          exportChartAsBlob: async () => {
            if (!engineInstanceRef.current) return null;
            return await engineInstanceRef.current.capture();
          },
        }),
        [] // Tidak ada dependency: fungsi delegate mengevaluasi engineInstanceRef yang mutabel secara stabil
      );

      return (
        <div 
          className="chart-wrapper-host" 
          style={{ position: 'relative', width: '100%' }}
        >
          {/* Host node murni: React dilarang merekonsiliasi anak-anak div ini */}
          <div ref={containerRef} style={{ width: '100%', minHeight: '400px' }} />
        </div>
      );
    }
  )
);

TradingChartBoundary.displayName = 'TradingChartBoundary';
