# Bab 02 Module 01: Reaktivitas Inti: Signals, RxJS, dan Interoperabilitas

---

## SEKSI 01 — IDENTITAS MODUL

* **Kategori Jalur Pembelajaran:** 03-Frontend-and-Mobile
* **Kurikulum:** Angular Enterprise Architecture
* **Modul:** Bab 02 Module 01
* **Topik:** Reaktivitas Inti: Signals, RxJS, dan Interoperabilitas
* **Tingkat Kesulitan:** Advanced / Staff Engineer Level
* **Prasyarat:** Pemahaman mendalam TypeScript 5.x, Angular Change Detection (`Zone.js`), Reactive Programming Paradigm, Lifecycle Hooks Angular.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Menganalisis dan Membedakan Paradigma Reaktivitas:** Membedakan model komputasi sinkron berbasis *Push-Pull (Glitches-Free)* pada Angular Signals dari model aliran asinkron berbasis *Push-Stream* pada RxJS.
2. **Menguasai Internal Engine Signals:** Membedah implementasi internal algoritma dependency tracking (Reactive Node Graph, Dynamic Dependency Recording, dan Epoch/Version Checking) di dalam `@angular/core`.
3. **Mengimplementasikan Interoperabilitas Presisi Tinggi:** Menggunakan `@angular/core/rxjs-interop` (`toSignal`, `toObservable`) tanpa memory leak, race condition, atau degradasi performa context-switching.
4. **Menerapkan Zone-less & Fine-Grained Architecture:** Mentransformasi arsitektur komponen Angular tradisional (`ChangeDetectionStrategy.Default`) menjadi arsitektur berbasis Signals murni untuk mencapai efisiensi komputasi *O(1)* per-node update.
5. **Mitigasi Anti-Pattern Mutasi State:** Mendiagnosis dan mengeliminasi circular dependencies, infinite reactive loops, side-effects tersembunyi di dalam `computed()`, dan kebocoran context subscription.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Mental Model: Dari "Events Over Time" ke "Values Over Epochs"

Dalam pengembangan Angular modern, Anda tidak lagi memandang reaktivitas sebagai satu solusi monolitik. Anda harus mengoperasikan dua mental model yang berbeda namun saling melengkapi:

```
+-----------------------------------------------------------------------------+
|                                REAKTIVITAS                                  |
+-------------------------------------+---------------------------------------+
|                RxJS                 |                Signals                |
|      (Asynchronous Event Streams)   |      (Synchronous State Values)       |
+-------------------------------------+---------------------------------------+
| Mental Model: Pipa Air (Conduit)    | Mental Model: Spreadsheet (Sel Excel) |
| Fokus: Kejadian (Events Over Time)  | Fokus: Nilai Sekarang (State Today)   |
| Karakteristik: Asinkron / Multicast | Karakteristik: Sinkron / Pull-Push    |
| Masalah: Kapan data tiba?           | Masalah: Berapa nilainya sekarang?    |
+-------------------------------------+---------------------------------------+
```

1. **RxJS adalah Pipa Kejadian (Events Over Time):** Gunakan RxJS ketika dimensi **waktu**, **pembatalan (cancellation)**, **penundaan (debounce/throttle)**, atau **orkestrasi multi-sumber asinkron** adalah kebutuhan utama (misalnya: WebSockets, HTTP Polling, UI Gesture Streams).
2. **Signals adalah Sel Spreadsheet (State & Derived Values):** Gunakan Signals untuk **keadaan aplikasi (state)**. Sebuah sel di spreadsheet tidak peduli seberapa sering sel lain berubah di masa lalu; sel tersebut hanya peduli: *"Jika formula saya bergantung pada sel A1 dan B1, berikan saya nilai mutakhir secara instan tanpa inkonsistensi temporal (glitches)."*

Seorang Principal Engineer tidak menggantikan RxJS dengan Signals, melainkan menempatkan keduanya pada batas arsitektur (*architectural boundary*) yang tepat: **RxJS di lapisan Event & I/O Boundary, Signals di lapisan State Management & View Layer.**

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Dynamic Dependency Graph & Reactive Graph Execution

