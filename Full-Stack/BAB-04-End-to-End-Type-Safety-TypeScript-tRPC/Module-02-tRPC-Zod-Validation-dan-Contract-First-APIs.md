---
[⬅️ Module 01: Advanced TypeScript Generics](./Module-01-Advanced-TypeScript-Generics-Conditional-Types.md) | [📋 Silabus Induk](../README.md) | [BAB 04 Quiz & Challenge ➡️](./BAB-04-Quiz-dan-Challenge.md)
---

# Module 02: tRPC, Zod Validation, & Contract-First End-to-End Type Safety

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Memahami konsep dan filosofi **End-to-End Type Safety** yang menghubungkan backend server dan frontend client tanpa memerlukan proses code-generation atau sinkronisasi skema manual.
- Menguasai **Zod Runtime Schema Validation**: mendeklarasikan skema data, melakukan parsing aman (`parse` vs `safeParse`), melakukan inferensi tipe otomatis (`z.infer<T>`), data sanitization, custom refinements, serta transformasi payload.
- Merancang dan membangun arsitektur **tRPC Router & Procedures**: membedakan *query* (idempotent read), *mutation* (side-effect write), dan *middleware pipeline* (autentikasi context, logging, rate limiting).
- Mengintegrasikan tRPC Client dengan React Query (`@trpc/react-query`) untuk manajemen *server state*, *caching*, *optimistic updates*, dan *automatic refetching*.
- Menangani tantangan data serialization pada arsitektur full-stack (handling `Date`, `BigInt`, `Map`, `Set`) menggunakan serializer seperti `superjson`.
- Menganalisis perbandingan arsitektur tRPC vs REST (OpenAPI) vs GraphQL dalam konteks performa, fleksibilitas multi-client, dan kompleksitas *developer experience* (DX).

---

## 2. Prerequisite
- Menguasai TypeScript tingkat lanjut (Generics, Type Inference, Utility Types) dari Module 01.
- Memahami konsep dasar protokol HTTP (Method, Status Codes, Request/Response body).
- Memahami konsep client-side fetching dan state management di React (TanStack React Query).

---

## 3. Concept
Dalam pengembangan web full-stack tradisional, ada jurang pemisah (*type chasm*) yang memisahkan backend dan frontend. Backend mendefinisikan model data dan endpoint, sedangkan frontend berasumsi bahwa respons JSON dari jaringan memiliki bentuk (*shape*) tertentu. 

Jika backend mengubah nama kolom dari `user_id` menjadi `userId`, compiler TypeScript di frontend tidak mengetahuinya sama sekali. Kesalahan ini hanya meledak di browser pengguna sebagai `TypeError: Cannot read properties of undefined` pada saat *runtime*.

```
[ Backend Data Model ] --- (Jaringan HTTP / JSON Biasa) ---> [ Frontend Asumsi Tipe ]
       ❌ Perubahan di backend TIDAK dideteksi oleh TypeScript di frontend!
```

**End-to-End Type Safety** menghapus jurang ini. Dengan menggabungkan **Zod** (validasi tipe saat runtime) dan **tRPC** (propagasi tipe saat kompilasi via TypeScript type-inference), kode client Anda secara instan mengetahui setiap perubahan fungsi, parameter input, dan return type di backend—tanpa perlu menjalankan *compiler generator* atau membuat file deklarasi tipe manual.

---

## 4. Why? (Mengapa Kita Membutuhkan tRPC & Zod?)
Sebelum hadirnya tRPC dan Zod, tim full-stack memiliki beberapa opsi untuk mengamankan kontrak data antara client dan server:

1. **Manual Type Mirroring (Duplikasi Manual)**:
   - Backend mendefinisikan interface `UserResponse`. Pengembang menyalin interface yang sama ke repo frontend.
   - **Kelemahan**: Menimbulkan *human error*. Cepat atau lambat salah satu repo akan lupa disinkronisasi saat ada migrasi database.

