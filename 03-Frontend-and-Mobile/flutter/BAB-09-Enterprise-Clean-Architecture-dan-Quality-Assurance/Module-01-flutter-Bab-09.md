# SEKSI 01 — IDENTITAS MODUL

*   **Jalur Pembelajaran:** 03-Frontend-and-Mobile
*   **Topik:** Flutter
*   **Bab:** 09 — Enterprise Clean Architecture & Quality Assurance
*   **Modul:** 01 — Enterprise Clean Architecture & Quality Assurance
*   **Tingkat Kesulitan:** Advanced / Staff Engineer Level
*   **Prasyarat:** Dart OOP mendalam, State Management (BLoC/Cubit), Asynchronous Programming (`Future`, `Stream`), HTTP Networking, dasar pengujian Flutter (`flutter_test`).

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1.  **Merancang Arsitektur Skala Enterprise:** Mengimplementasikan Uncle Bob's Clean Architecture yang diadaptasi khusus untuk ekosistem Flutter, memisahkan domain logic secara murni dari framework dependensi (`flutter/material.dart`).
2.  **Menerapkan Inversion of Control & DI:** Mengisolasi dependensi antar-lapisan menggunakan *Dependency Inversion Principle* (DIP) memanfaatkan `get_it` dan abstract contracts.
3.  **Membangun Functional Error Handling:** Meniadakan *unhandled runtime exceptions* pada presentation layer menggunakan pola Functional Error Handling (`Either<Failure, T>` via paket `fpdart`).
4.  **Menegakkan Quality Assurance Berlapis:** Menulis pengujian komprehensif mencakup *Unit Testing* (Domain & Data Layer), *Bloc Testing* (State Layer), *Widget Testing* (Pump, Find, Mocking), dan *Integration Testing* end-to-end.
5.  **Mengotomatisasi Metrik Kualitas:** Mengonfigurasi linting ketat (*custom analysis options*) dan menghitung *code coverage* secara deterministik untuk deployment CI/CD.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

Dalam rekayasa perangkat lunak skala enterprise, kode yang Anda tulis hari ini akan dibaca, dimodifikasi, dan diskalakan oleh puluhan engineer lain selama bertahun-tahun. Framework, UI trends, dan library pihak ketiga bersifat fana (*transient*), sedangkan aturan bisnis (*business rules*) perusahaan bersifat kekal (*durable*).

### Mental Model: The Dependency Rule
Aturan fundamental Clean Architecture menetapkan bahwa **arah dependensi kode hanya boleh menunjuk ke dalam, menuju Domain Layer**. Lapisan dalam sama sekali tidak boleh mengetahui keberadaan lapisan luar:

```
[ Presentation Layer ] (Flutter Framework, UI, BLoC)
         ↓  (bergantung pada)
[   Data Layer   ]     (Dio, SQLite, SharedPrefs, DTOs)
         ↓  (bergantung pada)
[  Domain Layer  ]     (Entities, Use Cases, Repository Contracts)
```

Jika framework Flutter dihentikan pengembangannya esok hari, seluruh sub-direktori `domain/` Anda harus dapat dieksekusi murni di Dart VM CLI tanpa eror kompilasi satu pun. Jangan biarkan objek visual (`BuildContext`, `Color`, `Widget`) menyusup ke Use Cases atau Entities.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah diagram aliran data siklikal dan pemisahan lapisan (Clean Architecture) pada aplikasi perbankan enterprise:

```
+---------------------------------------------------------------------------------------+
|                                  PRESENTATION LAYER                                   |
|  +---------------------------+               +-------------------------------------+  |
|  |       Flutter UI          |   Dispatches  |       TransferBloc / Cubit          |  |
|  | (Widgets, Pages, Screens) | ------------> | State: TransferLoading, TransferErr |  |
|  +---------------------------+               +-------------------------------------+  |
+-------------------------------------------------|-------------------------------------+
                                                  | Calls Execute()
                                                  v
+---------------------------------------------------------------------------------------+
|                                     DOMAIN LAYER                                      |
|  +---------------------------------------------------------------------------------+  |
|  |                  Use Case: ProcessFundTransferUseCase                           |  |
|  |  - Validasi Limit Transaksi                                                     |  |
|  |  - Memanggil TransferRepository (Interface Contract)                            |  |
|  +---------------------------------------------------------------------------------+  |
|                           |                                 ^                         |
|                           v                                 | Implements Contract     |
|  +-------------------------------------+                    |                         |
|  | Entity: TransferReceipt             |                    |                         |
|  | ValueObject: Currency, AccountNo    |                    |                         |
|  +-------------------------------------+                    |                         |
+-------------------------------------------------------------|-------------------------+
                                                              |
+-------------------------------------------------------------|-------------------------+
|                                      DATA LAYER             |                         |
|  +----------------------------------------------------------+                      |  |
|  | Repository Implementation: TransferRepositoryImpl                               |  |
|  | - Mengonversi TransferModel (DTO) ke TransferReceipt (Entity)                   |  |
|  | - Menangani Cache Policy & Network Strategy                                     |  |
|  +---------------------------------------------------------------------------------+  |
|                |                                          |                           |
|                v Calls API                                v Writes to DB              |
|  +-------------------------------+      +-----------------------------------------+   |
|  | RemoteDataSource (Dio/Retrofit|      | LocalDataSource (Drift/Isar/Hive)       |   |
|  +-------------------------------+      +-----------------------------------------+   |
+---------------------------------------------------------------------------------------+
```

### Aliran Data (Data Flow):
1. **User Action:** User menekan tombol "Transfer". Widget mengirim event ke **TransferBloc**.
2. **Execution:** **TransferBloc** mengeksekusi **ProcessFundTransferUseCase**.
3. **Domain Processing:** Use case memvalidasi domain invariants lalu memanggil method abstract `TransferRepository.executeTransfer()`.
4. **Data Retrieval:** **TransferRepositoryImpl** mengorkestrasi eksekusi: meminta **RemoteDataSource** melakukan HTTP POST.
5. **Serialization:** **RemoteDataSource** mengembalikan JSON yang diparsing ke **TransferModel** (DTO).
6. **Domain Mapping:** **TransferRepositoryImpl** memetakan **TransferModel** menjadi murni **TransferReceipt** (Entity) dan membungkusnya dalam `Right(TransferReceipt)`.
7. **Presentation Delivery:** Bloc menerima hasil, memetakan state, dan UI merender receipt berhasil.

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Struktur Folder Standar Enterprise
Struktur fitur modular (*Feature-first Clean Architecture*):

```
lib/
├── core/
│   ├── error/
│   │   ├── exceptions.dart
│   │   └── failures.dart
│   ├── network/
│   │   ├── api_client.dart
│   │   └── network_info.dart
│   └── usecase/
│       └── usecase.dart
├── features/
│   └── fund_transfer/
│       ├── data/
│       │   ├── datasources/
│       │   │   ├── transfer_local_data_source.dart
│       │   │   └── transfer_remote_data_source.dart
│       │   ├── models/
│       │   │   └── transfer_receipt_model.dart
│       │   └── repositories/
│       │       └── transfer_repository_impl.dart
│       ├── domain/
│       │   ├── entities/
│       │   │   └── transfer_receipt.dart
│       │   ├── repositories/
│       │   │   └── transfer_repository.dart
│       │   └── usecases/
│       │       └── process_transfer_usecase.dart
│       └── presentation/
│           ├── bloc/
│           │   ├── transfer_bloc.dart
│           │   ├── transfer_event.dart
│           │   └── transfer_state.dart
│           ├── pages/
│           │   └── transfer_page.dart
│           └── widgets/
│               └── transfer_form.dart
└── injection_container.dart
```