Diagram ASCII berikut mengilustrasikan bagaimana Angular Signals membangun graf ketergantungan secara dinamis saat runtime, mengeksekusi *mark-dirty*, dan melakukan evaluasi secara *lazy* (pull) untuk menghindari *diamond dependency problem*.

```
   [ WritableSignal (A) ]           [ WritableSignal (B) ]
        |             \                 /             |
        |              \               /              |
        v               v             v               v
  (Consumer C1)       [ ComputedSignal (D) ]     (Consumer C2)
  [ effect() ]        [ Formula: A() + B() ]     [ Template View ]
                              |
                              v
                      (Consumer C3: UI)

======================= SIKLUS DIRTY-PROPAGATION & LAZY-PULL =======================

1. Mutasi State:
   A.set(baru) 
      |
      +---> [Reactive Engine: Notifikasi Stale (Push Phase)]
                 |
                 +---> D diberi tanda (DIRTY / STALE Flag)
                 |         |
                 |         +---> C3 dijadwalkan untuk re-render (Check Notification)
                 |
                 +---> C1 dijadwalkan untuk eksekusi ulang pada microtask queue

2. Konsumsi Nilai (Pull Phase):
   Browser Render Frame -> UI Membaca D()
      |
      +---> C3 memanggil D()
                 |
                 +---> D memeriksa: Apakah versi D == Versi Node Dependensi (A & B)?
                 |          |
                 |          +-- [TIDAK SAMA / DIRTY] --> Rekalkulasi Formula
                 |          |                                   |
                 |          |                                   v
                 |          |                       Update Nilai Cache D & Versi D
                 |          |
                 |          +-- [SAMA / CLEAN] --------> Kembalikan Nilai Cache Instan!
                 v
   Render Selesai (Bebas dari Glitch / Tanpa Double Execution)
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### Mekanisme Engine di Balik `@angular/core`

Signals Angular tidak menggunakan runtime polling atau dirty-checking dari `Zone.js`. Mekanismenya dioperasikan oleh tiga komponen primitif:

1. **`ReactiveNode`:** Struktur data dasar internal C++/V8-optimized struct yang menyimpan pointer ke dependensi (nodes yang ia baca) dan dependents (nodes yang membaca dirinya).
2. **`activeConsumer` Tracking Variable:** Sebuah variabel penunjuk global (thread-local di level JS single-thread execution) yang menunjuk ke Consumer mana (`computed` atau `effect` atau template reactive context) yang saat ini sedang dieksekusi.
3. **Versi Monotonik (Epoch Counter):** Integer 64-bit yang melakukan inkrementasi setiap kali signal dasar mengalami mutasi.

#### Algoritma Dynamic Dependency Tracking

```
           Eksekusi context: computed(() => A() + B())
                                |
1. Setup Context:          activeConsumer = ComputedNode(D)
                                |
2. Evaluasi A():           Panggil A()
                           |-> A mendeteksi activeConsumer != null
                           |-> Tambahkan Edge: D bergantung pada A
                           |-> Kembalikan nilai A
                                |
3. Evaluasi B():           Panggil B()
                           |-> B mendeteksi activeConsumer != null
                           |-> Tambahkan Edge: D bergantung pada B
                           |-> Kembalikan nilai B
                                |
4. Cleanup Context:        activeConsumer = null
                           Kembalikan nilai kalkulasi
```

Jika fungsi komputasi memiliki percabangan kondisional:
```typescript
const dynamicValue = computed(() => useA() ? signalA() : signalB());
```
Ketika `useA()` bernilai `false`, pointer internal ke `signalA()` **dihapus seketika** dari graf dependensi `dynamicValue`. Jika `signalA()` berubah di kemudian hari, `dynamicValue` tidak akan ditandai *dirty*. Ini mencegah evaluasi zombie (*zombie computations*).

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Glitch-Free Reactivity: Solusi Masalah Diamond Dependency

Masalah klasik sistem reaktif (seperti RxJS murni tanpa penjadwalan kompleks) adalah fenomena *Glitch*: status inkonsistensi sementara di mana nilai turunan dihitung dua kali dengan nilai yang salah di antaranya.

Misalkan struktur dependensi berbentuk *Diamond*:

```
      Signal A
      /      \
  Signal B   Signal C  (Keduanya bergantung pada A)
      \      /
      Signal D         (D bergantung pada B dan C: formula = B + C)
