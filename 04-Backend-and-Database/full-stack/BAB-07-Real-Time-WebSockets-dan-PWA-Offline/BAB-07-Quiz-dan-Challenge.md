---
[⬅️ Module 02: PWA, Service Workers, & Offline-First](./Module-02-PWA-Service-Workers-Offline-First-dan-Web-Push.md) | [📋 Silabus Induk](../README.md) | [BAB 08: Keamanan Full-Stack Defensif (OWASP) ➡️](../BAB-08-Keamanan-Full-Stack-Defensif-OWASP/Module-01-XSS-CSP-Nonces-CSRF-dan-Clickjacking-Defense.md)
---

# BAB 07: Evaluasi Pembelajaran — Quiz, Challenge, & Knowledge Check

## 1. Uji Pemahaman Mandiri (Quiz)

### A. Soal Tingkat Dasar (Basic Questions)
1. **Apa perbedaan mendasar antara protokol WebSocket (`wss://`) dan Server-Sent Events (SSE) dalam hal arah komunikasi data?**
2. **Mengapa serverless functions (seperti AWS Lambda) tidak cocok digunakan secara langsung untuk mempertahankan koneksi WebSocket yang berumur panjang?**
3. **Bagaimana peran Redis Pub/Sub dalam memungkinkan komunikasi antar pengguna yang terhubung ke instance server WebSocket yang berbeda?**
4. **Apa fungsi utama dari skrip Service Worker pada arsitektur Progressive Web Apps (PWA)? Di thread mana Service Worker dieksekusi?**
5. **Jelaskan perbedaan mendasar antara strategi caching *Cache-First* dan *Network-First* pada Cache API browser!**

---

### B. Soal Tingkat Menengah (Intermediate Questions)
6. **Mengapa kita wajib menambahkan *Random Jitter* pada algoritma *Exponential Backoff* saat klien mencoba melakukan rekoneksi ke server WebSocket yang baru saja pulih?**
7. **Bagaimana mekanisme Heartbeat (frame Ping dan Pong) mencegah terjadinya masalah *Zombie Sockets* pada router NAT dan firewall publik?**
8. **Jelaskan cara kerja strategi caching *Stale-While-Revalidate* (SWR) dan mengapa strategi ini sangat disukai untuk meningkatkan skor Core Web Vitals!**
9. **Bagaimana IndexedDB dan Background Sync API bekerja sama untuk memastikan bahwa data yang di-submit saat perangkat offline tidak hilang begitu saja?**
10. **Apa fungsi dari kunci kriptografi VAPID (Voluntary Application Server Identification) pada protokol pengiriman Web Push Notifications?**

---

### C. Soal Berbasis Skenario Arsitektur (Scenario-Based Questions)
11. **Skenario Kasus — Collaborative Real-Time Document Editing (Conflict Resolution)**:
    Dua pengguna (User A dan User B) sedang mengedit dokumen yang sama di sebuah web app seperti Google Docs / Notion. Keduanya mengedit paragraf yang sama secara serentak dalam milidetik yang sama. Mengapa pendekatan *Last-Write-Wins* (LWW) tradisional sangat buruk untuk kasus ini, dan bagaimana algoritma modern seperti **CRDT (Conflict-free Replicated Data Types)** atau **Operational Transformation (OT)** menyelesaikan konflik data ini secara otomatis?
12. **Skenario Kasus — Service Worker Cache Invalidation Nightmare**:
    Sebuah tim engineer merilis perbaikan bug kritis pada file JavaScript frontend `app.js`. Namun, 40% pengguna aktif melaporkan bahwa mereka masih melihat tampilan lama yang rusak selama berminggu-minggu. Analisis kesalahan konfigurasi Service Worker apa yang menyebabkan hal ini terjadi, dan bagaimana solusinya?
13. **Skenario Kasus — E-Commerce Flash Sale Push Notification Delivery**:
    Sebuah toko online ingin mengirimkan push notification promo kilat ke 2.000.000 pengguna terdaftar secara serentak pada pukul 10:00:00. Jika server mengirimkan request Web Push satu per satu secara sinkron, banyak pengguna baru akan menerima notifikasi 3 jam kemudian saat promo sudah berakhir. Rancang arsitektur pipeline antrean pesan (Message Queue) yang mampu mendistribusikan 2 juta push notification dalam waktu kurang dari 60 detik!

