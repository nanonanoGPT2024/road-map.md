# BAB 03: Quiz, Challenge, & Knowledge Check
**Arsitektur Komponen Tingkat Lanjut & Komposisi UI**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Mekanisme Content Projection vs Dynamic Component Loading:**  
   Jelaskan perbedaan mendasar antara proyeksi konten via `<ng-content>` dan instansiasi dinamis berbasis `ViewContainerRef.createComponent()`. Tinjau dari perspektif kepemilikan siklus hidup (*lifecycle ownership*), resolusi *Dependency Injection* (DI), dan konsumsi memori ketika komponen di-*destroy*.

2. **Perbedaan Siklus Hidup `ngAfterContentInit` vs `ngAfterViewInit`:**  
   Mengapa modifikasi *state* lokal komponen di dalam `ngAfterViewInit` berisiko tinggi memicu error `ExpressionChangedAfterItHasBeenCheckedError` di mode pengembangan, sedangkan modifikasi yang sama di `ngAfterContentInit` umumnya aman? Jelaskan aliran eksekusi *Change Detection* (CD) top-down yang melatarbelakangi fenomena ini.

3. **Directive Composition API (`hostDirectives`):**  
   Angular 15 memperkenalkan *Directive Composition API*. Bandingkan pendekatan ini dengan pewarisan kelas komponen klasik (*class inheritance*) dan *TypeScript Mixins*. Sebutkan dua keterbatasan struktural dari `hostDirectives` yang tidak dapat dilanggar saat mengonfigurasi komponen *standalone*.

4. **Struktural Directives dan Micro-syntax Desugaring:**  
   Uraikan proses transformasi (*desugaring*) yang dilakukan oleh compiler Angular terhadap sintaks struktural `*myCustomDirective="let item of items; index as i"`. Struktur DOM dan node virtual apa saja (`ng-template`, `ViewContainerRef`) yang dihasilkan di balik layar?

5. **Signal Queries (`viewChild`, `contentChild`) vs Legacy Decorators (`@ViewChild`, `@ContentChild`):**  
   Bagaimana transisi dari decorator klasik ke *signal-based queries* di Angular modern mengubah paradigma timing ketersediaan referensi DOM/komponen? Analisis perbedaannya terhadap eksekusi awal sebelum *render phase* berlangsung.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Resolusi Hierarki DI pada Proyeksi Konten Bersarang (*Projected Content Injection Context*):**  
   Diberikan struktur: Komponen `HostComponent` memproyeksikan `ChildComponent` ke dalam `ContainerComponent`. Jika `ChildComponent` menginjeksi sebuah Service token `CONFIG_SERVICE`, dari injector manakah Angular menyelesaikan dependensi tersebut: `HostComponent`, `ContainerComponent`, atau `ElementInjector` terdekat dari *declaration site*? Jelaskan rute resolusi injector (*NodeInjector* vs *EnvironmentInjector*).

2. **Memory Leak pada Dynamic Component Creation:**  
   Sebuah *Dynamic Modal Service* membuat komponen secara dinamis menggunakan `createComponent(ModalComponent, { environmentInjector })`. Walaupun elemen modal dihapus dari DOM menggunakan manipulasi *renderer*, konsumsi memori aplikasi tetap meningkat secara konsisten. Analisis di mana letak kesalahan arsitektur tersebut dan jelaskan peran `ComponentRef.destroy()` serta detasemen dari `ApplicationRef`.

3. **Debugging Circular Dependency pada `hostDirectives`:**  
   Ketika mengomposisikan *Directive* `TooltipDirective` ke dalam `ButtonComponent` menggunakan `hostDirectives: [TooltipDirective]`, dan `TooltipDirective` secara bersamaan menginjeksi `ButtonComponent` sebagai host context, aplikasi mengalami *runtime error: Cannot access 'ButtonComponent' before initialization*. Bagaimana Anda memecahkan dependensi sirkular ini tanpa mengorbankan isolasi logika?

4. **Multi-slot Content Projection dengan Selektor Kompleks:**  
   Diberikan template:
   ```html
   <ng-content select="[card-header]"></ng-content>
   <ng-content select="app-badge"></ng-content>
   <ng-content></ng-content>
   ```
   Jika konsumen melemparkan `<app-badge card-header>Pro</app-badge>`, ke slot manakah elemen tersebut jatuh? Jelaskan algoritma *slot-matching order* internal Angular dan implikasinya jika terdapat elemen fallback default.

