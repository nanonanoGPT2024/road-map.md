# BAB 02: Quiz, Challenge, & Knowledge Check
**Reaktivitas Inti: Signals, RxJS, dan Interoperabilitas**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Push-Pull Reactivity vs Push-Only Streams
Jelaskan perbedaan mendasar antara model reaktivitas *Push-Pull* yang digunakan oleh Angular Signals dengan model *Push-Only* murni pada RxJS Observables. Bagaimana perbedaan arsitektural ini memengaruhi eksekusi evaluasi state turunan (*derived state*) yang tidak sedang dikonsumsi oleh UI?

### Soal 1.2: Glitch-Free Execution Graph
Apa yang dimaksud dengan *Glitch-Free Execution* (bebas inkonsistensi transien) dalam reactive dependency graph Signals, dan bagaimana algoritma dynamic dependency tracking (topological sorting / two-phase commit: mark & evaluate) pada Signals menyelesaikannya jika dibandingkan dengan pipeline RxJS tradisional yang rentan terhadap *diamond dependency problem*?

### Soal 1.3: Purity dan Dynamic Tracking pada `computed()`
Jelaskan mengapa fungsi kalkulasi di dalam `computed()` harus bersifat murni (*pure*) dan bebas dari efek samping (*side-effects*). Mengapa dynamic dependency tracking pada Signals memungkinkan dependensi berganti secara kondisional saat runtime (misal: percabangan `if-else`), dan apa dampaknya terhadap konsumsi memori graph reaktivitas?

### Soal 1.4: Batasan Kontekstual `effect()` dan Injection Context
Mengapa pemanggilan `effect()` secara default memerlukan *Injection Context*, dan apa implikasi teknisnya jika dieksekusi di luar constructor tanpa menyertakan `Injector` eksplisit? Jelaskan pula mengapa Angular melarang mutasi Signal secara default di dalam `effect()` (`allowSignalWrites: false`).

### Soal 1.5: Mekanisme Interoperabilitas: `toSignal()` vs `toObservable()`
Uraikan lifecycle dan lifecycle phase boundary saat mengonversi stream RxJS ke Signal menggunakan `toSignal()`, khususnya terkait inisialisasi synchronous vs asynchronous, penanganan `initialValue`, dan strategi unsubscription berbasis `DestroyRef`. Bandingkan dengan cara kerja `toObservable()` dalam menjadwalkan emisi nilai baru via microtask queue.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Diagnostik Infinite Loop dan Memory Leak pada `effect()`
Diberikan cuplikan kode berikut:
```typescript
@Component({ ... })
export class AnalyticsWidget {
  private readonly metricsService = inject(MetricsService);
  public filter = signal('ALL');
  public rawData = signal<Metric[]>([]);

  constructor() {
    effect(() => {
      const currentFilter = this.filter();
      this.metricsService.fetchData(currentFilter).subscribe(data => {
        this.rawData.set(data);
      });
    });
  }
}
```
Identifikasi **dua risiko fatal** (terkait arsitektur eksekusi dan memory lifecycle) dari kode di atas. Bagaimana cara refaktor yang benar menggunakan kombinasi operator RxJS dan primitif Signals tanpa memicu memory leak atau nested subscription?

### Soal 2.2: Isolasi Dependensi Menggunakan `untracked()`
Kapan dan mengapa fungsi `untracked()` mutlak diperlukan di dalam `computed()` atau `effect()`? Berikan analisis skenario di mana membaca Signal di dalam logging utility atau analytics service tanpa `untracked()` dapat merusak topologi dependensi dan memicu eksekusi ulang (*re-run*) yang tidak diinginkan secara eksponensial.

