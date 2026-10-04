# BAB 04: Quiz, Challenge, & Knowledge Check
**Advanced Object Systems, Prototypes & Metaprogramming**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Dualitas `prototype` vs `[[Prototype]]`
Jelaskan secara struktural perbedaan antara properti `.prototype` yang dimiliki oleh sebuah `Function` dan internal slot `[[Prototype]]` (yang diakses melalui `Object.getPrototypeOf()` atau `__proto__`) yang dimiliki oleh setiap instance objek di JavaScript. Apa yang terjadi pada alokasi memori dan resolusi lookup ketika sebuah metode didefinisikan langsung di dalam fungsi konstruktor (`this.method = ...`) dibandingkan ketika didefinisikan pada `Constructor.prototype.method`?

### Soal 1.2: Anatomi Property Descriptor & Tingkat Immutabilitas
Dekomposisi struktur internal dari sebuah *property descriptor* di JavaScript. Jelaskan perbedaan semantik dan batasan penegakan (*enforcement*) antara:
1. `Object.preventExtensions()`
2. `Object.seal()`
3. `Object.freeze()`

Mengapa `Object.freeze()` dikategorikan sebagai *shallow immutability*, dan bagaimana implikasi arsitekturalnya terhadap objek bersarang (*nested objects*) serta referensi koleksi (`Map`/`Set`)?

### Soal 1.3: Urgensi dan Mekanisme `Reflect` Bersama `Proxy`
Mengapa spesifikasi ECMAScript memperkenalkan objek global `Reflect` berdampingan dengan `Proxy`? Mengapa mengeksekusi operasi target secara langsung di dalam *trap* (misalnya: `target[prop] = value` di dalam trap `set`) dianggap sebagai *anti-pattern* fatal dibandingkan menggunakan `Reflect.set(target, prop, value, receiver)`? Kaitkan jawaban Anda dengan pelestarian konteks *receiver* (`this`).

### Soal 1.4: Well-Known Symbols dan Intersepsi Protokol Engine
Bagaimana JavaScript Engine memanfaatkan *Well-Known Symbols* untuk mengontrol perilaku internal objek? Jelaskan mekanisme intervensi kustom pada:
1. `Symbol.toPrimitive`: Bagaimana mesin membedakan *hint* (`"string"`, `"number"`, `"default"`) dalam operasi koersi matematis maupun konkatenasi.
2. `Symbol.iterator`: Kontrak protokol apa yang harus dipenuhi agar sebuah objek biasa dapat dikonsumsi oleh sintaksis `for...of` dan *spread operator* `...`.

### Soal 1.5: Desugaring ES6 Classes ke Prototypal Chain & `[[HomeObject]]`
ES6 `class` sering disebut sebagai "hanya *syntactic sugar*" di atas *prototypal inheritance*. Bedah secara mekanis mengapa pernyataan tersebut tidak sepenuhnya akurat! Jelaskan peran internal slot `[[HomeObject]]`, keterkaitannya dengan *keyword* `super`, dan mengapa pemanggilan konstruktor kelas tanpa *keyword* `new` melempar `TypeError` di level bytecode engine sedangkan fungsi konstruktor ES5 tradisional tidak.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: V8 Hidden Classes (Shapes) & Inline Cache (IC) Deoptimization
Analisis cuplikan kode berikut dari perspektif V8 Optimization Engine:
```javascript
function Point(x, y) {
  this.x = x;
  this.y = y;
}

const p1 = new Point(1, 2);
const p2 = new Point(3, 4);

// Mutasi A
p1.z = 5;

// Mutasi B
delete p2.x;
```
Bagaimana *Hidden Classes (Shapes)* dan pohon transisinya (*transition tree*) terbentuk saat inisialisasi `p1` dan `p2`? Apa dampak spesifik dari "Mutasi A" dan "Mutasi B" terhadap transisi *Shape*, alokasi memori (*backing store dictionary mode*), dan degradasi performa pada *Inline Cache (IC)* (dari *monomorphic* menuju *megamorphic*)?

### Soal 2.2: Pelanggaran Invarian pada Proxy Traps
Spesifikasi ECMAScript mendefinisikan *Proxy Invariants* yang dieksekusi secara ketat oleh engine untuk mencegah korupsi semantik bahasa. 
Diberikan kode berikut:
```javascript
const target = {};
Object.defineProperty(target, 'apiKey', {
  value: 'SECRET_PROD_123',
  writable: false,
  configurable: false
});

const proxy = new Proxy(target, {
  get(t, prop, receiver) {
    if (prop === 'apiKey') {
      return 'MOCKED_KEY';
    }
    return Reflect.get(t, prop, receiver);
  }
});

console.log(proxy.apiKey);
```
Jelaskan mengapa kode di atas akan melempar `TypeError` pada runtime! Invarian spesifik apa yang dilanggar? Apa saja kondisi invariabel lain yang dipaksakan oleh engine pada trap `getOwnPropertyDescriptor` dan `preventExtensions`?

