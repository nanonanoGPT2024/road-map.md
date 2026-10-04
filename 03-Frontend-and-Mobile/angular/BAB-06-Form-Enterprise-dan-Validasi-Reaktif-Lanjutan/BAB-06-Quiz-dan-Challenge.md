# BAB 06: Quiz, Challenge, & Knowledge Check
**Form Enterprise & Validasi Reaktif Lanjutan**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Strict Typing pada Reactive Forms (Angular 14+)
Jelaskan perbedaan arsitektural dan inferensi tipe antara `FormGroup`, `FormRecord`, dan `UntypedFormGroup`. Dalam skenario enterprise seperti apa Anda secara absolut harus memilih `FormRecord` dibandingkan `FormGroup`, dan bagaimana dampaknya terhadap runtime safety serta proteksi kompilasi TypeScript?

### Soal 1.2: Anatomi dan Siklus Hidup ControlValueAccessor (CVA)
Uraikan secara mendalam kontrak antarmuka `ControlValueAccessor` (`writeValue`, `registerOnChange`, `registerOnTouched`, dan `setDisabledState`). Jelaskan alur eksekusi saat data mengalir dari model form reaktif ke view custom component, dan sebaliknya saat interaksi pengguna memicu perubahan state ke form model. Mengapa delegasi `setDisabledState` bersifat krusial pada integrasi library UI pihak ketiga?

### Soal 1.3: Semantik Mutasi State: `setValue` vs `patchValue`
Bedakan secara presisi mekanisme internal `setValue()` dan `patchValue()`. Mengapa memanggil `setValue()` dengan payload parsial memicu kompilasi atau runtime error pada *strictly typed forms*? Kapan parameter `{ emitEvent: false, onlySelf: true }` wajib digunakan dalam sistem skala enterprise untuk mencegah cascade effect?

### Soal 1.4: Eksekusi Pipeline Validator Sinkron vs Asinkron
Jelaskan urutan deterministik eksekusi validasi di Angular ketika sebuah `FormControl` memiliki kombinasi `ValidatorFn` dan `AsyncValidatorFn`. Mengapa validator asinkron tidak akan pernah dieksekusi jika validator sinkron mengembalikan error? Uraikan siklus status kontrol dari `PENDING`, `INVALID`, hingga `VALID`.

### Soal 1.5: Granularitas Kontrol via `updateOn`
Jelaskan perbedaan arsitektur event-listener internal saat mengonfigurasi property `updateOn` dengan nilai `'change'`, `'blur'`, atau `'submit'` pada tingkat `FormControl` vs `FormGroup`. Bagaimana trade-off penggunaan `updateOn: 'blur'` terhadap beban CPU Change Detection dan payload transmisi jaringan pada validasi asinkron?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Infinite Loop pada Reactive Feedback Cycles
Perhatikan pola kode berikut yang sering ditemui pada sistem enterprise:
```typescript
this.form.get('sourceCurrency')!.valueChanges.subscribe(val => {
  const converted = this.exchangeRateService.convert(val);
  this.form.get('targetCurrency')!.setValue(converted);
});

this.form.get('targetCurrency')!.valueChanges.subscribe(val => {
  const converted = this.exchangeRateService.reverseConvert(val);
  this.form.get('sourceCurrency')!.setValue(converted);
});
```
Jelaskan mekanisme internal yang memicu `Maximum call stack size exceeded` pada Angular Forms engine. Bagaimana Anda merekayasa ulang arsitektur sinkronisasi dua arah ini menggunakan RxJS operator transisional (`distinctUntilChanged`, `emitEvent: false`, atau custom stream) tanpa merusak integritas event emitter Angular?

### Soal 2.2: Memory Leak dan Dynamic Unsubscription pada `FormArray`
Ketika sebuah form dinamis menambahkan dan menghapus kontrol secara terus-menerus pada `FormArray`, developer sering mengikat `valueChanges` dari child control ke Observable stream tanpa teardown logic yang memadai. Mengapa `removeAt()` pada `FormArray` tidak secara otomatis menghancurkan (garbage-collect) subscriber internal pada `control.valueChanges`? Rancang pola pencegahan kebocoran memori enterprise menggunakan `takeUntilDestroyed` atau `Subject` scoping.

