# Bab 01: Fondasi Arsitektur Perangkat Lunak Modern
## Module 01: Peran, Tanggung Jawab, dan Pola Pikir Software Architect

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
*   **Menganalisis (C4)** perbedaan mendasar antara peran Senior Software Engineer, Tech Lead, dan Software Architect dalam siklus hidup rekayasa perangkat lunak (*Software Engineering Lifecycle*).
*   **Mengevaluasi (C5)** kebutuhan bisnis dan batasan teknis guna mengekstraksi *Architectural Drivers* (Quality Attributes, Business Constraints, Technical Constraints).
*   **Merancang (C6)** kerangka kerja pengambilan keputusan menggunakan *Architecture Decision Records* (ADR) yang terstruktur dan terukur.
*   **Mengimplementasikan (C3)** *Architectural Fitness Functions* otomatis untuk memvalidasi batasan arsitektur (*architectural boundaries*) pada alur CI/CD.
*   **Menerapkan (C3)** paradigma *Systems Thinking* dalam memitigasi dampak *Conway’s Law* dan *Coupling-Cohesion Trade-offs* pada sistem terdistribusi.

---

### 2. Concept

Arsitektur perangkat lunak bukanlah sekadar kumpulan diagram kotak dan panah, melainkan himpunan **keputusan desain struktural yang memiliki biaya perubahan sangat tinggi (*high cost of change*)**. 

Pola pikir seorang *Software Architect* bergeser dari:
1. *Code-centric* (bagaimana mengimplementasikan fitur `X`) menuju *System-centric* (bagaimana fitur `X` mempengaruhi karakteristik *availability*, *maintainability*, dan latensi sistem secara agregat).
2. *Local optimization* (membuat modul A secepat mungkin) menuju *Global optimization* (memastikan throughput end-to-end tidak terhambat oleh *bottleneck* sinkronisasi data antar-layanan).
3. Pemikiran absolut (mencari "solusi terbaik") menuju analisis komparatif (mencari "himpunan kompromi/trade-off paling optimal").

---

### 3. Why It Matters

Kegagalan mendefinisikan batas dan peran arsitektur secara formal menyebabkan:
*   **Erosi Arsitektur (*Architectural Drift*)**: Implementasi kode menyimpang secara liar dari visi desain awal karena ketiadaan mekanisme penegakan otomatis (*automated governance*).
*   **Biaya Perubahan Eksponensial**: Perubahan skema basis data atau dependensi runtime yang tidak dianalisis batas isolasinya memaksa refaktorisasi masif di puluhan repositori mikro.
*   **Miskomunikasi Lintas-Disiplin**: Kesenjangan antara bahasa objektif bisnis (*time-to-market*, *compliance*, CAC) dan terminologi teknis (*event sourcing*, *garbage collection tuning*, *sharding*).

Architect berperan sebagai jembatan yang mentranslasikan strategi bisnis menjadi topologi teknis, seraya menjaga agar entropi sistem tetap berada di bawah kendali batas toleransi operasional.

---

### 4. What It Is

Arsitektur perangkat lunak mencakup:
*   **Struktur Sistem**: Dekomposisi sistem ke dalam elemen-elemen komputasi, relasi antar-elemen, serta properti yang terekspos ke lingkungan eksternal.
*   **Architectural Drivers**: Kombinasi dari atribut kualitas (*Non-Functional Requirements* / NFRs), batasan organisasi (*business constraints*), batasan teknologi (*technical constraints*), dan tujuan fungsional inti.
*   **Boundary Enforcement**: Mekanisme isolasi yang mencegah kebocoran abstraksi (*leaky abstractions*) antardomain.

Berikut adalah dekonstruksi peran teknis dalam hierarki rekayasa perangkat lunak:

