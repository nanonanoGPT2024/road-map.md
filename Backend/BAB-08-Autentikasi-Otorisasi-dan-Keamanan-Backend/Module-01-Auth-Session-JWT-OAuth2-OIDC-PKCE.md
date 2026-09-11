---
[⬅️ BAB 07 Quiz & Challenge](../BAB-07-Asynchronous-Processing-dan-Message-Brokers/BAB-07-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: OWASP API Security & Rate Limiting ➡️](./Module-02-OWASP-API-Security-Top-10-Rate-Limiting-Enkripsi.md)
---

# Module 01: Autentikasi Modern, JWT vs Session, OAuth 2.0 PKCE, & RBAC/ABAC

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
- Membedakan secara tegas antara **Autentikasi** (*Who are you?*) dan **Otorisasi** (*What are you allowed to do?*).
- Membandingkan trade-off mendalam antara **Stateful Session-based Authentication** (Redis/RDBMS) vs **Stateless Token-based Authentication (JSON Web Tokens - JWT)**.
- Menganalisis struktur anatomi JWT (Header, Payload, Signature) dan bahaya serangan enkripsi algoritma `none` serta pencurian *Secret Key*.
- Menguasai alur kerja **OAuth 2.0 Authorization Code Flow with PKCE** (*Proof Key for Code Exchange*) untuk aplikasi SPA dan Mobile.
- Memahami lapisan identitas **OpenID Connect (OIDC)** dan penggunaan `id_token` vs `access_token`.
- Merancang model otorisasi granular: **Role-Based Access Control (RBAC)** vs **Attribute-Based Access Control (ABAC)**.

---

## 2. Prerequisite
- Memahami protokol HTTP/HTTPS, Headers, dan Cookies (`HttpOnly`, `SameSite`, `Secure`) (BAB 01).
- Memahami konsep fungsi hash kriptografi dan tanda tangan digital (*Digital Signatures* HMAC-SHA256 vs RSA/ECDSA).
- Pemahaman penyimpanan terdistribusi Redis untuk sesi (BAB 06).

---

## 3. Concept
Keamanan backend bertumpu pada dua pilar utama:
1. **Autentikasi (AuthN):** Proses verifikasi identitas pengguna, entitas, atau sistem (misalnya: memvalidasi username & password, verifikasi OTP multi-faktor, atau otentikasi biometrik).
2. **Otorisasi (AuthZ):** Proses penentuan hak akses dari identitas yang telah terverifikasi terhadap resource tertentu (misalnya: "Apakah user dengan ID 101 berhak menghapus data faktur #8841?").

Di era komputasi modern yang melibatkan aplikasi web Single Page Application (React, Vue), mobile apps (Flutter, iOS, Android), microservices, dan integrasi pihak ketiga, sistem autentikasi berevolusi dari sekadar session cookie sederhana menjadi ekosistem token terdesentralisasi (**JWT**) dan protokol delegasi identitas global (**OAuth 2.0 & OIDC**).

---

## 4. Why?
Tanpa pemahaman mendalam tentang standar Auth modern:
- **Celah Keamanan Fatal:** Menyimpan token autentikasi di `localStorage` browser yang rentan terhadap serangan pencurian via *Cross-Site Scripting (XSS)*.
- **Inability to Invalidate JWT:** Menggunakan JWT tanpa mekanisme *Revocation List / Token Blacklist*, sehingga hacker yang mencuri token tetap bisa mengakses sistem meskipun user sudah mengganti password atau mengklik "Logout".
- **Skalabilitas Sesi Rusak:** Memaksakan stateful session pada cluster microservices yang memiliki 50 server tanpa adanya shared session store terpusat, menyebabkan user ter-logout berulang kali (*Session Drop*).
- **OAuth 2.0 Implicit Flow yang Usang:** Menggunakan alur OAuth usang yang mengembalikan access token langsung di URL fragment browser, rentan disadap oleh malware dan ekstensi peramban.

---

## 5. What? (Komparasi Stateful Session vs Stateless JWT)

