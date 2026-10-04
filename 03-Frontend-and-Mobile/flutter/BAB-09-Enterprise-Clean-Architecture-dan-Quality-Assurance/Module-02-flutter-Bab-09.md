# Bab 09: Enterprise Clean Architecture & Quality Assurance
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, software engineer enterprise diharapkan mampu:
1. **Mendesain Boundary Arsitektur Skala Besar**: Mengisolasi *Domain Layer* dari dependensi eksternal (UI, Database, Network) menggunakan *Dependency Inversion Principle* (DIP) dan pola *Domain-Driven Design* (DDD) taktis.
2. **Mengimplementasikan Robust Fault Tolerance**: Merancang penanganan galat deterministik berbasis tipe data fungsional (*Railway-Oriented Programming* menggunakan `fpdart` / `Either<Failure, Success>`) tanpa melempar *unhandled runtime exception*.
3. **Membangun Synchronization Engine Offline-First**: Mengembangkan strategi sinkronisasi data dua arah dengan resolusi konflik idempotensi menggunakan Dio, Drift/Isar, dan BLoC.
4. **Menerapkan Advanced Concurrency Control**: Mengatur eksekusi event asinkron pada Presentation Layer menggunakan custom *Event Transformers* (`droppable`, `restartable`, `concurrent`).
5. **Mengotomasi Quality Assurance Terintegrasi**: Mengonstruksi piramida pengujian otomatis mencakup unit test murni domain, repository contract testing, state management bloc test, dan UI golden/integration test dengan target code coverage > 85%.

---

### 2. Prerequisite

* **Dart SDK**: Pemahaman mendalam mengenai Dart 3 (Sealed Classes, Records, Pattern Matching) dan Asynchronous Programming (`Stream`, `Future`, Microtasks).
* **State Management**: Pemahaman operasional terhadap ekosistem `flutter_bloc` (`Bloc`, `Cubit`, `BlocObserver`).
* **Networking & Storage**: Pemahaman mendalam tentang HTTP/2, interceptor Dio, JWT lifecycle, serta relational/NoSQL local storage (Drift/SQLite/Isar).
* **Dependency Injection**: Penguasaan Service Locator (`get_it`) dan static code generation untuk dependency injection (`injectable`).
* **Design Principles**: Penguasaan SOLID Principles, Clean Architecture (Uncle Bob), dan Hexagonal Architecture (Ports and Adapters).

---

### 3. Concept & Internal Architecture

Clean Architecture pada Flutter enterprise dirancang untuk meminimalkan *coupling* dan memaksimalkan *testability* serta *maintainability*. Pemisahan layer diatur secara hierarkis menggunakan aturan ketergantungan (*Dependency Rule*): **Dependensi kode sumber hanya boleh mengarah ke dalam, menuju domain layer.**

```
+-------------------------------------------------------------+
| Presentation Layer (Widgets, Pages, BLoC/Cubit, UI Models)   |
|   |                                                         |
|   v                                                         |
| Domain Layer (UseCases, Entities, Value Objects, Failures)  |
|   ^                                                         |
|   | (Implements Interfaces / Inversion of Control)          |
| Data Layer (Repositories, DTOs, Local/Remote DataSources)   |
+-------------------------------------------------------------+
```

#### Komponen Internal Arsitektur:

1. **Domain Layer (The Core - Pure Dart)**
   * **Entities**: Objek bisnis murni yang tidak bergantung pada JSON serialization framework, Flutter SDK, atau database driver.
   * **Use Cases (Interactors)**: Unit logika bisnis spesifik aplikasi yang mengorkestrasi aliran data ke dan dari entitas. Mengeksekusi satu tanggung jawab tunggal (*Single Responsibility Principle*).
   * **Repository Interfaces (Ports)**: Abstraksi kontrak data access. Domain mendefinisikan *apa* yang dibutuhkannya, bukan *bagaimana* data tersebut diambil.
   * **Failures**: Representasi kesalahan bisnis bertipe kuat (*strongly-typed sealed class/unions*).

2. **Data Layer (The Adapters)**
   * **DTOs (Data Transfer Objects / Models)**: Representasi serialisasi/deserialisasi payload jaringan atau skema basis data lokal. Menyediakan method `toDomain()` dan `fromDomain()`.
   * **Data Sources**:
     * *RemoteDataSource*: Berkomunikasi dengan REST/gRPC/GraphQL API via HTTP client.
     * *LocalDataSource*: Menangani caching, persistence (Drift, Hive, Isar), dan memory cache.
   * **Repository Implementations (Adapters)**: Mengimplementasikan interface repository dari Domain Layer. Mengatur strategi *caching* (misal: *Cache-First*, *Network-First*, *Stale-While-Revalidate*) dan pemetaan dari DTO/Database Record ke Domain Entity.

