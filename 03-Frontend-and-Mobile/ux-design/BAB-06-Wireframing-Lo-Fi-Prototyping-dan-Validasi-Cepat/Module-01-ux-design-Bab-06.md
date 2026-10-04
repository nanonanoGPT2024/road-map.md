# Modul 06: Wireframing, Lo-Fi Prototyping & Validasi Cepat

---

## SEKSI 01 — IDENTITAS MODUL
* **Track:** UX Design
* **Kategori:** 03-Frontend-and-Mobile
* **Modul:** Bab 06 Module 01
* **Topik:** Wireframing, Lo-Fi Prototyping & Validasi Cepat
* **Prasyarat:** Information Architecture (IA), Task Flow Mapping, Mental Models & User Personas, Dasar-dasar DOM & Layouting (HTML/CSS).
* **Tingkat Kesulitan:** Intermediate to Advanced Systems Practitioner.

---

## SEKSI 02 — LEARNING OBJECTIVES
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. Menghilangkan ketergantungan estetika prematur (*aesthetic-usability bias distortion*) melalui penerapan sistematis representasi struktural skala rendah (Lo-Fi).
2. Memetakan *information density*, *visual hierarchy*, dan batasan spasial (*spatial constraints*) ke dalam blueprint digital monokromatik deterministik.
3. Membangun prototipe Lo-Fi interaktif dengan latensi rendah menggunakan HTML fungsional berbasis Semantic Elements dan Tailwind CSS/Plain CSS yang terikat pada event handler validasi.
4. Merancang dan mengeksekusi kerangka validasi cepat (*Guerilla & Unmoderated Testing*) dengan metrik kuantitatif: *Time-on-Task (ToT)*, *Task Success Rate (TSR)*, dan *System Usability Scale (SUS)*.
5. Mengintegrasikan instrumen telemetri dan *event-driven logging* langsung ke dalam artefak pengujian untuk menganalisis friksi UX sebelum fase *High-Fidelity UI engineering*.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Mental Model: The Skeletal Blueprint vs. The Painted Facade
Dalam rekayasa struktural, seorang arsitek tidak memulai pembangunan gedung pencakar langit dengan memilih warna cat lobi atau tekstur marmer; mereka merancang *load-bearing blueprint*. 

```
[Mental Model: The Separation of Structural Physics and Aesthetics]

+-------------------------------------------------------------+
|              HIGH-FIDELITY HAZARD: PREMATURE BIAS           |
|  (User & Stakeholders terdistraksi warna, tipografi, logo)  |
|                               |                             |
|                               v                             |
|    "Saya tidak suka tombol ungu ini" != "Alur checkout gagal"|
+-------------------------------------------------------------+
                               |
                               | Solusi Paradigma
                               v
+-------------------------------------------------------------+
|               LO-FI PROTO: STRUCTURAL REALISM               |
|   - Zero Chromatic Distraction (Grayscale / Monochromatic)  |
|   - Real Dynamic Copy (No Lorem Ipsum on critical path)     |
|   - Semantic Spatial Relationships (Grid, Layout, Bounds)    |
|   - Behavioral Mechanics Validated Before Token Delivery    |
+-------------------------------------------------------------+
```

* **Cost of Change Velocity:** Biaya iterasi arsitektur antarmuka saat fase wireframe bernilai $1x$. Saat masuk fase Figma High-Fidelity dengan ratusan komponen bernilai $10x$. Saat masuk fase kode frontend production (*React/Vue/Flutter*) bernilai $100x$.
* **The "Sacrificial Concept" Mindset:** Wireframe dan Lo-Fi prototype dirancang untuk dibuang (*disposable artifacts*). Jangan membangun keterikatan emosional pada tata letak awal. Tujuannya adalah membuktikan hipotesis interaksi salah secepat mungkin (*fail-fast spatial testing*).

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah diagram aliran data dan operasional yang menghubungkan fase konseptualisasi spasial hingga instrumen validasi berbasis kode fungsional:

```
+-----------------------------------------------------------------------------+
|               RAPID VALIDATION ARCHITECTURE PIPELINE                        |
+-----------------------------------------------------------------------------+
 [User Task Flow]
        |
        v
 [Spatial Wireframe System]  <---+  (Zero-chroma tokenization)
        |                        |
        v                        |
 [Lo-Fi Code Prototype]          |  Feedback Loop: Redesign Spatial Layout
  ├── Semantic DOM Skeleton      |
  ├── Telemetry Event Bus        |
  └── Dynamic Mock Data Router   |
        |                        |
        v                        |
 [Interaction Execution]         |
  ├── Micro-task: Step A         |
  ├── Micro-task: Step B         |
  └── Micro-task: Step C         |
        |                        |
        v                        |
 [Diagnostic Capture Engine]     |
  ├── Timestamp delta (ToT)      |
  ├── Misclick Tracker (Rage)    |
  └── Drop-off Coordinate Log    |
        |                        |
        +------------------------+ (Gagal kriteria TSR < 85%)
        |
        v (Lolos kriteria TSR >= 85%)
 [Hand-off to Hi-Fi & Design System Integration]
```

### State Machine Interaksi Prototipe Validasi
```
  [IDLE_UNLOADED]
         |
         | (Window Load / Session Token Init)
         v
  [TASK_INITIALIZED] <---------------------------------------------+
         |                                                         |
         | (User triggers primary CTA)                             |
         v                                                         |
  [INTERACTION_IN_PROGRESS]                                        | (Task Loop)
    ├── (Invalid Input / Dead Click) -> [MISCLICK_LOGGED]          |
    ├── (Time Threshold > 60s)        -> [FRICTION_FLAGGED]        |
    └── (Step Transition Validated)   -> [PROGRESS_UPDATED]        |
         |                                                         |
         v                                                         |
  [TASK_COMPLETED]                                                 |
         |                                                         |
         | (Send Payloads to Collector)                            |
         v                                                         |
  [METRICS_DISPATCHED] --------------------------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. The Anatomy of a Functional Lo-Fi Frame
Prototipe Lo-Fi tingkat lanjut membuang seluruh atribut visual non-esensial dan mempertahankan parameter mekanis fungsional:
* **Bounding Boxes (`div`, `section`, `main`):** Ditentukan strictly dengan *aspect-ratio* dan *fluid layout constraints* (`min-content`, `max-content`, `fr`).
* **Visual Anchor Markers:** Menggunakan substitusi geometris standar:
  * Gambar: Persegi panjang dengan garis diagonal ganda bersilang ($X$) atau kontainer abu-abu dengan rasio aspek eksplisit.
  * Teks: Batang abu-abu tipis (*skeleton bar*) untuk konten sekunder, namun menggunakan **Teks Nyata (Production Copy)** untuk label navigasi, nilai numerik krusial, dan tombol *Call to Action* (CTA). *Lorem Ipsum* dilarang keras pada alur keputusan kritis karena mendistorsi keterbacaan (*scanability*).
* **Affordance Cues:** Batasan status komponen hanya mencakup: `Default`, `Hover`, `Active`, `Focus`, dan `Disabled`, direpresentasikan murni lewat kontras monokromatik (`#FFFFFF`, `#E5E7EB`, `#9CA3AF`, `#111827`).

### 2. Instrumentasi Telemetri Validasi
Prototipe validasi cepat berbasis kode harus mengintegrasikan *state collection interceptor*:
* **Telemetry Event Hook:** Mengikat *listeners* pada simpul DOM interaktif untuk mendeteksi *dead clicks* (klik pada elemen non-interaktif) dan *rage clicks* (klik berulang $\ge 3$ kali dalam interval $\le 500\text{ ms}$).
* **Temporal Tracking:** Perekaman *monotonic time* (`performance.now()`) untuk mengukur *Time-on-Task (ToT)* presisi tinggi, menghilangkan distorsi pergeseran waktu sistem.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Fitts's Law dan Hick-Hyman Law dalam Desain Lo-Fi

#### Fitts's Law
Memprediksi waktu ($MT$) yang dibutuhkan untuk bergerak cepat ke area target sebagai fungsi dari jarak ke target ($D$) dan lebar target ($W$):

$$MT = a + b \cdot \log_2 \left( \frac{2D}{W} \right)$$

