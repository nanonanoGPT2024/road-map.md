# Module 01: Menggunakan ClawHub & Membuat Custom Skills

## 1. Learning Objective
Setelah menyelesaikan modul ini, Anda akan mampu:
- Memahami konsep **Skills Engine** dalam memperluas kemampuan fungsional agen OpenClaw melampaui percakapan teks biasa.
- Menginstal dan mengelola paket skill komunitas dari registry **ClawHub** (`openclaw skill install`).
- Membedah anatomi struktur berkas sebuah skill: *Manifest Metadata*, *JSON Schema Parameters*, dan *Execution Handler*.
- Menulis, menguji, dan mempublikasikan **Custom Skill** buatan sendiri menggunakan JavaScript/Node.js atau Python.

## 2. Prerequisite
- Memahami dasar pemrograman JavaScript / Node.js (fungsi async, export module) atau Python.
- Memahami format spesifikasi data JSON Schema.

## 3. Concept
Tanpa alat (*Tools* atau *Skills*), model AI tercanggih sekalipun hanyalah sebuah mesin prediksi teks yang terisolasi di dalam kotak. Model tidak tahu harga Bitcoin saat ini, tidak bisa memeriksa apakah ada email baru, dan tidak bisa mematikan lampu pintar di rumah Anda.

**Skills** adalah modul kapabilitas yang memberikan agen kemampuan untuk mengambil tindakan nyata di dunia fisik dan digital (*Agency & Tool Use*).  
OpenClaw menyediakan dua jalur untuk memanfaatkan skills:
1. **ClawHub**: Registry terpusat (mirip NPM atau GitHub Marketplace) tempat ribuan developer membagikan skill siap pakai (misal: *Google Calendar Sync*, *Spotify Controller*, *Crypto Tracker*, *Home Assistant*).
2. **Local Custom Skills**: Direktori lokal (`~/.openclaw/skills/`) tempat Anda dapat menulis script fungsional khusus untuk kebutuhan privat Anda sendiri.

## 4. Why?
- **Otomasi Tindakan Nyata**: Mengubah agen dari sekadar "teman mengobrol" menjadi "rekan kerja operasional" yang mampu mengeksekusi API, database, dan IoT.
- **Ekosistem Modular & Reusable**: Anda tidak perlu menulis ulang kode integrasi cuaca atau integrasi GitHub; cukup instal modul yang sudah diuji oleh komunitas.
- **Isolasi Logika Bisnis**: Kode penanganan API pihak ketiga terpisah rapi dari logika inti prompt LLM.

## 5. What?
### 1. Anatomi Sebuah Skill OpenClaw:
Sebuah skill OpenClaw tersimpan dalam satu folder mandiri:
```text
~/.openclaw/skills/crypto-ticker/
│
├── skill.json         (Manifest: Nama, deskripsi untuk LLM, parameter schema, izin)
├── index.js           (Script eksekusi runtime: memanggil API, memproses data)
└── README.md          (Dokumentasi panduan penggunaan)
```

### 2. Format Berkas Manifest `skill.json`:
```json
{
  "name": "crypto_ticker",
  "version": "1.0.0",
  "description": "Mengambil harga mata uang kripto terkini (Bitcoin, Ethereum, Solana) dalam Rupiah atau USD.",
  "author": "budi@developer.com",
  "permissions": ["network:outbound"],
  "parameters": {
    "type": "object",
    "properties": {
      "coin": {
        "type": "string",
        "description": "Simbol koin, misal: BTC, ETH, SOL",
        "enum": ["BTC", "ETH", "SOL"]
      },
      "currency": {
        "type": "string",
        "description": "Mata uang target, default: IDR",
        "default": "IDR"
      }
    },
    "required": ["coin"]
  }
}
```

## 6. How?
### Menggunakan Perintah CLI ClawHub:
1. **Mencari Skill di Marketplace**:
   ```bash
   openclaw skill search weather
   ```
2. **Menginstal Skill dari ClawHub**:
   ```bash
   openclaw skill install @clawhub/google-calendar
   openclaw skill install @clawhub/system-metrics
   ```
3. **Melihat Daftar Skill yang Terpasang**:
   ```bash
   openclaw skill list
   ```
