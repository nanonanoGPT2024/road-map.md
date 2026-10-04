# BAB 07: Enterprise Security, Identity Management, dan RBAC
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Principal Architect dan Senior Software Engineer diharapkan mampu:
- Merancang dan mengimplementasikan arsitektur otentikasi hibrida (*stateless JWT session* vs *stateful distributed Redis session*) pada Next.js App Router (versi 14/15) dengan performa sub-milidetik pada *Edge Runtime*.
- Mengimplementasikan sistem otorisasi multi-layer: Role-Based Access Control (RBAC), Attribute-Based Access Control (ABAC), dan Policy-Based Access Control (PBAC) yang terisolasi di level Edge Middleware, Server Components (RSC), Route Handlers, dan Server Actions.
- Mengamankan komunikasi *Machine-to-Machine* (M2M) dan *User-to-Service* menggunakan JSON Web Encryption (JWE), cryptographic token exchange (RFC 8693), dan rotasi *ephemeral keys*.
- Menerapkan mitigasi tingkat lanjut terhadap vektor serangan OWASP Top 10 (CSRF pada Server Actions, Next.js Server-Side Request Forgery / SSRF, Prototype Pollution, Token Replay, dan Timing Attacks).
- Merancang pipeline audit logging terdistribusi berbasis cryptographically-verifiable event stream untuk compliance standar industri (SOC2, PCI-DSS Level 1, ISO 27001).

---

### 2. Prerequisite

Sebelum memulai modul ini, Anda wajib menguasai:
- **Arsitektur Next.js Modern**: Memahami pemisahan eksekusi React Server Components (RSC), Client Components, Edge Middleware, dan Server Actions.
- **Kriptografi Terapan**: Pemahaman tentang enkripsi simetris (AES-GCM-256) vs asimetris (RSASSA-PKCS1-v1_5, ECDSA via Curve P-256, Ed25519), struktur format JSON Web Token (JWT, JWS, JWE), dan algoritma hashing (Argon2id, SHA-256).
- **TypeScript Tingkat Lanjut**: Generic conditional types, template literal types, *branded types*, dan dynamic schema validation menggunakan Zod.
- **Infrastruktur Terdistribusi**: Cara kerja Redis cluster, connection pooling, HTTP-only Secure SameSite Cookie mechanics, dan isolasi V8 runtime (Edge) vs Node.js runtime.

---

### 3. Concept & Internal Architecture

Keamanan enterprise modern pada Next.js tidak dapat bertumpu pada satu lapis verifikasi (misalnya hanya mengandalkan Next.js Middleware). Pendekatan yang benar adalah model pertahanan berlapis (*Defense-in-Depth*) dengan prinsip *Zero Trust*.

```
[ Ingress: Client Browser / External Agent ]
                   │
                   ▼ (1) TLS 1.3 Termination & WAF (Cloudflare/AWS CloudFront)
                   │
                   ▼ (2) Edge Middleware (Lightweight Stateless Inspection)
                   │    ├── Origin & CSRF Double Submit Validation
                   │    ├── Ephemeral Edge Session Token (PASETO/JWE Decryption)
                   │    └── Optimistic Path-based Routing Assertion
                   │
                   ├───┬───────────────────────────────┐
                   │   │                               │
                   ▼   ▼                               ▼
       (3A) React Server Component       (3B) Route Handler (API)       (3C) Server Action
      ┌─────────────────────────────┐   ┌─────────────────────────────┐ ┌─────────────────────────────┐
      │ • Secure Data Fetching      │   │ • Machine-to-Machine Oauth2 │   │ • Mutative Operations       │
      │ • Sub-tree Authorization    │   │ • Granular Scopes Guard     │   │ • Strict CSRF Header Val.   │
      │ • View-level Masking        │   │ • Strict JSON Schema Val.   │   │ • Domain Model Invariants   │
      │ • No Raw Secret Leaks       │   │ • Rate Limiting Engine      │   │ • Re-auth on High Risk      │
      └──────────────┬──────────────┘   └──────────────┬──────────────┘ └──────────────┬──────────────┘
                     │                                 │                               │
                     └─────────────────┬───────────────┴───────────────────────────────┘
                                       │
                                       ▼ (4) Data Access Layer (DAL) & Policy Engine
                                       │    ├── ABAC / PBAC Evaluation (RBAC is just a subset)
                                       │    ├── Session Cache Invalidation (Redis Cluster)
                                       │    └── Database Tenant Segregation (RLS / Tenant Schema)
                                       │
                                       ▼ (5) Immutable Audit Log (Kafka / EventHub)
```

#### Komponen Arsitektur:
1. **Edge Runtime vs Node.js Runtime Boundary**: Middleware berjalan di atas V8 isolate tanpa dependensi Node.js native (`crypto`, `fs`). Operasi kriptografi wajib menggunakan Web Crypto API standar (`SubtleCrypto`). Middleware bertindak sebagai *gatekeeper non-blocking*, bukan tempat eksekusi query database.
2. **Double-Cookie / Split-Token Architecture**: Untuk mengatasi limitasi ukuran header HTTP cookie (4KB limit), enterprise memecah token menjadi:
   - *Signature Token*: Cookie `__Host-sig` (HTTP-Only, Secure, SameSite=Strict).
   - *Payload Token*: Cookie `__Host-payload` (Readable by client jika diperlukan, atau encrypted).
   - Alternatif Enterprise: Session ID acak (Opaque Token 256-bit) tersimpan di Redis, ditransmisikan via `__Host-SessionId`, di mana state otorisasi tersimpan di cluster Redis memory dengan *sliding expiration*.
