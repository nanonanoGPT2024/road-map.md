---
[⬅️ Module 01: Autentikasi Modern & OAuth 2.0 PKCE](./Module-01-Auth-Session-JWT-OAuth2-OIDC-PKCE.md) | [📋 Silabus Induk](../README.md) | [BAB 08 Quiz & Challenge ➡️](./BAB-08-Quiz-dan-Challenge.md)
---

# Module 02: OWASP API Security Top 10, Rate Limiting, & Kriptografi Defensif

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
- Menguasai ancaman paling mematikan pada antarmuka backend berdasarkan **OWASP API Security Top 10 (2023 Edition)**, khususnya **BOLA (Broken Object Level Authorization)** dan **Mass Assignment**.
- Merancang dan membandingkan algoritma pembatasan laju trafik (**Rate Limiting**): **Token Bucket**, **Leaky Bucket**, dan **Sliding Window Counter**.
- Memahami mengapa fungsi hash cepat (MD5, SHA-256) dilarang keras untuk penyimpanan kata sandi dan menguasai fungsi memori-berat (*Memory-Hard Hashing*): **Argon2id** dan **bcrypt**.
- Mengimplementasikan enkripsi data diam (**Data-at-Rest**) menggunakan algoritma modern **AES-256-GCM** (*Authenticated Encryption with Associated Data / AEAD*) dan teknik *Envelope Encryption* via KMS.
- Mengamankan data bergerak (**Data-in-Transit**) dengan **TLS 1.3**, sertifikat mTLS (*Mutual TLS* antar microservices), dan header keamanan HTTP (**HSTS, CSP, CORS**).

---

## 2. Prerequisite
- Memahami konsep dasar Autentikasi dan Otorisasi (Modul 01).
- Pemahaman struktur data Redis Sorted Set untuk rate limiting (BAB 06).
- Pemahaman operasi kriptografi simetris vs asimetris.

---

## 3. Concept
Dalam lanskap rekayasa perangkat lunak modern, API bukan lagi sekadar pelengkap situs web; API adalah pintu gerbang utama yang langsung mengekspos logika bisnis dan database inti perusahaan ke jaringan internet publik.

Mayoritas insiden kebocoran data (*Data Breaches*) skala besar di dunia tidak disebabkan oleh peretasan kriptografi yang rumit, melainkan oleh kelemahan arsitektur level aplikasi:
1. Kegagalan validasi kepemilikan data pada level objek (**BOLA / IDOR**).
2. Ketiadaan pembatas laju request (**Rate Limiting**), memungkinkan penyerang melakukan *brute-force* atau menguras sumber daya server (*Denial of Service*).
3. Penggunaan fungsi hashing usang yang dapat dibongkar dalam hitungan menit menggunakan kartu grafis (GPU).

---

## 4. Why?
Tanpa pemahaman mendalam tentang standar OWASP dan kriptografi defensif:
- **Kebocoran Data Finansial Masif:** Mengubah parameter URL `GET /api/v1/invoices/8841` menjadi `8842` langsung menampilkan faktur pelanggan lain tanpa ada validasi apakah user yang login memiliki faktur tersebut (**BOLA**).
- **Eskalasi Hak Akses Ilegal:** Endpoint pendaftaran menerima payload JSON mentah dan menyimpannya langsung ke database (`User.create(req.body)`). Penyerang menyisipkan field `"role": "SUPER_ADMIN"`, langsung mengubah akun gratisnya menjadi administrator sistem (**Mass Assignment**).
- **Database Dump Menjadi Teks Telanjang:** Database dicuri penyerang. Jika password disimpan menggunakan SHA-256 atau MD5, penyerang dapat memecahkan 90% password pengguna dalam hitungan jam menggunakan *Rainbow Tables* atau rig GPU hashcat.

---

## 5. What? (Katalog OWASP API Security Top 10 - 2023)

