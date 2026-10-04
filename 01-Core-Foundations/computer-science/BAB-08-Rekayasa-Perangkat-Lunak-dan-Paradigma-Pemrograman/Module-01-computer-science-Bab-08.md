## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: CS-FND-0801
* **Nama Modul**: Rekayasa Perangkat Lunak & Paradigma Pemrograman (Software Engineering & Programming Paradigms)
* **Kategori**: 01-Core-Foundations
* **Tingkat Kesulitan**: Intermediate (Menengah)
* **Estimasi Waktu Penyelesaian**: 8 – 10 Jam Pembelajaran Mandiri / 4 Jam Sesi Perkuliahan Laboratorium
* **Prasyarat**: 
  * Pemahaman mendasar arsitektur komputer (eksekusi instruksi CPU, alokasi memori Stack & Heap).
  * Penguasaan minimal satu bahasa pemrograman berbasis teks (C, C++, Java, Rust, atau Python).
  * Struktur Data & Algoritma Tingkat Dasar (Array, Linked List, Tree, Kompleksitas Waktu & Ruang).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta ajar diharapkan mampu:

1. **Menganalisis dan Membedakan Paradigma Pemrograman (Kognitif - C4)**: Mengidentifikasi karakteristik struktural, model eksekusi, serta implikasi mutasi status (*state mutation*) antara paradigma Imperatif/Prosedural, Berorientasi Objek (*Object-Oriented*), Fungsional (*Functional*), dan Deklaratif.
2. **Mengimplementasikan Prinsip Desain Modular dan SOLID (Psikomotor - P4)**: Merancang dan menulis kode perangkat lunak modular yang mematuhi prinsip *Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation,* dan *Dependency Inversion* untuk meminimalkan keterikatan (*coupling*) dan memaksimalkan kohesi (*cohesion*).
3. **Mengevaluasi Mekanisme Eksekusi Runtime Paradigma (Kognitif - C5)**: Membedah mekanisme teknis *under-the-hood* seperti *virtual method table* (vtable) pada OOP dinamis serta *lexical closure* dan *higher-order function evaluation* pada paradigma fungsional.
4. **Menerapkan Metodologi Siklus Hidup Perangkat Lunak (Afektif - A3)**: Mengintegrasikan prinsip rekayasa perangkat lunak modern (seperti *Test-Driven Development*, integrasi berkelanjutan, metrik kompleksitas siklomatik) ke dalam alur kerja rekayasa aplikasi berskala industri.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                              [REKAYASA PERANGKAT LUNAK]
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 ▼                                               ▼
     [Metodologi & Arsitektur]                       [Paradigma Pemrograman]
         │              │                                        │
         ├─ SDLC        ├─ Modularitas                           ├─ Imperatif / Prosedural
         │   ├─ Waterfall├─ Kohesi (Tinggi)                      │   └─ State & Subroutine
         │   └─ Agile    └─ Coupling (Rendah)                    │
         │                                                       ├─ Berorientasi Objek (OOP)
         └─ Prinsip Desain                                       │   ├─ Encapsulation
             ├─ SOLID                                            │   ├─ Inheritance vs Composition
             ├─ DRY & YAGNI                                      │   └─ Polymorphism (VTable)
             └─ Clean Architecture                               │
                                                                 ├─ Fungsional (FP)
                                                                 │   ├─ Pure Functions
                                                                 │   ├─ Immutability
                                                                 │   └─ First-Class Functions
                                                                 │
                                                                 └─ Deklaratif / Logika
                                                                     └─ Target State Expression
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Kode komputer pada hakikatnya dieksekusi oleh mesin sebagai instruksi linier biner. Namun, perangkat lunak modern tidak dibangun oleh satu mesin untuk dibaca mesin lain; perangkat lunak dibangun oleh tim insinyur untuk menyelesaikan domain masalah bisnis dan teknis yang kompleks dan terus berevolusi.

