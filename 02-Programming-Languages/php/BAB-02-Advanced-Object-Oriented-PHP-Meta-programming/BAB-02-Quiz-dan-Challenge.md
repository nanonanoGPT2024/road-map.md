# BAB 02: Quiz, Challenge, & Knowledge Check
**Advanced Object-Oriented PHP & Meta-programming**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Late Static Binding (LSB) dan Resolusi Scope Runtime
Jelaskan perbedaan mendasar antara resolusi token `self::`, `parent::`, dan `static::` di level Zend Engine. Kapan runtime memanfaatkan *current class scope* tempat fungsi dideklarasikan versus *called class scope* tempat fungsi dieksekusi? Berikan analisis mekanismenya pada rantai pewarisan berjenjang (*multi-tiered inheritance*).

### Soal 1.2: Varian Subtipe: Kovariansi dan Kontravariansi
Jelaskan aturan formal PHP 7.4+ dan 8.x terkait tipe varian (*type variance*) pada signature method inheritance yang tunduk pada Liskov Substitution Principle (LSP). Mengapa tipe parameter bersifat kontravarian sementara tipe return bersifat kovarian? Sertakan konsekuensi fatal jika sebuah engine bahasa mengizinkan kovariansi pada parameter.

### Soal 1.3: Enums sebagai Objek Tingkat Pertama (First-Class Objects)
PHP 8.1 memperkenalkan Backed Enums dan Unit Enums yang diimplementasikan sebagai `final class` internal. Jelaskan batasan arsitektural yang diterapkan Zend Engine pada Enums (misalnya instansiasi, kloning, pewarisan, dan method magic) dan bagaimana Enum dapat mengimplementasikan interface serta memanfaatkan traits tanpa melanggar sifat deterministik nilainya.

### Soal 1.4: Semantik Immutabilitas: Readonly Classes vs Shallow Immutability
PHP 8.2 memungkinkan deklarasi `readonly class`. Analisis batasan semantik ini terhadap *deep immutability*: Apa yang terjadi ketika sebuah property bertipe objek atau referensi array di-assign ke dalam instance `readonly class`? Bagaimana Zend Engine memvalidasi inisialisasi property readonly, dan mengapa unset/re-assignment memicu `Error` fatal?

### Soal 1.5: Arsitektur PHP 8 Attributes vs Dokumen Annotations (DocBlock)
Bandingkan mekanisme deklarasi meta-programming menggunakan PHP 8 Native Attributes (`#[\Attribute]`) dengan parsing DocBlock konvensional (misalnya via `doctrine/annotations`). Tinjau dari aspek:
1. Waktu eksekusi parsing (*compile-time tokenization* vs *runtime regex parsing*).
2. Dampak integrasi dengan OpCache.
3. Type-safety dan validasi sintaks sebelum eksekusi logic.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: OpCache, JIT, dan Overhead Magic Methods
Magic methods seperti `__get()`, `__set()`, dan `__call()` menyediakan fleksibilitas meta-programming yang tinggi namun memiliki konsekuensi kinerja signifikan pada Zend VM. Jelaskan mengapa pemanggilan dynamic dispatch lewat `__call()` tidak dapat dioptimalkan secara agresif oleh OpCache optimizer dan JIT compiler jika dibandingkan dengan pemanggilan langsung (*direct method dispatch via class entry vtable*).

### Soal 2.2: Resolusi Konflik Trait dan Linierisasi Method Table
Ketika sebuah class menggunakan dua Traits yang mendefinisikan method dengan nama dan signature yang identik:
1. Bagaimana urutan precedensi resolusi method antara Base Class, Trait, dan Current Class?
2. Bagaimana operator `insteadof` dan `as` memanipulasi method entry pada `zend_class_entry` saat tahap kompilasi?
3. Apa implikasi struktural terhadap visibilitas saat alias method didefinisikan ulang menggunakan `as`?

