# SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: TS-02-07-01
* **Kategori**: 02-Programming-Languages / TypeScript
* **Judul**: OOP & Modern Decorators (Stage 3 Decorators & TypeScript 5.0+)
* **Level**: Advanced
* **Prasyarat**:
  * Pemahaman mendalam tentang Prototype Chain dan ES Classes (`class`, `extends`, `super`).
  * Penguasaan TypeScript Type System (Generics, Type Narrowing, Mapped Types).
  * Pemahaman dasar tentang Runtime Closures dan Higher-Order Functions.
* **Target Audiens**: Senior Software Engineer, Backend/Frontend Architect, Framework Developer.
* **Estimasi Waktu Belajar**: 120 Menit

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. **Menganalisis** perbedaan struktural dan runtime antara Legacy Decorators (`experimentalDecorators: true`) dan Standard ECMAScript Stage 3 Decorators yang diperkenalkan pada TypeScript 5.0+.
2. **Merancang** arsitektur Object-Oriented Programming (OOP) enterprise yang aman secara tipe (*type-safe*) dengan memanfaatkan *encapsulation*, *polymorphism*, dan *composition*.
3. **Mengimplementasikan** seluruh spektrum Stage 3 Decorators: Class, Method, Getter, Setter, Field, dan Auto-Accessor Decorators beserta manipulasi `context`-nya.
4. **Mengeksploitasi** `context.metadata` untuk membangun sistem metaprogramming deklaratif tanpa bergantung pada library eksternal seperti `reflect-metadata`.
5. **Mengisolasi** efek samping (*side effects*) dan menjaga integritas performa V8 Hidden Class / Inline Caching saat menggunakan decorator wrapper.
6. **Mendeteksi** serta memitigasi celah keamanan *Prototype Pollution* dan kebocoran state runtime pada dynamic decoration.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

Dalam paradigma OOP murni, sebuah objek bertanggung jawab atas data (*state*) dan perilaku (*behavior*)-nya. Namun, kebutuhan enterprise memperkenalkan *Cross-Cutting Concerns* (kebutuhan lintas sektoral) seperti otorisasi, validasi, audit logging, rate limiting, dan transaction boundary.

```
       Tanpa Decorators (Imperative Boilerplate)
       ┌────────────────────────────────────────────────────────┐
       │ class OrderService {                                   │
       │   placeOrder(order: Order) {                           │
       │     Logger.log("Execution started");   // Concern 1     │
       │     Auth.verify(currentUser);          // Concern 2     │
       │     RateLimiter.throttle("order");     // Concern 3     │
       │     try {                                              │
       │       // BUSINESS LOGIC INTI                           │
       │       return this.repo.save(order);                    │
       │     } finally {                                        │
       │       Metrics.recordExecutionTime();   // Concern 4     │
       │     }                                                  │
       │   }                                                    │
       │ }                                                      │
       └────────────────────────────────────────────────────────┘

       Dengan Modern Decorators (Declarative Metaprogramming)
       ┌────────────────────────────────────────────────────────┐
       │ class OrderService {                                   │
       │   @Logged()                                            │
       │   @Authorize(["CUSTOMER"])                             │
       │   @RateLimit({ points: 10, duration: 60 })             │
       │   placeOrder(order: Order) {                           │
       │     return this.repo.save(order); // Core logic bersih │
       │   }                                                    │
       │ }                                                      │
       └────────────────────────────────────────────────────────┘
```

### Mental Model: Wrapper vs. Constructor Interception
* **Bukan Magic**: Decorator hanyalah sebuah fungsi JavaScript biasa yang dieksekusi oleh runtime JavaScript pada fase *class definition time* (ketika class pertama kali dievaluasi oleh runtime), **bukan** pada fase *instantiation time* (saat `new Class()` dipanggil).
* **Higher-Order Function**: Anggap method decorator sebagai transformer: `Method Baru = Decorator(Method Asli, Context)`.
* **State vs Behavior**: Stage 3 Decorators memisahkan mutasi state dari deklarasi metadata, menghindari manipulasi properti prototype secara sembarangan.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Decorator Evaluation & Execution Order (Stage 3)

Dalam spesifikasi ECMAScript Decorators:
1. **Evaluasi Ekspresi (Decorator Factories)**: Berjalan dari **Atas ke Bawah** (*Top-to-Bottom*).
2. **Penerapan Decorator (Decorator Application)**: Berjalan dari **Bawah ke Atas** (*Bottom-up* atau *Inside-out*).
3. **Kategori Eksekusi**: Instance members (Method/Getter/Setter/Field/Accessor) dievaluasi terlebih dahulu sebelum Class Decorator dieksekusi.