3. **Presentation Layer (The Delivery Mechanism)**
   * **BLoC (Business Logic Component)**: Mengonversi *UI Events* menjadi *UI States* melalui pemanggilan *UseCases*. BLoC hanya mengonsumsi dan menghasilkan objek domain, tidak pernah berurusan langsung dengan HTTP response code atau SQL schema.
   * **UI Components (Pages & Widgets)**: Komponen deklaratif yang sepenuhnya reaktif terhadap state BLoC.

#### Boundary Inversion & Error Handling Engine
Alih-alih menggunakan mekanisme runtime `try-catch` di UI yang rawan bocor (*exception leaking*), layer arsitektur mengadopsi model *Result* fungsional:

$$\text{Result}\langle L, R\rangle = \text{Left}(L) \mid \text{Right}(R)$$

Di mana:
* $L$ merepresentasikan `Failure` (Domain-specific error object).
* $R$ merepresentasikan nilai kembalian sukses (`Entity` / `Unit`).

---

### 4. Why & What

| Dimensi | Legacy/Monolithic Flutter (Spaghetti) | Enterprise Clean Architecture |
| :--- | :--- | :--- |
| **Coupling** | UI memanggil HTTP Client / Database secara langsung. Perubahan API merusak UI. | UI terisolasi dari Data Layer. API berubah, hanya DTO yang dimodifikasi. |
| **Testability** | Testing membutuhkan `flutter_test` harness bahkan untuk unit test bisnis logic karena dependensi `BuildContext`. | Domain layer adalah *Pure Dart*. Pengujian logika bisnis berjalan instan tanpa boot Flutter Engine. |
| **Separation of Concerns** | Logika bisnis bercampur di dalam `StatefulWidget.setState()` atau single Mega-Controller. | Setiap use case terisolasi, atomic, dan dapat diuji secara independen. |
| **Error Handling** | Menggunakan arbitrary `throw Exception()`. Sering terjadi *unhandled exceptions* yang menyebabkan *red screen of death*. | Komprehensif via `Either<Failure, T>`. Compiler memaksa penanganan semua varian kegagalan secara eksplisit. |
| **Maintainability** | Refactoring berisiko tinggi. Sulit membagi tugas pada tim yang terdiri dari puluhan engineer. | *Feature-driven architecture* memungkinkan skalabilitas tim paralel tanpa konflik merge branch. |

---

### 5. How (Workflow Detail)

Alur eksekusi saat pengguna melakukan aksi (misalnya, menekan tombol transfer dana):

1. **User Interaction**: Pengguna menekan tombol "Kirim" di `TransferPage`.
2. **Event Dispatching**: Widget mengirimkan event `TransferFundsSubmitted(payload)` ke `TransferBloc`.
3. **State Mutation**: `TransferBloc` meng-emit `TransferState.loading()`.
4. **UseCase Invocation**: `TransferBloc` mengeksekusi `ExecuteFundTransferUseCase(params)`.
5. **Repository Access**: UseCase memanggil `TransferRepository.transfer(params)`. Kontrak ini diinjeksi melalui *Dependency Injection* (`GetIt`).
6. **Data Orchestration**:
   * `TransferRepositoryImpl` memverifikasi token idempotensi lokal via `LocalDataSource`.
   * Memanggil `RemoteDataSource.executeTransfer(dto)`.
   * Menangkap kegagalan jaringan atau HTTP 4xx/5xx, memetakan ke subtipe `Failure` (misal: `InsufficientBalanceFailure`), dan mengembalikan `Left(Failure)`.
   * Jika sukses, menyimpan transaksi ke `LocalDataSource` (audit log) dan mengembalikan `Right(TransactionEntity)`.
7. **Result Propagation**: UseCase menerima `Either<Failure, TransactionEntity>` dan meneruskannya ke `TransferBloc`.
8. **State Emission**: `TransferBloc` memproses `Either` menggunakan metode `.fold()`:
   * **Left(failure)** $\rightarrow$ emit `TransferState.failure(failure.message)`
   * **Right(data)** $\rightarrow$ emit `TransferState.success(data)`
9. **UI Reaction**: `BlocConsumer` di `TransferPage` mendengarkan perubahan state:
   * Menutup loading overlay.
   * Merender navigasi sukses atau menampilkan dialog error kontekstual.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Restoran Mewah (Fine Dining)
