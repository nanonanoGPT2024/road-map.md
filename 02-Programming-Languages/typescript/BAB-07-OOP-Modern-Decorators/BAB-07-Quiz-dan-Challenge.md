# BAB 07: Quiz, Challenge, & Knowledge Check
**Object-Oriented TypeScript & Modern Decorators**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Enkapsulasi Hard vs. Soft Private:**
   Jelaskan perbedaan mendasar secara kompilasi (*type erasure*), representasi *runtime*, dan memori antara modifier `private` milik TypeScript dengan *ECMAScript Private Identifier* (`#field`). Mengapa `private` TypeScript masih dapat diakses melalui `(instance as any).field` atau refleksi `Object.keys()`, sedangkan `#field` memberikan jaminan keamanan *hard-private* di level JavaScript Virtual Machine (V8)?

2. **Paradigma TC39 Stage 3 vs. Legacy Experimental Decorators:**
   TypeScript 5.0 mengadopsi standar resmi TC39 Stage 3 Decorators, menggantikan arsitektur lama `experimentalDecorators`. Jelaskan perbedaan struktural tanda tangan fungsi (*function signature*) antara *Method Decorator* lama (`(target, propertyKey, descriptor) => void | PropertyDescriptor`) dengan standar TC39 modern (`(target, context: ClassMethodDecoratorContext) => Function | void`). Informasi apa saja yang disediakan oleh objek `context` pada standar modern?

3. **Integritas Pewarisan dengan Keyword `override`:**
   Ditinjau dari flag kompilasi `noImplicitOverride`, mengapa penggunaan eksplisit *keyword* `override` pada *method* atau *property* kelas turunan menjadi krusial dalam pemeliharaan basis kode skala besar (*enterprise codebase*)? Analisis skenario bencana (*silent runtime failure*) yang terjadi apabila sebuah *method* di *base class* diubah namanya atau dihapus saat *subclass* tidak menggunakan `override`.

4. **Lifecycle dan Urutan Evaluasi Decorator:**
   Sebutkan urutan evaluasi (*evaluation*) dan eksekusi (*execution/application*) dari berbagai jenis decorator saat sebuah *class* didefinisikan di level modul. Kapan decorator dieksekusi: saat *runtime module load time*, atau saat instansiasi kelas (`new ClassName()`)? Bandingkan urutan eksekusi antara *Class Decorators*, *Method Decorators*, dan *Field Decorators*.

5. **Abstract Class vs Interface dalam Desain Sistem:**
   Dari perspektif *overhead runtime* (ukuran *bundle* JavaScript yang dihasilkan), *prototype chain*, dan kapabilitas pemodelan objek, kapan Anda wajib memilih `abstract class` dibandingkan `interface`? Berikan justifikasi teknis mengapa `interface` tidak dapat digunakan sebagai token injeksi dependensi runtime tanpa pustaka pihak ketiga.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Context Replacement & Boundary Safety di TC39 Decorators:**
   Pada TC39 Stage 3 Decorators, *method decorator* dapat mengembalikan fungsi pengganti (*replacement function*). Analisis potongan kode berikut:
   ```typescript
   function LogExecution<This, Args extends any[], Return>(
     target: (this: This, ...args: Args) => Return,
     context: ClassMethodDecoratorContext<This, (this: This, ...args: Args) => Return>
   ) {
     return function (this: This, ...args: Args): Return {
       console.log(`Executing ${String(context.name)}`);
       return target.call(this, ...args);
     };
   }
   ```
   Bagaimana parameter `this: This` pada fungsi pembungkus (*wrapper*) menjamin keamanan konteks eksekusi? Mengapa penggunaan fungsi panah (*arrow function*) sebagai pengganti di dalam decorator ini dilarang keras secara arsitektural?

