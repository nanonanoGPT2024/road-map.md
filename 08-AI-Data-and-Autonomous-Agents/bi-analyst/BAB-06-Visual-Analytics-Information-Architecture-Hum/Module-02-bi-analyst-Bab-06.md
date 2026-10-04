# BAB 06: Visual Analytics, Information Architecture, & Human-Data Interaction
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Mendesain dan Mengimplementasikan Arsitektur Headless BI:** Membangun lapisan konsumsi analitik terpisah (*decoupled semantic layer*) yang melayani antarmuka visual berbasis web dengan latensi sub-detik (<800ms).
- **Mengoptimalkan Human-Data Interaction (HDI):** Menerapkan teori kognitif (Gestalt, *Preattentive Processing*, *Visual Information-Seeking Mantra*) ke dalam desain sistem analitik multi-tier guna meminimalkan *cognitive load*.
- **Membangun Pipelines Visual Analytics Skala Enterprise:** Mengintegrasikan mesin *pre-aggregation*, *caching layer*, *dynamic query pushdown*, dan integrasi model AI/LLM untuk *automated root-cause analysis* (RCA).
- **Mengevaluasi Trade-offs Rendering Engine:** Memilih dan mengonfigurasi mesin render (*Canvas vs. SVG vs. WebGL*) untuk visualisasi data densitas tinggi (>100.000 titik data).
- **Menegakkan Tata Kelola & Observabilitas Visualisasi:** Menerapkan pengujian otomatis pada visualisasi data, *metric drift detection*, serta metrik performa UX (*Core Web Vitals* untuk dashboard analitik).

---

### 2. Prerequisite
- Pemahaman mendalam tentang pemodelan data dimensional (Kimball, Inmon, Data Vault 2.0).
- Kemahiran SQL tingkat lanjut (Window Functions, CTE, Partitioning, Execution Plan Analysis).
- Pengalaman dengan Semantic Layer (dbt MetricFlow, Cube.js, atau Looker LookML).
- Kemampuan pemrograman JavaScript/TypeScript tingkat menengah (Node.js, ekosistem React/Vue, serta pustaka visualisasi seperti Apache ECharts, D3.js, atau Vega-Lite).
- Pemahaman arsitektur data warehouse modern (Snowflake, BigQuery, ClickHouse, atau DuckDB).

---

### 3. Concept & Internal Architecture (Mendalam)

Arsitektur *Visual Analytics* tingkat enterprise tidak lagi mengandalkan koneksi langsung (*direct query*) dari *monolithic dashboard tool* ke *data warehouse*, melainkan menggunakan paradigma **Headless Semantic & Visual Analytics Architecture**.

```
[ Data Warehouse / Lakehouse ]
         │ (Pushdown / Rollup Query)
         ▼
┌──────────────────────────────────────────────┐
│        Headless Semantic Engine Layer        │
│  - Metrics & Dimensions Definition (Code)    │
│  - Access Control / RBAC / Multi-tenancy     │
│  - SQL Compilation & AST Rewriting           │
└──────────────────────┬───────────────────────┘
                       │
         ┌─────────────┴─────────────┐
         ▼                           ▼
┌──────────────────┐       ┌──────────────────┐
│ In-Memory Cache  │       │ Pre-Aggregation  │
│ (Redis / DuckDB) │       │ (Partitioned)    │
└────────┬─────────┘       └────────┬─────────┘
         │                          │
         └─────────────┬────────────┘
                       │ JSON via GraphQL / REST / Arrow Flight
                       ▼
┌──────────────────────────────────────────────┐
│           Visual Orchestration Layer         │
│  - Cognitive Hierarchy Engine                │
│  - AI Anomaly Explainer / RCA Integration    │
│  - Dynamic Aggregation (LOD Algorithms)      │
└──────────────────────┬───────────────────────┘
                       │
         ┌─────────────┴─────────────┐
         ▼                           ▼
┌──────────────────┐       ┌──────────────────┐
│ SVG Render Tree  │       │ Canvas / WebGL   │
│ (DOM Interactive)│       │ (High-Density)   │
└──────────────────┘       └──────────────────┘
```

#### Komponen Internal Utama:

1. **Semantic Query Compiler & AST Rewriter:**
   Mesin ini bertugas menerjemahkan permintaan visualisasi tingkat tinggi (misal: "Bandingkan *Gross Margin* MoM berdasarkan Region") menjadi Abstract Syntax Tree (AST). AST ini dioptimalkan dengan mengeliminasi *join* yang tidak perlu (*join pruning*), mendorong filter ke tingkat paling dasar (*predicate pushdown*), dan memetakan metrik ke tabel *pre-aggregation* terdekat.

2. **Pre-Aggregation & Rollup Hierarchy Engine:**
   Untuk mencegah kueri analitik membebani Data Warehouse (yang berimplikasi pada *cost* dan *concurrency degradation*), layer ini mengeksekusi strategi *multi-level rollup*:
   - Raw granular (Level 0 - Warehouse)
   - Hourly rollup partitioned by tenant/segment (Level 1 - ClickHouse/DuckDB)
   - In-memory result cache (Level 2 - Redis/Memory)

3. **Level of Detail (LOD) & Data Decimation Pipeline:**
   Mata manusia tidak dapat membedakan lebih dari ~1.000 titik horizontal dalam rentang tampilan standar tanpa zooming. Sebelum payload data dikirim ke browser, algoritma decimasi (misalnya: *Largest-Triangle-Three-Buckets* / LTTB) berjalan di edge server untuk mereduksi 5.000.000 titik deret waktu menjadi 1.500 titik representatif tanpa menghilangkan *visual outliers* atau puncak gelombang.