| Aspek | Stateful Session (Cookie-based) | Stateless JWT (Token-based) |
|---|---|---|
| **Lokasi Penyimpanan State** | Disimpan di server (RAM, Redis, Database) | Disimpan murni di sisi Client (Signed Token) |
| **Kebutuhan Memori Server**| Meningkat seiring bertambahnya user aktif ($O(N)$) | $O(1)$ (Nol memori di server, hanya butuh CPU verifikasi tanda tangan) |
| **Pencabutan Akses (Revoke)**| **Sangat Mudah & Instan** (Cukup hapus sesi dari Redis) | **Sangat Sulit** (Token valid sampai waktu kedaluwarsa `exp` tercapai) |
| **Dukungan Lintas Domain/Mobile**| Rentan isu CSRF dan pembatasan Third-party Cookie | Sangat mudah dikirim via header `Authorization: Bearer <token>` |
| **Ukuran Payload Jaringan** | Sangat kecil (hanya 32 byte Session ID) | Cukup besar (300 byte - 2 KB berisi claims identitas) |
| **Kesesuaian Arsitektur** | Web Monolitik Tradisional, SSR (Next.js/Nuxt) | Microservices Terdistribusi, RESTful APIs, Mobile Apps |

---

## 6. How? (Anatomi JWT & Alur OAuth 2.0 PKCE)

### A. Anatomi JSON Web Token (JWT)
Sebuah string JWT terdiri dari 3 bagian yang dipisahkan oleh tanda titik (`.`):
$$\text{JWT} = \text{Base64Url}(\text{Header}) + "." + \text{Base64Url}(\text{Payload}) + "." + \text{Signature}$$

```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMDEiLCJuYW1lIjoiQW5keSIsInJvbGUiOiJhZG1pbiIsImV4cCI6MTczNjU2MDgwMH0.4b7F...
```
1. **Header:** Menyatakan metadata tipe token (`JWT`) dan algoritma tanda tangan digital (contoh: `HS256` atau `RS256`).
2. **Payload (Claims):** Data identitas pengguna (contoh: `sub: user_id`, `role: admin`, `exp: expiration_time`). **PENTING: Payload TIDAK DIENKRIPSI! Payload hanya di-encode Base64. Siapapun bisa membacanya! Jangan pernah menyimpan password atau data rahasia di payload!**
3. **Signature:** Hash kriptografi dari kombinasi Header + Payload yang ditandatangani menggunakan *Secret Key* server (pada HMAC) atau *Private Key* (pada RSA). Jika penyerang memanipulasi role di payload, signature otomatis menjadi tidak valid.

### B. Alur OAuth 2.0 Authorization Code Flow with PKCE
Dirancang khusus untuk klien publik (SPA & Mobile) yang tidak dapat menyimpan `client_secret` secara aman.

```
[ Client (Mobile/SPA) ]              [ Authorization Server ]             [ Resource API Server ]
          │                                      │                                   │
 1. Generate: Code Verifier                      │                                   │
    + Code Challenge = SHA256(Verifier)          │                                   │
 2. Buka Halaman Login + Code Challenge ────────▶│                                   │
          │                                      │                                   │
          │  3. User Login & Setujui Consent     │                                   │
          │◀──4. Redirect + Authorization Code ──┘                                   │
          │                                                                          │
 5. Tukar Auth Code + Code Verifier ASLI ───────▶│                                   │
          │                                      │ (Verifikasi: SHA256(Verifier)    │
          │                                      │  apakah cocok dengan Challenge?)  │
          │◀──6. Kembalikan Access & ID Token ───┘                                   │
          │                                                                          │
 7. Request Data dengan Header Bearer Token ────────────────────────────────────────▶│
          │                                                                          │ (Verifikasi Signature)
          │◀──8. Data Resource Dikembalikan ─────────────────────────────────────────┘
```

---

## 7. Analogy
- **Stateful Session ibarat Karcis Penitipan Jaket di Bioskop:** Petugas memberi Anda secarik nomor karcis #42 (Session ID). Jaket Anda yang sebenarnya (data user, hak akses) tersimpan di lemari petugas di belakang loket (Server Redis). Jika petugas ingin mencabut hak Anda, petugas cukup merobek data nomor #42 di lemarinya.
- **Stateless JWT ibarat Gelang Masuk Konser Tahan Air:** Gelang dicetak dengan barcode khusus berisi nama dan kategori tiket VIP Anda, lalu distempel cap hologram resmi panitia (Digital Signature). Petugas keamanan di setiap pintu masuk tidak perlu mengecek database loket pusat; mereka cukup melihat stempel hologram tersebut. Namun, jika gelang Anda dicuri orang lain, orang tersebut bisa masuk selama stempelnya asli, kecuali ada daftar buronan khusus (*Revocation List*).

