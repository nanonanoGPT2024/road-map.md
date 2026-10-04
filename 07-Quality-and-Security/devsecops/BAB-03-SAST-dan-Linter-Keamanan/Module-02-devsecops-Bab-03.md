# BAB 03: SAST dan Linter Keamanan
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis dan Membedah Arsitektur Mesin SAST Modern**: Memahami representasi kode perantara (*Intermediate Representation*) mencakup *Abstract Syntax Tree* (AST), *Control Flow Graph* (CFG), *Data Flow Graph* (DFG), dan mekanisme *Taint Analysis*.
2. **Mengembangkan Aturan Keamanan Kustom (*Custom Detection Rules*)**: Menulis, menguji, dan memvalidasi aturan deteksi keamanan tingkat lanjut berbasis pola semantik dan pelacakan propagasi noda (*taint tracking*) menggunakan *rule engine* industri (Semgrep dan CodeQL).
3. **Merancang Arsitektur Pemindaian Skala Enterprise**: Mengimplementasikan arsitektur *differential scanning* (pemindaian inkremental/PR-level), integrasi format standar SARIF (*Static Analysis Results Interchange Format*), serta sistem agregasi temuan terpusat.
4. **Mengeliminasi *False Positive* dan Mengelola *Baseline Suppressions***: Mengonfigurasi strategi penanganan utang teknis keamanan (*technical security debt*) tanpa menghambat *developer velocity* dan siklus rilis CI/CD.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
- Pengetahuan fundamental arsitektur kompilator dasar (tahapan *Lexing*, *Parsing*, dan *AST Generation*).
- Pemahaman mendalam tentang vektor serangan *injection* (SQLi, Command Injection, XSS, SSRF, Deserialization) sesuai OWASP Top 10 dan taksonomi CWE (*Common Weakness Enumeration*).
- Kemahiran membaca sintaks bahasa pemrograman modern (Go, Python, atau Java) dan format serialisasi data (JSON, YAML).
- Pengalaman operasional tingkat menengah pada CI/CD *orchestration engines* (seperti GitHub Actions, GitLab CI, atau Jenkins Pipelines).

---

### 3. Concept & Internal Architecture

Mesin SAST (*Static Application Security Testing*) generasi modern telah berevolusi dari sekadar pencocokan ekspresi reguler (*regular expression matching*) menjadi mesin penalaran semantik (*semantic reasoning engines*). 

```
[Source Code] 
      │
      ▼ (Lexical Analysis & Parsing)
[Abstract Syntax Tree (AST)]
      │
      ├───────────────────────────────┐
      ▼ (Flow Modeling)               ▼ (Scope & Typing)
[Control Flow Graph (CFG)]    [Symbol Table & Typing Engine]
      │                               │
      └───────────────┬───────────────┘
                      ▼
            [Data Flow Graph (DFG)]
                      │
                      ▼
         [Taint Engine: Path Validation]
         (Source ──> Propagator ──> Sink)
                      │
                      ▼
         [SARIF Diagnostic Output]
```

#### A. Representasi Kode Internal

1. **Abstract Syntax Tree (AST)**:
   Representasi hierarkis struktural dari kode sumber. AST menangkap tata bahasa formal tanpa memperhatikan tanda baca atau spasi, namun belum memahami konteks eksekusi dinamis atau mutasi variabel.
2. **Control Flow Graph (CFG)**:
   Representasi graf terarah (*directed graph*) yang memetakan seluruh jalur eksekusi yang mungkin ditempuh selama *runtime*. Node merepresentasikan *Basic Block* (rangkaian instruksi linier tanpa percabangan), sedangkan edge merepresentasikan lompatan eksekusi (*conditional jumps, loops, function calls*).
3. **Data Flow Graph (DFG)**:
   Graf yang melacak dependensi dan siklus hidup data: bagaimana sebuah nilai dialokasikan, ditransformasikan, dimutasi antar register/variabel, dan dikonsumsi oleh instruksi lain tanpa memedulikan urutan percabangan kontrol secara ketat.

#### B. Mekanisme Taint Analysis (Pelacakan Noda)

Analisis noda adalah teknik verifikasi formal untuk membuktikan apakah data yang tidak tepercaya (*untrusted input*) dapat mengalir ke fungsi operasi sensitif (*critical sinks*) tanpa melalui fungsi validasi/sanitasi yang absah (*sanitizers*).

Secara matematis, alur perambatan noda dimodelkan sebagai triple operasional:
$$\tau = \langle \mathcal{S}_{rc}, \mathcal{P}_{rop}, \mathcal{S}_{ink} \rangle$$

- **Source ($\mathcal{S}_{rc}$)**: Titik masuk data eksternal yang tidak dapat dipercaya (misal: parameter HTTP, *header*, *message broker payload*, atau *file upload stream*).
- **Propagator ($\mathcal{P}_{rop}$)**: Operasi atau fungsi yang meneruskan atau mengubah status noda dari satu variabel ke variabel lain (misal: konkatenasi string, serialisasi, operasi *assignment*, atau pemanggilan fungsi pembantu).
- **Sanitizer / Cleanser ($\mathcal{C}$)**: Transformasi fungsional yang menjamin payload telah ternetralisir atau tervalidasi (misal: *parameterized statement binding*, *casting* numerik ketat, algoritma *HTML escaping*, atau fungsi *allowlist validation*).
- **Sink ($\mathcal{S}_{ink}$)**: Titik eksekusi sensitif yang berpotensi memicu kerentanan kritis jika menerima data yang ternoda (misal: `db.Query()`, `exec.Command()`, `eval()`, atau refleksi objek dinamis).

Pelacakan terbagi menjadi dua paradigma kompleksitas:
- **Intra-procedural Taint Tracking**: Analisis terbatas di dalam cakupan satu fungsi atau metode lokal. Cepat, penggunaan memori rendah, namun memiliki tingkat *false negative* tinggi saat nilai dipindahkan ke fungsi pembantu (*helper functions*).
- **Inter-procedural Taint Tracking**: Analisis menelusuri batas fungsi (*call-graph traversal*), *interface implementations*, hingga *module boundaries*. Memberikan akurasi deteksi superior dengan konsekuensi kompleksitas komputasional tinggi ($\mathcal{O}(V+E)$ hingga $\mathcal{O}(N^3)$) pada basis kode monolitik besar.

