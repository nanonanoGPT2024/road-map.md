---
[⬅️ BAB 05 Quiz & Challenge](../BAB-05-Data-Layer-ORMs-dan-Serverless-Databases/BAB-05-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Passwordless WebAuthn & MFA ➡️](./Module-02-Passwordless-WebAuthn-Passkeys-TOTP-MFA.md)
---

# Module 01: Auth.js / NextAuth Architecture: Secure JWT Cookies, OAuth 2.0 PKCE, & Edge Middleware Route Guards

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Memahami arsitektur inti **Auth.js (NextAuth.js v5)** dan evolusinya menuju model *Universal Auth* di seluruh layer Next.js App Router (Server Components, Server Actions, Route Handlers, Client Components, dan Edge Middleware).
- Menganalisis perbandingan arsitektural antara **Stateless JWT Sessions (JWE/JWS)** vs **Database Sessions (Stateful)** dalam konteks skalabilitas serverless, latensi, dan kemampuan revokasi sesi (*instant session revocation*).
- Merancang proteksi cookie tingkat tinggi: menguasai prefiks cookie standar browser (`__Host-`, `__Secure-`), atribut keamanan (`HttpOnly`, `SameSite=Lax/Strict`, `Secure`), dan mekanisme *Cookie Chunking* untuk token berukuran besar.
- Menguasai alur kerja protokol **OAuth 2.0 dengan PKCE (Proof Key for Code Exchange)** untuk mengamankan pertukaran authorization code dari serangan intersepsi jaringan.
- Mengimplementasikan **Edge Middleware Route Guards** untuk memverifikasi token dan hak akses pengguna (*Role-Based Access Control / RBAC*) langsung di CDN Edge Node dengan latensi mendekati 0ms tanpa menyentuh database utama.

---

## 2. Prerequisite
- Memahami dasar-dasar protokol HTTP (Headers, Set-Cookie, Redirects).
- Memahami konsep kriptografi dasar (Hashing SHA-256, Public-Private Key Signatures, HMAC).
- Memahami konsep Next.js App Router dan Edge Middleware dari Bab 03.

---

## 3. Concept
Autentikasi pada arsitektur web tradisional biasanya mengandalkan *Session ID* sederhana yang disimpan dalam memori server (seperti session Express di Redis). Server memeriksa ID tersebut pada setiap request masuk ke database.

Namun, dalam arsitektur **Full-Stack Serverless dan Edge**, request pengguna dapat diarahkan ke ratusan edge node di seluruh dunia. Jika setiap request ke route `/dashboard` harus melakukan query database untuk memvalidasi sesi, aplikasi akan menderita *high latency* dan pemborosan koneksi database.

**Auth.js v5** mengadopsi pendekatan **Stateless Secure JWT Session**:
Token sesi ditandatangani secara kriptografis (*signed JWS*) atau dienkripsi (*encrypted JWE*) menggunakan secret key server, lalu disimpan di dalam cookie browser dengan proteksi ketat (`HttpOnly`, `Secure`, `SameSite`). 

```
[ Browser Client ]
       |
       | Request + Cookie: __Host-authjs.session-token (JWE Kriptografis)
       v
[ Edge Middleware (Cloudflare / Vercel Edge) ]
       |
       | 🛡️ Verifikasi Signature Kriptografis via Web Crypto API (Sub-1ms, 0 Database Query!)
       +---> Token Valid? ---> Lanjut ke Server Component (Render Halaman)
       |
       +---> Token Tidak Sah? ---> Redirect ke /login
```

Verifikasi sesi dapat dilakukan secara lokal langsung di **Edge Node terdekat** hanya dengan memeriksa validitas signature matematika token, tanpa perlu melakukan panggilan jaringan (*network call*) ke database pusat!

---

## 4. Why? (Mengapa Membutuhkan Auth.js, PKCE, & Edge Guards?)
1. **Pencegahan Serangan XSS & Pencurian Sesi**:
   - Jika token disimpan di `localStorage`, skrip JavaScript jahat yang terinjeksi via XSS dapat dengan mudah mengeksekusi `localStorage.getItem("token")` dan membajak akun pengguna.
   - Menyimpan token di cookie dengan flag `HttpOnly` membuat token **100% tidak terlihat dan tidak dapat diakses oleh JavaScript browser**, mematikan vektor pencurian sesi via XSS.