### 2. Failure vs. Exception Mechanics
*   **Exception:** Objek teknis yang dilempar (*thrown*) oleh infrastruktur ketika terjadi kondisi tak terduga (contoh: `SocketException`, `DioException`, `CacheException`). Berada murni di Data Layer.
*   **Failure:** Entitas representasional domain yang memodelkan kegagalan logis tanpa melempar stack trace yang merusak performa (contoh: `ServerFailure`, `InsufficientFundsFailure`). Dipetakan di Repository dan dikonsumsi oleh Bloc/UI.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Monadic Error Handling Menggunakan `Either<L, R>`
Alih-alih melempar exception menggunakan `throw` yang menyebabkan eksekusi non-deterministik dan *unhandled crash*, kita menggunakan konstruksi *Monad Either* dari paradigma pemrograman fungsional. 

Tipe `Either<L, R>` memiliki dua varian:
*   `Left(L)`: Mengindikasikan kegagalan (*Failure*).
*   `Right(R)`: Mengindikasikan keberhasilan (*Success / Entity*).

```
                      +-------------------+
                      |   Either<L, R>    |
                      +-------------------+
                       /                 \
                      /                   \
        +------------------+         +------------------+
        |     Left(L)      |         |     Right(R)     |
        | Failure (Domain) |         |  Result (Entity) |
        +------------------+         +------------------+
```

Kompiler memaksa kita untuk mengekstrak kedua nilai tersebut menggunakan pola pencocokan (pattern matching / `.fold()`), mengeliminasi bug akibat lupa menangani `try-catch`.

### Inversion of Control (IoC) & Liskov Substitution Principle (LSP)
Domain layer mendefinisikan interface:
```dart
abstract class TransferRepository {
  Future<Either<Failure, TransferReceipt>> execute(TransferParams params);
}
```
Presentation layer hanya bergantung pada interface ini melalui *Use Case*. Pada saat runtime, *Dependency Injection Container* menginjeksikan implementasi konkret `TransferRepositoryImpl`. Hal ini memenuhi Prinsip Substitusi Liskov: kita dapat menukar implementasi HTTP dengan Mock implementation untuk Unit Test, atau implementasi Bluetooth/Offline-first tanpa mengubah sebaris pun logika di Use Case.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi pondasi inti Clean Architecture: Core Failure, Entity, Use Case Contract, dan Functional Pipeline.

```dart
// core/error/failures.dart
import 'package:equatable/equatable.dart';

abstract class Failure extends Equatable {
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
  const NetworkFailure({super.message = 'Koneksi jaringan terputus'});
}
```

```dart
// core/usecase/usecase.dart
import 'package:fpdart/fpdart.dart';
import '../error/failures.dart';

abstract class UseCase<Type, Params> {
  Future<Either<Failure, Type>> call(Params params);
}

class NoParams {}
```

