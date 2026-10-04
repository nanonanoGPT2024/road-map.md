# Modul 01: Domain-Driven Design (DDD) & Strategic Modeling

---

## SEKSI 01 — IDENTITAS MODUL

* **Jalur Pembelajaran:** Software Architecture & System Design
* **Kategori:** 06-Architecture-and-System-Design
* **Bab:** 04 — Enterprise Architectural Patterns & Modeling
* **Modul:** 01 — Domain-Driven Design (DDD) & Strategic Modeling: Bounded Contexts, Ubiquitous Language, Context Mapping, Core Domain vs Supporting Domains, Subdomains
* **Prasyarat:** Pemahaman mendalam tentang Object-Oriented Analysis & Design (OOAD), arsitektur Monolith vs Microservices, dasar-dasar pemodelan data relasional/non-relasional, serta pengalaman memimpin atau mendesain sistem skala enterprise.
* **Target Tingkat Keahlian:** Senior Engineer, Lead Architect, Principal Software Engineer.
* **Estimasi Waktu Penyelesaian:** 8 – 10 jam (termasuk pengerjaan studi kasus dan latihan implementasi).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Mendekomposisi Problem Space Enterprise:** Mengidentifikasi dan memisahkan Core Domain, Supporting Subdomain, dan Generic Subdomain secara objektif menggunakan metrik diferensiasi kompetitif dan kompleksitas domain.
2. **Menetapkan Batasan Eksplisit dalam Solution Space:** Merancang *Bounded Contexts* yang membatasi ambiguitas semantik dan mencegah terbentuknya *Big Ball of Mud*.
3. **Membangun dan Menegakkan Ubiquitous Language:** Mengisolasi leksikon teknis dan bisnis ke dalam model yang konsisten secara linguistik di dalam satu Bounded Context.
4. **Menganalisis Integrasi Lintas Batas via Context Mapping:** Memetakan dan mengimplementasikan relasi antar-konteks menggunakan pola *Anti-Corruption Layer (ACL)*, *Shared Kernel*, *Customer/Supplier*, *Conformist*, *Open Host Service (OHS)*, *Published Language (PL)*, dan *Separate Ways*.
5. **Mengeksekusi Strategi Transisi Arsitektural:** Mentransformasikan model data relasional terpusat yang monolitik menjadi batas-batas model independen yang siap dieksekusi sebagai microservices atau modular monoliths.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                              +---------------------------------------+
                              |             DOMAIN TOTAL              |
                              |   (Seluruh ekosistem bisnis sistem)   |
                              +---------------------------------------+
                                                  |
                    +-----------------------------+-----------------------------+
                    |                                                           |
          [ PROBLEM SPACE ]                                             [ SOLUTION SPACE ]
          Dekomposisi Masalah                                           Batas Implementasi
                    |                                                           |
       +------------+------------+                                      +-------+-------+
       |            |            |                                      |               |
       v            v            v                                      v               v
  CORE DOMAIN   SUPPORTING    GENERIC                              BOUNDED CONTEXT A  BOUNDED CONTEXT B
 (Diferensiasi   SUBDOMAIN    SUBDOMAIN                            (Model A: Order)   (Model B: Shipment)
  Kompetitif &  (Pelengkap   (Komoditas:                                |               |
  Kompleksitas   Unik Bisnis  Invoicing, Auth,                          +-------+-------+
    Tinggi)      Internal)     Notifikasi)                                      |
                                                                                v
                                                                        [ CONTEXT MAPPING ]
                                                                        - Anti-Corruption Layer (ACL)
                                                                        - Open Host Service (OHS)
                                                                        - Shared Kernel (SK)
                                                                        - Customer/Supplier
                                                                        - Conformist
                                                                        - Separate Ways
                                                                                |
                                                                                v
                                                                      [ UBIQUITOUS LANGUAGE ]
                                                                      (Ketegasan Semantik per Konteks)
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Kegagalan mendasar arsitektur enterprise modern jarang berakar pada performa algoritma atau pilihan bahasa pemrograman; kegagalan hampir selalu disebabkan oleh **Semantic Collision** dan **Model Coupling**.