### Soal 2.3: Lost `this` Context pada Getter Inheritans via Proxy
Diberikan rantai prototipe yang dibungkus oleh Proxy:
```javascript
const parent = {
  _value: 10,
  get calculated() {
    return this._value * 2;
  }
};

const proxyParent = new Proxy(parent, {
  get(target, prop, receiver) {
    console.log(`Accessing: ${String(prop)}`);
    return Reflect.get(target, prop, receiver);
  }
});

const child = Object.create(proxyParent);
child._value = 50;

console.log(child.calculated);
```
1. Berapakah nilai `child.calculated` yang dicetak (`20` atau `100`), dan properti apa saja yang dicatat oleh `console.log` di dalam trap?
2. Bagaimana hasilnya jika implementasi trap diubah menjadi `return target[prop]` tanpa meneruskan parameter `receiver`? Jelaskan alur eksekusi internal resolusi `this` pada kedua kondisi tersebut.

### Soal 2.4: Memory Leak Semantics pada Metaprogramming & WeakMaps
Dalam membangun sistem reaktivitas (*fine-grained reactivity*) menggunakan `Proxy` dan `WeakMap`, jelaskan kondisi spesifik di mana memori masih dapat bocor (*memory leak*) meskipun `WeakMap` menggunakan *weak references* untuk *keys*-nya. Bagaimana referensi sirkular antara *target object*, *proxy handler*, dan fungsi *subscriber* yang tersimpan di dalam closure dapat mencegah *Garbage Collector* (khususnya *Mark-and-Sweep*) mereklamasi memori?

### Soal 2.5: Prototype Pollution: Root Cause, Attack Vector, & Engine Mitigation
Perhatikan fungsi merge rekursif naif berikut:
```javascript
function deepMerge(target, source) {
  for (let key in source) {
    if (source[key] instanceof Object && key in target) {
      deepMerge(target[key], source[key]);
    } else {
      target[key] = source[key];
    }
  }
  return target;
}
```
1. Tunjukkan bagaimana payload JSON berbahaya dapat memanipulasi `__proto__` atau `constructor.prototype` untuk mengeksekusi *Prototype Pollution* global.
2. Tuliskan implementasi perbaikan defensif (*hardening*) tingkat *production* untuk mencegah polusi ini tanpa mematikan fungsionalitas penggabungan objek normal (gunakan pendekatan validasi kunci, `Object.create(null)`, dan `Object.hasOwn()`).

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Degradasi Throughput 85% pada Microservice API Gateway
Sebuah tim arsitektur menerapkan custom *Access Control Layer (ACL)* dinamis berbasis `Proxy` pada level domain model di Node.js API Gateway yang memproses 35.000 RPS. 

Setiap payload JSON yang masuk dideerialisasi menjadi objek, lalu dibungkus oleh rekursif *deep-proxy* untuk mencegat setiap mutasi field dan memvalidasi izin role pengguna secara *real-time*. Tiga hari setelah peluncuran, metrik APM menunjukkan:
- Latensi P99 meroket dari 12ms ke 480ms.
- Waktu GC (*Garbage Collection*) melonjak hingga 40% dari total CPU time.
- V8 CPU Profiler menunjukkan fungsi deoptimasi masif berlabel `OptimizeType: Deopt (Bailout)` dan alokasi IC beralih ke `MEGAMORPHIC`.

**Pertanyaan Diagnostik:**
1. Mengapa pembuatan deep-proxy dinamis per-request pada throughput tinggi menyebabkan alokasi memori masif dan menghancurkan efisiensi V8 Inline Caches?
2. Bagaimana cara merancang ulang arsitektur proteksi data tersebut tanpa membungkus setiap instansiasi objek ke dalam Proxy, namun tetap mempertahankan integritas validasi skema runtime?

### Skenario B: Race Condition dan State Mutation Corruption pada Global State Store
Sebuah aplikasi web enterprise berbasis micro-frontend menggunakan *custom central state store* yang mengekspos objek state yang diproteksi menggunakan `Proxy`. 

Untuk memastikan *immutability*, trap `set` pada Proxy melempar error di lingkungan produksi jika mutasi dilakukan di luar *Action Dispatcher*. Namun, tim menemukan bug kritis: sebuah plugin pihak ketiga berhasil mengubah isi array nested (`state.user.roles.push('ADMIN')`) tanpa memicu trap `set` dari Proxy terluar, menyebabkan korupsi hak akses antar micro-app tanpa terdeteksi oleh sistem audit.

