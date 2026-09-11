---
[⬅️ Module 01: Auth.js & Secure Cookies](./Module-01-Authjs-Secure-Cookies-OAuth-Edge-Guards.md) | [📋 Silabus Induk](../README.md) | [BAB 06 Quiz & Challenge ➡️](./BAB-06-Quiz-dan-Challenge.md)
---

# Module 02: Passwordless Security: WebAuthn / Passkeys (FIDO2 Biometrics), Magic Links, & TOTP Multi-Factor

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Memahami alasan mendasar mengapa sistem autentikasi berbasis kata sandi (*passwords*) sedang ditinggalkan oleh industri (*The Death of Passwords*) akibat serangan *credential stuffing*, *phishing*, dan *data breaches*.
- Menguasai arsitektur dan prinsip kerja standar **FIDO2 / WebAuthn (Web Authentication API)** serta konsep **Passkeys** berbasis biometrik perangkat (Apple Touch ID / Face ID, Windows Hello, Android Fingerprint).
- Menganalisis mengapa Passkeys bersifat **kebal phishing (Phishing-Resistant)** karena terikat secara permanen pada domain asal (*Origin-Bound / Relying Party ID*).
- Memahami secara mendalam dua seremoni kriptografi WebAuthn: **Registration Ceremony (Attestation)** dan **Authentication Ceremony (Assertion)**.
- Mengimplementasikan **Time-Based One-Time Password (TOTP - RFC 6238)** sebagai lapisan Multi-Factor Authentication (MFA) cadangan menggunakan aplikasi authenticator (Google Authenticator, 1Password).
- Mengintegrasikan alur **Passwordless Magic Links** dengan masa aktif terbatas dan hashing token satu kali pakai (*single-use*).

---

## 2. Prerequisite
- Memahami dasar-dasar kriptografi asimetris (*Public-Private Key Pair*).
- Memahami modul autentikasi dan cookie session dari Module 01.
- Memahami Web APIs bawaan browser modern (`navigator.credentials`).

---

## 3. Concept
Selama lebih dari empat dekade, autentikasi web bergantung pada rahasia bersama (*Shared Secret*): kata sandi yang diketahui oleh pengguna dan disimpan (dalam bentuk hash bcrypt/argon2) oleh server.

Kelemahan fatal model ini adalah: jika pengguna memasukkan kata sandi ke dalam situs palsu (*phishing site* yang mirip aslinya), kata sandi tersebut langsung jatuh ke tangan penyerang.

**WebAuthn / Passkeys** membalikkan paradigma ini dengan mengadopsi **Kriptografi Kunci Publik Asimetris**:

```
[ PERANGKAT PENGGUNA ]                              [ SERVER APLIKASI ]
(Laptop / Smartphone)                               (Relying Party)
+------------------------------------------+        +--------------------------+
| Secure Enclave / TPM Hardware            |        | Database                 |
|                                          |        |                          |
| 🔑 Private Key (TIDAK PERNAH KELUAR DARI |        | 🔓 Public Key (Tersimpan |
|    CHIP HARDWARE, Dilindungi Biometrik)  |        |    Aman di Server)       |
+------------------------------------------+        +--------------------------+
                    ^                                            ^
                    | (Tanda Tangan Kriptografis Challenge)      |
                    +--------------------------------------------+
```

Ketika pengguna login:
1. Server mengirimkan string acak bernama **Challenge**.
2. Perangkat pengguna meminta otorisasi biometrik (sidik jari atau sensor wajah).
3. Chip keras (*Secure Enclave / TPM*) menandatangani challenge tersebut menggunakan **Private Key**.
4. Server memverifikasi tanda tangan digital tersebut menggunakan **Public Key** yang telah terdaftar.

**Private Key tidak pernah dikirimkan melalui jaringan internet**, dan server tidak pernah menyimpan kata sandi pengguna. Bahkan jika database server diretas 100%, penyerang hanya mendapatkan *Public Key* yang tidak berguna untuk login!

---

