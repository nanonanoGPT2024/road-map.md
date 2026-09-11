# BAB 05 — Evaluasi, Quiz, & Chapter Challenge
## Ekosistem Skills, ClawHub, & Model Context Protocol (MCP)

---

## 🎯 Ringkasan Bab

Dalam Bab ini, kita telah memberdayakan agen OpenClaw dengan kapabilitas fungsional tindakan nyata:
1. **Ekosistem Skills & ClawHub**: Memahami struktur berkas manifest `skill.json`, penulisan handler runtime terisolasi, validasi parameter via JSON Schema, dan manajemen paket komunitas melalui ClawHub registry.
2. **Model Context Protocol (MCP)**: Mengadopsi standar industri terbuka dari Anthropic yang menghubungkan OpenClaw dengan ratusan server data dan tools eksternal (PostgreSQL, GitHub, Filesystem) melalui protokol JSON-RPC 2.0 (`stdio` dan `SSE`).

---

## 🧠 Knowledge Check

### Saya Harus Memahami:
- [ ] Perbedaan antara LLM murni (prediksi teks) dan AI Agent dengan Tool Calling (kemampuan eksekusi tindakan nyata).
- [ ] Anatomi berkas `skill.json`: pentingnya deskripsi yang jelas agar LLM memahami kapan harus memanggil skill.
- [ ] Arsitektur Model Context Protocol (MCP): peran MCP Host, MCP Client, dan MCP Server.
- [ ] Perbedaan mekanisme transport MCP: `stdio` (subprocess lokal) vs `SSE` (remote HTTP stream).
- [ ] Mengapa MCP Server database wajib menggunakan kredensial *Read-Only* untuk mencegah manipulasi data yang tidak disengaja.

### Saya Tidak Perlu Menghafal:
- Kode spesifik integer error JSON-RPC (`-32601`, `-32600`).
- Seluruh daftar argumen CLI dari ratusan MCP Server yang ada di open source.

### Saya Harus Bisa Melakukan:
- [ ] Menulis dan mendaftarkan custom skill mandiri ke dalam OpenClaw.
- [ ] Mengonfigurasi file `config.json` untuk menghubungkan server MCP eksternal.
- [ ] Menangani validasi skema parameter untuk mencegah kegagalan eksekusi tool.

---

## ❓ Quiz Evaluasi

### Bagian A: Pertanyaan Konseptual Fundamental (5 Soal)
1. **Apa perbedaan mendasar antara Native OpenClaw Skill dan MCP Server?**
2. **Apa yang dilakukan oleh OpenClaw Gateway saat menerima method `tools/list` dari protokol MCP?**
3. **Mengapa penulisan deskripsi pada `skill.json` sangat menentukan apakah LLM akan memanggil tool tersebut atau tidak?**
4. **Apa fungsi dari transport `stdio` dalam protokol MCP?**
5. **Sebutkan tiga primitif kapabilitas yang dapat diekspos oleh sebuah MCP Server.**

### Bagian B: Analisis & Intermediate (5 Soal)
6. **Jika sebuah skill membutuhkan akses ke internet untuk memanggil API cuaca, mengapa izin `network:outbound` harus dideklarasikan secara eksplisit di manifest?**
7. **Jelaskan bahaya keamanan jika Anda menghubungkan MCP Server PostgreSQL dengan user `postgres` (superuser) ke bot OpenClaw Anda.**
8. **Bagaimana MCP Client di OpenClaw memvalidasi argumen yang dihasilkan oleh LLM sebelum mengirimkannya ke MCP Server?**
9. **Mengapa menjalankan terlalu banyak MCP Server berbasis subprocess `stdio` di server VPS kecil dapat menyebabkan kehabisan memori RAM?**
10. **Apa perbedaan peran antara *Tools* dan *Resources* dalam spesifikasi Model Context Protocol?**

### Bagian C: Scenario-Based System Architecture (3 Soal)
11. **Skenario 1: Automasi DevOps Pull Request di GitHub via Telegram**  
   Developer ingin mereview dan melakukan merge PR GitHub langsung dari ponsel melalui bot Telegram OpenClaw.
   - MCP Server apa yang Anda integrasikan ke OpenClaw?
   - Token otentikasi apa yang dibutuhkan dan scope izin minimal apa yang harus diberikan pada GitHub Personal Access Token tersebut?

12. **Skenario 2: Skill Pemantauan IoT Smart Home Lokal**  
   Pengguna ingin mengendalikan saklar lampu dan suhu AC rumah (Home Assistant) via chat WhatsApp.
   - Apakah Anda akan membuat Custom Skill lokal atau MCP Server? Jelaskan alasan trade-off-nya.
   - Bagaimana Anda memastikan perintah menyalakan AC tidak bisa diakses oleh tamu yang masuk ke grup WhatsApp keluarga?

13. **Skenario 3: Mitigasi Serangan Tool Poisoning**  
   Sebuah skill buatan pihak ketiga dari internet diinstal ke OpenClaw. Di dalam kode handlernya, script tersebut diam-diam membaca file `.env` dan mengirimkannya ke server asing.
   - Lapisan perlindungan keamanan apa di OpenClaw yang harus membatasi akses sistem file dan network outbound dari skill pihak ketiga tersebut?

---

## 🏆 Chapter Challenge: Database BI Reporter Agent via MCP

### Problem Statement
Integrasikan MCP Database Server ke OpenClaw untuk menciptakan asisten Business Intelligence pribadi:
1. Hubungkan OpenClaw ke database SQLite transaksi lokal via MCP Server.
2. Terapkan guardrail: hanya izinkan query `SELECT` (tolak mentah-mentah jika ada kata `INSERT`, `UPDATE`, `DELETE`, `DROP`).
3. Pengguna dapat bertanya di Telegram: *"Berapa total omzet penjualan kita minggu ini?"*.
4. Agen secara mandiri memeriksa skema tabel, menyusun query SQL agregasi, memanggil MCP tool, dan merender grafik batang ASCII sederhana di chat balasan.
