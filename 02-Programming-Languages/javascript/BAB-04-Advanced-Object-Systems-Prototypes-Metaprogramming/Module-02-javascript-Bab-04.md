# Kurikulum Rekayasa Perangkat Lunak Enterprise: JavaScript Core Engine & Metaprogramming
## Bab 04: Advanced Object Systems, Prototypes & Metaprogramming
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan memiliki kompetensi tingkat *Principal/Staff Engineer* untuk:

*   **Menganalisis Internal Engine V8**: Mengidentifikasi representasi memori objek, *Hidden Classes* (*Shapes/Maps*), *Shape Transition Trees*, serta transisi *Inline Caching* (*Monomorphic*, *Polymorphic*, *Megamorphic*) menggunakan *V8 engine flags* dan *runtime builtins*.
*   **Mengoptimalkan Layout Objek**: Mencegah de-optimasi JIT (*Just-In-Time Compiler*) dengan merancang struktur objek deterministik (*In-Object Properties* vs. *Overflow Backing Stores*, penanganan *Elements/Fast vs. Slow Dictionaries*).
*   **Membangun Arsitektur Metaprogramming Skala Enterprise**: Mengimplementasikan *virtualization layers* menggunakan `Proxy` dan `Reflect` yang mematuhi *ECMA-262 Trapping Invariants*, aman terhadap kebocoran referensi, dan minim *overhead* latensi.
*   **Mitigasi Ancaman Sistem Objek**: Mencegah kerentanan *Prototype Pollution* pada layer *deserialization* dan *deep merge* menggunakan strategi *Hermetic Dictionaries* (`Object.create(null)`), `Object.freeze()`, dan *AST-level schema validations*.
*   **Manajemen Daur Hidup Memori Lanjutan**: Mengimplementasikan arsitektur *cache* non-bocor (*leak-free*) dan pelacakan *resource external* menggunakan `WeakMap`, `WeakSet`, `WeakRef`, dan `FinalizationRegistry`.

---

### 2. Prerequisites

Sebelum mempelajari modul ini, Anda wajib menguasai:
*   **JavaScript Execution Context**: *Call Stack*, *Heap*, *Microtask Queue*, dan *Event Loop*.
*   **Fundamental Prototypes**: `Object.prototype`, *chain lookup*, `__proto__`, dan delegasi prototipikal dasar.
*   **ES6+ Core Features**: Destrukturisasi, `Symbol` dasar, `Map`/`Set`, serta sintaksis `class`.
*   **Sistem Kompilasi JIT Dasar**: Konsep dasar *Ignition* (interpreter V8) dan *TurboFan* (optimizing compiler V8).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1. Anatomi Memori Objek V8 (V8 Object Layout)
Di dalam V8 (engine yang menggerakkan Node.js dan Chromium), sebuah objek JavaScript (`JSObject`) bukan representasi *hash map* sederhana di dalam memori C++. Objek dialokasikan di dalam V8 Heap dengan tata letak (*layout*) berstruktur:

```
+-------------------------------------------------+
|                   JSObject                      |
+-------------------------------------------------+
|  1. Map / Shape Pointer (Offset 0)              | ---> Mengarah ke Hidden Class (Shape)
|  2. Properties Pointer                          | ---> Mengarah ke PropertyArray (Overflow)
|  3. Elements Pointer                            | ---> Mengarah ke FixedArray (Indexed props)
|  4. In-Object Property 0 (Offset 16/24)         | ---> Fast direct access
|  5. In-Object Property 1 (Offset 20/28)         | ---> Fast direct access
+-------------------------------------------------+
```

1.  **Map (Hidden Class / Shape)**: Menentukan deskriptor struktural objek (offset tiap *property*, konfigurasi bit *writable/enumerable/configurable*).
2.  **In-Object Properties**: Properti yang langsung dialokasikan berdampingan dengan *header* `JSObject`. Akses ke *In-Object Properties* adalah yang tercepat karena hanya membutuhkan dereferensi *offset base pointer*.
3.  **PropertyArray (Slow/Normal Properties)**: Jika jumlah properti melebihi kapasitas *In-Object* yang dihitung V8 saat instansiasi, sisa properti disimpan dalam *array pointer* sekunder.
4.  **Elements (FixedArray)**: Properti berbasis indeks numerik (`obj[0]`, `obj[1]`) disimpan terpisah dari properti bernama (*named properties*) untuk optimasi akses *array-like*.

#### 3.2. Hidden Classes & Shape Transition Tree
JavaScript adalah bahasa dinamis tanpa deklarasi *class* statis di tingkat memori biner. Untuk mencapai performa mendekati C++, V8 menciptakan abstraksi *Hidden Classes* (secara internal disebut **Map**).

Setiap kali properti baru ditambahkan ke dalam objek, V8 tidak memodifikasi Map yang sudah ada secara *in-place*, melainkan melakukan **Shape Transition**:

```
        [Map 0: Empty Object]
                 |
          tambah 'id'
                 v
        [Map 1: { id @ offset 0 }]
                 |
         tambah 'status'
                 v
        [Map 2: { id @ offset 0, status @ offset 1 }]
```

