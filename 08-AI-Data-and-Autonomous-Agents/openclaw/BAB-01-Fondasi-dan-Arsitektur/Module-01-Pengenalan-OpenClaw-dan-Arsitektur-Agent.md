# Module 01: Pengenalan OpenClaw, Konsep Gateway Daemon, & Model-Agnostic Agent

## 1. Learning Objective
Setelah menyelesaikan modul ini, Anda akan mampu:
- Memahami konsep dasar dan filosofi arsitektur **OpenClaw** sebagai *open-source, self-hosted personal AI agent*.
- Membedakan paradigma **Agen Reaktif** (seperti Claude Code, ChatGPT CLI) dengan **Agen Otonom Proaktif** (OpenClaw).
- Memahami arsitektur **Gateway Daemon**, hubungan antara *Messaging Channels*, *Model Adapters*, *Execution Sandboxes*, dan *State Stores*.
- Menjelaskan keuntungan sistem **Model-Agnostic** (bebas memilih antara OpenAI, Anthropic, Gemini, atau model lokal via Ollama).

## 2. Prerequisite
- Pemahaman dasar tentang cara kerja Large Language Models (LLM) dan API berbasis token.
- Pengetahuan dasar terminal Linux/Unix atau PowerShell Windows (proses daemon, background service).

## 3. Concept
Kebanyakan alat AI saat ini beroperasi dengan model *Chatbot Reaktif*: Anda membuka tab browser atau terminal, mengetik prompt, menunggu AI merespons, lalu menutup jendela. Begitu jendela ditutup, interaksi terhenti. AI tidak mengetahui apa yang terjadi di dunia nyata saat Anda tidak berada di depan laptop.

**OpenClaw** mengubah paradigma ini menjadi **Personal Autonomous Agent**:
1. **Always-On Background Daemon**: OpenClaw berjalan 24/7 di komputer lokal atau VPS Anda sebagai proses latar belakang (*gateway daemon*).
2. **Omni-Channel Messaging Hub**: Anda tidak perlu membuka antarmuka khusus. Anda cukup mengirim pesan melalui aplikasi yang sudah Anda gunakan setiap hari: **Telegram, WhatsApp, Discord, atau Slack**.
3. **Proactive & Event-Driven**: Selain merespons pesan teks Anda, OpenClaw dapat bertindak sendiri berdasarkan pemicu waktu (*Cron*), pemantauan sistem berkala (*Heartbeat*), atau panggilan API masuk (*Webhooks*).
4. **Model-Agnostic Control**: Anda memegang kendali penuh atas data dan otak AI Anda. Anda dapat menggunakan Anthropic Claude untuk tugas penalaran rumit, OpenAI GPT-4o untuk multimodal, Gemini Flash untuk ringkasan cepat, atau LLM lokal (Llama 3 di Ollama) agar data sensitif tidak pernah meninggalkan komputer Anda.

## 4. Why?
- **Zero Lock-In & Privasi Data**: Menggunakan asisten komersial pihak ketiga berarti menyerahkan email, kalender, dan file pribadi Anda ke server perusahaan besar. Dengan OpenClaw, seluruh gateway dan penyimpanan data berada di bawah kendali infrastruktur pribadi Anda.
- **Kenyamanan Akses dari Ponsel**: Anda sedang berada di jalan dan ingin mengecek status deploy server, merangkum dokumen PDF kerja, atau mengatur agenda besok. Anda cukup mengirim voice note atau chat teks di Telegram ke bot OpenClaw Anda.
- **Automasi Mandiri**: Agen dapat memantau harga tiket pesawat, email penting dari klien VIP, atau error log server di tengah malam, lalu secara proaktif mengirimkan ringkasan peringatan ke WhatsApp Anda saat Anda bangun pagi.

## 5. What?
### Komponen Inti Arsitektur OpenClaw:
1. **OpenClaw Gateway (Core Daemon)**:
   Proses inti tunggal yang mendengarkan event, mengelola koneksi socket perpesanan, dan menjadi pengendali lalu lintas instruksi (*dispatcher*).
