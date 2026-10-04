# Modul Pembelajaran: Performa Lanjutan, Zoneless Architecture, & Micro-Frontends

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** Frontend & Mobile Engineering
*   **Kategori:** 03-Frontend-and-Mobile
*   **Spesialisasi:** Advanced Angular Enterprise Architecture
*   **Modul:** Bab 10, Modul 01
*   **Judul:** Performa Lanjutan, Zoneless Architecture, & Micro-Frontends
*   **Tingkat Kesulitan:** Advanced / Staff Engineer
*   **Prasyarat:** Angular Signals Fundamental, RxJS Advanced Operators, Angular Dependency Injection Engine, Webpack/Vite Internals, Distributed Architecture Basics.
*   **Waktu Penyelesaian:** 6-8 Jam Pelatihan Intensif

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta mampu:
1.  **Membongkar dan Merekonstruksi Siklus Deteksi Perubahan:** Menganalisis secara mendalam bagaimana runtime Angular beralih dari manipulasi asynchronous monkey-patching via `zone.js` ke reaktivitas granular berbasis Signal Graph.
2.  **Mengimplementasikan Arsitektur Zoneless Penuh:** Mengonfigurasi aplikasi Angular produksi tanpa dependensi `zone.js`, memanfaatkan `provideExperimentalZonelessChangeDetection()` (atau primitive scheduler berbasis `ChangeDetectorRef.markForCheck` & Signals), serta mengeliminasi memory and runtime overhead.
3.  **Mendesain dan Membangun Arsitektur Micro-Frontend Enterprise:** Merancang topologi decoupled frontend menggunakan Webpack Module Federation dan `@angular-architects/module-federation` secara type-safe dan resilient.
4.  **Mengelola Cross-Micro-Frontend State & Lifecycle Synchronization:** Mengimplementasikan orkestrasi event terisolasi, sandboxing styling, serta lazy-loading boundary yang tahan terhadap kegagalan parsial jaringan.
5.  **Mendiagnosis dan Mengoptimalkan Metrik Web Vitals:** Menekan Interaction to Next Paint (INP) dan Cumulative Layout Shift (CLS) pada enterprise scale application melalui teknik zoneless execution dan granular micro-chunking.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: Coarse-Grained Pull vs Fine-Grained Push-Pull
Secara historis, mental model deteksi perubahan Angular dibangun di atas konsep *Coarse-Grained "Dirty Checking" Cycle*. Setiap kali terjadi event asynchronous (klik, `setTimeout`, HTTP response), `zone.js` mencegat execution context, membunyikan alarm "ada sesuatu yang berubah di suatu tempat", lalu Angular mengeksekusi traversal pohon komponen dari akar (`RootComponent`) ke seluruh daun (`Leaf Components`) untuk memvalidasi state mana yang kotor (dirty).

```
[Mental Model Historis: Zone.js]
Asynchronous Event -> Monkey-Patched API -> onTurnDone Notification -> Full Component Tree Traversal
```

Dalam paradigma **Zoneless Architecture berbasis Signals**, mental model beralih ke *Fine-Grained Reactive Graph*:
1. State direpresentasikan sebagai node dalam Dynamic Dependency Graph.
2. View template secara langsung berlangganan (subscribes) secara implisit ke state node tersebut.
3. Perubahan nilai pada Signal menandai (dirty-marking) node konsumen secara langsung tanpa menginterupsi seluruh pohon komponen.
4. Scheduler engine Angular cukup menjadwalkan render mikro hanya pada boundary komponen yang relevan via microtask queue engine bawaan browser.

```
[Mental Model Modern: Zoneless Signal Graph]
Signal Mutation -> Producer Notifies Consumer Node -> Scheduler Registers Microtask -> Granular DOM Patch
```

### Mental Model Micro-Frontends: Desentralisasi Monolitik
Micro-frontends tidak boleh dipandang sebagai kumpulan `<iframe>` atau aplikasi mandiri yang di-bundle menjadi satu halaman tanpa aturan. Mental model yang benar adalah **Federasi Dependensi Terdistribusi (Distributed Dependency Federation)**:
*   Aplikasi Host (Shell) bertindak sebagai Service Orchestrator dan Identity Provider.
*   Aplikasi Remote bertindak sebagai Autonomous Feature Domain yang mengekspor unit fungsional (Components/Routes) pada tataran runtime.
*   Jaringan modul diikat bukan saat proses kompilasi (*compile-time binding*), melainkan saat runtime (*runtime dependency resolution*) melalui runtime manifest.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### 1. Perbandingan Arsitektur: Zone.js Traversal vs Zoneless Reactive Scheduler