Jika dua objek diinisialisasi dengan urutan properti yang berbeda:
```javascript
const a = {}; a.x = 1; a.y = 2; // Map 0 -> Map 1(x) -> Map 2(x, y)
const b = {}; b.y = 2; b.x = 1; // Map 0 -> Map 3(y) -> Map 4(y, x)
```
Objek `a` dan `b` memiliki properti yang identik secara logis, namun memiliki **Map yang berbeda**. Hal ini memicu percabangan pohon transisi dan menghancurkan optimasi *Inline Cache*.

#### 3.3. Mekanisme Inline Caching (IC)
Ketika fungsi mengakses properti (misal: `return user.id`), V8 menggunakan *Inline Cache* (IC) untuk mengingat lokasi memori properti tersebut. Terdapat tiga fase IC:

1.  **Monomorphic**: Pemanggilan fungsi hanya pernah melihat **satu** Map. TurboFan menghasilkan instruksi mesin langsung: ambil data dari `offset 0` tanpa *lookup*. Kecepatan: setara instruksi *assembly direct load*.
2.  **Polymorphic**: Fungsi melihat hingga **4** Map yang berbeda. Engine melakukan *conditional check* (misal: `if (map == MapA) load offset 0; else if (map == MapB) load offset 1;`).
3.  **Megamorphic**: Fungsi melihat **lebih dari 4** Map yang berbeda. JIT menyerah melakukan optimasi lokal; pemanggilan dialihkan ke *global lookup table* / *dictionary search*. Penurunan performa hingga orde 10x-50x.

#### 3.4. Proxy Virtualization & Invariant Enforcement
`Proxy` (ECMAScript 2015) menyediakan mekanisme *metaprogramming* untuk mencegat (*trap*) 13 operasi fundamental mesin JavaScript (seperti `get`, `set`, `has`, `deleteProperty`, `apply`, `construct`).

Namun, implementasi V8 memaksakan **Proxy Trapping Invariants** demi integritas memori:
*   Jika properti target non-configurable dan non-writable, trap `get` **wajib** mengembalikan nilai yang identik dengan nilai target aslinya.
*   Jika properti target non-configurable, trap `deleteProperty` tidak boleh mengembalikan `true`.
*   Jika target di-*freeze* melalui `Object.freeze()`, trap `isExtensible` **wajib** mengembalikan `false`.

Pelanggaran terhadap *invariant* ini menghasilkan `TypeError` fatal di tingkat runtime, mencegah *Proxy* merusak konsistensi internal engine.

---

### 4. Why & What

| Dimensi | Pendekatan Naif (Ad-hoc) | Pendekatan Enterprise (Engine-Aware & Metaprogramming) |
| :--- | :--- | :--- |
| **Inisialisasi Properti** | Properti ditambahkan secara dinamis sesuai alur eksekusi `if/else`. | Semua properti dideklarasikan di konstruktor dengan urutan identik (*Monomorphic Shapes*). |
| **Penyimpanan Dictionary** | Menggunakan objek `{}` polos sebagai *hash map* / *lookup table*. | Menggunakan `Map` native atau `Object.create(null)` untuk mengeliminasi bahaya *Prototype Pollution*. |
| **Validasi & Intersepsi** | Pengecekan manual di setiap fungsi bisnis atau mutasi properti. | Arsitektur `Proxy` + `Reflect` transparan dengan penjagaan *invariants* dan *low-overhead design*. |
| **Manajemen State Siklus Hidup**| Menyimpan referensi objek langsung di memori; rentan *memory leak*. | Penggunaan `WeakMap` untuk metadata terisolasi dan `WeakRef`/`FinalizationRegistry` untuk *cleanup* deterministik. |
| **Mutasi Objek** | Mutasi prototipe dinamis (`Object.setPrototypeOf()`). | Menggunakan *Composition* atau *Object Creation Pipeline* statis; menghindari de-optimasi V8 total. |

---

### 5. How (Workflow Detail)

Untuk merancang arsitektur sistem objek berkinerja tinggi dan aman di tingkat produksi, implementasikan alur kerja 4 tahap berikut:

```
+---------------------------------------------------------------------------------------+
| FASE 1: DETERMINISTIC INSTANTIATION                                                   |
| - Tentukan skema kelas secara rigid.                                                  |
| - Inisialisasi seluruh field pada constructor (gunakan null/undefined jika kosong).  |
| - Hindari operator 'delete' (gunakan penugasan sentinel value, e.g., null).          |
+---------------------------------------------------------------------------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
| FASE 2: MONOMORPHIC CALL SITES ENFORCEMENT                                            |
| - Pastikan fungsi/metode hanya menerima objek dengan Shape seragam.                   |
| - Jaga Inline Cache (IC) pada level Monomorphic untuk hot paths.                     |
+---------------------------------------------------------------------------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
| FASE 3: SECURE METAPROGRAMMING WRAPPER                                                |
| - Terapkan Proxy untuk Cross-Cutting Concerns (Audit, Telemetry, Invalidation).       |
| - Gunakan Reflect API untuk menjamin delegasi operasi default yang sempurna.          |
| - Gunakan Revocable Proxy jika lifecycle objek bersifat transient/restricted.        |
+---------------------------------------------------------------------------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
| FASE 4: MEMORY LEAK PROOFING                                                          |
| - Simpan private state & metadata di WeakMap.                                         |
| - Terapkan FinalizationRegistry untuk unregister native handlers / buffer release.    |
+---------------------------------------------------------------------------------------+
```

