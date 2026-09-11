# Module 01: Menghubungkan Telegram & Discord Bot Gateway

## 1. Learning Objective
Setelah menyelesaikan modul ini, Anda akan mampu:
- Mengonfigurasi dan menghubungkan **Telegram Bot API** ke OpenClaw Gateway menggunakan mode *Long Polling* maupun *Webhooks*.
- Mengonfigurasi **Discord Bot Application** dengan *Privileged Gateway Intents* untuk mendengarkan pesan langsung (DM) dan channel server.
- Memproses berbagai tipe media masuk: teks, gambar/dokumen, dan pesan suara (*Voice Notes*).
- Mengimplementasikan filter keamanan ketat: *User Whitelisting*, *Chat ID verification*, dan isolasi sesi per kanal.

## 2. Prerequisite
- Memahami konsep arsitektur Gateway Daemon dari BAB 01.
- Memiliki akun Telegram aktif dan akun Discord dengan akses Developer Portal.

## 3. Concept
Kanal perpesanan (*Messaging Channels*) adalah antarmuka utama tempat Anda berinteraksi dengan agen OpenClaw Anda. Alih-alih membuat aplikasi mobile baru dari nol, OpenClaw memanfaatkan platform perpesanan yang sudah memiliki enkripsi, sinkronisasi cloud, dan aplikasi mobile kelas dunia: **Telegram** dan **Discord**.

Kedua platform ini memiliki karakteristik protokol yang berbeda:
1. **Telegram Bot API**:
   - Berbasis HTTP REST.
   - Mendukung dua mode penerimaan: **Long Polling** (`getUpdates`) yang sangat mudah digunakan di jaringan lokal tanpa IP publik, atau **Webhooks** untuk efisiensi tinggi di server produksi dengan domain HTTPS.
2. **Discord Gateway**:
   - Berbasis koneksi persisten **WebSocket (WSS)**.
   - Bot mendengarkan aliran event real-time dari gateway Discord (`MESSAGE_CREATE`, `INTERACTION_CREATE`).
   - Membutuhkan izin khusus (*Privileged Gateway Intent: Message Content*) agar bot dapat membaca isi teks pesan.

## 4. Why?
- **Aksesibilitas Universal**: Anda dapat mengendalikan server dan agen AI Anda dari smartwatch Apple/Android, tablet, laptop, atau smartphone di mana saja tanpa VPN rumit.
- **Dukungan Rich Media Bawaan**: Telegram dan Discord mendukung pengiriman voice note, foto tangkapan layar, file PDF, dan tombol interaktif (*Inline Keyboards / Buttons*).

## 5. What?
### Komponen Integrasi Kanal:
1. **Telegram Adapter**:
   - Mengelola koneksi polling atau webhook endpoint.
   - Mengekstrak metadata pengirim: `message.from.id` (User ID), `message.chat.id` (Chat ID), dan tipe payload.
   - Menangani pesan suara: mengunduh file `.oga` / `.ogg`, mengonversinya via `ffmpeg`, dan mengirimkannya ke Speech-to-Text (Whisper).
2. **Discord Adapter**:
   - Mengelola koneksi WebSocket dan siklus heartbeat ping-pong Discord.
   - Memfilter asal pesan: membedakan antara *Direct Message (DM)* pribadi dengan *Channel Obrolan Publik*.
   - Menangani mention bot (`@OpenClaw status`).
3. **Channel Normalizer**:
   - Mengubah format event Telegram dan Discord menjadi satu format paket internal OpenClaw:
     `{ channelId, senderId, text, attachments, replyCallback }`.

## 6. How?
### Langkah 1: Menyiapkan Bot Telegram
1. Buka aplikasi Telegram, cari bot resmi `@BotFather`.
2. Kirim perintah `/newbot`, ikuti petunjuk nama dan username (misal: `MyClawButler_bot`).
3. Simpan **HTTP API Bot Token** yang diberikan (format: `123456789:ABCdefGhIJKlmNoPQRstuVWxYz`).
4. Dapatkan ID Akun Telegram pribadi Anda menggunakan bot `@userinfobot` (misal ID: `987654321`).
5. Tambahkan ke file `~/.openclaw/.env`:
   ```env
   TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRstuVWxYz
   TELEGRAM_OWNER_ID=987654321
   ```

