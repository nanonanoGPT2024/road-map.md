# BAB 10: Architectural Governance & Leadership
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Merancang dan Mengimplementasikan Automated Architecture Fitness Functions** menggunakan *Architecture-as-Code* (ArchUnit, Open Policy Agent/OPA) di dalam *deployment pipeline* skala enterprise.
- **Mengoperasionalkan Dynamic Architectural Governance** dengan memadukan model *Policy Enforcement Point* (PEP) dan *Policy Decision Point* (PDP) untuk menjaga integritas *bounded context* dan batasan domain.
- **Mengorkestrasi Transformasi Organisasi Berbasis Pola Team Topologies & Inverse Conway Maneuver** guna meminimalkan *cognitive load* tim rekayasa dan mengeliminasi *architectural drift*.
- **Membangun Sistem Kuantifikasi & Remediasi Technical Debt** berbasis metrik objektif (*Instability*, *Abstractness*, *Distance from the Main Sequence*, dan analisis *Code Churn Hotspot*).
- **Menjalankan Architecture Review Board (ARB) Federasi** yang beroperasi secara asinkron dengan *Service Level Agreement* (SLA) terukur untuk *waiver* dan mitigasi risiko arsitektur kritis.

---

### 2. Prerequisite
Peserta wajib memiliki pemahaman mendalam dan pengalaman praktis pada:
- **Domain-Driven Design (DDD)**: Konsep *Strategic Design* (*Bounded Context*, *Context Mapping*, *Ubiquitous Language*).
- **Modern CI/CD Pipelines**: GitLab CI, GitHub Actions, atau Jenkins Enterprise (pemahaman mendalam tentang *gating*, *exit codes*, dan *artifact promotion*).
- **Core Architectural Patterns**: Hexagonal/Ports & Adapters, Clean Architecture, Event-Driven Architecture, Microservices.
- **Object-Oriented & Distributed Systems Internals**: Pemrograman tingkat lanjut (Java/Go/TypeScript), *reflection API*, struktur metadata AST (*Abstract Syntax Tree*), serta abstraksi *Infrastructure-as-Code* (Terraform, Kubernetes manifest).

---

### 3. Concept & Internal Architecture

Architectural Governance konvensional sering kali gagal pada skala enterprise karena mengandalkan komite manual (*gated reviews* birokratis) yang menjadi *bottleneck* pengiriman perangkat lunak. Pada arsitektur produksi modern, tata kelola arsitektur ditransformasikan dari *human-centric policy enforcement* menjadi **Continuous Automated Governance**.

```
+-----------------------------------------------------------------------------------+
|                        ENTERPRISE REPOSITORY / VCS                                |
+-----------------------------------------------------------------------------------+
                                         │
                                   [git push]
                                         ▼
+-----------------------------------------------------------------------------------+
|                           CONTINUOUS INTEGRATION (PEP)                            |
|                                                                                   |
|  +--------------------+   +-----------------------+   +------------------------+  |
|  |   Static AST &     |   | Architecture Gating   |   | Infrastructure Policy  |  |
|  | Structural Linter  |   | (ArchUnit / NetArch)  |   | (OPA / Conftest)       |  |
|  +--------------------+   +-----------------------+   +------------------------+  |
|            │                          │                           │               |
+------------┼──────────────────────────┼───────────────────────────┼---------------+
             ▼                          ▼                           ▼
+-----------------------------------------------------------------------------------+
|                     POLICY DECISION POINT (PDP) EVALUATION                        |
|                                                                                   |
|  [Fitness Functions Evaluation Engine]                                            |
|  - Dependency Rule Verification (Layers, Onion, Hexagonal)                        |
|  - Microservice Isolation Verification (No direct cross-domain DB access)         |
|  - Non-Functional Attributes (P99 SLA, Thread-Safety, Memory Allocations)        |
+-----------------------------------------------------------------------------------+
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 │ Valid                                         │ Violations Detected
                 ▼                                               ▼
+---------------------------------+             +---------------------------------+
| PIPELINE PROCEED: ARTIFACT PROMO|             | PIPELINE FAILURE (Exit 1)       |
|                                 |             |                                 |
| - Build Container Images        |             | - Emit Metric to Dashboard      |
| - Deploy to Ephemeral Env       |             | - Block Merge Request           |
| - Register Architecture Spec    |             | - Route Exception to ARB Portal |
+---------------------------------+             +---------------------------------+
```

#### Komponen Kunci Arsitektur Governance Produksi

1. **Fitness Functions Engine**: Kumpulan pengujian otomatis terprogram (*automated tests*) yang mengevaluasi apakah karakteristik arsitektur sistem (modularitas, stabilitas, performa, keamanan) menyimpang dari batasan yang telah ditetapkan.
2. **Policy Enforcement Point (PEP)**: Titik intervensi otomatis dalam siklus hidup rekayasa perangkat lunak (contoh: Git Pre-commit hook, CI runner, Admission Controller Kubernetes) yang bertugas mengeksekusi inspeksi dan memblokir alur jika terdeteksi anomali.
3. **Policy Decision Point (PDP)**: Mesin penilai kebijakan (seperti OPA atau modul ArchUnit) yang menerima representasi sistem (AST, metadata dependensi, *manifest schema*) dan mengembalikannya dalam keputusan biner: `PERMIT` atau `DENY`.
4. **Architectural Metric Registry**: *Time-series datastore* yang memetakan evolusi kopling (*coupling*), kohesi (*cohesion*), dan rasio *technical debt* dari waktu ke waktu untuk menghindari degradasi struktural sistem.

---

### 4. Why & What