### Soal 2.3: Mitigasi Memory Leak pada Dynamic Proxy & Hydrator via WeakMap
Dalam implementasi dynamic ORM hydrator atau proxy pattern berbasis Reflection, developer kerap menyimpan metadata objek atau circular references antar entity dalam cache lokal memory. 
1. Jelaskan mengapa penggunaan array asosiatif standar (`spl_object_hash($obj) => $meta`) mengakibatkan memory leak laten meski objek di luar cache sudah di-*destroy*.
2. Bagaimana struktur internal `WeakMap` mengatasi siklus referensi (*circular reference*) pada Zend Garbage Collector (GC)?

### Soal 2.4: Deprekasi Dynamic Properties dan Penghapusan Property Table Mutasi
PHP 8.2 secara resmi mendeprekasi penambahan *dynamic properties* secara implisit pada runtime object (kecuali menggunakan `stdClass` atau atribut `#[\AllowDynamicProperties]`). 
1. Jelaskan alasan teknis Zend Engine menghentikan fitur ini ditinjau dari alokasi memori hash-table (`properties_table` pada struct `zend_object`).
2. Apa dampak performa dan konsumsi memori saat sebuah objek dialokasikan tanpa alokasi dynamic property table yang dinamis?

### Soal 2.5: Manipulasi Scope Internal via `Closure::bind` vs Reflection API
Dua teknik utama meta-programming untuk mengakses property/method `private` adalah melalui `ReflectionProperty::setAccessible(true)` (atau pemanggilan langsung di PHP 8.1+) dan `Closure::bind()` / `Closure::bindTo()`. 
1. Bagaimana perbedaan mekanisme internal kedua pendekatan tersebut dalam memintas encapsulation boundary?
2. Pendekatan mana yang memiliki overhead eksekusi lebih rendah untuk eksekusi berulang ribuan kali? Jelaskan alasannya dari sudut pandang *Zend VM call frame* dan *cacheability*.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Degradasi Latensi P99 pada Event-Driven Microservice
*Konteks Sistem:* Sebuah microservice transaksi keuangan dengan beban 25.000 RPS berbasis PHP 8.2 dan Swoole mengalami lonjakan latensi P99 dari 12ms ke 450ms setelah migrasi arsitektur ke sistem Event Dispatcher berbasis meta-programming. 

*Temuan Diagnostik:* Profiling via Blackfire/Excimer menunjukkan 68% CPU time dialokasikan pada fungsi `ReflectionClass::getAttributes()`, `ReflectionMethod::getParameters()`, dan deserialisasi payload yang menggunakan nested dynamic Reflection instantiation di setiap siklus request.

```
[Incoming Request] 
      │
      ▼
[Swoole Worker] ──► [EventDispatcher::dispatch()]
                           │
                           ├──► [ReflectionClass::getAttributes()] (Dijalankan per request)
                           ├──► [ReflectionParameter Type Check]   (Dijalankan per request)
                           └──► Dynamic Dispatch via Closure
```

*Pertanyaan Diagnostik:*
1. Identifikasi akar penyebab arsitektural (*architectural root-cause*) dari degradasi sistem tersebut.
2. Rancang strategi refaktorisasi arsitektur untuk mempertahankan penggunaan Native Attributes namun memindahkan overhead meta-programming dari *request-time execution* ke *application bootstrap/warmup-up phase*.
3. Bagaimana Anda menstrukturkan cache metadata internal agar thread-safe dan ramah terhadap memory model persistent worker seperti Swoole atau RoadRunner?

---

### Skenario B: State Mutation & Split-Brain pada Domain-Driven Design (DDD) Aggregate
*Konteks Sistem:* Sebuah platform e-commerce menerapkan DDD Aggregate menggunakan `readonly class` untuk menjamin immutabilitas `Order` Aggregate Root saat transaksi sedang divalidasi oleh asynchronous worker pool.

*Implementasi Kode:*
```php
readonly class Money {
    public function __construct(
        public int $amount,
        public string $currency
    ) {}
}

readonly class Order {
    public function __construct(
        public string $id,
        public Money $total,
        public ArrayObject $items // Menampung koleksi OrderItem
    ) {}
}
```