```
Evaluasi Kode:
  @FactoryA()
  @FactoryB()
  targetMethod() {}

Timeline Runtime:
┌──────────────────────────────────────────────────────────────────┐
│ FASE 1: EVALUASI FACTORY (Top-to-Bottom)                         │
│ 1. FactoryA() dipanggil -> Mengembalikan DecoratorFnA            │
│ 2. FactoryB() dipanggil -> Mengembalikan DecoratorFnB            │
├──────────────────────────────────────────────────────────────────┤
│ FASE 2: DEFINISI CLASS (Bottom-to-Top)                           │
│ 3. DecoratorFnB(targetMethod, contextB) dieksekusi               │
│    └─> Menghasilkan WrappedMethodB                               │
│ 4. DecoratorFnA(WrappedMethodB, contextA) dieksekusi             │
│    └─> Menghasilkan WrappedMethodA                               │
│ 5. Class definition selesai; WrappedMethodA menggantikan target   │
├──────────────────────────────────────────────────────────────────┤
│ FASE 3: RUNTIME INVOCATION (new Class().targetMethod())          │
│ 6. Pemanggil -> WrappedMethodA                                   │
│    └─> WrappedMethodB                                            │
│        └─> targetMethod Asli                                     │
└──────────────────────────────────────────────────────────────────┘
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### TypeScript 5.0+ Stage 3 Decorator Anatomy

Stage 3 Decorators menerima signature standar:

```typescript
type Decorator = (
  value: DecoratedValue,
  context: ClassDecoratorContext |
           ClassMethodDecoratorContext |
           ClassGetterDecoratorContext |
           ClassSetterDecoratorContext |
           ClassMemberDecoratorContext |
           ClassAccessorDecoratorContext |
           ClassFieldDecoratorContext
) => ReplacementValue | void;
```

#### Struktur `context` Objek:
* `kind`: Tipe target (`"class"` | `"method"` | `"getter"` | `"setter"` | `"field"` | `"accessor"`).
* `name`: Nama dari property/method target (`string` atau `symbol`).
* `static`: Boolean; `true` jika properti bertipe `static`, `false` jika instance property.
* `private`: Boolean; `true` jika properti diawali dengan `#` (Private Identifier).
* `access`: Objek penyedia runtime accessor (`get()` dan `set()`).
* `addInitializer(initializer: () => void)`: Mendaftarkan callback untuk dieksekusi saat runtime initialization.
* `metadata`: Key-value storage object universal yang dibagi di seluruh decorator dalam hierarki class (`Symbol.metadata`).

#### Mekanisme `accessor` (Auto-Accessor)
TypeScript 5 memperkenalkan keyword `accessor`:
```typescript
class Account {
  accessor balance: number = 0;
}
```
Di balik layar, transpiler akan mengubahnya menjadi:
```javascript
class Account {
  #balance = 0;
  get balance() { return this.#balance; }
  set balance(value) { this.#balance = value; }
}
```
Field Decorator biasa tidak bisa mengubah field menjadi getter/setter, namun **Accessor Decorator** dapat mengganti logic get/set tersebut secara runtime.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Stage 3 vs Legacy Experimental Decorators

| Parameter | Legacy Decorators (`experimentalDecorators`) | Standard Stage 3 Decorators (TS 5.0+) |
| :--- | :--- | :--- |
| **Spesifikasi** | Stage 1 proposal (obsolete) | Official Stage 3 TC39 proposal |
| **Signature Method** | `(target, key, descriptor)` | `(value, context)` |
| **Mutasi Descriptor** | Langsung memodifikasi `descriptor.value` | Mengembalikan function pengganti (*pure replacement*) |
| **Metadata** | Butuh `reflect-metadata` dan `emitDecoratorMetadata` | Standar built-in `context.metadata` |
| **Private Fields** | Tidak kompatibel dengan `#field` | Sepenuhnya kompatibel dengan `#field` |
| **Parameter Decorator**| Didukung via `(target, key, index)` | **Belum didukung** (Masih dalam Stage proposal terpisah) |

### 2. Modern Encapsulation: `private` vs `#private`
TypeScript memiliki dua layer proteksi:
* `private` keyword: Soft-private (Hanya dicek saat compile-time. Saat ditranspile ke plain JS, properti tetap public).
* `#field` syntax: Hard-private (Ditegakkan langsung oleh V8 engine runtime menggunakan PrivateSymbols/PrivateEnvironment slots. Tidak bisa diakses bahkan via `any` casting atau `Object.keys`).

Stage 3 Decorator Context membawa field `private: boolean` untuk menandakan apakah decorator sedang diterapkan ke hard-private identifier.

### 3. Built-in Metaprogramming: `Symbol.metadata`
Dalam ECMAScript terkini:
```typescript
// Polyfill global jika runtime belum mendukung native Symbol.metadata
(Symbol as any).metadata ??= Symbol("Symbol.metadata");
```
Setiap decorator menerima `context.metadata` yang mereferensikan prototype metadata object yang sama. Metadata terikat secara hierarkis via prototypal inheritance.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut implementasi lengkap Method Decorator, Auto-Accessor Decorator, dan Class Decorator menggunakan spesifikasi standar TypeScript 5.0+.