* **Presentation Layer (Pelayan & Meja)**: Menerima pesanan dari pelanggan (Event), membawakan makanan yang sudah jadi (State), dan menampilkan ke meja makan. Pelayan tidak tahu cara memotong daging atau menanam sayuran.
* **Domain Layer (Head Chef & Resep Rahasia)**: Menentukan standar rasa, komposisi bahan, dan urutan memasak (Logika Bisnis / Use Cases). Resep ini tidak peduli apakah kompornya menggunakan gas LPG atau induksi listrik (Teknologi Framework).
* **Data Layer (Supplier & Gudang Bahan)**: Membeli bahan baku dari pasar basah (Remote API) atau mengambil stok di chiller pendingin (Local Cache / SQLite). Menyuplai bahan mentah tersebut sesuai standar yang diminta Head Chef.

#### Architectural Data Flow Diagram:
```
+---------------------------------------------------------------------------------------+
|                                    PRESENTATION LAYER                                 |
|  [ User Action ]                                                                      |
|         │                                                                             |
|         ▼                                                                             |
|    [ UI Widget ] ──( Dispatch Event )──► [ Bloc/Cubit ] ◄──( Listen State )── [ UI ]  |
+──────────────────────────────────────────────────┬────────────────────────────────────+
                                                   │ Invokes
                                                   ▼
+--------------------------------------------------┴------------------------------------+
|                                      DOMAIN LAYER                                     |
|                                [ UseCase.call(params) ]                               |
|                                          │                                            |
|                                          ▼                                            |
|                        [ Repository Interface (Contract) ]                            |
|                                          ▲                                            |
+──────────────────────────────────────────┼────────────────────────────────────────────+
                                           │ Implements (Dependency Inversion)
+──────────────────────────────────────────┴────────────────────────────────────────────+
|                                       DATA LAYER                                      |
|                               [ Repository Implementation ]                           |
|                                          │                                            |
|                    ┌─────────────────────┴─────────────────────┐                      |
|                    ▼                                           ▼                      |
|          [ Local DataSource ]                        [ Remote DataSource ]            |
|          (Drift / SQLite / Cache)                     (Dio HTTP/gRPC Client)          |
+---------------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Domain Layer: Failures, Entities, dan Contract Interface

```dart
// domain/core/error/failures.dart
import 'package:equatable/equatable.dart';

sealed class Failure extends Equatable {
  final String message;
  final int? statusCode;

  const Failure({required this.message, this.statusCode});

  @override
  List<Object?> get props => [message, statusCode];
}

class ServerFailure extends Failure {
  const ServerFailure({required super.message, super.statusCode});
}

class NetworkFailure extends Failure {
  const NetworkFailure({required super.message});
}

class CacheFailure extends Failure {
  const CacheFailure({required super.message});
}
```

```dart
// domain/entities/account_balance.dart
import 'package:equatable/equatable.dart';

class AccountBalance extends Equatable {
  final String accountId;
  final double amount;
  final String currency;

  const AccountBalance({
    required this.accountId,
    required this.amount,
    required this.currency,
  });

  @override
  List<Object?> get props => [accountId, amount, currency];
}
```

```dart
// domain/repositories/account_repository.dart
import 'package:fpdart/fpdart.dart';
import '../core/error/failures.dart';
import '../entities/account_balance.dart';

abstract interface class AccountRepository {
  Future<Either<Failure, AccountBalance>> getBalance(String accountId);
}
```

```dart
// domain/usecases/get_account_balance_usecase.dart
import 'package:fpdart/fpdart.dart';
import '../core/error/failures.dart';
import '../entities/account_balance.dart';
import '../repositories/account_repository.dart';

class GetAccountBalanceUseCase {
  final AccountRepository _repository;

  const GetAccountBalanceUseCase(this._repository);

  Future<Either<Failure, AccountBalance>> call(String accountId) async {
    if (accountId.trim().isEmpty) {
      return left(const ServerFailure(message: "Account ID tidak boleh kosong"));
    }
    return await _repository.getBalance(accountId);
  }
}
```

#### B. Data Layer: DTO, DataSources, dan Repository Implementation

```dart
// data/models/account_balance_dto.dart
import '../../domain/entities/account_balance.dart';

class AccountBalanceDTO {
  final String accountId;
  final double amount;
  final String currency;

  const AccountBalanceDTO({
    required this.accountId,
    required this.amount,
    required this.currency,
  });

  factory AccountBalanceDTO.fromJson(Map<String, dynamic> json) {
    return AccountBalanceDTO(
      accountId: json['account_id'] as String,
      amount: (json['balance_amount'] as num).toDouble(),
      currency: json['currency_code'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'account_id': accountId,
      'balance_amount': amount,
      'currency_code': currency,
    };
  }

  AccountBalance toDomain() {
    return AccountBalance(
      accountId: accountId,
      amount: amount,
      currency: currency,
    );
  }
}
```

```dart
// data/datasources/account_remote_datasource.dart
import 'package:dio/dio.dart';
import '../models/account_balance_dto.dart';

abstract interface class AccountRemoteDataSource {
  Future<AccountBalanceDTO> fetchBalanceFromApi(String accountId);
}

class AccountRemoteDataSourceImpl implements AccountRemoteDataSource {
  final Dio _dio;