2. **Ketiadaan Parameter Decorators pada TC39 Stage 3:**
   TC39 Stage 3 Decorator resmi saat ini **tidak** mendukung *Parameter Decorators* seperti yang ada pada `experimentalDecorators` (yang sering dimanfaatkan oleh Angular, NestJS, atau Tsyringe). Jelaskan alasan komite TC39 menunda spesifikasi ini dan jelaskan strategi arsitektur modern untuk mencapai fungsionalitas validasi parameter atau Inversi Kendali (*Inversion of Control*) tanpa dependensi pada parameter decorator.

3. **Mekanisme `addInitializer` dan Mutasi Instance:**
   Objek `ClassMemberDecoratorContext` menyediakan metode `addInitializer(initializer: () => void)`. Kapan fungsi *callback* yang didaftarkan lewat `addInitializer` dijamin dieksekusi oleh runtime? Jelaskan bagaimana mekanisme ini mengeliminasi kebutuhan komputasi kotor seperti pembajakan konstruktor (*constructor hijacking*) untuk mengikat (*binding*) metode ke instance.

4. **Memory Leak melalui Closure Decorator:**
   Perhatikan skenario di mana sebuah *Method Decorator* mengimplementasikan *caching* (memoization):
   ```typescript
   function Memoize() {
     const cache = new Map<string, any>(); // closure level
     return function(target: Function, context: ClassMethodDecoratorContext) {
       return function(this: any, ...args: any[]) {
         const key = JSON.stringify(args);
         if (cache.has(key)) return cache.get(key);
         const result = target.call(this, ...args);
         cache.set(key, result);
         return result;
       }
     }
   }
   ```
   Analisis mengapa implementasi di atas menyebabkan kebocoran memori (*memory leak*) global antar instance yang berbeda dan bagaimana cara memperbaiki arsitektur penyimpanan statusnya menggunakan `WeakMap` yang terikat pada instance `this`.

5. **Covariance dan Contravariance pada Method Overriding:**
   Ketika meng-override sebuah *method* dari *base class*, TypeScript memberlakukan aturan *subtyping* tertentu terhadap parameter dan nilai kembalian (*return type*). Jika sebuah *base class* memiliki *method* `handle(event: MouseEvent): void`, mengapa *subclass* diizinkan/dilarang mengubah tipenya menjadi `handle(event: UIEvent): void` atau `handle(event: PointerEvent): void` di bawah flag `strictFunctionTypes`? Bagaimana prinsip Liskov Substitution Principle (LSP) ditegakkan di sini?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Memory Leak & Latency Degradation pada Observability Decorator
Sebuah sistem transaksi finansial mengalami degradasi performa *throughput* hingga 60% dan insiden *Out of Memory* (OOM) fatal 48 jam pasca penerapan decorator APM (Tracing & Metrics) kustom baru:
```typescript
export function TracePerformance() {
  return function (target: any, propertyKey: string, descriptor: PropertyDescriptor) {
    const originalMethod = descriptor.value;
    descriptor.value = function (...args: any[]) {
      const traceContext = { timestamp: Date.now(), traceId: crypto.randomUUID(), instance: this };
      (globalThis as any).__ALL_TRACES__.push(traceContext); // Global APM buffer
      const start = performance.now();
      try {
        return originalMethod.apply(this, args);
      } finally {
        const duration = performance.now() - start;
        APMRegistry.record(propertyKey, duration, traceContext);
      }
    };
    return descriptor;
  };
}
```
* **Pertanyaan Diagnostik:**
  1. Identifikasi dua sumber utama kebocoran memori (*memory leaks*) dan retensi objek (*uncollected objects*) oleh Garbage Collector V8 dari implementasi decorator di atas.
  2. Bagaimana pengaruh retensi referensi `instance: this` terhadap siklus hidup kelas service berumur pendek (*transient services*)?
  3. Rancang ulang decorator tersebut menggunakan standar TC39 Stage 3 yang *zero-leak*, bebas mutasi global, dan memanfaatkan `WeakMap` atau `AsyncLocalStorage` untuk penelusuran asinkron (*distributed tracing*).