3. **Data Access Layer (DAL)**: Isolasi mutlak logic otorisasi dari UI layer. Setiap pemanggilan database wajib melewati modul DAL yang mengevaluasi otorisasi menggunakan *Dependency Injection Pattern* dan memvalidasi izin eksekusi terhadap entitas data spesifik (*Row-Level ABAC*).

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (Naive) | Pendekatan Enterprise Produksi |
| :--- | :--- | :--- |
| **Pengecekan Izin** | Middleware-only inspection (`req.nextUrl.pathname.startsWith('/admin')`). | **Defense-in-Depth**: Middleware menyaring *boundary*, Server Action/DAL memverifikasi *fine-grained data invariant* via Policy Engine. |
| **Token Session** | Plain Signed JWT disimpan di `localStorage` atau Cookie standar tanpa prefix. | **Encrypted Session Cookie (`__Host-Prefix`)**: Menggunakan JWE (AES-256-GCM) dengan anti-tamper envelope, strict boundary isolation. |
| **Model Otorisasi** | Static Role Check (`user.role === 'admin'`). | **Context-Aware Dynamic ABAC/PBAC**: Mengevaluasi subjek, objek, aksi, waktu, geolokasi IP, dan status kepemilikan data dinamis. |
| **Manajemen State** | Direct DB hit pada setiap navigasi komponen Next.js. | **Dual-Tier Cache**: Verifikasi kriptografis lokal via public key (In-Memory Worker) + distributed fast cache (Redis) untuk *instant revocation*. |
| **Server Actions** | Server Action dieksekusi langsung tanpa validasi *caller origin* atau izin level data. | **Action Envelope Wrapper**: Validasi CSRF built-in, type-safe execution pipeline, parsing input Zod, authorization pre-flight check, dan audit-emission. |

---

### 5. How (Workflow Detail)

1. **Ingress Phase**:
   - Request diterima Next.js Middleware. Header `Host`, `X-Forwarded-Host`, dan `Origin` divalidasi silang untuk mencegah *Host Header Injection*.
   - Cookie bertingkat `__Host-auth-token` didekripsi menggunakan *Web Cryptography API* (AES-GCM).
   - Jika payload expired atau signature korup, middleware melakukan redirect atau meneruskan *nullified identity context* via headers (`x-user-id`, `x-user-roles`) yang ditandai secara kriptografis (*HMAC-SHA256 signature by Edge Secret*) agar RSC di hilir mempercayai header tersebut tanpa evaluasi ulang.

2. **Server Execution Phase (RSC & Server Actions)**:
   - Server Component memanggil `verifySession()` dari internal Data Access Layer (bukan membaca `headers()` mentah).
   - Jika mengeksekusi mutasi (Server Action):
     - Pipeline wrapper `createSecureAction` menghentikan eksekusi jika token CSRF/Origin tidak cocok.
     - Policy engine ABAC dijalankan: `can(user, 'invoice:update', invoiceEntity)`.
     - Operasi database diproteksi oleh Row Level Security (RLS) di Postgres atau `WHERE tenant_id = :tenantId AND owner_id = :userId`.

3. **Revocation & Invalidation Phase**:
   - Ketika security incident terdeteksi atau user melakukan *Logout Everywhere*, event disiarkan via Redis Pub/Sub.
   - Redis menyimpan *Denylist/Revocation Fingerprint* (JTI - JWT ID) dengan TTL sesuai umur maksimal token. Edge Middleware dan Node.js RSC memeriksa eksistensi JTI di cache layer.

---

### 6. Analogy & Diagram ASCII

#### Analogi Bandara Internasional (Airport Security Check)
- **Edge Middleware = Pintu Imigrasi Pertama**: Memeriksa kelayakan paspor (keabsahan kriptografis dan tanggal kadaluarsa). Imigrasi meloloskan Anda ke terminal, tetapi tidak berhak mengizinkan Anda masuk ke ruang kokpit pesawat.
- **Server Action / RSC = Pintu Masuk Kokpit Pesawat**: Memeriksa identitas biometrik dan kualifikasi kapten secara spesifik saat itu juga sebelum membuka pintu kendali.

```
       HTTP Request 
             │
             ▼
   [ Middleware Gate ]
             │
     Valid Edge Signature?
     ├── No  ──► [ Redirect /login ]
     └── Yes ──► Tambahkan Cryptographic Context Header
                       │
                       ▼
       ┌───────────────────────────────┐
       │     Next.js Runtime Core      │
       │                               │
       │   [ RSC / Action Pipeline ]   │
       │               │               │
       │       Ambil Context Header    │
       │               │               │
       │       Validasi HMAC Signature │
       │               │               │
       │       Evaluasi Atribut ABAC   │
       │       User + Entity + Context │
       │               │               │
       │       Diizinkan?              │
       │       ├── No  ──► Throw 403   │
       │       └── Yes ──► DB Query    │
       └───────────────────────────────┘
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Insecure vs Basic Secure Identity Context

##### Konvensional / Insecure:
```typescript
// app/actions/update-user.ts (BURUK: Rawan eksploitasi parameter tampering)
'use server'
import { db } from '@/lib/db';