1. **Pengendalian Kompleksitas (*Complexity Management*)**: Masalah terbesar dalam rekayasa perangkat lunak adalah pertumbuhan entropi kode. Paradigma pemrograman adalah kacamata mental dan kerangka formal yang menentukan bagaimana kita memecah masalah besar menjadi komponen-komponen terisolasi yang dapat dinalar secara kognitif.
2. **Mitigasi Biaya Pemeliharaan (*Maintainability & Total Cost of Ownership*)**: Lebih dari 70% biaya siklus hidup perangkat lunak dialokasikan untuk pemeliharaan (*maintenance*), perbaikan *bug*, dan adaptasi fitur baru. Desain yang salah melahirkan *Technical Debt* yang dapat melumpuhkan kecepatan rilis (*velocity*) tim rekayasa.
3. **Konkurensi dan Keamanan Memori**: Paradigma menentukan bagaimana *state* diakses. Kesalahan mutasi *shared-state* pada program konkuren OOP multithreaded dapat memicu *race condition*, *deadlock*, dan kegagalan yang sulit di-*reproduce*. Paradigma fungsional menawarkan solusi matematis melalui *immutability*.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Rekayasa Perangkat Lunak (*Software Engineering*)
Rekayasa Perangkat Lunak (RPL) adalah penerapan pendekatan sistematis, disiplin, dan terukur terhadap pengembangan, operasi, dan pemeliharaan perangkat lunak. RPL mentransformasikan pemrograman dari sekadar seni merangkai sintaks (*hacking*) menjadi disiplin rekayasa yang dapat diprediksi secara kualitas, biaya, dan waktu.

### 2. Paradigma Pemrograman (*Programming Paradigms*)
Paradigma pemrograman adalah pendekatan fundamental dalam menyusun struktur, mengorganisir logika, dan memodelkan eksekusi komputasi. Paradigma tidak terikat kaku pada satu bahasa, melainkan memengaruhi gaya bahasa tersebut dirancang.

* **Imperatif/Prosedural**: Berfokus pada *bagaimana* (*how*) tugas dieksekusi selangkah demi selangkah. Program tersusun atas kumpulan prosedur/fungsi yang memanipulasi *state* global atau lokal yang dapat bermutasi (*mutable*).
* **Berorientasi Objek (OOP)**: Memodelkan domain persoalan sebagai kumpulan unit mandiri yang disebut *Objek*. Objek membungkus data (*state/attribute*) dan perilaku (*behavior/methods*), mengisolasi akses langsung melalui antarmuka (*interface*).
* **Fungsional (FP)**: Memperlakukan komputasi sebagai evaluasi fungsi-fungsi matematika murni (*pure mathematical functions*). FP menghindari status yang berubah (*mutable state*) dan efek samping (*side effects*), memperlakukan fungsi sebagai warga kelas satu (*first-class citizens*).
* **Deklaratif**: Berfokus pada *apa* (*what*) hasil yang diinginkan tanpa mendikte kontrol alur eksekusi langkah-demi-langkah (misal: SQL, HTML, Prolog).

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### 1. Paradigma Prosedural: Aliran Kontrol dan Stack Frame
Program prosedural mengeksekusi instruksi secara sekuensial. Saat sebuah prosedur dipanggil:
1. Alamat instruksi saat ini (*Program Counter*) disimpan ke *Call Stack*.
2. Stack frame baru dialokasikan untuk menyimpan argumen dan variabel lokal.
3. Eksekusi melompat ke alamat prosedur tujuan.
4. Ketika prosedur selesai, nilai balik dioperasikan, stack frame dideallokasi (*pop*), dan eksekusi berlanjut dari alamat pengembalian.
*State* diubah langsung melalui modifikasi nilai memori pada stack atau heap.

### 2. Paradigma OOP: Dynamic Dispatch dan Virtual Method Table (VTable)
Pada OOP, polimorfisme runtime dicapai melalui mekanisme penyesuaian dinamis (*dynamic dispatch*).
* Setiap kelas yang memiliki metode virtual memiliki tabel pointer fungsi tersembunyi bernama **vtable**.
* Setiap instans objek dari kelas tersebut memiliki pointer tersembunyi bernama **vptr** yang menunjuk ke vtable kelasnya.
* Ketika metode polimorfik dipanggil, CPU tidak melompat ke alamat absolut secara langsung (*static call*), melainkan membaca alamat melalui `vptr -> vtable[offset] -> jump`.

```
Instance Object (Heap)           VTable Class (Data Segment)         Function Code (Text Segment)
┌──────────────────────┐         ┌─────────────────────────┐         ┌─────────────────────────┐
│ vptr                 ├────────►│ MethodA() Pointer       ├────────►│ Machine Code MethodA() │
├──────────────────────┤         ├─────────────────────────┤         └─────────────────────────┘
│ Field 1 (e.g., id)   │         │ MethodB() Pointer       ├────┐    ┌─────────────────────────┐
├──────────────────────┤         └─────────────────────────┘    └───►│ Machine Code MethodB() │
│ Field 2 (e.g., name) │                                             └─────────────────────────┘
└──────────────────────┘
```