2. **OpenAPI / Swagger + Codegen Tool**:
   - Backend mendokumentasikan API via OpenAPI YAML/JSON, lalu tool seperti `openapi-typescript-codegen` dijalankan di CI/CD atau terminal lokal untuk menghasilkan SDK client.
   - **Kelemahan**: Memerlukan langkah kompilasi perantara (*build step*). Pengembang frontend harus terus-menerus menjalankan perintah CLI setiap kali backend menambahkan atau mengubah endpoint.

3. **GraphQL + Apollo / Relay + GraphQL Code Generator**:
   - Skema GraphQL tunggal menjadi kontrak (*Single Source of Truth*).
   - **Kelemahan**: Kompleksitas tinggi (schema definition language terpisah, resolvers, N+1 problem, payload parser overhead, dan tooling yang berat) untuk tim yang hanya membangun web app monorepo atau full-stack TypeScript terpadu.

**tRPC hadir untuk menyederhanakan segalanya**: Jika backend dan frontend Anda sama-sama ditulis dalam TypeScript (misalnya di monorepo, Next.js, Nuxt, atau Express + Vite), tRPC mengimpor **hanya tipe (type-only import)** dari backend router ke frontend client. Hasilnya: **Nol bytes backend bocor ke bundle frontend**, namun autocomplete IDE dan type-checking 100% real-time!

---

## 5. What? (Apa itu tRPC & Zod?)
- **Zod**: Pustaka deklarasi skema TypeScript-first yang melakukan validasi data pada saat **runtime**. Zod menjembatani jurang antara data mentah yang tidak tepercaya (seperti request body `any` atau `unknown` dari pengguna atau API eksternal) menjadi data bertipe aman yang dijamin valid oleh TypeScript.
- **tRPC (TypeScript Remote Procedure Call)**: Framework komunikasi client-server yang memungkinkan Anda memanggil fungsi backend langsung dari frontend seolah-olah fungsi tersebut adalah fungsi lokal, lengkap dengan autocompletion dan validasi tipe parameter, tanpa skema terpisah atau build step.

---

## 6. How? (Bagaimana tRPC dan Zod Bekerja Bersama?)

### 1. Zod Runtime Parsing & Type Inference
```typescript
import { z } from "zod";

// Deklarasi skema validasi runtime
export const CreateOrderSchema = z.object({
  customerId: z.string().uuid("ID Pelanggan harus UUID yang valid"),
  items: z.array(
    z.object({
      sku: z.string().min(3),
      quantity: z.number().int().positive("Kuantitas minimal 1"),
      unitPrice: z.number().positive(),
    })
  ).min(1, "Pesanan harus memiliki minimal satu barang"),
  discountCode: z.string().optional(),
});

// Otomatisasi inferensi tipe TypeScript statis
export type CreateOrderInput = z.infer<typeof CreateOrderSchema>;
```

### 2. tRPC Router Definition (Backend)
```typescript
import { initTRPC, TRPCError } from "@trpc/server";
import { CreateOrderSchema } from "./schemas";

const t = initTRPC.context<{ userId?: string }>().create();

export const appRouter = t.router({
  // Query: Idempotent Read
  getOrderHistory: t.procedure.query(async ({ ctx }) => {
    if (!ctx.userId) throw new TRPCError({ code: "UNAUTHORIZED" });
    return [{ id: "ord-1", total: 250000 }];
  }),

  // Mutation: Stateful Write dengan Validasi Zod
  createOrder: t.procedure
    .input(CreateOrderSchema)
    .mutation(async ({ input, ctx }) => {
      // TypeScript menjamin 'input' bertipe CreateOrderInput!
      console.log(`Memproses pesanan untuk customer ${input.customerId}`);
      return { success: true, orderId: "ord-999" };
    }),
});

// Ekspor hanya TIPE dari router (bukan kodenya!)
export type AppRouter = typeof appRouter;
```