export async function updateUser(userId: string, data: any) {
  // Tidak ada verifikasi otentikasi session penyerang dapat memasukkan arbitrary userId
  return await db.user.update({
    where: { id: userId },
    data
  });
}
```

##### Perbaikan Enterprise Dasar:
```typescript
// app/actions/update-user.ts (BENAR: Menggunakan context terenkripsi dari cookies)
'use server'
import { verifySession } from '@/lib/dal';
import { db } from '@/lib/db';
import { z } from 'zod';

const UpdateSchema = z.object({
  displayName: z.string().min(3).max(50),
});

export async function updateUser(rawInput: z.infer<typeof UpdateSchema>) {
  const session = await verifySession(); // Mengambil user ID internal dari state aman
  const validatedData = UpdateSchema.parse(rawInput);

  return await db.user.update({
    where: { id: session.userId },
    data: validatedData,
  });
}
```

---

#### B. Practical Enterprise Example: Comprehensive RBAC/ABAC Production Pipeline

Implementasi di bawah ini merupakan *production-ready architecture* yang memisahkan otentikasi Edge, Data Access Layer, dan Action Protection.

##### 1. Cryptographic Edge Utilities (`src/lib/security/crypto.ts`)
*Berjalan kompatibel di Node.js dan V8 Edge Runtime via Web Crypto API.*

```typescript
// src/lib/security/crypto.ts
const ALGORITHM = { name: 'AES-GCM', length: 256 };

export async function deriveKey(secret: string): Promise<CryptoKey> {
  const enc = new TextEncoder();
  const keyMaterial = await crypto.subtle.importKey(
    'raw',
    enc.encode(secret),
    'PBKDF2',
    false,
    ['deriveKey']
  );

  return crypto.subtle.deriveKey(
    {
      name: 'PBKDF2',
      salt: enc.encode('enterprise-salt-secure-string-constant'),
      iterations: 100000,
      hash: 'SHA-256',
    },
    keyMaterial,
    ALGORITHM,
    false,
    ['encrypt', 'decrypt']
  );
}

export async function encryptToken(payload: object, secret: string): Promise<string> {
  const key = await deriveKey(secret);
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const encodedPayload = new TextEncoder().encode(JSON.stringify(payload));

  const encryptedContent = await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv },
    key,
    encodedPayload
  );

  // Buffer concat: IV + Ciphertext
  const combined = new Uint8Array(iv.length + encryptedContent.byteLength);
  combined.set(iv);
  combined.set(new Uint8Array(encryptedContent), iv.length);

  return Buffer.from(combined).toString('base64url');
}

export async function decryptToken<T>(encryptedBase64Url: string, secret: string): Promise<T | null> {
  try {
    const key = await deriveKey(secret);
    const combined = Buffer.from(encryptedBase64Url, 'base64url');

    if (combined.length < 13) return null;

    const iv = combined.subarray(0, 12);
    const data = combined.subarray(12);

    const decrypted = await crypto.subtle.decrypt(
      { name: 'AES-GCM', iv },
      key,
      data
    );

    return JSON.parse(new TextDecoder().decode(decrypted)) as T;
  } catch (err) {
    return null; // Decryption failed or tampered
  }
}

export async function signHmac(data: string, secret: string): Promise<string> {
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    'raw',
    encoder.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );
  const signature = await crypto.subtle.sign('HMAC', key, encoder.encode(data));
  return Buffer.from(signature).toString('base64url');
}
```

##### 2. Edge Middleware Gatekeeper (`src/middleware.ts`)

```typescript
// src/middleware.ts
import { NextResponse, type NextRequest } from 'next/server';
import { decryptToken, signHmac } from '@/lib/security/crypto';

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico|api/public).*)'],
};

interface SessionPayload {
  userId: string;
  tenantId: string;
  roles: string[];
  exp: number;
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const sessionCookie = request.cookies.get('__Host-session')?.value;
  const internalSecret = process.env.INTERNAL_SECURITY_SECRET!;
  const encryptionSecret = process.env.SESSION_ENCRYPTION_SECRET!;

  // 1. Path Publik Whitelisting
  if (pathname.startsWith('/login') || pathname.startsWith('/auth')) {
    return NextResponse.next();
  }

  if (!sessionCookie) {
    return redirectToLogin(request);
  }

  // 2. Dekripsi Sesi di Edge
  const session = await decryptToken<SessionPayload>(sessionCookie, encryptionSecret);

  if (!session || Date.now() > session.exp) {
    return redirectToLogin(request);
  }

  // 3. Structural Routing Boundary Enforcement
  if (pathname.startsWith('/admin') && !session.roles.includes('SUPERADMIN')) {
    return new NextResponse('Access Denied: Missing Administrative Role', { status: 403 });
  }

  // 4. Buat Immutable Context Header yang ditandatangani secara kriptografis
  // Mencegah client spoofing x-user-id header
  const contextData = JSON.stringify({
    userId: session.userId,
    tenantId: session.tenantId,
    roles: session.roles,
  });

