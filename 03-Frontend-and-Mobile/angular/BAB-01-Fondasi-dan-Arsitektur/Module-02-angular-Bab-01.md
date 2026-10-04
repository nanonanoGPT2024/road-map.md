# Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Mengurai arsitektur internal Angular Runtime Engine (Ivy Engine), mencakup struktur data internal `LView` dan `TView`, model eksekusi *Incremental DOM*, serta eliminasi *Virtual DOM overhead*.
- Menganalisis dan merancang topologi *Hierarchical Dependency Injection* (DI) tingkat lanjut dengan memanfaatkan resolusi *ElementInjector* dan *EnvironmentInjector*, serta *resolution modifiers* (`@Host`, `@Self`, `@SkipSelf`, `@Optional`).
- Mengimplementasikan mekanisme reaktivitas modern menggunakan *Angular Signals* terintegrasi dengan runtime *Change Detection* (OnPush, Zone.js patching, hingga *Zoneless mode*).
- Menghasilkan arsitektur aplikasi *enterprise-grade* berbasis *Standalone Components*, *Directive Composition API*, dan *Dynamic Component Instantiation* tanpa kebocoran memori (*memory leaks*).
- Menemukan, mendiagnosis, dan menyelesaikan isu performa kritis seperti `ExpressionChangedAfterItHasBeenCheckedError`, degradasi memori akibat *detached DOM tree*, dan *bottleneck* siklus Change Detection.

---

## 2. Prerequisites

Sebelum mempelajari modul ini, Anda wajib menguasai:
- **TypeScript Advanced Types**: Mampu mengoperasikan *Generics*, *Conditional Types*, *Mapped Types*, *Type Narrowing*, dan *Decorators*.
- **Konsep Fondasi Angular (Module 01)**: Pemahaman siklus hidup komponen (`ngOnInit`, `ngOnChanges`, `ngOnDestroy`), dasar dependency injection, serta sintaks template control flow (`@if`, `@for`).
- **RxJS Primitives**: Menguasai konsep dasar `Observable`, `Subject`, `BehaviorSubject`, operator transformasi (`switchMap`, `exhaustMap`), dan siklus *unsubscription*.
- **Browser Rendering Engine**: Pemahaman mendalam mengenai siklus eksekusi JavaScript (Event Loop, Microtasks, Macrotasks), DOM Tree, CSSOM, dan proses compositing browser.

---

## 3. Concept & Internal Architecture

### 3.1 Ivy Compiler & Runtime: Incremental DOM vs. Virtual DOM

Mayoritas framework frontend modern (seperti React) menggunakan abstraksi **Virtual DOM (VDOM)**. Ketika terjadi perubahan state, VDOM membuat pohon representasi baru di memori, membandingkannya dengan pohon VDOM sebelumnya (*reconciliation/diffing*), lalu menulis perubahannya ke DOM asli. Pendekatan ini membutuhkan alokasi memori ekstra untuk mengalokasikan node VDOM baru pada setiap siklus render.

Angular Ivy mengambil pendekatan **Incremental DOM**. Template Angular dikompilasi oleh AOT (*Ahead-of-Time*) Compiler menjadi serangkaian instruksi komputasi langsung (*bytecode/instructions* dalam bentuk JavaScript murni). Instruksi ini memodifikasi DOM asli secara *in-place* ketika state berubah, tanpa menciptakan representasi pohon perantara di memori.

```
+-------------------------------------------------------------+
|                     Template Angular                        |
|        <h1>{{ title() }}</h1> <app-user [id]="userId()" />   |
+-------------------------------------------------------------+
                              |
                              | (AOT Compilation)
                              v
+-------------------------------------------------------------+
|                 Ivy Instructions Template Fn                |
|  function MyComponent_Template(rf, ctx) {                   |
|    if (rf & 1) { // Creation Mode                           |
|      ɵɵelementStart(0, "h1");                               |
|      ɵɵtext(1);                                             |
|      ɵɵelementEnd();                                        |
|      ɵɵelement(2, "app-user");                              |
|    }                                                        |
|    if (rf & 2) { // Update Mode                             |
|      ɵɵadvance(1);                                          |
|      ɵɵtextInterpolate(ctx.title());                        |
|      ɵɵadvance(1);                                          |
|      ɵɵproperty("id", ctx.userId());                        |
|    }                                                        |
|  }                                                          |
+-------------------------------------------------------------+
```

Keuntungan utama arsitektur ini:
1. **Tree-Shaking Maksimal**: Jika template Anda tidak menggunakan instruksi tertentu (misalnya `ɵɵpipe`), instruksi tersebut tidak akan pernah dimasukkan ke dalam bundel akhir oleh *terser/esbuild*.
2. **Low Memory Footprint**: Karena tidak ada pohon VDOM yang dibuat ulang, penggunaan alokasi memori GC (*Garbage Collector*) browser menurun secara drastis.

#### Struktur Data Internal: `LView` vs `TView`

Untuk memisahkan data statis (definisi template) dengan data dinamis (instance komponen aktual), Ivy membagi struktur internal tampilan menjadi dua model data array:

- **`TView` (Template View)**: Struktur data tunggal yang dibagikan ke seluruh instance komponen yang sama. Berisi metadata statis, skema DOM, *binding index table*, dan definisi injection token. `TView` hanya diinisialisasi sekali.
- **`LView` (Logical View)**: Array dinamis yang dialokasikan per instance komponen. `LView` merepresentasikan state konkret saat runtime: referensi elemen DOM asli, instance directive/komponen, nilai binding saat ini, serta status dirty change detection.

```
       TView (Shared, Immutable Blueprint)
       +---------------------------------------------+
       | 0: Header Info | 1: Directive Def | ...     |
       +---------------------------------------------+
                              ^
                              | (Shared Blueprint Pointer)
       +----------------------+----------------------+
       |                                             |
LView Instance A (Component 1)          LView Instance B (Component 2)
+-------------------------------+       +-------------------------------+
| 0: TView Ref                  |       | 0: TView Ref                  |
| 1: DOM Node: <h1> "User 1"    |       | 1: DOM Node: <h1> "User 2"    |
| 2: UserComponent Instance     |       | 2: UserComponent Instance     |
| 3: Binding Val: "Alpha"       |       | 3: Binding Val: "Beta"        |
+-------------------------------+       +-------------------------------+
```

### 3.2 Hierarchical Dependency Injection: ElementInjector vs. EnvironmentInjector

