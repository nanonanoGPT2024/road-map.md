# SEKSI 01 — IDENTITAS MODUL
* **Track:** 03-Frontend-and-Mobile
* **Kurikulum:** Next.js Enterprise Architecture
* **Bab:** 07 — Enterprise Security dan Auth
* **Modul:** 01 — Enterprise Security, Identity Management, & RBAC
* **Target Audience:** Lead Engineers, Senior Full-Stack Developers, Enterprise Architects
* **Prasyarat:** Next.js App Router (v14+), React Server Components (RSC), Node.js Web Crypto API, Pemahaman Protokol OAuth2/OIDC, TypeScript Tingkat Lanjut.

---

# SEKSI 02 — LEARNING OBJECTIVES
Setelah menyelesaikan modul ini, peserta didik mampu:
1. Merancang dan mengimplementasikan arsitektur Identity Management berbasis Next.js App Router yang mematuhi standar Zero Trust.
2. Membangun sistem otentikasi hybrid (stateless token validation via Web Crypto API di Edge Middleware dan stateful/database session verification di Node.js Runtime).
3. Menerapkan skema Role-Based Access Control (RBAC) dan Attribute-Based Access Control (ABAC) yang tahan manipulasi di level Middleware, React Server Component (RSC), Route Handlers, dan Server Actions.
4. Mencegah kerentanan kritis seperti Broken Object Level Authorization (BOLA), Token Side-Channel Leaks, Cross-Site Scripting (XSS), dan Cross-Site Request Forgery (CSRF) pada ekosistem RSC.
5. Mengonfigurasi integrasi OpenID Connect (OIDC) tingkat lanjut dengan enterprise Identity Providers (misalnya Okta, Keycloak, Azure AD) menggunakan enkripsi payload dan rotasi kunci publik (JWKS).

---

# SEKSI 03 — MINDSET & MENTAL MODEL
Dalam arsitektur frontend tradisional (Single Page Applications/SPA), keamanan otentikasi sering kali diserahkan sepenuhnya ke API Gateway, sementara browser menyimpan access token di `localStorage` atau memori sementara. Mental model ini **rusak total** dalam arsitektur Next.js App Router.

### Paradigma Zero Trust pada Next.js
Pada Next.js, batas komputasi terbagi menjadi tiga:
1. **Client Boundary (Browser):** Lingkungan yang sepenuhnya tidak tepercaya (*untrusted*).
2. **Edge Boundary (Middleware):** Lingkungan komputasi cepat (*lightweight V8 isolate*), ideal untuk inspeksi heuristik awal dan routing, tetapi tidak boleh dipercaya sebagai satu-satunya *gatekeeper* otorisasi final.
3. **Server Boundary (RSC, Route Handlers, Server Actions):** Lingkungan eksekusi aman (*trusted execution environment*), memiliki akses ke database internal, private VPC, dan kunci kriptografi sensitif.

```
       UNTRUSTED                      BOUNDARY                      TRUSTED
┌───────────────────────┐     ┌───────────────────────┐     ┌───────────────────────┐
│        BROWSER        │───▶ │    EDGE MIDDLEWARE    │───▶ │   NODE.JS BACKEND     │
│  (Next.js Client / UI)│     │  (Inspection/Routing) │     │  (RSC, Actions, APIs) │
└───────────────────────┘     └───────────────────────┘     └───────────────────────┘
  Cookie: HttpOnly;             Verify JWT Signature;         Resolve DB Session;
  SameSite=Lax; Secure          Heuristic Role Routing        Fine-Grained ABAC/RBAC
```

**Aturan Emas:** Jangan pernah mempercayai validasi yang hanya dilakukan di Middleware. Middleware berfungsi sebagai *gatekeeper* pengalaman pengguna (UX guard) dan filter lapisan pertama. Server Components, Route Handlers, dan Server Actions **wajib** melakukan validasi identitas dan otorisasi independen secara terisolasi sebelum memproses atau mengembalikan data sensitif.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

