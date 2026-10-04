# Bab 04 Module 01: Deterministic Enterprise State Management

---

## SEKSI 01 — IDENTITAS MODUL

* **Jalur Kurikulum:** 03-Frontend-and-Mobile
* **Topik Utama:** Flutter
* **Kode Modul:** FLT-STA-0401
* **Judul Modul:** Deterministic Enterprise State Management
* **Tingkat Kesulitan:** Advanced / Staff Engineer Level
* **Prasyarat Pengetahuan:** 
  * Pemahaman mendalam mengenai Dart Async primitives (`Stream`, `Future`, `Completer`, `Zone`).
  * Lifecycle Flutter Widget (`Element Tree`, `RenderObjectTree`, dirty marking pipeline).
  * Prinsip Object-Oriented & Functional Programming (Immutability, Value Equality, Algebraic Data Types).
  * Design Pattern: Reactive Extensions (Rx), State Machine, Finite State Automata (FSA).
* **Estimasi Waktu Belajar:** 180 Menit

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, engineer diharapkan mampu:

1. **Menganalisis dan Membuktikan Determinisme Status:** Membangun state machine matematis di Flutter yang mencegah race condition, mutasi status liar, dan fenomena *inconsistent UI state*.
2. **Menguasai Arsitektur BLoC & Redux pada Skala Enterprise:** Mengimplementasikan pola unidirectional data flow murni menggunakan `flutter_bloc` modern tanpa anti-pattern leakage.
3. **Mencegah Stream Memory Leaks dan Re-render Tak Perlu:** Mengoptimasi tree widget Flutter melalui strategi granular rebuild, pemanfaatan selector, dan penanganan auto-cancellation context.
4. **Mengisolasi Business Logic dari UI Lifecycle:** Mengimplementasikan transformasi event (`rxdart` event transformers: `debounce`, `throttle`, `droppable`, `concurrent`, `restartable`) untuk kontrol konkurensi I/O yang ketat.
5. **Membangun Telemetri dan Audit Trail Terpusat:** Merancang centralized interceptor/observer untuk merekam setiap mutasi status, memfasilitasi post-mortem debugging, dan integrasi automated crash forensics.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam sistem enterprise, bug fatal pada frontend jarang disebabkan oleh rendering layout yang rusak; bug fatal hampir selalu diakibatkan oleh **Non-Deterministic State**. Non-determinisme terjadi ketika status aplikasi bergantung pada urutan waktu yang tidak dapat diprediksi (misal: respons API lambat menimpa aksi user terbaru, navigasi bolak-balik menyisakan subscription aktif, atau dua komponen memutasi status yang sama secara bersamaan).

### Formula Status Deterministik
$$\text{UI} = f(\text{State})$$
$$\text{State}_{n+1} = \text{Transition}(\text{State}_n, \text{Event})$$

Mental model yang harus dipegang teguh:
* **UI adalah Proyeksi Pasif:** Widget tree adalah proyeksi visual murni dari state snapshot saat ini. UI tidak boleh membuat keputusan logis atau mengkalkulasi mutasi.
* **Perubahan adalah Rentetan Kejadian Diskret (Discrete Events):** State tidak boleh dimutasi secara imperatif (`state.x = y`). Perubahan status hanya diizinkan sebagai akibat dari *Event* atau *Action* eksplisit yang diproses oleh fungsi transisi state deterministik.
* **Immutability Mutlak:** Setiap perubahan menghasilkan instans objek status baru secara keseluruhan (`deep immutable copy`). Objek lama dibekukan (*frozen*) untuk menjamin *time-travel auditability* dan mencegah *side-effect leaking*.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah diagram aliran data satu arah (Unidirectional Data Flow) berbasis event-driven enterprise state machine dengan Rx transformer concurrency control.

