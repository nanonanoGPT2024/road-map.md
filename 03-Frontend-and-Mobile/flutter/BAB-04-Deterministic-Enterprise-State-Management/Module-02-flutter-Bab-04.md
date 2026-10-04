# Kurikulum Enterprise: Flutter Engineering
## Kategori: 03-Frontend-and-Mobile
### BAB-04: Deterministic Enterprise State Management
#### Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, software engineer enterprise diharapkan mampu:
1. **Menganalisis dan Mengendalikan Concurrency**: Menguasai semantik `bloc_concurrency` (misalnya `droppable`, `restartable`, `sequential`, `concurrent`) pada event transformer untuk memitigasi race condition dan starvation.
2. **Merancang Finite State Machine (FSM)**: Mengimplementasikan state machine deterministik tingkat enterprise menggunakan Dart 3 *sealed classes* dan *pattern matching* guna mencegah transisi state ilegal (*invalid state transitions*).
3. **Membangun Komunikasi Antar-BLoC Skala Besar**: Mengeliminasi kopling langsung antar-BLoC melalui implementasi *Domain Repository-driven Events* atau *Mediator Pattern*.
4. **Menerapkan Persistence & Hydration Terdistribusi**: Mengonfigurasi `HydratedBloc` dengan enkripsi lokal, migrasi skema state otomatis, dan sinkronisasi atomik.
5. **Melakukan Profiling Memori & Garbage Collection**: Mendeteksi, menganalisis, dan membasmi memory leak yang disebabkan oleh *dangling stream subscriptions* dan *unreleased event listeners* menggunakan Dart DevTools.

---

### 2. Prerequisite
Sebelum mempelajari modul ini, peserta wajib memiliki pemahaman mendalam tentang:
* **Dart Asynchronous Primitives**: Event loop, Microtask queue, `Future`, `StreamController`, `StreamTransformer`, dan Backpressure.
* **Dart 3 Core Features**: Pattern matching, exhaustive switch statements, dan *sealed class hierarchies*.
* **Fundamental BLoC/Cubit**: Unidirectional Data Flow (UDF), lifecycle `BlocObserver`, serta konfigurasi dependensi via `RepositoryProvider` dan `BlocProvider`.
* **Clean Architecture & SOLID Principles**: Pemisahan tegas antara Presentation Layer, Domain Layer (Use Cases/Entities), dan Data Layer (Repositories/DataSources).

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Mekanisme Internal Stream dan Event Transformation
Di bawah kap mesin, BLoC bekerja sebagai pemrosesan berbasis `StreamController.broadcast()`. Ketika sebuah event ditambahkan melalui `bloc.add(Event)`, event tersebut tidak langsung dieksekusi secara instan, melainkan dimasukkan ke dalam antrean sinkron BLoC internal yang kemudian dialirkan ke `EventTransformer`.

Secara default, implementasi `on<Event>` pada BLoC modern memproses event secara `concurrent`. Namun, dalam sistem transaksional enterprise, pemrosesan konkuren tanpa kendali membuka celah *out-of-order execution* akibat latensi jaringan asinkron.

```
+-------------------------------------------------------------------------+
|                               BLoC Engine                               |
|                                                                         |
|  Event Inbound             Event Transformer (e.g., sequential)         |
|  [E1] [E2] [E3] ---> [ Queue / Stream ] ===> [ Transform Pipeline ]     |
|                                                     |                   |
|                                                     v                   |
|  State Outbound             State Stream         Event Handler (on<E>)  |
|  (S3) <--- (S2) <--- (S1) <===================== [ emit(State) ]       |
+-------------------------------------------------------------------------+
```

Jika tidak dikontrol, dua event asinkron identik yang dieksekusi bersamaan akan memicu race condition:
* **`concurrent()`**: Event diproses paralel. Urutan emisi state tidak dijamin berbanding lurus dengan urutan datangnya event (rentan race condition).
* **`sequential()`**: Memanfaatkan `asyncExpand`. Event berikutnya diblokir hingga `Future` dari event handler sebelumnya selesai (Wajib untuk pipeline mutasi finansial).
* **`droppable()`**: Memanfaatkan `exhaustMap`. Jika handler sedang mengeksekusi operasi asinkron, seluruh event baru yang masuk akan diabaikan hingga handler kembali idle (Wajib untuk pencegahan multi-submit/double-tap).
* **`restartable()`**: Memanfaatkan `switchMap`. Jika event baru masuk saat handler sebelumnya masih berjalan, operasi asinkron yang sedang berjalan langsung dibatalkan (diberhentikan via stream cancellation token) dan hanya event terbaru yang diproses (Wajib untuk Typeahead Search).

#### B. Deterministik Finite State Machine (FSM) via Sealed Classes
State management enterprise menuntut determinisme absolut: sistem hanya boleh berada dalam satu state valid pada satu waktu, dan perpindahan dari State A ke State B harus melalui transisi yang terverifikasi.

Menggunakan Dart 3 `sealed class`, kompiler menjamin keamanan tipe secara *exhaustive*:
```dart
// Transisi matematis FSM: T(S, E) -> S'
// State S dipadukan dengan Event E menghasilkan State baru S' secara deterministik
```
Jika ada kombinasi State dan Event yang tidak terdefinisi dalam blok transisi, sistem secara arsitektural menolak mutasi tersebut melalui *compile-time error*, bukan *runtime crash*.