4. **Human-Data Interaction (HDI) Internal Execution Loop:**
   Berdasarkan teori kognitif Ben Shneiderman (*Overview first, zoom and filter, then details-on-demand*):
   - **Stage 1 (System State):** Kompresi data global menggunakan kartu skor KPI dan representasi *Sparkline* densitas tinggi.
   - **Stage 2 (Exploration State):** State management berbasis URL/Deep-link yang mereplikasi irisan koordinat data multidimensi (Cross-filtering, Brushing).
   - **Stage 3 (Cognitive Contextualization):** Korelasi otomatis dengan *contextual agents* yang menginjeksi anotasi teks alami jika metrik menyimpang $\pm 3\sigma$ dari baseline.

---

### 4. Why & What

| Dimensi | Legacy BI Monolith (Tableau/PowerBI/Qlik Native Direct) | Modern Production Visual Analytics |
| :--- | :--- | :--- |
| **Arsitektur** | Terikat erat (*Tight coupling*) antara antarmuka visual, logika bisnis, dan driver kueri. | Terpisah (*Decoupled*): Semantic Layer terpusat, Visual Layer berbasis Web Framework modern. |
| **Version Control** | File biner (.pbix, .twb) yang sulit di-*diff* dan di-*merge* via Git. | *Code-first* (YAML/JSON/TypeScript) yang terintegrasi penuh ke dalam CI/CD. |
| **Latensi & Skalabilitas** | Eksekusi kueri berulang ke DWH; rentan terhadap batas konkurensi (biasanya melambat pada >50 user serentak). | *Tiered Pre-aggregations* & In-memory Caching; mampu melayani ribuan *concurrent queries* dengan latensi <800ms. |
| **Ekstensibilitas & AI** | Terbatas pada plugin bawaan vendor; integrasi AI seringkali bersifat *black box*. | Bebas mengintegrasikan custom WebGL visualizer, LLM explainability agents, dan komponen UX kustom. |
| **Konsistensi Metrik** | Tingginya risiko "Metric Drift" di mana dua dashboard menghasilkan angka berbeda untuk KPI yang sama. | *Single Source of Truth* (SSOT) melalui Semantic API yang tidak dapat diubah sepihak oleh visual developer. |

---

### 5. How (Workflow Detail)

Alur kerja ujung-ke-ujung (end-to-end) dari data mentah hingga interaksi kognitif pengguna diatur dalam 6 fase produksi:

```
[Fase 1: Semantic Modeling] 
   └── Mendefinisikan Cube, Measures, Dimensions, Joins, dan Pre-aggregation rules via YAML/TypeScript.
[Fase 2: Compilation & Warm-up]
   └── CI/CD pipeline memvalidasi skema semantik, menjalankan DRY run SQL ke DWH, dan memanaskan (warm-up) tabel pre-agregasi.
[Fase 3: Request Handling & Routing]
   └── Client mengirimkan GraphQL/REST payload -> Semantic Router mengevaluasi apakah kueri dilayani via Cache, Rollup, atau DWH Raw.
[Fase 4: Edge Decimation & Anomaly Evaluation]
   └── Payload hasil kueri dipotong via LTTB Algorithm jika densitas titik > resolusi kanvas. Engine mendeteksi outlier untuk trigger context tag.
[Fase 5: UI Render Optimization]
   └── Dynamic Canvas/WebGL engine memetakan koordinat ke frame buffer tanpa memblokir Main Thread (Web Workers).
[Fase 6: Interaction & Context Propagation]
   └── Interaksi pengguna (e.g., box-select / cross-filter) mengubah global state atomik -> memicu partial render melalui micro-queries.
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Kokpit Pesawat Tempur Supersonik vs. Ruang Arsip Fisik
Melihat dashboard monolitik lama itu seperti masuk ke **Ruang Arsip Dokumen**: Ketika pilot (eksekutif) ingin tahu kecepatan angin, seseorang harus berlari ke tumpukan berkas mentah (Warehouse), menghitung rata-rata secara manual, lalu menggambar grafik dengan pena di kertas (Browser Render). Jika kertas robek atau meja penuh, pilot terlambat membuat keputusan.

Arsitektur **Visual Analytics Modern** adalah **Heads-Up Display (HUD) Kokpit Pesawat Tempur**:
Sensor mentah disaring oleh komputer penerbangan (*Semantic Engine*), disimpan di memori sirkuit (*Pre-aggregations*), dan diproyeksikan ke kaca kokpit via laser (*WebGL/Canvas*). Pilot hanya melihat anomali kritis melalui visual terstandar dengan *zero lag*, didukung radar pintar (*AI Contextual Explainer*) yang memberi tahu penyebab turbulensi sebelum pilot sempat bertanya.

```
                      +---------------------------------------+
                      |               USER                    |
                      +---------------------------------------+
                                          |
                                   1. Interaksi (Pan/Zoom/Filter)
                                          v
                      +---------------------------------------+
                      |         Application Frontend          |
                      |   (State Manager: Jotai/Zustand)      |
                      +---------------------------------------+
                                          |
                        2. Fetch Metric Request (GraphQL/REST)
                                          v
                      +---------------------------------------+
                      |        Semantic Layer (Cube.js)       |
                      +---------------------------------------+
                               /                     \
                   [Cache Hit]/                       \[Cache Miss]
                             v                         v
               +-----------------------+     +-----------------------+
               | In-Memory Cache/DuckDB|     | Data Warehouse SQL    |
               | (Latensi < 100ms)     |     | (Snowflake/ClickHouse)|
               +-----------------------+     +-----------------------+
                             \                         /
                              \                       /
                               v                     v
                      +---------------------------------------+
                      | Web Worker / Decimation Engine (LTTB) |
                      +---------------------------------------+
                                          |
                              3. ArrayBuffer / TypedArray
                                          v
                      +---------------------------------------+
                      |      Canvas 2D / WebGL Renderer       |
                      |          (Apache ECharts Engine)      |
                      +---------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Semantic Layer Definition & Dynamic Aggregation (Cube.js/DuckDB syntax concept)

