# Panduan Hands-On: Capacity Planning & Chaos Engineering Simulator

Panduan teknis langkah demi langkah untuk menjalankan simulasi kapasitas antrean sistem terdistribusi, pengujian beban bebas *Coordinated Omission*, dan injeksi kegagalan chaos (*Fault Injection*).

---

## 1. Prasyarat Sistem
- **Python**: Versi `3.8` atau yang lebih baru.
- **Modul Eksternal**: Simulator menggunakan *Standard Library* bawaan Python (`threading`, `queue`, `dataclasses`, `time`, `random`, `math`, `logging`), tidak memerlukan instalasi `pip` tambahan.
- Sistem Operasi: Linux, macOS, atau Windows (disarankan terminal berbasis Unix untuk representasi format escape string).

---

## 2. Struktur File Lab
```
hands-on/m01/
├── README.md                     # Petunjuk lab
└── chaos_fault_injection_sim.py   # Kode simulator utama
```

---

## 3. Langkah Menjalankan Simulasi

### Langkah 1: Persiapan Environment
Buka terminal Anda dan masuk ke direktori modul hands-on:
```bash
cd hands-on/m01
chmod +x chaos_fault_injection_sim.py
```

### Langkah 2: Eksekusi Eksperimen
Jalankan simulator secara langsung:
```bash
python3 chaos_fault_injection_sim.py
```

---

## 4. Rincian Fase Eksperimen yang Diamati

| Fase | Waktu (Detik) | Kondisi Operasional | Apa yang Terjadi? |
| :--- | :--- | :--- | :--- |
| **Fase 1** | `0s - 7s` | **Baseline / Steady State** | Sistem melayani 1.200 RPS stabil. P50 latensi berkisar di ~35ms, queue size mendekati 0, error rate 0%. Sistem mematuhi perhitungan Little's Law ($L \approx 42$). |
| **Fase 2** | `8s - 16s` | **Chaos Fault Injection** | Injeksi latensi +120ms, packet loss 3%, dan kontensi CPU 3.5x. Latensi P95/P99 melonjak di atas 150ms. Jumlah in-flight request membengkak hingga memenuhi antrean buffer (200 item). Terjadi penolakan request (*Queue Drops*) secara masif. |
| **Fase 3** | `17s - 25s` | **Rollback & Self-Healing** | Injeksi dihentikan secara otomatis. Worker pool menguras antrean tertunggak, latensi kembali normal ke baseline ~35ms, dan error rate berhenti naik. |

---

## 5. Tugas Modifikasi Parameter (Eksperimen Lanjutan)

Buka berkas `chaos_fault_injection_sim.py` dan lakukan pengujian berikut untuk mengamati perilaku sistem:

### Eksperimen A: Uji Skalabilitas Worker Pool (Amdahl's Law)
1. Ubah parameter `WORKER_POOL_SIZE` dari `30` menjadi `120`.
2. Jalankan kembali script.
3. **Analisis**: Apakah peningkatan worker 4x lipat mampu menampung traffic saat chaos terjadi tanpa adanya *Queue Drops*? Amati lonjakan penggunaan thread dan perilaku latensi tail (p99).

### Eksperimen B: Proteksi Buffer Sizing & Fail-Fast
1. Perkecil ukuran `QUEUE_CAPACITY` dari `200` menjadi `20` (Pola *Fail-Fast*).
2. Naikkan `TARGET_RPS` menjadi `2000`.
3. **Analisis**: Mengapa membatasi buffer queue secara ketat justru melindungi latensi P99 dari degradasi ekstrem (*Bufferbloat prevention*), meskipun jumlah drops langsung meningkat seketika?

---

## 6. Output Terminal yang Diharapkan
```
===========================================================================
      SRE LAB: CAPACITY PLANNING & CHAOS EXPERIMENT SIMULATOR
===========================================================================

[1] Kalkulasi Kapasitas Little's Law:
    - Target Arrival Rate (lambda) : 1200 RPS
    - Base Latency Service (W)     : 35.0 ms
    - Kebutuhan Konkurensi Rata-rata (L) : 42.00 parallel execution
    - Worker Threads Dialokasikan  : 30
    - Bounded Queue Buffer Size    : 200

Status Simulasi:
Detik | Status       | In-Queue | P50 (ms) | P95 (ms) | P99 (ms) | Err Rate (%) | Queue Drops
-------------------------------------------------------------------------------------
    0 | STEADY       |        2 |     35.1 |     36.2 |     37.0 |        0.00% |           0
    1 | STEADY       |        0 |     35.0 |     36.0 |     36.9 |        0.00% |           0
    ...
[08:14:22] [WARNING] [MainThread] >>> [GAME DAY ACTION] Menginjeksi Chaos Faults:
    * Network Delay: +120ms
    * Packet Loss  : 3%
    * CPU Contention Factor: 3.5x
    8 | CHAOS ACTIVE |       98 |     78.4 |    156.2 |    168.1 |        2.14% |          12
    9 | CHAOS ACTIVE |      200 |    152.0 |    165.4 |    172.9 |        8.45% |         184
    ...
[08:14:30] [INFO] [MainThread] >>> [ROLLBACK / RECOVERY] Menghentikan Injeksi Chaos. Memulihkan Steady State...
   17 | RECOVERING   |       45 |    140.2 |    162.0 |    169.5 |       14.20% |        1250
   18 | STEADY       |        0 |     35.2 |     36.5 |     37.2 |       13.80% |        1250
```

---

## 7. Verifikasi Pembelajaran SRE
Setelah menjalankan simulasi ini, Anda telah berhasil memvalidasi secara langsung bahwa:
1. Peningkatan latensi downstream secara linier akan melipatgandakan kebutuhan konkurensi di sisi hulu (*Little's Law*).
2. Sistem yang tidak memiliki mekanisme *adaptive rate limiting* atau *circuit breaker* akan mengalami kehabisan buffer (*queue saturation*) saat dependensi downstream mengalami degradasi performa minor.
3. Observabilitas terhadap p95 dan p99 adalah satu-satunya cara objektif untuk mendeteksi *grey failures* sebelum seluruh layanan mengalami pemadaman total.