```dart
// features/fund_transfer/domain/entities/transfer_receipt.dart
import 'package:equatable/equatable.dart';

class TransferReceipt extends Equatable {
  final String transactionId;
  final double amount;
  final String recipientAccountNumber;
  final DateTime timestamp;

  const TransferReceipt({
    required this.transactionId,
    required this.amount,
    required this.recipientAccountNumber,
    required this.timestamp,
  });

  @override
  List<Object?> get props => [transactionId, amount, recipientAccountNumber, timestamp];
}
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis File `failures.dart`:
*   `abstract class Failure extends Equatable`: Mewarisi `Equatable` agar dua instance failure dengan pesan dan status code yang sama dianggap identik secara nilai (`==`). Hal ini sangat krusial saat unit testing untuk assert kesamaan state.
*   `final String message; final int? statusCode;`: Atribut immutable penampung representasi error ramah-pengguna dan kode status teknis.
*   `List<Object?> get props => [message, statusCode];`: Memberi tahu Equatable properti mana yang diperhitungkan dalam evaluasi kesetaraan nilai.

### Analisis File `usecase.dart`:
*   `abstract class UseCase<Type, Params>`: Generic contract di mana `Type` merepresentasikan return value ketika berhasil, dan `Params` adalah value object pembungkus payload input.
*   `Future<Either<Failure, Type>> call(Params params);`: Menggunakan Dart *callable class mechanism* (`call`), memungkinkan instance class dieksekusi layaknya fungsi: `useCase(params)`. Return type secara ketat menjamin hasil berupa *Failure* atau objek *Type*.

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario: Modul Transfer Dana Perbankan Skala Enterprise
Aplikasi Core Banking menghadapi kendala reliabilitas tinggi:
1. Jaringan sering *flaky* di pedesaan saat proses debet rekening.
2. Endpoint backend mengembalikan respons 500 dengan payload error berformat heterogen.
3. Kebutuhan compliance PCI-DSS melarang penyimpanan data kartu atau rekening dalam unencrypted cache.
4. Tim Audit mewajibkan code coverage testing minimal 85% untuk modul transaksi keuangan sebelum dirilis ke Google Play dan App Store.

Kita akan merekayasa implementasi penuh fitur ini mulai dari Data Layer (Remote Data Source & Repository), Presentation Layer (Bloc), dan Unit/Widget/Bloc testing secara menyeluruh.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

### 1. Data Layer: Data Source & Model DTO

```dart
// features/fund_transfer/data/models/transfer_receipt_model.dart
import '../../domain/entities/transfer_receipt.dart';

class TransferReceiptModel extends TransferReceipt {
  const TransferReceiptModel({
    required super.transactionId,
    required super.amount,
    required super.recipientAccountNumber,
    required super.timestamp,
  });

  factory TransferReceiptModel.fromJson(Map<String, dynamic> json) {
    return TransferReceiptModel(
      transactionId: json['trx_id'] as String,
      amount: (json['nominal'] as num).toDouble(),
      recipientAccountNumber: json['beneficiary_acc'] as String,
      timestamp: DateTime.parse(json['executed_at'] as String),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'trx_id': transactionId,
      'nominal': amount,
      'beneficiary_acc': recipientAccountNumber,
      'executed_at': timestamp.toIso8601String(),
    };
  }
}
```

```dart
// features/fund_transfer/data/datasources/transfer_remote_data_source.dart
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../../../../core/error/exceptions.dart';
import '../models/transfer_receipt_model.dart';

abstract class TransferRemoteDataSource {
  Future<TransferReceiptModel> executeTransfer({
    required String recipientAcc,
    required double amount,
  });
}

class TransferRemoteDataSourceImpl implements TransferRemoteDataSource {
  final http.Client client;
  final String baseUrl;

  TransferRemoteDataSourceImpl({required this.client, required this.baseUrl});

  @override
  Future<TransferReceiptModel> executeTransfer({
    required String recipientAcc,
    required double amount,
  }) async {
    final response = await client.post(
      Uri.parse('$baseUrl/v1/transfers'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'beneficiary_acc': recipientAcc,
        'nominal': amount,
      }),
    );

    if (response.statusCode == 200 || response.statusCode == 201) {
      return TransferReceiptModel.fromJson(
        jsonDecode(response.body) as Map<String, dynamic>,
      );
    } else {
      throw ServerException(
        statusCode: response.statusCode,
        message: 'Gagal memproses transaksi keuangan: ${response.body}',
      );
    }
  }
}

// core/error/exceptions.dart
class ServerException implements Exception {
  final int statusCode;
  final String message;
  ServerException({required this.statusCode, required this.message});
}
```

### 2. Data Layer: Repository Implementation

```dart
// features/fund_transfer/data/repositories/transfer_repository_impl.dart
import 'package:fpdart/fpdart.dart';
import '../../../../core/error/exceptions.dart';
import '../../../../core/error/failures.dart';
import '../../domain/entities/transfer_receipt.dart';
import '../../domain/repositories/transfer_repository.dart';
import '../datasources/transfer_remote_data_source.dart';

class TransferRepositoryImpl implements TransferRepository {
  final TransferRemoteDataSource remoteDataSource;