## 4. Why? (Mengapa Passkeys Kebal Terhadap Phishing?)
Ciri paling revolusioner dari Passkeys adalah sifatnya yang **Origin-Bound (Terikat pada Domain)**:
- Saat browser memanggil API `navigator.credentials.get()`, sistem operasi dan browser memeriksa domain URL di *address bar* secara ketat (misalnya: `https://bank-mandiri.co.id`).
- Jika penyerang membuat situs tipuan dengan domain `https://bank-mandiri-login.xyz`, browser akan menolak menggunakan kunci privat yang terdaftar untuk `bank-mandiri.co.id`.
- Pengguna **secara fisik mustahil tertipu untuk menyerahkan Passkey miliknya ke situs phishing**, karena perangkat keras akan menolak menandatangani challenge jika *Relying Party ID (RP ID)* tidak cocok secara matematis!

---

## 5. What? (Dua Seremoni Inti WebAuthn)

### A. Seremoni Pendaftaran (Registration / Attestation)
1. **Server**: Menghasilkan `challenge` acak dan mengirim opsi registrasi (`rp: { name, id }`, `user: { id, name }`, `challenge`).
2. **Browser**: Menjalankan `navigator.credentials.create()`. Pengguna memindai biometrik.
3. **Hardware**: Membuat pasangan kunci publik-privat baru khusus untuk domain tersebut.
4. **Server**: Menerima `credentialId` dan `publicKey` baru, lalu menyimpannya ke database profil pengguna.

### B. Seremoni Login (Authentication / Assertion)
1. **Server**: Menghasilkan `challenge` acak baru.
2. **Browser**: Menjalankan `navigator.credentials.get({ challenge, allowCredentials })`. Pengguna memindai biometrik.
3. **Hardware**: Mengambil private key lokal, menandatangani challenge server beserta metadata client (`authenticatorData`), menghasilkan *Assertion Signature*.
4. **Server**: Memverifikasi signature menggunakan public key yang tersimpan di database. Jika tanda tangan valid, buatkan cookie session!

---

## 6. How? (Implementasi Full-Stack Passkeys dengan SimpleWebAuthn)

### 1. Server: Menghasilkan Opsi Registrasi (Backend)
```typescript
import { generateRegistrationOptions, verifyRegistrationResponse } from "@simplewebauthn/server";

// Endpoint: GET /api/auth/passkey/register-options
export async function getRegisterOptions(user: { id: string; email: string }) {
  const options = await generateRegistrationOptions({
    rpName: "Enterprise SaaS Portal",
    rpID: "perusahaan.com", // Relying Party ID (Domain Web)
    userID: Buffer.from(user.id),
    userName: user.email,
    attestationType: "none",
    authenticatorSelection: {
      residentKey: "required", // Mendukung Discoverable Passkey
      userVerification: "preferred", // Meminta Biometrik (FaceID / TouchID)
    },
  });

  // Simpan options.challenge ke database/redis session (kadaluwarsa 5 menit)
  await saveTemporaryChallenge(user.id, options.challenge);

  return options;
}
```

### 2. Client: Memanggil Biometrik Browser (Frontend)
```typescript
import { startRegistration, startAuthentication } from "@simplewebauthn/browser";

// Pendaftaran Passkey Baru
async function handleRegisterPasskey() {
  // 1. Ambil opsi challenge dari backend
  const res = await fetch("/api/auth/passkey/register-options");
  const options = await res.json();

  // 2. Browser memunculkan prompt biometrik (Apple TouchID / Windows Hello)
  const attestationResponse = await startRegistration(options);

  // 3. Kirim hasil tanda tangan biometrik ke backend untuk disimpan
  const verifyRes = await fetch("/api/auth/passkey/verify-registration", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(attestationResponse),
  });

  const result = await verifyRes.json();
  if (result.verified) alert("Passkey berhasil didaftarkan! Anda kini bisa login tanpa password.");
}
```