4. **Menghapus Skill**:
   ```bash
   openclaw skill uninstall @clawhub/system-metrics
   ```

### Alur Eksekusi Skill oleh Agen:
```text
[User Chat di Telegram] ──> "Berapa harga Bitcoin sekarang bro?"
                                    │
                                    ▼ 1. LLM Membaca Manifest Skill yang Tersedia
                         [LLM Reasoning & Function Selection]
                         Pilihan: Panggil tool 'crypto_ticker' dengan argumen: { coin: "BTC" }
                                    │
                                    ▼ 2. Gateway Memvalidasi Parameter (JSON Schema Check)
                         [Security & Schema Validator]
                                    │
                                    ▼ 3. Jalankan index.js: handler({ coin: "BTC" })
                         [Sandbox Runner] ──> Panggil API CoinGecko
                                    │
                                    ▼ 4. Kembalikan Output Data: { price: "Rp 1.450.000.000" }
                         [LLM Response Formatter]
                                    │
                                    ▼
[User Chat di Telegram] <── "Harga Bitcoin (BTC) saat ini berada di Rp 1.450.000.000."
```

## 7. Analogy
- **LLM Tanpa Skill = Ahli Bedah Hebat Tanpa Peralatan**: Dokter bedah tahu persis cara mengoperasi pasien di otaknya, tetapi dia tidak memiliki pisau bedah, gunting medis, atau mikroskop di tangannya.
- **Skills = Tas Peralatan Medis Lengkap**: Memberikan alat spesifik ke tangan dokter bedah sehingga keahliannya dapat diwujudkan menjadi tindakan nyata.
- **ClawHub = Toko Penyedia Perkakas Resmi**: Tempat dokter membeli peralatan baru yang sudah bersertifikat standar keamanan.

## 8. Diagram

```text
================ SIKLUS HIDUP EKSEKUSI SKILL ================

               [System Prompt LLM]
             (Membawa daftar deklarasi
              seluruh skill.json aktif)
                        │
                        ▼ (User: "Cek harga BTC")
           [LLM Menghasilkan Tool Call]
          `tool: crypto_ticker, args: { coin: 'BTC' }`
                        │
                        ▼
           [OpenClaw Tool Dispatcher]
                        │
            ┌───────────┴───────────┐
            ▼                       ▼
    [Validasi Skema]        [Pengecekan Izin]
    (JSON Schema OK?)       (Network Outbound diizinkan?)
            │                       │
            └───────────┬───────────┘
                        ▼
              [Jalankan index.js]
                        │
                        ▼
         [Kembalikan Hasil JSON ke LLM]
                        │
                        ▼
           [Balasan Final ke Pengguna]
```

## 9. Simple Example: Handler Script `index.js`
```javascript
// index.js
module.exports = async function handler(args) {
  const { coin, currency = "IDR" } = args;
  
  // Simulasi fetch harga
  const mockPrices = {
    BTC: { IDR: 1450000000, USD: 92000 },
    ETH: { IDR: 52000000, USD: 3300 },
    SOL: { IDR: 3200000, USD: 205 }
  };

  const price = mockPrices[coin] ? mockPrices[coin][currency] : null;
  if (!price) {
    throw new Error(`Data harga untuk ${coin} tidak ditemukan.`);
  }

  return {
    success: true,
    coin,
    currency,
    priceFormatted: price.toLocaleString("id-ID"),
    timestamp: new Date().toISOString()
  };
};
```

## 10. Practical Example: Skill dengan Izin Khusus (Dangerous Permissions)
Sebuah skill yang memodifikasi sistem file atau menjalankan bash script harus secara eksplisit mendeklarasikan izin berbahaya di `skill.json`:
```json
{
  "name": "docker_manager",
  "permissions": ["system:exec", "docker:socket"],
  "requiresConfirmation": true
}
```
Ketika LLM memanggil skill ini, OpenClaw **tidak langsung mengeksekusinya**, melainkan mengirimkan notifikasi ke Telegram pemilik:
*"⚠️ OpenClaw ingin menjalankan: `docker restart redis_cluster`. Apakah Anda mengizinkan? [Ya/Tidak]"*.

