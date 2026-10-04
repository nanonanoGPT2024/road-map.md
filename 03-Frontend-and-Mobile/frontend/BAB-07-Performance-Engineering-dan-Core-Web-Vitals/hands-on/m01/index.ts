// CoreWebVitalsCollector.ts

export interface MetricPayload {
  name: 'LCP' | 'INP' | 'CLS';
  value: number;
  rating: 'good' | 'needs-improvement' | 'poor';
  navigationPreload?: number;
  entries: PerformanceEntry[];
}

export class CoreWebVitalsCollector {
  private clsScore: number = 0;
  private clsEntries: PerformanceEntry[] = [];
  private sessionValue: number = 0;
  private sessionEntries: PerformanceEntry[] = [];
  private onMetric: (metric: MetricPayload) => void;

  constructor(callback: (metric: MetricPayload) => void) {
    this.onMetric = callback;
    this.initLCPObserver();
    this.initCLSObserver();
    this.initINPObserver();
  }

  private getRating(name: MetricPayload['name'], value: number): MetricPayload['rating'] {
    const thresholds = {
      LCP: { good: 2500, poor: 4000 },
      INP: { good: 200, poor: 500 },
      CLS: { good: 0.1, poor: 0.25 },
    };

    if (value <= thresholds[name].good) return 'good';
    if (value <= thresholds[name].poor) return 'needs-improvement';
    return 'poor';
  }

  private initLCPObserver(): void {
    if (!PerformanceObserver.supportedEntryTypes.includes('largest-contentful-paint')) {
      return;
    }

    const observer = new PerformanceObserver((entryList) => {
      const entries = entryList.getEntries();
      const lastEntry = entries[entries.length - 1] as PerformanceEntry;

      this.onMetric({
        name: 'LCP',
        value: lastEntry.startTime,
        rating: this.getRating('LCP', lastEntry.startTime),
        entries: [lastEntry],
      });
    });

    observer.observe({ type: 'largest-contentful-paint', buffered: true });
  }

  private initCLSObserver(): void {
    if (!PerformanceObserver.supportedEntryTypes.includes('layout-shift')) {
      return;
    }

    const observer = new PerformanceObserver((entryList) => {
      for (const entry of entryList.getEntries() as any[]) {
        // Abaikan shift yang dipicu oleh interaksi pengguna (hadRecentInput = true)
        if (!entry.hadRecentInput) {
          const firstSessionEntry = this.sessionEntries[0];
          const lastSessionEntry = this.sessionEntries[this.sessionEntries.length - 1];

          // CLS Session Window Logic (max 5s, gap max 1s)
          if (
            this.sessionValue &&
            entry.startTime - lastSessionEntry.startTime < 1000 &&
            entry.startTime - firstSessionEntry.startTime < 5000
          ) {
            this.sessionValue += entry.value;
            this.sessionEntries.push(entry);
          } else {
            this.sessionValue = entry.value;
            this.sessionEntries = [entry];
          }

          if (this.sessionValue > this.clsScore) {
            this.clsScore = this.sessionValue;
            this.clsEntries = this.sessionEntries;

            this.onMetric({
              name: 'CLS',
              value: this.clsScore,
              rating: this.getRating('CLS', this.clsScore),
              entries: this.clsEntries,
            });
          }
        }
      }
    });

    observer.observe({ type: 'layout-shift', buffered: true });
  }

  private initINPObserver(): void {
    if (!PerformanceObserver.supportedEntryTypes.includes('event')) {
      return;
    }

    let maxDuration = 0;
    let worstEntry: PerformanceEntry | null = null;

    const observer = new PerformanceObserver((entryList) => {
      const entries = entryList.getEntries() as any[];

      for (const entry of entries) {
        // Hanya pantau interaksi yang valid dan memiliki interactionId
        if (entry.interactionId) {
          const duration = entry.duration;
          if (duration > maxDuration) {
            maxDuration = duration;
            worstEntry = entry;

            this.onMetric({
              name: 'INP',
              value: maxDuration,
              rating: this.getRating('INP', maxDuration),
              entries: [worstEntry],
            });
          }
        }
      }
    });

    // durationThreshold 16ms memastikan kita menangkap interaksi bermasalah (> 1 frame)
    observer.observe({
      type: 'event',
      durationThreshold: 16,
      buffered: true,
    } as any);
  }
}