2. **Channel Adapters (Ingress/Egress)**:
   Modul penghubung ke platform perpesanan eksternal (Telegram Bot API, Discord Gateway WebSocket, WhatsApp Baileys multi-device socket, Slack Events API).
3. **Model Router & Provider Engine**:
   Lapisan abstraksi yang menerjemahkan instruksi pengguna ke format payload model AI target (OpenAI API, Anthropic Messages API, Google Generative AI, atau Ollama Local API).
4. **Skills & Tools Registry**:
   Kumpulan kapabilitas fungsional agen (akses shell terminal, pembaca file, pencari web, Google Calendar, pengirim email, atau custom tool eksternal via MCP).
5. **Memory & State Storage**:
   Penyimpanan sesi obrolan (SQLite) dan memori semantik jangka panjang (*vector database embeddings*) agar agen mengingat preferensi dan instruksi masa lalu Anda.

## 6. How?
### Alur Pemrosesan Pesan End-to-End:
```text
[Pengguna di HP] ── 1. Kirim Chat: "Tolong cek sisa disk server dan ringkas" ──> [Telegram Server]
                                                                                     │
                                                                                     ▼ 2. Long Poll / Webhook
                                                                           [OpenClaw Gateway Daemon]
                                                                                     │
                                    ┌────────────────────────────────────────────────┤
                                    │ 3. Load Context & Memory                       │ 4. Route ke LLM
                                    ▼                                                ▼
                          [SQLite / Vector DB]                           [Anthropic Claude 3.5 Sonnet]
                                                                                     │
                                                                                     ▼ 5. LLM Mengembalikan Tool Call:
                                                                                     `execute_shell("df -h")`
                                                                                     │
                                    ┌────────────────────────────────────────────────┘
                                    │ 6. Evaluasi Keamanan & Izin (Permission Check)
                                    ▼
                          [Sandbox Execution Engine]
                                    │ (Eksekusi: df -h -> Output: Disk 85% full)
                                    ▼
                          [Kirim Output Tool ke LLM]
                                    │
                                    ▼ 7. LLM Menghasilkan Respon Final dalam Bahasa Manusia
                          [OpenClaw Gateway]
                                    │
                                    ▼ 8. Kirim Pesan Balasan via Telegram API
[Pengguna di HP] <── "Sisa disk server Anda saat ini berada di 15% (85% terpakai)..."
```

## 7. Analogy
- **Chatbot Konvensional (ChatGPT Web) = Booth Informasi di Mal**: Anda harus berjalan menghampiri meja informasi, bertanya kepada petugas, dan petugas hanya menjawab saat Anda berdiri di depannya. Saat Anda pergi, petugas lupa siapa Anda.
- **Claude Code = Mekanik Khusus di Bengkel**: Anda datang membawa mobil ke bengkel, mekanik memeriksa mesin dengan teliti di terminal kerja bengkel. Tapi dia bukan orang yang bisa Anda suruh belanja sayur atau membangunkan Anda di pagi hari.
- **OpenClaw = Asisten Pribadi / Butler 24 Jam (Jarvis)**: Dia selalu siaga di rumah Anda (daemon 24/7). Anda bisa menghubunginya lewat walkie-talkie atau WhatsApp dari mana saja. Jika ada maling di pagar rumah saat tengah malam (event/webhook), dia langsung menelepon Anda secara proaktif.

## 8. Diagram