```
       +-------------------------------------------------------------+
       |                        USER INTERFACE                       |
       |  (Flutter Widget Tree: Declarative, Stateless/Hook Consumer)|
       +-------------------------------------------------------------+
                   |                                        ^
                   | Dispatch (Event)                       | Listen / Select
                   v                                        | (New State Emission)
       +-------------------------+            +-------------------------+
       |      EVENT STREAM       |            |      STATE STREAM       |
       |  (Buffered Broadcast)   |            |  (BehaviorSubject/Seed) |
       +-------------------------+            +-------------------------+
                   |                                        ^
                   | Rx Transformer (debounce/restartable)  | Emit (Yield)
                   v                                        |
+-------------------------------------------------------------------------------+
|                    STATE MACHINE CORE (BLoC / Reducer Engine)                 |
|                                                                               |
|  +--------------------+      Validation       +---------------------------+   |
|  | Event Queue Worker | --------------------> | State Transition Function |   |
|  +--------------------+                       +---------------------------+   |
|            |                                                |                 |
|            | Intercept / Telemetry                          | Dependency Call |
|            v                                                v                 |
|  +--------------------+                       +---------------------------+   |
|  | Corporate Observer |                       | Repository & Domain Layer |   |
|  | (Audit Logging)    |                       | (Data Sync, HTTP, Cache)  |   |
|  +--------------------+                       +---------------------------+   |
+-------------------------------------------------------------------------------+
```

### Penjelasan Komponen Alur:
1. **User Interface** memicu `Event` terdefinisi dan mengirimkannya ke `BLoC Engine`. UI tidak memedulikan bagaimana event diproses.
2. **Event Transformer Engine** mengevaluasi event queue dengan aturan konkurensi (misal: membatalkan request sebelumnya jika request baru datang, atau mengabaikan event baru jika event lama sedang berjalan).
3. **State Transition Engine** mengeksekusi business logic via Repository, menghitung delta perubahan, memvalidasi invariant bisnis, lalu menghasilkan `Immutable State` baru.
4. **State Stream** mendistribusikan state terbaru ke widget subscriber. Hanya sub-tree widget yang terdampak diferensiasi nilai (`distinctUntilChanged`) yang akan di-rebuild oleh Flutter engine.

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Struktur Eksekusi Event di BLoC Engine
Secara internal, BLoC dibangun di atas `StreamController` Dart. Pemrosesan internal mengikuti siklus berikut:
* `on<Event>` meregistrasikan handler ke dalam internal event map.
* Secara default, `Bloc` mengeksekusi event secara concurent via transformer bawaan yang menggunakan urutan event bertahap (`asyncExpand` atau `switchMap` tergantung konfigurasi).
* Jika event ditambahkan melalui method `add(Event)`, event tersebut dialirkan ke internal `_eventController`.
* Handler mengeksekusi operasi asinkron dan memanggil fungsi `emit(State)`.

### 2. Guarding State Transition
BLoC internal memiliki proteksi built-in:
* **State De-duplication:** Jika `emit(newState)` dipanggil dan `newState == oldState` (berdasarkan value equality `==`), BLoC secara otomatis menolak emisi tersebut dan tidak meneruskannya ke listener UI. Inilah mengapa implementasi `Equatable` atau immutable value types sangat krusial.
* **Closed Stream Guard:** Jika BLoC telah di-`close()`, pemanggilan `emit()` akan memicu runtime assertion exception `StateError` untuk mencegah memory leak dan zombie callback.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Event Transformations & Concurrency Controls
Dalam skenario enterprise, salah satu penyebab terbesar rusaknya determinisme adalah *Race Condition* pada asynchronous network calls. Pertimbangkan pengguna yang mengetik di kotak pencarian: jika request "ABC" memakan waktu 800ms dan request "ABCD" memakan waktu 150ms, respons "ABC" bisa tiba terakhir dan menimpa UI, menampilkan hasil yang usang.

Untuk mengatasi ini, state management harus menggunakan transformer konkurensi:

| Transformer Policy | Basis Operasi RxDart | Perilaku Eksekusi | Use Case Ideal |
| :--- | :--- | :--- | :--- |
| **Concurrent (Default)** | `mergeMap` | Semua event diproses paralel serentak tanpa antrean. | Analitik logging, background metric dispatching. |
| **Sequential** | `concatMap` | Event diproses satu per satu secara sekuensial; event berikutnya menunggu event sebelumnya selesai. | Operasi order payment checkout, sinkronisasi offline-first SQLite. |
| **Droppable** | `exhaustMap` | Jika ada event sedang diproses, event baru yang masuk diabaikan sampai handler selesai. | Submit tombol forms, tombol refresh transaksi. |
| **Restartable** | `switchMap` | Membatalkan event yang sedang berjalan dan hanya memproses event yang paling baru masuk. | Search bar autocomplete, tab switching dynamic fetching. |

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi BLoC murni dari dasar, memanfaatkan value equality mutlak dan konfigurasi event transformer lanjutan.