---

### 4. Why & What

| Dimensi | Pendekatan Naif (Regex/Linter Konvensional) | Advanced AST/Taint-Based SAST |
| :--- | :--- | :--- |
| **Konteks Semantik** | Buta konteks; gagal membedakan kode aktif vs komentar/string literal. | Sadar konteks; memahami struktur hierarki, tipe data, dan dependensi lingkup (*scope*). |
| **Pendeteksian Jalur Data** | Tidak mampu melacak variabel yang berpindah tangan antar fungsi. | Mampu melacak aliran data dari *boundary controller* hingga *database repository*. |
| **Rasio False Positive** | Sangat tinggi (>40%); memicu *alert fatigue* dan friksi pada tim pengembang. | Terukur dan rendah; dapat diisolasi melalui verifikasi keberadaan fungsi *sanitizer*. |
| **Deteksi Logic Flaws** | Terbatas pada kesalahan sintaksis dan *formatting*. | Mampu mendeteksi kerentanan bisnis kompleks (misal: IDOR, kegagalan otorisasi rute). |
| **Ekstensibilitas** | Pola *regex* rapuh (*brittle*), mudah diakali dengan spasi atau *line breaks*. | Pola deklaratif terstruktur (*structural pattern matching*) yang tahan terhadap refaktor kode. |

Penerapan SAST tingkat lanjut berfungsi sebagai mekanisme validasi deterministik pada tingkat kode sebelum artefak perangkat lunak dikompilasi, dikemas ke dalam *container image*, atau dialokasikan ke lingkungan pengujian (*runtime*).

---

### 5. How (Workflow Detail)

Arsitektur orkestrasi SAST skala produksi beroperasi melalui alur kerja berikut:

```
[Developer Git Push]
         │
         ▼
[1. Pre-Flight Trigger] 
 ├─ Analisis Git Commit Range (Diff Parsing)
 └─ Identifikasi Scope: Changed Files Only
         │
         ▼
[2. AST & Taint Processing Engine]
 ├─ Pengambilan Custom & Standard Security Rules
 ├─ Ekstraksi Graph (AST, CFG, Call Graph)
 └─ Inter-procedural Data Flow Analysis
         │
         ▼
[3. SARIF Result Normalization]
 ├─ Normalisasi Skema Output ke OASIS SARIF v2.1.0
 ├─ Sidik Jari Temuan (Fingerprinting via Source Context Hashes)
 └─ Korelasi Baseline Suppression (Menyaring Utang Teknis Lama)
         │
         ▼
[4. Quality Gate Evaluation Engine]
 ├─ Cek Ambang Batas Kegagalan:
 │   ├─ Critical/High Severity CWE baru -> BLOCK PR
 │   └─ Medium/Low Severity -> Inline Annotation / Warning
 └─ Sinkronisasi Metrik ke Pusat Visibilitas DevSecOps
```

1. **Pre-flight & Scope Definition**: *Runner* mengidentifikasi kumpulan berkas yang termodifikasi melalui `git diff-tree`. Menjalankan pemindaian penuh (*full scan*) pada setiap *pull request* monorepo terbukti tidak efisien; oleh karena itu, target eksekusi dipetakan secara diferensial.
2. **Contextual Engine Execution**: Mesin SAST membaca berkas terdampak beserta modul dependensinya untuk menyusun *call graph*. Mesin mengevaluasi aturan deteksi (*ruleset*) berbasis pola semantik dan keterlacakan noda.
3. **SARIF Normalization & Fingerprinting**: Hasil analisis dikonversi ke format standar SARIF. Setiap temuan diberikan tanda pengenal unik (*fingerprint*) yang dihitung berdasarkan *contextual hashing* (nama fungsi, struktur *parent node*, tipe variabel) dan bukan berdasarkan nomor baris murni, sehingga temuan tetap valid meskipun terjadi penambahan baris kode di atasnya.
4. **Baseline Filtering & Gating**: Hasil dibandingkan dengan basis data *baseline*. Jika temuan berstatus *pre-existing debt*, sistem menandai sebagai catatan tanpa membatalkan *pipeline*. Namun, apabila ditemukan kerentanan baru berkategori *High/Critical*, *Quality Gate* secara otomatis memutus rantai *merge* (*hard break*).

---

### 6. Analogy & Diagram ASCII

#### Analogi Sistem Perpipaan Industri (Industrial Fluid Pipeline)

Bayangkan basis kode Anda adalah jaringan perpipaan air bersih pada instalasi industri:
- **Source**: Katup hisap air baku dari sungai luar yang berisiko tercemar zat kimia berbahaya (*untrusted input*).
- **Propagator**: Pipa-pipa transmisi, tangki penampungan sementara, dan percabangan katup yang mengalirkan fluida ke seluruh fasilitas pabrik.
- **Sanitizer**: Unit desalinasi, penyaringan karbon aktif, dan sterilisasi ultraviolet yang membersihkan kontaminan hingga memenuhi spesifikasi aman.
- **Sink**: Dispenser air minum pekerja pabrik.
- **Kerentanan (Vulnerability)**: Terjadi ketika fluida dari katup hisap luar berhasil mengalir langsung ke dispenser air minum tanpa melewati unit sterilisasi. Mesin SAST bertindak sebagai inspektur visual terotomatisasi yang memetakan seluruh denah pipa guna memverifikasi ketiadaan jalur bypass pada sistem filtrasi.

#### Arsitektur Orkestrasi Produksi (Differential SAST Pipeline)

