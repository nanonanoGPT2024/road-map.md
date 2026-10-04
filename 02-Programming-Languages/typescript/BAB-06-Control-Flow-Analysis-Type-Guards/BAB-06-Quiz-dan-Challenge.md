# BAB 06: Quiz, Challenge, & Knowledge Check
**Control Flow Analysis & Type Guards**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Mekanisme Reachability Graph pada Control Flow Analysis (CFA)
Jelaskan secara mendalam bagaimana TypeScript Compiler (tsc) membangun *directed acyclic graph* (DAG) untuk mengevaluasi aliran eksekusi kode! Bagaimana compiler menentukan tipe suatu variabel pada titik eksekusi tertentu (*point-in-time typing*) saat menemui percabangan (`if/else`, `switch`, *early returns*), dan apa perbedaan mendasar antara *declared type* dan *flow type*?

### Soal 1.2: Anatomi dan Soundness dari Custom Type Predicates (`val is T`)
Mengapa return type `arg is T` diperlakukan secara istimewa oleh compiler dibandingkan return type `boolean` murni? Bedah bagaimana compiler memperbarui *flow type* di dalam scope blok kondisional yang divalidasi oleh type guard tersebut, dan jelaskan risiko *type-safety soundness* yang muncul jika implementasi logika runtime di dalam fungsi guard tidak sinkron dengan tipe target `T`!

### Soal 1.3: Semantik dan Mekanisme Assertion Signatures (`asserts val is T`)
Bandingkan semantik eksekusi dan implikasi kontrol alur antara User-Defined Type Guard (`arg is T`) dengan Assertion Functions (`asserts condition` / `asserts val is T`). Kapan compiler memutuskan untuk memotong jalur eksekusi (*unreachable code detection*) saat memproses assertion signature, dan bagaimana mutasi tipe diaplikasikan ke sisa scope leksikal saat ini tanpa memerlukan blok kondisional eksplisit?

### Soal 1.4: Discriminated Unions dan Teori Exhaustiveness Checking
Mengapa *tagged/discriminated unions* dianggap sebagai implementasi idiomatik *algebraic data types* (ADT) di TypeScript? Jelaskan bagaimana mekanisme *narrowing* bekerja saat compiler membaca properti diskriminan yang bersifat literal, dan bagaimana pemanfaatan tipe `never` menjamin *compile-time exhaustiveness* ketika varian baru ditambahkan ke dalam union type.

### Soal 1.5: Batasan `typeof` dan `instanceof` Guards
Identifikasi dan bedah kegagalan struktural (structural pitfalls) dari penggunaan guard bawaan JavaScript:
1. Mengapa `typeof x === "object"` tidak cukup aman untuk mempersempit tipe data non-primitif?
2. Mengapa `instanceof` dapat menghasilkan false negative atau runtime crash ketika bekerja di lingkungan multi-realm (seperti perlintasan `iframe`, *worker threads*, atau dual-package hazard CJS/ESM)?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Analisis CFA Invalidation Akibat Closure dan Asynchronous Execution
Perhatikan kode berikut:
```typescript
function processBuffer(data: { payload: string | null }) {
  if (data.payload !== null) {
    // Flow type: string
    setTimeout(() => {
      console.log(data.payload.toUpperCase()); // Potensi Runtime Error: TypeError
    }, 1000);
  }
}
```
Mengapa TypeScript terkadang mengizinkan kode di atas tanpa komplain jika target transpilasinya berbeda, namun bagaimana aturan formal CFA menangani penutupan (*closure boundaries*) dan pemanggilan fungsi callback? Jelaskan konsep *type-guard invalidation* atau *aliasing mutation* yang mendasari fenomena ini dan bagaimana memperbaikinya secara mutlak.

### Soal 2.2: Limitasi Operator `in` pada Prototipe Objek dan Tipe `unknown`
Diberikan sebuah fungsi parser yang menerima input bertipe `unknown`:
```typescript
function parseEvent(event: unknown) {
  if (typeof event === "object" && event !== null && "eventId" in event) {
    // Tipe event di sini menyempit menjadi object & Record<"eventId", unknown>
    console.log(event.eventId);
  }
}
```
Jelaskan mengapa operator `in` mempersempit properti menjadi `unknown` alih-alih tipe yang lebih spesifik. Apa yang terjadi jika objek input dibuat menggunakan `Object.create(null)` atau properti tersebut berada pada rantai prototipe (`__proto__`)? Bagaimana merancang validasi bertingkat yang benar-benar type-safe tanpa bergantung pada `any`?