```
+-----------------------------------------------------------------------------------+
|                        KLASIK: ZONE.JS TOP-DOWN SWEEP                             |
+-----------------------------------------------------------------------------------+

     [ Event: (click) ]  ==> [ zone.js Monkey Patch ] ==> triggers onMicrotaskEmpty()
                                                                  |
                                                                  v
                                                           [ Root Component ]
                                                             /          \
                                                            v            v
                                                       [Comp A]       [Comp B]
                                                        /     \         /    \
                                                       v       v       v      v
                                                     [C1]     [C2]   [C3]    [C4]
                                                     
    * Seluruh cabang dicek ulang (O(N) traversal), kecuali OnPush memotong cabang aktif.
    * Memori terpakai untuk mempertahankan async stack context.

+-----------------------------------------------------------------------------------+
|                   MODERN: ZONELESS + SIGNALS REACTIVE GRAPH                       |
+-----------------------------------------------------------------------------------+

     [ Signal Mutated: count.set(2) ]
                   |
                   |--> Producer mengabari Consumers via Reactive Graph
                   |
     +-------------v-------------+
     |   Angular Internal Engine  |  ==> Menjadwalkan microtask: requestAnimationFrame/
     |    (Reactive Scheduler)   |      queueMicrotask (Batching Notification)
     +-------------+-------------+
                   |
                   +------------------------------+
                   |                              |
                   v                              v
            [Comp A (Consumer)]            [Comp C4 (Consumer)]
          HANYA DOM Node Terikat         HANYA DOM Node Terikat
              yang Diperbarui                yang Diperbarui
              
    * Tidak ada traversal menyeluruh (O(1) langsung ke target).
    * Bebas dari overhead monkey-patching zone.js.
```

### 2. Arsitektur Enterprise Micro-Frontends dengan Module Federation

