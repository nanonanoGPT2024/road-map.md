# BAB 03: Arsitektur Komponen Tingkat Lanjut & Komposisi UI
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Menguasai arsitektur internal Angular Ivy runtime (`LView`, `TView`, dan mekanisme resolusi *Embedded View*).
- Merancang dan mengimplementasikan sistem *Dynamic Component Loading* terisolasi menggunakan API modern (`ViewContainerRef.createComponent`, `EnvironmentInjector`, dan standalone components) tanpa ketergantungan pada `ComponentFactoryResolver` yang telah usang.
- Menguasai pola *Structural & Attribute Directive Composition* menggunakan `hostDirectives` (Angular 15+) untuk menciptakan perilaku komponen yang modular, dapat diuji, dan mematuhi prinsip *Composition over Inheritance*.
- Mengimplementasikan pola *Multi-slot Content Projection* mutakhir dengan manipulasi runtime berbasis `TemplateRef`, `ViewContainerRef`, serta Signal Queries (`contentChild`, `contentChildren`, `viewChild`, `viewChildren`).
- Mengisolasi dan mendesain strategi styling modular menggunakan `ViewEncapsulation.ShadowDom` dan `Emulated`, serta bridging token CSS kustom untuk mengatasi tantangan tema global tanpa `::ng-deep`.
- Mengidentifikasi dan memitigasi kebocoran memori (*memory leak*), siklus deteksi perubahan yang berlebihan, dan kegagalan resolusi injeksi dependensi dinamis pada aplikasi berskala *enterprise*.

---

### 2. Prerequisite
Untuk memahami modul ini secara komprehensif, peserta wajib menguasai:
- **Angular Fundamentals**: Lifecycle hooks (`ngOnInit`, `ngAfterViewInit`, `ngOnDestroy`), Standalone Components, dan Signal primitives (`signal`, `computed`, `effect`).
- **Dependency Injection**: Hierarki `Injector`, `ElementInjector`, `EnvironmentInjector`, dan resolution modifiers (`@Host`, `@Self`, `@SkipSelf`, `@Optional`).
- **TypeScript Advanced Types**: Conditional types, utility types, generic constraints, dan metadata reflection.
- **Web Standards**: DOM Tree traversal, Web Components Custom Elements v1, dan Shadow DOM encapsulation internals.

---

### 3. Concept & Internal Architecture (Mendalam)

#### Ivy Runtime Structures: `LView` vs `TView`
Di balik abstraksi komponen, Angular Ivy merepresentasikan setiap view sebagai pasangan struktur data: **`TView`** (Template/Type View) dan **`LView`** (Logical/Instance View).
- **`TView` (Shared Static Blueprint)**: Dibuat satu kali per tipe komponen. Menyimpan struktur statis DOM, instruksi template (`ɵɵelementStart`, `ɵɵtext`, dll.), query metadata, dan blueprint dependency injection. `TView` meminimalkan konsumsi memori karena di-*share* ke seluruh instance komponen bertipe sama.
- **`LView` (Dynamic Instance Data)**: Representasi array runtime untuk setiap instance komponen di DOM. Indeks pada array ini memetakan referensi elemen DOM riil, instance komponen, state bindings, child `LView`, dan `LContainer`.

```
           +------------------------------------------------------+
           |                   TView (Static Blueprint)          |
           |  - Template Instructions                             |
           |  - Directive/Pipe Registry                           |
           |  - Injection Blueprints (TData)                      |
           +--------------------------+---------------------------+
                                      |
              Shared by all instances | (1-to-Many Relationship)
                                      v
       +------------------------------+-------------------------------+
       |                                                              |
+------v-----------------------+                               +------v-----------------------+
|    LView (Instance A)        |                               |    LView (Instance B)        |
| [0]  DOM Element (Host)      |                               | [0]  DOM Element (Host)      |
| [1]  Component Instance A    |                               | [1]  Component Instance B    |
| [2]  Binding Value (v1)      |                               | [2]  Binding Value (v2)      |
| [N]  LContainer / Child LView|                               | [N]  LContainer / Child LView|
+------------------------------+                               +------------------------------+
```

#### Dynamic View Insertion Mechanism: `ViewContainerRef` & `LContainer`
Ketika Anda menginjeksi `ViewContainerRef`, Angular mengaitkan referensi tersebut dengan indeks tertentu di dalam `LView`, yang diinisialisasi sebagai `LContainer` jika belum ada.
- `LContainer` bertindak sebagai node jangkar (*anchor comment node* `<!--container-->`) di dalam DOM nyata.
- Pemanggilan `createComponent` atau `createEmbeddedView` akan mengalokasikan child `LView` baru, menjalankannya melewati fase initial change detection, dan menyisipkan DOM nodes dari child view tersebut tepat setelah node jangkar di DOM tree.
- Secara internal, child `LView` ditautkan secara bidireksional (`PARENT_VIEW`, `NEXT`, `PREV`) ke pohon view induknya, memastikan bahwa mekanisme Change Detection traversal (`refreshView`) dapat menavigasi struktur dinamis ini dengan mulus.

#### Directive Composition API (`hostDirectives`) Internals
Sebelum Angular 15, abstraksi perilaku lintas komponen dilakukan melalui *class inheritance* atau deklarasi direktif eksplisit di template pemanggil. *Inheritance* menimbulkan coupling yang ketat, mengaburkan siklus hidup, dan melanggar prinsip *Single Responsibility*.

`hostDirectives` membedah masalah ini pada level metadata compiler:
- Compiler menggabungkan pipeline instruksi lifecycle direktif ke dalam host pipeline `TView`.
- Host component mendapatkan kepemilikan siklus hidup dari host directives yang terikat, sementara instance direktif diinstansiasi di dalam `NodeInjector` yang sama dengan host component.
- Fitur *aliasing* input/output (`inputs: ['color: hostColor']`, `outputs: ['clicked: hostClicked']`) dievaluasi pada fase kompilasi sehingga tidak menimbulkan *lookup overhead* pada waktu runtime.