5. **`TemplateRef` Context Typing dan Generics Safety:**  
   Mengapa secara default data yang diekspos melalui `TemplateRef` context (`$implicit`) sering kali kehilangan *type-safety* (terbaca sebagai `any`) pada template konsumen? Mekanisme apa yang harus diimplementasikan pada custom structural directive (misal: static guard `ngTemplateContextGuard`) agar Angular Language Service dapat melakukan inferensi tipe data secara ketat (*strict template type checking*)?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Performa pada Dynamic Widget Dashboard
Sebuah platform analitik finansial memuat dashboard yang dapat dikonfigurasi pengguna dengan ratusan widget dinamis. Setiap widget di-render menggunakan `ViewContainerRef.createComponent()`.  
* **Insiden:** Ketika pengguna beralih antar *workspace* dengan cepat atau saat data pasar saham berkedip via WebSocket (100 pesan/detik), UI mengalami drop frame parah (< 15 FPS) dan browser tab kerap kali *crash* akibat out-of-memory.  
* **Pertanyaan Diagnostik:**  
  1. Bagaimana Anda mengaudit siklus hidup komponen dinamis ini untuk mendeteksi apakah *ViewRef* lama masih terdaftar di Change Detection Tree?  
  2. Pendekatan arsitektur apa yang harus diambil untuk mengganti instansiasi dinamis naïf agar Change Detection terisolasi per widget, dan bagaimana peran `EmbeddedViewRef` / Virtual Scrolling di sini?

### Skenario B: Race Condition pada Multi-Step Wizard Menggunakan Signals
Sebuah modul checkout enterprise mengimplementasikan dynamic form wizard multi-step. Komponen induk mengontrol transisi form via sinyal `$currentStepIndex` dan memproyeksikan form step yang sesuai.  
* **Insiden:** Pada step 3 (Verifikasi Pembayaran), input step bergantung pada data asynchronous yang diambil di step 2. Terjadi kondisi balapan (*race condition*) di mana Signal Query `contentChildren` membaca *state* komponen anak sebelum form step 3 selesai menginisialisasi sinyal internalnya. Hal ini mengakibatkan form terkirim dengan payload `undefined` secara acak.  
* **Pertanyaan Diagnostik:**  
  1. Identifikasi cacat arsitektur dalam sinkronisasi antar-komponen via signals saat dikombinasikan dengan proyeksi konten dinamis (`ng-template` vs dynamic rendering).  
  2. Rancang ulang state flow menggunakan `effect()`, `computed()`, atau alur data deklaratif unirectional murni agar pembacaan nilai tidak bergantung pada waktu resolusi DOM/query lifecycle.

### Skenario C: Trade-off Arsitektur Design System (Directives vs inheritance)
Tim arsitektur frontend sedang membangun *Design System Core* internal berskala besar (digunakan oleh 40+ micro-frontend). Terdapat perdebatan keras:  
* **Kubu A:** Mengusulkan *Base Component Inheritance* (`class CustomButton extends BaseButton`) untuk mendistribusikan fungsionalitas seperti *Ripple*, *Accessibility (ARIA)*, *Theming*, dan *Tracking Analytics*.  
* **Kubu B:** Mengusulkan *Headless Component Architecture* yang dikombinasikan secara modular menggunakan *Directive Composition API* (`hostDirectives`).  
* **Pertanyaan Diagnostik:**  
  Evaluasi trade-off dari kedua pendekatan tersebut ditinjau dari sisi:  
  1. Dampak terhadap *Tree-shaking* dan ukuran bundle akhir.  
  2. Fleksibilitas saat sebuah komponen host membutuhkan ARIA dan Tracking, namun harus menolak efek Ripple.  
  3. Berikan rekomendasi arsitektur final Anda secara objektif beserta mitigasi batasannya.

---

## 4. Chapter Challenge

**Tantangan Praktis: Headless, Dynamic, & Accessible Overlay/Dialog System**

### Problem Statement
Sebagian besar library dialog pihak ketiga memiliki dependensi berat pada DOM wrapper eksternal, sulit dikustomisasi tampilannya, dan mengabaikan isolasi *Change Detection*. Anda diminta membangun arsitektur sistem Overlay/Dialog berbasis *headless architecture* murni dari nol untuk Design System internal enterprise.