### 3. Paradigma Fungsional: Pure Functions, Immutability & Lexical Closures
* **Pure Function**: Fungsi yang untuk argumen masukan yang identik selalu mengembalikan keluaran yang sama dan tidak memicu *side-effect* (tidak mengubah variabel luar, tidak menulis I/O, tidak memodifikasi memori global). Sifat ini memungkinkan optimasi *memoization* dan *referential transparency*.
* **Immutability**: Saat suatu data diubah, alih-alih menimpa data di alamat memori lama, lingkungan FP mengalokasikan data baru dengan perubahan yang diterapkan (sering kali dioptimalkan melalui *Persistent Data Structures* yang menggunakan *structural sharing* berbasis Directed Acyclic Graph / DAG untuk menghemat memori).
* **Lexical Closure**: Kemampuan sebuah fungsi untuk menangkap (*capture*) referensi variabel dari lingkungan leksikal pembuatannya, menyimpannya di Heap bahkan setelah ruang lingkup (*scope*) luarnya selesai dieksekusi.

### 4. Prinsip Desain Berorientasi Objek: SOLID
1. **Single Responsibility Principle (SRP)**: Sebuah modul/kelas harus memiliki satu dan hanya satu alasan untuk berubah.
2. **Open/Closed Principle (OCP)**: Entitas perangkat lunak harus terbuka untuk ekstensi (*open for extension*), namun tertutup untuk modifikasi (*closed for modification*).
3. **Liskov Substitution Principle (LSP)**: Objek dari subtipe harus dapat menggantikan objek dari supertipe tanpa merusak kebenaran program.
4. **Interface Segregation Principle (ISP)**: Klien tidak boleh dipaksa bergantung pada antarmuka (*interface*) yang tidak digunakannya.
5. **Dependency Inversion Principle (DIP)**: Modul tingkat tinggi tidak boleh bergantung pada modul tingkat rendah; keduanya harus bergantung pada abstraksi (*interfaces*).

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Perbandingan Arsitektur Eksekusi Antar Paradigma

```
MODEL PROSEDURAL:
Global/Heap State <─── Mutation ─── Prosedur A()
      │                                │
      └─────────────── Mutation ─── Prosedur B()

─────────────────────────────────────────────────────────────────────────

MODEL BERORIENTASI OBJEK (OOP):
┌─────────────────────────┐            ┌─────────────────────────┐
│       Objek Alpha       │            │        Objek Beta       │
│  ┌───────────────────┐  │   Pesan    │  ┌───────────────────┐  │
│  │ State Terisolasi  │  │ (Message)  │  │ State Terisolasi  │  │
│  └─────────▲─────────┘  ├───────────►│  └─────────▲─────────┘  │
│            │            │            │            │            │
│       Metode Publik     │            │       Metode Publik     │
└─────────────────────────┘            └─────────────────────────┘

─────────────────────────────────────────────────────────────────────────

MODEL FUNGSIONAL:
Input Stream (Imutabel)
     │
     ▼
┌───────────────┐
│ Pure Function │ ── (Tanpa State/Tanpa Side Effect)
└───────┬───────┘
        ▼ Data Baru (Imutabel)
┌───────────────┐
│ Pure Function │ ── (Tanpa State/Tanpa Side Effect)
└───────┬───────┘
        ▼
Output Stream (Hasil Akhir)
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Studi Kasus: Menyaring sekumpulan bilangan bulat positif genap, lalu mengalikannya dengan dua.

### Pendekatan Prosedural (Imperatif C-Style)
Menggunakan iterasi manual, manipulasi indeks, dan mutasi *in-place* atau alokasi array baru.

```c
#include <stdio.h>

void filter_and_double(const int* src, int size, int* dest, int* out_size) {
    int count = 0;
    for (int i = 0; i < size; i++) {
        if (src[i] % 2 == 0) {
            dest[count] = src[i] * 2; // Mutasi langsung
            count++;
        }
    }
    *out_size = count;
}

int main(void) {
    int numbers[] = {1, 2, 3, 4, 5, 6};
    int result[6];
    int result_len = 0;

    filter_and_double(numbers, 6, result, &result_len);

    for (int i = 0; i < result_len; i++) {
        printf("%d ", result[i]); // Output: 4 8 12
    }
    return 0;
}
```

### Pendekatan Berorientasi Objek (Encapsulation & Polymorphic Processor)
Membungkus data dalam koleksi objek yang memiliki tanggung jawab proses.

```java
import java.util.ArrayList;
import java.util.List;