---

### 4. Why & What

| Fitur / Pola | Apa Masalahnya? (Why) | Apa Solusinya? (What) |
| :--- | :--- | :--- |
| **Dynamic Component Loading** | Perutean statis via template tag `<app-x>` tidak dapat mengakomodasi UI berbasis konfigurasi runtime (misal: CMS, dashboard modular dinamis, form builder kustom). | API `ViewContainerRef.createComponent` yang dikombinasikan dengan dynamic import ES Module (`import('./path')`) dan `EnvironmentInjector` memungkinkan pemuatan *lazy* komponen secara *on-demand* dengan footprint memori minimal. |
| **Host Directives** | Pola *Class Inheritance* menyebabkan *fragile base classes*, duplikasi kode, dan kesulitan dalam eksposur selektif contract/events dari mixins/subclasses. | Menggunakan komposisi berbasis trait via metadata `hostDirectives`, memungkinkan penggabungan fungsionalitas (seperti tooltip, keyboard navigation, a11y, tracking) tanpa membuat relasi inheritance. |
| **Content Projection & Signal Queries** | Komponen UI generik (Design Systems) sulit memproyeksikan konten dinamis yang memerlukan pertukaran data dua arah tanpa bocornya arsitektur internal. | Pemanfaatan `ng-template` kontekstual (`TemplateRef<C>`), multi-slot projection menggunakan atribut `select="[slot-name]"`, serta `contentChild` / `viewChild` berbasis Signal untuk reaktivitas non-nullable yang aman. |
| **Style Encapsulation** | Penggunaan `::ng-deep` telah didepresiasi karena membocorkan isolasi gaya ke seluruh aplikasi, merusak isolasi CSS, dan menyebabkan *specificity wars*. | Mengadopsi CSS Custom Properties (`var(--theme-token)`) sebagai kontrak visual publik dengan enkapsulasi `ViewEncapsulation.Emulated` atau `ShadowDom`. |

---

### 5. How (Workflow Detail)

#### Alur Eksekusi Dynamic Component Loading Tingkat Enterprise
1. **Trigger Request**: Pengguna memicu aksi yang membutuhkan komponen dinamis (misal: membuka widget analitik).
2. **Chunk Fetching**: Dynamic import `import(...)` mengeksekusi fetch via browser network terhadap JavaScript chunk yang terpisah.
3. **Injector Resolution**: Menentukan `EnvironmentInjector` atau membuat custom `Injector` menggunakan `Injector.create()` untuk menyuplai dependensi kontekstual ke komponen dinamis.
4. **View Container Binding**: `ViewContainerRef.clear()` dipanggil untuk membersihkan view lama jika diperlukan.
5. **Component Instantiation**: Memanggil `containerRef.createComponent(componentType, { injector, environmentInjector })`.
6. **State & Reactive Binding**: Mengisi input komponen menggunakan API `.setInput('name', value)` untuk mempertahankan siklus reaktivitas Signal.
7. **Subscription Management**: Mengaitkan output/events (`instance.someOutput.subscribe()`) ke dalam context boundary dan memastikan pembersihan memori pada `ngOnDestroy`.

```
[UI Trigger] 
      │
      ▼
[Dynamic Import: import('./widget.component')] ──> [Webpack/Vite Chunk Load]
      │
      ▼
[Create Contextual Injector: Injector.create()]
      │
      ▼
[ViewContainerRef.createComponent(WidgetComp, { injector })]
      │
      ├──> [Allocate LView in Ivy Memory]
      ├──> [Insert DOM elements after Anchor Comment]
      └──> [Bind Inputs via setInput() / Subscribe to Outputs]
      │
      ▼
[Host Change Detection Cycle (Target LView Checked)]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Komposisi vs Pewarisan
Bayangkan Anda sedang merakit sebuah **Mobil Balap Enterprise (Component)**:
- **Inheritance (Pewarisan Klasik)**: Anda membuat kelas `SportsCar` yang mewarisi dari `BaseVehicle`. Jika Anda ingin kemampuan `Flyable`, Anda terpaksa merombak hierarki atau membuat kelas hibrida raksasa `FlyingCar` yang rentan rusak.
- **Host Directives (Komposisi)**: Anda memiliki modul terpisah: `EngineModule`, `TurboBoostDirective`, `DriftAssistDirective`. Mobil balap cukup mengumumkan: *"Saya terdiri dari Komponen Rangka ini, dan pasang `hostDirectives: [TurboBoostDirective, DriftAssistDirective]`"*. Anda dapat menambah atau mengurangi kapabilitas secara plug-and-play tanpa merusak hierarki rangka.

#### Diagram Arsitektur Komposisi UI Dinamis

```
+-----------------------------------------------------------------------------------+
| Host Container (LView Parent)                                                     |
|                                                                                   |
|  +-----------------------------------+   +-------------------------------------+  |
|  | Host Directives:                  |   | Content Projection Slot:            |  |
|  | - FocusableDirective              |   |                                     |  |
|  | - RbacPermissionDirective         |   | <ng-content select="[header]">      |  |
|  +-----------------------------------+   +-------------------------------------+  |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | Dynamic View Insertion Boundary (ViewContainerRef Anchor: <!--container-->) |  |
|  |                                                                             |  |
|  |   [LContainer Chain]                                                        |  |
|  |         |                                                                   |  |
|  |         v                                                                   |  |
|  |   +-------------------------------------------------------------------+     |  |
|  |   | Dynamic Child Component (Loaded via Dynamic Import)               |     |  |
|  |   |  - Custom Injector Layer (Overrides scoped tokens)                |     |  |
|  |   |  - Isolated OnPush / Signal Change Detection                      |     |  |
|  |   +-------------------------------------------------------------------+     |  |
|  +-----------------------------------------------------------------------------+  |
|                                                                                   |
+-----------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Host Directives dengan State Aliasing
Contoh penggunaan `hostDirectives` untuk menambahkan perilaku *toggleable* dan *focus-tracker* ke sebuah *card component*.