| Dimensi | Governance Manual / Tradisional | Continuous Architecture-as-Code |
| :--- | :--- | :--- |
| **Metode Verifikasi** | Review dokumen PDF/Word di akhir fase rilis (*Phase-Gate*). | *Automated Fitness Functions* di setiap *Pull Request*. |
| **Feedback Loop** | Berminggu-minggu hingga berbulan-bulan (Siklus lambat, *high friction*). | Menit (Terintegrasi langsung dalam siklus CI/CD). |
| **Skalabilitas** | Melemah seiring bertambahnya tim (*ARB bottleneck*). | Linear & deterministik, terdistribusi ke seluruh *repo*. |
| **Konteks Deviasi** | Bersifat interpretatif dan bergantung pada subjektivitas *reviewer*. | Berbasis aturan tegas (*declarative rules* / *AST inspection*). |
| **Biaya Remediasi** | Sangat mahal (Dilakukan setelah kode mencapai tahap *staging/prod*). | Sangat murah (Terdeteksi saat *commit* lokal atau uji CI). |

#### Apa yang Diatur?
1. **Structural Boundaries**: Isolasi *Core Domain*, *Application Layer*, *Domain Layer*, dan *Infrastructure Layer*. Memastikan bahwa *Infrastructure Layer* bergantung pada *Domain Layer*, bukan sebaliknya (Inversi Dependensi).
2. **Inter-Service Communication**: Mencegah integrasi database silang (*shared-database anti-pattern*) antar *bounded context*.
3. **Evolutionary Architecture Attributes**: Membatasi kompleksitas siklomatis (*Cyclomatic Complexity*), tingkat keparahan kopling (*Afferent/Efferent Coupling*), dan kompatibilitas skema kontrak API (menggunakan Semantic Versioning dan *breaking-change prevention*).

---

### 5. How (Workflow Detail)

Alur kerja tata kelola arsitektur tingkat lanjut berjalan melalui lima fase deterministik:

```
[Developer] 
    │ (1) Menulis kode fitur & melanggar batas arsitektur 
    │     (misal: Domain class memanggil Spring Framework / SQL Driver secara langsung)
    ▼
[Git Push / Pull Request]
    │ (2) Memicu Pipeline CI/CD
    ▼
[CI Stage: Arch-Gating]
    │ (3) Eksekusi Test Runner (ArchUnit) & OPA Linter
    ├───────► Evaluasi AST via Bytecode Inspection
    ├───────► Verifikasi Boundary Context via Dependency Graph
    ▼
[Evaluasi Hasil PDP]
    ├───► [PASS] ──► Tahap Compile, Unit Test, & Container Build berlanjut.
    └───► [FAIL] ──► PIPELINE TERMINATED.
            │
            ├─► Cetak Diagnostic StackTrace (Nama file, baris kode pelanggar, aturan dilanggar).
            ├─► Push event pelanggaran ke Central Governance Metrics Dashboard.
            └─► Opsi: Pengajuan Form Architectural Waiver jika ada *business urgency*.
```

#### Tahapan Implementasi di Tim Enterprise:
1. **Fase Definisi**: Enterprise Architect bersama Domain Architect menetapkan *Architectural Guardrails* dalam bentuk kode deklaratif.
2. **Fase Integrasi**: Menyematkan *runner* pengujian arsitektur ke dalam templat dasar CI/CD enterprise (misal: *Golden Pipeline*).
3. **Fase Baseline & Exemption**: Proyek eksisting (*legacy*) diberikan *baseline exception* sementara untuk mencegah kegagalan pipeline seketika (*fail-soft*), disertai target tanggal depresiasi utang teknis (*time-bound technical debt*).
4. **Fase Penegakan Ketat (*Strict Enforcement*)**: Menghapus toleransi pada modul baru. Pelanggaran aturan berstatus *P0 blocker* untuk *merge pull request*.

---

### 6. Analogy & Diagram ASCII

#### Analogi Dunia Nyata: Sistem Kode Bangunan Sipil Modern vs Inspektur Gedung Manual
Governance tradisional bertindak seperti inspektur bangunan independen yang baru datang saat gedung 50 lantai sudah selesai dibangun, lalu meminta dinding lantai 2 dirobohkan karena melanggar jalur evakuasi kebakaran.

Continuous Governance beroperasi layaknya material konstruksi pintar bersensor (*smart building materials*) dan sistem fabrikasi terkomputerisasi: jika baja profil berukuran di luar batas toleransi beban struktural dipasang pada lantai 10, sistem derek otomatis terkunci seketika (*fail-fast*) dan menolak mengangkat beban tersebut hingga spesifikasi struktural terpenuhi.

```
       CONWAY'S LAW RE-ALIGNMENT: INVERSE CONWAY MANEUVER
       ==================================================

  Target Software Architecture          Required Organization Structure
  (Loosely Coupled Microservices)       (Decoupled Cross-Functional Teams)

  +-----------------------------+       +-----------------------------+
  | Order Context               | <---> | Team Alpha (Stream-Aligned) |
  | (Independent DB, Event Pub) |       | (Dev, QA, Sec, PO)          |
  +-----------------------------+       +-----------------------------+
                 ▲                                     ▲
                 │ (Asynchronous Messaging)            │ (API Contract)
                 ▼                                     ▼
  +-----------------------------+       +-----------------------------+
  | Inventory Context           | <---> | Team Beta (Stream-Aligned)  |
  | (Independent DB, Event Sub) |       | (Dev, QA, Sec, PO)          |
  +-----------------------------+       +-----------------------------+
                 │                                     │
                 └──────────────────┬──────────────────┘
                                    │
                                    ▼
       +---------------------------------------------------------+
       | PLATFORM ARCHITECTURE TEAM                              |
       | - Menyediakan Continuous Governance Tools (ArchUnit/OPA)|
       | - Menyediakan Observability Platform & Messaging Fabric |
       | - Mengurangi Cognitive Load Stream-Aligned Teams       |
       +---------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### Implementasi Praktis 1: ArchUnit untuk Hexagonal Architecture
Contoh implementasi pengujian arsitektur menggunakan **ArchUnit** pada Java/Spring Boot enterprise untuk menegakkan aturan *Hexagonal Architecture*.

```java
package com.enterprise.architecture.governance;