### Soal 2.3: Mutasi Objek Kompleks dan Equality Predicate (`equal`)
Secara default, Signal menggunakan perbandingan identitas `Object.is` untuk mendeteksi perubahan nilai. Jika Anda memiliki Signal yang menampung *deeply nested immutable state tree*, jelaskan bahaya komputasi dan performa saat mengimplementasikan custom equality predicate `equal: (a, b) => deepEqual(a, b)`. Apa strategi arsitektur yang lebih optimal untuk menangani granular reactivity pada state bersarang?

### Soal 2.4: Hazard `allowSignalWrites: true` dan Scheduled Effects
Mengapa mengaktifkan opsi `{ allowSignalWrites: true }` pada `effect()` dianggap sebagai *code smell* arsitektural yang berbahaya di Angular? Jelaskan skenario di mana write operation di dalam `effect()` dapat memicu cascading state updates, degradasi frame rate (jank), atau `ExpressionChangedAfterItHasBeenCheckedError` jika berinteraksi dengan Zone.js atau OnPush change detection.

### Soal 2.5: Glitch Boundary pada `toObservable()` di dalam Microtask Queue
Karena `toObservable()` menggunakan scheduler internal berbasis microtask (Signals dievaluasi sinkron, sedangkan konversi ke Observable ditunda hingga microtask tick berikutnya), jelaskan edge-case yang terjadi ketika sebuah Signal bermutasi berkali-kali secara sinkron dalam satu execution frame:
```typescript
mySignal.set(1);
mySignal.set(2);
mySignal.set(3);
```
Berapa kali Observable turunan dari `toObservable(mySignal)` akan mengemisikan nilai, dan nilai apa saja yang diterima oleh subscriber? Kapan perilaku ini menjadi bug kritis?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Performa pada Financial Real-Time Dashboard
* **Konteks:** Sebuah sistem trading enterprise menerima pembaruan harga valuta asing melalui WebSocket dengan frekuensi mencapai 2.000 update/detik untuk 50 pasangan mata uang. UI mengalami lag parah, frame rate drop ke < 15 FPS, dan browser sering mengalami UI thread freezing.
* **Arsitektur Eksisting:** Setiap pesan WebSocket langsung dikirim ke `rawFxStream$` (RxJS), kemudian diubah menjadi Signal via `toSignal()`, dan template me-render daftar menggunakan `computed()` untuk memfilter serta mengurutkan mata uang berdasarkan volatilitas tertinggi.
* **Pertanyaan Diagnostik:**
  1. Analisis mengapa kombinasi streaming RxJS frekuensi tinggi langsung ke Signal tanpa backpressure throttling menyebabkan bottleneck pada Signal Graph dan Change Detection.
  2. Rancang arsitektur reaktif hibrida: Tentukan operator RxJS apa yang harus diletakkan di layer data stream sebelum state masuk ke Signal UI, dan bagaimana mengisolasi komputasi volatilitas agar tidak menghalangi rendering thread.

### Skenario B: Race Condition dan State Desynchronization pada Form Pencarian Asinkron
* **Konteks:** Sebuah aplikasi e-commerce memiliki search bar multi-kriteria: `searchTerm` (Signal), `selectedCategory` (Signal), dan `sortOrder` (Signal).
* **Masalah:** Developer mencoba menghindari RxJS dan menulis flow data hanya dengan Signals:
  ```typescript
  effect(async () => {
    const query = this.searchTerm();
    const cat = this.selectedCategory();
    const sort = this.sortOrder();
    
    this.isLoading.set(true);
    const results = await this.apiService.search({ query, cat, sort });
    this.searchResults.set(results);
    this.isLoading.set(false);
  });
  ```
  Di jaringan yang tidak stabil (3G/LTE), pengguna mengetik "laptop", lalu dengan cepat menggantinya menjadi "phone". UI sempat menampilkan hasil "phone" sesaat, namun kemudian tertimpa oleh respons API dari pencarian "laptop" yang terlambat datang (*out-of-order execution*).