| Kategori Ancaman | Deskripsi Kerentanan | Dampak Serangan | Contoh Skenario Nyata |
|---|---|---|---|
| **API1:2023 BOLA (IDOR)** | Endpoint tidak memverifikasi apakah user yang login berhak mengakses objek yang diminta | Pencurian data privasi masif | Mengubah ID dokumen di URL untuk melihat rekam medis orang lain |
| **API2:2023 Broken Authentication** | Kelemahan pada alur login, token generation, atau password reset | Pengambilalihan akun (*Account Takeover*) | Token password reset tidak kedaluwarsa atau bisa ditebak (*Weak Entropy*) |
| **API3:2023 Broken Property Auth** | Mass Assignment atau Excessive Data Exposure | Manipulasi field sensitif, kebocoran PII | API mengembalikan seluruh baris DB termasuk hash password |
| **API4:2023 Unrestricted Resource** | Ketiadaan Rate Limiting atau batas ukuran payload/query | Server crash (DoS), biaya cloud melonjak | Menjalankan 100.000 request login per menit |
| **API5:2023 BFLA** | Broken Function Level Authorization | User biasa mengeksekusi fungsi admin | Akses endpoint `DELETE /api/admin/users` tanpa validasi role |
| **API6:2023 Sensitive Business Flows**| Bot otomatis menyalahgunakan alur bisnis legal | Scalping tiket konser, penimbunan kupon promo | Bot memborong seluruh tiket konser dalam 2 detik |
| **API7:2023 SSRF** | Server diarahkan untuk mengambil resource internal yang terlarang | Akses metadata cloud AWS `169.254.169.254` | Mengirim URL webhook yang mengarah ke jaringan intranet |
| **API8:2023 Security Misconfiguration**| CORS `*` dengan kredensial, verbose stack trace, default password | Pencurian sesi, eksposur arsitektur internal | Error 500 menampilkan seluruh kode query SQL dan kredensial DB |
| **API9:2023 Improper Inventory** | API versi lama (*Shadow / Zombie APIs*) dibiarkan hidup tanpa patch | Akses melalui pintu belakang yang terlupakan | Endpoint `/api/v1/login` yang belum ada MFA masih aktif |
| **API10:2023 Unsafe 3rd Party APIs** | Mempercayai data dari API pihak ketiga tanpa sanitasi | Injeksi SQL atau eksekusi kode berbahaya | Mengintegrasikan payload webhook vendor tanpa validasi signature |

---

## 6. How? (Algoritma Rate Limiting: Token Bucket)

Algoritma **Token Bucket** adalah standar industri paling populer (digunakan oleh AWS, Cloudflare, GitHub API):

```
       [ Token Refill Generator ] ──Menambahkan token dengan laju konstan (misal: 10 token/detik)──┐
                                                                                                    ▼
                                                                                   ┌─────────────────┐
                                                                                   │  TOKEN BUCKET   │
                                                                                   │ Kapasitas Maks  │
                                                                                   │ (misal: 50 tok) │
                                                                                   │  ●  ●  ●  ●  ●  │
                                                                                   └────────┬────────┘
                                                                                            │
                                                                          Tiap Request Mengambil 1 Token
                                                                                            │
                                                                                            ▼
                                                    [ Request Masuk ] ──▶ (Ada Token?) ───┬─── [YA] ──▶ Izinkan Request (HTTP 200)
                                                                                          │
                                                                                          └─── [TIDAK] ──▶ Tolak Request (HTTP 429 Too Many Requests)
```
- **Kelebihan:** Mengizinkan lonjakan trafik sesaat (*Traffic Burstiness*) selama kuota token di dalam ember masih tersedia, namun tetap menjaga laju jangka panjang pada rata-rata yang ditentukan.

---

## 7. Analogy
- **BOLA (IDOR) ibarat Kamar Hotel dengan Kunci Universal Palsu:** Anda menginap di kamar 301. Di kartu kunci Anda tertulis angka "301". Anda mencoret angka tersebut dengan spidol menjadi "302", lalu menempelkannya ke pintu kamar 302. Jika pintu terbuka, berarti hotel tersebut memiliki kerentanan BOLA (pintu hanya membaca nomor tanpa mencocokkan identitas tamu yang terdaftar di database resepsionis).
- **Argon2id ibarat Brankas Baja dengan Kombinasi Waktu & Berat:** Jika MD5 adalah gembok koper plastik yang bisa dibuka peretas dalam 1 detik, Argon2id adalah brankas bank tebal yang memaksa peretas menghabiskan 64 Megabyte memori RAM dan 0,5 detik waktu CPU untuk satu kali tebakan. Menjalankan 1 miliar tebakan pada Argon2id membutuhkan biaya listrik dan perangkat keras miliaran rupiah.

