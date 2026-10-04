# Bab 10: Content Health, Doc Decay, Deprecation, & Versioning

## Module 01: Architecture of Documentation Health, Decay Prevention, and Versioning for AI & Autonomous Systems

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis dan Mengukur *Doc Decay***: Mengidentifikasi degradasi semantik dan keusangan teknis (*content rot*) dalam dokumentasi menggunakan metrik terukur (*freshness score*, *code-doc parity ratio*, dan *usage-decay velocity*).
- **Merancang Arsitektur *Deprecation & Sunset***: Membangun siklus hidup depresiasi dokumentasi formal berbasis standar RFC 8594 (*Sunset HTTP Header*) dan skema metadata terstruktur untuk sistem manusia dan agen otonom.
- **Mengimplementasikan Multi-Tier Versioning**: Mengembangkan strategi *versioning* terpadu (SemVer 2.0.0) yang menyinkronkan *codebase*, *agent tool registry schema*, *model context prompt*, dan *documentation artifact*.
- **Membangun Automated Health Engine**: Mengembangkan *pipeline* otomatisasi berbasis Python/CI-CD untuk mendeteksi *drift* antara spesifikasi API (OpenAPI/JSONSchema) dengan korpus dokumentasi sebelum berdampak pada *execution failure* pada sistem RAG (*Retrieval-Augmented Generation*) dan agen AI.

---

### 2. Concept Overview

Dalam ekosistem rekayasa perangkat lunak tradisional, dokumentasi yang usang (*stale documentation*) berakibat pada penurunan produktivitas pengembang. Namun, dalam ekosistem **AI, Data Pipelines, dan Autonomous Agents**, dokumentasi berfungsi ganda: sebagai referensi manusia dan sebagai **basis pengetahuan deterministik bagi Large Language Models (LLM)** melalui RAG atau *Tool Calling*. 

*Doc Decay* dalam konteks ini bukan sekadar tautan rusak (HTTP 404), melainkan **Semantic Drift**: kondisi di mana representasi tekstual mengenai kapabilitas, parameter, batasan, dan skema sistem tidak lagi selaras dengan kondisi riil sistem produksi. 

```
+-----------------------------------------------------------------------------+
|                            THE DOC DECAY SPECTRUM                           |
+-----------------------------------------------------------------------------+
| 1. Syntactic Decay   : Broken links, invalid code blocks, formatting errors. |
| 2. Structural Decay  : Schema mismatch (docs say string, code expects int).  |
| 3. Semantic Drift    : Description implies behavior A, model executes B.     |
| 4. Contextual Decay  : Outdated best practices, high latency patterns kept.  |
+-----------------------------------------------------------------------------+
```

Model mental pengelolaan dokumentasi modern memandangnya sebagai **Immutable State per System Version**:
1. **Freshness & Decay**: Dokumentasi memiliki waktu paruh (*half-life*). Seiring *commits* masuk ke repositori agen tanpa pembaruan dokumen, entropi meningkat dan *health score* menurun.
2. **Deprecation**: Proses multi-fase eksplisit yang memberi sinyal kepada konsumen (manusia dan agen AI) bahwa suatu antarmuka (*interface*), *tool*, atau endpoint akan dihentikan, menyediakan jalur migrasi (*migration path*), dan menetapkan batas waktu terminasi (*sunset date*).
3. **Versioning**: Pemetaan bideksional deterministik antara versi artefak kode, versi bobot model (*model checkpoints*), versi *tool definitions*, dan versi teks dokumentasi.

---

### 3. Why It Matters

#### Dampak Nyata pada Sistem Otonom & RAG
Jika sebuah API mengubah tipe parameter dari `optional` menjadi `required`, namun dokumentasi tidak diperbarui:
1. **Autonomous Agents**: Agen yang menggunakan *zero-shot tool calling* membaca dokumentasi usang, menghasilkan payload invalid, masuk ke dalam *infinite retry loops*, menghabiskan *token quota*, dan memicu kegagalan transaksi (*task failure*).
2. **Enterprise RAG Systems**: Mesin pencari vektor (*vector retriever*) menyajikan *chunks* dokumentasi lama yang memiliki kesamaan semantik (*cosine similarity*) tinggi dengan *query* pengguna, menyebabkan LLM mengalami *grounded hallucination*—menjawab dengan percaya diri berdasarkan data yang kedaluwarsa.
3. **SLA & Compliance**: Pada sektor finansial dan kesehatan, menyajikan dokumentasi yang mengalami *drift* terkait retensi data atau kepatuhan privasi dapat memicu pelanggaran regulasi hukum (GDPR, HIPAA, SOC2).