import com.tngtech.archunit.core.domain.JavaClasses;
import com.tngtech.archunit.core.importer.ClassFileImporter;
import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.lang.ArchRule;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.classes;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;
import static com.tngtech.archunit.library.Architectures.onionArchitecture;

public class HexagonalArchitectureFitnessTest {

    private static JavaClasses importedClasses;

    @BeforeAll
    public static void setUp() {
        importedClasses = new ClassFileImporter()
                .withImportOption(ImportOption.Predefined.DO_NOT_INCLUDE_TESTS)
                .importPackages("com.enterprise.app");
    }

    @Test
    @DisplayName("Layer Domain tidak boleh bergantung pada infrastruktur atau framework luar")
    public void domainLayerShouldBeIsolated() {
        ArchRule domainIsolationRule = noClasses()
                .that().resideInAPackage("..domain..")
                .should().dependOnClassesThat()
                .resideInAnyPackage("org.springframework..", "javax.persistence..", "jakarta.persistence..", "..infrastructure..");

        domainIsolationRule.check(importedClasses);
    }

    @Test
    @DisplayName("Infrastruktur Adapter harus mengimplementasikan interface dari Port")
    public void adaptersShouldImplementPorts() {
        ArchRule portsAndAdaptersRule = classes()
                .that().resideInAPackage("..infrastructure.adapters..")
                .should().toImplement(classes().that().resideInAPackage("..application.ports.."));

        // Validasi dependensi unidirectional
        portsAndAdaptersRule.allowEmptyShould(false).check(importedClasses);
    }

    @Test
    @DisplayName("Memastikan Arsitektur Onion Terpenuhi Secara Holistik")
    public void verifyOnionArchitectureHierarchy() {
        ArchRule onionRule = onionArchitecture()
                .domainModels("com.enterprise.app.domain.model..")
                .domainServices("com.enterprise.app.domain.service..")
                .applicationServices("com.enterprise.app.application.usecases..")
                .adapter("persistence", "com.enterprise.app.infrastructure.persistence..")
                .adapter("rest", "com.enterprise.app.infrastructure.rest..");

        onionRule.check(importedClasses);
    }

    @Test
    @DisplayName("Mencegah Injeksi Lapangan (Field Injection) - Wajib Menggunakan Constructor Injection")
    public void noFieldInjectionAllowed() {
        ArchRule constructorInjectionRule = noClasses()
                .should().dependOnClassesThat().haveSimpleName("Autowired")
                .because("Dependency Injection harus melalui Constructor untuk memastikan Testability dan Immutability.");

        constructorInjectionRule.check(importedClasses);
    }
}
```

#### Implementasi Praktis 2: Open Policy Agent (Rego) untuk Tata Kelola Microservice
Kebijakan OPA untuk memblokir pendaftaran konfigurasi mikroservis di Kubernetes/Service Mesh jika mikroservis mencoba mengekspos port database atau menyalahi aturan *bounded context* (misal: memetakan volume host secara ilegal).

```rego
package architecture.governance

default allow = false

# Definisi pelanggaran struktural
violations[msg] {
    input.kind == "Deployment"
    some i
    container := input.spec.template.spec.containers[i]
    
    # Aturan 1: Database sidecar dilarang keras di dalam domain microservice pod
    # (Pencegahan shared local state / shared storage)
    regex.match(".*(mysql|postgres|oracle|mongo).*", container.image)
    msg := sprintf("Pelanggaran Batasan Arsitektur: Database image '%v' dilarang dideploy sebagai sidecar pada Service '%v'. Gunakan Dedicated Managed Service.", [container.image, input.metadata.name])
}

violations[msg] {
    input.kind == "Deployment"
    some i
    volume := input.spec.template.spec.volumes[i]
    
    # Aturan 2: Mencegah HostPath Volume (Merusak prinsip stateless service)
    volume.hostPath
    msg := sprintf("Pelanggaran Immutability: Microservice '%v' mengikat HostPath volume '%v'. Stateful storage dilarang di compute-tier.", [input.metadata.name, volume.name])
}