---

## 8. Diagram: Enkripsi Data-at-Rest Modern (AES-256-GCM AEAD)

Mengapa AES-CBC usang dan wajib diganti dengan **AES-256-GCM**?
AES-GCM adalah **Authenticated Encryption with Associated Data (AEAD)**: Selain mengenkripsi kerahasiaan data (*Confidentiality*), algoritma ini menghasilkan **Authentication Tag** (16 byte) yang menjamin integritas data (*Integrity*). Jika penyerang mengubah 1 bit saja dari ciphertext di database, proses dekripsi akan langsung gagal total (*Tamper-Proof*).

```
   [ Plaintext Data (PII) ]
              │
              ▼
   [ AES-256-GCM Encryptor ] ◄── Data Encryption Key (DEK) 256-bit
         /          \
        ▼            ▼
 [ Ciphertext ]   [ Auth Tag (16-byte) ] ──▶ Disimpan ke Database: "IV : Ciphertext : Tag"
```

---

## 9. Simple Example: Enkripsi & Dekripsi AES-256-GCM (Node.js murni)

```javascript
const crypto = require('crypto');

function encryptData(text, key32Bytes) {
  const iv = crypto.randomBytes(12); // Standard 96-bit IV untuk GCM
  const cipher = crypto.createCipheriv('aes-256-gcm', key32Bytes, iv);

  let encrypted = cipher.update(text, 'utf8', 'hex');
  encrypted += cipher.final('hex');

  const authTag = cipher.getAuthTag(); // 16-byte Authentication Tag

  // Format penyimpanan: iv:authTag:ciphertext
  return `${iv.toString('hex')}:${authTag.toString('hex')}:${encrypted}`;
}

function decryptData(encryptedPayload, key32Bytes) {
  const [ivHex, tagHex, ciphertextHex] = encryptedPayload.split(':');
  if (!ivHex || !tagHex || !ciphertextHex) throw new Error('Format ciphertext rusak!');

  const iv = Buffer.from(ivHex, 'hex');
  const authTag = Buffer.from(tagHex, 'hex');
  const decipher = crypto.createDecipheriv('aes-256-gcm', key32Bytes, iv);

  decipher.setAuthTag(authTag); // Wajib di-set untuk memvalidasi integritas data

  let decrypted = decipher.update(ciphertextHex, 'hex', 'utf8');
  decrypted += decipher.final('utf8'); // Melempar error jika data pernah diubah oleh pihak ketiga!

  return decrypted;
}
```

---

## 10. Practical Example: Proteksi BOLA & Mass Assignment di Level Kode

```javascript
// ANTIPATTERN (RENTAN BOLA & MASS ASSIGNMENT):
app.put('/api/v1/orders/:orderId', async (req, res) => {
  // Rentan BOLA: Siapapun yang punya orderId bisa update order milik orang lain!
  // Rentan Mass Assignment: Penyerang bisa menyisipkan status: 'PAID' secara ilegal!
  await Order.update(req.body, { where: { id: req.params.orderId } });
  res.json({ message: 'Updated' });
});

// BEST PRACTICE DEFENSIF:
app.put('/api/v1/orders/:orderId', authenticateUser, async (req, res) => {
  const { orderId } = req.params;
  const currentUserId = req.user.id; // Diambil dari JWT terverifikasi

  // 1. Mitigasi BOLA: Validasi Kepemilikan Objek
  const order = await Order.findOne({ where: { id: orderId, userId: currentUserId } });
  if (!order) {
    // Kembalikan 404 (bukan 403) agar penyerang tidak bisa menduga keberadaan ID tersebut
    return res.status(404).json({ error: 'Pesanan tidak ditemukan' });
  }

  // 2. Mitigasi Mass Assignment: DTO Whitelisting Ketat
  const { shippingAddress, deliveryNotes } = req.body; // Hanya ambil field yang diizinkan!

  order.shippingAddress = shippingAddress;
  order.deliveryNotes = deliveryNotes;
  await order.save();

  res.json({ message: 'Pesanan berhasil diperbarui', data: order });
});
```

---

## 11. Real World Example: Kebocoran Data BOLA Terbesar di Industri Fintech