2. **Mitigasi Intersepsi Kode pada OAuth 2.0 (PKCE)**:
   - Alur OAuth klasik rentan terhadap pencurian *authorization code* di jaringan publik. PKCE (*Proof Key for Code Exchange*) mewajibkan client membuat `code_verifier` rahasia dan mengirimkan hash `code_challenge` ke identity provider (Google, GitHub), sehingga pihak penyerang tidak dapat menukar kode otorisasi curian tanpa verifier asli.
3. **Performa Proteksi Rute (Edge Middleware)**:
   - Memeriksa hak akses di level Server Component berarti serverless function harus *boot up* dan memproses request sebelum menolak akses.
   - Dengan **Edge Middleware Guard**, request tanpa otentikasi ditolak atau dialihkan ke halaman login langsung di perbatasan CDN dalam waktu kurang dari 5 milidetik.

---

## 5. What? (Komponen Utama Auth.js v5)

### A. Universal Auth Helpers
Auth.js v5 menyatukan seluruh fungsi otentikasi menjadi satu titik masuk tunggal:
- `auth()`: Dapat dipanggil di Server Component, Server Action, Route Handler, dan Edge Middleware.
- `handlers`: Handler endpoint `/api/auth/[...nextauth]` untuk GET dan POST.
- `signIn()` dan `signOut()`: Fungsi mutasi otentikasi universal.

### B. Anatomi Cookie Prefixes (`__Host-` & `__Secure-`)
Standar browser modern (RFC 6265bis) menerapkan aturan khusus untuk cookie dengan prefiks:
- `__Secure-`: Wajib dikirim hanya melalui HTTPS (`Secure=true`).
- `__Host-`: Wajib HTTPS, **tidak boleh memiliki atribut `Domain`** (terkunci hanya pada host spesifik, tidak bocor ke subdomain), dan `Path` wajib bernilai `/`. Ini adalah standar proteksi cookie tertinggi di web modern.

---

## 6. How? (Implementasi Konfigurasi & Middleware)

### 1. Inisialisasi Auth.js v5 (auth.ts)
```typescript
import NextAuth from "next-auth";
import GitHub from "next-auth/providers/github";
import Google from "next-auth/providers/google";

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    GitHub({
      clientId: process.env.AUTH_GITHUB_ID!,
      clientSecret: process.env.AUTH_GITHUB_SECRET!,
    }),
    Google({
      clientId: process.env.AUTH_GOOGLE_ID!,
      clientSecret: process.env.AUTH_GOOGLE_SECRET!,
    }),
  ],
  session: {
    strategy: "jwt", // Stateless JWT session untuk performa Edge
    maxAge: 30 * 24 * 60 * 60, // 30 hari
  },
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        // Suntikkan role pengguna ke dalam payload JWT
        token.role = user.role || "USER";
        token.id = user.id;
      }
      return token;
    },
    async session({ session, token }) {
      if (token && session.user) {
        session.user.role = token.role as string;
        session.user.id = token.id as string;
      }
      return session;
    },
  },
});
```

### 2. Edge Middleware Route Guard (middleware.ts)
```typescript
import { auth } from "@/auth";
import { NextResponse } from "next/server";

export default auth((req) => {
  const { nextUrl } = req;
  const isLoggedIn = !!req.auth;
  const userRole = req.auth?.user?.role;

  const isApiAuthRoute = nextUrl.pathname.startsWith("/api/auth");
  const isDashboardRoute = nextUrl.pathname.startsWith("/dashboard");
  const isAdminRoute = nextUrl.pathname.startsWith("/admin");

  if (isApiAuthRoute) return NextResponse.next();

  // 1. Proteksi Halaman Dashboard (Wajib Login)
  if (isDashboardRoute && !isLoggedIn) {
    const redirectUrl = new URL("/login", nextUrl.origin);
    redirectUrl.searchParams.set("callbackUrl", nextUrl.pathname);
    return NextResponse.redirect(redirectUrl);
  }

  // 2. Proteksi Halaman Admin (Role-Based Guard)
  if (isAdminRoute) {
    if (!isLoggedIn) return NextResponse.redirect(new URL("/login", nextUrl.origin));
    if (userRole !== "ADMIN") return NextResponse.redirect(new URL("/unauthorized", nextUrl.origin));
  }

  return NextResponse.next();
});

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
```