1. **Ilusi Canonical Data Model (Enterprise Data Model):**
   Mencoba menyatukan istilah "User", "Account", atau "Product" ke dalam satu skema tunggal raksasa (single source of truth) untuk seluruh perusahaan selalu berujung pada kompromi kotor: tabel dengan ratusan kolom nullable, relasi foreign key sirkular, dan resistensi ekstrem terhadap perubahan (rigidity). Perubahan kecil pada logika penagihan (*Billing*) dapat melumpuhkan sistem pengiriman (*Fulfillment*) karena entitas `Order` yang saling tumpang tindih.

2. **Disfungsi Komunikasi Teknis-Bisnis:**
   Ketika developer berbicara dalam terminologi tabel basis data (`tbl_order_hdr`, `fk_usr_id`), sementara subject matter expert (SME) berbicara tentang alur operasional ("Underwriting", "Dispatch", "Settlement"), terjadi distorsi penerjemahan (cognitive translation penalty). Hal ini menghasilkan bug semantik: kode bekerja sesuai spesifikasi tiket, tetapi menyimpang dari intensi bisnis yang sebenarnya.

3. **Kekeliruan Alokasi Investasi Rekayasa:**
   Tanpa pemisahan Subdomain, tim rekayasa sering membuang sumber daya paling bernilai (top-tier engineers) untuk membangun ulang sistem Generic (misalnya: membangun sistem inventaris atau auth kustom yang sebenarnya bisa menggunakan solusi COTS / *Commercial Off-The-Shelf*), sementara Core Domain (mesin rekomendasi berbasis risiko, penetapan harga dinamis) kekurangan alokasi dan akhirnya rapuh.

DDD Strategis menyediakan perangkat formal bagi arsitek untuk memetakan boundaries sebelum baris kode pertama ditulis atau sebelum refactoring besar-besaran dimulai.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Problem Space vs Solution Space
* **Problem Space:** Wilayah di mana analisis bisnis dilakukan untuk memahami masalah yang ingin diselesaikan oleh organisasi. Problem Space didekomposisi menjadi **Subdomains**.
* **Solution Space:** Wilayah implementasi nyata software, arsitektur, dan kode. Diatur secara ketat ke dalam **Bounded Contexts**.

### 2. Taksonomi Subdomain
* **Core Domain:** Inti dari keunggulan kompetitif organisasi. Di sinilah diferensiasi bisnis terjadi. Menuntut kompleksitas domain tertinggi dan harus dibangun secara *in-house* dengan kontrol arsitektur penuh.
* **Supporting Subdomain:** Logika bisnis khusus yang melengkapi Core Domain, unik bagi perusahaan, tetapi bukan diferensiasi pemenang pasar. Biasanya tidak tersedia secara *off-the-shelf*, namun tidak membutuhkan talenta terbaik untuk membangunnya.
* **Generic Subdomain:** Bagian fungsionalitas sistem yang standar di seluruh industri (misal: Autentikasi/OIDC, Penagihan Pembayaran, Sistem Notifikasi SMS/Email). Subdomain ini sebaiknya dibeli, disewa (SaaS), atau mengadopsi pustaka open-source standar.

### 3. Bounded Context
Batas konseptual dan struktural eksplisit tempat suatu model domain berlaku secara utuh dan konsisten. Di dalam batasan ini, setiap istilah dalam model hanya memiliki satu makna tunggal tanpa ambiguitas (*semantic boundary*). Bounded Context bukan sekadar boundary teknis (seperti batas modul atau repository), melainkan batas validitas kognitif dan operasional dari sebuah model.

### 4. Ubiquitous Language
Bahasa terpadu, ketat, dan eksplisit yang dikonstruksi bersama oleh tim developer dan Domain Experts. Ubiquitous Language **tidak berlaku secara global** di seluruh organisasi, melainkan **terikat secara absolut ke satu Bounded Context tertentu**. 

### 5. Context Mapping
Visualisasi dan penetapan pola relasi antarmuka formal (kontrak, sosiologis, dan teknologi) yang menghubungkan dua atau lebih Bounded Contexts.

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

Dekomposisi strategis DDD dieksekusi melalui metodologi bertahap:

```
[ Domain Discovery (EventStorming) ]
                 │
                 ▼
[ Identifikasi Subdomain Matrix ] ──── (Core vs Supporting vs Generic)
                 │
                 ▼
[ Penentuan Bounded Context Boundaries ] ──── (Linguistic & Lifecycle Separation)
                 │
                 ▼
[ Konstruksi Ubiquitous Language Dict ] ──── (Glosarium kontekstual per bounded context)
                 │
                 ▼
[ Pemetaan Context Map & Integration Contracts ] ──── (Pola relasi teknis: OHS, ACL, dll.)
```

### Langkah 1: Problem Space Partitioning
Gunakan kuadran Core Domain Assessment untuk membagi subdomains:
* Sumbu X: Diferensiasi Bisnis (Rendah ke Tinggi)
* Sumbu Y: Kompleksitas Model Domain (Rendah ke Tinggi)
* Kuadran Kanan-Atas = **Core Domain**
* Kuadran Kiri-Tinggi/Rendah = **Supporting Subdomain**
* Kuadran Kiri-Bawah = **Generic Subdomain**

### Langkah 2: Linguistic Boundary Tracing
Untuk menentukan di mana batas Bounded Context diletakkan, periksa homonim dan sinonim dalam komunikasi bisnis:
* **Polisemi/Homonim (Kata sama, makna beda):** Istilah "Klaim" memiliki arti berbeda bagi Divisi Hukum (gugatan perdata) versus Divisi Asuransi (permintaan pencairan polis). Ini menandakan **dua Bounded Context terpisah**.
* **Sinonim (Kata beda, entitas sama):** "Pelanggan" di Sales, "Debitur" di Billing, "Penerima" di Logistics. Menyatukan mereka menjadi `CustomerEntity` tunggal akan merusak integritas arsitektur. Mereka harus dipisah ke dalam konteksnya masing-masing.

### Langkah 3: Menentukan Relasi Context Mapping
Pilih pola integrasi yang tepat berdasarkan dinamika tim dan kebutuhan otonomi:

1. **Shared Kernel (SK):** Dua Bounded Context berbagi sebagian model domain dan basis data yang sama. Berisiko tinggi; modifikasi model memerlukan koordinasi dua tim.
2. **Customer/Supplier (C/S):** Upstream (Supplier) menyediakan kapabilitas, Downstream (Customer) memiliki pengaruh langsung terhadap jadwal pengiriman fitur upstream.
3. **Conformist (CF):** Downstream tunduk sepenuhnya pada model domain Upstream tanpa translasi data karena upstream tidak bersedia/mampu beradaptasi.
4. **Anti-Corruption Layer (ACL):** Downstream membangun lapisan penerjemah (adapter/translator) untuk mengisolasi model domainnya sendiri dari intervensi atau polusi model eksternal (terutama saat berintegrasi dengan legacy system).
5. **Open Host Service / Published Language (OHS/PL):** Upstream mendefinisikan protokol akses standar (misal: REST/GraphQL API publik) dan skema pertukaran data standar (misal: JSON Schema/Protobuf) untuk melayani downstream manapun secara netral.
6. **Separate Ways:** Tim memutuskan tidak ada integrasi teknis sama sekali karena biaya koordinasi lebih tinggi daripada membangun kembali solusi independen.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Strategic Domain Classification & Context Map

