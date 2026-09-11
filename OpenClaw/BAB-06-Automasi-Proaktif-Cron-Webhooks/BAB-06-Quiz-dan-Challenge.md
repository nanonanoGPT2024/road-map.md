# BAB 06: Quiz, Challenge, & Knowledge Check
**Automasi Proaktif: Heartbeats, Scheduled Cron, & Inbound Webhooks**

---

## 1. Basic Questions (5 Soal)
1. Apa perbedaan mendasar antara model kerja agen *reaktif* (chat-driven) dan model kerja agen *proaktif* (heartbeat/cron-driven)?
2. Mengapa file `HEARTBEAT.md` atau state periodic check pada OpenClaw penting untuk menjaga persistensi interval pemeriksaan?
3. Pada sintaks cron standar UNIX 5-field (`* * * * *`), apakah arti dari ekspresi `0 8 * * 1-5`?
4. Apa fungsi dari header `X-Hub-Signature-256` pada pengiriman Inbound Webhook dari platform seperti GitHub?
5. Mengapa server webhook listener disarankan mengembalikan status HTTP `200` atau `202 Accepted` sesegera mungkin daripada menunggu LLM selesai berpikir?

---

## 2. Intermediate Questions (5 Soal)
6. Bagaimana cara mencegah fenomena *notification fatigue* (kebanjiran notifikasi) ketika periodic heartbeat mendeteksi server sedang down selama 30 menit berturut-turut?
7. Mengapa verifikasi HMAC-SHA256 harus dilakukan pada *raw string body* HTTP request dan bukan pada `JSON.stringify(req.body)` yang telah di-parse?
8. Bagaimana strategi penanganan *idempotency* untuk menangani kondisi di mana provider webhook (misal Stripe) mengirim ulang payload yang sama akibat jaringan lambat (*network retry*)?
9. Jika agen OpenClaw di-host di server lokal/rumah tanpa IP publik statis, sebutkan minimal 2 metode tunneling aman agar webhook dari internet dapat masuk ke port lokal agent.
10. Bagaimana cara mendesain prompt LLM agar model hanya mengirim notifikasi proaktif jika ada kondisi darurat, dan tetap diam (*no-op*) jika semua metrik normal?

---

## 3. Scenario-Based Questions (3 Soal)

### Skenario A: The Infinite Loop Incident
Anda mengatur heartbeat task setiap 60 detik untuk memeriksa inbox email. Setiap kali ada email baru, agent membalas email dan mengirim konfirmasi ke Telegram Anda. Suatu hari, sistem email auto-responder dari vendor membalas balasan agent Anda, memicu siklus tak berujung (*infinite loop ping-pong*) hingga menghabiskan 2 juta token LLM dalam satu jam.
- *Pertanyaan:* Arsitektur proteksi dan guardrail apa yang harus diterapkan pada event listener email untuk menghentikan siklus ini?

### Skenario B: Delayed Webhook vs Execution Timeout
GitHub Webhook dikonfigurasi untuk memicu analisa security audit pada PR baru. Model LLM membutuhkan waktu 25 detik untuk membaca seluruh diff code. Namun, GitHub menandai webhook sebagai *Failed / Timeout* karena timeout maksimal GitHub adalah 10 detik.
- *Pertanyaan:* Bagaimana cara Anda merefaktor arsitektur webhook handler OpenClaw agar GitHub menerima sinyal sukses secara instan, sementara proses audit AI tetap berjalan di latar belakang hingga selesai?

### Skenario C: False Alarm Spike
Sebuah heartbeat checker mengamati penggunaan CPU VPS. Setiap kali CPU > 85%, agen mengirim pesan panik ke Telegram CIO. Ternyata, setiap jam 00:00 ada scheduled backup database yang membuat CPU melonjak ke 90% selama 4 menit, menyebabkan CIO terbangun tengah malam karena false alarm.
- *Pertanyaan:* Bagaimana rancangan evaluasi threshold CPU yang lebih cerdas (misal: time-window sliding atau anomaly suppression) untuk mengatasi false positive tersebut?

---

## 4. Chapter Challenge
**Tantangan Praktis: Autonomous GitHub PR Sentinel**
1. Bangun alur kerja terintegrasi:
   - Webhook server menerima payload PR baru dari GitHub.
   - Verifikasi signature HMAC-SHA256 menggunakan secret key lokal.
   - Ekstrak judul PR dan diff modifikasi file.
   - Kirimkan instruksi ke model untuk membuat *Executive Summary* 3 butir poin mengenai dampak perubahan kode tersebut.
   - Kirimkan ringkasan hasil review ke webhook simulator bot Telegram atau console output dengan format rapi.
   - Pastikan terdapat deduplikasi idempotency sehingga PR update yang sama tidak memicu review berulang.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Konsep kerja daemon proaktif berbasis heartbeat cycle dan scheduled cron.
- [ ] Kriptografi HMAC-SHA256 dan pentingnya timing-safe comparison dalam autentikasi webhook.
- [ ] Alur asinkron: Acknowledge HTTP request segera (`202 Accepted`) lalu eksekusi LLM di background.
- [ ] Teknik mitigasi idempotency deduplication dan pencegahan spam notifikasi.

### Saya tidak perlu menghafal:
- [ ] Detail algoritma matematika internal SHA-256 (cukup manfaatkan library standar `crypto`).
- [ ] Seluruh format spesifikasi JSON webhook ribuan platform pihak ketiga (cukup petakan payload field esensial).

### Saya harus bisa melakukan:
- [ ] Membuat cron job terjadwal pada OpenClaw untuk rutinitas harian (morning briefing).
- [ ] Membuka inbound HTTP listener mini yang aman dengan HMAC validation.
- [ ] Menguji alur event webhook menggunakan script cURL atau script testing simulasi.

---
*Ketik **LANJUT** untuk berpindah ke BAB 07: Keamanan, Sandboxing, & Mitigasi Risiko.*