Definisi skema semantik terpusat yang memproteksi rumus agregasi dan mengonfigurasi *rollup table* otomatis.

```javascript
// schema/Orders.js (Cube.js Semantic Definition)
cube(`Orders`, {
  sql: `SELECT * FROM analytics_prod.fact_orders`,

  measures: {
    count: {
      type: `count`,
      drillMembers: [id, createdAt]
    },

    totalRevenue: {
      sql: `net_amount`,
      type: `sum`,
      format: `currency`
    },

    averageOrderValue: {
      sql: `${totalRevenue} / NULLIF(${count}, 0)`,
      type: `number`,
      format: `currency`
    }
  },

  dimensions: {
    id: {
      sql: `order_id`,
      type: `string`,
      primaryKey: true
    },

    status: {
      sql: `order_status`,
      type: `string`
    },

    createdAt: {
      sql: `created_at`,
      type: `time`
    }
  },

  preAggregations: {
    // Rollup otomatis untuk mempercepat visualisasi tren harian
    dailyRevenueRollup: {
      measures: [totalRevenue, count],
      dimensions: [status],
      timeDimension: createdAt,
      granularity: `day`,
      partitionGranularity: `month`,
      refreshKey: {
        every: `1 hour`
      }
    }
  }
});
```

#### B. Practical Example: Production-Grade High-Performance Visual Analytics Component

Komponen berikut menggunakan React, Apache ECharts, dan Web Worker untuk menerapkan algoritma LTTB (Largest-Triangle-Three-Buckets) guna merender 100.000 titik data time-series secara mulus tanpa *main-thread blocking*.

```typescript
// src/utils/lttbWorker.ts
// Web Worker untuk mengeksekusi decimasi data LTTB di luar UI Thread

export const lttbCode = `
self.onmessage = function(e) {
  const { data, threshold } = e.data;
  if (threshold >= data.length || threshold === 0) {
    self.postMessage(data);
    return;
  }

  const sampled = [];
  const every = (data.length - 2) / (threshold - 2);
  let a = 0;
  let maxAreaPoint;
  let maxArea;
  let nextA;

  sampled.push(data[a]); // Selalu sertakan titik awal

  for (let i = 0; i < threshold - 2; i++) {
    let avgX = 0;
    let avgY = 0;
    let avgRangeStart = Math.floor((i + 1) * every) + 1;
    let avgRangeEnd = Math.floor((i + 2) * every) + 1;
    avgRangeEnd = avgRangeEnd < data.length ? avgRangeEnd : data.length;

    const avgRangeLength = avgRangeEnd - avgRangeStart;
    for (; avgRangeStart < avgRangeEnd; avgRangeStart++) {
      avgX += data[avgRangeStart][0];
      avgY += data[avgRangeStart][1];
    }
    avgX /= avgRangeLength;
    avgY /= avgRangeLength;

    let rangeOffs = Math.floor(i * every) + 1;
    const rangeTo = Math.floor((i + 1) * every) + 1;
    const pointAX = data[a][0];
    const pointAY = data[a][1];
    maxArea = -1;

    for (; rangeOffs < rangeTo; rangeOffs++) {
      const area = Math.abs(
        (pointAX - avgX) * (data[rangeOffs][1] - pointAY) -
        (pointAX - data[rangeOffs][0]) * (avgY - pointAY)
      ) * 0.5;

      if (area > maxArea) {
        maxArea = area;
        maxAreaPoint = data[rangeOffs];
        nextA = rangeOffs;
      }
    }

    sampled.push(maxAreaPoint);
    a = nextA;
  }

  sampled.push(data[data.length - 1]); // Selalu sertakan titik akhir
  self.postMessage(sampled);
};
`;
```