---

### 6. Analogy & Diagram ASCII

#### 6.1. Analogi Hidden Classes dan Inline Cache
Bayangkan sebuah kantor pos (CPU/JIT Engine) yang memproses formulir pajak (Objek):
*   **Monomorphic**: Semua formulir menggunakan format standar Versi 1.0. Petugas hafal buta bahwa kolom tanda tangan selalu berada di koordinat (X: 10cm, Y: 25cm). Petugas membubuhkan cap tanpa melihat isi formulir.
*   **Polymorphic**: Terdapat 3 variasi formulir (Perorangan, Badan Usaha, Asing). Petugas memeriksa label atas: jika Versi A, cap di (10, 25); jika Versi B, cap di (15, 30). Masih relatif cepat.
*   **Megamorphic**: Setiap warga membuat format formulir sendiri secara dinamis. Petugas harus membaca kata per kata dari atas ke bawah untuk menemukan di mana letak kolom tanda tangan. Kecepatan pemrosesan ambruk drastis.

#### 6.2. Diagram V8 Shape Transitions vs. Inline Cache Check

```
[Inisialisasi Objek: const u = new User()]
      |
      v
+-------------+         Transisi Properti 'name'        +-------------+
|   Shape 0   |  ------------------------------------>  |   Shape 1   |
| (Offset: -) |                                         | name: @off0 |
+-------------+                                         +-------------+
                                                               |
                                                     Transisi properti 'role'
                                                               v
                                                        +-------------+
                                                        |   Shape 2   |
                                                        | role: @off1 |
                                                        +-------------+

================================================================================
INLINE CACHE (IC) ACCESS LOGIC: fn(user) => user.role
================================================================================

                           [Call Site: user.role]
                                     |
                                     v
                        +--------------------------+
                        | Current Shape == Shape 2 |
                        +--------------------------+
                               /            \
                       (TRUE) /              \ (FALSE)
                             v                v
                 [FAST PATH: Monomorphic]   [SLOW PATH: IC Miss]
                 Akses langsung Memory      Periksa Feedback Vector:
                 Offset Index 1 (TurboFan)  - Polymorphic? (Shape 3, 4)
                                            - Megamorphic? Dictionary lookup
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Demonstrasi Perubahan Shape & Dampak De-optimasi

Simpan kode ini dan jalankan menggunakan Node.js dengan flag engine internal:
`node --allow-natives-syntax index.js`

```javascript
// file: index.js

function Point(x, y) {
    this.x = x;
    this.y = y;
}

// Case 1: Monomorphic Instantiation (Bentuk/Shape Seragam)
const p1 = new Point(1, 2);
const p2 = new Point(3, 4);

// Case 2: Shape Divergence (Urutan Inisialisasi Dinamis)
const p3 = {};
p3.x = 5;
p3.y = 6; // Shape p3 berbeda dari Point jika konstruktor Point dioptimasi berbeda

const p4 = {};
p4.y = 6; // URUTAN TERBALIK! Menghasilkan Shape Transition Tree berbeda
p4.x = 5;

function computeMagnitude(point) {
    // Call site untuk IC
    return point.x + point.y;
}

// Warm-up IC
for (let i = 0; i < 10000; i++) {
    computeMagnitude(p1);
    computeMagnitude(p2);
}

// Analisis menggunakan V8 Builtins (Hanya berjalan dengan flag --allow-natives-syntax)
if (typeof %HaveSameMap !== 'undefined') {
    console.log("p1 dan p2 memiliki Shape sama?:", %HaveSameMap(p1, p2)); // true
    console.log("p1 dan p3 memiliki Shape sama?:", %HaveSameMap(p1, p3)); // false
    console.log("p3 dan p4 memiliki Shape sama?:", %HaveSameMap(p3, p4)); // false
} else {
    console.log("Jalankan dengan: node --allow-natives-syntax index.js");
}
```

#### 7.2. Practical Enterprise Example: Transparent Audit & Invariant-Safe Virtualization Engine

Implementasi modul pelacakan mutasi data transaksional perbankan berbasis `Proxy`, `Reflect`, dan `WeakMap`. Desain ini menjamin audit otomatis, pembekuan status, dan mempertahankan *Engine Invariants*.

```javascript
/**
 * @file EnterpriseAuditEngine.js
 * Modul virtualisasi objek untuk Enterprise Data Layer dengan zero property pollution.
 */

// Simpan audit log secara terisolasi tanpa memodifikasi properti target
const AUDIT_TRAIL = new WeakMap();
const REVOCATION_HANDLERS = new WeakMap();

// Namespace Symbol untuk properti metadata internal engine
const $IS_PROXIED = Symbol('engine.isProxied');
const $SNAPSHOT = Symbol('engine.snapshot');

class EntityInvariantViolation extends Error {
    constructor(message) {
        super(`[INVARIANT_VIOLATION] ${message}`);
        this.name = 'EntityInvariantViolation';
    }
}

/**
 * Factory untuk membuat Enterprise Proxied Entity dengan audit capture deterministik.
 * @template T
 * @param {T} target
 * @param {string} actor
 * @returns {{ proxy: T, revoke: () => void }}
 */