  TransferRepositoryImpl({required this.remoteDataSource});

  @override
  Future<Either<Failure, TransferReceipt>> execute(
    String recipientAcc,
    double amount,
  ) async {
    try {
      final remoteReceipt = await remoteDataSource.executeTransfer(
        recipientAcc: recipientAcc,
        amount: amount,
      );
      return Right(remoteReceipt);
    } on ServerException catch (e) {
      return Left(ServerFailure(message: e.message, statusCode: e.statusCode));
    } catch (e) {
      return Left(ServerFailure(message: 'Unexpected runtime error: $e'));
    }
  }
}
```

### 3. Domain Layer: Use Case & Repository Interface

```dart
// features/fund_transfer/domain/repositories/transfer_repository.dart
import 'package:fpdart/fpdart.dart';
import '../../../../core/error/failures.dart';
import '../entities/transfer_receipt.dart';

abstract class TransferRepository {
  Future<Either<Failure, TransferReceipt>> execute(
    String recipientAcc,
    double amount,
  );
}
```

```dart
// features/fund_transfer/domain/usecases/process_transfer_usecase.dart
import 'package:equatable/equatable.dart';
import 'package:fpdart/fpdart.dart';
import '../../../../core/error/failures.dart';
import '../../../../core/usecase/usecase.dart';
import '../entities/transfer_receipt.dart';
import '../repositories/transfer_repository.dart';

class ProcessTransferParams extends Equatable {
  final String recipientAccountNumber;
  final double amount;

  const ProcessTransferParams({
    required this.recipientAccountNumber,
    required this.amount,
  });

  @override
  List<Object?> get props => [recipientAccountNumber, amount];
}

class ProcessTransferUseCase implements UseCase<TransferReceipt, ProcessTransferParams> {
  final TransferRepository repository;

  ProcessTransferUseCase(this.repository);

  @override
  Future<Either<Failure, TransferReceipt>> call(ProcessTransferParams params) async {
    if (params.amount <= 0) {
      return const Left(ServerFailure(message: 'Nominal transfer harus lebih besar dari 0'));
    }
    return await repository.execute(params.recipientAccountNumber, params.amount);
  }
}
```

### 4. Presentation Layer: BLoC Implementation

```dart
// features/fund_transfer/presentation/bloc/transfer_event.dart
import 'package:equatable/equatable.dart';

abstract class TransferEvent extends Equatable {
  const TransferEvent();
  @override
  List<Object?> get props => [];
}

class ExecuteTransferEvent extends TransferEvent {
  final String destinationAccount;
  final double amount;

  const ExecuteTransferEvent({required this.destinationAccount, required this.amount});

  @override
  List<Object?> get props => [destinationAccount, amount];
}
```

```dart
// features/fund_transfer/presentation/bloc/transfer_state.dart
import 'package:equatable/equatable.dart';
import '../../domain/entities/transfer_receipt.dart';

abstract class TransferState extends Equatable {
  const TransferState();
  @override
  List<Object?> get props => [];
}

class TransferInitialState extends TransferState {}

class TransferLoadingState extends TransferState {}

class TransferSuccessState extends TransferState {
  final TransferReceipt receipt;
  const TransferSuccessState(this.receipt);

  @override
  List<Object?> get props => [receipt];
}

class TransferErrorState extends TransferState {
  final String errorMessage;
  const TransferErrorState(this.errorMessage);

  @override
  List<Object?> get props => [errorMessage];
}
```

```dart
// features/fund_transfer/presentation/bloc/transfer_bloc.dart
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../domain/usecases/process_transfer_usecase.dart';
import 'transfer_event.dart';
import 'transfer_state.dart';

class TransferBloc extends Bloc<TransferEvent, TransferState> {
  final ProcessTransferUseCase processTransfer;