## 11. Real World Example
- **Automasi Server Maintenance dari Ranjang Tidur**: Developer membuat custom skill `github_deploy`. Ketika ada laporan bug di malam hari, developer mengirim voice note di Telegram: *"Tolong deploy hotfix commit terbaru ke server staging"*. Agen memicu GitHub workflow via skill, menunggu tes selesai, dan melaporkan hasilnya dalam 3 menit.

## 12. Trade-offs

| Pendekatan | Kecepatan Integrasi | Fleksibilitas | Keamanan |
|---|---|---|---|
| **ClawHub Community Skills** | Sangat Cepat (1 baris perintah) | Terbatas pada fitur pembuatnya | Perlu diaudit sebelum instalasi |
| **Custom Local Skills** | Butuh waktu menulis kode | **100% Sesuai Kebutuhan Spesifik**| **100% Terkontrol Sendiri** |

## 13. When To Use Skills
- Setiap kali agen membutuhkan akses ke data real-time (harga saham, cuaca, tiket pesawat).
- Menghubungkan agen ke API internal kantor, database SQL, atau perangkat smart home (IoT).

## 14. When NOT To Use Skills
- Tugas yang murni membutuhkan penalaran teks (menerjemahkan bahasa, menulis puisi, merangkum dokumen yang sudah ada di konteks obrolan).

## 15. Common Mistakes
1. **Deskripsi Skill Terlalu Singkat atau Ambigu**: Menulis deskripsi `"Mengambil data"` di `skill.json`. LLM tidak akan tahu kapan harus memanggil skill ini! Tulis deskripsi yang jelas dan spesifik: *"Mengambil status kesehatan CPU, RAM, dan sisa disk server produksi"*.
2. **Tidak Menangani Error Handling di Script Handler**: Ketika API pihak ketiga mengembalikan status 500 dan script melempar uncaught exception, seluruh proses daemon bisa mengalami crash. Selalu bungkus kode dengan blok `try-catch`.
3. **Mengabaikan Validasi Input**: Mempercayai argumen dari LLM tanpa memvalidasi tipe data, membuka celah injeksi perintah jika argumen tersebut diteruskan ke shell command.

## 16. Best Practices
- **Strict Parameter Schema**: Selalu tentukan `enum`, `default`, dan tipe data yang ketat pada `parameters` di `skill.json`.
- **Return Data Terstruktur & Ringkas**: Jangan kembalikan raw HTML 10 MB ke LLM; parse dan kembalikan hanya field-field penting dalam bentuk JSON ringkas untuk menghemat context window.
- **Terapkan Timeout**: Beri batas waktu eksekusi maksimal (misal: 10 detik) pada setiap panggilan API luar di dalam skill handler.

## 17. Troubleshooting
- **Masalah: LLM tidak pernah memanggil skill yang baru dibuat**.
  - *Sebab*: Nama skill mengandung karakter non-alphanumeric, atau deskripsi skill tidak relevan dengan kata kunci pertanyaan pengguna.
  - *Solusi*: Pastikan nama skill hanya menggunakan huruf kecil dan underscore (misal: `get_server_status`), dan perjelas kalimat deskripsi di `skill.json`.

## 18. Hands-on Practice
Mari kita buktikan cara kerja Skills Engine OpenClaw dengan membangun sebuah Custom Skill Crypto Ticker mandiri, memvalidasi schema, dan mengeksekusi handlernya di `hands-on/m01/custom_skill_authoring.js`.

## 19. Exercises & Challenge
- **Exercise**: Tuliskan deklarasi skema JSON Schema untuk skill `send_sms` yang mewajibkan parameter `phone_number` (format string regex angka) dan `message` (string maksimal 160 karakter).
- **Challenge**: Rancang custom skill `backup_folder` yang menerima path direktori lokal, mengompresnya menjadi berkas `.zip`, lalu mengembalikan ukuran file hasil kompresi dan lokasi penyimpanan.

## 20. Summary
Skills adalah otot dan tangan bagi otak AI OpenClaw Anda. Melalui perpaduan registry komunitas **ClawHub** untuk instanitas kapabilitas dan **Custom Local Skills** untuk automasi privat, Anda dapat memberdayakan agen Anda untuk mengendalikan API, server, dan alur kerja digital Anda secara mandiri dan aman.
