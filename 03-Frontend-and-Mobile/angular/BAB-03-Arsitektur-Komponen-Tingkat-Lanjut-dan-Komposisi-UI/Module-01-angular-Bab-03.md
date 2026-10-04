# Bab 03 Module 01: Arsitektur Komponen Tingkat Lanjut & Komposisi UI

---

## SEKSI 01 — IDENTITAS MODUL

* **Domain Kurikulum:** `03-Frontend-and-Mobile`
* **Jalur Spesialisasi:** `Angular Enterprise Architecture & Performance Engineering`
* **Modul:** `Bab 03 Module 01`
* **Topik/Judul:** `Arsitektur Komponen Tingkat Lanjut & Komposisi UI`
* **Tingkat Kompleksitas:** `Tingkat Lanjut (Advanced / Staff Engineer Level)`
* **Prasyarat Pengetahuan:**
  * Pemahaman mendalam tentang Angular Component Lifecycle Hooks (`OnInit`, `AfterViewInit`, `OnDestroy`).
  * Kemahiran dalam TypeScript Generics, Mapped Types, dan Strict Null Checks.
  * Pemahaman mendasar tentang Document Object Model (DOM) Abstraction Layer di Angular (`ElementRef`, `Renderer2`).
  * Konsep dasar Reactive Programming menggunakan RxJS (`Observables`, `Subjects`) dan Angular Signal Primitives (`signal`, `computed`, `effect`).
* **Dependensi Lingkungan Runtime:**
  * Angular CLI: `>= 17.x / 18.x` (Menargetkan arsitektur Standalone Components & Signal inputs/queries).
  * Node.js Runtime: `>= 20.x LTS`
  * TypeScript Compiler Target: `ES2022` / `strict: true`

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, Anda dituntut dan dinilai mampu untuk:

1. **Mendekonstruksi dan Menguasai Komposisi Tingkat Lanjut (Content Projection):** Mengimplementasikan Multi-slot Content Projection kompleks menggunakan selektor mutakhir, fallbacks (default content), serta transklusi berbasis programmatic menggunakan `ngProjectAs` dan dynamic templates.
2. **Mengabstraksi Perilaku Komponen via Directives:** Memanfaatkan Directive Composition API (`hostDirectives`) untuk mereduksi duplikasi kode, memfasilitasi arsitektur *mixins* tanpa hierarki pewarisan kelas (*inheritance*) yang rapuh (*fragile base class problem*).
3. **Mengontrol DOM Abstraction Layer Secara Deterministik:** Membedah perbedaan teknis, siklus hidup, dan implikasi performa antara `ViewContainerRef`, `TemplateRef`, `ComponentRef`, dan `EmbeddedViewRef` untuk dynamic component instantiation berkecepatan tinggi.
4. **Menerapkan Modern Signal Queries:** Menggantikan `@ViewChild`, `@ViewChildren`, `@ContentChild`, dan `@ContentChildren` warisan (*legacy decorators*) dengan fungsi `viewChild()`, `viewChildren()`, `contentChild()`, dan `contentChildren()` berbasis Signals untuk reaktivitas nir-overhead siklus hidup Angular.
5. **Membangun Headless UI Design Systems:** Mengembangkan pustaka komponen berskala enterprise dengan memisahkan representasi visual (Skin/Presentation) dan state machine perilaku (Headless/Behaviors) yang tahan uji terhadap audit aksesibilitas (WCAG 2.1 AA/AAA dan WAI-ARIA APG).

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Komposisi di Atas Pewarisan (Composition over Inheritance)
Dalam perancangan sistem enterprise skala besar, kesalahan fatal yang paling sering dijumpai adalah pembuatan hierarki kelas komponen bertingkat:
`BaseComponent -> BaseInputComponent -> BaseSelectComponent -> SearchableSelectComponent`. 
Pola pewarisan ini menciptakan *tight coupling*, mendistribusikan dependensi siklus hidup secara tersembunyi, dan memaksa subclass mewarisi dependensi yang tidak dibutuhkannya.

