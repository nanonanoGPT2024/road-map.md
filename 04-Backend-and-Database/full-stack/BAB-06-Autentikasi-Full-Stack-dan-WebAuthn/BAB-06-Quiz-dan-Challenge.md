---
[⬅️ Module 02: Passwordless WebAuthn & MFA](./Module-02-Passwordless-WebAuthn-Passkeys-TOTP-MFA.md) | [📋 Silabus Induk](../README.md) | [BAB 07: Real-Time WebSockets & PWA ➡️](../BAB-07-Real-Time-WebSockets-dan-PWA-Offline/Module-01-WebSockets-SSE-dan-Redis-PubSub-Clustering.md)
---

# BAB 06: Evaluasi Pembelajaran — Quiz, Challenge, & Knowledge Check

## 1. Uji Pemahaman Mandiri (Quiz)

### A. Soal Tingkat Dasar (Basic Questions)
1. **Mengapa menyimpan token otentikasi di dalam cookie dengan flag `HttpOnly` jauh lebih aman dibandingkan menyimpannya di `localStorage` browser?**
2. **Apa yang dimaksud dengan prefiks cookie `__Host-` dan batasan apa saja yang dipaksakan oleh browser ketika cookie menggunakan prefiks ini?**
3. **Mengapa alur OAuth 2.0 modern mewajibkan penggunaan PKCE (*Proof Key for Code Exchange*) bahkan untuk aplikasi web sisi server?**
4. **Apa perbedaan antara Seremoni Registrasi (*Attestation*) dan Seremoni Otentikasi (*Assertion*) pada standar FIDO2 / WebAuthn?**
5. **Mengapa Passkey secara fundamental bersifat kebal terhadap serangan phishing (*phishing-resistant*)?**

---

### B. Soal Tingkat Menengah (Intermediate Questions)
6. **Jelaskan bagaimana Edge Middleware mampu memverifikasi token sesi JWT tanpa perlu melakukan satu pun query jaringan ke database pusat!**
7. **Apa yang dimaksud dengan *Cookie Chunking* pada Auth.js, dan kondisi apa yang memicu browser membutuhkan mekanisme ini?**
8. **Bagaimana nilai `counter` pada kredensial WebAuthn berfungsi mencegah serangan *Replay Attack* saat transmisi data dicegat di jaringan publik?**
9. **Jelaskan cara kerja algoritma TOTP (RFC 6238) dan mengapa fungsi verifikasi di sisi server perlu menyertakan toleransi jendela waktu $\pm 1$ step (30 detik)!**
10. **Bandingkan kelebihan dan kekurangan antara arsitektur sesi *Stateless JWT* vs *Stateful Database Session* dalam konteks pembatalan sesi (*Session Revocation*)!**

---

### C. Soal Berbasis Skenario Arsitektur (Scenario-Based Questions)
11. **Skenario Kasus — Global Session Invalidation di Era Stateless JWT**:
    Seorang pengguna melaporkan bahwa laptop kerjanya tertinggal di kedai kopi umum. Pengguna mengakses smartphone-nya dan menekan tombol *"Logout dari Semua Perangkat"*. Jika aplikasi Anda menggunakan stateless JWT di Edge Middleware (tanpa query DB per request), bagaimana arsitektur Anda membatalkan token yang tersimpan di laptop tersebut seketika tanpa mengubah sistem menjadi stateful yang lambat?
12. **Skenario Kasus — Serangan Phishing pada Transaksi Perbankan**:
    Seorang penyerang mendaftarkan domain `https://bca-klik-secure.com` dan menyalin 100% tampilan antarmuka web perbankan resmi `https://klikbca.com`. Korban yang terkecoh mencoba melakukan login menggunakan Passkey TouchID. Jelaskan secara teknis di level protokol browser dan hardware TPM mengapa serangan phishing ini gagal secara otomatis!
13. **Skenario Kasus — Account Recovery Trap**:
    Sebuah aplikasi SaaS menerapkan kebijakan *Passwordless Murni* hanya dengan Passkeys. Seorang eksekutif perusahaan tidak sengaja menjatuhkan iPhone-nya ke laut dan tidak mengaktifkan iCloud Keychain sync. Rancang alur pemulihan akun (*Disaster Recovery Flow*) berlapis yang memungkinkan eksekutif tersebut memulihkan akses tanpa merusak prinsip *Zero Trust* keamanan sistem!

---

## 2. Chapter Challenge: Zero-Trust Step-Up Authentication Engine