---

## 8. Diagram: RBAC (Role-Based) vs ABAC (Attribute-Based Access Control)

```
MODEL 1: RBAC (Sederhana & Berbasis Peran Statis)
[ User: Alice ] ──memiliki peran──▶ [ Role: Editor ] ──memiliki izin──▶ [ Permission: POST_UPDATE ]
Kelemahan: Sulit menerapkan logika kontekstual (misal: "Hanya boleh edit artikel buatan sendiri dan pada jam kerja").

MODEL 2: ABAC (Fleksibel & Berbasis Kebijakan Multidimensi)
Policy Engine mengevaluasi 4 atribut dinamis:
1. Atribut Subjek     : User role = 'Doctor', Department = 'Cardiology'
2. Atribut Objek      : Medical Record patient_id = 9912, Clinic = 'Cardiology'
3. Atribut Aksi       : Action = 'VIEW_RECORD'
4. Atribut Lingkungan : Time = 09:30 AM, Network = 'Internal Hospital WiFi'
                      │
                      ▼
         [ Policy Engine (XACML / OPA) ] ──▶ Evaluasi Kebijakan: ALLOW / DENY
```

---

## 9. Simple Example: Verifikasi JWT Manual HMAC-SHA256 (Node.js murni)

```javascript
const crypto = require('crypto');

function base64UrlEncode(str) {
  return Buffer.from(str)
    .toString('base64')
    .replace(/=/g, '')
    .replace(/\+/g, '-')
    .replace(/\//g, '_');
}

function createJWT(payload, secretKey, expiresInSeconds = 3600) {
  const header = { alg: 'HS256', typ: 'JWT' };
  const fullPayload = {
    ...payload,
    exp: Math.floor(Date.now() / 1000) + expiresInSeconds
  };

  const encodedHeader = base64UrlEncode(JSON.stringify(header));
  const encodedPayload = base64UrlEncode(JSON.stringify(fullPayload));
  const dataToSign = `${encodedHeader}.${encodedPayload}`;

  const signature = crypto
    .createHmac('sha256', secretKey)
    .update(dataToSign)
    .digest('base64')
    .replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_');

  return `${dataToSign}.${signature}`;
}

function verifyJWT(token, secretKey) {
  const parts = token.split('.');
  if (parts.length !== 3) throw new Error('Format JWT tidak valid!');

  const [encodedHeader, encodedPayload, signature] = parts;
  const dataToSign = `${encodedHeader}.${encodedPayload}`;

  // Hitung ulang signature dengan secret key server
  const expectedSignature = crypto
    .createHmac('sha256', secretKey)
    .update(dataToSign)
    .digest('base64')
    .replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_');

  // Gunakan timing-safe compare untuk mencegah timing attacks!
  const isSignatureValid = crypto.timingSafeEqual(
    Buffer.from(signature),
    Buffer.from(expectedSignature)
  );

  if (!isSignatureValid) throw new Error('Signature tidak cocok! Token telah dimanipulasi!');

  const payload = JSON.parse(Buffer.from(encodedPayload, 'base64').toString('utf-8'));
  if (payload.exp && Math.floor(Date.now() / 1000) > payload.exp) {
    throw new Error('Token telah kedaluwarsa (Expired)!');
  }

  return payload;
}
```

---

## 10. Practical Example: Implementasi RBAC Middleware di Express.js

```javascript
function authorizeRoles(...allowedRoles) {
  return (req, res, next) => {
    // Diasumsikan req.user sudah diisi oleh Authentication Middleware sebelumnya
    if (!req.user || !req.user.role) {
      return res.status(401).json({ error: 'Unauthorized: Autentikasi diperlukan.' });
    }

    if (!allowedRoles.includes(req.user.role)) {
      return res.status(403).json({
        error: `Forbidden: Akses ditolak. Memerlukan peran salah satu dari: [${allowedRoles.join(', ')}]`
      });
    }

    next();
  };
}

// Penggunaan pada endpoint API:
// app.delete('/api/v1/users/:id', authenticateToken, authorizeRoles('SUPER_ADMIN'), deleteUserHandler);
```

---

## 11. Real World Example: Arsitektur Single Sign-On (SSO) di Perusahaan Multinasional