  AccountRemoteDataSourceImpl(this._dio);

  @override
  Future<AccountBalanceDTO> fetchBalanceFromApi(String accountId) async {
    final response = await _dio.get('/v1/accounts/$accountId/balance');
    return AccountBalanceDTO.fromJson(response.data as Map<String, dynamic>);
  }
}
```

```dart
// data/repositories/account_repository_impl.dart
import 'package:dio/dio.dart';
import 'package:fpdart/fpdart.dart';
import '../../domain/core/error/failures.dart';
import '../../domain/entities/account_balance.dart';
import '../../domain/repositories/account_repository.dart';
import '../datasources/account_remote_datasource.dart';

class AccountRepositoryImpl implements AccountRepository {
  final AccountRemoteDataSource remoteDataSource;

  AccountRepositoryImpl({required this.remoteDataSource});

  @override
  Future<Either<Failure, AccountBalance>> getBalance(String accountId) async {
    try {
      final dto = await remoteDataSource.fetchBalanceFromApi(accountId);
      return right(dto.toDomain());
    } on DioException catch (dioErr) {
      if (dioErr.type == DioExceptionType.connectionTimeout ||
          dioErr.type == DioExceptionType.connectionError) {
        return left(const NetworkFailure(message: "Koneksi ke server terputus"));
      }
      return left(ServerFailure(
        message: dioErr.response?.statusMessage ?? "Kesalahan server internal",
        statusCode: dioErr.response?.statusCode,
      ));
    } catch (e) {
      return left(ServerFailure(message: e.toString()));
    }
  }
}
```

#### C. Presentation Layer: BLoC State Management

```dart
// presentation/bloc/account_balance_state.dart
import 'package:equatable/equatable.dart';
import '../../domain/entities/account_balance.dart';

sealed class AccountBalanceState extends Equatable {
  const AccountBalanceState();

  @override
  List<Object?> get props => [];
}

class AccountBalanceInitial extends AccountBalanceState {}

class AccountBalanceLoading extends AccountBalanceState {}

class AccountBalanceLoaded extends AccountBalanceState {
  final AccountBalance balance;

  const AccountBalanceLoaded(this.balance);

  @override
  List<Object?> get props => [balance];
}

class AccountBalanceError extends AccountBalanceState {
  final String message;

  const AccountBalanceError(this.message);

  @override
  List<Object?> get props => [message];
}
```

```dart
// presentation/bloc/account_balance_event.dart
import 'package:equatable/equatable.dart';

sealed class AccountBalanceEvent extends Equatable {
  const AccountBalanceEvent();

  @override
  List<Object?> get props => [];
}

class FetchAccountBalanceRequested extends AccountBalanceEvent {
  final String accountId;

  const FetchAccountBalanceRequested(this.accountId);

  @override
  List<Object?> get props => [accountId];
}
```

```dart
// presentation/bloc/account_balance_bloc.dart
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../domain/usecases/get_account_balance_usecase.dart';
import 'account_balance_event.dart';
import 'account_balance_state.dart';

class AccountBalanceBloc extends Bloc<AccountBalanceEvent, AccountBalanceState> {
  final GetAccountBalanceUseCase _getAccountBalance;