### 3. Mengakses Sesi di React Server Component & Server Action
```typescript
// app/dashboard/page.tsx (Server Component)
import { auth } from "@/auth";
import { redirect } from "next/navigation";

export default async function DashboardPage() {
  const session = await auth();
  if (!session?.user) redirect("/login");

  return (
    <div>
      <h1>Selamat Datang, {session.user.name}!</h1>
      <p>Role Akses Anda: {session.user.role}</p>
    </div>
  );
}
```

---

## 7. Analogy
Bayangkan sebuah konser VIP berkecepatan tinggi:
- **Database Session**: Setiap kali Anda ingin berpindah ruangan (toilet, kantin, panggung utama), satpam harus menelepon kantor pusat untuk memeriksa nomor registrasi Anda di buku besar komputer induk. Jika kantor pusat sibuk atau jaringannya putus, Anda tertahan di depan pintu (*High Database Latency / Single Point of Failure*).
- **Stateless JWT dengan Edge Guard**: Di pintu masuk, panitia menyematkan gelang bercap hologram anti-palsu (*Digitally Signed JWT*). Setiap satpam di setiap pintu (*Edge Nodes*) cukup melihat kilau segel hologram gelang Anda menggunakan lampu UV (*Web Crypto Verification*). Dalam 0.1 detik Anda dipersilakan masuk tanpa ada yang perlu menelepon kantor pusat!

---

## 8. Diagram Alur OAuth 2.0 PKCE & Edge Verification

```
[ Browser Client ]             [ Authorization Server ]           [ App Edge Middleware ]
        |                                  |                                 |
        | 1. Generate verifier & challenge |                                 |
        | -------------------------------> |                                 |
        |    GET /authorize                |                                 |
        |    (code_challenge=SHA256(v))    |                                 |
        |                                  |                                 |
        | 2. User Login & Setuju           |                                 |
        | <------------------------------- |                                 |
        |    Redirect + Auth Code          |                                 |
        |                                  |                                 |
        | 3. POST /token                   |                                 |
        |    (code + code_verifier) -----> |                                 |
        |                                  | (Verifikasi SHA256(v) == c)    |
        | 4. Return Access & ID Token      |                                 |
        | <------------------------------- |                                 |
        |                                                                    |
        | 5. Simpan ke __Host- Cookie (HttpOnly, Secure)                     |
        |                                                                    |
        | 6. Request GET /dashboard + Cookie ------------------------------> |
        |                                                                    | 7. Verifikasi JWE
        |                                                                    |    secara lokal (0ms)
        | <----------------------------------------------------------------- |
        |    200 OK (Render Halaman Langsung di Edge!)                       |
```

---

## 9. Simple Example: Perbandingan Anatomi Cookie Session

| Properti Cookie | Nilai Standar Enterprise | Mengapa Wajib? |
| :--- | :--- | :--- |
| **Nama Cookie** | `__Host-authjs.session-token` | Memaksa browser menolak cookie jika tidak HTTPS atau dikirim ke domain lain. |
| **`HttpOnly`** | `true` | Mencegah pembacaan cookie oleh JavaScript (`document.cookie`), kebal serangan XSS. |
| **`Secure`** | `true` | Cookie hanya dikirimkan melalui koneksi TLS/HTTPS terenkripsi. |
| **`SameSite`** | `Lax` (atau `Strict`) | Mencegah cookie dikirimkan pada permintaan lintas situs pihak ketiga (*CSRF Defense*). |
| **`Path`** | `/` | Memastikan cookie berlaku untuk seluruh rute dalam domain aplikasi. |

---

## 10. Practical Example: Mengatasi Batas Ukuran Cookie 4KB (Cookie Chunking)
Standar HTTP melarang satu cookie melebihi ukuran 4096 bytes. Jika JWT Anda memuat banyak metadata (roles, permissions, claims), browser akan memotong cookie tersebut dan sesi pengguna akan rusak.