---

### 4. Arsitektur & Diagram Komponen

Arsitektur berikut mengilustrasikan **Automated Documentation Health & Versioning Pipeline** yang terintegrasi langsung dengan repositori *agent tool* dan *vector database*:

```
+-------------------+      +----------------------+
| Git Repository    |      | Agent Tool Registry  |
| (Code + Markdown) |      | (OpenAPI/JSONSchema) |
+---------+---------+      +----------+-----------+
          |                           |
          +-------------+-------------+
                        |
                        v
        +---------------+---------------+
        |   CI/CD Documentation Engine  |
        |   (GitHub Actions / GitLab CI)|
        +---------------+---------------+
                        |
       [Step 1: Schema Parity Inspector]
       * Compares Markdown specs vs Code Schemas
                        |
       [Step 2: Doc Health & Decay Analyzer]
       * Evaluates: Age, Commits drift, Run Code Snippets
                        |
       [Step 3: Deprecation & Sunset Injector]
       * Adds RFC 8594 headers & visual warnings
                        |
          +-------------+-------------+
          |                           |
          v                           v
+-------------------+       +--------------------+
| Static Site Docs  |       | RAG / Vector Store |
| (VitePress/Docus) |       | (Sync / Chunking)  |
+-------------------+       +--------------------+
          |                           |
          v                           v
+-------------------+       +--------------------+
|   Human Readers   |       | Autonomous Agents  |
| (Software Engs)   |       | (Tool Execution)   |
+-------------------+       +--------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### 5.1 Algoritma Doc Decay Scoring
Skor kesehatan dokumen ($H$) dihitung berdasarkan fungsi penalti terbobot (*weighted penalty function*):

$$H = 100 - (w_t \cdot \Delta t + w_c \cdot \Delta c + w_p \cdot P + w_e \cdot E)$$

Dimana:
- $\Delta t$: Hari sejak verifikasi manual terakhir (*days since last manual review*).
- $\Delta c$: Jumlah *commits* pada kode terkait sejak pembaruan dokumen terakhir (*code drift*).
- $P$: Penalti inkonsistensi skema (*schema mismatch flag*: 0 atau 1).
- $E$: Penalti kegagalan eksekusi cuplikan kode (*snippet execution errors*).
- $w_t, w_c, w_p, w_e$: Bobot normalisasi (contoh: $w_t = 0.1$, $w_c = 1.5$, $w_p = 30$, $w_e = 40$).

Dokumen dengan nilai $H < 70$ otomatis ditandai sebagai *Needs Review*, dan $H < 50$ memicu status *Stale/Quarantine* sehingga di-eksklusi dari penyajian konteks RAG.

#### 5.2 Siklus Hidup Depresiasi (The Deprecation Lifecycle)
Siklus hidup depresiasi wajib melewati 4 status formal:

```
[ ACTIVE ] 
    |
    v (Deprecation Notice Issued: Sunset date defined, migration path documented)
[ DEPRECATED ] 
    |
    v (Sunset Date Reached: Execution blocked or redirected)
[ SUNSET / TOMBSTONED ] 
    |
    v (Retention Period Expired: Removed from active index)