  const signature = await signHmac(contextData, internalSecret);

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set('x-internal-identity', contextData);
  requestHeaders.set('x-internal-identity-sig', signature);

  return NextResponse.next({
    request: {
      headers: requestHeaders,
    },
  });
}

function redirectToLogin(request: NextRequest) {
  const loginUrl = new URL('/login', request.url);
  loginUrl.searchParams.set('redirect', request.nextUrl.pathname);
  const response = NextResponse.redirect(loginUrl);
  // Clear compromised or dead cookie
  response.cookies.delete('__Host-session');
  return response;
}
```

##### 3. Data Access Layer & Policy Engine (`src/lib/security/policy.ts`)

```typescript
// src/lib/security/policy.ts
import { headers } from 'next/headers';
import { signHmac } from './crypto';

export type Action = 'read' | 'create' | 'update' | 'delete' | 'approve';
export type Resource = 'Billing' | 'Document' | 'AuditTrail';

export interface UserContext {
  userId: string;
  tenantId: string;
  roles: string[];
}

export interface ResourceEntity {
  tenantId: string;
  ownerId?: string;
  isLocked?: boolean;
  classification?: 'PUBLIC' | 'CONFIDENTIAL' | 'RESTRICTED';
}

// 1. Cryptographically Verified Identity Fetcher
export async function getVerifiedUser(): Promise<UserContext> {
  const headerList = headers();
  const identityRaw = headerList.get('x-internal-identity');
  const signature = headerList.get('x-internal-identity-sig');
  const secret = process.env.INTERNAL_SECURITY_SECRET!;

  if (!identityRaw || !signature) {
    throw new Error('UNAUTHENTICATED: Identity context missing');
  }

  const expectedSignature = await signHmac(identityRaw, secret);
  if (signature !== expectedSignature) {
    throw new Error('SECURITY_ALERT: Identity context tampering detected');
  }

  return JSON.parse(identityRaw) as UserContext;
}

// 2. ABAC Engine Implementation
export class PolicyEngine {
  static evaluate(
    user: UserContext,
    action: Action,
    resource: Resource,
    entity?: ResourceEntity
  ): boolean {
    // Break-glass emergency Superadmin access
    if (user.roles.includes('SUPERADMIN')) return true;

    // Boundary 1: Strict Multi-tenant Data Isolation
    if (entity && entity.tenantId !== user.tenantId) {
      return false; // Cross-tenant breach attempt blocked
    }

    // Boundary 2: Resource-Specific Attribute Policies
    switch (resource) {
      case 'Billing':
        if (action === 'approve') {
          return user.roles.includes('FINANCE_DIRECTOR') && !entity?.isLocked;
        }
        return user.roles.includes('FINANCE_USER');

      case 'Document':
        if (action === 'delete') {
          // Hanya owner atau tenant admin yang dapat menghapus dokumen yang tidak terkunci
          const isOwner = entity?.ownerId === user.userId;
          const isTenantAdmin = user.roles.includes('TENANT_ADMIN');
          return (isOwner || isTenantAdmin) && !entity?.isLocked;
        }
        if (entity?.classification === 'RESTRICTED') {
          return user.roles.includes('SECURITY_OFFICER');
        }
        return true;

      default:
        return false;
    }
  }

  static enforce(
    user: UserContext,
    action: Action,
    resource: Resource,
    entity?: ResourceEntity
  ) {
    const isAllowed = this.evaluate(user, action, resource, entity);
    if (!isAllowed) {
      throw new Error(`ACCESS_FORBIDDEN: Insufficient privileges for ${action} on ${resource}`);
    }
  }
}
```

##### 4. Production-Grade Server Action Wrapper (`src/lib/security/action-guard.ts`)

```typescript
// src/lib/security/action-guard.ts
import { z } from 'zod';
import { getVerifiedUser, PolicyEngine, Action, Resource, ResourceEntity, UserContext } from './policy';

interface ActionOptions<TInput, TOutput> {
  inputSchema: z.ZodSchema<TInput>;
  resource: Resource;
  action: Action;
  loadEntity?: (input: TInput, user: UserContext) => Promise<ResourceEntity | null>;
  handler: (data: { input: TInput; user: UserContext; entity?: ResourceEntity }) => Promise<TOutput>;
}

export function createSecureAction<TInput, TOutput>(options: ActionOptions<TInput, TOutput>) {
  return async (rawInput: TInput): Promise<{ success: boolean; data?: TOutput; error?: string }> => {
    try {
      // 1. Validasi Autentikasi
      const user = await getVerifiedUser();

      // 2. Validasi Skema Input (Sanitasi & Tipe)
      const parsedInput = options.inputSchema.safeParse(rawInput);
      if (!parsedInput.success) {
        return { success: false, error: `VALIDATION_FAILED: ${parsedInput.error.message}` };
      }

      // 3. Muat State Entitas Jika Diperlukan Evaluasi ABAC
      let entity: ResourceEntity | undefined = undefined;
      if (options.loadEntity) {
        const loaded = await options.loadEntity(parsedInput.data, user);
        if (!loaded) {
          return { success: false, error: 'RESOURCE_NOT_FOUND' };
        }
        entity = loaded;
      }

      // 4. Evaluasi Otorisasi (ABAC/PBAC)
      PolicyEngine.enforce(user, options.action, options.resource, entity);

      // 5. Eksekusi Handler Domain Mutasi
      const result = await options.handler({
        input: parsedInput.data,
        user,
        entity,
      });

      return { success: true, data: result };
    } catch (err: any) {
      console.error(`[SECURITY AUDIT] Action Violation: ${err.message}`);
      return {
        success: false,
        error: process.env.NODE_ENV === 'production' ? 'An unauthorized error occurred' : err.message,
      };
    }
  };
}
```

##### 5. Penerapan Server Action (`src/app/actions/billing.ts`)

```typescript
// src/app/actions/billing.ts
'use server'