### Soal 2.3: Silent Failure pada Custom CVA dengan `ChangeDetectionStrategy.OnPush`
Sebuah komponen kustom (misal: *Rich Text Editor*) mengimplementasikan `ControlValueAccessor`. Komponen induk menggunakan form reaktif untuk memodifikasi nilai kontrol tersebut secara asinkron via `patchValue()`. Komponen kustom telah dikonfigurasi dengan `ChangeDetectionStrategy.OnPush`. Mengapa pemanggilan `writeValue(obj)` sering gagal me-render ulang visual view meskipun data telah masuk ke internal property komponen? Tunjukkan titik injeksi dependency internal yang hilang untuk mengatasi isu ini.

### Soal 2.4: Race Condition pada Async Validation Engine
Sebuah field registrasi username divalidasi via backend API menggunakan `AsyncValidatorFn`. Jika pengguna mengetikkan "admin" lalu dengan cepat menghapusnya dan mengetikkan "administrator", apa yang terjadi pada *microtask/macrotask queue* form engine jika validator mengembalikan Observable HTTP tanpa isolasi pembatalan? Mengapa operator `switchMap` di dalam validator kustom menjadi krusial untuk mencegah stale HTTP response menimpa status validitas kontrol yang lebih baru?

### Soal 2.5: Cross-Field Validation & Status Desynchronization
Diberikan sebuah `FormGroup` dengan dua kontrol: `startDate` dan `endDate`. Validator cross-field diletakkan pada level `FormGroup`. Ketika pengguna mengubah `startDate` sehingga nilainya menjadi lebih besar daripada `endDate`, `FormGroup` berstatus `INVALID`. Namun, UI library mengecek status validitas pada level individu (`endDate.errors`). Mengapa `endDate.valid` tetap bernilai `true` secara internal? Bagaimana cara mendesain validator yang secara atomik mendistribusikan error ke kontrol spesifik tanpa memicu cyclic notification?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Performa pada Financial Grid Entry Form
**Konteks**: Sistem *Financial Reporting* korporat menampilkan tabel mutasi anggaran yang direpresentasikan oleh sebuah `FormArray` berisi 5.000 baris. Masing-masing baris memiliki 12 `FormControl` (Total: 60.000 kontrol aktif). Setiap sel melakukan perhitungan pajak secara otomatis dan validasi format numerik. 
**Insiden**: Saat akuntan mengetikkan angka pada satu sel di baris 4.500, terjadi input lag masif (frame drop hingga 4 FPS, CPU spike 100% pada main thread). Profiling DevTools menunjukkan bahwa pengetikan 1 karakter memicu eksekusi dirty-checking dan re-validasi pada seluruh form tree secara rekursif dari root.

**Pertanyaan Diagnostik & Solusi:**
1. Mengapa struktur hierarki default `FormGroup` dan `FormArray` di Angular memicu propagasi event ke atas (*bubbling*) hingga ke root form?
2. Bagaimana Anda merestrukturisasi arsitektur form ini agar mutasi pada satu sel tidak mengeksekusi change detection atau validasi pada baris lainnya? (Gunakan konsep kombinasi `updateOn`, isolasi sub-tree form, custom state bridging via Signals, atau virtual rendering).

---

### Skenario B: Race Condition dan State Hijacking pada Checkout Multi-Langkah
**Konteks**: Aplikasi logistik enterprise memiliki checkout wizard 3 tahap. Pada Tahap 2, terdapat field "Voucher Code" dengan async validator yang mengecek ketersediaan promo via gRPC-Web gateway (membutuhkan waktu respons bervariasi: 200ms - 2500ms). Form level 2 mengikat tombol "Lanjut ke Pembayaran" ke properti `form.valid`.
**Insiden**: Pengguna memasukkan kode promo `SUPER100` (respons backend lambat: 2000ms), lalu menyadari salah ketik dan langsung menggantinya dengan `DISC10` (respons backend cepat: 300ms). Respons `DISC10` kembali terlebih dahulu dan menyatakan valid. Namun, 1,7 detik kemudian, respons dari `SUPER100` baru kembali dan mengembalikan pesan "Voucher Kadaluarsa". Status form seketika berubah menjadi `INVALID`, padahal field input visual menampilkan `DISC10`.