public class NumberProcessor {
    private final List<Integer> numbers;

    public NumberProcessor(List<Integer> numbers) {
        this.numbers = new ArrayList<>(numbers);
    }

    public List<Integer> filterEvenAndDouble() {
        List<Integer> transformed = new ArrayList<>();
        for (Integer n : this.numbers) {
            if (this.isEven(n)) {
                transformed.add(this.multiplyByTwo(n));
            }
        }
        return transformed;
    }

    private boolean isEven(int n) {
        return n % 2 == 0;
    }

    private int multiplyByTwo(int n) {
        return n * 2;
    }
}
```

### Pendekatan Fungsional (Pure, Declarative, Pipeline)
Menggunakan komposisi fungsi tingkat tinggi (*higher-order functions*) tanpa mutasi state.

```python
from typing import List

def is_even(n: int) -> bool:
    return n % 2 == 0

def double(n: int) -> int:
    return n * 2

def process_pipeline(nums: List[int]) -> List[int]:
    # Pipeline transformasi fungsional: map(double, filter(is_even, nums))
    return list(map(double, filter(is_even, nums)))

numbers = [1, 2, 3, 4, 5, 6]
result = process_pipeline(numbers)
# Original 'numbers' tidak bermutasi sama sekali (Immutability terjamin)
print(result) # Output: [4, 8, 12]
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Kasus Produksi: Sistem Pemrosesan Pembayaran Transaksi (*Order Processing Engine*) dengan Penerapan Prinsip SOLID dan Pemisahan Paradigma Fungsional Murni pada Kalkulasi Pajak.

Bahasa: **TypeScript**