```dart
// lib/core/bloc/order_contract.dart
import 'package:flutter/foundation.dart';
import 'package:bloc/bloc.dart';
import 'package:bloc_concurrency/bloc_concurrency.dart';

// -------------------------------------------------------------
// EVENT DEFINITION (Algebraic Data Types via Sealed Classes)
// -------------------------------------------------------------
@immutable
sealed class OrderEvent {
  const OrderEvent();
}

final class OrderSearchQueryChanged extends OrderEvent {
  final String query;
  const OrderSearchQueryChanged(this.query);

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is OrderSearchQueryChanged &&
          runtimeType == other.runtimeType &&
          query == other.query;

  @override
  int get hashCode => query.hashCode;
}

final class OrderCheckoutSubmitted extends OrderEvent {
  final String cartId;
  const OrderCheckoutSubmitted(this.cartId);

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is OrderCheckoutSubmitted &&
          runtimeType == other.runtimeType &&
          cartId == other.cartId;

  @override
  int get hashCode => cartId.hashCode;
}

// -------------------------------------------------------------
// STATE DEFINITION
// -------------------------------------------------------------
enum OrderStatus { initial, loading, success, failure }

@immutable
final class OrderState {
  final OrderStatus status;
  final List<String> searchResults;
  final String? errorMessage;
  final String? activeTransactionId;

  const OrderState({
    required this.status,
    this.searchResults = const [],
    this.errorMessage,
    this.activeTransactionId,
  });

  const OrderState.initial()
      : status = OrderStatus.initial,
        searchResults = const [],
        errorMessage = null,
        activeTransactionId = null;

  OrderState copyWith({
    OrderStatus? status,
    List<String>? searchResults,
    String? errorMessage,
    String? activeTransactionId,
  }) {
    return OrderState(
      status: status ?? this.status,
      searchResults: searchResults ?? this.searchResults,
      errorMessage: errorMessage ?? this.errorMessage,
      activeTransactionId: activeTransactionId ?? this.activeTransactionId,
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is OrderState &&
          runtimeType == other.runtimeType &&
          status == other.status &&
          listEquals(searchResults, other.searchResults) &&
          errorMessage == other.errorMessage &&
          activeTransactionId == other.activeTransactionId;

  @override
  int get hashCode =>
      status.hashCode ^
      Object.hashAll(searchResults) ^
      errorMessage.hashCode ^
      activeTransactionId.hashCode;
}

// -------------------------------------------------------------
// REPOSITORY CONTRACT
// -------------------------------------------------------------
abstract interface class OrderRepository {
  Future<List<String>> searchOrders(String query);
  Future<String> executeCheckout(String cartId);
}

// -------------------------------------------------------------
// BLOC IMPLEMENTATION
// -------------------------------------------------------------
class OrderBloc extends Bloc<OrderEvent, OrderState> {
  final OrderRepository _orderRepository;

  OrderBloc(this._orderRepository) : super(const OrderState.initial()) {
    // Transformer Restartable: Batalkan pencarian lama jika query baru dimasukkan
    on<OrderSearchQueryChanged>(
      _onSearchQueryChanged,
      transformer: restartable(),
    );

    // Transformer Droppable: Abaikan klik berulang saat proses checkout berlangsung
    on<OrderCheckoutSubmitted>(
      _onCheckoutSubmitted,
      transformer: droppable(),
    );
  }

  Future<void> _onSearchQueryChanged(
    OrderSearchQueryChanged event,
    Emitter<OrderState> emit,
  ) async {
    if (event.query.trim().isEmpty) {
      emit(state.copyWith(
        status: OrderStatus.initial,
        searchResults: const [],
      ));
      return;
    }

    emit(state.copyWith(status: OrderStatus.loading));

    try {
      final results = await _orderRepository.searchOrders(event.query);
      emit(state.copyWith(
        status: OrderStatus.success,
        searchResults: results,
      ));
    } catch (e) {
      emit(state.copyWith(
        status: OrderStatus.failure,
        errorMessage: e.toString(),
      ));
    }
  }

  Future<void> _onCheckoutSubmitted(
    OrderCheckoutSubmitted event,
    Emitter<OrderState> emit,
  ) async {
    emit(state.copyWith(status: OrderStatus.loading));

    try {
      final txId = await _orderRepository.executeCheckout(event.cartId);
      emit(state.copyWith(
        status: OrderStatus.success,
        activeTransactionId: txId,
      ));
    } catch (e) {
      emit(state.copyWith(
        status: OrderStatus.failure,
        errorMessage: e.toString(),
      ));
    }
  }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

* **Baris 11 (`sealed class OrderEvent`):** Fitur compile-time safety dari Dart 3. Semua variasi event harus didefinisikan dalam modul/file yang sama, memungkinkan exhaustiveness checking pada struktur percabangan tanpa `default:`.
* **Baris 20–28 (`operator ==` & `hashCode` di Event):** Memberikan validasi value equality. Dua instans event dengan konten identik dianggap sama persis, mencegah duplikasi event yang tidak disengaja.
* **Baris 44–75 (`final class OrderState`):** Implementasi immutable state sejati. Nilai tidak dapat diubah di tempat (`in-place modification`), melainkan harus dikloning menggunakan method `copyWith`.
* **Baris 78–82 (`operator ==` pada State dengan `listEquals`):** Memastikan bahwa array `searchResults` dibandingkan berdasarkan elemen di dalamnya, bukan referensi memorinya. Ini vital agar UI Flutter tidak me-rebuild dirinya sendiri jika isi array-nya identik.
* **Baris 98–101 (`transformer: restartable()`):** Memasukkan interceptor Rx concurrency `switchMap`. Jika user mengetik karakter berikutnya, Future pencarian yang sedang berjalan langsung dibatalkan di level stream, mencegah race condition jaringan.
* **Baris 104–107 (`transformer: droppable()`):** Memasukkan interceptor `exhaustMap`. Jika tombol checkout diklik 10 kali secara membabi buta, hanya klik pertama yang dijalankan. Klik ke-2 hingga ke-10 diabaikan sepenuhnya hingga proses pertama selesai.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Aplikasi Bursa Saham FinTech (Order Book Execution)
Pada sistem bursa instrumen keuangan tingkat tinggi, aplikasi menerima pembaruan harga realtime via WebSocket (30 frame/detik) sekaligus menangani pengiriman instruksi order pengguna. 

**Tantangan Sistem:**
1. Emisi WebSocket berkecepatan tinggi dapat melumpuhkan rendering thread UI jika setiap pembaruan data memicu rebuild pohon widget global.
2. Pengguna sering kali mengubah filter portofolio secara agresif saat koneksi jaringan berfluktuasi antara 4G dan Edge.
3. Mutasi order tidak boleh tereksekusi dua kali (*Idempotency Risk*) di bawah kondisi sinyal tidak stabil.

**Solusi Arsitektural:**
* Gunakan custom event transformer berbasis `throttleTime` dari RxDart untuk mengelompokkan emisi real-time WebSocket ke batas refresh rate target (maksimal 60 FPS / per 16ms).
* Gunakan state machine terisolasi dengan isolasi transaksi menggunakan *Optimistic UI Update* yang aman dan dapat di-rollback secara deterministik bila backend menolak eksekusi order.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah kode siap produksi untuk menangani trading order system dengan state deterministik:

```dart
// lib/features/trading/trading_engine.dart
import 'dart:async';
import 'package:flutter/widgets.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:rxdart/rxdart.dart';