### Soal 2.3: Interaksi CFA dengan Mutasi Properti Objek (Aliasing Effects)
Telaah skenario kode berikut:
```typescript
interface State {
  status: "idle" | "loading" | "success";
  data?: string[];
}

function handleState(state: State) {
  const isSuccess = state.status === "success";
  if (isSuccess) {
    // Pertanyaan: Apakah state.status otomatis menyempit ke "success"?
    // Pertanyaan: Mengapa ekstraksi guard ke variabel terpisah memiliki batas kedalaman pelacakan (alias analysis)?
  }
}
```
Jelaskan bagaimana TypeScript 4.4+ melacak *aliased conditions* dan batasan apa saja yang membatalkan narrowing tersebut (misalnya re-assignment pada variabel perantara atau mutasi properti objek oleh eksekusi fungsi perantara).

### Soal 2.4: Destructuring vs Direct Access Narrowing pada Discriminated Unions
Mengapa kode di bawah ini gagal mempertahankan narrowing pada variabel yang telah di-destructure?
```typescript
type Action = 
  | { type: "WRITE"; payload: { text: string } }
  | { type: "RESET"; payload: undefined };

function execute(action: Action) {
  const { type, payload } = action;
  if (type === "WRITE") {
    // Error: Object is possibly 'undefined' pada payload.text
    console.log(payload.text);
  }
}
```
Bedah bagaimana compiler memutus hubungan keterikatan (*discriminated coupling*) saat variabel properti didekonstruksi secara independen, dan bagaimana cara memodelkan abstraksi jika destructuring tetap diwajibkan oleh coding standard tim!

### Soal 2.5: Narrowing pada Generic Type Parameters
Mengapa type guard konvensional sering kali gagal mempersempit parameter bertipe generik murni secara langsung seperti pada contoh berikut?
```typescript
function processGeneric<T extends string | number>(val: T): T {
  if (typeof val === "string") {
    // Error: Type 'string' is not assignable to type 'T'.
    // 'string' is assignable to the constraint of type 'T', but 'T' could be instantiated with a different subtype of 'string'.
    return val.toUpperCase();
  }
  return val;
}
```
Jelaskan inkonsistensi antara representasi *type variable* `T` dengan *concrete narrowed type*, serta berikan dua strategi arsitektural untuk menyelesaikan masalah ini (misalnya via *function overloads* atau *type-level assertion*).

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Unhandled Mutation pada Streaming Pipeline (Fintech Core)
Sistem pemrosesan transaksi berkecepatan tinggi mengonsumsi ribuan mutasi saldo rekening secara konkuren. Tim backend menemukan insiden crash di level worker node (Node.js) akibat *unhandled null pointer dereference*. Investigasi menemukan kode berikut:

```typescript
type Account = { id: string; balance: number | null };

async function reconcileAccount(acc: Account, fetchRemoteBalance: () => Promise<number>) {
  if (acc.balance === null) {
    // CFA mempersempit acc.balance ke null
    const remote = await fetchRemoteBalance();
    applyReconciliation(acc, remote);
  } else {
    // CFA mengasumsikan acc.balance adalah number
    // Namun ada fungsi mutasi lain di event loop tick yang sama via reference sharing
    processSettlement(acc.id, acc.balance); 
  }
}
```
Meskipun TypeScript mengompilasi kode tersebut tanpa error, sistem tetap melempar runtime exception karena `acc.balance` bermutasi secara asinkron atau diubah melalui referensi bersama selama proses `await fetchRemoteBalance()`.
* **Pertanyaan Diagnostik:** 
  1. Mengapa compiler TypeScript tetap menganggap tipe `acc.balance` valid di seluruh percabangan meski ada jeda eksekusi asinkron (`await`)?
  2. Bagaimana Anda merancang ulang *state isolation* dan type narrowing function agar compiler secara paksa memvalidasi ulang invariansi data pasca-`await`?