```text
======================= ARSITEKTUR SUBSISTEM OPENCLAW =======================

       [Telegram]       [WhatsApp]       [Discord]       [Slack]
           │                │                │               │
           └────────────────┴───────┬────────┴───────────────┘
                                    │ (Channel Ingress)
                                    ▼
                     ┌───────────────────────────────┐
                     │    OPENCLAW GATEWAY DAEMON    │
                     │  - Event Loop & Scheduler     │
                     │  - Session & Context Manager  │
                     │  - Security & Permission Gate │
                     └──────────────┬────────────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         ▼                          ▼                          ▼
  [Model Router]           [Skills & Tools Engine]     [Memory & State]
  ├── OpenAI               ├── Local Shell Exec        ├── SQLite (History)
  ├── Anthropic            ├── File System RW          └── Vector Store
  ├── Google Gemini        ├── Web Scraper / Search         (Chroma/pgvector)
  └── Ollama (Lokal)       └── MCP Tool Servers
```

## 9. Simple Example: Perbandingan Arsitektur Perintah
- **Model Reaktif (CLI Standar)**:
  `$ claude "ringkas file meeting.txt"` $\rightarrow$ CLI jalan, panggil API, cetak hasil ke terminal, proses mati (*exit 0*).
- **Model Otonom OpenClaw (Daemon)**:
  Daemon berjalan terus di background (`systemctl status openclaw`). Di aplikasi Telegram, Anda mengirim voice note: *"Bro, baca meeting.txt terus kirim poin pentingnya ke channel Discord tim ya"*. OpenClaw mendengarkan via socket Telegram, memproses audio, membaca file lokal, dan mem-posting ringkasan ke webhook Discord tim Anda secara otonom!

## 10. Practical Example: Mengganti Otak AI Secara Dinamis
Dalam OpenClaw, Anda tidak terkunci pada satu vendor AI. Anda dapat mengonfigurasi aturan routing di file konfigurasi:
```json
{
  "models": {
    "default": "anthropic/claude-3-5-sonnet",
    "fast_chat": "google/gemini-2.0-flash",
    "private_local": "ollama/llama3.2:3b",
    "coding_tasks": "openai/gpt-4o"
  }
}
```
Saat Anda mengirim pertanyaan santai, gateway merutekan ke Gemini Flash yang murah dan kilat. Saat Anda menyuruh agen menganalisis laporan keuangan rahasia, agen merutekannya ke Ollama lokal di mesin Anda tanpa satu byte pun data terkirim ke internet!

## 11. Real World Example
- **DevOps On-Call Engineer**: Menggunakan OpenClaw di VPS pribadi. Ketika Prometheus mendeteksi server database down jam 3 pagi, webhook Prometheus memicu OpenClaw. OpenClaw menjalankan skill diagnosa log `journalctl -u mysql -n 50`, merangkum penyebab crash, lalu mengirimkan notifikasi darurat beserta tombol aksi *"Restart Database?"* langsung ke WhatsApp engineer yang sedang tidur.
- **Freelance Researcher**: Mengonfigurasi cron job OpenClaw setiap jam 08:00 untuk men-scrape artikel terbaru di arXiv dan HackerNews tentang AI Agents, lalu mengirimkan audio briefing atau ringkasan 3 paragraf ke Telegram.

## 12. Trade-offs: OpenClaw vs Alternatif

| Parameter | OpenClaw | Claude Code | Web Chat (ChatGPT/Claude) |
|---|---|---|---|
| **Sifat Operasi** | Proaktif 24/7 (Daemon background) | Reaktif (Per sesi terminal) | Reaktif (Browser session) |
| **Kanal Akses** | Telegram, WhatsApp, Discord, Slack | Command Line Interface (CLI) | Web Browser GUI / Mobile App |
| **Pilihan Model** | **Model-Agnostic** (Bebas pilih) | Terkunci pada Anthropic Claude | Terkunci pada provider masing-masing |
| **Akses Sistem Lokal** | Ya (File, Shell, Cron, Webhooks) | Ya (File, Shell proyek lokal) | Tidak (Cloud sandbox tertutup) |
| **Automasi Mandiri** | Ya (Cron, Heartbeat, Webhook) | Tidak (Menunggu input user) | Terbatas (Custom GPTs / Actions) |
| **Kompleksitas Setup** | Sedang (Perlu setup daemon & token) | Sangat Rendah | Nol (Tinggal login) |