Auth.js secara otomatis menerapkan **Cookie Chunking**:
- Chunk 1: `__Host-authjs.session-token.0` (3900 bytes)
- Chunk 2: `__Host-authjs.session-token.1` (1200 bytes)

Saat request masuk, serverless runtime menggabungkan seluruh chunk kembali menjadi satu token utuh sebelum diverifikasi.

---

## 11. Real-World Example: Multi-Tenant Enterprise Role Guard
Pada sistem B2B SaaS, hak akses pengguna terbagi menjadi `OWNER`, `MEMBER`, dan `AUDITOR` di level organisasi tertentu:

```typescript
import { auth } from "@/auth";
import { TRPCError } from "@trpc/server";

export async function requireOrgRole(targetOrgId: string, requiredRole: "OWNER" | "MEMBER") {
  const session = await auth();
  if (!session?.user) {
    throw new TRPCError({ code: "UNAUTHORIZED", message: "Silakan login terlebih dahulu" });
  }

  // Ambil data tenant dari token JWT
  const memberships = (session.user as any).organizations || [];
  const currentOrg = memberships.find((org: any) => org.id === targetOrgId);

  if (!currentOrg) {
    throw new TRPCError({ code: "FORBIDDEN", message: "Anda bukan anggota dari organisasi ini" });
  }

  if (requiredRole === "OWNER" && currentOrg.role !== "OWNER") {
    throw new TRPCError({ code: "FORBIDDEN", message: "Aksi ini membutuhkan hak akses OWNER organisasi" });
  }

  return { user: session.user, org: currentOrg };
}
```

---

## 12. Trade-offs: Stateless JWT vs Database Sessions

| Parameter | Stateless JWT Session | Database Session (Stateful) |
| :--- | :--- | :--- |
| **Latensi di Edge** | **Sangat Cepat (<1ms, No Network)** | Lambat (Harus query DB/Redis) |
| **Beban Database** | **Nol Query per Request** | 1 Query per Request |
| **Revokasi Sesi Instan** | Sulit (Membutuhkan Token Blacklist) | **Sangat Mudah (Hapus baris di DB)** |
| **Ukuran Cookie** | Cenderung Besar (1KB–4KB) | Sangat Kecil (Session ID ~32 bytes) |
| **Kesesuaian Serverless** | **Pilihan Utama (Ideal)** | Membutuhkan Redis berlatensi rendah |

---

## 13. When To Use Auth.js Stateless JWT
- Anda membangun aplikasi modern di atas Vercel / Cloudflare Workers / AWS Amplify.
- Anda memprioritaskan latensi halaman dan *Time to First Byte (TTFB)* yang super instan.
- Anda ingin menghemat ratusan juta koneksi database yang hanya digunakan untuk memeriksa apakah pengguna masih login.

---

## 14. When NOT To Use Stateless JWT
- Sistem perbankan atau finansial kritis yang menuntut **pembatalan sesi instan dalam milidetik yang sama** saat akun dibekukan oleh fraud detection system (gunakan Database Session di Redis).
- Aplikasi yang menyimpan ratusan izin kustom per pengguna yang melebihi batas 4KB cookie.

---

## 15. Common Mistakes
1. **Menggunakan JWT Rahasia yang Lemah**:
   - Menyetel `AUTH_SECRET="123456"` atau teks sembarangan. Penyerang dapat memalsukan signature JWT dan menjadi admin! Selalu generate via `npx auth secret` (minimal 32 byte string acak).
2. **Menyimpan Token Akses OAuth Eksternal di Browser Client**:
   - Mengekspos Google / GitHub Access Token ke client component. Jika client di-XSS, penyerang bisa mengakses email atau repositori privat pengguna.
3. **Lupa Memasang Config Matcher di Middleware**:
   - Jika `matcher` di `middleware.ts` tidak mengecualikan folder `_next/static` atau gambar, setiap file gambar dan CSS akan memicu eksekusi middleware, memboroskan komputasi edge Anda!

---

## 16. Best Practices

### Must Have
- Selalu gunakan opsi `HttpOnly: true` dan `Secure: true` pada seluruh cookie otentikasi.
- Gunakan variabel lingkungan `AUTH_SECRET` yang di-generate secara kriptografis.
- Batasi masa berlaku JWT (*Expiration Time*) maksimal 7–30 hari dan kombinasikan dengan refresh token pattern jika perlu masa aktif panjang.