| Dimensi | Senior Software Engineer | Tech Lead | Software Architect |
| :--- | :--- | :--- | :--- |
| **Fokus Utama** | Desain detail komponen, efisiensi kode, algoritma, refaktorisasi modul. | Eksekusi tim, bimbingan teknis, alur CI/CD, kecepatan pengiriman fitur. | Batas sistem makro, atribut kualitas (NFR), analisis kompromi lintas domain, evolusi sistem. |
| **Cakupan Waktu** | Sprint berjalan (1–4 minggu). | Kuartal berjalan (1–3 bulan). | Multi-tahun (1–5 tahun). |
| **Metrik Keberhasilan** | Kualitas kode, cakupan tes, penyelesaian task zero-defect. | Throughput tim, stabilitas deploy harian, resolusi blokade teknis. | Ketahanan sistem, skalabilitas, rasio efisiensi biaya infrastruktur terhadap pertumbuhan bisnis. |

---

### 5. How It Works

Alur operasional seorang Software Architect dalam mentransformasikan ketidakpastian (*ambiguity*) menjadi keputusan arsitektur yang solid:

```
[ Kebutuhan Bisnis & Domain Context ]
                  │
                  ▼
[ Ekstraksi Architectural Drivers ] 
  ├── Business Constraints (Budget, Compliance, Deadlines)
  ├── Technical Constraints (Stack, Legacy Systems, Team Skills)
  └── Quality Attributes / NFRs (Latency, RPO/RTO, Scalability)
                  │
                  ▼
[ Analisis Trade-Off & Alternatif Solusi ]
  ├── ATAM (Architecture Tradeoff Analysis Method)
  └── Evaluasi Skalabilitas, Biaya, Kompleksitas
                  │
                  ▼
[ Pengambilan Keputusan & Dokumentasi (ADR) ]
                  │
                  ▼
[ Kodifikasi Batasan (Fitness Functions / Linters) ]
                  │
                  ▼
[ Validasi Berkelanjutan via Alur CI/CD ]
```

1. **Eksplorasi Driver**: Mengonversi kebutuhan abstrak ("Sistem harus cepat dan aman") menjadi skenario terukur (*Quality Attribute Scenarios*):
   * *Source of stimulus*: Pengguna eksternal.
   * *Stimulus*: Melakukan checkout pada saat *flash sale*.
   * *Artifact*: Transaksi / Order Processing System.
   * *Environment*: Beban puncak (10x trafik normal).
   * *Response*: Transaksi divalidasi dan disimpan.
   * *Response Measure*: Latensi P99 < 800ms; zero drop order.
2. **Eksplorasi Desain**: Mengkaji alternatif pola arsitektur (misal: *Event-Driven Choreography* vs. *Centralized Orchestration*).
3. **Dokumentasi (ADR)**: Menyusun konteks, keputusan yang diambil, dan konsekuensi negatif yang diterima secara sadar.
4. **Automated Governance**: Menanamkan aturan struktural ke dalam kode (misal via unit test struktural atau custom linter) untuk memastikan developer tidak melanggar batasan lapisan (*layer boundaries*).

---

### 6. Architecture Diagram

Diagram berikut mengilustrasikan ruang lingkup dan batasan tanggung jawab *Software Architect* dalam siklus perancangan sistem:

```
+-------------------------------------------------------------------------------+
|                             ENTERPRISE CONTEXT                                |
|  Bisnis: Regulasi (GDPR/PCI-DSS), Finansial (TCO), Target Pasar (Time-to-Mkt)  |
+---------------------------------------+---------------------------------------+
                                        │
                                        ▼
+-------------------------------------------------------------------------------+
|                       SOFTWARE ARCHITECT BOUNDARY                             |
|                                                                               |
|   [ Architectural Drivers ]                                                   |
|   ├── Non-Functional Requirements (SLAs, SLOs, P99 Latency, Availability)     |
|   └── Structural Boundaries (Domain Boundaries, Isolation Zones)              |
|                                                                               |
|   [ Decision & Governance Framework ]                                         |
|   ├── ADR Repository (Architecture Decision Records)                          |
|   └── Fitness Functions (Automated Governance Engine)                         |
+-------------------+---------------------------------------+-------------------+
                    │                                       │
                    ▼                                       ▼
+---------------------------------------+   +-----------------------------------+
|      INTERNAL SYSTEM TOPOLOGY         |   |       DATA & COMMS ARCHITECTURE   |
|  +---------------------------------+  |   |  +-----------------------------+  |
|  |       Domain Layer (Core)       |  |   |  | Asynchronous Message Broker |  |
|  +---------------------------------+  |   |  | (Strict Schema Evolution)   |  |
|                  ▲                    |   |  +-----------------------------+  |
|  +---------------------------------+  |   |                  │                |
|  |     Application / Use Cases     |  |   |                  ▼                |
|  +---------------------------------+  |   |  +-----------------------------+  |
|                  ▲                    |   |  | Polyglot Persistence Layer  |  |
|  +---------------------------------+  |   |  | (EventStore, Relational,    |  |
|  | Infrastructure (Adapters, I/O)  |  |   |  |  Cache, Search Engine)      |  |
|  +---------------------------------+  |   |  +-----------------------------+  |
+---------------------------------------+   +-----------------------------------+
```

---

### 7. Simple Example

Sebuah contoh sederhana pembuatan **Architecture Decision Record (ADR)** untuk menentukan format komunikasi antar-layanan microservices:

```markdown
# ADR 001: Penggunaan gRPC untuk Komunikasi Antar-Layanan Internal

## Status
Diterima (Accepted)

## Konteks
Sistem Checkout memanggil Identity Service dan Inventory Service secara sinkron 
selama proses checkout berlangsung. Protokol REST over HTTP/1.1 JSON saat ini 
menghasilkan overhead serialisasi yang tinggi dan latensi P99 melampaui 1200ms 
pada beban 5.000 RPS. Kami membutuhkan protokol transfer internal yang efisien 
dengan *type-safety* ketat.

## Keputusan
Kami mengadopsi gRPC (HTTP/2 framing, Protobuf serialization) untuk seluruh 
komunikasi sinkron antar-layanan internal backend-to-backend.
REST/JSON hanya dipertahankan di level API Gateway untuk klien eksternal.

## Konsekuensi
Positif:
* Penurunan ukuran payload hingga 65% dibandingkan payload JSON.
* P99 Latency turun menjadi < 350ms pada uji beban 5.000 RPS.
* Kontrak antarmuka (*interface contract*) tervalidasi saat kompilasi via .proto.

Negatif:
* Debugging payload di level jaringan membutuhkan tooling khusus (e.g., Evans, Wireshark).
* Kompleksitas konfigurasi load balancing di layer L7 (perlu Kubernetes gRPC keepalive/Envoy).
```

---

### 8. Practical Production Example

Dalam paradigma modern *Evolutionary Architecture*, seorang Architect tidak hanya membuat dokumen statis, melainkan membuat **Architectural Fitness Functions**: kode otomatis yang menguji apakah arsitektur kode saat ini melanggar aturan struktural (*structural boundaries*).

Di bawah ini adalah implementasi nyata menggunakan Python dengan pustaka `pytest` dan manipulasi AST (Abstract Syntax Tree) untuk menegakkan *Hexagonal Architecture (Ports and Adapters)*: memastikan lapisan **Domain Core** sama sekali tidak mengimpor dari lapisan **Infrastructure** atau **Frameworks**.

#### Struktur Proyek:
```text
src/
├── domain/
│   └── order.py
├── application/
│   └── checkout.py
└── infrastructure/
    └── db_repository.py
tests/
└── architecture/
    └── test_boundaries.py
```

#### Implementasi Fitness Function (`tests/architecture/test_boundaries.py`):