```typescript
// Pastikan Symbol.metadata tersedia
(Symbol as any).metadata ??= Symbol("Symbol.metadata");

// 1. CLASS DECORATOR: Mendaftarkan Frozen Class (Immutable Prototype)
function ImmutableEntity<T extends abstract new (...args: any[]) => any>(
  value: T,
  context: ClassDecoratorContext<T>
) {
  context.addInitializer(function (this: any) {
    Object.freeze(this.constructor.prototype);
  });
  return value;
}

// 2. METHOD DECORATOR: Audit Execution Logger
function AuditLog<This, Args extends any[], Return>(
  target: (this: This, ...args: Args) => Return,
  context: ClassMethodDecoratorContext<This, (this: This, ...args: Args) => Return>
) {
  const methodName = String(context.name);

  return function (this: This, ...args: Args): Return {
    const start = performance.now();
    try {
      const result = target.apply(this, args);
      const duration = performance.now() - start;
      console.log(`[AUDIT] ${methodName} executed in ${duration.toFixed(3)}ms`);
      return result;
    } catch (error) {
      console.error(`[AUDIT ERROR] ${methodName} threw:`, error);
      throw error;
    }
  };
}

// 3. AUTO-ACCESSOR DECORATOR: Boundary Range Validator
function MinValue(min: number) {
  return function <This, Value extends number>(
    target: ClassAccessorDecoratorTarget<This, Value>,
    context: ClassAccessorDecoratorContext<This, Value>
  ): ClassAccessorDecoratorResult<This, Value> {
    return {
      get(this: This): Value {
        return target.get.call(this);
      },
      set(this: This, val: Value): void {
        if (val < min) {
          throw new RangeError(`Field ${String(context.name)} must be at least ${min}. Received: ${val}`);
        }
        target.set.call(this, val);
      },
      init(this: This, initialValue: Value): Value {
        if (initialValue < min) {
          throw new RangeError(`Initial value for ${String(context.name)} violates minimum of ${min}`);
        }
        return initialValue;
      }
    };
  };
}

// PENGGUNAAN
@ImmutableEntity
class BankAccount {
  readonly id: string;

  @MinValue(0)
  accessor balance: number;

  constructor(id: string, initialBalance: number) {
    this.id = id;
    this.balance = initialBalance;
  }

  @AuditLog
  deposit(amount: number): number {
    this.balance += amount;
    return this.balance;
  }
}

// Test Drive
const acc = new BankAccount("ACC-001", 100);
acc.deposit(50); // Log: [AUDIT] deposit executed in X.XXXms
console.log(`Final balance: ${acc.balance}`);

try {
  acc.balance = -10; // Throws RangeError!
} catch (e: any) {
  console.error(e.message);
}
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

### 1. `ImmutableEntity` Class Decorator
* `T extends abstract new (...args: any[]) => any`: Generic Constraint yang memastikan decorator hanya dapat ditempelkan pada tipe konstruktor class.
* `context.addInitializer(...)`: Mendaftarkan callback yang dijalankan tepat saat konstruktor instansiasi selesai. Callback ini membekukan prototype agar method-method class tidak dapat di-monkey-patch saat runtime.

### 2. `AuditLog` Method Decorator
* `target: (this: This, ...args: Args) => Return`: Menangkap tipe fungsi asli dengan preservasi konteks runtime `this`, tipe argumen (`Args`), dan return value (`Return`).
* `ClassMethodDecoratorContext<This, ...>`: Menerima generic yang sama dengan fungsi target untuk validasi compile-time ketat.
* `return function (this: This, ...args: Args)`: Mengembalikan wrapper closure baru yang menggantikan fungsi asli pada target prototype.
* `target.apply(this, args)`: Memanggil method asli dengan context `this` instans objek saat ini secara transparan.

### 3. `MinValue` Factory & Accessor Decorator
* `ClassAccessorDecoratorTarget<This, Value>`: Antarmuka yang menyediakan fungsi getter/setter asli dari auto-accessor.
* `ClassAccessorDecoratorResult<This, Value>`: Objek konfigurasi yang memuat tuple method pengganti: `{ get, set, init }`.
* `init(this, initialValue)`: Method lifecycle eksklusif dari Stage 3 Accessor/Field Decorator. Berjalan saat field assignment dilakukan dalam konstruktor, memvalidasi initial state sebelum disimpan.

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Enterprise REST Controller Engine

Kita akan membangun micro-framework controller berbasis deklaratif untuk Node.js environment tanpa ketergantungan pada runtime reflection engine eksternal. Framework harus:
1. Memetakan rute HTTP (`@Route("GET", "/path")`).
2. Menerapkan skema otorisasi berbasis Role-Based Access Control (`@Roles(["ADMIN"])`).
3. Mengukur throughput latency endpoint (`@Metrics()`).
4. Memvalidasi payload via DTO schema validation decorator.

Seluruh data mapping harus disimpan murni di dalam `context.metadata`.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

```typescript
// Memastikan compatibility metadata
(Symbol as any).metadata ??= Symbol("Symbol.metadata");