```
+----------------------------------------------------------------------------------------------------+
|                                      NEXT.JS RUNTIME TOPOLOGY                                      |
+----------------------------------------------------------------------------------------------------+
 [BROWSER]                                                                                            
     │                                                                                                
     │ 1. Request with Encrypted Session Cookie (__Host-auth-token)                                   
     ▼                                                                                                
 ┌──────────────────────────────────────────────────────────────────────────────────────────────────┐ 
 │ 2. EDGE MIDDLEWARE (middleware.ts)                                                               │ 
 │    ├── A. Web Crypto API: Decrypt & Verify JWE/JWS Signature via In-Memory JWKS Cache            │ 
 │    ├── B. Parse Claims: { sub, tenantId, roles: ['AUDITOR'] }                                    │ 
 │    ├── C. URL Path Inspection: Matches '/admin/*' against claims.roles                          │ 
 │    │       └── DENIED: Rewrite to /403 or Redirect to /login                                     │ 
 │    └── D. PASSED: Inject Identity Headers (x-user-id, x-tenant-id) via request mutation         │ 
 └──────────────────────────────────────────────────────────────────────────────────────────────────┘ 
     │                                                                                                
     │ 3. Forward to Target Server Boundary (Upstream Internal Transfer)                             
     ▼                                                                                                
 ┌──────────────────────────────────────────────────────────────────────────────────────────────────┐ 
 │ 4. SERVER RUNTIME (RSC / SERVER ACTIONS / ROUTE HANDLERS)                                        │ 
 │    ├── A. Layer 1: Cryptographic Validation Check                                               │ 
 │    │       └── Do NOT trust 'x-user-id' from headers blindly (Prevent Header Spoofing via        │ 
 │    │           direct client requests). Read and decrypt cookies directly on the server.         │ 
 │    ├── B. Layer 2: Domain Context Hydration                                                      │ 
 │    │       └── React 'cache()' memoizes getSession() per request execution graph                 │ 
 │    ├── C. Layer 3: Enterprise RBAC/ABAC Policy Engine Execution                                  │ 
 │    │       └── Evaluate: PolicyEngine.can(user, 'read:financial_records', targetResource)       │ 
 │    └── D. Layer 4: Data Layer Execution                                                          │ 
 │            └── Query Database via Multi-Tenant Row-Level Security (RLS) Parameter                │ 
 └──────────────────────────────────────────────────────────────────────────────────────────────────┘ 
     │                                                                                                
     │ 5. Render Secure RSC Payload / Return JSON Action Response                                    
     ▼                                                                                                
 [BROWSER UI]                                                                                         
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. The Dynamic Request Lifecycle
Ketika sebuah request masuk ke Next.js:
* **Edge Runtime (Middleware):** Dijalankan pada V8 Isolate. V8 Isolate tidak mendukung seluruh ekosistem Node.js core APIs (misalnya `crypto` berbasis OpenSSL bawaan tidak tersedia secara identik, melainkan menggunakan `SubtleCrypto` dari Web Crypto standard). Operasi verifikasi token harus non-blocking dan hemat memori.
* **Server Components (RSC):** RSC dijalankan secara streaming. Komponen dirender ke dalam *RSC Payload* (representasi pohon virtual biner/JSON). Jika otorisasi gagal di tengah eksekusi RSC pohon anak, Next.js tidak dapat mengubah status code HTTP jika chunk respons awal sudah di-flush ke client. Oleh karena itu, otorisasi data sensitif harus diselesaikan sebelum pemanggilan data (*data-fetching*).

### 2. Header Spoofing Vulnerability & Mutated Requests
Ketika middleware memodifikasi header request menggunakan:
```typescript
const requestHeaders = new Headers(request.headers);
requestHeaders.set('x-user-id', user.id);
return NextResponse.next({ request: { headers: requestHeaders } });
```
Header ini diteruskan ke Server Components melalui `headers()` dari `next/headers`. Namun, jika aplikasi berada di balik reverse proxy yang tidak terkonfigurasi dengan benar, penyerang luar dapat menyuntikkan `x-user-id` secara langsung dari client. Middleware harus secara eksplisit menghapus atau me-reset header sensitif ini sebelum menyetel nilainya kembali.

### 3. Session Caching Lifecycle via React Cache
Dalam RSC, pemanggilan fungsi otentikasi di multiple komponen anak dapat menyebabkan *over-fetching* dan duplikasi dekripsi kriptografi yang mahal.
```
                  ┌──────────────────────┐
                  │    Incoming Request  │
                  └──────────┬───────────┘
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
   ┌─────────────────┐               ┌─────────────────┐
   │ Page Component  │               │ Navbar Component│
   └────────┬────────┘               └────────┬────────┘
            │ getSession()                    │ getSession()
            ▼                                 ▼
   ┌───────────────────────────────────────────────────┐
   │     React Cache Boundary (`cache(getSession)`)     │
   │  - Invocation 1: Decrypts & returns identity       │
   │  - Invocation 2: Cache Hit! Returns same reference │
   └───────────────────────────────────────────────────┘