# PDP Directive: Izinkan deployment hanya jika TIDAK ADA violation
allow {
    count(violations) == 0
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
Bank Sentral / Institusi Finansial Multinasional (Tier-1 Enterprise) dengan lebih dari 450 pengembang terbagi dalam 65 tim *stream-aligned*, mengelola 300+ layanan mikro.

#### Permasalahan Skala Besar
1. **Architectural Drift**: Tim pengembang secara diam-diam mulai mengakses replika database modul pembayaran (*Payment Service*) secara langsung dari modul analitik (*Analytics Service*) demi efisiensi query, merusak *domain boundaries* dan menyebabkan *distributed locking* serta insiden P1 beruntun pada saat pemrosesan *payroll* nasional.
2. **Review Bottleneck**: Komite ARB pusat memerlukan waktu 3 minggu untuk memvalidasi satu *Change Request*, menghambat *Time-to-Market*.
3. **Kerapuhan Sistem (*Cyclic Dependencies*)**: Modul Akun bergantung pada Modul Transfer, yang secara tidak langsung bergantung kembali pada Modul Akun lewat sistem audit lama.

#### Strategi Solusi: Automated Governance & Inverse Conway Maneuver
1. **Restrukturisasi Organisasi**: 
   - Membentuk **Platform Architecture Team** yang merancang alat tata kelola otomatis dan bertindak sebagai *Enabling Team*.
   - Mengalihkan otoritas kepemilikan domain ke tim *stream-aligned* menggunakan pola tata kelola desentralisasi (*Federated ARB*).
2. **Implementasi Continuous Architecture Verification**:
   - Memasukkan **ArchUnit** pada setiap repositori berbasis Java dan **spectral/linter** untuk *OpenAPI contracts* di repositori TypeScript/Go.
   - Pemasangan OPA di tahap *pre-deployment* ArgoCD untuk memvalidasi *network security policy* antar *bounded context*.
3. **Pemberian Kuota Technical Debt (SLA Remediasi)**:
   - Jika metrik *Distance from the Main Sequence* ($D = |A + I - 1|$) sebuah repositori melebihi ambang batas $0.7$, sistem secara otomatis membekukan pembuatan fitur baru pada sprint berikutnya dan mewajibkan alokasi 30% sprint capacity untuk *refactoring*.

#### Hasil Terukur (Metrics & Outcomes):
- **Lead Time for Changes**: Turun dari rata-rata 38 hari menjadi 4 hari kerja.
- **Cross-Domain Database Direct Querying**: Mencapai **0 kasus** dalam 90 hari pasca integrasi ArchUnit + OPA gate.
- **Incident Escalation Rate**: Insiden kritis P1 terkait *locking database cross-boundary* turun sebesar **94%**.

---

### 9. Trade-offs

Setiap keputusan governance yang ketat memperkenalkan serangkaian konsekuensi yang harus dikalkulasi oleh seorang Enterprise/Lead Architect.

```
       RIGID GOVERNANCE                           CHAOTIC VELOCITY
 (100% Policy-as-Code Enforced)               (Zero Governance / Freedom)
  ◄─────────────────────────────────────────────────────────────────────►
  [+] Deterministic Compliance                 [+] Extremely Fast Prototyping
  [+] Zero Architectural Drift                 [-] High Accumulation of Debt
  [-] Slower Dev Feedback Loop                 [-] Massive Outages at Scale
  [-] Increased Initial Friction               [-] Unmaintainable Monoliths
```

| Parameter | High Automation (Strict Enforcement) | Low/Moderate Automation (Advisory Only) |
| :--- | :--- | :--- |
| **Developer Velocity (Short-term)** | Tertekan; developer terblokir jika belum memahami batasan layer arsitektur. | Sangat tinggi; kode langsung di-merge tanpa verifikasi arsitektur. |
| **System Maintainability (Long-term)**| Terjaga pada status optimal; batas arsitektur tidak terdegradasi. | Menurun drastis; terjadi *architectural erosion* (*Big Ball of Mud*). |
| **CI/CD Pipeline Latency** | Bertambah (peningkatan 1-3 menit untuk *bytecode reflection analysis*). | Cepat; hanya menjalankan kompilasi dan *unit testing* dasar. |
| **Infrastructure & Tooling Cost** | Memerlukan investasi komputasi CI/CD dan lisensi dashboard governance. | Minimal pada awalnya, namun melambung saat restrukturisasi sistem masif. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Over-Constraining Structural Rules Terlalu Cepat
- **Gejala**: Pipeline gagal total di hampir seluruh repositori legacy saat *rule* baru dirilis. Produktivitas pengembang terhenti (*developer gridlock*).
- **Akar Masalah**: Memperlakukan aturan arsitektur baru secara retrospektif ke *legacy codebase* tanpa mekanisme *gradual deprecation*.
- **Solusi**: Terapkan mekanisme *Ignored Packages Baseline* atau *Freezing Rules* (seperti `FreezingArchRule` pada ArchUnit) yang hanya mencatat pelanggaran pada kode lama, tetapi memblokir penambahan pelanggaran baru pada kode yang baru ditulis.

#### Kesalahan 2: The "Ghost Waiver" (Zombie Exception Syndrome)
- **Gejala**: Pengecualian arsitektur (*waiver*) disetujui untuk rilis darurat, namun pengecualian tersebut tetap aktif selama bertahun-tahun di dalam codebase.
- **Akar Masalah**: *Waiver* tidak memiliki tanggal kedaluwarsa yang diverifikasi oleh mesin secara otomatis.
- **Solusi**: Tambahkan metadata waktu pada deklarasi pengecualian:
```java
// Anti-Pattern: Pengecualian permanen tanpa limitasi waktu
@ArchIgnore 
public class LegacyIntegrationService { ... }

// Best Practice: Pengecualian dengan batas kedaluwarsa terprogram
@ArchitecturalWaiver(
    reason = "DEVOPS-4102: Migrasi broker belum selesai",
    approvedBy = "LeadArchitect",
    expiryDate = "2025-06-30"
)
public class TemporaryBrokerBridge { ... }
```
Gunakan test runner khusus untuk membaca nilai `expiryDate`. Jika tanggal hari ini melampaui tanggal tersebut, gagalkan *build* secara otomatis.

#### Kesalahan 3: Fragmentasi Kebijakan (Decoupled Policy vs Reality)
- **Gejala**: Dokumen arsitektur di Confluence menyatakan arsitektur bersifat *Event-Driven*, namun di level kode 80% komunikasi dilakukan melalui pemanggilan synchronous REST HTTP antar-servis.
- **Akar Masalah**: Arsitek hidup dalam "menara gading", memproduksi diagram tanpa mengaitkannya dengan *Policy-as-Code*.
- **Solusi**: Hapus dokumen pasif. Jadikan kode dan *fitness functions* sebagai satu-satunya *Single Source of Truth* arsitektur (*Living Architecture*).

---

### 11. Best Practices (Production Checklist)

#### Pre-Commit & Local Dev
- [ ] Install linter lokal dan git pre-commit hook untuk memvalidasi *package structural integrity* sebelum kode di-push.
- [ ] Sediakan panduan cepat bagi pengembang (*Architectural Decision Records - ADR*) yang tertaut langsung pada pesan error ArchUnit/OPA.

#### CI/CD Pipeline Gate (PEP)
- [ ] Gating arsitektur dijalankan paralel dengan *Unit Test* untuk menekan waktu tunggu *feedback*.
- [ ] Batasi total durasi eksekusi pengujian arsitektur agar tidak melebihi 5 menit per modul.
- [ ] Integrasikan pendeteksi siklus dependensi paket (*cyclic dependency detection*) di level kelas dan level modul.
- [ ] Verifikasi bahwa tidak ada dependensi eksternal yang memiliki lisensi restriktif (GPL di kode komersial) atau CVE kritis pada fase *Dependency Guard*.

#### Production Observability & Evolution
- [ ] Hubungkan metrik *afferent/efferent coupling* ke central telemetry (Grafana) untuk mengamati tren degradasi arsitektur per kuartal.
- [ ] Jalankan *Architectural Review Board* (ARB) berbasis model asinkron: Review dokumen waiver hanya jika pipeline mendeteksi pelanggaran berstatus *critical-unresolvable*.
- [ ] Implementasikan evaluasi *Inverse Conway Maneuver* secara berkala: Jika arsitektur sistem dipecah, sesuaikan struktur tim dan jalur komunikasi Slack/Gitlab secara paralel.

---

### 12. Hands-on Practice

Buat dan simpan struktur proyek berikut di direktori `hands-on/m02/`:

```
hands-on/m02/
├── pom.xml
├── policies/
│   └── network-isolation.rego
└── src/
    ├── main/java/com/enterprise/core/
    │   ├── domain/
    │   │   └── PaymentOrder.java
    │   ├── application/
    │   │   └── ProcessPaymentUseCase.java
    │   └── infrastructure/
    │       └── persistence/
    │           └── BadDomainEntityLeak.java
    └── test/java/com/enterprise/core/
        └── ArchitectureGovernanceTest.java
```

#### Langkah 1: Siapkan `pom.xml`
Definisikan dependensi ArchUnit di file `hands-on/m02/pom.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <groupId>com.enterprise.governance</groupId>
    <artifactId>architectural-governance-lab</artifactId>
    <version>1.0.0-SNAPSHOT</version>

    <properties>
        <maven.compiler.source>17</maven.compiler.source>
        <maven.compiler.target>17</maven.compiler.target>
        <archunit.version>1.2.1</archunit.version>
        <junit.version>5.10.1</junit.version>
    </properties>

    <dependencies>
        <dependency>
            <groupId>com.tngtech.archunit</groupId>
            <artifactId>archunit-junit5</artifactId>
            <version>${archunit.version}</version>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter-engine</artifactId>
            <version>${junit.version}</version>
            <scope>test</scope>
        </dependency>
    </dependencies>
</project>
```

#### Langkah 2: Buat Kode Domain dan Infrastruktur yang Melanggar Aturan
Buat file `hands-on/m02/src/main/java/com/enterprise/core/domain/PaymentOrder.java`:

```java
package com.enterprise.core.domain;

public class PaymentOrder {
    private final String orderId;
    private final double amount;

    public PaymentOrder(String orderId, double amount) {
        this.orderId = orderId;
        this.amount = amount;
    }

    public String getOrderId() { return orderId; }
    public double getAmount() { return amount; }
}
```

Buat file pelanggaran `hands-on/m02/src/main/java/com/enterprise/core/infrastructure/persistence/BadDomainEntityLeak.java` (Infrastruktur memanipulasi domain secara ilegal atau sebaliknya: domain mengakses repository langsung):

```java
package com.enterprise.core.domain;

// PELANGGARAN ARSITEKTUR: Domain layer mengimpor kelas dari infrastruktur!
import com.enterprise.core.infrastructure.persistence.BadDomainEntityLeak;

public class IllegalDomainService {
    public void execute() {
        BadDomainEntityLeak leak = new BadDomainEntityLeak();
        leak.directDatabaseAccess();
    }
}
```

Isi konten `BadDomainEntityLeak.java` di direktori `hands-on/m02/src/main/java/com/enterprise/core/infrastructure/persistence/BadDomainEntityLeak.java`:

```java
package com.enterprise.core.infrastructure.persistence;

public class BadDomainEntityLeak {
    public void directDatabaseAccess() {
        System.out.println("Bypassing domain boundary to access raw SQL!");
    }
}
```

#### Langkah 3: Definisikan Architecture Verification Engine
Buat file `hands-on/m02/src/test/java/com/enterprise/core/ArchitectureGovernanceTest.java`:

```java
package com.enterprise.core;

import com.tngtech.archunit.core.domain.JavaClasses;
import com.tngtech.archunit.core.importer.ClassFileImporter;
import com.tngtech.archunit.lang.ArchRule;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;

public class ArchitectureGovernanceTest {

    @Test
    @DisplayName("Domain Layer HARUS BEBAS dari dependensi Infrastructure Layer")
    public void domainMustNotDependOnInfrastructure() {
        JavaClasses importedClasses = new ClassFileImporter()
                .importPackages("com.enterprise.core");

        ArchRule rule = noClasses()
                .that().resideInAPackage("..domain..")
                .should().dependOnClassesThat()
                .resideInAPackage("..infrastructure..")
                .because("Domain Layer harus murni (Pure Domain) dan tidak boleh terikat detail teknis persistensi!");

        AssertionError error = Assertions.assertThrows(AssertionError.class, () -> {
            rule.check(importedClasses);
        }, "Harus melempar assertion error karena ada pelanggaran arsitektur!");

        System.out.println("SUKSES: Pipeline Tata Kelola Mendeteksi Pelanggaran Terprogram:");
        System.out.println(error.getMessage());
    }
}
```

#### Langkah 4: Uji Eksekusi Policy Engine
Jalankan Maven test dari direktori `hands-on/m02/`:
```bash
mvn test
```
*Hasil yang Diharapkan*: Build berhasil menjalankan tes dan membuktikan bahwa `AssertionError` tertangkap ketika domain mencoba mengimpor paket infrastruktur, mendemonstrasikan sistem gating fungsional.

---

### 13. Exercise

#### Level Easy
Tuliskan satu aturan ArchUnit yang memvalidasi bahwa seluruh kelas dengan akhiran nama `*Repository` harus berupa `interface`, bertempat di package `..domain.repository..` atau `..ports..`, dan tidak boleh dianotasi dengan anotasi Spring `@Repository` secara langsung di tingkat domain.

#### Level Medium
Buat sebuah custom ArchUnit condition yang mengukur kedalaman pewarisan (*Depth of Inheritance Tree* / DIT). Jika ada kelas dalam domain model yang memiliki kedalaman pewarisan lebih dari 2 tingkat (misal: `A extends B`, `B extends C`, `C extends D`), maka aturan tersebut harus menggagalkan unit test dengan pesan yang menyatakan bahwa komposisi harus lebih diutamakan daripada pewarisan (*composition over inheritance*).

#### Level Hard
Rancang arsitektur governance untuk integrasi multirepositori:
Tulis sebuah skrip atau program (dapat menggunakan Bash/Node.js/Python) yang bertindak sebagai Policy Enforcement Point di level orkestrasi CI/CD. Skrip ini harus membaca file skema OpenAPI v3 dari repositori downstream, membandingkannya dengan versi rilis upstream via REST contract breaking-change engine, dan secara otomatis menghasilkan *Exit Code 1* serta memetakan matriks dependensi yang terputus (*broken blast radius*) ke file Markdown ringkas untuk komentar otomatis di Gitlab Merge Request.

---

### 14. Challenge

#### Skenario Kasus Kompleks: Penggabungan Dua Platform Pasca-Akuisisi (M&A Architectural Unification)

Perusahaan Anda (Fintech Unicorn "PayFast") baru saja mengakuisisi kompetitor regional ("PayLegacy") yang memiliki stack arsitektur monolitik PHP dan Java lama dengan 120 database terhubung silang tanpa batas modul yang jelas.

CEO menginstruksikan agar seluruh transaksi PayLegacy dialihkan melalui *Risk & Compliance Engine* terpusat milik PayFast dalam waktu 6 bulan, tanpa menghentikan SLA operasional (99.99%). Sementara itu, tim PayLegacy resisten terhadap komite review PayFast dan terus melakukan deployment *hotfix* yang melanggar kontrak integrasi.

#### Tugas Anda sebagai Lead Software Architect:
1. **Rancang Blueprint Tata Kelola Arsitektur Terdistribusi (Hybrid Governance)**: Bagaimana Anda membangun mekanisme PEP/PDP otomatis yang dapat diterapkan pada platform monolitik PayLegacy tanpa menyebabkan mogok rilis total?
2. **Inverse Conway Maneuver**: Definisikan ulang struktur interaksi tim (*Team Topologies*) antara engineer PayFast dan PayLegacy. Tentukan *interaction mode* (Collaboration, Facilitating, X-as-a-Service) untuk masing-masing fase dalam transisi 6 bulan tersebut.
3. **Automated Quota & Gating System**: Rancang aturan konkrit dan metrik objektif kapan sebuah tim PayLegacy diizinkan rilis independen, kapan rilis mereka diblokir otomatis oleh pipeline, dan bagaimana mekanisme eskalasi *waiver* jika terdapat risiko kerugian finansial bisnis jutaan dolar versus integritas arsitektur.

*(Tantangan ini tidak memiliki solusi tunggal. Susun sebuah dokumen arsitektural komprehensif yang memuat diagram interaksi, tata urutan pipeline gating, dan matrik delegasi kepemimpinan).*

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)