*Insiden:* Terjadi kegagalan audit transaksi di mana nilai total pesanan tidak cocok dengan akumulasi item di database. Log menunjukkan bahwa item ditambahkan ke property `$items` saat order sedang dieksekusi di state *processing*, padahal instance class dideklarasikan sebagai `readonly`.

*Pertanyaan Diagnostik:*
1. Mengapa engine PHP mengizinkan mutasi pada `$order->items` meskipun class `Order` didefinisikan sebagai `readonly class`? Jelaskan batasan semantic dari *shallow immutability*.
2. Modifikasi arsitektur class di atas agar Aggregate Root memiliki jaminan *deep immutability* yang mutlak, tanpa memungkinkan manipulasi state internal secara direct reference dari luar boundary domain.
3. Rancang pola pertukaran data yang thread-safe untuk skenario pembaharuan data (misalnya: *Wither pattern / Immutable update pattern*).

---

### Skenario C: Dilema Arsitektur: Dynamic AOP Proxy vs Static Code Generation
*Konteks Sistem:* Tim arsitek sedang merancang framework modul audit trail dan keamanan internal untuk enterprise banking. Sistem harus mampu mencegat (*intercept*) method call pada level Service Layer untuk mencatat audit log, validasi otorisasi RBAC, dan eksekusi distributed transaction rollback.

Terdapat dua proposal arsitektur yang bersaing:
- **Proposal 1:** Menggunakan Dynamic Runtime Proxy memanfaatkan `__call()`, magic method delegation, dan `ReflectionClass` secara runtime (mengadopsi pendekatan Doctrine Dynamic Proxies / ByteBuddy style via dynamic eval).
- **Proposal 2:** Menggunakan Ahead-Of-Time (AOT) Static Compilation yang membaca Native Attributes `#[\Audit]` dan `#[\Authorize]`, lalu menghasilkan *generated concrete proxy classes* fisik ke disk saat fase deployment CI/CD.

*Pertanyaan Diagnostik:*
1. Lakukan analisis perbandingan mendalam (*trade-off analysis*) antara Proposal 1 dan Proposal 2 mencakup aspek:
   - Performansi eksekusi runtime (CPU/Memory).
   - Traceability stack trace & kemudahan debugging production error.
   - Kompatibilitas dengan OpCache Preloading dan PHP JIT.
2. Tentukan pendekatan mana yang paling tepat untuk sistem enterprise banking dengan persyaratan zero-downtime, deterministik, dan audit regulasi yang ketat. Berikan justifikasi teknis arsitektural Anda.

---

## 4. Chapter Challenge

### Tantangan Praktis: Zero-Overhead Type-Safe Event Dispatcher Berbasis Attributes & Dynamic Class Compilation

#### Problem Statement
Dalam framework enterprise modern, arsitektur event-driven decoupling sering kali mengorbankan performa akibat overhead Reflection API yang berjalan berulang pada critical path, atau mengorbankan type-safety dengan memanfaatkan closure berbasis untyped array. Anda diminta membangun subsistem Event Dispatcher berkinerja ultra-tinggi yang mengeliminasi seluruh runtime reflection overhead.

#### Requirements
1. **Attribute Definition:**
   - Buat attribute `#[\Listen(event: string, priority: int = 0)]`.
   - Attribute harus dapat didefinisikan pada method dalam class listener apa pun. Validasi target atribut hanya pada level `Attribute::TARGET_METHOD`.
   
2. **Metadata Compilation & Validation:**
   - Bangun komponen `EventMetadataCompiler` yang memindai class listener yang didaftarkan.
   - Lakukan inspeksi signature method via Reflection: Method pendengar **wajib** memiliki tepat satu parameter dan parameter tersebut harus berupa strongly-typed class (nama Event). Jika tidak valid, lemparkan exception compile-time `InvalidListenerSignatureException`.
   