**Pertanyaan Diagnostik:**
1. Mengapa operasi mutasi in-place seperti `Array.prototype.push`, `splice`, atau mutasi langsung pada nested object gagal dicegat oleh *shallow Proxy*?
2. Analisis implikasi konsistensi data jika Anda memilih solusi *On-Demand Dynamic Proxy Wrapping* vs *Eager Deep Freezing via Object.freeze*. Apa trade-off struktural antara kecepatan write vs overhead memori untuk state tree berukuran 20MB?

### Skenario C: Dilema Arsitektur ORM: Proxied Lazy-Loading vs Explicit Accessors vs Code-Generation
Anda memimpin arsitektur data layer untuk platform e-commerce skala besar. Tim sedang mendesain Identity Map dan Lazy-Loading pattern untuk ORM internal Node.js. 

Ada tiga proposal arsitektur yang diajukan untuk mendeteksi kapan relasi antar-entitas (misal: `order.items`) perlu di-fetch dari database:
- **Proposal 1:** Menggunakan `Proxy` dinamis pada setiap model entitas untuk mencegat akses properti via trap `get`.
- **Proposal 2:** Mendefinisikan *ES Getters/Setters* via `Object.defineProperty()` saat skema model dikompilasi saat bootstrap.
- **Proposal 3:** Pendekatan *Data Mapper* murni (POJO) tanpa metaprogramming, mengharuskan pemanggilan eksplisit via service/repository (`orderService.getItems(order)`).

**Pertanyaan Diagnostik:**
1. Evaluasi ketiga proposal tersebut berdasarkan kriteria:
   - Overhead CPU & Memory Footprint pada pemrosesan batch 100.000 entitas.
   - Kemudahan *Serialization* (`JSON.stringify()`) dan interoperabilitas dengan library pihak ketiga.
   - Kompleksitas debugging (analisis *stack trace* dan visibilitas saat diinspeksi via runtime debugger).
2. Tentukan arsitektur mana yang paling layak untuk sistem dengan beban transaksi tinggi (*read-heavy*), dan berikan justifikasi teknis komparatif Anda!

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise Reactive State Kernel dengan Deep Revocable Proxies, Invariant Enforcement, & Mutation Journaling

#### Problem Statement
Sebagian besar library *state management* modern bergantung pada Proxy untuk reaktivitas, namun sering kali gagal menangani *lifecycle revocation*, isolasi mutasi transaksi, atau overhead deteksi siklus (*cyclic graph*), yang berakibat pada *memory leak* dan *state divergence*. Anda diminta untuk membangun sebuah core engine independen (State Kernel) berbasis metaprogramming murni tanpa dependensi eksternal.

#### Requirements
1. **Deep Dynamic Proxy Trapping:** Objek state kompleks (termasuk objek bersarang dan Array) harus dibungkus secara lazily (*on-access*). Mutasi pada level hierarki mana pun harus terdeteksi.
2. **Transactional State Machine (`draft` pattern):**
   - Kernel menyediakan method `produce(baseState, recipeFn)`.
   - Di dalam `recipeFn`, pengguna memutasi `draft` (berbasis Proxy).
   - Jika `recipeFn` melempar error, seluruh mutasi harus dibatalkan (*aborted*), dan `baseState` dijamin murni tidak termutasi.
   - Jika berhasil, kembalikan objek *immutable* baru yang membagikan struktur data yang tidak berubah (*structural sharing*) dengan `baseState`.
3. **Revocation Execution:** Segera setelah `recipeFn` selesai dieksekusi (baik sukses maupun gagal), semua Proxy draft yang dibuat selama siklus tersebut harus di-revokasi (*revoked*) menggunakan `Proxy.revocable()`. Setiap upaya akses/mutasi lanjutan terhadap referensi draft lama di luar fungsi harus melempar `TypeError: Cannot perform 'get/set' on a proxy that has been revoked`.
4. **Structural Invariant & Type Enforcement:**
   - Objek yang dibekukan (`Object.isFrozen(obj) === true`) atau non-extensible tidak boleh merusak invarian engine.
   - Engine harus mendukung penggunaan `Symbol` kustom (`Symbol.for('kernel.meta')`) yang tidak dapat diiterasi (`enumerable: false`) untuk melacak metadata internal.
5. **Mutation Journaling:** Setiap mutasi harus dicatat dalam array internal dengan struktur:
   `{ type: 'SET' | 'DELETE', path: Array<string|symbol>, oldValue: any, newValue: any }`.