## 13. When To Use OpenClaw
- Anda ingin memiliki asisten AI pribadi yang selalu aktif dan dapat dihubungi kapan saja dari smartphone via Telegram/WhatsApp.
- Membutuhkan automasi tugas rutin tanpa perlu membuka komputer (scheduled reporting, log monitoring, email drafting).
- Mengharuskan data sensitif diproses secara lokal di server pribadi Anda (*Self-hosted sovereignty*).

## 14. When NOT To Use OpenClaw
- Anda hanya membutuhkan asisten sesekali untuk coding cepat di satu repo lokal (lebih praktis menggunakan CLI reaktif seperti Claude Code atau Cursor).
- Anda belum memiliki pemahaman dasar keamanan komputer dan tidak siap mengelola izin eksekusi shell agen Anda.

## 15. Common Mistakes
1. **Memberikan Root Shell Access Tanpa Sandboxing**: Menjalankan daemon OpenClaw sebagai `root` di Linux dan memberikan izin eksekusi shell bebas tanpa konfirmasi manusia (*Human-in-the-loop*). Jika terjadi prompt injection, attacker dapat menghapus seluruh server!
2. **Mengabaikan Penguncian ID Pengguna (User Whitelisting)**: Menghubungkan bot Telegram publik tanpa memvalidasi `chat_id` pengirim. Akibatnya, orang asing di internet yang menemukan bot Anda bisa menyuruh agen Anda membaca file pribadi di komputer Anda!
3. **Mengabaikan Biaya Token API pada Heartbeat Terlalu Sering**: Mengatur heartbeat proaktif setiap 10 detik menggunakan model mahal (GPT-4o) akan menghabiskan saldo ratusan dolar dalam beberapa hari hanya untuk mengecek sistem kosong.

## 16. Best Practices
- **Prinsip Least Privilege**: Jalankan OpenClaw di bawah user sistem terisolasi (misal user `openclaw` tanpa hak `sudo`).
- **Strict User Whitelist**: Kunci semua kanal komunikasi hanya untuk ID pengguna pribadi Anda.
- **Tiered Model Strategy**: Gunakan model hemat/lokal untuk tugas background heartbeat, dan gunakan model tier atas hanya untuk penalaran rumit.

## 17. Troubleshooting
- **Masalah: Daemon OpenClaw berjalan, tetapi bot Telegram tidak merespons pesan**.
  - *Sebab*: Token bot Telegram salah, atau ada proses bot lain yang sedang berjalan menggunakan token yang sama (*Conflict: 409 Conflict getUpdates*).
  - *Solusi*: Matikan proses bot lama, verifikasi bot token via `curl https://api.telegram.org/bot<TOKEN>/getMe`, dan cek log daemon.

## 18. Hands-on Practice
Mari kita buktikan arsitektur inti OpenClaw secara visual dan fungsional melalui simulator gateway Node.js murni di direktori `hands-on/m01/gateway_sim.js`.

## 19. Exercises & Challenge
- **Exercise**: Jelaskan mengapa arsitektur pemisahan antara *Channel Adapters* dan *Model Adapters* mempermudah penambahan platform baru (misal menambahkan bot Signal tanpa mengubah kode integrasi LLM).
- **Challenge**: Rancang skema routing pesan di mana pesan dengan kata kunci "DARURAT" akan langsung diproses oleh model penalaran tercepat dan mengirimkan SMS/Telepon darurat ke nomor pemilik.

## 20. Summary
OpenClaw adalah evolusi arsitektur asisten kecerdasan buatan dari yang sebelumnya bersifat reaktif dan terisolasi di browser/CLI, menjadi sistem operasi agen mandiri yang selalu aktif (*always-on 24/7*), multi-kanal (*omni-channel*), proaktif, dan bebas dari penguncian vendor (*model-agnostic*).