// Domain Entities
@immutable
final class TickerPrice {
  final String symbol;
  final double price;
  final int timestampMs;

  const TickerPrice({
    required this.symbol,
    required this.price,
    required this.timestampMs,
  });

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is TickerPrice &&
          runtimeType == other.runtimeType &&
          symbol == other.symbol &&
          price == other.price &&
          timestampMs == other.timestampMs;

  @override
  int get hashCode => symbol.hashCode ^ price.hashCode ^ timestampMs.hashCode;
}

// Events
@immutable
sealed class TradingEvent {
  const TradingEvent();
}

final class RealtimeTickReceived extends TradingEvent {
  final TickerPrice tick;
  const RealtimeTickReceived(this.tick);
}

final class ExecuteMarketOrder extends TradingEvent {
  final String orderId;
  final String symbol;
  final double amount;
  const ExecuteMarketOrder({
    required this.orderId,
    required this.symbol,
    required this.amount,
  });
}

// State
enum OrderExecutionPhase { idle, executing, confirmed, rejected }

@immutable
final class TradingState {
  final TickerPrice? latestTick;
  final OrderExecutionPhase executionPhase;
  final String? lastOrderId;
  final String? failureReason;

  const TradingState({
    this.latestTick,
    this.executionPhase = OrderExecutionPhase.idle,
    this.lastOrderId,
    this.failureReason,
  });