export function createAuditedEntity(target, actor) {
    if (typeof target !== 'object' || target === null) {
        throw new TypeError('Target harus berupa objek non-null.');
    }

    // Inisialisasi audit trail untuk target
    if (!AUDIT_TRAIL.has(target)) {
        AUDIT_TRAIL.set(target, []);
    }

    const { proxy, revoke } = Proxy.revocable(target, {
        get(rawTarget, prop, receiver) {
            // Internal reflection bypass
            if (prop === $IS_PROXIED) return true;
            if (prop === $SNAPSHOT) {
                return Object.freeze({ ...rawTarget });
            }

            // Gunakan Reflect untuk menjamin penanganan receiver yang tepat
            const value = Reflect.get(rawTarget, prop, receiver);

            // Jika properti berupa sub-objek, bungkus secara rekursif (Virtualization Barrier)
            if (typeof value === 'object' && value !== null && !value[$IS_PROXIED]) {
                return createAuditedEntity(value, actor).proxy;
            }

            return value;
        },

        set(rawTarget, prop, newValue, receiver) {
            // ENFORCE INVARIANT: Larang mutasi ID atau atribut immutable
            const descriptor = Reflect.getOwnPropertyDescriptor(rawTarget, prop);
            if (descriptor && descriptor.writable === false && descriptor.configurable === false) {
                // Memenuhi ECMAScript Invariant
                return Reflect.set(rawTarget, prop, newValue, receiver);
            }

            if (prop === 'id' && Reflect.has(rawTarget, 'id')) {
                throw new EntityInvariantViolation("Properti 'id' immutable dan tidak dapat diubah.");
            }

            const oldValue = Reflect.get(rawTarget, prop, receiver);
            
            // Lakukan mutasi default
            const success = Reflect.set(rawTarget, prop, newValue, receiver);

            if (success && oldValue !== newValue) {
                const logs = AUDIT_TRAIL.get(target);
                logs.push({
                    timestamp: Date.now(),
                    actor,
                    field: String(prop),
                    oldValue,
                    newValue
                });
            }

            return success;
        },

        deleteProperty(rawTarget, prop) {
            // Anti-Deoptimization Guard: Mencegah delete operator pada production hot-objects
            throw new EntityInvariantViolation(
                `Penghapusan properti '${String(prop)}' dilarang. Setel properti menjadi null.`
            );
        }
    });

    REVOCATION_HANDLERS.set(proxy, revoke);
    return { proxy, revoke };
}

/**
 * Ekstraksi riwayat audit dari entitas target.
 */
export function getAuditLogs(target) {
    if (!AUDIT_TRAIL.has(target)) {
        throw new Error('Objek target bukan entitas yang terdaftar pada audit system.');
    }
    return Object.freeze([...AUDIT_TRAIL.get(target)]);
}

// ======================= DEMO PENGGUNAAN =======================
try {
    const rawAccount = {
        id: 'ACC-9921',
        holder: 'PT. Teknologi Global',
        balance: 500000000,
        settings: {
            notification: true
        }
    };

    const { proxy: account, revoke } = createAuditedEntity(rawAccount, 'system_worker_42');

    // Mutasi legal
    account.balance = 450000000;
    account.settings.notification = false;

    console.log('Current Balance:', account.balance);
    console.log('Audit Log Master Target:', getAuditLogs(rawAccount));

    // Uji Pelanggaran Invariant: Ubah ID
    // account.id = 'ACC-0000'; // Throws EntityInvariantViolation

    // Uji Anti-Deoptimization: Operator delete
    // delete account.balance; // Throws EntityInvariantViolation

    // Revocation Test: Amankan memori / tutup akses
    revoke();
    console.log(account.balance); // Throws TypeError: Cannot perform 'get' on a proxy that has been revoked
} catch (err) {
    console.error(`Caught Controlled Error: ${err.message}`);
}
```

---

### 8. Real-World Case Study (Enterprise Scale)

#### Konteks Sistem
Pada sistem transaksi pembayaran *high-frequency* perbankan (memproses ~45.000 req/detik), terdapat *Pipeline Data Normalizer* yang melakukan validasi skema dan mutasi ringan sebelum transaksi diserialisasi ke Apache Kafka.

#### Permasalahan (Root Cause Analysis)
Pemrosesan transaksi mengalami *latency degradation* ekstrem: p99 latency melonjak dari 1.8ms ke 84ms di bawah beban *peak*. Profiling melalui V8 CPU Profiler (`--prof`, dikonversi via `node --prof-process`) mengungkap temuan berikut:
1.  **Deoptimasi Inline Cache Massal**: Objek *payload* transaksi dikonsumsi dari API gateway dalam format JSON parsial. Tim engineering menambahkan properti secara dinamis berdasarkan *flags* bisnis menggunakan blok kondisional:
    ```javascript
    // KODE BERMASALAH SEBELUMNYA
    const tx = JSON.parse(rawPayload);
    if (tx.isInternational) tx.swiftCode = getSwift();
    if (tx.taxExempt) tx.taxId = null;
    tx.processedAt = Date.now();
    ```
    Urutan penambahan properti yang acak menghasilkan lebih dari **60 Shape berbeda** untuk entitas transaksi yang sama.
2.  **Megamorphic Dispatch**: Fungsi sentral `validateAndSerialize(tx)` jatuh ke status **Megamorphic**. TurboFan membuang (*bailout*) kode teroptimasi mesin dan menggunakan *Runtime Dynamic Hash Lookup*.
3.  **V8 Elements Kind Degradation**: Penanganan field tagging transaksi berubah dari *PACKED_SMI_ELEMENTS* menjadi *HOLEY_ELEMENTS* akibat penggunaan `delete tx[field]` untuk menghapus data sensitif.

#### Solusi Arsitektural Terintegrasi
1.  **Strict Object Shape Seeding**: Merancang skema monomorfik absolut. Setiap objek transaksi diinstansiasi melalui fungsi konstruktor pabrik (*Factory Function*) yang menginisialisasi **seluruh** kemungkinan field pada urutan yang identik dengan nilai *default* `null`.
2.  **Sentinel Invalidation**: Mengeliminasi penggunaan `delete`. Properti sensitif di-masking menjadi `null` atau `undefined` agar Shape tidak bermutasi menjadi *Slow Dictionary Mode*.
3.  **Hermetic Class Definition**:
```javascript
// SOLUSI: Monomorphic Shape Preservation Architecture
class CanonicalTransaction {
    constructor(source) {
        // Alokasi in-object properties secara deterministik
        this.transactionId = source.transactionId ?? null;
        this.accountId = source.accountId ?? null;
        this.amount = source.amount ?? 0;
        this.currency = source.currency ?? 'IDR';
        this.isInternational = Boolean(source.isInternational);
        this.swiftCode = source.swiftCode ?? null;
        this.taxId = source.taxId ?? null;
        this.processedAt = Date.now();
    }
}