### Skenario B: Race Condition State Mutability pada Concurrency Tinggi
Sebuah layanan perbankan memiliki arsitektur *singleton service* untuk penarikan dana. Tim pengembang mengimplementasikan decorator `@AuditLock()` untuk mencegah penarikan ganda (*double withdrawal*) dengan mengunci eksekusi metode:
```typescript
function AuditLock() {
  let isLocked = false; // Flag status di-share di level decorator closure
  return function(target: any, context: ClassMethodDecoratorContext) {
    return async function(this: any, ...args: any[]) {
      if (isLocked) {
        throw new Error("Concurrent operation blocked");
      }
      isLocked = true;
      try {
        return await target.call(this, ...args);
      } finally {
        isLocked = false;
      }
    };
  };
}

class WalletService {
  @AuditLock()
  async withdraw(userId: string, amount: number) {
    const balance = await db.getBalance(userId);
    if (balance >= amount) {
      await db.setBalance(userId, balance - amount);
    }
  }
}
```
* **Pertanyaan Diagnostik:**
  1. Jelaskan *race condition* katastropik dan kegagalan isolasi yang terjadi ketika dua user berbeda (`User A` dan `User B`) memanggil `withdraw()` secara bersamaan pada instance singleton `WalletService`.
  2. Mengapa variabel status primitif yang dideklarasikan pada *outer scope* decorator melanggar prinsip *reentrancy* dan *thread/asynchronous safety*?
  3. Ubah kode tersebut menjadi implementasi *per-instance/per-user lock* yang aman tanpa menggunakan shared lexical scope.

### Skenario C: Migrasi Masif Legacy Decorator ke TC39 Stage 3 Decorator
Perusahaan Anda memiliki aplikasi berbasis monolit NestJS dengan ribuan *controller* dan *service* yang bergantung penuh pada:
- `experimentalDecorators: true`
- `emitDecoratorMetadata: true`
- Pustaka `reflect-metadata`
- Parameter decorator `@Inject()`, `@Param()`, `@Body()`

Komite Arsitektur menginstruksikan migrasi penuh ke *Modern TypeScript Decorators* (TC39 Stage 3) dan menonaktifkan flag `experimentalDecorators` untuk mendukung target build ES2024 murni dengan *transpiler* berkecepatan tinggi (esbuild/swc).
* **Pertanyaan Diagnostik:**
  1. Apa kendala fundamental (*blocker*) utama dari ekosistem dependensi saat flag `emitDecoratorMetadata` dimatikan pada proyek yang sangat bergantung pada *runtime metadata* untuk Dependency Injection?
  2. Mengapa *decorators* TC39 Stage 3 tidak memancarkan metadata tipe desain (*design:type*, *design:paramtypes*, *design:returntype*) ke `Reflect`?
  3. Susun rencana mitigasi arsitektur: Apakah Anda merekomendasikan migrasi langsung (*hard-cut*), pembuatan *metadata provider* kustom berbasis compiler transform plugin, atau penggunaan isolasi berbasis modul? Berikan evaluasi trade-off teknisnya.

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise Resilience Suite (Circuit Breaker & Telemetry) berbasis TC39 Stage 3

#### Problem Statement
Anda ditugaskan merancang *Resilience & Telemetry Library* internal untuk gateway finansial. Library ini harus memanfaatkan **TC39 Stage 3 Decorators murni** (TypeScript 5.x+, `experimentalDecorators: false`), tanpa pustaka `reflect-metadata`, *strictly typed*, dan aman digunakan di lingkungan konkurensi tinggi (*high-concurrency async*).

#### Requirements
1. **`@CircuitBreaker(options: CircuitBreakerOptions)` (Method Decorator):**
   * Mampu melacak kegagalan (*failure threshold*) pemanggilan asynchronous.
   * State machine: `CLOSED` (normal), `OPEN` (langsung gagalkan eksekusi dengan `CircuitOpenException`), `HALF_OPEN` (uji coba pemanggilan tunggal setelah batas *cooldown* waktu tertentu).
   * Status circuit breaker **wajib terisolasi per-instance dan per-metode**, tidak boleh bocor ke instance lain dari kelas yang sama.
   * Mencegah mutasi langsung ke `target.prototype`.