```python
import ast
import os
from pathlib import Path
from typing import List, Tuple

DOMAIN_DIR = Path("src/domain")
FORBIDDEN_IMPORTS = ["src.infrastructure", "infrastructure", "sqlalchemy", "django", "requests"]

def get_imports_from_file(filepath: Path) -> List[Tuple[str, int]]:
    """Mengekstrak seluruh statement import beserta nomor baris dari AST file Python."""
    with open(filepath, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=str(filepath))

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append((node.module, node.lineno))
    return imports

def test_domain_layer_isolation_fitness_function():
    """
    FITNESS FUNCTION:
    Domain Core harus murni (POPO - Plain Old Python Objects).
    Domain DILARANG mengimpor modul dari infrastructure, framework, atau external I/O.
    Pelanggaran akan membatalkan alur build/CI.
    """
    violations = []

    for root, _, files in os.walk(DOMAIN_DIR):
        for file in files:
            if file.endswith(".py") and not file.startswith("__"):
                filepath = Path(root) / file
                imported_modules = get_imports_from_file(filepath)

                for module_name, lineno in imported_modules:
                    for forbidden in FORBIDDEN_IMPORTS:
                        if module_name == forbidden or module_name.startswith(f"{forbidden}."):
                            violations.append(
                                f"Pelanggaran Arsitektur di {filepath}:{lineno} -> "
                                f"Domain mengimpor '{module_name}' yang dilarang."
                            )

    assert not violations, "\n".join(violations)
```

Jika seorang developer mencoba menambahkan baris `import requests` atau `from infrastructure import db` di dalam `src/domain/order.py`, CI Pipeline akan langsung *fail* secara otomatis sebelum kode sempat di-*merge*.

---

### 9. Trade-Off Analysis

Keputusan arsitektural selalu melibatkan kompromi multi-vektor. Tidak ada solusi yang superior di segala sisi.

```
       [ Skalabilitas / Otonomi ]
                 /\
                /  \
               /    \  <--- Trade-off Boundary
              /      \
             /________\
[ Konsistensi Data ]  [ Kompleksitas Operasional ]
```

Matriks evaluasi gaya arsitektur berdasarkan atribut kualitas:

| Karakteristik | Arsitektur Monolith Modular | Microservices Terdistribusi | Event-Driven Architecture (EDA) |
| :--- | :--- | :--- | :--- |
| **Kompleksitas Deploy** | **Rendah**: Single artifact, atomik deploy. | **Tinggi**: Orkestrasi multi-container, canary matrix. | **Sangat Tinggi**: Manajemen versi event, deduplikasi. |
| **Konsistensi Data** | **Tinggi (ACID)**: RDBMS Transactions lokal. | **Rendah (BASE)**: Dual-write, Saga pattern, Sagas compensation. | **Eventual Consistency**: Reconciler engine, out-of-order events. |
| **Batas Kegagalan (*Blast Radius*)** | **Tinggi**: Memory leak atau infinite loop dapat mematikan seluruh app. | **Rendah-Sedang**: Terisolasi di service level, jika circuit breaker terpasang. | **Sangat Rendah**: Backpressure tertahan di broker antrean. |
| **Overhead Kognitif Tim** | **Rendah**: Mudah melacak stack trace secara end-to-end. | **Tinggi**: Membutuhkan distributed tracing (OpenTelemetry, Jaeger). | **Tinggi**: Jalur eksekusi asinkron, non-linear flow. |

---

### 10. Best Practices & Guidelines

1. **Prinsip *Last Responsible Moment***: Jangan membuat keputusan arsitektural yang mahal terlalu cepat sebelum variabel kebutuhan bisnis dan beban sistem terdefinisi secara jelas.
2. **Kendalikan Hukum Conway (*Reverse Conway Maneuver*)**: Susun struktur tim sesuai dengan target arsitektur yang diinginkan. Jika Anda menginginkan subsistem yang independen, pisahkan tim secara fungsional berdasarkan domain *bounded context*.
3. **Dokumentasikan Konsekuensi Negatif pada ADR**: Keputusan yang baik adalah keputusan yang menyadari kelemahannya sendiri dan mendokumentasikan langkah mitigasinya sejak awal.
4. **Hindari *Technology-Driven Architecture***: Jangan memilih Kafka, Kubernetes, atau Rust hanya karena popularitas. Justifikasikan setiap komponen teknologi melalui *Architectural Driver* yang konkret.

---

### 11. Anti-Patterns & Common Pitfalls