// Tipe HTTP Method
type HttpMethod = "GET" | "POST" | "DELETE" | "PUT";

// Definisi Struktur Metadata Routing
interface RouteMetadata {
  method: HttpMethod;
  path: string;
  handlerName: string | symbol;
  roles?: string[];
}

// Global metadata symbols
const ROUTES_KEY = Symbol("routes");

// 1. ROUTE DECORATOR FACTORY
function Route(method: HttpMethod, path: string) {
  return function <This, Args extends any[], Return>(
    target: (this: This, ...args: Args) => Return,
    context: ClassMethodDecoratorContext<This, (this: This, ...args: Args) => Return>
  ) {
    const meta = context.metadata;
    if (!meta[ROUTES_KEY]) {
      meta[ROUTES_KEY] = [] as RouteMetadata[];
    }

    const routes = meta[ROUTES_KEY] as RouteMetadata[];
    routes.push({
      method,
      path,
      handlerName: context.name,
    });

    return target;
  };
}

// 2. AUTHORIZATION DECORATOR FACTORY
function Roles(requiredRoles: string[]) {
  return function <This, Args extends any[], Return>(
    target: (this: This, ...args: Args) => Return,
    context: ClassMethodDecoratorContext<This, (this: This, ...args: Args) => Return>
  ) {
    const meta = context.metadata;
    const routes = (meta[ROUTES_KEY] ?? []) as RouteMetadata[];
    const currentRoute = routes.find((r) => r.handlerName === context.name);

    if (currentRoute) {
      currentRoute.roles = requiredRoles;
    }

    // Wrap target with authorization interceptor
    return function (this: This, ...args: Args): Return {
      const user = (this as any).currentUser;
      if (!user) {
        throw new Error(`401 Unauthorized: Session not found.`);
      }

      const hasRole = requiredRoles.some((role) => user.roles.includes(role));
      if (!hasRole) {
        throw new Error(`403 Forbidden: Insufficient permissions for ${String(context.name)}`);
      }

      return target.apply(this, args);
    };
  };
}

// 3. BASE CONTROLLER
abstract class BaseController {
  currentUser: { id: string; roles: string[] } | null = null;

  public setUserContext(user: { id: string; roles: string[] } | null) {
    this.currentUser = user;
  }
}

// 4. BUSINESS CONTROLLER IMPLEMENTATION
class UserController extends BaseController {
  private users = [
    { id: "1", name: "Alice", role: "ADMIN" },
    { id: "2", name: "Bob", role: "USER" },
  ];

  @Route("GET", "/users")
  @Roles(["ADMIN"])
  public getAllUsers() {
    return this.users;
  }

  @Route("GET", "/me")
  @Roles(["ADMIN", "USER"])
  public getCurrentUser() {
    return this.currentUser;
  }
}

// 5. APPLICATION ROUTE DISPATCHER ENGINE
class MiniDispatcher {
  public static dispatch(
    controllerInstance: BaseController,
    method: HttpMethod,
    path: string
  ): any {
    const prototype = Object.getPrototypeOf(controllerInstance);
    const metadata = (controllerInstance.constructor as any)[Symbol.metadata];

    if (!metadata || !metadata[ROUTES_KEY]) {
      throw new Error(`No route metadata configured.`);
    }

    const routes = metadata[ROUTES_KEY] as RouteMetadata[];
    const route = routes.find((r) => r.method === method && r.path === path);

    if (!route) {
      return { status: 404, body: "Not Found" };
    }

    try {
      const handler = (controllerInstance as any)[route.handlerName];
      const result = handler.call(controllerInstance);
      return { status: 200, body: result };
    } catch (err: any) {
      if (err.message.startsWith("401")) return { status: 401, body: err.message };
      if (err.message.startsWith("403")) return { status: 403, body: err.message };
      return { status: 500, body: "Internal Server Error" };
    }
  }
}

// 6. VERIFIKASI RUNTIME (TEST SUITE EXECUTION)
console.log("=== EXECUTION TEST SUITE ===");
const controller = new UserController();

// Request 1: Unauthorized Access
console.log("Req 1 (No Auth):", MiniDispatcher.dispatch(controller, "GET", "/users"));

// Request 2: Insufficient Permission (Logged as USER, hits ADMIN endpoint)
controller.setUserContext({ id: "user-2", roles: ["USER"] });
console.log("Req 2 (Forbidden):", MiniDispatcher.dispatch(controller, "GET", "/users"));