1. Apa definisi dasar dari *Architectural Fitness Function* menurut Neal Ford dan Rebecca Parsons?
   - A. Tes performa yang hanya dijalankan saat sistem mencapai status produksi.
   - B. Mekanisme terprogram yang menyediakan eksekusi objektif dan terukur untuk mempertahankan karakteristik integritas arsitektur.
   - C. Dokumen panduan kepemimpinan arsitektur yang disahkan oleh jajaran eksekutif C-Level.
   - D. Metrik untuk menghitung kecepatan penulisan baris kode per developer per sprint.

2. Menurut Hukum Conway (*Conway's Law*), desain arsitektur sebuah sistem perangkat lunak mencerminkan:
   - A. Kebutuhan formal dari analisis pasar dan dokumen PRD.
   - B. Struktur komunikasi dari organisasi yang membangun sistem tersebut.
   - C. Pilihan framework terpopuler yang tersedia di industri.
   - D. Rasio alokasi biaya infrastruktur cloud perusahaan.

3. Pada model *Policy-as-Code*, apa perbedaan esensial antara PEP (*Policy Enforcement Point*) dan PDP (*Policy Decision Point*)?
   - A. PEP membuat keputusan boleh/tidaknya aksi, sedangkan PDP bertugas mendistribusikan lisensi perangkat lunak.
   - B. PEP mengintersepsi alur dan mengeksekusi tindakan (misal: CI runner memblokir build), sedangkan PDP mengevaluasi fakta terhadap aturan untuk menghasilkan keputusan.
   - C. PDP bekerja di level UI, sedangkan PEP bekerja di database.
   - D. Tidak ada perbedaan; keduanya istilah sinonim dalam arsitektur microservices.

4. Apa dampak negatif langsung jika *Afferent Coupling* ($Ca$) pada sebuah paket utilitas bersama bernilai sangat tinggi, sementara paket tersebut memiliki tingkat instabilitas ($I$) mendekati 1?
   - A. Paket menjadi sangat fleksibel dan aman untuk sering diubah kapan saja.
   - B. Paket memasuki *Zone of Pain*, di mana paket sangat rapuh, sulit diubah tanpa merusak banyak modul pemanggil, dan memicu efek domino kegagalan.
   - C. Latensi jaringan sistem akan meningkat secara eksponensial.
   - D. Biaya deployment Kubernetes menjadi lebih mahal.

5. Manakah dari pernyataan berikut yang paling tepat mendeskripsikan *Inverse Conway Maneuver*?
   - A. Mengubah struktur arsitektur sistem perangkat lunak untuk mengikuti struktur divisi manajemen yang telah ada.
   - B. Meniadakan posisi arsitek software dan menggantikannya sepenuhnya dengan product manager.
   - C. Mengembangkan arsitektur perangkat lunak yang diinginkan terlebih dahulu, lalu membentuk struktur tim dan pola interaksi organisasi agar sesuai dengan arsitektur tersebut.
   - D. Membagi tim berdasarkan keahlian bahasa pemrograman (tim Java, tim Go, tim Python).

---

#### Bagian 2: Intermediate (5 Pertanyaan)

6. Mengapa pengujian *Hexagonal Architecture* menggunakan ArchUnit lebih unggul dibandingkan pemeriksaan SonarQube standar dalam konteks penegakan batasan domain?
   - A. SonarQube tidak dapat memeriksa baris kode Java.
   - B. ArchUnit beroperasi langsung pada *bytecode* AST dan mampu menegakkan aturan spesifik arah ketergantungan paket internal (*unidirectional incoming/outgoing ports*), sedangkan SonarQube standar fokus pada *code smells*, sekuriti, dan kompleksitas umum.
   - C. ArchUnit tidak memerlukan compiler Java untuk menjalankan pemeriksaannya.
   - D. ArchUnit secara otomatis memperbaiki pelanggaran kode tanpa campur tangan developer.

7. Dalam konteks *Team Topologies*, tipe tim manakah yang bertugas memfasilitasi tim *Stream-Aligned* untuk mengadopsi kapabilitas baru (seperti tata kelola ArchUnit/OPA) tanpa menciptakan dependensi permanen?
   - A. Complicated Subsystem Team.
   - B. Platform Team.
   - C. Enabling Team.
   - D. Outsource Support Team.

8. Perhatikan metrik arsitektur Martin: $A = \text{Abstractness}$, $I = \text{Instability}$. Jika suatu komponen memiliki $A = 0$ (sangat konkret) dan $I = 0$ (sangat stabil/banyak yang bergantung padanya), komponen tersebut berada di:
   - A. *Zone of Uselessness*.
   - B. *Main Sequence*.
   - C. *Zone of Pain*.
   - D. *Zone of Scalability*.

9. Dalam integrasi Open Policy Agent (OPA) pada orkestrasi container production, peran utama *Admission Controller* berbasis OPA Gatekeeper adalah:
   - A. Mengompilasi kode program ke dalam container binary saat *push*.
   - B. Menolak mutasi atau pembuatan pod/deployment di kluster Kubernetes secara runtime jika manifes melanggar aturan tata kelola isolasi jaringan atau batas kuota arsitektur.
   - C. Menghitung penggunaan CPU pod secara real-time untuk billing cloud.
   - D. Melakukan enkripsi pada database PostgreSQL yang dikelola di cloud.

10. Apa risiko terbesar dari penerapan kebijakan arsitektur yang menggunakan mode *strict non-blocking* (hanya mengeluarkan pesan peringatan / *warning*) pada pipeline enterprise?
    - A. Waktu kompilasi CI/CD melonjak hingga 300%.
    - B. Munculnya fenomena *Warning Fatigue*, di mana developer mengabaikan semua log peringatan sehingga degradasi arsitektur terus terjadi hingga memicu kegagalan sistemik.
    - C. Server Jenkins akan kehabisan disk space akibat file log peringatan.
    - D. Modul dilarang dipublikasikan ke public container registry.

---

#### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)

11. **Skenario 1**: Sebuah tim *Stream-Aligned* sedang menghadapi tenggat waktu rilis regulasi perbankan yang sangat ketat (tersisa 36 jam). Pipeline CI mereka gagal karena aturan ArchUnit mendeteksi bahwa *Domain Use Case* mengakses langsung `EntityManager` Hibernate untuk mengeksekusi *native query bulk-update* demi memenuhi SLA throughput. 
    Sebagai Lead Architect, keputusan apa yang paling tepat dan profesional secara teknik arsitektural?
    - A. Menghapus aturan ArchUnit tersebut secara permanen dari repository master agar rilis berhasil.
    - B. Menginstruksikan tim untuk memodifikasi konfigurasi ArchUnit menggunakan *Waiver Mechanism* dengan anotasi kedaluwarsa waktu terbatas (misal: aktif 14 hari), mencatatnya ke dalam *Technical Debt Backlog* dengan prioritas P0, dan mewajibkan remediasi abstraksi Port/Adapter pasca rilis darurat.
    - C. Menolak rilis secara mutlak, membiarkan institusi gagal memenuhi regulasi pemerintah karena aturan batas arsitektur tidak boleh dilanggar dalam kondisi apa pun.
    - D. Memindahkan seluruh kode domain ke dalam direktori infrastruktur agar aturan ArchUnit tidak terpicu.

12. **Skenario 2**: Anda mengamati bahwa dashboard arsitektur menampilkan penurunan drastis pada kecepatan rilis tim *Inventory Service*. Analisis Git Hotspot menunjukkan bahwa file `OrderContract.java` diubah oleh 14 tim berbeda dalam satu sprint yang sama, memicu seringnya *merge conflict* dan kegagalan integrasi.
    Tindakan tata kelola arsitektur berbasis *Inverse Conway Maneuver* mana yang harus diambil?
    - A. Merekrut lebih banyak developer ke dalam tim Inventory Service untuk menangani merge conflict.
    - B. Mengisolasi `OrderContract` menjadi dependensi bersama yang dibekukan, lalu memecah kontrak tersebut ke dalam model *Consumer-Driven Contracts* (Pact) dan mengalihkan kepemilikan data ke domain masing-masing tim guna memutus kopling organisasi.
    - C. Menghapus kontrak dan membiarkan tim bertukar data menggunakan JSON mentah tanpa validasi skema.
    - D. Mengubah jadwal sprint masing-masing tim agar tidak pernah rilis di minggu yang sama.

13. **Skenario 3**: Sebuah organisasi enterprise memiliki 80 microservices. Pipeline CI/CD global memakan waktu 45 menit per build karena menjalankan 2.000 aturan ArchUnit yang memindai seluruh *classpath* dan dependensi transitif secara mendalam pada setiap commit kecil. Developer mulai mengeluh dan mencoba membypass pipeline.
    Langkah optimasi arsitektural apa yang wajib dilakukan untuk memitigasi hal ini?
    - A. Mematikan semua pengecekan arsitektur dan kembali ke model review mingguan manual oleh ARB.
    - B. Membagi *Architectural Fitness Functions* ke dalam tingkat eksekusi berlapis (*Shift-Left Layering*): Jalankan aturan isolasi paket lokal yang ringan pada tahapan PR verification, dan pindahkan pemindaian dependensi transitif mendalam serta analisis grafik global ke dalam *Nightly Pipeline*.
    - C. Mengganti seluruh bahasa pemrograman ke Go agar tidak memerlukan ArchUnit.
    - D. Menambah kapasitas core CPU server runner CI/CD sebanyak 10 kali lipat tanpa mengubah skenario pengujian.

---

### Kunci Jawaban Quiz

#### Bagian 1: Basic
1. **B** — Fitness function adalah eksekusi terprogram yang terukur dan objektif untuk memvalidasi karakteristik arsitektur.
2. **B** — Hukum Conway mendikte bahwa arsitektur sistem adalah replika dari struktur komunikasi organisasi pembuatnya.
3. **B** — PEP berfungsi sebagai eksekutor/penegak (enforcer), PDP berfungsi sebagai evaluator kebijakan deklaratif.
4. **B** — Kombinasi tanggung jawab tinggi ($Ca$ tinggi) dengan ketidakstabilan tinggi ($I$ tinggi / implementasi konkret tanpa abstraksi) menciptakan kerapuhan ekstrem (*Zone of Pain*).
5. **C** — *Inverse Conway Maneuver* secara proaktif menyelaraskan struktur tim organisasi untuk mendorong arsitektur sistem yang diinginkan.

#### Bagian 2: Intermediate
6. **B** — ArchUnit membaca bytecode AST untuk melacak dependensi paket domain secara granular dan mengarahkan aliran abstraksi port/adapter.
7. **C** — *Enabling Team* bertugas menanamkan kapabilitas dan keahlian baru ke tim *Stream-Aligned* untuk sementara waktu tanpa menciptakan ketergantungan silang permanen.
8. **C** — Modul yang sangat konkret ($A=0$) dan sangat stabil/tidak fleksibel ($I=0$) berada di *Zone of Pain* karena sulit diubah tanpa merusak ekosistem sekitarnya.
9. **B** — OPA Gatekeeper bertindak sebagai Admission Controller yang mencegat pemanggilan API server K8s dan memvalidasi manifes sebelum resource disimpan ke etcd.
10. **B** — Peringatan tanpa penegakan disiplin (*warning fatigue*) akan diabaikan developer, meniadakan nilai operasional tata kelola arsitektur.

#### Bagian 3: Kasus Produksi
11. **B** — Pendekatan pragmatis enterprise: Menyediakan jalur *waiver* terukur dengan batas kedaluwarsa eksplisit (*time-bound technical debt*) untuk kebutuhan rilis kritikal, diimbangi komitmen remediasi terencana.
12. **B** — Mengurangi *cognitive load* dan gesekan tim dengan menerapkan *Consumer-Driven Contracts* serta memisahkan kepemilikan skema kontrak domain.
13. **B** — Menerapkan pemisahan tugas pipeline (*staged fitness functions*): pengujian cepat untuk PR gating harian, pengujian komprehensif skala besar pada pipeline nightly.

---

### 16. Summary

Implementasi tata kelola arsitektur (*Architectural Governance*) modern pada skala enterprise telah bergeser secara fundamental dari paradigma manual berbasis komite (*Phase-Gate Verification*) menuju paradigma terotomatisasi berbasis kode (**Continuous Architecture-as-Code**).

Keberhasilan tata kelola arsitektur produksi bersandar pada tiga pilar utama:
1. **Automated Fitness Functions**: Menggunakan *tools* deterministik seperti **ArchUnit** untuk verifikasi internal kode sumber (isolasi lapisan Hexagonal/DDD) dan **Open Policy Agent (OPA)** untuk verifikasi infrastruktur dan lingkungan orkestrasi container.
2. **Organizational & Architectural Alignment**: Menerapkan prinsip **Inverse Conway Maneuver** dan konsep **Team Topologies** untuk memastikan bahwa struktur organisasi tim memperkuat—bukan merusak—arsitektur sistem terdistribusi yang dirancang.
3. **Objective Technical Debt & Exception Management**: Menghilangkan subjektivitas review dengan memantau metrik struktural terukur (*Distance from the Main Sequence*, kopling, kohesi) serta mengelola deviasi melalui mekanisme *Time-Bound Architectural Waivers* yang secara otomatis gagal ketika batas toleransi waktu telah terlampaui.

Dengan mentransformasikan arsitek dari "polisi birokratis" menjadi "pembangun platform guardrails", integritas sistem enterprise skala besar dapat terus berevolusi tanpa mengorbankan kecepatan pengiriman (*delivery velocity*) tim rekayasa perangkat lunak.