```typescript
import { Directive, Component, signal, input, output } from '@angular/core';

// 1. Directive yang dapat dikomposisikan (Behavior Trait)
@Directive({
  standalone: true
})
export class SelectableDirective {
  readonly isSelected = signal(false);
  readonly selectedChange = output<boolean>();

  toggle(): void {
    const nextState = !this.isSelected();
    this.isSelected.set(nextState);
    this.selectedChange.emit(nextState);
  }
}

// 2. Component yang mengadopsi directive tersebut
@Component({
  selector: 'app-selectable-card',
  standalone: true,
  template: `
    <div class="card" [class.active]="selectable.isSelected()" (click)="selectable.toggle()">
      <ng-content />
    </div>
  `,
  styles: [`
    .card { padding: 1rem; border: 1px solid #ccc; cursor: pointer; transition: all 0.2s; }
    .card.active { border-color: #0066cc; background: #e6f0fa; }
  `],
  hostDirectives: [
    {
      directive: SelectableDirective,
      outputs: ['selectedChange: cardSelected'] // Alias output ke interface publik host
    }
  ]
})
export class SelectableCardComponent {
  // Akses direct instance direktif melalui NodeInjector
  constructor(protected readonly selectable: SelectableDirective) {}
}
```

#### Practical Example: Production-Ready Dynamic Analytics Widget Engine
Implementasi micro-engine dinamis yang merender widget analitik finansial secara terisolasi berdasarkan konfigurasi metadata.

```typescript
// widget-token.ts
import { InjectionToken, Type } from '@angular/core';

export interface WidgetPayload {
  ticker: string;
  refreshIntervalMs: number;
}

export interface DynamicWidget {
  configure(payload: WidgetPayload): void;
}

export const WIDGET_DATA = new InjectionToken<WidgetPayload>('WIDGET_DATA');

// base-widget.directive.ts (Host Directive untuk Pelacakan Telemetri & Aksesibilitas)
import { Directive, inject, ElementRef, OnInit, OnDestroy } from '@angular/core';

@Directive({ standalone: true })
export class TelemetryHostDirective implements OnInit, OnDestroy {
  private readonly el = inject(ElementRef);

  ngOnInit(): void {
    // Simulasi integrasi IntersectionObserver untuk melacak render widget
    console.info(`[Telemetry] Widget mounted in DOM:`, this.el.nativeElement);
  }

  ngOnDestroy(): void {
    console.info(`[Telemetry] Widget destroyed.`);
  }
}

// widgets/stock-ticker.component.ts (Komponen yang akan dimuat dinamis)
import { Component, inject, signal, OnInit, OnDestroy, ChangeDetectionStrategy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { WIDGET_DATA, DynamicWidget, WidgetPayload } from './widget-token';
import { TelemetryHostDirective } from './base-widget.directive';

@Component({
  selector: 'app-stock-ticker-widget',
  standalone: true,
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="ticker-box">
      <h4>{{ config.ticker }}</h4>
      <div class="price" [class.up]="price() >= openPrice" [class.down]="price() < openPrice">
        \${{ price().toFixed(2) }}
      </div>
      <small>Interval: {{ config.refreshIntervalMs }}ms</small>
    </div>
  `,
  styles: [`
    :host { display: block; border: 1px solid #e1e4e8; border-radius: 6px; padding: 12px; }
    .price { font-size: 1.5rem; font-weight: bold; }
    .up { color: #28a745; }
    .down { color: #d73a49; }
  `],
  hostDirectives: [TelemetryHostDirective]
})
export class StockTickerWidgetComponent implements DynamicWidget, OnInit, OnDestroy {
  protected readonly config: WidgetPayload = inject(WIDGET_DATA);
  protected readonly price = signal<number>(100.0);
  protected readonly openPrice = 100.0;
  private intervalId?: number;

  ngOnInit(): void {
    this.intervalId = window.setInterval(() => {
      const delta = (Math.random() - 0.49) * 2;
      this.price.update(current => Math.max(1, current + delta));
    }, this.config.refreshIntervalMs);
  }

  configure(payload: WidgetPayload): void {
    // Opsional jika data diperbarui secara runtime setelah inisialisasi
  }

  ngOnDestroy(): void {
    if (this.intervalId) {
      clearInterval(this.intervalId);
    }
  }
}

// widget-renderer.component.ts (Host Komponen Engine)
import {
  Component,
  ViewContainerRef,
  Injector,
  EnvironmentInjector,
  input,
  effect,
  inject,
  ChangeDetectionStrategy,
  ComponentRef
} from '@angular/core';
import { WIDGET_DATA, DynamicWidget, WidgetPayload } from './widget-token';

export type WidgetType = 'stock-ticker' | 'fx-rate';