[ ARCHIVED ]
```

1. **Active**: Dokumentasi mutakhir dan merepresentasikan kondisi produksi.
2. **Deprecated**: Menampilkan peringatan visual (*admonition warning*) bagi manusia, metadata `deprecated: true` bagi parser LLM, dan HTTP Header `Sunset` sesuai RFC 8594.
3. **Sunset / Tombstoned**: Halaman digantikan dengan *tombstone document* yang hanya berisi penjelasan alasan penghentian dan instruksi migrasi.
4. **Archived**: Dipindahkan ke *cold storage/subpath* terisolasi, dihapus dari indeks *embedding* RAG untuk mencegah polusi konteks.

#### 5.3 Co-Versioning Triad
Dalam arsitektur agen otonom, versi dokumentasi harus terikat secara ketat (*tightly coupled*) melalui **Co-Versioning Triad**:
- **App/Engine Version**: Rilis fungsionalitas sistem (misal: `v2.4.0`).
- **Tool Interface Version**: Skema input/output *tool* yang dieksekusi oleh LLM (misal: `tools/search_v2.json`).
- **Context/Doc Version**: Dokumentasi yang diubah menjadi representasi *embedding* untuk inferensi RAG (misal: `docs/v2.4.0/tools/search.md`).

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi sistem pemeriksa kesehatan dokumen otomatis (*Doc Health & Deprecation Linter*) berbasis Python. Modul ini memeriksa *schema parity*, mengevaluasi *staleness*, dan menyuntikkan metadata deprecation.

```python
"""
DocHealth & Deprecation Engine for AI Agent Architectures.
Provides automated schema verification, staleness scoring, and tombstone enforcement.
"""

from __future__ import annotations

import datetime
import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("DocHealthEngine")