// Request 3: Success Permission for ADMIN
controller.setUserContext({ id: "admin-1", roles: ["ADMIN"] });
console.log("Req 3 (Success Admin):", MiniDispatcher.dispatch(controller, "GET", "/users"));

// Request 4: Access User Endpoint
console.log("Req 4 (Success User):", MiniDispatcher.dispatch(controller, "GET", "/me"));
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

```
Metode Abstraksi Cross-Cutting Concerns:
1. Stage 3 Decorators (Metaprogramming)
   [+] Sangat deklaratif; sintaks bersih; standardized metadata.
   [-] Evaluasi terjadi pada class declaration time; stack trace bertambah 1 layer.

2. Higher-Order Functions / Manual Wrappers
   [+] Sederhana, zero abstraction overhead, fleksibel tanpa transpile.
   [-] Boilerplate berlebih, rentan duplikasi, mengaburkan signature class.

3. Dynamic Proxies (Proxy / Reflect)
   [+] Menangkap pemanggilan secara dinamik tanpa memodifikasi class asli.
   [-] Degradasi performa drastis pada hot paths (V8 Inline Caching ter-bypass).
```

### Matriks Komparasi Karakteristik

| Fitur / Metrik | Stage 3 Decorator | Legacy Decorator (`experimental`) | Dynamic Proxy | Higher-Order Function |
| :--- | :--- | :--- | :--- | :--- |
| **Standardisasi TC39** | Ya (Stage 3) | Tidak (Abandoned) | Ya (ES6 Standard) | N/A (Functional Pattern) |
| **Compile Output** | Standar ES | Kompleks (`__decorate`) | Standar ES | Standar ES |
| **Performance Impact** | Rendah (Hanya 1x wrap saat startup)| Rendah (1x wrap) | Sangat Tinggi (Overhead per call) | Nol (Langsung memanggil closure) |
| **Parameter Decorator** | Belum Mendukung | Mendukung | Tidak Relevan | Tidak Relevan |
| **Type Integrity** | Ketat via Decorator Context | Rentan `any` casting | Sering Hilang (*Weak typing*) | Sangat Ketat |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. Kehilangan Konteks `this` pada Asynchronous Callbacks
Jika decorator mengembalikan arrow function untuk membungkus method target, arrow function akan mengikat `this` secara leksikal ke scope decorator factory, **bukan** instans class runtime:

```typescript
// PITFALL FATAL:
function BadDecorator(target: Function, context: ClassMethodDecoratorContext) {
  return (...args: any[]) => {
    // RUNTIME CRASH: 'this' di sini adalah lexical scope deklarasi, bukan Class Instance!
    return target.apply(this, args);
  };
}

// PERBAIKAN: Gunakan classic function expression
function GoodDecorator(target: Function, context: ClassMethodDecoratorContext) {
  return function (this: any, ...args: any[]) {
    // 'this' ditangkap secara dinamis sesuai pemanggil instansiasi
    return target.apply(this, args);
  };
}
```

### 2. Private Identifiers dan Reflection Isolation
Decorator yang dipasang pada hard-private property (`#property`) tidak dapat membaca name identifier secara arbitrary pada prototype eksternal. `context.name` akan tetap mengembalikan nama string, namun akses mutasi di luar slot instance class tersebut akan memicu `TypeError: Cannot read private member from an object whose class did not declare it`.

### 3. Inheritance Traversal pada Metadata Object
Objek `context.metadata` memanfaatkan Prototype Chain secara native. Metadata subclass mewarisi metadata parent class via `Object.prototype`.
* *Trap*: Jika subclass memutasi nested object di dalam metadata secara direct (`metadata.tags.push(...)`), maka data parent class akan ikut terkorupsi!
* *Mitigasi*: Selalu buat shallow copy atau pisahkan isolated arrays per level inheritance.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Mengaktifkan `experimentalDecorators: true` bersama TypeScript 5
* **Mistake**: Menyalakan flag `experimentalDecorators: true` di `tsconfig.json` saat mencoba menulis Stage 3 Decorators.
* **Akibat**: TypeScript compiler akan mengasumsikan signature legacy (`target, propertyKey, descriptor`), menyebabkan error syntax compiler: `Expected 2 arguments, but got 3`.
* **Solusi**: Set `"experimentalDecorators": false` atau hapus baris tersebut dari `tsconfig.json`.

### 2. Lupa Mengembalikan Return Value dari Target
```typescript
// SALAH
function LogResult(target: Function, context: ClassMethodDecoratorContext) {
  return function (this: any, ...args: any[]) {
    const res = target.apply(this, args);
    // Lupa me-return 'res', pemanggil mendapatkan 'undefined'
  };
}

// BENAR
function LogResult(target: Function, context: ClassMethodDecoratorContext) {
  return function (this: any, ...args: any[]) {
    const res = target.apply(this, args);
    return res; // Wajib di-return
  };
}
```