3. **Execution Engine (Zero Runtime Reflection):**
   - Hasil akhir kompilasi harus berupa closure teroptimasi atau generated direct invoker table yang disimpan dalam memory.
   - Saat method `dispatch(object $event): object` dipanggil, dispatcher **dilarang keras** memanggil class Reflection apa pun (`ReflectionClass`, `ReflectionMethod`, dll.).
   - Resolusi pemanggilan listener harus didasarkan pada FQCN (Fully Qualified Class Name) dari `$event` yang diuji secara kovarian (jika Listener mendengarkan `DomainEvent`, maka instance `OrderCreatedEvent` yang mengimplementasikan `DomainEvent` juga harus terpicu).
   - Eksekusi listener harus taat pada urutan `priority` (angka lebih besar dieksekusi lebih dahulu).

4. **Weak Referencing / Memory Safety:**
   - Dispatcher harus menyediakan mekanisme agar lifecycle listener yang berupa dynamic instance dapat dibersihkan oleh Garbage Collector jika scope listener telah hancur (manfaatkan `WeakReference` atau `WeakMap` untuk instance-level listener).

#### Constraints
- PHP Version: **PHP 8.2+**.
- `declare(strict_types=1);` pada seluruh file.
- Tidak boleh menggunakan library eksternal (murni PHP Standard Library).
- Eksekusi `dispatch()` pada benchmark 10.000 events tidak boleh mengakibatkan alokasi memory leaking (harus stabil pada baseline memory consumption).

#### Expected Output
1. File deklarasi Attribute `#[\Listen]`.
2. Implementasi interface `EventDispatcherInterface`.
3. Engine `CompiledEventDispatcher` yang mencakup fase `warmup()` dan fase `dispatch()`.
4. Script benchmark/verifikasi sederhana yang mendemonstrasikan:
   - Priority ordering.
   - Penolakan terhadap invalid listener method signature.
   - Bukti zero reflection call pada runtime dispatch.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Mekanisme internal Zend Engine dalam melacak scope LSB (`zend_class_entry` vs *called scope*).
- [ ] Batasan dan aturan Liskov Substitution Principle (LSP) pada kovariansi return type dan kontravariansi parameter type.
- [ ] Perbedaan representasi memori antara Unit Enums, Backed Enums, dan Standar Class.
- [ ] Karakteristik *shallow immutability* pada `readonly class` dan dampaknya terhadap object graph references.
- [ ] Lifecycle pemrosesan Native Attributes dari AST (Abstract Syntax Tree), bytecode OpCache, hingga pemanggilan Reflection API.
- [ ] Dampak dynamic property deprecation terhadap efisiensi hash table internal `zval`.
- [ ] Perbedaan arsitektural dan implikasi GC antara `WeakMap`, `WeakReference`, dan standard reference collection.

### Saya tidak perlu menghafal:
- [ ] Nilai bitmask integer spesifik dari Zend internal flags (misalnya nilai hex dari `ZEND_ACC_PUBLIC` atau `Attribute::TARGET_METHOD`).
- [ ] Urutan parameter numerik pada fungsi-fungsi C-level Zend Engine API.
- [ ] Detail implementasi algoritma bucket hash index di level internal Zend HashTable.

### Saya harus bisa melakukan:
- [ ] Mengonfigurasi dan memvalidasi class hierarchy yang aman secara varian (Covariant Return & Contravariant Arguments) tanpa menghasilkan LSP violation error.
- [ ] Membangun dynamic proxy engine yang type-safe menggunakan Native Attributes dan Reflection API dengan performa teroptimasi.
- [ ] Mencegah dan mendiagnosis memory leak yang disebabkan oleh static registries atau dynamic closures menggunakan `WeakMap`.
- [ ] Mengaudit kode sistem legacy yang bergantung pada dynamic properties dan memigrasikannya secara aman ke pola `readonly` atau Explicit DTOs.
- [ ] Merancang arsitektur pre-compiled meta-programming untuk infrastruktur mission-critical yang bersahabat dengan OpCache Preloading dan Persistent Runtimes (Swoole/RoadRunner).