class DocStatus(str, Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    SUNSET = "sunset"
    ARCHIVED = "archived"


@dataclass
class HealthScoreResult:
    doc_path: Path
    score: float
    status: DocStatus
    is_rag_eligible: bool
    issues: List[str] = field(default_factory=list)


@dataclass
class ToolParameter:
    name: str
    param_type: str
    required: bool


class DocHealthEngine:
    def __init__(
        self,
        max_allowed_drift_days: int = 90,
        decay_weight_days: float = 0.2,
        decay_weight_commits: float = 2.0,
    ) -> None:
        self.max_allowed_drift_days = max_allowed_drift_days
        self.decay_weight_days = decay_weight_days
        self.decay_weight_commits = decay_weight_commits

    def parse_markdown_frontmatter(self, content: str) -> Tuple[Dict[str, Any], str]:
        """Parses YAML-like frontmatter without external dependency vulnerabilities."""
        frontmatter = {}
        body = content
        pattern = r"^---\s*\n(.*?)\n---\s*\n"
        match = re.search(pattern, content, re.DOTALL)
        
        if match:
            raw_fm = match.group(1)
            body = content[match.end():]
            for line in raw_fm.splitlines():
                if ":" in line:
                    key, val = line.split(":", 1)
                    frontmatter[key.strip()] = val.strip().strip('"').strip("'")
                    
        return frontmatter, body

    def extract_doc_parameters(self, body: str) -> Dict[str, ToolParameter]:
        """Extracts documented parameters from markdown tables."""
        parameters = {}
        # Expecting markdown table format: | param_name | type | required |
        table_row_pattern = r"\|\s*([a-zA-Z0-9_]+)\s*\|\s*([a-zA-Z0-9_]+)\s*\|\s*(true|false)\s*\|"
        matches = re.findall(table_row_pattern, body, re.IGNORECASE)
        
        for name, p_type, req in matches:
            parameters[name] = ToolParameter(
                name=name,
                param_type=p_type.lower(),
                required=req.lower() == "true",
            )
        return parameters

    def evaluate_schema_parity(
        self, doc_params: Dict[str, ToolParameter], live_schema: Dict[str, Any]
    ) -> List[str]:
        """Compares documentation parameters with active JSONSchema definitions."""
        discrepancies = []
        live_properties = live_schema.get("properties", {})
        live_required = live_schema.get("required", [])

        # Check for missing parameters in documentation
        for prop_name, prop_data in live_properties.items():
            if prop_name not in doc_params:
                discrepancies.append(f"Param '{prop_name}' exists in code schema but missing in documentation.")
            else:
                doc_p = doc_params[prop_name]
                expected_type = prop_data.get("type", "any").lower()
                if doc_p.param_type != expected_type:
                    discrepancies.append(
                        f"Type mismatch on '{prop_name}': Doc says '{doc_p.param_type}', Code expects '{expected_type}'."
                    )
                is_actually_required = prop_name in live_required
                if doc_p.required != is_actually_required:
                    discrepancies.append(
                        f"Requirement mismatch on '{prop_name}': Doc says required={doc_p.required}, Code is {is_actually_required}."
                    )

        # Check for ghost parameters in documentation (parameters removed from code)
        for doc_p_name in doc_params:
            if doc_p_name not in live_properties:
                discrepancies.append(f"Ghost param '{doc_p_name}' documented but not present in code schema.")

        return discrepancies

    def calculate_health(
        self,
        doc_path: Path,
        live_schema_path: Optional[Path] = None,
        simulated_commits_ahead: int = 0,
    ) -> HealthScoreResult:
        """Computes comprehensive health score of a document artifact."""
        if not doc_path.exists():
            raise FileNotFoundError(f"Document not found: {doc_path}")

        raw_content = doc_path.read_text(encoding="utf-8")
        frontmatter, body = self.parse_markdown_frontmatter(raw_content)

        issues: List[str] = []
        score: float = 100.0

        # 1. Parse Status and Dates
        status = DocStatus(frontmatter.get("status", DocStatus.ACTIVE.value))
        last_reviewed_str = frontmatter.get("last_reviewed")
        sunset_date_str = frontmatter.get("sunset_date")

        if not last_reviewed_str:
            issues.append("Missing 'last_reviewed' frontmatter.")
            score -= 20.0
            days_unreviewed = self.max_allowed_drift_days
        else:
            last_reviewed = datetime.datetime.strptime(last_reviewed_str, "%Y-%m-%d").date()
            days_unreviewed = (datetime.date.today() - last_reviewed).days

        # Decay via days elapsed
        if days_unreviewed > 0:
            score -= days_unreviewed * self.decay_weight_days

        # Decay via code commits drift
        score -= simulated_commits_ahead * self.decay_weight_commits

        # 2. Schema Parity Evaluation
        if live_schema_path and live_schema_path.exists():
            try:
                live_schema = json.loads(live_schema_path.read_text(encoding="utf-8"))
                doc_params = self.extract_doc_parameters(body)
                discrepancies = self.evaluate_schema_parity(doc_params, live_schema)
                if discrepancies:
                    score -= len(discrepancies) * 15.0
                    issues.extend(discrepancies)
            except Exception as e:
                logger.error(f"Failed parsing schema {live_schema_path}: {e}")
                issues.append(f"Schema load failure: {str(e)}")
                score -= 30.0

        # 3. Sunset / Tombstone Policy Enforcement
        if status == DocStatus.DEPRECATED and sunset_date_str:
            sunset_date = datetime.datetime.strptime(sunset_date_str, "%Y-%m-%d").date()
            if datetime.date.today() >= sunset_date:
                status = DocStatus.SUNSET
                issues.append(f"Document has passed sunset date ({sunset_date_str}) and must be tombstoned.")
                score = 0.0

        score = max(0.0, min(100.0, score))
        
        # A document is RAG eligible ONLY if health score >= 70 and not sunset/archived
        is_rag_eligible = score >= 70.0 and status not in [DocStatus.SUNSET, DocStatus.ARCHIVED]

        return HealthScoreResult(
            doc_path=doc_path,
            score=round(score, 2),
            status=status,
            is_rag_eligible=is_rag_eligible,
            issues=issues,
        )


# =====================================================================
# Demonstration & Self-Validation
# =====================================================================
if __name__ == "__main__":
    temp_dir = Path("/tmp/doc_engine_demo")
    temp_dir.mkdir(parents=True, exist_ok=True)

    # 1. Mock JSONSchema representing code reality
    tool_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "top_k": {"type": "integer"},
            "filter_ns": {"type": "string"},
        },
        "required": ["query"],
    }
    schema_file = temp_dir / "tool_search_schema.json"
    schema_file.write_text(json.dumps(tool_schema, indent=2))

    # 2. Mock Markdown Doc with subtle drift
    doc_content = """---
status: active
last_reviewed: 2024-01-01
---
# Search Agent Tool

| query | string | true |
| top_k | string | false |
"""
    doc_file = temp_dir / "tool_search.md"
    doc_file.write_text(doc_content)

    # 3. Run Engine
    engine = DocHealthEngine()
    result = engine.calculate_health(
        doc_path=doc_file,
        live_schema_path=schema_file,
        simulated_commits_ahead=12,
    )

    print("\n--- Doc Health Audit Result ---")
    print(f"Path            : {result.doc_path}")
    print(f"Health Score    : {result.score} / 100")
    print(f"Current Status  : {result.status.value}")
    print(f"RAG Eligible    : {result.is_rag_eligible}")
    print("Issues Detected :")
    for issue in result.issues:
        print(f"  [!] {issue}")