```
Fungsi `cache()` memastikan runtime dekripsi token hanya dieksekusi **satu kali per siklus request**.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Token Storage: Stateless JWE vs. Database Session
* **Access Tokens (JWT/JWE):** Cocok untuk Edge Middleware karena tidak membutuhkan round-trip database. Kelemahan: Sulit untuk direvokasi secara instan sebelum masa kedaluwarsa habis (*TTL expiry*).
* **Reference Tokens (Database Session):** Menyimpan opaque string (misal UUIDv4) di cookie, state tersimpan di Redis/Database. Keuntungan: Revokasi instan. Kelemahan: Panggilan database per request menciptakan overhead latensi di Edge Middleware.

**Solusi Enterprise:** *Hybrid Stateless-Stateful Security Architecture*. Token yang disimpan di cookie adalah JWE (*JSON Web Encryption*) terenkripsi yang berisi Session Reference ID dan Role Snapshot. Middleware memvalidasi integritas kriptografi token untuk routing awal. Route Handlers / Server Actions mengevaluasi status aktif session dari memory store (misalnya Redis cluster) hanya ketika operasi mutasi sensitif dilakukan.

### The Cryptographic Cookie Standard
Penggunaan cookie wajib mengikuti skema pertahanan berikut:
* **Prefix `__Host-`:** Memaksa browser memastikan cookie hanya dikirim ke host asal yang tepat (mencegah subdomain hijacking), harus menggunakan flag `Secure`, dan path harus `/`.
* **`HttpOnly`:** Mencegah ekstraksi cookie via serangan XSS (`document.cookie`).
* **`SameSite=Lax` atau `SameSite=Strict`:** Mencegah pengiriman cookie otomatis pada cross-site request (mitigasi utama CSRF).

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi fondasi verifikasi token kriptografis menggunakan `jose` (kompatibel penuh dengan Edge Runtime dan Web Crypto API) dan validasi skema runtime via `zod`.

### 1. Schema Token & Core Crypto Utility
```typescript
// lib/auth/crypto.ts
import { jwtVerify, SignJWT, JWTPayload } from 'jose';
import { z } from 'zod';

export const UserRoleSchema = z.enum(['SUPER_ADMIN', 'ORG_ADMIN', 'MEMBER', 'AUDITOR']);
export type UserRole = z.infer<typeof UserRoleSchema>;

export const SessionPayloadSchema = z.object({
  sub: z.string().uuid(),
  email: z.string().email(),
  tenantId: z.string().uuid(),
  roles: z.array(UserRoleSchema),
  exp: z.number(),
  jti: z.string(),
});

export type SessionPayload = z.infer<typeof SessionPayloadSchema>;

const SECRET_KEY = new TextEncoder().encode(
  process.env.AUTH_SECRET || 'fallback-enterprise-secret-key-32-chars-minimum!'
);

export async function signSessionToken(payload: Omit<SessionPayload, 'exp' | 'jti'>): Promise<string> {
  return new SignJWT({ ...payload })
    .setProtectedHeader({ alg: 'HS256', typ: 'JWT' })
    .setJti(crypto.randomUUID())
    .setIssuedAt()
    .setExpirationTime('15m')
    .sign(SECRET_KEY);
}