#### 1. The Ivory Tower Architect
*   **Gejala**: Architect memproduksi dokumen Word/PDF tebal berisi diagram konseptual tanpa pernah menyentuh basis kode, tidak pernah menjalankan profiling sistem, dan tidak pernah berdiskusi dengan tim implementasi.
*   **Dampak**: Desain tidak realistis, diabaikan oleh engineer, dan tim kehilangan kepercayaan terhadap inisiatif arsitektur.
*   **Solusi**: Architect wajib mengalokasikan minimal 20-30% waktu untuk *hands-on code review*, *prototyping*, dan memvalidasi langsung performa sistem di environment staging/production.

#### 2. Premature Distributed Architecture
*   **Gejala**: Memecah aplikasi berukuran kecil (kurang dari 10.000 pengguna harian) ke dalam 30 mikroservis independen dengan basis data terpisah.
*   **Dampak**: Biaya latensi jaringan membengkak, koordinasi distributed transaction (2PC/Saga) menyita 80% kapasitas tim, *cloud cost* melonjak tanpa peningkatan efisiensi.
*   **Solusi**: Mulai dengan *Modular Monolith*. Ekstraksi service hanya jika terdapat kebutuhan isolasi resource perangkat keras yang drastis atau independensi tim yang masif.

#### 3. Vendor-Lock Blindness
*   **Gejala**: Merancang domain logika inti yang bergantung langsung pada pustaka atau SDK proprietary cloud provider tertentu.
*   **Dampak**: Mustahil melakukan migrasi infrastruktur atau menjalankan pengujian unit testing secara luring (*offline*).
*   **Solusi**: Isolasi ketergantungan eksternal di balik layer adapter (*Hexagonal Ports and Adapters*).

---

### 12. Performance & Scalability Considerations

Seorang architect harus memperhitungkan implikasi arsitektur terhadap batas fisik mesin dan jaringan:
*   **Network I/O vs. In-Memory**: Latensi jaringan lintas-datacenter berkisar antara 10ms–50ms, sementara akses RAM berada di kisaran 100ns (faktor perbedaan 100.000x). Setiap batasan modular yang melewati batas proses (*process boundary*) memperkenalkan latensi yang tidak dapat dieliminasi oleh optimasi algoritma lokal.
*   **Amdahl’s Law**: Peningkatan throughput sistem melalui konkurensi dibatasi oleh fraksi kode yang wajib dijalankan secara sekuensial. Arsitek harus mengidentifikasi dan meminimalkan operasi *locking* global serta transaksi serial pada basis data relasional.
*   **Backpressure Handling**: Sistem yang dapat menangani skalabilitas tinggi harus mendesain kapasitas penolakan beban secara anggun (*graceful degradation*) melalui *rate-limiting*, *load shedding*, dan *circuit breakers*.

---

### 13. Security Considerations

Keamanan arsitektur wajib diintegrasikan sejak perancangan awal (*Security by Design*), bukan ditambahkan sebagai lapisan luar di akhir implementasi:
*   **Threat Modeling (Metodologi STRIDE)**:
    *   *Spoofing*: Identitas service-to-service harus diverifikasi menggunakan mTLS dengan rotasi sertifikat otomatis (misalnya SPIFFE/SPIRE).
    *   *Tampering*: Integritas payload asinkron harus diverifikasi dengan signature kriptografis jika melewati zona sekuriti berbeda.
    *   *Repudiation*: Audit trail immutable pada log transaksi bisnis.
    *   *Information Disclosure*: Enkripsi pada saat diam (*at-rest*) menggunakan envelope encryption, dan saat berpindah (*in-transit*).
    *   *Denial of Service*: Throttling pada layer batas (*edge/ingress layer*).
    *   *Elevation of Privilege*: Menegakkan prinsip *Least Privilege* di tingkat IAM role container dan koneksi DB user.
*   **Zero Trust Architecture**: Jangan pernah mempercayai paket data hanya karena ia berasal dari dalam satu Virtual Private Cloud (VPC). Setiap komunikasi RPC/HTTP internal wajib melalui autentikasi dan otorisasi eksplisit.