**Pertanyaan Diagnostik & Solusi:**
1. Bedah alur konkurensi Observable pada `AsyncValidatorFn` yang menyebabkan anomali out-of-order execution ini.
2. Tuliskan implementasi factory function `AsyncValidatorFn` berstandar produksi yang memanfaatkan `Subject`, `switchMap`, dan `timer` (debouncing) untuk menjamin determinisme validasi form model dan pembatalan payload network yang usang (*stale*).

---

### Skenario C: Dynamic Configurator Schema Builder & Tree Detachment
**Konteks**: Perusahaan telekomunikasi memiliki platform provisioning router. Spesifikasi form sepenuhnya dikirim oleh backend dalam format dynamic JSON schema (berisi *conditional dependencies*, misal: jika protocol == 'BGP', render 20 kontrol routing; jika protocol == 'STATIC', render 4 kontrol). 
Ketika switch protokol terjadi, kontrol lama dihapus dari form tree menggunakan `.removeControl()` dan kontrol baru diinjeksi via `.addControl()`.
**Insiden**: Pada skenario pengguna beralih protokol berulang kali, aplikasi mengalami degradasi memori progresif (*memory leak*) hingga browser tab crash. Selain itu, nilai yang telah diketikkan pengguna pada sub-form sebelumnya hilang total saat switch kembali, menyebabkan UX disaster.

**Pertanyaan Diagnostik & Solusi:**
1. Analisis mengapa penambahan dan penghapusan kontrol secara dinamis via dynamic schema builders rentan meninggalkan zombie subscription dan detached DOM nodes di Angular forms engine.
2. Tentukan trade-off arsitektur: Apakah lebih baik melakukan mutasi dinamis pada `FormGroup` via `addControl`/`removeControl`, atau menggunakan pola *Form Disabling/Detaching* (`control.disable({ emitEvent: false })`) yang dipadukan dengan persistent state cache? Berikan justifikasi teknis berdasarkan stabilitas memori dan integritas validasi.

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise Matrix Configurator dengan Custom CVA & Dynamic Asynchronous Validation Engine

#### Problem Statement
Anda ditugaskan merancang modul inti form untuk sistem perbankan korporat: **"Tiered Transaction Limit Matrix Engine"**. Form ini memungkinkan Admin menetapkan batas transaksi bertingkat berdasarkan kombinasi *User Role*, *Transaction Type*, dan *Currency*. Form harus menangani dependensi antar-field yang kompleks, integrasi custom UI via `ControlValueAccessor`, dan verifikasi anti-tampering secara asinkron.

#### Functional Requirements
1. **Strongly Typed Master Form**:
   - Master form harus fully strictly-typed, merepresentasikan struktur data:
     ```typescript
     interface MatrixConfig {
       matrixId: string;
       effectiveDate: Date;
       tiers: Array<{
         roleId: string;
         currency: 'USD' | 'EUR' | 'IDR';
         minLimit: number;
         maxLimit: number;
         dailyCap: number;
       }>;
       auditTrail: {
         reason: string;
         approverEmail: string;
       };
     }
     ```
2. **Custom Component via ControlValueAccessor**:
   - Bangun komponen `CurrencyLimitInputComponent` yang mengimplementasikan `ControlValueAccessor`.
   - Komponen harus menerima input numerik murni, namun menampilkan visual terformat (misal: memisahkan ribuan, prefix simbol mata uang dinamis sesuai sibling control `currency`).
   - Komponen harus merespons disable state secara native dan mengimplementasikan `Validator` interface untuk internal min/max sanitization.
   - Komponen harus menggunakan `ChangeDetectionStrategy.OnPush`.
3. **Advanced Async Matrix Validator**:
   - Terapkan validator tingkat `FormArray` (`tiers`) yang memverifikasi ke backend bahwa rentang `[minLimit, maxLimit]` tidak overlap dengan konfigurasi tier aktif lainnya di database bank.
   - Request verifikasi harus memiliki mekanisme *debounce* sebesar 400ms dan *cancellation* via `switchMap` terhadap request yang masih berjalan saat user merevisi data tier.