export async function verifySessionToken(token: string): Promise<SessionPayload | null> {
  try {
    const { payload } = await jwtVerify(token, SECRET_KEY, {
      algorithms: ['HS256'],
    });

    const parsed = SessionPayloadSchema.safeParse(payload);
    if (!parsed.success) {
      return null;
    }

    return parsed.data;
  } catch (error) {
    return null;
  }
}
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis Kriptografi `lib/auth/crypto.ts`
1. `const SECRET_KEY = new TextEncoder().encode(...)`: Mengonversi string secret menjadi `Uint8Array`. Web Crypto API di Edge Runtime tidak menerima string mentah untuk algoritma simetris (`HS256`), melainkan byte array standar.
2. `new SignJWT({ ...payload })`: Menginisialisasi JWT builder dari modul `jose`. Modul ini tidak memiliki dependensi Node.js `crypto` C++ layer, sehingga zero-overhead di Cloudflare Workers dan V8 Isolates.
3. `.setJti(crypto.randomUUID())`: Menambahkan JWT ID unik. Elemen penting untuk mitigasi serangan *Replay Attack*, memungkinkan kita mencatat blacklist ID token di Redis jika dilakukan logout darurat.
4. `.setExpirationTime('15m')`: Membatasi masa hidup token hanya 15 menit, mengurangi resiko *credential abuse* jika token berhasil disadap.
5. `const parsed = SessionPayloadSchema.safeParse(payload)`: **Critical Defense Line.** Jangan pernah percaya isi payload hanya karena tanda tangan kriptografisnya valid. Validasi runtime menggunakan Zod menjamin struktur token tidak mengalami desinkronisasi versi atau manipulasi struktur internal.

---

# SEKSI 09 — STUDI KASUS NYATA (Real-World Enterprise Scenario)

### Skenario: Financial Multi-Tenant B2B SaaS Engine
Sebuah platform manajemen audit finansial multi-tenant melayani 500 perusahaan skala enterprise. 

**Persyaratan Keamanan:**
1. Isolasi Data Multi-Tenant: Tenant ID tidak boleh dimanipulasi oleh URL parameter tampering.
2. RBAC Dinamis:
   * `SUPER_ADMIN`: Akses cross-tenant hanya untuk operasi sistem.
   * `ORG_ADMIN`: Konfigurasi organisasi dan manajemen anggota internal.
   * `AUDITOR`: Hanya boleh membaca laporan finansial (`financial_records`), tidak boleh mengubah settingan akun.
   * `MEMBER`: Akses terbatas pada data milik entitas mereka sendiri.
3. Strict Defense-in-Depth: Upaya bypass middleware wajib dipatahkan pada level Server Action dan Database Layer.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Struktur direktori:
```text
├── middleware.ts
├── lib/
│   ├── auth/
│   │   ├── crypto.ts
│   │   ├── session.ts
│   │   └── rbac.ts
│   └── errors.ts
└── app/
    └── actions/
        └── financial-records.ts
```

### 1. Definisi Kontrol Akses Berbasis Peran (RBAC) & Kebijakan
```typescript
// lib/auth/rbac.ts
import { UserRole } from './crypto';

export type Permission = 
  | 'org:settings:update'
  | 'members:invite'
  | 'records:view'
  | 'records:create'
  | 'records:delete';

const ROLE_PERMISSIONS: Record<UserRole, readonly Permission[]> = {
  SUPER_ADMIN: ['org:settings:update', 'members:invite', 'records:view', 'records:create', 'records:delete'],
  ORG_ADMIN: ['org:settings:update', 'members:invite', 'records:view', 'records:create'],
  AUDITOR: ['records:view'],
  MEMBER: ['records:view', 'records:create'],
};

export class AccessControlEngine {
  static hasPermission(roles: UserRole[], permission: Permission): boolean {
    return roles.some((role) => ROLE_PERMISSIONS[role]?.includes(permission));
  }

  static assertPermission(roles: UserRole[], permission: Permission): void {
    if (!this.hasPermission(roles, permission)) {
      throw new Error(`FORBIDDEN: Missing permission [${permission}]`);
    }
  }

  static validateTenantContext(userTenantId: string, requestedTenantId: string, roles: UserRole[]): boolean {
    if (roles.includes('SUPER_ADMIN')) {
      return true; // Super admins can bypass tenant pinning for global debugging
    }
    return userTenantId === requestedTenantId;
  }
}
```