Perusahaan dengan 20.000 karyawan mengintegrasikan 50 aplikasi internal (Jira, Slack, HR Portal, GitHub, AWS Console):
1. **Penyedia Identitas Terpusat (IdP):** Menggunakan Okta / Keycloak berbasis protokol **OIDC & SAML 2.0**.
2. **Multi-Factor Authentication (MFA):** Setiap karyawan wajib memverifikasi push notification di smartphone (FIDO2 / WebAuthn hardware token).
3. **Dual-Token Architecture:**
   - **Access Token:** Berupa JWT bertanda tangan digital asimetris (RS256) dengan masa aktif sangat singkat (**15 menit**).
   - **Refresh Token:** Disimpan dalam cookie `HttpOnly; Secure; SameSite=Strict` yang tersimpan di server auth dengan masa aktif **7 hari** dan mekanisme *Refresh Token Rotation* (setiap kali dipakai, token lama dihanguskan dan token baru diterbitkan).

Hasil: Karyawan hanya login 1 kali di pagi hari untuk mengakses seluruh sistem kerja dengan standar keamanan perbankan internasional.

---

## 12. Trade-offs

| Pendekatan Autentikasi | Keamanan Terhadap XSS | Kemudahan Revokasi | Performa Verifikasi | Kompleksitas Arsitektur |
|---|---|---|---|---|
| **Session + Redis** | Tinggi (Bila disimpan di HttpOnly Cookie)| Instan ($O(1)$ hapus Redis)| Cepat (~1ms periksa Redis)| Menengah (Butuh shared Redis cluster)|
| **JWT (Short-lived 15m)**| Rentan jika di localStorage; Aman di HttpOnly Cookie| Sulit (Butuh blacklist store jika ingin instan)| Sangat Cepat (~0.05ms CPU verify)| Sederhana (Stateless)|
| **JWT + Refresh Token Rotation**| Sangat Tinggi (Cookie HttpOnly + Rotation)| Tinggi (Cukup batalkan family refresh token)| Sangat Cepat| Menengah ke Tinggi|
| **OAuth 2.0 + OIDC** | Standar Industri Tertinggi | Terpusat di IdP | Cepat (JWKS caching publik)| Tinggi (Butuh server IdP/OIDC)|

---

## 13. When To Use
- **Gunakan JWT Stateless:** Pada arsitektur microservices berskala besar di mana puluhan service backend perlu memverifikasi identitas pemanggil secara independen menggunakan *Public Key* (JWKS) tanpa membebani database auth pusat.
- **Gunakan Session-based Auth:** Pada aplikasi web monolith tradisional atau Server-Side Rendering (SSR) yang mengutamakan kontrol keamanan absolut (kemampuan mematikan sesi user seketika saat ada aktivitas mencurigakan).
- **Gunakan OAuth 2.0 PKCE:** Wajib digunakan saat membangun aplikasi mobile (iOS/Android) atau Single Page Application (React/Vue) yang membutuhkan otorisasi akun pihak ketiga (Google, GitHub, Apple) atau API backend terpisah.

---

## 14. When NOT To Use
- **Jangan Gunakan JWT untuk Sesi yang Wajib Bisa Direvoke Instan Tanpa Delay:** Jika bisnis Anda menuntut user yang di-banned harus terputus seketika dalam milidetik yang sama tanpa menunggu masa aktif token 15 menit berakhir.
- **Jangan Simpan Data Sensitif di Payload JWT:** Nomor kartu kredit, password hash, atau data PII pribadi tidak boleh dimasukkan ke payload karena Base64 dapat didecode oleh siapa saja secara telanjang.
- **Jangan Gunakan Algoritma Simetris (HS256) Jika Verifier Berada di Banyak Pihak Eksternal:** Menyerahkan Shared Secret Key HS256 kepada service pihak ketiga membuat mereka mampu memalsukan (*forge*) JWT baru atas nama siapapun. Gunakan kriptografi kunci publik-privat (RS256 atau ES256)!

---