---

### Skenario B: Broken Discriminated Union pada Multi-Tenant Webhook Parser
Sebuah sistem agregasi Webhook multi-vendor menerima ratusan skema payload JSON heterogen (misalnya Stripe, Shopify, GitHub). Arsitek sistem mendesain discriminated union raksasa:

```typescript
type WebhookPayload = StripeEvent | ShopifyEvent | GitHubEvent;

function routeWebhook(payload: WebhookPayload) {
  switch (payload.provider) {
    case "stripe":
      handleStripe(payload); // payload: StripeEvent
      break;
    case "shopify":
      handleShopify(payload); // payload: ShopifyEvent
      break;
    default:
      assertNever(payload);
  }
}
```
Ketika payload runtime yang tidak valid atau vendor baru yang belum terdaftar di-push ke endpoint, runtime melempar unhandled exception di `assertNever`, atau lebih buruk: salah satu payload Shopify yang strukturnya mirip Stripe meloloskan evaluasi guard secara parsial akibat manipulasi runtime payload (structural subtyping bleeding), menyebabkan data kotor masuk ke database.
* **Pertanyaan Diagnostik:**
  1. Di mana letak kelemahan arsitektural yang mengasumsikan input eksternal mentah (`unknown`) langsung diperlakukan sebagai discriminated union type?
  2. Buatlah rancangan *Two-Tier Narrowing Pipeline* yang memisahkan validasi runtime (misal via schema parser / custom recursive guard) dengan internal discriminated unions!

---

### Skenario C: Trade-off Arsitektur: Schema Validation Engine (Zod/Valibot) vs User-Defined Type Guards (UDTG) pada High-Throughput Edge API
Anda adalah Principal Architect pada aplikasi Edge Gateway yang menangani 150.000 requests/detik. Tim Anda memperdebatkan dua pendekatan untuk validasi dan narrowing request body:
* **Pendekatan 1:** Menggunakan pustaka skema fungsional berbasis JIT/Reflection (seperti Zod/Valibot/ArkType).
* **Pendekatan 2:** Menulis User-Defined Type Guards murni secara manual (`isPayload(data): data is Payload`) yang dioptimalkan dengan zero dependencies.

* **Pertanyaan Diagnostik:**
  1. Analisis performa CPU cycles, memory allocations, dan bundle size dari kedua pendekatan pada environment edge (seperti Cloudflare Workers atau V8 isolates)!
  2. Dari perspektif *maintainability*, *type drift* (kondisi di mana type definition dan runtime validator menyimpang), serta *supply chain risk*, formulasikan matriks keputusan komprehensif: kapan tim Anda **wajib** menggunakan library validator, dan kapan harus beralih ke handwritten custom type predicates?

---

## 4. Chapter Challenge

### Tantangan Praktis: Type-Safe Event Sourcing Ingestion Engine dengan Zero-Cost Exhaustive Narrowing

#### Problem
Anda diminta untuk membangun core ingestion engine untuk sistem CQRS/Event Sourcing. Engine ini menerima event mentah dari Kafka/RabbitMQ yang bersifat untyped (`unknown`), memvalidasinya, menyempitkannya ke varian event yang tepat secara exhaustive, memblokir kemungkinan mutasi asinkron, dan mengeksekusi handler yang terdaftar tanpa adanya *type assertion* (`as`) ilegal atau pembobolan tipe (`any`).

#### Requirements
1. **Definisi Union:** Definisikan minimal 3 tipe domain event yang kompleks (misalnya: `UserRegistered`, `OrderCreated`, `PaymentFailed`) yang memiliki struktur payload berbeda secara radikal dan properti diskriminan bersama (`type` dan `version`).
2. **Defensive Runtime Validator:** Buat *Higher-Order Type Guard* atau *Assertion Guard* generic yang mampu menguji input `unknown` dan memastikan bahwa data tersebut benar-benar mematuhi kontrak discriminated union tanpa menggunakan library eksternal.
3. **Exhaustive Event Dispatcher:** Implementasikan fungsi dispatching engine yang:
   * Menggunakan pola exhaustiveness check berbasis fungsi utility `exhaustiveCheck(x: never): never`.
   * Mempertahankan *immutability* mutlak untuk mencegah mutasi CFA invalidation pada event context.
   * Mendukung penanganan versi skema (Schema Versioning Narrowing), misalnya jika `OrderCreated` memiliki varian `version: 1` dan `version: 2`.