### 2. Edge Middleware Layer
```typescript
// middleware.ts
import { NextRequest, NextResponse } from 'next/server';
import { verifySessionToken } from './lib/auth/crypto';

const ROUTE_RULES: Array<{ prefix: string; roles: string[] }> = [
  { prefix: '/admin', roles: ['SUPER_ADMIN', 'ORG_ADMIN'] },
  { prefix: '/audit', roles: ['SUPER_ADMIN', 'AUDITOR'] },
];

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  
  // 1. Ekstraksi token dari Strict Encrypted Cookie
  const token = request.cookies.get('__Host-auth-token')?.value;

  // 2. Sanitasi header internal yang masuk dari internet untuk mencegah spoofing
  const cleanHeaders = new Headers(request.headers);
  cleanHeaders.delete('x-user-id');
  cleanHeaders.delete('x-tenant-id');
  cleanHeaders.delete('x-roles');

  const isPublicRoute = pathname.startsWith('/login') || pathname.startsWith('/api/public');
  if (isPublicRoute) {
    return NextResponse.next({ request: { headers: cleanHeaders } });
  }

  if (!token) {
    return handleUnauthorized(request);
  }

  const session = await verifySessionToken(token);
  if (!session) {
    return handleUnauthorized(request);
  }

  // 3. Evaluasi routing berbasis peran secara terpusat di Edge
  const matchedRule = ROUTE_RULES.find((rule) => pathname.startsWith(rule.prefix));
  if (matchedRule) {
    const hasRole = session.roles.some((r) => matchedRule.roles.includes(r));
    if (!hasRole) {
      return NextResponse.rewrite(new URL('/unauthorized', request.url));
    }
  }

  // 4. Set context internal untuk routing downstream
  cleanHeaders.set('x-user-id', session.sub);
  cleanHeaders.set('x-tenant-id', session.tenantId);
  cleanHeaders.set('x-roles', JSON.stringify(session.roles));

  return NextResponse.next({
    request: {
      headers: cleanHeaders,
    },
  });
}

function handleUnauthorized(request: NextRequest) {
  if (request.nextUrl.pathname.startsWith('/api/')) {
    return NextResponse.json({ error: 'UNAUTHORIZED' }, { status: 401 });
  }
  const loginUrl = new URL('/login', request.url);
  loginUrl.searchParams.set('redirect', request.nextUrl.pathname);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};
```

### 3. Server Boundary Session Resolver (React Cache Per-Request Context)
```typescript
// lib/auth/session.ts
import { cache } from 'react';
import { cookies } from 'next/headers';
import { verifySessionToken, SessionPayload } from './crypto';

/**
 * getSession dibungkus dengan React cache() untuk memastikan
 * parsing, dekripsi, dan validasi token hanya dieksekusi SEKALI 
 * per render lifecycle request.
 */
export const getSession = cache(async (): Promise<SessionPayload | null> => {
  const cookieStore = await cookies();
  const token = cookieStore.get('__Host-auth-token')?.value;

  if (!token) {
    return null;
  }

  return await verifySessionToken(token);
});

export async function requireAuth(): Promise<SessionPayload> {
  const session = await getSession();
  if (!session) {
    throw new Error('UNAUTHORIZED_REQUEST');
  }
  return session;
}
```