```

Jika `A` berubah dari `1` ke `2`:
* Pada implementasi *Push murni* yang naif: `A` memberi tahu `B`, `B` mengupdate nilainya dan memberi tahu `D`. `D` melakukan evaluasi ulang secara prematur menggunakan `B` yang baru dan `C` yang **lama**. Kemudian `A` memberi tahu `C`, dan `C` memberi tahu `D`. `D` melakukan evaluasi kedua kalinya. Ini memicu:
  1. *Double execution* (pemborosan sumber daya).
  2. Pembacaan state yang salah secara transien (glitch) yang dapat memicu crash atau HTTP call duplikat.
* Pada model **Push-Pull Topological Engine** (Signals):
  1. **Fase 1 (Push - Notifikasi Saja):** `A` hanya memicu transisi status: `B` menjadi STALE, `C` menjadi STALE, `D` menjadi STALE. Tidak ada kalkulasi nilai di fase ini.
  2. **Fase 2 (Pull - Rekalkulasi saat Dibutuhkan):** Ketika `D` dibaca oleh UI, engine menelusuri graf ke atas. Engine mengevaluasi `B`, mengevaluasi `C`, lalu mengevaluasi `D` tepat **satu kali** dengan data yang dijamin mutakhir dan konsisten.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah kode dasar yang mendemonstrasikan deklarasi Signal, Computed dengan dynamic branching, Effect dengan cleanup, serta interoperabilitas RxJS.

```typescript
import { Component, signal, computed, effect, inject, Injector } from '@angular/core';
import { toSignal, toObservable } from '@angular/core/rxjs-interop';
import { fromEvent, interval } from 'rxjs';
import { map } from 'rxjs/operators';

@Component({
  selector: 'app-fundamental-reactive',
  standalone: true,
  template: `
    <div>
      <p>Base Count: {{ count() }}</p>
      <p>Multiplied: {{ multiplied() }}</p>
      <p>Window Width (RxJS toSignal): {{ windowWidth() }}</p>
      <button (click)="increment()">Increment</button>
      <button (click)="toggleMultiplier()">Toggle Multiplier</button>
    </div>
  `
})
export class FundamentalReactiveComponent {
  // 1. Primitive Writable Signal
  readonly count = signal<number>(0);
  readonly applyMultiplier = signal<boolean>(true);

  // 2. Computed Signal dengan Kondisional Dinamis
  readonly multiplied = computed(() => {
    if (!this.applyMultiplier()) {
      return this.count(); // Tidak mengamati multiplier konstan
    }
    return this.count() * 10;
  });

  // 3. Interoperabilitas: Observable -> Signal
  // windowWidth otomatis unsubscribed ketika komponen hancur (DestroyRef context)
  readonly windowWidth = toSignal(
    fromEvent(window, 'resize').pipe(map(() => window.innerWidth)),
    { initialValue: window.innerWidth }
  );

  // 4. Interoperabilitas: Signal -> Observable
  readonly count$ = toObservable(this.count);

  constructor() {
    // 5. Effect dengan Mekanisme Cleanup (onCleanup)
    effect((onCleanup) => {
      const currentCount = this.count();
      const timer = setTimeout(() => {
        console.log(`[Effect Logging] Debounced state count: ${currentCount}`);
      }, 500);

      // Cleanup function dieksekusi sebelum effect berjalan ulang atau saat destroy
      onCleanup(() => {
        clearTimeout(timer);
        console.log('[Effect Cleanup] Membersihkan timer sebelumnya.');
      });
    });
  }

  increment(): void {
    this.count.update(prev => prev + 1);
  }