@Component({
  selector: 'app-widget-renderer',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="widget-wrapper">
      <div class="widget-header">
        <span>Dynamic Instance</span>
      </div>
      <!-- Anchor untuk ViewContainerRef -->
      <ng-container #anchor />
    </div>
  `,
  styles: [`
    .widget-wrapper { border: 1px dashed #bbb; padding: 8px; border-radius: 8px; margin: 8px 0; }
    .widget-header { font-size: 0.75rem; color: #777; margin-bottom: 4px; text-transform: uppercase; }
  `]
})
export class WidgetRendererComponent {
  // Input Signal API
  readonly type = input.required<WidgetType>();
  readonly payload = input.required<WidgetPayload>();

  private readonly vcr = inject(ViewContainerRef);
  private readonly envInjector = inject(EnvironmentInjector);
  private componentRef?: ComponentRef<DynamicWidget>;

  constructor() {
    // Re-instantiate widget saat input berubah secara reaktif
    effect((onCleanup) => {
      const currentType = this.type();
      const currentPayload = this.payload();

      this.renderWidget(currentType, currentPayload);

      onCleanup(() => {
        this.destroyCurrentWidget();
      });
    });
  }

  private async renderWidget(type: WidgetType, payload: WidgetPayload): Promise<void> {
    this.destroyCurrentWidget();

    // Resolusi Komponen Dinamis secara Lazy via Async Import
    let componentClass: any;
    if (type === 'stock-ticker') {
      const module = await import('./stock-ticker-widget.component');
      componentClass = module.StockTickerWidgetComponent;
    } else {
      throw new Error(`Widget type ${type} tidak didukung.`);
    }

    // Bangun Custom Injector untuk Injecting Contextual Data
    const contextualInjector = Injector.create({
      providers: [
        {
          provide: WIDGET_DATA,
          useValue: payload
        }
      ],
      parent: this.vcr.injector
    });

    // Buat komponen dinamis dengan inject spesifik
    this.componentRef = this.vcr.createComponent(componentClass, {
      injector: contextualInjector,
      environmentInjector: this.envInjector
    });

    this.componentRef.changeDetectorRef.markForCheck();
  }

  private destroyCurrentWidget(): void {
    if (this.componentRef) {
      this.componentRef.destroy();
      this.componentRef = undefined;
      this.vcr.clear();
    }
  }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
Platform Core Banking Enterprise dengan modul **Dynamic Form Engine & Workspace Configurator**. Sistem memiliki ratusan tipe modul operasional (Kredit, AML Verification, Valas) yang harus dirender dalam layout multi-tab dinamis berdasarkan skema JSON yang di-fetch dari microservice Configuration Management.

#### Tantangan Skalabilitas & Runtime
1. **Memory Bloat**: Pembukaan 50+ tab secara bersamaan tanpa lifecycle disposal yang bersih mengakibatkan retensi ratusan `ComponentRef`, `LView`, dan listeners, memicu lag garbage collection (GC pauses > 1.5 detik).
2. **Injector Mismatch**: Tiap form tab membutuhkan isolasi konteks (Transaction ID, Scoped Audit Logger, Scoped Validation Schema) tanpa mengotori Global Root Injector.
3. **Circular Template Dependencies**: Komponen form kompleks memanggil field builder secara rekursif, memicu bundle circular reference.

#### Solusi Arsitektural
1. **Dynamic Factory Cache & Pool**: Membangun `DynamicComponentPoolManager` yang mengontrol kuota maksimal *active view*.
2. **Contextual Hierarchical Injector**: Pemanfaatan `Injector.create` dengan dependensi hierarkis terikat pada siklus hidup Tab:

```typescript
// contextual-form-orchestrator.ts
import { Injectable, Injector, ComponentRef, ViewContainerRef, EnvironmentInjector } from '@angular/core';
import { FORM_CONTEXT, FormTransactionContext } from './form-context.token';

@Injectable({ providedIn: 'root' })
export class DynamicFormOrchestrator {
  private activeComponents = new Map<string, ComponentRef<any>>();

  async mountFormTab(
    tabId: string,
    componentLoader: () => Promise<any>,
    containerRef: ViewContainerRef,
    contextData: FormTransactionContext,
    envInjector: EnvironmentInjector
  ): Promise<ComponentRef<any>> {
    // 1. Eviction logic jika tab sudah ada
    if (this.activeComponents.has(tabId)) {
      this.unmountFormTab(tabId);
    }

    // 2. Load chunk secara isolated
    const loadedComponent = await componentLoader();

    // 3. Bangun hierarchical context injector
    const scopedInjector = Injector.create({
      providers: [
        { provide: FORM_CONTEXT, useValue: Object.freeze(contextData) }
      ],
      parent: containerRef.injector
    });

    // 4. Instansiasi komponen ke host container
    const compRef = containerRef.createComponent(loadedComponent, {
      index: containerRef.length,
      injector: scopedInjector,
      environmentInjector: envInjector
    });

    this.activeComponents.set(tabId, compRef);
    return compRef;
  }

  unmountFormTab(tabId: string): void {
    const ref = this.activeComponents.get(tabId);
    if (ref) {
      ref.destroy(); // Melepaskan LView, membersihkan listeners DOM, memutus Injector references
      this.activeComponents.delete(tabId);
    }
  }
}
```

---

### 9. Trade-offs (Performance, Latency, Scalability, Cost)

| Parameter | Dynamic Loading (`createComponent`) | Static Template Declarations (`*ngIf` / `@if`) |
| :--- | :--- | :--- |
| **Initial Bundle Size** | **Sangat Rendah (Optimal)**: Potongan komponen terpecah menjadi bundle chunk terpisah yang di-*download on-demand*. | **Tinggi**: Seluruh kemungkinan komponen harus di-import secara eksplisit ke dalam host standalone component. |
| **Runtime Latency (TTI)** | **Ada Network Latency**: Saat pertama kali komponen dipanggil, ada delay resolusi chunk JS melalui HTTP. Butuh UX placeholder / skeleton. | **Nol Network Latency**: Komponen sudah berada di browser memory; instansiasi instan saat kondisi bernilai `true`. |
| **Memory Footprint** | **Dapat Dikelola Dinamis**: Komponen dapat di-*unmount* secara manual dan memory dapat diklaim kembali oleh V8 engine GC kapan saja. | **Tergantung Ivy Garbage Collection**: Angular tetap mempertahankan metadata instruksi rendering di memory selama modul induk hidup. |
| **Type Safety & Dx** | **Rentan Runtime Errors**: Pengecekan input/output via string token atau generic casting. Refactoring tool IDE tidak selalu otomatis mendeteksi dependensi. | **Strictly Type-Safe**: Kompilator TypeScript memvalidasi tipe input, output, dan generic properties secara native pada saat build time. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Lupa Memanggil `ComponentRef.destroy()` Menyebabkan Detached DOM Memory Leak
- **Gejala**: Memory footprint browser terus meningkat setiap kali elemen dinamis dibuka dan ditutup. Heap Snapshot menunjukkan ribuan node bertipe `Detached HTMLDivElement` dan retained instance `LView`.
- **Root Cause**: Developer menghapus elemen host dari DOM via native DOM APIs (`el.remove()`) atau membersihkan parent container tanpa memanggil `.destroy()` pada referensi `ComponentRef`.
- **Solusi**: Selalu simpan handle `ComponentRef` dan eksekusi `.destroy()` pada hook `ngOnDestroy()` atau sebelum instansiasi baru.

#### 2. Resolusi Dependency Gagal (`NullInjectorError`) pada Dynamic Component
- **Gejala**: Muncul pesan error `NullInjectorError: No provider for XService!` saat dynamic component dibuat via `createComponent`.
- **Root Cause**: `createComponent` dipanggil hanya dengan parameter `Type`, tanpa menyertakan `injector: containerRef.injector`. Akibatnya, Angular mengasumsikan root fallback injector dan kehilangan *scoped providers* yang didefinisikan pada parent view.
- **Solusi**:
  ```typescript
  // SALAH
  this.vcr.createComponent(DynamicComponent);

  // BENAR
  this.vcr.createComponent(DynamicComponent, { injector: this.vcr.injector });
  ```

#### 3. Styling Rusak Akibat Ketergantungan pada `::ng-deep` yang Usang
- **Gejala**: Komponen dynamic yang dirender ke dalam `ViewContainerRef` kehilangan tema atau CSS kustom tidak terpasang karena enkapsulasi CSS default (`Emulated`) menghasilkan scoping hash atribut (misal `_ngcontent-c12`) yang berbeda antara parent dan dynamic child.
- **Solusi**: Hindari `::ng-deep`. Terapkan pola CSS Variables API:

```css
/* Parent Component Styling */
:host {
  --btn-dynamic-bg: #0066cc;
  --btn-dynamic-color: #ffffff;
}

/* Dynamic Child Component Styling */
:host {
  display: inline-block;
}
button {
  background-color: var(--btn-dynamic-bg, #gray);
  color: var(--btn-dynamic-color, #black);
}
```

---

### 11. Best Practices (Production Checklist)

- [ ] **Gunakan Modern Signal Queries**: Gantikan `@ViewChild` dan `@ContentChild` lawas dengan `viewChild()`, `viewChildren()`, `contentChild()`, dan `contentChildren()` untuk sinyal reaktivitas terpadu dan proteksi null-safety.
- [ ] **Deklarasikan Host Directives Secara Terisolasi**: Batasi `hostDirectives` hanya pada perilaku stateless atau behavior ber-scope elemen (misal: A11y keyboard trapping, active styling, logging). Hindari menyimpan state domain bisnis global dalam directive.
- [ ] **Eksplisitkan Dependency Injector Boundary**: Selalu teruskan `injector: this.vcr.injector` atau custom `Injector.create()` saat menggunakan `ViewContainerRef.createComponent`.
- [ ] **Wajib Gunakan ChangeDetectionStrategy.OnPush**: Seluruh dynamic components dan slot host harus mengadopsi `OnPush` untuk menghindari full-tree dirty checking saat event mikro terpicu.
- [ ] **Terapkan `ngProjectAs` saat Berurusan dengan Wrapper Components**: Jika melakukan multi-slot projection di dalam template berjenjang, gunakan `ngProjectAs="[target-slot]"` untuk mencegah kegagalan pencocokan CSS selector pada `<ng-content>`.
- [ ] **Gunakan Standalone Component Secara Utuh**: Hapus penggunaan `ComponentFactoryResolver` dan deklarasi di array `entryComponents` (telah usang sejak Angular Ivy).

---

### 12. Hands-on Practice

Buat dan simpan latihan implementasi ini pada path: `hands-on/m02/`

#### Struktur Proyek
```
hands-on/m02/
├── dynamic-modal-manager/
│   ├── modal.token.ts
│   ├── modal-host.directive.ts
│   ├── modal-backdrop.component.ts
│   ├── alert-modal.component.ts
│   └── modal.service.ts
└── README.md
```

#### Langkah-langkah Implementasi

1. **Definisikan Token Konfigurasi Modal (`modal.token.ts`)**:
```typescript
import { InjectionToken } from '@angular/core';

export interface ModalConfig<T = any> {
  title: string;
  data: T;
}

export const MODAL_DATA = new InjectionToken<ModalConfig>('MODAL_DATA');
```

2. **Buat Trait Directive untuk Escape Key Handling (`modal-host.directive.ts`)**:
```typescript
import { Directive, HostListener, output } from '@angular/core';

@Directive({
  selector: '[appModalHostEvents]',
  standalone: true
})
export class ModalHostEventsDirective {
  readonly escapePressed = output<void>();

  @HostListener('document:keydown.escape', ['$event'])
  onKeydown(event: KeyboardEvent): void {
    this.escapePressed.emit();
  }
}
```

3. **Buat Implementasi Komponen Modal Dinamis (`alert-modal.component.ts`)**:
```typescript
import { Component, inject, ChangeDetectionStrategy } from '@angular/core';
import { MODAL_DATA, ModalConfig } from './modal.token';
import { ModalService } from './modal.service';

@Component({
  selector: 'app-alert-modal',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="modal-box">
      <h3>{{ modalConfig.title }}</h3>
      <p>{{ modalConfig.data.message }}</p>
      <button (click)="close()">Tutup</button>
    </div>
  `,
  styles: [`
    .modal-box {
      background: white;
      padding: 24px;
      border-radius: 8px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      min-width: 300px;
    }
    button {
      margin-top: 16px;
      padding: 8px 16px;
      background: #0070f3;
      color: white;
      border: none;
      border-radius: 4px;
      cursor: pointer;
    }
  `]
})
export class AlertModalComponent {
  protected readonly modalConfig: ModalConfig<{ message: string }> = inject(MODAL_DATA);
  private readonly modalService = inject(ModalService);

  close(): void {
    this.modalService.close();
  }
}
```

4. **Buat Container Modal Backdrop Berbasis Host Directive (`modal-backdrop.component.ts`)**:
```typescript
import { Component, ViewContainerRef, viewChild, ChangeDetectionStrategy } from '@angular/core';
import { ModalHostEventsDirective } from './modal-host.directive';
import { ModalService } from './modal.service';

@Component({
  selector: 'app-modal-backdrop',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="overlay" (click)="onBackdropClick($event)">
      <div class="container" (click)="$event.stopPropagation()">
        <ng-container #modalTarget />
      </div>
    </div>
  `,
  styles: [`
    .overlay {
      position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
      background: rgba(0, 0, 0, 0.4); display: flex;
      justify-content: center; align-items: center; z-index: 1000;
    }
    .container { position: relative; }
  `],
  hostDirectives: [
    {
      directive: ModalHostEventsDirective,
      outputs: ['escapePressed: onEscape']
    }
  ]
})
export class ModalBackdropComponent {
  readonly modalTarget = viewChild.required('modalTarget', { read: ViewContainerRef });

  constructor(private readonly modalService: ModalService) {}

  onEscape(): void {
    this.modalService.close();
  }

  onBackdropClick(event: MouseEvent): void {
    if (event.target === event.currentTarget) {
      this.modalService.close();
    }
  }
}
```

5. **Bangun Dynamic Orchestrator Service (`modal.service.ts`)**:
```typescript
import {
  Injectable,
  ApplicationRef,
  createComponent,
  EnvironmentInjector,
  Injector,
  Type,
  ComponentRef
} from '@angular/core';
import { ModalBackdropComponent } from './modal-backdrop.component';
import { MODAL_DATA, ModalConfig } from './modal.token';

@Injectable({ providedIn: 'root' })
export class ModalService {
  private backdropRef?: ComponentRef<ModalBackdropComponent>;
  private modalContentRef?: ComponentRef<any>;

  constructor(
    private readonly appRef: ApplicationRef,
    private readonly envInjector: EnvironmentInjector
  ) {}

  open<T>(componentType: Type<any>, config: ModalConfig<T>): void {
    this.close(); // Bersihkan jika masih ada modal aktif

    // 1. Instansiasi Host Backdrop langsung ke Root DOM
    this.backdropRef = createComponent(ModalBackdropComponent, {
      environmentInjector: this.envInjector
    });

    // 2. Hubungkan ke Change Detection Application Tree
    this.appRef.attachView(this.backdropRef.hostView);
    document.body.appendChild(this.backdropRef.location.nativeElement);

    // 3. Inject Contextual Modal Data ke Komponen Target
    const targetVcr = this.backdropRef.instance.modalTarget();
    const contextualInjector = Injector.create({
      providers: [{ provide: MODAL_DATA, useValue: config }],
      parent: targetVcr.injector
    });

    // 4. Instansiasi Dynamic Content di dalam Backdrop Target
    this.modalContentRef = targetVcr.createComponent(componentType, {
      injector: contextualInjector,
      environmentInjector: this.envInjector
    });

    this.backdropRef.changeDetectorRef.detectChanges();
  }

  close(): void {
    if (this.modalContentRef) {
      this.modalContentRef.destroy();
      this.modalContentRef = undefined;
    }
    if (this.backdropRef) {
      this.appRef.detachView(this.backdropRef.hostView);
      this.backdropRef.destroy();
      this.backdropRef = undefined;
    }
  }
}
```

---

### 13. Exercise

#### Level Easy
Gunakan `hostDirectives` untuk membuat atribut directive `AutoFocusDirective` yang otomatis memberikan fokus pada elemen form input HTML begitu komponen selesai dirender. Aplikasikan directive ini secara internal pada komponen `AppSearchInputComponent` tanpa mengeksposnya pada template markup pemanggil.

#### Level Medium
Buat komponen UI Data List generik `VirtualDynamicList<T>` yang menerima array data generic dan sebuah `TemplateRef<C>` dari parent component. Implementasikan fallback slot menggunakan multi-slot `<ng-content>`:
1. Slot `[list-header]` untuk menyuntikkan header kustom.
2. Slot fallback default jika data array kosong (`list-empty`).
3. Template rendering untuk tiap baris list item menggunakan `*ngTemplateOutlet` kontekstual yang mengekspos `$implicit: item` dan `index: number`.

#### Level Hard
Rancang sebuah **Micro-Frontend Widget Loader** yang menerima URL Remote ESM Module secara runtime:
1. Mengunduh remote JavaScript bundle menggunakan native dynamic import (`await import(/* webpackIgnore: true */ moduleUrl)`).
2. Mengekstrak Angular Standalone Component class yang diekspor dari module tersebut.
3. Menyuntikkan child injector yang membawa konfigurasi auth JWT token.
4. Menangani kondisi jika script gagal diunduh (network crash/CORS) dengan merender *Fall-back Dynamic Error Component* tanpa memutus Change Detection tree induk.

---

### 14. Challenge

#### Skenario Kasus Kompleks
Anda adalah Principal Architect pada perusahaan platform SaaS E-Commerce Global. Aplikasi memiliki fitur **Live Drag-and-Drop Page Builder** yang berjalan sepenuhnya di sisi browser client. 

**Persyaratan Sistem**:
1. Kanvas layout editor dapat menampung hingga **200 blok komponen UI dinamis** secara bersamaan (misal: Hero Banner, Product Carousel, Countdown Timer, Testimonial, Checkout Widget).
2. Pengguna dapat melakukan *reordering* (menggeser posisi blok naik/turun) secara instan.
3. Setiap komponen dinamis memiliki dependensi state dan form konfigurasi panel terpisah di sidebar.
4. **Constraint Keras**: Dilarang me-reinstansiasi (menghancurkan dan membuat ulang via `createComponent`) seluruh komponen ketika urutan blok berubah, karena re-instansiasi akan menghilangkan state internal (seperti unsubmitted text data, scroll position video, canvas chart WebGL buffers) dan memicu FPS drop drastis di bawah 30 FPS.

**Tugas Anda**:
Rancang arsitektur komponen runtime menggunakan `ViewContainerRef`, `ViewRef`, dan array manipulasi `LContainer` (`move()`, `detach()`, `insert()`). Jelaskan dan dokumentasikan bagaimana data injector dikelola per komponen yang berpindah posisi tanpa memutus referensi memori, serta bagaimana Anda memastikan lifecycle hooks (`ngOnDestroy`) tidak terpicu secara salah selama proses pemindahan posisi elemen tersebut di runtime DOM.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda & Konseptual Singkat)
1. **Apa perbedaan mendasar antara `TView` dan `LView` pada arsitektur Ivy?**
   - A. `TView` menyimpan data spesifik instance, sedangkan `LView` menyimpan blueprint statis.
   - B. `TView` adalah blueprint statis bersama (template instruksi/konstanta), sedangkan `LView` menyimpan state aktual dan referensi runtime per instance.
   - C. `TView` dieksekusi di Web Worker, `LView` di main thread.
   - D. `TView` digunakan hanya untuk Angular Signals, `LView` untuk RxJS.
2. **Kapan method `ViewContainerRef.clear()` sebaiknya dipanggil?**
   - A. Hanya saat aplikasi Angular pertama kali bootstrap.
   - B. Setiap kali ada perubahan kecil pada binding string di template.
   - C. Sebelum menginstansiasi view baru pada container yang sama jika view lama ingin dihancurkan dari memori dan DOM.
   - D. Hanya saat menggunakan `ViewEncapsulation.ShadowDom`.
3. **Bagaimana cara Angular 15+ mengekspos output milik host directive ke komponen pemanggil?**
   - A. Melalui `@Output()` inheritance biasa.
   - B. Menggunakan array konfigurasi `outputs: ['internalEvent: publicAlias']` di metadata `hostDirectives`.
   - C. Melalui mekanisme bubbling native DOM CustomEvent secara otomatis.
   - D. Menggunakan operator `outputFromDirective()` di constructor.
4. **Mengapa API `ComponentFactoryResolver` didepresiasi (*deprecated*) oleh tim Angular?**
   - A. Karena ukuran bundle Angular terlalu kecil.
   - B. Karena arsitektur Ivy mampu langsung menyelesaikan referensi komponen tanpa memerlukan factory class yang dihasilkan pada saat kompilasi.
   - C. Karena Angular tidak lagi mendukung rendering dinamis.
   - D. Karena `ComponentFactoryResolver` tidak kompatibel dengan TypeScript 5.
5. **Apa fungsi utama dari atribut `ngProjectAs` dalam content projection?**
   - A. Mengganti nama selector komponen di DOM.
   - B. Memaksa elemen diproyeksikan ke dalam slot `<ng-content>` tertentu terlepas dari tag DOM asli atau struktur pembungkusnya.
   - C. Menghubungkan CSS class global ke shadow DOM.
   - D. Mencegah komponen memicu lifecycle `ngAfterContentInit`.

#### Bagian 2: Intermediate (Analisis Arsitektur)
6. **Jelaskan siklus hidup (*lifecycle execution order*) antara host directive dan host component tempat directive tersebut dikomposisikan!**
7. **Bagaimana mekanisme `contentChild` signal query menyelesaikan nilai saat konten yang diproyeksikan berada di dalam blok `@if` yang kondisinya berubah menjadi `false`?**
8. **Apa implikasi performa dari pembuatan `Injector` baru via `Injector.create()` untuk setiap komponen dinamis yang dibuat dalam loop virtual scroll?**
9. **Mengapa penggunaan pseudo-class `:host-context()` sebaiknya dibatasi dalam sistem desain berskala besar?**
10. **Bagaimana cara mencegah memory leak ketika sebuah Dynamic Component menginjeksi sebuah service bertaraf `root` (`@Injectable({ providedIn: 'root' })`) yang memiliki infinite RxJS Observable interval?**

#### Bagian 3: Skenario Kasus Produksi
11. **Skenario A**: Sebuah tim e-commerce mendapati bahwa setelah beralih ke dynamic widget rendering, analytics tracking berbasis directive di host widget mereka berhenti mencatat event click. Padahal directive tersebut dideklarasikan pada `hostDirectives` komponen target. Mengapa hal ini bisa terjadi jika instansiasi dynamic komponen dilakukan dengan cara menyisipkan native DOM via `ElementRef.nativeElement.appendChild()`?
12. **Skenario B**: Pada sebuah aplikasi micro-frontend multi-tenant, Anda melihat styling komponen modal tenant B bocor dan mengubah tampilan tombol pada tenant A, meskipun kedua komponen menggunakan `ViewEncapsulation.Emulated`. Setelah diteliti, kedua komponen mendefinisikan class `.btn-primary` dengan properti yang bertentangan. Bagaimana ini bisa terjadi dan apa mitigasi teknisnya?
13. **Skenario C**: Form Engine dinamis Anda mengalami penurunan performa rendering yang tajam saat merender 100 field input dinamis secara bersamaan. Profiling V8 CPU mencatat mayoritas waktu dihabiskan pada fungsi `refreshView` dan sinkronisasi `LView`. Langkah arsitektur apa yang harus Anda lakukan untuk merestrukturisasi proses rendering 100 komponen tersebut?

---

### Kunci Jawaban & Panduan Evaluasi Quiz

#### Bagian 1
1. **B** - `TView` bersifat statis dan dipakai bersama oleh semua instance (mengurangi alokasi memori blueprint), sedangkan `LView` adalah representasi array runtime spesifik untuk tiap instance elemen/komponen.
2. **C** - `ViewContainerRef.clear()` menghancurkan seluruh child `ViewRef` yang ada di container tersebut, melepas node dari DOM, dan memanggil `destroy()` untuk mencegah memory leak.
3. **B** - Metadata `hostDirectives` menyediakan properti pemetaan eksplisit `inputs` dan `outputs` untuk mengekspos atau me-rename contract internal directive ke interface luar host.
4. **B** - Ivy membuang kebutuhan factory metadata class (`.ngfactory`), sehingga komponen class itu sendiri sudah dapat langsung dipakai oleh `createComponent`.
5. **B** - `ngProjectAs` mengesampingkan identitas CSS selector alami sebuah node sehingga matching engine `<ng-content select="...">` mencocokkannya ke slot yang dituju.

#### Bagian 2
6. **Siklus Lifecycle**: Host Directives diinisialisasi **sebelum** Host Component. Konstruktor directive dieksekusi lebih dulu, disusul lifecycle hooks directive (`ngOnInit`, dll.) dijalankan mendahului lifecycle hooks host component yang menampungnya.
7. **Resolusi Signal Query**: `contentChild` menghasilkan signal reaktif yang mengembalikan nilai `undefined` segera setelah kondisi `@if` bernilai false dan view dihancurkan. Berbeda dengan decorator `@ContentChild` lawas, signal query otomatis memicu efek komputasi hilir secara reaktif tanpa menunggu siklus change detection manual berikutnya.
8. **Implikasi Injector Loop**: Membuat ribuan `Injector` instance terpisah di dalam loop virtual scroll akan membebani memory GC dan memperpanjang lookup path dependency resolution chain. Best practice: gunakan injector pooling atau teruskan shared parameterized context.
9. **Kelemahan `:host-context()`**: Mengharuskan CSS engine menelusuri DOM tree ke arah root (*ancestor walking*). Hal ini merusak modularitas CSS, melanggar batas isolasi komponen, dan menyebabkan degradasi rendering pipeline pada DOM tree yang sangat dalam.
10. **Mitigasi RxJS Memory Leak**: Komponen dinamis wajib mengimplementasikan hook pembersihan (`DestroyRef.onDestroy` atau `takeUntilDestroyed`) pada subscription service root, karena siklus hidup service root melampaui siklus hidup komponen dinamis yang bersangkutan.

#### Bagian 3
11. **Analisis Skenario A**: Menggunakan native DOM `appendChild` memotong arsitektur pipeline Angular Ivy. Host Directives terikat pada level instruksi Ivy `LView`/`TView`. Tanpa melewati `createComponent` dan `ViewContainerRef`, Angular tidak pernah mengalokasikan NodeInjector untuk elemen tersebut, sehingga event listeners directive tidak terikat ke DOM runtime.
12. **Analisis Skenario B**: Enkapsulasi `Emulated` menggunakan atribut internal seperti `_ngcontent-cXX`. Jika kedua micro-frontend di-build terpisah tanpa sinkronisasi identifier seed kompilator Angular, class name generik dapat mengalami *collision* jika styles diinjeksi ke global `<head>` oleh loader masing-masing. Solusi: Migrasikan komponen micro-frontend yang rentan konflik ke `ViewEncapsulation.ShadowDom`, atau isolasi CSS class dengan spesifisitas namespace khusus tenant.
13. **Analisis Skenario C**: 
    - Ubah form fields menjadi `ChangeDetectionStrategy.OnPush`.
    - Hindari instansiasi 100 komponen dinamis dalam satu kali frame event loop. Terapkan chunked scheduling menggunakan `requestAnimationFrame` atau Angular CDK Virtual Scrolling sehingga hanya elemen yang terlihat (*in-viewport*) yang diinstansiasi ke dalam `LContainer`.
    - Manfaatkan Embedded Views (`TemplateRef`) daripada Component instances penuh jika fields tersebut hanya merepresentasikan input varian sederhana, guna memangkas overhead pembuatan `LView` komponen penuh.

---

### 16. Summary
- Arsitektur modern Angular Ivy memisahkan representasi view menjadi **`TView`** (definisi statis terdistribusi) dan **`LView`** (instance state dinamis terindeks array).
- Pemuatan komponen dinamis mutakhir berpusat pada **`ViewContainerRef.createComponent`** yang dipadukan dengan Dynamic Imports ES Module, standalone components, serta isolated custom injectors.
- Pola **`hostDirectives`** menghadirkan paradigma *Composition over Inheritance*, memungkinkan integrasi kapabilitas cross-cutting (A11y, telemetry, interactions) secara modular tanpa kopling hierarkis yang rapuh.
- Manajemen lifecycle dan pelepasan memori (**`ComponentRef.destroy()`**, **`ViewContainerRef.clear()`**, signal teardown) adalah pertahanan utama dalam menjaga performa memory runtime aplikasi enterprise bebas dari *detached DOM leaks*.