  TransferBloc({required this.processTransfer}) : super(TransferInitialState()) {
    on<ExecuteTransferEvent>((event, emit) async {
      emit(TransferLoadingState());
      
      final result = await processTransfer(
        ProcessTransferParams(
          recipientAccountNumber: event.destinationAccount,
          amount: event.amount,
        ),
      );

      result.fold(
        (failure) => emit(TransferErrorState(failure.message)),
        (receipt) => emit(TransferSuccessState(receipt)),
      );
    });
  }
}
```

### 5. Dependency Injection Setup (Service Locator Pattern)

```dart
// injection_container.dart
import 'package:get_it/get_it.dart';
import 'package:http/http.dart' as http;
import 'features/fund_transfer/data/datasources/transfer_remote_data_source.dart';
import 'features/fund_transfer/data/repositories/transfer_repository_impl.dart';
import 'features/fund_transfer/domain/repositories/transfer_repository.dart';
import 'features/fund_transfer/domain/usecases/process_transfer_usecase.dart';
import 'features/fund_transfer/presentation/bloc/transfer_bloc.dart';

final sl = GetIt.instance;

Future<void> initServiceLocator() async {
  // Bloc (Factory: selalu instance baru per-screen lifecycle)
  sl.registerFactory(() => TransferBloc(processTransfer: sl()));

  // Use Cases
  sl.registerLazySingleton(() => ProcessTransferUseCase(sl()));

  // Repositories
  sl.registerLazySingleton<TransferRepository>(
    () => TransferRepositoryImpl(remoteDataSource: sl()),
  );

  // Data Sources
  sl.registerLazySingleton<TransferRemoteDataSource>(
    () => TransferRemoteDataSourceImpl(client: sl(), baseUrl: 'https://api.bank.com'),
  );

  // External Infrastructure
  sl.registerLazySingleton(() => http.Client());
}
```

### 6. Suite Pengujian Lengkap (Testing Strategy)

#### A. Unit Test (Use Case Layer via Mocktail)
```dart
// test/features/fund_transfer/domain/usecases/process_transfer_usecase_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:mocktail/mocktail.dart';
import 'package:your_app/core/error/failures.dart';
import 'package:your_app/features/fund_transfer/domain/entities/transfer_receipt.dart';
import 'package:your_app/features/fund_transfer/domain/repositories/transfer_repository.dart';
import 'package:your_app/features/fund_transfer/domain/usecases/process_transfer_usecase.dart';

class MockTransferRepository extends Mock implements TransferRepository {}

void main() {
  late ProcessTransferUseCase useCase;
  late MockTransferRepository mockRepository;

  setUp(() {
    mockRepository = MockTransferRepository();
    useCase = ProcessTransferUseCase(mockRepository);
  });

  final tReceipt = TransferReceipt(
    transactionId: "TRX-9988",
    amount: 50000.0,
    recipientAccountNumber: "9876543210",
    timestamp: DateTime(2025, 1, 1),
  );

  test('harus mengembalikan TransferReceipt ketika repository berhasil memproses transaksi', () async {
    // Arrange
    when(() => mockRepository.execute("9876543210", 50000.0))
        .thenAnswer((_) async => Right(tReceipt));

    // Act
    final result = await useCase(const ProcessTransferParams(
      recipientAccountNumber: "9876543210",
      amount: 50000.0,
    ));

    // Assert
    expect(result, Right(tReceipt));
    verify(() => mockRepository.execute("9876543210", 50000.0)).called(1);
    verifyNoMoreInteractions(mockRepository);
  });

  test('harus memvalidasi nominal transfer dan mengembalikan ServerFailure jika <= 0', () async {
    // Act
    final result = await useCase(const ProcessTransferParams(
      recipientAccountNumber: "9876543210",
      amount: -100.0,
    ));

    // Assert
    expect(result.isLeft(), true);
    result.fold(
      (failure) => expect(failure.message, 'Nominal transfer harus lebih besar dari 0'),
      (_) => fail('Harus mengembalikan left failure'),
    );
    verifyZeroInteractions(mockRepository);
  });
}
```

#### B. BLoC Test (State Management Testing via `bloc_test`)
```dart
// test/features/fund_transfer/presentation/bloc/transfer_bloc_test.dart
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:mocktail/mocktail.dart';
import 'package:your_app/core/error/failures.dart';
import 'package:your_app/features/fund_transfer/domain/entities/transfer_receipt.dart';
import 'package:your_app/features/fund_transfer/domain/usecases/process_transfer_usecase.dart';
import 'package:your_app/features/fund_transfer/presentation/bloc/transfer_bloc.dart';
import 'package:your_app/features/fund_transfer/presentation/bloc/transfer_event.dart';
import 'package:your_app/features/fund_transfer/presentation/bloc/transfer_state.dart';