### 4. Defense-in-Depth pada Server Action
```typescript
// app/actions/financial-records.ts
'use server';

import { requireAuth } from '@/lib/auth/session';
import { AccessControlEngine } from '@/lib/auth/rbac';
import { z } from 'zod';

const CreateRecordSchema = z.object({
  targetTenantId: z.string().uuid(),
  amount: z.number().positive(),
  description: z.string().min(3).max(255),
});

export async function createFinancialRecord(formDataRaw: unknown) {
  // 1. Otorisasi Identitas (Gagal di sini = Eksekusi terhenti seketika)
  const session = await requireAuth();

  // 2. Validasi Skema Input Ketat
  const validation = CreateRecordSchema.safeParse(formDataRaw);
  if (!validation.success) {
    return { success: false, error: 'INVALID_INPUT', details: validation.error.flatten() };
  }

  const { targetTenantId, amount, description } = validation.data;

  // 3. Attribute-Based Policy Check (Cross-Tenant Tampering Guard)
  const isTenantAllowed = AccessControlEngine.validateTenantContext(
    session.tenantId,
    targetTenantId,
    session.roles
  );

  if (!isTenantAllowed) {
    console.error(`SECURITY VIOLATION: User ${session.sub} attempted cross-tenant access to ${targetTenantId}`);
    return { success: false, error: 'ACCESS_DENIED_CROSS_TENANT' };
  }

  // 4. Role-Based Access Control Assert
  try {
    AccessControlEngine.assertPermission(session.roles, 'records:create');
  } catch (error) {
    return { success: false, error: 'FORBIDDEN_INSUFFICIENT_PRIVILEGES' };
  }

  // 5. Database Interaction (Diisolasi dengan session.tenantId terverifikasi)
  // const record = await db.financialRecords.create({ ... });

  return {
    success: true,
    data: {
      id: crypto.randomUUID(),
      tenantId: targetTenantId,
      amount,
      description,
      createdBy: session.sub,
    },
  };
}
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Fitur / Arsitektur | Pure Stateless JWT (Cookie) | Database Session (Stateful via Redis) | Hybrid Architecture (Terpilih) |
| :--- | :--- | :--- | :--- |
| **Edge Compatibility** | Sangat Cepat (Native Web Crypto, zero network round-trip). | Rendah/Sedang (Harus query Redis per edge hop). | **Tinggi** (Kriptografi lokal di Edge, Redis hanya dipanggil di Server Runtime saat mutasi). |
| **Instant Revocation** | Sangat Sulit (Menunggu TTL token kedaluwarsa). | Instan (Hapus record session di Redis). | **Instan untuk Mutasi** (Edge membiarkan lewat, tetapi Server Action membatalkan request). |
| **Network Overhead** | Ukuran Cookie besar (~1-2KB per request). | Ukuran Cookie sangat kecil (~64 bytes UUID). | **Seimbang** (Payload JWT diminimalkan hanya untuk claims primer). |
| **Database Load** | 0 query ke database untuk otentikasi. | Sangat tinggi (1+ DB query per navigasi halaman). | **Minimal** (Query hanya saat otentikasi mutasi dan refresh cycle). |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Middleware Redirect Loop (Pitfall)
* **Kasus:** Middleware memverifikasi token dan menemukan token expired, lalu me-redirect ke `/login`. Namun, route `/login` tidak dikecualikan dalam blok evaluasi, memicu redirect loop tak terbatas: `/login` -> `/login` -> `/login`.
* **Mitigasi:** Gunakan matcher regex yang ketat dan secara eksplisit definisikan `PUBLIC_PATHS` sebelum eksekusi verifikasi token.

### 2. RSC Streaming Chunk Failure (Edge Case)
* **Kasus:** Komponen Server bersifat `async` dan melakukan otorisasi di dalam render body. Namun sebagian kerangka layout UI telah dikirim via streaming HTTP chunk ke browser dengan status `200 OK`. Jika otorisasi gagal di komponen daun (leaf component), server tidak dapat mengirimkan status `401/403` ke browser.
* **Mitigasi:** Eksekusi otorisasi fundamental pada Root Layout atau Page Entry point sebelum komponen anak async dimulai, atau panggil fungsi internal Next.js `redirect()` / `notFound()`, yang akan memotong rendering sub-tree tanpa membocorkan data parsial.

### 3. Header Forgery via Client Request
* **Kasus:** Pengembang bergantung pada `headers().get('x-user-id')` di Server Component, mempercayai bahwa header tersebut selalu di-set oleh Middleware. Penyerang mengirim request manual dengan menyuntikkan header mentah `x-user-id: 0000-admin-bypass`.
* **Mitigasi:** Wajib menghapus header internal sensitif di middleware (`request.headers.delete(...)`) sebelum meneruskan request downstream, dan **selalu prioritaskan** pembacaan langsung dari decrypted cookie via `getSession()` di Server Components.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Menyimpan Token di Web Storage (`localStorage` / `sessionStorage`)
* **Masalah:** Kerentanan absolut terhadap Cross-Site Scripting (XSS). Skrip berbahaya dari dependency pihak ketiga dapat mencuri token.
* **Solusi:** Gunakan cookie dengan flags `__Host-`, `HttpOnly`, `Secure`, dan `SameSite=Lax`.

### 2. Memercayai Client Context untuk Keputusan Otorisasi
```typescript
// ANTI-PATTERN: Client mengirimkan userID yang dipercaya mentah-mentah
export async function deleteUserAction(targetUserId: string, currentUserId: string) {
  // JANGAN LAKUKAN INI! currentUserId bisa dipalsukan via direct POST request.
  if (currentUserId !== 'admin') throw new Error();
}

