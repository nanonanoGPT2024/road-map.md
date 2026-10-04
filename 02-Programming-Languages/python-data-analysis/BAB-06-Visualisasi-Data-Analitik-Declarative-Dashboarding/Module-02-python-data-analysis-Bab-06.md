# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis & Mengoptimalkan Rendering Pipeline**: Mengidentifikasi hambatan (*bottleneck*) serialisasi data dari Python runtime ke browser Document Object Model (DOM) dan Canvas/WebGL.
- **Mengarsiteksi State Management Reaktif**: Membangun aplikasi dashboard analitik terdistribusi dengan pemisahan *stateless compute layer* dan *externalized session store* (Redis).
- **Mengimplementasikan Akselerasi Data Skala Besar**: Menangani visualisasi time-series bervolume tinggi ($>10^7$ baris data) menggunakan teknik dynamic downsampling (*Plotly-Resampler*, *Datashader*) dan zero-copy Arrow IPC.
- **Merancang Infrastruktur Skalabel & Aman**: Men-deploy arsitektur dashboard analitik berbasis kontainer di balik reverse proxy (NGINX/Traefik) dengan dukungan WebSocket/SSE terkonfigurasi untuk sesi multi-tenant yang aman.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, pastikan Anda telah menguasai:
- **Python Lanjutan**: Concurrency model (`asyncio`, threading, multiprocessing), type hinting PEP 484/585, memory profiling (`tracemalloc`, `objgraph`).
- **Data Engineering Dasar**: Manipulasi vektor dengan NumPy dan Pandas/Polars, serialisasi data (Apache Arrow, JSON, Protocol Buffers).
- **Jaringan & Protokol Web**: HTTP/1.1 vs HTTP/2, WebSockets RFC 6455, Server-Sent Events (SSE), CORS, Lifecycle TCP Connection.
- **Tools**: Docker, Redis, Python $\ge$ 3.10, Poetry atau UV package manager.

---

## 3. Concept & Internal Architecture

Dashboard analitik deklaratif modern (seperti Dash/Plotly, Panel, Streamlit) beroperasi di atas abstraksi dua lapisan: **Python Analytical Engine** (Server Runtime) dan **Reactive JavaScript Rendering Client** (Browser Runtime).

```
+---------------------------------------------------------------------------------------+
|                                    BROWSER RUNTIME                                    |
|                                                                                       |
|  +--------------------+         Patch Event          +-----------------------------+  |
|  |   DOM / WebGL      |<-----------------------------|  Reactive Client Runtime    |  |
|  | (Plotly.js / Vega) |                              |  (VDOM Reconciliation)     |  |
|  +--------------------+                              +-----------------------------+  |
|            |                                                        ^                 |
|            | User Interaction (Zoom/Pan/Filter)                     | JSON / Arrow    |
|            v                                                        v Binary          |
+------------|--------------------------------------------------------|-----------------+
             | HTTP POST / WebSocket                                  |
=============|========================================================|==================
             v                                                        |
+---------------------------------------------------------------------|-----------------+
|                                 SERVER RUNTIME (PYTHON)             |                 |
|                                                                     |                 |
|  +--------------------+       Dispatch Work         +------------------------------+  |
|  | ASGI/WSGI Gateway  |---------------------------->|   Reactive Dependency Graph  |  |
|  | (Uvicorn / Gunicorn|                             |   (DAG Callback Resolver)    |  |
|  +--------------------+                             +------------------------------+  |
|                                                                     |                 |
|                                                                     v                 |
|                                                     +------------------------------+  |
|                                                     | Data Engine (Polars / DuckDB)|  |
|                                                     | + Resampling Algorithm       |  |
|                                                     +------------------------------+  |
|                                                                     |                 |
|                                                                     v                 |
|                                                     +------------------------------+  |
|                                                     | Redis State & Caching Store  |  |
|                                                     +------------------------------+  |
+---------------------------------------------------------------------------------------+
```

### 3.1 Siklus Hidup Reaktivitas (DAG Engine)
Arsitektur deklaratif memetakan fungsi Python sebagai simpul-simpul dalam sebuah *Directed Acyclic Graph* (DAG). Setiap komponen UI (Input) yang berubah memicu propagasi event:
1. **Event Capture**: Interaksi pengguna memicu event di browser (`relayout`, `clickData`, `change`).
2. **Payload Serialization**: Browser membentuk payload JSON berisi target identifier dan state properti terbaru.
3. **Transport Layer**: Payload dikirim via HTTP POST (model request-response Dash) atau WebSocket Frame (model bidirectional Streamlit/Panel).
4. **Resolution via Topology Sort**: Server menelusuri DAG untuk mengeksekusi fungsi callback yang terdampak.
5. **JSON/Binary Diffing**: Komputasi menghasilkan representasi visual baru. Server menghitung perubahan konfigurasi (*diff*) dan mengirimkannya kembali ke klien untuk di-patch ke VDOM atau kanvas WebGL.

### 3.2 Bottleneck Serialisasi: The JSON Tax
Secara tradisional, transfer data matriks numerik dari Python runtime (`float64`, `int64`) ke browser client mewajibkan konversi ke format string JSON melalui standard encoder. Operasi ini menyebabkan beban signifikan:
- **CPU Overhead**: Serialisasi representasi biner memori IEEE 754 ke representasi teks ASCII.
- **Bandwidth Bloat**: Angka float biner 8-byte dapat membengkak menjadi 16–24 byte teks JSON (termasuk koma dan tanda kutip).
- **Garbage Collection Pressure**: Browser engine (V8) harus mengalokasikan ribuan objek JavaScript baru saat menjalankan `JSON.parse()`.