### 3. Frontend Client Consumption
```typescript
// Di kode frontend (Next.js / Vite)
import { createTRPCReact } from "@trpc/react-query";
import type { AppRouter } from "../server/routers/app"; // Type-only import!

export const trpc = createTRPCReact<AppRouter>();

function CheckoutPage() {
  const createOrderMutation = trpc.createOrder.useMutation({
    onSuccess: (data) => alert(`Pesanan berhasil dibuat: ${data.orderId}`),
  });

  const handleSubmit = () => {
    // IDE akan memberikan autocompletion merah jika kolom salah atau tidak sesuai schema!
    createOrderMutation.mutate({
      customerId: "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
      items: [{ sku: "LAPTOP-PRO", quantity: 1, unitPrice: 15000000 }],
    });
  };
}
```

---

## 7. Analogy
Bayangkan memesan obat di apotek:
- **Pendekatan REST Tradisional**: Anda menulis pesanan di secarik kertas tanpa panduan baku. Kasir apotek menerima kertas tersebut, membacanya, dan mungkin menyadari 15 menit kemudian bahwa dosis yang Anda minta tidak masuk akal atau obatnya tidak ada. Waktu terbuang sia-sia karena tidak ada jaminan bahwa format pesanan Anda cocok dengan sistem stok.
- **Pendekatan tRPC + Zod**: Apotek memberikan formulir digital interaktif pintar (*Zod Schema*). Jika Anda salah memasukkan nomor resep atau melebihi batas dosis, pena digital Anda langsung bergetar dan menolak teks tersebut saat itu juga. Di saat yang sama, tablet kasir apotek terhubung langsung (*tRPC Client-Server Link*) secara instan dengan panduan obat pabrikan tanpa perlu ada kurir yang bolak-balik menerjemahkan dokumen.

---

## 8. Diagram Arsitektur End-to-End Type Safety

```
+-----------------------------------------------------------------------------------+
| FRONTEND BROWSER / CLIENT                                                         |
|                                                                                   |
|  import type { AppRouter } from '@/server/router' <---+ Type-Only Compilation     |
|                                                       | (0 Byte Bundle Output!)   |
|  trpc.createOrder.useMutation()                       |                           |
|       |                                               |                           |
|       | 1. Full IDE Autocompletion & Type Check       |                           |
|       v                                               |                           |
|  [ HTTP JSON POST /api/trpc/createOrder ]             |                           |
+-----------------------|-------------------------------|---------------------------+
                        | (Jaringan HTTP / WebSocket)   |
+-----------------------v-------------------------------|---------------------------+
| BACKEND SERVER                                        |                           |
|                                                       |                           |
|  appRouter = t.router({                               |                           |
|    createOrder: t.procedure                           |                           |
|      .input(CreateOrderSchema)                        |                           |
|          |                                            |                           |
|          | 2. Zod Runtime Validation & Sanitization   |                           |
|          v                                            |                           |
|      .mutation(async ({ input, ctx }) => {            |                           |
|          // 3. Database Execution                     |                           |
|          return db.orders.create({ data: input });    |                           |
|      })                                               |                           |
|  })                                                   |                           |
|                                                       |                           |
|  export type AppRouter = typeof appRouter; -----------+                           |
+-----------------------------------------------------------------------------------+
```

---

## 9. Simple Example: Zod Runtime Schema Validation

```typescript
import { z } from "zod";

// 1. Definisikan Schema
const UserProfileSchema = z.object({
  username: z.string().min(3).max(20).toLowerCase(),
  email: z.string().email(),
  age: z.number().int().min(18, "Usia minimal harus 18 tahun"),
  role: z.enum(["ADMIN", "MEMBER", "GUEST"]).default("MEMBER"),
  tags: z.array(z.string()).default([]),
});

// 2. Simulasi Data Masuk (Runtime Request Body)
const rawData = {
  username: "SUPERUSER",
  email: "admin@perusahaan.com",
  age: 25,
};

// 3. Validasi Aman Menggunakan safeParse
const result = UserProfileSchema.safeParse(rawData);

if (result.success) {
  console.log("Data Valid:", result.data);
  // Output: { username: 'superuser', email: 'admin@perusahaan.com', age: 25, role: 'MEMBER', tags: [] }
} else {
  console.error("Validasi Gagal:", result.error.format());
}
```

