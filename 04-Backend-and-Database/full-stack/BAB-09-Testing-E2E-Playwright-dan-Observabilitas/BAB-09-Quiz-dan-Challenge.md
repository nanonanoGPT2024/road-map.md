---
[⬅️ Module 02: OpenTelemetry & Core Web Vitals](./Module-02-OpenTelemetry-FullStack-Tracing-dan-Core-Web-Vitals.md) | [📋 Silabus Induk](../README.md) | [BAB 10: Serverless & Monorepo ➡️](../BAB-10-Serverless-Edge-Infrastructure-dan-Monorepo/Module-01-Serverless-Cloudflare-Edge-Workers-Cold-Starts.md)
---

# BAB 09: Evaluasi Pembelajaran — Quiz, Challenge, & Knowledge Check

## 1. Uji Pemahaman Mandiri (Quiz)

### A. Soal Tingkat Dasar (Basic Questions)
1. **Mengapa Playwright dianggap lebih tahan banting (*resilient*) terhadap masalah tes rapuh (*flaky tests*) dibandingkan Selenium tradisional?**
2. **Apa fungsi dari file `storageState.json` pada arsitektur pengujian Playwright dan bagaimana fitur ini memangkas waktu eksekusi CI/CD?**
3. **Sebutkan dan jelaskan tiga metrik utama dalam Google Core Web Vitals (LCP, INP, CLS) beserta ambang batas skor "Baik" (*Good*) untuk masing-masing metrik!**
4. **Apa perbedaan mendasar antara metrik baru Interaction to Next Paint (INP) dengan metrik pendahulunya First Input Delay (FID)?**
5. **Bagaimana format standar header W3C `traceparent` disusun dan informasi apa saja yang dikandungnya?**

---

### B. Soal Tingkat Menengah (Intermediate Questions)
6. **Jelaskan bagaimana metode `page.route()` di Playwright memungkinkan pengujian frontend mensimulasikan kegagalan jaringan (seperti HTTP 500 atau timeout) tanpa menyentuh server backend produksi!**
7. **Mengapa pengujian Visual Regression memerlukan penentuan ambang batas toleransi piksel (`maxDiffPixelRatio`) dan apa penyebab kegagalan tes visual saat dijalankan di sistem operasi berbeda?**
8. **Jelaskan perbedaan peran antara *Metrics*, *Logs*, dan *Distributed Traces* dalam observabilitas aplikasi full-stack modern!**
9. **Bagaimana sebuah *Sequential Async Waterfall* dapat merusak skor Largest Contentful Paint (LCP) pada aplikasi web dan bagaimana teknik eksekusi paralel mengatasinya?**
10. **Apa yang dimaksud dengan *Head-Based Sampling* vs *Tail-Based Sampling* pada arsitektur OpenTelemetry Collector? Kapan kita harus memilih salah satunya?**

---

### C. Soal Berbasis Skenario Arsitektur (Scenario-Based Questions)
11. **Skenario Kasus — Flaky Payment Gateway Test di Pipeline CI**:
    Sebuah pengujian E2E checkout Playwright sering kali gagal secara acak di GitHub Actions saat mengklik tombol "Bayar dengan Kartu Kredit", karena API sandbox Stripe eksternal kadang memakan waktu 8 detik untuk merespons. Bagaimana Anda mendesain ulang pengujian tersebut menggunakan *Network Interception & Synthetic Response Mocking* agar tes selalu selesai dalam waktu < 200ms dengan stabilitas 100%?
12. **Skenario Kasus — Investigasi Lonjakan Latensi Global**:
    Dashboard pemantauan melaporkan bahwa pengguna di wilayah Asia Tenggara mengalami lonjakan latensi checkout dari 300ms menjadi 2.800ms. Berbekal OpenTelemetry Distributed Tracing, jelaskan langkah-langkah sistematis yang Anda ambil untuk menemukan komponen akar masalah (*Root Cause Analysis*) hanya dengan membaca Flame Graph Trace ID!
13. **Skenario Kasus — Perbaikan Cumulative Layout Shift (CLS) Akibat Font & Banner Dinamis**:
    Skor CLS sebuah landing page bernilai 0.35 (Merah / Buruk). Dua biang keladinya adalah: (1) teks berkedip dan melompat saat web font eksternal selesai diunduh (*FOUT*), dan (2) banner diskon dinamis disuntikkan di atas navigasi tanpa reservasi ruang layout. Jelaskan bagaimana Anda memperbaiki kedua masalah tersebut menggunakan optimasi `@next/font` dan CSS `min-height / aspect-ratio`!