4. **Cross-Field Math Integrity**:
   - Pada setiap baris tier, harus ada validasi sinkron: `minLimit < maxLimit` dan `maxLimit <= dailyCap`. Error harus dipetakan tepat pada kontrol `maxLimit` dan `dailyCap` tanpa menyebabkan re-render tak terkendali pada parent form.

#### Technical Constraints
- Dilarang keras menggunakan tipe `any`, `UntypedFormGroup`, atau `UntypedFormArray`.
- Menggunakan Angular standalone component pattern modern.
- Wajib menggunakan `ChangeDetectionStrategy.OnPush` di semua level komponen.
- Hindari recursive subscription loops pada event sync. Semua logic side-effect harus terisolasi menggunakan RxJS pipe deklaratif.
- Alokasi memory leak safe: Semua subscription manual (jika ada) harus dihentikan via `DestroyRef` / `takeUntilDestroyed`.

#### Expected Deliverables
1. **Arsitektur Tipe Data**: Definisi interface dan deklarasi Form Type (`FormGroup<{...}>`).
2. **Implementasi CVA**: Kode lengkap `CurrencyLimitInputComponent` yang menangani CVA + Validator interface + OnPush markForCheck mechanism.
3. **Async Cross-Row Validator**: Implementasi pure function `AsyncValidatorFn` untuk mitigasi overlap tier limit via backend simulation (RxJS `of`, `delay`, `switchMap`).
4. **Form Initialization Factory**: Service/komponen yang merakit seluruh form dengan lazy initialization, konfigurasi `updateOn`, dan sinkronisasi reaktif antar field.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Mekanisme inferensi TypeScript pada Angular Strongly Typed Forms (`FormGroup`, `FormControl`, `FormArray`, `FormRecord`).
- [ ] Siklus internal 4 metode `ControlValueAccessor` dan integrasinya dengan `NG_VALUE_ACCESSOR` provider multi-token.
- [ ] Alur propagasi event form (`statusChanges`, `valueChanges`) serta implikasi parameter `{ emitEvent, onlySelf }` terhadap performa dan cascading trigger.
- [ ] Algoritma eksekusi validasi Angular: Mengapa validasi sinkron memblokir validator asinkron dan bagaimana state `PENDING` diproses.
- [ ] Pengaruh Change Detection Strategy (`Default` vs `OnPush`) terhadap pembaruan visual form controls saat data dimutasi via API programmatic.
- [ ] Mengapa operator RxJS `switchMap` mutlak diperlukan pada validasi asinkron untuk mencegah HTTP race condition.
- [ ] Dampak memory allocation dari dynamic `FormArray` pada enterprise dashboard dan bagaimana strategi isolasi tree bekerja.

### Saya tidak perlu menghafal:
- [ ] Syntax exact Regex RFC 5322 untuk validasi email kompleks (gunakan library teruji atau standar platform).
- [ ] Urutan parameter numerik legacy dari signature constructor Angular Forms v2-v13 yang telah didegradasi.
- [ ] Seluruh daftar kode ISO currency untuk masking formatter; delegasikan parsing display ke `Intl.NumberFormat`.

### Saya harus bisa melakukan:
- [ ] Mengembangkan custom form control tingkat produksi dari nol yang mengimplementasikan `ControlValueAccessor` dan `Validator` interface dengan dukungan penuh `OnPush`.
- [ ] Melakukan profiling runtime Change Detection untuk mendeteksi bottleneck form reaktif berskala besar menggunakan Chrome DevTools Profiler & Angular DevTools.
- [ ] Membangun custom synchronous dan asynchronous validator kompleks yang menangani dependensi cross-field tanpa memicu cyclic notification loops.
- [ ] Memprogram dynamic enterprise forms berorientasi schema (metaprogramming form builder) yang bebas kebocoran memori menggunakan `takeUntilDestroyed` dan clean teardown lifecycles.
- [ ] Mengintegrasikan Angular Reactive Forms secara aman dengan state management eksternal atau modern Angular Signals.