import { z } from 'zod';
import { createSecureAction } from '@/lib/security/action-guard';

const ApproveBillingSchema = z.object({
  invoiceId: z.string().uuid(),
  memo: z.string().max(255).optional(),
});

// Mock database lookup
async function fetchInvoiceFromDB(id: string) {
  return {
    id,
    tenantId: 'tenant-enterprise-alpha',
    ownerId: 'usr-9876',
    isLocked: false,
    amount: 5000000,
  };
}

export const approveInvoiceAction = createSecureAction({
  inputSchema: ApproveBillingSchema,
  resource: 'Billing',
  action: 'approve',
  loadEntity: async (input, user) => {
    const invoice = await fetchInvoiceFromDB(input.invoiceId);
    if (!invoice) return null;
    return {
      tenantId: invoice.tenantId,
      isLocked: invoice.isLocked,
    };
  },
  handler: async ({ input, user }) => {
    // Database mutation with zero trust
    return {
      transactionId: `trx_${Date.now()}`,
      approvedBy: user.userId,
      status: 'APPROVED',
      invoiceId: input.invoiceId,
    };
  },
});
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Arsitektur Multi-Tenant FinTech Core Banking Platform
Sebuah platform Core Banking SaaS menangani 150 bank daerah (*multitenancy*) dengan throughput 40.000 request per detik pada jam sibuk.

**Vulnerability Insiden Sebelumnya:**
1. **Broken Object Level Authorization (BOLA/IDOR)**: User dari Bank A dapat melihat histori transaksi nasabah Bank B dengan memanipulasi parameter serial ID di URL.
2. **Session Hijacking via Subdomain Takeover**: Cookie `auth_token` di-*set* pada `.domain-fintech.com`, memungkinkan subdomain dev yang terbengkalai membaca session admin.

**Solusi Arsitektur Baru:**
1. **Penerapan Cookie Prefixing**: Menggunakan prefiks `__Host-` pada seluruh cookie session. Cookie ini menuntut bendera `Secure`, path `/`, dan tidak mengizinkan inheritance oleh subdomain manapun.
2. **Context-Aware Dynamic ABAC Engine**: Setiap pemanggilan data diverifikasi menggunakan identitas yang ditanamkan pada level database PostgreSQL via Dynamic Session Settings:
   ```sql
   -- Dieksekusi otomatis oleh connection pooler sebelum query bisnis dijalankan
   SET LOCAL app.current_tenant_id = 'tenant-bank-a';
   SET LOCAL app.current_user_id = 'usr-1234';
   ```
   Postgres Row Level Security (RLS) secara fisik menolak baris data jika `tenant_id` tidak sesuai dengan session variable, meminimalisir kemungkinan human error pada developer code.

---

### 9. Trade-offs

| Pendekatan | Keuntungan | Kerugian & Konsekuensi |
| :--- | :--- | :--- |
| **Stateless JWE Session (Edge Ready)** | Performa Edge ultra-rendah (<2ms latensi). Tidak membebani Redis/Database untuk session lookups. Sangat cocok untuk Global CDN (Cloudflare/Vercel). | Sulit melakukan *instant global revocation*. Jika private key compromised, penyerang dapat memalsukan sesi sampai batas exp. Solusi: TTL pendek (5-15 menit) + rotating refresh token. |
| **Stateful Redis Session (Centralized)** | Kendali instan 100% atas pencabutan sesi (*instant revoke/single logout*), pemantauan concurrent sessions per user. | Memperkenalkan network latency (10-40ms hop ke Redis cache). Titik kegagalan terpusat (*Single Point of Failure*) jika cluster Redis bottleneck. Biaya operasional tinggi. |
| **Hierarchical RBAC (Role Trees)** | Konseptual sederhana, mudah dipetakan ke UI dashboard, kueri database untuk pengecekan grup sangat cepat. | *Role Explosion*: Lambat laun organisasi butuh `REGIONAL_BRANCH_MANAGER_NORTH_VIEW_ONLY`, memicu puluhan role identik yang rapuh dan sulit dikelola. |
| **Attribute-Based Access Control (ABAC)** | Sangat fleksibel, ekspresif, dan mencakup semua konteks dinamis (waktu, kepemilikan, relasi entitas). | Kompleksitas evaluasi CPU naik, tracing bug otorisasi menjadi sulit, kueri loading entitas untuk verifikasi policy berpotensi memicu masalah $N+1$. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. "Middleware Only" Authorization Trap
- **Kesalahan**: Mengira rute `/api/protected` sudah aman hanya karena `middleware.ts` memeriksa token.
- **Penyebab**: Kesalahan konfigurasi regex `matcher` atau exploit internal routing (seperti Server Actions yang dipanggil via POST tanpa melewati matcher path middleware).
- **Solusi**: Jangan pernah jadikan Middleware sebagai satu-satunya garis pertahanan. Selalu lakukan otorisasi ulang di DAL/Server Action (`defense-in-depth`).