## 15. Common Mistakes
1. **Menerima Algoritma `alg: "none"`:** Celah kerentanan klasik di mana server menerima JWT tanpa verifikasi signature jika header mencantumkan `none`.
2. **Menyimpan Token di `localStorage` Browser:** Akses JavaScript murni membuat token rentan disedot oleh skrip berbahaya saat terjadi celah injeksi XSS.
3. **Masa Berlaku Token Terlalu Panjang:** Menerbitkan Access Token JWT dengan masa kedaluwarsa 30 hari tanpa mekanisme refresh token. Jika token disadap, peretas leluasa menguasai akun korban selama satu bulan penuh!
4. **Tidak Menggunakan `timingSafeEqual`:** Membandingkan signature string dengan operator `===` biasa, membuka celah kerentanan *Timing Attack* yang memungkinkan penyerang menebak signature byte per byte.

---

## 16. Best Practices

### Must Have
- Gunakan algoritma asimetris modern (**RS256** atau **ES256**) untuk lingkungan enterprise microservices.
- Pasang masa berlaku singkat pada Access Token (**maksimal 5 - 15 menit**).
- Simpan token di browser menggunakan **Cookie dengan atribut: `HttpOnly; Secure; SameSite=Strict`**.

### Recommended
- Implementasikan **Refresh Token Rotation**: Setiap kali refresh token digunakan, ganti dengan token baru dan tandai token lama sebagai hangus. Jika token lama digunakan kembali, kunci seluruh sesi keluarga token tersebut (*Token Reuse Detection*).
- Gunakan open-source policy engine seperti **Open Policy Agent (OPA)** untuk implementasi otorisasi kompleks berbasis ABAC.

### Advanced
- Lindungi Private Key penandatangan token menggunakan **Hardware Security Module (HSM)** atau AWS KMS / Google Cloud KMS.

---

## 17. Troubleshooting

| Masalah | Akar Masalah | Tindakan Investigasi | Solusi Perbaikan |
|---|---|---|---|
| **Error: `jwt signature is invalid`** | Secret key salah, token termodifikasi, atau ketidakcocokan algoritma | Bandingkan signature manual, verifikasi secret key di env | Pastikan runtime menggunakan secret key yang sama atau refresh public JWKS cache |
| **User Ter-logout Sendiri Setiap Beberapa Menit** | Clock skew antara server auth dan server resource API | Periksa sinkronisasi NTP clock antar server | Tambahkan toleransi waktu (*Clock Tolerance / Leeway*) 30-60 detik pada library verifikasi JWT |
| **CORS Error saat Kirim Authorization Header** | Browser memblokir preflight request OPTIONS | Cek response header `Access-Control-Allow-Headers` di API Gateway | Izinkan header `Authorization` dan pastikan kredensial diizinkan (`Access-Control-Allow-Credentials: true`) |

---

## 18. Exercise
1. Bangun generator dan verifikator JWT murni menggunakan modul `crypto` bawaan Node.js tanpa dependensi npm eksternal.
2. Tambahkan simulasi mekanisme *Token Blacklist* in-memory untuk membatalkan (*revoke*) token tertentu sebelum masa berlakunya habis.
3. Uji coba manipulasi satu karakter pada payload Base64 dan buktikan verifikator melempar error signature tidak valid.

---

## 19. Challenge
Rancang arsitektur autentikasi & otorisasi enterprise untuk aplikasi telemedicine:
1. Dokter hanya boleh membaca rekam medis pasien yang memiliki jadwal konsultasi aktif dengannya pada hari yang sama.
2. Pasien hanya boleh membaca rekam medis miliknya sendiri.
3. Petugas asuransi hanya boleh melihat rincian klaim biaya tanpa melihat catatan diagnosa klinis dokter.
Rancang skema kebijakan **ABAC (Attribute-Based Access Control)** dalam format JSON Policy untuk memvalidasi akses ketiga persona di atas!

---

## 20. Summary
Autentikasi dan otorisasi adalah garda terdepan integritas sistem backend. Memahami kapan harus memanfaatkan kelincahan stateless JWT, kapan harus mempertahankan ketegasan kontrol stateful session, serta bagaimana mengamankan pertukaran kredensial via OAuth 2.0 PKCE adalah fondasi wajib bagi setiap engineer yang membangun sistem kelas dunia.

---
[⬅️ BAB 07 Quiz & Challenge](../BAB-07-Asynchronous-Processing-dan-Message-Brokers/BAB-07-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: OWASP API Security & Rate Limiting ➡️](./Module-02-OWASP-API-Security-Top-10-Rate-Limiting-Enkripsi.md)
---
