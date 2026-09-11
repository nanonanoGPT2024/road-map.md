# Module 01: Proactive Heartbeats & Scheduled Cron Jobs

## 1. Learning Objective
Setelah menyelesaikan modul ini, Anda akan mampu:
- Mengubah agen dari asisten pasif yang hanya merespons prompt menjadi **Agen Mandiri Proaktif** yang bertindak atas inisiatif sendiri.
- Mengonfigurasi **Heartbeat Engine** untuk melakukan inspeksi sistem berkala tanpa membebani perhatian pengguna (*Silent Heartbeat vs Alerting Heartbeat*).
- Menjadwalkan tugas terjadwal berbasis **Cron Expressions** (5-field syntax) untuk rutinitas harian (Morning Briefing, Daily Backups, Market Sweep).
- Mengelola state dan penjadwalan persisten agar jadwal cron tidak hilang saat daemon di-restart.

## 2. Prerequisite
- Memahami konsep arsitektur Gateway Daemon 24/7 dari BAB 01.
- Pengetahuan dasar tentang sintaks format waktu Cron (`* * * * *`).

## 3. Concept
Kelemahan terbesar chatbot tradisional adalah sifatnya yang sepenuhnya pasif: jika Anda lupa menyuruhnya mengecek server, AI tidak akan mengeceknya. Jika ada disk server yang 99% penuh pada jam 3 pagi, chatbot tidak akan memperingatkan Anda hingga server benar-benar roboh.

**OpenClaw Proactive Engine** memecahkan masalah ini dengan dua mekanisme waktu:
1. **Periodic Heartbeat (Denyut Nadi Agen)**:
   Setiap interval waktu tertentu (misal: setiap 15 menit), gateway membangunkan agen secara internal untuk menjalankan fungsi *System Sweep*. Agen memeriksa metrik, cuaca, atau status task.
   - Jika semua kondisi normal: agen kembali tidur tanpa mengirim notifikasi (**Silent Heartbeat**).
   - Jika terdeteksi anomali: agen secara proaktif mengirim pesan peringatan ke Telegram/WhatsApp Anda (**Alerting Heartbeat**).
2. **Scheduled Cron Jobs (Jadwal Terencana)**:
   Menjalankan alur kerja otomatis pada jam dan hari tertentu yang presisi (misal: setiap Senin jam 08:00 membuat agenda mingguan, setiap hari jam 22:00 mematikan server development staging).

## 4. Why?
- **Perhatian Pengguna adalah Sumber Daya Berharga**: Anda tidak ingin dibanjiri notifikasi spam setiap 5 menit jika tidak ada hal darurat (*Zero Alert Fatigue*).
- **Automasi Rutinitas Tanpa Usaha (Set and Forget)**: Bangun di pagi hari dengan secangkir kopi dan menemukan rangkuman berita, cuaca, dan agenda kalender sudah tersusun rapi di WhatsApp Anda.
- **Deteksi Dini Insiden**: Mencegah insiden sebelum menjadi bencana besar (deteksi kenaikan temperatur CPU atau sertifikat SSL yang tersisa 3 hari).

## 5. What?
### 1. Anatomi Sintaks Cron Standar (5-Field):
```text
┌───────────── Menit (0 - 59)
│ ┌─────────── Jam (0 - 23)
│ │ ┌───────── Hari dalam Bulan (1 - 31)
│ │ │ ┌─────── Bulan (1 - 12)
│ │ │ │ ┌───── Hari dalam Minggu (0 - 6, 0 = Minggu)
│ │ │ │ │
* * * * *
```
*Contoh Jadwal Populer:*
- `0 8 * * *` : Setiap hari tepat jam 08:00 pagi (Morning Briefing).
- `*/15 * * * *` : Setiap 15 menit sekali (Pemeriksaan status server).
- `0 2 * * 0` : Setiap hari Minggu jam 02:00 dini hari (Maintenance mingguan).

### 2. Aturan Emas Heartbeat (Silent vs Alerting):
Agen yang cerdas adalah agen yang **tahu kapan harus diam**:
- *Buruk*: Setiap 15 menit agen mengirim chat: *"Halo, saya sudah cek server dan kondisinya baik-baik saja"*. (Ini mengganggu tidur pengguna!).
- *Benar*: Agen mengecek diam-diam. Jika disk > 90%, baru agen mengirim chat: *"⚠️ Peringatan: Sisa disk server produksi Anda tersisa 8 GB (92% terpakai). Segera bersihkan log!"*.