  TradingState copyWith({
    TickerPrice? latestTick,
    OrderExecutionPhase? executionPhase,
    String? lastOrderId,
    String? failureReason,
  }) {
    return TradingState(
      latestTick: latestTick ?? this.latestTick,
      executionPhase: executionPhase ?? this.executionPhase,
      lastOrderId: lastOrderId ?? this.lastOrderId,
      failureReason: failureReason ?? this.failureReason,
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is TradingState &&
          runtimeType == other.runtimeType &&
          latestTick == other.latestTick &&
          executionPhase == other.executionPhase &&
          lastOrderId == other.lastOrderId &&
          failureReason == other.failureReason;

  @override
  int get hashCode =>
      latestTick.hashCode ^
      executionPhase.hashCode ^
      lastOrderId.hashCode ^
      failureReason.hashCode;
}

// Custom Transformer untuk Throttling High Frequency Socket
EventTransformer<E> throttleWindow<E>(Duration duration) {
  return (events, mapper) {
    return events.throttleTime(duration).flatMap(mapper);
  };
}

// BLoC Implementation
class TradingBloc extends Bloc<TradingEvent, TradingState> {
  final Stream<TickerPrice> _priceStream;
  final Future<void> Function(String id, String symbol, double amt) _tradeApi;
  StreamSubscription<TickerPrice>? _socketSubscription;

  TradingBloc({
    required Stream<TickerPrice> priceStream,
    required Future<void> Function(String id, String symbol, double amt) tradeApi,
  })  : _priceStream = priceStream,
        _tradeApi = tradeApi,
        super(const TradingState()) {
    
    // Proteksi UI dari render loop: Throttle ke 50ms (~20 updates/sec maks)
    on<RealtimeTickReceived>(
      _onRealtimeTickReceived,
      transformer: throttleWindow(const Duration(milliseconds: 50)),
    );

    // Sekuensial: Jamin order dieksekusi berurutan tanpa jumping
    on<ExecuteMarketOrder>(
      _onExecuteMarketOrder,
    );

    _listenToMarketSocket();
  }

  void _listenToMarketSocket() {
    _socketSubscription = _priceStream.listen(
      (tick) => add(RealtimeTickReceived(tick)),
      onError: (err) => addError(err),
      cancelOnError: false,
    );
  }

  void _onRealtimeTickReceived(
    RealtimeTickReceived event,
    Emitter<TradingState> emit,
  ) {
    // Hindari emit jika harga tidak bergeser secara signifikan
    if (state.latestTick != null &&
        state.latestTick!.price == event.tick.price) {
      return;
    }
    emit(state.copyWith(latestTick: event.tick));
  }

  Future<void> _onExecuteMarketOrder(
    ExecuteMarketOrder event,
    Emitter<TradingState> emit,
  ) async {
    // Idempotency check: Jangan jalankan order yang sama dua kali
    if (state.executionPhase == OrderExecutionPhase.executing &&
        state.lastOrderId == event.orderId) {
      return;
    }

    emit(state.copyWith(
      executionPhase: OrderExecutionPhase.executing,
      lastOrderId: event.orderId,
      failureReason: null,
    ));

    try {
      await _tradeApi(event.orderId, event.symbol, event.amount);
      emit(state.copyWith(
        executionPhase: OrderExecutionPhase.confirmed,
      ));
    } catch (e) {
      emit(state.copyWith(
        executionPhase: OrderExecutionPhase.rejected,
        failureReason: e.toString(),
      ));
    }
  }

  @override
  Future<void> close() async {
    await _socketSubscription?.cancel();
    return super.close();
  }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter Arsitektur | BLoC Pattern (`flutter_bloc`) | Riverpod (`AsyncNotifier`) | Redux murni | Provider Dasar |
| :--- | :--- | :--- | :--- | :--- |
| **Tingkat Determinisme** | **Tertinggi.** Event-driven kaku, mutasi imperatif dilarang keras. | **Tinggi.** Fungsional-deklaratif, tetapi mudah dirusak jika state di-assign langsung. | **Tertinggi.** Pure reducer function tanpa side-effect langsung. | **Rendah.** Rawan mutasi imperatif liar pada `ChangeNotifier`. |
| **Boilerplate & Verbosity** | Tinggi (Memerlukan Event, State, dan Handler terpisah). | Rendah hingga Menengah (Didukung macro/codegen). | Sangat Tinggi (Actions, Reducers, Middleware, State classes). | Minimal (Hanya class membungkus method biasa). |
| **Testing Simplicity** | Sangat mudah via `bloc_test`. Format deklaratif `expect: [...]`. | Sangat mudah, tetapi setup mock dependensi provider cukup kompleks. | Sangat murni (Hanya perlu unit test fungsi reducer murni). | Rumit ketika dependensi multi-provider bersarang. |
| **Stream Overhead** | Memerlukan runtime memory overhead dari StreamController dan Rx microtasks. | Sangat ringan, menggunakan internal linked-list notification. | Sangat ringan, pemanggilan sinkronus murni. | Ringan, berbasis listener array native. |
| **Concurrency Tuning** | **Terbaik.** Dukungan native untuk stream transformers (`switchMap`, dsb). | Terbatas secara native (Perlu penanganan debounce/throttle manual). | Bergantung pada middleware pihak ketiga (`redux_epics`). | Manual. Sulit mencegah race condition tanpa helper kustom. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Zombie Subscription Context Leak
* **Masalah:** Menggunakan callback asinkronus `emit()` setelah bloc ditutup (`close()`). Ini sering terjadi ketika user meninggalkan layar (BLoC di-dispose) sementara Future I/O masih tertunda di jaringan.
* **Mitigasi:** Pustaka BLoC modern mengamankan ini secara internal, namun jika Anda membangun custom state machine, selalu evaluasi `emit.isDone` sebelum memancarkan status dalam handler:
  ```dart
  final data = await fetchAsync();
  if (!emit.isDone) {
    emit(Success(data));
  }
  ```

### 2. Shallow Equality Array Pitfall
* **Masalah:** Instans state baru memuat reference array yang sama dengan instance state lama:
  ```dart
  // RUSAK: Mutasi in-place tidak akan memicu rebuild UI karena instance List sama
  state.items.add(newItem);
  emit(state.copyWith(items: state.items)); 
  ```
* **Mitigasi:** Selalu duplikasi koleksi ke instans memori baru:
  ```dart
  // BENAR: Instance array baru dialokasikan
  emit(state.copyWith(items: List.unmodifiable([...state.items, newItem])));
  ```

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Menjalankan Logika Navigasi di dalam `BlocBuilder`
* **Anti-Pattern:**
  ```dart
  // JANGAN LAKUKAN INI
  BlocBuilder<AuthBloc, AuthState>(
    builder: (context, state) {
      if (state is Unauthenticated) {
        Navigator.pushReplacementNamed(context, '/login'); // Side-effect di render function!
      }
      return Container();
    },
  )
  ```
* **Solusi Arsitektural:** Pisahkan antara fungsi proyeksi visual murni (`BlocBuilder`) dan penanganan efek samping transien seperti dialog/navigasi (`BlocListener`).

### 2. Over-Globalizing State
* **Anti-Pattern:** Meletakkan semua state pada akar aplikasi (`MultiBlocProvider` di `main.dart`). Ini menyebabkan bloat memori dan lifecycle yang tidak pernah bersih.
* **Solusi Arsitektural:** Batasi scope lifecycle BLoC sedekat mungkin dengan layar atau sub-tree yang membutuhkannya, manfaatkan auto-dispose lifecycle pada route.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **State Immunitability Enforced via Lint:** Gunakan rule analitik static analyzer ketat. Tambahkan package `freezed` atau definisikan `dart_code_metrics` untuk melarang mutable field (`late`, `var`, mutable `List/Map`) pada state class.
2. **Naming Convention:**
   * **Events:** Format waktu lampau yang berorientasi pada aksi pengguna: `OrderPaymentButtonPressed`, `CustomerAddressUpdated` (Bukan `PayOrder`, `UpdateAddress`).
   * **State:** Menggambarkan fakta saat ini: `OrderState(status: OrderStatus.loading)`.
3. **Satu Event, Satu Tujuan:** Jangan gunakan event generik seperti `SetData(dynamic data)`. Setiap interaksi bisnis harus memiliki event diskret untuk mempertahankan jejak audit.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### Granular Rebuild Optimization
Untuk mencegah rebuild pohon widget secara keseluruhan saat status berubah sebagian, gunakan mekanisme `buildWhen` atau `context.select`:

```dart
// Mencegah widget OrderPriceTag me-rebuild saat field non-price (misal: errorMessage) berubah
Widget build(BuildContext context) {
  final currentPrice = context.select<TradingBloc, double?>(
    (bloc) => bloc.state.latestTick?.price,
  );

  return Text('Price: ${currentPrice ?? 0.0}');
}
```

Mekanisme `context.select` mengaitkan elemen `InheritedWidget` secara presisi hanya pada nilai hasil reduksi pemetaan (scalar selector), secara drastis mengurangi *frame-drop* (jank) selama animasi rendering.

---

## SEKSI 16 — KEAMANAN & HARDENING

State management sering kali menjadi target kebocoran data sensitif (PII - Personally Identifiable Information).

1. **Redaksi Logging Otomatis:** Saat mengimplementasikan logger global (BLoC Observer), pastikan state tidak mencetak data mentah seperti password, CVV kartu kredit, atau token autentikasi.
   ```dart
   @override
   String toString() {
     // Hindari mencetak password ke log/crashlytics
     return 'UserState(id: $id, email: $email, token: [REDACTED])';
   }
   ```
2. **State Purging on Auth Invalidation:** Ketika state otentikasi berubah menjadi `Unauthenticated`, rancang sistem pembersihan hierarkis. Semua sub-bloc harus secara deterministik dieksekusi untuk mereset seluruh in-memory state guna menghindari privilege escalation antarsesi pengguna pada perangkat bersama.

---

## SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

Untuk lingkungan produksi enterprise, implementasikan centralized observer yang menangkap setiap transisi state dan kesalahan:

```dart
// lib/core/observability/enterprise_bloc_observer.dart
import 'package:bloc/bloc.dart';
import 'dart:developer' as developer;

class EnterpriseBlocObserver extends BlocObserver {
  @override
  void onEvent(Bloc bloc, Object? event) {
    super.onEvent(bloc, event);
    developer.log(
      'EVENT DISPATCHED: ${event.runtimeType}',
      name: 'STATE_TELEMETRY',
      error: {'bloc': bloc.runtimeType.toString(), 'event': event.toString()},
    );
  }

  @override
  void onTransition(Bloc bloc, Transition transition) {
    super.onTransition(bloc, transition);
    developer.log(
      'TRANSITION: ${transition.event.runtimeType}',
      name: 'STATE_TELEMETRY',
      error: {
        'bloc': bloc.runtimeType.toString(),
        'currentState': transition.currentState.toString(),
        'nextState': transition.nextState.toString(),
      },
    );
  }

  @override
  void onError(BlocBase bloc, Object error, StackTrace stackTrace) {
    developer.log(
      'BLOC EXCEPTION DETECTED',
      name: 'STATE_TELEMETRY',
      error: error,
      stackTrace: stackTrace,
    );
    // Disini tempat menyambungkan ke Sentry / Datadog / Crashlytics
    super.onError(bloc, error, stackTrace);
  }
}
```
Aktifkan di entry point aplikasi (`main.dart`):
```dart
void main() {
  Bloc.observer = EnterpriseBlocObserver();
  runApp(const MyApp());
}
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

* **Unidirectional Flow:** Event $\rightarrow$ Transformer $\rightarrow$ State Transition $\rightarrow$ New Immutable State $\rightarrow$ UI Build Selector.
* **`restartable()`:** Paling cocok untuk query pencarian/autocomplete (membatalkan request sebelumnya).
* **`droppable()`:** Paling cocok untuk submit form/transaksi (mencegah double-click spam).
* **`concurrent()`:** Menjalankan pemrosesan paralel tanpa antrean blocking.
* **`sequential()`:** Memproses strictly satu demi satu secara berurutan sesuai timeline pengiriman.
* **Granular Rebuild:** Jangan membungkus seluruh `Scaffold` dengan `BlocBuilder`. Bungkus hanya widget target terkecil, atau gunakan `context.select()`.

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal 1
Mengapa fungsi `build` pada Widget Flutter tidak boleh memanggil `bloc.add(Event)` secara langsung?
A) Karena Dart melarang eksekusi asinkronus dalam method render.  
B) Karena fungsi `build` harus berupa pure function bebas efek samping; memicu event saat build dapat mengakibatkan siklus render loop tanpa henti.  
C) Karena StreamController akan otomatis tertutup jika dipanggil dari pohon render.  
D) Karena hal itu memblokir Garbage Collector Dart untuk membersihkan memory widget lama.  

### Soal 2
Apa yang terjadi jika Anda memanggil `emit(state.copyWith())` namun nilai internal state yang baru menghasilkan evaluasi `true` pada operator `==` dibanding state yang lama?
A) BLoC melempar exception `StateRedundancyException`.  
B) BLoC tetap mendistribusikan state ke stream dan widget akan dipaksa me-render ulang.  
C) BLoC secara otomatis mendeteksi kesamaan nilai dan membatalkan emisi sehingga widget listener tidak me-rebuild.  
D) State engine mereset diri kembali ke initial state.  

### Soal 3
Dalam situasi di mana user menekan tombol "Pay Now" secara berulang-ulang dalam rentang 200 milidetik, transformer manakah yang paling tepat untuk mencegah pemrosesan transaksi ganda?
A) `concurrent()`  
B) `restartable()`  
C) `droppable()`  
D) `bufferCount()`  

### Soal 4
Apa perbedaan mendasar antara `BlocListener` dan `BlocBuilder`?
A) `BlocListener` digunakan untuk rendering UI, sedangkan `BlocBuilder` untuk navigasi.  
B) `BlocListener` hanya merespons perubahan state untuk menjalankan side-effect (seperti navigasi atau Snackbar) tanpa mengembalikan widget, sedangkan `BlocBuilder` mengembalikan widget untuk dirender.  
C) `BlocListener` tidak memerlukan tipe generics, sedangkan `BlocBuilder` wajib.  
D) `BlocBuilder` otomatis menutup controller BLoC ketika widget di-dispose, sedangkan `BlocListener` tidak.  

### Soal 5
Manakah teknik paling efisien untuk membatasi pembaruan widget hanya pada perubahan satu string properti dari sebuah BLoC yang memuat puluhan data kompleks?
A) Menggunakan `DefaultTextStyle`.  
B) Menggunakan `context.select<MyBloc, String>((bloc) => bloc.state.targetProperty)`.  
C) Membuka stream baru langsung via `bloc.stream.listen()`.  
D) Memanggil `setState()` di dalam listener lokal.  

---

### Kunci Jawaban & Analisis Evaluasi
1. **Jawaban: B.** Pemanggilan mutasi di dalam `build` memicu side-effect saat UI sedang dalam proses layout. Hal ini merusak stabilitas Flutter Engine dan sering memicu error *setState() or markNeedsBuild() called during build*.
2. **Jawaban: C.** BLoC mengimplementasikan filter `distinctUntilChanged` internal; jika state baru sama secara nilai (`==`) dengan state aktif saat ini, perubahan diabaikan untuk efisiensi CPU dan GPU.
3. **Jawaban: C.**