// Di level Pipeline API:
function processPipeline(rawBatch) {
    const size = rawBatch.length;
    const normalizedBatch = new Array(size);
    for (let i = 0; i < size; i++) {
        // Semua instans memiliki tepat SATU Map yang identik
        normalizedBatch[i] = new CanonicalTransaction(rawBatch[i]);
    }
    return normalizedBatch;
}
```

#### Hasil Metrik Produksi
*   **p99 Latency**: Berkurang secara drastis dari 84ms ke 1.2ms.
*   **V8 Deoptimizations**: Turun dari ~12.000 kejadian/menit ke 0 kejadian pada *hot path*.
*   **Throughput Node.js Cluster**: Meningkat 3.2x lipat pada pemanfaatan CPU yang sama.

---

### 9. Trade-offs (Analisis Arsitektur)

| Dimensi Rekayasa | Opsi A: Dynamic & Metaprogramming-Heavy (`Proxy`/`Reflect`) | Opsi B: Monomorphic Static Shapes (`Pojos`/`Classes`) | Justifikasi Arsitektur |
| :--- | :--- | :--- | :--- |
| **Runtime Latency** | **Tinggi (~2x-5x lebih lambat)**: Setiap akses properti melewati *trapping overhead* dan dereferensi C++ V8. | **Sangat Rendah (Near Native C++)**: Direct offset indexing yang di-*inlined* langsung oleh TurboFan. | Gunakan `Proxy` hanya pada *Boundary Layer* (misal: ORM unit-of-work, Audit, Security Gateway), bukan di dalam *Ultra-Hot Calculation Loops*. |
| **Fleksibilitas Kode** | **Maksimal**: Virtualisasi dinamis, lazy-loading, sandboxing, mocking tanpa manipulasi target fisik. | **Kaku**: Properti harus dideklarasikan di awal; variasi struktur objek ditekan ke batas minimum. | Opsi A ideal untuk *Framework & Platform Engines*. Opsi B wajib untuk *Data Processing Pipeline*. |
| **Konsumsi Memori** | **Tinggi**: `Proxy` wrapper mengalokasikan slot memori sekunder dan *Heap Overhead* untuk internal handler. | **Sangat Efisien**: Memanfaatkan *In-Object Properties* V8 tanpa alokasi wrapper tambahan. | Jika sistem mengelola >1.000.000 objek serentak di memori, hindari pembungkusan objek satu per satu dengan `Proxy`. |
| **Developer Ergonomics** | Otomatisasi *Cross-Cutting Concerns* terpusat (DRY principle). | Perlu boilerplate kelas eksplisit atau fungsi normalisasi DTO. | Menukar sedikit ergonomi kode demi stabilitas p99 latency di skala jutaan TPS. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Kerentanan Prototype Pollution pada Deep Object Merge
**Masalah**: Penggabungan objek rekursif tanpa validasi *key* internal memungkinkan penyerang menyuntikkan properti ke `Object.prototype`.

```javascript
// ANTI-PATTERN: Rentan Prototype Pollution
function unsafeDeepMerge(target, source) {
    for (let key in source) {
        if (typeof source[key] === 'object' && source[key] !== null) {
            if (!target[key]) target[key] = {};
            unsafeDeepMerge(target[key], source[key]);
        } else {
            target[key] = source[key];
        }
    }
    return target;
}