---

## 10. Practical Example: Custom Middleware & Protected Procedure di tRPC

```typescript
import { initTRPC, TRPCError } from "@trpc/server";

// 1. Context Generator (di-invoke setiap HTTP Request masuk)
export interface Context {
  authToken?: string;
  user?: { id: string; role: "USER" | "ADMIN" };
}

const t = initTRPC.context<Context>().create();

// 2. Base Procedures
export const publicProcedure = t.procedure;

// 3. Auth Middleware Pipeline
const isAuthed = t.middleware(async ({ ctx, next }) => {
  if (!ctx.user) {
    throw new TRPCError({
      code: "UNAUTHORIZED",
      message: "Sesi login Anda tidak valid atau telah kedaluwarsa.",
    });
  }
  return next({
    ctx: {
      user: ctx.user, // TypeScript tahu user dijamin terdefinisi di sini!
    },
  });
});

// 4. Role-based Admin Guard Middleware
const isAdmin = isAuthed.unstable_pipe(async ({ ctx, next }) => {
  if (ctx.user.role !== "ADMIN") {
    throw new TRPCError({
      code: "FORBIDDEN",
      message: "Hanya Administrator yang memiliki akses ke operasi ini.",
    });
  }
  return next({ ctx });
});

export const protectedProcedure = t.procedure.use(isAuthed);
export const adminProcedure = t.procedure.use(isAdmin);
```

---

## 11. Real-World Example: SaaS Billing & Subscription Checkout Flow
Pada platform SaaS, modul checkout menuntut proteksi input yang sangat ketat untuk mencegah manipulasi kupon diskon, penetapan harga negatif, atau inject parameter berbahaya:

```typescript
import { z } from "zod";
import { initTRPC, TRPCError } from "@trpc/server";

export const CheckoutPayloadSchema = z.object({
  planTier: z.enum(["STARTER", "PROFESSIONAL", "ENTERPRISE"]),
  seats: z.number().int().min(1).max(500),
  couponCode: z.string().trim().toUpperCase().optional(),
  billingCycle: z.enum(["MONTHLY", "ANNUAL"]),
  paymentMethodId: z.string().startsWith("pm_", "Metode pembayaran Stripe tidak valid"),
}).refine(
  (data) => {
    // Custom business rule: Enterprise wajib minimal 10 seat
    if (data.planTier === "ENTERPRISE" && data.seats < 10) {
      return false;
    }
    return true;
  },
  {
    message: "Paket Enterprise mewajibkan minimal 10 kuota kursi tim (seats)",
    path: ["seats"],
  }
);

// Router Implementation
const t = initTRPC.create();

export const billingRouter = t.router({
  createSubscription: t.procedure
    .input(CheckoutPayloadSchema)
    .mutation(async ({ input }) => {
      // Seluruh validasi format dan aturan bisnis dieksekusi secara otomatis oleh Zod!
      const finalPrice = calculatePrice(input.planTier, input.seats, input.billingCycle);
      return {
        invoiceId: `INV-${Date.now()}`,
        amountDue: finalPrice,
        status: "ACTIVE",
      };
    }),
});

function calculatePrice(plan: string, seats: number, cycle: string): number {
  const base = plan === "ENTERPRISE" ? 150 : plan === "PROFESSIONAL" ? 50 : 20;
  const multiplier = cycle === "ANNUAL" ? 10 : 12;
  return base * seats * multiplier;
}
```

---

## 12. Trade-offs: tRPC vs REST (OpenAPI) vs GraphQL