```tsx
// src/components/HighDensityChart.tsx
import React, { useEffect, useRef, useState, useMemo } from 'react';
import * as echarts from 'echarts';

interface HighDensityChartProps {
  rawData: [number, number][]; // Tuple [Timestamp, Value]
  targetResolution?: number;
  metricName: string;
}

export const HighDensityChart: React.FC<HighDensityChartProps> = ({
  rawData,
  targetResolution = 2000,
  metricName
}) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);
  const [processedData, setProcessedData] = useState<[number, number][]>([]);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);

  // Inisialisasi Web Worker dari inline string
  const worker = useMemo(() => {
    const blob = new Blob([lttbCode], { type: 'application/javascript' });
    return new Worker(URL.createObjectURL(blob));
  }, []);

  useEffect(() => {
    if (!rawData || rawData.length === 0) return;

    setIsProcessing(true);
    worker.postMessage({ data: rawData, threshold: targetResolution });

    worker.onmessage = (e: MessageEvent<[number, number][]>) => {
      setProcessedData(e.data);
      setIsProcessing(false);
    };

    return () => {
      worker.terminate();
    };
  }, [rawData, targetResolution, worker]);

  // Inisialisasi ECharts Canvas Context
  useEffect(() => {
    if (!chartRef.current) return;

    // Paksa penggunaan Canvas renderer untuk high-performance streaming/rendering
    chartInstance.current = echarts.init(chartRef.current, undefined, {
      renderer: 'canvas',
      useDirtyRect: true // Optimasi dirty-rectangle rendering
    });

    const handleResize = () => {
      chartInstance.current?.resize();
    };

    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
      chartInstance.current?.dispose();
    };
  }, []);

  // Update option chart saat data hasil decimasi siap
  useEffect(() => {
    if (!chartInstance.current || processedData.length === 0) return;

    const option: echarts.EChartsOption = {
      animation: false, // Matikan animasi untuk latensi instan saat data points masif
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          const date = new Date(params[0].value[0]).toISOString();
          const val = params[0].value[1].toLocaleString();
          return `<b>${date}</b><br/>${metricName}: <b>${val}</b>`;
        }
      },
      grid: {
        top: 30,
        right: 20,
        bottom: 40,
        left: 60,
        containLabel: false
      },
      xAxis: {
        type: 'time',
        boundaryGap: false,
        axisLine: { lineStyle: { color: '#888' } }
      },
      yAxis: {
        type: 'value',
        scale: true,
        splitLine: { lineStyle: { color: '#eee' } }
      },
      series: [
        {
          name: metricName,
          type: 'line',
          sampling: 'lttb', // Double fallback via native C++ engine if needed
          showSymbol: false,
          data: processedData,
          lineStyle: {
            width: 1.5,
            color: '#0052CC'
          },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(0, 82, 204, 0.3)' },
              { offset: 1, color: 'rgba(0, 82, 204, 0.01)' }
            ])
          }
        }
      ]
    };

    chartInstance.current.setOption(option);
  }, [processedData, metricName]);

  return (
    <div style={{ position: 'relative', width: '100%', height: '400px' }}>
      {isProcessing && (
        <div style={{
          position: 'absolute',
          top: 10,
          right: 10,
          zIndex: 10,
          background: 'rgba(255,255,255,0.8)',
          padding: '4px 8px',
          borderRadius: 4,
          fontSize: 12
        }}>
          Memproses {rawData.length.toLocaleString()} points...
        </div>
      )}
      <div ref={chartRef} style={{ width: '100%', height: '100%' }} />
    </div>
  );
};
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem:
Sebuah perusahaan logistik on-demand regional memproses **25 juta transaksi per hari** di 5 negara. Tim operasional membutuhkan *Operations Control Cockpit* untuk memantau metrik kritis: *SLA Fulfillment Rate*, *Driver Allocation Time*, dan *Surge Pricing Factor* secara real-time dan historis (rentang 90 hari) dengan filter tingkat armada, geofence, dan kota.

#### Masalah Arsitektur Sebelumnya:
- Menggunakan dashboard monolitik BI tradisional yang terhubung via ODBC langsung ke Amazon Redshift.
- Saat 200 *City Operations Leads* membuka dashboard di awal jam sibuk, Redshift mengalami *concurrency queueing*. Latensi kueri melonjak dari 4 detik menjadi **180+ detik** (atau timeout).
- Browser pengguna sering mengalami *out-of-memory crash* karena aplikasi mencoba merender 120.000 titik koordinat GPS ke dalam DOM elemen SVG.

#### Solusi yang Diimplementasikan:
1. **Semantic Decoupling:** Membangun headless semantic layer menggunakan **Cube** yang membaca dari Redshift, namun dialihkan ke **ClickHouse** sebagai layer *pre-aggregation*.
2. **Tiered Aggregation Strategy:**
   - Detik 0 s.d. 3 Jam terakhir: Streaming ingestion via Kafka ke ClickHouse (agregasi 10 detik).
   - Data historis (> 3 Jam): Pre-aggregated table harian dan mingguan di Redshift diekspor ke ClickHouse.
3. **Decimated Rendering:** Mengimplementasikan WebGL-based visualization (*Deck.gl + Apache ECharts*) dengan *LTTB dynamic decimation* melalui Web Workers.
4. **Contextual Root-Cause Engine:** Integrasi model inferensi lokal (FastAPI + LLM Agent) yang mengevaluasi deviasi metrik. Jika metrik *Allocation Time* naik >20%, model secara otomatis mengekstrak 3 segmen dengan korelasi tertinggi (misal: "Hujan ekstrem di Jakarta Barat") dan menyuntikkannya sebagai *callout card* di UI.

#### Metrik Keberhasilan:
- **P95 Dashboard Latency:** Berkurang dari 180 detik menjadi **620 milidetik**.
- **Data Warehouse Monthly Compute Cost:** Turun sebesar **68%** karena reduksi kueri redundan langsung ke Redshift.
- **Client Crash Rate:** Turun ke **0%** dengan utilisasi memori browser stabil di kisaran <150MB terlepas dari ukuran dataset.

---

### 9. Trade-offs

Setiap keputusan arsitektur dalam visual analytics memiliki kompromi teknis:

| Desain / Pendekatan | Keuntungan | Biaya / Trade-off | Kapan Harus Digunakan |
| :--- | :--- | :--- | :--- |
| **SVG Rendering (D3.js native)** | Kualitas grafis tajam tanpa batas (vektor), dukungan selektor CSS native, aksesibilitas DOM tinggi. | Performa $O(N)$ terhadap elemen DOM; lag parah jika objek $>2.000$ titik. | Diagram silsilah data (*Lineage*), peta hierarki node kecil, dashboard dengan grafik batang/donat sederhana. |
| **HTML5 Canvas (ECharts/Chart.js)** | Performa cepat; rendering jutaan piksel dalam 1 frame buffer tanpa overhead DOM. | Bersifat raster (resolusi kabur jika di-zoom tanpa redraw); event handling manual per elemen grafis. | Analitik time-series standar industri, grafik keuangan, densitas medium ($2.000 - 50.000$ titik). |
| **WebGL (Deck.gl/Three.js)** | Memanfaatkan GPU penuh; mampu merender $>1.000.000$ titik dan spasial 3D pada 60 FPS. | Overhead inisialisasi tinggi, konsumsi baterai perangkat mobile signifikan, kompleksitas debugging tinggi. | Visualisasi geospasial real-time, sensor IoT masif, visualisasi embedding klaster multi-dimensi. |
| **Dynamic Server-side Decimation (LTTB)** | Menghemat bandwidth jaringan secara drastis, proteksi terhadap crash pada client. | Beban komputasi tambahan pada server/edge; hilangnya detail mikro jika parameter decimasi salah. | Data historis multi-bulan/tahun yang dibuka di antarmuka web desktop maupun mobile. |
| **Full Aggregated Rollup Tables** | Kueri sub-detik instan ($<50ms$); biaya komputasi runtime mendekati nol. | Kehilangan kapabilitas drill-down ke level baris transaksi individual (*loss of grain*). | Dashboard C-Level, metrik eksekutif tingkat tinggi tanpa kebutuhan forensik transaksional. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Masalah: "Dashboard Graveyard" & Cognitive Overload
- **Gejala:** Pengguna mengeluhkan dashboard terlalu membingungkan dan akhirnya kembali meminta ekspor file Excel mentah.
- **Root Cause:** Kegagalan menerapkan *Information Architecture Hierarchy*. Memuat 30 grafik berbeda dengan palet warna pelangi dalam satu layar tanpa visual flow.
- **Solusi:** Terapkan aturan kognitif 5 detik. Pisahkan arsitektur dashboard menjadi model 3-tingkat:
  1. *Executive Summary Screen* (Max 4 KPI + 1 trendline global).
  2. *Diagnostic View* (Korelasi & Slice-and-dice).
  3. *Operational Ledger* (Tabel raw data dengan pagination/server-side virtual scroll).

#### 2. Masalah: Memory Leaks pada Canvas/SVG Instance
- **Gejala:** Tab browser perlahan memakan memori hingga >2GB ketika pengguna membiarkan dashboard terbuka sepanjang hari (*kiosk mode*).
- **Root Cause:** Instance chart tidak di-*dispose* secara tepat saat re-render komponen (misal: di React `useEffect` tidak mengembalikan fungsi cleanup yang memanggil `chartInstance.dispose()`).
- **Solusi:**
  ```typescript
  useEffect(() => {
    const chart = echarts.init(domRef.current);
    // ... konfig
    return () => {
      chart.dispose(); // Wajib: Hancurkan instance dan bebaskan context canvas dari V8 heap
    };
  }, [dependencies]);
  ```

#### 3. Masalah: Metric Drift antar Dashboard
- **Gejala:** Tim Keuangan melaporkan *Churn Rate* 5.2%, sedangkan Tim Pemasaran melaporkan 3.8% pada rentang bulan yang sama.
- **Root Cause:** Logika agregasi ditulis manual di masing-masing UI script/SQL kueri dashboard individu.
- **Solusi:** Isolasi metrik secara absolut ke dalam *Semantic Layer Codebase*. CI/CD harus memblokir merge PR jika ada deklarasi kueri yang menghitung metrik derivatif langsung di client-side.

---

### 11. Best Practices (Production Checklist)

Gunakan daftar periksa teknis ini sebelum merilis sistem Visual Analytics ke lingkungan produksi:

- [ ] **Semantic Single-Source-of-Truth:** Tidak ada rumus kalkulasi bisnis (agregasi, pembagian, windowing) yang ditulis langsung di lapisan antarmuka pengguna (Frontend).
- [ ] **LTTB/Downsampling Guardrail:** Data time-series berukuran $>3.000$ baris harus melalui algoritma decimasi sebelum masuk ke thread visualizer.
- [ ] **Core Web Vitals Thresholds:**
  - Largest Contentful Paint (LCP) dashboard $< 1.5$ detik pada jaringan 4G.
  - Interaction to Next Paint (INP) untuk operasi filter/brush $< 100$ milidetik.
  - Cumulative Layout Shift (CLS) mendekati $0$ (gunakan layout skeleton placeholder sebelum grafik selesai dimuat).
- [ ] **Accessibility (WCAG 2.1 AA Compliance):**
  - Palet warna mematuhi rasio kontras minimum $4.5:1$ terhadap background.
  - Visualisasi tidak mengandalkan warna semata untuk menyampaikan status (gunakan pola titik/garis atau ikon pendukung).
  - Elemen interaktif dapat diakses melalui navigasi Tab keyboard.
- [ ] **Failover & Query Timeout Limits:** Kueri visual layer dibatasi timeout ketat ($10$ detik). Jika timeout tercapai, sistem secara otomatis memberikan opsi agregasi fallback atau visualisasi berbasis *cached snapshot*.

---

### 12. Hands-on Practice

Dalam sesi praktikum ini, Anda akan membangun sistem *high-density visualizer* mandiri yang membaca jutaan metrik buatan menggunakan DuckDB WASM / In-Memory Mock, memprosesnya melalui LTTB Decimator, dan merendernya secara real-time.

Simpan seluruh file praktikum di direktori: `hands-on/m02/`

#### Langkah 1: Siapkan Struktur Folder & File
```bash
mkdir -p hands-on/m02/src
cd hands-on/m02
npm init -y
npm install typescript echarts @types/echarts vite --save-dev
```

#### Langkah 2: Buat Skrip Mock Data Generator (100.000 Titik Data)
Buat file `hands-on/m02/src/mockData.ts`:
```typescript
export function generateTimeseriesData(pointCount: number): [number, number][] {
  const data: [number, number][] = [];
  let baseValue = 500;
  const startTime = new Date('2025-01-01T00:00:00Z').getTime();
  const stepMs = 60 * 1000; // 1 menit per step

  for (let i = 0; i < pointCount; i++) {
    const timestamp = startTime + i * stepMs;
    // Random walk with trend and seasonal spikes
    const noise = (Math.random() - 0.5) * 20;
    const seasonality = Math.sin((i / 1440) * 2 * Math.PI) * 50; // Daily pattern
    baseValue += (Math.random() - 0.49) * 5;
    
    // Injeksi Outlier ekstrem sesekali (misal anomali sistem)
    let finalValue = baseValue + noise + seasonality;
    if (i % 15000 === 0 && i !== 0) {
      finalValue += 300; // Spike outlier
    }

    data.push([timestamp, Math.round(finalValue * 100) / 100]);
  }

  return data;
}
```

#### Langkah 3: Implementasikan Runner HTML & Engine Visualizer
Buat file `hands-on/m02/index.html`:
```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Hands-on M02: High-Density Visual Analytics</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 20px; background: #f4f6f8; }
    .card { background: white; border-radius: 8px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
    #chart-container { width: 100%; height: 500px; margin-top: 15px; }
    .metrics-bar { display: flex; gap: 20px; margin-bottom: 10px; font-size: 14px; }
  </style>
</head>
<body>
  <div class="card">
    <h2>Enterprise Visual Analytics Engine: LOD Decimation Pipeline</h2>
    <div class="metrics-bar">
      <div>Titik Data Asli: <strong id="raw-count">0</strong></div>
      <div>Titik Terender (LOD): <strong id="rendered-count">0</strong></div>
      <div>Durasi Pemrosesan: <strong id="exec-time">0 ms</strong></div>
    </div>
    <div id="chart-container"></div>
  </div>
  <script type="module" src="/src/main.ts"></script>
</body>
</html>
```

#### Langkah 4: Tulis Logika Utama pada `src/main.ts`
Buat file `hands-on/m02/src/main.ts`:
```typescript
import * as echarts from 'echarts';
import { generateTimeseriesData } from './mockData';

// Implementasi LTTB Synchronous Engine
function applyLTTB(data: [number, number][], threshold: number): [number, number][] {
  if (threshold >= data.length || threshold === 0) return data;
  const sampled: [number, number][] = [];
  const every = (data.length - 2) / (threshold - 2);
  let a = 0;
  let maxAreaPoint: [number, number] = data[0];
  let maxArea: number;
  let nextA = 0;

  sampled.push(data[a]);

  for (let i = 0; i < threshold - 2; i++) {
    let avgX = 0;
    let avgY = 0;
    let avgRangeStart = Math.floor((i + 1) * every) + 1;
    let avgRangeEnd = Math.floor((i + 2) * every) + 1;
    avgRangeEnd = avgRangeEnd < data.length ? avgRangeEnd : data.length;

    const avgRangeLength = avgRangeEnd - avgRangeStart;
    for (; avgRangeStart < avgRangeEnd; avgRangeStart++) {
      avgX += data[avgRangeStart][0];
      avgY += data[avgRangeStart][1];
    }
    avgX /= avgRangeLength;
    avgY /= avgRangeLength;

    let rangeOffs = Math.floor(i * every) + 1;
    const rangeTo = Math.floor((i + 1) * every) + 1;
    const pointAX = data[a][0];
    const pointAY = data[a][1];
    maxArea = -1;

    for (; rangeOffs < rangeTo; rangeOffs++) {
      const area = Math.abs(
        (pointAX - avgX) * (data[rangeOffs][1] - pointAY) -
        (pointAX - data[rangeOffs][0]) * (avgY - pointAY)
      ) * 0.5;

      if (area > maxArea) {
        maxArea = area;
        maxAreaPoint = data[rangeOffs];
        nextA = rangeOffs;
      }
    }

    sampled.push(maxAreaPoint);
    a = nextA;
  }

  sampled.push(data[data.length - 1]);
  return sampled;
}

// Main Execution
const rawCountEl = document.getElementById('raw-count')!;
const renderedCountEl = document.getElementById('rendered-count')!;
const execTimeEl = document.getElementById('exec-time')!;
const chartDom = document.getElementById('chart-container')!;

const TOTAL_POINTS = 100000;
const LOD_RESOLUTION = 1500;

console.time('Generate Data');
const rawData = generateTimeseriesData(TOTAL_POINTS);
console.timeEnd('Generate Data');

rawCountEl.innerText = rawData.length.toLocaleString();

const startTime = performance.now();
const downsampledData = applyLTTB(rawData, LOD_RESOLUTION);
const endTime = performance.now();

renderedCountEl.innerText = downsampledData.length.toLocaleString();
execTimeEl.innerText = `${(endTime - startTime).toFixed(2)} ms`;

const myChart = echarts.init(chartDom, undefined, { renderer: 'canvas' });
myChart.setOption({
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'time' },
  yAxis: { type: 'value' },
  series: [{
    type: 'line',
    showSymbol: false,
    data: downsampledData,
    lineStyle: { color: '#0066FF', width: 1.5 }
  }]
});