// Eksploitasi Payload:
const payload = JSON.parse('{"__proto__": {"isAdmin": true}}');
unsafeDeepMerge({}, payload);
console.log({}.isAdmin); // true! SELURUH APLIKASI TERKOMPROMISI
```

**Solusi Perbaikan (Production Hardening)**:
```javascript
// SECURE PATTERN: Hermetic Guarded Merge
function secureDeepMerge(target, source) {
    const FORBIDDEN_KEYS = new Set(['__proto__', 'constructor', 'prototype']);

    for (const [key, value] of Object.entries(source)) {
        if (FORBIDDEN_KEYS.has(key)) {
            continue; // Abaikan key yang mengancam prototype integrity
        }

        if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
            if (!Object.prototype.hasOwnProperty.call(target, key)) {
                target[key] = Object.create(null); // Hermetic object
            }
            secureDeepMerge(target[key], value);
        } else {
            target[key] = value;
        }
    }
    return target;
}
```

#### 10.2. De-optimasi Bentuk Objek melalui Operator `delete`
**Masalah**: Penggunaan `delete obj.prop` memaksa V8 memindahkan penyimpanan properti dari *Fast In-Object/Descriptor Array* menjadi *Slow Dictionary Mode* (Hash Table internal).

```javascript
// MEMICU DICTIONARY MODE
const entity = { a: 1, b: 2, c: 3 };
delete entity.b; // V8 merusak Shape Tree: entity sekarang berada di "Dictionary Mode"

// SOLUSI: Nullify Sentinel Strategy
entity.b = undefined; // Shape Map tetap FAST_PROPERTIES
```

#### 10.3. Kebocoran Memori Akibat Retained Reference pada Proxy Target
**Masalah**: Menyimpan referensi ke *target* dan *proxy* secara bersamaan pada arsitektur *caching* jangka panjang mencegah *Garbage Collector* membebaskan *target*.
*   *Troubleshooting*: Gunakan `Proxy.revocable()` untuk memutus relasi internal ketika masa aktif entitas selesai, serta pasangkan dengan `WeakMap` untuk memetakan *metadata*.

---

### 11. Best Practices (Production Checklist)

*   [ ] **Inisialisasi Lengkap di Konstruktor**: Deklarasikan seluruh properti entitas di dalam `constructor`. Tetapkan nilai `null` jika nilainya belum tersedia.
*   [ ] **Urutan Inisialisasi Seragam**: Pastikan urutan penugasan properti identik pada setiap pemanggilan fungsi pembangun objek.
*   [ ] **Zero `delete` in Hot Paths**: Larang penggunaan operator `delete`. Ganti dengan penetapan `null` atau `undefined` untuk mencegah fallback ke *Dictionary Mode*.
*   [ ] **Hermetic Dictionaries**: Untuk *hash map* murni yang menampung *arbitrary keys* (input luar), gunakan `new Map()` atau `Object.create(null)`.
*   [ ] **Defensif terhadap Dynamic Prototypes**: Hindari pemanggilan `Object.setPrototypeOf()` setelah objek terinstansiasi; mutasi prototipe dinamis membatalkan semua optimasi IC inline di seluruh aplikasi.
*   [ ] **Reflect Synchronization**: Pastikan setiap Proxy Trap yang dibuat mendelegasikan operasi fallback menggunakan pasangan `Reflect[trapName]` yang sesuai.
*   [ ] **Defensive Invariant Compliance**: Pastikan trap `get/set` pada *Proxy* selalu memeriksa apakah target berstatus *frozen* atau *sealed* sebelum mengembalikan nilai non-standard.

---

### 12. Hands-on Practice (Implementasi Bertahap)

Instruksi: Simpan seluruh kode di direktori `hands-on/m02/`.

#### Langkah 1: Eksplorasi Shape V8 Engine Flags
Buat file `hands-on/m02/01-shape-inspection.cjs`:
```javascript
// Jalankan dengan: node --allow-natives-syntax hands-on/m02/01-shape-inspection.cjs

function createRecord(id, code) {
    return { id, code };
}

const rec1 = createRecord(1, "A");
const rec2 = createRecord(2, "B");

// Modifikasi bentuk rec2 secara dinamis
rec2.dynamicField = "Leak";

console.log("--- V8 Shape Status ---");
console.log("rec1 dan rec2 satu map?:", %HaveSameMap(rec1, rec2));

// Debugging detail struktur internal C++ V8 (Output tercetak di stdout)
console.log("Memory Map rec1:");
%DebugPrint(rec1);

console.log("Memory Map rec2 (Pemberian field tambahan):");
%DebugPrint(rec2);
```

#### Langkah 2: Membangun Production Transactional State Manager
Buat file `hands-on/m02/02-transactional-state.mjs`:
```javascript
/**
 * hands-on/m02/02-transactional-state.mjs
 * State Container dengan Transactional Rollback bertenaga Proxy & Reflect.
 */

export class TransactionalContainer {
    #state;
    #backup;
    #inTransaction = false;

    constructor(initialState = {}) {
        // Deep copy sederhana untuk hermetic isolation
        this.#state = JSON.parse(JSON.stringify(initialState));
        this.#backup = null;
    }

    beginTransaction() {
        if (this.#inTransaction) {
            throw new Error("Transaksi sudah berjalan!");
        }
        this.#inTransaction = true;
        this.#backup = JSON.parse(JSON.stringify(this.#state));
    }

