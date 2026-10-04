# BAB 04: Quiz, Challenge, & Knowledge Check
**Data Mutation, Server Actions, & Stateful Forms**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Anatomi dan Siklus Hidup RPC pada Server Actions
Jelaskan secara mendalam bagaimana Next.js mengabstraksi pemanggilan fungsi JavaScript biasa pada Server Action menjadi Remote Procedure Call (RPC) berbasis HTTP POST. Apa yang terjadi pada payload argumen fungsi ketika melintasi *network boundary*, bagaimana Next.js memetakan aksi tersebut ke endpoint internal (header `Next-Action`), dan apa implikasinya terhadap tipe data yang dapat dikirimkan (*serializability constraints*)?

### Soal 1.2: Paradigma Progressive Enhancement
Bagaimana arsitektur Server Actions mengeksekusi mutasi form ketika JavaScript pada sisi klien dimatikan (*disabled*) atau gagal dimuat? Bandingkan mekanisme eksekusi form berbasis standard HTML POST submission tersebut dengan eksekusi berbasis AJAX/Fetch yang di-intervensi oleh React Runtime, khususnya terkait siklus rendering dan pembaruan UI.

### Soal 1.3: Mekanisme Invalidation: `revalidatePath` vs `revalidateTag`
Analisis perbedaan teknis antara `revalidatePath` dan `revalidateTag` yang dieksekusi di dalam Server Action. Bagaimana kedua fungsi ini memanipulasi *Full Route Cache* di server dan *Router Cache* di browser klien? Dalam skenario apa pemanggilan `revalidatePath` dapat memicu beban komputasi server yang tidak diinginkan (*over-rendering*) dibanding granularitas `revalidateTag`?

### Soal 1.4: Batasan Kontekstual `useFormStatus` dan `useActionState`
Mengapa `useFormStatus` tidak dapat membaca status pending dari `<form>` jika dipanggil di dalam komponen yang sama dengan deklarasi elemen `<form>` tersebut? Jelaskan dependensi internal hook ini terhadap React Context API dan pola dekomposisi komponen yang wajib diterapkan untuk mengatasinya.

### Soal 1.5: Rekonsiliasi State pada `useOptimistic`
Uraikan siklus hidup state saat menggunakan hook `useOptimistic`. Bagaimana React mengelola transisi antara state aktual, state optimis sementara, dan state hasil resolusi mutasi dari server? Apa yang terjadi pada UI jika Server Action melempar uncaught error atau mengembalikan respons kegagalan mutasi?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Server Actions sebagai Attack Surface (Security & Authorization)
Meskipun Server Action dideklarasikan di dalam file komponen privat, Next.js tetap mengeksposnya sebagai endpoint publik via POST request. Mengapa mempercayakan validasi konteks hanya pada closure scope Server Action adalah celah keamanan fatal (*security vulnerability*)? Bagaimana cara menerapkan autentikasi sesi, otorisasi RBAC (Role-Based Access Control), dan validasi integritas input yang benar sebelum mutasi menyentuh database layer?

### Soal 2.2: Dual-Payload Resolution & Streaming Collision
Ketika Server Action memicu `revalidatePath` atau `revalidateTag` yang mengubah data pada layout induk yang sedang melakukan streaming komponen asinkron (`<Suspense>`), bagaimana Next.js mengorkestrasi response payload? Jelaskan struktur protokol RSC payload yang mengembalikan data hasil eksekusi action sekaligus pohon komponen UI yang telah di-render ulang dalam satu stream koneksi HTTP.

### Soal 2.3: Mutasi Cookies dan Headers: Batasan dan Revalidasi Implisit
Next.js mengizinkan manipulasi cookies di dalam Server Action (`cookies().set()` / `cookies().delete()`), tetapi melarangnya di dalam Server Component standar selama fase render murni. Mengapa batasan arsitektur ini diberlakukan? Selain itu, mengapa penulisan cookie tertentu di dalam Server Action dapat secara otomatis membatalkan *Router Cache* klien untuk rute yang bergantung pada cookie tersebut?

### Soal 2.4: Bottleneck Memory & Payload Limits pada File Uploads
Saat mengunggah berkas biner (misal: PDF 15MB atau Video) menggunakan Server Action melalui form multipart:
```typescript
async function uploadFile(formData: FormData) {
  'use server';
  const file = formData.get('file') as File;
  // ...
}
```
Jelaskan mengapa pendekatan di atas sangat berisiko di lingkungan *serverless computing* (seperti Vercel Functions atau AWS Lambda). Analisis batas payload execution, konsumsi RAM pada node runtime, dan bagaimana arsitektur mutasi harus dialihkan menggunakan *Presigned URL* (direct-to-storage upload).