Mental model modern Angular mendikte: **Komponen adalah orchestrator representasi visual, sedangkan direktif adalah unit atomik dari perilaku (behavior).** Jika sebuah tombol membutuhkan kemampuan keyboard navigation, focus trapping, dan analytics tracking, kita tidak membuat `AnalyticsKeyboardFocusTrappedButtonComponent`. Kita menyusun direktif-direktif fungsional tersebut ke dalam satu komponen menggunakan **Directive Composition API**.

```
[ Mental Model: Inheritance vs Composition ]

Inheritance (Anti-Pattern):
  +-----------------------------------+
  |           BaseComponent           | (State, DI, Lifecycle)
  +-----------------------------------+
                   |
                   v
  +-----------------------------------+
  |        BaseButtonComponent        | (Mewarisi seluruh dependensi)
  +-----------------------------------+
                   |
                   v
  +-----------------------------------+
  |      IconButtonComponent          | (Rapuh, sulit diuji secara terisolasi)
  +-----------------------------------+

Composition (Arsitektur Target):
  +---------------------------------------------------------------+
  |                     CustomButtonComponent                     |
  |  +----------------+  +-----------------+  +----------------+  |
  |  | KeyboardNavDir |  | FocusTrapDir    |  | TelemetryDir   |  |
  |  +----------------+  +-----------------+  +----------------+  |
  +---------------------------------------------------------------+
```

### Abstraksi DOM: Dari Manipulasi Langsung Menuju Node Virtual Angular
Pengembang pemula memperlakukan DOM browser sebagai target manipulasi langsung melalui `document.getElementById` atau langsung menyentuh `elementRef.nativeElement`. Mental model yang harus ditanamkan:
* **DOM Browser hanyalah sebuah proyeksi.** Angular berjalan di atas layer abstraksi runtime internal (`LView`, `TView`).
* Komponen tidak merender HTML murni; komponen membangun dan memodifikasi struktur pohon node Angular (`LContainer`, `ViewContainerRef`).
* Template adalah instruksi blueprint (`TemplateRef`), sedangkan instance yang dialokasikan di memori adalah view tersemat (`EmbeddedViewRef`) atau view komponen (`ComponentRef`). Manipulasi UI yang aman, deterministik, dan bebas kebocoran memori hanya terjadi ketika operasi dilakukan melalui abstraksi `ViewContainerRef`.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah representasi siklus hidup kompilasi, resolusi struktural, dan alur dynamic component instantiation di Angular runtime.

