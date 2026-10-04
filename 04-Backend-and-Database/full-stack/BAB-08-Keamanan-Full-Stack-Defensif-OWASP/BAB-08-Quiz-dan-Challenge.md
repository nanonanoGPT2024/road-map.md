---
[⬅️ Module 02: SSRF & Server Action Defense](./Module-02-SSRF-Server-Action-Tampering-dan-CORS-Isolation.md) | [📋 Silabus Induk](../README.md) | [BAB 09: Pengujian Full-Stack (E2E) & Observabilitas ➡️](../BAB-09-Testing-E2E-Playwright-dan-Observabilitas/Module-01-Playwright-E2E-Automation-dan-Component-Testing.md)
---

# BAB 08: Evaluasi Pembelajaran — Quiz, Challenge, & Knowledge Check

## 1. Uji Pemahaman Mandiri (Quiz)

### A. Soal Tingkat Dasar (Basic Questions)
1. **Apa perbedaan antara Stored XSS, Reflected XSS, dan DOM-based XSS? Mana yang memiliki dampak paling merusak pada aplikasi komunitas?**
2. **Mengapa penggunaan nonce dinamis pada Content Security Policy (CSP) jauh lebih aman dibandingkan mengizinkan `'unsafe-inline'`?**
3. **Bagaimana serangan Clickjacking (UI Redressing) dilakukan dan bagaimana header `frame-ancestors 'none'` pada CSP membatalkannya?**
4. **Apa yang dimaksud dengan Server-Side Request Forgery (SSRF) dan mengapa alamat IP `169.254.169.254` menjadi target favorit para penyerang di lingkungan cloud?**
5. **Mengapa kita tidak boleh mempercayai React Server Actions sebagai fungsi privat yang kebal dari manipulasi parameter oleh client?**

---

### B. Soal Tingkat Menengah (Intermediate Questions)
6. **Jelaskan cara kerja serangan DNS Rebinding untuk mem-bypass filter SSRF sederhana yang hanya memvalidasi hostname pada saat input awal!**
7. **Bagaimana mekanisme verifikasi Origin dan Host header bawaan pada React Server Actions secara otomatis memitigasi serangan Cross-Site Request Forgery (CSRF)?**
8. **Mengapa standar keamanan web melarang keras penggunaan header `Access-Control-Allow-Origin: *` secara bersamaan dengan `Access-Control-Allow-Credentials: true`?**
9. **Jelaskan apa itu *Prototype Pollution* di JavaScript runtime, dan bagaimana seorang penyerang dapat mengeksploitasi fungsi deep-merge objek yang tidak higienis!**
10. **Apa perbedaan mendasar antara header `X-Frame-Options: DENY` dengan direktif CSP `frame-ancestors 'none'`? Mengapa browser modern lebih memprioritaskan direktif CSP?**

---

### C. Soal Berbasis Skenario Arsitektur (Scenario-Based Questions)
11. **Skenario Kasus — Webhook Consumer & Cloud Metadata Breach**:
    Sebuah platform SaaS menyediakan fitur "Integrasi Webhook Kustom", di mana pengguna dapat memasukkan URL endpoint mereka sendiri untuk menerima payload event. Seorang penyerang memasukkan URL `http://169.254.169.254/latest/meta-data/iam/security-credentials/production-role`. Rancang arsitektur sanitasi jaringan berlapis yang menjamin serverless function Anda tidak akan pernah bisa mengakses IP metadata cloud maupun subnet intranet internal!
12. **Skenario Kasus — Mass Assignment pada Checkout E-Commerce**:
    Sebuah Server Action dideklarasikan untuk memperbarui detail pesanan: `export async function updateOrder(orderId, data) { await db.orders.update(data).where(eq(orders.id, orderId)); }`. Penyerang membuka Network Tab, mencatat ID Server Action, dan menembakkan request POST via `curl` dengan menyuntikkan payload `{ price: 0, paymentStatus: "PAID" }`. Analisis mengapa bug ini terjadi dan tuliskan perbaikan kodenya menggunakan Zod dan otorisasi sesi server!
13. **Skenario Kasus — Dynamic CSP Nonce pada Server Component Caching**:
    Tim engineering Anda ingin menerapkan Full-Route Caching (SSG/ISR) di Next.js agar halaman artikel dimuat dalam 10ms dari CDN Edge. Namun, Anda juga wajib menerapkan CSP Nonce unik per request untuk mencegah XSS. Mengapa kedua kebutuhan ini saling bertolak belakang, dan bagaimana solusi arsitekturalnya (misalnya menggunakan CSP berbasis hash `'sha256-...'` atau memisahkan layout statis dengan middleware dynamic injection)?