### Soal 2.5: Middleware Interception & Wrapper Architecture
Server Actions secara teknis melewati layer Middleware Next.js (`middleware.ts`). Bagaimana urutan eksekusi middleware ketika sebuah Server Action dipanggil? Jika Anda merancang sebuah sistem enterprise, bagaimana pola implementasi *Higher-Order Functions* (Action Wrappers) untuk menangani *cross-cutting concerns* seperti input validation (menggunakan Zod), structured telemetry logging, tracing ID propagation, dan standardized error formatting tanpa membocorkan database error stack ke klien?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Database Connection Pool Exhaustion Pasca Flash-Sale
* **Konteks:** Sebuah platform e-commerce meluncurkan flash-sale. Pada rute produk `/products/[id]`, form mutasi "Beli Sekarang" menggunakan Server Action:
  ```typescript
  export async function purchaseItem(productId: string) {
    'use server';
    await db.orders.create({ data: { productId, userId: getUserId() } });
    revalidatePath('/products/[id]');
  }
  ```
* **Insiden:** Saat traffic mencapai 8.000 RPS, database PostgreSQL mengalami crash akibat kehabisan koneksi (*Connection Pool Exhaustion*), padahal connection pooler (PgBouncer) sudah terpasang. Analisis APM menunjukkan bahwa query mutasi `orders.create` berjalan normal (<15ms), namun ratusan query berat yang membaca riwayat ulasan, data rekomendasi produk, dan relasi katalog mengalami lonjakan eksekusi simultan yang masif.
* **Pertanyaan Diagnostik:**
  1. Identifikasi akar masalah arsitektural mengapa pemanggilan `revalidatePath('/products/[id]')` di dalam Server Action tersebut memicu badai query (*stampede query*) ke database.
  2. Bagaimana solusi mitigasi performa tinggi untuk memisahkan mutasi status pembelian dari rendering ulang seluruh pohon komponen produk menggunakan granular caching tags atau client-state update?

---

### Skenario B: Race Condition & Double Submit pada Koneksi Latensi Tinggi
* **Konteks:** Aplikasi perbankan B2B memiliki form transfer dana dengan otentikasi multi-faktor. Klien dengan koneksi 3G yang tidak stabil menekan tombol "Kirim Dana" secara berulang kali karena respons UI terasa lambat (latensi > 3 detik).
* **Insiden:** Terjadi transfer ganda (*double spending*) untuk ID transaksi yang sama. Logging menunjukkan bahwa Server Action dieksekusi 3 kali secara paralel dengan payload yang identik sebelum respons pertama selesai diproses. Upaya tim frontend menambahkan `disabled={isPending}` pada tombol submit menggunakan `useActionState` gagal menghentikan request kedua dan ketiga yang telah terlanjur dikirim oleh event handler browser.
* **Pertanyaan Diagnostik:**
  1. Mengapa proteksi sisi klien (`disabled` button / state flag) tidak pernah cukup untuk menjamin integritas data mutasi finansial pada arsitektur Server Actions?
  2. Rancang pola arsitektur pertahanan berbasis *Idempotency Keys* yang diintegrasikan ke dalam Server Action menggunakan Redis atau database lock untuk memastikan mutasi hanya dieksekusi tepat satu kali (*strictly once*), terlepas dari berapa kali request POST identik diterima.

---

### Skenario C: Konflik Arsitektur: Server Action vs Dedicated Route Handler
* **Konteks:** Tim inti sedang membangun modul *Bulk Data Import* yang memproses file spreadsheet CSV berisi 50.000 baris data karyawan untuk diimpor ke sistem ERP multi-tenant. Pengembang junior mengimplementasikannya via Server Action dengan parsing CSV dan mutasi batch langsung di dalam action tersebut.
* **Insiden:** Request sering mengalami timeout HTTP 504 (*Gateway Timeout*) setelah 30 detik. Klien mengeluhkan UI membeku tanpa ada visualisasi progres upload baris data, dan konsumsi memori instance server melonjak hingga memicu *Out of Memory* (OOM) kill.
* **Pertanyaan Diagnostik:**
  1. Bedah trade-off fundamental penggunaan Server Action vs Route Handler (`/api/import`) untuk operasi mutasi data berdurasi panjang (*long-running background jobs*).
  2. Rekonstruksi arsitektur modul tersebut: Bagaimana alur data yang tepat mulai dari inisialisasi upload, pemrosesan asinkron (worker queue), polling status atau streaming progress (SSE/WebSockets), hingga sinkronisasi final dengan React Client UI?

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise Stateful Subscription Switcher dengan Optimistic Rollback & Resilient Pipeline

#### Problem Statement
Anda ditugaskan membangun modul pergantian paket langganan SaaS (*Subscription Upgrade/Downgrade Engine*) untuk platform cloud. Sistem harus menangani perubahan tier (misal: Free -> Pro -> Enterprise) dengan transisi UI instan tanpa latency lag, validasi ketat, mitigasi double-submit, proteksi rate-limiting, penanganan kalkulasi prorata secara atomik, dan rollback transparan jika kartu kredit klien ditolak oleh payment gateway di sisi server.

