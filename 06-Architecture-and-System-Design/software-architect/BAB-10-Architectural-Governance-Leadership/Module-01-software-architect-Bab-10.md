## SEKSI 01 — IDENTITAS MODUL

*   **Kode Modul**: ARCH-06-10-01
*   **Judul Modul**: Architectural Governance, Evolution & Leadership: Architecture Decision Records (ADR), Technology Radars, Technical Debt Management, Architectural Leadership & Communication
*   **Kategori**: 06-Architecture-and-System-Design
*   **Tingkat Kesulitan**: Advanced / Principal Level
*   **Estimasi Waktu Penyelesaian**: 8 Jam Pembelajaran (Self-paced / Workshop)
*   **Prasyarat**:
    *   Pemahaman mendalam tentang Enterprise Architecture Patterns (Microservices, Event-Driven, Monoliths).
    *   Pengalaman praktis memimpin tim engineering atau bertindak sebagai Tech Lead/Senior Engineer minimal 3 tahun.
    *   Kemahiran menggunakan Git dan Tooling CI/CD pipelines.
*   **Target Audiens**: Software Architects, Principal Engineers, Staff Engineers, Engineering Managers, dan Technical Directors yang bertanggung jawab atas keberlanjutan arsitektur skala enterprise.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1.  **Menganalisis & Mengartikulasikan Keputusan Arsitektural**: Merumuskan, menyusun, dan mengaudit *Architecture Decision Records* (ADR) berstandar industri (MADR / Nygard) untuk mencegah *architectural amnesia*.
2.  **Merancang Tata Kelola Portofolio Teknologi**: Membangun, mengkurasi, dan memelihara *Enterprise Technology Radar* berbasis metodologi ThoughtWorks guna mengarahkan standardisasi alat dan pustaka (libraries).
3.  **Mengkuantifikasi & Mengelola Technical Debt**: Mengklasifikasikan utang teknis menggunakan *Technical Debt Quadrant*, mengukur implikasi finansialnya melalui metrik objektif (seperti *Debt-to-Asset Ratio* dan *Code Churn*), serta menyusun strategi pelunasan berbasis prioritas risiko.
4.  **Menerapkan Pola Architectural Governance Modern**: Menjalankan mekanisme tata kelola adaptif (*Federated Governance*, *Automated Fitness Functions*) tanpa menciptakan birokrasi *Ivory Tower Architecture*.
5.  **Mengeksekusi Kepemimpinan dan Komunikasi Arsitektural**: Memfasilitasi konsensus lintas pemangku kepentingan (*engineering*, produk, eksekutif) menggunakan teknik *Request for Comments* (RFC), *Architecture Review Board* (ARB) berbasis kolaborasi, dan mitigasi konflik teknis.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                       ARCHITECTURAL EVOLUTION & GOVERNANCE
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        ▼                              ▼                              ▼
  DOCUMENTATION                  RADAR & RADIAL                 DEBT & METRICS
  & CAPTURE                        STANDARDS                      LIFECYCLE