```

---

### 7. Edge Cases & Failure Modes

| Edge Case / Failure Mode | Akar Masalah (*Root Cause*) | Dampak Sistemik (*Impact*) | Strategi Mitigasi Terverifikasi |
| :--- | :--- | :--- | :--- |
| **Zombie Context Vectors** | Halaman dokumentasi di-*deprecate* di Git, namun proses sinkronisasi RAG gagal menghapus vektor lama (*dangling embeddings*). | LLM tetap mengambil instruksi usang melalui penelusuran semantik similarity. | Implementasikan *atomic transactional upsert/delete* pada Vector DB menggunakan *manifest hash* per *build*. |
| **Semantic Drift Tanpa Kode** | Definisi API tetap sama, tetapi domain bisnis berubah (misal: ambang batas kuota transaksi berubah). | Agen beroperasi dengan asumsi batasan lama, menyebabkan penolakan transaksi di sisi *backend*. | Wajibkan pengujian eksekusi *black-box assertion* berbasis *doc-snippets* secara harian via cron. |
| **Circular Deprecation Path** | Doc A menyarankan migrasi ke Doc B, namun Doc B menandai fitur tersebut *deprecated* dan mengarah kembali ke Doc A. | Pengembang dan agen perencana (*planner agents*) terjebak dalam rekursi tak berhingga (*infinite resolution loop*). | Analisis graf asiklik terarah (*Directed Acyclic Graph / DAG verification*) pada seluruh tautan depresiasi saat kompilasi CI. |
| **Prompt Injection via Tombstone** | Halaman *tombstone* publik diisi tautan pihak ketiga eksternal yang kemudian kedaluwarsa dan diambil alih (*domain hijacking*). | Penyerang menyuntikkan instruksi berbahaya ke dalam konteks agen yang merayapi tautan tersebut. | Batasi *tombstone pages* hanya ke rujukan internal terenkripsi tanpa dependensi eksternal. |

---

### 8. Trade-offs & Alternatif Solusi

#### Static Linters vs. LLM-as-a-Judge untuk Doc Health

```
                [Doc Analysis Approaches]
                          |
        +-----------------+-----------------+
        |                                   |
        v                                   v
[Deterministic AST/Regex]           [LLM-as-a-Judge]
  * Extremely Fast (<10ms)            * High Semantic Comprehension
  * Zero Dollar/Token Cost            * Identifies Subtle Intent Drift
  * Brittle to Complex Syntax         * High Token Cost & Non-deterministic
  * Cannot verify natural intent      * Latency Bottleneck in CI
```

- **Pilihan Terpilih**: Gunakan **Deterministic AST/Regex + JSONSchema Validator** sebagai *hard-gate* pemblokir pada CI/CD *Pull Requests*. Gunakan **LLM-as-a-Judge** secara berkala (misal: mingguan via *background worker*) hanya untuk mengevaluasi kejelasan penjelasan semantik dan kualitas contoh implementasi (*examples completeness*).

#### Hard Deletion vs. Tombstoning
- **Hard Deletion**: Menghapus file secara instan dari repositori.
  - *Kelemahan*: Menghasilkan HTTP 404, merusak tautan eksternal yang telah terindeks manusia, dan memutus rantai penelusuran versi model lama.
- **Tombstoning (Direkomendasikan)**: Menyisakan dokumen minimalis yang berisi metadata kepunahan, alasan penghentian, serta tautan ekuivalen baru. Menghindari 404 dan secara eksplisit mendidik LLM mengenai kapabilitas yang tidak lagi didukung.

---

### 9. Best Practices & Standar Industri

1. **RFC 8594 Sunset Header Enforcement**: Setiap dokumentasi atau endpoint API yang didepresiasi harus menyertakan respons header HTTP standar:
   ```http
   Deprecation: @1735689600
   Sunset: Wed, 01 Jan 2025 00:00:00 GMT
   Link: <https://api.domain.com/v2/docs>; rel="successor-version"
   ```
2. **Strict SemVer untuk Skema & Dokumentasi**:
   - **PATCH**: Pembaruan klarifikasi teks dokumentasi, perbaikan *typo*, tanpa perubahan tanda tangan metode (*signature*).
   - **MINOR**: Penambahan parameter opsional baru pada *tool*, penambahan panduan baru.
   - **MAJOR**: Modifikasi parameter wajib, penghapusan fungsionalitas, atau perombakan skema respon JSON.
3. **Automated Documentation Quarantine**: Dokumen dengan skor *Doc Decay* di bawah nilai 70 harus diisolasi dari indeks penelusuran produksi (*noindex* pada HTML meta, dan dikeluarkan dari korpus RAG) guna melindungi integritas agen otonom.

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda bertindak sebagai Documentation Engineer pada platform agen AI keuangan. Tugas Anda adalah mengonfigurasi mekanisme proteksi otomatis di CI/CD yang mendeteksi *doc rot*, memverifikasi skema *tool*, dan menolak *merge request* jika dokumentasi tidak sinkron dengan skema kode.

#### Langkah 1: Persiapan Lingkungan
Buat direktori dan struktur file berikut:

```bash
mkdir -p doc-health-lab/docs doc-health-lab/schemas
cd doc-health-lab
```

#### Langkah 2: Buat Skema Live Tool
Tulis file `schemas/transaction_tool.json`:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ExecuteTransaction",
  "type": "object",
  "properties": {
    "account_id": {
      "type": "string"
    },
    "amount": {
      "type": "number"
    },
    "currency": {
      "type": "string"
    }
  },
  "required": ["account_id", "amount", "currency"]
}
```