class MockProcessTransferUseCase extends Mock implements ProcessTransferUseCase {}

void main() {
  late TransferBloc bloc;
  late MockProcessTransferUseCase mockUseCase;

  setUpAll(() {
    registerFallbackValue(
      const ProcessTransferParams(recipientAccountNumber: '', amount: 0),
    );
  });

  setUp(() {
    mockUseCase = MockProcessTransferUseCase();
    bloc = TransferBloc(processTransfer: mockUseCase);
  });

  tearDown(() {
    bloc.close();
  });

  final tReceipt = TransferReceipt(
    transactionId: "TRX-101",
    amount: 100000.0,
    recipientAccountNumber: "1234567890",
    timestamp: DateTime(2025, 1, 1),
  );

  blocTest<TransferBloc, TransferState>(
    'memancarkan [TransferLoadingState, TransferSuccessState] ketika transaksi sukses',
    build: () {
      when(() => mockUseCase(any())).thenAnswer((_) async => Right(tReceipt));
      return bloc;
    },
    act: (bloc) => bloc.add(const ExecuteTransferEvent(
      destinationAccount: "1234567890",
      amount: 100000.0,
    )),
    expect: () => [
      TransferLoadingState(),
      TransferSuccessState(tReceipt),
    ],
    verify: (_) {
      verify(() => mockUseCase(const ProcessTransferParams(
        recipientAccountNumber: "1234567890",
        amount: 100000.0,
      ))).called(1);
    },
  );

  blocTest<TransferBloc, TransferState>(
    'memancarkan [TransferLoadingState, TransferErrorState] ketika eksekusi usecase gagal',
    build: () {
      when(() => mockUseCase(any()))
          .thenAnswer((_) async => const Left(ServerFailure(message: 'Saldo tidak mencukupi')));
      return bloc;
    },
    act: (bloc) => bloc.add(const ExecuteTransferEvent(
      destinationAccount: "1234567890",
      amount: 5000000.0,
    )),
    expect: () => [
      TransferLoadingState(),
      const TransferErrorState('Saldo tidak mencukupi'),
    ],
  );
}
```

#### C. Widget Testing
```dart
// test/features/fund_transfer/presentation/widgets/transfer_status_widget_test.dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

class TransferStatusWidget extends StatelessWidget {
  final bool isLoading;
  final String? errorMessage;
  final String? receiptId;

  const TransferStatusWidget({
    super.key,
    required this.isLoading,
    this.errorMessage,
    this.receiptId,
  });

  @override
  Widget build(BuildContext context) {
    if (isLoading) {
      return const CircularProgressIndicator(key: Key('loader'));
    }
    if (errorMessage != null) {
      return Text('Error: $errorMessage', key: const Key('error_text'));
    }
    if (receiptId != null) {
      return Text('Success: $receiptId', key: const Key('success_text'));
    }
    return const SizedBox.shrink();
  }
}

