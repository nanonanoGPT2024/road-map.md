# Module 02: Inbound Webhooks & Event-Driven Action Triggers

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar akan mampu:
1. Memahami arsitektur *event-driven* OpenClaw melalui sistem Inbound Webhooks.
2. Mengamankan endpoint webhook menggunakan HMAC signature verification (`X-Hub-Signature-256`) dan shared secret token.
3. Mengonversi payload eksternal (GitHub PR/Issues, Stripe Payment, Grafana/Prometheus alert) menjadi structured event context yang dapat diproses oleh AI agent.
4. Merancang alur otomatisasi *event-to-action*: webhook masuk -> evaluasi reasoning model -> trigger tool/skill -> kirim respons/notifikasi ke kanal chat.

---

## 2. Prerequisite
- Memahami konsep dasar HTTP POST request, payload format JSON, dan HTTP Status Codes.
- Menguasai dasar kriptografi hashing (HMAC-SHA256).
- Telah menyelesaikan [BAB 06 Module 01](file:///d:/explore/roadmap.sh%20materi/OpenClaw/BAB-06-Automasi-Proaktif-Cron-Webhooks/Module-01-Proactive-Heartbeats-dan-Scheduled-Cron-Jobs.md) mengenai otomasi proaktif OpenClaw.

---

## 3. Concept
Secara default, agen percakapan bersifat pasif: menunggu user mengetik pesan di Telegram atau Discord. Namun, dalam lingkungan operasional modern, banyak kejadian kritis yang terjadi di luar aplikasi chat—misalnya:
- Repository GitHub menerima commit atau Pull Request baru.
- Layanan Stripe berhasil menerima pembayaran transaksi atau mengalami *chargeback*.
- Alerting engine (Datadog/Grafana) mendeteksi lonjakan error 5xx pada microservice.

**Inbound Webhooks** mengubah OpenClaw menjadi agen *event-driven real-time*. OpenClaw membuka HTTP listener mini di port lokal (atau melalui tunnel aman). Ketika sistem eksternal mengirim HTTP POST request berisi event payload, OpenClaw memvalidasi signature-nya, mem-parsing datanya, menginstruksikan model AI untuk menganalisis dampaknya, dan jika perlu mengambil tindakan otomatis (seperti merangkum PR, mengeksekusi script perbaikan, atau menyapa user di Telegram).

---

## 4. Why?
Mengapa agen personal membutuhkan Inbound Webhook listener?
1. **Zero Latency**: Daripada melakukan polling berulang kali (setiap 1 menit) yang membuang bandwidth dan kuota rate-limit API eksternal, webhook memberikan notifikasi secara instan (push-based) begitu event terjadi.
2. **Konteks Otonom**: Agent dapat bertindak sebagai *Autonomous Incident Responder*—ketika ada server crash alert via webhook, agent langsung mengecek log VPS dan melaporkan ringkasan diagnosa ke WhatsApp developer.
3. **Sentralisasi Notifikasi Cerdas**: Mengurangi *notification fatigue*. Alih-alih ratusan spam email notifikasi dari GitHub/Stripe, OpenClaw memfilter dan hanya meneruskan alert relevan berdasar preferensi user.

---

## 5. What?
Komponen arsitektur Inbound Webhooks pada OpenClaw:
- **Webhook Listener Gateway**: HTTP Server ringan yang menangani endpoint `/api/v1/webhooks/:source` (misal `/api/v1/webhooks/github`).
- **Signature Authenticator**: Middleware yang memverifikasi keaslian pengirim menggunakan Shared Secret & HMAC header.
- **Event Parser & Normalizer**: Mengonversi JSON payload dari berbagai platform yang beraneka ragam ke dalam format standar `AgentEventPayload`.
- **Trigger Router & Filter**: Meneruskan event ke agent runner atau langsung memicu skill tertentu berdasar rule/metadata.

---

## 6. How?
Alur kerja pemrosesan event webhook pada OpenClaw:

```text
[ Sistem Eksternal ] (GitHub, Stripe, Sentry)
         │
         │ HTTP POST /api/v1/webhooks/github
         │ Header: X-Hub-Signature-256: sha256=abcdef...
         ▼
[ Webhook Inbound Listener ]
         │
         ├── 1. Validasi Header & HMAC Secret
         │      (Jika tidak valid -> 401 Unauthorized)
         │
         ├── 2. Normalisasi Payload (JSON Parser)
         │
         ▼
[ Event Router / Trigger Pipeline ]
         │
         ├── 3. Apakah event butuh reasoning AI?
         │      ├─ Tidak: Langsung eksekusi tindakan deterministik
         │      └─ Ya: Inject prompt kontekstual ke LLM
         │
         ▼
[ LLM Reasoning & Action Execution ]
         │
         ├── Menjalankan Skill (misal: review PR code via GitHub API)
         └── Mengirimkan pesan proaktif ke user (Telegram/Discord)
```

---

## 7. Analogy
Bayangkan **Inbound Webhook** seperti **Bel Pintu Rumah Pintar dengan Kamera & Barcode Scanner**.
- Tanpa webhook (polling): Anda harus berjalan ke pintu depan setiap 30 detik untuk memeriksa apakah ada paket di teras (melelahkan dan boros waktu).
- Dengan webhook: Kurir kurir ekspedisi (GitHub/Stripe) cukup memencet bel pintu dan menempelkan barcode paket. Bel berbunyi seketika, asisten rumah pintar (OpenClaw) memverifikasi segel kurir (HMAC signature), menerima paket, membukanya, dan membawakan laporannya ke ruang kerja Anda.

---

## 8. Diagram
```text
+-------------------+      HTTP POST Event       +------------------------------------+
|   GitHub / CI     | ------------------------> | OpenClaw Inbound Server (:18789)   |
+-------------------+                           +------------------------------------+
                                                                  |
                                                                  v
                                                        [ HMAC Signature Check ]
                                                                  |
                                                           Valid? +-- [No] --> Reject (401)
                                                                  |
                                                                [Yes]
                                                                  v
                                                        [ Event Normalizer ]
                                                                  |
                                                                  v
+-------------------+      Prompt & Event JSON        +------------------------------------+
|  User di Telegram | <------------------------------ | LLM Decision Engine                |
|  "PR #12 Diterima |     Proactive Notification      | Prompt: "Analisis dampak PR #12..."|
|  & Di-review!"    |                                 +------------------------------------+
+-------------------+
```

---

## 9. Simple Example
Contoh konfigurasi webhook listener pada `openclaw.json`:

```json
{
  "webhooks": {
    "enabled": true,
    "port": 18789,
    "pathPrefix": "/webhooks",
    "endpoints": [
      {
        "id": "github-events",
        "path": "/github",
        "secret": "env:GITHUB_WEBHOOK_SECRET",
        "signatureHeader": "x-hub-signature-256",
        "action": "trigger_agent_workflow",
        "systemPrompt": "Kamu menerima webhook GitHub. Berikan ringkasan aksi commit/PR dan jika ada isu breaking changes, laporkan segera ke Telegram channel #alerts."
      }
    ]
  }
}
```

---

## 10. Practical Example
Verifikasi HMAC SHA-256 pada payload Inbound Webhook (Node.js Vanilla):

```javascript
const crypto = require('crypto');

function verifyWebhookSignature(payloadString, signatureHeader, secret) {
  if (!signatureHeader) return false;
  
  // Format header GitHub: "sha256=<hex_hash>"
  const [algorithm, hash] = signatureHeader.split('=');
  if (algorithm !== 'sha256' || !hash) return false;

  const expectedHash = crypto
    .createHmac('sha256', secret)
    .update(payloadString, 'utf8')
    .digest('hex');

  // Gunakan timingSafeEqual untuk mencegah timing attack
  return crypto.timingSafeEqual(
    Buffer.from(hash, 'utf8'),
    Buffer.from(expectedHash, 'utf8')
  );
}
```

---

## 11. Real World Example
### Kasus: Sentry Crash Alert ke Telegram Otomatis dengan Analisis AI
1. Backend production crash dengan uncaught exception di microservice transaksi.
2. Sentry memicu Webhook ke OpenClaw: `POST /webhooks/sentry` berisi stack trace error.
3. OpenClaw memvalidasi secret Sentry.
4. OpenClaw memicu LLM: *"Analisis stack trace ini, cari file yang bermasalah, dan berikan estimasi root cause."*
5. OpenClaw mengirimkan pesan terformat ke Telegram Engineering Lead:
   > 🚨 **Critical Bug Alert (Prod)**
   > **Service**: `payment-service`
   > **Error**: `NullReferenceException at CheckoutController.js:142`
   > **Analisis AI**: Variabel `customer.billingAddress` bernilai null ketika user checkout via Apple Pay.
   > **Saran**: Tambahkan optional chaining `customer?.billingAddress?.zipCode`.

---

## 12. Trade-offs
| Aspek | Polling (Interval Fetch) | Inbound Webhook (Push) |
|---|---|---|
| **Latency** | Tertunda sesuai interval polling (1-5 menit) | Real-time (< 500 ms) |
| **Beban Jaringan / CPU** | Tinggi karena ribuan request kosong (no changes) | Nol saat idle, aktif hanya saat ada event |
| **Aksesibilitas Jaringan** | Sangat mudah (hanya butuh outbound internet) | Memerlukan public IP / reverse proxy / tunnel (Cloudflare, Ngrok, Tailscale) |
| **Keamanan** | Aman dari serangan inbound | Harus memproteksi port terbuka & validasi autentikasi |

---

## 13. When To Use
- Integrasi CI/CD (GitHub Actions, GitLab CI, Vercel deployments).
- Pemrosesan event keuangan (Stripe, Midtrans, PayPal webhooks).
- Alert monitoring server & uptime (Prometheus Alertmanager, Datadog, Uptime Kuma).
- Smart Home triggers (Home Assistant automation webhook).

---

## 14. When NOT To Use
- Jika agent OpenClaw di-host di laptop pribadi tanpa koneksi internet statis atau tanpa tunnel publik yang stabil.
- Untuk alur data streaming berkecepatan ribuan event per detik (gunakan Kafka / RabbitMQ consumer daripada HTTP webhook).

---

## 15. Common Mistakes
1. **Tidak Melakukan Signature Verification**: Menerima HTTP POST langsung tanpa memverifikasi signature header. Siapa pun di internet yang mengetahui URL webhook Anda dapat mengirim payload palsu.
2. **Parsing Body Terlebih Dahulu Sebelum Verifikasi HMAC**: HMAC harus dihitung dari **raw body string**, bukan dari objek JSON yang sudah di-`JSON.parse()` dan di-`JSON.stringify()` ulang karena urutan key dapat berubah.
3. **Blocking Response ke Provider**: Memproses LLM selama 15 detik sebelum merespons HTTP request. Provider webhook (seperti Stripe atau GitHub) akan menganggap timeout (> 10s) dan melakukan retry berkali-kali. **Aturan baku**: Segera kembalikan HTTP `200/202 Accepted`, lalu proses event secara asinkron di latar belakang.

---

## 16. Best Practices
### Must Have
- Selalu kembalikan respon HTTP `200 OK` atau `202 Accepted` dalam waktu < 2 detik.
- Validasi HMAC signature menggunakan `crypto.timingSafeEqual()`.
- Catat audit log untuk setiap payload webhook yang masuk (disimpan di folder log).

### Recommended
- Buat idempotency store menggunakan UUID atau Event ID agar payload retry tidak diproses ganda.
- Gunakan Cloudflare Tunnel atau Tailscale Funnel untuk mengekspos port webhook lokal ke publik tanpa harus membuka port router (port forwarding).

### Avoid / Overengineering
- Jangan mengirimkan seluruh raw payload JSON berukuran 50KB ke LLM prompt. Ekstrak hanya field esensial (event type, sender, title, message) untuk menghemat token dan biaya.

---

## 17. Troubleshooting
| Gejala | Kemungkinan Penyebab | Solusi |
|---|---|---|
| Webhook selalu mengembalikan HTTP `401 Invalid Signature` | Secret tidak cocok atau HMAC dihitung setelah body di-parse | Pastikan raw buffer string digunakan saat hashing, bukan `JSON.stringify(req.body)` |
| Provider (GitHub/Stripe) mendeteksi Webhook Failure (Red Flag) | OpenClaw membutuhkan waktu lama untuk menjalankan LLM | Pisahkan endpoint listener: kirim `res.writeHead(202).end()` di awal, lalu trigger reasoning async |
| URL webhook tidak dapat diakses oleh server eksternal | IP lokal (192.168.x.x atau 127.0.0.1) belum diekspos | Gunakan tunnel tool seperti `cloudflared` atau `ngrok` |

---

## 18. Exercise
1. Buat webhook listener mini yang mendengarkan event `git:push`.
2. Validasi token secret yang dikirim melalui header `X-Auth-Token`.
3. Jika token valid, ekstrak nama author commit dan daftar file yang diubah.

---

## 19. Challenge
Implementasikan mekanisme **Idempotency Deduplication**:
- Jika provider mengirim ulang webhook yang sama (misal network glitch menghasilkan 2x request dengan Event ID sama dalam 10 detik), pastikan LLM dan notifikasi chat hanya dipicu tepat satu kali.

---

## 20. Summary
- Inbound Webhooks mengubah OpenClaw dari agen reaktif menjadi agen operasional *event-driven* yang proaktif.
- Keamanan webhook wajib dijaga dengan HMAC-SHA256 signature verification atas *raw payload*.
- Eksekusi LLM harus dijalankan secara asinkron setelah HTTP acknowledgment `200/202` dikembalikan ke provider pengirim.
- Modul praktikum lab dapat dijalankan langsung di [hands-on/m02/inbound_webhook_trigger.js](file:///d:/explore/roadmap.sh%20materi/OpenClaw/BAB-06-Automasi-Proaktif-Cron-Webhooks/hands-on/m02/inbound_webhook_trigger.js).