Pendekatan enterprise mengatasi hal ini dengan mentransfer **Apache Arrow IPC Binary Streams** atau melakukan **Server-Side LTTB (Largest-Triangle-Three-Buckets) Downsampling** sebelum payload diserialisasi.

---

## 4. Why & What

| Fitur | Imperatif Tradisional (Matplotlib, Seaborn) | Deklaratif Enterprise (Dash, Panel, Modern Streamlit) |
| :--- | :--- | :--- |
| **Model Eksekusi** | Batch script; menghasilkan file bitmap statis (PNG/SVG). | Dynamic Event-Loop; terhubung langsung ke interaksi browser. |
| **State Management** | State lokal sementara (in-memory process variables). | Externalized/Stateless Session Backend (Redis, Encrypted Cookies). |
| **Kapasitas Skala** | Tidak interaktif, statis per sesi komputasi. | Mampu menangani multi-tenant secara asynchronous concurrency. |
| **Rendering Target** | Raster canvas / Vector file lokal. | Dynamic Client DOM, SVG, Canvas, atau WebGL Context. |
| **Separation of Concerns**| Komputasi, data formatting, dan styling tercampur dalam satu alur. | Deklarasi visual terpisah dari analytical query engine. |

**Mengapa memilih arsitektur deklaratif di level enterprise?**
1. **Separation of Concerns**: Tim Data Analyst hanya mendefinisikan layout dan dependensi logis (deklaratif), sementara platform engineer dapat mengontrol caching, routing, security, dan scaling di layer abstraksi infrastruktur.
2. **Reactivity**: Meminimalisir race condition pada state aplikasi karena state transition dikelola secara formal lewat graf dependensi.

---

## 5. How (Workflow Detail)

Untuk mengimplementasikan arsitektur visualisasi data skala enterprise, workflow dibagi menjadi 4 pipeline utama:

```
[ Ingest & Storage ] -> [ Aggregation & Filtering ] -> [ Dynamic Downsampling ] -> [ Zero-Copy / Fast Wire Transfer ]
      (DuckDB)                 (Polars DAG)                   (LTTB Engine)                      (Arrow / WebGL)
```

1. **Analytical Query Pushdown**: Beban komputasi pemfilteran dan pengelompokan didelegasikan ke engine analitik in-process berperforma tinggi (misal: DuckDB atau Polars) alih-alih mengeksekusi filtering iteratif di native Python objects.
2. **View-Port Dynamic Resampling**: Jika dataset memiliki 10.000.000 titik, tetapi lebar layar browser hanya memiliki resolusi 1.920 piksel horizontal, server mengaplikasikan algoritma LTTB untuk mereduksi data menjadi 3.840 titik secara adaptif sesuai rentang koordinat `xaxis.range`.
3. **Transport Optimization**: Payload dikompresi menggunakan transport biner atau dictionary-encoded JSON payloads dengan gzip/brotli di level reverse-proxy.
4. **Hardware-Accelerated Client Paint**: Rendering di sisi browser didelegasikan langsung ke WebGL pipeline (`scattergl` pada Plotly) untuk menghindari limitasi single-threaded DOM engine.

---

## 6. Analogy & Diagram ASCII

Bayangkan sebuah **Restoran Masakan Cepat Saji (Fast Food Drive-Thru)**:

- **Imperatif (Matplotlib)**: Setiap kali pelanggan meminta burger, koki harus menanam gandum, menyembelih sapi, memasak, mencetak foto burger di atas kertas, lalu memberikan foto tersebut ke pelanggan. Jika pelanggan ingin menambah keju, seluruh siklus diulang dari awal.
- **Deklaratif Skala Rendah**: Koki memasak burger, namun memisahkannya menjadi ribuan partikel atom mikroskopis, memasukkannya ke dalam jutaan kotak kecil (JSON Bloat), lalu mengirimkannya ke meja pelanggan untuk dirakit ulang satu per satu.
- **Deklaratif Skala Enterprise (Zero-Copy & Resampling)**: Koki melihat ukuran perut dan meja pelanggan (lebar viewport browser). Koki mengambil bahan baku dari pendingin modular (DuckDB/Parquet), memotongnya sesuai kapasitas konsumsi meja (LTTB Downsampling), lalu membawanya menggunakan baki standard pabrik bersertifikasi langsung ke pemanggang meja tanpa memotong-motongnya secara berlebihan (Arrow/WebGL stream).

```
+----------------------------------------------------------------------------------------------------+
| TRADITIONAL DATA PATH                                                                              |
| Dataframe (Memori) --> Iterrows() --> Python Dict --> json.dumps() --> Text Network Packet        |
| [100 MB Array]         [Slow Loop]    [High RAM]      [CPU Heavy]      [~300 MB JSON String]       |
+----------------------------------------------------------------------------------------------------+
                                                VS
+----------------------------------------------------------------------------------------------------+
| ENTERPRISE OPTIMIZED PATH                                                                          |
| Parquet/DuckDB ------> Polars Viewport Query -> LTTB Downsampler -> Arrow RecordBatch -> WebGL     |
| [Zero-Copy Read]       [SIMD Parallelism]       [Reduce to 2000 pts][Binary Stream]    [GPU Paint] |
+----------------------------------------------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### Simple Example: Client-side Aggregation Bottleneck (Anti-Pattern vs Pattern Dasar)

```python
# app_simple.py
# Contoh dasar reaktivitas Dash dengan pemanfaatan WebGL
import dash
from dash import dcc, html, Input, Output
import numpy as np
import plotly.graph_objects as go