Sistem DI Angular bersifat hierarkis dan berjalan dalam dua pohon terpisah yang saling bekerja sama:

1. **`EnvironmentInjector` Tree**:
   - Berisi dependensi yang disediakan pada tingkat aplikasi (`providedIn: 'root'`), konfigurasi `ApplicationConfig` via `bootstrapApplication`, atau modul routing.
   - Bertanggung jawab atas dependensi tingkat singleton dan layanan yang hidup sepanjang siklus aplikasi atau lifecycle rute tertentu.
2. **`ElementInjector` Tree**:
   - Dibuat secara implisit pada setiap node DOM tempat komponen atau directive berada.
   - Mengikuti struktur hierarki pohon DOM.
   - Mengatur instansiasi dependensi lokal komponen melalui array `providers` atau `viewProviders`.

#### Algoritma Resolusi Dependensi:
Saat dependensi diminta di komponen terdalam:
1. Angular menelusuri hierarki `ElementInjector` dari node saat ini ke atas hingga ke root element.
2. Jika tidak ditemukan, Angular berpindah menelusuri hierarki `EnvironmentInjector` (Rute aktif -> Parent Rute -> Root Environment Injector -> Platform Injector).
3. Jika masih tidak ditemukan dan tidak ditandai `@Optional()`, runtime akan melempar `NullInjectorError`.

```
                  [Platform Injector]
                           ^
                           |
               [Root EnvironmentInjector]
              (providedIn: 'root', AppConfig)
                           ^
                           |
               [Route EnvironmentInjector]
                           ^
                           |
   =================================================
             ElementInjector Tree Boundary
   =================================================
               [App ElementInjector]
                           ^
                           |
               [Parent Component Injector]
                           ^
                           |
               [Child Component Injector] <--- Dependency lookup starts here
```

### 3.3 Change Detection Engine: Zone.js vs. Zoneless Signals Runtime

Secara historis, Angular menggunakan **Zone.js** untuk mendeteksi perubahan state. Zone.js melakukan *monkey-patching* terhadap semua API asynchronous browser (`setTimeout`, `Promise`, `fetch`, event listener DOM). Ketika suatu async task selesai dieksekusi, Zone.js memicu *top-down change detection sweep* melalui `ApplicationRef.tick()` dari root component sampai leaf component.

**Masalah pada Model Zone.js**:
- Overhead komputasi: Memeriksa setiap binding di seluruh pohon aplikasi, meskipun hanya satu leaf node yang berubah (kecuali dibendung oleh `ChangeDetectionStrategy.OnPush`).
- Debugging sulit: Asynchronous stack trace menjadi sangat panjang dan kabur.
- Beban muat awal (*payload bundle*): Menambah bobot sekitar 30-40 KB gzip ke dalam bundle inti.

**Paradigma Modern: Fine-Grained Reactivity (Angular Signals & Zoneless)**:
Angular Signals memperkenalkan grafik ketergantungan reaktif (*Reactive Dependency Graph*). Menggunakan algoritma *push-pull*:
1. **Push**: Ketika nilai `signal.set()` berubah, sinyal memberi sinyal ke bawah graf (*dirty notification*) tanpa mengeksekusi komputasi atau template secara instan.
2. **Pull**: Ketika proses render dijadwalkan, hanya node yang terbukti *dirty* dan dikonsumsi oleh view yang akan membaca (*pull*) nilai terbaru dan memicu pembaruan DOM secara presisi (*targeted update*).

Pada arsitektur **Zoneless** (`provideExperimentalZonelessChangeDetection()`), Zone.js dinonaktifkan sepenuhnya. Angular memanfaatkan sinyal internal dari framework (seperti Signal updates, RxJS `AsyncPipe`, pemanggilan eksplisit `ChangeDetectorRef.markForCheck()`, atau event listener template) untuk menjadwalkan *tick* langsung ke scheduler browser menggunakan `queueMicrotask` atau `requestAnimationFrame`.

---

## 4. Why & What

| Paradigma / Fitur | Alasan Penggunaan (Why) | Definisi & Karakteristik (What) |
|---|---|---|
| **Incremental DOM** | Menghilangkan beban GC pada VDOM allocation, memangkas overhead bundle size untuk runtime framework. | Mekanisme kompilasi template langsung menjadi fungsi eksekusi manipulasi DOM berbasis linear buffer. |
| **Hierarchical DI** | Mengisolasi scope state data, mencegah kebocoran state antar instance modul, memungkinkan arsitektur modular/multi-tenant. | Topologi injeksi dependensi ganda (Element vs Environment) yang mengikuti nesting komponen DOM dan hierarki rute. |
| **Angular Signals** | Menghilangkan pemeriksaan pohon komponen global yang boros daya, menghasilkan komputasi reaktif synchronous dan aman dari *glitch*. | Tipe data primitif pembungkus nilai yang secara otomatis melacak pembaca (*consumer*) dan memberi tahu dependensi saat nilainya berubah. |
| **Standalone Components**| Menghapus boilerplate `NgModule`, menyederhanakan dependensi graf, mempermudah lazy loading dan tree-shaking native. | Komponen mandiri yang mendeklarasikan langsung daftar dependensi template-nya via properti `imports`. |

---

## 5. How (Workflow Detail)

Berikut siklus hidup runtime eksekusi Angular dari bootstrap hingga rendering zoneless:

```
[1. Bootstrap Phase]
  main.ts -> bootstrapApplication(AppComponent, appConfig)
    |
    v
  Inisialisasi PlatformRef & EnvironmentInjector (Root)
    |
    v
[2. View Creation Phase]
  Instansiasi AppComponent via ComponentFactory / Template Instructions
    |
    v
  Alokasi TView (Statik) & LView (Dynamic Array) untuk AppComponent
    |
    v
  Eksekusi Create Mode: ɵɵelementStart, ɵɵlistener, ɵɵelementEnd
    |
    v
  Penyusunan ElementInjector Tree pada DOM Node
    |
    v
[3. Reactive Binding Phase]
  Sinyal/State diregistrasikan ke Reactive Consumer View
    |
    v
[4. Event / Mutation Phase]
  State bermutasi via signal.update() atau interaksi pengguna
    |
    v
  Graph Dependency menandai LView terasosiasi sebagai DIRTY
    |
    v
[5. Render Scheduling Phase]
  Scheduler menjadwalkan microtask flush -> traversal terarah hanya pada LView yang DIRTY
    |
    v
  Eksekusi Update Mode: ɵɵadvance, ɵɵtextInterpolate, ɵɵproperty
    |
    v
  DOM asli dimutasi secara In-Place
```

