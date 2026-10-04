# EVALUASI BAB 01: Fondasi Skalabilitas & Metrik Sistem

Dokumen ini berisi rangkuman bab, kuis pemahaman, dan tantangan arsitektur (*Chapter Challenge*) untuk menguji kesiapan Anda sebelum melangkah ke **BAB 02: Edge Computing, DNS, & Jaringan Distribusi**.

---

## 📌 Chapter Summary (Rangkuman BAB 01)

Sepanjang BAB 01, Anda telah mempelajari 4 pilar dasar sistem terdistribusi:
1. **Module 01 (Skalabilitas):** Membedakan Scale Up vs Scale Out, mendeteksi 4 bottleneck sistem (CPU, Memory, Disk, Network), Hukum Amdahl, dan syarat mutlak *Stateless Backend*.
2. **Module 02 (Metrik Kinerja):** Bahaya ilusi rata-rata (*the flaw of averages*), pembacaan Percentiles (p50, p95, p99), formula antrean Hukum Little ($L = \lambda \times W$), serta trade-off Latency vs Throughput (*batching*).
3. **Module 03 (Keandalan & Availability):** Menghitung toleransi downtime (*The Nines*), kontrak SLI/SLO/SLA, pengelolaan Error Budget untuk stabilitas tim SRE, serta perbandingan Active-Passive vs Active-Active.
4. **Module 04 (Teori Terdistribusi):** Memahami keniscayaan partisi jaringan fisik ($P$), trade-off mutlak antara CP vs AP, pemodelan perilaku normal PACELC, serta formula konsensus Quorum ($W + R > N$).

---

## 📝 BAB 01 QUIZ (Uji Pemahaman)

Kerjakan kuis di bawah ini secara mandiri sebelum melihat kunci evaluasi.

### Bagian A: Soal Fundamental (Basic)
1. Apa perbedaan arsitektural mendasar antara *Scale Up* dan *Scale Out*?
2. Mengapa server aplikasi yang menyimpan data session di memori lokal (`req.session`) akan gagal saat di-scale out secara horizontal?
3. Apa perbedaan antara metrik p50 (median) dan p99 (99th percentile)?
4. Jika SLA menjanjikan 99.9% availability per bulan (30 hari), berapa menit batas maksimal downtime yang diizinkan?
5. Mengapa dalam sistem terdistribusi riil di dunia nyata, arsitek tidak bisa memilih kombinasi "CA" pada CAP Theorem?

### Bagian B: Soal Menengah (Intermediate)
6. Sebuah API menerima 1.000 requests per detik (RPS). Rata-rata response time database query adalah 150 ms (0.15 detik). Berdasarkan **Hukum Little**, berapa jumlah koneksi database simultan minimum yang harus ditampung sistem?
7. Jelaskan konsep **Error Budget** dan bagaimana perannya dalam mengontrol kecepatan deployment fitur baru bagi tim software engineering!
8. Apa yang dimaksud dengan fenomena **Split-Brain** pada arsitektur database Active-Passive, dan bagaimana cara mencegahnya?
9. Bagaimana formula Quorum Consensus ($W + R > N$) menjamin tercapainya **Strong Consistency** meskipun beberapa node mengalami keterlambatan replikasi?
10. Berdasarkan **PACELC Theorem**, apa yang dikorbankan oleh sistem bertipe **PA/EL** saat jaringan berjalan dalam kondisi normal (tanpa partisi)?

### Bagian C: Scenario-Based Questions (Studi Kasus Arsitektur)
11. **Skenario 1 (Tail Latency di Microservices):**  
    Sebuah halaman e-commerce memanggil 25 microservices secara paralel di belakang API Gateway. Setiap microservice memiliki p99 = 99% (hanya 1% kemungkinan lambat). Mengapa lebih dari 20% pengguna akhir melaporkan halaman tersebut loading sangat lambat? Tunjukkan perhitungannya!
12. **Skenario 2 (Kasus Finansial vs Media Sosial):**  
    Anda ditugaskan merancang dua sistem:
    - Sistem A: Transfer Saldo Dompet Digital antar-pengguna.
    - Sistem B: Counter Jumlah Penonton Live Streaming Konser Musik.  
    Tentukan apakah Sistem A dan Sistem B harus mengadopsi karakteristik **CP** atau **AP**, dan berikan analisis trade-off bisnisnya!
13. **Skenario 3 (Investasi Hardware vs Optimasi Kode):**  
    Sebuah aplikasi backend monolitik berjalan lambat pada CPU 90%. Manajemen berencana melipatgandakan server dari 8 core menjadi 32 core (Scale Up seharga $2.000/bulan). Setelah di-profiling, ternyata 60% waktu eksekusi kode terblokir pada satu lock tabel database secara berurutan (*serial execution*). Berdasarkan **Hukum Amdahl**, mengapa penambahan core tersebut tidak akan menghasilkan peningkatan kecepatan yang signifikan?

---

## 🏆 CHAPTER CHALLENGE: Merancang Baseline Backend High Availability

### Misi Arsitek:
Rancang arsitektur level sistem (blok diagram teks atau ASCII) untuk backend layanan otentikasi login pengguna yang melayani **5.000 login requests/detik** dengan target SLO **99.99% Availability** (*Four Nines*).

### Syarat & Batasan Desain:
1. Layanan tidak boleh memiliki *Single Point of Failure (SPOF)* pada lapisan web server, database, maupun caching.
2. Pengguna tidak boleh tiba-tiba logout meskipun salah satu web server crash di tengah sesi.
3. Database utama tidak boleh mengalami Split-Brain saat terjadi pemutusan jaringan antar-zona.
4. Jelaskan bagaimana alur request dari pengguna (Client) melewati DNS, Load Balancer, Web App Cluster, Session Store terdistribusi, hingga Database Primary-Replica.

---

## ✅ Knowledge Checklist BAB 01

Periksa apakah Anda telah menguasai seluruh ceklis berikut:
- [ ] Mampu mendeteksi bottleneck sistem pada 4 komponen: CPU, RAM, Disk, Jaringan.
- [ ] Memahami alasan mengapa backend wajib *Stateless* sebelum di-scale horizontal.
- [ ] Mampu menghitung kapasitas sistem menggunakan Hukum Little ($L = \lambda \times W$).
- [ ] Mampu membaca grafik percentiles latensi (p50, p95, p99).
- [ ] Menguasai batas toleransi downtime untuk Three Nines (99.9%) dan Four Nines (99.99%).
- [ ] Menguasai cara kerja Error Budget dan pencegahan Split-Brain.
- [ ] Menguasai kompromi CAP Theorem (CP vs AP) dan PACELC Theorem.
- [ ] Mampu menjalankan dan memverifikasi script pengujian lab di folder `hands-on/`.