### 3. Server: Verifikasi Assertion Login
```typescript
// Endpoint: POST /api/auth/passkey/verify-login
export async function verifyLoginAssertion(body: any, userId: string) {
  const expectedChallenge = await getSavedChallenge(userId);
  const userPasskey = await getPasskeyFromDb(body.id);

  const verification = await verifyAuthenticationResponse({
    response: body,
    expectedChallenge,
    expectedOrigin: "https://perusahaan.com",
    expectedRPID: "perusahaan.com",
    authenticator: {
      credentialID: userPasskey.credentialId,
      credentialPublicKey: userPasskey.publicKey,
      counter: userPasskey.counter, // Mencegah Replay Attack!
    },
  });

  if (verification.verified) {
    // Update counter di database untuk mencegah replay attack
    await updatePasskeyCounter(userPasskey.id, verification.authenticationInfo.newCounter);
    // Buat session cookie login pengguna!
    return { success: true };
  }

  throw new Error("Verifikasi biometrik gagal");
}
```

---

## 7. Analogy
Bayangkan kunci kamar hotel mewah:
- **Kata Sandi Biasa**: Pihak hotel meminta Anda mengingat kombinasi 16 angka rahasia. Jika seseorang mengintip saat Anda menekan tombol di pintu, atau ada orang yang mengaku petugas kebersihan meminta kode tersebut lewat telepon, Anda bisa tertipu memberikannya (*Phishing & Credential Leak*).
- **Passkeys (FIDO2)**: Pintu kamar Anda memiliki pemindai retina mata berteknologi militer. Anda tidak perlu mengingat angka apapun. Anda hanya perlu berdiri di depan pintu kamar Anda sendiri (*Biometrik & Origin Validation*). Bahkan jika ada orang yang menduplikasi pintu hotel palsu di jalan raya, retina mata Anda tidak akan mengunci pintu palsu tersebut karena nomor kamar dan koordinat GPS fisiknya tidak cocok.

---

## 8. Diagram Seremoni Registrasi & Otentikasi Passkeys

```
+-----------------------------------------------------------------------------------+
| SEREMONI REGISTRASI (PENDAFTARAN BIOMETRIK)                                       |
|                                                                                   |
|  Browser                      Operating System (TPM)             Backend Server   |
|     |                                   |                              |          |
|     | 1. Minta Opsi Registrasi          |                              |          |
|     | ---------------------------------------------------------------> |          |
|     | <--------------------------------------------------------------- |          |
|     |    Opsi: { challenge, rpId, userId }                             |          |
|     |                                   |                              |          |
|     | 2. navigator.credentials.create() |                              |          |
|     | --------------------------------> |                              |          |
|     |                                   | 3. Scan Sidik Jari / Wajah   |          |
|     |                                   | 4. Generate Kunci Asimetris: |          |
|     |                                   |    - PrivateKey (Disimpan)   |          |
|     |                                   |    - PublicKey               |          |
|     | <-------------------------------- |                              |          |
|     |    Attestation + PublicKey        |                              |          |
|     |                                                                  |          |
|     | 5. Simpan PublicKey & CredentialID ke Database ----------------> |          |
|     | <--------------------------------------------------------------- |          |
|     |    200 OK (Passkey Berhasil Didaftarkan)                         |          |
+-----------------------------------------------------------------------------------+
```

---

## 9. Simple Example: Anatomi TOTP (Time-Based One-Time Password)
Untuk pengguna yang belum memiliki perangkat biometrik modern, TOTP (RFC 6238) adalah standar MFA universal:

$$\text{TOTP} = \text{Truncate}(\text{HMAC-SHA1}(K, T))$$

Di mana:
- $K$: Kunci rahasia bersama (*Shared Secret Key* berformat Base32).
- $T$: Penghitung waktu interval 30 detik: $T = \lfloor \frac{\text{CurrentUnixTime}}{30} \rfloor$.
- Hasil perhitungan menghasilkan **6 digit angka** yang berganti secara otomatis setiap 30 detik pada aplikasi Authenticator.

---

## 10. Practical Example: Format URI QR-Code untuk Authenticator App
Saat mengaktifkan MFA di akun pengguna, backend membuat secret key dan menyajikannya dalam format tautan standar:

```
otpauth://totp/Perusahaan%20SaaS:budi@perusahaan.com?secret=JBSWY3DPEHPK3PXP&issuer=Perusahaan%20SaaS&algorithm=SHA1&digits=6&period=30
```
Tautan ini di-render menjadi gambar QR Code. Saat pengguna memindai QR Code menggunakan aplikasi Google Authenticator, secret key tersimpan aman di smartphone pengguna.