### Langkah 2: Menyiapkan Bot Discord
1. Buka **Discord Developer Portal** (`discord.com/developers/applications`).
2. Klik **New Application**, beri nama (misal: `OpenClaw Agent`).
3. Masuk ke tab **Bot**:
   - Klik **Reset Token** dan salin bot token.
   - Gulir ke bawah ke bagian **Privileged Gateway Intents**: Aktifkan centang **MESSAGE CONTENT INTENT**.
4. Masuk ke tab **OAuth2 -> URL Generator**:
   - Pilih scope: `bot`.
   - Pilih permissions: `Send Messages`, `Read Message History`, `Attach Files`.
   - Buka tautan URL yang dihasilkan di browser untuk mengundang bot ke server Discord pribadi Anda.
5. Tambahkan ke file `~/.openclaw/.env`:
   ```env
   DISCORD_BOT_TOKEN=MTEyMzQ1...
   DISCORD_OWNER_ID=334455667788990011
   ```

## 7. Analogy
- **Telegram & Discord = Dua Jalur Walkie-Talkie Berbeda**:
  - Saluran 1 adalah frekuensi Telegram (mudah dihubungi di jalanan).
  - Saluran 2 adalah frekuensi Discord (siaga di komputer gaming dan komunitas).
  - Asisten OpenClaw Anda memegang kedua walkie-talkie tersebut di telinganya. Ketika Anda berbicara di saluran manapun, dia mendengarkan, menjalankan perintah, dan membalas di saluran yang sama.

## 8. Diagram

```text
================ ARSITEKTUR INTEGRASI KANAL PERPESANAN ================

[Telegram App (Mobile)]                     [Discord App (Desktop)]
         │                                             │
         │ (HTTP Long Poll / Webhook)                  │ (WebSocket Gateway WSS)
         ▼                                             ▼
┌──────────────────┐                         ┌──────────────────┐
│ Telegram Adapter │                         │ Discord Adapter  │
└────────┬─────────┘                         └────────┬─────────┘
         │                                            │
         └─────────────────────┬──────────────────────┘
                               │
                               ▼
                   [Channel Normalizer Engine]
                  - Extract Sender ID & Channel
                  - Whitelist Authentication Check
                  - Convert Audio/Image to Text/Vision
                               │
                               ▼
                   [OpenClaw Gateway Core]
```

## 9. Simple Example: Penanganan Long Polling Telegram (Node.js)
```javascript
async function pollTelegramUpdates(token, offset = 0) {
  const url = `https://api.telegram.org/bot${token}/getUpdates?offset=${offset}&timeout=30`;
  const res = await fetch(url);
  const data = await res.json();
  
  for (const update of data.result) {
    if (update.message) {
      console.log(`Pesan dari ${update.message.from.first_name}: ${update.message.text}`);
      offset = update.update_id + 1;
    }
  }
  return offset;
}
```

## 10. Practical Example: Voice Note Transcription Workflow
Ketika Anda sedang mengemudi mobil dan mengirim voice note di Telegram ke OpenClaw:
1. Telegram mengirimkan objek `voice` berisi `file_id`.
2. OpenClaw mengunduh audio biner via Telegram API `getFile`.
3. OpenClaw menjalankan ffmpeg lokal untuk konversi ke WAV:
   `ffmpeg -i voice.oga -ar 16000 voice.wav`.
4. Audio di-transkrip oleh OpenAI Whisper API atau Whisper.cpp lokal menjadi teks:
   *"Tolong ingatkan saya bayar tagihan internet jam 7 malam"*.
5. Teks tersebut diproses oleh LLM agen, lalu bot membalas via teks:
   *"Siap Pak, pengingat bayar internet jam 19:00 telah saya jadwalkan!"*.

## 11. Real World Example
- **Server Ops Team di Discord**: Sebuah tim developer mengundang bot OpenClaw ke channel privat `#devops-war-room`. Bot hanya merespons perintah dari role `@Lead-Engineer`. Saat anggota tim mengetik `@OpenClaw deploy staging`, bot mengeksekusi pipeline GitHub Actions dan mem-posting log kemajuan langsung ke thread obrolan Discord.