┌────────────────┐             ┌────────────────┐             ┌────────────────┐
│      ADR       │             │   Technology   │             │ Technical Debt │
│  Architecture  │             │     Radar      │             │   Management   │
│Decision Records│             │  (ThoughtWorks)│             │  (Fowler/Ward) │
└───────┬────────┘             └───────┬────────┘             └───────┬────────┘
        │                              │                              │
        │ Context & Trade-offs         │ Hold, Assess, Trial, Adopt   │ Intentional vs
        │ Immutable Log via Git        │ Quadrants: Tools, Tech,      │ Reckless / Cruft
        │ Status: Accepted/Superseded  │ Platforms, Languages         │ Debt Payoff Ratio
        │                              │                              │
        └──────────────────────────────┼──────────────────────────────┘
                                       │
                                       ▼
                       LEADERSHIP & ADAPTIVE CONTROL
        ┌─────────────────────────────────────────────────────────────┐
        │                 Architectural Leadership                    │
        │                                                             │
        │  * Federated Governance vs. Ivory Tower ARB                 │
        │  * Automated Architecture Fitness Functions                 │
        │  * RFC (Request for Comments) Engineering Workflows         │
        │  * Alignment over Control (Conway's Law Adaptation)         │
        └─────────────────────────────────────────────────────────────┘
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Arsitektur perangkat lunak tidak runtuh karena satu kegagalan teknis masif; arsitektur membusuk (*software entropy*) akibat ribuan keputusan mikro yang tidak terdokumentasi, adopsi teknologi acak (*fragmented stack*), dan akumulasi utang teknis yang tidak dikelola. 

Berikut adalah risiko fatal jika tata kelola arsitektur diabaikan:

1.  **Architectural Amnesia**: Enam bulan setelah sistem dirilis, tim baru tidak mengetahui *mengapa* MongoDB dipilih alih-alih PostgreSQL. Pertanyaan ini memicu perdebatan berulang, atau lebih buruk lagi: arsitektur dirombak kembali dengan kesalahan yang sama karena konteks batasan (*constraints*) di masa lalu telah hilang.
2.  **Technology Sprawl**: Tanpa *Technology Radar*, setiap engineer bebas memasukkan library, framework, dan database baru ke dalam repositori produksi. Hasilnya adalah lonjakan *cognitive load*, audit kepatuhan keamanan yang mustahil dikendalikan, dan kesulitan transfer knowledge lintas divisi.
3.  **The Bankruptcy of Technical Debt**: Utang teknis yang diabaikan akan bertransisi dari *friction* (fitur baru memakan waktu 2x lebih lama) menjadi *insolvency* (sistem tidak lagi dapat diubah secara aman tanpa memicu *cascading failures*).
4.  **Ivory Tower Failure**: Tim arsitek yang bertindak sebagai birokrat absolut menghasilkan aturan yang diabaikan oleh developer di lapangan (*shadow architecture*). Sebaliknya, ketiadaan arsitek menghasilkan anarki teknis (*Wild West architecture*).

Kepemimpinan arsitektural modern bertransformasi dari sekadar **perancang cetak biru (blueprint designer)** menjadi **desainer sistem umpan balik (feedback-loop engineer)** yang menetapkan *guardrails* agar tim dapat berinovasi secara aman dan otonom.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Architecture Decision Record (ADR)
ADR adalah artefak teks sederhana berbasis *version-control* yang mendokumentasikan keputusan arsitektural kritis, konteks saat keputusan diambil, dan konsekuensi logisnya (baik positif, negatif, maupun netral). 

Format paling populer meliputi:
*   **Format Nygard**: Format minimalis yang dicetuskan oleh Michael Nygard (Title, Status, Context, Decision, Consequences).
*   **MADR (Markdown Any Architecture Decision Record)**: Format kaya yang memuat opsi-opsi alternatif yang dipertimbangkan serta argumen pro/kontra dari setiap alternatif.

### 2. Technology Radar
Model visual yang dikembangkan oleh ThoughtWorks untuk memetakan portofolio teknologi yang digunakan, dievaluasi, atau dilarang dalam sebuah organisasi. Tech Radar dibagi menjadi:
*   **4 Kuadran**: *Techniques*, *Tools*, *Platforms*, *Languages & Frameworks*.
*   **4 Cincin (Rings)**:
    *   **ADOPT**: Standard industri internal yang telah teruji dalam skala produksi; pilihan *default*.
    *   **TRIAL**: Siap dicoba pada proyek nyata dengan risiko terkendali; untuk membuktikan kapabilitas.
    *   **ASSESS**: Perlu dieksplorasi dan dipahami melalui PoC (*Proof of Concept*); belum boleh diimplementasikan di produksi.
    *   **HOLD**: Jangan digunakan untuk proyek baru; pertahankan hanya untuk *maintenance*, atau segera lakukan migrasi penggantian.

### 3. Technical Debt Management
Technical Debt (istilah dari Ward Cunningham) adalah metafora ekonomi: mengambil jalan pintas teknis jangka pendek demi mempercepat pengiriman bisnis ibarat meminjam uang. Pinjaman tersebut harus dibayar dengan bunga (*interest*) berupa waktu pengembangan yang melambat di masa depan.

Martin Fowler mengklasifikasikan utang teknis ke dalam **Technical Debt Quadrant**:
*   *Deliberate & Prudent*: Keputusan sadar untuk rilis cepat demi *time-to-market*, dengan rencana pelunasan terjadwal.
*   *Deliberate & Reckless*: Tim mengetahui cara yang benar, namun mengabaikannya demi malas atau tekanan yang tidak disaring.
*   *Inadvertent & Prudent*: Tim telah belajar banyak setelah mengimplementasikan solusi; arsitektur yang dibuat kemarin kini dipahami dapat dibuat lebih baik.
*   *Inadvertent & Reckless*: Tim tidak memahami prinsip dasar arsitektur dan secara tidak sadar menghasilkan *spaghetti code*.

### 4. Modern Architectural Governance & Leadership
Tata kelola arsitektur modern menolak pendekatan terpusat (*Centralized Architecture Review Board*) yang lambat dan birokratis. Sebaliknya, diterapkan **Federated Architectural Governance**:
*   **Guardrails over Gates**: Menggunakan pengujian otomatis (*Fitness Functions*) di CI/CD untuk memvalidasi batasan arsitektur (misal: dependency cycle checks, p99 latency thresholds).
*   **Architectural Enablement**: Arsitek bertindak sebagai konsultan internal yang melatih Tech Lead dan memfasilitasi proses RFC (*Request for Comments*).

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

### Alur Kerja Siklus Hidup ADR (ADR Lifecycle)
1.  **Drafting**: Seorang arsitek atau tech lead menyusun berkas ADR di dalam repositori Git lokal (pada folder `docs/decisions/` atau `doc/adr/`).
2.  **Review (RFC via Pull Request)**: ADR diajukan sebagai PR. Tim mendiskusikan *trade-offs* secara asinkron.
3.  **Consensus / Decision**: Jika disetujui, status diubah menjadi `Accepted` dan dimerge ke *main branch*.
4.  **Superseding**: Jika keputusan di masa depan berubah (misal: Kafka menggantikan RabbitMQ), dibuat ADR baru berstatus `Accepted` yang merujuk ADR lama. ADR lama diubah statusnya menjadi `Superseded by ADR-0024`. **ADR tidak pernah dihapus atau diubah isinya secara retroaktif.**

### Kurasi Technology Radar
1.  **Gathering Blips**: Komite arsitektur mengumpulkan input berkala (triwulanan) dari para engineer di lini depan mengenai tool/framework yang sedang dieksplorasi.
2.  **Triage & Ring Assignment**: Melalui sesi deliberasi triwulanan, kandidat teknologi dipindahkan antar-ring (misalnya dari `ASSESS` ke `TRIAL`).
3.  **Publication**: Radar dirilis dalam bentuk web interaktif statis (dihasilkan melalui repositori Markdown/JSON).

### Strategi Manajemen & Audit Technical Debt
1.  **Debt Identification**: Menggunakan *static analysis* (SonarQube), metrik kompleksitas siklomatik, *churn rate* Git, dan umpan balik tim (*architectural pain points*).
2.  **Valuation & Prioritization**: Evaluasi dampak utang terhadap *developer velocity* dan stabilitas sistem. Buat backlog item dengan nilai bisnis eksplisit.
3.  **Payment Allocation (The 20% Rule)**: Alokasikan 15-20% kapasitas per sprint secara konsisten untuk melunasi utang arsitektur, bukan menunggu hingga fase perbaikan khusus (*refactoring sprint* yang sering kali dibatalkan produk).
4.  **Fitness Functions Execution**: Jalankan tes otomatis pada pipeline CI/CD untuk mencegah masuknya utang arsitektur baru.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 1. Federated Architectural Governance & RFC Workflow

```
DEVELOPER / TECH LEAD                  ARCHITECTURAL GUILD / ARB             CI/CD FITNESS FUNCTION
      │                                             │                                  │
      ├─── 1. Write Proposed ADR ──────────────────►│                                  │
      │    (PR in docs/adr/0042.md)                 │                                  │
      │                                             │                                  │
      │◄── 2. Asynchronous Review (RFC Feedback) ───┤                                  │
      │    - Critique Trade-offs                    │                                  │
      │    - Check Technology Radar alignment       │                                  │
      │                                             │                                  │
      ├─── 3. Finalize Decision ───────────────────►│                                  │
      │    (Status -> ACCEPTED)                     │                                  │
      │                                             ├─── 4. Merge ADR to Main Repos ──►│
      │                                             │                                  │
      │                                             │    5. Validate Invariants ───────┤
      │                                             │       - ArchUnit/Lint Execution  │
      │                                             │       - Package Dependency Check │
      │                                             │◄── 6. Alert on Invariant Breach ─┤
```

### 2. Technology Radar Quadrants and Rings Topology

```
                              TECHNOLOGY RADAR
                                     ▲
                     TECHNIQUES      │      TOOLS
                                     │
                     ┌───────────────┼───────────────┐
                     │   HOLD        │        HOLD   │
                     │    ┌──────────┼──────────┐    │
                     │    │  ASSESS  │  ASSESS  │    │
                     │    │   ┌──────┴──────┐   │    │
                     │    │   │    TRIAL    │   │    │
                     │    │   │   ┌─────┐   │   │    │
                     │    │   │   │ADOPT│   │   │    │
  ───────────────────┼────┼───┼───┼─────┼───┼───┼────┼───────────────────►
                     │    │   │   │ADOPT│   │   │    │
                     │    │   │   └─────┘   │   │    │
                     │    │   │    TRIAL    │   │    │
                     │    │   └──────┬──────┘   │    │
                     │    │  ASSESS  │  ASSESS  │    │
                     │    └──────────┼──────────┘    │
                     │   HOLD        │        HOLD   │
                     └───────────────┼───────────────┘
                                     │
                      PLATFORMS      │   LANGUAGES & FRAMEWORKS
                                     ▼
```

### 3. Martin Fowler's Technical Debt Matrix

```
                        RECKLESS                       PRUDENT
             ┌──────────────────────────────┬──────────────────────────────┐
             │ "We don't have time for      │ "We must ship now and deal   │
 DELIBERATE  │  architecture; just patch    │  with the consequences       │
             │  it up immediately."         │  in the next release."       │
             ├──────────────────────────────┼──────────────────────────────┤
             │ "What is Layering?           │ "Now we know how we should   │
INADVERTENT  │  What is Modularity?         │  have architected it from    │
             │  We just write code."        │  the start."                 │
             └──────────────────────────────┴──────────────────────────────┘
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah implementasi format ADR Nygard standar dalam bentuk Markdown sederhana untuk pemilihan format serialisasi data antar-layanan.

Berkas: `docs/adr/0005-use-protocol-buffers-for-internal-communication.md`

```markdown
# 5. Use Protocol Buffers for Internal Service-to-Service Communication

* Status: accepted
* Date: 2026-03-30
* Deciders: Chief Architect, Lead Backend Engineer, Lead DevOps

## Context and Problem Statement
Komunikasi antar-layanan internal (microservices) saat ini menggunakan REST via JSON over HTTP/1.1.
Seiring bertambahnya volume transaksi (mencapai 45.000 req/sec pada jam sibuk), profil CPU menunjukkan
bahwa 28% penggunaan CPU di cluster Kubernetes dihabiskan untuk parsing dan serialisasi string JSON.
Selain itu, ketiadaan penegakan skema yang ketat (*strict contract enforcement*) telah menyebabkan 
tiga insiden produksi dalam satu bulan terakhir akibat perubahan skema tipe data tanpa deklarasi eksplisit.

## Decision Outcome
Diputuskan untuk menggunakan **Protocol Buffers (Protobuf) over gRPC (HTTP/2)** sebagai standar
komunikasi sinkron antar-layanan internal.

Konsekuensi Positif:
* Efisiensi payload jaringan: Ukuran data berkurang sekitar 60-80% dibandingkan JSON.
* Parsing CPU overhead berkurang secara signifikan karena encoding biner.
* Skema antarmuka dipaksa (*strictly enforced*) melalui berkas definisi `.proto`, mencegah breaking changes.
* Auto-generated client stubs untuk berbagai bahasa pemrograman (Go, Java, Python).

Konsekuensi Negatif:
* Human Readability: Payload tidak dapat dibaca langsung menggunakan cURL standar; memerlukan tooling
  seperti `grpcurl` untuk debugging operasional.
* Kurva pembelajaran (*learning curve*) bagi tim yang belum terbiasa dengan siklus kompilasi Protobuf.
* Load balancing di tingkat L7 (HTTP/2 multiplexing) memerlukan penyesuaian pada Ingress controller/Envoy.
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Pada skenario enterprise nyata, arsitek tidak hanya menulis dokumen, melainkan membangun **Fitness Functions** berbasis kode untuk mengevaluasi apakah *guardrails* arsitektur ditaati secara otomatis.

Di bawah ini adalah sistem Python otomatis yang diintegrasikan ke CI/CD pipeline untuk:
1. Memvalidasi kepatuhan tata kelola ADR (memastikan metadata valid dan status tidak menggantung).
2. Memindai basis kode untuk mendeteksi utang teknis kritis (penggunaan library yang masuk ke status `HOLD` pada *Technology Radar*).

### Implementasi: `scripts/governance_guardrails.py`

```python
#!/usr/bin/env python3
"""
Architectural Governance CI/CD Gate
Tujuan:
1. Validasi integritas berkas ADR (Architecture Decision Records).
2. Deteksi 'Tech Radar Violations' (mencegah impor library berstatus 'HOLD').
"""

import os
import sys
import re
from pathlib import Path
from typing import List, Dict, Tuple

# Konfigurasi Radar Internal: Library yang dilarang (HOLD)
RADAR_HOLD_LIBRARIES = {
    "python": {
        "requests": "Gunakan 'httpx' untuk dukungan async/http2 sesuai ADR-0012.",
        "pycrypto": "Pustaka ini tidak terawat dan memiliki kerentanan kritis. Gunakan 'cryptography'.",
        "pickle": "Raw deserialization dilarang karena risiko RCE. Gunakan Pydantic atau Protobuf."
    }
}

REQUIRED_ADR_HEADERS = ["Status:", "Date:", "Context", "Decision"]
VALID_STATUSES = ["draft", "proposed", "accepted", "rejected", "superseded", "deprecated"]

def validate_adrs(adr_directory: str) -> List[str]:
    """Validasi format, metadata, dan konsistensi direktori ADR."""
    errors = []
    path = Path(adr_directory)
    
    if not path.exists():
        return [f"Direktori ADR tidak ditemukan: {adr_directory}"]

    adr_files = list(path.glob("*.md"))
    if not adr_files:
        return [f"Tidak ada berkas ADR berformat markdown di {adr_directory}"]

    filename_pattern = re.compile(r"^\d{4}-[\w-]+\.md$")

    for file_path in adr_files:
        filename = file_path.name
        
        # Validasi naming convention: e.g., 0001-record-architecture-decisions.md
        if not filename_pattern.match(filename):
            errors.append(
                f"[ADR Naming Error]: {filename} tidak mengikuti konvensi '####-nama-keputusan.md'"
            )
            continue

        content = file_path.read_text(encoding="utf-8")
        
        # Validasi Header Esensial
        for header in REQUIRED_ADR_HEADERS:
            if header.lower() not in content.lower():
                errors.append(f"[ADR Schema Error]: {filename} kehilangan bagian wajib: '{header}'")

        # Validasi Status ADR
        status_match = re.search(r"Status:\s*(\w+)", content, re.IGNORECASE)
        if status_match:
            status = status_match.group(1).lower()
            if status not in VALID_STATUSES:
                errors.append(
                    f"[ADR Status Error]: {filename} memiliki status tidak valid: '{status}'. "
                    f"Status yang diizinkan: {VALID_STATUSES}"
                )
        else:
            errors.append(f"[ADR Status Error]: {filename} tidak mendefinisikan 'Status:' yang valid.")

    return errors

def scan_radar_violations(source_directory: str) -> List[str]:
    """Memindai kode sumber terhadap pustaka yang dilarang pada Technology Radar (HOLD)."""
    violations = []
    source_path = Path(source_directory)
    py_files = list(source_path.rglob("*.py"))

    import_pattern = re.compile(r"^\s*(?:import|from)\s+([a-zA-Z0-9_]+)")

    for py_file in py_files:
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                for line_no, line in enumerate(f, start=1):
                    match = import_pattern.match(line)
                    if match:
                        module_name = match.group(1)
                        if module_name in RADAR_HOLD_LIBRARIES["python"]:
                            reason = RADAR_HOLD_LIBRARIES["python"][module_name]
                            violations.append(
                                f"[Tech Radar Violation]: {py_file}:{line_no} mengimpor '{module_name}'. "
                                f"Alasan HOLD: {reason}"
                            )
        except Exception as e:
            violations.append(f"Gagal memproses berkas {py_file}: {str(e)}")

    return violations

def main():
    adr_dir = os.getenv("ADR_DIR", "docs/adr")
    src_dir = os.getenv("SRC_DIR", "src")

    print(f"=== Menjalankan Architectural Governance Gate ===")
    print(f"Audit ADR di: {adr_dir}")
    print(f"Audit Tech Radar Guardrails di: {src_dir}")
    print("=" * 50)

    adr_errors = validate_adrs(adr_dir)
    radar_errors = scan_radar_violations(src_dir)

    all_failures = adr_errors + radar_errors

    if all_failures:
        print("\n[!] ARCHITECTURAL GOVERNANCE BREACH DETECTED:\n")
        for err in all_failures:
            print(f"  FAILED: {err}")
        print("\nPipeline ditolak. Harap patuhi standar arsitektur organisasi.\n")
        sys.exit(1)
    else:
        print("\n[✓] Seluruh pengujian tata kelola arsitektur lulus.")
        sys.exit(0)

if __name__ == "__main__":
    main()
```

### Eksekusi di Terminal

```bash
# Menjalankan skrip tata kelola di local environment
$ python3 scripts/governance_guardrails.py

=== Menjalankan Architectural Governance Gate ===
Audit ADR di: docs/adr
Audit Tech Radar Guardrails di: src
==================================================

[!] ARCHITECTURAL GOVERNANCE BREACH DETECTED:

  FAILED: [Tech Radar Violation]: src/services/payment.py:4 mengimpor 'requests'. Alasan HOLD: Gunakan 'httpx' untuk dukungan async/http2 sesuai ADR-0012.
  FAILED: [ADR Schema Error]: 0003-use-nosql.md kehilangan bagian wajib: 'Decision'

Pipeline ditolak. Harap patuhi standar arsitektur organisasi.
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

Dalam mendesain model tata kelola dan evolusi arsitektur, arsitek dihadapkan pada dilema spektrum trade-off berikut:

| Dimensi Arsitektural | Pendekatan Terpusat (Centralized ARB) | Pendekatan Terfederasi (Federated / Guardrails) | Analisis Trade-off Rekayasa |
| :--- | :--- | :--- | :--- |
| **Kecepatan Tim (Velocity)** | Rendah. Menunggu persetujuan komite arsitektur mingguan/bulanan. | Tinggi. Tim mengeksekusi secara otonom dalam batasan guardrail otomatis. | Otonomi tim meningkatkan kecepatan, namun berisiko memicu fragmentasi lokal tanpa standardisasi. |
| **Inovasi & Eksperimen** | Tertekan. Engineer ragu mencoba teknologi baru karena hambatan birokrasi. | Terkontrol. Inovasi difasilitasi melalui ring `ASSESS`/`TRIAL` pada Tech Radar. | Eksperimen yang terlalu longgar memicu pembengkakan biaya pemeliharaan multi-stack runtime. |
| **Tingkat Konsistensi Stack** | Sangat Tinggi. Stack monolitik/homogen terjaga ketat. | Moderat. Variasi terkontrol melalui *paved path* / *golden paths*. | Homogenitas mempermudah mobilitas engineer; heterogenitas menyelesaikan problem domain secara presisi. |
| **Beban Kognitif (Cognitive Load)**| Rendah untuk tim (semua diputuskan oleh arsitek), arsitek kewalahan (*bottleneck*). | Terbagi merata. Lead Engineer memikul tanggung jawab atas ADR masing-masing. | Memerlukan maturitas engineering yang tinggi; junior engineer dapat kewalahan tanpa bimbingan. |
| **Pencegahan Technical Debt**| Reaktif. Dideteksi saat arsitek meninjau secara manual. | Proaktif. Ditegakkan melalui *automated fitness functions* dan *debt budgeting*. | Otomatisasi membutuhkan investasi waktu rekayasa awal untuk membangun linter & fitness functions. |

---

## SEKSI 11 — BEST PRACTICES

1.  **Treat Architecture Documentation as Code**:
    *   Simpan ADR dan Tech Radar dalam repositori Git bersama kode sumber.
    *   Gunakan pull request untuk review arsitektural. Jangan gunakan wiki terisolasi (misal Confluence) yang rentan usang dan tidak terintegrasi dengan branch deployment.
2.  **Continuous Architecture Fitness Functions**:
    *   Tulis tes otomatis untuk batasan arsitektur menggunakan alat seperti ArchUnit (Java), NetArchTest (.NET), atau custom AST linters (Go/Python).
    *   Jalankan fitness functions di pipeline CI untuk memvalidasi metrik seperti *cyclomatic complexity*, integritas lapisan domain, dan larangan circular dependency.
3.  **Establish Paved Paths (Golden Paths)**:
    *   Jangan hanya melarang teknologi. Berikan alternatif siap pakai berupa *scaffolding templates* atau *starter kits* untuk opsi yang berstatus `ADOPT`. Developer cenderung memilih jalur termudah; pastikan jalur termudah adalah jalur yang paling benar secara arsitektural.
4.  **Allocate Non-Negotiable Technical Debt Budgets**:
    *   Terapkan perjanjian baku dengan Product Manager: Sisihkan kuota tetap 20% kapasitas engineering per siklus untuk pelunasan utang teknis yang berisiko tinggi.
5.  **Cultivate an Architecture Guild**:
    *   Bentuk *Architecture Guild* atau *Community of Practice* lintas tim. Biarkan keputusan diambil oleh mereka yang paling dekat dengan kode (*subsidiarity principle*), dengan bimbingan dan koordinasi dari Principal/Staff Architects.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1.  **The "Ivory Tower" Architect Pattern**:
    *   *Gejala*: Arsitek yang tidak pernah menulis kode atau tidak pernah mengoperasikan sistem di level produksi merilis instruksi baku tanpa memahami tantangan implementasi nyata.
    *   *Koreksi*: Arsitek harus terus aktif dalam *code review*, memvalidasi implementasi, atau menyediakan waktu *hands-on* reguler bersama tim engineering.
2.  **Write-Only ADRs**:
    *   *Gejala*: Menulis ADR hanya untuk formalitas persetujuan proyek baru, lalu tidak pernah dibaca, diperbarui, atau diacu lagi saat tim melakukan perubahan sistem.
    *   *Koreksi*: Tautkan ADR pada deskripsi pull request dan ticket JIRA/issue tracker saat fitur baru dirancang. Jika keputusan berubah, buat ADR baru yang secara eksplisit menyatakan `Supersedes ADR-xxxx`.
3.  **Equating All Technical Debt to Bugs**:
    *   *Gejala*: Menganggap utang teknis sama dengan *software bugs*, sehingga pelunasan utang teknis selalu ditolak oleh tim produk karena "fitur masih berjalan normal".
    *   *Koreksi*: Komunikasikan utang teknis dalam metrik bisnis: *Developer Lead Time*, *Blast Radius*, estimasi biaya kegagalan sistem, dan *Opportunity Cost*.
4.  **Tech Radar as a Static Annual Document**:
    *   *Gejala*: Membuat radar teknologi sekali setahun dan mengabaikannya di antara periode tersebut.
    *   *Koreksi*: Jadikan kurasi radar sebagai proses triwulanan yang dinamis, terintegrasi dengan evaluasi teknologi dari Proof of Concept yang dilakukan oleh tim.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Menulis ADR Migrasi Kompleks (MADR Format)
*   **Skenario**: Sistem Payment Gateway Anda saat ini menggunakan arsitektur monolitik sinkron berbasis relational DB (PostgreSQL). Saat terjadi lonjakan traffic flash-sale, proses checkout gagal akibat *connection pool exhaustion* dan lock contention.
*   **Tugas**: Tulis sebuah ADR lengkap menggunakan format MADR (`docs/adr/0010-async-checkout-event-driven.md`) yang memutuskan transisi ke pemrosesan pembayaran asinkron.
*   **Ketentuan**: Wajib menyertakan minimal 2 alternatif arsitektur yang dipertimbangkan (misalnya: Kafka vs. AWS SQS vs. Redis Streams), pro-kontra masing-masing, serta mitigasi konsistensi data (*Outbox Pattern*, *Saga*).

### Latihan 2: Membangun Fitness Function untuk Modularity Enforcing
*   **Skenario**: Modul inti domain finansial (*Financial Core Domain*) tidak boleh mengimpor modul Delivery/Logistics secara langsung karena melanggar batasan konteks (*Bounded Context Boundary*).
*   **Tugas**: Buat skrip tes otomatis (menggunakan Python, Node.js, atau Bash) yang memeriksa dependensi berkas impor pada repositori untuk mendeteksi pelanggaran tersebut dan menghasilkan kegagalan tes (exit code 1) jika pelanggaran ditemukan.

### Latihan 3: Kalkulasi dan Prioritas Technical Debt Menggunakan Risk Matrix
*   **Skenario**: Anda mewarisi legacy codebase dengan 4 kategori utang teknis:
    1.  Ketiadaan unit test pada modul otentikasi warisan (Core Auth).
    2.  Penggunaan library ORM yang sudah *end-of-life* (EOL).
    3.  Duplikasi kode kalkulasi diskon di 5 repositori terpisah.
    4.  Kubernetes cluster masih berjalan pada versi v1.21 (tidak didukung lagi).
*   **Tugas**: Buat matriks evaluasi berbasis *Probability of Failure* vs *Business Impact* (skala 1-5). Tentukan urutan eksekusi pembersihan dan formulasikan argumen komersial/bisnis untuk meyakinkan Chief Product Officer (CPO).

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

### Pertanyaan Evaluasi

#### 1. Kapan sebuah berkas Architecture Decision Record (ADR) lama boleh diubah isinya secara drastis atau dihapus dari repositori?
A. Setiap kali ada arsitek baru yang bergabung dan tidak setuju dengan keputusan lama.  
B. Saat implementasi kode dari keputusan tersebut telah dihapus seluruhnya dari produksi.  
C. ADR bersifat *immutable log*; berkas lama tidak boleh dihapus atau diubah substansinya secara retroaktif, melainkan harus ditandai sebagai `Superseded` atau `Deprecated` melalui ADR baru.  
D. ADR boleh dihapus jika keputusan arsitektur tersebut diambil lebih dari dua tahun yang lalu.

#### 2. Pada ThoughtWorks Technology Radar, sebuah framework baru yang sangat menjanjikan telah berhasil diuji dalam implementasi Proof of Concept (PoC) skala kecil internal, namun belum pernah dipakai di lingkungan beban produksi tinggi. Ring manakah yang paling tepat untuk framework tersebut?
A. ADOPT  
B. TRIAL  
C. ASSESS  
D. HOLD  

#### 3. Menurut klasifikasi Technical Debt Quadrant dari Martin Fowler, situasi di mana tim engineering terpaksa merilis produk dengan implementasi cepat yang tidak ideal demi memenangkan momentum pasar penting, disertai rencana refactoring eksplisit pada sprint berikutnya, masuk dalam kategori:
A. Reckless & Deliberate  
B. Prudent & Deliberate  
C. Reckless & Inadvertent  
D. Prudent & Inadvertent  

#### 4. Apa fungsi utama dari "Architectural Fitness Function" dalam evolusi sistem perangkat lunak?
A. Memastikan seluruh engineer memiliki kebugaran fisik yang optimal saat bertugas on-call.  
B. Memberikan mekanisme evaluasi objektif dan otomatis (misalnya melalui CI/CD) untuk memeriksa apakah sistem mempertahankan karakteristik arsitekturalnya seiring waktu.  
C. Mengukur kecepatan pengetikan baris kode (LoC per jam) yang dihasilkan arsitek.  
D. Menguji performa API hanya pada lingkungan staging sebelum rilis akhir tahun.

#### 5. Apa kelemahan utama dari pola kepemimpinan arsitektur "Centralized Ivory Tower ARB"?
A. Menghasilkan terlalu banyak dokumentasi dalam bentuk kode.  
B. Mempercepat siklus rilis fitur hingga sulit dipantau tim audit.  
C. Menjadi leher botol (*bottleneck*) birokrasi yang mematikan inisiatif inovasi tim, memisahkan pembuat keputusan dari realitas implementasi, dan memicu *shadow architecture*.  
D. Menyebabkan sistem terlalu bergantung pada platform cloud-native.

---

### Kunci Jawaban & Penjelasan

*   **1: C** — ADR berfungsi sebagai jejak sejarah (audit trail) evolusi sistem. Menghapus atau mengubah ADR lama akan merusak konteks historis arsitektur. Keputusan baru harus dimuat dalam ADR terpisah yang membatalkan (*supersedes*) keputusan lama.
*   **2: B** — Cincin *TRIAL* diperuntukkan bagi teknologi yang telah melewati tahap asesmen awal dan siap dicoba pada proyek bisnis nyata dengan skala/risiko yang terkelola guna membuktikan ketahanannya.
*   **3: B** — *Prudent & Deliberate* adalah utang teknis strategis yang diambil dengan sadar (*deliberate*) dan bijak (*prudent*), di mana tim memahami konsekuensinya dan mengelola risikonya secara profesional.
*   **4: B** — Istilah yang diperkenalkan oleh Neal Ford dkk. dalam *Building Evolutionary Architectures*: Fitness Function adalah tes terautomasi yang memverifikasi integritas arsitektur (kepatuhan layer, performa, keamanan, dsb).
*   **5: C** — Tata kelola sentralistik yang kaku membuat arsitek terisolasi dari permasalahan nyata developer di lapangan. Hal ini memperlambat *delivery* dan mendorong developer untuk mengambil jalan pintas rahasia (*shadow architecture*).

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

### Buku Standar Industri
1.  *Building Evolutionary Architectures: Support Constant Change* (2nd Edition) — Neal Ford, Rebecca Parsons, Patrick Kua, Pramod Sadalage (O'Reilly Media).
2.  *Software Architecture: The Hard Parts* — Neal Ford, Mark Richards, Pramod Sadalage, Zhamak Dehghani (O'Reilly Media).
3.  *The Staff Engineer's Path: A Guide for Individual Contributors Navigating Innovation and Change* — Tanya Reilly (O'Reilly Media).
4.  *Managing Technical Debt: Reducing Friction in Software Development* — Philippe Kruchten, Robert Nord, Ipek Ozkaya (Addison-Wesley).

### Standar & Tooling Terbuka
*   **MADR (Markdown Any Architecture Decision Records)**: [https://adr.github.io/madr/](https://adr.github.io/madr/)
*   **ThoughtWorks Technology Radar Documentation**: [https://www.thoughtworks.com/radar](https://www.thoughtworks.com/radar)
*   **ArchUnit Architecture Verification Library**: [https://www.archunit.org/](https://www.archunit.org/)
*   **ADR Tools CLI**: Utility untuk automasi pembuatan dan indexing berkas ADR (`adr-tools` oleh Nat Pryce).

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1.  **Arsitektur Berkelanjutan Membutuhkan Tata Kelola Berkelanjutan**: Desain sistem terbaik akan terdegradasi jika tidak dipelihara melalui proses evaluasi berkelanjutan yang transparan dan dapat dilacak.
2.  **ADR Mencegah Hilangnya Konteks Historis**: Dokumentasikan alasan arsitektural (*why*), batasan yang dihadapi, serta *trade-offs* yang disepakati. Simpan ADR sedekat mungkin dengan kode (in-repo Git).
3.  **Technology Radar Mengurangi Cognitive Load**: Pandu organisasi dalam memilih alat dengan jelas melalui kuadran dan cincin status (`ADOPT`, `TRIAL`, `ASSESS`, `HOLD`).
4.  **Utang Teknis Harus Dikelola Secara Finansial**: Kategorikan utang secara objektif. Pisahkan utang yang disengaja dan bijak dari kelalaian teknis, lalu negosiasikan kapasitas pelunasan tetap (~20%) dalam alokasi produk.
5.  **Kepemimpinan Arsitektur Modern Berbasis Guardrails**: Tinggalkan model birokrasi *Ivory Tower*. Terapkan *Federated Governance*, automasi batasan arsitektur menggunakan *fitness functions*, dan bangun jalur mudah (*paved path*) untuk memberdayakan tim rekayasa.

---

## SEKSI 17 — GLOSARIUM

*   **Architecture Decision Record (ADR)**: Berkas dokumen terstruktur yang menangkap satu keputusan arsitektural penting beserta konteks dan konsekuensinya.
*   **Architectural Fitness Function**: Mekanisme komputasional objektif (tes terautomasi, metrik build) yang digunakan untuk memvalidasi apakah sistem memenuhi standar atribut kualitas arsitektur.
*   **Ivory Tower Architecture**: Istilah peyoratif untuk gaya kepemimpinan arsitek yang membuat keputusan teoritis di ruang terisolasi tanpa interaksi nyata dengan kondisi basis kode atau tim teknis di lapangan.
*   **Technology Radar**: Portofolio visual terstruktur yang menunjukkan penilaian organisasi terhadap kumpulan teknologi pada titik waktu tertentu.
*   **Technical Debt (Utang Teknis)**: Biaya terselubung akibat memilih solusi cepat yang tidak optimal saat ini, yang akan meningkatkan biaya rekayasa di masa mendatang.
*   **Paved Path (Golden Path)**: Kumpulan template, pustaka standar, dan pipeline CI/CD yang didukung penuh oleh arsitek untuk mempermudah developer membangun layanan sesuai standar baku tanpa beban kognitif berlebih.
*   **Code Churn**: Frekuensi perubahan pada suatu berkas kode dalam periode tertentu; metrik penting untuk mengidentifikasi area yang sarat utang teknis dan rawan regresi.

---

## SEKSI 18 — CATATAN INSTRUKTUR

### Poin Penekanan Materi
*   Tegaskan bahwa ADR **bukanlah** dokumentasi sistem lengkap (*system documentation*), melainkan log keputusan kejadian (*event log*). Jangan menulis ulang diagram kelas/ERD di dalam ADR.
*   Bantu peserta memahami bahwa *Technical Debt* tidak selalu buruk. Mengambil utang teknis yang *Deliberate & Prudent* adalah instrumen bisnis yang valid untuk validasi *Product-Market Fit*. Yang menjadi racun adalah utang yang tidak diukur, tidak disadari (*Inadvertent*), dan tidak pernah dibayar.

### Hambatan Umum Siswa
*   *Resistensi Dokumentasi*: Peserta sering merasa penulisan ADR membuang waktu. Tunjukkan bagaimana satu sesi penulisan ADR selama 30 menit dapat menghemat ratusan jam rapat debat berulang di masa mendatang.
*   *Kecenderungan Otoriter*: Engineer senior baru sering ingin langsung menjadi penentu tunggal (gatekeeper). Gunakan simulasi *RFC Process* untuk melatih kemampuan memengaruhi tim melalui persuasi berbasis bukti (*influence without authority*).

### Ide Sesi Interaktif / Roleplay
*   Lakukan simulasi **Architecture Review Board Mock**: Bagilah kelas menjadi dua kelompok:
    *   Kelompok 1 mengajukan migrasi radikal (misalnya: mengganti basis data SQL dengan Graph DB).
    *   Kelompok 2 bertindak sebagai Architecture Guild yang membedah *trade-offs*, mengevaluasi kesesuaian radar, dan menuntut pembuatan fitness functions pendukung.

---

## SEKSI 19 — CHANGELOG & VERSI

*   **Versi 1.0.0** (Maret 2026):
    *   Rilis awal modul tata kelola dan kepemimpinan arsitektur enterprise.
    *   Integrasi spesifikasi ADR standar MADR dan Nygard.
    *   Penambahan kode executable untuk CI/CD Architectural Governance Guardrails.
    *   Penyelarasan diagram topologi Technology Radar dan Fowler Technical Debt Matrix.

---

## SEKSI 20 — NAVIGASI KURIKULUM

*   **Modul Sebelumnya**: `ARCH-06-09-02`: *Chaos Engineering, Disaster Recovery & High Availability Strategies*
*   **Modul Saat Ini**: `ARCH-06-10-01`: *Architectural Governance, Evolution & Leadership: Architecture Decision Records (ADR), Technology Radars, Technical Debt Management, Architectural Leadership & Communication*
*   **Modul Berikutnya**: `ARCH-06-10-02`: *Enterprise Architecture Patterns, Domain-Driven Design Strategic Mapping & Organizational Alignment*