---

## 11. Real-World Example: Multi-Tier Authentication Fallback Strategy
Pada sistem perbankan modern, strategi otentikasi diterapkan secara bertingkat (*Graceful Fallback*):

```
                       [ Login Flow ]
                             |
              (Apakah browser mendukung Passkeys?)
                   /                    \
                [ YA ]                [ TIDAK ]
                  |                       |
       [ Coba Otentikasi Biometrik ]   [ Masukkan Email ]
                  |                       |
            (Sukses?)          [ Kirim Magic Link 10 Menit ]
             /     \                      |
          [YA]    [GAGAL]        (User Klik Tautan Email)
           |         \                    |
      [ Dashboard ]   +--------> [ Minta 6 Digit TOTP MFA ]
                                          |
                                    [ Dashboard ]
```

---

## 12. Trade-offs: Perbandingan Metode Autentikasi Modern

| Metode | Kebal Phishing? | Kemudahan Pengguna (UX) | Biaya Operasional (SMS/Email) | Ketergantungan Perangkat |
| :--- | :--- | :--- | :--- | :--- |
| **Passkeys (FIDO2)** | **100% Kebal** | **Sangat Tinggi (1 Klik Biometrik)** | **Nol Biaya (Gratis)** | Butuh Device Modern (TPM/Enclave) |
| **TOTP Authenticator**| Tidak (Bisa di-phishing)| Menengah (Ketik 6 angka) | **Nol Biaya (Gratis)** | Butuh Aplikasi Authenticator |
| **Magic Links** | Parsial | Menengah (Buka Inbox Email) | Biaya Kirim Email (SendGrid/Resend) | Butuh Akses Akun Email |
| **SMS OTP** | Sangat Rentan (SIM Swap)| Tinggi | Mahal (Biaya SMS Telco) | Butuh Sinyal Seluler |
| **Password Biasa** | **Sangat Rentan** | Rendah (Harus ingat/ketik) | Nol Biaya | Bebas Perangkat |

---

## 13. When To Use Passkeys
- Anda membangun aplikasi web modern yang mengutamakan keamanan tinggi (Fintech, Healthcare, B2B SaaS, E-Commerce).
- Anda ingin meningkatkan konversi registrasi dan checkout dengan menghilangkan gesekan mengingat dan mengetik kata sandi (*Frictionless Login*).

---

## 14. When NOT To Use Passkeys Saja
- Jangan menjadikannya **satu-satunya pilihan tanpa opsi pemulihan (*recovery fallback*)**: Jika pengguna kehilangan smartphone atau laptop mereka dan Passkey tidak disinkronisasi ke cloud (iCloud Keychain / Google Password Manager), pengguna dapat terkunci dari akunnya selamanya. Selalu sediakan Magic Link atau Security Recovery Codes!

---

## 15. Common Mistakes
1. **Mengabaikan Pengecekan Counter pada WebAuthn**:
   - WebAuthn memiliki properti `counter` yang bertambah setiap kali signature dibuat. Jika counter yang dikirimkan client lebih kecil atau sama dengan counter sebelumnya di database, itu menandakan adanya **Replay Attack** (peretas mencoba menduplikasi respons jaringan lama).
2. **Hardcoding Expected Origin**:
   - Menyetel `expectedOrigin: "http://localhost:3000"` di production, menyebabkan verifikasi passkey gagal total di domain publik.
3. **Mengizinkan Waktu Kadaluwarsa Challenge yang Terlalu Lama**:
   - Membiarkan challenge registrasi/login aktif selama berjam-jam. Challenge WebAuthn harus kadaluwarsa dalam 2 hingga 5 menit untuk mencegah eksploitasi timing.

---

## 16. Best Practices

### Must Have
- Selalu verifikasi `expectedRPID` dan `expectedOrigin` secara ketat di backend.
- Simpan `counter` autentikator di database dan tolak login jika `newCounter <= currentCounter`.
- Gunakan HTTPS pada seluruh lingkungan pengujian (WebAuthn diblokir total oleh browser pada protokol HTTP biasa, kecuali `localhost`).