## 6. How?
### Konfigurasi Jadwal di `~/.openclaw/config.json`:
```json
{
  "scheduler": {
    "heartbeat": {
      "enabled": true,
      "intervalMinutes": 15,
      "targetChannel": "telegram",
      "silentIfNormal": true,
      "checks": ["check_disk_space", "check_api_health"]
    },
    "cronJobs": [
      {
        "id": "morning_briefing",
        "schedule": "0 7 * * 1-5",
        "channel": "whatsapp",
        "prompt": "Kumpulkan agenda Google Calendar saya hari ini, cek cuaca Tangerang Selatan, dan buatkan ringkasan 3 poin untuk memulai hari."
      },
      {
        "id": "nightly_cleanup",
        "schedule": "0 23 * * *",
        "channel": "telegram",
        "prompt": "Jalankan skill pembersihan berkas sementara dan laporkan total byte yang berhasil dihapus."
      }
    ]
  }
}
```

## 7. Analogy
- **Chatbot Reaktif = Bel Pintu Rumah**: Bel hanya berbunyi jika ada tamu yang datang dan menekan tombol. Jika tidak ada orang menekan bel, rumah diam saja.
- **Heartbeat Proaktif = Satpam Perumahan yang Berkeliling Setiap 30 Menit**: Satpam berkeliling mengecek pagar rumah. Jika pagar terkunci aman, dia lewat tanpa mengetuk pintu. Tapi jika dia melihat ada keran air bocor atau asap mencurigakan di garasi, dia langsung mengetuk pintu dan membangunkan Anda.
- **Cron Jobs = Jam Beker / Alarm Pagi**: Jam beker yang sudah disetel berdering tepat setiap jam 07:00 pagi untuk membangunkan Anda dan menyajikan sarapan.

## 8. Diagram

```text
================ OPENCLAW PROACTIVE SCHEDULER ENGINE ================

             [Gateway Daemon Event Loop (24/7)]
                             │
       ┌─────────────────────┴─────────────────────┐
       ▼                                           ▼
[Heartbeat Ticker: Tiap 15 Menit]          [Cron Evaluator: Tiap Menit]
       │                                           │
       ▼ (Eksekusi Skill Cek Kondisi)              ▼ (Jam 07:00 Pagi?)
 [Cek RAM, CPU, Disk, Web Health]           [Trigger: Morning Briefing]
       │                                           │
  Ada Anomali?                                     ▼ (Panggil LLM)
  ├── TIDAK ──> [Silent: Log diam-diam & Tidur]  [Generate Briefing Text]
  │                                                │
  └── YA (CPU > 90%)                               ▼
       │                                  [Push Chat ke WhatsApp HP]
       ▼
 [Alerting: Push Chat Darurat ke Telegram HP]
```

## 9. Simple Example: Engine Evaluasi Heartbeat
```javascript
async function runHeartbeatCheck(systemCheckFn, notifyFn) {
  const metrics = await systemCheckFn();
  
  // Evaluasi Kondisi Ambang Batas (Threshold)
  if (metrics.diskUsagePercent > 90) {
    await notifyFn(`🚨 KRITIS: Disk server mencapai ${metrics.diskUsagePercent}%!`);
  } else if (metrics.serviceStatus !== "ONLINE") {
    await notifyFn(`🚨 KRITIS: Service '${metrics.serviceName}' mengalami CRASH!`);
  } else {
    // Silent mode: hanya catat ke log lokal
    console.log(`[Heartbeat OK] Semua metrik normal (Disk: ${metrics.diskUsagePercent}%). Tetap senyap.`);
  }
}
```

## 10. Practical Example: Morning Executive Briefing
Setiap hari kerja pukul 07:00 WIB:
1. OpenClaw Cron memicu event `morning_briefing`.
2. Agen mengeksekusi skill kalender: membaca 3 jadwal meeting hari ini.
3. Agen mengeksekusi skill cuaca: membaca cuaca Jakarta (hujan sore hari).
4. Agen mengeksekusi skill RSS: mengambil 2 berita teknologi terhangat.
5. Agen merangkum semuanya dalam 1 pesan WhatsApp yang elegan:
   *"Selamat pagi Pak Budi! Agenda Anda hari ini dimulai jam 09:30 dengan Tim Product. Siapkan payung karena BSD diprediksi hujan lebat jam 16:00. Berita utama: Model reasoning open-source baru resmi dirilis hari ini. Semangat berkarya!"*.

## 11. Real World Example
- **Serverless Cloud Cost Watchdog**: Startup mengonfigurasi heartbeat OpenClaw setiap 6 jam untuk memeriksa tagihan AWS Billing API. Jika lonjakan biaya harian melebihi \$50 dari batas normal (misal akibat serangan DDoS atau loop Lambda), agen mengirimkan notifikasi darurat langsung ke grup Slack tim finance dengan tombol aksi *"Lock AWS Account"*.