```
+---------------------------------------------------------------------------------------+
| FASE 1: TEMPLATE DECLARATION & PROJECTION RESOLUTION                                  |
|                                                                                       |
|  Parent Template                                                                      |
|  +---------------------------------------------------------------------------------+  |
|  | <app-modal>                                                                     |  |
|  |   <!-- Transcluded via CSS Selector Slot -->                                    |  |
|  |   <div modal-header>Header Content</div>                                        |  |
|  |                                                                                 |  |
|  |   <!-- Transcluded via ngProjectAs Dynamic Mapping -->                          |  |
|  |   <ng-container ngProjectAs="modal-body">                                       |  |
|  |     <ng-template #dynamicTpl let-data="item">                                   |  |
|  |        <span>Item Value: {{ data.name }}</span>                                 |  |
|  |     </ng-template>                                                              |  |
|  |   </ng-container>                                                               |  |
|  | </app-modal>                                                                    |  |
|  +---------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
| FASE 2: INTERNAL RUNTIME EVALUATION (Ivy Engine)                                     |
|                                                                                       |
|   AppModalComponent (TView / LView Structure)                                         |
|   +-------------------------------------------------------------------------------+   |
|   | Host Node: <app-modal>                                                        |   |
|   |                                                                               |   |
|   | 1. Evaluasi Slots:                                                            |   |
|   |    <header><ng-content select="[modal-header]"></ng-content></header>         |   |
|   |                                                                               |   |
|   | 2. Deteksi Signal Queries:                                                    |   |
|   |    tplSignal = contentChild.required<TemplateRef<any>>('dynamicTpl');         |   |
|   |    containerSignal = viewChild.required('targetAnchor', {read: ViewContainerRef});|
|   |                                                                               |   |
|   | 3. Directive Composition Assembly (hostDirectives):                           |   |
|   |    HostBindings -> CdkTrapFocus -> AriaDescribedByDirective                  |   |
|   +-------------------------------------------------------------------------------+   |
+---------------------------------------------------------------------------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
| FASE 3: DYNAMIC EMBEDDING & INSTANTIATION                                             |
|                                                                                       |
|  +----------------------------------+        Instantiate Embedded View                |
|  | TemplateRef<ModalContext<T>>     | -------------------------------------+          |
|  +----------------------------------+                                      |          |
|                                                                            v          |
|  +----------------------------------+   Insert View    +----------------------------+ |
|  | ViewContainerRef                 | <--------------- | EmbeddedViewRef<T>         | |
|  | (Structural Insertion Anchor)    |                  | LView Data Array:          | |
|  +----------------------------------+                  | - Context: { item: data }  | |
|                                                        | - Root Nodes: [span, text] | |
|                                                        +----------------------------+ |
|                                                                                       |
|  Angular Change Detection Pipeline Triggered via Microtask Queue                      |
|  DOM di-update tanpa bypass Change Detection Root                                     |
+---------------------------------------------------------------------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. `ViewContainerRef` vs `TemplateRef` vs `ComponentRef` vs `EmbeddedViewRef`

Untuk mengendalikan DOM pada level mahir, Anda harus membedakan objek-objek inti berikut:

* **`TemplateRef<C>`**: Representasi blueprint UI yang tidak dieksekusi secara mandiri. Berisi instruksi pembuatan node DOM beserta konteks data tipe `C`. `TemplateRef` diisolasi di luar DOM tree utama hingga secara eksplisit di-instansiasi.
* **`EmbeddedViewRef<C>`**: Instance konkret dari sebuah `TemplateRef`. Objek ini memiliki referensi ke simpul-simpul DOM fisik (`rootNodes`), status penghancuran (`destroy()`), serta konteks data reaktif (`context`) yang dapat diperbarui saat runtime.
* **`ComponentRef<C>`**: Instance komponen yang dibuat secara dinamis menggunakan runtime Ivy. Objek ini membungkus instance kelas komponen (`instance`), deteksi perubahan (`changeDetectorRef`), host node DOM (`location`), dan siklus hidupnya.
* **`ViewContainerRef`**: Anchor struktural yang terhubung secara intim dengan sebuah simpul DOM. Berperan sebagai wadah alokasi dinamis. Objek ini dapat menampung satu atau lebih View (`EmbeddedViewRef` atau `ViewRef` dari `ComponentRef`). Metode kuncinya meliputi `createEmbeddedView()`, `createComponent()`, dan `clear()`.

### 2. Multi-Slot Content Projection & `ngProjectAs`
Sistem kompilasi template Angular memproses `<ng-content>` pada waktu kompilasi (*compile-time slot assignment*). Angular mencocokkan node turunan terproyeksi dengan atribut `select` pada `<ng-content>`. 
Ketika sebuah komponen pembungkus menampung beberapa elemen perantara (misalnya `<ng-container>` wrapper yang berisi logika iterasi struktural seperti `@for`), Angular secara bawaan gagal memetakan elemen ke slot bertarget selektor atribut CSS (`[slot-name]`). 
Solusi internalnya adalah **`ngProjectAs`**: Instruksi kompilator tingkat rendah yang memaksa Angular memperlakukan node tersebut seolah-olah ia cocok dengan selektor CSS yang didefinisikan, melewati hierarki pembungkus virtual.

### 3. Directive Composition API Internals (`hostDirectives`)
Diperkenalkan pada Angular 15, `hostDirectives` dieksekusi pada level runtime compiler:
* Tidak ada relasi pewarisan JavaScript (`extends`). Instansiasi kelas terjadi secara delegasi.
* Angular mengalokasikan memori untuk direktif pada host node yang sama dengan komponen target.
* Input dan output dari host directives dapat dialias (*aliased*) atau diekspos secara selektif (*forwarded API*), mencegah polusi antarmuka publik host component.
* Siklus hidup host directives (`ngOnInit`, `ngOnDestroy`, dsb.) diikat langsung dengan host component dan dieksekusi secara deterministik sebelum siklus hidup host component berjalan.

### 4. Signal Queries vs Decorator Queries
Tabel perbandingan arsitektural mekanisme internal queries:

| Aspek | Legacy Decorators (`@ViewChild`, `@ContentChild`) | Modern Signal Queries (`viewChild()`, `contentChild()`) |
| :--- | :--- | :--- |
| **Penyelesaian Siklus Hidup** | Resolusi terjadi saat `ngAfterViewInit` / `ngAfterContentInit`. Bernilai `undefined` pada `ngOnInit`. | Resolusi reaktif. Nilai signal tersedia segera setelah view terhubung; terintegrasi dengan siklus reaktivitas Angular. |
| **Tipe Data Nilai** | Objek mentah (`T \| undefined`). Membutuhkan operator opsional chaining berulang. | `Signal<T \| undefined>` atau `Signal<T>` jika menggunakan varian `.required()`. |
| **Keterlibatan Zone.js** | Memerlukan siklus change detection penuh untuk memperbarui referensi. | Deteksi reaktif murni (fine-grained). Sinkron dengan alur deklarasi template. |
| **Kompatibilitas Zoneless** | Rentan terhadap desinkronisasi jika tidak dipicu manual. | Dirancang *native* untuk mode Zoneless (Angular 18+). |

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Isolasi Perilaku Menggunakan Headless Architecture
Headless UI adalah paradigma arsitektur di mana logika komponen—mencakup *state management*, *keyboard accessibility*, *ARIA state synchronizations*, dan *focus traps*—diabstraksi secara menyeluruh tanpa opini desain CSS apa pun.

Dalam ekosistem Angular murni, pola ini diwujudkan dengan memisahkan:
1. **Behavioral Directives**: Menyediakan kontrak antarmuka aksesibilitas (WAI-ARIA), manipulasi host attribute (`aria-expanded`, `aria-selected`, `tabindex`), dan pendengar event (`keydown`, `click`).
2. **State Models**: Dikelola murni melalui Signal primitives (`WritableSignal`, `computed`).
3. **Presentational Components**: Bertindak murni sebagai "kulit" (*skin*). Menelan direktif via `hostDirectives` dan memetakan slot template via Content Projection.

### Mekanika Kompilasi Ivy: TView, LView, dan View Injection
Ketika `ViewContainerRef.createComponent()` dipanggil saat runtime:
1. Angular memeriksa `TView` (struktur blueprint statis bersama) dari tipe komponen yang diminta.
2. Angular mengalokasikan `LView` (Logical View array) baru di memori heap, yang menyimpan dependensi, sinyal, node DOM aktual, dan referensi change detector dari instance tersebut.
3. Node DOM dari komponen yang baru dibuat dimasukkan ke dalam DOM Tree browser secara langsung sebelum atau sesudah host node dari `ViewContainerRef`, tergantung index slot yang diinstruksikan.
4. Komponen induk memegang referensi ke `ComponentRef`, yang bertanggung jawab melakukan pembersihan eksplisit melalui `ComponentRef.destroy()` saat container dibersihkan, mencegah detached DOM elements yang menyebabkan *memory leak*.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Contoh implementasi fundamental ini mengilustrasikan:
1. Directive Composition API dengan pemetaan input/output.
2. Multi-slot Content Projection tingkat lanjut menggunakan `ngProjectAs` dan fallback template.
3. Signal Queries (`viewChild`, `contentChild`).

### 1. Behavioral Directive: Click Outside Behavior
Direktif ini mengkapsulasi logika deteksi interaksi klik di luar elemen host.

```typescript
// click-outside.directive.ts
import { Directive, ElementRef, inject, output } from '@angular/core';