### Recommended
- Berikan opsi kepada pengguna untuk mendaftarkan lebih dari satu Passkey (misalnya: "MacBook Kantor" dan "iPhone Pribadi").
- Sediakan minimal 8 buah *Recovery Codes* (kode cadangan sekali pakai) saat pengguna pertama kali mengaktifkan MFA.

### Advanced
- Aktifkan *Synced Passkeys* (FIDO Credential Exchange) yang memungkinkan Passkey disinkronkan secara aman antar-perangkat pengguna melalui Apple iCloud Keychain, Google Password Manager, atau 1Password.

### Avoid
- Jangan pernah menggunakan SMS OTP sebagai faktor otentikasi utama karena rentan terhadap serangan *SIM Swapping* dan *SS7 Interception*.

---

## 17. Troubleshooting Guide

| Gejala Masalah | Kemungkinan Akar Masalah | Solusi |
| :--- | :--- | :--- |
| Browser melempar `NotAllowedError: The operation either timed out or was not allowed.` | Pengguna membatalkan prompt biometrik atau jendela browser kehilangan fokus saat scan. | Tangani error secara anggun di UI dan berikan tombol "Coba Lagi". |
| Error `Origin mismatch` saat memverifikasi respon di server. | URL domain yang diakses browser tidak sama persis dengan `expectedOrigin` (misal beda port atau subdomain). | Pastikan `expectedOrigin` mencakup protokol lengkap (misal `https://app.perusahaan.com`). |
| TOTP selalu ditolak (*Invalid OTP Code*) padahal angka di aplikasi sudah benar. | Terjadi pergeseran waktu (*Clock Drift*) antara server aplikasi dan jam di ponsel pengguna. | Izinkan toleransi jendela waktu $\pm 1$ interval (30 detik sebelum dan sesudah) di fungsi verifikasi server. |

---

## 18. Exercise
- **Easy**: Buat fungsi verifikasi token Magic Link sederhana yang memeriksa apakah token cocok dengan hash di memori dan belum melewati masa aktif 15 menit.
- **Medium**: Implementasikan algoritma perhitungan TOTP 6 digit menggunakan modul `crypto` Node.js bawaan tanpa pustaka eksternal.
- **Hard**: Bangun modul verifikasi tanda tangan digital ECDSA (P-256) untuk memvalidasi assertion response WebAuthn terhadap challenge server.

---

## 19. Challenge
Rancang arsitektur pemulihan akun (*Account Recovery Architecture*) untuk sistem login murni tanpa kata sandi (*pure passwordless*). Jika pengguna kehilangan perangkat biometrik mereka, bagaimana sistem Anda memverifikasi kepemilikan akun secara aman menggunakan kombinasi Magic Link, Recovery Codes bertanda tangan kriptografis, dan penundaan waktu (*Time-Lock Quarantine* 24 jam) untuk mencegah pembajakan akun?

---

## 20. Summary
- **Passkeys (FIDO2 / WebAuthn)** adalah lompatan keamanan terbesar dalam sejarah web: menggantikan kata sandi yang rentan dengan kriptografi kunci publik asimetris berbasis biometrik.
- Sifatnya yang **Origin-Bound** mengeliminasi 100% risiko penipuan via situs *phishing*.
- Menggabungkan Passkeys sebagai jalur login utama, dengan **TOTP Authenticator** dan **Magic Links** sebagai jalur pemulihan, menciptakan arsitektur autentikasi enterprise yang aman, modern, dan tanpa gesekan bagi pengguna.

---

## Hands-on Practice: Simulasi FIDO2 WebAuthn Passkeys & TOTP MFA Engine
Jalankan simulator seremoni pendaftaran, otentikasi biometrik, dan generator TOTP mandiri:

```bash
node Full-Stack/BAB-06-Autentikasi-Full-Stack-dan-WebAuthn/hands-on/m02/webauthn_passkey_fido2_sim.js
```

---
[⬅️ Module 01: Auth.js & Secure Cookies](./Module-01-Authjs-Secure-Cookies-OAuth-Edge-Guards.md) | [📋 Silabus Induk](../README.md) | [BAB 06 Quiz & Challenge ➡️](./BAB-06-Quiz-dan-Challenge.md)
---