### Deskripsi Tantangan
Anda diminta merancang modul *Step-Up Authentication Gateway* untuk aplikasi portal keuangan enterprise. Modul ini harus menerapkan pengamanan adaptif berbasis sensitivitas rute dan status biometrik pengguna.

### Kebutuhan & Spesifikasi:
1. **Tier 1: Sesi Standar (Low Risk)**:
   - Rute `/dashboard` dan `/invoices` hanya membutuhkan stateless cookie JWT (`HttpOnly`, `__Host-`) yang diverifikasi oleh Edge Middleware.
2. **Tier 2: Transaksi Sensitif (High Risk Step-Up)**:
   - Saat pengguna membuka rute `/transfers/authorize` atau `/settings/api-keys`, sistem harus memicu **Step-Up Challenge**.
   - Pengguna diwajibkan melakukan konfirmasi ulang menggunakan **Passkey Biometrik (WebAuthn)** atau memasukkan **6 digit kode TOTP Authenticator**.
3. **Short-Lived Elevated Privilege**:
   - Jika verifikasi Step-Up berhasil, terbitkan token hak akses sementara (*Elevated Token*) dengan masa aktif hanya **5 menit**.
   - Setelah 5 menit, rute sensitif akan otomatis meminta konfirmasi biometrik ulang jika diakses kembali.

---

## 3. Knowledge Check & Mastery Checklist

### Yang Wajib Anda Pahami:
- [ ] Anatomi cookie aman: `HttpOnly`, `Secure`, `SameSite`, dan prefiks `__Host-`.
- [ ] Mekanisme pertukaran token OAuth 2.0 PKCE (`code_verifier` dan `code_challenge`).
- [ ] Arsitektur kriptografi kunci publik asimetris WebAuthn / Passkeys.
- [ ] Standar waktu dan hashing TOTP (RFC 6238).

### Yang Tidak Perlu Anda Hafal di Luar Kepala:
- Derivasi matematika kurva eliptik ECDSA secp256r1 (cukup gunakan Web Crypto API atau modul Node.js `crypto`).
- Spesifikasi bitwise binary format CBOR / COSE pada WebAuthn attestation (telah ditangani oleh pustaka `@simplewebauthn`).

### Yang Harus Bisa Anda Lakukan:
- [ ] Mengonfigurasi Auth.js v5 dengan provider OAuth dan stateless JWT strategy.
- [ ] Menulis Edge Middleware Route Guard untuk melindungi rute privat dan rute admin berdasarkan peran (*RBAC*).
- [ ] Mengintegrasikan alur registrasi dan login Passkeys pada aplikasi frontend dan backend.
- [ ] Mengimplementasikan verifikasi TOTP MFA dengan toleransi drift waktu.

---

## 4. Ringkasan Bab (Chapter Summary)
Bab 06 telah mengupas tuntas arsitektur autentikasi dan manajemen sesi full-stack modern:
1. **Auth.js v5 & Universal Auth** memungkinkan pengelolaan otentikasi yang konsisten di seluruh lapisan arsitektur Next.js App Router.
2. **Stateless JWT dengan Edge Middleware** memberikan kombinasi terbaik antara keamanan tingkat tinggi (kebal XSS via cookie `HttpOnly`) dan kecepatan verifikasi sub-milidetik di CDN edge tanpa membebani database.
3. **Passkeys & FIDO2 WebAuthn** menandai era baru keamanan web: menyingkirkan kerentanan kata sandi dan memberikan proteksi phishing 100% berbasis biometrik perangkat keras.
4. **MFA (TOTP & Magic Links)** menjadi pilar pelengkap yang menjamin redundansi akses dan pemulihan akun yang tangguh.

Kini aplikasi Anda telah terlindungi dengan sistem otentikasi enterprise! Kita siap melanjutkan ke **BAB 07: Real-Time Systems, WebSockets, & PWA Offline-First**, di mana kita akan mempelajari komunikasi data dua arah real-time, Redis Pub/Sub clustering, dan kapabilitas aplikasi web yang tetap berfungsi tanpa koneksi internet!

---
[⬅️ Module 02: Passwordless WebAuthn & MFA](./Module-02-Passwordless-WebAuthn-Passkeys-TOTP-MFA.md) | [📋 Silabus Induk](../README.md) | [BAB 07: Real-Time WebSockets & PWA ➡️](../BAB-07-Real-Time-WebSockets-dan-PWA-Offline/Module-01-WebSockets-SSE-dan-Redis-PubSub-Clustering.md)
---