### Recommended
- Implementasikan prefiks `__Host-` di environment produksi untuk mencegah serangan manipulasi cookie dari subdomain lain (*Subdomain Cookie Injection*).
- Gunakan Edge Middleware untuk proteksi rute statis dasar dan Server Components untuk proteksi data granular.

### Advanced
- Gabungkan stateless JWT dengan *Session Version Number* di JWT payload. Jika user logout dari semua perangkat, naikkan versi di database sekali saja, sehingga JWT lama otomatis ditolak.

### Avoid
- Jangan pernah menyimpan password hash atau data sensitif pengguna (seperti nomor KTP atau nomor kartu kredit) di dalam payload JWT.

---

## 17. Troubleshooting Guide

| Gejala Error | Analisis Akar Masalah | Solusi |
| :--- | :--- | :--- |
| Loop Redirect tiada henti (`ERR_TOO_MANY_REDIRECTS`) antara `/login` dan `/dashboard`. | Middleware memeriksa rute `/login` dan mencoba me-redirect kembali ke `/login` saat belum terotentikasi. | Pastikan rute publik dan `/login` dikecualikan dari pemeriksaan proteksi middleware. |
| User sering ter-logout sendiri secara misterius saat membuka halaman tertentu. | Ukuran cookie JWT melebihi 4KB dan browser menolak sebagian chunk cookie. | Pangkas data yang disimpan di dalam token JWT (`callbacks.jwt`). Simpan hanya `id` dan `role`. |
| Error `UntrustedHost: Host must be trusted` saat deploy di reverse proxy. | Auth.js tidak mengenali header `x-forwarded-host` dari proxy Nginx atau Vercel. | Tambahkan variabel lingkungan `AUTH_TRUST_HOST=true` pada `.env`. |

---

## 18. Exercise
- **Easy**: Buat fungsi middleware yang mengecek header `authorization: Bearer <token>` sederhana dan mengembalikan status 401 jika kosong.
- **Medium**: Konfigurasikan callback `jwt` dan `session` di Auth.js untuk menyertakan `subscriptionTier: "FREE" | "PRO"` dari database ke dalam sesi pengguna.
- **Hard**: Rancang skema *Session Versioning* di mana token JWT tetap stateless, tetapi memiliki properti `tokenVersion`. Jika pengguna menekan tombol "Logout dari Semua Perangkat", sistem cukup menaikkan `tokenVersion` di tabel database.

---

## 19. Challenge
Bangun sistem simulasi Edge Route Guard mandiri yang mengimplementasikan verifikasi HMAC-SHA256 signature pada cookie sesi, memvalidasi role pengguna (`ADMIN` vs `MEMBER`), serta mengimplementasikan mitigasi Cookie Chunking jika ukuran token melebihi 256 karakter.

---

## 20. Summary
- **Auth.js (NextAuth.js v5)** menghadirkan arsitektur otentikasi universal yang menyederhanakan manajemen sesi di seluruh lapisan Next.js App Router.
- **Stateless JWT Sessions** adalah tulang punggung performa tinggi di ekosistem Serverless, memotong query database verifikasi sesi menjadi nol.
- **Edge Middleware Route Guards** bertindak sebagai perisai terdepan di CDN global, menangkal akses ilegal dalam waktu kurang dari 5ms sebelum kode serverless utama sempat diinisialisasi.

---

## Hands-on Practice: Simulasi NextAuth Edge Session Guard & Cookie Verification
Jalankan simulator verifikasi token kriptografis Edge Middleware dan RBAC guard mandiri:

```bash
node Full-Stack/BAB-06-Autentikasi-Full-Stack-dan-WebAuthn/hands-on/m01/nextauth_edge_session_guard_sim.js
```

---
[⬅️ BAB 05 Quiz & Challenge](../BAB-05-Data-Layer-ORMs-dan-Serverless-Databases/BAB-05-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Passwordless WebAuthn & MFA ➡️](./Module-02-Passwordless-WebAuthn-Passkeys-TOTP-MFA.md)
---