#### Langkah 3: Buat Dokumentasi yang Mengalami Semantic Decay
Tulis file `docs/transaction_tool.md`. Perhatikan bahwa tipe `amount` salah (*integer* alih-alih *number*) dan parameter `currency` tidak tercatat:

```markdown
---
status: active
last_reviewed: 2023-01-01
---

# Execute Transaction Tool

Dokumentasi ini menjelaskan eksekusi transfer dana via agen.

| account_id | string | true |
| amount | integer | true |
```

#### Langkah 4: Tulis Script Verifikator CI (Verification Guard)
Tulis file `verify_health.py`:

```python
import sys
from pathlib import Path
# Mengimpor Engine dari subbab 6
from doc_health_engine import DocHealthEngine, DocStatus

def run_lab_verification():
    engine = DocHealthEngine()
    doc_path = Path("docs/transaction_tool.md")
    schema_path = Path("schemas/transaction_tool.json")
    
    result = engine.calculate_health(
        doc_path=doc_path,
        live_schema_path=schema_path,
        simulated_commits_ahead=5
    )
    
    print(f"Health Check Score: {result.score}/100")
    print(f"RAG Eligible Status: {result.is_rag_eligible}")
    
    if not result.is_rag_eligible:
        print("\n[CRITICAL FAILURE] Document health standards violated:")
        for issue in result.issues:
            print(f"  -> {issue}")
        print("\nCI Pipeline: BLOCKED. Fix discrepancies before merge.")
        sys.exit(1)
    else:
        print("\nCI Pipeline: PASSED. Documentation is healthy.")
        sys.exit(0)

if __name__ == "__main__":
    run_lab_verification()
```

#### Langkah 5: Eksekusi dan Verifikasi Kegagalan
Jalankan script verifikasi:

```bash
python3 verify_health.py
```

*Expected Terminal Output:*
```text
Health Check Score: 20.0/100
RAG Eligible Status: False

[CRITICAL FAILURE] Document health standards violated:
  -> Type mismatch on 'amount': Doc says 'integer', Code expects 'number'.
  -> Param 'currency' exists in code schema but missing in documentation.

CI Pipeline: BLOCKED. Fix discrepancies before merge.
```

#### Langkah 6: Remediasi Dokumentasi
Perbaiki file `docs/transaction_tool.md` agar mutakhir dan sinkron:

```markdown
---
status: active
last_reviewed: 2026-03-30
---

# Execute Transaction Tool

Dokumentasi ini menjelaskan eksekusi transfer dana via agen.

| account_id | string | true |
| amount | number | true |
| currency | string | true |
```

Jalankan kembali:
```bash
python3 verify_health.py
```

*Expected Terminal Output:*
```text
Health Check Score: 90.0/100
RAG Eligible Status: True

CI Pipeline: PASSED. Documentation is healthy.
```
Laboratorium selesai. Sistem proteksi konten dokumentasi Anda kini berhasil mencegah regresi data dan melindungi sistem otonom dari kegagalan eksekusi skema.