```
+-----------------------------------------------------------------------------------+
| CI/CD Pipeline Orchestrator (Worker Node)                                         |
|                                                                                   |
|  +------------------+      +-------------------+      +------------------------+  |
|  |  Git Workspace   | ---> | In-Memory Engine  | ---> | SARIF Transformer      |  |
|  |  (PR Diff Target)|      | (Custom Rulesets) |      | & Fingerprinter        |  |
|  +------------------+      +-------------------+      +------------------------+  |
|                                                                    │              |
|                                                                    ▼              |
|  +------------------+      +-------------------+      +------------------------+  |
|  |  Security Gate   | <--- | Suppression Engine| <--- | Baseline Store         |  |
|  |  (Exit 0/1 Eval) |      | (Filter KnownDebt)|      | (S3/GCS SARIF Cache)   |  |
|  +------------------+      +-------------------+      +------------------------+  |
|           │                                                                       |
+-----------┼───────────────────────────────────────────────────────────────────────+
            │
            ▼
    +---------------+        +----------------------+
    | PR Blocked/OK |        | Central Dashboard    |
    | (VCS Checks)  |        | (e.g., DefectDojo)   |
    +---------------+        +----------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Konsep Dasar AST (Visualisasi Struktur Data)

Potongan kode instruksi Go:
```go
db.Exec("SELECT * FROM users WHERE id = " + input)
```

Dikonversi menjadi representasi pohon sintaksis terabstraksi (AST) oleh *parser*:
```text
CallExpr
├── Fun: SelectorExpr
│   ├── X: Ident (Name: "db")
│   └── Sel: Ident (Name: "Exec")
└── Args:
    └── BinaryExpr
        ├── X: BasicLit (Kind: STRING, Value: "SELECT * FROM users WHERE id = ")
        ├── Op: +
        └── Y: Ident (Name: "input")
```
Mesin penganalisis mengevaluasi bahwa node `CallExpr` memanggil fungsi berisiko (`Exec`) dengan argumen bertipe `BinaryExpr` (operasi konkatenasi string), yang secara struktural menandakan keberadaan potensi SQL Injection.

---

#### B. Practical Implementation: Advanced Taint Tracking Rule

Berikut implementasi aturan deklaratif Semgrep tingkat lanjut (*Advanced Taint Analysis*) untuk mendeteksi kerentanan Server-Side Request Forgery (SSRF) pada arsitektur Go HTTP microservice.

Simpan aturan ini sebagai: `rules/security/ssrf-taint.yaml`

```yaml
rules:
  - id: go-net-http-tainted-ssrf
    message: >-
      Terdeteksi potensi SSRF kritis: Aliran data yang tidak tepercaya dialirkan 
      langsung ke pemanggilan fungsi jaringan HTTP internal tanpa proses validasi 
      allowlist skema atau host.
    severity: ERROR
    languages: [go]
    mode: taint
    metadata:
      cwe: "CWE-918: Server-Side Request Forgery (SSRF)"
      owasp: "A10:2021 - Server-Side Request Forgery (SSRF)"
      confidence: HIGH
      impact: CRITICAL

    pattern-sources:
      # Titik masuk 1: Parameter URL dari context HTTP standard
      - pattern: ($REQ *http.Request).URL.Query().Get(...)
      # Titik masuk 2: Ekstraksi URL Parameters dari Gorilla Mux
      - pattern: mux.Vars($REQ)[...]
      # Titik masuk 3: Body Payload Parser (Decoder stream)
      - pattern: json.NewDecoder($BODY).Decode(...)

    pattern-propagators:
      # Pelacakan propagasi noda melalui konkatenasi dan interpolasi string
      - pattern: fmt.Sprintf(..., $TAINTED, ...)
        from: $TAINTED
        to: $OUTPUT
      - pattern: strings.Join([]string{..., $TAINTED, ...}, ...)
        from: $TAINTED
        to: $OUTPUT

    pattern-sanitizers:
      # Sanitizer 1: Pengecekan eksplisit melalui fungsi validasi domain/URL terdaftar
      - pattern: internal.ValidateTargetURL($TAINTED)
      # Sanitizer 2: Validasi skema dan resolusi IP private secara komprehensif
      - pattern: netutil.ValidateSafeOutboundHost($TAINTED)

    pattern-sinks:
      # Titik eksekusi sensitif
      - pattern: http.Get($URL)
      - pattern: http.Post($URL, ...)
      - pattern: http.NewRequest(..., $URL, ...)
      - pattern: ($CLIENT *http.Client).Do($REQ)
```

#### C. Kode Aplikasi Pengujian (Test Harness)

Simpan sebagai `services/proxy_handler.go`:

```go
package main

import (
	"fmt"
	"net/http"
	"github.com/gorilla/mux"
)

// VulnerableHandler: Memetakan sumber noda langsung ke sink tanpa sanitasi
func VulnerableHandler(w http.ResponseWriter, r *http.Request) {
	// Source: Input pengguna via Query parameter
	target := r.URL.Query().Get("dest")
	
	// Propagator: Format string URL
	targetURL := fmt.Sprintf("https://%s/api/v1/telemetry", target)

	// SINK: http.Get rentan SSRF! Mesin SAST wajib membunyikan alarm!
	resp, err := http.Get(targetURL)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	defer resp.Body.Close()
	w.WriteHeader(resp.StatusCode)
}