```
====================================================================================================
PROBLEM SPACE: Enterprise Logistics & E-Commerce Platform
====================================================================================================

      High ^
           |                    [SUPPORTING]                           [CORE DOMAIN]
           |              Custom Dynamic Routing                  Algorithmic Route &
           |                  Configuration                     Yield Optimization Engine
Diferensiasi |
  Bisnis   |
           |
           |        [GENERIC]                    [GENERIC]                     [SUPPORTING]
           |    Identity & Access          Payment Processing            Warehouse Yard
           |     Management (IAM)             Integration                  Management
       Low +------------------------------------------------------------------------------------>
           Low                                                                               High
                                        Kompleksitas Domain

====================================================================================================
SOLUTION SPACE: Context Map & Inter-Context Relationships
====================================================================================================

   +-----------------------+                         +-----------------------------+
   |  Identity & Access BC |                         |  Route Optimization BC      |
   |      (Generic)        |                         |         (Core Domain)       |
   +-----------------------+                         +-----------------------------+
              |                                                     ^
              | [Upstream] (OHS / PL)                               |
              | OpenID Connect / JWT                                | [Downstream]
              v                                                     |
   +-----------------------+                                        |
   |   Order Placement BC  | [Upstream]                             | (Customer/Supplier)
   |       (Core)          |------------------+                     |
   +-----------------------+ (Domain Events)  |                     |
              |                               v                     |
              |                   +-----------------------+         |
              |                   | Transportation &      |---------+
              | (Customer/        | Logistics BC (Core)   | [Upstream]
              |  Supplier)        +-----------------------+
              v                               |
   +-----------------------+                  | [Upstream] (Proprietary RPC)
   |  Billing & Invoicing  |                  v
   |      (Generic)        |      +-----------------------+
   +-----------------------+      | [ACL] Anti-Corruption |
                                  |       Layer           |
                                  +-----------------------+
                                              |
                                              | [Downstream] (Conformist via ACL)
                                              v
                                  +-----------------------+
                                  | 3rd-Party Telematics  |
                                  | Legacy Fleet Provider |
                                  +-----------------------+
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah ilustrasi **Ubiquitous Language** dan pemisahan semantik entity `Policy` dalam domain Asuransi.

### 1. Masalah Monolitik (Big Ball of Mud):
Satu class `Policy` dipaksa menampung seluruh domain lifecycle:

```typescript
// ANTI-PATTERN: God Object "Policy"
class Policy {
  id: string;
  // Kebutuhan Underwriting
  medicalCheckupHistory: MedicalRecord[];
  actuarialRiskScore: number;
  
  // Kebutuhan Sales
  agentCommissionRate: number;
  promoCodeApplied: string;
  
  // Kebutuhan Claims
  payoutBankDetails: BankAccount;
  totalClaimsCount: number;
  
  // Kebutuhan Billing
  premiumBillingCycle: "MONTHLY" | "ANNUAL";
  latePaymentGracePeriodDays: number;
}
```

### 2. DDD Strategic Separation:
Bagi menjadi context terpisah dengan Ubiquitous Language masing-masing:

```typescript
// Bounded Context: Underwriting
// Bahasa: Risk Assessment, Underwriting Guidelines, Coverability
namespace UnderwritingContext {
  export class UnderwritingApplication {
    constructor(
      public readonly applicationId: string,
      public readonly applicantHealthData: MedicalHistory,
      public readonly calculatedRiskFactor: RiskScore
    ) {}

    public evaluateEligibility(): UnderwritingVerdict {
      return this.calculatedRiskFactor.value < 0.25 ? "ACCEPTED" : "MANUAL_REVIEW";
    }
  }
}

// Bounded Context: Claims Management
// Bahasa: Claimant, Adjudication, Coverage Limit, Settlement
namespace ClaimsContext {
  export class InsuredCoverage {
    constructor(
      public readonly policyContractId: string,
      public readonly maximumCoverageLimit: MonetaryAmount,
      public readonly isDeductibleMet: boolean
    ) {}

    public adjudicateClaim(claimAmount: MonetaryAmount): ClaimDecision {
      if (claimAmount.isGreaterThan(this.maximumCoverageLimit)) {
        return ClaimDecision.reject("Exceeds coverage limit");
      }
      return ClaimDecision.approve(claimAmount);
    }
  }
}
```

Dalam model ini, Underwriting tidak perlu mengetahui rekening bank untuk pencairan, dan Claims tidak perlu dibebani dengan skor aktuarial mentah.

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Kasus implementasi nyata integrasi **Anti-Corruption Layer (ACL)**: 
Bounded Context baru kita (*Logistics Tracking*) membutuhkan data dari sistem vendor logistik pihak ketiga (*Legacy Fleet System*), yang memiliki format aneh, penamaan buruk, dan tidak stabil.

### 1. Model Domain Downstream (Clean Architecture)

```typescript
// LogisticsTrackingBC: Domain Model
export class TrackingId {
  constructor(public readonly value: string) {
    if (!value || value.length < 8) throw new Error("Invalid Tracking ID");
  }
}