app = dash.Dash(__name__)

# Simulasi 100,000 titik (Cukup berat untuk standard SVG Canvas)
np.random.seed(42)
t = np.linspace(0, 100, 100_000)
y = np.sin(t) + np.random.normal(0, 0.2, len(t))

app.layout = html.Div([
    html.H3("High-Frequency Sensor Monitoring (WebGL Accelerated)"),
    dcc.Slider(id="noise-filter", min=1, max=100, value=10, step=1),
    dcc.Graph(id="sensor-plot")
])

@app.callback(
    Output("sensor-plot", "figure"),
    Input("noise-filter", "value")
)
def update_graph(window_size: int) -> go.Figure:
    # Komputasi moving average sederhana
    kernel = np.ones(window_size) / window_size
    smoothed = np.convolve(y, kernel, mode="same")
    
    # KUNCI: Gunakan Scattergl (WebGL), BUKAN Scatter biasa (SVG/DOM)
    fig = go.Figure()
    fig.add_trace(go.Scattergl(
        x=t[::2],  # Downsample dasar
        y=smoothed[::2],
        mode="lines",
        line=dict(color="#00FFAA", width=1),
        name="Filtered Signal"
    ))
    fig.update_layout(
        template="plotly_dark",
        margin=dict(l=20, r=20, t=20, b=20),
        uirevision="constant_zoom" # Mempertahankan zoom level stateful
    )
    return fig

if __name__ == "__main__":
    app.run_server(debug=False, port=8050)
```

---

### Practical Example: Production Enterprise Real-time Streaming Engine

Contoh berikut menunjukkan arsitektur industri: Backend asynchronous FastAPI terpisah yang memancarkan data time-series performa tinggi via WebSocket, dikombinasikan dengan frontend Plotly yang menggunakan client-side LTTB downsampling simulation dan stateless session handling.

```python
# server.py
"""
Backend Pipeline: FastAPI, Redis-ready architecture, SIMD downsampling simulation.
Menyediakan interface analitik real-time bervolume tinggi.
"""
from __future__ import annotations

import asyncio
import json
import math
from typing import Generator, List, Tuple
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import numpy as np

app = FastAPI(title="Enterprise Telemetry Streamer")

class HighFrequencyDataSimulator:
    """Simulasi sensor industrial: 5,000 events/detik dipaketkan per interval."""
    
    @staticmethod
    def generate_window(size: int = 5000, base_offset: float = 0.0) -> Tuple[List[float], List[float]]:
        x = np.linspace(base_offset, base_offset + 5.0, size, dtype=np.float64)
        noise = np.random.normal(0, 0.5, size)
        harmonics = np.sin(x * 2.0) + 0.5 * np.cos(x * 10.0)
        y = harmonics + noise
        return x.tolist(), y.tolist()

def lttb_downsample(x: List[float], y: List[float], threshold: int) -> Tuple[List[float], List[float]]:
    """
    Largest Triangle Three Buckets (LTTB) downsampling algorithm 
    dioptimalkan untuk memangkas resolusi payload ke jaringan tanpa kehilangan visual peak.
    """
    data_length = len(x)
    if threshold >= data_length or threshold == 0:
        return x, y

    sampled_x: List[float] = [x[0]]
    sampled_y: List[float] = [y[0]]

    every = (data_length - 2) / (threshold - 2)
    a = 0

    for i in range(0, threshold - 2):
        avg_x = 0.0
        avg_y = 0.0
        avg_range_start = int(math.floor((i + 1) * every) + 1)
        avg_range_end = int(math.floor((i + 2) * every) + 1)
        avg_range_end = min(avg_range_end, data_length)

        avg_range_length = avg_range_end - avg_range_start
        for j in range(avg_range_start, avg_range_end):
            avg_x += x[j]
            avg_y += y[j]

        if avg_range_length > 0:
            avg_x /= avg_range_length
            avg_y /= avg_range_length

        range_offs = int(math.floor((i + 0) * every) + 1)
        range_to = int(math.floor((i + 1) * every) + 1)

        point_ax = x[a]
        point_ay = y[a]

        max_area = -1.0
        next_a = range_offs

        for j in range(range_offs, range_to):
            area = abs(
                (point_ax - avg_x) * (y[j] - point_ay)
                - (point_ax - x[j]) * (avg_y - point_ay)
            ) * 0.5
            if area > max_area:
                max_area = area
                next_a = j

        sampled_x.append(x[next_a])
        sampled_y.append(y[next_a])
        a = next_a

    sampled_x.append(x[-1])
    sampled_y.append(y[-1])

    return sampled_x, sampled_y