#### Requirements
1. **Type-Safe Validation Pipeline:**
   * Buat Zod schema untuk memvalidasi input mutasi: `tierId` (enum), `billingCycle` (`monthly` | `yearly`), dan `idempotencyKey` (UUIDv4).
   * Implementasikan Higher-Order Action Wrapper `createSafeAction` yang memvalidasi input, memverifikasi JWT session user, dan menyuntikkan `userId` ke context action.
2. **Stateful Form Implementation:**
   * Gunakan `useActionState` untuk mengelola state mutasi: error validasi field, pesan error server, dan return payload.
   * Gunakan `useOptimistic` untuk langsung merefleksikan perubahan visual badge tier dan estimasi tagihan baru sebelum server merespons.
   * Gunakan `useFormStatus` di dalam submit button untuk menampilkan micro-animation spinner dan teks kontekstual (misal: "Mengalkulasi prorata...").
3. **Robust Backend Mutation Flow:**
   * Implementasikan atomic database transaction (simulasi Prisma/Drizzle) yang mengunci baris subscription, mencatat log audit, dan berintegrasi dengan mock gateway pembayaran.
   * Simulasikan probabilitas kegagalan payment (misal: tier "Enterprise" melempar error `CARD_DECLINED_INSUFFICIENT_FUNDS` jika kondisi tertentu terpenuhi) untuk menguji mekanisme rollback UI `useOptimistic`.
   * Eksekusi `revalidateTag(`billing-subscription-${userId}`)` secara selektif hanya saat mutasi berhasil.

#### Constraints
* **Zero Client Secret Leakage:** Tidak boleh ada API keys atau gateway secret token yang terkirim ke bundle klien.
* **Network Throttling Tolerance:** Sistem harus teruji tahan uji pada kondisi *Slow 3G* (latensi ~2500ms) tanpa desinkronisasi antara state form dan server cache.
* **Strict TypeScript:** Dilarang menggunakan `any`. Seluruh return signature mutasi harus terdefinisi via discriminated union (`{ success: true; data: T } | { success: false; error: ActionError }`).

#### Expected Output
1. File `lib/safe-action.ts`: Action wrapper utility lengkap dengan penanganan exception terstandarisasi.
2. File `actions/subscription.ts`: Server Action yang mengimplementasikan pipeline validasi, simulasi atomik, delay jaringan, dan tag revalidation.
3. File `components/subscription-form.tsx`: Client Component yang mengintegrasikan `useActionState`, `useOptimistic`, sub-komponen bersarang dengan `useFormStatus`, serta penanganan visual error boundary/toast ketika optimisme di-rollback.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Batasan serialisasi data pada argumen dan return value Server Action (mengapa `Functions`, `Classes`, dan Symbol tidak dapat diparsing melintasi network boundary).
- [ ] Perbedaan siklus eksekusi Server Action saat dijalankan via progressive enhancement (native form submit) vs client-side transition (Fetch/RSC protocol).
- [ ] Dampak pemanggilan `revalidatePath` dan `revalidateTag` terhadap *Data Cache*, *Full Route Cache*, dan *Router Cache* klien.
- [ ] Cara kerja internal React Transition (`startTransition`) dalam melacak pending state pada Server Actions.
- [ ] Titik kerentanan keamanan Server Action sebagai open POST endpoint dan mitigasi via explicit authentication & authorization checks.
- [ ] Mekanisme rollback state pada `useOptimistic` ketika server promise mengalami *rejection*.

### Saya tidak perlu menghafal:
- [ ] Struktur byte-stream mentah dari protokol RPC Next.js (misal: format string internal chunk `$ACTION_ID_...`).
- [ ] Seluruh konfigurasi internal boundary HTTP POST headers yang di-generate otomatis oleh bundler Next.js.
- [ ] Konfigurasi parameter low-level pada underlying fetch polyfill Next.js untuk server actions.

### Saya harus bisa melakukan:
- [ ] Membangun pipeline Server Action yang type-safe menggunakan library validasi skema (Zod/Valibot) dengan Action Wrapper kustom.
- [ ] Mengimplementasikan *Idempotency Key pattern* untuk mencegah duplicate transaction execution akibat double-click atau network retry.
- [ ] Mengisolasi submit button ke dalam sub-komponen untuk memanfaatkan hook `useFormStatus` tanpa memicu re-render pada seluruh form.
- [ ] Menggunakan `useActionState` untuk mengembalikan feedback validasi per-field (*field-level validation errors*) secara mulus ke antarmuka formulir.
- [ ] Menerapkan arsitektur upload berkas aman berbasis *Presigned URL* untuk menghindari bottleneck memori serverless saat menangani berkas besar.
- [ ] Mendiagnosis dan memperbaiki *race conditions* serta memori leaks yang disebabkan oleh pembaruan cache yang tidak sinkron pasca-mutasi data.