| Parameter | tRPC + Zod | REST + OpenAPI | GraphQL |
| :--- | :--- | :--- | :--- |
| **Penyusunan Skema** | TypeScript Murni (Zod) | YAML/JSON terpisah | GraphQL Schema (.graphql) |
| **Kebutuhan Codegen** | **TIDAK BUTUH** (Zero-Codegen) | Wajib via OpenAPI generator | Wajib via GraphQL Codegen |
| **Multi-Language Client** | Kurang cocok (khusus TS) | **Sangat Baik** (Universal) | **Sangat Baik** (Universal) |
| **Overfetching Control** | Ditentukan oleh backend | Ditentukan oleh backend | **Sangat Fleksibel** (Client query) |
| **Developer Velocity** | **Sangat Cepat** (Instan) | Menengah (Perlu re-run script) | Menengah (Perlu tooling setup) |
| **Bundle Size Overhead** | Nol bytes backend di client | Tergantung SDK hasil codegen | Memerlukan client Apollo/Relay |
| **Caching Layer** | Didukung TanStack Query | HTTP Gateway (CDN, Varnish) | Normalized Cache di Client |

---

## 13. When To Use tRPC + Zod
- Anda membangun aplikasi web modern full-stack menggunakan TypeScript di frontend dan backend (misalnya Next.js App Router, Vite + Express/Fastify monorepo).
- Anda menginginkan kecepatan iterasi produk yang maksimal tanpa gesekan sinkronisasi manual atau langkah *build codegen*.
- Tim Anda berfokus pada web app tunggal di mana backend dan frontend dikembangkan berdampingan secara lincah.

---

## 14. When NOT To Use tRPC
- **Public API Konsumsi Publik**: Jika API Anda akan dikonsumsi oleh ribuan pengembang eksternal dengan beragam bahasa pemrograman (Python, Go, Java, Swift, Ruby). Gunakan REST OpenAPI standard.
- **Aplikasi Mobile Native Non-TypeScript**: Jika client utama adalah Swift (iOS) atau Kotlin (Android), GraphQL atau OpenAPI REST jauh lebih ramah ekosistem tooling mobile.
- **Arsitektur Microservices Multi-Bahasa**: Di mana backend terdiri dari service C++, Go, dan Rust. Gunakan gRPC (Protocol Buffers).

---

## 15. Common Mistakes
1. **Mengimpor Implementasi Router ke Frontend**:
   - *Salah*: `import { appRouter } from '@/server/routers'` di komponen React. Ini akan memasukkan kode database, ORM, dan credential server ke bundle JavaScript client!
   - *Benar*: Selalu gunakan keyword `import type { AppRouter } from ...`.
2. **Tidak Menggunakan `safeParse` saat Menangani Input Non-tRPC**:
   - Memanggil `schema.parse(data)` tanpa blok `try-catch` akan melemparkan exception runtime tak tertangani (*unhandled promise rejection*).
3. **Mengabaikan Serialisasi Objek Khusus**:
   - Mengirim objek `Date` melalui JSON biasa akan mengubahnya menjadi string `ISO-8601`. Di frontend, data tersebut tetap bertipe string, bukan objek `Date` asli, sehingga `date.getTime()` akan meledak jika tidak menggunakan `superjson`.

---

## 16. Best Practices

### Must Have
- Gunakan Zod untuk memvalidasi seluruh request payload yang masuk ke backend (`t.procedure.input(...)`).
- Gunakan `import type` untuk menjaga separasi antara client bundle dan server codebase.
- Strukturkan routers secara modular (misalnya `authRouter`, `userRouter`, `billingRouter`) dan satukan di `rootRouter`.

### Recommended
- Pasang serializer `superjson` di konfigurasi tRPC untuk menjamin tipe data kompleks (`Date`, `Map`, `Set`, `BigInt`) tetap utuh dari server ke client.
- Gunakan Zod `.trim()`, `.toLowerCase()`, dan `.transform()` untuk sanitasi data sebelum masuk ke layer database.