4. **Compile-time Failure Test:** Kode harus gagal dikompilasi jika ada satu varian event ditambahkan ke union types namun handler untuk varian tersebut belum diimplementasikan di switch/dispatcher block.

#### Constraints
* **Strict Mode:** Wajib menggunakan flag compiler `--strict: true` (termasuk `noImplicitAny`, `strictNullChecks`).
* **Zero Runtime Casting:** Dilarang keras menggunakan kata kunci `as <Type>` di dalam badan fungsi handler atau parser logic (kecuali `as const` pada static metadata, atau double assertion terisolasi yang diizinkan hanya pada core low-level type predicate implementation).
* **Zero Dependencies:** Implementasi harus murni TypeScript tanpa bantuan Zod, Yup, Joi, lodash, atau runtime parser lainnya.

#### Expected Output
Sebuah file TypeScript mandiri (`event-engine.ts`) yang rapi, modular, terdokumentasi dengan baik, berisi:
1. Definisi types/interfaces event domain.
2. Core type guards & recursive helper validators.
3. Fungsi dispatcher yang mengembalikan promise dari execution result.
4. Contoh eksekusi kasus uji:
   * Case 1: Valid event payload berhasil di-dispatch dengan type inference presisi.
   * Case 2: Invalid payload ditolak secara elegan via throwing Assertion Error runtime.
   * Case 3: Bukti blok static check gagal compile jika ada union branch yang dihilangkan.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Bagaimana TypeScript Compiler mengonstruksi *Control Flow Graph* (CFG) dan mengkalkulasi titik union/intersection types pada percabangan kode.
- [ ] Perbedaan formal antara *Narrowing by Equality* (`===`), *Narrowing by Truthiness*, *Narrowing by Instanceof*, dan *Narrowing by the `in` Operator*.
- [ ] Peran dan cara kerja User-Defined Type Guard (`arg is T`) dalam memodifikasi status inferensi compiler pada lexical scope bersyarat.
- [ ] Perbedaan semantik, kontrol alur, dan use-case antara Type Predicate (`arg is T`) dengan Assertion Functions (`asserts arg is T`).
- [ ] Kenapa destrukturisasi properti dari discriminated union memutus rantai keterikatan narrowing (*discriminated context loss*).
- [ ] Konsep *exhaustiveness checking* memanfaatkan tipe `never` untuk memastikan cakupan komprehensif pada pattern matching struktural.
- [ ] Masalah soundness pada CFA di sekitar mutasi objek referensial dan pembatalan narrowing pada asynchrony/closure boundaries.

### Saya tidak perlu menghafal:
- [ ] Kode implementasi internal AST scanner compiler TypeScript untuk control flow nodes.
- [ ] Semua nama internal error code (seperti `TS2345` atau `TS2322`) yang dikeluarkan oleh compiler saat type narrowing gagal.
- [ ] Setiap kemungkinan runtime type hack untuk membobol JavaScript engine di luar batas spesifikasi ECMAScript standar.

### Saya harus bisa melakukan:
- [ ] Merancang discriminated union berkinerja tinggi untuk memodelkan *domain state* yang kompleks dan meminimalisir kemungkinan *illegal states*.
- [ ] Menulis custom type predicate guard (`is`) dan assertion function (`asserts`) yang aman, presisi, dan bebas bug runtime.
- [ ] Menerapkan pola pattern matching yang aman menggunakan `switch(val.discriminant)` dengan fallback `never` handler untuk mencegah bug regresi.
- [ ] Mengatasi masalah narrowed type parameter yang tidak kompatibel dengan generic return types tanpa mengorbankan type safety.
- [ ] Melakukan isolasi data lokal (cloning / immutability enforcement) untuk mencegah hilangnya jaminan soundness tipe pada operasi multi-tick asynchronous di Node.js/Browser runtime.