### 3. Asumsi Decorator Berjalan per Instansiasi Objek
* **Mistake**: Menginisialisasi state spesifik per user di dalam decorator scope utama:
  ```typescript
  function Counter(target: Function, context: ClassMethodDecoratorContext) {
    let callCount = 0; // State ini adalah SINGLETON di level prototype!
    return function (this: any, ...args: any[]) {
      callCount++;
      return target.apply(this, args);
    };
  }
  ```
* **Akibat**: State dibagi (*shared*) ke seluruh instans class yang dibuat.
* **Solusi**: Gunakan `WeakMap` yang dipetakan ke pointer `this`, atau manfaatkan `context.addInitializer`.

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Idempotence & Purity**: Decorator wrappers tidak boleh menghasilkan side effect tak terkendali saat fase definisi class (*definition time*). Batasi proses berat (koneksi database, I/O) hingga method yang didekorasi dieksekusi.
2. **Defensive Metadata Writes**: Gunakan `Symbol` unik sebagai key untuk metadata guna menghindari tabrakan (*name collisions*) antar-library pihak ketiga.
3. **Type-Safe Decorator Signatures**: Selalu gunakan generic type parameters `<This, Args extends any[], Return>` agar method wrapper mewarisi auto-complete dan static type checking penuh.
4. **Hindari Mutasi Prototype Langsung**: Manfaatkan `context.addInitializer` alih-alih melakukan `target.prototype.foo = bar` secara imperatif.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Mencegah V8 De-Optimization (Monomorphic Call Sites)
Saat decorator membungkus method target, V8 engine membentuk Inline Cache (IC) baru. Jika decorator wrapper memodifikasi struktur internal `this` (menambah atau menghapus properti secara dinamis), hidden class (*shape*) objek akan bertransisi menjadi slow dictionary mode (*megamorphic*), yang memperlambat pemanggilan method hingga 10x-50x lipat.

```typescript
// BAD: Mengubah shape objek, merusak Inline Cache
function MutateShape(target: Function, context: ClassMethodDecoratorContext) {
  return function (this: any, ...args: any[]) {
    this.__injected_timestamp = Date.now(); // Hindari mutasi shape di runtime hot path
    return target.apply(this, args);
  };
}

// GOOD: Simpan context terpisah di WeakMap instance
const instanceTimestamps = new WeakMap<object, number>();
function FastContext(target: Function, context: ClassMethodDecoratorContext) {
  return function (this: any, ...args: any[]) {
    instanceTimestamps.set(this, Date.now()); // Memory safe & mempertahankan shape instance
    return target.apply(this, args);
  };
}
```

### 2. Hindari Alokasi Closure Berlebih pada Hot Paths
Jika suatu method dieksekusi jutaan kali per detik, hindari pembuatan objek sementara (seperti rest parameters `...args` jika argumennya statis dan sedikit). Gunakan `target.call(this, arg1, arg2)` jika arity method sudah pasti.

---

# SEKSI 16 — KEAMANAN & HARDENING

### 1. Prototype Pollution Defense
Saat decorator memetakan metadata rute atau menyusun property injection, input pengguna eksternal tidak boleh menjadi key dari prototype metadata secara langsung.

```typescript
// DEFENSIVE MEASURE: Cegah polusi metadata
function SafeRegisterMetadata(meta: Record<string | symbol, any>, key: string, val: any) {
  const sanitizedKey = key.replace(/__proto__|constructor|prototype/g, "");
  if (!sanitizedKey) {
    throw new SecurityError("Exploitation attempt detected via property pollution.");
  }
  meta[sanitizedKey] = val;
}
```

### 2. Freezing Intercepted Methods
Pastikan wrapper method yang menggantikan method asli didefinisikan sebagai non-configurable dan non-writable jika class tersebut dirancang untuk dieksekusi di multi-tenant environment, guna mencegah modifikasi dari kode malicious.

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### 1. Menjaga Stack Trace Asli
Saat method dibungkus, nama fungsi dalam call stack traces seringkali berubah menjadi anonymous wrapper: `at Array.<anonymous> (file.ts:12)`.

```typescript
function Observable(target: Function, context: ClassMethodDecoratorContext) {
  const originalName = String(context.name);

  // Buat named function secara eksplisit
  const wrapper = {
    [originalName](this: any, ...args: any[]) {
      try {
        return target.apply(this, args);
      } catch (err: any) {
        // Log stack trace dengan nama fungsi target yang jelas
        console.error(`Error inside decorated method [${originalName}]:`, err.stack);
        throw err;
      }
    }
  }[originalName];

  return wrapper;
}
```

### 2. Debugging `context.metadata`
Untuk menginspeksi seluruh metadata yang tersimpan dalam class hierarchy:
```typescript
function dumpClassMetadata(targetClass: Function) {
  const meta = (targetClass as any)[Symbol.metadata];
  console.dir(meta, { depth: null, colors: true });
}
```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