2. **`@Telemetry(eventName: string)` (Method Decorator):**
   * Mengukur latensi eksekusi asinkron secara presisi (`performance.now()`).
   * Menggunakan `context.addInitializer` untuk mendaftarkan nama metode ke sebuah metadata registry yang terikat pada instance.
   * Mempertahankan penanganan error asli (*transparent error propagation*).
3. **Type Safety:**
   * Decorator hanya boleh dipasang pada fungsi asinkron (`(...args: any[]) => Promise<any>`). Pemasangan decorator pada fungsi sinkron harus memicu *compile-time type error*.

#### Constraints
* Flag tsconfig: `"experimentalDecorators": false`, `"strict": true`.
* Dilarang mengimpor atau menggunakan pustaka `reflect-metadata`.
* Memory-leak free: Gunakan `WeakMap` untuk mengasosiasikan status *circuit breaker* dengan instance target.

#### Expected Output
Sajikan kode implementasi lengkap berisi:
1. Definisi antarmuka tipe (*type signatures*) untuk Circuit Breaker State & Decorator.
2. Implementasi decorator `@CircuitBreaker` dan `@Telemetry`.
3. Contoh implementasi kelas target:
   ```typescript
   class PaymentServiceClient {
     @Telemetry("payment_processing")
     @CircuitBreaker({ failureThreshold: 3, recoveryTimeoutMs: 5000 })
     async processTransaction(transactionId: string, amount: number): Promise<TransactionResult> {
       // logic implementation
     }
   }
   ```
4. Unit testing/Assertion harness sederhana yang membuktikan mekanisme state `CLOSED -> OPEN -> HALF_OPEN` serta *type safety assertion*.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan internal ECMAScript `#private` (diimplementasikan via JVM *private names* / *WeakMap storage*) dan `private` modifier TypeScript yang terhapus saat kompilasi.
- [ ] Arsitektur dan siklus hidup TC39 Stage 3 Decorators (TypeScript 5.x+) vs. Legacy `experimentalDecorators`.
- [ ] Fungsi dan struktur dari parameter `context: ClassMemberDecoratorContext`, termasuk properti `kind`, `name`, `static`, `private`, `access`, dan metode `addInitializer`.
- [ ] Mekanisme evaluasi Decorator: Luar-ke-dalam (*evaluation*) dan Dalam-ke-luar (*execution/application*).
- [ ] Batasan teknis ketiadaan *Parameter Decorators* dan pembuangan metadata emisi otomatis (`emitDecoratorMetadata`) pada standar ECMAScript modern.
- [ ] Aturan Liskov Substitution Principle (LSP) pada pewarisan kelas, mencakup kontravariansi pada parameter metode dan kovariansi pada nilai kembalian (*return type*).

### Saya tidak perlu menghafal:
- [ ] Spesifikasi byte-level dari metadata polyfill `reflect-metadata`.
- [ ] Kode emisi JavaScript ES5 boiler-plate hasil transpilasi helper class TypeScript (`__extends`, `__decorate`).
- [ ] Setiap properti internal yang dihasilkan compiler untuk polyfill *private identifiers* pada target kompilasi di bawah ES2015.

### Saya harus bisa melakukan:
- [ ] Menulis kustom *Class Decorator*, *Method Decorator*, *Field Decorator*, dan *Getter/Setter Decorator* menggunakan sintaks TC39 Stage 3 secara *strongly typed*.
- [ ] Membatasi target penempatan decorator secara statis menggunakan generic constraints pada `This` dan `Args`/`Return`.
- [ ] Mengimplementasikan *state storage* per-instance yang aman dari kebocoran memori (*memory leak*) menggunakan `WeakMap` di dalam lingkup decorator.
- [ ] Menangani *method binding* dan inisialisasi lifecycle instance secara elegan menggunakan `context.addInitializer`.
- [ ] Melakukan refactoring basis kode warisan (*legacy codebase*) yang menggunakan `experimentalDecorators` ke pola arsitektur modern tanpa merusak kontrak dependensi aplikasi.