Pada audit keamanan sebuah aplikasi pinjaman online:
- Peneliti keamanan menemukan endpoint `/api/v1/users/{userId}/loan-status`.
- Peneliti login dengan akun penguji miliknya (`userId: 5501`).
- Ketika parameter diubah menjadi `userId: 5502`, server dengan polosnya mengembalikan seluruh data KTP, foto selfie, slip gaji, dan nomor rekening bank milik pengguna 5502.
- Remediasi yang dilakukan:
  1. API Gateway menerapkan interceptor yang mengekstrak `sub` dari JWT token.
  2. URL endpoint diubah menjadi: `/api/v1/me/loan-status` (meniadakan parameter ID publik di URL sama sekali).
  3. Query database mengunci baris berdasarkan `WHERE user_id = :token_user_id`.

---

## 12. Trade-offs

| Algoritma Rate Limiting | Kemampuan Menahan Burst | Konsumsi Memori | Kompleksitas Implementasi |
|---|---|---|---|
| **Fixed Window Counter** | Buruk (Bisa 2x lipat kuota di batas jendela waktu)| Sangat Rendah ($O(1)$ satu counter)| Sangat Sederhana |
| **Sliding Window Log** | Sempurna (Presisi milidetik mutlak) | Sangat Tinggi ($O(N)$ mencatat tiap request)| Menengah (ZSET di Redis)|
| **Token Bucket** | **Sangat Baik** (Mendukung traffic burst terkendali)| Sangat Rendah (2 atribut: lastRefill, tokens)| Menengah |
| **Leaky Bucket** | Sangat Kaku (Output rata tanpa burst sama sekali)| Sangat Rendah | Menengah |

---

## 13. When To Use
- **Mitigasi BOLA (IDOR):** Wajib diterapkan pada **100% endpoint** yang menerima parameter ID entitas (`:id`, `:uuid`, `:slug`) yang berhubungan dengan data privat pengguna.
- **Token Bucket Rate Limiting:** Terapkan di lapisan API Gateway untuk melindungi seluruh endpoint publik, dan berikan batas yang lebih ketat pada endpoint sensitif (seperti `/api/auth/login`, `/api/auth/reset-password`, `/api/payments/checkout`).
- **Memory-Hard Password Hashing (Argon2id):** Wajib digunakan untuk hashing password pengguna. Standar OWASP merekomendasikan Argon2id dengan parameter minimal: memori 19 MB, 2 iterasi waktu, dan 1 thread paralel.

---

## 14. When NOT To Use
- **Jangan Gunakan Rate Limiting Kaku pada Komunikasi Internal Pod Microservices:** Membatasi pod Order Service memanggil Inventory Service dengan rate limiter statis 100 req/detik dapat menyebabkan transaksi valid pelanggan gagal saat jam sibuk.
- **Jangan Gunakan Kriptografi Simetris (Shared Key) Tanpa Key Management Service (KMS):** Menyimpan kunci enkripsi AES `const SECRET = '1234567890...'` langsung di dalam kode Git repository (*Hardcoded Secrets*) adalah pelanggaran kepatuhan paling fatal dalam audit ISO 27001 dan PCI-DSS.

---

## 15. Common Mistakes
1. **Mengandalkan Obfuscation (UUID):** Mengira bahwa mengganti integer ID `101` dengan UUID `e4d909c2-...` sudah menyelesaikan masalah BOLA. UUID hanya menyulitkan penyerang menebak nomor sekuensial (*Enumeration*), namun jika UUID bocor di tempat lain, penyerang tetap bisa mengakses data tanpa dicegat oleh otorisasi server!
2. **Verbose Error Messages di Produksi:** Menampilkan pesan error detail `SequelizeDatabaseError: syntax error at or near "SELECT"` beserta stack trace direktori file server ke browser pengguna saat HTTP 500.
3. **CORS `Access-Control-Allow-Origin: *` Bersama `Allow-Credentials: true`:** Mengizinkan situs berbahaya mana pun di internet membaca data pengguna yang sedang login di sistem Anda via AJAX request browser.
4. **Hashing Password dengan MD5 / SHA-256:** Kecepatan ekstrem SHA-256 (bisa mencapai 10 miliar hash per detik di GPU modern) membuatnya sangat rapuh terhadap serangan *Brute-Force Offline*.

---

## 16. Best Practices

