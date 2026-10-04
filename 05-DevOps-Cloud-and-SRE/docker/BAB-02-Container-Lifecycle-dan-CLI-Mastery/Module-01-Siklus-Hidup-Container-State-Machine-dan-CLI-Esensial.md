# Module 01: Siklus Hidup Container, State Machine, & Command CLI Esensial

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar diharapkan mampu:
- Menguasai mesin status (**Finite State Machine / FSM**) siklus hidup container: *Created*, *Running*, *Paused*, *Stopped (Exited)*, dan *Dead*.
- Mengoperasikan perintah CLI fundamental untuk mengontrol siklus hidup: `docker run`, `create`, `start`, `stop`, `kill`, `pause`, `unpause`, dan `rm`.
- Membedakan secara presisi mekanisme penghentian proses: **Graceful Termination (`SIGTERM` / signal 15)** via `docker stop` vs **Force Kill (`SIGKILL` / signal 9)** via `docker kill`.
- Berinteraksi dengan container yang sedang berjalan menggunakan `docker exec`, `docker attach`, `docker logs`, dan `docker cp`.
- Membaca dan menganalisis **Container Exit Codes** (Exit 0, Exit 1, Exit 137, Exit 143) untuk troubleshooting cepat.

---

## 2. Prerequisite
- Memahami konsep arsitektur Docker: CLI, dockerd, containerd, runc (BAB 01 Module 01).
- Memahami konsep sinyal proses sistem operasi POSIX (`SIGTERM`, `SIGKILL`, `SIGINT`).
- Mengetahui cara navigasi direktori dan eksekusi command line.

---

## 3. Concept
Container bukanlah server statis yang selalu hidup selamanya. Container adalah entitas dinamis yang siklus hidupnya terikat secara mutlak pada **proses utama (PID 1)** yang dijalankannya. Ketika proses PID 1 di dalam container selesai atau dimatikan, container tersebut **otomatis berhenti (*exited*)**.

Siklus hidup container diatur oleh sebuah *Finite State Machine (FSM)*:
1. **Created**: Layer container telah disiapkan, namun proses PID 1 belum dijalankan.
2. **Running**: Proses PID 1 aktif berjalan dan mengonsumsi CPU/RAM.
3. **Paused**: Eksekusi proses dibekukan sementara di memori menggunakan freezer cgroup.
4. **Stopped (Exited)**: Proses PID 1 telah berhenti (baik secara normal exit 0 maupun error), namun metadata dan layer writable container masih tersimpan di disk.
5. **Dead**: Container mengalami kegagalan fatal saat proses pelepasan resource oleh kernel.

```
       CONTAINER LIFECYCLE FINITE STATE MACHINE (FSM)
                  ┌───────────────┐
                  │ docker create │
                  └───────┬───────┘
                          │
                          ▼
                   ┌─────────────┐
        ┌─────────>│   CREATED   │
        │          └──────┬──────┘
        │                 │ docker start / docker run
        │                 ▼
        │ docker   ┌─────────────┐  docker pause   ┌─────────────┐
        │ restart  │   RUNNING   │────────────────>│   PAUSED    │
        │          └──────┬──────┘<────────────────└─────────────┘
        │                 │         docker unpause
        │                 │ docker stop (SIGTERM) / docker kill (SIGKILL)
        │                 ▼
        │          ┌─────────────┐
        └──────────│   STOPPED   │
                   └──────┬──────┘
                          │ docker rm
                          ▼
                     [ DESTROYED ]
```

---

## 4. Why?
1. **Pencegahan Kehilangan Data Transaksi (*Graceful Shutdown*)**: Saat aplikasi web atau database dimatikan, ia harus menyelesaikan transaksi yang sedang berjalan, menutup koneksi database pool, dan menyimpan state ke disk. Menggunakan `docker stop` mengirimkan sinyal `SIGTERM` yang memberikan jendela waktu tenggang (default 10 detik) bagi aplikasi untuk bersih-bersih sebelum dipaksa mati.
2. **Inspeksi Non-Invasif**: Dengan `docker exec`, Anda dapat masuk ke dalam container yang sedang berjalan untuk melakukan debugging tanpa perlu me-restart container atau memasang SSH daemon.
3. **Audit dan Forensik Pasca Insiden**: Container yang berhenti (*exited*) tidak langsung lenyap dari server. Log stdout/stderr dan layer file terakhirnya tetap utuh, memungkinkan engineer melakukan otopsi error sebelum dihapus dengan `docker rm`.

