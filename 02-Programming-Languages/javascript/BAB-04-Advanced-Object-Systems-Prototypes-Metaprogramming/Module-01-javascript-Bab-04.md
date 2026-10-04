# Bab 04 Module 01: Advanced Object Systems, Prototypes & Metaprogramming

---

## SEKSI 01 — IDENTITAS MODUL

* **Jalur Kurikulum:** 02-Programming-Languages
* **Bahasa / Ekosistem:** JavaScript (ECMAScript 2022+)
* **Nomor Modul:** Bab 04, Modul 01
* **Judul Modul:** Advanced Object Systems, Prototypes & Metaprogramming
* **Prasyarat Pengetahuan:**
  * Pemahaman mendalam tentang tipe data primitif vs tipe referensi (Object).
  * Mekanisme eksekusi JavaScript dasar: Call Stack, Memory Heap, dan Execution Context.
  * Sintaksis ES6 dasar: Classes, Destructuring, Rest/Spread, Arrow Functions.
  * Pemahaman dasar tentang Closures dan Scope Chain.
* **Target Tingkat Kemahiran:** Advanced / Senior Software Engineer.
* **Estimasi Waktu Penyelesaian:** 8 – 10 Jam Pembelajaran Mandiri & Hands-on Lab.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini secara komprehensif, peserta didik diharapkan mampu:

1. **Membedah Mekanisme Prototypal Inheritance:** Menganalisis dan mengonstruksi delegasi rantai prototipe (`[[Prototype]]`, `.prototype`, `Object.create`) hingga tingkat representasi memori engine JavaScript.
2. **Memanipulasi Property Descriptors Secara Presisi:** Mengontrol mutabilitas, enumerabilitas, dan konfigurabilitas objek secara granular menggunakan `Object.defineProperty` dan `Object.defineProperties`.
3. **Menguasai Metaprogramming Tingkat Lanjut:** Mengimplementasikan teknik introspeksi, intercepti, dan modifikasi runtime menggunakan API `Proxy`, `Reflect`, dan `Well-Known Symbols`.
4. **Mengoptimalkan Representasi Internal Engine (V8 Hidden Classes & Inline Caches):** Menulis kode yang ramah kompilator Just-In-Time (JIT) dengan mencegah de-optimasi akibat perubahan bentuk objek (*shape transitions* / *megamorphic ICs*).
5. **Memitigasi Kerentanan Keamanan Prototipe:** Mengidentifikasi dan menangkal eksploitasi keamanan tingkat lanjut seperti *Prototype Pollution* melalui penerapan objek kamus nir-prototipe (*null-prototype objects*) dan pembekuan prototipe (*prototype freezing*).

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam JavaScript, orientasi objek sering disalahpahami oleh pengembang yang berasal dari bahasa berbasis *class-based classical inheritance* (seperti Java, C++, atau C#). Di JavaScript:

1. **Classes Adalah Syntactic Sugar di Atas Prototipe:** Kata kunci `class` tidak mendefinisikan cetak biru (*blueprint*) statis yang mengkloning struktur ke instansiasi baru. `class` hanyalah abstraksi ergonomis di atas *prototypal delegation*.
2. **Delegasi, Bukan Salinan (Delegation, Not Copying):** Saat Anda memanggil metode pada suatu objek, JavaScript tidak mencari metode yang disalin ke objek tersebut. Objek tersebut mendelegasikan pencarian ke atas melalui rantai prototipe (`[[Prototype]]`) sampai menemukan properti tersebut atau mencapai `null`.
3. **Objek Adalah Kumpulan Kantong Properti Dinamis:** Objek pada tingkat konseptual adalah tabel hash (*dictionary*) dari kunci (*strings* atau *symbols*) ke *property descriptors*. Namun, pada tingkat engine (V8), objek direpresentasikan secara terstruktur menggunakan *Shapes* (atau *Hidden Classes*) untuk efisiensi eksekusi tingkat mesin.
4. **Metaprogramming Menggeser Status Objek dari Pasif Menjadi Reaktif:** Melalui `Proxy` dan `Reflect`, objek bukan lagi struktur data pasif yang hanya menerima mutasi langsung, melainkan antarmuka terprogram yang mampu mencegat operasi fundamental bahasa (seperti akses properti, pemanggilan fungsi, dan pengecekan operator `in`).

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### 1. Arsitektur Rantai Prototipe (Prototype Chain)

```text
+-------------------------+
|      instance (dog)     |
|-------------------------|
| name: "Rex"             |
| [[Prototype]] ----------+------> +-------------------------------+
+-------------------------+        |     Dog.prototype             |
                                   |-------------------------------|
                                   | bark: function()              |
                                   | constructor: Dog              |
                                   | [[Prototype]] ----------------+----+
                                   +-------------------------------+    |
                                                                        v
+-------------------------+        +-------------------------------+    |
|          null           | <------+       Object.prototype        |<---+
+-------------------------+        |-------------------------------|
                                   | toString: function()          |
                                   | hasOwnProperty: function()    |
                                   | [[Prototype]]: null           |
                                   +-------------------------------+
```

### 2. Alur Resolusi Properti (Property Lookup Resolution Flow)

```text
[Operasi: Evaluasi objek.properti]
                |
                v
  Apakah 'properti' ada pada
      objek langsung?
       (Own Property)
       /            \
     (Ya)           (Tidak)
     /                \
    v                  v
Kembalikan     Apakah [[Prototype]]
  Nilai           adalah null?
                   /         \
                 (Ya)       (Tidak)
                 /             \
                v               v
           Kembalikan       Pindah konteks ke
           undefined       objek [[Prototype]],
                            Ulangi pengecekan
```

### 3. Pipeline Intersepsi Proxy dan Reflect

```text
Runtime Operation (e.g., obj.prop = 42)
                |
                v
+-------------------------------+
|          Proxy Trap           |
|  handler.set(target, prop,    |
|              val, receiver)   |
+-------------------------------+
        |               |
   [Validation]   [Side-Effects]
        |               |
        v               v
+-------------------------------+
|          Reflect API          |
|  Reflect.set(...)             |
+-------------------------------+
                |
                v
+-------------------------------+
|      Target Object Mutation   |
+-------------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### Internal Slot `[[Prototype]]` vs Properti `.prototype`

* `[[Prototype]]`: Slot internal privat yang dimiliki oleh setiap objek JavaScript. Mengindikasikan objek mana yang dijadikan rujukan delegasi properti. Slot ini dapat diakses melalui `Object.getPrototypeOf()` / `Object.setPrototypeOf()` atau melalui accessor warisan `__proto__`.
* `.prototype`: Properti reguler yang **hanya** dimiliki oleh fungsi konstruktor (*constructor functions*) dan deklarasi `class`. Properti ini merepresentasikan objek yang akan ditetapkan sebagai `[[Prototype]]` dari instansiasi baru yang dibuat menggunakan operator `new`.

### Property Descriptors

Setiap properti dalam JavaScript dikontrol oleh atribut internal yang terbagi menjadi dua kategori:

1. **Data Descriptors:**
   * `[[Value]]`: Data aktual yang disimpan.
   * `[[Writable]]`: Boolean; jika `false`, nilai tidak dapat diubah (mutasi gagal secara senyap atau melempar `TypeError` pada *strict mode*).
   * `[[Enumerable]]`: Boolean; jika `true`, properti muncul dalam iterasi `for...in` dan `Object.keys()`.
   * `[[Configurable]]`: Boolean; jika `false`, deskriptor tidak dapat dimodifikasi (kecuali mempersempit `writable` dari `true` ke `false`), dan properti tidak dapat dihapus melalui `delete`.

2. **Accessor Descriptors:**
   * `[[Get]]`: Fungsi yang dieksekusi saat properti dibaca.
   * `[[Set]]`: Fungsi yang dieksekusi saat properti ditulis.
   * `[[Enumerable]]`: Sama seperti Data Descriptor.
   * `[[Configurable]]`: Sama seperti Data Descriptor.

### Arsitektur Engine V8: Shapes, Transition Trees, dan Inline Caches (IC)

Untuk menghindari latensi pencarian hash dinamis, engine modern seperti Google V8 mengimplementasikan optimasi C++ tingkat rendah:

* **Shape (Map / Hidden Class):** Struktur data internal C++ yang menyimpan metadata tata letak properti dan *offset* memori relatif properti dalam objek.
* **Transition Tree:** Ketika properti ditambahkan ke suatu objek, V8 tidak menyalin struktur objek tersebut melainkan memindahkan pointer *Shape* objek tersebut ke *Shape* transisi berikutnya.
* **Inline Cache (IC):** Mekanisme *caching* di mana situs panggilan (*call-site*) kode mengingat *Shape* dari objek yang pernah melewatinya. Terdapat tiga fase status IC:
  1. *Monomorphic:* Call-site hanya pernah melihat satu jenis Shape. Sangat dioptimalkan menjadi pembacaan offset memori langsung.
  2. *Polymorphic:* Call-site melihat 2 hingga 4 Shape berbeda. Memerlukan percabangan pengecekan minimal.
  3. *Megamorphic:* Call-site melihat lebih dari 4 Shape berbeda. Engine menyerah melakukan optimasi khusus dan kembali ke pencarian tabel hash lambat (*generic lookup*).

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Object Invariants dan Aturan Integritas Objek

Tiga metode integritas runtime mendasar dalam JavaScript:

* `Object.preventExtensions(obj)`: Mencegah penambahan properti baru ke objek. Properti yang ada tetap dapat dimutasi atau dihapus.
* `Object.seal(obj)`: Menjalankan `preventExtensions` dan menandai seluruh properti yang ada menjadi `configurable: false`. Nilai properti masih dapat diubah jika `writable: true`.
* `Object.freeze(obj)`: Menjalankan `seal` dan menandai seluruh data property menjadi `writable: false`. Objek menjadi *shallowly immutable*.

> **Perhatian:** Pembekuan objek via `Object.freeze()` bersifat *shallow* (hanya tingkat pertama). Objek yang bersarang (*nested objects*) di dalamnya tetap dapat dimutasi secara bebas kecuali dibekukan secara rekursif (*deep freeze*).

### 2. Proxy & Reflect: Introspeksi dan Virtualisasi Runtime

`Proxy` memungkinkan pembungkusan target objek untuk mengabstraksi dan mencegat 13 operasi internal fundamental (*traps*), yang berkorelasi 1:1 dengan metode statis pada objek `Reflect`:

| Proxy Trap | Perilaku Fundamental Tercegat | Ekivalen Reflect |
| :--- | :--- | :--- |
| `get` | Membaca properti (`obj.prop`) | `Reflect.get(target, prop, receiver)` |
| `set` | Menulis properti (`obj.prop = val`) | `Reflect.set(target, prop, val, receiver)` |
| `has` | Operator `in` (`prop in obj`) | `Reflect.has(target, prop)` |
| `deleteProperty` | Operator `delete` (`delete obj.prop`) | `Reflect.deleteProperty(target, prop)` |
| `apply` | Pemanggilan fungsi (`fn(...args)`) | `Reflect.apply(target, thisArg, args)` |
| `construct` | Operator `new` (`new Cls(...)`) | `Reflect.construct(target, args, newTarget)` |
| `ownKeys` | `Object.getOwnPropertyNames` / `Symbols` | `Reflect.ownKeys(target)` |

Argumen `receiver` pada trap `get` dan `set` sangat krusial: argumen ini memastikan bahwa referensi `this` tetap terikat secara dinamis ke Proxy (atau objek yang mewarisinya), bukan langsung terikat ke *raw target*. Melewatkan parameter `receiver` ke `Reflect.get(target, prop, receiver)` adalah fondasi dari pemeliharaan perilaku pewarisan yang benar.

### 3. Well-Known Symbols: Ekstensi Semantik Bahasa

ECMAScript mengekspos representasi internal algoritma runtime melalui *Well-Known Symbols*:

* `Symbol.iterator`: Mengontrol bagaimana objek dapat diiterasi oleh `for...of` atau spread operator (`...`).
* `Symbol.toPrimitive`: Mencegat konversi tipe implisit objek menjadi tipe data primitif (*hint*: `"number"`, `"string"`, atau `"default"`).
* `Symbol.hasInstance`: Menyesuaikan perilaku operator `instanceof`.
* `Symbol.species`: Mengontrol konstruktor turunan yang digunakan untuk membuat objek turunan pada metode bawaan (misal: `map()`, `slice()`).
* `Symbol.toStringTag`: Menentukan keluaran string saat dipanggil via `Object.prototype.toString.call(obj)`.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah demonstrasi eksplisit mengenai pembentukan delegasi prototipe murni, deskriptor properti, manipulasi rantai prototipe, serta metaprogramming via `Proxy` dan `Reflect`.

```javascript
'use strict';

// -------------------------------------------------------------
// 1. Prototypal Inheritance Manual via Object.create & Descriptors
// -------------------------------------------------------------

const EntityProto = {
  getIdentity() {
    return `ID: ${this.id}`;
  }
};

// Instansiasi objek mendelegasikan langsung ke EntityProto
const userNode = Object.create(EntityProto, {
  id: {
    value: 'USR_001',
    writable: false,
    enumerable: true,
    configurable: false
  },
  _role: {
    value: 'GUEST',
    writable: true,
    enumerable: false,
    configurable: true
  }
});

// Menambahkan Accessor Property dengan validasi logika
Object.defineProperty(userNode, 'role', {
  get() {
    return this._role;
  },
  set(newRole) {
    const validRoles = ['GUEST', 'MEMBER', 'ADMIN'];
    if (!validRoles.includes(newRole)) {
      throw new TypeError(`Invalid role assignment: ${newRole}`);
    }
    this._role = newRole;
  },
  enumerable: true,
  configurable: false
});

// -------------------------------------------------------------
// 2. Metaprogramming Interception Menggunakan Proxy & Reflect
// -------------------------------------------------------------

const schemaValidator = {
  set(target, property, value, receiver) {
    if (property === 'age') {
      if (typeof value !== 'number' || !Number.isInteger(value)) {
        throw new TypeError('Property "age" must be an integer.');
      }
      if (value < 0 || value > 150) {
        throw new RangeError('Property "age" must be between 0 and 150.');
      }
    }
    
    // Meneruskan mutasi ke target aktual menggunakan Reflect dengan context receiver yang benar
    return Reflect.set(target, property, value, receiver);
  },

  get(target, property, receiver) {
    if (property in target) {
      return Reflect.get(target, property, receiver);
    }
    // Mengembalikan fallback terstruktur untuk properti yang tidak ada
    return `[Undefined Property: ${String(property)}]`;
  }
};

const rawProfile = { name: 'Alice', age: 28 };
const monitoredProfile = new Proxy(rawProfile, schemaValidator);

// -------------------------------------------------------------
// 3. Modifikasi Semantik Menggunakan Well-Known Symbols
// -------------------------------------------------------------

const SmartCollection = {
  items: [10, 20, 30],
  
  // Custom type coercion logic
  [Symbol.toPrimitive](hint) {
    if (hint === 'number') {
      return this.items.reduce((acc, curr) => acc + curr, 0);
    }
    if (hint === 'string') {
      return `Collection[${this.items.join(', ')}]`;
    }
    return this.items.length;
  },

  // Custom iteration protocol
  *[Symbol.iterator]() {
    for (const item of this.items) {
      yield item * 2; // Mengembalikan item yang dimodifikasi saat iterasi
    }
  }
};
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

* **Baris 10–14:** `EntityProto` didefinisikan sebagai objek literal sederhana yang bertindak sebagai *prototype base*.
* **Baris 17–28:** `Object.create(EntityProto, descriptors)` menginisialisasi `userNode` dengan internal slot `[[Prototype]]` yang langsung mengarah ke `EntityProto`. Properti `id` disetel dengan `writable: false` dan `configurable: false`, menjadikannya *read-only* permanen yang tidak dapat dimodifikasi ataupun dihapus dari memori.
* **Baris 31–44:** `Object.defineProperty` menambahkan properti accessor `role`. Implementasi `_role` disembunyikan dari perulangan berbasis kunci dengan menyetel `enumerable: false`, sementara setter mengeksekusi *type checking* ketat sebelum mengizinkan mutasi.
* **Baris 50–68:** `schemaValidator` bertindak sebagai *handler* bagi `Proxy`.
  * Trap `set(target, property, value, receiver)` mencegat seluruh operasi penetapan nilai.
  * `Reflect.set(target, property, value, receiver)`: Mengembalikan *boolean* penanda keberhasilan mutasi. Penggunaan `receiver` memastikan integritas binding `this` apabila target merupakan prototipe dari objek pemanggil lain.
  * Trap `get(target, property, receiver)`: Mencegat operasi pembacaan nilai dan memberikan degradasi yang anggun (*graceful fallback*) alih-alih mengembalikan `undefined`.
* **Baris 76–90:** Penyesuaian semantik internal engine via `Symbol.toPrimitive` dan `Symbol.iterator`:
  * `Symbol.toPrimitive(hint)`: Engine secara otomatis mengirimkan argument `"number"`, `"string"`, atau `"default"` bergantung pada operasi primitif yang dipicu (contoh: `+SmartCollection` mengirimkan `"number"`).
  * Generator function `*[Symbol.iterator]()`: Menyediakan antarmuka standar untuk konsumsi oleh konstruksi sintaksis modern JavaScript (`for...of`, `[...SmartCollection]`).

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: Engine State Reactivity & ORM Change-Tracking (Enterprise Production)

Dalam arsitektur *Enterprise Frontend / Backend Data Mappers* (seperti internal mekanisme Vue 3 Reactivity Engine atau Prisma/TypeORM unit-of-work tracker), sistem harus mampu:
1. Mendeteksi mutasi data secara rekursif (*deep observation*) tanpa memaksa pengembang menggunakan setter manual seperti `model.set('prop', val)`.
2. Menghitung mutasi bersih (*delta tracking*) secara otomatis untuk meminimalkan *payload* query `UPDATE` ke basis data.
3. Mencegah mutasi ilegal pada properti *read-only* atau properti primer/kunci sistem (*identity immutability*).
4. Menjaga referensi identitas objek (*proxy identity caching*) agar pemanggilan berulang terhadap *nested object* yang sama tidak mengalokasikan instansiasi Proxy baru, yang dapat memicu *memory leak* dan kegagalan komparasi referensi kesetaraan (`===`).

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi sistem *Deep Reactive Unit-of-Work & Dirty-Checking Engine*:

```javascript
'use strict';

/**
 * Enterprise Change-Tracking Engine via Recursive Virtual Proxy
 */
class ChangeTracker {
  static #rawToProxy = new WeakMap();
  static #proxyToRaw = new WeakMap();
  
  #target;
  #dirtyState = new Map();
  #isSealed = false;

  constructor(initialData = {}) {
    this.#target = initialData;
    this.proxy = this.#createProxy(this.#target);
  }

  #createProxy(obj) {
    if (obj === null || typeof obj !== 'object') {
      return obj;
    }

    // Hindari alokasi ganda: kembalikan proxy yang telah dipetakan jika ada
    if (ChangeTracker.#rawToProxy.has(obj)) {
      return ChangeTracker.#rawToProxy.get(obj);
    }

    // Jika objek sudah berupa Proxy, kembalikan objek tersebut
    if (ChangeTracker.#proxyToRaw.has(obj)) {
      return obj;
    }

    const handler = {
      get: (target, prop, receiver) => {
        // Introspeksi internal engine: bypass unwrap
        if (prop === '__isProxy') return true;
        if (prop === '__rawTarget') return target;

        const value = Reflect.get(target, prop, receiver);

        // Rekursif membungkus properti bertipe objek (Lazy Evaluation)
        if (value !== null && typeof value === 'object') {
          return this.#createProxy(value);
        }

        return value;
      },

      set: (target, prop, value, receiver) => {
        if (this.#isSealed) {
          throw new Error('Transaction is sealed. Commits are final.');
        }

        const oldValue = Reflect.get(target, prop, receiver);

        // Normalisasi unwrap jika value yang dimasukkan adalah sebuah proxy
        const actualValue = ChangeTracker.#proxyToRaw.get(value) || value;

        if (oldValue !== actualValue) {
          // Rekam mutasi jika belum tercatat di dirtyState Map
          const targetDelta = this.#dirtyState.get(target) || new Map();
          if (!targetDelta.has(prop)) {
            targetDelta.set(prop, { original: oldValue, current: actualValue });
            this.#dirtyState.set(target, targetDelta);
          } else {
            // Update current value pada mutasi berikutnya
            targetDelta.get(prop).current = actualValue;
          }
        }

        return Reflect.set(target, prop, actualValue, receiver);
      },

      deleteProperty: (target, prop) => {
        if (this.#isSealed) {
          throw new Error('Transaction is sealed. Mutating schema is disallowed.');
        }

        if (Reflect.has(target, prop)) {
          const oldValue = Reflect.get(target, prop);
          const targetDelta = this.#dirtyState.get(target) || new Map();
          targetDelta.set(prop, { original: oldValue, current: undefined, deleted: true });
          this.#dirtyState.set(target, targetDelta);
        }

        return Reflect.deleteProperty(target, prop);
      }
    };

    const proxy = new Proxy(obj, handler);
    ChangeTracker.#rawToProxy.set(obj, proxy);
    ChangeTracker.#proxyToRaw.set(proxy, obj);
    return proxy;
  }

  isDirty() {
    return this.#dirtyState.size > 0;
  }

  getChanges() {
    const changes = [];
    for (const [target, deltaMap] of this.#dirtyState.entries()) {
      for (const [prop, delta] of deltaMap.entries()) {
        changes.push({
          target,
          property: prop,
          from: delta.original,
          to: delta.current,
          isDeleted: delta.deleted || false
        });
      }
    }
    return changes;
  }

  commit() {
    this.#isSealed = true;
    this.#dirtyState.clear();
    Object.freeze(this.#target);
  }
}

// -------------------------------------------------------------
// Verifikasi Pengujian Sistem
// -------------------------------------------------------------

const entityData = {
  id: 1001,
  metadata: {
    version: '1.0.0',
    tags: ['production', 'financial']
  },
  payload: {
    amount: 5000000
  }
};

const tracker = new ChangeTracker(entityData);
const tracked = tracker.proxy;

// Verifikasi Identity Caching
console.assert(tracked.metadata === tracked.metadata, 'Identity cache lookup validation');

// Mutasi Properti Bersarang
tracked.metadata.version = '1.0.1';
tracked.payload.amount = 7500000;
delete tracked.metadata.tags;

console.log('Is Dirty:', tracker.isDirty()); // true
console.log('Delta Changes Matrix:', JSON.stringify(tracker.getChanges(), null, 2));

tracker.commit();

try {
  // Upaya mutasi pasca commit harus diblokir oleh integritas transaksi
  tracked.payload.amount = 9999999;
} catch (error) {
  console.log('Security Constraint Enforced:', error.message);
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Karakteristik | `Object.defineProperty` (ES5) | `Proxy` & `Reflect` (ES6) | Pure Prototypal (`Object.create`) |
| :--- | :--- | :--- | :--- |
| **Cakupan Intersepsi** | Terbatas pada mutasi/pembacaan properti yang didefinisikan sebelumnya. | Universal (mencegat penambahan kunci baru, penghapusan, iterasi, pemanggilan). | Pasif; tidak memiliki mekanisme *trapping* eksekusi. |
| **Overhead Kinerja** | Rendah. JIT dapat mengompilasi deskriptor menjadi kode mesin yang stabil. | Moderat hingga Tinggi. Memicu pembatalan optimasi JIT jika *traps* dinamis dieksekusi secara intensif. | Sangat Rendah. Menggunakan optimasi rantai lookup prototipe native engine. |
| **Dukungan Array Tracking**| Lemah. Tidak dapat mendeteksi mutasi berbasis mutasi index langsung atau perubahan `length`. | Sempurna. Mengabstraksi dan mencegat mutasi index maupun metode mutator (`push`, `pop`). | Tidak relevan (bukan peruntukan observasi). |
| **Kompatibilitas Runtime** | Penuh (Internet Explorer 9+). | Node.js 6+, Modern Browser (Tidak dapat di-*polyfill* dengan sempurna menggunakan Babel). | Penuh (ES5+). |
| **Memori Consumption** | Konstan per properti descriptor yang dialokasikan. | Membutuhkan alokasi *handler*, *traps closures*, dan pemetaan tracking (*WeakMap*). | Minimal. Hanya penunjuk memori tunggal (`[[Prototype]]`). |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Invariant Violations pada Proxy
Spesifikasi ECMAScript melarang keras `Proxy` melanggar integritas invarian target objek. Jika sebuah properti pada target didefinisikan sebagai `configurable: false` dan `writable: false`, trap `get` dari Proxy **wajib** mengembalikan nilai yang identik dengan nilai pada target aktual.

```javascript
const target = {};
Object.defineProperty(target, 'fixedValue', {
  value: 42,
  writable: false,
  configurable: false
});

const invalidProxy = new Proxy(target, {
  get() {
    return 99; // Melanggar Invariant!
  }
});

// TypeError: 'get' on proxy: property 'fixedValue' is a read-only and
// non-configurable data property on the proxy target but the proxy did not return
// the same value (got '99', expected '42')
// console.log(invalidProxy.fixedValue);
```

### 2. Kehilangan Akses Private Identifier (`#field`) via Proxy
Metode privat JavaScript native (`#privateField`) terikat secara leksikal ke instansi C++ internal objek target. Saat metode yang mengakses `#field` dieksekusi melalui sebuah Proxy, `this` menunjuk ke instansi Proxy, bukan target asli. Engine mendeteksi ketiadaan *private brand* pada Proxy tersebut dan melempar `TypeError`.

```javascript
class BankAccount {
  #balance = 1000;

  getBalance() {
    return this.#balance;
  }
}

const account = new BankAccount();
const accountProxy = new Proxy(account, {});

// Melempar: TypeError: Cannot read private member #balance from an object whose class did not declare it
// accountProxy.getBalance(); 

// Solusi: Lakukan binding eksekusi get secara manual ke target atau binding method:
const fixedProxy = new Proxy(account, {
  get(target, prop, receiver) {
    const value = Reflect.get(target, prop, receiver);
    return typeof value === 'function' ? value.bind(target) : value;
  }
});
console.log(fixedProxy.getBalance()); // 1000 (Berhasil)
```

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Manipulasi Dinamis Rantai Prototipe via `Object.setPrototypeOf`
Mengubah rantai prototipe objek yang telah berjalan (*in-flight*) menggunakan `Object.setPrototypeOf` atau `obj.__proto__ = ...` adalah anti-pattern performa paling parah dalam JavaScript.

* **Penyebab:** Tindakan ini langsung menghancurkan seluruh pohon transisi (*Hidden Classes*) dan Inline Caches yang telah dikompilasi oleh JIT engine untuk objek tersebut dan seluruh objek yang mewarisinya.
* **Solusi:** Buat selalu objek sejak awal dengan prototipe yang ditargetkan secara deklaratif menggunakan `Object.create(desiredProto)`.

### 2. Lupa Mengembalikan Nilai Boolean pada Trap `set`
Spesifikasi ECMAScript mewajibkan trap `set` pada Proxy untuk mengembalikan `true` jika mutasi berhasil, dan `false` jika gagal.

```javascript
// KESALAHAN FATAL
const brokenProxy = new Proxy({}, {
  set(target, prop, val) {
    target[prop] = val;
    // Lupa return true
  }
});

'use strict';
// brokenProxy.data = 'test'; 
// Melempar TypeError: 'set' on proxy: trap returned falsish for property 'data'

// PERBAIKAN BENAR
const robustProxy = new Proxy({}, {
  set(target, prop, val, receiver) {
    return Reflect.set(target, prop, val, receiver); // Mengembalikan boolean secara eksplisit
  }
});
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Selalu Teruskan Receiver ke API Reflect:** Ketika mengimplementasikan Proxy traps `get` dan `set`, jangan pernah memanggil pembacaan/penulisan langsung pada `target[prop]`. Selalu gunakan `Reflect.get(target, prop, receiver)` dan `Reflect.set(target, prop, value, receiver)` untuk menjaga resolusi akses polimorfik.
2. **Gunakan WeakMap untuk Identitas Objek Terisolasi:** Gunakan `WeakMap` untuk mengaitkan metadata privat atau caching pada objek/proxy tanpa mencegah pembersihan *garbage collection* (*memory leak prevention*).
3. **Pemberian Prefiks Symbol untuk Metadata Tersembunyi:** Jangan pernah menambahkan properti metadata ke objek pihak ketiga menggunakan *string keys*. Gunakan `Symbol('custom.meta')` untuk menjamin tidak akan terjadi benturan nama (*name collision*).
4. **Isolasi Mutasi Prototype Bawaan:** Hindari memodifikasi `Object.prototype`, `Array.prototype`, atau tipe global lainnya (*monkey patching*). Mutasi global merusak determinisme dependensi pihak ketiga dan menghentikan optimasi kompilator V8.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Mempertahankan Monomorphic Shapes pada V8

V8 melacak tata letak objek berdasarkan urutan inisialisasi propertinya. Inisialisasi properti yang tidak konsisten membagi Hidden Class menjadi jalur polimorfik yang memperlambat laju eksekusi loop secara signifikan.

```javascript
// BURUK: Memecah Shapes menjadi 2 transisi berbeda (Polymorphic)
function createPointBad(x, y) {
  const pt = {};
  if (x > 0) {
    pt.x = x;
    pt.y = y;
  } else {
    pt.y = y; // Urutan dibalik!
    pt.x = x;
  }
  return pt;
}

// OPTIMAL: Struktur seragam menghasilkan Shape yang sama (Monomorphic)
function createPointGood(x, y) {
  return {
    x: x,
    y: y
  };
}
```

### 2. Hindari Penggunaan Operator `delete` pada Objek dengan Trafik Tinggi
Eksekusi operator `delete obj.prop` mengubah representasi V8 Shape dari *Fast Properties* (penyimpanan array C++ terstruktur) langsung menjadi *Slow Dictionary Properties* (tabel hash terfragmentasi).

* **Solusi Performa:** Tetapkan nilai properti tersebut ke `undefined` atau `null` daripada menghapus kuncinya secara fisik jika objek tersebut digunakan secara berulang dalam jalur kritis (*hot-path*).

---

## SEKSI 16 — KEAMANAN & HARDENING

### Ancaman: Prototype Pollution

*Prototype Pollution* terjadi ketika input yang dikontrol oleh penyerang (seperti parsing JSON yang tidak divalidasi dengan kunci recursive `__proto__` atau `constructor.prototype`) menyuntikkan properti berbahaya secara global ke `Object.prototype`. Hal ini dapat menyebabkan *Denial of Service* (DoS), pembajakan alur logika aplikasi, hingga *Remote Code Execution* (RCE).

### Strategi Pertahanan Lapis Baja (Defense-in-Depth)

```javascript
'use strict';

// 1. Objek Kamus Nir-Prototipe (Dictionary Object tanpa pewarisan)
const secureStorage = Object.create(null);
// secureStorage.__proto__ sekarang hanyalah properti string biasa, 
// tidak ada prototipe yang dapat disusupi.

// 2. Pembekuan Prototipe Global Inti saat Bootstrap Aplikasi
function freezeGlobalPrototypes() {
  Object.freeze(Object.prototype);
  Object.freeze(Array.prototype);
  Object.freeze(Function.prototype);
}

// 3. Sanitizer Rekursif Aman terhadap Kerentanan Polusi
function safeMerge(target, source) {
  for (const key of Object.keys(source)) {
    // Blokir akses langsung ke vektor injeksi prototipe
    if (key === '__proto__' || key === 'constructor' || key === 'prototype') {
      continue;
    }

    if (
      source[key] &&
      typeof source[key] === 'object' &&
      !Array.isArray(source[key])
    ) {
      if (!target[key]) target[key] = {};
      safeMerge(target[key], source[key]);
    } else {
      target[key] = source[key];
    }
  }
  return target;
}
```

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Debugging proxy dan rantai prototipe memerlukan alat bantu khusus karena `console.log()` sering kali menyembunyikan lapisan abstraksi atau memicu eksekusi trap `get` secara tidak sengaja (*side-effect execution*).

### Pemeriksaan Jejak Prototipe dan State Proxy Secara Programatik

```javascript
function inspectObjectSystem(target) {
  console.group('--- OBJECT INTROSPECTION TRACE ---');
  
  // 1. Dapatkan Rantai Prototipe Menyeluruh
  const prototypeChain = [];
  let curr = target;
  while (curr !== null) {
    prototypeChain.push(curr.constructor ? curr.constructor.name : '[Null Prototype]');
    curr = Object.getPrototypeOf(curr);
  }
  console.log('Prototype Chain Delegation:', prototypeChain.join(' -> '));

  // 2. Dapatkan Seluruh Descriptors (termasuk non-enumerable & symbols)
  const ownKeys = Reflect.ownKeys(target);
  console.log(`Total Direct Properties: ${ownKeys.length}`);
  
  for (const key of ownKeys) {
    const desc = Object.getOwnPropertyDescriptor(target, key);
    const type = desc.get || desc.set ? 'Accessor' : 'Data';
    console.log(` - Key: [${String(key)}] | Type: ${type} | Configurable: ${desc.configurable} | Enumerable: ${desc.enumerable}`);
  }

  // 3. Deteksi Integritas
  console.log('Is Extensible:', Object.isExtensible(target));
  console.log('Is Sealed:', Object.isSealed(target));
  console.log('Is Frozen:', Object.isFrozen(target));
  
  console.groupEnd();
}
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

* `obj.__proto__`: Antarmuka warisan lawas; gunakan selalu `Object.getPrototypeOf(obj)` atau `Object.setPrototypeOf(obj, proto)`.
* `Object.create(proto, descriptors)`: Menginstansiasi objek baru secara murni dengan mengaitkan internal slot `[[Prototype]]` ke `proto` tanpa memanggil constructor.
* `Object.freeze()`: Menjadikan properti objek *read-only* dan *non-configurable* (secara *shallow*).
* `Proxy(target, handler)`: Membungkus objek untuk mencegat dan mengubah perilaku semantik internal JavaScript.
* `Reflect.*`: Menyediakan metode fungsional terstandardisasi untuk mengeksekusi operasi objek default; selalu pasangkan dengan traps Proxy terkait.
* `Symbol.iterator`: Protokol iterasi untuk sintaksis `for...of` dan destructuring.
* `Symbol.toPrimitive`: Mengambil alih konversi tipe eksplisit/implisit (*type casting*).
* V8 Shape Transitions: Pertahankan keteraturan penambahan properti konstruksi untuk memaksimalkan *Monomorphic Inline Caches*.
* `Object.create(null)`: Menghasilkan objek absolut tanpa rantai prototipe; standar industri untuk penyimpanan kamus yang kebal terhadap *Prototype Pollution*.

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Bagian A: Pilihan Ganda (Tingkat Dasar)

1. **Apa perbedaan struktural utama antara `Object.seal()` dan `Object.freeze()`?**
   * A. `Object.seal()` mencegah penambahan properti baru, sedangkan `Object.freeze()` tidak.
   * B. `Object.freeze()` menyetel seluruh properti menjadi `writable: false`, sedangkan `Object.seal()` tetap memperbolehkan mutasi nilai properti yang berstatus `writable: true`.
   * C. `Object.seal()` menghapus internal slot `[[Prototype]]`.
   * D. `Object.freeze()` bekerja secara rekursif hingga *nested objects*, sedangkan `Object.seal()` tidak.
   * *Jawaban yang Benar:* **B**

2. **Diberikan kode `const a = Object.create(null);`. Pernyataan manakah yang benar mengenai objek `a`?**
   * A. `a.toString()` akan mengembalikan string `"[object Object]"`.
   * B. `a` memiliki properti bawaan `hasOwnProperty`.
   * C. `Object.getPrototypeOf(a)` akan mengembalikan `null`.
   * D. `a` melempar *SyntaxError* saat ditambahkan properti baru.
   * *Jawaban yang Benar:* **C**

3. **Kapan sebaiknya argumen `receiver` diteruskan ke `Reflect.get(target, prop, receiver)` di dalam Proxy trap?**
   * A. Hanya jika target objek bertipe Array.
   * B. Selalu, agar nilai `this` pada getter yang didelegasikan terikat dengan benar ke pemanggil terluar (Proxy).
   * C. Tidak pernah, karena `receiver` memicu *memory leak* pada garbage collector.
   * D. Hanya saat menggunakan *strict mode*.
   * *Jawaban yang Benar:* **B**

4. **Operasi mana yang TIDAK DAPAT dicegat oleh Proxy handler trap?**
   * A. Evaluasi operator `in` (`prop in obj`).
   * B. Pengecekan kesetaraan identitas referensi strictly equal (`proxy === target`).
   * C. Penghapusan properti via `delete obj.prop`.
   * D. Pemanggilan fungsi instansiasi `new MyClass()`.
   * *Jawaban yang Benar:* **B**

5. **Apa konsekuensi performa pada engine V8 jika kita menggunakan operator `delete` secara berulang pada properti objek?**
   * A. Mempercepat eksekusi memori karena alokasi segera dibersihkan.
   * B. Mengubah representasi internal objek dari Fast Mode (Shape Struct) menjadi Slow Mode (Dictionary).
   * C. Memaksa engine V8 melakukan kompilasi ulang kode secara instan menjadi WebAssembly.
   * D. Mengunci seluruh proses eksekusi thread JavaScript (Event Loop blocking).
   * *Jawaban yang Benar:* **B**

---

### Bagian B: Analisis Masalah Kode (Tingkat Lanjut)

6. **Perhatikan kode berikut. Apa output eksekusinya dan jelaskan mengapa error tersebut terjadi?**
   ```javascript
   const proto = {
     get count() { return this._count; }
   };
   const obj = Object.create(proto);
   obj._count = 10;
   
   const proxy = new Proxy(obj, {
     get(target, prop) {
       return Reflect.get(target, prop); // Receiver diabaikan
     }
   });
   
   const subObj = Object.create(proxy);
   subObj._count = 99;
   console.log(subObj.count);
   ```
   * *Solusi & Analisis:* Outputnya adalah **10**, bukan 99. Mengabaikan argumen `receiver` pada `Reflect.get(target, prop)` memutuskan rantai pengikatan konteks dinamis. Nilai `this` di dalam getter `count` terikat ke `target` asli (`obj`) alih-alih terikat ke pemanggil hakiki yang mewarisinya (`subObj`). Jika diperbaiki menjadi `Reflect.get(target, prop, receiver)`, outputnya benar: **99**.

7. **Bagaimana cara mendeteksi apakah suatu properti merupakan *own property* tanpa memicu pemanggilan getter atau rentan terhadap penimpaan properti lokal `hasOwnProperty`?**
   * *Solusi & Analisis:* Menggunakan metode ECMAScript 2022 terstandarisasi: `Object.hasOwn(obj, 'propName')`, atau secara defensif menggunakan `Object.prototype.hasOwnProperty.call(obj, 'propName')`.

8. **Analisis anomali pada kode berikut: Mengapa `Reflect.ownKeys` menampilkan hasil yang berbeda dibanding `Object.keys`?**
   ```javascript
   const sym = Symbol('secret');
   const entity = {};
   Object.defineProperty(entity, 'visible', { value: 1, enumerable: true });
   Object.defineProperty(entity, 'hidden', { value: 2, enumerable: false });
   entity[sym] = 3;
   
   console.log(Object.keys(entity)); // ['visible']
   console.log(Reflect.ownKeys(entity)); // ['visible', 'hidden', Symbol(secret)]
   ```
   * *Solusi & Analisis:* `Object.keys()` hanya mengembalikan representasi string keys yang berstatus `enumerable: true`. Sedangkan `Reflect.ownKeys()` setara dengan gabungan deterministik dari `Object.getOwnPropertyNames(target)` dan `Object.getOwnPropertySymbols(target)`, yang mengembalikan seluruh kunci (*string* maupun *symbol*), terlepas dari nilai konfigurasi flag `enumerable`.

9. **Mengapa modifikasi `obj.__proto__` secara runtime lebih merusak performa kompilasi JIT dibandingkan membangun relasi menggunakan `Object.create`?**
   * *Solusi & Analisis:* Kompilator JIT (seperti V8 TurboFan) memvalidasi keabsahan prediksi Inline Caches (IC) berdasarkan kestabilan struktur *Prototype Chain*. Memutasi prototipe objek secara dinamis membatalkan validitas (*de-optimizes*) seluruh kode terkompilasi yang bergantung pada struktur pohon transisi prototipe objek tersebut, memaksa engine beralih ke interpretasi bailout lambat (*deopt loop*).

10. **Tinjau kerentanan pada fungsi shallow/deep merge berikut: bagaimana sebuah payload JSON berbahaya dapat memicu *Prototype Pollution*?**
    ```javascript
    function insecureMerge(target, source) {
      for (let k in source) {
        if (typeof source[k] === 'object') {
          if (!target[k]) target[k] = {};
          insecureMerge(target[k], source[k]);
        } else {
          target[k] = source[k];
        }
      }
    }
    ```
    * *Solusi & Analisis:* Jika payload input JSON mengandung properti `{"__proto__": {"isAdmin": true}}`, loop rekursif akan mengevaluasi `target["__proto__"]`. Dalam JavaScript reguler, mengakses kunci `__proto__` pada objek standar akan merujuk langsung ke `Object.prototype`. Penugasan nilai selanjutnya secara otomatis menyuntikkan properti `isAdmin: true` ke basis prototipe global seluruh objek JavaScript di dalam runtime eksekusi.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Proyek Praktikum
**Membangun "TypeShield": Secure Runtime-Enforced Schema & Immutable Snapshot Library**

### Spesifikasi Kebutuhan Teknis

Anda ditantang untuk membangun sebuah library mandiri bernama `TypeShield` dengan arsitektur berbasis Prototypal System dan Metaprogramming murni (tanpa dependensi eksternal / *zero-dependencies*):

1. **Schema Definition Builder via Prototypes:**
   * Buat modul definisi skema yang mendukung tipe data: `String`, `Number`, `Boolean`, dan skema bersarang (*nested schema*).
   * Gunakan pewarisan prototipe untuk membangun rantai validasi modular (contoh: `TypeShield.String().minLength(5).notNull()`).

2. **Secure Proxy-Based Data Wrapper:**
   * Bungkus setiap objek data yang didaftarkan ke dalam skema menggunakan `Proxy`.
   * Trap `set`: Harus memvalidasi tipe data secara ketat sesuai skema saat runtime. Melempar `TypeError` jika kontrak skema dilanggar.
   * Cegah kerentanan *Prototype Pollution*: Larang penulisan atau akses terhadap properti `__proto__`, `constructor`, atau modifikasi terhadap slot delegasi.

3. **Time-Traveling & Immutable Snapshot Mechanism:**
   * Implementasikan metode metaprogramming `.snapshot()` yang menghasilkan salinan objek yang sepenuhnya dibekukan secara rekursif (*Deep Freeze*).
   * Implementasikan antarmuka iterasi kustom pada objek snapshot menggunakan `Symbol.iterator`, sehingga snapshot dapat diiterasi langsung menghasilkan tuple pasangan `[key, value]`.
   * Modifikasi konversi primitif via `Symbol.toPrimitive`: Jika objek dikonversi ke *string*, kembalikan ringkasan hash/schema audit JSON; jika dikonversi ke *number*, kembalikan *timestamp epoch* saat snapshot diciptakan.

### Batasan Arsitektur
* Wajib menggunakan *Strict Mode* (`'use strict'`).
* Hindari penurunan performa: Semua representasi properti internal harus memelihara *shape consistency* untuk menjaga V8 Inline Caches tetap monomorphic.
* Gunakan `WeakMap` untuk penyimpanan internal instansiasi proxy dan skema audit terisolasi guna menghindari kebocoran memori (*memory leak*).