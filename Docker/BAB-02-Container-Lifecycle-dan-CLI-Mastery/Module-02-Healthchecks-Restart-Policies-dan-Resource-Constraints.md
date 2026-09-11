# Module 02: Healthchecks, Restart Policies, & Resource Constraints

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar diharapkan mampu:
- Mengonfigurasi dan mengoperasikan instruksi **Docker Healthcheck** deklaratif pada Dockerfile dan CLI.
- Membedakan status kesehatan container: `starting`, `healthy`, dan `unhealthy`.
- Memahami perbedaan krusial antara **Process Liveness** (proses PID 1 hidup) vs **Application Health** (aplikasi benar-benar siap melayani request).
- Memilih dan mengonfigurasi **Restart Policies** yang tepat: `no`, `always`, `unless-stopped`, dan `on-failure`.
- Mengontrol alokasi sumber daya perangkat keras secara presisi: batas memori keras (*Hard Limit*) vs lunak (*Soft Limit / Reservation*), kuota CPU, dan CPU core pinning (`--cpuset-cpus`).

---

## 2. Prerequisite
- Memahami status dasar container (Running, Stopped) dan exit code (BAB 02 Module 01).
- Memahami konsep Cgroups v2 pada kernel Linux (BAB 01 Module 02).
- Pengetahuan dasar tentang HTTP status codes (200 OK vs 500 Internal Error) dan perintah `curl`.

---

## 3. Concept
Secara default, Docker Daemon hanya memantau apakah proses **PID 1 masih hidup di memori**. Namun, dalam dunia nyata, sebuah aplikasi bisa saja mengalami kondisi **Deadlock**, kehabisan thread pool, atau database connection hang, di mana proses PID 1 tetap berstatus `Up / Running`, tetapi aplikasi **sudah tidak bisa merespons traffic sama sekali** (*Zombie State*).

**Docker Healthcheck** memecahkan masalah ini dengan menjalankan perintah pengujian berkala (misal `curl http://localhost:8080/healthz`) di dalam container. Jika perintah gagal beberapa kali berturut-turut, Docker mengubah status container menjadi **`unhealthy`**, memberi sinyal kepada orchestrator atau reverse proxy untuk mengalihkan traffic atau me-restart container.

```
       CONTAINER HEALTHCHECK STATE TRANSITIONS
                   ┌──────────────────┐
                   │  Container Start │
                   └────────┬─────────┘
                            │
                            ▼
                   ┌──────────────────┐
                   │ status: starting │ <── (start-period window: e.g. 15s)
                   └────────┬─────────┘
                            │
            ┌───────────────┴───────────────┐
            │ Healthcheck probe succeeds    │ Probe fails (retries > 3)
            ▼                               ▼
   ┌─────────────────┐             ┌─────────────────┐
   │ status: healthy │             │status: unhealthy│
   └────────┬────────┘             └────────┬────────┘
            │                               │
            │ Fails 3x consecutively        │ Restart Policy / Alerting
            └──────────────────────────────>│
```

---

## 4. Why?
1. **Pendeteksian Deadlock & Silent Failures**: Tanpa healthcheck, Docker menganggap aplikasi sehat selama prosesnya tidak crash, padahal ribuan pengguna mendapat pesan timeout. Healthcheck memverifikasi fungsionalitas end-to-end aplikasi.
2. **Kemandirian Pemulihan Otomatis (*Self-Healing*)**: Dengan memadukan `restart: always` atau `restart: on-failure`, container yang mengalami crash mendadak akibat panik runtime atau host reboot akan otomatis dibangkitkan kembali oleh Docker tanpa perlu campur tangan manusia.
3. **Pencegahan Alokasi Monopoli CPU**: Tanpa pembatasan `--cpus`, satu thread kalkulasi matematika atau query lambat dapat menghabiskan 100% dari seluruh core CPU yang tersedia di host, membuat server unresponsive.

---

## 5. What?
### Komponen Instruksi Healthcheck:
- `--interval=<duration>`: Seberapa sering pengujian dijalankan (default: `30s`).
- `--timeout=<duration>`: Waktu maksimal menunggu respons probe sebelum dianggap gagal (default: `30s`).
- `--start-period=<duration>`: Waktu tenggang startup inisialisasi aplikasi; kegagalan probe selama periode ini tidak dihitung dalam kuota retry (default: `0s`).
- `--retries=<N>`: Jumlah kegagalan berturut-turut yang dibutuhkan sebelum status diubah menjadi `unhealthy` (default: `3`).

### 4 Opsi Restart Policies:
- **`no`**: Kebijakan default. Container tidak akan pernah di-restart jika mati.
- **`always`**: Selalu me-restart container jika berhenti, apapun exit code-nya. Jika Docker daemon di-reboot, container otomatis dihidupkan kembali.
- **`unless-stopped`**: Mirip dengan `always`, dengan satu pengecualian: jika container dihentikan secara manual oleh admin (`docker stop`), container **TIDAK AKAN** otomatis hidup kembali saat daemon/server direstart.
- **`on-failure[:max-retries]`**: Me-restart container HANYA JIKA proses berhenti dengan exit code bukan 0 (kegagalan/crash). Jika proses selesai dengan normal (Exit 0), container tidak di-restart.