    commit() {
        if (!this.#inTransaction) {
            throw new Error("Tidak ada transaksi untuk di-commit.");
        }
        this.#inTransaction = false;
        this.#backup = null;
    }

    rollback() {
        if (!this.#inTransaction) {
            throw new Error("Tidak ada transaksi aktif untuk di-rollback.");
        }
        this.#state = this.#backup;
        this.#backup = null;
        this.#inTransaction = false;
    }

    get access() {
        const self = this;
        return new Proxy(this.#state, {
            get(target, prop, receiver) {
                const value = Reflect.get(target, prop, receiver);
                if (typeof value === 'object' && value !== null) {
                    // Proteksi pembacaan dalam bentuk nested proxy jika dibutuhkan
                    return value;
                }
                return value;
            },
            set(target, prop, value, receiver) {
                if (!self.#inTransaction) {
                    throw new Error("Mutasi state dilarang di luar transaksi!");
                }
                return Reflect.set(target, prop, value, receiver);
            }
        });
    }
}

// Uji coba operasional
const store = new TransactionalContainer({ balance: 1000, profile: { tier: 'Gold' } });
const state = store.access;

console.log("Initial Balance:", state.balance);

store.beginTransaction();
state.balance = 2500;
console.log("Mutated Balance (In-Tx):", state.balance);

console.log("Simulating failure... Rolling back!");
store.rollback();
console.log("Rolled back Balance:", state.balance);