// SECURE PATTERN:
export async function deleteUserAction(targetUserId: string) {
  const session = await requireAuth(); // Ditarik langsung dari Session Cookie Server
  AccessControlEngine.assertPermission(session.roles, 'members:invite');
}
```

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI
1. **Cookie Prefixing:** Selalu gunakan format penamaan cookie `__Host-` untuk production environment guna menjamin flags `Secure` dan `Path=/` diterapkan oleh engine browser.
2. **Fail-Closed Principle:** Jika terjadi runtime exception selama evaluasi RBAC, sistem harus secara default menolak akses (*Deny by default*).
3. **Short-Lived Access Tokens:** Batasi masa aktif token stateless maksimal 15 menit, dikombinasikan dengan mekanisme *Sliding Refresh Tokens* di Server Action.
4. **Isolate Security Boundaries:** Pisahkan logika assertion izin bisnis (`AccessControlEngine`) dari UI/Presentation components.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI

### 1. Eliminasi Request Waterfalls dengan React Memoization
Pemanfaatan `cache()` dari paket `'react'` menjamin biaya verifikasi kriptografi (misalnya dekripsi RSA/AES via `jose`) bernilai konstan $O(1)$ untuk seluruh hierarki pemanggilan komponen dalam satu lifecycle request:
```typescript
import { cache } from 'react';
// Hanya dieksekusi 1x meski dipanggil di Layout, Page, dan 5 Child Components
export const getSession = cache(async () => { /* CPU-heavy decrypt operations */ });
```

### 2. Compact Serialization
Hindari memasukkan metadata profil berukuran masif (seperti data riwayat alamat atau preferensi tema) ke dalam session token cookie. Jaga ukuran token di bawah **4KB** (batas maksimal browser standard cookie size), disarankan < **1.5KB** agar tidak memecah paket MTU TCP jaringan (yang dapat menambah latensi initial packet transfer).

---

# SEKSI 16 — KEAMANAN & HARDENING

### Enkripsi Berlapis via JWE (JSON Web Encryption)
Untuk data kepatuhan PCI-DSS / HIPAA, claims di dalam token tidak boleh hanya ditandatangani (*Signed - JWT*), tetapi harus dienkripsi (*Encrypted - JWE*) menggunakan algoritma `A256GCM` sehingga inspeksi pasif pada level browser storage inspector tidak dapat membaca email atau role pengguna.

```typescript
import { CompactEncrypt, compactDecrypt } from 'jose';

