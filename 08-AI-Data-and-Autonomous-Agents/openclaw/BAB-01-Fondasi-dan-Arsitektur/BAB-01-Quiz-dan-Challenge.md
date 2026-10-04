# BAB 01 — Evaluasi, Quiz, & Chapter Challenge
## Fondasi & Arsitektur OpenClaw

---

## 🎯 Ringkasan Bab

Dalam Bab pembuka ini, kita telah meletakkan fondasi arsitektur dan operasional agen AI otonom:
1. **Arsitektur Gateway Daemon**: Memahami bagaimana OpenClaw menjembatani dunia nyata (Telegram, WhatsApp, Discord, Slack) dengan model AI sebagai proses latar belakang (*always-on 24/7 background service*), berbeda dari asisten reaktif biasa.
2. **Setup, Onboarding, & Diagnostik Mandiri**: Menginstal CLI, mengelola struktur direktori `~/.openclaw/`, menerapkan prinsip *Least Privilege* pada permission berkas konfigurasi, serta menjalankan audit kesehatan menyeluruh via `openclaw doctor --deep`.

---

## 🧠 Knowledge Check

### Saya Harus Memahami:
- [ ] Perbedaan fundamental antara agen reaktif (CLI/browser satu arah) dan agen otonom proaktif (daemon yang merespons event dan waktu).
- [ ] Arsitektur Model-Agnostic: mengapa gateway OpenClaw dapat berganti provider AI (Claude, OpenAI, Gemini, Ollama) tanpa mengubah kode integrasi perpesanan.
- [ ] Bahaya keamanan fatal jika `ownerChatId` tidak dikonfigurasi (bot dapat dikendalikan siapa saja di internet).
- [ ] Mengapa permission berkas konfigurasi rahasia harus disetel ke `0600` pada lingkungan Linux/Unix.
- [ ] Peran perintah `openclaw doctor --deep` dalam memvalidasi network handshake ke Telegram dan provider API sebelum daemon dijalankan.

### Saya Tidak Perlu Menghafal:
- Seluruh daftar argumen flag baris perintah CLI tingkat rendah.
- Struktur biner internal dari SQLite file header.

### Saya Harus Bisa Melakukan:
- [ ] Menjalankan inisialisasi dan konfigurasi workspace OpenClaw dari terminal.
- [ ] Mendiagnosis penyebab error daemon tidak merespons menggunakan alat `doctor`.
- [ ] Mengatur whitelist ID pengguna untuk mengamankan gateway pribadi.

---

## ❓ Quiz Evaluasi

### Bagian A: Pertanyaan Konseptual Fundamental (5 Soal)
1. **Apa perbedaan utama antara OpenClaw dan alat AI coding seperti Claude Code dalam hal siklus hidup proses (lifecycle)?**
2. **Mengapa OpenClaw disebut sebagai sistem yang "Model-Agnostic"?**
3. **Apa yang dilakukan oleh perintah `openclaw init` saat pertama kali dijalankan di komputer baru?**
4. **Apa fungsi utama dari parameter `ownerChatId` di berkas konfigurasi OpenClaw?**
5. **Mengapa perintah `openclaw doctor --deep` menguji koneksi jaringan ke endpoint provider AI selain hanya memeriksa file lokal?**

### Bagian B: Analisis & Intermediate (5 Soal)
6. **Jika Anda menjalankan dua instance daemon OpenClaw secara bersamaan dengan token bot Telegram yang sama, error apa yang akan terjadi dan mengapa?**
7. **Mengapa menyimpan API Key langsung di dalam file `config.json` dianggap sebagai anti-pattern berbahaya jika proyek tersebut dibagikan ke Git?**
8. **Jelaskan trade-off antara menjalankan OpenClaw di foreground terminal lokal versus sebagai systemd background service di server VPS.**
9. **Bagaimana arsitektur OpenClaw memisahkan Channel Adapter (Telegram/Discord) dari Skill Execution Sandbox? Apa keuntungan pemisahan ini?**
10. **Jika `openclaw doctor` memberikan status `WARN` pada koneksi ke Ollama port 11434, apakah daemon tetap bisa dijalankan jika model utama Anda adalah Google Gemini? Jelaskan.**

### Bagian C: Scenario-Based System Architecture (3 Soal)
11. **Skenario 1: Bot Publik yang Mengancam Keamanan Server**  
   Seorang developer pemula menghubungkan bot Telegram ke OpenClaw tanpa menyetel whitelist `ownerChatId`, dan mengaktifkan skill shell execution tanpa konfirmasi.
   - Serangan apa yang bisa dilakukan oleh pengguna Telegram acak yang menemukan username bot tersebut?
   - Langkah mitigasi apa yang wajib diterapkan di layer gateway untuk menutup celah ini?

12. **Skenario 2: Asisten Pribadi Hybrid (Hemat Biaya & Privasi Tinggi)**  
   Anda ingin asisten OpenClaw Anda memproses chat santai dan ringkasan berita menggunakan model cloud super murah (Gemini Flash), tetapi dokumen pajak dan transaksi bank wajib diproses oleh LLM lokal offline (Llama 3 via Ollama).
   - Rancang aturan model routing di konfigurasi OpenClaw untuk mendukung skenario ini.

13. **Skenario 3: Daemon Monitoring & Automated Self-Healing**  
   OpenClaw berjalan di server VPS mandiri untuk memantau status website Anda 24/7.
   - Bagaimana Anda mengonfigurasi systemd service dan script healthcheck berkala agar daemon otomatis hidup kembali jika terjadi pemadaman listrik sesaat atau server restart?

---

## 🏆 Chapter Challenge: Automated Gateway Health Watchdog

### Problem Statement
Buat script utilitas otomatis (dapat ditulis dalam Bash atau Node.js) bernama `openclaw-watchdog` yang bertugas:
1. Memeriksa apakah proses daemon OpenClaw sedang aktif berjalan di background.
2. Jika daemon mati, secara otomatis me-restart daemon dan mencatat waktu insiden ke log.
3. Menjalankan pengujian `doctor` ringan setiap 1 jam.
4. Jika koneksi ke Telegram terputus selama 3 kali pengecekan berturut-turut, kirimkan notifikasi email darurat ke pemilik server.