@Directive({
  selector: '[appClickOutside]',
  standalone: true,
})
export class ClickOutsideDirective {
  private readonly elementRef = inject(ElementRef);

  // Signal-based output API
  public readonly insideClick = output<void>();
  public readonly outsideClick = output<MouseEvent>();

  constructor() {
    // Menambahkan document listener secara manual via native event
    // Pada production code, perhatikan konteks SSR (cek platform browser)
    if (typeof window !== 'undefined') {
      window.addEventListener('pointerdown', this.handleGlobalPointerDown, { passive: true });
    }
  }

  private handleGlobalPointerDown = (event: MouseEvent): void => {
    const target = event.target as Node | null;
    if (!target) return;

    if (this.elementRef.nativeElement.contains(target)) {
      this.insideClick.emit();
    } else {
      this.outsideClick.emit(event);
    }
  };

  public ngOnDestroy(): void {
    if (typeof window !== 'undefined') {
      window.removeEventListener('pointerdown', this.handleGlobalPointerDown);
    }
  }
}
```

### 2. Presentational Component Menggunakan Directive Composition & Signal Queries

```typescript
// custom-panel.component.ts
import { 
  Component, 
  ChangeDetectionStrategy, 
  contentChild, 
  viewChild, 
  ElementRef, 
  TemplateRef,
  signal 
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { ClickOutsideDirective } from './click-outside.directive';

@Component({
  selector: 'app-custom-panel',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './custom-panel.component.html',
  styleUrl: './custom-panel.component.css',
  changeDetectionStrategy: ChangeDetectionStrategy.OnPush,
  // Mengintegrasikan directive tanpa inheritance
  hostDirectives: [
    {
      directive: ClickOutsideDirective,
      outputs: ['outsideClick: onDismissPanel'],
    }
  ]
})
export class CustomPanelComponent {
  // Signal Query untuk mengambil Template khusus Header dari Content Children
  public readonly customHeaderTpl = contentChild<TemplateRef<unknown>>('panelHeader');

  // Signal Query untuk referensi DOM internal dari template view
  public readonly bodyContainerRef = viewChild.required<ElementRef<HTMLDivElement>>('bodyContainer');

  public readonly isCollapsed = signal<boolean>(false);

  public toggleCollapse(): void {
    this.isCollapsed.update(state => !state);
  }
}
```

### 3. Template Component dengan Multi-slot & Fallbacks

```html
<!-- custom-panel.component.html -->
<div class="panel-root" [class.panel--collapsed]="isCollapsed()">
  
  <header class="panel-header">
    <!-- Slot 1: Header kustom via ContentChild template atau fallback ke default projection -->
    <ng-container *ngIf="customHeaderTpl(); else defaultHeader">
      <ng-container *ngTemplateOutlet="customHeaderTpl()!"></ng-container>
    </ng-container>
    
    <ng-template #defaultHeader>
      <div class="panel-header__default">
        <ng-content select="[panel-title]">
          <span class="fallback-title">Default Fallback Title</span>
        </ng-content>
      </div>
    </ng-template>

    <button type="button" class="panel-toggle-btn" (click)="toggleCollapse()">
      {{ isCollapsed() ? 'Expand' : 'Collapse' }}
    </button>
  </header>

  <div class="panel-body" #bodyContainer [hidden]="isCollapsed()">
    <!-- Slot 2: Body utama via standard content projection -->
    <ng-content select="[panel-body]"></ng-content>
  </div>

  <footer class="panel-footer">
    <!-- Slot 3: Footer opsional dengan default fallback content -->
    <ng-content select="[panel-footer]">
      <small class="panel-footer__fallback">Standard System Footer</small>
    </ng-content>
  </footer>

</div>
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis File: `custom-panel.component.ts`

* **Baris 19-24:**
  ```typescript
  hostDirectives: [
    {
      directive: ClickOutsideDirective,
      outputs: ['outsideClick: onDismissPanel'],
    }
  ]
  ```
  *Mekanisme:* Mengikat `ClickOutsideDirective` langsung ke host element `<app-custom-panel>`. Kompiler Angular menyambungkan siklus hidup direktif ke komponen ini.
  *Aliasing:* Output `outsideClick` milik direktif di-alias menjadi `onDismissPanel` pada antarmuka publik host. Pemanggil luar dapat menulis `<app-custom-panel (onDismissPanel)="handleClose()">` tanpa tahu ada direktif internal yang bekerja.

* **Baris 28:**
  ```typescript
  public readonly customHeaderTpl = contentChild<TemplateRef<unknown>>('panelHeader');
  ```
  *Mekanisme:* Mendeklarasikan reaktif query signal yang mencari template lokal bernilai template variable `#panelHeader` di antara anak-anak yang dioper pemanggil komponen. 
  *Keuntungan:* Tidak memerlukan lifecycle hook `AfterContentInit`. Sinyal ini dapat diamati menggunakan `computed()` atau `effect()` secara langsung.

* **Baris 31:**
  ```typescript
  public readonly bodyContainerRef = viewChild.required<ElementRef<HTMLDivElement>>('bodyContainer');
  ```
  *Mekanisme:* Mengambil referensi simpul DOM fisik `#bodyContainer` di dalam view komponen sendiri. Modifikator `.required` menjamin bahwa nilai signal tidak akan bertipe `ElementRef | undefined`, melainkan murni `ElementRef`, dan Angular melempar compile-time/runtime invariant assertion jika simpul tersebut tidak ditemukan.

---

## SEKSI 09 — STUDI KASUS NYATA (ENTERPRISE)

### Konteks Skenario Arsitektural
Sebuah platform perbankan global (Core Banking) membutuhkan sistem modal interaktif terdistribusi (*Dynamic Multi-Step Financial Transaction Dialog System*). Persyaratan tingkat tinggi mencakup:

1. **Aksesibilitas Mutlak (Fintech Compliance):** Harus patuh terhadap standar WCAG 2.1 AAA. Dialog wajib menangani dynamic focus trapping, melepaskan scroll body latar belakang, mendengarkan escape key events, dan menetapkan ARIA roles secara deterministik.
2. **Kustomisasi Layout Beragam:** Layout dialog mendukung *Multi-Slot Content Projection* dengan *Dynamic Action Injection* (tombol-tombol transaksi yang bervariasi bergantung level otorisasi pengguna).
3. **Lazy Step Rendering:** Dialog alur transfer uang memiliki beberapa step (Input Rekening -> Verifikasi OTP -> Cetak Bukti Transaksi). Step UI harus dimuat dan dihancurkan secara dinamis via programmatic template execution (`ViewContainerRef` + `TemplateRef`) untuk menjaga konsumsi memori browser perbankan tetap rendah dan aman dari kebocoran memori (memory footprint < 10MB per active dialog lifecycle).

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & PRODUCTION CODE

Berikut adalah implementasi sistem dialog perbankan headless berskala enterprise yang mengombinasikan `hostDirectives`, `ViewContainerRef`, `TemplateRef`, Multi-slot Projection, dan Signals.

### 1. Accessibility Directive: Focus Trap & ARIA Controller

```typescript
// focus-trap.directive.ts
import { 
  Directive, 
  ElementRef, 
  inject, 
  OnInit, 
  OnDestroy, 
  HostListener 
} from '@angular/core';

@Directive({
  selector: '[bankFocusTrap]',
  standalone: true,
})
export class FocusTrapDirective implements OnInit, OnDestroy {
  private readonly elementRef = inject<ElementRef<HTMLElement>>(ElementRef);
  private previouslyFocusedElement: HTMLElement | null = null;

  private readonly focusableElementsSelector = 
    'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

  public ngOnInit(): void {
    if (typeof document !== 'undefined') {
      this.previouslyFocusedElement = document.activeElement as HTMLElement;
      this.trapFocusToFirstElement();
    }
  }

  public ngOnDestroy(): void {
    if (this.previouslyFocusedElement && typeof this.previouslyFocusedElement.focus === 'function') {
      this.previouslyFocusedElement.focus();
    }
  }

  @HostListener('keydown', ['$event'])
  public handleKeydown(event: KeyboardEvent): void {
    if (event.key !== 'Tab') return;

    const focusableNodes = this.getFocusableNodes();
    if (focusableNodes.length === 0) {
      event.preventDefault();
      return;
    }

    const firstElement = focusableNodes[0];
    const lastElement = focusableNodes[focusableNodes.length - 1];

    if (event.shiftKey) {
      // Shift + Tab
      if (document.activeElement === firstElement) {
        event.preventDefault();
        lastElement.focus();
      }
    } else {
      // Tab
      if (document.activeElement === lastElement) {
        event.preventDefault();
        firstElement.focus();
      }
    }
  }

  private getFocusableNodes(): HTMLElement[] {
    const elements = this.elementRef.nativeElement.querySelectorAll(this.focusableElementsSelector);
    return Array.from(elements) as HTMLElement[];
  }

  private trapFocusToFirstElement(): void {
    setTimeout(() => {
      const nodes = this.getFocusableNodes();
      if (nodes.length > 0) {
        nodes[0].focus();
      } else {
        this.elementRef.nativeElement.focus();
      }
    }, 0);
  }
}
```

### 2. Core Dynamic Dialog Component

```typescript
// bank-dialog.component.ts
import {
  Component,
  ChangeDetectionStrategy,
  ViewContainerRef,
  TemplateRef,
  EmbeddedViewRef,
  viewChild,
  contentChild,
  input,
  output,
  signal,
  computed,
  DestroyRef,
  inject
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FocusTrapDirective } from './focus-trap.directive';

export interface DialogStepContext {
  $implicit: {
    stepIndex: number;
    transactionId: string;
  };
  actions: {
    nextStep: () => void;
    cancel: () => void;
  };
}

@Component({
  selector: 'bank-dialog',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './bank-dialog.component.html',
  styleUrl: './bank-dialog.component.css',
  changeDetectionStrategy: ChangeDetectionStrategy.OnPush,
  hostDirectives: [
    {
      directive: FocusTrapDirective
    }
  ],
  host: {
    'role': 'dialog',
    '[attr.aria-modal]': 'true',
    '[attr.aria-labelledby]': 'dialogTitleId()',
    'tabindex': '-1'
  }
})
export class BankDialogComponent {
  private readonly destroyRef = inject(DestroyRef);

  // Inputs via Signal API
  public readonly transactionId = input.required<string>();
  public readonly title = input<string>('Konfirmasi Transaksi');
  
  // Outputs via Signal API
  public readonly dialogClosed = output<{ reason: string }>();

  // Signal State Management
  public readonly currentStep = signal<number>(1);
  public readonly dialogTitleId = computed(() => `dialog-title-${this.transactionId()}`);

  // DOM Query Anchors
  private readonly dynamicContentContainer = viewChild.required('dynamicContentAnchor', { read: ViewContainerRef });
  
  // Signal Content Queries
  public readonly projectedFooterActions = contentChild<TemplateRef<unknown>>('dialogActions');

  private activeEmbeddedViewRef: EmbeddedViewRef<DialogStepContext> | null = null;

  constructor() {
    this.destroyRef.onDestroy(() => {
      this.clearDynamicView();
    });
  }

  public renderDynamicStep(stepTemplate: TemplateRef<DialogStepContext>): void {
    const container = this.dynamicContentContainer();
    
    // Clear dynamic views sebelumnya untuk mencegah kebocoran memori (Leak Isolation)
    this.clearDynamicView();

    // Context Factory
    const context: DialogStepContext = {
      $implicit: {
        stepIndex: this.currentStep(),
        transactionId: this.transactionId()
      },
      actions: {
        nextStep: () => this.goToNextStep(),
        cancel: () => this.closeDialog('USER_CANCELLED')
      }
    };

    // Alokasi instance EmbeddedViewRef ke dalam engine LContainer
    this.activeEmbeddedViewRef = container.createEmbeddedView(stepTemplate, context);
    this.activeEmbeddedViewRef.detectChanges();
  }

  public goToNextStep(): void {
    this.currentStep.update(current => current + 1);
  }

  public closeDialog(reason: string): void {
    this.clearDynamicView();
    this.dialogClosed.emit({ reason });
  }

  private clearDynamicView(): void {
    if (this.activeEmbeddedViewRef) {
      this.activeEmbeddedViewRef.destroy();
      this.activeEmbeddedViewRef = null;
    }
    const container = this.dynamicContentContainer();
    if (container) {
      container.clear();
    }
  }
}
```

### 3. Template Component: Dynamic Dialog Layout

```html
<!-- bank-dialog.component.html -->
<div class="bank-dialog-overlay" (click)="closeDialog('BACKDROP_CLICK')">
  <div class="bank-dialog-window" (click)="$event.stopPropagation()">
    
    <!-- Header Projection Slot -->
    <header class="bank-dialog-header">
      <h2 [id]="dialogTitleId()">{{ title() }}</h2>
      <ng-content select="[bank-dialog-header-tools]"></ng-content>
      <button 
        type="button" 
        class="bank-dialog-close-btn" 
        aria-label="Tutup Dialog" 
        (click)="closeDialog('CLOSE_BUTTON')">
        &times;
      </button>
    </header>

    <!-- Structural Anchor Node untuk Dynamic Content Injection -->
    <main class="bank-dialog-main">
      <ng-container #dynamicContentAnchor></ng-container>
    </main>

    <!-- Footer Actions: Content Projection dengan Structural Fallback -->
    <footer class="bank-dialog-footer">
      <ng-container *ngIf="projectedFooterActions(); else defaultActions">
        <ng-container *ngTemplateOutlet="projectedFooterActions()!"></ng-container>
      </ng-container>

      <ng-template #defaultActions>
        <div class="bank-default-actions">
          <button 
            type="button" 
            class="btn-secondary" 
            (click)="closeDialog('CANCEL')">
            Batal
          </button>
        </div>
      </ng-template>
    </footer>

  </div>
</div>
```

### 4. Consumption Tier: Smart Parent Feature Component

```typescript
// transaction-flow.component.ts
import { Component, ChangeDetectionStrategy, viewChild, TemplateRef, AfterViewInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { BankDialogComponent, DialogStepContext } from './bank-dialog.component';

@Component({
  selector: 'app-transaction-flow',
  standalone: true,
  imports: [CommonModule, BankDialogComponent],
  template: `
    <section class="flow-container">
      <h1>Transaksi Perbankan Aman</h1>
      <button type="button" class="btn-primary" (click)="launchFlow()">Mulai Transfer</button>

      @if (isDialogOpen()) {
        <bank-dialog 
          [transactionId]="currentTxId" 
          [title]="'Otorisasi Pembayaran'"
          (dialogClosed)="onDialogClose($event)">
          
          <!-- Transcluded Tool via css selector -->
          <span bank-dialog-header-tools class="badge-secure">SSL 256-Bit</span>

          <!-- Projected Template untuk Custom Actions -->
          <ng-template #dialogActions>
            <div class="custom-actions-layout">
              <span class="warning-text">Transaksi tidak dapat dibatalkan setelah eksekusi.</span>
            </div>
          </ng-template>

        </bank-dialog>
      }

      <!-- Blueprints TemplateRef untuk multi-step form views -->
      <ng-template #stepOneTpl let-ctx>
        <div class="step-view">
          <h3>Langkah 1: Verifikasi Akun (ID: {{ ctx.transactionId }})</h3>
          <p>Index Langkah: {{ ctx.stepIndex }}</p>
          <button type="button" class="btn-step" (click)="ctx.actions.nextStep()">Verifikasi dan Lanjut</button>
        </div>
      </ng-template>

      <ng-template #stepTwoTpl let-ctx>
        <div class="step-view">
          <h3>Langkah 2: Otorisasi Biometrik / PIN Token</h3>
          <button type="button" class="btn-step btn-confirm" (click)="finalizeTransaction(ctx)">Selesaikan Transaksi</button>
        </div>
      </ng-template>
    </section>
  `,
  changeDetectionStrategy: ChangeDetectionStrategy.OnPush,
})
export class TransactionFlowComponent {
  public isDialogOpen = signal<boolean>(false);
  public currentTxId = 'TX-9988231';

  // Signal View Child queries untuk referensi template
  private readonly dialogRef = viewChild(BankDialogComponent);
  private readonly stepOneTpl = viewChild.required<TemplateRef<DialogStepContext>>('stepOneTpl');
  private readonly stepTwoTpl = viewChild.required<TemplateRef<DialogStepContext>>('stepTwoTpl');

  public launchFlow(): void {
    this.isDialogOpen.set(true);
    // Jalankan eksekusi awal rendering ke modal di microtask queue berikutnya
    setTimeout(() => {
      this.dialogRef()?.renderDynamicStep(this.stepOneTpl());
    }, 0);
  }

  public finalizeTransaction(ctx: DialogStepContext['$implicit']): void {
    // Logika payload finansial enterprise
    this.dialogRef()?.closeDialog('TRANSACTION_COMPLETED');
  }

  public onDialogClose(event: { reason: string }): void {
    this.isDialogOpen.set(false);
  }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter Arsitektur | Directives Composition (`hostDirectives`) | Warisan Kelas Klasik (`extends BaseComponent`) | Dynamic Structural Injection (`ViewContainerRef`) | Multi-slot Projection (`<ng-content>`) |
| :--- | :--- | :--- | :--- | :--- |
| **Kopling Kelas (Coupling)** | **Nir-Kopling (Decoupled).** Logika dikomposisi pada saat runtime tanpa membag