### Advanced
- Implementasikan tRPC Middleware untuk automatic telemetry tracing (OpenTelemetry span per procedure).
- Terapkan batching HTTP link (`httpBatchLink`) untuk menggabungkan beberapa query tRPC dalam satu single HTTP request guna menekan network roundtrip.

### Avoid
- Jangan menumpuk seluruh logika bisnis di dalam closure procedure tRPC. Pisahkan logika ke Service / Use Case layer agar mudah diuji secara independen.

---

## 17. Troubleshooting Guide

| Gejala Masalah | Kemungkinan Akar Masalah | Solusi Perbaikan |
| :--- | :--- | :--- |
| `TypeError: Cannot read properties of undefined (reading 'useQuery')` | tRPC Provider atau React Query Client Provider belum membungkus root komponen aplikasi. | Bungkus layout aplikasi dengan `<trpc.Provider>` dan `<QueryClientProvider>`. |
| Bundle frontend membesar drastis dan mengekspos variabel lingkungan backend. | Ada file komponen frontend yang melakukan `import` biasa (bukan `import type`) terhadap modul server. | Periksa seluruh import tRPC di client dan pastikan menggunakan `import type { AppRouter }`. |
| Properti `createdAt` bertipe `string` di frontend padahal backend mengembalikan `new Date()`. | JSON bawaan tidak mendukung tipe data Date asli. | Aktifkan transformer `superjson` pada `initTRPC.create({ transformer: superjson })` dan client link. |

---

## 18. Exercise
- **Easy**: Buat skema Zod untuk registrasi pengguna yang memvalidasi `password` minimal 8 karakter dan mengandung minimal satu angka.
- **Medium**: Buat procedure tRPC yang menerima query pagination bertipe `{ page: number, limit: number }` dengan default `page: 1` dan `limit: 20` (maksimal 100).
- **Hard**: Rancang skema Zod bertingkat (*nested object*) untuk sistem pembayaran yang memvalidasi metode `CREDIT_CARD` (wajib ada CVV & Expiry) atau `BANK_TRANSFER` (wajib ada Virtual Account Bank) menggunakan discriminated union `z.discriminatedUnion()`.

---

## 19. Challenge
Rancang arsitektur monorepo sederhana yang menghubungkan backend tRPC (Node.js) dengan frontend client simulasi, lengkap dengan middleware autentikasi bearer token, error formatter yang menyembunyikan stack trace di environment produksi, dan validator Zod untuk skema CRUD produk.

---

## 20. Summary
- **tRPC + Zod** merevolusi cara kerja tim full-stack TypeScript dengan menghadirkan **End-to-End Type Safety** murni tanpa overhead proses code generation.
- **Zod** bertindak sebagai perisai di perbatasan runtime untuk memastikan seluruh payload eksternal valid, aman, dan bersih.
- **tRPC** menyebarkan tipe data backend langsung ke autocomplete IDE frontend tanpa menyertakan satupun baris kode server ke dalam bundle client browser.
- Kombinasi ini meniadakan seluruh kelas bug koordinasi tipe antara frontend dan backend, meningkatkan kecepatan *shipping* software hingga berkali-kali lipat.

---

## Hands-on Practice: Simulasi Engine tRPC & Zod Contract-First Safety
Jalankan simulator engine validasi Zod dan dispatcher tRPC lokal mandiri:

```bash
node Full-Stack/BAB-04-End-to-End-Type-Safety-TypeScript-tRPC/hands-on/m02/trpc_zod_end_to_end_safety_sim.js
```

---
[⬅️ Module 01: Advanced TypeScript Generics](./Module-01-Advanced-TypeScript-Generics-Conditional-Types.md) | [📋 Silabus Induk](../README.md) | [BAB 04 Quiz & Challenge ➡️](./BAB-04-Quiz-dan-Challenge.md)
---