@app.websocket("/ws/telemetry")
async def websocket_telemetry_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    offset = 0.0
    try:
        while True:
            # Generate 5,000 raw points per tick
            raw_x, raw_y = HighFrequencyDataSimulator.generate_window(size=5000, base_offset=offset)
            
            # Downsample to 250 points optimal for DOM/WebGL packet size
            down_x, down_y = lttb_downsample(raw_x, raw_y, threshold=250)
            
            payload = {
                "x": down_x,
                "y": down_y,
                "meta": {
                    "raw_points": len(raw_x),
                    "transmitted_points": len(down_x),
                    "compression_ratio": round(len(raw_x) / len(down_x), 2)
                }
            }
            await websocket.send_text(json.dumps(payload))
            offset += 5.0
            await asyncio.sleep(0.05)  # 20 FPS Update Rate
    except WebSocketDisconnect:
        pass

@app.get("/")
def get_dashboard() -> HTMLResponse:
    """Menyajikan Client HTML + Plotly.js Native Engine."""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Production Telemetry Engine</title>
        <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
        <style>
            body { background: #0F172A; color: #E2E8F0; font-family: monospace; padding: 20px; }
            #metrics { display: flex; gap: 20px; margin-bottom: 10px; }
            .metric-card { background: #1E293B; padding: 10px 20px; border-radius: 4px; border: 1px solid #334155; }
            #chart { width: 100%; height: 600px; }
        </style>
    </head>
    <body>
        <h2>High-Throughput Declarative Visualization</h2>
        <div id="metrics">
            <div class="metric-card">Points/Sec: <span id="pts-sec">0</span></div>
            <div class="metric-card">Compression: <span id="comp-ratio">0</span>x</div>
        </div>
        <div id="chart"></div>

        <script>
            const chartDiv = document.getElementById('chart');
            Plotly.newPlot(chartDiv, [{
                x: [],
                y: [],
                type: 'scattergl',
                mode: 'lines+markers',
                line: { color: '#38BDF8', width: 1.5 },
                marker: { size: 3 }
            }], {
                plot_bgcolor: '#0F172A',
                paper_bgcolor: '#0F172A',
                font: { color: '#94A3B8' },
                xaxis: { title: 'Timestamp Offset' },
                yaxis: { title: 'Signal Amplitude', range: [-4, 4] },
                margin: { t: 20, r: 20, l: 40, b: 40 }
            });

            const ws = new WebSocket(`ws://${location.host}/ws/telemetry`);
            let accumulatedPoints = 0;
            let lastReport = performance.now();

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                
                // Reaktivitas parsial via Plotly.extendTraces
                Plotly.extendTraces(chartDiv, {
                    x: [data.x],
                    y: [data.y]
                }, [0], 1500); // Pertahankan window sliding buffer 1,500 points

                accumulatedPoints += data.meta.raw_points;
                const now = performance.now();
                if (now - lastReport >= 1000) {
                    document.getElementById('pts-sec').innerText = accumulatedPoints;
                    document.getElementById('comp-ratio').innerText = data.meta.compression_ratio;
                    accumulatedPoints = 0;
                    lastReport = now;
                }
            };
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Real-Time Risk Desk Telemetry System (Top-Tier Hedge Fund)

**Konteks Masalah**:
Sebuah hedge fund global memonitor portofolio derivatif frekuensi tinggi dengan $1.200$ parameter eksposur risiko secara *real-time*. Tim Quant Analyst awalnya membangun dashboard berbasis framework prototype Streamlit sederhana. 

**Bottleneck Arsitektural Awal**:
1. Setiap kali tick harga baru masuk (100 Hz), runtime Streamlit me-rerun *seluruh modul script* dari atas ke bawah.
2. In-memory data frame (Pandas) di-copy berulang kali (memory explosion hingga $>32\text{ GB}$ per instance worker).
3. Session state disimpan lokal di dalam process memory; restart container Kubernetes menyebabkan terputusnya analitik pada workstation puluhan trader.
4. Serialisasi JSON murni memakan $85\%$ CPU server time.

**Desain Arsitektur Produksi Skala Enterprise**:

```
[ Market Ticks (Kafka) ]
          |
          v
[ Analytical Compute Service (C++ / Rust Engine) ]
          | Zero-Copy Arrow RecordBatches
          v
[ Distributed In-Memory Cache (Redis 7.x Cluster) ]
          |
     +----+----+ (Pub/Sub Notifications)
     |         |
     v         v
[ Dash Enterprise Worker A ]  [ Dash Enterprise Worker B ]
(Stateless ASGI/Uvicorn)       (Stateless ASGI/Uvicorn)
     |         |
     +----+----+ (Sticky Sessions / WebSocket Mesh)
          |
          v
[ Traefik Edge Router / API Gateway ]
          | TLS 1.3 / HTTP/2 Push
          v
[ Trader WebGL Workstations (Plotly.js + Resampler) ]
```

**Hasil Optimasi Arsitektural**:
- **Pemisahan Compute & State**: Worker Dash dijadikan murni *stateless*. Status layout, filter pengguna, dan viewport window disimpan di Redis cluster dengan token session JWT terenkripsi.
- **Micro-batching & Arrow Deserialization**: Frontend beralih dari HTTP polling individual ke subscription WebSocket multiplexing.
- **Pengurangan Latensi**: End-to-end latency turun dari $1.850\text{ ms}$ menjadi $38\text{ ms}$.
- **Efisiensi Server**: Penggunaan CPU per worker turun sebesar $74\%$, kapasitas koneksi bersamaan (*concurrent trader sessions*) naik $12\times$ lipat pada cluster computing yang sama.

---

## 9. Trade-offs

Setiap keputusan arsitektur visualisasi membawa konsekuensi operasional yang nyata:

| Skenario | Pilihan Arsitektur | Keuntungan | Kerugian & Batasan |
| :--- | :--- | :--- | :--- |
| **Rendering Strategy** | Server-Side Rendering (SSR - Matplotlib/Datashader Image Push) | Aman untuk dataset masif ($>10^8$ rows); client-side hanya merender lightweight PNG tag. | Interaktivitas miskin (zoom/pan terasa lagging akibat round-trip network IO tinggi). |
| | Client-Side Rendering (CSR - Plotly WebGL / Canvas) | Interaksi instan, zooming halus hingga 60 FPS, membebaskan komputasi grafis server. | Rentan crash pada browser klien jika dataset tidak di-downsample secara ketat ($>500\text{k}$ points di mobile/low-end device). |
| **Framework Ecosystem** | Streamlit | Rapid prototyping; minim boilerplate; linear logic model mudah bagi Data Scientist. | Siklus eksekusi penuh (script rerunning) membutuhkan mitigasi cache kompleks pada skala enterprise. |
| | Dash (Plotly) | Reaktivitas fine-grained berbasis Callback DAG; fully customizeable HTML/React layout. | Kurva belajar lebih curam; arsitektur callback kompleks dapat menyebabkan cyclic dependency jika tidak dirancang rapi. |
| **Data Serialization** | Pure JSON Serialization | Kompatibilitas universal (native browser support); debugging payload via DevTools mudah. | CPU tax tinggi, bloat ukuran transfer hingga $300\%$, alokasi memory heap ekstrem di engine JS. |
| | Apache Arrow IPC Stream | Zero-copy access, representasi biner kompak, memory-aligned buffers langsung ke GPU/Canvas memory. | Butuh deserializer client-side (seperti `arrow-js`); kompleksitas konfigurasi pipeline lebih tinggi. |

---

## 10. Common Mistakes & Troubleshooting

### 1. In-Memory Session Bleeding (State Leak Multi-Tenant)
* **Penyebab**: Menyimpan state pengguna di tingkat global scope file Python:
  ```python
  # SALAH: Global state dishare oleh SEMUA user yang terhubung ke server instance
  user_selected_filters = {} 

  @app.callback(...)
  def update(val):
      user_selected_filters['val'] = val # RACE CONDITION & DATA LEAKAGE!
  ```
* **Solusi**: Gunakan `dcc.Store(storage_type='session')` atau inject ID sesi pengguna yang divalidasi ke backend session manager terisolasi (Redis session hash).

### 2. Event-Loop Starvation (Blocking Callback Execution)
* **Penyebab**: Menjalankan query I/O berat atau data training machine learning synchronous langsung di dalam callback worker thread Dash/FastAPI.
* **Gejala**: Dashboard tampak *freeze* untuk pengguna lain ketika satu pengguna memicu query berat.
* **Solusi**: Delegasikan tugas komputasi berat ke worker asynchronous (Celery, RQ, atau native `asyncio.to_thread`) dan polling status menggunakan background callback identifier.

### 3. Cyclic Dependency Deadlock pada Callback DAG
* **Penyebab**: Callback A menghasilkan output yang memicu Callback B, dan Callback B secara langsung atau transitif memperbarui input Callback A.
* **Troubleshooting**: Dash akan memunculkan exception `CantHaveMultipleOutputs` atau siklus looping rendering tak terbatas. Visualisasikan DAG menggunakan dependency graph validator internal:
  ```bash
  # Cek callback graph Dash
  dash-dev-tools validate-dag app:app
  ```

---

## 11. Best Practices (Production Checklist)

Gunakan daftar periksa teknis ini sebelum melakukan rilis visualisasi analitik ke cluster production:

```markdown
- [ ] 1. DATA TRANSPORT & DOWN-SAMPLING
      - [ ] Implementasikan dynamic downsampling (LTTB/MinMax) untuk time-series > 10,000 titik.
      - [ ] Aktifkan kompresi GZIP/Brotli pada layer reverse proxy untuk endpoint JSON/Arrow.
      - [ ] Hindari konversi Float64/Float32 ke String berpresisi tak terhingga di output JSON.

- [ ] 2. RENDERING HARDWARE OPTIMIZATION
      - [ ] Gunakan `go.Scattergl` bukan `go.Scatter` jika total marker melebihi 2,000 elemen.
      - [ ] Matikan animasi layout (`animate=False`) untuk real-time update > 5 Hz.
      - [ ] Terapkan static `uirevision` property agar view zoom tidak reset saat auto-refresh data.

- [ ] 3. ARCHITECTURE & MULTI-TENANCY
      - [ ] Python Worker runtime harus sepenuhnya STATELESS.
      - [ ] Session persistence dipetakan ke Redis / Memcached cluster.
      - [ ] Pasang Sticky Sessions pada load balancer jika menggunakan protokol WebSocket stateful.

- [ ] 4. ERROR HANDLING & TELEMETRY
      - [ ] Pasang global callback exception handler; jangan expose raw stack trace ke DOM klien.
      - [ ] Catat latensi eksekusi tiap simpul DAG menggunakan middleware Prometheus metrics.
```

---

## 12. Hands-on Practice

Implementasikan dashboard pemantau performa klaster enterprise menggunakan pola arsitektur caching layer dan dynamic downsampling. Simpan seluruh artefak ke dalam direktori `hands-on/m02/`.

### Struktur Direktori
```
hands-on/m02/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── engine.py
│   └── app.py
```

### File 1: `hands-on/m02/requirements.txt`
```text
dash==2.14.2
pandas==2.2.0
polars==0.20.7
numpy==1.26.3
redis==5.0.1
gunicorn==21.2.0
```

### File 2: `hands-on/m02/src/engine.py`
```python
"""
Data Engine: Mensimulasikan pemrosesan analitik high-volume
dengan downsampling dan Redis caching.
"""
from __future__ import annotations

import json
import numpy as np
import polars as pl
import redis

# Inisialisasi koneksi Redis
r = redis.Redis(host="redis", port=6379, db=0, decode_responses=True)

class MetricEngine:
    @staticmethod
    def get_or_generate_telemetry(metric_id: str, points: int = 500_000) -> pl.DataFrame:
        cache_key = f"telemetry:{metric_id}"
        
        # 1. Coba baca dari Cache Redis
        cached_data = r.get(cache_key)
        if cached_data:
            data_dict = json.loads(cached_data)
            return pl.DataFrame(data_dict)

        # 2. Compute Pipeline: Generate dan proses via Polars (SIMD parallel)
        t = np.linspace(0, 1000, points)
        signal = np.sin(t) + np.random.normal(0, 0.2, points) + (t * 0.005)
        
        df = pl.DataFrame({
            "timestamp": t,
            "value": signal
        })

        # 3. Dynamic Decimation untuk penyimpanan intermediate (Ambil tiap kelipatan)
        # Menjaga efisiensi payload serialization
        decimated_df = df.gather_every(every=100) # 500,000 -> 5,000 points

        # Simpan ke Redis (TTL 60 detik)
        r.setex(cache_key, 60, json.dumps(decimated_df.to_dict(as_series=False)))
        
        return decimated_df
```

### File 3: `hands-on/m02/src/app.py`
```python
"""
Web UI Application: Dash Enterprise stateless instance.
"""
import dash
from dash import dcc, html, Input, Output
import plotly.graph_objects as go
from engine import MetricEngine

app = dash.Dash(__name__)
server = app.server  # Expose WSGI untuk Gunicorn

app.layout = html.Div(
    style={"backgroundColor": "#111827", "minHeight": "100vh", "padding": "24px", "color": "#F3F4F6"},
    children=[
        html.H1("Production Cluster Analytical Telemetry", style={"fontSize": "24px"}),
        html.Div([
            html.Label("Pilih Node Metric Target:"),
            dcc.Dropdown(
                id="node-selector",
                options=[
                    {"label": "Compute-Node-Alpha (500k Points)", "value": "node-alpha"},
                    {"label": "Compute-Node-Beta (500k Points)", "value": "node-beta"},
                ],
                value="node-alpha",
                style={"color": "#111827"}
            ),
        ], style={"width": "300px", "marginBottom": "20px"}),
        
        dcc.Loading(
            type="default",
            children=dcc.Graph(id="metric-canvas", style={"height": "70vh"})
        )
    ]
)

@app.callback(
    Output("metric-canvas", "figure"),
    Input("node-selector", "value")
)
def render_metric_plot(selected_node: str) -> go.Figure:
    df = MetricEngine.get_or_generate_telemetry(selected_node)

    # Implementasi WebGL Rendering
    fig = go.Figure()
    fig.add_trace(go.Scattergl(
        x=df["timestamp"].to_numpy(),
        y=df["value"].to_numpy(),
        mode="lines",
        line=dict(color="#10B981", width=1.5),
        name="Telemetry Stream"
    ))

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#1F2937",
        plot_bgcolor="#111827",
        xaxis=dict(title="Operational Epoch (seconds)", gridcolor="#374151"),
        yaxis=dict(title="Vibration / Workload Level", gridcolor="#374151"),
        uirevision=selected_node,  # Zoom tetap bertahan kecuali metric diubah
        margin=dict(l=40, r=40, t=20, b=40)
    )
    return fig

if __name__ == "__main__":
    app.run_server(host="0.0.0.0", port=8050, debug=False)
```

### File 4: `hands-on/m02/docker-compose.yml`
```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    container_name: telemetry_redis
    ports:
      - "6379:6379"

  dashboard:
    build: .
    container_name: telemetry_app
    command: gunicorn --workers 4 --bind 0.0.0.0:8050 src.app:server
    ports:
      - "8050:8050"
    environment:
      - PYTHONUNBUFFERED=1
    depends_on:
      - redis
```

### File 5: `hands-on/m02/Dockerfile`
```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

EXPOSE 8050
```

### Panduan Eksekusi
Jalankan sistem dashboard multi-worker ini:
```bash
cd hands-on/m02
docker-compose up --build
```
Akses `http://localhost:8050` pada browser Anda. Amati bagaimana data 500,000 titik di-downsample dan dimuat dalam hitungan milidetik secara asinkron tanpa memblokir worker pool Gunicorn.

---

## 13. Exercise

### Level Easy
1. Modifikasi file `src/app.py` untuk menambahkan panel indikator total titik data (`len(df)`) yang berhasil dirender ke layar klien.
   * *Kriteria Evaluasi*: Gunakan komponen HTML Dash murni tanpa merender ulang trace canvas utama.

### Level Medium
1. Ubah downsampling pipeline pada `MetricEngine` dari fixed decimation (`gather_every`) menjadi adaptif rolling aggregation (Mean & Std Deviation Envelope) menggunakan fungsi windowing Polars.
   * *Kriteria Evaluasi*: Visualisasikan boundary shading (Confidence Interval $2\sigma$) di sekitar garis metric utama menggunakan layout SVG/WebGL fill.

### Level Hard
1. Implementasikan fitur dynamic zoom downsampler: Ketika user melakukan zoom (`relayoutData` event tertangkap di callback), ambil range `xaxis.range[0]` dan `xaxis.range[1]`, lalu hitung downsample resolusi tinggi hanya pada area bounded box yang dipilih langsung dari DataFrame raw in-memory.
   * *Kriteria Evaluasi*: Latensi end-to-end respons zoom harus berada di bawah 150 ms untuk input array mentah sebesar $2.000.000$ baris data.

---

## 14. Challenge

### High-Volume FinTech Order Book Heatmap Profiler

**Deskripsi Tantangan**:
Rancanglah sebuah dashboard analitik Level 2 Limit Order Book (LOB) yang menerima aliran snapshot kedalaman pasar (Market Depth) dengan frekuensi 50 snapshot per detik. Masing-masing snapshot terdiri dari 200 level penawaran (Bids) dan 200 level permintaan (Asks).

**Spesifikasi Persyaratan Teknis**:
1. **Engine Komputasi**: Gunakan DuckDB atau Polars untuk mengakumulasi volume transaksi ke dalam micro-bucket berbasis waktu (Time-Bucketed 2D Grid Matrix).
2. **Kapasitas Rendering**: Visualisasikan 10 menit riwayat data transaksi (30.000 snapshot kumulatif) dalam bentuk dynamic Heatmap visual canvas tanpa membuat browser mengalami memory exhaustion crash ($<300\text{ MB}$ footprint heap memory pada browser tab).
3. **Stateless Session Concurrency**: Sistem harus dapat dijalankan dengan 3 instance Gunicorn worker yang berbeda di balik load balancer, di mana setiap user dapat menyaring order size tanpa mengganggu stream visualisasi user lainnya.
4. **Deliverable**: Arsitektur script modular (`engine.py`, `dashboard.py`) beserta konfigurasi Redis Pub/Sub backplane.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Basic (5 Pertanyaan)
1. Apa perbedaan arsitektural utama antara trace `scatter` dan `scattergl` pada Plotly?
2. Mengapa format serialisasi JSON menjadi bottleneck saat mentransfer dataset numerik besar dari Python ke browser?
3. Apa kegunaan parameter `uirevision` pada layout chart Plotly dalam siklus interaksi callback?
4. Mengapa variabel global level file dilarang keras digunakan untuk menyimpan user filter state pada dashboard berbasis Dash atau Streamlit produksi?
5. Protokol jaringan apa yang paling optimal untuk visualisasi data analitik frekuensi tinggi ($>30\text{ Hz}$ update rate)?

### Bagian B: Intermediate (5 Pertanyaan)
1. Jelaskan bagaimana algoritma Largest Triangle Three Buckets (LTTB) menjaga integritas bentuk visual data time-series dibandingkan metode uniform decimation (nth point skipping)!
2. Bagaimana cara kerja Client-Side Callback di Dash, dan apa keuntungannya bagi performa server?
3. Sebutkan kelemahan arsitektur eksekusi Streamlit pada pemrosesan dataframe masif ($>1\text{ GB}$) jika dibandingkan dengan Directed Acyclic Graph (DAG) Callback milik Dash.
4. Apa peran zero-copy Arrow IPC deserialization dalam mempercepat pipeline visualisasi web modern?
5. Mengapa teknik reverse proxy buffering (misalnya pada NGINX) harus dimatikan (`proxy_buffering off`) saat menyajikan visualisasi data berbasis Server-Sent Events (SSE) atau WebSockets?

### Bagian C: Skenario Kasus Produksi (3 Pertanyaan Kasus)

1. **Skenario 1**: Dashboard produksi Anda mengalami kebocoran memori (Memory Leak) bertahap, di mana penggunaan RAM container Python meningkat 500 MB setiap jam meskipun jumlah pengguna aktif konstan pada angka 10 orang. Setelah dianalisis, pengguna sering membuka tab visualisasi baru.
   * *Pertanyaan*: Komponen arsitektural mana yang paling mungkin menjadi sumber masalah dan bagaimana langkah isolasi teknisnya?
2. **Skenario 2**: Sebuah klaster analitik memvisualisasikan data geospasial armada logistik (50.000 armada truk diperbarui tiap 2 detik). Saat peta diperbesar (zoomed-in), latensi callback meningkat drastis hingga 5 detik per interaksi.
   * *Pertanyaan*: Transformasi komputasi apa yang harus diterapkan pada database/query engine layer sebelum data dikirim ke renderer browser?
3. **Skenario 3**: Perusahaan Anda mewajibkan implementasi arsitektur multi-region Kubernetes untuk dashboard risiko finansial. Trader di Singapura dan London harus melihat data dan state visualisasi yang sama secara sinkron tanpa race-condition.
   * *Pertanyaan*: Bagaimana Anda mengarsiteki state management layer untuk memenuhi kriteria konsistensi ini tanpa mengorbankan rendering frame-rate?

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Bagian A
1. `scatter` me-render elemen visual sebagai simpul SVG individual di dalam DOM (berat di CPU jika titik $>2.000$), sedangkan `scattergl` mengeksekusi komputasi piksel langsung melalui konteks WebGL hardware acceleration pada kartu grafis (GPU), mampu menangani ratusan ribu hingga jutaan titik secara lancar.
2. JSON memproses angka biner 64-bit menjadi string ASCII karakter per karakter, memicu pembengkakan bandwidth jaringan hingga 300% dan membebani parser thread JavaScript browser dengan proses parsing string dan garbage collection yang intensif.
3. `uirevision` bertindak sebagai locking key untuk UI state. Jika nilainya tetap sama antar eksekusi callback, browser akan mempertahankan status interaksi pengguna sebelumnya (seperti zoom level, pan coordinates, dan orientasi rotasi 3D) alih-alih me-reset tampilan grafik ke default.
4. Runtime server Python dibagi pakai oleh semua thread worker. Variabel global bersifat *shared across processes/threads*, sehingga perubahan filter oleh User A akan menimpa filter milik User B (Data Privacy Breach & Race Conditions).
5. Protokol WebSockets (RFC 6455) atau Server-Sent Events (SSE), karena meniadakan overhead negosiasi HTTP handshaking berulang kali via full-duplex persistent connection.

#### Bagian B
1. LTTB membagi data ke dalam bucket-bucket dan memilih satu titik per bucket yang memaksimalkan luas segitiga bersama titik sebelumnya dan titik rata-rata bucket berikutnya. Hal ini mempertahankan titik puncak lokal (*peaks*), lembah (*valleys*), dan varians sinyal tanpa membuang anomali yang penting secara visual, tidak seperti uniform decimation yang berpotensi memotong titik anomali runcing.
2. Client-side callback mengeksekusi fungsi JavaScript langsung di dalam browser pengguna tanpa mengirim round-trip HTTP request ke server Python. Ini menghilangkan latensi jaringan untuk interaksi sederhana seperti toggle visibility atau kalkulasi matematika lokal.
3. Streamlit secara default mengeksekusi ulang seluruh baris kode file dari atas ke bawah saat ada state widget yang berubah. Jika data 1 GB tersebut tidak diisolasi menggunakan pattern caching yang cermat, memory overhead akan berlipat ganda dan waktu eksekusi melambat drastis dibandingkan Dash yang hanya mengeksekusi node terisolasi pada graf dependensi callback.
4. Arrow IPC memetakan format memori berdekatan (contiguous memory layout) yang identik antara runtime server dan client. Deserialisasi dapat dilakukan secara instan (*zero-copy* pointer read) tanpa translasi tipe data per elemen array.
5. Buffering NGINX akan menahan frame data berukuran kecil hingga buffer penuh sebelum mengalirkannya ke klien. Akibatnya, paket analitik streaming tertahan di proxy, merusak karakteristik ketepatan waktu *real-time* (data tersendat lalu keluar secara burst).

#### Bagian C
1. **Solusi Skenario 1**: Sumber kebocoran memori paling umum adalah pendaftaran callback dinamis atau penumpukan referensi objek visual ke dalam global collection/closure memory yang tidak pernah dihapus oleh Garbage Collector. Langkah isolasi: Gunakan module `objgraph` atau `tracemalloc` untuk mengambil memory snapshot saat container baru berjalan vs saat container berjalan 1 jam, lalu telusuri jenis instance objek yang bertambah secara abnormal (biasanya `Figure` objects atau referensi session listener yang tertinggal).
2. **Solusi Skenario 2**: Terapkan teknik *Spatial Partitioning Indexing* (R-Tree / QuadTree) pada query engine (misal DuckDB Spatial / PostGIS) dan kirimkan koordinat bounding box viewport (`relayoutData`) ke query. Data harus di-aggregate secara dinamis di server menggunakan spatial clustering (misal: algoritma DBSCAN atau H3 Hexagonal Binning) sebelum diserialisasi, sehingga browser hanya menerima ringkasan agregasi cluster alih-alih 50.000 titik koordinat mentah.
3. **Solusi Skenario 3**: Pisahkan Dashboard Worker menjadi stateless pod di tiap region, dipadukan dengan cluster data backend terdistribusi global yang mendukung replikasi multi-master berlatensi rendah (misal: CockroachDB atau Google Cloud Spanner untuk transactional state, serta Redis Enterprise dengan CRDTs / Active-Active clustering untuk sync visual state). Event sinkronisasi di-publish melalui stream broker dengan timestamping NTP terkalibrasi tinggi.

---

## 16. Summary

Visualisasi data analitik skala enterprise menuntut pergeseran paradigma dari pembuatan grafik statis imperatif ke **arsitektur visualisasi deklaratif reaktif**. 

Pilar-pilar penting dalam arsitektur dashboard analitik modern meliputi:
1. **Separation of Compute and State**: Runtime Python harus sepenuhnya stateless; session persistence dikelola di external store (Redis).
2. **Pipeline Optimizations**: Mengatasi bottleneck "JSON Tax" melalui teknik dynamic downsampling adaptif (LTTB) dan pergeseran ke zero-copy streaming format (Apache Arrow).
3. **Hardware-Accelerated Rendering**: Pemanfaatan WebGL di sisi klien untuk mendistribusikan beban komputasi rendering dari server CPU ke client GPU.
4. **Resilient Production Topology**: Penggunaan WebSocket/SSE di balik reverse proxy terkonfigurasi dengan session orchestration yang aman untuk skenario enterprise multi-tenant.