## 12. Trade-offs

| Aspek | Telegram Bot | Discord Bot |
|---|---|---|
| **Kemudahan Setup** | Sangat Mudah (Hanya butuh `@BotFather`) | Menengah (Butuh konfigurasi portal & intents) |
| **Konektivitas di Balik NAT/Firewall**| Luar Biasa (Long Polling bekerja di mana saja) | Sangat Baik (WebSocket outbound connection) |
| **Kapasitas Media** | File hingga 20 MB (Bot API standar) | File hingga 25 MB (Server biasa) |
| **User Interface** | Bersih, fokus pada 1-on-1 private chat | Sangat kaya (Threads, Channels, Server Roles) |

## 13. When To Use Telegram
- Pilihan utama untuk asisten pribadi harian (*Personal Butler*): cepat dibuka di ponsel, konsumsi baterai rendah, dan fitur voice note terbaik.

## 14. When To Use Discord
- Pilihan ideal jika asisten digunakan bersama tim, komunitas pengembang, atau diintegrasikan ke dalam channel server proyek tertentu.

## 15. Common Mistakes
1. **Lupa Mengaktifkan "Message Content Intent" di Discord**: Bot berhasil online dan masuk server, tetapi setiap pesan yang dikirim anggota dibaca sebagai string kosong `""` karena intent tidak dicentang di Developer Portal.
2. **Tidak Memvalidasi Asal Chat ID di Grup Telegram**: Jika bot dimasukkan ke grup obrolan keluarga, bot merespons perintah dari siapa saja di grup tersebut jika Anda tidak mengunci validasi `from.id`.
3. **Menjalankan Webhook Tanpa Sertifikat SSL Valid**: Telegram mewajibkan HTTPS dengan sertifikat SSL valid untuk webhook; koneksi plain HTTP atau SSL self-signed yang salah konfigurasi akan ditolak Telegram.

## 16. Best Practices
- **Prioritaskan Long Polling untuk Local/Home Server**: Jika menjalankan OpenClaw di PC rumah di balik router IndiHome/FirstMedia tanpa IP publik statis, gunakan Long Polling (tidak butuh port forwarding).
- **Gunakan Typo-Proof Sanitizer**: Hapus awalan slash atau mention otomatis (misal `/ask` atau `@MyBot`) sebelum pesan diteruskan ke prompt LLM.
- **Tampilkan Indikator Mengetik (*Typing Indicator*)**: Kirimkan status `sendChatAction: typing` saat LLM sedang memproses penalaran agar pengguna tahu bot tidak sedang macet.

## 17. Troubleshooting
- **Masalah: Error `409 Conflict: terminated by other getUpdates request` di Telegram**.
  - *Sebab*: Ada dua proses bot OpenClaw yang menggunakan token yang sama secara bersamaan.
  - *Solusi*: Matikan proses zombie lama dengan `openclaw stop --force` atau jalankan `pkill -f openclaw`.

## 18. Hands-on Practice
Mari kita buktikan arsitektur multi-channel yang mampu menerima pesan secara serempak dari Telegram dan Discord, memvalidasi whitelist, dan mengirimkan balasan kontekstual di `hands-on/m01/telegram_discord_gateway.js`.

## 19. Exercises & Challenge
- **Exercise**: Mengapa mode Long Polling pada Telegram tidak memerlukan IP publik atau domain HTTPS, sedangkan mode Webhook mewajibkannya?
- **Challenge**: Rancang skema *Interactive Action Buttons (Inline Keyboards)* di Telegram di mana jika agen mendeteksi perintah berbahaya (`rm -rf tmp/`), agen memunculkan 2 tombol di layar HP: `[✅ Setujui]` dan `[❌ Batalkan]`.

## 20. Summary
Telegram dan Discord adalah gerbang komunikasi manusia terdepan bagi OpenClaw. Dengan memahami arsitektur Long Polling vs Webhook pada Telegram, koneksi WebSocket berizin tinggi pada Discord, dan pengamanan whitelist berbasis Chat ID, agen AI Anda siap melayani kebutuhan Anda dari perangkat manapun di seluruh dunia.