// Enkripsi Payload ke JWE
export async function encryptSensitiveClaims(payload: Record<string, unknown>, secretKey: Uint8Array) {
  const plaintext = new TextEncoder().encode(JSON.stringify(payload));
  return new CompactEncrypt(plaintext)
    .setProtectedHeader({ alg: 'dir', enc: 'A256GCM' })
    .encrypt(secretKey);
}
```

---

# SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING
Semua kegagalan otorisasi harus dicatat sebagai security event terstruktur (*Structured Audit Logs*):

```typescript
export function logSecurityEvent(event: {
  eventType: 'AUTH_SUCCESS' | 'AUTH_FAILURE' | 'RBAC_VIOLATION';
  userId?: string;
  tenantId?: string;
  action: string;
  ip: string;
  resourceId?: string;
}) {
  console.warn(JSON.stringify({
    timestamp: new Date().toISOString(),
    severity: event.eventType === 'RBAC_VIOLATION' ? 'CRITICAL' : 'INFO',
    ...event,
  }));
  // Integrasikan dengan OpenTelemetry, Datadog, atau CloudWatch
}
```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

1. **Edge Middleware != Absolute Security:** Middleware adalah route router dan UX guard. Otorisasi data sejati berada di **RSC** dan **Server Actions**.
2. **HttpOnly + Host Prefix:** Gunakan `__Host-auth-token` dengan `HttpOnly; Secure; SameSite=Lax`.
3. **Session Hydration via `React.cache()`:** Mencegah multiple decryption overhead di multi-level komponen server.
4. **Clean Sensitive Headers:** Hapus header `x-*` di middleware sebelum menyuntikkan data context baru untuk menghindari injection attack via client headers.
5. **Fail Closed:** Default skema authorization adalah `DENY ALL` sampai izin secara eksplisit diberikan.

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal 1
Mengapa verifikasi identitas yang dilakukan secara eksklusif hanya di `middleware.ts` Next.js dianggap sebagai celah keamanan kritis dalam aplikasi enterprise?
* A. Middleware tidak berjalan pada rute statis.
* B. Middleware tidak dapat memvalidasi token JWT.
* C. Middleware berjalan sebelum routing, namun Server Actions dan Route Handlers dapat diakses langsung tanpa melewati pemeriksaan otorisasi data jika implementasi handler tidak melakukan validasi independen.
* D. Edge Runtime tidak mendukung Web Crypto API.

### Soal 2
Apa fungsi utama dari awalan cookie `__Host-` dalam mitigasi serangan otentikasi?
* A. Mengompresi ukuran payload cookie secara otomatis.
* B. Memaksa browser memastikan cookie hanya dikirim ke domain asal (tanpa subdomain), memiliki flag Secure, dan path bernilai `/`.
* C. Memungkinkan cookie dibaca oleh Web Workers dan Service Workers.
* D. Menginstruksikan Next.js untuk menyimpan session di Redis secara otomatis.

### Soal 3
Bagaimana fungsi `cache()` dari modul `react` meningkatkan efisiensi otentikasi di Server Components?
* A. Menyimpan payload session di local storage browser pengguna.
* B. Mencegah komputasi ulang dekripsi kriptografi token pada beberapa komponen yang meminta sesi pada satu render request yang sama.
* C. Menyimpan session pengguna di Redis secara permanen di seluruh request global.
* D. Menghubungkan sesi antara dua browser yang berbeda.

### Soal 4
Jika client mengirimkan header buatan sendiri `x-user-id: evil-attacker` secara manual ke aplikasi Next.js Anda, bagaimana cara paling aman untuk mencegah Server Components mempercayai header palsu tersebut?
* A. Mengabaikan keberadaan header tersebut karena RSC kebal terhadap header injection.
* B. Melarang semua request yang berasal dari luar negara domisili server.
* C. Di `middleware.ts`, hapus header `x-user-id` dari incoming request sebelum me-rewrite/next request ke server tree, atau baca session langsung dari cookie yang terenkripsi.
* D. Melakukan enkripsi pada seluruh parameter URL.

### Soal 5
Pada skenario Multi-Tenant, apa langkah mitigasi terbaik terhadap serangan IDOR (Insecure Direct Object Reference) saat pengguna mengubah `tenantId` pada Server Action payload?
* A. Mengonfigurasi CORS di Next.js middleware.
* B. Memverifikasi bahwa `tenantId` pada request payload identik dengan `tenantId` yang tersimpan pada payload token session yang tervalidasi secara kriptografis.
* C. Menyimpan ID pengguna di `sessionStorage`.
* D. Mengenkripsi path URL halaman dashboard.

---

### Kunci Jawaban & Analisis Singkat
1. **C** — Server Actions dan sub-routes memerlukan defense-in-depth karena middleware hanya mengawal routing perimeter.
2. **B** — Prefix `__Host-` adalah standar W3C untuk mencegah subdomain cookie tossing dan sniffing.
3. **B** — `React.cache()` mengikat lifecycle eksekusi per request, mengeliminasi duplikasi pembacaan/dekripsi cookie token.
4. **C** — Sanitasi eksplisit pada layer Edge Middleware dan verifikasi langsung via cookie di RSC mematikan vektor spoofing header.
5. **B** — Attribute validation antara token state server vs payload klien adalah inti pertahanan ABAC terhadap IDOR/BOLA.

---

# SEKSI 20 — TANTANGAN MANDIRI & PROYEK PRAKTIKUM

### Objective
Bangun sistem "Enterprise Vault File Access" menggunakan Next.js App Router dengan ketentuan teknis berikut:
1. Buat Server Action `downloadAuditReport(reportId: string)` yang:
   * Mengambil sesi pengguna via `requireAuth()` menggunakan `cookies()`.
   * Mengecek apakah pengguna memiliki permission `reports:read`.
   * Memastikan `reportId` yang diminta berada di bawah `tenantId` pengguna yang sama (Database isolation check).
2. Konfigurasikan file `middleware.ts` untuk memverifikasi session JWT pada path `/vault/*`, melempar redirect ke `/login` jika tidak valid, dan menghapus seluruh header injeksi tak dikenal.
3. Tulis Unit/Integration test sederhana (menggunakan Jest atau Vitest) yang menyimulasikan:
   * Percobaan request dengan session token valid tetapi memiliki role yang salah (`MEMBER` mencoba membaca laporan restricted).
   * Verifikasi bahwa eksekusi melempar status error `FORBIDDEN`.