try {
    state.balance = 9999; // Harusnya ditolak
} catch (e) {
    console.log("Blocked Mutation:", e.message);
}
```

---

### 13. Exercises

#### Level Easy
Buat file `hands-on/m02/ex-easy.js`.
*   **Tugas**: Buat fungsi `stabilizeObject(rawObj)` yang menerima objek dengan properti arbitrer, mengekstrak semua key-nya, mengurutkannya secara alfabetis, dan mengembalikan objek baru yang propertinya disusun berdasarkan urutan tersebut.
*   **Target Engine**: Pastikan setiap pemanggilan `stabilizeObject({ b: 1, a: 2 })` dan `stabilizeObject({ a: 10, b: 20 })` menghasilkan objek dengan Shape/Map yang **identik** di V8.

#### Level Medium
Buat file `hands-on/m02/ex-medium.js`.
*   **Tugas**: Buat kelas `HermeticRegistry` yang berfungsi sebagai container penyimpan event handler atau middleware.
*   **Batasan**:
    1.  Dilarang menggunakan `Map` native (harus menggunakan `Object.create(null)`).
    2.  Container harus kebal terhadap serangan penyuntikan properti `__proto__`, `toString`, atau `valueOf`.
    3.  Setiap modifikasi harus menggunakan fungsi `register(key, handler)` dan dilarang mengekspos raw dictionary ke konsumen luar.

#### Level Hard
Buat file `hands-on/m02/ex-hard.js`.
*   **Tugas**: Rancang sebuah **Micro Unit-Of-Work Engine** untuk entitas data.
*   **Spesifikasi**:
    1.  Menerima entitas model bisnis.
    2.  Membungkusnya dalam *Revocable Proxy*.
    3.  Lacak status entitas: `DIRTY` (berubah), `CLEAN` (tidak berubah), `PRISTINE` (baru).
    4.  Pelacakan dirty-checking dilakukan dengan membandingkan nilai lama dan baru via `WeakMap` tanpa menempelkan metadata apapun pada objek target.
    5.  Sediakan metode `commit()` yang mengembalikan *changeset diff payload* dan secara otomatis me-revoke proxy tersebut agar tidak dapat diakses kembali.

---

### 14. Challenges

Rancang sistem arsitektur terisolasi: **"Multi-Tenant Plugin Sandboxing Engine"**.
*   **Deskripsi Kasus**: Anda memimpin tim arsitektur *Fintech Platform*. Sistem Anda memungkinkan pihak ketiga menyuntikkan kode JS plugin dinamis untuk menghitung komisi/pajak.
*   **Spesifikasi Teknis Tantangan**:
    1.  Plugin dieksekusi di context terkontrol dan hanya diberi akses ke objek `TransactionContext`.
    2.  Objek `TransactionContext` dibungkus menggunakan *Layered Proxies*:
        *   Membatasi pembacaan data (Field `userPasswordHash`, `internalAuditKey` harus menghasilkan `undefined` dan memicu alert log saat dibaca via trap `get` atau dicek via trap `has`).
        *   Mencegah modifikasi data di luar field spesifik yang diizinkan (Field whitelist: `calculatedFee`, `customTags`).
        *   Mencegah *leakage* dari `Object.prototype` (eksekusi plugin tidak boleh dapat mengubah prototipe global apapun).
        *   Jika plugin mencoba melanggar *ECMAScript Invariant*, sistem tidak boleh *crash*, melainkan menangkap *error*, mencatat identitas tenant ke *blacklisted logger*, dan mematikan eksekusi plugin secara aman via *Proxy Revocation*.
    3.  Tingkat performa: Arsitektur proxy harus mampu mengeksekusi 10.000 kalkulasi plugin/detik tanpa memicu deoptimasi Inline Cache (*Megamorphism*) pada pemrosesan batch.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)
1.  **Di mana V8 menyimpan named properties pertama dari sebuah objek secara direct access tanpa array pointer tambahan?**
    *   A. Elements FixedArray
    *   B. In-Object Properties
    *   C. Global Hash Table
    *   D. Call Stack

2.  **Apa yang terjadi pada struktur internal V8 jika dua objek diisi dengan properti yang sama tetapi dalam urutan penugasan yang berbeda?**
    *   A. V8 otomatis menyusun ulang offset properti sehingga keduanya memiliki Map yang sama.
    *   B. V8 memicu runtime error karena struktur Map tidak sinkron.
    *   C. Keduanya memiliki Shape/Map yang berbeda karena jalur transisinya bercabang.
    *   D. Objek kedua otomatis berstatus Megamorphic.

3.  **Manakah fungsi bawaan `Object` yang menghasilkan dictionary tanpa delegasi prototipe bawaan (`prototype: null`)?**
    *   A. `Object.assign({}, null)`
    *   B. `Object.freeze({})`
    *   C. `Object.create(null)`
    *   D. `new Object(null)`

4.  **Apa fungsi dari API `Reflect` dalam implementasi Proxy?**
    *   A. Menggandakan performa trapping Proxy menjadi 2x lebih cepat.
    *   B. Meneruskan operasi fundamental default ke target dengan konteks `receiver` yang benar.
    *   C. Mengonversi objek target menjadi berstatus Monomorphic.
    *   D. Mengabaikan aturan ECMAScript Invariants.

5.  **Status Inline Cache (IC) yang paling optimal dan menghasilkan eksekusi kode mesin langsung oleh TurboFan adalah...**
    *   A. Megamorphic
    *   B. Polymorphic
    *   C. Monomorphic
    *   D. Uninitialized

---

#### Bagian 2: Intermediate (Analisis Singkat)
1.  Jelaskan mengapa pemanggilan operator `delete obj.property` sangat tidak disarankan pada *hot code paths* di Node.js!
2.  Sebutkan salah satu contoh pelanggaran *Proxy Trapping Invariant* yang dapat memicu `TypeError` instan dari V8 engine!
3.  Mengapa `WeakMap` lebih direkomendasikan untuk menyimpan metadata internal objek dibandingkan menempelkan *property flag* menggunakan `Symbol`?
4.  Jelaskan perbedaan mendasar antara *Elements* dan *Properties* pada tata letak memori internal objek V8!
5.  Apa perbedaan mendasar antara representasi objek dalam mode *Fast Properties* vs *Dictionary Mode* (Slow Properties)?

---

#### Bagian 3: Skenario Kasus Produksi
1.  **Kasus Profiling Memory Leak**: Tim Anda mendapati konsumsi memori server bertambah secara linier seiring waktu hingga Node.js mengalami OOM (*Out Of Memory*). Analisis Heap Snapshot menunjukkan jutaan instance `Proxy` tertahan di memori. Objek target aslinya sebenarnya sudah tidak digunakan di alur bisnis. Identifikasi penyebab potensialnya dan bagaimana solusi pencegahannya secara arsitektural!
2.  **Kasus Prototype Pollution Attack**: Sebuah layanan microservice menerima payload JSON dari webhook publik. Setelah 1 jam berjalan, seluruh penanganan logika otorisasi `if (user.isAdmin)` mengembalikan nilai `true` untuk semua user tak dikenal. Deskripsikan alur bagaimana celah ini dieksploitasi dan desain modul penangkalnya di layer terdepan!
3.  **Kasus Extreme Latency De-optimization**: Sebuah fungsi serializer `serializeUser(user)` mengalami regresi performa 20x lebih lambat setelah rilis fitur baru. Fitur baru tersebut menambahkan properti `user.partnerId` hanya jika user bertipe mitra bisnis. Bagaimana Anda merombak kode tersebut untuk memulihkan status *Inline Cache* kembali ke kondisi optimal?

---

### 16. Summary

1.  **V8 Object Representation**: Objek di V8 tidak sekadar hash table C++. Tata letak memori terdiri dari *Map (Shape)* pointer, *Elements* (untuk array index), *Properties* (overflow storage), dan *In-Object Properties* (alokasi memori berdampingan dengan header yang super cepat).
2.  **Monomorphic Dominance**: Kinerja puncak JIT Compiler (TurboFan) bergantung pada stabilitas *Shape Transitions*. Objek yang memiliki properti identik dengan urutan alokasi seragam menghasilkan akses *Monomorphic Inline Cache (IC)* yang mengeksekusi instruksi langsung di level assembly.
3.  **Metaprogramming Compliance**: `Proxy` dan `Reflect` menyediakan abstraksi intersepsi kelas enterprise, namun memiliki penalti latensi dan wajib mematuhi aturan ketat *Proxy Trapping Invariants* untuk mencegah kerusakan konsistensi state engine.
4.  **Engine-Aware Defense**: Mencegah de-optimasi V8 sama pentingnya dengan keamanan sistem: hindari mutasi dinamis via `delete` dan eliminasi ancaman *Prototype Pollution* menggunakan kamus hermetis (`Object.create(null)`), `WeakMap`, dan isolasi skema yang ketat.