---

## 5. What?
Daftar Perintah CLI Inti Berdasarkan Kategori:
- **Lifecycle Control**:
  - `docker run`: Menggabungkan `docker create` + `docker start` (opsional `-d` untuk detached/background mode).
  - `docker stop -t <seconds>`: Mengirim sinyal `SIGTERM`, menunggu timeout, lalu mengirim `SIGKILL` jika proses membandel.
  - `docker kill`: Mengirim sinyal `SIGKILL` seketika (tanpa waktu tenggang).
  - `docker pause` / `docker unpause`: Membekukan thread CPU proses tanpa mematikan koneksi memori.
  - `docker rm -f`: Menghapus metadata dan layer read-write container dari disk.
- **Debugging & Interaksi**:
  - `docker exec -it <id> sh`: Membuka sesi shell interaktif baru di dalam namespace container yang sudah berjalan.
  - `docker logs -f --tail 100 <id>`: Melakukan streaming log output `stdout` dan `stderr`.
  - `docker cp <host_path> <container_id>:<path>`: Menyalin file dua arah antara host dan container.
  - `docker top <id>`: Melihat daftar proses Linux yang sedang aktif di dalam container dari kacamata host.

---

## 6. How?
### Arti Nilai Exit Codes Standar:
- **Exit Code 0**: Container berhenti dengan sukses (*Normal Termination*).
- **Exit Code 1**: Kesalahan umum aplikasi (misal throw Exception yang tidak ditangkap di kode, salah syntax).
- **Exit Code 127**: Perintah binary tidak ditemukan di dalam filesystem image (`Command not found`).
- **Exit Code 137 (128 + 9)**: Container dihentikan paksa oleh sinyal **`SIGKILL` (Signal 9)**, baik karena dipicu oleh perintah `docker kill` atau dibunuh oleh kernel **OOM Killer**.
- **Exit Code 143 (128 + 15)**: Container dihentikan secara sopan melalui sinyal **`SIGTERM` (Signal 15)** via `docker stop`.

---

## 7. Analogy
Bayangkan **Siklus Hidup Container** seperti **Mobil Mesin Listrik Modern**:
- **`docker create`**: Mobil selesai dirakit di garasi, kunci kontak terpasang, namun mesin belum dihidupkan (**Created**).
- **`docker start` / `run`**: Anda menginjak pedal gas, mesin menyala, mobil melaju di jalan tol (**Running**).
- **`docker pause`**: Anda berhenti di lampu merah, mesin masuk ke mode *idle/standby* di mana semua posisi penumpang tetap diam di tempat (**Paused**).
- **`docker stop`**: Anda menyalakan lampu sein, menepi ke bahu jalan secara perlahan, mematikan AC dan audio, lalu memutar kunci kontak ke posisi off (**Graceful Shutdown via SIGTERM**).
- **`docker kill`**: Seseorang mendadak mencabut kabel aki mobil atau menabrakkan mobil ke dinding beton (**Instant Force Kill via SIGKILL**).

---

## 8. Diagram
```
+-----------------------------------------------------------------------------------+
|               GRACEFUL SHUTDOWN (DOCKER STOP) VS FORCE KILL                       |
+-----------------------------------------------------------------------------------+

 [ docker stop -t 10 my-app ]
             │
             ▼
 1. Daemon sends SIGTERM (Signal 15) to PID 1
             │
             ├──> [ App receives SIGTERM ]
             │      ↳ 1. Stop accepting new incoming HTTP requests
             │      ↳ 2. Finish existing inflight requests
             │      ↳ 3. Close Database connection pool
             │      ↳ 4. Process exits cleanly with Exit Code 0 or 143
             │
             ▼ (If App does NOT exit within 10 seconds timeout)
 2. Daemon sends SIGKILL (Signal 9)
             │
             ▼
      [ App immediately terminated by Kernel ] ──> Exit Code 137
```

---

## 9. Simple Example: Perintah Dasar Mengelola Siklus Hidup
Alur praktis di terminal:

```bash
# 1. Menjalankan web server Nginx di background
docker run -d --name web-prod -p 8080:80 nginx:alpine

# 2. Memeriksa status aktif
docker ps

# 3. Menjalankan perintah di dalam container tanpa SSH
docker exec -it web-prod sh -c "cat /etc/nginx/nginx.conf"

# 4. Membekukan proses sementara
docker pause web-prod

# 5. Mengaktifkan kembali proses
docker unpause web-prod

# 6. Menghentikan container dengan tenggang waktu 5 detik
docker stop -t 5 web-prod

# 7. Memeriksa container yang telah berhenti beserta exit code-nya
docker ps -a --filter "name=web-prod" --format "table {{.Names}}\t{{.Status}}\t{{.ExitCode}}"

# 8. Menghapus container
docker rm web-prod
```

---

## 10. Practical Example: Penanganan Graceful Shutdown di Kode Aplikasi
Contoh kode Node.js (`server.js`) yang menangkap sinyal `SIGTERM` dari `docker stop` untuk mencegah putusnya transaksi klien:

```javascript
const http = require('http');

const server = http.createServer((req, res) => {
  res.writeHead(200, { 'Content-Type': 'text/plain' });
  res.end('Hello from Graceful Docker Container!\n');
});

server.listen(3000, () => {
  console.log('[App] HTTP Server listening on port 3000');
});

// Menangkap sinyal shutdown dari Docker Daemon
process.on('SIGTERM', () => {
  console.log('📢 [SIGTERM Received] Starting graceful shutdown sequence...');
  server.close(() => {
    console.log('✅ [Shutdown Complete] All connections closed cleanly. Exiting.');
    process.exit(0); // Exit code 0 (Sukses)
  });

  // Fallback timeout jika ada request yang menggantung
  setTimeout(() => {
    console.error('⚠️  Forcefully shutting down due to timeout!');
    process.exit(1);
  }, 8000);
});
```

---

## 11. Real World Example: Mencegah Korupsi Database Selama Rolling Deployment
Sebuah platform e-commerce memperbarui container background worker yang memproses pencairan saldo penjual (*merchant payout*):
- **Pendekatan Buruk (`docker kill`)**: Pipeline deployment langsung membunuh container lama dengan `docker kill`. Tiga transaksi pembayaran terputus di tengah jalan: saldo merchant terpotong, namun API transfer bank belum sempat dieksekusi. Akuntan harus melakukan rekonsiliasi manual selama 2 hari.
- **Pendekatan Sempurna (`docker stop -t 30`)**: Pipeline mengirim `docker stop -t 30`. Worker berhenti mengambil antrean job baru, menyelesaikan 3 transaksi yang sedang berjalan hingga tuntas dalam 6 detik, menutup koneksi database dengan aman, dan keluar dengan Exit Code 0. Zero data loss.

---

## 12. Trade-offs

| Aspek | `docker stop` (Graceful) | `docker kill` (Force) |
|---|---|---|
| **Kecepatan Shutdown** | Memerlukan waktu (hingga timeout default 10s) | Instan (hitungan milidetik) |
| **Keamanan Data Transaksi** | Terjamin (Aplikasi sempat flush buffer disk & DB) | Sangat Berisiko (Rawan korupsi file dan split-brain) |
| **Exit Code yang Dihasilkan** | 0 (Sukses) atau 143 (Terminated by SIGTERM) | 137 (Killed by SIGKILL) |
| **Kasus Penggunaan Utama** | Rilis produksi normal, restart terjadwal | Emergency stop saat aplikasi hang / deadlocked |

---

## 13. When To Use
- Gunakan `docker exec` untuk diagnostik langsung seperti memeriksa DNS (`nslookup`), menguji endpoint internal dengan `curl`, atau mengecek konektivitas database.
- Gunakan `docker logs --tail 50 -f` untuk streaming log real-time saat melakukan rilis baru.

---

## 14. When NOT To Use
- Jangan gunakan `docker exec` untuk mengubah file source code aplikasi atau menginstall package permanent secara manual di produksi (melanggar prinsip *Immutable Infrastructure*).
- Jangan gunakan `docker attach` pada container produksi publik jika Anda tidak ingin secara tidak sengaja menghentikan container saat menekan `Ctrl+C`.