---

## 2. Chapter Challenge: Defensive API Gateway & Secure Webhook Sandbox

### Deskripsi Tantangan
Anda ditugaskan merancang modul *Defensive Webhook Dispatcher & API Shield* untuk aplikasi SaaS berskala enterprise. Modul ini bertanggung jawab mengirimkan data webhook ke URL mitra pihak ketiga dengan jaminan keamanan 100%.

### Kebutuhan & Spesifikasi:
1. **Strict SSRF Resolution & Subnet Guard**:
   - Terima URL dari mitra (misal: `https://partner.com/webhook`).
   - Lakukan resolusi DNS sebelum koneksi dibuka. Jika IP menunjuk ke loopback (`127.0.0.0/8`), private subnet RFC 1918 (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), atau link-local metadata (`169.254.0.0/16`), tolak request seketika dan catat ke security audit log.
2. **DNS Rebinding Immunity (Socket Pinning)**:
   - Pastikan koneksi HTTP client mengunci (*pin*) IP hasil resolusi DNS awal saat membuka soket TCP, sehingga perubahan DNS mendadak di tengah jalan tidak dapat menipu server.
3. **Cryptographic Webhook Signature (HMAC-SHA256)**:
   - Sertakan header `X-Hub-Signature-256: sha256=<hmac>` pada setiap payload webhook yang dikirimkan, sehingga penerima dapat memverifikasi keaslian pengirim menggunakan secret key bersama.
4. **Timeout & Payload Bomb Guard**:
   - Batasi waktu tunggu respon webhook maksimal 3.000 milidetik dan batasi ukuran respon maksimal 512KB untuk mencegah *Denial-of-Service (DoS)* akibat respon berukuran raksasa.

---

## 3. Knowledge Check & Mastery Checklist

### Yang Wajib Anda Pahami:
- [ ] Varian serangan XSS dan bagaimana Content Security Policy (CSP) dengan cryptographic nonces menghentikannya.
- [ ] Bahaya Server-Side Request Forgery (SSRF) dan pentingnya memblokir rentang IP privat dan cloud metadata.
- [ ] Mengapa React Server Actions wajib diperlakukan sebagai antarmuka publik yang membutuhkan validasi Zod dan otorisasi sesi server penuh.
- [ ] Konfigurasi CORS yang aman dan bahaya memantulkan origin sembarangan dengan kredensial aktif.

### Yang Tidak Perlu Anda Hafal di Luar Kepala:
- Seluruh daftar bitwise mask IP (dapat diotomatisasi menggunakan pustaka standar seperti `ipaddr.js`).
- Daftar lengkap direktif Permissions-Policy browser (cukup sesuaikan dengan kebutuhan hardware aplikasi Anda).

### Yang Harus Bisa Anda Lakukan:
- [ ] Menulis konfigurasi Edge Middleware yang menerbitkan header CSP dengan dynamic cryptographic nonces.
- [ ] Mengamankan form Server Action dari serangan Mass Assignment menggunakan validasi Zod whitelist.
- [ ] Memvalidasi dan menyaring URL eksternal untuk mencegah kebocoran SSRF ke jaringan internal.
- [ ] Mengonfigurasi whitelist CORS yang aman untuk API multi-domain.

---

## 4. Ringkasan Bab (Chapter Summary)
Bab 08 telah membongkar sisi defensif paling penting dalam rekayasa perangkat lunak full-stack modern:
1. **Frontend Defense (XSS, CSP, CSRF, Clickjacking)** membangun benteng di browser pengguna, memastikan tidak ada kode ilegal yang dieksekusi atau antarmuka yang dibajak.
2. **Backend Defense (SSRF & Server Action Security)** menerapkan prinsip *Zero Trust* di server: setiap input dari client dan URL dari dunia luar diperiksa secara ketat sebelum disentuh oleh logika bisnis atau jaringan internal.

Dengan benteng keamanan yang kokoh di seluruh lini, kini kita siap melangkah ke **BAB 09: Pengujian Full-Stack (E2E), Observabilitas, & Web Vitals**, di mana kita akan memastikan aplikasi tidak hanya aman, tetapi juga teruji secara otomatis menggunakan Playwright dan terpantau performanya menggunakan OpenTelemetry!

---
[⬅️ Module 02: SSRF & Server Action Defense](./Module-02-SSRF-Server-Action-Tampering-dan-CORS-Isolation.md) | [📋 Silabus Induk](../README.md) | [BAB 09: Pengujian Full-Stack (E2E) & Observabilitas ➡️](../BAB-09-Testing-E2E-Playwright-dan-Observabilitas/Module-01-Playwright-E2E-Automation-dan-Component-Testing.md)
---