#### C. Topologi Komunikasi Antar-BLoC (Decoupled Topologies)
Kesalahan fatal pada arsitektur skala menengah ke atas adalah mengizinkan satu BLoC mendengarkan BLoC lain secara langsung (`BlocListener` yang memanggil `blocB.add(Event)` atau menyuntikkan `BlocA` ke konstruktor `BlocB`). Pola ini menciptakan *tight-coupling*, siklus dependensi (*circular dependencies*), dan menyulitkan isolasi unit test.

Solusi arsitektur produksi adalah menggunakan **Domain Repository / Event-Driven State Mediation**:
1. `BlocA` memanggil method pada `Repository`.
2. `Repository` memodifikasi data dan memancarkan stream entitas baru melalui broadcast `Stream` internal (misalnya `BehaviorSubject` dari RxDart atau Reactive Cache).
3. `BlocB` mengamati (*subscribe*) `Stream` dari `Repository` tersebut di domain layer.
4. BLoC tidak pernah tahu eksistensi satu sama lain. Relasi terjalin secara reaktif melalui single source of truth (SSOT) pada layer Data/Domain.

---

### 4. Why & What
* **Mengapa bukan pendekatan Stateful Biasa atau Provider primitif?**
  Aplikasi enterprise (Fintech, Core Banking, Supply Chain, Logistics) menangani multi-koneksi websocket, transisi offline-ke-online, otentikasi sesi token kedaluwarsa secara mendadak, serta manipulasi data transaksional bertingkat. Mengandalkan `setState` atau mutasi state mutable lokal menyebabkan *distributed state divergence*, di mana dua bagian layar menampilkan status entitas yang bertentangan.
* **Apa itu Deterministic Enterprise BLoC?**
  Arsitektur state management yang menjamin:
  1. *Single Source of Truth*: Data bersifat immutable.
  2. *Predictable Mutations*: Perubahan data hanya dapat terjadi lewat Event terdaftar.
  3. *Auditability & Observability*: Setiap mutasi dicatat melalui pipeline analitik/log global.
  4. *Idempotency*: Re-evaluasi event yang sama tidak merusak integritas state aplikasi.

---

### 5. How (Workflow Detail)

Alur siklus hidup pemrosesan Event tingkat lanjut:

1. **Dispatching**: View memanggil `context.read<OrderBloc>().add(const SubmitOrderEvent())`.
2. **Transforming**: Event melewati custom `EventTransformer` (misal: `sequential()`). Jika operasi sebelumnya masih pending, event diparkir di buffer antrean memori.
3. **Execution Guard**: FSM memvalidasi apakah state aktif saat ini mengizinkan aksi tersebut (misal: hanya boleh submit jika state adalah `OrderDraft`, tolak jika `OrderSubmitting`).
4. **Side-Effect Invocation**: BLoC mendelegasikan pemrosesan I/O ke Domain Use Case/Repository.
5. **State Materialization**: Use Case mengembalikan `Either<Failure, Success>`.
6. **Emission**: BLoC memanggil `emit(OrderState.success())`.
7. **Observer Interception**: `EnterpriseBlocObserver` mencegat tuple `(CurrentState, Event, NextState)` untuk telemetri Sentry/Datadog.
8. **Reconciliation**: Flutter framework mengevaluasi kembali subtree UI hanya pada widget yang terbungkus `BlocBuilder` dengan `buildWhen` spesifik.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Pabrik Perakitan Otomotif Otomatis
Bayangkan sebuah lini perakitan mobil:
* **Event**: Perintah kerja perakitan sasis baru yang masuk dari komputer pusat.
* **EventTransformer (Sequential)**: Robot pemasang pintu tidak boleh mulai sebelum robot sasis selesai mengelas platform dasar. Perintah kerja diantrekan secara ketat satu per satu.
* **State (Sealed Class)**: Kondisi fisik mobil: `ChassisMounted` -> `EngineFitted` -> `Painted` -> `QualityChecked`. Anda tidak dapat melompat dari `ChassisMounted` langsung ke `Painted` tanpa melalui `EngineFitted`.
* **BlocObserver**: Inspektur mutu independen yang berdiri di samping konveyor, mencatat timestamp setiap kali status mobil berganti, mendeteksi jika ada anomali atau proses yang macet.