void main() {
  testWidgets('menampilkan CircularProgressIndicator saat isLoading = true', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: TransferStatusWidget(isLoading: true),
        ),
      ),
    );

    expect(find.byKey(const Key('loader')), findsOneWidget);
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
  });

  testWidgets('menampilkan pesan error saat errorMessage disediakan', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: TransferStatusWidget(isLoading: false, errorMessage: 'Koneksi Terputus'),
        ),
      ),
    );

    expect(find.byKey(const Key('error_text')), findsOneWidget);
    expect(find.text('Error: Koneksi Terputus'), findsOneWidget);
  });
}
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Aspek | Pragmatic MVC / "Feature by Type" | Clean Architecture Enterprise | Micro-Frontend Modular Package |
| :--- | :--- | :--- | :--- |
| **Boilerplate Code** | Rendah (Sedikit file dan mapper) | Tinggi (Entity, Model, DTO, Mappers, Use Case) | Sangat Tinggi (Banyak `pubspec.yaml` mandiri) |
| **Testability** | Rendah (UI terikat erat dengan network logic) | Ekstrem (Tiap lapisan dapat dimock secara independen) | Ekstrem (Isolasi modul total) |
| **Pemisahan Tanggung Jawab** | Buruk (Controller/Widget menampung logika SQL/API) | Sangat Ketat (Domain layer murni dari framework) | Sangat Ketat (Pemisahan fisik repositori/package) |
| **Kurva Pembelajaran Tim**| Sangat Cepat (Cocok untuk junior/prototyping) | Moderat hingga Tinggi (Butuh disiplin arsitektur) | Sangat Tinggi (Manajemen dependency tree kompleks) |
| **Skalabilitas Engineer** | Max ~3-5 engineers (Banyak merge conflict) | 10 - 50 engineers lintas tim | 50+ engineers (Skala multi-organisasi besar) |
| **Waktu Kompilasi (Build)**| Cepat | Normal | Sangat Cepat (Cache modular per package) |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. Kebocoran Abstraksi UI ke Domain Layer (Framework Leakage)
*   **Kasus:** Menaruh parameter `BuildContext` atau `Color` di dalam Use Case atau Entity.
*   **Dampak Buruk:** Tidak mungkin menjalankan Unit Test murni tanpa menjalankan *WidgetTester environment* yang membutuhkan resource rendering headless, memperlambat pipeline CI/CD hingga 10x lipat.
*   **Mitigasi:** Aturan analisis statis (linter rule) ketat: larang impor `package:flutter/...` di dalam folder `lib/**/domain/**`.

### 2. DTO Leakage (Menggunakan Model di Presentation Layer)
*   **Kasus:** BLoC mengonsumsi `TransferReceiptModel` langsung tanpa konversi ke `TransferReceipt` entity.
*   **Dampak Buruk:** Jika backend mengubah nama key JSON (`beneficiary_acc` menjadi `destination_account`), perubahan merembet ke Widget UI.
*   **Mitigasi:** Repositori wajib memetakan DTO ke Domain Entity sebelum dikembalikan via `Right(entity)`.

### 3. Memory Leaks pada Stream/Bloc Subscription
*   **Kasus:** Tidak menutup controller atau mengabaikan lifecycle `BlocProvider`.
*   **Dampak Buruk:** Native memory footprint membengkak secara linier setiap kali user membuka dan menutup screen transfer.
*   **Mitigasi:** Gunakan `BlocProvider` terikat route context untuk membersihkan memory otomatis via `.close()` ketika rute di-*pop*.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. The Anemic Domain Anti-Pattern
*Salah:* Menggunakan use case hanya sebagai proxy passthrough tanpa logika apa pun:
```dart
class TransferUseCase {
  final Repository repo;
  TransferUseCase(this.repo);
  Future<Data> call() => repo.getData(); // Tidak ada validasi atau rule
}
```
*Solusi:* Jika use case benar-benar tidak memiliki domain invariant, satukan dengan flow orkestrasi, atau lakukan validasi bisnis (cek boundary, hashing token, validasi izin) di Use Case sebelum menyentuh data layer.

### 2. Mengabaikan Try-Catch di Luar DataSource
*Salah:* Membiarkan generic `Exception` dari paket pihak ketiga tembus ke Presentation.
*Solusi:* Tangkap `DioException`, `PlatformException`, atau `FormatException` di `RepositoryImpl`