```
+-----------------------------------------------------------------------------------------+
|                                    BROWSER RUNTIME                                      |
+-----------------------------------------------------------------------------------------+
|                                                                                         |
|   +---------------------------------------------------------------------------------+   |
|   |                        SHELL / HOST APPLICATION (:4200)                         |   |
|   |                                                                                 |   |
|   |   +-------------------+  +-----------------------+  +-----------------------+   |   |
|   |   |  App Shell Core   |  | Event Bus (Broadcast) |  |   Shared Libraries    |   |   |
|   |   |  - Ng Router      |  | - SignalStore Matrix  |  |   - @angular/core     |   |   |
|   |   |  - Auth State     |  | - Cross-Domain Msg    |  |   - @angular/common   |   |   |
|   |   +---------+---------+  +-----------+-----------+  +-----------+-----------+   |   |
|   +-------------|------------------------|--------------------------|---------------+   |
|                 | Dynamic Route Import   | Event Propagation        | Singleton Injection
|                 v                        v                          v                   |
|   +-----------------------------+        |        +-----------------------------+       |
|   |  REMOTE 1: ORDER DOMAIN     |        |        | REMOTE 2: PAYMENT DOMAIN    |       |
|   |  (Port :4201)               |        |        | (Port :4202)                |       |
|   |  - remoteEntry.js           |        |        | - remoteEntry.js            |       |
|   |  - Exposed: './OrderModule' | <------+------> | - Exposed: './PaymentMod'   |       |
|   |  - Standalone Order Route   |                 | - Standalone Payment Route  |       |
|   +-----------------------------+                 +-----------------------------+       |
|                                                                                         |
+-----------------------------------------------------------------------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### Mekanisme Zoneless: Penghapusan Monkey-Patching Engine
`zone.js` bekerja dengan mengganti referensi fungsi asynchronous global di browser:
```javascript
// Konsep internal Zone.js monkey patching
const originalAddEventListener = window.EventTarget.prototype.addEventListener;
window.EventTarget.prototype.addEventListener = function(type, listener, options) {
  const wrappedListener = function(...args) {
    // 1. Masuk execution zone
    // 2. Eksekusi callback asli
    // 3. Picu deteksi perubahan global (onTurnDone -> tick())
    return Zone.current.runGuarded(listener, this, args);
  };
  return originalAddEventListener.call(this, type, wrappedListener, options);
};
```
Dalam arsitektur Zoneless, Angular mengeliminasi ketergantungan ini sepenuhnya. Mekanismenya diatur oleh antarmuka `ChangeDetectionScheduler`:
1.  **Notification Pipeline**: Ketika primitive reactive (seperti `WritableSignal`, method `markForCheck()`, atau template event listener bawaan Angular) mengalami interaksi, primitive tersebut memanggil `ChangeDetectionScheduler.notify()`.
2.  **Scheduler Coalescing**: Scheduler Angular mengumpulkan (*batching*) beberapa notifikasi ke dalam satu siklus microtask browser menggunakan `queueMicrotask()` atau `requestAnimationFrame()`.
3.  **Application Ref Synchronization**: Scheduler secara eksplisit mengeksekusi sinkronisasi tampilan hanya pada view-view yang memiliki flag `Consumer` kotor (`LView` flags).

### Module Federation: Anatomi Runtime Loading
Webpack Module Federation bekerja dengan membagi bundling ke dalam tiga komponen dasar:
1.  `remoteEntry.js`: Manifest kecil yang berisi tabel pemetaan (*manifest table*) chunk JavaScript, modul yang diekspos (*exposes*), dan kebutuhan dependensi bersama (*shared dependencies*).
2.  `Container Controller`: Objek global (`window.<remoteScope>`) yang diinisialisasi oleh `remoteEntry.js`, memiliki antarmuka standar:
    *   `init(sharedScope)`: Melakukan inisialisasi namespace modul bersama dan melakukan resolusi versi (semantic versioning fallback).
    *   `get(moduleName)`: Mengembalikan factory function untuk instantiation modul yang diminta.
3.  `Shared Scope Matrix`: Registry singleton runtime (`__webpack_share_scopes__.default`) tempat aplikasi Host dan Remote mendaftarkan library seperti `@angular/core`. Jika versi kompatibel, instance di memori akan dipakai bersama; jika tidak kompatibel, fallback isolated chunk akan di-load secara dinamis.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Zoneless Reactivity Graph & Signal Dependency Tracking
Secara internal di `@angular/core`, Signal diimplementasikan menggunakan arsitektur **Push/Pull Directed Acyclic Graph (DAG)**.

1.  **Node Types**:
    *   *Producer*: Signal yang menyimpan nilai mutabel (`WritableSignal`) atau turunan (`ComputedSignal`).
    *   *Consumer*: Konteks reaktif yang membaca producer, seperti `effect()` atau template rendering expression node (`ReactiveLViewConsumer`).
2.  **Fase Push (Dirtiness Propagation)**:
    Ketika Anda memanggil `.set()` atau `.update()` pada sebuah Signal:
    *   Producer mengiterasi seluruh daftar Consumer yang mencatatnya sebagai dependensi.
    *   Producer mengirimkan sinyal status "Dirty" (hanya satu bit flag) ke Consumer.
    *   Pada tahap ini, **tidak ada kalkulasi nilai baru**. Yang ditransmisikan hanyalah invalidasi status.
3.  **Fase Pull (Lazy Evaluation)**:
    Ketika scheduler Angular mencapai giliran eksekusi frame DOM:
    *   Renderer membaca Consumer yang kotor.
    *   Consumer secara rekursif meminta (*pull*) nilai terbaru dari Producer.
    *   Jika Producer adalah `computed()`, ia hanya mengevaluasi ulang logikanya jika nilai producer hulu (*upstream*) benar-benar telah berubah nilainya (`===` atau custom equality checker).

### Webpack Module Federation: Dynamic Host-Remote Resolution
Dalam arsitektur micro-frontend dinamis, URL Remote tidak boleh di-*hardcode* pada build time. Kita menggunakan arsitektur **Dynamic Remote Manifest**:
1. Host memuat file konfigurasi runtime `manifest.json`.
2. Angular Router membaca manifest tersebut dan mengonfigurasi jalur routing secara dinamis menggunakan `loadChildren` atau `loadComponent`.
3. Komponen federasi dimuat secara asinkron (*lazy chunk*). Seluruh siklus Dependency Injection (DI) Angular pada remote dipetakan sebagai anak (*child injector*) dari Host root injector, atau terisolasi penuh melalui *EnvironmentInjector* mandiri.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah perbandingan nyata: aplikasi zoneless mandiri (*standalone*) yang mengimplementasikan fine-grained reactivity.

### 1. Inisialisasi Zoneless Application (`main.ts`)
```typescript
import { bootstrapApplication } from '@angular/platform-browser';
import { provideExperimentalZonelessChangeDetection } from '@angular/core';
import { provideRouter } from '@angular/router';
import { AppComponent } from './app/app.component';
import { APP_ROUTES } from './app/app.routes';