* **Pertanyaan Diagnostik:**
  1. Mengapa `effect()` dengan `async/await` rentan terhadap race condition dan bagaimana perilaku dependensi tracking Signals setelah `await` pertama kali dieksekusi?
  2. Tuliskan implementasi korektif yang benar menggunakan jembatan interoperabilitas RxJS (`toObservable` + `switchMap` + cancellation token) dan kembalikan ke Signal dengan `toSignal()`.

### Skenario C: Migrasi Arsitektur Global Store (NgRx ComponentStore / RxJS ke Modern SignalStore)
* **Konteks:** Tim Anda sedang memodernisasi modul checkout berskala besar dari arsitektur berbasis RxJS (Subject/BehaviorSubject berantai dengan 15 `combineLatest` dan `pipe` kompleks) menuju Angular Signals murni.
* **Dilema Arsitektur:** Sebagian tim berargumen bahwa seluruh kode RxJS harus dimusnahkan demi "kesederhanaan" Signals. Sebagian lain berargumen bahwa Signals tidak mampu menangani operasi retry jaringan bertingkat, polling intermiten, dan debounce validasi kupon diskon.
* **Pertanyaan Diagnostik:**
  1. Sebagai Principal Architect, definisikan *boundary matrix* (aturan tegas): Karakteristik state/aliran data seperti apa yang **wajib** tetap berada di domain RxJS, dan karakteristik state seperti apa yang **wajib** dipindahkan ke Signals?
  2. Bagaimana merancang layer abstraksi Service State di mana consumer komponen template 100% hanya mengonsumsi Signals (`signal`, `computed`), namun internal service tetap memanfaatkan ketangguhan asynchronous pipeline RxJS?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Frequency Algorithmic Order-Book Visualizer
Membangun engine front-end untuk visualisasi Order Book bursa aset kripto dengan beban transaksi tinggi tanpa membebani browser main thread dan bebas dari memory leak.

#### 1. Problem Statement
Pasar aset kripto menghasilkan ratusan pembaruan pesanan (Bids & Asks) setiap detik. Data ini harus diterima via stream, di-buffer, diagregasi berdasarkan tingkat harga (depth), diurutkan, dan divisualisasikan secara real-time. Template harus beroperasi di bawah mode `ChangeDetectionStrategy.OnPush` (atau Signals standalone tanpa Zone.js) dengan efisiensi maksimal.

#### 2. Requirements & Architecture
* **Data Ingestion (RxJS Domain):**
  * Buat mock WebSocket provider menggunakan RxJS `interval` / `timer` yang memproduksi batch update `OrderBookDelta` (Side: 'BUY' | 'SELL', Price: number, Amount: number) setiap 10ms-50ms (fluktuasi random).
  * Lakukan *throttling / sample / buffer* pada RxJS stream agar tidak membombardir UI thread pada setiap micro-tick (misal: agregasi emisi maksimum setiap 100ms menggunakan windowing/buffering).
* **State & Derivations (Signals Domain):**
  * Konversi data teragregasi ke Signal State menggunakan `toSignal()`.
  * Simulasikan State Order Book utama:
    * `bids = signal<Map<number, number>>(new Map())`
    * `asks = signal<Map<number, number>>(new Map())`
  * Buat `computed()` derivation:
    * `topBids`: Mengembalikan 10 bid tertinggi, terurut menurun (*descending*).
    * `topAsks`: Mengembalikan 10 ask terendah, terurut menaik (*ascending*).
    * `spread`: Selisih harga antara ask terendah dan bid tertinggi.
    * `marketCondition`: Nilai `'NORMAL' | 'VOLATILE' | 'ILLIQUID'` berdasarkan `spread` dan volume.
* **Interoperabilitas & Side-Effects:**
  * Implementasikan logging ke mock analytics/telemetry via `effect()` yang hanya mencatat jika `marketCondition()` bernilai `'VOLATILE'`.
  * Pastikan logging analytics menggunakan `untracked()` untuk pembacaan payload harga agar dependensi tracking tidak membengkak.
  * Implementasikan cleanup / teardown logic yang ketat: Jika komponen di-destroy, seluruh stream RxJS ter-cancel otomatis, memory map dibersihkan, dan tidak ada dangling timers.