Di mana indeks kesulitan interaksi (*Index of Difficulty / ID*) dinyatakan sebagai $\log_2(2D/W)$. 
* **Penerapan Lo-Fi:** Desainer tidak boleh mengabaikan ukuran target sentuh (*hit area*) hanya karena artefak berstatus "draft". Luas area klik tombol pada wireframe Lo-Fi harus segera disetel minimal $44 \times 44\text{ pt}$ (standar Apple HIG) atau $48 \times 48\text{ dp}$ (Android Material) untuk memastikan data *misclick rate* yang dikumpulkan selama validasi awal merefleksikan kondisi ergonomis perangkat sebenarnya.

#### Hick-Hyman Law
Menyatakan waktu yang dibutuhkan seseorang untuk mengambil keputusan ($T$) sebagai fungsi dari jumlah opsi alternatif ($n$):

$$T = b \cdot \log_2(n + 1)$$

* **Penerapan Lo-Fi:** Wireframing struktural berfungsi untuk menguji redundansi navigasi. Menghilangkan elemen visual dekoratif memungkinkan arsitek UX menghitung secara langsung apakah penambahan percabangan pada pohon navigasi meningkatkan waktu kognitif pengguna di luar batas toleransi efisiensi alur.

### The Grayscale Visual Hierarchy Rule
* **Base Background:** White (`#FFFFFF`) / Light Gray (`#F9FAFB`).
* **Structural Borders:** Mid-light Gray (`#D1D5DB`).
* **Informational Containers (Secondary):** Neutral (`#F3F4F6`).
* **Content Text/Typography:** Dark Neutral (`#1F2937`).
* **Focus & Action Indicator (The Single Chroma Rule):** Satu warna netral berbobot kontras tinggi (`#111827`) atau aksen fungsional tunggal (misal: Deep Blue `#1D4ED8`) untuk mengarahkan pengguna secara eksklusif ke tujuan operasional tanpa kebisingan estetika.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Implementasi prototipe mandiri (single-file HTML) yang mengintegrasikan wireframe struktural beresolusi monokromatik dengan instrumentasi telemetri pelacakan validasi pengguna:

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Lo-Fi Validation Prototype: Multi-Step Checkout Flow</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    /* Lo-Fi Image Placeholder Wireframe Diagonal Pattern */
    .wireframe-img-placeholder {
      background: linear-gradient(to top right, transparent calc(50% - 1px), #9ca3af 50%, transparent calc(50% + 1px)),
                  linear-gradient(to bottom right, transparent calc(50% - 1px), #9ca3af 50%, transparent calc(50% + 1px));
      background-color: #e5e7eb;
    }
  </style>
</head>
<body class="bg-gray-100 text-gray-900 font-mono antialiased min-h-screen flex flex-col justify-between">

  <!-- Header Navigasi Struktural Monokrom -->
  <header class="border-b-2 border-dashed border-gray-400 bg-white p-4">
    <div class="max-w-4xl mx-auto flex justify-between items-center">
      <div class="font-bold text-lg tracking-widest uppercase border-2 border-black px-2 py-1">[LOGO]</div>
      <nav class="flex space-x-4 text-sm text-gray-600">
        <span class="underline">01. Keranjang</span>
        <span class="font-bold text-black border-b-2 border-black">02. Pembayaran</span>
        <span class="text-gray-400">03. Review</span>
      </nav>
    </div>
  </header>

  <!-- Kontainer Utama Task Validasi -->
  <main class="max-w-4xl mx-auto w-full p-4 my-6 grid grid-cols-1 md:grid-cols-3 gap-6 flex-grow">
    
    <!-- Kolom Kiri: Formulir Interaksi (2 Kolom) -->
    <section class="md:col-span-2 bg-white border-2 border-gray-800 p-6 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
      <h1 class="text-xl font-bold mb-4 border-b-2 border-gray-200 pb-2">Informasi Penagihan & Alamat</h1>
      
      <form id="checkout-form" class="space-y-4" novalidate>
        <div>
          <label for="fullName" class="block text-xs uppercase font-bold text-gray-700 mb-1">Nama Lengkap Sesuai KTP *</label>
          <input 
            type="text" 
            id="fullName" 
            name="fullName" 
            required 
            placeholder="John Doe" 
            class="w-full border-2 border-gray-400 p-2 text-sm focus:border-black focus:outline-none transition-colors"
          />
          <span class="text-xs text-red-600 hidden font-sans mt-1" id="err-fullName">Bidang ini wajib diisi dengan benar.</span>
        </div>

        <div>
          <label for="address" class="block text-xs uppercase font-bold text-gray-700 mb-1">Alamat Pengiriman Lengkap *</label>
          <textarea 
            id="address" 
            name="address" 
            rows="3" 
            required
            placeholder="Jl. Sudirman No. 42, Kavling 3, Jakarta Selatan" 
            class="w-full border-2 border-gray-400 p-2 text-sm focus:border-black focus:outline-none transition-colors"
          ></textarea>
          <span class="text-xs text-red-600 hidden font-sans mt-1" id="err-address">Alamat harus diisi lengkap.</span>
        </div>

        <fieldset class="border-2 border-gray-300 p-3">
          <legend class="text-xs font-bold uppercase px-1 text-gray-600">Metode Pengiriman</legend>
          <div class="space-y-2 mt-1">
            <label class="flex items-center space-x-2 text-sm cursor-pointer">
              <input type="radio" name="shippingMethod" value="express" class="accent-black" checked>
              <span>Express Next-Day (Rp 30.000)</span>
            </label>
            <label class="flex items-center space-x-2 text-sm cursor-pointer">
              <input type="radio" name="shippingMethod" value="standard" class="accent-black">
              <span>Reguler Ekonomi (Rp 15.000)</span>
            </label>
          </div>
        </fieldset>

        <button 
          type="submit" 
          id="btn-submit" 
          class="w-full bg-black text-white py-3 uppercase tracking-wider font-bold text-sm hover:bg-gray-800 active:translate-y-0.5 transition-all cursor-pointer"
        >
          Lanjut ke Konfirmasi &rarr;
        </button>
      </form>
    </section>

    <!-- Kolom Kanan: Spatial Anchor Summary (1 Kolom) -->
    <aside class="bg-gray-50 border-2 border-gray-300 p-4 h-fit space-y-4">
      <h2 class="text-xs font-bold uppercase text-gray-500 tracking-wider">Ringkasan Pesanan</h2>
      
      <!-- Visual Placeholder Wireframe -->
      <div class="flex items-center space-x-3">
        <div class="w-16 h-16 wireframe-img-placeholder border border-gray-400 flex-shrink-0"></div>
        <div class="space-y-1 w-full">
          <div class="h-3 bg-gray-300 rounded w-3/4"></div>
          <div class="h-3 bg-gray-200 rounded w-1/2"></div>
          <div class="text-xs font-bold text-gray-700 mt-1">1x Rp 1.250.000</div>
        </div>
      </div>

      <div class="border-t border-dashed border-gray-300 pt-3 space-y-2 text-xs">
        <div class="flex justify-between">
          <span class="text-gray-500">Subtotal</span>
          <span>Rp 1.250.000</span>
        </div>
        <div class="flex justify-between">
          <span class="text-gray-500">Estimasi Pajak</span>
          <span>Rp 137.500</span>
        </div>
        <div class="flex justify-between font-bold text-sm border-t border-gray-400 pt-2">
          <span>Total Akhir</span>
          <span>Rp 1.387.500</span>
        </div>
      </div>
    </aside>
  </main>

  <!-- Instrumentasi Telemetri Pengujian UX -->
  <footer class="bg-gray-900 text-gray-400 p-4 text-xs font-mono">
    <div class="max-w-4xl mx-auto flex flex-col md:flex-row justify-between items-center gap-2">
      <div>Telemetri Validasi: Status Rekam Aktif</div>
      <div id="telemetry-display" class="text-yellow-400">Time-on-Task: 0.00s | Dead/Rage Clicks: 0</div>
    </div>
  </footer>

  <script>
    (function initUsabilityTestingEngine() {
      const startTime = performance.now();
      let deadClickCount = 0;
      let lastClickTimestamp = 0;
      let rapidClickCount = 0;
      const metricsPayload = {
        taskId: "task_checkout_phase_1",
        timeOnTaskMs: 0,
        misclicks: 0,
        validationErrors: 0,
        completionStatus: "abandoned"
      };

      // Timer real-time untuk display telemetri
      const timerInterval = setInterval(() => {
        const currentToT = ((performance.now() - startTime) / 1000).toFixed(2);
        document.getElementById("telemetry-display").innerText = 
          `Time-on-Task: ${currentToT}s | Dead/Rage Clicks: ${deadClickCount}`;
      }, 100);

      // Dead Click and Rage Click Interceptor
      document.addEventListener("click", (e) => {
        const now = performance.now();
        const interactiveTarget = e.target.closest("button, input, textarea, a, label");

        if (!interactiveTarget) {
          deadClickCount++;
        }

        if (now - lastClickTimestamp < 400) {
          rapidClickCount++;
          if (rapidClickCount >= 3) {
            console.warn("[UX TELEMETRY] RAGE CLICK DETECTED pada Node:", e.target);
            deadClickCount++;
            rapidClickCount = 0;
          }
        } else {
          rapidClickCount = 1;
        }
        lastClickTimestamp = now;
      });

      // Validasi Form dan Event Completion
      const form = document.getElementById("checkout-form");
      form.addEventListener("submit", (e) => {
        e.preventDefault();
        let hasError = false;

        const fullName = document.getElementById("fullName");
        const address = document.getElementById("address");
        const errFullName = document.getElementById("err-fullName");
        const errAddress = document.getElementById("err-address");

        if (!fullName.value.trim()) {
          errFullName.classList.remove("hidden");
          fullName.classList.add("border-red-600");
          hasError = true;
        } else {
          errFullName.classList.add("hidden");
          fullName.classList.remove("border-red-600");
        }

        if (!address.value.trim()) {
          errAddress.classList.remove("hidden");
          address.classList.add("border-red-600");
          hasError = true;
        } else {
          errAddress.classList.add("hidden");
          address.classList.remove("border-red-600");
        }

        if (hasError) {
          metricsPayload.validationErrors++;
          return;
        }

        // Sukses Task
        clearInterval(timerInterval);
        metricsPayload.timeOnTaskMs = Math.round(performance.now() - startTime);
        metricsPayload.misclicks = deadClickCount;
        metricsPayload.completionStatus = "success";

        console.info("[UX TELEMETRY COMPLETE] Task Dispatching Data:", metricsPayload);
        alert(`Task Sukses divalidasi!\nTime on Task: ${(metricsPayload.timeOnTaskMs / 1000).toFixed(2)} detik\nTotal Misclicks: ${metricsPayload.misclicks}\nForm Errors: ${metricsPayload.validationErrors}`);
      });
    })();
  </script>
</body>
</html>
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Konfigurasi Visual Skeletal (CSS & Layouting)
* **Baris 11–17:** `.wireframe-img-placeholder`: Memanfaatkan teknik *dual linear-gradient* yang saling bersilangan membentuk kurva diagonal $X$ monokromatik. Ini secara visual membedakan aset grafis ilustratif/foto dari elemen data tanpa memerlukan pemuatan gambar raster eksternal, mematuhi prinsip nihil estetika visual prematur.
* **Baris 20:** `font-mono`: Menggunakan font *monospaced* netral secara seragam di seluruh antarmuka. Pemilihan ini mengecilkan bias persepsi keindahan tipografi sans-serif modern (*Inter*, *Roboto*) dan memaksa subjek uji fokus pada relasi struktural dan pemahaman teks label fungsional.
* **Baris 35:** `shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]`: Penerapan bayangan *brutalist monokrom*. Memberikan indikasi spasial kedalaman (*depth perception*) elevasi $Z$-index murni dengan kontras tinggi tanpa bergantung pada blur *soft-shadow* modern yang memecah konsentrasi.

### Arsitektur Telemetri UX Berbasis Event (JavaScript Engine)
* **Baris 114:** `performance.now()`: Perekaman waktu berbasis monolitik presisi sub-milidetik. Bertujuan mengabaikan manipulasi jam sistem perangkat pengguna untuk menjamin kalkulasi *Time-on-Task (ToT)* akurat.
* **Baris 131–146:** *Dead-Click and Rage-Click Interception Model*:
  * Metode `e.target.closest("button, input, textarea, a, label")` memverifikasi apakah koordinat interaksi berlabuh pada simpul interaktif semantik. Apabila bernilai `null`, variabel `deadClickCount` bertambah secara deterministik.
  * Blok `(now - lastClickTimestamp < 400)` mendeteksi anomali kecepatan klik. Jika frekuensi klik mencapai ambang $\ge 3$ kali dalam jendela 400 ms, sistem menandai sebagai sinyal frustrasi kognitif (*rage-click*), mengisolasi elemen yang ambigu dalam desain spasial.
* **Baris 150–186:** *Validation Interception Phase*: Menghitung kegagalan input form pengguna ke dalam metrik `validationErrors`. Menangkap ambiguitas penamaan label *field* form sejak fase prototipe Lo-Fi, menghindari keterlambatan redesain saat backend API sudah terikat kontrak.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: Rekayasa Ulang Alur "One-Click Settlement" Enterprise B2B SaaS
* **Perusahaan:** PT Fintek Logistik Nusantara (SaaS Manajemen Invoice B2B).
* **Masalah:** Alur persetujuan faktur massal (*batch settlement*) memiliki *abandonment rate* 48% di tahap produksi. Versi High-Fidelity UI sebelumnya sarat dengan *modal pop-ups*, animasi mikro, dan skema palet korporat yang rumit, mengakibatkan waktu pelatihan pengguna operasional mencapai 3 minggu.
* **Hipotesis Desain:** Mengganti model *nested modal* dengan pola tata letak panel terpisah (*Split-Panel Workspace*) secara monokromatik deterministik akan memotong *Time-on-Task (ToT)* hingga $\ge 35\%$ dan menekan angka kegagalan otorisasi (*Authorization Error Rate*) menjadi di bawah 5%.
* **Metodologi Pengujian:** Pengujian *Unmoderated Usability Testing* melibatkan 30 manajer keuangan menggunakan prototipe Lo-Fi fungsional berbasis web tanpa warna, menguji akurasi eksekusi seleksi, kalkulasi toleransi pajak, dan *bulk signing*.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah kode produksi instrumen pengujian Lo-Fi terstruktur untuk skenario *Split-Panel Batch Settlement Engine* enterprise, dilengkapi *telemetry collector payload generator*:

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Enterprise B2B Batch Settlement - Lo-Fi Testbed</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    .split-pane { height: calc(100vh - 4rem); }
  </style>
</head>
<body class="bg-gray-200 text-gray-900 font-sans antialiased overflow-hidden">

  <!-- Top System App Bar -->
  <header class="h-16 bg-white border-b-2 border-gray-400 px-6 flex justify-between items-center z-10 relative">
    <div class="flex items-center space-x-4">
      <div class="h-8 w-8 bg-gray-900 text-white font-mono flex items-center justify-center font-bold text-xs">B2B</div>
      <span class="font-mono text-sm tracking-wide font-bold uppercase">Console &rsaquo; Invoicing &rsaquo; Batch Settlement</span>
    </div>
    <div class="flex items-center space-x-4 font-mono text-xs">
      <span class="bg-gray-100 border border-gray-400 px-3 py-1.5" id="selection-counter">0 Dokumen Dipilih</span>
      <button id="btn-batch-settle" disabled class="bg-gray-400 text-gray-700 px-4 py-2 uppercase font-bold cursor-not-allowed transition-all">
        Eksekusi Settlement
      </button>
    </div>
  </header>

  <!-- Split Panel Interface -->
  <main class="split-pane grid grid-cols-12 overflow-hidden">
    
    <!-- Left Panel: Data Table Stream (7 Kolom) -->
    <section class="col-span-7 bg-white border-r-2 border-gray-400 overflow-y-auto p-6">
      <div class="flex justify-between items-center mb-4">
        <h2 class="font-mono text-sm font-bold uppercase tracking-wider">Antrean Invoice Belum Terbayar</h2>
        <div class="text-xs font-mono text-gray-500">Menampilkan 3 Entri Tertunda</div>
      </div>

      <table class="w-full text-left border-collapse font-mono text-xs">
        <thead>
          <tr class="border-b-2 border-black bg-gray-100">
            <th class="p-3 w-10 text-center"><input type="checkbox" id="select-all" class="accent-black cursor-pointer"></th>
            <th class="p-3">NO. INVOICE</th>
            <th class="p-3">VENDOR</th>
            <th class="p-3 text-right">TOTAL NILAI</th>
            <th class="p-3 text-center">STATUS</th>
          </tr>
        </thead>
        <tbody id="invoice-table-body" class="divide-y divide-gray-300">
          <tr class="hover:bg-gray-50 cursor-pointer" data-id="INV-001" data-amount="45000000">
            <td class="p-3 text-center"><input type="checkbox" class="row-checkbox accent-black cursor-pointer"></td>
            <td class="p-3 font-bold">INV/2026/03/001</td>
            <td class="p-3">PT Global Logistik Sentosa</td>
            <td class="p-3 text-right">Rp 45.000.000</td>
            <td class="p-3 text-center"><span class="border border-gray-400 px-2 py-0.5 text-[10px]">PENDING</span></td>
          </tr>
          <tr class="hover:bg-gray-50 cursor-pointer" data-id="INV-002" data-amount="12500000">
            <td class="p-3 text-center"><input type="checkbox" class="row-checkbox accent-black cursor-pointer"></td>
            <td class="p-3 font-bold">INV/2026/03/002</td>
            <td class="p-3">CV Baja Perkasa Mandiri</td>
            <td class="p-3 text-right">Rp 12.500.000</td>
            <td class="p-3 text-center"><span class="border border-gray-400 px-2 py-0.5 text-[10px]">PENDING</span></td>
          </tr>
          <tr class="hover:bg-gray-50 cursor-pointer" data-id="INV-003" data-amount="89200000">
            <td class="p-3 text-center"><input type="checkbox" class="row-checkbox accent-black cursor-pointer"></td>
            <td class="p-3 font-bold">INV/2026/03/003</td>
            <td class="p-3">PT Samudra Maritim Trans</td>
            <td class="p-3 text-right">Rp 89.200.000</td>
            <td class="p-3 text-center"><span class="border border-gray-400 px-2 py-0.5 text-[10px]">PENDING</span></td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- Right Panel: Inspection & Ledger Aggregator (5 Kolom) -->
    <aside class="col-span-5 bg-gray-50 overflow-y-auto p-6 flex flex-col justify-between">
      <div class="space-y-6">
        <div>
          <h3 class="font-mono text-sm font-bold uppercase tracking-wider border-b-2 border-gray-300 pb-2">Inspeksi Settlement Ledger</h3>
          <p class="text-xs font-mono text-gray-500 mt-1">Audit validasi debit pool sebelum eksekusi massal.</p>
        </div>

        <!-- Ledger Metrics Matrix -->
        <div class="bg-white border-2 border-gray-300 p-4 space-y-3 font-mono text-xs">
          <div class="flex justify-between">
            <span class="text-gray-500">Akun Rekening Sumber:</span>
            <span class="font-bold">IDR ESCROW #982-10029-1</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-500">Total Akumulasi Debit:</span>
            <span id="txt-accumulated-debit" class="font-bold text-sm">Rp 0</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-500">Biaya Kliring Gateway:</span>
            <span id="txt-clearing-fee" class="font-bold">Rp 0</span>
          </div>
          <div class="border-t-2 border-dashed border-gray-300 pt-2 flex justify-between text-black font-bold">
            <span>Total Pengeluaran Saldo:</span>
            <span id="txt-grand-total">Rp 0</span>
          </div>
        </div>

        <!-- Compliance Check -->
        <div class="border-2 border-gray-300 bg-white p-4">
          <label class="flex items-start space-x-2 text-xs font-mono cursor-pointer">
            <input type="checkbox" id="compliance-check" class="accent-black mt-0.5 cursor-pointer">
            <span class="text-gray-700 leading-relaxed">
              Saya menyatakan otorisasi settlement batch ini tunduk pada audit SOP Perusahaan No. 44/FIN/2026 dan dana escrow telah teralokasi valid.
            </span>
          </label>
        </div>
      </div>

      <!-- Telemetry Output Hub Status -->
      <div class="border-2 border-black bg-white p-3 font-mono text-[11px] text-gray-600">
        <span class="font-bold text-black uppercase">Session Diagnostic Stream:</span>
        <div id="live-diagnostic-log" class="mt-1 text-gray-500 truncate">Menunggu interaksi operator...</div>
      </div>
    </aside>
  </main>

  <script>
    (function initEnterpriseSettlementTesting() {
      const taskStartTime = performance.now();
      let state = {
        selectedInvoices: new Set(),
        complianceApproved: false,
        misclickEvents: [],
        taskAttempts: 0
      };

      const tableBody = document.getElementById("invoice-table-body");
      const selectAll = document.getElementById("select-all");
      const selectionCounter = document.getElementById("selection-counter");
      const btnBatchSettle = document.getElementById("btn-batch-settle");
      const complianceCheck = document.getElementById("compliance-check");
      