#### 2. Identity Forgery via Unsigned HTTP Headers
- **Kesalahan**: Middleware meneruskan `requestHeaders.set('x-user-id', user.id)` tanpa menandatanganinya, dan RSC hilir langsung mempercayai header tersebut.
- **Penyebab**: Penyerang luar dapat menyuntikkan header `x-user-id: admin` jika *Reverse Proxy/WAF* di depan Next.js tidak membersihkan (*strip*) header `x-user-*` yang datang dari luar.
- **Solusi**: Terapkan enkripsi/tanda tangan HMAC (`signHmac`) dengan secret simetris antara Middleware dan Server Layer, atau ambil data session langsung melalui secure server context token.

#### 3. CSRF Vulnerability pada Server Actions
- **Kesalahan**: Menganggap Next.js Server Actions 100% imun terhadap Cross-Site Request Forgery secara default.
- **Penyebab**: Server Action yang menangani multi-part form payloads tanpa header `Origin`/`Host` yang diverifikasi Next.js secara ketat dapat dieksploitasi dalam arsitektur custom CORS.
- **Solusi**: Pastikan proteksi origin bawaan Next.js aktif dan hindari menonaktifkan header checks pada konfigurasi `next.config.js`.

---

### 11. Best Practices (Production Checklist)

- [ ] **Cookie Security**: Gunakan prefix `__Host-` untuk session cookie (`SameSite=Strict`, `HttpOnly=true`, `Secure=true`, `Path=/`).
- [ ] **Data Minimization in Tokens**: Jangan menyimpan data PII (Personally Identifiable Information) seperti nomor handphone atau NIK di dalam decrypted token payload.
- [ ] **Double Assertion**: Selalu lakukan evaluasi integritas sesi pada Middleware (untuk abort cepat) dan Data Access Layer (untuk eksekusi data).
- [ ] **Safe Serialization**: Pastikan objek user yang diteruskan ke Client Component tidak mengandung atribut sensitif (`passwordHash`, `twoFactorSecret`). Terapkan Zod Output Transform / DTO.
- [ ] **Constant-Time Verification**: Gunakan `crypto.timingSafeEqual` ketika membandingkan token kriptografis, hash, atau signature untuk menggagalkan *Side-Channel Timing Attacks*.
- [ ] **Audit Trail Stream**: Setiap kegagalan otorisasi (`403 Forbidden`) wajib memicu event log terstruktur yang mencakup: `userId`, `ipAddress`, `action`, `resourceId`, dan `timestamp`.

---

### 12. Hands-on Practice

Simpan seluruh file praktikum di direktori: `hands-on/m02/`

#### Langkah 1: Inisialisasi Environment
Buat file `hands-on/m02/.env.local`:
```env
INTERNAL_SECURITY_SECRET=7f9d8a3b5c2e1f4a6b8d0e2c4a6f8b0d1e3c5a7b9d1f3a5c7e9b1d3f5a7c9e1b
SESSION_ENCRYPTION_SECRET=d8e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0
```

#### Langkah 2: Buat Modul Kriptografi & Context Guard
Salin kode dari **Seksi 7.B** ke dalam subdirektori:
- `hands-on/m02/lib/crypto.ts`
- `hands-on/m02/lib/policy.ts`
- `hands-on/m02/lib/action-guard.ts`

#### Langkah 3: Setup Server Action Test Runner
Buat skrip pengujian eksekusi Server Action terisolasi: `hands-on/m02/test-runner.ts`
```typescript
import { approveInvoiceAction } from './actions/billing';

async function runTest() {
  console.log('--- TEST 1: Eksekusi Tanpa Konteks Otentikasi ---');
  const res1 = await approveInvoiceAction({ invoiceId: 'd3b07384-d113-494b-9c8e-aa783296c0d4' });
  console.log('Result 1 (Expected Error):', res1);

  // Implementasi mocking konteks header untuk simulasi Middleware
}
```

---

### 13. Exercise

#### Level Easy
Tuliskan generic utility function `sanitizeUserForClient<T extends Record<string, any>>(user: T)` yang menerima user object sembarang dari database, dan membuang property `password`, `salt`, `internalNotes`, serta me-*return* object yang aman dikirim ke Client Component menggunakan TypeScript type assertion.

#### Level Medium
Buatlah fungsi Middleware yang mengevaluasi `Authorization: Bearer <token>` untuk rute API `/api/v1/*` ATAU cookie `__Host-session` untuk rute web application `/dashboard/*`. Jika keduanya absen, kembalikan response JSON 401 untuk API, atau HTTP redirect 307 ke `/login` untuk web application.

#### Level Hard
Rancang dan implementasikan Policy-Based Access Control (PBAC) engine dinamis yang mendukung operator logika kondisional JSON (AND, OR, NOT) seperti format AWS IAM Policy. Engine harus dapat mengevaluasi context seperti:
```json
{
  "effect": "Allow",
  "action": "document:export",
  "condition": {
    "and": [
      { "stringEquals": { "user.department": "Compliance" } },
      { "numericLessThan": { "resource.riskScore": 75 } },
      { "timeBetween": { "env.currentHour": [8, 17] } }
    ]
  }
}
```