### Requirements
1. **Dynamic Instantiation Engine:**  
   Bangun `OverlayService` yang mampu membuka komponen arbitrary ke dalam layer global overlay root menggunakan `ViewContainerRef` dan `EnvironmentInjector` modern tanpa melibatkan library UI eksternal (seperti Angular CDK Overlay).
2. **Compound & Headless UI Directives:**  
   Gunakan *Directive Composition API* untuk menyediakan fungsionalitas:
   * `FocusTrapDirective`: Mengunci siklus navigasi Tab di dalam overlay.
   * `EscapeKeyDirective`: Menutup overlay saat tombol `Esc` ditekan.
   * `A11yDialogDirective`: Menghubungkan atribut ARIA (`aria-modal="true"`, `role="dialog"`, `aria-labelledby`, `aria-describedby`) secara otomatis ke elemen host.
3. **Reactive State & Two-way Binding via Signals:**  
   Gunakan Angular Signals (`input()`, `output()`, atau signal model) untuk menangani *open/close state* dan pertukaran data (passing payload ke dialog dan menerima balikan data saat dialog di-*close*).
4. **Content & Template Flexibility:**  
   Dialog harus mendukung rendering berbasis `Type<T>` (komponen dinamis utuh) MAUPUN `TemplateRef<C>` (template kustom inline) dengan type-safe context.

### Constraints
* **Standar Angular:** Angular 17/18+ (Wajib Standalone Components & Directives).
* **Strict Mode:** Wajib lulus `noImplicitAny` dan strict template checking.
* **Zero CDK:** Dilarang mengimpor `@angular/cdk`. Seluruh trap fokus dan komputasi overlay harus dibuat secara modular menggunakan Angular core API native.
* **Clean Destruction:** Tidak boleh meninggalkan *orphan DOM nodes*, memory leak pada router navigation, atau lingering event listeners di window.

### Expected Output
1. File struktur kode arsitektural:
   * Directives (`FocusTrapDirective`, `A11yDialogDirective`, dll).
   * Service (`OverlayService`, `OverlayRef`).
   * Component (`DialogContainerComponent`).
2. Kode TypeScript demonstrasi implementasi end-to-end yang bersih dan terdokumentasi rapi.
3. Contoh konsumsi pemanggilan dialog oleh end-developer (baik mode Komponen maupun mode `TemplateRef`).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan siklus hidup dan dependensi hierarki antara Proyeksi Konten (`<ng-content>`) dan Tampilan Tertanam (`ViewContainerRef` / `TemplateRef`).
- [ ] Titik kritis eksekusi Change Detection yang memicu `ExpressionChangedAfterItHasBeenCheckedError` pada lifecycle views.
- [ ] Cara kerja internal *Directive Composition API* (`hostDirectives`), termasuk mekanisme *Input/Output mapping*.
- [ ] Konsep *Headless UI pattern* di Angular dan mengapa komposisi lebih unggul daripada pewarisan kelas (*inheritance*).
- [ ] Perbedaan rute resolusi dependensi antara *ElementInjector* dan *EnvironmentInjector*.
- [ ] Mekanisme deteksi Signal Queries (`viewChild`, `contentChild`) dan interaksinya dengan reaktivitas fine-grained.

### Saya tidak perlu menghafal:
- [ ] Kode implementasi internal compiler Angular untuk parsing micro-syntax `*ngFor` atau `*ngIf`.
- [ ] Seluruh key-code legacy pada event keyboard (gunakan standar modern `event.key === 'Escape'`).
- [ ] Konfigurasi internal webpack/esbuild untuk optimasi tree-shaking directive secara manual.

### Saya harus bisa melakukan:
- [ ] Mengonversi kode berbasis class inheritance yang kaku menjadi struktur modular menggunakan `hostDirectives`.
- [ ] Membangun custom structural directive lengkap dengan `TemplateRef`, `ViewContainerRef`, dan `ngTemplateContextGuard` berkemampuan tipe data generik ketat.
- [ ] Mengisolasi komponen dinamis dari memory leak dengan mengimplementasikan pelepasan *ViewRef* dan pembersihan injektor secara deterministik.
- [ ] Mendiagnosis dan memperbaiki inkonsistensi data UI yang diakibatkan oleh tabrakan slot pada multi-slot content projection.
- [ ] Mengimplementasikan pattern *Compound Components* di Angular menggunakan Signal queries modern.