---

## 2. Chapter Challenge: Offline-First Real-Time Chat System

### Deskripsi Tantangan
Anda diminta merancang arsitektur aplikasi perpesanan instan yang menggabungkan kapabilitas **Real-Time WebSockets** saat online dan **Offline-First Resilience** saat koneksi seluler terputus.

### Kebutuhan & Spesifikasi:
1. **Dual-Mode Transport Switch**:
   - Saat ada koneksi internet aktif, pesan dikirimkan secara langsung melalui WebSocket yang terhubung ke kluster multi-node Redis Pub/Sub.
   - Saat koneksi internet terputus (`navigator.onLine === false`), tangkap pesan baru di sisi client, tandai statusnya sebagai `PENDING_SYNC`, dan simpan ke dalam `IndexedDB`.
2. **Optimistic Local UI**:
   - Tampilkan pesan di layar seketika dengan icon jam pasir abu-abu saat offline, sehingga pengguna merasa aplikasi tetap responsif tanpa hambatan.
3. **Automatic Drain & Reconciliation**:
   - Begitu koneksi internet pulih, Service Worker atau client sync manager harus menguras antrean IndexedDB secara berurutan, mengirimkan pesan ke server, dan memperbarui status pesan menjadi `DELIVERED` (centang ganda hijau).
4. **Distributed Presence**:
   - Implementasikan sistem presensi status online/offline pengguna menggunakan Redis Key ber-TTL 45 detik yang di-refresh secara berkala oleh heartbeat WebSocket.

---

## 3. Knowledge Check & Mastery Checklist

### Yang Wajib Anda Pahami:
- [ ] Kapan harus memilih WebSockets vs Server-Sent Events vs Polling.
- [ ] Mengapa Redis Pub/Sub mutlak dibutuhkan saat menskalakan WebSocket melintasi beberapa node server.
- [ ] Arsitektur Service Worker sebagai perantara proxy programmable di browser pengguna.
- [ ] Strategi caching: Cache-First, Network-First, dan Stale-While-Revalidate.
- [ ] Alur kerja Offline-First menggunakan IndexedDB dan Background Sync.

### Yang Tidak Perlu Anda Hafal di Luar Kepala:
- Derivasi bitwise header WebSocket frame (RFC 6455 opcode, masking key)—telah ditangani secara native oleh modul `ws` atau browser.
- Format biner spesifikasi enkripsi Web Push RFC 8291 (telah diotomatisasi oleh pustaka `web-push`).

### Yang Harus Bisa Anda Lakukan:
- [ ] Membangun server WebSocket di Node.js yang terhubung dengan Redis Pub/Sub channel adapter.
- [ ] Mengimplementasikan algoritma rekoneksi client yang tahan banting (*exponential backoff with jitter*).
- [ ] Menulis Service Worker kustom untuk caching aset statis dan offline fallback.
- [ ] Mengirimkan Web Push Notifications menggunakan VAPID keys.

---

## 4. Ringkasan Bab (Chapter Summary)
Bab 07 telah mengantarkan Anda menguasai dua pilar interaktivitas mutakhir dalam ekosistem full-stack modern:
1. **Real-Time Architecture** (WebSockets, SSE, dan Redis Pub/Sub) memangkas latensi pertukaran data hingga ke batas milidetik, memungkinkan pengalaman kolaboratif tanpa jeda.
2. **Progressive Web Apps (PWA) & Offline-First** membebaskan aplikasi web dari ketergantungan mutlak pada koneksi internet, mengubah browser menjadi runtime aplikasi yang tangguh, cepat, dan selalu siap melayani pengguna di mana pun mereka berada.

Dengan aplikasi yang interaktif dan tahan banting, kita kini siap melangkah ke ranah yang sangat krusial bagi kelangsungan sistem produksi: **BAB 08: Keamanan Full-Stack Defensif (OWASP Web & API Top 10)**!

---
[⬅️ Module 02: PWA, Service Workers, & Offline-First](./Module-02-PWA-Service-Workers-Offline-First-dan-Web-Push.md) | [📋 Silabus Induk](../README.md) | [BAB 08: Keamanan Full-Stack Defensif (OWASP) ➡️](../BAB-08-Keamanan-Full-Stack-Defensif-OWASP/Module-01-XSS-CSP-Nonces-CSRF-dan-Clickjacking-Defense.md)
---