export class GeoCoordinate {
  constructor(public readonly latitude: number, public readonly longitude: number) {
    if (latitude < -90 || latitude > 90) throw new Error("Latitude out of range");
    if (longitude < -180 || longitude > 180) throw new Error("Longitude out of range");
  }
}

export enum VesselStatus {
  IN_TRANSIT = "IN_TRANSIT",
  DOCKED = "DOCKED",
  MAINTENANCE = "MAINTENANCE"
}

export class VesselLocationUpdate {
  constructor(
    public readonly trackingId: TrackingId,
    public readonly coordinates: GeoCoordinate,
    public readonly status: VesselStatus,
    public readonly timestamp: Date
  ) {}
}

// Port/Interface yang diharapkan domain internal kita
export interface FleetTrackingPort {
  fetchLatestLocation(trackingId: TrackingId): Promise<VesselLocationUpdate>;
}
```

### 2. Data Transfer Object (DTO) Eksternal / Legacy Model

```typescript
// Kontrak dari Vendor Luar (Legacy XML-over-JSON style)
export interface LegacyVendorTelematicsPayload {
  TRK_ID: string;
  GPS_LAT_STR: string;
  GPS_LNG_STR: string;
  ENGINE_ST: "1" | "0" | "ERR";
  SYS_UPTIME_EPOCH: number;
}
```

### 3. Implementasi Anti-Corruption Layer (ACL)

Lapisan ACL bertindak sebagai penerjemah dan firewall pertahanan yang memastikan model legacy tidak meracuni domain model internal.

```typescript
import { 
  FleetTrackingPort, 
  TrackingId, 
  VesselLocationUpdate, 
  GeoCoordinate, 
  VesselStatus 
} from "./domain";

export class LegacyFleetAntiCorruptionLayer implements FleetTrackingPort {
  private readonly legacyApiEndpoint: string;

  constructor(endpoint: string) {
    this.legacyApiEndpoint = endpoint;
  }

  public async fetchLatestLocation(trackingId: TrackingId): Promise<VesselLocationUpdate> {
    const rawData = await this.queryExternalLegacySystem(trackingId.value);
    return this.translateToCleanDomain(rawData);
  }

  private async queryExternalLegacySystem(id: string): Promise<LegacyVendorTelematicsPayload> {
    // Simulasi pemanggilan API Upstream Vendor
    return {
      TRK_ID: id,
      GPS_LAT_STR: "-6.2088",
      GPS_LNG_STR: "106.8456",
      ENGINE_ST: "1",
      SYS_UPTIME_EPOCH: Date.now()
    };
  }

  // Inti dari Anti-Corruption Layer: Validasi, Normalisasi, Penerjemahan Semantik
  private translateToCleanDomain(payload: LegacyVendorTelematicsPayload): VesselLocationUpdate {
    const lat = parseFloat(payload.GPS_LAT_STR);
    const lng = parseFloat(payload.GPS_LNG_STR);

    if (isNaN(lat) || isNaN(lng)) {
      throw new Error(`Corrupted coordinates received from external legacy vendor: ${payload.TRK_ID}`);
    }

    const domainCoordinates = new GeoCoordinate(lat, lng);
    const domainTrackingId = new TrackingId(payload.TRK_ID);

    let domainStatus: VesselStatus;
    switch (payload.ENGINE_ST) {
      case "1":
        domainStatus = VesselStatus.IN_TRANSIT;
        break;
      case "0":
        domainStatus = VesselStatus.DOCKED;
        break;
      default:
        domainStatus = VesselStatus.MAINTENANCE;
        break;
    }

    const domainTimestamp = new Date(payload.SYS_UPTIME_EPOCH);

    return new VesselLocationUpdate(
      domainTrackingId,
      domainCoordinates,
      domainStatus,
      domainTimestamp
    );
  }
}
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi Arsitektural | Single Canonical Model (Monolitik Database) | Bounded Contexts (DDD Strategis) |
|---|---|---|
| **Kompleksitas Kognitif** | Rendah di awal; Eksponensial seiring bertambahnya tim dan fitur. | Tinggi di awal; Stabil dan terlokalisasi di masing-masing konteks saat sistem membesar. |
| **Penyalinan Data & Duplikasi** | Nol duplikasi data; Single Source of Truth teoritis. | Model data sengaja diduplikasi/diisolasi demi otonomi semantik dan transaksional. |
| **Konsistensi Data** | Immediate Consistency via Relational ACID Transactions. | Eventual Consistency antar-Bounded Context; ACID hanya berlaku di dalam satu Context. |
| **Overhead Komunikasi** | Kebutuhan sinkronisasi database lintas-tim sangat tinggi saat skema berubah. | Kebutuhan sinkronisasi berkurang; Kontrak (API/Events) menjadi penengah komunikasi. |
| **Kinerja Runtime** | Overhead performa berasal dari Database Locks dan Contention tabel besar. | Overhead performa berasal dari network latency dan serialization/deserialization ACL. |

