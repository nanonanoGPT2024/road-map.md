# BAB 08: Quiz, Challenge, & Knowledge Check
**Multi-Agent Orchestration & Deployment 24/7**

---

## 1. Basic Questions (5 Soal)
1. Apa keuntungan utama menggunakan pola arsitektur *Orchestrator-Worker* dibandingkan menjalankan satu agen monolitik besar?
2. Mengapa menjalankan agent di laptop pribadi kurang ideal untuk asisten otonom dibandingkan menaruhnya di VPS Linux 24/7?
3. Apa fungsi direktif `Restart=always` pada service definition Systemd (`openclaw.service`)?
4. Mengapa kita tidak disarankan mengekspos port dashboard OpenClaw (`18789`) secara publik ke `0.0.0.0` di server VPS?
5. Bagaimana Tailscale VPN mengamankan akses ke server OpenClaw tanpa memerlukan port forwarding pada router atau firewall VPS?

---

## 2. Intermediate Questions (5 Soal)
6. Bagaimana cara mencegah fenomena *infinite recursion loop* ketika subagent diberikan izin untuk memanggil subagent lain?
7. Mengapa subagent spesialis sebaiknya menggunakan model AI yang lebih kecil (seperti Claude 3.5 Haiku atau GPT-4o-mini) sementara Orchestrator menggunakan model penalaran tingkat tinggi?
8. Mengapa rotasi file log (`max-size` dan `max-file` pada Docker / `logrotate` pada Linux) sangat penting pada server 24/7 dengan kapasitas disk terbatas?
9. Apa perbedaan mendasar antara mengeksekusi subagent secara sekuensial (serial) vs secara konkruen menggunakan `Promise.all()`?
10. Bagaimana strategi penanganan *Out-of-Memory* (OOM) pada VPS berspesifikasi rendah (RAM 1GB) saat beberapa subagent berjalan bersamaan?

---

## 3. Scenario-Based Questions (3 Soal)

### Skenario A: The Cascading Timeout Crash
Sebuah Orchestrator memanggil 4 subagent riset secara paralel dengan total waktu tunggu 60 detik. Salah satu subagent macet (*hang*) karena website target memblokir scraping IP. Hal ini menyebabkan request Orchestrator secara keseluruhan timeout dan pengguna Telegram menerima pesan error.
- *Pertanyaan:* Bagaimana pola *circuit breaker* atau *individual subagent timeout with fallback* dapat diimplementasikan agar Orchestrator tetap bisa menghasilkan laporan dengan 3 subagent yang berhasil?

### Skenario B: The Runaway Log Disk Full
Setelah berjalan selama 3 bulan tanpa masalah, bot OpenClaw di VPS mendadak mati. Saat dicek via SSH, perintah `df -h` menunjukkan root disk `/dev/vda1` 100% penuh. Database SQLite korup karena tidak bisa menulis data baru.
- *Pertanyaan:* Langkah-langkah hardening dan konfigurasi apa yang harus diterapkan pada Docker daemon dan Systemd journal untuk memastikan insiden ini tidak terulang kembali?

### Skenario C: Multi-Device WhatsApp Disconnect
Bot WhatsApp OpenClaw Anda di VPS sering mengalami disconnect setiap seminggu sekali dan meminta scan ulang QR Code.
- *Pertanyaan:* Pengaturan persistensi volume Docker apa yang kurang tepat, dan bagaimana cara menjaga session folder Baileys tetap persisten saat container di-restart?

---

## 4. Chapter Challenge
**Tantangan Praktis: The 24/7 Resilient Multi-Agent Pod**
Bangun demonstrasi sistem multi-agent tahan banting:
1. Buat **Orchestrator** yang menerima instruksi analisis pasar.
2. Spawn 2 subagent independen: `NewsWorker` (mencari berita terkini) dan `SentimentWorker` (menganalisis sentimen positif/negatif).
3. Jalankan kedua worker secara konkruen dengan batas timeout individu 3 detik.
4. Gabungkan kedua output menjadi pesan ringkas untuk user.
5. Pantau status proses: jika salah satu worker melempar error / exception, supervisor harus mampu mengembalikan status degradasi parsial tanpa menumbangkan seluruh proses Orchestrator.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Pola pembagian tugas Orchestrator dan Specialized Subagents.
- [ ] Pencegahan context window pollution melalui memori worker terisolasi.
- [ ] Arsitektur supervisor 24/7 menggunakan Systemd atau Docker Compose.
- [ ] Pengamanan akses remote menggunakan Tailscale private mesh network.

### Saya tidak perlu menghafal:
- [ ] Seluruh parameter kernel Linux cgroup v2.
- [ ] Sintaks puluhan opsi konfigurasi systemd yang jarang dipakai.

### Saya harus bisa melakukan:
- [ ] Menulis definisi subagent dengan batasan toolset spesifik.
- [ ] Menjalankan eksekusi delegasi subagent secara paralel di Node.js.
- [ ] Menulis konfigurasi `openclaw.service` dan `docker-compose.yml` yang aman dengan batas memori dan rotasi log.

---
*Ketik **LANJUT** untuk berpindah ke Capstone Project Akhir: Autonomous 24/7 Personal Operations Agent.*
