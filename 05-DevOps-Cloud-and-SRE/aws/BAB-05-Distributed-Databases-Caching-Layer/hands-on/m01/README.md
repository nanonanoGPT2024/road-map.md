# Hands-On Lab: Distributed Databases & Multi-Region Caching Simulation

## 1. Deskripsi Lab
Lab praktis ini dirancang untuk mendemonstrasikan secara transparan mekanisme internal arsitektur database terdistribusi dan caching layer di AWS tanpa memerlukan tagihan akun cloud AWS aktif.

Melalui simulator ini, Anda akan membedah:
1. **Replikasi Multi-Region Active-Active**: Bagaimana mutasi data pada satu region didistribusikan secara asinkronus ke region lain (seperti yang dilakukan DynamoDB Global Tables).
2. **Resolusi Konflik Last-Writer-Wins (LWW)**: Penyelesaian deterministik ketika dua region menerima penulisan data konkuren pada *item partition key* yang sama.
3. **Pola Caching Cache-Aside (Lazy Loading)**: Pengurangan latensi pembacaan data dari penyimpanan disk via in-memory caching (ElastiCache/MemoryDB).
4. **Cache Invalidation via CDC (Change Data Capture)**: Pengusiran (*eviction*) cache otomatis ketika terdeteksi rekaman modifikasi baru pada data stream.

---

## 2. Struktur Berkas
- `dynamodb_global_replication_sim.py`: Script Python runnable mandiri (multi-threaded) yang memodelkan replikasi cross-region dan local cache.

---

## 3. Kebutuhan Sistem (Prerequisites)
- Python versi 3.8 atau lebih baru.
- Terminal/Shell yang mendukung ANSI color codes (Linux, macOS, WSL2, atau Git Bash/Windows Terminal).
- Tidak membutuhkan library pihak ketiga (`pip install` tidak diperlukan; seluruh modul menggunakan standard library `threading`, `time`, dan `json`).

---

## 4. Langkah-Langkah Menjalankan Lab

### Langkah 1: Navigasi ke Direktori Hands-On
Buka terminal dan arahkan kursor ke direktori modul:
```bash
cd hands-on/m01
```

### Langkah 2: Berikan Izin Eksekusi pada Skrip
```bash
chmod +x dynamodb_global_replication_sim.py
```

### Langkah 3: Eksekusi Skrip Simulasi
Jalankan simulator menggunakan interpreter Python 3:
```bash
python3 dynamodb_global_replication_sim.py
```

---

## 5. Analisis Hasil Simulasi

Saat skrip dijalankan, perhatikan 4 tahapan eksekusi pada log terminal:

1. **Skenario 1 - Write Propagation**:
   - Terjadi `[LOCAL-WRITE]` di `us-east-1`.
   - DynamoDB Stream memancarkan event `INSERT`.
   - Thread replikasi cross-region menerima data di `eu-west-1` dengan status `[REPLICATION-NEW]`.

2. **Skenario 2 - Cache-Aside Flow**:
   - Pembacaan pertama di `eu-west-1` memicu `[CACHE-MISS]` dan mengambil data dari persistent table dictionary.
   - Pembacaan kedua di `eu-west-1` langsung memicu `[CACHE-HIT]` dari in-memory RAM tanpa membebani disk.

3. **Skenario 3 & 4 - Concurrent Active-Active Conflicts (LWW)**:
   - Dua thread menulis ke `PRODUCT#SKU-7721` secara serentak di Region US dan Region EU.
   - Timestamp internal presisi tinggi (`_last_updated_at`) dievaluasi.
   - Region yang menerima write dengan timestamp lebih tua akan mencatat log `[REPLICATION-DISCARD]` (kalah LWW).
   - Kedua region secara deterministik konvergen ke versi data yang sama persis (`[SUCCESS] Global Convergence Tercapai!`).

---

## 6. Eksperimen Mandiri Lanjutan
Untuk memperdalam pemahaman, buka file `dynamodb_global_replication_sim.py` dan lakukan modifikasi berikut:
1. **Ubah Nilai TTL Cache**: Ubah parameter `default_ttl_sec` pada kelas `InMemoryCache` dari `2.0` detik menjadi `0.5` detik. Amati bagaimana cache expired sebelum read berikutnya dipanggil.
2. **Simulasikan Network Partition**: Tambahkan probabilitas kegagalan (packet loss) pada fungsi `apply_replicated_write` untuk mensimulasikan terputusnya koneksi fiber optic bawah laut antar-region AWS. Amati terjadinya kondisi inkonsistensi data sementara (*stale state*).