#### Diagram Interaksi Concurrency & FSM
```
UI Interaction
      |
      | (1) bloc.add(SubmitPayment)
      v
+-------------------------------------------------------------+
| BLoC Concurrency Layer                                      |
| Transformer: droppable()                                    |
| [Active Execution: Task A]                                  |
|   |                                                         |
|   +---> [SubmitPayment (New)] ---> DROPPED (Anti Double-Tap)|
+-------------------------------------------------------------+
      |
      | (2) Processes Task A
      v
+-------------------------------------------------------------+
| FSM Validation (Current State: CheckoutIdle)                |
| Valid Transition: CheckoutIdle + SubmitPayment -> Submitting|
+-------------------------------------------------------------+
      |
      | (3) emit(CheckoutSubmitting)
      v
+-------------------------------------------------------------+
| Async Domain Operation (PaymentGateway.charge())            |
| Status: Awaiting I/O Response...                            |
+-------------------------------------------------------------+
      |
      | (4) Resolves: Success
      v
+-------------------------------------------------------------+
| FSM Validation (Current State: CheckoutSubmitting)          |
| Valid Transition: Submitting + Success -> CheckoutSuccess   |
| emit(CheckoutSuccess)                                       |
+-------------------------------------------------------------+
      |
      +============================+
      |                            |
      v                            v
[BlocObserver Telemetry]    [UI Renders Receipt]
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Search Typeahead dengan Concurrency `restartable()`
Penerapan transformer untuk membatalkan request HTTP pencarian lama saat karakter baru diketik.

```dart
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:bloc_concurrency/bloc_concurrency.dart';

// Events
sealed class SearchEvent {
  const SearchEvent();
}

final class QueryChanged extends SearchEvent {
  final String query;
  const QueryChanged(this.query);
}

// States
sealed class SearchState {
  const SearchState();
}

final class SearchInitial extends SearchState {}
final class SearchLoading extends SearchState {}
final class SearchSuccess extends SearchState {
  final List<String> results;
  const SearchSuccess(this.results);
}

// BLoC
class SearchBloc extends Bloc<SearchEvent, SearchState> {
  SearchBloc() : super(SearchInitial()) {
    // restartable() memastikan request lama di-cancel otomatis jika ada QueryChanged baru
    on<QueryChanged>(
      _onQueryChanged,
      transformer: restartable(),
    );
  }

  Future<void> _onQueryChanged(
    QueryChanged event,
    Emitter<SearchState> emit,
  ) async {
    if (event.query.isEmpty) {
      emit(SearchInitial());
      return;
    }
    emit(SearchLoading());
    try {
      // Simulasi delay jaringan
      await Future.delayed(const Duration(milliseconds: 400));
      emit(SearchSuccess(['Apple', 'Banana', 'Avocado']
          .where((item) => item.toLowerCase().contains(event.query.toLowerCase()))
          .toList()));
    } catch (_) {
      // Tangani error deterministik
    }
  }
}
```

#### B. Practical Enterprise Example: Order Execution FSM Engine
Sistem pemesanan instan kelas perbankan yang menuntut validasi FSM, anti double-submit via `droppable()`, dan pembatasan transisi state.

```dart
// order_state.dart
import 'package:flutter/foundation.dart';

@immutable
sealed class OrderState {
  const OrderState();
}

final class OrderDraft extends OrderState {
  const OrderDraft();
}

final class OrderSubmitting extends OrderState {
  final DateTime startedAt;
  const OrderSubmitting(this.startedAt);
}

final class OrderSuccess extends OrderState {
  final String transactionId;
  const OrderSuccess(this.transactionId);
}

final class OrderFailure extends OrderState {
  final String errorMessage;
  final bool isRetryable;
  const OrderFailure(this.errorMessage, {this.isRetryable = false});
}

// order_event.dart
@immutable
sealed class OrderEvent {
  const OrderEvent();
}

final class SubmitOrderEvent extends OrderEvent {
  final double amount;
  final String destinationAccountId;

  const SubmitOrderEvent({
    required this.amount,
    required this.destinationAccountId,
  });
}

final class ResetOrderEvent extends OrderEvent {
  const ResetOrderEvent();
}

// order_bloc.dart
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:bloc_concurrency/bloc_concurrency.dart';

abstract interface class IOrderRepository {
  Future<String> executeOrder(double amount, String destinationAccountId);
}

class OrderBloc extends Bloc<OrderEvent, OrderState> {
  final IOrderRepository _repository;

  OrderBloc(this._repository) : super(const OrderDraft()) {
    // Gunakan droppable() agar spam clicking tombol submit diabaikan total
    on<SubmitOrderEvent>(
      _onSubmitOrder,
      transformer: droppable(),
    );

    // sequential() memastikan proses reset menunggu operasi aktif selesai
    on<ResetOrderEvent>(
      _onResetOrder,
      transformer: sequential(),
    );
  }

  Future<void> _onSubmitOrder(
    SubmitOrderEvent event,
    Emitter<OrderState> emit,
  ) async {
    // Strict FSM Enforcement: Order hanya boleh di-submit dari state OrderDraft atau OrderFailure
    final currentState = state;
    if (currentState is! OrderDraft && currentState is! OrderFailure) {
      // Transisi ilegal diabaikan atau dilempar ke layer observabilitas
      return;
    }

    emit(OrderSubmitting(DateTime.now()));

    try {
      final txId = await _repository.executeOrder(
        event.amount,
        event.destinationAccountId,
      );
      emit(OrderSuccess(txId));
    } catch (error) {
      emit(OrderFailure(
        error.toString(),
        isRetryable: true,
      ));
    }
  }