```typescript
// 1. DOMAIN ABSTRACTIONS (DIP & ISP - Interfaces)
export interface Transaction {
  readonly id: string;
  readonly amount: number;
  readonly taxRate: number;
}

export interface PaymentReceipt {
  readonly transactionId: string;
  readonly netPayable: number;
  readonly status: 'PAID' | 'FAILED';
}

export interface PaymentGateway {
  executeCharge(amount: number): Promise<boolean>;
}

// 2. FUNCTIONAL CORE (Pure business logic, zero side-effects, deterministik)
export namespace TaxCalculator {
  export const computeNet = (baseAmount: number, taxRate: number): number => {
    if (baseAmount < 0 || taxRate < 0) {
      throw new Error("Argumen kalkulasi tidak valid.");
    }
    return baseAmount + (baseAmount * taxRate);
  };
}

// 3. OBJECT-ORIENTED ENGINE (SRP & OCP - State and coordination)
export class OrderPaymentService {
  // Dependency Inversion: Bergantung pada abstraksi antarmuka Gateway, bukan kelas konkret
  constructor(private readonly gateway: PaymentGateway) {}

  public async processOrder(transaction: Transaction): Promise<PaymentReceipt> {
    // Memanggil pure function dari Core FP
    const finalAmount = TaxCalculator.computeNet(transaction.amount, transaction.taxRate);

    // Side-effect dikoordinasikan oleh Object Layer
    const success = await this.gateway.executeCharge(finalAmount);

    if (!success) {
      return {
        transactionId: transaction.id,
        netPayable: finalAmount,
        status: 'FAILED',
      };
    }

    return {
      transactionId: transaction.id,
      netPayable: finalAmount,
      status: 'PAID',
    };
  }
}

// 4. INFRASTRUCTURE IMPLEMENTATION (LSP - Substitutable Gateway)
export class StripeGatewayAdapter implements PaymentGateway {
  async executeCharge(amount: number): Promise<boolean> {
    // Logika integrasi ke API eksternal Stripe
    console.log(`[Stripe API] Berhasil menarik dana: Rp ${amount}`);
    return true;
  }
}

export class MockGatewayAdapter implements PaymentGateway {
  async executeCharge(amount: number): Promise<boolean> {
    // Digunakan untuk pengujian otomatis tanpa real network call
    return true;
  }
}
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi Parameter | Imperatif / Prosedural | Berorientasi Objek (OOP) | Fungsional (FP) |
| :--- | :--- | :--- | :--- |
| **Overhead Memori** | **Sangat Rendah**: Akses langsung ke stack/flat buffer. | **Menengah-Tinggi**: Overhead header objek, referensi pointer, vptr/vtable. | **Tinggi (Kecuali dioptimasi)**: Pembuatan objek baru berkelanjutan akibat immutability. |
| **Beban Kognitif / Konsep** | Rendah di awal, namun luar biasa rumit saat skala basis kode membesar. | Menengah: Memerlukan perancangan hierarki kelas dan *design patterns* yang tepat. | Tinggi: Menuntut abstraksi matematika (monad, currying, komposisi). |
| **Safety pada Concurrency** | **Sangat Buruk**: Rawan *race condition* akibat shared mutable state. | **Rentan**: Memerlukan sinkronisasi manual yang berat (Mutex, Lock, Semaphore). | **Sangat Tinggi**: Aman secara alamiah (*thread-safe*) karena data bersifat *immutable*. |
| **Debugging & Pelacakan State** | Sulit diidentifikasi jika pointer/state global dimutasi dari banyak prosedur. | Bisa menjadi kompleks jika hierarki *inheritance* bertingkat terlalu dalam. | **Sangat Mudah**: Fungsi deterministik dapat diuji secara terisolasi tanpa mock state. |
| **Biaya Eksekusi CPU** | Cepat, instruksi dapat diterjemahkan hampir 1:1 ke Assembly. | Ada penalti beberapa siklus CPU untuk *dynamic dispatch indirection*. | Overhead alokasi memori GC (*Garbage Collection*) & rekursi (jika tanpa tail-call optimization). |

---

## SEKSI 11 — BEST PRACTICES

1. **Komposisi daripada Warisan (*Composition Over Inheritance*)**: Jangan membuat hierarki pewarisan kelas lebih dari 2 tingkat kedalaman. Pewarisan memperkuat *coupling* (*fragile base class problem*). Gunakan antarmuka dan delegasi objek.
2. **Prioritaskan Immutability**: Jadikan variabel bersifat konstan (`const`, `final`, `readonly`) secara default. Batasi ruang gerak mutasi hanya pada fungsi terkecil yang benar-benar membutuhkan optimasi performa *in-place*.
3. **Pemisahan Logika Murni dan Efek Samping (*Functional Core, Imperative Shell*)**:
   * Letakkan kalkulasi bisnis terpenting di dalam *pure function* tanpa ketergantungan I/O.
   * Buat *shell* (lapisan terluar) bertipe imperatif/OOP yang bertugas menangani pembacaan database, HTTP request, dan penyimpanan file.
4. **Law of Demeter (Prinsip Interaksi Minimal)**: Sebuah metode hanya boleh memanggil fungsi pada objek miliknya sendiri, objek yang diteruskan sebagai parameter, atau objek yang diinstansiasi secara lokal. Hindari pemanggilan berantai: `a.getB().getC().execute()`.
5. **Static Analysis & Formatting Enforcement**: Gunakan *linter* (misal: ESLint, Clippy, SonarQube) untuk memverifikasi kompleksitas kode (*cyclomatic complexity* di bawah ambang batas < 10) secara otomatis pada pipeline CI/CD.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. *God Object / God Class Anti-Pattern*
* **Bentuk Kesalahan**: Membuat kelas tunggal yang menampung ribuan baris kode dan mengendalikan semua fungsionalitas sistem (misal: `AppManager`, `SystemController`).
* **Dampak**: Pelanggaran berat prinsip SRP, memicu konflik merge Git permanen, dan mustahil untuk diuji (*unit test*) secara terisolasi.
* **Perbaikan**: Pecah kelas tersebut menjadi layanan-layanan granular yang memiliki batasan domain (*bounded context*) spesifik.

### 2. Kebocoran Abstraksi (*Leaky Abstraction*)
* **Bentuk Kesalahan**: Antarmuka mengekspos detail implementasi internal (misal: interface `UserDatabase` mengekspos tipe data internal driver database seperti `SQLException`).
* **Dampak**: Jika database diganti dengan cache Redis, modul pemanggil ikut rusak karena terikat erat pada kontrak implementasi lama.
* **Perbaikan**: Bungkus exception dan struktur data vendor ke dalam bentuk domain murni (*Domain Exceptions / Custom DTO*).

### 3. *Primitive Obsession*
* **Bentuk Kesalahan**: Menggunakan tipe primitif secara langsung untuk entitas yang memiliki aturan validasi bisnis (misal: merepresentasikan email, uang, koordinat geografis hanya sebagai `string` atau `double`).
* **Dampak**: Pengecekan duplikasi `if (email.contains("@"))` tersebar di seluruh basis kode.
* **Perbaikan**: Terapkan pola *Value Object* (misal: kelas `EmailAddress` yang memvalidasi dirinya sendiri saat konstruksi).

### 4. *Side-Effect* Tak Terduga dalam Paradigma Fungsional
* **Bentuk Kesalahan**: Memanipulasi array yang dilewatkan sebagai argumen fungsi alih-alih mengembalikan array baru:
  ```javascript
  // SALAH (Mengubah input array eksternal)
  function badSort(arr) { return arr.sort(); } 

  // BENAR (Menjaga purity)
  function goodSort(arr) { return [...arr].sort(); }
  ```

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Refactoring Prosedural ke OOP Bersih (Tingkat: Pemula)
* **Tugas**: Diberikan sebuah fungsi C/Python yang menghitung luas dan keliling berbagai bentuk geometri menggunakan pernyataan `switch-case` bercabang banyak.
* **Instruksi**: Refaktorisasi fungsi tersebut menjadi hierarki polimorfik OOP menggunakan antarmuka `Shape` dengan metode abstrak `calculateArea()` dan `calculatePerimeter()`. Buat implementasi konkret: `Circle`, `Rectangle`, dan `Triangle`. Hilangkan seluruh percabangan kondisional `if-else` atau `switch`.

### Latihan 2: Implementasi Pipeline Transformasi Data FP (Tingkat: Menengah)
* **Tugas**: Diberikan sebuah dataset transaksi berupa array objek JSON:
  `[{ id: 1, user: "Alice", type: "CREDIT", amount: 150 }, ...]`.
* **Instruksi**: Tanpa menggunakan perulangan imperatif (`for`, `while`) dan tanpa mutasi variabel:
  1. Filter hanya transaksi berjenis `"CREDIT"`.
  2. Ekstrak nilai nominalnya dan konversikan mata uangnya menggunakan fungsi kurs.
  3. Hitung akumulasi totalnya menggunakan operasi *fold/reduce*.
  4. Kode harus disusun menggunakan teknik *Function Composition* atau *Pipelining*.

### Latihan 3: Mini IoC/Dependency Injection Container (Tingkat: Lanjutan)
* **Tugas**: Rancang pustaka modular kecil dalam TypeScript atau Java yang mampu mendaftarkan interface terhadap implementasi konkretnya.
* **Kriteria Pengujian**:
  1. Kontainer mampu menginstansiasi *Service* secara dinamis dan menyuntikkan (*inject*) dependensi gateway/repository melalui konstruktor.
  2. Terapkan prinsip DIP: modul bisnis tidak boleh memanggil kata kunci `new` untuk layanan infrastruktur.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

**Pertanyaan 1:**
Apa yang secara mekanis membedakan pemanggilan metode reguler (*static dispatch*) dengan metode polimorfik (*dynamic dispatch*) pada bahasa berorientasi objek yang dikompilasi seperti C++?
* A. Metode polimorfik dialokasikan di dalam stack frame pemanggil.
* B. Metode polimorfik diselesaikan pada saat *compile-time* oleh linker.
* C. Metode polimorfik memerlukan pembacaan pointer melalui vtable objek untuk mendapatkan alamat fungsi runtime.
* D. Metode polimorfik mengubah status CPU ke mode kernel sebelum dieksekusi.

**Pertanyaan 2:**
Sebuah modul perangkat lunak dikatakan melanggar *Liskov Substitution Principle* (LSP) apabila:
* A. Modul tersebut memiliki lebih dari satu alasan untuk berubah.
* B. Subkelas melempar exception tak terduga (*unexpected exception*) untuk metode yang didukung oleh superkelasnya.
* C. Kelas mengimplementasikan lebih dari satu antarmuka secara bersamaan.
* D. Fungsi memodifikasi variabel global di luar lingkup leksikalnya.

**Pertanyaan 3:**
Manakah pernyataan berikut yang mendefinisikan sifat *Referential Transparency* dalam paradigma fungsional?
* A. Kemampuan sebuah fungsi untuk mengakses variabel private milik objek lain secara transparan.
* B. Karakteristik di mana ekspresi pemanggilan fungsi dapat digantikan langsung oleh nilai hasilnya tanpa mengubah perilaku komputasi program.
* C. Proses serialisasi objek menjadi representasi string transparan seperti JSON.
* D. Eksekusi kode yang menjamin pembebasan memori secara instan tanpa menunggu Garbage Collector.

**Pertanyaan 4:**
Prinsip *Open/Closed Principle* (OCP) dari akronim SOLID merekomendasikan arsitek sistem untuk:
* A. Membuka semua visibilitas atribut kelas menjadi publik agar mudah dimodifikasi.
* B. Mencegah penambahan fitur baru setelah perangkat lunak berhasil dideploy ke fase produksi.
* C. Merancang modul sehingga penambahan kapabilitas baru dilakukan dengan menulis kode baru, bukan mengedit kode lama yang telah stabil.
* D. Memisahkan antarmuka besar menjadi antarmuka kecil yang terspesialisasi.

**Pertanyaan 5:**
Apa bahaya utama dari mutasi status (*shared mutable state*) pada sistem perangkat lunak yang mengeksekusi operasi konkurensi skala tinggi (*high-concurrency multithreading*)?
* A. Meningkatnya kompleksitas siklomatik kode.
* B. Terjadinya ketidakkonsistenan data akibat *race condition* dan overhead penguncian (*lock contention*).
* C. Penurunan resolusi pemetaan alamat virtual memori oleh unit MMU.
* D. Ketidakmampuan compiler dalam melakukan inlining fungsi rekursif.

---

### Kunci Jawaban & Rasional

* **Jawaban 1: C** — *Rasional*: Dynamic dispatch mengandalkan dereferensi pointer ganda secara runtime: instans objek membawa pointer `vptr` yang merujuk pada `vtable` kelas untuk menemukan alamat memori fungsi yang tepat sesuai tipe konkret runtime-nya.
* **Jawaban 2: B** — *Rasional*: LSP mengharuskan subtipe mematuhi kontrak supertipe. Jika turunan menolak atau melempar pengecualian pada perilaku dasar yang didefinisikan induk, program pemanggil yang mengasumsikan tipe induk akan mengalami crash runtime saat pergantian instans dilakukan.
* **Jawaban 3: B** — *Rasional*: Transparansi referensial adalah karakteristik fungsi murni (*pure function*), di mana fungsi `f(x)` yang menghasilkan `y` dapat secara langsung diganti dengan nilai literal `y` kapan pun dan di mana pun, karena tidak melibatkan manipulasi status tersembunyi.
* **Jawaban 4: C** — *Rasional*: OCP menyatakan bahwa modul harus tertutup untuk modifikasi (*closed for modification*) guna mencegah regresi kode yang telah diuji, namun terbuka untuk perluasan (*open for extension*) menggunakan abstraksi antarmuka atau polimorfisme.
* **Jawaban 5: B** — *Rasional*: Ketika beberapa thread membaca dan memutasi lokasi memori yang sama secara simultan tanpa proteksi ketat, integritas memori runtuh (*race condition*). Jika diproteksi dengan primitive locking secara berlebihan, latensi sistem melonjak (*contention*) atau terjadi saling kunci (*deadlock*).

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

### Buku Referensi Wajib
1. **"Clean Architecture: A Craftsman's Guide to Software Structure and Design"** oleh Robert C. Martin (Uncle Bob), Prentice Hall.
2. **"Design Patterns: Elements of Reusable Object-Oriented Software"** oleh Erich Gamma, Richard Helm, Ralph Johnson, John Vlissides (Gang of Four - GoF), Addison-Wesley.
3. **"Structure and Interpretation of Computer Programs" (SICP)** oleh Harold Abelson dan Gerald Jay Sussman, MIT Press.

### Artikel Akademik & Spesifikasi
* Dijkstra, E. W. (1968). *"Go To Statement Considered Harmful"*. Communications of the ACM, 11(3), 147-148.
* Parnas, D. L. (1972). *"On the Criteria To Be Used in Decomposing Systems into Modules"*. Communications of the ACM, 15(12), 1053-1058.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

Rekayasa Perangkat Lunak bukan semata-mata aktivitas menulis kode, melainkan proses mengelola kompleksitas dan entropi sistem sepanjang siklus hidupnya. Paradigma pemrograman adalah perangkat konseptual mendasar yang menyediakan pola pikir bagaimana state, data, dan kontrol aliran distrukturisasi:

1. **Paradigma Prosedural** memodelkan komputasi sebagai urutan eksekusi step-by-step yang sederhana dan sangat efisien dekat dengan perangkat keras, namun rentan mengalami kekacauan organisasi state pada skala besar.
2. **Paradigma Berorientasi Objek (OOP)** menyatukan data dengan perilaku dalam batas-batas enkapsulasi terproteksi, menyediakan fleksibilitas runtime melalui polimorfisme dinamis (bertenagakan vtable), dan membutuhkan disiplin desain tinggi seperti prinsip SOLID untuk mencegah arsitektur yang kaku.
3. **Paradigma Fungsional (FP)** menghapuskan komplikasi mutasi state melalui keanggunan matematis: *immutability*, *pure functions*, dan *higher-order function composition*, menjadikannya fondasi superior untuk sistem terdistribusi dan konkurensi modern.
4. Perangkat lunak industri modern jarang menerapkan satu paradigma secara dogmatis murni; pendekatan terbaik adalah **pendekatan multi-paradigma hibrida**: logika bisnis diisolasi sebagai fungsi murni (*pure functional core*), sementara orkestrasi status, integrasi I/O, dan antarmuka eksternal diatur menggunakan struktur berorientasi objek yang modular (*OOP/imperative shell*).

---

## SEKSI 17 — GLOSARIUM

* **Coupling**: Derajat ketergantungan antar-modul perangkat lunak. Desain rekayasa yang baik menargetkan *low/loose coupling* agar perubahan pada modul A tidak merusak modul B.
* **Cohesion**: Derajat keterkaitan internal tanggung jawab di dalam sebuah modul. Desain yang baik menargetkan *high cohesion*, di mana seluruh elemen di dalam modul bekerja untuk satu tujuan fungsional yang terfokus.
* **Dynamic Dispatch**: Mekanisme penentuan implementasi metode polimorfik mana yang akan dieksekusi pada saat runtime program berjalan, bukan pada waktu kompilasi.
* **VTable (Virtual Method Table)**: Struktur data berupa array pointer fungsi yang dialokasikan oleh compiler untuk merealisasikan dynamic dispatch pada bahasa OOP.
* **Pure Function**: Fungsi yang nilainya ditentukan hanya oleh argumen inputnya tanpa menyebabkan mutasi status luar atau *observable side-effects*.
* **Immutability**: Keadaan di mana struktur data tidak dapat dimodifikasi setelah proses alokasi dan inisialisasi awal pada memori selesai dilakukan.
* **Technical Debt**: Metafora rekayasa yang menggambarkan konsekuensi biaya refaktorisasi di masa depan akibat memilih solusi jalan pintas yang cepat namun tidak terstruktur saat ini.
* **Side-Effect**: Perubahan apa pun di luar ruang lingkup lokal fungsi yang dipicu oleh eksekusi fungsi tersebut (misal: mutasi memori global, I/O disk, network calls).

---

## SEKSI 18 — CATATAN INSTRUKTUR

### Poin Pedagogis Utama
* **Hindari Perdebatan Dogmatis**: Mahasiswa sering terjebak dalam perdebatan "OOP vs Functional mana yang terbaik". Tegaskan bahwa paradigma hanyalah perkakas dalam kotak alat rekayasa. Diskusikan kasus konkret di mana FP unggul (pemrosesan data paralel) dan di mana OOP unggul (pemodelan subsistem terisolasi seperti GUI Framework atau Game Engine).
* **Demistifikasi OOP Magic**: Saat mengajarkan polimorfisme OOP, jangan hanya menggunakan analogi dunia nyata (seperti Kucing mewarisi Hewan). Bukalah apa yang terjadi di tingkat compiler: jelaskan representasi memori struct, layout memori pointer `vptr`, dan bagaimana lookup `vtable` setara dengan pemanggilan pointer fungsi dalam bahasa C. Ini menghilangkan kebingungan konseptual mahasiswa tingkat menengah.
* **Visualisasi Immutability**: Tunjukkan bahwa immutability tidak selalu berarti menyalin memori secara masif (*naive deep copying*). Jelaskan secara visual konsep *Structural Sharing* pada struktur data persisten (*Persistent Trees*).

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi 1.0.0** (Maret 2026):
  * Rilis modul awal standar kurikulum *Computer Science Core Foundations*.
  * Penyusunan komparasi mendalam tiga paradigma: Prosedural, OOP, dan FP.
  * Penyediaan studi kasus produksi sistem transaksi keuangan berbasis prinsip SOLID dan arsitektur hibrida.
  * Penyusunan asesmen komprehensif dan dekonstruksi teknis VTable.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya**: `CS-FND-0703` — Pemrograman Berorientasi Sistem & Manajemen Memori Manual
* **Modul Saat Ini**: `CS-FND-0801` — Rekayasa Perangkat Lunak & Paradigma Pemrograman
* **Modul Berikutnya**: `CS-FND-0802` — Pola Desain Perangkat Lunak (*Software Design Patterns*) & Refaktorisasi Tingkat Lanjut