// SecureHandler: Jalur terlindungi dengan pemanggilan Sanitizer eksplisit
func SecureHandler(w http.ResponseWriter, r *http.Request) {
	target := mux.Vars(r)["host"]

	// SANITIZER: Menetralkan sifat noda
	safeURL, err := internal.ValidateTargetURL(target)
	if err != nil {
		http.Error(w, "Target Host Ditolak Secara Keamanan", http.StatusBadRequest)
		return
	}

	// SINK: Diperbolehkan karena safeURL telah ditandai steril oleh Sanitizer
	req, _ := http.NewRequest("GET", safeURL, nil)
	client := &http.Client{}
	client.Do(req)
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Insiden & Tantangan Skala Besar
Sebuah platform perbankan digital skala enterprise mengelola repositori mikroservis yang terdiri atas 4.500 repositori terpisah dan satu monorepo inti berbasis Go dan Java (dengan total estimasi 22 juta baris kode aktif). 

**Masalah**:
1. Pemindaian penuh (*full scan*) menggunakan mesin SAST komersial berbasis *on-premise runner* membutuhkan waktu rata-rata 3,5 jam per eksekusi pipeline.
2. Tim DevOps mematikan pemindaian pada *Merge Request* (MR) karena memperlambat siklus *lead time for changes* tim pengembang.
3. Terjadi kebocoran insiden keamanan di mana *vulnerable sink* pada modul pembayaran eksternal mengakibatkan kerentanan SSRF kritis yang mengekspos instans metadata cloud AWS internal (`http://169.254.169.254`).

#### Solusi Arsitektur DevSecOps
Arsitek keamanan merancang ulang pipeline SAST menjadi model *Multi-Tiered Differential Analysis*:

1. **Tier 1 (PR Level / Pre-Merge)**: 
   - Mesin *lightweight* semantik (*Semgrep Engine*) dijalankan secara paralel di CI runner containerized murni.
   - Menggunakan mekanisme analisis diferensial: hanya memindai berkas yang berubah berdasarkan `git diff origin/main...HEAD`.
   - Menggunakan *custom taint ruleset* yang berfokus ketat pada subset CWE berbobot *High* dan *Critical* (SQLi, SSRF, Deserialization, Hardcoded Secrets).
   - Waktu eksekusi dipangkas menjadi **< 45 detik** per PR.
2. **Tier 2 (Nightly Build / Post-Merge)**:
   - Mesin *deep inter-procedural graph analysis* (CodeQL & SonarQube) dieksekusi secara asinkron setiap malam pada cabang utama (`main`).
   - Melakukan pelacakan ketergantungan lintas berkas dan *whole-program control analysis*.
   - Hasil diekspor ke format SARIF, lalu dikirim ke platform *DefectDojo* untuk pemantauan tren utang keamanan.

#### Hasil Kuantitatif
- Penurunan waktu validasi CI dari **210 menit** ke **38 detik** per *pull request*.
- Tercapainya kepatuhan *merge-gate* 100% tanpa adanya bypass/skip oleh pengembang.
- Deteksi dan pencegahan otomatis terhadap 17 potensi kebocoran SSRF dan SQL Injection baru dalam rentang waktu 6 bulan pertama implementasi.

---

### 9. Trade-offs

Mengimplementasikan advanced SAST pada skala produksi menuntut perimbangan teknis yang ketat:

| Vektor Arsitektur | Pilihan A: Intra-procedural (Shallow AST Pattern) | Pilihan B: Inter-procedural (Deep Graph Taint) |
| :--- | :--- | :--- |
| **Kecepatan Analisis (Latency)** | **Ultra-Cepat**: Milidetik hingga beberapa detik per berkas. Ideal untuk integrasi PR gating dan *developer pre-commit hook*. | **Lambat**: Membutuhkan hitungan menit hingga jam. Memerlukan parsing *Call Graph* global dan pembuatan basis data perantara. |
| **Akurasi (True Positive Rate)** | **Rendah - Menengah**: Kehilangan konteks saat data melewati fungsi *wrapper*, *abstraction layer*, atau *handler interface*. | **Tinggi**: Mampu memvalidasi propagasi nilai yang melintasi berbagai modul internal, *package boundaries*, dan *class hierarchies*. |
| **Konsumsi Memori & CPU** | **Rendah**: Kebutuhan memori linier $\mathcal{O}(N)$ terhadap ukuran baris kode berkas yang dianalisis. | **Sangat Tinggi**: Kebutuhan memori polinomial hingga eksponensial $\mathcal{O}(V \times E)$. Berisiko memicu *Out Of Memory* (OOM) pada container terbatas. |
| **Operational & Rule Maintenance Cost** | **Rendah**: Aturan deklaratif mudah ditulis, diverifikasi, dan dikelola oleh insinyur keamanan aplikasi. | **Tinggi**: Membutuhkan pemeliharaan skema basis data relasional/logika kode yang kompleks (misal: penulisan predikat Datalog/CodeQL). |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Umum Produksi

1. **Menjalankan Pemindaian Penuh (*Full Scan*) pada Seluruh Cabang Fitur**:
   - *Dampak*: Antrean CI/CD macet total, biaya *compute runner* melonjak tajam, dan pengembang mencari cara melakukan bypass sistem validasi keamanan.
   - *Solusi*: Batasi analisis pra-penggabungan (*pre-merge*) pada ruang lingkup diferensial via target git SHA.
2. **Memutus Pipeline Berdasarkan *Raw Finding Counts* (Ketiadaan *Baseline Suppression*)**:
   - *Dampak*: Menolak PR perbaikan bug kritis yang dibuat pengembang hanya karena repositori warisan (*legacy*) tersebut sudah memiliki 400 temuan lama (*backlog debt*).
   - *Solusi*: Terapkan pemfilteran *Baseline SARIF*. Hanya gagalkan PR jika terdapat kerentanan berstatus **BARU** yang diperkenalkan pada *commit range* tersebut.
3. **Mengabaikan Sanitizer dalam Desain Aturan Taint**:
   - *Dampak*: Munculnya ratusan *false positive* untuk fungsi-fungsi yang telah divalidasi dengan aman, menurunkan tingkat kepercayaan pengembang (*alert fatigue*).
   - *Solusi*: Identifikasi modul enkapsulasi dan utilitas sanitasi internal organisasi dan daftarkan ke dalam blok `pattern-sanitizers` pada konfigurasi aturan.

#### Troubleshooting Panduan Cepat

*   **Gejala: Mesin SAST mengalami Crash / OOM (Killed Signal 9) di Lingkungan CI Runner.**
    *   *Akar Masalah*: Analisis inter-procedural terjebak pada dependensi sirkular atau pemindaian direktori *vendor/build output* (`node_modules`, `vendor/`, `dist/`).
    *   *Mitigasi*: Konfigurasikan berkas `.semgrepignore` atau parameter mesin untuk mengabaikan direktori pihak ketiga (*third-party dependencies*) dan *generated auto-code*.
*   **Gejala: Temuan lama berulang kali muncul sebagai temuan baru setiap kali baris kode digeser (*Line Number Shifting*).**
    *   *Akar Masalah*: Mesin SAST mengidentifikasi kerentanan secara naif hanya berdasarkan penomoran baris file (`start_line`).
    *   *Mitigasi*: Aktifkan fitur *Deterministic Structural Fingerprinting* berbasis hash AST atau gunakan parser SARIF yang memanfaatkan atribut `partialFingerprints.primaryLocationLineHash`.

---

### 11. Best Practices (Production Checklist)

Gunakan daftar periksa kesiapan arsitektur produksi berikut sebelum menerapkan gerbang SAST pada level organisasi:

- [ ] **Targeting Diferensial**: Analisis gating hanya memproses `git diff` dari target *base branch* untuk memastikan latensi pipeline CI $\le 60\text{ detik}$.
- [ ] **Standarisasi SARIF**: Seluruh perkakas SAST multi-bahasa dinormalisasi untuk menghasilkan output OASIS SARIF v2.1.0 terpadu.
- [ ] **Taint Ruleset Hygiene**: Seluruh *custom rule* berbasis noda mendefinisikan triplet Source, Sanitizer, dan Sink secara eksplisit.
- [ ] **Baseline Exclusion Matrix**: Tersedia mekanisme sentralisasi untuk memisahkan *technical security debt* warisan dari baris kode yang baru ditulis.
- [ ] **Automated Inline PR Comments**: Temuan dikomunikasikan langsung pada baris kode yang relevan di platform VCS (GitHub/GitLab PR conversation), bukan tersembunyi di dalam log *runner* yang panjang.
- [ ] **Fail-Secure Gating Policy**: Pipeline CI dikonfigurasi dengan toleransi:
  - Severity `CRITICAL` & `HIGH`: **Hard Break (Exit Code 1)**
  - Severity `MEDIUM` & `LOW`: **Soft Warning (Exit Code 0) + Log tracking**
- [ ] **Ignore-Rule Governance**: Pengembang tidak diizinkan menambahkan komentar pengabaian (misal: `// nosec` atau `# nosemgrep`) tanpa mencantumkan kode tiket persetujuan resmi dari Tim Keamanan (misal: `// nosemgrep: reason=SEC-10943`).

---

### 12. Hands-on Practice

Dalam sesi praktikum ini, Anda akan membangun sistem *Differential SAST Gatekeeper* berbasis CLI yang secara otomatis menganalisis komparasi *diff*, menjalankan pemeriksaan berbasis *taint rule*, dan mengevaluasi SARIF payload untuk menentukan kelolosan PR.

Struktur folder praktikum:
```text
hands-on/m02/
├── rules/
│   └── injection-taint.yaml
├── src/
│   ├── app.py
│   └── database.py
├── scripts/
│   └── diff-gatekeeper.py
└── run-test.sh
```

#### Langkah 1: Siapkan Struktur Direktori dan Aturan Taint SAST
Buat berkas aturan Semgrep kustom untuk mendeteksi *SQL Injection* pada kode Python:
Simpan di: `hands-on/m02/rules/injection-taint.yaml`

```yaml
rules:
  - id: python-sqlite3-raw-injection
    message: "Data input pengguna yang tidak disanitasi dialirkan langsung ke kueri SQLite."
    severity: ERROR
    languages: [python]
    mode: taint
    metadata:
      cwe: "CWE-89: Improper Neutralization of Special Elements used in an SQL Command"
    pattern-sources:
      - pattern: flask.request.args.get(...)
      - pattern: flask.request.form[...]
      - pattern: flask.request.json.get(...)
    pattern-propagators:
      - pattern: f"...{$VAR}..."
        from: $VAR
        to: $OUTPUT
      - pattern: "{}...".format($VAR)
        from: $VAR
        to: $OUTPUT
    pattern-sanitizers:
      - pattern: sanitize_input(...)
    pattern-sinks:
      - pattern: $CURSOR.execute($QUERY)
      - pattern: $DB.execute($QUERY)
```

#### Langkah 2: Buat Kode Target Aplikasi Python yang Rentan dan yang Aman
Simpan di: `hands-on/m02/src/app.py`

```python
import sqlite3
import flask

app = flask.Flask(__name__)

def get_db():
    return sqlite3.connect("production.db")

@app.route("/users/search", methods=["GET"])
def search_user_vulnerable():
    # SOURCE: Input pengguna langsung
    user_id = flask.request.args.get("id")
    
    # PROPAGATOR: Interpolasi string mentah
    query = f"SELECT id, username FROM users WHERE id = '{user_id}'"
    
    conn = get_db()
    cursor = conn.cursor()
    
    # SINK: Eksekusi string yang terkontaminasi (Wajib terdeteksi!)
    cursor.execute(query)
    records = cursor.fetchall()
    return flask.jsonify(records)

@app.route("/users/secure", methods=["GET"])
def search_user_secure():
    user_id = flask.request.args.get("id")
    
    conn = get_db()
    cursor = conn.cursor()
    
    # AMAN: Menggunakan bind parameter, bukan taint string propagation
    cursor.execute("SELECT id, username FROM users WHERE id = ?", (user_id,))
    records = cursor.fetchall()
    return flask.jsonify(records)
```

#### Langkah 3: Bangun Differential SARIF Gating Script
Simpan di: `hands-on/m02/scripts/diff-gatekeeper.py`

Script ini bertindak sebagai *decision engine* di pipeline CI yang membedah berkas hasil pemindaian berformat SARIF OASIS Standard:

```python
#!/usr/bin/env python3
import json
import sys
import os

def evaluate_sarif_gate(sarif_path, fail_on_severities=["error"]):
    if not os.path.exists(sarif_path):
        print(f"[ERROR] Berkas output SARIF tidak ditemukan: {sarif_path}")
        sys.exit(2)

    with open(sarif_path, "r", encoding="utf-8") as f:
        sarif_data = json.load(f)

    violations = []
    runs = sarif_data.get("runs", [])
    
    for run in runs:
        results = run.get("results", [])
        for result in results:
            rule_id = result.get("ruleId", "UNKNOWN_RULE")
            level = result.get("level", "warning").lower()
            message = result.get("message", {}).get("text", "")
            
            # Ekstraksi lokasi baris dan berkas
            locations = result.get("locations", [])
            loc_str = "Unknown"
            if locations:
                phys = locations[0].get("physicalLocation", {})
                uri = phys.get("artifactLocation", {}).get("uri", "")
                line = phys.get("region", {}).get("startLine", 0)
                loc_str = f"{uri}:{line}"

            if level in fail_on_severities:
                violations.append({
                    "rule": rule_id,
                    "level": level,
                    "location": loc_str,
                    "message": message
                })

    print("=================================================================")
    print("           DEVSECOPS ENTERPRISE QUALITY GATE EVALUATION           ")
    print("=================================================================")

    if violations:
        print(f"\n[CRITICAL FAILURE] Ditemukan {len(violations)} pelanggaran kebijakan keamanan mutlak!\n")
        for idx, v in enumerate(violations, 1):
            print(f"  {idx}. [Level: {v['level'].upper()}] Rule: {v['rule']}")
            print(f"     Lokasi : {v['location']}")
            print(f"     Catatan: {v['message']}")
            print("  ---------------------------------------------------------------")
        print("\nKesimpulan: Pull Request DIBLOKIR. Lakukan remediasi sebelum penggabungan kode.")
        sys.exit(1)
    else:
        print("\n[SUCCESS] Pemindaian lolos! Tidak ditemukan pelanggaran berderajat Error/Critical.")
        print("Kesimpulan: Status Quality Gate: PASS (Diizinkan melanjutkan merge).")
        sys.exit(0)

if __name__ == "__main__":
    target_sarif = sys.argv[1] if len(sys.argv) > 1 else "semgrep-output.sarif"
    evaluate_sarif_gate(target_sarif)
```

#### Langkah 4: Eksekusi Pipeline Otomasi Praktikum
Simpan di: `hands-on/m02/run-test.sh`

```bash
#!/usr/bin/env bash
set -e

echo "[*] Menjalankan Analisis Semantik Berbasis Taint Engine..."

# Eksekusi Semgrep secara lokal dengan target SARIF output
semgrep scan \
  --config=rules/injection-taint.yaml \
  --sarif \
  --output=semgrep-output.sarif \
  src/

echo "[*] Pemindaian selesai. Mengevaluasi SARIF Result via Gatekeeper..."

# Uji Gating
chmod +x scripts/diff-gatekeeper.py
python3 scripts/diff-gatekeeper.py semgrep-output.sarif || GATE_EXIT_CODE=$?

if [ "${GATE_EXIT_CODE:-0}" -ne 0 ]; then
    echo "[!] Quality Gate bekerja sebagaimana mestinya (Pemindaian berhasil menggagalkan PR yang rentan)."
    exit 0
else
    echo "[FAIL] Quality Gate gagal mendeteksi kerentanan!"
    exit 1
fi
```

Jalankan perintah pengujian:
```bash
chmod +x run-test.sh
./run-test.sh
```

---

### 13. Exercise

#### Level: Easy
1. Ubah aturan `rules/injection-taint.yaml` untuk menambahkan *pattern-propagator* baru yang mengenali penggabungan string menggunakan metode operator tambah (`query = "SELECT * FROM users WHERE id = " + user_id`). Uji dan buktikan bahwa penambahan ini mendeteksi variasi penulisan sintaksis alternatif tersebut.

#### Level: Medium
1. Tulis sebuah *custom rule* Semgrep baru bernama `no-hardcoded-jwt-secrets` yang menggunakan mode pencocokan AST semantik untuk mendeteksi penulisan string literal langsung pada pemanggilan fungsi penandatanganan token JWT:
   - Bahasa: Go
   - Sink: `jwt.NewWithClaims(..., []byte("HARDCODED_LITERAL_SECRET"))`
   - Pastikan aturan mengabaikan pemanggilan fungsi yang mengambil secret dari pembacaan *environment variable* aman (`os.Getenv(...)`).

#### Level: Hard
1. Buat arsitektur pemrosesan Python yang membaca dua berkas SARIF: `baseline-master.sarif` (temuan lama) dan `current-pr.sarif` (temuan pada PR saat ini). 
2. Program harus mampu melakukan *fingerprint matching* berbasis atribut `partialFingerprints` untuk:
   - Mengisolasi dan mengabaikan seluruh temuan lama yang sudah ada di master (*suppressed debt*).
   - Memunculkan alarm pemblokiran hanya jika terdapat temuan dengan sidik jari baru (*novel vulnerability*).
   - Menghasilkan berkas keluaran `delta.sarif` yang bersih untuk diunggah ke VCS PR Conversation.

---

### 14. Challenge

**Skenario Tantangan Enterprise**:
Sebuah tim arsitektur keamanan dihadapkan pada monorepo perbankan legacy dengan 35.000 pelanggaran SAST yang tercatat pada *baseline* awal. Tim pengembang menuntut *pipeline gate* yang:
1. **Memiliki Zero False Positive** untuk pemblokiran *hard break* pada jalur *critical payment*.
2. **Anti-Tampering**: Menghentikan upaya pengembang menyisipkan instruksi komentar pembungkaman (*silencing pragmas* seperti `nosemgrep` atau `noqa`) secara diam-diam tanpa otorisasi.
3. **Mendeteksi Kerentanan Deserialisasi Objek yang Kompleks**: Harus mampu melacak alur data inter-procedural dari API Gateway masuk ke DTO class, melintasi lapisan Service Bus Message, hingga ke metode `deserialize()` yang tidak aman di tingkat *Background Worker*.

**Instruksi**:
- Rancang arsitektur integrasi sistem deteksi *anti-tampering* menggunakan Git Pre-Receive Hooks atau Custom CI Enforcement Action.
- Susun model aturan semantik lengkap (spesifikasi deklaratif) yang mampu memetakan skenario transfer data asinkron tersebut secara presisi.
- Formulasikan metrik matematis operasional untuk menghitung rasio *Signal-to-Noise Ratio (SNR)* dan penurunan *False Positive Rate (FPR)* sepanjang siklus triase bulanan.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Tingkat Dasar (Basic)

1. **Apa perbedaan struktural utama antara AST (Abstract Syntax Tree) dan CFG (Control Flow Graph)?**
   - *Jawaban/Penjelasan*: AST memetakan hierarki sintaksis dan tata bahasa formal kode sumber secara deklaratif tanpa memedulikan urutan eksekusi. Sementara CFG memetakan seluruh jalur alur eksekusi logika percabangan kondisi (*runtime conditional jumps*, iterasi loop, dan pemanggilan subrutin) yang mungkin dilewati selama aplikasi berjalan.

2. **Sebutkan tiga komponen utama yang membangun mekanisme analisis pelacakan noda (Taint Analysis)!**
   - *Jawaban/Penjelasan*: Taint analysis terdiri atas:
     - **Source**: Titik masuk input data tidak terpercaya dari entitas luar.
     - **Propagator**: Instruksi atau fungsi yang meneruskan atau mengubah nilai noda ke variabel lain.
     - **Sink**: Titik pemanggilan fungsi komputasi atau infrastruktur kritis yang berbahaya jika dieksekusi menggunakan payload tercemar tanpa sanitasi.

3. **Mengapa pemindaian menggunakan pencocokan Regular Expression (Regex) memiliki performa buruk dalam mendeteksi SQL Injection jika dibandingkan dengan pendekatan AST?**
   - *Jawaban/Penjelasan*: Regex buta konteks gramatikal; regex tidak dapat membedakan apakah kata kunci seperti `SELECT` berada di dalam baris komentar, string dokumentasi, atau merupakan bagian dari eksekusi instruksi database aktif. Regex juga rentan dilewati (*bypass*) melalui variasi whitespace, konkatenasi variabel bertingkat, dan aliasing variabel.

4. **Apa tujuan dari spesifikasi standar OASIS SARIF (Static Analysis Results Interchange Format)?**
   - *Jawaban/Penjelasan*: Untuk menyediakan skema format pertukaran JSON yang seragam dan terstandardisasi industri, memungkinkan berbagai vendor mesin pemindai statis (SAST, Linters, Secrets Scanner) mengekspor data diagnostik terpadu yang dapat dikonsumsi oleh dashboard dan CI/CD gatekeeper mana pun.

5. **Apa yang dimaksud dengan "Differential SAST Scanning"?**
   - *Jawaban/Penjelasan*: Teknik pengoptimalan pemindaian statis di mana analisis kode hanya difokuskan pada berkas atau baris kode yang mengalami modifikasi (*git diff*) dalam cakupan commit atau pull request tertentu, bukan menganalisis keseluruhan repositori secara menyeluruh.

---

#### B. Pertanyaan Tingkat Menengah (Intermediate)

6. **Bagaimana arsitektur penganalisis semantik membedakan antara variabel yang "Ternoda (Tainted)" dan variabel yang sudah "Dibersihkan (Sanitized)"?**
   - *Jawaban/Penjelasan*: Mesin membangun *graph reachability*. Data dari Source diberi label/tag status aktif (*tainted*). Sepanjang alur perambatan di DFG, mesin memeriksa apakah terdapat node yang cocok dengan definisi fungsional *Sanitizer/Cleanser*. Jika simpul sanitizer tereksekusi pada semua jalur kontrol menuju Sink, tag noda dihapus (*cleansed*), sehingga tidak memicu alarm pelanggaran.

7. **Mengapa penomoran baris file mentah (`start_line`) tidak boleh digunakan sebagai primary identifier dalam memetakan utang keamanan baseline?**
   - *Jawaban/Penjelasan*: Karena penambahan atau pengurangan baris kode sederhana di bagian atas berkas akan menggeser nomor baris kode di bawahnya (*line shifting*). Hal ini menyebabkan mesin SAST naif mendeteksi kerentanan lama yang tergeser tersebut sebagai kerentanan baru (*novel finding*), sehingga merusak reliabilitas sistem *baseline suppression*.

8. **Jelaskan konsep kompleksitas komputasional antara analisis Intra-procedural dan Inter-procedural!**
   - *Jawaban/Penjelasan*: Analisis Intra-procedural bekerja secara terisolasi pada satu blok fungsi dengan kompleksitas linier $\mathcal{O}(N)$ terhadap jumlah node AST lokal. Analisis Inter-procedural menganalisis *call graph* global antar fungsi dan dependensi berkas; kompleksitasnya meningkat menjadi polinomial $\mathcal{O}(V \times E)$ hingga $\mathcal{O}(N^3)$, yang membutuhkan kalkulasi state space yang jauh lebih intensif.

9. **Apa kegunaan mekanisme "Fingerprinting via Context Hashing" pada format SARIF?**
   - *Jawaban/Penjelasan*: *Context hashing* menghitung sidik jari unik temuan berdasarkan hash identitas semantik di sekitarnya (seperti nama fungsi pembungkus, AST parent type, dan token di sekitarnya), bukan nomor baris fisik. Ini menjaga stabilitas identitas temuan meskipun kode mengalami refaktorisasi atau penataan letak baris.

10. **Bagaimana cara mencegah "Alert Fatigue" pada tim pengembang saat pertama kali mengintegrasikan SAST pada repositori warisan (*legacy*)?**
    - *Jawaban/Penjelasan*: Dengan membuat berkas penekanan basis data awal (*baseline suppression*). Semua temuan yang ada sebelum tanggal aktivasi dicatat sebagai utang teknis historis yang tidak memblokir pipeline. Pipeline hanya dikonfigurasi untuk memutus proses integrasi (*hard failure*) jika terdapat temuan berderajat kritis yang baru diperkenalkan (*net-new vulnerabilities*).

---

#### C. Skenario Kasus Produksi (Production Scenarios)

11. **Skenario 1**: Sebuah tim platform DevSecOps mendapati bahwa pipeline pemindaian PR pada monorepo utama sering mengalami kegagalan *Timeout* (melebihi batas 30 menit). Analisis log menunjukkan mesin SAST menghabiskan 90% waktu pada pelacakan dependensi kompilasi pustaka pihak ketiga.
    *   *Pertanyaan*: Tindakan arsitektural spesifik apa yang harus dieksekusi untuk mereduksi waktu eksekusi di bawah 2 menit tanpa menurunkan akurasi temuan pada kode internal perusahaan?
    *   *Solusi*: 
        1. Menerapkan pemisahan cakupan direktori secara ketat via berkas konfigurasi pengecualian (`.semgrepignore` / target exclusion) untuk memotong traversal direktori paket pihak ketiga (`vendor/`, `node_modules/`, `target/`).
        2. Beralih secara penuh ke *Differential PR Analysis* (`--diff-depth` berbasis commit merge base).
        3. Menunda pemindaian *full call-graph* inter-procedural yang komprehensif ke *asynchronous nightly builds*, sementara *PR gate* dibatasi pada pemindaian pola semantik intra-procedural berbasis aturan kritis lokal.

12. **Skenario 2**: Ditemukan kerentanan kritis SQL Injection yang lolos ke lingkungan *Production*. Investigasi menemukan bahwa pengembang menulis fungsi kustom untuk membersihkan tanda kutip string yang dinamai `cleanseString()`, sehingga mesin SAST menganggap input telah aman karena fungsi pembersih tersebut keliru didaftarkan oleh insinyur keamanan sebagai *Sanitizer* universal pada *custom ruleset*. Padahal fungsi tersebut tidak memitigasi serangan berbasis *numeric injection* (`OR 1=1`).
    *   *Pertanyaan*: Bagaimana Anda mendesain ulang arsitektur aturan deteksi untuk mencegah kegagalan logika sanitasi parsial seperti ini di masa mendatang?
    *   *Solusi*:
        1. Hapus fungsi sanitasi kustom berbasis manipulasi string dari daftar `pattern-sanitizers`. 
        2. Terapkan prinsip penegakan *Type-Safe Parameterization*: Hanya tetapkan sanitasi yang valid jika alur data dikonversi melalui fungsi pengikatan parameter resmi mesin database (*prepared statement parameters* atau *type-checked strong casting* seperti pemanggilan eksplisit fungsi parser integer).
        3. Tambahkan aturan meta-linter keamanan untuk melarang penggunaan fungsi manipulasi sanitasi string buatan sendiri (*in-house custom sanitizers*) melalui deteksi arsitektur anti-pattern.

13. **Skenario 3**: Sebuah organisasi perbankan mengimplementasikan *Quality Gate* ketat yang secara otomatis menggagalkan *Pull Request* jika ditemukan kerentanan berstatus severity `HIGH` atau `CRITICAL`. Pengembang senior yang dituntut merilis fitur mendesak menambahkan anotasi komentar penekan pemindaian `// nosec: G201` pada puluhan titik kode untuk membungkam mesin pemeriksa, sehingga pipeline CI lolos secara artifisial.
    *   *Pertanyaan*: Rancang mekanisme sistemik dan terotomatisasi di level arsitektur DevSecOps untuk mencegah, mendeteksi, dan menganulir *bypass* tidak terotorisasi ini!
    *   *Solusi*:
        1. **In-Pipeline Suppression Audit Gate**: Tambahkan modul pemeriksa linier yang mengevaluasi diff untuk mencari penambahan token komentar pembungkaman (`nosec`, `nosemgrep`, `sonar-ignore`).
        2. **Signature & Metadata Validation**: Konfigurasikan sistem bahwa setiap penekanan wajib memiliki metadata tiket persetujuan yang sah (misal: `// nosec: ticket=SEC-9981 expire=2024-12-31 approver=appsec-team`). Jika nomor tiket tidak valid atau tidak ditemukan dalam status "Approved" pada REST API pelacak tiket internal, pipeline otomatis membatalkan build.
        3. **VCS Codeowners Rule**: Kunci file konfigurasi keamanan dan tetapkan bahwa penambahan komentar *inline suppression* mewajibkan *mandatory review approval* dari grup security engineers menggunakan mekanisme `CODEOWNERS` pada platform kontrol versi.

---

### 16. Summary

Implementasi lanjutan SAST dalam arsitektur DevSecOps tingkat produksi menuntut pergeseran dari sekadar pencocokan sintaks naif (*regex matching*) menuju pemodelan komputasional semantik yang mendalam melalui **Abstract Syntax Tree (AST)**, **Control Flow Graph (CFG)**, dan **Taint Analysis**. 

Dengan memodelkan interaksi antara **Source**, **Propagator**, dan **Sink**, insinyur keamanan aplikasi dapat menulis *custom ruleset* yang secara deterministik menangkap kerentanan kritikal sembari meminimalkan *false positive*.

```
[Legacy / Naive Linting]                   [Production DevSecOps SAST]
- Pencocokan Pola Teks Dangkal       ->   - Model Semantik AST, CFG, & DFG
- Full Scan Berdurasi Jam-jaman      ->   - Differential PR Scanning (< 60 detik)
- False Positive Tinggi & Fatigued   ->   - Inter-procedural Taint Validation
- Menghambat Eksekusi Developer      ->   - Deterministic Quality Gate via SARIF
```

Skalabilitas enterprise dicapai melalui pemindaian diferensial inkremental, pemanfaatan format standar OASIS SARIF v2.1.0, serta segregasi evaluasi: *lightweight semantic checks* pada level *Pull Request* untuk menjaga *developer velocity*, dipadukan dengan *deep inter-procedural analysis* asinkron pada jadwal *nightly builds*. Sistem tata kelola *baseline* dan pencegahan manipulasi *suppression* menjamin bahwa utang keamanan masa lalu dapat dikelola secara bertahap tanpa membuka ruang bagi masuknya kerentanan baru ke lingkungan produksi.