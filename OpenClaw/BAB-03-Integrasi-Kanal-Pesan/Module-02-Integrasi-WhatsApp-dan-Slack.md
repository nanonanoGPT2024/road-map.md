# Module 02: Integrasi WhatsApp & Slack (Session Management & Multi-Device)

## 1. Learning Objective
Setelah menyelesaikan modul ini, Anda akan mampu:
- Menghubungkan akun **WhatsApp** ke OpenClaw menggunakan emulasi multi-device session (Baileys / WhatsApp Web Protocol) tanpa biaya API resmi Meta.
- Mengonfigurasi **Slack Bot** menggunakan **Socket Mode** untuk menerima event tanpa memerlukan IP publik statis.
- Mengelola persistensi sesi kredensial WhatsApp (`auth_info`) agar bot tidak perlu scan QR ulang setiap kali daemon restart.
- Mengimplementasikan **Unified Identity Mapping**: menyatukan identitas Anda di WhatsApp, Telegram, Discord, dan Slack ke dalam satu profil memori agen terpadu.

## 2. Prerequisite
- Memahami konsep dasar WebSockets dan Channel Adapters dari Module 01.
- Memiliki nomor WhatsApp aktif di smartphone dan workspace Slack (akses administrator).

## 3. Concept
WhatsApp dan Slack memiliki pendekatan arsitektur yang sangat kontras dengan Telegram:
1. **WhatsApp (Tantangan Multi-Device Tanpa API Resmi)**:
   Meta membatasi WhatsApp Cloud API resmi hanya untuk akun bisnis berbayar per percakapan (*Pay-per-conversation*). Untuk personal AI agent self-hosted gratis, OpenClaw mengadopsi protokol **WhatsApp Web Multi-Device Socket (Baileys Engine)**. Agen bertindak layaknya browser web sekunder (seperti membuka WhatsApp Web di laptop): Anda melakukan scan QR code satu kali di terminal, dan daemon menyimpan kunci sesi kriptografis untuk terhubung 24/7.
2. **Slack (Socket Mode)**:
   Secara tradisional, Slack Events API mewajibkan URL Webhook publik yang dilindungi HTTPS. OpenClaw memanfaatkan fitur **Slack Socket Mode**: bot membuka koneksi WebSocket keluar (*outbound WSS*) ke server Slack menggunakan App-Level Token (`xapp-...`). Ini memungkinkan bot berjalan dengan aman di PC rumah di balik router tanpa port forwarding atau tunnel.

## 4. Why?
- **WhatsApp adalah Aplikasi Utama di Indonesia & Global**: Lebih dari 90% komunikasi masyarakat Indonesia terjadi di WhatsApp. Mampu mengirim pesan ke agen AI Anda langsung dari aplikasi chat yang Anda buka setiap 5 menit adalah kenyamanan tertinggi.
- **Slack untuk Otomasi Tempat Kerja (Workplace Integration)**: Agen OpenClaw dapat bertindak sebagai asisten kantor yang membantu merangkum thread diskusi tim, mengingatkan deadline sprint Jira, dan menyiapkan draft jawaban tiket support.

## 5. What?
### Komponen Integrasi WhatsApp & Slack:
1. **WhatsApp Baileys Adapter**:
   - Membuka soket Noise Protocol ke server WhatsApp.
   - Menghasilkan terminal QR Code saat pertama kali inisialisasi.
   - Menyimpan kredensial sesi multi-device di folder `state/wa_auth/`.
   - Menangani sinkronisasi pesan masuk, centang biru (read receipts), dan status online.
2. **Slack Socket Mode Client**:
   - Menghubungkan client WebSocket ke `wss://wss-primary.slack.com/link`.
   - Mengonsumsi event `app_mention` dan `message.im`.
   - Mengembalikan respon interaktif menggunakan Slack Block Kit (teks terformat rapi, tombol, dropdown).
3. **Cross-Channel User Mapping Store**:
   - Menghubungkan nomor telepon WhatsApp (`+62812...`), ID Telegram (`99881122`), dan ID Slack (`U04AB...`) ke satu `User Profile: Budi`.

## 6. How?
### Langkah Integrasi WhatsApp (Baileys):
1. Aktifkan kanal WhatsApp di `~/.openclaw/config.json`:
   ```json
   {
     "channels": {
       "whatsapp": {
         "enabled": true,
         "authFolder": "state/wa_auth",
         "ownerPhone": "628123456789"
       }
     }
   }
   ```