---

## 6. How?
### Konfigurasi Resource Constraints di CLI:
1. **Batas Memori Keras & Lunak**:
   - `--memory="512m"`: Batas keras (*Hard limit*). Melewati batas ini memicu kernel OOM Killer.
   - `--memory-reservation="256m"`: Batas lunak (*Soft limit*). Docker akan mencoba menjaga alokasi di angka ini saat server kekurangan memori.
2. **Batas Kuota CPU**:
   - `--cpus="2.0"`: Membatasi container menggunakan maksimal 2 core CPU secara ekuivalen (mengatur `cpu.max` di Cgroups).
   - `--cpu-shares=512`: Pembagian bobot prioritas CPU relatif jika terjadi persaingan (*contention*) antar-container (default: 1024).
   - `--cpuset-cpus="0,1"`: Menyematkan (*CPU pinning*) container secara eksklusif hanya pada Core 0 dan Core 1 fisik.

---

## 7. Analogy
- **Healthcheck** seperti **Dokter yang Memeriksa Pasien Koma**: Pasien mungkin masih bernapas (proses PID 1 hidup), namun dokter tetap memanggil namanya dan menyinari matanya dengan senter (**Probe test**). Jika pasien tidak merespons sama sekali, dokter menyatakan kondisi kritis (**unhealthy**).
- **Restart Policy `unless-stopped`** seperti **Lampu Kamar Mandi Cerdas**: Lampu akan otomatis menyala kembali jika listrik sempat padam lalu menyala (**Daemon reboot**). Namun jika Anda sengaja menekan tombol saklar ke posisi OFF (**Manual `docker stop`**), lampu pintar menghormati keputusan Anda dan tidak akan menyala sendiri.

---

## 8. Diagram
```
+-----------------------------------------------------------------------------------+
|                     RESTART POLICIES COMPARISON LOGIC                             |
+-----------------------------------------------------------------------------------+

 Container Exits / Server Reboots
         │
         ├──> Policy: "no" ───────────────> Tetap MATI (No Action)
         │
         ├──> Policy: "on-failure" ───────> Exit Code == 0 ? ──> MATI
         │                                  Exit Code != 0 ? ──> RESTART OTOMATIS
         │
         ├──> Policy: "always" ───────────> Selalu RESTART (Termasuk setelah host reboot)
         │
         └──> Policy: "unless-stopped" ───> Dihentikan manual via `docker stop` ?
                                              ├── Ya  ──> Tetap MATI
                                              └── Tidak -> RESTART OTOMATIS
```

---

## 9. Simple Example: Menjalankan Container dengan Healthcheck via CLI
Menjalankan container Nginx dengan polling healthcheck setiap 5 detik:

```bash
docker run -d \
  --name web-health \
  --health-cmd="curl -f http://localhost/ || exit 1" \
  --health-interval=5s \
  --health-timeout=3s \
  --health-retries=3 \
  --health-start-period=5s \
  --restart=unless-stopped \
  nginx:alpine

# Memeriksa status kesehatan container
docker ps --filter "name=web-health" --format "table {{.Names}}\t{{.Status}}"
# Output bertahap:
# web-health   Up 3 seconds (health: starting)
# web-health   Up 8 seconds (healthy)
```

---

## 10. Practical Example: Definisi Healthcheck di Dockerfile
Menuliskan instruksi langsung di dalam file `Dockerfile`:

```dockerfile
FROM node:20-alpine

WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .

EXPOSE 3000

# Healthcheck menggunakan wget bawaan Alpine (tanpa perlu install curl)
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://127.0.0.1:3000/healthz || exit 1

CMD ["node", "server.js"]
```

---

## 11. Real World Example: Mencegah Kegagalan Server Database Melalui CPU Pinning
Pada server komputasi high-frequency trading (HFT) dengan 32 Core CPU:
- **Masalah**: Container background worker analitik sering menggunakan 100% CPU di semua core secara acak, menyebabkan thread database Redis mengalami lonjakan latensi (*jitter*) dari 0.2ms ke 45ms.
- **Solusi**:
  1. DevOps mengisolasi Redis pada core berlatensi rendah menggunakan CPU Pinning:
     `docker run -d --cpuset-cpus="0,1,2,3" --memory="8g" redis:alpine`
  2. Worker analitik dibatasi secara ketat pada core terpisah:
     `docker run -d --cpuset-cpus="4-15" --cpus="8.0" worker:prod`
- **Hasil**: Redis memiliki core perangkat keras eksklusif tanpa interupsi cache CPU dari aplikasi lain, mengembalikan latensi stabil di bawah 0.3ms pada persentil $p99.9$.

---

## 12. Trade-offs