### Type Signature Cheat Sheet (TypeScript 5+)

```typescript
// 1. Class Decorator
(value: Function, context: ClassDecoratorContext) => Function | void;

// 2. Method Decorator
(value: Function, context: ClassMethodDecoratorContext) => Function | void;

// 3. Getter Decorator
(value: Function, context: ClassGetterDecoratorContext) => Function | void;

// 4. Setter Decorator
(value: Function, context: ClassSetterDecoratorContext) => Function | void;

// 5. Field Decorator
(value: undefined, context: ClassFieldDecoratorContext) => (initialValue: T) => T | void;

// 6. Accessor Decorator
(
  value: { get: () => T; set: (val: T) => void },
  context: ClassAccessorDecoratorContext
) => { get?: () => T; set?: (val: T) => void; init?: (val: T) => T } | void;
```

### Aturan Emas Decorators
1. **Urutan Evaluasi Factory**: Atas ke Bawah.
2. **Urutan Eksekusi Wrapper**: Bawah ke Atas (Inside-Out).
3. **Eksekusi Waktu**: Class definition time (hanya sekali saat startup runtime), bukan instantiation time.
4. **Arrow Function Pitfall**: Jangan gunakan arrow function sebagai wrapper method jika membutuhkan runtime `this`.

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Bagian 1: Tingkat Basic (5 Soal)

**Q1: Kapan logika method decorator wrapper pertama kali dibentuk dan dieksekusi?**
* A) Setiap kali class diinisialisasi dengan keyword `new`.
* B) Saat file module di-load dan class dievaluasi oleh runtime JavaScript engine.
* C) Setiap kali method yang bersangkutan dipanggil.
* D) Saat build-time kompilasi TypeScript saja.
* **Jawaban:** B
* **Rasional:** Decorator diterapkan saat class definition time. Method wrapper dibuat sekali saat engine membaca definisi class; wrapper tersebut kemudian dieksekusi setiap kali method dipanggil (opsi C mereferensikan eksekusi logic wrapper-nya, bukan inisialisasi decorator-nya).

**Q2: Opsi tsconfig manakah yang HARUS dimatikan/dihapus agar TypeScript 5 menggunakan ECMAScript Stage 3 Decorators?**
* A) `"useDefineForClassFields": false`
* B) `"experimentalDecorators": true`
* C) `"target": "ES5"`
* D) `"emitDecoratorMetadata": true`
* **Jawaban:** B
* **Rasional:** Mengaktifkan `"experimentalDecorators": true` akan memaksa TypeScript compiler memakai legacy Stage 1 decorator signature.

**Q3: Keyword apa yang diperkenalkan untuk memungkinkan decorator mengontrol pembacaan, penulisan, dan inisialisasi suatu field class?**
* A) `delegate`
* B) `property`
* C) `accessor`
* D) `observable`
* **Jawaban:** C
* **Rasional:** Keyword `accessor` memicu pembuatan auto-accessor (getter/setter implisit di atas private storage) yang dapat didekorasi via `ClassAccessorDecoratorContext`.

**Q4: Mengapa wrapper decorator tidak boleh menggunakan sintaks Arrow Function `() => {}`?**
* A) Arrow function tidak mendukung penanganan error `try/catch`.
* B) Arrow function mengikat `this` secara leksikal pada saat deklarasi, sehingga menghilangkan akses ke instansiasi class runtime.
* C) V8 engine menolak arrow function di dalam prototype class.
* D) Arrow function memiliki overhead alokasi memori 100x lipat lebih besar.
* **Jawaban:** B
* **Rasional:** Arrow function tidak memiliki binding `this` sendiri, sehingga target method tidak akan dapat mengakses properti objek instansinya.

**Q5: Di manakah decorator standar Stage 3 menyimpan data refleksi/metaprogramming secara native?**
* A) Library global `Reflect.getMetadata()`
* B) Di dalam prototype target secara manual via `__metadata__`
* C) Di dalam objek `context.metadata` yang memanfaatkan `Symbol.metadata`
* D) Di dalam `package.json` manifest
* **Jawaban:** C
* **Rasional:** Stage 3 Decorator Metadata proposal menyediakan slot universal melalui `context.metadata` yang terhubung ke `Symbol.metadata`.

---

### Bagian 2: Tingkat Intermediate (5 Soal)