---

### 14. Monitoring & Observability

Observabilitas bukan sekadar pengumpulan log, melainkan kemampuan menurunkan status internal sistem berdasarkan output telemetri eksternal:
*   **The Three Pillars Correlation**:
    *   **Logs**: Terstruktur dalam format JSON dengan injeksi otomatis `trace_id` dan `span_id`.
    *   **Metrics**: Menggunakan format counter, gauge, dan histogram berbasis Prometheus untuk mendeteksi saturasi sumber daya, rasio eror (5xx), dan latensi kuantil (P50, P95, P99).
    *   **Distributed Traces**: Memanfaatkan OpenTelemetry SDK untuk melacak alur *causal graph* pemanggilan dependensi di seluruh layanan backend.
*   **Golden Signals (Google SRE Framework)**:
    1. *Latency*: Waktu yang dibutuhkan untuk melayani request.
    2. *Traffic*: Ukuran permintaan yang masuk ke sistem (misal: RPS).
    3. *Errors*: Rasio request yang gagal.
    4. *Saturation*: Tingkat kepenuhan resource yang paling dibatasi (CPU, Memory, DB Connection Pool).

---

### 15. Edge Cases & Failure Modes

Arsitek harus mendesain sistem dengan asumsi bahwa **kegagalan adalah keniscayaan**:
*   **Split-Brain Scenario**: Pada sistem terdistribusi dengan kluster konsensus (misal: Raft/Zookeeper), partisi jaringan dapat memotong node menjadi dua kubu. Arsitektur harus secara eksplisit mendefinisikan perilaku: menolak penulisan baru (*favor Consistency*) atau menerima penulisan dengan risiko rekonsiliasi inkonsistensi (*favor Availability*).
*   **Cascading Failures**: Satu dependensi lambat pada downstream service dapat menghabiskan thread pool upstream service hingga memicu keruntuhan total ekosistem mikroservis.
    *   *Mitigasi*: Wajib menetapkan batas *timeout* yang agresif, *deadline propagation*, dan isolasi *bulkhead*.
*   **Poison Pill Message**: Pesan dalam antrean Kafka/RabbitMQ yang selalu gagal diproses dan membuat consumer crash berulang kali.
    *   *Mitigasi*: Mekanisme Dead Letter Queue (DLQ) otomatis setelah $N$ kali percobaan retry, disertai alert ke on-call engineer.

---

### 16. Testing & Validation Strategies

Pengujian arsitektur melampaui pengujian fungsional konvensional:

```
          / \
         /   \         Chaos Engineering (Chaos Mesh, Gremlin)
        /-----\
       /       \       Performance & Load Testing (k6, Locust)
      /---------\
     /           \     Architectural Fitness Functions (ArchUnit, AST checks)
    /-------------\
   /               \   Integration & Contract Testing (Pact)
  /-----------------\
 /                   \ Unit Testing (TDD, Pure Logic)
-----------------------
```

*   **Contract Testing**: Memverifikasi antarmuka komunikasi antar-layanan secara independen tanpa perlu menyalakan seluruh sistem di lingkungan lokal (misal: Consumer-Driven Contracts via Pact).
*   **Chaos Engineering**: Menginjeksi kegagalan jaringan secara terencana (misal: mematikan node worker, menambahkan delay latency 2000ms pada pod database) di environment staging/canary untuk menguji apakah sistem dapat melakukan pemulihan mandiri (*self-healing*).

---

### 17. Real-World Case Study