window.addEventListener('resize', () => myChart.resize());
```

---

### 13. Exercise

Kerjakan latihan berikut secara terstruktur:

#### Level Easy
Ubah konfigurasi styling pada grafik hands-on di atas untuk mematuhi standar *accessibility contrast*. Pastikan garis seri memiliki kontras rasio minimal $4.5:1$ terhadap background putih, serta tambahkan `markPoint` otomatis khusus untuk titik tertinggi (Max) dan titik terendah (Min).

#### Level Medium
Buat modul korelasi client-side: Ketika pengguna memilih rentang waktu tertentu menggunakan *brush zoom* pada sumbu horizontal (X-Axis), hitung koefisien variasi ($\sigma / \mu$) dari sub-dataset yang dipilih dan tampilkan status volatilitas (*Low*, *Medium*, *High*) pada badge UI secara reaktif tanpa memicu render ulang keseluruhan chart.

#### Level Hard
Modifikasi implementasi pipeline rendering agar algoritma LTTB berjalan secara *non-blocking* di dalam native **Web Worker**, lalu kembalikan payload data yang telah diproses menggunakan **Transferable Objects** (`ArrayBuffer` melalui `Float64Array`) alih-alih serialisasi objek JSON standar, untuk meminimalisasi latensi IPC (Inter-Process Communication).

---

### 14. Challenge

**Skenario Tantangan:**
Sebuah platform pertukaran aset kripto enterprise (*Crypto Exchange*) membutuhkan dashboard visualisasi *order book* dan volume transaksi terdistribusi yang harus memvisualisasikan **500.000 order per detik** dari koneksi WebSocket stream langsung. 

**Persyaratan Sistem yang Harus Anda Rancang & Buat Dokumen Arsitekturnya:**
1. Desain mekanisme *sliding window buffer* di lapisan web browser yang menjaga frame rate rendering stabil di **60 FPS** tanpa membuat memori browser membengkak (*bounded memory buffer*).
2. Tentukan arsitektur *rendering pipeline* (pilih antara pure Canvas 2D atau WebGL via Pixi.js / Three.js / Deck.gl) beserta alasannya.
3. Rancang mekanisme **Adaptive Decimation Threshold**: Jika CPU utilization browser terdeteksi melonjak $>80\%$, sistem harus secara dinamis menurunkan resolusi decimasi dari 2.000 titik menjadi 500 titik secara transparan tanpa terjadi *layout flash*.
4. Solusi tidak boleh mengabaikan *flash crashes* (jarum lilin anomali tajam tidak boleh hilang tereliminasi akibat algoritma decimasi).

*Kirimkan arsitektur berupa diagram sequence, pseudocode algoritma adaptive decimation, dan analisis trade-off memori.*

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Konsep Dasar (Basic)
1. **Mengapa DOM-based SVG rendering mengalami penurunan performa drastis ketika jumlah visualisasi melebihi puluhan ribu elemen?**
   - *Jawaban Singkat:* Karena setiap elemen SVG adalah node DOM terpisah yang membutuhkan overhead alokasi memori, perhitungan CSS box model, event listeners, dan reflow/repaint pada UI layout tree browser.
2. **Apa yang dimaksud dengan aturan "Overview first, zoom and filter, then details-on-demand" menurut Ben Shneiderman?**
   - *Jawaban Singkat:* Pola interaksi manusia-data di mana pengguna mula-mula disajikan gambaran data makro/ringkasan, diberikan alat untuk menyaring segmen yang relevan, dan hanya memuat detail granular granular mikro saat diminta secara eksplisit.
3. **Mengapa algoritma LTTB (Largest-Triangle-Three-Buckets) lebih disukai daripada Min-Max downsampling biasa untuk grafik time-series?**
   - *Jawaban Singkat:* Karena LTTB menjaga karakteristik visual kurva secara optimal (luas area segitiga efektif) tanpa memperkenalkan distorsi visual, sekaligus mempertahankan titik puncak dan lembah secara proporsional.
4. **Apa fungsi utama Semantic Layer dalam arsitektur decoupled analitik?**
   - *Jawaban Singkat:* Menyediakan Single Source of Truth (SSOT) untuk definisi logika bisnis, hierarki metrik, dan relasi tabel, terpisah dari antarmuka visualisasi presentasi data.
5. **Dalam prinsip Gestalt, hukum mana yang menjelaskan mengapa titik-titik data dengan warna yang sama dianggap oleh pengguna sebagai satu kelompok kategori fungsional?**
   - *Jawaban Singkat:* *Law of Similarity* (Hukum Kesamaan).

#### Bagian B: Konsep Menengah (Intermediate)
1. **Bagaimana mekanisme *Dirty Rectangle Rendering* pada HTML5 Canvas meningkatkan performa dashboard interaktif?**
   - *Jawaban Singkat:* Alih-alih menghapus dan menggambar ulang seluruh kanvas piksel per frame, mesin hanya merender ulang area sub-koordinat persegi panjang (*bounding box*) yang datanya mengalami perubahan.
2. **Apa dampak langsung dari fenomena "Metric Drift" terhadap operasional lintas departemen dalam sebuah enterprise?**
   - *Jawaban Singkat:* Hilangnya integritas data operasional dan kegagalan konsensus pengambilan keputusan akibat definisi metrik yang tidak konsisten antar alat visualisasi yang berbeda.
3. **Kapan WebGL mutlak dibutuhkan dibandingkan Canvas 2D dalam antarmuka Visual Analytics?**
   - *Jawaban Singkat:* Ketika memetakan objek data spasial 3D, representasi grafis dengan densitas titik $>100.000$, atau ketika membutuhkan visual pipeline shader langsung dari GPU.
4. **Bagaimana cara mengukur bahwa dashboard visualisasi data berhasil meminimalkan *Cognitive Load* pengguna?**
   - *Jawaban Singkat:* Diukur dari *Time-to-Insight* yang rendah, metrik penugasan tugas navigasi yang minim kesalahan (*low task error rate*), dan skor SUS (System Usability Scale) yang tinggi pada pengujian pengguna.
5. **Mengapa penggunaan Transferable Objects (`ArrayBuffer`) sangat krusial saat berkomunikasi dengan Web Worker pada analitik berdensitas tinggi?**
   - *Jawaban Singkat:* Karena Transferable Objects memindahkan kepemilikan memori secara langsung tanpa proses *structured cloning* (duplikasi salinan data), sehingga waktu transfer data menjadi mendekati $0$ ms.

#### Bagian C: Skenario Kasus Produksi
1. **Skenario 1:** Pengguna mengeluhkan dashboard operasional gudang mengalami lag parah (layar membeku selama 3 detik) setiap kali mereka menggeser slider rentang tanggal. Hasil profiling menunjukkan kueri SQL di Snowflake hanya butuh waktu 300ms, namun browser mengalami freeze.  
   *Diagnosa masalah dan langkah solusinya:*  
   - *Solusi:* Masalah ada pada Main Thread UI blocking di sisi client browser. Payload kueri mengembalikan puluhan ribu baris data yang langsung dirender ke antarmuka atau diproses oleh CPU thread utama. Solusinya: Lakukan agregasi/decimasi di layer backend atau pindahkan algoritma parsing data ke Web Worker, serta ganti renderer grafik dari SVG ke Canvas dengan opsi animasi dinonaktifkan.

2. **Skenario 2:** Sebuah visual analytics tool terintegrasi dengan AI LLM yang secara otomatis menafsirkan lonjakan grafik. Namun, seringkali ringkasan AI memberikan kesimpulan halusinasi yang bertentangan dengan angka visualisasi di grafik.  
   *Bagaimana merekayasa arsitekturnya untuk mengatasi hal ini?*  
   - *Solusi:* Implementasikan arsitektur *Deterministic Grounding Layer*. LLM tidak boleh membaca teks grafik secara bebas via penglihatan gambar (OCR/Vision). Sebaliknya, *Semantic Engine* mengekstrak ringkasan statistik deterministik (misal: Mean, Max, Z-score Outlier) dalam bentuk JSON terstruktur, lalu menyuplai data tersebut sebagai *system prompt context* (Grounding RAG) kepada LLM untuk menghasilkan narasi penjelas yang akurat secara matematis.

3. **Skenario 3:** Tim arsitektur data Anda ditugaskan membangun dashboard multi-tenant B2B SaaS di mana ribuan klien eksternal mengakses data mereka sendiri secara bersamaan. Biaya komputasi DWH melonjak tidak terkendali.  
   *Jelaskan strategi optimasi arsitektur lapisannya:*  
   - *Solusi:* Terapkan *Headless Pre-aggregation Layer* menggunakan mesin in-memory kolom (seperti ClickHouse atau DuckDB cluster) yang dipartisi berdasarkan `tenant_id`. Kueri visual klien harus dicegat di Semantic Caching Layer (Redis/Pre-aggregations) dan tidak diizinkan menyentuh Data Warehouse utama secara langsung kecuali jika terjadi *cache miss* eksplisit untuk metrik historis yang tidak diagregasi.

---

### 16. Summary

Visual Analytics tingkat enterprise merupakan perpaduan multidisiplin antara **rekayasa data berkinerja tinggi**, **arsitektur semantik terpusat**, dan **rekayasa interaksi manusia-data (Human-Data Interaction)**. Membangun visualisasi skala produksi bukan sekadar membuat grafik yang estetis, melainkan merancang sistem pemrosesan data end-to-end yang menjamin konsistensi metrik (*single source of truth*), kueri latensi sub-detik melalui *smart caching* dan *pre-aggregations*, serta antarmuka yang meminimalkan beban kognitif pengguna melalui manipulasi data adaptif (LOD Decimation, Canvas/WebGL rendering). 

Dengan mengisolasi logika metrik dari antarmuka visual melalui *Headless BI* dan mengoptimalkan siklus interaksi data, sistem analitik mampu menyajikan wawasan bernilai tinggi secara reliabel, terukur, dan efisien secara komputasi.