  AccountBalanceBloc({required GetAccountBalanceUseCase getAccountBalance})
      : _getAccountBalance = getAccountBalance,
        super(AccountBalanceInitial()) {
    on<FetchAccountBalanceRequested>((event, emit) async {
      emit(AccountBalanceLoading());

      final result = await _getAccountBalance(event.accountId);

      result.fold(
        (failure) => emit(AccountBalanceError(failure.message)),
        (data) => emit(AccountBalanceLoaded(data)),
      );
    });
  }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem:
Aplikasi FinTech SuperApp perbankan dengan modul mutasi rekening, pembayaran QRIS, dan transfer instan. Aplikasi harus mendukung kondisi konektivitas ekstrem (3G/daerah terpencil) dan menjamin data mutasi tetap dapat diakses secara luring (*offline-first*).

#### Solusi Arsitektur:
1. **Network Interceptor Layer**: Menangani *Silent Token Refresh* menggunakan *Thread Mutex/Queue* saat menerima respons HTTP `401 Unauthorized`.
2. **Synchronization Strategy**: Pola *Cache-Then-Network* menggunakan Stream di mana UI mengonsumsi data lokal terlebih dahulu, lalu di-*update* secara asinkron ketika respons remote diterima.
3. **Write Path Idempotency**: Setiap mutasi transfer diberi Client UUID v4 unik untuk mencegah *double deduction* di tingkat gateway backend.

#### Implementasi Production Token Refresh Interceptor (Dio):

```dart
import 'package:dio/dio.dart';

class AuthInterceptor extends QueuedInterceptor {
  final Dio dio;
  final Future<String?> Function() getAccessToken;
  final Future<String?> Function() getRefreshToken;
  final Future<void> Function(String newAccessToken, String newRefreshToken) saveTokens;

  AuthInterceptor({
    required this.dio,
    required this.getAccessToken,
    required this.getRefreshToken,
    required this.saveTokens,
  });

  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    final token = await getAccessToken();
    if (token != null) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    return handler.next(options);
  }

  @override
  Future<void> onError(DioException err, ErrorInterceptorHandler handler) async {
    if (err.response?.statusCode == 401) {
      final refreshToken = await getRefreshToken();
      if (refreshToken == null) {
        return handler.reject(err);
      }

      try {
        // Menggunakan instance dio terpisah agar tidak terjebak infinite loop interceptor
        final refreshDio = Dio(BaseOptions(baseUrl: err.requestOptions.baseUrl));
        final response = await refreshDio.post('/v1/auth/refresh', data: {
          'refresh_token': refreshToken,
        });

        final newAccessToken = response.data['access_token'] as String;
        final newRefreshToken = response.data['refresh_token'] as String;

        await saveTokens(newAccessToken, newRefreshToken);

        // Update authorization header dan lakukan retry request asli
        final options = err.requestOptions;
        options.headers['Authorization'] = 'Bearer $newAccessToken';

        final retryResponse = await dio.fetch(options);
        return handler.resolve(retryResponse);
      } catch (refreshErr) {
        // Refresh token hangus / invalid -> trigger force logout event
        return handler.reject(err);
      }
    }
    return handler.next(err);
  }
}
```

---

### 9. Trade-offs

| Pendekatan / Keputusan | Keuntungan | Biaya / Trade-off |
| :--- | :--- | :--- |
| **Pemisahan DTO vs Entity** | Domain entities bersih dari serialisasi framework. API backend dapat mengubah skema JSON tanpa merusak UI. | *Boilerplate code* meningkat drastis; butuh proses *mapping* eksplisit (`toDomain()` & `fromDomain()`). |
| **Functional Error Handling (`Either`)** | Kompilator memaksa penanganan kegagalan secara eksplisit; menghilangkan runtime crashing dari exception tak terduga. | Kurva belajar lebih tinggi untuk developer junior yang belum terbiasa dengan paradigma *Monadic / Functional Programming*. |
| **Repository with Cache Layer** | Latensi UI mendekati 0ms saat memuat data (*Offline first UX*); beban trafik backend berkurang. | Kompleksitas *Cache Invalidation*, risiko *Stale Data*, dan overhead penyimpanan memori/disk lokal perangkat. |
| **Micro-UseCases (1 Class = 1 Action)** | Ekstremitas modularitas; unit testing menjadi sangat sederhana dan presisi; SRP terjaga ketat. | Ledakan jumlah file class (*file bloat*); navigasi IDE membutuhkan tooling pencarian yang disiplin. |

---

### 10. Common Mistakes & Troubleshooting

#### Anti-Pattern 1: Bocornya Data Layer ke UI
* **Kesalahan**: Mengakses properti DTO atau model database Drift/Isar langsung di dalam Widget Flutter atau BLoC.
* **Akibat**: UI terkunci secara *tightly coupled* ke implementasi driver eksternal. Jika nama kolom database berubah, struktur UI rusak.
* **Solusi**: Selalu konversi DTO ke Domain Entity di boundary Repository Implementation sebelum dikembalikan ke Use Case.

#### Anti-Pattern 2: Dynamic Execution Exception Leakage
* **Kesalahan**: Melempar `throw CustomException()` dari dalam Repository dan mengharapkan UI menangkapnya dengan `try-catch`.
* **Akibat**: Jika satu layer lupa menangkap exception, aplikasi crash.
* **Solusi**: Bungkus pemanggilan *lower-level* di repository menggunakan blok `try-catch`, tangkap spesifik SDK exception (misal: `DioException`), petakan ke subtipe `Failure`, lalu kembalikan melalui `left(Failure)`.

#### Anti-Pattern 3: Circular Dependencies pada Layering
* **Kesalahan**: Domain Layer mengimpor file dari Data Layer atau Presentation Layer.
* **Diagnosa CLI**: Jalankan tool analisis arsitektural:
```bash
dart run dart_code_metrics:metrics analyze lib --fatal-style
```
* **Solusi**: Patuhi *Inversion of Control*. Jika Domain membutuhkan data, deklarasikan `abstract interface class` di dalam Domain, lalu implementasikan kelas tersebut di Data Layer.

---

### 11. Best Practices (Production Checklist)

- [ ] **Pure Domain**: Direktori `lib/features/*/domain` tidak boleh memiliki satupun impor `package:flutter/*`, `package:dio/*`, atau library database lokal.
- [ ] **Immutable Entities & Values**: Semua entity menggunakan modifier `@immutable` atau extend `Equatable` / `freezed`.
- [ ] **Strict Typing Failure**: Gunakan `sealed class` untuk representasi `Failure` guna memanfaatkan keunggulan *Exhaustive Pattern Matching* di Dart 3.
- [ ] **Mocktail/Mockito Safety**: Gunakan mock interfaces abstrak murni tanpa menyertakan concrete I/O classes pada unit test domain.
- [ ] **Stream Disposing**: Selalu tutup `StreamController` dan batalkan `StreamSubscription` pada lifecycle hook `close()` di dalam BLoC.
- [ ] **Idempotent Requests**: Request tipe `POST`/`PATCH` kritis harus menyertakan Header `X-Idempotency-Key: UUIDv4`.
- [ ] **Unified Dependency Injection**: Pendaftaran service locator diatur terpusat menggunakan annotasi `@InjectableInit` dan generator code-gen.

---

### 12. Hands-on Practice

Buat skenario arsitektur di workspace project Flutter Anda di bawah direktori `hands-on/m02/`.

#### Langkah 1: Setup Dependensi `pubspec.yaml`
```yaml
name: clean_architecture_production
description: Production Clean Architecture Module
version: 1.0.0+1
environment:
  sdk: '>=3.0.0 <4.0.0'

dependencies:
  flutter:
    sdk: flutter
  flutter_bloc: ^8.1.3
  equatable: ^2.0.5
  fpdart: ^1.1.0
  dio: ^5.4.0
  get_it: ^7.6.0

dev_dependencies:
  flutter_test:
    sdk: flutter
  mocktail: ^1.0.1
  bloc_test: ^9.1.5
```

#### Langkah 2: Setup Struktur Direktori
```bash
mkdir -p lib/core/error
mkdir -p lib/features/crypto_tracker/domain/entities
mkdir -p lib/features/crypto_tracker/domain/repositories
mkdir -p lib/features/crypto_tracker/domain/usecases
mkdir -p lib/features/crypto_tracker/data/models
mkdir -p lib/features/crypto_tracker/data/datasources
mkdir -p lib/features/crypto_tracker/data/repositories
mkdir -p lib/features/crypto_tracker/presentation/bloc
mkdir -p test/features/crypto_tracker/domain/usecases
mkdir -p test/features/crypto_tracker/presentation/bloc
```

#### Langkah 3: Implementasi Test-Driven Development (TDD) pada UseCase
Simpan file ini di: `test/features/crypto_tracker/domain/usecases/get_crypto_price_test.dart`

```dart
import 'package:clean_architecture_production/core/error/failures.dart';
import 'package:clean_architecture_production/features/crypto_tracker/domain/entities/crypto_asset.dart';
import 'package:clean_architecture_production/features/crypto_tracker/domain/repositories/crypto_repository.dart';
import 'package:clean_architecture_production/features/crypto_tracker/domain/usecases/get_crypto_price.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:mocktail/mocktail.dart';

class MockCryptoRepository extends Mock implements CryptoRepository {}

void main() {
  late GetCryptoPriceUseCase useCase;
  late MockCryptoRepository mockRepository;

  setUp(() {
    mockRepository = MockCryptoRepository();
    useCase = GetCryptoPriceUseCase(mockRepository);
  });

  const tSymbol = 'BTC';
  const tCryptoAsset = CryptoAsset(symbol: 'BTC', priceUsd: 50000.0);

  test('Harus mengembalikan CryptoAsset ketika repository berhasil mengambil data', () async {
    // Arrange
    when(() => mockRepository.getCryptoPrice(tSymbol))
        .thenAnswer((_) async => const Right(tCryptoAsset));

    // Act
    final result = await useCase(tSymbol);

    // Assert
    expect(result, const Right(tCryptoAsset));
    verify(() => mockRepository.getCryptoPrice(tSymbol)).called(1);
    verifyNoMoreInteractions(mockRepository);
  });

  test('Harus mengembalikan ServerFailure ketika repository gagal', () async {
    // Arrange
    const tFailure = ServerFailure(message: 'Internal Server Error', statusCode: 500);
    when(() => mockRepository.getCryptoPrice(tSymbol))
        .thenAnswer((_) async => const Left(tFailure));

    // Act
    final result = await useCase(tSymbol);

    // Assert
    expect(result, const Left(tFailure));
    verify(() => mockRepository.getCryptoPrice(tSymbol)).called(1);
    verifyNoMoreInteractions(mockRepository);
  });
}
```

Jalankan test hingga lolos:
```bash
flutter test test/features/crypto_tracker/domain/usecases/get_crypto_price_test.dart
```

---

### 13. Exercise

#### Level: Easy
Implementasikan custom `EventTransformer` pada BLoC pencarian (Search Input) menggunakan package `rxdart` atau custom stream controller untuk menerapkan teknik *debounce* selama 300ms agar event tidak ditembakkan pada setiap ketikan karakter.

#### Level: Medium
Rancang skema *Drift (SQLite)* untuk `LocalDataSource` yang menyimpan entitas `ProductItem`. Buat implementasi metode `cacheProducts(List<ProductDTO> products)` dan `getCachedProducts()` yang mengonversi record database ke DTO secara komprehensif.

#### Level: Hard
Tulis suite testing integrasi contract (`contract_test.dart`) menggunakan `dio_interceptors` dan mock backend HTTP server lokal (`HttpServer.bind`). Verifikasi skenario di mana token expired mengembalikan 401, refresh token terpanggil tepat satu kali, request awal diulang (*retried*), dan data transaksi sukses di-parse hingga ke tingkat UI presentation stream.

---

### 14. Challenge

**Skenario**: Sistem Rekonsiliasi Pembayaran Offline untuk Kurir Logistik Enterprise.
* **Kasus**: Kurir sering berada di area tanpa sinyal seluler (*dead zone*). Mereka melakukan *cash collection* dan mencatatnya ke aplikasi mobile.
* **Persyaratan Teknis**:
  1. Rancangan arsitektur harus menyediakan queue penyimpanan operasi pembayaran offline berbasis FIFO di persistent storage lokal.
  2. Ketika perangkat kembali online (*connectivity recovered* via Connectivity Stream), sistem harus melakukan batch synchronization secara otomatis di background.
  3. Desain mekanisme *Conflict Resolution* jika akun pengirim telah ditandai *fraudulent* oleh backend selama transaksi offline kurir berlangsung.
  4. Tuliskan blueprint diagram alur data dan struktur class interaksi antara Presentation, Domain, Data, dan Engine Background Sync.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Mengapa `Domain Layer` tidak boleh mengimpor paket `package:flutter`?
2. Apa tujuan utama dari fungsi mapper `toDomain()` pada DTO?
3. Sebutkan perbedaan antara Entity dan Value Object dalam Domain-Driven Design!
4. Mengapa kita lebih memilih tipe data fungsional `Either<Failure, T>` daripada `try-catch` konvensional di layer presentation?
5. Di layer manakah interface dari sebuah Repository harus didefinisikan?

#### B. Pertanyaan Intermediate
6. Bagaimana cara mencegah terjadinya *Token Refresh Loop* tak berujung (*infinite loop*) saat server terus-menerus merespons dengan HTTP 401?
7. Apa peran dari `BlocTransformer.droppable()` dan kapan waktu yang tepat untuk menggunakannya?
8. Mengapa Service Locator (`GetIt`) dianjurkan di-register menggunakan interface abstrak dan bukan instance implementasi konkretnya?
9. Bagaimana Clean Architecture menangani variasi format tanggal string (`"2026-03-31T00:00:00Z"`) dari API agar tidak mengotori representasi native domain `DateTime`?
10. Dalam skenario pengujian unit BLoC, apa perbedaan fundamental antara `setUp`, `act`, dan `expect`?

#### C. Skenario Kasus Produksi
11. **Skenario 1**: Sebuah tim mengeluhkan waktu compile kode Flutter membengkak sangat signifikan dan hot-reload lambat setelah menerapkan ratusan UseCase dan DTO dengan code-generator `build_runner`. Strategi partisi modul apa yang harus diambil untuk mereduksi problem ini?
12. **Skenario 2**: Aplikasi e-commerce enterprise mengalami anomali di mana UI menampilkan data produk lama (*stale data*) bahkan setelah pengguna melakukan *pull-to-refresh*. Telusuri titik kegagalan di layer arsitektur dan jelaskan cara perbaikannya!
13. **Skenario 3**: Terjadi memory leak masif ketika pengguna keluar-masuk dari layar transaksi finansial berulang kali. Hasil profiling DevTools menunjukkan ratusan listener repository tetap hidup. Di layer manakah bug ini terjadi dan bagaimana perbaikan kodenya?

---

### Kunci Jawaban & Panduan Evaluasi Quiz

#### Jawaban Basic
1. Agar Domain Layer tetap independen dari framework UI (Pure Dart). Ini memungkinkan kode bisnis diuji tanpa Flutter test engine, dan bahkan dapat digunakan kembali di CLI, backend server Dart, atau platform lain.
2. DTO memisahkan representasi data mentah (misal: JSON/Database) dari representasi domain murni. `toDomain()` memastikan domain hanya menerima format data yang telah tervalidasi dan relevan secara bisnis.
3. Entity memiliki identitas unik (`identity/ID`) yang membedakannya meskipun properti lainnya identik. Value Object dinilai murni dari nilainya; jika dua Value Object memiliki nilai properti yang sama, keduanya dianggap identik (imutable).
4. `Either` memaksa pemanggil secara eksplisit (*type-safe compile-time check*) untuk menangani skenario sukses dan gagal (`.fold()`), menghindari unhandled runtime crashes.
5. Di **Domain Layer** (sebagai port / abstraksi), sedangkan implementasinya berada di Data Layer.

#### Jawaban Intermediate
6. Dengan menggunakan instance HTTP Client terpisah (tanpa interceptor auth) untuk endpoint refresh, atau memberikan flag internal pada `RequestOptions` (misal: `isRetry: true`) agar interceptor tidak mengulang refresh jika request refresh itu sendiri menghasilkan status 401.
7. `droppable()` mengabaikan event baru yang masuk jika event sebelumnya masih dalam proses eksekusi asinkron. Tepat digunakan untuk aksi seperti tombol checkout pembayaran guna menghindari *double submission*.
8. Untuk mendukung prinsip *Dependency Inversion* dan *Polymorphism*. Ini memungkinkan pertukaran implementasi produksi dengan mock object secara transparan saat melakukan pengujian otomatis.
9. Parsing string menjadi `DateTime` dilakukan di dalam DTO mapper constructor (`AccountDTO.fromJson`), sehingga Entity di Domain Layer langsung menerima tipe data native `DateTime`.
10. `setUp`: Mempersiapkan mock dan kondisi awal dependency. `act`: Menjalankan trigger/event ke BLoC. `expect`: Memverifikasi urutan state yang di-emit oleh BLoC terhadap skenario tersebut.

#### Jawaban Skenario Kasus Produksi
11. **Solusi Modul Partisi**:
    * Mengadopsi arsitektur multi-package/multi-repo menggunakan Melos atau Dart Workspaces.
    * Memisahkan core domain ke dalam pure Dart package tersendiri tanpa dependensi Flutter SDK.
    * Mengurangi dependensi code-gen pada domain layer (gunakan Dart 3 sealed class native dibanding Freezed untuk model sederhana).
12. **Troubleshooting Cache Stale**:
    * Masalah terjadi di `Repository Implementation` Data Layer. Implementasi repository kemungkinan mengembalikan cache tanpa melakukan invalidasi atau tidak memperbarui memori lokal setelah pemanggilan API sukses pada flow refresh.
    * Solusi: Terapkan strategi *Network-First* khusus untuk aksi *pull-to-refresh* (lewat flag `forceRefresh: true` di parameter UseCase) atau gunakan pola Reactive Stream (Drift watch queries) yang otomatis mengalirkan data baru ke UI begitu data lokal di-update oleh network fetch.
13. **Troubleshooting Memory Leak**:
    * Bug terjadi di `Presentation Layer` atau `Repository Subscription Management`. Stream listener atau subscription ke repository/usecase dibuka di BLoC tanpa pernah di-cancel saat BLoC ditutup.
    * Solusi: Override method `close()` pada BLoC untuk membatalkan semua `StreamSubscription.cancel()` aktif, atau gunakan helper `emit.forEach()` yang secara otomatis mengelola lifecycle subscription bersamaan dengan lifecycle BLoC.

---

### 16. Summary

Implementasi Enterprise Clean Architecture pada Flutter bukan sekadar pemisahan folder, melainkan penegakan batasan struktural (*strict architectural boundaries*). Dengan memusatkan logika bisnis murni pada **Domain Layer**, mengabstraksi mekanisme input/output pada **Data Layer**, dan mengontrol aliran reaktif pada **Presentation Layer**, aplikasi enterprise memperoleh:
1. **Determinisme Tinggi**: Penanganan error terstruktur tanpa runtime crash.
2. **Skalabilitas Tim**: Puluhan engineer dapat bekerja secara paralel pada fitur independen tanpa memicu merge-conflict struktural.
3. **Resiliensi Pengujian**: Siklus pengujian logika bisnis terbebas dari overhead rendering engine Flutter, memastikan pipeline CI/CD berjalan cepat, presisi, dan terukur.