---

## 15. Common Mistakes
1. **Menggunakan `Ctrl+C` saat `docker attach`**: Menekan `Ctrl+C` di terminal attach akan mengirimkan sinyal `SIGINT` ke PID 1, yang langsung mematikan container! Gunakan urutan tombol `Ctrl+P` lalu `Ctrl+Q` untuk melepaskan (*detach*) terminal dengan aman tanpa mematikan container.
2. **PID 1 Zombie Reaping Problem**: Menjalankan aplikasi menggunakan shell script pembungkus (`CMD ["./start.sh"]` di mana script menjalankan node di background). Sinyal `SIGTERM` dari `docker stop` hanya diterima oleh script shell dan tidak pernah diteruskan ke proses node di bawahnya, menyebabkan aplikasi selalu menunggu 10 detik dan mati secara brutal via `SIGKILL`. Gunakan perintah `exec node server.js` di dalam shell script atau gunakan init system ringan seperti `tini` (`docker run --init`).

---

## 16. Best Practices
### Must Have
- Pastikan aplikasi menangani sinyal `SIGTERM` dan `SIGINT` secara eksplisit di kode sumber.
- Gunakan `--init` flag (`docker run --init`) jika aplikasi Anda membuat banyak proses anak (*child processes*) agar tidak terjadi penumpukan *zombie processes*.
- Pasang label `--name` yang deskriptif pada setiap container produksi (hindari nama acak seperti `heuristic_almeida`).

### Recommended
- Gunakan `docker system prune` secara berkala untuk membersihkan container berstatus *exited* dan volume yatim piatu.
- Atur timeout stop yang realistis sesuai beban aplikasi (`docker stop -t 30`).

### Advanced
- Gabungkan `docker stats --no-stream` dengan script monitoring bash untuk ekstraksi metrik utilisasi CPU/Memory instan tanpa overhead agent eksternal.

---

## 17. Troubleshooting
- **Masalah**: Perintah `docker stop` selalu memakan waktu tepat 10 detik sebelum container mati.
  - *Penyebab*: Aplikasi Anda tidak menangani sinyal `SIGTERM` atau aplikasi dibungkus oleh script shell tanpa `exec`, sehingga daemon terpaksa menunggu timeout 10 detik sebelum mengeksekusi `SIGKILL`.
  - *Solusi*: Tangani event `SIGTERM` di kode, atau tambahkan flag `--init` pada `docker run`.
- **Masalah**: `Error response from daemon: Conflict. The container name "/my-web" is already in use by container "...".`
  - *Solusi*: Container lama dengan nama yang sama masih ada dalam status *Stopped*. Hapus dengan `docker rm my-web` atau jalankan dengan `docker run --rm` saat pengujian.

---

## 18. Exercise
1. Tulis skrip Node.js atau Python yang menangani `SIGTERM` dengan jeda simulasi pembersihan 3 detik sebelum `process.exit(0)`. Uji dengan `docker stop` dan periksa waktu eksekusi serta exit code-nya!
2. Buat container detached berstatus Paused (`docker pause`), lalu amati dampaknya terhadap penggunaan CPU di `docker stats`!

---

## 19. Challenge
Rancang alur otomatisasi pengujian exit code:
- Buat skrip yang menjalankan 4 container simulasi:
  1. Container yang selesai sukses (Exit 0).
  2. Container yang error melempar exception (Exit 1).
  3. Container yang dimatikan via SIGKILL (Exit 137).
  4. Container yang dimatikan via SIGTERM (Exit 143).
- Skrip harus mengekstrak dan mem-parse exit code secara otomatis via Docker API/CLI dan memberikan laporan status kesehatan ke terminal.

---

## 20. Summary
- Siklus hidup container terikat langsung dengan status proses utamanya (**PID 1**).
- Status container berpindah antara **Created**, **Running**, **Paused**, dan **Stopped**.
- `docker stop` memicu *graceful shutdown* via `SIGTERM`, sedangkan `docker kill` mengeksekusi *force termination* via `SIGKILL`.
- Memahami arti exit code adalah kunci utama efisiensi penanganan insiden container.