| Aspek | Tanpa Healthcheck | Menggunakan Docker Healthcheck |
|---|---|---|
| **Visibilitas Status** | Terbatas (Hanya tahu PID hidup/mati) | Akurat (Tahu aplikasi siap layani traffic) |
| **Overhead CPU** | Nol | Minimal (Menjalankan probe process setiap N detik) |
| **Integrasi Orchestrator** | Rentan mengirim request ke container zombie | Reverse proxy/K8s tahu kapan harus stop kirim traffic |
| **Kompleksitas Image** | Sederhana | Image harus memiliki tool probe (`curl`, `wget`, binary probe) |

---

## 13. When To Use
- Gunakan `restart: unless-stopped` untuk seluruh layanan produksi persisten (Web server, API, Database, Cache).
- Gunakan `restart: on-failure` untuk worker job atau database migration container (agar saat migrasi sukses exit 0, container tidak me-looping restart).
- Pasang healthcheck pada setiap service yang memiliki dependensi startup bertahap (misal menunggu koneksi DB siap).

---

## 14. When NOT To Use
- Jangan gunakan interval healthcheck terlalu agresif (misal `--interval=500ms`) karena dapat membebani CPU dan membanjiri log web server.
- Jangan gunakan `--oom-kill-disable` tanpa membatasi memori keras, karena dapat menyebabkan kernel Linux kehabisan memori total dan mematikan proses sistem kritis host.

---

## 15. Common Mistakes
1. **Probe Menjalankan Query Database Berat**: Menaruh query SQL `SELECT * FROM large_table` di dalam endpoint `/healthz`. Healthcheck yang dipanggil setiap 10 detik justru menjadi penyebab utama database overload. Endpoint healthcheck harus seringan mungkin (cek liveness socket atau return string `"OK"`).
2. **Tidak Memasang `--start-period` pada Aplikasi Java / Spring Boot**: Aplikasi Java membutuhkan waktu startup 30-60 detik. Tanpa `--start-period=60s`, Docker akan langsung menganggap probe gagal 3 kali dalam 15 detik pertama dan menandai container sebagai `unhealthy` sebelum aplikasi selesai booting.
3. **Menggunakan `restart: always` pada Script Batch Sekali Pakai**: Menjalankan script backup mingguan dengan `restart: always`. Begitu script selesai (Exit 0), Docker langsung menjalankannya kembali, menciptakan loop eksekusi tak berujung.

---

## 16. Best Practices
### Must Have
- Sertakan instruksi `HEALTHCHECK` pada setiap Dockerfile aplikasi mikroservis produksi.
- Selalu tentukan `--start-period` yang realistis sesuai durasi inisialisasi aplikasi.
- Pasang `--memory` limit pada seluruh container untuk mencegah cascading OOM.

### Recommended
- Gunakan `restart: unless-stopped` sebagai standar default production server.
- Buat endpoint `/livez` (apakah proses hidup) dan `/readyz` (apakah dependensi database siap) secara terpisah.

### Advanced
- Buat binary probe mandiri dalam bahasa Go berukuran 1MB tanpa dependensi shell untuk image distroless/scratch yang tidak memiliki `curl` atau `wget`.

---

## 17. Troubleshooting
- **Masalah**: Container berstatus `unhealthy` terus-menerus padahal aplikasi tampak berjalan normal.
  - *Diagnostik*: Jalankan `docker inspect --format='{{json .State.Health}}' <container-id> | jq .` untuk melihat output teks dari 5 probe terakhir.
  - *Solusi*: Periksa apakah port di probe salah, atau aplikasi memerlukan token autentikasi di header HTTP.
- **Masalah**: Container terus-menerus me-restart dalam status *CrashLoop* (`Restarting (1) 2 seconds ago`).
  - *Solusi*: Periksa log error startup dengan `docker logs --tail 100 <container-id>`.

---

## 18. Exercise
1. Tulis Dockerfile untuk aplikasi Node.js yang mengekspos endpoint `/health` dan konfigurasikan `HEALTHCHECK` dengan interval 10s dan timeout 2s.
2. Jalankan container dengan CPU Core Pinning pada Core 0 host dan verifikasi utilisasinya menggunakan perintah `taskset -c -p <container_pid>`.

---

## 19. Challenge
Rancang sistem failover mandiri:
- Buat container web yang secara sengaja mengubah endpoint `/healthz` dari 200 OK menjadi 500 Error setelah 30 detik beroperasi.
- Amati transisi status Docker dari `starting` -> `healthy` -> `unhealthy`.
- Buat skrip automasi pengawas (Watchdog) yang mendeteksi event `unhealthy` via `docker events` dan me-restart container secara otomatis.

---

## 20. Summary
- **Process liveness** tidak menjamin **Application health**; gunakan `HEALTHCHECK` untuk memverifikasi fungsionalitas riil.
- **Restart Policies** (`unless-stopped`, `on-failure`) memberikan kemampuan pemulihan mandiri (*self-healing*) bagi infrastruktur container.
- Batasan sumber daya Cgroups (`--memory`, `--cpus`, `--cpuset-cpus`) mencegah terjadinya fenomena *noisy neighbors* dan menjamin stabilitas server.