---

## 6. Analogy & Diagram ASCII

### Analogi TView dan LView: Denah Arsitektur vs. Ruangan Fisik

Bayangkan pembangunan 100 unit rumah identik di sebuah kompleks perumahan:
- **`TView`** adalah **Kertas Cetak Biru (Blueprint)**: Hanya ada satu lembar denah arsitektur. Denah mencatat bahwa di koordinat `[0]` terdapat sakelar lampu, koordinat `[1]` terdapat pintu geser, dan koordinat `[2]` adalah pipa air. Kertas ini tidak menyimpan air atau listrik, melainkan hanya skema murni.
- **`LView`** adalah **Unit Rumah Fisik Nyata**: Setiap rumah memiliki wujud fisik aktual. Koordinat `[0]` menyimpan sakelar fisik milik Rumah No. 12, dan nilainya sedang *ON*. Rumah No. 13 memiliki sakelarnya sendiri, bernilai *OFF*.

Jika 100 rumah dibangun, Anda tidak menggambar 100 cetak biru baru; Anda menggunakan 1 cetak biru (`TView`) dan menerapkannya pada 100 alokasi lahan fisik (`LView`).

### Diagram Arsitektur Internal: Signal Dependency Graph & Runtime Flush

```
              [ Developer Action: signal.set("NEW_VAL") ]
                                   |
                                   v
                      +-------------------------+
                      |   Source Signal Node    |
                      |   value: "NEW_VAL"      |
                      |   version: 2            |
                      +-------------------------+
                                   |
         (Push Notification: Mark Dependents Dirty, Glitch-Free)
                                   v
             +-------------------------------------------+
             |         Computed Signal Node              |
             |  state: DIRTY | fn: () => sig() + " FX"   |
             +-------------------------------------------+
                                   |
                                   v
             +-------------------------------------------+
             |        LView Template Consumer Node       |
             |       Flags: LView.FLAGS |= DIRTY         |
             +-------------------------------------------+
                                   |
                                   v
                    [ Microtask Scheduler Queue ]
                                   |
               (Browser ticks -> Flush scheduled queue)
                                   v
             +-------------------------------------------+
             |      Execute Ivy Update Mode:             |
             |      ɵɵadvance(1)                         |
             |      ɵɵtextInterpolate(computedSig())     |
             +-------------------------------------------+
                                   |
                                   v
                   [ In-Place Direct Native DOM Mutation ]
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Directive Composition API & Type-Safe Injection

Pendekatan modern menggantikan warisan inheritance/decorator lama dengan memadukan `inject()`, `HostDirectives`, dan *Signals*.

```typescript
import { Directive, ElementRef, inject, input, effect } from '@angular/core';

// Reusable low-level interaction directive
@Directive({
  standalone: true,
  selector: '[appRippleEffect]'
})
export class RippleEffectDirective {
  private host = inject<ElementRef<HTMLElement>>(ElementRef);
  public rippleColor = input<string>('rgba(0,0,0,0.1)');

  constructor() {
    effect(() => {
      // Akses reactive input value
      this.host.nativeElement.style.setProperty('--ripple-col', this.rippleColor());
    });
  }
}

// Enterprise Component yang mengomposisikan Directive tanpa inheritance
@Directive({
  standalone: true,
  selector: 'button[appPrimaryBtn]',
  hostDirectives: [
    {
      directive: RippleEffectDirective,
      inputs: ['rippleColor: rippleStyle']
    }
  ],
  host: {
    'class': 'btn-primary-base',
    '(click)': 'onButtonClick($event)'
  }
})
export class PrimaryButtonDirective {
  onButtonClick(event: MouseEvent): void {
    // Isolated button handler logic
  }
}
```

### 7.2 Practical Example: Enterprise-Grade Dynamic Widget Engine (Zoneless-Ready)

Di aplikasi enterprise skala besar, view sering kali harus memuat widget pihak ketiga atau modul dinamis tanpa keterikatan deklaratif di template compile-time, tetap aman terhadap memori, serta memanfaatkan resolusi dependensi bertingkat (*hierarchical token override*).

```typescript
// widget-token.ts
import { InjectionToken, Type, Signal } from '@angular/core';

export interface WidgetPayload {
  tenantId: string;
  metricGroup: string;
}

export interface DynamicWidgetInstance {
  configure(payload: WidgetPayload): void;
  isReady: Signal<boolean>;
}

export const WIDGET_DATA_CONTEXT = new InjectionToken<WidgetPayload>('WIDGET_DATA_CONTEXT');