---

### 14. Challenge

**Studi Kasus: Multi-Region Distributed Ephemeral Token Hijack Prevention**

**Skenario Masalah:**
Perusahaan Anda memiliki aplikasi Next.js enterprise yang dideploy di Edge multi-region (Singapura, Frankfurt, Oregon). Ditemukan indikasi serangan di mana aktor jahat berhasil mencuri cookie `__Host-session` milik eksekutif melalui serangan XSS pada sub-aplikasi yang tidak terisolasi secara sempurna.

Sesi penyerang menunjukkan karakteristik berikut:
- Menggunakan cookie yang valid (belum expired).
- Mengakses sistem dari rentang IP subnet yang berbeda namun di negara yang sama.
- Merubah User-Agent secara dinamis untuk menghindari static fingerprinting.

**Tantangan Arsitektur:**
1. Rancang algoritma deteksi anomali session (*Device & TLS Fingerprinting*) yang dapat dijalankan secara sinkron di Next.js Edge Middleware tanpa bergantung pada koneksi TCP database yang lambat.
2. Implementasikan mekanisme **Cryptographic Token Binding** (DPoP - Demonstrating Proof-of-Possession pada level application/middleware layer) di mana browser client menghasilkan pasangan public-private key ephemeral via Web Crypto API, dan setiap Server Action wajib menandatangani nonce payload request.
3. Rancang fallback strategi rotasi token instan lintas region (*zero-downtime*) ketika fingerprint mismatch terdeteksi, dengan memblokir token curian di edge cluster cache tanpa mengganggu pengguna sah yang hanya berpindah cell tower seluler.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic Level
1. **Mengapa penggunaan prefix `__Host-` pada cookie otentikasi wajib diimplementasikan pada aplikasi Next.js level enterprise?**
   - *Jawaban*: Prefix `__Host-` secara absolut mewajibkan cookie memiliki atribut `Secure`, harus dikirim dari domain host yang sama persis (menolak inheritance ke subdomain), dan harus diset dengan `Path=/`. Hal ini mencegah serangan *Cookie Tossing* dan eksploitasi subdomain yang terkompromi.

2. **Apa perbedaan struktural mendasar antara otentikasi Edge Runtime dan Node.js Runtime pada Next.js?**
   - *Jawaban*: Edge Runtime berjalan di lingkungan isolasi V8 tanpa akses ke native core module Node.js (`crypto`, `fs`, `stream`). Seluruh manipulasi token di Edge wajib menggunakan API standar Web Standard (seperti `SubtleCrypto`).

3. **Mengapa pemeriksaan authorization berbasis URL path saja pada Next.js Middleware rentan terhadap celah keamanan?**
   - *Jawaban*: URL-path check hanya menguji gerbang masuk halaman (routing). Server Actions dan internal data RPC dapat dipanggil secara langsung oleh client tanpa melewati struktur visual halaman tersebut jika matcher regex memiliki celah atau jika routing internal tidak terisolasi.

4. **Apa fungsi dari algoritma enkripsi Authenticated Encryption with Associated Data (AEAD) seperti AES-GCM dalam enkripsi token sesi?**
   - *Jawaban*: AEAD tidak hanya mengenkripsi kerahasiaan isi payload (*confidentiality*), tetapi juga memverifikasi integritas dan keaslian metadata (*authenticity*), mendeteksi jika terjadi bit-flipping atau tampering oleh pihak ketiga tanpa membutuhkan HMAC terpisah.

5. **Mengapa Client Component tidak boleh mengevaluasi status permission pengguna untuk tujuan keamanan sistem?**
   - *Jawaban*: Seluruh kode yang dieksekusi di Client Component dapat dimodifikasi oleh pengguna melalui debugger browser. Otorisasi di Client Component hanya bertujuan untuk *User Experience* (menampilkan/menyembunyikan tombol), sedangkan verifikasi otoritatif wajib berada di server.

---

#### Intermediate Level
6. **Bagaimana cara mencegah celah Server-Side Request Forgery (SSRF) ketika Next.js Server Components melakukan fetching data berdasarkan atribut user context?**
   - *Jawaban*: Validasi target URL menggunakan URL parser strict, tolak skema selain `https:`, blacklist alamat loopback (`127.0.0.1`, `localhost`) dan rentang IP privat (RFC 1918) serta metadata IP cloud (`169.254.169.254`), atau gunakan internal proxy gateway terisolasi.

7. **Dalam arsitektur stateless token, bagaimana cara menangani skenario "Immediate Account Suspension" sebelum token expired?**
   - *Jawaban*: Implementasikan arsitektur hybrid: Token tetap stateless, namun membawa ID unik (`jti`). Edge Middleware atau DAL melakukan lookup cepat ke high-performance distributed key-value store (seperti Redis atau Cloudflare KV) untuk mengecek keberadaan `jti` di daftar pembatalan (*Revocation Denylist*).