---

## 2. Chapter Challenge: Synthetic Monitoring & Auto-Remediation Pipeline

### Deskripsi Tantangan
Anda diminta merancang sistem pemantauan sintetis (*Synthetic E2E Health Check*) untuk aplikasi perbankan digital. Sistem harus menjalankan skenario transaksi Playwright di lingkungan staging setiap 10 menit, merekam metrik OpenTelemetry, dan memicu peringatan otomatis jika terdeteksi anomali.

### Kebutuhan & Spesifikasi:
1. **Automated User Journey**:
   - Skrip Playwright harus menguji alur login (re-using `storageState`), membuka mutasi rekening, dan melakukan transfer antar-bank sintetis dengan mock API.
2. **Telemetry Span Injection**:
   - Selama skrip Playwright berjalan, injeksikan header W3C `traceparent` ke setiap request HTTP yang dikirimkan browser.
3. **Core Web Vitals Threshold Gate**:
   - Kumpulkan metrik performa browser secara real-time. Jika pengujian mendeteksi LCP > 2.500ms atau INP > 200ms, gagalkan proses pengujian dengan status `PERFORMANCE_REGRESSION`.
4. **Artifact Failure Recording**:
   - Jika tes gagal atau mengalami timeout, simpan rekaman video eksekusi, screenshot layar terakhir, dan trace file `.zip` untuk dianalisis oleh tim on-call.

---

## 3. Knowledge Check & Mastery Checklist

### Yang Wajib Anda Pahami:
- [ ] Keunggulan arsitektur Playwright (Auto-Waiting, Web-First Assertions, isolasi browser context).
- [ ] Standar Google Core Web Vitals: LCP (Loading), INP (Responsivitas Interaksi), dan CLS (Stabilitas Visual).
- [ ] Arsitektur Distributed Tracing OpenTelemetry dan propagasi W3C Trace Context.
- [ ] Dampak buruk kueri berantai (*sequential async waterfalls*) terhadap latensi aplikasi.

### Yang Tidak Perlu Anda Hafal di Luar Kepala:
- Rumus kalkulasi internal matriks pergeseran piksel CLS (dihitung otomatis oleh browser PerformanceObserver API).
- Skema biner Protocol Buffers OTLP (telah ditangani secara native oleh OTel SDK exporter).

### Yang Harus Bisa Anda Lakukan:
- [ ] Menulis skenario pengujian E2E menggunakan Playwright dengan locator semantik (`getByRole`, `getByText`).
- [ ] Melakukan mocking network request menggunakan `page.route()`.
- [ ] Mengonfigurasi OpenTelemetry di aplikasi Next.js menggunakan file `instrumentation.ts`.
- [ ] Menangkap dan menganalisis metrik Core Web Vitals di frontend menggunakan `useReportWebVitals`.

---

## 4. Ringkasan Bab (Chapter Summary)
Bab 09 telah melengkapi keahlian Anda dengan instrumen penjamin kualitas dan observabilitas tingkat enterprise:
1. **Playwright E2E Automation** memberikan jaminan bahwa fitur-fitur kritis aplikasi berjalan mulus dari sudut pandang browser nyata pengguna tanpa dihantui oleh masalah *flaky tests*.
2. **OpenTelemetry & Core Web Vitals** memberi Anda mata elang untuk melihat setiap pergeseran piksel antarmuka dan setiap milidetik perjalanan paket data di backend serverless dan database.

Kini aplikasi Anda telah teruji dan terobservasi dengan sempurna! Kita siap melangkah ke bab pamungkas sebelum Capstone Project: **BAB 10: Serverless, Edge Infrastructure, Monorepo, & CI/CD**, di mana kita akan membedah orkestrasi Turborepo, containerization Docker, Cloudflare Workers, dan pipeline GitOps!

---
[⬅️ Module 02: OpenTelemetry & Core Web Vitals](./Module-02-OpenTelemetry-FullStack-Tracing-dan-Core-Web-Vitals.md) | [📋 Silabus Induk](../README.md) | [BAB 10: Serverless & Monorepo ➡️](../BAB-10-Serverless-Edge-Infrastructure-dan-Monorepo/Module-01-Serverless-Cloudflare-Edge-Workers-Cold-Starts.md)
---