// widget-renderer.component.ts
import {
  Component,
  ChangeDetectionStrategy,
  ViewContainerRef,
  ComponentRef,
  inject,
  input,
  Injector,
  OnDestroy,
  effect,
  runInInjectionContext,
  EnvironmentInjector
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { DynamicWidgetInstance, WIDGET_DATA_CONTEXT, WidgetPayload } from './widget-token';

@Component({
  selector: 'app-dynamic-widget-host',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="widget-wrapper">
      <div class="widget-header">
        <span>Node Tenant: {{ payload().tenantId }}</span>
      </div>
      <!-- Tempat komponen dinamis disuntikkan secara imperatif -->
      <ng-container #anchor />
    </div>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class DynamicWidgetHostComponent implements OnDestroy {
  // Template Anchor
  private vcr = inject(ViewContainerRef);
  private envInjector = inject(EnvironmentInjector);

  // Modern input signals
  public payload = input.required<WidgetPayload>();
  public componentType = input.required<Type<DynamicWidgetInstance>>();

  private currentComponentRef: ComponentRef<DynamicWidgetInstance> | null = null;

  constructor() {
    // Sinkronisasi pemuatan komponen dengan lifecycle reactive signal
    effect(() => {
      const CompType = this.componentType();
      const currentPayload = this.payload();

      this.instantiateDynamicWidget(CompType, currentPayload);
    });
  }

  private instantiateDynamicWidget(comp: Type<DynamicWidgetInstance>, data: WidgetPayload): void {
    // 1. Bersihkan view container untuk mencegah leaking detached DOM nodes
    this.vcr.clear();
    if (this.currentComponentRef) {
      this.currentComponentRef.destroy();
      this.currentComponentRef = null;
    }

    // 2. Buat ElementInjector lokal khusus untuk instance widget ini
    const localInjector = Injector.create({
      providers: [
        {
          provide: WIDGET_DATA_CONTEXT,
          useValue: data
        }
      ],
      parent: this.vcr.injector
    });

    // 3. Render komponen secara dinamis menggunakan container injector kontekstual
    this.currentComponentRef = this.vcr.createComponent(comp, {
      injector: localInjector,
      environmentInjector: this.envInjector
    });

    // 4. Inisialisasi kontrak data
    this.currentComponentRef.instance.configure(data);

    // 5. Change detection execution isolation
    this.currentComponentRef.changeDetectorRef.markForCheck();
  }

  ngOnDestroy(): void {
    // Memastikan cleanup manual bila ViewContainerRef belum ter-flush otomatis
    if (this.currentComponentRef) {
      this.currentComponentRef.destroy();
      this.currentComponentRef = null;
    }
    this.vcr.clear();
  }
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Real-Time High-Frequency FX/Crypto Trading Dashboard

#### Konteks & Masalah:
Sebuah perusahaan finansial multinasional membangun sistem order book dan monitor valas (*Foreign Exchange*) real-time. Sistem menerima rata-rata **3.000 hingga 5.000 pesan WebSocket per detik**.
Aplikasi Angular versi awal mengalami:
- *UI Frame Drop*: FPS turun hingga di bawah 15 FPS (layar terasa membeku).
- Konsumsi memori browser membengkak lebih dari 1.8 GB dalam 10 menit pengoperasian, memicu browser crash (*Out of Memory*).
- Profiling DevTools menunjukkan bahwa Zone.js membajak setiap event WebSocket, memicu `ApplicationRef.tick()` global dan memeriksa seluruh pohon komponen sebanyak ribuan kali per detik.

#### Solusi Arsitektural:
1. **Transisi ke Zoneless / Isolated Signal Runtime**:
   Zone.js dieksekusi bypass menggunakan `runOutsideAngular()` untuk koneksi socket data stream, atau sepenuhnya bermigrasi ke mode Zoneless dengan memanfaatkan Angular Signals.
2. **Buffer Stream & Local In-Place Update via Signals**:
   Membuat pipeline RxJS yang mengelompokkan update transaksi dalam interval micro-batch (misal, 50ms) menggunakan operator `bufferTime()`, kemudian memperbarui sinyal state lokal.
3. **Penyempitan Ruang Lingkup Change Detection**:
   Penggunaan `ChangeDetectionStrategy.OnPush` pada baris tabel harga, memetakan sinyal mutasi hanya pada cell yang nilainya berubah (*tick-by-tick*).

```typescript
// financial-stream.service.ts
import { Injectable, signal, computed } from '@angular/core';
import { Subject, Observable } from 'rxjs';
import { bufferTime, filter } from 'rxjs/operators';

export interface PriceTick {
  symbol: string;
  price: number;
  timestamp: number;
}

@Injectable({ providedIn: 'root' })
export class MarketDataStreamingService {
  private socket!: WebSocket;
  private rawStream$ = new Subject<PriceTick>();

  // State Store terdesentralisasi berbasis Record Signal
  private marketSignals = new Map<string, ReturnType<typeof signal<PriceTick>>>();

  public initializeStream(wsUrl: string): void {
    // Jalankan murni di level native browser thread tanpa intervensi Zone.js
    this.socket = new WebSocket(wsUrl);
    this.socket.onmessage = (event: MessageEvent) => {
      const tick: PriceTick = JSON.parse(event.data);
      this.rawStream$.next(tick);
    };

    // Micro-batch buffer untuk meredam frekuensi mutasi
    this.rawStream$
      .pipe(
        bufferTime(50),
        filter((batch) => batch.length > 0)
      )
      .subscribe((batch) => {
        // Tulis batch mutasi secara sinkron ke dalam reactive dependency graph
        for (const tick of batch) {
          const targetSignal = this.marketSignals.get(tick.symbol);
          if (targetSignal) {
            targetSignal.set(tick);
          }
        }
      });
  }

  public getOrCreatePriceSignal(symbol: string) {
    if (!this.marketSignals.has(symbol)) {
      this.marketSignals.set(symbol, signal<PriceTick>({ symbol, price: 0, timestamp: Date.now() }));
    }
    return this.marketSignals.get(symbol)!.asReadonly();
  }
}
```

#### Hasil Terukur:
- **FPS UI**: Naik stabil ke **60 FPS** tanpa *stuttering*.
- **CPU Time (Scripting)**: Turun sebesar **78%** pada Chrome Performance Profiler.
- **Konsumsi Memori**: Stabil di angka **~120 MB** setelah 4 jam pengujian stress-test konstan.

---

## 9. Trade-offs & Comparisons

| Parameter Evaluasi | Virtual DOM (React-style) | Ivy Incremental DOM (Angular) | Zone.js Full Sweep (Default) | Angular Signals (Zoneless Engine) |
|---|---|---|---|---|
| **Alokasi Memori Runtime** | Tinggi (Membuat node VDOM baru saat diffing). | **Sangat Rendah** (Memodifikasi pointer array LView secara statis). | Sedang hingga Tinggi (Banyak menyimpan closure state event). | **Minimal** (Hanya menyimpan graf dependensi pointer). |
| **Kecepatan Cold-start / TTI**| Sedang (Membutuhkan runtime parsing abstraksi). | Cepat (Operasi instruksi linier langsung dieksekusi). | Lambat (Inisialisasi patching seluruh browser window API). | **Sangat Cepat** (Zero polyfill overhead Zone.js). |
| **Kemudahan Debugging** | Tinggi (Tree abstraction transparan, object inspectable). | Kompleks (Debugging internal LView/TView berupa numeric array). | Rendah (Stack trace kotor oleh wrapper zone.js). | **Tinggi** (StackTrace sinkron langsung dari pemanggil sinyal). |
| **Granularitas Reaktivitas** | Komponen-level (Seluruh fungsi komponen dieksekusi ulang). | Komponen-level instruksional. | Global Tree-level (Dari root hingga leaf node). | **Fine-Grained Node-level** (Targeted instruction branch). |
| **Complexity Budget** | Perlu manual optimization via memo/callback hooks. | Kompilator menangani beban optimasi secara otomatis. | Paradigma imperatif: *developer tidak perlu memikirkan tracking*. | Memerlukan disiplin deklaratif pembungkusan sinyal. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 `ExpressionChangedAfterItHasBeenCheckedError`

#### Penyebab Root-Cause:
Dalam mode pengembangan (*Development Mode*), Angular menjalankan proses Change Detection dua kali secara beruntun (`ApplicationRef.tick()` diikuti verifikasi pass kedua). Jika pada pass kedua binding menghasilkan nilai yang berbeda dari pass pertama, Angular mendeteksi inkonsistensi graf render dan melempar error ini. Masalah ini paling sering muncul saat lifecycle hook anak (`ngOnInit`, `ngAfterViewInit`) memutasi state parent secara sinkron melalui shared service atau event emitter.

```
Parent View Checked (Value = "A")
    |
    v
Child Component View Executes
    |
    v
Child mutates Parent State directly -> (Value changed to "B")
    |
    v
Verification Pass: Parent Checked Again!
Expected: "A", Actual found: "B"  ===> CRASH: ExpressionChangedAfterItHasBeenCheckedError
```

#### Solusi Arsitektural yang Benar:
Hindari modifikasi sinkron yang melintasi batasan hierarki hierarki atas (*upward data mutation*). Gunakan arsitektur sinyal satu arah atau tunda eksekusi ke microtask berikutnya jika benar-benar tak terhindarkan.

```typescript
// ❌ SALAH: Menyebabkan ExpressionChanged Error
ngAfterViewInit() {
  this.parentStateService.setTitle('Judul Baru');
}

// ✅ BENAR (Pendekatan 1 - Redesign ke Deklaratif Signal):
// Buat data mengalir dari atas ke bawah secara natural
public titleSignal = computed(() => this.childStateService.title());

// ✅ BENAR (Pendekatan 2 - Jika terpaksa sinkronisasi asynchronous boundary):
ngAfterViewInit() {
  queueMicrotask(() => {
    this.parentStateService.setTitle('Judul Baru');
  });
}
```

### 10.2 Memory Leak via Detached Element Injector / DOM Nodes

#### Penyebab Root-Cause:
Membuat komponen dinamis menggunakan `ViewContainerRef.createComponent()` atau mengalokasikan langganan `Observable.subscribe()` di dalam directive lokal, tetapi tidak mengeksekusi `ComponentRef.destroy()` atau `Subscription.unsubscribe()`. Instance komponen terhapus dari DOM visual, namun tetap hidup di dalam memori heap JavaScript karena referensi referensial yang masih dipegang oleh Event Bus, Root Injector, atau Global Stream.

#### Solusi Arsitektural:
Gunakan `takeUntilDestroyed()` dari `@angular/core/rxjs-interop` yang mengaitkan siklus hidup subscription secara otomatis ke `DestroyRef` milik node tersebut:

```typescript
import { Component, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { GlobalEventBus } from './global-event-bus';

@Component({
  standalone: true,
  template: `<div>Listener Active</div>`
})
export class LeakProofComponent {
  private eventBus = inject(GlobalEventBus);

  constructor() {
    this.eventBus.events$
      .pipe(takeUntilDestroyed()) // Otomatis unhook saat ComponentRef dihancurkan
      .subscribe((data) => this.handleEvent(data));
  }

  private handleEvent(data: unknown): void {
    // Process data
  }
}
```

### 10.3 Circular Dependency pada Hierarchical Injection Token

#### Penyebab Root-Cause:
Dua service atau dependensi lokal saling menginjeksi satu sama lain secara silang (`ServiceA -> ServiceB -> ServiceA`), memicu resolusi dependensi rekursif tanpa ujung saat runtime runtime membentuk injektor graf.

#### Solusi:
Gunakan abstraksi antarmuka via `InjectionToken` murni, pindahkan dependensi bersama ke kelas ketiga, atau gunakan `forwardRef()` sebagai solusi sementara:

```typescript
// service-a.ts
import { Injectable, inject, forwardRef } from '@angular/core';
import { ServiceB } from './service-b';

@Injectable({ providedIn: 'root' })
export class ServiceA {
  // Resolusi dievaluasi saat runtime instansiasi, bukan kompilasi modul
  private serviceB = inject(forwardRef(() => ServiceB));
}
```

---

## 11. Best Practices & Production Checklist

1. **Gunakan Mode Zoneless atau Enforce `OnPush` di Seluruh Pohon**:
   Hindari `ChangeDetectionStrategy.Default` pada komponen produksi berskala besar. Tetapkan komponen menjadi `OnPush` atau hapus Zone.js secara sistemik.
2. **Gunakan `inject()` Function Menggantikan Constructor Injection**:
   Memberikan dukungan type inference yang lebih kuat, memudahkan inheritance, dan mendukung *factory composition context*.
3. **Gunakan `runInInjectionContext` untuk Factory Dinamis**:
   Saat mengeksekusi logika yang memerlukan dependensi Angular di luar siklus lifecycle standar (misalnya di Web Worker atau callback pihak ketiga), bungkus dalam `runInInjectionContext`.
4. **Validasi Template Type Checking Maksimal**:
   Pastikan file `tsconfig.json` menyertakan konfigurasi ketat:
   ```json
   "angularCompilerOptions": {
     "strictTemplates": true,
     "strictInjectionParameters": true,
     "strictInputAccessModifiers": true
   }
   ```
5. **Cegah Penggunaan Direct DOM Manipulation**:
   Hindari `document.getElementById` atau interaksi langsung dengan objek `Element`. Gunakan `ElementRef` yang diabstraksi bersama `Renderer2` untuk mempertahankan kompatibilitas lingkungan Server-Side Rendering (Angular Universal / SSR) dan perlindungan dari serangan Cross-Site Scripting (XSS).
6. **Batasi Scope Providers**:
   Jangan mendaftarkan service transien di `providedIn: 'root'`. Letakkan di `providers` komponen jika masa hidup service tersebut terikat langsung dengan siklus hidup komponen visual.

---

## 12. Hands-on Practice

Dalam sesi praktikum ini, Anda akan membangun modul isolasi plugin multi-tenant dengan dependensi bertingkat (*dynamic injection scope*) di direktori `hands-on/m02/`.

### Struktur File:
```
hands-on/m02/
├── tokens/
│   └── tenant-config.token.ts
├── services/
│   └── metrics-collector.service.ts
├── components/
│   ├── tenant-badge.component.ts
│   └── tenant-dashboard.component.ts
└── main-practice.ts
```

### Langkah 1: Definisikan Kontrak dan Token Konfigurasi
Buat file `hands-on/m02/tokens/tenant-config.token.ts`:

```typescript
import { InjectionToken } from '@angular/core';

export interface TenantConfig {
  tenantId: string;
  themeColor: string;
  allowedFeatures: string[];
}

export const TENANT_CONFIG = new InjectionToken<TenantConfig>('TENANT_CONFIG');
```

### Langkah 2: Buat Scoped Metrics Service
Buat file `hands-on/m02/services/metrics-collector.service.ts`. Service ini sengaja tidak menggunakan `providedIn: 'root'` agar instansinya terisolasi di tingkat `ElementInjector`.

```typescript
import { Injectable, inject, signal } from '@angular/core';
import { TENANT_CONFIG } from '../tokens/tenant-config.token';

@Injectable()
export class MetricsCollectorService {
  private config = inject(TENANT_CONFIG);
  private executionCount = signal<number>(0);

  public readonly currentCount = this.executionCount.asReadonly();

  public trackAction(actionName: string): void {
    this.executionCount.update((prev) => prev + 1);
    console.log(`[Tenant: ${this.config.tenantId}] Action: ${actionName} | Count: ${this.executionCount()}`);
  }
}
```

### Langkah 3: Buat Child Badge Component
Buat file `hands-on/m02/components/tenant-badge.component.ts`:

```typescript
import { Component, ChangeDetectionStrategy, inject } from '@angular/core';
import { TENANT_CONFIG } from '../tokens/tenant-config.token';
import { MetricsCollectorService } from '../services/metrics-collector.service';

@Component({
  selector: 'app-tenant-badge',
  standalone: true,
  template: `
    <div [style.borderColor]="config.themeColor" class="badge-box">
      <span>Tenant: <strong>{{ config.tenantId }}</strong></span>
      <span>Dispatched Events: {{ metrics.currentCount() }}</span>
      <button (click)="metrics.trackAction('BADGE_CLICK')">Emit Action</button>
    </div>
  `,
  styles: [`
    .badge-box {
      border: 2px solid;
      padding: 12px;
      margin: 8px 0;
      border-radius: 6px;
      display: flex;
      gap: 12px;
      align-items: center;
    }
  `],
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class TenantBadgeComponent {
  // Resolusi inject mencari injector hierarki milik parent yang mendefinisikan token
  public config = inject(TENANT_CONFIG);
  public metrics = inject(MetricsCollectorService);
}
```

### Langkah 4: Buat Hierarchical Host Dashboard
Buat file `hands-on/m02/components/tenant-dashboard.component.ts`:

```typescript
import { Component, ChangeDetectionStrategy, input } from '@angular/core';
import { TenantBadgeComponent } from './tenant-badge.component';
import { TENANT_CONFIG, TenantConfig } from '../tokens/tenant-config.token';
import { MetricsCollectorService } from '../services/metrics-collector.service';

@Component({
  selector: 'app-tenant-dashboard',
  standalone: true,
  imports: [TenantBadgeComponent],
  template: `
    <div class="tenant-card">
      <h2>Partition Scope Container</h2>
      <!-- Child mengonsumsi provider yang didefinisikan secara lokal di injector ini -->
      <app-tenant-badge />
    </div>
  `,
  // Di sinilah isolasi ElementInjector didefinisikan untuk setiap subtree
  providers: [
    MetricsCollectorService,
    {
      provide: TENANT_CONFIG,
      useFactory: (comp: TenantDashboardComponent): TenantConfig => ({
        tenantId: comp.tenantId(),
        themeColor: comp.primaryColor(),
        allowedFeatures: ['METRICS', 'EXPORT']
      }),
      deps: [TenantDashboardComponent]
    }
  ],
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class TenantDashboardComponent {
  public tenantId = input.required<string>();
  public primaryColor = input.required<string>();
}
```

---

## 13. Exercises

### 13.1 Level: Easy
Buat directive mandiri bernama `AutoTrimDirective` yang mendengarkan event input pada elemen `<input>`, melakukan sanitasi *leading/trailing whitespace*, serta memutasi nilai model secara sinkron menggunakan `ElementRef` dan `Renderer2` tanpa memicu error `ExpressionChangedAfterItHasBeenCheckedError`.

### 13.2 Level: Medium
Rancang custom injection token bernama `API_RETRY_STRATEGY` dengan konfigurasi default:
- `maxRetries: 3`
- `delayMs: 1000`

Terapkan modifikasi injection token di tingkat child-route atau sub-komponen tertentu menjadi `maxRetries: 5`, dan verifikasi via unit test bahwa parent component tetap menggunakan konfigurasi default tanpa polusi state.

### 13.3 Level: Hard
Bangun komponen layout dinamis berbasis grid (`AdaptiveGridComponent`) yang mampu menerima daftar tipe komponen secara dinamis saat runtime, merendernya ke dalam `ViewContainerRef` internal, menginjeksi token koordinat matriks (`GRID_CELL_COORDINATES`) secara independen untuk tiap cell, dan secara otomatis memusnahkan (*destroy*) instance komponen jika terjadi reorganisasi tata letak tanpa meninggalkan residual LView di heap memory.

---

## 14. Enterprise Architectural Challenge

### Skenario:
Sebuah perusahaan Software-as-a-Service (SaaS) perbankan mengharuskan platform frontend mereka mampu memuat *Plugin Micro-Frontend Eksternal* yang dikompilasi secara independen oleh tim pihak ketiga secara runtime (tanpa proses *re-build* aplikasi shell utama).

### Batasan Arsitektur & Persyaratan Teknis:
1. **Dynamic Sandbox Resolution**:
   Setiap plugin harus dimuat via URL JavaScript murni menggunakan dynamic `import()`.
2. **Contextual Sandbox Injection**:
   Plugin tidak boleh mengakses `EnvironmentInjector` root secara langsung. Shell harus membungkus instance plugin dalam `Injector` khusus yang membatasi akses token backend (misalnya melempar error jika plugin mencoba menginjeksi `ShellSecurityContextToken`).
3. **Zoneless Signal Bridge**:
   Plugin mungkin dibangun menggunakan versi Angular yang lebih baru atau berbeda dari shell. Anda wajib merancang kontrak komunikasi reaktif berbasis *Signal-to-Signal Bridge* atau *Custom Event Target API* tanpa bergantung pada event loop global Zone.js.
4. **Memory Strict Bounds**:
   Jika pengguna berpindah tab modul perbankan, seluruh subtree DOM, script runtime plugin, dynamic views, serta LView instance wajib dibersihkan secara instan dengan jejak referensi *0 byte* terverifikasi pada snapshot Memory Chrome DevTools.

### Tugas Anda:
Rancang struktur diagram alur injeksi dependensi, antarmuka kelas TypeScript, serta mekanisme dynamic load execution engine yang memenuhi kriteria keamanan dan isolasi tingkat enterprise di atas.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Soal)

#### Q1: Apa perbedaan paling mendasar antara model Virtual DOM dan Incremental DOM milik Angular Ivy?
- A. Virtual DOM tidak menggunakan JavaScript, sedangkan Incremental DOM murni JavaScript.
- B. Incremental DOM tidak menciptakan pohon data memori perantara saat mendeteksi perubahan; ia memodifikasi DOM asli secara in-place via instruksi linier.
- C. Virtual DOM selalu lebih cepat daripada Incremental DOM dalam segala ukuran aplikasi.
- D. Incremental DOM memerlukan Zone.js untuk berjalan, sedangkan Virtual DOM tidak.

#### Q2: Apa fungsi utama dari struktur data internal `TView`?
- A. Menyimpan status binding runtime spesifik untuk satu instance komponen tunggal.
- B. Berisi referensi native elemen DOM nyata dari setiap instance view.
- C. Menyimpan cetak biru statis (skema DOM, indeks binding, instruksi template) yang dibagikan ke seluruh instance komponen bertipe sama.
- D. Menggantikan peran Event Loop browser pada runtime Angular.

#### Q3: Resolution modifier manakah yang membatasi pencarian dependensi hanya sampai host view dari komponen saat ini?
- A. `@Self()`
- B. `@Host()`
- C. `@SkipSelf()`
- D. `@Optional()`

#### Q4: Perilaku apa yang terjadi jika dependensi tidak ditemukan dalam hierarki `ElementInjector`?
- A. Angular langsung melempar `NullInjectorError` tanpa memeriksa injector lain.
- B. Pencarian dilanjutkan ke hierarki `EnvironmentInjector` dari level rute aktif hingga ke root platform injector.
- C. Nilai otomatis diisi dengan `null`.
- D. Framework merestart Change Detection cycle.

#### Q5: Fitur baru apa di Angular modern yang memungkinkan penambahan kemampuan fungsional ke suatu host element tanpa menggunakan warisan kelas (*class inheritance*)?
- A. Structural Directives
- B. Module Federation
- C. Directive Composition API (`hostDirectives`)
- D. ViewProviders

---

### Bagian 2: Intermediate (5 Soal)

#### Q6: Mengapa error `ExpressionChangedAfterItHasBeenCheckedError` hanya muncul pada saat aplikasi dijalankan dalam Development Mode?
- A. Karena production mode menonaktifkan change detection sama sekali.
- B. Karena Angular sengaja menjalankan siklus pengecekan kedua (*verification pass*) di Development Mode untuk mendeteksi mutasi state yang tidak deterministik di luar alur unidirectional data flow.
- C. Karena TypeScript compiler menghapus metadata decorator di production mode.
- D. Karena itu adalah bug bawaan browser saat mengaktifkan Source Map.

#### Q7: Jika Anda mendaftarkan service pada array `viewProviders` dari `ParentComponent`, komponen manakah yang DAPAT menginjeksi service tersebut?
- A. Semua komponen proyek aplikasi secara global.
- B. Template view internal milik `ParentComponent` saja, tetapi TIDAK dapat diakses oleh komponen yang diproyeksikan melalui `<ng-content>`.
- C. Hanya komponen anak yang disuntikkan via `<ng-content>`.
- D. Hanya service lain yang terdaftar di `EnvironmentInjector`.

#### Q8: Bagaimana cara kerja algoritma push-pull reactivity pada Angular Signals?
- A. Push mengeksekusi re-render DOM seketika; Pull membatalkan subscription yang tidak aktif.
- B. Push mendistribusikan notifikasi dirty ke consumer graf; Pull mengevaluasi dan membaca nilai terbaru saat nilai tersebut benar-benar diminta oleh render scheduler atau pemanggil.
- C. Push mengambil data dari backend WebSocket; Pull mengirimkannya ke REST API.
- D. Push dan pull berjalan bersamaan secara asynchronous di dalam Web Worker terpisah.

#### Q9: Apa bahaya utama dari mendaftarkan dynamic component instance ke `ViewContainerRef` tanpa menyimpan referensi `ComponentRef` dan tidak memanggil `destroy()` saat komponen induk dilepas?
- A. Mengakibatkan template compile error secara diam-diam.
- B. Menahan referensi LView dan DOM node di heap memori melalui injector retention chain, menyebabkan memory leak.
- C. Mengubah change detection strategy dari OnPush menjadi Default.
- D. Mengubah nilai runtime `TView` secara global.

#### Q10: Kapan Anda harus menggunakan fungsi pembantu `runInInjectionContext`?
- A. Saat membuat constructor class secara reguler.
- B. Saat perlu mengeksekusi fungsi yang memanfaatkan `inject()` di luar waktu inisialisasi sinkron (misalnya di dalam callback asynchronous, event listener native, atau dynamic loader).
- C. Hanya saat menjalankan unit test dengan Jasmine/Karma.
- D. Setiap kali memanggil `signal.set()`.

---

### Bagian 3: Skenario Kasus Produksi (3 Kasus)

#### Skenario A:
Sebuah portal berita dengan traffic tinggi mengimplementasikan lazy-loaded Standalone Route untuk halaman baca artikel. Di dalam route tersebut dideklarasikan:
```typescript
providers: [ArticleAnalyticsService]
```
Namun, engineer mendapati bahwa setiap kali pembaca berpindah antar artikel, data analytic dari artikel sebelumnya masih tersimpan di memory dan tidak pernah direset. Setelah ditelusuri, `ArticleAnalyticsService` memiliki decorator `@Injectable({ providedIn: 'root' })`. 

*Jelaskan mengapa konfigurasi ganda tersebut menyebabkan masalah, dan apa tindakan perbaikannya!*

#### Skenario B:
Pada aplikasi enterprise dashboard, terdapat sebuah komponen chart berat (`DataChartComponent`) yang dibungkus dalam modal popup. Setiap kali modal ditutup dan dibuka kembali sebanyak 20 kali, penggunaan RAM browser meningkat dari 60MB ke 900MB. Tim mendapati bahwa chart menggunakan library pihak ketiga non-Angular (misal: Chart.js / D3) di dalam directive-nya.

*Identifikasi letak kebocoran memori potensial pada integrasi DOM/Library pihak ketiga dan berikan struktur perbaikannya!*

#### Skenario C:
Aplikasi Enterprise Core Anda sedang dalam proses migrasi bertahap dari Zone.js ke Zoneless Mode (`provideExperimentalZonelessChangeDetection`). Sebuah form validation directive warisan (*legacy*) mengandalkan event `(keyup)` native untuk menghitung validitas form dan menyimpan hasilnya pada variabel privat reguler (bukan Signal). Setelah Zone.js dinonaktifkan, tampilan pesan validasi di layar tidak pernah terupdate, padahal log konsol menunjukkan perhitungan berjalan.

*Mengapa tampilan tidak terupdate pada arsitektur Zoneless, dan bagaimana cara memulihkan reaktivitas komponen tersebut secara idiomatik sesuai standar Angular modern?*

---

### Kunci Jawaban & Pembahasan

#### Kunci Bagian 1:
1. **B** — Incremental DOM mengeksekusi instruksi langsung pada native DOM tanpa membuat representasi pohon perantara di memori.
2. **C** — `TView` adalah blueprint statis bersama (immutable) yang dibagikan kepada seluruh instance komponen tersebut.
3. **B** — `@Host()` membatasi penelusuran resolusi DI hingga komponen yang menjadi host template view saat ini.
4. **B** — Resolusi dependensi bertingkat akan berpindah dari `ElementInjector` ke hierarki `EnvironmentInjector` sebelum melempar error.
5. **C** — Directive Composition API via properti `hostDirectives`.

#### Kunci Bagian 2:
6. **B** — Verification pass dijalankan khusus di Development mode untuk memastikan kepatuhan terhadap siklus *Unidirectional Data Flow*.
7. **B** — `viewProviders` membatasi visibilitas dependensi hanya untuk elemen internal template komponen itu sendiri, memblokirnya dari anak yang diproyeksikan melalui `<ng-content>`.
8. **B** — Push hanya menandai node konsumen sebagai DIRTY; pembacaan aktual (*evaluation*) di-pull saat eksekusi render dijalankan oleh scheduler.
9. **B** — Objek referensi native yang terikat pada hierarki injector tidak dapat dibersihkan oleh Garbage Collector jika pointer internal container-nya masih memegang referensi aktif.
10. **B** — `runInInjectionContext` menyediakan injection context aktif buatan untuk scope komputasi yang berjalan di luar waktu konstruksi instance reguler.

#### Pembahasan Skenario Kasus Produksi:

- **Skenario A**: 
  Penyebab: `@Injectable({ providedIn: 'root' })` memaksa compiler mendaftarkan service ke tingkat *Root EnvironmentInjector* sebagai singleton global aplikasi. Pendaftaran ulang pada array `providers` di route konfigurasi menjadi terabaikan atau menyebabkan ambiguitas hierarki di mana instansi root yang hidup permanen terus dipakai.
  Solusi: Hapus metadata `{ providedIn: 'root' }` dari decorator `@Injectable()` pada `ArticleAnalyticsService` dan biarkan service tersebut murni di-provide pada konfigurasi rute atau komponen level agar lifecycle service tersebut dimusnahkan secara alami saat rute berganti.

- **Skenario B**:
  Penyebab: Library manipulasi visual pihak ketiga seperti Chart.js/D3 menambahkan referensi callback event listener native langsung ke elemen DOM window atau canvas, dan memegang closure memori internal. Ketika komponen Angular dihancurkan (`ngOnDestroy`), referensi library visual native belum di-destroy secara eksplisit, menyebabkan seluruh detached DOM tree dan LView terperangkap di heap memory (*Zombie View*).
  Solusi: Implementasikan `OnDestroy` atau gunakan `DestroyRef` untuk secara eksplisit memanggil method pembersihan library pihak ketiga (misalnya `chartInstance.destroy()`), menghapus semua event listener eksternal, dan melepaskan referensi DOM element ke `null`.

- **Skenario C**:
  Penyebab: Pada arsitektur Zoneless, Angular tidak lagi menggunakan monkey-patch Zone.js untuk mendeteksi event native browser seperti `(keyup)` guna memicu *dirty checking* global. Karena state disimpan pada variabel biasa (non-reactive), Angular tidak menerima sinyal notifikasi bahwa ada bagian view yang berubah.
  Solusi:
  1. Ubah variabel internal penampung validitas form menjadi **Signal** (`validitySignal = signal<boolean>(false)`). Perubahan nilai via `set()` atau `update()` akan secara otomatis memberitahukan scheduler Zoneless untuk me-refresh LView terkait; ATAU
  2. Suntikkan `ChangeDetectorRef` dan panggil secara eksplisit `cdr.markForCheck()` di akhir event handling kalkulasi validasi tersebut.

---

## 16. Summary

- **Ivy Runtime Engine** menggunakan pendekatan linear **Incremental DOM** dengan membagi representasi memori menjadi **`TView`** (cetak biru statis bersama) dan **`LView`** (state dinamis per instance komponen), meminimalkan alokasi memori GC secara drastis dibandingkan arsitektur Virtual DOM.
- **Hierarchical Dependency Injection** beroperasi dalam dua pohon terpisah: **`ElementInjector`** (mengikuti hierarki pohon visual DOM) dan **`EnvironmentInjector`** (mengikuti hierarki modularitas rute dan aplikasi). Resolusi dapat dikontrol secara presisi menggunakan modifiers `@Host`, `@Self`, `@SkipSelf`, dan `@Optional`.
- **Evolusi Reaktivitas Angular** bertransformasi dari pendekatan pemindaian global berbasis **Zone.js** menuju fine-grained reactivity berbasis **Angular Signals**. Model ini menggunakan mekanisme koordinasi *push-pull* yang glitch-free dan membuka kapabilitas **Zoneless Runtime** berkecepatan tinggi.
- Arsitektur produksi modern menuntut pemanfaatan **Standalone Components**, pembersihan memori imperatif via **`DestroyRef`**, composability melalui **Directive Composition API**, serta kepatuhan mutlak terhadap arsitektur *unidirectional data flow* untuk mencegah degradasi performa dan memory leaks.