#### Skenario: Modernisasi Sistem Monolith FinTech "PayFast"
*   **Masalah**: PayFast memiliki core system berbasis monolitik PHP yang memproses seluruh transaksi pembayaran, otentikasi, pendaftaran merchant, dan reporting rekonsiliasi. Pada periode promosi tanggal kembar (11.11), query laporan akuntansi yang berat mengunci tabel transaksi, mengakibatkan kegagalan checkout global selama 45 menit.
*   **Analisis Arsitektural**:
    *   *Driver*: Menjaga Availability transaksi pembayaran tetap 99.99%, latensi checkout < 500ms, terlepas dari aktivitas analitik atau pendaftaran pengguna.
    *   *Identifikasi Flaw*: Coupling tinggi antara domain *Transactional Processing* (OLTP) dan domain *Analytical Reporting* (OLAP) di satu basis data monolitik tunggal.
*   **Intervensi Software Architect**:
    1. Mengisolasi domain pembayaran menggunakan pola **Strangler Fig Pattern**.
    2. Memisahkan jalur baca dan tulis (*Command Query Responsibility Segregation* / CQRS).
    3. Mengimplementasikan *Change Data Capture* (Debezium + Kafka) dari basis data utama ke read-replica / Elasticsearch khusus untuk tim pelaporan dan analytics.
*   **Hasil**: Beban transaksi checkout terbebas sepenuhnya dari interferensi query analitik. Ketersediaan pembayaran mencapai 99.995% pada event diskon berikutnya dengan penurunan load CPU basis data utama sebesar 60%.

---

### 18. Exercises & Challenges

1.  **Latihan Skenario Driver Ekstraksi**:
    Sebuah aplikasi *Ride-Hailing* ingin memperluas layanannya ke pelacakan pengemudi secara real-time. Bisnis menuntut:
    * 500.000 pengemudi mengirimkan koordinat GPS setiap 3 detik.
    * Penumpang dapat melihat posisi pengemudi dengan keterlambatan maksimal 5 detik.
    * Sistem harus tahan terhadap lonjakan trafik di jam sibuk tanpa kehilangan koneksi.
    * *Tugas*: Tuliskan 3 *Quality Attribute Scenarios* lengkap (Source, Stimulus, Artifact, Environment, Response, Response Measure) untuk kebutuhan tersebut.

2.  **Hands-on Fitness Function Challenge**:
    *   Buatlah sebuah script pengujian otomatis menggunakan bahasa pemrograman pilihan Anda (misal: Node.js, Go, Python, atau Java via ArchUnit) yang memindai codebase Anda dan menggagalkan eksekusi jika ada komponen di dalam folder `controller` atau `handlers` yang memanggil `database.query()` secara langsung tanpa melalui layer `service` atau `usecase`.

---

### 19. Key Takeaways & Summary

*   Arsitektur perangkat lunak adalah pengelolaan kumpulan keputusan strategis yang berbiaya mahal jika diubah di masa depan.
*   Pola pikir arsitek mengedepankan **analisis kompromi (*trade-off analysis*)** dibandingkan pencarian solusi absolut; arsitek mengevaluasi dampak global di atas optimasi lokal.
*   *Architectural Drivers* yang terdiri atas Quality Attributes, Business Constraints, dan Technical Constraints merupakan fondasi dari seluruh keputusan desain struktural.
*   Keputusan arsitektur harus didokumentasikan secara formal via **Architecture Decision Records (ADR)** dan ditegakkan secara mekanis via **Architectural Fitness Functions**.
*   Menghargai batasan organisasi dan komunikasi (*Conway’s Law*) sama krusialnya dengan mendesain topologi teknis dan partisi jaringan.

---

### 20. References & Further Reading

*   Bass, L., Clements, P., & Kazman, R. (2021). *Software Architecture in Practice (4th Edition)*. Addison-Wesley Professional.
*   Ford, N., Parsons, R., Kua, P., & Sadalage, P. (2021). *Building Evolutionary Architectures: Automated Software Governance (2nd Edition)*. O'Reilly Media.
*   Richards, M., & Ford, N. (2020). *Fundamentals of Software Architecture: An Engineering Approach*. O'Reilly Media.
*   Nygard, M. T. (2018). *Release It!: Design and Deploy Production-Ready Software (2nd Edition)*. Pragmatic Bookshelf.
*   Architecture Decision Record Repository Standards: [https://adr.github.io/](https://adr.github.io/)