#### 3. Constraints
* Dilarang menggunakan `{ allowSignalWrites: true }` di dalam `effect()`.
* Dilarang memanggil `.subscribe()` manual di dalam komponen (Gunakan `toSignal()` atau async-pipe pattern boundary).
* State derivation di dalam `computed()` harus murni O(N log N) paling efisien, hindari deep clone yang tidak perlu pada setiap tick.
* Wajib kompatibel dengan arsitektur Zoneless (`provideExperimentalZonelessChangeDetection()`).

#### 4. Expected Output
1. File TypeScript implementasi service (`OrderBookEngineService`).
2. File TypeScript implementasi komponen (`OrderBookComponent`).
3. Analisis kompleksitas waktu dan memori (Big-O) dari pipeline reaktif yang dibuat.

---

## 5. Knowledge Check & Checklist

Verifikasi kesiapan Anda sebelum melangkah ke bab berikutnya. Berikan tanda centang jika Anda telah menguasai kompetensi di bawah ini.

### Saya harus memahami:
- [ ] Perbedaan fundamental arsitektur push-pull (Signals) vs push-only (RxJS Observables) serta trade-off alokasi memori keduanya.
- [ ] Mengapa Signals secara inheren bersifat *glitch-free* dan bagaimana *topological sorting* membatalkan evaluasi kalkulasi redundan (*diamond problem*).
- [ ] Karakteristik *Dynamic Dependency Tracking*: Bagaimana Signal mendaftarkan dependensi saat diakses dan melepasnya secara dinamis pada runtime branch.
- [ ] Perilaku *lazy evaluation* dan *memoization* pada `computed()`, serta batasan mengapa mutasi dilarang di dalamnya.
- [ ] Mekanisme Microtask Scheduling pada `toObservable()` dan implikasi intermediate value drop (lossy stream vs lossless stream).
- [ ] Aturan ketat Injection Context pada `effect()` dan bahaya runtime dari aktivasi `allowSignalWrites: true`.
- [ ] Boundary arsitektural: Kapan domain masalah harus diselesaikan dengan RxJS (koordinasi asinkron, retry, race conditions, debouncing) versus Signals (state synchrony, UI binding, derived state).

### Saya tidak perlu menghafal:
- [ ] Kode implementasi low-level dari linked list dependency graph internal Angular framework (`ReactiveNode`, `producer`, `consumer`).
- [ ] Nama algoritma private internal Angular yang mengontrol microtask batching change detection.
- [ ] Seluruh variasi overload signature method `toSignal()` dan `toObservable()` di TypeScript deklarasi (cukup pahami fungsi opsi kuncinya seperti `rejectErrors`, `requireSync`, `manualCleanup`).

### Saya harus bisa melakukan:
- [ ] Melakukan refaktor komponen lama yang sarat dengan subscription manual (`.subscribe()`, `takeUntilDestroyed`) menjadi deklaratif menggunakan `toSignal()`.
- [ ] Mengeliminasi race conditions pada flow pencarian/filter asinkron dengan merutekan Signal input ke RxJS `switchMap` sebelum mengembalikannya ke Signal UI.
- [ ] Mengisolasi non-reactive side-effects di dalam `effect()` menggunakan fungsi `untracked()`.
- [ ] Mengidentifikasi dan memperbaiki akar masalah siklus looping tak hingga (*infinite loop*) akibat mutasi state implisit di dalam consumer reaktif.
- [ ] Merancang arsitektur front-end enterprise zoneless-ready di mana transfer data intensitas tinggi ditangani via RxJS backpressure dan direpresentasikan ke view via fine-grained Signals.