2. Jalankan perintah pairing di terminal:
   ```bash
   openclaw channel login whatsapp
   ```
3. Terminal akan mencetak gambar **QR Code ASCII**.
4. Buka WhatsApp di ponsel $\rightarrow$ **Settings** $\rightarrow$ **Linked Devices** $\rightarrow$ **Link a Device** $\rightarrow$ Arahkan kamera ke layar terminal.
5. Sesi berhasil dipasangkan (*Device Paired*). Kredensial disimpan di `state/wa_auth/creds.json`.

### Langkah Integrasi Slack (Socket Mode):
1. Buat Slack App di `api.slack.com/apps`.
2. Masuk ke **Socket Mode** $\rightarrow$ Aktifkan toggle **Enable Socket Mode**. Buat App-Level Token dengan scope `connections:write` (Simpan token `xapp-...`).
3. Masuk ke **OAuth & Permissions** $\rightarrow$ Tambahkan bot scopes: `chat:write`, `channels:history`, `im:history`, `app_mentions:read`.
4. Install App ke Workspace dan salin Bot User OAuth Token (`xoxb-...`).
5. Tambahkan ke file `.env`:
   ```env
   SLACK_BOT_TOKEN=xoxb-...
   SLACK_APP_TOKEN=xapp-...
   SLACK_OWNER_ID=U04ABCDEF
   ```

## 7. Analogy
- **WhatsApp Baileys = Laptop Cadangan yang Terhubung ke WhatsApp Web**: Begitu Anda scan barcode satu kali, laptop tersebut bisa mengirim dan membaca pesan kapan saja meskipun smartphone utama Anda berada di saku atau mati baterai sementara.
- **Cross-Channel User Sync = Buku Kontak Terpadu**: Di ponsel Anda tersimpan nama *"Pak Budi"*. Anda tahu dia bisa menelepon dari nomor WhatsApp, mengirim DM Telegram, atau mention di Slack. Siapapun jalur yang dia gunakan, asisten Anda tahu dia adalah orang yang sama dan memiliki riwayat obrolan yang sama.

## 8. Diagram

```text
================ CROSS-CHANNEL UNIFIED IDENTITY ARCHITECTURE ================

  [WhatsApp Mobile]       [Telegram Mobile]       [Slack Desktop]
          │                       │                      │
          │ (+628123...)          │ (TG_ID: 998811)      │ (Slack_ID: U04...)
          ▼                       ▼                      ▼
  [WhatsApp Adapter]      [Telegram Adapter]      [Slack Adapter]
          │                       │                      │
          └───────────────────────┼──────────────────────┘
                                  │
                                  ▼
                    [Identity Resolution Layer]
                    - Cek Mapping Table: Siapa Pengirim Ini?
                    - Hasil: Semuanya adalah "User: Budi (Admin)"
                                  │
                                  ▼
                     [Unified Memory Context]
       (Konteks chat di WhatsApp kemarin tetap diingat saat chat di Slack hari ini!)
```

## 9. Simple Example: Skema Database Cross-Channel Mapping (SQLite)
```sql
CREATE TABLE user_identities (
    unified_user_id VARCHAR(50) PRIMARY KEY, -- misal: "user_budi"
    name VARCHAR(100),
    telegram_id VARCHAR(50),
    whatsapp_phone VARCHAR(50),
    discord_id VARCHAR(50),
    slack_id VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Contoh Data:
INSERT INTO user_identities (unified_user_id, name, telegram_id, whatsapp_phone, slack_id)
VALUES ('usr_01', 'Budi Santoso', '99881122', '628123456789', 'U04ABCDEF');
```

## 10. Practical Example: Meneruskan Percakapan Antar-Kanal
1. Jam 14:00 di **WhatsApp**: Anda chat: *"Bro, buatkan kerangka proposal kerja sama proyek fintech ya."*
   Agen merespons: *"Siap Pak, sedang saya susun."*
2. Jam 16:00 di kantor via **Slack**: Anda membuka laptop dan chat: *"Bagaimana proposal tadi? Sudah selesai?"*
   Karena identitas Anda tersinkronisasi, agen langsung membalas di Slack:
   *"Proposal kerja sama fintech yang Anda minta via WhatsApp tadi sudah selesai! Berikut draf 4 poin utamanya..."*.
   **Nol redundansi! Konteks tidak terputus lintas aplikasi!**