#### Constraints
- Zero external dependencies.
- Mendukung referensi sirkular tanpa menimbulkan *infinite recursive loop* (gunakan `WeakMap` untuk cache proxy).
- Performa: Pembacaan properti yang tidak mengalami mutasi tidak boleh menduplikasi objek target (*structural sharing preservation*).
- Larangan modifikasi: Dilarang memodifikasi prototype global (`Object.prototype`, `Array.prototype`).

#### Expected Output Contract
```javascript
const kernel = new StateKernel();

const initialState = {
  user: {
    name: "Alice",
    roles: ["editor"]
  },
  settings: {
    theme: "dark"
  }
};

Object.freeze(initialState.settings); // Invariant test

let leakedDraft;

const [nextState, journal] = kernel.produce(initialState, (draft) => {
  draft.user.name = "Bob";
  draft.user.roles.push("admin");
  leakedDraft = draft.user;
});

// 1. Immutability verification
console.log(initialState.user.name); // "Alice"
console.log(nextState.user.name);    // "Bob"

// 2. Structural sharing check (settings tidak berubah, referensi memori harus identik)
console.log(initialState.settings === nextState.settings); // true
console.log(initialState.user === nextState.user);         // false

// 3. Revocation verification
try {
  console.log(leakedDraft.name);
} catch (err) {
  console.log("Proxy revoked successfully"); // Harus masuk ke catch block
}

// 4. Journaling verification
console.log(journal);
/*
Output Journal:
[
  { type: 'SET', path: ['user', 'name'], oldValue: 'Alice', newValue: 'Bob' },
  { type: 'SET', path: ['user', 'roles', '1'], oldValue: undefined, newValue: 'admin' },
  { type: 'SET', path: ['user', 'roles', 'length'], oldValue: 1, newValue: 2 }
]
*/
```

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan fundamental antara prototipe sebuah fungsi (`F.prototype`) dan prototipe dari instance (`Object.getPrototypeOf(instance)`).
- [ ] Mekanisme resolusi rantai prototipe (*prototype chain lookup*) dan bagaimana proses dereferensi berjalan hingga mencapai `null`.
- [ ] Makna serta konsekuensi mutasi atribut descriptor: `value`, `writable`, `get`, `set`, `enumerable`, dan `configurable`.
- [ ] Cara kerja internal engine V8 terkait *Hidden Classes (Shapes)*, *Transition Trees*, dan bahaya transisi ke *Dictionary/Slow Mode*.
- [ ] Hubungan simbiotik antara `Proxy` traps dan method statis `Reflect` dalam menjaga integritas *internal methods* bahasa.
- [ ] Hakikat *Proxy Invariants* dan batasan spesifikasi yang tidak dapat dilanggar oleh trap logic.
- [ ] Mengapa *Receiver* context (`this`) krusial saat mengeksekusi operasi prototipe dengan getter/setter bersarang.
- [ ] Ancaman keamanan *Prototype Pollution*, vektor serangannya, serta dampaknya pada runtime security lingkungan Node.js.
- [ ] Perbedaan semantik penanganan referensi antara `WeakMap`/`WeakSet` vs `Map`/`Set` dalam arsitektur metaprogramming.

### Saya tidak perlu menghafal:
- [ ] Nomor opcode bytecode V8 spesifik (misal: `LdaNamedProperty`, `StaNamedProperty`) untuk setiap operasi objek.
- [ ] Seluruh daftar 13 *Proxy traps* dan parameter spesifiknya secara verbatim di luar kepala (cukup pahami pemetaannya terhadap internal operations ECMAScript).
- [ ] Spesifikasi matematis algoritma hashing yang digunakan V8 untuk bucket memori *dictionary mode*.

### Saya harus bisa melakukan:
- [ ] Melakukan debugging dan tracing akar masalah degradasi performa yang diakibatkan oleh *megamorphic IC* akibat mutasi bentuk objek yang tidak seragam.
- [ ] Mengonfigurasi property descriptor secara presisi menggunakan `Object.defineProperty()` dan `Object.defineProperties()`.
- [ ] Mengimplementasikan Proxy transparan (*transparent virtualization*) yang menjaga interoperabilitas dengan method bawaan seperti `Array.prototype.slice` atau `Map.prototype.get`.
- [ ] Merancang arsitektur sanitasi payload yang kebal terhadap *Prototype Pollution* menggunakan metode validasi eksplisit dan *dictionary null-prototype*.
- [ ] Membangun abstraction layer berbasis `Proxy.revocable()` untuk mencegah kebocoran state atau siklus hidup objek yang tidak sah.
- [ ] Mengkombinasikan *Well-Known Symbols* (`Symbol.iterator`, `Symbol.toPrimitive`, `Symbol.hasInstance`) untuk merancang custom domain object yang terintegrasi secara native dengan operator bahasa.