  void _onResetOrder(
    ResetOrderEvent event,
    Emitter<OrderState> emit,
  ) {
    if (state is OrderSubmitting) {
      // FSM Guard: Melarang reset data ketika transaksi tengah berjalan di payment gateway
      return;
    }
    emit(const OrderDraft());
  }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks: High-Frequency Digital Banking Point-of-Sale (POS)
* **Klien**: Jaringan retail multinasional dengan 10.000+ terminal kasir berbasis Flutter.
* **Permasalahan**: Kasir sering menekan tombol "Bayar" berkali-kali saat koneksi jaringan drop (*double debit issue*). Selain itu, perubahan stok barang dari terminal lain via WebSocket menyebabkan UI transaksi kasir lokal sering me-refresh secara agresif dan merusak input yang sedang berlangsung.
* **Arsitektur Solusi**:
  1. **Concurrency Control**: Menerapkan custom event transformer `exhaustMap` (`droppable`) pada blok `PaymentBloc` yang dikombinasikan dengan idempotency token unik (UUID v4) per sesi checkout.
  2. **Cross-Bloc Decoupling**: Menghilangkan dependensi langsung antara `InventoryBloc` dan `CheckoutBloc`. Dibuat sebuah `TransactionSynchronizationRepository` yang bertindak sebagai mediator stream lokal (menggunakan SQLite/Isar sebagai local store).
  3. **Hydrated Offline Resilience**: Terminal POS harus tetap bisa memproses antrean transaksi dalam mode offline tanpa kehilangan status transaksi lokal jika aplikasi tiba-tiba ditutup paksa (*force close*).

```
+---------------------------------------------------------------------------------+
|                               Enterprise Topology                               |
|                                                                                 |
|  [ Barcode Scanner ]     [ WebSocket Engine ]          [ Kasir UI Screen ]      |
|           |                       |                             ^               |
|           v                       v                             |               |
|   +---------------+      +------------------+         +--------------------+    |
|   | InventoryBloc |      | NotificationBloc |         |    CheckoutBloc    |    |
|   +---------------+      +------------------+         +--------------------+    |
|           \                       /                             ^               |
|            v                     v                             /                |
|      +-----------------------------------------+              /                 |
|      |    Local Domain Sync Repository         |-------------+                  |
|      |  (Reactive SQLite / Rx State Stream)    | (Clean Decoupled Subscription) |
|      +-----------------------------------------+                                |
|                           ^                                                     |
|                           | Bi-directional Sync Engine                          |
|                           v                                                     |
|             [ Cloud Gateway / Core Banking REST ]                               |
+---------------------------------------------------------------------------------+
```

Implementasi `EnterpriseBlocObserver` untuk mendeteksi latensi pemrosesan dan audit trail:

```dart
// enterprise_bloc_observer.dart
import 'dart:developer' as developer;
import 'package:flutter_bloc/flutter_bloc.dart';

class EnterpriseBlocObserver extends BlocObserver {
  @override
  void onEvent(Bloc bloc, Object? event) {
    super.onEvent(bloc, event);
    developer.log(
      'EVENT_DISPATCH: ${bloc.runtimeType} -> ${event.runtimeType}',
      name: 'BLOC_TELEMETRY',
    );
  }

  @override
  void onTransition(Bloc bloc, Transition transition) {
    super.onTransition(bloc, transition);
    developer.log(
      'TRANSITION: ${bloc.runtimeType} | '
      'From: ${transition.currentState.runtimeType} -> '
      'Event: ${transition.event.runtimeType} -> '
      'To: ${transition.nextState.runtimeType}',
      name: 'BLOC_TRANSITION',
    );
  }

  @override
  void onError(BlocBase bloc, Object error, StackTrace stackTrace) {
    developer.log(
      'FATAL_UNHANDLED_EXCEPTION: ${bloc.runtimeType}',
      error: error,
      stackTrace: stackTrace,
      name: 'BLOC_ERROR',
    );
    // Forward ke crash reporting pipeline: Sentry.captureException(...)
    super.onError(bloc, error, stackTrace);
  }
}
```

---

### 9. Trade-offs

| Pendekatan / Pola | Keuntungan | Biaya / Trade-off |
| :--- | :--- | :--- |
| **`bloc_concurrency (sequential)`** | Eksekusi aman 100%, terhindar dari state race conditions, integritas data FIFO terjamin. | Latensi akumulatif. Jika satu transaksi lambat, antrean berikutnya mengalami blocking (*head-of-line blocking*). |
| **`bloc_concurrency (droppable)`** | Mencegah duplicate submissions, meminimalkan load server, hemat konsumsi resource memori. | Event hilang secara sengaja (*silent drop*). UI harus memberikan feedback visual (disabled state) yang presisi agar user tidak bingung. |
| **Domain Repository Mediator** | BLoC benar-benar decoupled, arsitektur modular, unit testing sangat mudah (hanya butuh mock repository). | Menambah lapisan abstraksi (boilerplate tinggi), butuh stream management ekstra di domain/data layer. |
| **State Hydration (`HydratedBloc`)**| Restorasi state otomatis pasca app kill/restart, native persistence. | Disk I/O cost saat penulisan serialisasi data kompleks. Membutuhkan skema migrasi jika data struktur berubah di versi baru. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Mutasi Objek Langsung di Dalam State (Object Identity Bug)
* **Penyebab**: Memodifikasi isi property `List` atau `Map` internal objek state yang sama tanpa membuat referensi objek baru, lalu memanggil `emit(SameStateObject)`.
* **Dampak**: BLoC menggunakan operator perbandingan identitas `identical()` atau `Equatable`. UI tidak pernah re-render karena referensi memori tidak berubah (`oldState == newState`).
* **Solusi**: Terapkan immutability absolut via `List.unmodifiable` atau factory constructor `copyWith` yang selalu mengalokasikan instance baru.

```dart
// SALAH (Anti-pattern)
state.items.add(newItem);
emit(CartLoaded(state.items)); // Equatable menganggap CartLoaded lama == baru

// BENAR (Production-grade)
emit(CartLoaded(List<Item>.unmodifiable([...state.items, newItem])));
```

#### 2. Emitting Setelah BLoC Closed (`Bad state: Cannot emit new states after calling close`)
* **Penyebab**: Asynchronous task (seperti HTTP call berdurasi panjang) baru mengembalikan hasil saat widget penampung BLoC sudah di-*dispose* dari widget tree.
* **Solusi**: Manfaatkan flag internal BLoC `isClosed` sebelum memanggil `emit()`.

```dart
final result = await _api.fetchData();
if (isClosed) return; // Guard clause krusial
emit(DataLoaded(result));
```

#### 3. Bocornya BuildContext Melewati Async Gaps pada BlocListener
* **Penyebab**: Memanggil `Navigator.of(context)` atau `ScaffoldMessenger.of(context)` di dalam async callback setelah jeda `await` yang panjang tanpa verifikasi integritas mount tree.
* **Solusi**: Gunakan properti `context.mounted` sebelum mengeksekusi operasi rendering berbasis context pasca jeda asinkron.

---

### 11. Best Practices (Production Checklist)

- [ ] **Exhaustive State Pattern Matching**: Menggunakan Dart 3 `switch (state)` tanpa blok `default` liar, memaksa penanganan seluruh subclass sealed state di UI.
- [ ] **Explicit Event Transformers**: Setiap implementasi `on<Event>` wajib mengevaluasi opsi transformer (`droppable`, `restartable`, `sequential`, atau default `concurrent`).
- [ ] **Granular UI Subscriptions**: Gunakan `buildWhen` dan `listenWhen` di tingkat widget sekecil mungkin (*leaf node*), jangan me-rebuild seluruh layar/Scaffold atas mutasi field minor.
- [ ] **Domain Error Encapsulation**: State kegagalan (`ErrorState`) wajib membawa objek `Failure` domain terstruktur (bukan raw `Exception` atau `String`), memisahkan message user-friendly dari stack trace debugging.
- [ ] **Zero BLoC-to-BLoC Construction**: Melarang instansiasi BLoC yang meminta BLoC lain di parameter konstruktornya. Gunakan layer data reaktif.
- [ ] **Memory Hygiene**: Selalu batalkan manual `StreamSubscription` di method `Future<void> close()` override pada BLoC yang mengamati domain service langsung.

---

### 12. Hands-on Practice

Buat dan atur workspace praktikum mandiri dengan langkah-langkah berikut:

#### Langkah 1: Persiapan Struktur Direktori
Jalankan perintah berikut di terminal:
```bash
mkdir -p hands-on/m02/lib/blocs
mkdir -p hands-on/m02/lib/models
mkdir -p hands-on/m02/lib/repositories
cd hands-on/m02
```

#### Langkah 2: Setup `pubspec.yaml`
Inisialisasi project dan pastikan dependensi berikut terpasang:
```yaml
name: advanced_state_mgmt
description: Enterprise BLoC Concurrency and FSM Demo
publish_to: 'none'
version: 1.0.0+1

environment:
  sdk: '>=3.0.0 <4.0.0'

dependencies:
  flutter:
    sdk: flutter
  flutter_bloc: ^8.1.3
  bloc_concurrency: ^0.2.2
  equatable: ^2.0.5

dev_dependencies:
  flutter_test:
    sdk: flutter
  bloc_test: ^9.1.5
```

#### Langkah 3: Eksekusi Kode Sumber Lengkap
Tuliskan implementasi state machine transaksional berikut pada `hands-on/m02/lib/main.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:bloc_concurrency/bloc_concurrency.dart';

// --- DOMAIN CONTRACT & REPOSITORY ---
abstract interface class ITransferRepository {
  Future<void> processTransfer(double amount);
}

class FakeBankRepository implements ITransferRepository {
  @override
  Future<void> processTransfer(double amount) async {
    // Simulasi latensi pemrosesan gateway core-banking
    await Future.delayed(const Duration(seconds: 2));
    if (amount > 1000) {
      throw Exception('Limit transfer harian terlampaui.');
    }
  }
}

// --- FSM STATES (Dart 3 Sealed Hierarchy) ---
@immutable
sealed class TransferState {
  const TransferState();
}

final class TransferInitial extends TransferState {
  const TransferInitial();
}

final class TransferInProgress extends TransferState {
  final double amount;
  const TransferInProgress(this.amount);
}

final class TransferSuccess extends TransferState {
  final String referenceNumber;
  const TransferSuccess(this.referenceNumber);
}

final class TransferFailed extends TransferState {
  final String error;
  const TransferFailed(this.error);
}

// --- EVENTS ---
@immutable
sealed class TransferEvent {
  const TransferEvent();
}

final class ExecuteTransfer extends TransferEvent {
  final double amount;
  const ExecuteTransfer(this.amount);
}

final class ResetTransfer extends TransferEvent {
  const ResetTransfer();
}

// --- BLOC IMPLEMENTATION ---
class TransferBloc extends Bloc<TransferEvent, TransferState> {
  final ITransferRepository _repository;

  TransferBloc(this._repository) : super(const TransferInitial()) {
    // droppable() menjamin tidak ada double submission ketika sedang diproses
    on<ExecuteTransfer>(
      _onExecuteTransfer,
      transformer: droppable(),
    );

    on<ResetTransfer>(
      (event, emit) => emit(const TransferInitial()),
    );
  }

  Future<void> _onExecuteTransfer(
    ExecuteTransfer event,
    Emitter<TransferState> emit,
  ) async {
    // FSM Guard: Hanya izinkan transfer jika berstatus TransferInitial atau TransferFailed
    if (state is! TransferInitial && state is! TransferFailed) return;

    emit(TransferInProgress(event.amount));

    try {
      await _repository.processTransfer(event.amount);
      if (isClosed) return;
      emit(TransferSuccess('TXN-${DateTime.now().millisecondsSinceEpoch}'));
    } catch (e) {
      if (isClosed) return;
      emit(TransferFailed(e.toString().replaceAll('Exception: ', '')));
    }
  }
}

// --- UI PRESENTATION LAYER ---
void main() {
  runApp(
    RepositoryProvider<ITransferRepository>(
      create: (context) => FakeBankRepository(),
      child: const MaterialApp(
        home: TransferScreen(),
      ),
    ),
  );
}

class TransferScreen extends StatelessWidget {
  const TransferScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider<TransferBloc>(
      create: (context) => TransferBloc(context.read<ITransferRepository>()),
      child: Scaffold(
        appBar: AppBar(title: const Text('Enterprise Transfer Engine')),
        body: const Padding(
          padding: EdgeInsets.all(24.0),
          child: TransferBody(),
        ),
      ),
    );
  }
}

class TransferBody extends StatefulWidget {
  const TransferBody({super.key});

  @override
  State<TransferBody> createState() => _TransferBodyState();
}

class _TransferBodyState extends State<TransferBody> {
  final _amountController = TextEditingController();

  @override
  void dispose() {
    _amountController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return BlocConsumer<TransferBloc, TransferState>(
      listenWhen: (previous, current) => current is TransferSuccess || current is TransferFailed,
      listener: (context, state) {
        if (state is TransferSuccess) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Berhasil! Ref: ${state.referenceNumber}'), backgroundColor: Colors.green),
          );
        } else if (state is TransferFailed) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Gagal: ${state.error}'), backgroundColor: Colors.red),
          );
        }
      },
      builder: (context, state) {
        return Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextField(
              controller: _amountController,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(
                labelText: 'Nominal Transfer (IDR)',
                border: OutlineInputBorder(),
              ),
              enabled: state is! TransferInProgress,
            ),
            const SizedBox(height: 20),
            switch (state) {
              TransferInitial() => ElevatedButton(
                  onPressed: () {
                    final amount = double.tryParse(_amountController.text) ?? 0.0;
                    context.read<TransferBloc>().add(ExecuteTransfer(amount));
                  },
                  child: const Text('Kirim Dana Sekarang'),
                ),
              TransferInProgress(:final amount) => Column(
                  children: [
                    const CircularProgressIndicator(),
                    const SizedBox(height: 8),
                    Text('Memproses transfer IDR $amount... Anti-Double-Tap aktif.'),
                  ],
                ),
              TransferSuccess() => OutlinedButton(
                  onPressed: () {
                    _amountController.clear();
                    context.read<TransferBloc>().add(const ResetTransfer());
                  },
                  child: const Text('Mulai Transaksi Baru'),
                ),
              TransferFailed() => ElevatedButton(
                  style: ElevatedButton.styleFrom(backgroundColor: Colors.orange),
                  onPressed: () {
                    final amount = double.tryParse(_amountController.text) ?? 0.0;
                    context.read<TransferBloc>().add(ExecuteTransfer(amount));
                  },
                  child: const Text('Coba Lagi'),
                ),
            },
          ],
        );
      },
    );
  }
}
```

---

### 13. Exercise

#### Level Easy
Ubah implementasi `SearchBloc` pada section 7A. Tambahkan custom debounce operator murni menggunakan native Dart Stream transformer sebelum event diarahkan ke `restartable()`, agar event pencarian ditahan selama minimal 300 ms sebelum mengeksekusi request.

#### Level Medium
Buat sebuah `AuthenticationBloc` dan `UserProfileBloc`. Terapkan pola *Domain Repository Mediator* menggunakan RxDart `BehaviorSubject` di dalam `AuthSessionRepository`. Pastikan saat `AuthenticationBloc` logout, `UserProfileBloc` secara otomatis mereset profile cache tanpa ada dependency reference langsung antar kedua BLoC tersebut.

#### Level Hard
Rancang FSM untuk sistem download berkas berukuran besar (Multi-segment Downloader) dengan status: `Idle`, `Connecting`, `Downloading(progress, bytesPerSec)`, `Paused(cachedBytes)`, `Completed(fileUri)`, dan `Corrupted(error)`. Terapkan custom EventTransformer yang mengimplementasikan `throttleTime` khusus pada event `UpdateDownloadProgress` agar tidak membanjiri Flutter Engine dengan re-render per frame (maksimum emisi state UI 60Hz / 16ms sekali).

---

### 14. Challenge

#### Skenario Kasus Kompleks: High-Frequency Stock Trading Desk
Rancang arsitektur state management untuk aplikasi bursa efek enterprise dengan beban streaming:
1. Terminal menerima fluktuasi harga 50 instrumen saham secara simultan melalui connection pooling WebSocket (mencapai ~500 update/detik).
2. Terdapat formulir **"One-Click Market Execution"** di mana pengguna dapat menekan tombol beli instan kapan saja. Order ini harus memiliki prioritas pemrosesan tertinggi, bebas dari latensi rendering tick bursa, dan dijamin *idempotent* serta *strictly sequential*.
3. **Syarat Teknis**:
   * Rancang diagram topologi interaksi BLoC dan isolasi thread-nya.
   * Definisikan strategi pemisahan antara tick streaming data UI (Ephemerality vs Persistence) dan Order Execution pipeline.
   * Uraikan bagaimana Anda mengombinasikan `concurrent`, `sequential`, dan isolasi `Isolate` di Dart agar antarmuka pengguna tetap berjalan mulus pada 120 FPS tanpa lag micro-stuttering (*frame drops*).

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic Concept (5 Pertanyaan)
1. **Mengapa transformer `droppable()` sangat krusial digunakan pada implementasi authentication/login submission?**
   * *Jawaban*: Untuk mencegah eksploitasi multi-submit akibat aksi penekanan tombol berkali-kali secara simultan oleh user, yang dapat memicu pembuatan token duplikat atau benturan sesi di backend.
2. **Apa yang terjadi secara default jika kita mendaftarkan handler event `on<MyEvent>(_handler)` tanpa mendefinisikan transformer secara eksplisit?**
   * *Jawaban*: BLoC akan menggunakan transformer `concurrent()`, di mana setiap event yang masuk akan diproses secara paralel tanpa antrean dan urutan penyelesaian emisi state-nya tidak terjamin.
3. **Mengapa Dart 3 `sealed class` lebih superior dibandingkan class turunan biasa (`abstract class`) untuk merepresentasikan State pada BLoC?**
   * *Jawaban*: Karena `sealed class` menjamin keamanan *exhaustiveness checking* pada saat kompilasi. Jika ada subtype state yang tidak ditangani dalam switch statement, compiler akan menghasilkan compile error.
4. **Apa fungsi utama dari method `isClosed` yang disediakan oleh class BLoC?**
   * *Jawaban*: Berfungsi sebagai guard clause untuk memeriksa apakah controller BLoC telah di-dispose sebelum memanggil `emit()`, menghindari runtime exception `Bad state: Cannot emit new states after calling close`.
5. **Mengapa memanggil method `bloc.close()` secara manual di dalam widget tree dianggap sebagai dangerous anti-pattern jika menggunakan `BlocProvider`?**
   * *Jawaban*: Karena `BlocProvider` secara otomatis mengelola siklus hidup BLoC. Menutup BLoC secara manual akan merusak manajemen resource `BlocProvider` dan memicu crash jika widget anak mencoba mengakses instance yang sudah disposed.

#### Bagian 2: Intermediate Concept (5 Pertanyaan)
1. **Bagaimana cara kerja transformer `restartable()` ketika event baru masuk saat operasi I/O asinkron event sebelumnya sedang berjalan?**
   * *Jawaban*: `restartable()` mendengarkan aliran event sebagai `switchMap`. Begitu event baru tiba, subscription/pemrosesan event sebelumnya yang belum selesai akan langsung dibatalkan (diberikan sinyal cancel) dan dialihkan secara eksklusif ke event terbaru.
2. **Apa kelemahan mendasar jika kita menyuntikkan (inject) instance `BlocA` ke dalam konstruktor `BlocB`?**
   * *Jawaban*: Menciptakan kopling erat (tight coupling) antar BLoC, mempersulit penulisan unit test secara terisolasi, meningkatkan risiko *circular dependency*, dan melanggar prinsip pemisahan tanggung jawab (Single Responsibility Principle).
3. **Jelaskan perbedaan mendasar antara `BlocListener` dan `BlocBuilder` dalam kaitannya dengan siklus hidup rendering Flutter framework.**
   * *Jawaban*: `BlocBuilder` murni digunakan untuk me-return UI Widget baru berdasarkan perubahan state (berjalan di phase build), sedangkan `BlocListener` khusus digunakan untuk mengeksekusi side-effects satu kali (seperti navigasi, SnackBar, dialog) tanpa me-render ulang widget tree.
4. **Apa risiko menggunakan transformer `sequential()` pada aplikasi yang memproses streaming event berkecepatan tinggi?**
   * *Jawaban*: Dapat menyebabkan akumulasi antrean memori tak terbatas (*Head-of-Line Blocking* & *Out of Memory*), karena setiap event dipaksa menunggu hingga handler sebelumnya selesai secara tuntas.
5. **Kapan sebaiknya kita mengabstraksikan state menggunakan tuple data (misal: `State(data, isLoading, error)`) versus inheritance-based State (`StateLoading`, `StateSuccess`, `StateFailure`)?**
   * *Jawaban*: Inheritance-based State cocok untuk model Finite State Machine (FSM) yang eksklusif (misal: alur checkout atau login). Tuple/Copyable State cocok untuk layar dashboard kompleks yang memiliki banyak kontrol independen di mana data lama harus tetap ditampilkan di layar sembari operasi mutasi background berjalan.

#### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)

1. **Skenario Kasus 1**:
   Sebuah aplikasi e-wallet sering mengalami komplain pengguna: saldo berkurang dua kali lipat saat melakukan transfer pada area bersinyal buruk (Edge/3G). Setelah diperiksa, pengguna menekan tombol "Kirim" berulang-ulang karena UI tidak segera merespons.
   *Pertanyaan*: Solusi deterministik apa yang harus diterapkan pada layer BLoC dan Repository?
   * *Jawaban*:
     1. Pada presentation layer BLoC, ganti transformer event transfer menjadi `droppable()` agar event tambahan yang terkirim saat proses HTTP berjalan diabaikan secara absolut.
     2. Pada domain/data layer, terapkan *Idempotency-Key* berbasis UUID yang digenerate di level state machine saat masuk status `TransferInitial`. Kunci ini dikirim melalui header HTTP ke backend sehingga server dapat menolak transaksi duplikat di sisi gateway API.

2. **Skenario Kasus 2**:
   Sebuah aplikasi live tracking driver taksi online menerima koordinat lintang-bujur setiap 50 milidetik via MQTT stream. UI peta Flutter mengalami lag parah (*jank*) hingga frame drop ke 15 FPS.
   *Pertanyaan*: Bagaimana Anda mengoptimasi alur state management pada BLoC agar peta tetap terupdate secara halus?
   * *Jawaban*:
     1. Terapkan custom event transformer dengan operator *throttling* atau *sampling* (misal: emit data maksimum per 16ms atau 32ms) untuk meredam frekuensi event agar tidak melebihi kecepatan refresh rate layar.
     2. Hindari memproses deserialisasi format payload koordinat di thread utama (UI Isolate); gunakan background `Isolate` (via `compute`) untuk parsing data koordinat mentah sebelum dimasukkan ke dalam event BLoC.
     3. Gunakan `buildWhen` pada widget map controller untuk memastikan hanya elemen layer koordinat yang dirender ulang, bukan keseluruhan canvas peta.

3. **Skenario Kasus 3**:
   Aplikasi Core Banking memiliki modul sesi otentikasi global (`AuthBloc`) dan modul pinjaman mikro (`LoanBloc`). Ketika masa aktif token otentikasi kedaluwarsa, `AuthBloc` mendeteksi sesi mati dan mengubah state menjadi `Unauthenticated`. Namun, layar pengajuan pinjaman (`LoanBloc`) masih menampilkan data limit pinjaman nasabah yang bersifat konfidensial jika kasir berpindah layar sebelum app me-refresh.
   *Pertanyaan*: Bagaimana mengorkestrasi pembersihan state lintas modul tersebut tanpa melanggar prinsip decoupling?
   * *Jawaban*:
     1. Buat abstraction `SessionTokenRepository` yang mengekspos stream reaktif `sessionStateStream`.
     2. `AuthBloc` bertindak sebagai entitas yang menulis ke repo tersebut ketika sesi berakhir.
     3. `LoanBloc` mendengarkan (`listen`) perubahan stream pada `SessionTokenRepository` di level domain/data repository. Begitu terdeteksi sesi null/unauthenticated, `LoanBloc` secara otomatis mengirim internal event `ClearLoanSensitiveData` ke dirinya sendiri untuk membersihkan memori internal secara mandiri dan deterministik.

---

### 16. Summary
1. **Concurrency Control**: Pemilihan transformer yang tepat (`sequential`, `droppable`, `restartable`, `concurrent`) pada `bloc_concurrency` bukan sekadar optimasi, melainkan garda pertahanan utama dalam menjaga integritas data transaksional enterprise.
2. **Determinisme Mutlak dengan Dart 3**: Pemanfaatan `sealed class` dan exhaustive pattern matching memindahkan risiko runtime bug transisi state ke fase kompilasi (*compile-time safety*).
3. **Loose Coupling**: BLoC tingkat enterprise tidak boleh saling mereferensikan satu sama lain secara langsung. Komunikasi antar state harus dimediasi secara reaktif melalui Domain Repositories dan Single Source of Truth (SSOT).
4. **Resilience & Hygiene**: Arsitektur yang tangguh selalu memvalidasi siklus hidup instansiasi (`isClosed`, auto-cancellation tokens) dan mengaudit mutasi transisi melalui `BlocObserver` global untuk visibilitas produksi secara menyeluruh.