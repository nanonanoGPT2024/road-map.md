# BAB 02 — Quiz, Challenge, & Knowledge Check: Container Lifecycle & CLI Mastery

## A. Quiz Evaluasi Pemahaman

### Bagian 1: Soal Tingkat Dasar (Basic)
1. Jelaskan perbedaan mendasar antara `docker stop` dan `docker kill` terkait sinyal proses yang dikirimkan ke aplikasi!
2. Mengapa menekan `Ctrl+C` saat sesi `docker attach` berbahaya bagi container produksi, dan kombinasi tombol apa yang seharusnya digunakan untuk keluar dengan aman?
3. Sebutkan 3 status kesehatan yang dapat dimiliki oleh sebuah container yang dilengkapi dengan instruksi `HEALTHCHECK`!
4. Apa perbedaan perilaku antara restart policy `always` dan `unless-stopped` saat server fisik atau daemon Docker mengalami reboot?
5. Apa arti dari **Exit Code 0** dan **Exit Code 143**?

### Bagian 2: Soal Tingkat Menengah (Intermediate)
6. Jelaskan apa yang dimaksud dengan kondisi *Zombie State* di mana proses PID 1 container masih berstatus `Up / Running`, namun aplikasi sebenarnya sudah mati atau tidak bisa merespons traffic pengguna!
7. Mengapa parameter `--start-period` sangat krusial saat mengonfigurasi healthcheck pada aplikasi yang memiliki waktu bootstrap lama seperti Java / JVM / Spring Boot?
8. Bagaimana restart policy `on-failure` mencegah perulangan tak terbatas (*infinite loop*) saat menjalankan script database migration atau batch processing?
9. Apa perbedaan antara pembatasan memori keras (`--memory`) dan pembatasan memori lunak (`--memory-reservation`)?
10. Bagaimana cara kerja CPU core pinning (`--cpuset-cpus="0,1"`) dalam mencegah latensi tidak terduga (*jitter*) pada aplikasi database seperti Redis?

### Bagian 3: Pertanyaan Skenario Nyata (Scenario-Based)
11. **Skenario 1**: Sebuah container payment gateway membutuhkan waktu 8 detik untuk menyelesaikan transaksi kredit yang sedang berjalan saat menerima perintah shutdown. Namun, setiap kali di-deploy ulang dengan `docker stop`, transaksi klien selalu gagal di tengah jalan. Apa penyebabnya dan flag apa yang harus ditambahkan pada perintah stop?
12. **Skenario 2**: Anda menjalankan container dengan perintah `docker run -d --restart=always my-script.sh`. Script tersebut bertugas mem-backup database lalu keluar dengan Exit Code 0. Namun, server mengalami lonjakan CPU tinggi dan ratusan file backup duplikat tercipta setiap menit. Mengapa hal ini terjadi dan bagaimana memperbaikinya?
13. **Skenario 3**: Sebuah microservice mengalami deadlock pada thread pool koneksi database. Proses node tetap hidup, sehingga Docker menganggap container berstatus `Up 3 days`. Reverse proxy Nginx terus meneruskan traffic ke container tersebut dan menghasilkan ratusan pesan HTTP 504 Gateway Timeout bagi pengguna. Rancang solusi healthcheck deklaratif untuk mendeteksi dan memulihkan kondisi ini secara otomatis!

---

## B. Practical Chapter Challenge: High-Availability Self-Healing Web Container

### Deskripsi Skenario
Rancang perintah eksekusi container mandiri yang kebal terhadap reboot server, mampu mendeteksi kegagalan aplikasi secara internal, dan memiliki alokasi sumber daya terisolasi.

### Persyaratan Implementasi:
1. **Container Naming & Detachment**:
   - Jalankan container web berbasis `nginx:alpine` di background dengan nama `production-edge-web`.
2. **Healthcheck Configuration**:
   - Uji endpoint HTTP `http://127.0.0.1/` setiap 10 detik.
   - Waktu timeout probe maksimal 3 detik.
   - Waktu tenggang inisialisasi awal (`start-period`) selama 5 detik.
   - Ambang batas kegagalan maksimal 3 kali sebelum berstatus `unhealthy`.
3. **Restart Policy**:
   - Pastikan container selalu aktif kembali saat reboot server, kecuali jika secara sengaja dihentikan oleh administrator.
4. **Resource Bounds**:
   - Batasi penggunaan memori maksimal 128MB.
   - Batasi kuota CPU maksimal 0.5 core.

---

## C. Knowledge Check & Mastery Checklist

### Saya Harus Memahami:
- [ ] 5 State Machine siklus hidup container (Created, Running, Paused, Stopped, Dead).
- [ ] Perbedaan sinyal POSIX: `SIGTERM` (15) vs `SIGKILL` (9).
- [ ] Logika restart policies (`no`, `always`, `unless-stopped`, `on-failure`).
- [ ] Parameter instruksi Healthcheck: `interval`, `timeout`, `start-period`, `retries`.
- [ ] Flag pembatasan cgroup di CLI (`--memory`, `--cpus`, `--cpuset-cpus`).

### Saya Tidak Perlu Menghafal:
- [ ] Seluruh nomor sinyal Linux dari 1 hingga 64 (cukup kuasai 9, 15, dan 2).
- [ ] Seluruh puluhan parameter opsional pada `docker inspect`.

### Saya Harus Bisa Melakukan:
- [ ] Menghentikan container secara elegan menggunakan `docker stop -t <seconds>`.
- [ ] Melakukan streaming log interaktif menggunakan `docker logs -f --tail`.
- [ ] Menulis instruksi `HEALTHCHECK` di Dockerfile dan memvalidasi transisi statusnya di `docker ps`.
- [ ] Melakukan troubleshooting exit codes container (0, 1, 137, 143).

```text
Checklist Kesiapan BAB 02:
[ ] Memahami state machine container & signals
[ ] Menjalankan hands-on lifecycle FSM m01
[ ] Menjalankan hands-on healthcheck & restart policy m02
[ ] Mampu menjawab seluruh pertanyaan Quiz dan Skenario
```