  toggleMultiplier(): void {
    this.applyMultiplier.update(prev => !prev);
  }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

* **Baris 23:** `readonly count = signal<number>(0);`
  Menginisialisasi `WritableSignal` dengan state awal `0`. Nilai dienkapsulasi dan hanya dapat diubah melalui API `.set()` atau `.update()`.
* **Baris 27–32:** `readonly multiplied = computed(() => { ... });`
  Mendefinisikan memoized reactive derivation. Jika `applyMultiplier()` bernilai `false`, sistem dynamic tracking melepaskan relasi ke signal lain di dalam blok `true`, mengoptimalkan evaluasi.
* **Baris 36–39:** `readonly windowWidth = toSignal(..., { initialValue: window.innerWidth });`
  Mengonversi streaming RxJS ke synchronous Signal. Penggunaan `initialValue` mencegah tipe kembalian menjadi `number | undefined`, menjaga inferensi tipe tetap ketat (*strict type-safety*). Operasi ini otomatis terikat ke injector lifecycle (`DestroyRef`).
* **Baris 42:** `readonly count$ = toObservable(this.count);`
  Mengekstrak emisi nilai Signal ke aliran event RxJS. Perlu diingat bahwa emisi ini menggunakan sinkronisasi mikro-tugas (*microtask queue*), sehingga nilai tidak dipancarkan secara sinkron murni melainkan pada iterasi *tick* berikutnya.
* **Baris 45–56:** `effect((onCleanup) => { ... });`
  Mendaftarkan consumer side-effect. Parameter `onCleanup` mendaftarkan callback yang dijalankan tepat sebelum effect dieksekusi ulang untuk mencegah *memory leaks* dan *dangling timers*.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Enterprise: Dashboard Perdagangan Finansial Real-Time (High-Frequency Trading Terminal)

#### Konteks
Sebuah platform broker valuta asing (Forex) menerima pembaruan harga (ticks) dengan frekuensi 50–200 per detik via WebSocket. Pada saat yang sama, pengguna dapat mengubah filter pasangan mata uang, menetapkan leverage, memasukkan lot pesanan, dan mengamati ringkasan margin akun.

#### Masalah Kritis
1. **Bottleneck Zone.js:** Jika setiap tick WebSocket memicu Angular Change Detection melalui `Zone.js`, browser mengalami degradasi frame rate (drop ke < 15 FPS) karena seluruh komponen tree diperiksa.
2. **Kekacauan Asinkron:** Pengguna sering mengalami *race condition* saat mengubah leverage di UI, sementara perhitungan margin sedang di-stream dari server.
3. **Memory Leaks:** Komponen stream yang dibuat dengan RxJS murni seringkali terlambat di-*unsubscribe* saat berpindah tab workspace trading, memicu memory leak ratusan megabyte per jam.

#### Solusi Arsitektur
Membangun sistem *Hybrid Separation of Concerns*:
* **Layer I/O (RxJS):** Menerima frame data mentah dari WebSocket, melakukan batching, filtering, dan sliding window rate-limiting.
* **Layer State & Interoperabilitas (`toSignal`):** Data yang sudah ter-batch dialirkan ke dalam Signal Store terisolasi.
* **Layer UI Components (Signals Pure):** Template hanya membaca *Signals* dan berjalan dalam mode Change Detection OnPush murni (atau Zone-less) tanpa ketergantungan pada siklus *digest Zone.js*.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah arsitektur produksi lengkap: Service ingest streaming real-time, State Store reaktif, dan Komponen Konsumen UI tanpa memory leak.

### 1. Model Domain & Service WebSocket Mock

```typescript
// trading.types.ts
export interface PriceTick {
  readonly symbol: string;
  readonly bid: number;
  readonly ask: number;
  readonly timestamp: number;
}

export interface TradePosition {
  readonly id: string;
  readonly symbol: string;
  readonly units: number;
  readonly entryPrice: number;
}
```

```typescript
// market-data.service.ts
import { Injectable } from '@angular/core';
import { Observable, interval } from 'rxjs';
import { map, share } from 'rxjs/operators';
import { PriceTick } from './trading.types';

@Injectable({ providedIn: 'root' })
export class MarketDataService {
  // Mensimulasikan data tick dari WebSocket dengan frekuensi tinggi
  readonly rawTicks$: Observable<PriceTick> = interval(20).pipe(
    map(() => {
      const symbols = ['EUR/USD', 'GBP/USD', 'USD/JPY'];
      const selected = symbols[Math.floor(Math.random() * symbols.length)];
      const basePrice = selected === 'USD/JPY' ? 150.0 : 1.1;
      const spread = 0.0002;
      const variation = (Math.random() - 0.5) * 0.01;
      const bid = parseFloat((basePrice + variation).toFixed(4));
      return {
        symbol: selected,
        bid: bid,
        ask: parseFloat((bid + spread).toFixed(4)),
        timestamp: Date.now()
      };
    }),
    share()
  );
}
```

### 2. Trading Engine Store (Signal-RxJS Hybrid Architecture)

```typescript
// trading-engine.store.ts
import { Injectable, computed, signal, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { MarketDataService } from './market-data.service';
import { PriceTick, TradePosition } from './trading.types';
import { bufferTime, filter } from 'rxjs/operators';

@Injectable({ providedIn: 'root' })
export class TradingEngineStore {
  private readonly marketDataService = inject(MarketDataService);

  // --- STATE MUTABLE VIA SIGNALS ---
  readonly activeSymbol = signal<string>('EUR/USD');
  readonly leverage = signal<number>(30);
  readonly accountBalance = signal<number>(100_000.00); // USD
  readonly openPositions = signal<TradePosition[]>([
    { id: 'POS-1', symbol: 'EUR/USD', units: 100_000, entryPrice: 1.0950 },
    { id: 'POS-2', symbol: 'USD/JPY', units: 50_000, entryPrice: 154.20 }
  ]);

  // --- INGEST DATA DARI RXJS DENGAN BATCH BUFFERING KE SIGNAL ---
  // Kita menahan tick dalam buffer 100ms agar UI tidak bergetar dan tidak crash
  private readonly bufferedTicks$ = this.marketDataService.rawTicks$.pipe(
    bufferTime(100),
    filter(ticks => ticks.length > 0),
    map(ticks => {
      // Ambil tick paling mutakhir per simbol dari array batch
      const mapLatest = new Map<string, PriceTick>();
      for (const t of ticks) {
        mapLatest.set(t.symbol, t);
      }
      return mapLatest;
    })
  );

  // Mengubah Stream RxJS menjadi Signal Map
  readonly latestTicks = toSignal(this.bufferedTicks$, {
    initialValue: new Map<string, PriceTick>()
  });

  // --- COMPUTED DERIVATIONS (BEBAS GLITCH & MEMOIZED) ---
  
  // Ambil tick dari simbol yang sedang aktif dipilih
  readonly currentActiveTick = computed<PriceTick | null>(() => {
    const symbol = this.activeSymbol();
    const ticksMap = this.latestTicks();
    return ticksMap.get(symbol) ?? null;
  });

  // Kalkulasi Total Unrealized Profit/Loss (PnL)
  readonly unrealizedPnL = computed<number>(() => {
    const positions = this.openPositions();
    const ticksMap = this.latestTicks();

    return positions.reduce((acc, pos) => {
      const currentTick = ticksMap.get(pos.symbol);
      if (!currentTick) return acc;
      // PnL Long sederhana: (Current Bid - Entry Price) * Units
      const diff = currentTick.bid - pos.entryPrice;
      return acc + (diff * pos.units);
    }, 0);
  });

  // Kalkulasi Margin Digunakan
  readonly usedMargin = computed<number>(() => {
    const positions = this.openPositions();
    const lev = this.leverage();
    const totalExposure = positions.reduce((acc, pos) => acc + (pos.units * pos.entryPrice), 0);
    return totalExposure / lev;
  });

  // Margin Bebas (Free Margin) = Balance + PnL - Used Margin
  readonly freeMargin = computed<number>(() => {
    return this.accountBalance() + this.unrealizedPnL() - this.usedMargin();
  });

  // Status Margin Call (Bila rasio margin kritis)
  readonly isMarginCallRisk = computed<boolean>(() => {
    const used = this.usedMargin();
    if (used === 0) return false;
    const equity = this.accountBalance() + this.unrealizedPnL();
    return (equity / used) * 100 < 120; // Margin level di bawah 120%
  });

  // --- ACTIONS (INTENT API) ---
  setActiveSymbol(symbol: string): void {
    if (this.activeSymbol() !== symbol) {
      this.activeSymbol.set(symbol);
    }
  }

  setLeverage(newLeverage: number): void {
    if (newLeverage > 0 && newLeverage <= 500) {
      this.leverage.set(newLeverage);
    }
  }

  closePosition(id: string): void {
    this.openPositions.update(positions => positions.filter(p => p.id !== id));
  }
}
```

### 3. Komponen UI Produksi Berkinerja Tinggi

```typescript
// trading-terminal.component.ts
import { Component, ChangeDetectionStrategy, inject } from '@angular/core';
import { CommonModule, DecimalPipe } from '@angular/common';
import { TradingEngineStore } from './trading-engine.store';

@Component({
  selector: 'app-trading-terminal',
  standalone: true,
  imports: [CommonModule, DecimalPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="terminal-container" [class.risk-alert]="store.isMarginCallRisk()">
      <header class="header">
        <h1>Institutional Trading Desk</h1>
        <div class="balance-bar">
          <div>Balance: <strong>\${{ store.accountBalance() | number:'1.2-2' }}</strong></div>
          <div>Equity: <strong>\${{ (store.accountBalance() + store.unrealizedPnL()) | number:'1.2-2' }}</strong></div>
          <div>Used Margin: <strong>\${{ store.usedMargin() | number:'1.2-2' }}</strong></div>
          <div>Free Margin: <strong>\${{ store.freeMargin() | number:'1.2-2' }}</strong></div>
          <div>PnL: <strong [style.color]="store.unrealizedPnL() >= 0 ? 'green' : 'red'">
            \${{ store.unrealizedPnL() | number:'1.2-2' }}
          </strong></div>
        </div>
      </header>

      <div class="symbol-selector">
        @for (sym of availableSymbols; track sym) {
          <button 
            [class.active]="store.activeSymbol() === sym" 
            (click)="store.setActiveSymbol(sym)">
            {{ sym }}
          </button>
        }
      </div>

      <section class="ticker-box">
        <h2>Symbol: {{ store.activeSymbol() }}</h2>
        @if (store.currentActiveTick(); as tick) {
          <div class="tick-display">
            <span>BID: <b class="bid">{{ tick.bid | number:'1.4-4' }}</b></span>
            <span>ASK: <b class="ask">{{ tick.ask | number:'1.4-4' }}</b></span>
          </div>
        } @else {
          <p>Connecting to price feed...</p>
        }
      </section>

      <section class="positions-table">
        <h3>Open Positions</h3>
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Symbol</th>
              <th>Units</th>
              <th>Entry Price</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            @for (pos of store.openPositions(); track pos.id) {
              <tr>
                <td>{{ pos.id }}</td>
                <td>{{ pos.symbol }}</td>
                <td>{{ pos.units | number }}</td>
                <td>{{ pos.entryPrice | number:'1.4-4' }}</td>
                <td>
                  <button (click)="store.closePosition(pos.id)">Liquidate</button>
                </td>
              </tr>
            }
          </tbody>
        </table>
      </section>
    </div>
  `,
  styles: [`
    .terminal-container { padding: 1.5rem; font-family: monospace; background: #0f172a; color: #f8fafc; }
    .risk-alert { border: 2px solid #ef4444; }
    .balance-bar { display: flex; gap: 1.5rem; padding: 0.5rem 0; border-bottom: 1px solid #334155; }
    .symbol-selector button { margin-right: 0.5rem; margin-top: 1rem; padding: 0.5rem 1rem; }
    .symbol-selector button.active { background: #3b82f6; color: white; font-weight: bold; }
    .ticker-box { margin: 1rem 0; padding: 1rem; background: #1e293b; border-radius: 4px; }
    .tick-display { font-size: 1.5rem; display: flex; gap: 2rem; }
    .bid { color: #22c55e; }
    .ask { color: #f43f5e; }
    table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
    th, td { text-align: left; padding: 0.5rem; border-bottom: 1px solid #334155; }
  `]
})
export class TradingTerminalComponent {
  readonly store = inject(TradingEngineStore);
  readonly availableSymbols = ['EUR/USD', 'GBP/USD', 'USD/JPY'];
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter Evaluasi | RxJS Murni (BehaviorSubject / Observables) | Angular Signals (`signal`, `computed`) | Hybrid (`toSignal` / `toObservable`) |
| :--- | :--- | :--- | :--- |
| **Model Sinkronisasi** | Penuh Asinkron (Scheduler dependent) | Sinkron Penuh (Predictable Evaluation) | Konversi Sinkron/Asinkron Terkendali |
| **Penanganan Glitch** | Rentan kecuali menggunakan arsitektur state tersentralisasi rumit | Bebas glitch secara inheren (*Push-Pull*) | Bebas glitch pada layer Signal |
| **Beban Eksekusi Komputasi** | Eager (dihitung saat data dipancarkan ke subscriber) | Lazy (hanya dihitung saat nilai benar-benar dibaca) | Eager di I/O, Lazy di View |
| **Kemudahan Pembersihan Memori** | Membutuhkan `.pipe(takeUntilDestroyed())` manual | Otomatis bersih bersama Lifecycle Node | Otomatis melalui scoped Injector |
| **Kompleksitas Operasi Waktu** | Sangat Kuat (`switchMap`, `debounceTime`, dll.) | Tidak Tersedia secara primitif | Kuat di Stream, Sederhana di Template |
| **Kesiapan Zone-less** | Memerlukan `AsyncPipe` atau manual `markForCheck()` | Optimal, langsung memicu fine-grained view check | Maksimal untuk transisi arsitektur enterprise |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Async-Boundary Race Condition pada `toObservable()`
Signal selalu sinkron, tetapi `toObservable(mySignal)` menggunakan scheduler asinkron (berjalan pada siklus microtask berikutnya).
* **Failure Mode:** Jika Anda mengubah signal: `mySignal.set(1); mySignal.set(2);`, maka subscriber `toObservable(mySignal)` hanya akan menerima nilai `2`. Nilai `1` dilewati (*dropped*).
* **Mitigasi:** Jangan gunakan `toObservable()` untuk melacak setiap sequence log audit data berurutan (*lossless stream*). Gunakan RxJS `Subject` murni untuk transmisi event transaksi.

### 2. Zombie Child Subscription / Missing Injection Context
* **Failure Mode:** Menjalankan `toSignal(observable$)` di luar siklus inisialisasi injection context (misalnya di dalam method biasa atau hook `ngOnInit` tanpa menyuplai injector eksplisit) memicu `NG0203: toSignal() must be called in an injection context`.
* **Mitigasi:** Simpan referensi injector `private injector = inject(Injector);`, lalu berikan opsi: `toSignal(observable$, { injector: this.injector });`.

### 3. Context Polling Starvation pada Lazy-Computed
* **Failure Mode:** Jika sebuah `computed()` dibuat tetapi nilainya tidak pernah di-read di template HTML atau di dalam `effect()`, kalkulasi tersebut tidak pernah dieksekusi. Ini menjadi pitfall fatal jika engineer menyisipkan *side-effect* di dalamnya.
* **Mitigasi:** Hormati prinsip murni: *Computed must be purely idempotent without side-effects.*

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: Mutasi State Bersarang Tanpa Immutability
```typescript
// SALAH: Mutasi properti object secara langsung tidak mengubah referensi!
// Dependents tidak akan mendeteksi perubahan jika referensi alamat memori sama.
const user = signal({ name: 'Alpha', roles: ['ADMIN'] });
user().roles.push('USER'); // ANTI-PATTERN!
user.set(user());          // Engine menganggap nilai sama via referential comparison (Object.is)

// BENAR: Buat salinan referensi objek baru (Immutable Update)
user.update(current => ({
  ...current,
  roles: [...current.roles, 'USER']
}));
```

### Kesalahan 2: Menulis State Lain di Dalam `computed()`
```typescript
// SALAH: Memodifikasi state lain di dalam computed memicu error kompilasi/runtime
// NG0600: Writing to signals is not allowed in a computed or template context.
const count = signal(0);
const otherSignal = signal(0);

const derived = computed(() => {
  otherSignal.set(99); // CRITICAL FAULT!
  return count() * 2;
});

// BENAR: computed() HANYA melakukan transformasi read-only murni
const derived = computed(() => count() * 2);
```

### Kesalahan 3: Menggunakan `effect()` untuk Menggantikan Pola Reactive State
```typescript
// SALAH: Sinkronisasi manual antar signal menggunakan effect()
const a = signal(1);
const b = signal(0);
effect(() => {
  b.set(a() * 2); // Pemicu Infinite Loops & Spaghetti Dependency Flow
}, { allowSignalWrites: true });

// BENAR: Gunakan computed() untuk state turunan
const a = signal(1);
const b = computed(() => a() * 2);
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Prinsip Immutability Total:** Selalu gunakan `Object.freeze()` pada entitas state complex atau gunakan teknik immutable update via spread operator/Immer saat memanggil `signal.update()`.
2. **Readonly State Exposure:** Jangan pernah mengekspos `WritableSignal` secara langsung ke komponen luar dari sebuah Service. Gunakan `.asReadonly()`:
   ```typescript
   @Injectable()
   export class SecureConfigStore {
     private readonly _apiKey = signal<string>('secret');
     // Public API hanya bersifat Read-Only
     readonly apiKey = this._apiKey.asReadonly();
   }
   ```
3. **Pemberian Nama Konvensional (Naming Convention):**
   * Signal: `entity` (contoh: `userData`, `price`, `activeTab`). Hindari akhiran `$` (simbol `$` hanya untuk RxJS Observables: `userData$`).
   * Computed: Berikan predikat turunan deskriptif (contoh: `isValid`, `totalAmount`).
4. **Isolasi Side-Effect Boundary:** Batasi penggunaan `effect()` hanya untuk:
   * Integrasi pustaka pihak ketiga non-reaktif (misal: memetakan koordinat ke Leaflet/Mapbox, rendering canvas D3).
   * Sinkronisasi data ke `localStorage`/`sessionStorage`.
   * Logging telemetri internal dan debugging.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### 1. Equality Predicates Kustom pada Signals
Secara default, Signals memverifikasi perubahan menggunakan perbandingan `Object.is()`. Untuk objek kompleks atau array, definisikan `equal` function kustom guna memotong overhead dirty checking yang tidak perlu:

```typescript
import { signal } from '@angular/core';

interface DeepPayload {
  id: string;
  hash: string;
}

export const payloadSignal = signal<DeepPayload>(
  { id: '1', hash: 'a8f90' },
  {
    // Hanya picu downstream notification jika 'hash' benar-benar berubah
    equal: (prev, curr) => prev.hash === curr.hash
  }
);
```

### 2. Meredam Frekuensi Emisi dengan Microtask Buffering
Saat menghubungkan websocket berkecepatan tinggi dengan Signals, jangan memperbarui `WritableSignal` per packet event. Gunakan RxJS `bufferTime(ms)` atau `auditTime(ms)` sebelum dilempar ke `toSignal()`. Ini menjaga frame rate browser tetap stabil di angka 60/120 FPS tanpa membuang siklus thread CPU pada eksekusi render virtual DOM.

---

## SEKSI 16 — KEAMANAN & HARDENING

### 1. State Poisoning via Injection Context Leaks
Hindari penggunaan global state signals yang diinisialisasi di root tanpa enkapsulasi isolasi tenant, khususnya pada arsitektur SSR (Angular Universal / Server-Side Rendering).
* **Risiko:**