## 11. Real World Example
- **Automasi Layanan Pelanggan UMKM**: Pemilik toko online menghubungkan WhatsApp nomor bisnisnya ke OpenClaw. Di siang hari saat sibuk melayani pembeli di toko fisik, agen OpenClaw otomatis membalas pertanyaan pembeli WhatsApp mengenai katalog stok dan ongkos kirim. Di saat yang sama, laporan ringkasan pesanan masuk dikirimkan agen ke channel privat `#laporan-omzet` di Slack tim gudang.

## 12. Trade-offs

| Fitur | WhatsApp (Baileys) | Slack (Socket Mode) |
|---|---|---|
| **Stabilitas Sesi** | Sedang (Bisa terputus jika WhatsApp web di-logout) | Sangat Tinggi (Token permanen) |
| **Biaya Operasional** | **100% Gratis** | **100% Gratis (Free Workspace)** |
| **Resiko Ban Akun** | Ada jika mengirim spam blast massal | Nol (Platform resmi Developer) |
| **Formatting Pesan** | Terbatas (Bold, Italic, Monospace) | Sangat Kaya (Block Kit, Tables, Buttons) |

## 13. When To Use WhatsApp
- Interaksi asisten pribadi personal langsung dari smartphone tanpa perlu menginstal aplikasi chatting baru.

## 14. When NOT To Use WhatsApp Baileys
- Mengirim pesan promosi blast dingin (*cold spam*) ke ribuan nomor orang asing (algoritma anti-spam WhatsApp akan langsung memblokir nomor telepon Anda!). Gunakan nomor WhatsApp sekunder khusus untuk agen pribadi Anda.

## 15. Common Mistakes
1. **Menghapus Folder `state/wa_auth`**: Menghapus folder ini akan menghapus kunci sesi kriptografis, sehingga Anda harus melakukan scan QR ulang dari awal.
2. **Nomor HP Tidak Menggunakan Kode Negara**: Memasukkan `0812...` alih-alih `62812...` di konfigurasi WhatsApp filter. Format ID WhatsApp selalu menggunakan format JID internasional: `628123456789@s.whatsapp.net`.
3. **Mengabaikan Keep-Alive Reconnection pada Baileys**: Koneksi soket WhatsApp dapat terputus sejenak saat smartphone berganti jaringan dari WiFi ke 4G. Wajib memasang logic auto-reconnect dengan exponential backoff.

## 16. Best Practices
- **Gunakan Nomor HP Khusus (Dedicated SIM)**: Jangan gunakan nomor WhatsApp utama pribadi keluarga untuk eksperimen bot agresif; beli nomor eSIM sekunder khusus untuk nomor bot asisten Anda.
- **Backup Folder Kredensial**: Buat backup terenkripsi dari folder `state/wa_auth` agar bot dapat langsung dipulihkan saat server migrasi.
- **Rate Limit Pengiriman WhatsApp**: Berikan jeda waktu acak (*human delay*) 1-3 detik sebelum membalas pesan di WhatsApp untuk menghindari deteksi otomatis bot oleh Meta.

## 17. Troubleshooting
- **Masalah: WhatsApp terus terputus dengan error `ConnectionClosed: 401 Disconnected`**.
  - *Sebab*: Akun telah di-logout manual dari aplikasi WhatsApp di HP (*Linked Devices*), atau masa berlaku sesi browser habis.
  - *Solusi*: Hapus isi folder `state/wa_auth`, lalu jalankan `openclaw channel login whatsapp` untuk memunculkan QR Code pairing baru.

## 18. Hands-on Practice
Mari kita buktikan implementasi integrasi WhatsApp Session Handler dan Cross-Channel Unified Identity Resolver di `hands-on/m02/whatsapp_session_sync.js`.

## 19. Exercises & Challenge
- **Exercise**: Mengapa WhatsApp Multi-Device session tidak memerlukan smartphone utama selalu menyala dengan internet aktif sepanjang waktu?
- **Challenge**: Rancang skema deteksi platform di mana jika pengguna bertanya di Slack saat jam kantor (09:00 - 17:00), agen membalas di Slack, namun jika pengguna bertanya di luar jam kantor, agen mengirimkan balasan darurat ke WhatsApp.

## 20. Summary
Menghubungkan WhatsApp dan Slack melengkapi kapabilitas omni-channel OpenClaw. Melalui emulasi **Multi-Device Baileys** dan **Slack Socket Mode**, dipadukan dengan **Unified Identity Resolution**, asisten AI Anda mampu mengenali Anda dan mempertahankan kesinambungan memori konteks obrolan di platform manapun Anda berada.