---

## SEKSI 11 — BEST PRACTICES

1. **Satu Tim Maksimal Menguasai Satu atau Beberapa Bounded Context; Tidak Pernah Satu Bounded Context Dibagi ke Berbagai Tim Tanpa Pemilik Jelas (Conway's Law):**
   Garis batasan perangkat lunak harus mencerminkan struktur komunikasi organisasi. Jika dua tim memodifikasi Bounded Context yang sama tanpa garis batas yang jelas, konteks tersebut akan segera terdegradasi menjadi *Shared Kernel* yang tidak terawat.

2. **Dahulukan Batasan Makro Sebelum Mikro (Coarse-Grained Contexts First):**
   Jangan langsung membagi domain menjadi puluhan microservices. Mulailah dengan Bounded Context yang lebih besar dalam arsitektur Monolith Modular. Pisahkan secara fisik (jaringan terpisah/microservices) hanya jika skala beban trafik, siklus rilis, atau kebutuhan otonomi tim memang mengharuskannya.

3. **Dokumentasikan Ubiquitous Language dalam Bentuk Executable Specifications:**
   Jangan biarkan definisi istilah hanya hidup di dokumen Wiki statis. Gunakan nama-nama kelas, method, event, dan use case tests yang persis sama dengan Ubiquitous Language yang disepakati bersama Domain Expert.

4. **Jangan Pernah Mengabaikan ACL Saat Berhadapan dengan Domain Eksternal:**
   Setiap interaksi dengan sistem pihak ketiga atau sistem legacy wajib melalui Anti-Corruption Layer. Membiarkan DTO eksternal bocor ke dalam Application Service atau Domain Layer downstream adalah resep utama ketergantungan yang rapuh (*tight architectural coupling*).

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1. **Technical Bounded Contexts (Membuat Boundary Berdasarkan Pola Teknis):**
   *Kesalahan:* Membagi konteks menjadi "UI Context", "Database Context", atau "Notification Context".
   *Koreksi:* Bounded Context harus membatasi **model domain bisnis**, bukan lapisan teknis arsitektur n-tier.

2. **Tergelincir ke dalam "Conformist Trap":**
   *Kesalahan:* Mengadopsi struktur tabel atau skema API sistem upstream secara mentah-mentah ke dalam domain baru hanya untuk menghemat waktu penulisan kode adapter.
   *Koreksi:* Bila upstream tidak menyediakan Published Language yang netral, bangun ACL untuk melindungi model domain internal dari mutasi yang tidak terkendali.

3. **Polisemi yang Tidak Terdeteksi:**
   *Kesalahan:* Mengasumsikan bahwa kata "Invoice" memiliki arti yang sama persis bagi tim Operasional Gudang (packing slip) dan tim Finance (tax invoice & balance ledger).
   *Koreksi:* Lakukan wawancara semantik mendalam via EventStorming. Jika fungsionalitas dan atribut yang dipedulikan berbeda, pisahkan menjadi model yang berbeda di dalam Bounded Context yang berbeda.

4. **Shared Kernel yang Membengkak:**
   *Kesalahan:* Menggunakan package `common` atau `shared-kernel` sebagai tempat pembuangan seluruh entity dasar (seperti `User`, `Tenant`, `Product`) yang diimpor oleh seluruh modul atau repositori.
   *Koreksi:* Batasi isi Shared Kernel hanya pada primitif fundamental yang stateless (misal: Value Objects penanganan mata uang `Money`, `Currency`, atau identifier standar). Entitas bisnis yang memiliki state machine tidak boleh berada di Shared Kernel.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Skenario:
Sebuah perusahaan logistik farmasi sedang membangun platform distribusi obat bernama **PharmaLink**. Platform ini menangani:
1. Validasi resep dokter dan lisensi apoteker legal.
2. Manajemen inventaris obat di gudang pendingin (Cold Chain).
3. Pengiriman rute kurir dengan armada khusus sensor suhu.
4. Penagihan klaim BPJS/Asuransi Swasta.

### Instruksi:
1. **Analisis Problem Space:**
   Petakan sub-fitur di atas ke dalam Core Domain, Supporting Subdomain, dan Generic Subdomain. Berikan justifikasi kompetitifnya.
2. **Desain Bounded Context:**
   Gambarkan Bounded Context yang direkomendasikan beserta definisi Ubiquitous Language untuk kata `Medication` di masing-masing konteks.
3. **Context Mapping Strategy:**
   Tentukan pola Context Mapping (ACL, OHS/PL, Conformist, Customer/Supplier) untuk integrasi antara **Context Inventaris Cold-Chain** dan **Sensor IoT Suhu Pihak Ketiga**.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Pertanyaan:** Apa perbedaan fundamental antara Subdomain dan Bounded Context?
   * **Jawaban Ideal:** Subdomain adalah bagian dari *Problem Space* (bagaimana bisnis menstrukturkan domain masalah dan area operasinya di dunia nyata). Bounded Context adalah bagian dari *Solution Space* (bagaimana software architect mendesain batas konseptual dan teknis software tempat model perangkat lunak berlaku secara eksplisit).

2. **Pertanyaan:** Tim Anda mengintegrasikan sistem baru dengan Core Banking System legacy berusia 20 tahun yang tidak mungkin dimodifikasi. Pola Context Mapping apa yang mutlak harus diterapkan pada downstream, dan mengapa?
   * **Jawaban Ideal:** *Anti-Corruption Layer (ACL)*. Karena Core Banking legacy adalah Upstream yang tidak fleksibel dan model datanya kemungkinan usang serta penuh polusi terminologi lama. Downstream tidak boleh menjadi *Conformist* karena akan merusak Ubiquitous Language dan model domain baru downstream.

3. **Pertanyaan:** Kapan sebuah Subdomain yang awalnya dikategorikan sebagai Supporting Subdomain dapat bertransformasi menjadi Core Domain?
   * **Jawaban Ideal:** Ketika strategi kompetitif bisnis berubah sedemikian rupa sehingga kapabilitas pendukung tersebut menjadi pembeda utama di pasar yang menghasilkan margin tinggi atau disrupsi inovasi (misalnya: Amazon Web Services yang bermula dari supporting infrastructure untuk e-commerce Amazon kemudian berevolusi menjadi Core Business).

4. **Pertanyaan:** Mengapa penggunaan canonical enterprise data model (model data terpadu global) sering kali dianggap sebagai anti-pattern dalam organisasi modern berskala besar?
   * **Jawaban Ideal:** Karena model data terpadu mencoba menghapus batas-batas konteks, mengabaikan fakta bahwa kata yang sama memiliki arti berbeda di divisi berbeda. Hal ini menciptakan bottleneck koordinasi organisasi, penguncian dependensi massal, dan kompleksitas skema yang tidak dapat dikelola.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Evans, Eric.** (2003). *Domain-Driven Design: Tackling Complexity in the Heart of Software*. Addison-Wesley Professional. (Bab 14: Strategic Design Overview, Bab 15: Distillation).
* **Vernon, Vaughn.** (2013). *Implementing Domain-Driven Design*. Addison-Wesley Professional. (Bab 2: Domains, Subdomains, and Bounded Contexts, Bab 3: Context Maps).
* **Khononov, Vlad.** (2021). *Learning Domain-Driven Design: Aligning Software Architecture and Business Strategy*. O'Reilly Media.
* **Brandolini, Alberto.** (2019). *Introducing EventStorming*. Leanpub.
* **Millett, Scott & Tune, Nick.** (2015). *Patterns, Principles, and Practices of Domain-Driven Design*. Wrox.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

Strategic Domain-Driven Design adalah instrumen utama arsitek perangkat lunak untuk menaklukkan kompleksitas domain enterprise sebelum berurusan dengan detail taktis kode. 

Dengan membagi Problem Space ke dalam **Core**, **Supporting**, dan **Generic Subdomains**, organisasi dapat mengalokasikan modal engineering dan talenta terbaik ke area yang menghasilkan keunggulan kompetitif. Melalui pembatasan model dalam **Bounded Contexts** yang ditenagai oleh **Ubiquitous Language**, arsitek memusnahkan ambiguitas semantik dan mencegah terbentuknya *Big Ball of Mud*. Terakhir, **Context Mapping** menyediakan kerangka kerja analitis dan taktis untuk merekayasa integrasi antar-batas konteks secara sadar, melindungi model murni downstream melalui penerapan pertahanan seperti **Anti-Corruption Layer**.

---

## SEKSI 17 — GLOSARIUM

* **Bounded Context:** Batas eksplisit tempat sebuah model domain perangkat lunak didefinisikan, diterapkan, dan dijaga validitas logis serta konsistensi terminologinya.
* **Ubiquitous Language:** Kosakata formal, ketat, dan eksplisit yang disepakati bersama oleh Domain Experts dan Software Engineers, terbatas pada satu Bounded Context.
* **Problem Space:** Perspektif analisis arsitektural yang berfokus pada dinamika bisnis aktual, peluang industri, dan tantangan yang perlu diselesaikan.
* **Solution Space:** Perspektif eksekusi rekayasa perangkat lunak yang mencakup arsitektur, boundary modul, basis data, dan implementasi kode.
* **Core Domain:** Subdomain yang menjadi diferensiasi primer bisnis dan nilai jual kompetitif organisasi di pasar.
* **Anti-Corruption Layer (ACL):** Lapisan isolasi dan penerjemahan mekanis yang memfasilitasi komunikasi antara dua sistem/konteks tanpa membiarkan model upstream merusak model downstream.
* **Open Host Service (OHS):** Protokol atau antarmuka publik standar yang disediakan oleh konteks upstream untuk memudahkan siapa pun mengonsumsi kapabilitasnya.
* **Published Language (PL):** Skema data standar terdokumentasi (misal: XML, JSON Schema, Protobuf) yang disepakati sebagai media transfer data antara downstream dan upstream.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Fokus Diskusi:** Tekankan bahwa DDD Strategis adalah 80% sosio-teknikal dan 20% teknikal murni. Jangan biarkan siswa langsung melompat ke pembahasan Entity, Value Object, dan Repositories (DDD Taktis) sebelum mereka benar-benar memahami batas-batas Bounded Context.
* **Sesi Studi Kasus:** Saat memfasilitasi sesi Latihan Hands-on, minta siswa untuk secara aktif memainkan peran yang saling berkonflik: satu siswa berperan sebagai Chief Logistics Officer (Cold Chain), yang lain sebagai Legal Compliance Officer (Perizinan Obat). Tunjukkan bagaimana kedua role tersebut menggunakan terminologi yang bertabrakan untuk entity yang sama.
* **Perangkap Pembelajaran:** Waspadai kecenderungan siswa untuk mendefinisikan boundary berdasarkan tabel database yang sudah ada. Ingatkan bahwa tujuan strategic modeling sering kali adalah memecah tabel raksasa tersebut ke dalam konteks yang benar-benar otonom.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi:** 1.0.0
* **Tanggal Rilis:** 2026-03-31
* **Perubahan Terakhir:**
  * Inisialisasi materi perdana Bab 04 Module 01: Strategic Domain-Driven Design.
  * Penyusunan modul 20 seksi sesuai standar Enterprise Curriculum Architecture.
  * Penambahan diagram ASCII Context Map dan implementasi nyata Anti-Corruption Layer dalam TypeScript.
* **Maintainer:** Technical Curriculum Engineering Group

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya:** Bab 03 Module 05: Data Partitioning, Sharding, & Distributed Consistency Models
* **Modul Berikutnya:** Bab 04 Module 02: Tactical Domain-Driven Design: Entities, Value Objects, Aggregates, & Domain Events
* **Repositori Kurikulum:** `software-architect/06-Architecture-and-System-Design/`