8. **Mengapa `headers()` pada Next.js Server Components bersifat read-only dan bagaimana arsitektur enterprise meneruskan state yang dimutasi dari Middleware?**
   - *Jawaban*: Karena RSC dieksekusi dalam mode streaming dan respons HTTP headers mungkin sudah terkirim sebagian ke client. Mutasi context dari Middleware ke RSC dilakukan dengan memodifikasi *Request Headers* yang diteruskan ke hilir menggunakan `NextResponse.next({ request: { headers: modifiedHeaders } })`.

9. **Apa risiko keamanan dari melewatkan seluruh data entitas database (misal model ORM Prisma) langsung sebagai props ke Client Component?**
   - *Jawaban*: Risiko kebocoran data sensitif (*Over-fetching & Secret Exposure*). Model database sering kali memuat audit fields, password hash, internal flags, atau tenant IDs yang dapat dibaca oleh inspeksi state React DevTools di browser client.

10. **Bagaimana cara menangani ancaman Timing Attack ketika memverifikasi custom signature token atau string hash di Next.js?**
    - *Jawaban*: Hindari operator perbandingan standar `===` atau `==` yang berhenti pada karakter pertama yang salah (*early exit*). Gunakan fungsi constant-time comparison seperti `crypto.timingSafeEqual` yang selalu mengevaluasi seluruh panjang buffer secara konstan.

---

#### Production Scenarios

11. **Skenario 1**:
    Sebuah aplikasi enterprise Next.js mengalami lonjakan 500 Internal Server Error saat middleware mencoba mendekripsi cookie session menggunakan Web Crypto API pada traffic 20.000 RPS. CPU utilization di edge instan menyentuh 100%. Setelah diaudit, fungsi `deriveKey` mengeksekusi PBKDF2 dengan 100.000 iterasi secara real-time pada *setiap* request.
    *Bagaimana modifikasi arsitektur Anda untuk menstabilkan sistem tanpa menurunkan tingkat keamanan?*
    - *Solusi Rekayasa*: PBKDF2 dirancang secara komputasional berat dan dilarang dieksekusi per-request pada Edge Middleware. Ubah arsitektur dengan melakukan *pre-derivation* CryptoKey saat proses startup/deployment, simpan key yang sudah di-derive dalam module-level in-memory cache pada V8 isolate runtime, atau gunakan raw base64-encoded secret langsung via `crypto.subtle.importKey('raw', ...)` untuk AES-GCM tanpa re-derivation berulang.

12. **Skenario 2**:
    Tim frontend Anda melaporkan bug aneh: Seorang manager Bank dapat menyetujui approval request milik manager lain jika mereka menekan tombol "Approve" secara simultan (kurang dari 50 milidetik). Log menunjukkan aksi Server Action dipanggil paralel dan keduanya berhasil (*Race Condition*).
    *Bagaimana Anda merancang mitigasi pada level Identity & Access Management di Server Actions?*
    - *Solusi Rekayasa*: Terapkan *Optimistic Locking* (version flag pada database entity) atau *Distributed Mutex Locking* menggunakan Redis (Redlock) berbasis kombinasi `resourceId` dan `action`. Selain itu, jalankan Server Action di dalam transaksi database serializable (`ISOLATION LEVEL SERIALIZABLE`) yang memvalidasi status entitas saat ini sebelum mengizinkan pembaruan state mutasi.

13. **Skenario 3**:
    Auditor eksternal SOC2 menemukan bahwa sistem Next.js Anda rentan terhadap impersonasi internal: Developer menemukan celah di mana mereka dapat memodifikasi container Docker lokal mereka untuk menyuntikkan header `x-internal-identity: {"userId":"admin"}` langsung ke port internal service Next.js Node.js runtime, melewati Edge Reverse Proxy.
    *Bagaimana Anda mendesain ulang Trust Boundary antara Reverse Proxy dan Next.js runtime?*
    - *Solusi Rekayasa*: Menerapkan arsitektur *Zero Trust Network Architecture (ZTNA)* dengan **Mutual TLS (mTLS)** antara Edge Proxy dan upstream Next.js container, di mana upstream secara ketat menolak koneksi tanpa sertifikat client valid. Tambahan: Middleware/Proxy wajib menandatangani identity header menggunakan asymmetric private key (RS256/ES256), dan Data Access Layer memverifikasi signature menggunakan public key sebelum mempercayai data header tersebut.

---

### 16. Summary

- **Defense-in-Depth Bukan Opsional**: Middleware hanyalah lapisan pertama untuk perlindungan perimetrik (stateless checks, basic path gating). Data Access Layer (DAL) dan Server Actions adalah benteng pertahanan absolut untuk menegakkan otorisasi data (RBAC/ABAC).
- **Kriptografi yang Benar**: Hindari pembuatan mekanisme enkripsi sendiri. Gunakan Web Crypto API yang telah terbukti, lindungi cookie dengan prefiks `__Host-`, terapkan algoritma AES-GCM-256 untuk kerahasiaan sesi, dan selalu lakukan evaluasi constant-time untuk mencegah *side-channel attacks*.
- **Otorisasi Kontekstual**: RBAC statis tidak mencukupi untuk kebutuhan enterprise modern. Terapkan ABAC/PBAC yang memvalidasi *tenant boundary*, *entity ownership*, dan *runtime state* secara atomik sebelum setiap operasi mutasi data diizinkan.