bootstrapApplication(AppComponent, {
  providers: [
    // Mengaktifkan Zoneless Change Detection Scheduler murni
    provideExperimentalZonelessChangeDetection(),
    provideRouter(APP_ROUTES)
  ]
}).catch((err: unknown) => console.error(err));
```

### 2. Implementasi Reaktif Granular (`user-profile.component.ts`)
```typescript
import { Component, ChangeDetectionStrategy, signal, computed, effect } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-user-profile',
  standalone: true,
  imports: [CommonModule],
  template: `
    <section class="profile-card">
      <h2>Profil Pengguna (Zoneless Reactive)</h2>
      <p>Nama: <strong>{{ fullName() }}</strong></p>
      <p>Poin Reputasi: <strong>{{ reputation() }}</strong></p>
      <p>Kategori: <span [class]="tierClass()">{{ tier() }}</span></p>

      <div class="actions">
        <button (click)="incrementReputation()">Tambah Poin</button>
        <button (click)="resetReputation()">Reset Poin</button>
      </div>
    </section>
  `,
  // Selalu gunakan OnPush untuk kepastian kompatibilitas scheduler zoneless
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class UserProfileComponent {
  // State primitif menggunakan Signal
  readonly firstName = signal<string>('Budi');
  readonly lastName = signal<string>('Pratama');
  readonly reputation = signal<number>(100);

  // Computed signal: Turunan terisolasi yang dihitung secara efisien
  readonly fullName = computed(() => `${this.firstName()} ${this.lastName()}`);
  
  readonly tier = computed<'Elite' | 'Standard'>(() => {
    return this.reputation() >= 150 ? 'Elite' : 'Standard';
  });

  readonly tierClass = computed(() => {
    return this.tier() === 'Elite' ? 'badge-gold' : 'badge-silver';
  });

  constructor() {
    // Effect: Side effect terisolasi yang bereaksi terhadap perubahan granular
    effect(() => {
      console.log(`[Telemetry] Perubahan tier terdeteksi: ${this.tier()}`);
    });
  }

  incrementReputation(): void {
    // Mutasi signal memicu scheduler Zoneless secara granular
    this.reputation.update((current) => current + 25);
  }

  resetReputation(): void {
    this.reputation.set(100);
  }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Mari kita bedah secara mendalam kode pada **Seksi 07**:

### Pada File `main.ts`
*   `provideExperimentalZonelessChangeDetection()`:
    *   **Fungsi**: Menonaktifkan inisialisasi `zone.js`. Angular tidak lagi mendengarkan event emisi via `NgZone`.
    *   **Dampak Memori**: Menghemat ~100KB parse/execution time di runtime browser karena monkey-patched script ditiadakan.
    *   **Dampak Eksekusi**: Event listener global tidak akan lagi menjalankan dirty checking global di seluruh aplikasi.

### Pada File `user-profile.component.ts`
*   `readonly firstName = signal<string>('Budi');`
    *   Mendefinisikan node Producer reaktif murni. Menggunakan modifier `readonly` untuk memastikan referensi signal instance tidak ditimpa (*immutable pointer*), menjaga integritas dependency graph.
*   `readonly fullName = computed(() => ...);`
    *   Menciptakan Consumer sekaligus Producer. Signal ini *memoized*. Fungsi kalkulasi string concatenation tidak akan dipanggil ulang kecuali `firstName()` atau `lastName()` menghasilkan nilai baru yang tidak lolos pengecekan equality.
*   `changeDetection: ChangeDetectionStrategy.OnPush`:
    *   Sangat krusial. Dalam model Zoneless, `OnPush` memastikan compiler menandai component view node sebagai boundary reaktif, mengoptimalkan proses flushing yang di-dispatch oleh microtask queue.
*   `this.reputation.update((current) => current + 25);`:
    *   Memperbarui nilai secara transaksional berbasis nilai sebelumnya. Operasi ini menandai `reputation` sebagai *dirty*, meneruskan sinyal pembaharuan ke `tier` computed node, kemudian menjadwalkan update DOM ke microtask scheduler Angular tanpa intervensi `zone.js`.

---

## SEKSI 09 — STUDI KASUS NYATA (Real-World Enterprise Production Scenario)

### Konteks: High-Frequency Trading & Logistics Dashboard
**Perusahaan:** PT Logistika Finansial Global.  
**Masalah:**  
Aplikasi Core Enterprise Dashboard menerima pembaharuan data via WebSocket sebanyak **500 update per detik** (harga logistik, GPS fleet tracking, kuota inventory). 
1.  **Dampak Zone.js**: Setiap pesan WebSocket memicu `ZoneDelegate.invokeTask()`, menyebabkan Angular melakukan validasi dirty-checking ke seluruh komponen yang berjumlah >2.500 komponen di halaman.
2.  **Gejala**: Browser mengalami UI Freeze, metrik INP melonjak hingga **850ms** (batas buruk adalah >500ms), utilisasi CPU menyentuh 100%, dan memori bocor akibat retensi reference async task.
3.  **Masalah Organisasi**: Tim terbagi menjadi Tim Host Platform, Tim Fleet Tracking, dan Tim Billing. Monolitik bundling membuat rilis satu tim dapat merusak kestabilan tim lainnya.

### Solusi Arsitektural:
1.  Transformasi Host ke **Zoneless Architecture** untuk mematikan auto dirty checking global saat WebSocket menerima traffic.
2.  Penerapan **Module Federation** dinamis: Memecah aplikasi menjadi Shell (Host), Remote Fleet Tracking, dan Remote Billing.
3.  Komunikasi antar-remote berbasis **Event Bus Terisolasi** memanfaatkan native Signal Graph lintas micro-frontend tanpa cross-bundle leakage.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

### 1. Host Configuration: `webpack.config.js` (Shell Orchestrator)
```javascript
const { shareAll, withModuleFederationPlugin } = require('@angular-architects/module-federation/webpack');

module.exports = withModuleFederationPlugin({
  remotes: {
    // Static fallback, manifest dinamis akan menangani runtime URI
    'fleetRemote': 'http://localhost:4201/remoteEntry.js',
    'billingRemote': 'http://localhost:4202/remoteEntry.js',
  },
  shared: {
    ...shareAll({ 
      singleton: true, 
      strictVersion: true, 
      requiredVersion: 'auto' 
    }),
  },
});
```

### 2. Cross-Domain Enterprise Event Bus (`cross-domain-bus.service.ts`)
```typescript
import { Injectable, signal, computed } from '@angular/core';

export interface TelemetryEvent {
  vehicleId: string;
  latitude: number;
  longitude: number;
  speed: number;
  timestamp: number;
}

@Injectable({
  providedIn: 'root'
})
export class CrossDomainBusService {
  // Event stream state berbasis internal signal
  private readonly _latestTelemetry = signal<TelemetryEvent | null>(null);
  
  // Public readonly signals exposing granular states
  public readonly latestTelemetry = this._latestTelemetry.asReadonly();
  
  public readonly isOverspeed = computed(() => {
    const data = this._latestTelemetry();
    return data !== null && data.speed > 80;
  });

  public dispatchTelemetry(event: TelemetryEvent): void {
    // Pembaruan granular - hanya komponen yang subscribe yang akan memproses perubahan
    this._latestTelemetry.set(event);
  }
}
```

### 3. Remote Loader Service Dinamis (`federation-loader.service.ts`)
```typescript
import { Injectable } from '@angular/core';
import { loadRemoteModule } from '@angular-architects/module-federation';
import { Route } from '@angular/router';

@Injectable({ providedIn: 'root' })
export class DynamicFederationLoaderService {
  public createRemoteRoute(
    path: string, 
    remoteEntryUri: string, 
    remoteName: string, 
    exposedModule: string
  ): Route {
    return {
      path,
      loadChildren: () =>
        loadRemoteModule({
          type: 'module',
          remoteEntry: remoteEntryUri,
          exposedModule: exposedModule,
        }).then((m) => m.routes)
        .catch((err) => {
          console.error(`[MFE Error] Gagal memuat Remote: ${remoteName}`, err);
          // Fallback module routing darurat jika terjadi kegagalan jaringan
          return import('./fallback/remote-fallback.routes').then(f => f.FALLBACK_ROUTES);
        }),
    };
  }
}
```

### 4. Remote Module: Zoneless WebSocket Ingestion Component (`fleet-stream.component.ts`)
```typescript
import { 
  Component, 
  OnInit, 
  OnDestroy, 
  ChangeDetectionStrategy, 
  signal, 
  computed, 
  inject 
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { CrossDomainBusService, TelemetryEvent } from '../services/cross-domain-bus.service';

@Component({
  selector: 'fleet-stream-viewer',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="fleet-panel" [class.alert-border]="isOverspeedWarning()">
      <h3>Monitoring Armada (High-Frequency Stream)</h3>
      
      @if (currentTelemetry(); as data) {
        <div class="telemetry-grid">
          <div>Armada: <strong>{{ data.vehicleId }}</strong></div>
          <div>Kecepatan: <strong>{{ data.speed }} km/jam</strong></div>
          <div>Koordinat: <span>{{ data.latitude }}, {{ data.longitude }}</span></div>
        </div>
      } @else {
        <p class="placeholder">Menunggu sinyal telemetri...</p>
      }

      @if (isOverspeedWarning()) {
        <div class="danger-toast">PERINGATAN: Kecepatan Melebihi Batas Aman!</div>
      }
    </div>
  `,
  styles: [`
    .fleet-panel { padding: 16px; border: 2px solid #ccc; border-radius: 8px; }
    .alert-border { border-color: #d32f2f; background-color: #ffebee; }
    .danger-toast { color: #d32f2f; font-weight: bold; margin-top: 8px; }
  `],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FleetStreamComponent implements OnInit, OnDestroy {
  private readonly busService = inject(CrossDomainBusService);
  private webSocketWorker: Worker | null = null;

  // Signal lokal untuk menampung telemetri
  readonly currentTelemetry = this.busService.latestTelemetry;
  readonly isOverspeedWarning = this.busService.isOverspeed;

  ngOnInit(): void {
    this.initializeOffThreadWebSocket();
  }

  private initializeOffThreadWebSocket(): void {
    // Memindahkan WebSocket processing ke Web Worker untuk isolasi total dari Main Thread
    const workerScript = `
      self.onmessage = function() {
        // Simulasi high-frequency data pipeline
        setInterval(() => {
          const telemetry = {
            vehicleId: 'B-9021-UX',
            latitude: -6.2088 + (Math.random() - 0.5) * 0.01,
            longitude: 106.8456 + (Math.random() - 0.5) * 0.01,
            speed: Math.floor(60 + Math.random() * 35),
            timestamp: Date.now()
          };
          self.postMessage(telemetry);
        }, 20); // 50 updates per detik
      };
    `;

    const blob = new Blob([workerScript], { type: 'application/javascript' });
    this.webSocketWorker = new Worker(URL.createObjectURL(blob));

    this.webSocketWorker.onmessage = (event: MessageEvent<TelemetryEvent>) => {
      // Ingest ke Angular state: Scheduler zoneless hanya merender 
      // komponen ini secara lokal, tanpa menyentuh root dashboard!
      this.busService.dispatchTelemetry(event.data);
    };

    this.webSocketWorker.postMessage('START');
  }

  ngOnDestroy(): void {
    if (this.webSocketWorker) {
      this.webSocketWorker.terminate();
      this.webSocketWorker = null;
    }
  }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter Dimensi | Arsitektur Klasik (Zone.js Monolithic) | Arsitektur Modern (Zoneless + Micro-Frontend) | Analisis Trade-Off & Justifikasi |
| :--- | :--- | :--- | :--- |
| **Ukuran Bundle Baseline** | Bundle lebih besar (+~100KB `zone.js` uncompressed). | Sangat minimal di entry point; chunk di-stream on-demand. | Mengeliminasi overhead bootstrapping; sangat menguntungkan First Contentful Paint (FCP). |
| **CPU Overhead (Main Thread)** | Tinggi; setiap async task menjalankan top-down check $O(N)$. | Rendah; push-pull scheduling hanya mengevaluasi Consumer aktif $O(1)$. | Mengubah batas kapasitas aplikasi untuk skenario data streaming frekuensi tinggi. |
| **Debugging & DevEx** | Sederhana. Stack trace dilacak otomatis oleh `zone.js`. | Menantang. Asynchronous context tracing terputus tanpa Monkey Patch. | Perlu rely pada structured logging, tracing context explicit, dan browser dev tools native async stack. |
| **Kompleksitas Deployment** | Single Pipeline; build-deploy seragam (at-once). | Multi Pipeline; independen antar domain MFE. | MFE butuh Orkestrasi CI/CD tingkat lanjut, contract testing, dan monitoring versi shared scope. |
| **Versioning Conflict** | Tidak ada (single `node_modules`). | Risiko "Dependency Hell" antar remote yang memuat versi runtime berbeda. | Butuh aturan ketat pada Webpack `shared` scope (`strictVersion: true`). |

---

## SEKSI 12 — EDGE CASES & PITFALLS (Failure Modes & Mitigation)

### 1. Kegagalan Jaringan Saat Runtime Fetching `remoteEntry.js`
*   **Mode Kegagalan**: Jaringan pengguna mengalami RTT latency tinggi atau failover DNS saat navigasi router menuju micro-frontend remote, mengakibatkan blank screen / `ChunkLoadError`.
*   **Mitigasi**: Gunakan Circuit Breaker Pattern pada fungsi `loadRemoteModule` router. Tambahkan komponen penampung fallback (*graceful degradation*) yang menyediakan opsi reload komponen atau beralih ke state offline.

### 2. Memory Leaking Melalui Singleton Shared Scope
*   **Mode Kegagalan**: Remotes mendaftarkan event listener pada shared services (`CrossDomainBusService`) namun komponen di-destroy tanpa membersihkan referensi. Akibatnya instance injector remote tidak pernah dibersihkan oleh Garbage Collector.
*   **Mitigasi**: Selalu manfaatkan `DestroyRef` atau `takeUntilDestroyed` pada konteks subscription, dan hindari menyimpan instance DOM Node atau Component di dalam Service singleton.

### 3. Out-of-Band State Mutation pada Zoneless Mode
*   **Mode Kegagalan**: Library pihak ketiga non-Angular memodifikasi data array/object internal di luar pantauan Signals, namun tampilan UI tidak ter-refresh karena tidak ada `zone.js` yang mendeteksi callback callback pihak ketiga tersebut.
*   **Mitigasi**: Bungkus callback library eksternal menggunakan `ChangeDetectorRef.markForCheck()` atau sinkronkan mutasi ke dalam `signal.set()` secara eksplisit.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Memanggil Signal Getter di Template Tanpa Menggunakannya Sebagai Function
*   **Salah**: `<span>{{ userProfile }}</span>` (menampilkan object/function code reference).
*   **Benar**: `<span>{{ userProfile() }}</span>`.

### 2. Mengabaikan Dynamic Versioning pada Module Federation Shared Libraries
*   **Salah**:
    ```javascript
    shared: ['@angular/core', '@angular/common'] // Mengabaikan parameter strictVersion
    ```
*   **Benar**:
    ```javascript
    shared: {
      '@angular/core': { singleton: true, strictVersion: true, requiredVersion: '^18.0.0' },
      '@angular/common': { singleton: true, strictVersion: true, requiredVersion: '^18.0.0' },
    }
    ```
    *Konsekuensi Fatal*: Jika host memuat Angular 18 dan Remote memuat Angular 17 tanpa deklarasi ketat, browser akan mengeksekusi dua instance framework berbeda secara paralel, merusak Injection Token dan Context Engine.

### 3. Menjalankan Heavy Computational Logic di Dalam `computed()`
*   **Salah**: Melakukan iterasi jutaan data atau HTTP call di dalam `computed()`.
*   **Benar**: `computed()` harus murni (*pure*), deterministik, bebas efek samping (*idempotent*), dan beroperasi pada kompleksitas rendah ($O(1)$ atau amortized $O(N)$ skala kecil). Operasi asinkron harus dieksekusi di Service via RxJS pipelines atau Signals Resource API baru.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Standarisasi Host Shell Agnostik**: Shell Host hanya boleh menangani Authentication, Base Layout, Authorization Router Guard, dan Notification Bus. Hindari memasukkan logika bisnis domain ke dalam Host.
2.  **Enforce OnPush Everywhere**: Sekalipun Zoneless aktif, konfigurasi `changeDetection: ChangeDetectionStrategy.OnPush` pada linting rule (ESLint Angular Plugin) untuk menjamin kompatibilitas deterministik antara compiler dan scheduler.
3.  **Strict Styling Isolation**: Gunakan `ViewEncapsulation.Emulated` (default) atau `ShadowDom` pada Micro-Frontend. Jangan pernah menulis style global (`styles.scss`) di remote yang menarget tag HTML murni (`body`, `h1`, `table`) karena akan mencemari Shell Host (*style bleeding*).
4.  **Contract Testing Antar-MFE**: Selalu terapkan Contract Testing (misal menggunakan Pact.io atau Typescript Typing NPM packages terisolasi) untuk antarmuka state bus lintas aplikasi.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### 1. Memory Efficiency: Garbage Collection Lifecycle
Pada arsitektur monolitik, seluruh JavaScript heap dikelola dalam satu context. Dalam MFE:
*   Ketika navigasi berpindah dari `FleetRemote` ke `BillingRemote`, chunk `FleetRemote` tetap berada di runtime memory jika tidak ditangani dengan baik.
*   **Optimasi**: Pastikan remote module mendestroy injector scope-nya saat leave routing path:
```typescript
export const FLEET_ROUTES: Route[] = [
  {
    path: '',
    providers: [
      // Scoped Injector: otomatis hancur saat navigasi berpindah
      FleetInternalStateService 
    ],
    component: FleetStreamComponent
  }
];
```

### 2. Network Footprint: Preloading Strategies
Gunakan kustom `PreloadingStrategy` pada router Shell Host untuk memuat chunk MFE secara probabilistik di background setelah interaksi awal stabil:
```typescript
import { PreloadingStrategy, Route } from '@angular/router';
import { Observable, of } from 'rxjs';

export class SelectiveMfePreloader implements PreloadingStrategy {
  preload(route: Route, load: () => Observable<any>): Observable<any> {
    // Hanya preload jika route metadata secara eksplisit mengizinkan
    return route.data && route.data['preloadMfe'] === true ? load() : of(null);
  }
}
```

---

## SEKSI 16 — KEAMANAN & HARDENING

1.  **Cross-Site Scripting (XSS) via Untrusted Remote Loading**:
    Memuat arbitrary JavaScript dari domain remote pihak ketiga membuka celah eksekusi kode berbahaya.
    *   *Hardening*: Wajib menerapkan **Content Security Policy (CSP)** level-3 yang ketat di HTTP Header Host Shell:
        ```http
        Content-Security-Policy: default-src 'self'; script-src 'self' https://mfe-fleet.internal.domain.com https://mfe-billing.internal.domain.com;
        ```
2.  **Subresource Integrity (SRI) pada Federasi Dinamis**:
    Implementasikan signature verification pada file manifest `manifest.json`. Host harus memverifikasi SHA-384 checksum `remoteEntry.js` sebelum mengeksekusi injeksi script tag ke DOM tree.
3.  **Context Sandboxing**: Jangan pernah mengekspos API berstatus privileged (seperti session tokens berkuasa penuh, direct localStorage setter) ke global window object. Gunakan isolasi Angular Dependency Injection tokens yang di-shield dengan encapsulation.

---

## SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

### 1. Debugging Profiler: Zoneless Microtask Tracing
Untuk melacak pemicu reaktivitas tanpa bantuan Zone stack trace:
```typescript
import { Component, effect, inject, NgZone } from '@angular/core';

export function debugSignalWatcher(name: string, signalFn: () => any) {
  effect(() => {
    const value = signalFn();
    // Menggunakan Console Timings Native API
    console.time(`[Signal Track] -> ${name}`);
    console.debug(`[Signal Detail] Evaluated:`, { name, value, timestamp: performance.now() });
    console.timeEnd(`[Signal Track] -> ${name}`);
  });
}
```

### 2. Telemet