## 12. Trade-offs

| Mode Proaktif | Beban Komputasi & Token | Nilai Manfaat | Resiko |
|---|---|---|---|
| **High Frequency (< 1 menit)** | Sangat Tinggi (Biaya bengkak) | Deteksi instan | Alert fatigue (Pengguna terganggu) |
| **Silent Heartbeat (15-30 menit)**| **Sangat Rendah (Model lokal/aturan)**| **Optimal (Proteksi tanpa spam)**| **Nol Resiko (Hanya berbunyi saat bahaya)**|
| **Fixed Daily Cron** | Terprediksi (1x panggil per hari)| Sangat Tinggi untuk rutinitas | Tidak menangani krisis mendadak |

## 13. When To Use Heartbeats & Cron
- Pemantauan kesehatan server, sisa kuota API, dan uptime website 24 jam.
- Pengingat agenda kalender harian dan rutinitas penulisan laporan harian (*EOD Report*).

## 14. When NOT To Use
- Jangan gunakan cron untuk mendengarkan perubahan data real-time eksternal yang frekuensinya tinggi (gunakan **Inbound Webhooks** dari Module 02 sebagai gantinya).

## 15. Common Mistakes
1. **Heartbeat Mengirim Pesan Chat Setiap Interval**: Membanjiri ponsel pengguna dengan ratusan pesan *"Status OK"* per hari. Pesan obrolan hanya boleh dikirim saat ada anomali atau tindakan yang membutuhkan keputusan manusia!
2. **Tidak Memperhitungkan Perbedaan Zona Waktu (Timezone)**: Menyetel cron `0 8 * * *` di server VPS yang menggunakan waktu UTC. Jam 08:00 UTC adalah jam 15:00 sore di Jakarta (WIB)! Selalu set timezone eksplisit: `"timezone": "Asia/Jakarta"`.
3. **Panggilan LLM Berbiaya Mahal di Setiap Heartbeat**: Memanggil GPT-4o hanya untuk membaca angka disk space. Gunakan kode logika JavaScript biasa atau model gratis lokal untuk mengevaluasi ambang batas, dan gunakan LLM hanya saat menyusun kalimat peringatan.

## 16. Best Practices
- **Explicit Timezone Declaration**: Selalu sertakan zona waktu geografis Anda di konfigurasi scheduler.
- **Threshold Cooldown (Meredam Pengulangan Alarm)**: Jika server sedang down, jangan kirim alarm yang sama setiap 15 menit. Kirim alarm sekali, lalu tahan alarm berikutnya selama minimal 2 jam (*Alarm Deduplication & Throttling*).
- **Graceful Job Recovery**: Jika server sempat mati dan menyala kembali jam 08:15, scheduler harus cerdas mengecek apakah ada cron jam 08:00 yang terlewat (*missed job execution*).

## 17. Troubleshooting
- **Masalah: Cron job tidak berjalan pada waktu yang diharapkan**.
  - *Sebab*: Perbedaan zona waktu sistem operasi VPS (UTC vs WIB).
  - *Solusi*: Periksa waktu server dengan perintah terminal `date` dan konfigurasikan tzdata: `timedatectl set-timezone Asia/Jakarta`.

## 18. Hands-on Practice
Mari kita buktikan arsitektur Proactive Scheduler dengan membangun simulator Event Loop yang menjalankan Heartbeat senyap, mendeteksi anomali kritis, dan mengeksekusi Cron Morning Briefing di `hands-on/m01/cron_heartbeat_scheduler.js`.

## 19. Exercises & Challenge
- **Exercise**: Tuliskan ekspresi Cron untuk menjalankan tugas setiap hari Senin sampai Jumat tepat pukul 17:30 sore.  
  *(Jawaban: `30 17 * * 1-5`)*.
- **Challenge**: Rancang modul *Adaptive Heartbeat Frequency* yang otomatis menaikkan frekuensi pengecekan dari 15 menit menjadi 2 menit ketika beban CPU server terdeteksi mulai naik melebihi 75%.

## 20. Summary
Kemampuan proaktif adalah lompatan evolusioner yang mengubah OpenClaw dari sekadar alat bantu pasif menjadi rekan kerja mandiri sejati. Dengan memadukan **Silent Heartbeat** untuk pemantauan sistem tanpa polusi notifikasi dan **Scheduled Cron Jobs** untuk orkestrasi rutinitas harian, asisten AI Anda bekerja menjaga dan membantu produktivitas Anda tanpa henti 24 jam sehari.