### Must Have
- Terapkan validasi kepemilikan data eksplisit pada query database (**BOLA Prevention**): `SELECT * FROM data WHERE id = :id AND user_id = :current_user_id`.
- Gunakan schema validator (seperti Zod, Joi, atau class-validator) dengan konfigurasi `stripUnknown: true` untuk memusnahkan ancaman **Mass Assignment**.
- Simpan password menggunakan **Argon2id** atau **bcrypt (cost factor minimal 12)**.

### Recommended
- Pasang HTTP Security Headers menggunakan middleware standar (seperti `helmet` di Node.js):
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains` (HSTS)
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
- Terapkan **Envelope Encryption**: Data dienkripsi dengan DEK (*Data Encryption Key*), lalu DEK dienkripsi dengan KEK (*Key Encryption Key*) yang dikelola di AWS KMS / HashiCorp Vault.

### Advanced
- Implementasikan sertifikat **mTLS (Mutual TLS)** antar microservices di dalam Kubernetes Service Mesh (Istio / Linkerd) untuk menjamin enkripsi *Zero-Trust* antar pod internal.

---

## 17. Troubleshooting

| Masalah Keamanan | Akar Masalah | Tindakan Investigasi | Langkah Perbaikan |
|---|---|---|---|
| **Peringatan Vulnerability: BOLA Terdeteksi saat Pentest** | Handler controller langsung mengambil data berdasarkan parameter ID tanpa mencocokkan `req.user.id` | Audit seluruh baris query database di repository layer | Tambahkan filter user ID atau implementasikan middleware Authorizer per objek |
| **Server CPU 100% saat Login User Masuk** | Cost factor bcrypt terlalu tinggi (misal: `rounds = 16` memakan waktu 4 detik CPU per login) | Profiling durasi eksekusi hash password dengan `console.time` | Turunkan cost factor ke angka wajar (10 - 12) yang memakan waktu ~100-250 ms |
| **Request Valid Ditolak HTTP 429 Terlalu Sering** | Token bucket rate limiter terlalu sempit atau IP user dihitung per NAT kantor/kampus | Periksa header `X-Forwarded-For` dan log proxy | Ganti identitas rate limit dari IP menjadi kombinasi `IP + UserID` atau perbesar kapasitas bucket |

---

## 18. Exercise
1. Tulis simulator algoritma **Token Bucket Rate Limiter** murni di Node.js.
2. Konfigurasikan ember dengan kapasitas 5 token dan kecepatan isi ulang 1 token per detik.
3. Kirimkan rentetan 10 request simultan. Buktikan 5 request pertama lolos (menguras bucket), dan 5 request berikutnya ditolak dengan HTTP 429.
4. Tunggu 3 detik, lalu kirim 3 request lagi dan buktikan bahwa request kembali diizinkan seiring bertambahnya token baru.

---

## 19. Challenge
Rancang arsitektur keamanan end-to-end untuk API Pembayaran Kartu Kredit yang mematuhi standar **PCI-DSS Level 1**:
1. Rancang arsitektur enkripsi data nomor kartu kredit (PAN) dan CVV di database menggunakan AES-256-GCM dan AWS KMS Envelope Encryption.
2. Tentukan field apa yang boleh disimpan permanen, field apa yang **diharamkan disimpan sama sekali** setelah otorisasi (sesuai aturan PCI-DSS), dan bagaimana melakukan *Tokenisasi* nomor kartu kredit!

---

## 20. Summary
Keamanan backend bukanlah fitur tambahan yang dipasang di akhir proyek; keamanan adalah pola pikir arsitektural (*Security by Design*). Dengan memahami taksonomi ancaman OWASP API Security Top 10, mengimplementasikan Token Bucket Rate Limiting, serta menerapkan fungsi hash defensif Argon2id dan enkripsi AES-256-GCM, Anda membangun benteng pertahanan digital yang kokoh bagi data dan reputasi organisasi Anda.

---
[⬅️ Module 01: Autentikasi Modern & OAuth 2.0 PKCE](./Module-01-Auth-Session-JWT-OAuth2-OIDC-PKCE.md) | [📋 Silabus Induk](../README.md) | [BAB 08 Quiz & Challenge ➡️](./BAB-08-Quiz-dan-Challenge.md)
---