**Q6: Perhatikan kode berikut. Urutan output log yang benar saat instansiasi/eksekusi adalah:**
```typescript
function DecA() {
  console.log("Eval A");
  return (fn: any, ctx: any) => console.log("Apply A");
}
function DecB() {
  console.log("Eval B");
  return (fn: any, ctx: any) => console.log("Apply B");
}

class Test {
  @DecA()
  @DecB()
  run() {}
}
```
* A) Apply B -> Apply A -> Eval A -> Eval B
* B) Eval A -> Eval B -> Apply B -> Apply A
* C) Eval A -> Apply A -> Eval B -> Apply B
* D) Eval B -> Eval A -> Apply A -> Apply B
* **Jawaban:** B
* **Rasional:** Factory dievaluasi top-down (`Eval A`, lalu `Eval B`). Penerapan decorator berjalan bottom-up (`Apply B`, lalu `Apply A`).

**Q7: Manakah decorator berikut yang valid jika kita ingin menghentikan instansiasi class yang melanggar batasan tertentu?**
* A) Field Decorator menggunakan `context.access.set`
* B) Class Decorator yang mengembalikan subclass constructor pengganti dengan throw di constructor
* C) Method Decorator pada private `#constructor`
* D) Parameter Decorator dengan validasi index 0
* **Jawaban:** B
* **Rasional:** Class decorator dapat me-return konstruktor turunan baru yang mengeksekusi validasi custom sebelum memanggil `super(...args)`.

**Q8: Apa yang terjadi jika dua method decorator mengembalikan function baru untuk target yang sama?**
* A) TypeScript melempar error compile time: duplicate replacement.
* B) Terbentuk pipeline bersarang (composition): wrapper method terluar memanggil wrapper method di dalamnya.
* C) Decorator yang paling atas menimpa decorator di bawahnya tanpa memanggil decorator di bawahnya.
* D) Runtime crash dengan error `TypeError: Duplicate identifier`.
* **Jawaban:** B
* **Rasional:** Decorators membentuk rantai komposisi fungsi (Function Composition): `outer(inner(originalMethod))`.

**Q9: Bagaimana cara mengisolasi state agar suatu method decorator caching tidak memicu kebocoran data antar-user pada concurrent request?**
* A) Menyimpan cache pada local variable di luar decorator factory.
* B) Menyimpan cache pada `target.prototype`.
* C) Menggunakan `WeakMap<object, CacheStore>` dengan instans class (`this`) sebagai key map.
* D) Menggunakan Redis connection singleton pada field decorator.
* **Jawaban:** C
* **Rasional:** `WeakMap` dengan key referensi instans objek menjamin isolasi state antar-instans dan mencegah memory leak karena key dapat di-garbage collect saat instans dihapus.

**Q10: Mengapa mutasi dinamis properti pada instans class di dalam method decorator wrapper dapat merusak kinerja engine JavaScript (V8)?**
* A) Memaksa Garbage Collector berjalan setiap milidetik.
* B) Menyebabkan Hidden Class (Shape) objek berubah dari Monomorphic menjadi Megamorphic/Dictionary Mode, mendegradasi Inline Caching.
* C) Membatalkan proses Just-In-Time (JIT) compilation secara permanen untuk seluruh file.
* D) Mengubah prototype chain objek menjadi circular reference.
* **Jawaban:** B
* **Rasional:** V8 mengoptimalkan property lookup melalui Inline Caching yang bergantung pada kestabilan shape (Hidden Class). Menambah properti ad-hoc merusak kestabilan tersebut.

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Task: Bangun Type-Safe Cache Invalidation & Event Dispatcher Layer

#### Deskripsi
Buat modul repository berbasis class TypeScript murni yang mengimplementasikan dua Modern Decorator khusus menggunakan TypeScript 5.0+ Stage 3 Standard:

1. `@Cacheable(ttlMs: number)`:
   * Diterapkan pada method pembacaan data (misal: `findById(id: string)`).
   * Melakukan in-memory caching berdasarkan parameter yang diterima method.
   * Jika parameter yang sama dipanggil sebelum TTL kedaluwarsa, kembalikan hasil dari cache tanpa mengeksekusi body method asli.
   * State cache wajib terisolasi antar-instansiasi menggunakan `WeakMap`.

2. `@InvalidatesCache(methodNames: string[])`:
   * Diterapkan pada method mutasi data (misal: `update(id: string, data: any)` atau `delete(id: string)`).
   * Ketika method mutasi ini selesai dieksekusi dengan sukses, bersihkan entri cache yang relevan untuk method-method yang didaftarkan pada parameter `methodNames`.

#### Syarat & Batasan
* Dilarang menggunakan library pihak ketiga (`reflect-metadata`, `lodash`, dsb.).
* Tidak boleh menyalakan `experimentalDecorators: true` di konfigurasi TypeScript.
* Wajib type-safe: decorator harus mempertahankan signature method asli.
* Sediakan class dummy `UserRepository` untuk mendemonstrasikan bahwa pemanggilan `findById("1")` kedua mengambil dari cache, dan setelah `update("1", ...)` dipanggil, pemanggilan `findById("1")` berikutnya kembali mengeksekusi method asli. Run script Anda dengan `ts-node` atau transpile dengan `tsc` target ES2022+.