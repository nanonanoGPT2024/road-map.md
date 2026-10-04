# Modul 07-03-01: Static Application Security Testing (SAST) & Linter Keamanan

---

## 1. Identitas Modul

* **Track:** DevSecOps Engineering
* **Kategori:** 07 - Quality and Security
* **Bab:** 03 - Static Application Security Testing (SAST) & Linter Keamanan
* **Modul:** 01 - Arsitektur Analisis Statis, Semantic Taint Tracking, dan Integrasi Quality Gate Enterprise
* **Tingkat Kesulitan:** Advanced / Enterprise Professional
* **Prasyarat:**
  * Pemahaman mendalam tentang siklus hidup kompilasi kode (Lexing, Parsing, Abstract Syntax Tree).
  * Penguasaan dasar bahasa pemrograman Go, Python, dan JavaScript/TypeScript.
  * Pengalaman mengonfigurasi pipeline CI/CD (GitHub Actions / GitLab CI).
  * Pemahaman konsep kerentanan OWASP Top 10 (khususnya Injection, SSRF, dan Broken Access Control).
* **Estimasi Waktu Penyelesaian:** 180 Menit

---

## 2. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

* **LO-01:** Menganalisis perbedaan mekanis antara pemindaian berbasis *Regular Expression* (Regex) dan pemindaian struktural berbasis *Abstract Syntax Tree* (AST).
* **LO-02:** Mengonstruksi model *Data Flow Analysis* (DFA) dan *Inter-procedural Taint Analysis* untuk melacak propagasi payload dari *Source*, melintasi *Propagator/Sanitizer*, hingga mencapai *Sink*.
* **LO-03:** Menulis *custom rules* Semgrep tingkat lanjut menggunakan sintaks deklaratif YAML berbasis Semantic/Taint Engine.
* **LO-04:** Merancang dan mengimplementasikan arsitektur integrasi SonarQube/SonarCloud pada pipeline CI/CD skala enterprise.
* **LO-05:** Mengonfigurasi parameter *Automated Quality Gates* berbasis metodologi *Clean as You Code* guna mencegah regresi keamanan pada branch utama.
* **LO-06:** Mengembangkan prosedur operasional standar (SOP) untuk *False Positive Triage* dan manajemen *security debt*.
* **LO-07:** Mengintegrasikan keluaran pemindaian berbasis Static Analysis Results Interchange Format (SARIF) ke dalam dasbor keamanan terpusat.
* **LO-08:** Mengevaluasi batasan teoritis SAST (misalnya refleksi dinamis, RPC boundaries) dan merumuskan strategi mitigasi kompensasi.

---

## 3. Concept Map & Architecture Diagram

```
+---------------------------------------------------------------------------------------+
|                              SAST INTERNAL ENGINE ARCHITECTURE                         |
+---------------------------------------------------------------------------------------+
|  Source Code Files (.go, .py, .java, .js)                                             |
|        |                                                                              |
|        v [Lexical Analyzer / Tokenizer]                                               |
|  Token Stream: [IDENT("req"), ACCESS("."), IDENT("Query"), ASSIGN("="), LIT("x")]     |
|        |                                                                              |
|        v [Parser / Grammar Rules]                                                     |
|  Abstract Syntax Tree (AST): Representasi Hierarki Simbolik                           |
|        |                                                                              |
|        +-----------------------------------+-----------------------------------+      |
|        |                                   |                                   |      |
|        v [Semantic Model Construction]     v [Control Flow Graph (CFG)]        |      |
|  Symbol Table & Type Resolution     Blok Dasar Eksekusi & Percabangan          |      |
|        |                                   |                                   |      |
|        +-----------------+-----------------+                                   |      |
|                          |                                                     |      |
|                          v                                                     |      |
|            Data Flow Graph (DFG) / Program Dependence Graph (PDG)              |      |
|                          |                                                     |      |
|                          v                                                     |      |
|             Inter-procedural Taint Engine                                      |      |
|             - Source  : Titik masuk input eksternal tak tepercaya              |      |
|             - Tracker : Propagasi variabel antar-fungsi/file                   |      |
|             - Sanitizer: Fungsi validasi/encoding (Escape, Parameterize)       |      |
|             - Sink    : Operasi kritis (Exec, Query, Write, Network)           |      |
|                          |                                                     |      |
|                          v [Rule Matching Engine] <--- Custom Rules / Policies |      |
|                  Temuan Pelanggaran / Vulnerability Matrix                     |      |
+--------------------------+-------------------------------------------------------------+
                           |
                           v
+---------------------------------------------------------------------------------------+
|                       ENTERPRISE PIPELINE INTEGRATION (CI/CD)                         |
+---------------------------------------------------------------------------------------+
| Developer Workstation            CI Runner (GitHub Actions / GitLab)     Enterprise Gate
| +-------------------+            +-------------------------------+    +---------------+
| | Git Commit / Push | ---------> | Run Semgrep (Fast Linter)     |    | SonarQube     |
| +-------------------+            | Parse AST / Fast Semantic     |    | Deep Engine   |
|                                  +---------------+---------------+    +-------+-------+
|                                                  |                            |
|                                                  v                            v
|                                  +-------------------------------+    +---------------+
|                                  | SARIF Normalization Engine    | -> | Quality Gate  |
|                                  +---------------+---------------+    | PASS / BLOCK  |
|                                                  |                    +---------------+
|                                                  v                            |
|                                  +-------------------------------+            |
|                                  | PR Annotation & Feedback Loop | <----------+
|                                  +-------------------------------+
```

---

## 4. Mengapa Ini Penting

Implementasi SAST dan linter keamanan modern bukan sekadar otomasi pengecekan kode, melainkan pilar struktural dalam paradigma *Shift-Left Security*. Mengidentifikasi kerentanan pada tahap pengembangan memberikan dampak strategis:

1. **Efisiensi Finansial dan Biaya Remediasi:** Berdasarkan metrik NIST (*National Institute of Standards and Technology*), biaya remediasi kerentanan keamanan perangkat lunak pada fase pasca-rilis (*production*) mencapai 30 hingga 100 kali lipat lebih tinggi dibandingkan perbaikan yang dilakukan pada fase desain atau pengkodean awal (*commit phase*). Kerentanan logika seperti SQL Injection atau Remote Code Execution (RCE) yang lolos ke produksi menimbulkan beban investigasi forensik, downtime sistem, audit regulasi, serta sanksi finansial.
2. **Pengurangan Latensi Remediasi (Mean Time to Remediate - MTTR):** Feedback langsung di lingkungan Pull Request (PR) memungkinkan pengembang langsung merekayasa ulang kode bermasalah saat konteks logika kode masih segar dalam ingatan (*working memory*).
3. **Kepatuhan Terhadap Standar Regulasi:** Standar kepatuhan industri seperti PCI-DSS 4.0 (Persyaratan 6.2 dan 6.3), ISO/IEC 27001, SOC 2 Type II, dan panduan keamanan NIST SP 800-218 (Secure Software Development Framework - SSDF) secara eksplisit mewajibkan validasi statis otomatis terhadap kode sumber aplikasi sebelum artefak dideploy ke lingkungan non-pengembangan.

---

## 5. Apa Itu Konsep (Definisi Formal)

### 5.1 Abstract Syntax Tree (AST)
*Abstract Syntax Tree* adalah struktur data pohon yang merepresentasikan struktur sintaksis hierarkis dari kode sumber yang ditulis dalam bahasa pemrograman tertentu. Berbeda dengan teks mentah, AST membuang detail leksikal permukaan seperti spasi, indentasi, dan komentar, serta berfokus pada hubungan struktural antara operator, operan, deklarasi variabel, pemanggilan fungsi, dan alur percabangan. Setiap node dalam pohon merepresentasikan sebuah konstruksi yang terjadi dalam kode sumber.

### 5.2 Control Flow Graph (CFG) dan Data Flow Analysis (DFA)
* **Control Flow Graph (CFG):** Representasi terarah dari seluruh jalur eksekusi yang dapat dilalui oleh program selama berjalan. Titik simpul (*nodes*) berupa *basic blocks* (urutan instruksi linier tanpa percabangan internal), dan sisi (*edges*) merepresentasikan lompatan eksekusi (*branching, loops, jumps*).
* **Data Flow Analysis (DFA):** Teknik untuk mengumpulkan informasi tentang kemungkinan kumpulan nilai atau properti yang dihitung pada berbagai titik dalam program komputer sepanjang alur CFG.

### 5.3 Taint Analysis (Analisis Noda)
Taint Analysis adalah bentuk spesifik dari DFA yang melacak aliran informasi tak tepercaya (*untrusted / tainted data*) dari komponen tertentu ke komponen lain dalam sistem. Analisis ini dibangun di atas tiga elemen formal:
* **Source ($\mathcal{S}$):** Titik awal tempat data yang dapat dikontrol oleh pengguna luar masuk ke dalam batas kepercayaan aplikasi (contoh: parameter HTTP request, pembacaan file eksternal, WebSocket input).
* **Sanitizer / Neutralizer ($\mathcal{N}$):** Operasi transformasi data yang secara komputasi menjamin data berbahaya dinetralkan, divalidasi, atau di-encode sehingga tidak lagi membawa sifat eksploitatif.
* **Sink ($\mathcal{K}$):** Titik akhir eksekusi sensitif di mana eksekusi data yang belum dinetralkan dapat memicu kegagalan keamanan sistemik (contoh: fungsi eksekusi sistem `os.system()`, interpretasi query SQL `db.Query()`, atau pembukaan berkas direktori).

Hubungan formal Taint Analysis dapat didefinisikan sebagai:
$$\text{Vulnerability} = \exists \text{ path } P(\mathcal{S} \to \mathcal{K}) \quad \text{s.t.} \quad P \cap \mathcal{N} = \emptyset$$
Kerentanan terjadi jika terdapat jalur propagasi data dari Source $\mathcal{S}$ ke Sink $\mathcal{K}$ tanpa melalui Sanitizer $\mathcal{N}$ yang valid untuk konteks sink tersebut.

---

## 6. Bagaimana Cara Kerjanya

Mekanisme internal pemindaian SAST tingkat lanjut beroperasi melalui pipeline multi-tahap yang memproses kode sumber dari bentuk tekstual mentah hingga representasi semantik terkomputasi:

```
[Raw Code] -> (1. Lexing) -> [Tokens] -> (2. Parsing) -> [AST] 
           -> (3. Semantic Normalization) -> [CFG / DFG] 
           -> (4. Taint Tracking Engine) -> (5. Pattern Evaluation) -> [Findings]
```

### Tahap 1 & 2: Tokenization dan AST Parsing
Lexer memindai karakter mentah dan mengonversinya menjadi token leksikal terstruktur. Parser kemudian mengevaluasi token stream berdasarkan tata bahasa (*grammar*) formal bahasa target, menghasilkan representasi pohon hierarki.

Sebagai ilustrasi, ekspresi Python berikut:
```python
query = "SELECT * FROM users WHERE id = '" + user_input + "'"
```
Dikonversi menjadi representasi node AST:
* `Assign`
  * `targets`: `[Name(id='query', ctx=Store())]`
  * `value`: `BinOp`
    * `left`: `BinOp`
      * `left`: `Constant(value="SELECT * FROM users WHERE id = '")`
      * `op`: `Add()`
      * `right`: `Name(id='user_input', ctx=Load())`
    * `op`: `Add()`
    * `right`: `Constant(value="'")`

### Tahap 3: Konstruksi Control Flow Graph (CFG) dan Symbol Table
Engine SAST membangun CFG untuk menentukan blok dasar program dan alur kendali. Pada tahap ini, *symbol table* dibuat untuk melacak cakupan (*scope*) variabel, tipe data (*type inference*), dan visibilitasnya. Variabel `user_input` yang dideklarasikan di level handler fungsi akan dipetakan referensinya ke seluruh cakupan lokal maupun closure.

### Tahap 4: Inter-procedural Data Flow & Taint Tracking
Engine SAST menandai variabel dari Source sebagai `TAINTED(id)`. Saat eksekusi melewati assignment, operasi manipulasi string, atau pemanggilan fungsi pembantu (*inter-procedural call*):
1. Status `TAINTED` disebarkan ke variabel target (`query = TAINTED + Constant` $\to$ `query` menjadi `TAINTED`).
2. Jika variabel melewati fungsi validasi tipe data (misal: casting ke `int(user_input)`), engine yang mengenali sanitizer ini akan menghapus label `TAINTED` (*cleansing*).
3. Jika variabel mencapai Sink (`cursor.execute(query)`) dan status `TAINTED` masih melekat pada argumen query, engine membangkitkan alert kerentanan.

---

## 7. Perbandingan Paradigma / Taksonomi Matriks

| Parameter Evaluasi | Regex-based Scanners (mis. Trufflehog/GitLeaks) | Linter Konvensional (mis. ESLint, Flake8) | AST-based SAST (mis. Bandit, Semgrep Basic) | Deep Semantic & Taint Engine (mis. Semgrep Pro, SonarQube Deep, CodeQL) |
| :--- | :--- | :--- | :--- | :--- |
| **Mekanisme Inti** | Pencocokan string pola linier (*pattern matching*). | Pemindaian aturan gaya kode dan pola AST lokal satu berkas. | Pola struktural berbasis pohon kode, pemetaan ekspresi AST. | Global inter-procedural Data Flow Analysis, Path-sensitive Taint Analysis. |
| **Konteks Kode** | Nol (mengabaikan komentar vs kode executable). | Terbatas pada file tunggal dan node lokal. | Menengah (membedakan tipe node, variabel, string literal). | Sangat Tinggi (melacak aliran data lintas fungsi, kelas, dan multi-file). |
| **Tingkat False Positive** | Sangat Tinggi (> 50%). | Moderat. | Rendah-Menengah. | Rendah (jika sanitasi dikenali dengan baik). |
| **Tingkat False Negative** | Tinggi (mudah dibypass variasi sintaks/spasi). | Tinggi (tidak memetakan aliran data antar fungsi). | Moderat (gagal jika data dialirkan lewat variabel perantara). | Rendah (mampu melacak pelarian variabel yang kompleks). |
| **Kecepatan Eksekusi** | Sangat Cepat (megabyte per detik). | Sangat Cepat (skala milidetik). | Cepat (skala detik). | Lambat-Moderat (skala menit, membutuhkan pemetaan dependensi). |
| **Beban Komputasi** | $O(N)$ terhadap ukuran teks. | $O(N)$ terhadap jumlah node AST. | $O(N \cdot M)$ terhadap ukuran rule set. | $O(N^2)$ hingga $O(N^3)$ karena kompleksitas graph traversal. |
| **Kasus Penggunaan Optimal** | Deteksi Secret/Kredensial, Hardcoded Keys. | Standardisasi gaya kode, deteksi dead code, bug sederhana. | Deteksi penggunaan API usang, salah konfigurasi library statis. | Deteksi Injection (SQL, Command), SSRF, Deserialization, Path Traversal. |

---

## 8. Analisis Mendalam Attack Surface & Vector Matrix

Taint-based SAST difokuskan untuk menghentikan vektor serangan berikut sebelum kode dikompilasi atau dijalankan:

| Kerentanan & CWE | Typical Attack Vectors | Source ($\mathcal{S}$) Input Points | Sink ($\mathcal{K}$) Execution Targets | Kebutuhan Validasi Sanitizer ($\mathcal{N}$) |
| :--- | :--- | :--- | :--- | :--- |
| **SQL Injection**<br>`CWE-89` | Manipulasi klausa SQL melalui parameter query injection. | `http.Request.URL.Query()`, `request.args.get()`, GraphQL resolver input. | `database/sql.DB.Query()`, `cursor.execute()`, raw ORM queries (`session.execute()`). | Prepared statement parameterized query, Object Relational Mapping (ORM) query builder aman. |
| **OS Command Injection**<br>`CWE-78` | Penggunaan separator shell (`;`, `\|`, `&&`) untuk mengeksekusi biner arbitrer. | Header HTTP, parsing argumen CLI dari input klien, webhook payload. | `os/exec.Command()`, `subprocess.Popen(..., shell=True)`, `child_process.exec()`. | Penggunaan `shell=False` dengan argumen array statis, escape spesifik OS (`shlex.quote`). |
| **Server-Side Request Forgery (SSRF)**<br>`CWE-918` | Memaksa server internal mengakses metadata cloud (`169.254.169.254`) atau intranet. | Parameter webhook URL, download file dari tautan luar. | `http.Get()`, `requests.get()`, `fetch()`, `urllib.request.urlopen()`. | Whitelisting IP/Domain, pemblokiran alamat IP non-routable/RFC-1918 pada level network client. |
| **Path Traversal**<br>`CWE-22` | Urutan direktori traversi (`../`, `..\`) untuk membaca file privat sistem operasi. | Nama file unggahan, parameter download path. | `os.Open()`, `open()`, `fs.readFile()`, `sendFile()`. | Ekstraksi basename (`filepath.Base`), pemastian path absolut berada di dalam target base directory. |
| **Insecure Deserialization**<br>`CWE-502` | Stream objek yang diserialisasi dimodifikasi untuk RCE saat instansiasi. | Raw HTTP body, pesan antrean broker (Kafka, RabbitMQ). | `pickle.loads()`, `yaml.load(..., Loader=Loader)`, `ObjectInputStream.readObject()`. | Penggunaan parser format data aman (JSON, Protobuf), safe loading (`yaml.safe_load`). |

---

## 9. Code Example Sederhana: Regex vs AST

Berikut adalah perbandingan deteksi kerentanan SQL Injection menggunakan pendekatan Regex yang rapuh dibandingkan representasi rule Semgrep berbasis AST sederhana.

### 9.1 Kode Rentan Target (Python)
```python
# target.py
def get_user_profile(request):
    user_id = request.GET.get("id")
    # VULNERABLE: String formatting mentah pada SQL query
    query = "SELECT * FROM profiles WHERE user_id = '%s'" % user_id
    db.cursor().execute(query)
```

### 9.2 Pendekatan Regex (Rapuh dan Banyak Mengabaikan Kasus)
```regex
# Regex untuk mendeteksi execute dengan formatting:
execute\(.*(%|\+).*format.*\)
```
*Kelemahan Regex:* Jika kode memisahkan string query ke dalam variabel seperti pada baris `query = ...` kemudian memanggil `db.cursor().execute(query)`, regex di atas mengalami **False Negative** (gagal mendeteksi) karena pola format tidak berada persis di dalam pemanggilan `.execute()`. Jika ditambahkan kelonggaran, regex akan memicu ribuan **False Positive** pada operasi log string biasa.

### 9.3 Pendekatan AST/Semantic Pattern (Semgrep Simple Rule)
Aturan ini memeriksa struktur sintaksis pembuatan string SQL yang digabungkan atau diformat dengan variabel, tanpa memedulikan spasi, baris baru, maupun penggunaan variabel perantara:

```yaml
# semgrep-simple-sqli.yaml
rules:
  - id: simple-python-sqli
    languages: [python]
    severity: ERROR
    message: "Terdeteksi konstruksi SQL query menggunakan manipulasi string dinamis."
    metadata:
      cwe: "CWE-89"
      owasp: "A03:2021 - Injection"
    patterns:
      - pattern-either:
          - pattern: $DB.cursor().execute("..." % $VAR)
          - pattern: $DB.cursor().execute("...".format($VAR))
          - pattern: $DB.cursor().execute(f"...{$VAR}...")
          - pattern: |
              $QUERY = "..." % $VAR
              ...
              $DB.cursor().execute($QUERY)
          - pattern: |
              $QUERY = f"...{$VAR}..."
              ...
              $DB.cursor().execute($QUERY)
```

---

## 10. Code Example Lanjutan: Production-Ready Custom Taint Rule

Aturan produksi memerlukan pelacakan aliran data (*Taint Mode*) lengkap lintas scope untuk mendeteksi *Command Injection* pada aplikasi Go, dengan mengecualikan masukan yang telah melewati fungsi validasi ketat (*Sanitizer*).

### 10.1 Definisi Custom Semgrep Taint Rule
Simpan berkas berikut sebagai `rules/go-command-injection-taint.yaml`:

```yaml
rules:
  - id: advanced-go-command-injection
    languages: [go]
    severity: ERROR
    mode: taint
    message: |
      CRITICAL: Data tidak tepercaya (tainted) dari HTTP input terpropagasi langsung 
      ke dalam eksekusi OS Command (exec.Command). Hal ini memungkinkan eksekusi 
      kode arbitrer (Remote Code Execution - CWE-78). Pastikan input divalidasi 
      menggunakan skema allowlist atau gunakan biner dengan argumen tetap tanpa shell.
    metadata:
      cwe: "CWE-78: Improper Neutralization of Special Elements used in an OS Command"
      owasp: "A03:2021 - Injection"
      confidence: HIGH
      references:
        - https://cwe.mitre.org/data/definitions/78.html
        - https://owasp.org/www-community/attacks/Command_Injection

    pattern-sources:
      # Sumber 1: Input langsung dari context query request standar net/http
      - pattern: |
          ($REQ : *http.Request).URL.Query().Get(...)
      # Sumber 2: Gin Framework parameter access
      - pattern: |
          ($CTX : *gin.Context).Query(...)
      - pattern: |
          ($CTX : *gin.Context).Param(...)
      # Sumber 3: Input dari I/O read reader eksternal
      - pattern: |
          io.ReadAll($REQ.Body)

    pattern-sanitizers:
      # Sanitizer 1: Penggunaan fungsi pembersih khusus allowlist regex
      - pattern: |
          sanitizeNumericOnly(...)
      - pattern: |
          sanitizeAgainstAllowlist(...)
      # Sanitizer 2: Konversi ke tipe data integer (menghilangkan sifat eksploitatif)
      - pattern: |
          strconv.Atoi(...)

    pattern-sinks:
      # Sink 1: Eksekusi command langsung via library bawaan Go os/exec
      - pattern: exec.Command($PROG, ...)
      - pattern: exec.CommandContext($CTX, $PROG, ...)
      # Sink 2: Panggilan eksekusi shell eksplisit
      - pattern: exec.Command("sh", "-c", $ARG, ...)
      - pattern: exec.Command("bash", "-c", $ARG, ...)
```

### 10.2 Kode Uji Validasi (Test Case)
Simpan berkas ini sebagai `app/cmd_test_sample.go`:

```go
package main

import (
	"net/http"
	"os/exec"
	"strconv"
	"regexp"
	"github.com/gin-gonic/gin"
)

var safeAlphabetRegex = regexp.MustCompile("^[a-zA-Z0-9_-]+$")

func sanitizeAgainstAllowlist(input string) string {
	if !safeAlphabetRegex.MatchString(input) {
		return ""
	}
	return input
}

func VulnerableHandler(c *gin.Context) {
	// Source: Input pengguna dari URL query param
	taintedInput := c.Query("tool")

	// SINK HIT: Variable mengalir langsung ke Sink tanpa Sanitizer
	// Rule harus MENANGKAP baris ini!
	cmd := exec.Command("sh", "-c", "ping -c 1 "+taintedInput)
	_ = cmd.Run()
}

func SafeHandlerSanitized(c *gin.Context) {
	taintedInput := c.Query("tool")

	// Melalui Sanitizer yang dikenali rule
	cleanInput := sanitizeAgainstAllowlist(taintedInput)

	if cleanInput != "" {
		// SINK AMAN: Rule harus MENGABAIKAN baris ini karena data telah bersih
		cmd := exec.Command("ping", "-c", "1", cleanInput)
		_ = cmd.Run()
	}
}

func SafeHandlerTypeConversion(c *gin.Context) {
	taintedCount := c.Query("count")

	// Sanitizer: Konversi tipe data menjamin eliminasi payload shell
	cleanCount, err := strconv.Atoi(taintedCount)
	if err != nil {
		c.AbortWithStatus(http.StatusBadRequest)
		return
	}

	// SINK AMAN
	cmd := exec.Command("sleep", strconv.Itoa(cleanCount))
	_ = cmd.Run()
}
```

---

## 11. Diagram Alur Serangan & Mitigasi

```
DIAGRAM PROPAGASI TAINT DARI SOURCE KE SINK (OS COMMAND INJECTION)

+-----------------------------------------------------------+
| Untrusted Actor                                           |
| Payload: "127.0.0.1; cat /etc/passwd"                     |
+-----------------------------------------------------------+
                             |
                             v [HTTP GET /ping?tool=...]
+-----------------------------------------------------------+
| [SOURCE]: c.Query("tool")                                 |
| Status: TAINTED [Variable: taintedInput]                  |
+-----------------------------------------------------------+
                             |
         +-------------------+-------------------+
         | [JALUR RENTAN]                        | [JALUR TERMITIGASI]
         v                                       v
+-----------------------------+         +-------------------------------+
| Pengabaian Validasi /       |         | [SANITIZER]:                  |
| Penggabungan String         |         | sanitizeAgainstAllowlist(...) |
| ("ping -c 1 " +             |         | Memastikan input hanya berupa |
|  taintedInput)              |         | karakter alfanumerik.         |
| Status: TETAP TAINTED       |         | Status: TAINT REMOVED         |
+-----------------------------+         +-------------------------------+
         |                                       |
         v                                       v
+-----------------------------+         +-------------------------------+
| [SINK]:                     |         | [SINK]:                       |
| exec.Command("sh", "-c", ..)|         | exec.Command("ping", "-c", ..)|
| Eksekusi Shell Arbitrer     |         | Payload shell dinetralisir    |
+-----------------------------+         +-------------------------------+
         |                                       |
         v                                       v
+-----------------------------+         +-------------------------------+
| VULNERABILITY CONFIRMED     |         | SAST SUPPRESSION              |
| Engine: Flagging Violation  |         | Engine: No Violation Emitted  |
| Pipeline: Quality Gate FAIL |         | Pipeline: Quality Gate PASS   |
+-----------------------------+         +-------------------------------+
```

---

## 12. Trade-offs & Security vs Usability / Performance

Penerapan SAST dalam siklus hidup rekayasa perangkat lunak melibatkan trade-off yang harus diseimbangkan oleh Security Architect:

```
               [ Analisis Mendalam (Deep Inter-procedural) ]
                                   /\
                                  /  \
                                 /    \
                                /      \
                               /        \
   (Akurasi Tinggi, FP Rendah)/          \(Waktu Komputasi Sangat Lama,
  Beban Engine Sangat Berat) /            \ CI Pipeline Timeout)
                            /              \
                           /________________\
[ Kecepatan Pipeline ]                         [ Keringanan Beban Pengembang ]
 (Eksekusi Detik, Regex/AST)                   (Developer Experience / Frictionless)
 (Kelemahan: FP/FN Tinggi)                     (Risiko: Vulnerability lolos)
```

1. **Akurasi vs Kecepatan Analisis (Execution Time):**
   * *Analisis dangkal (AST-only pattern):* Memberikan eksekusi sangat cepat (< 30 detik untuk repositori besar), cocok untuk Git Pre-commit Hook. Namun, pendekatan ini meningkatkan False Positive dan False Negative karena ketiadaan konteks aliran data.
   * *Analisis mendalam (Inter-procedural Taint Tracking):* Menghitung closure call graph global. Membutuhkan waktu eksekusi 10 hingga 45 menit pada basis kode jutaan baris. Jika dimasukkan langsung ke PR blocker, pengembang mengalami *productivity friction*.
2. **False Positives vs Developer Fatigue:**
   * Memasang rule-set yang terlalu sensitif akan memicu ratusan alert yang tidak dapat dieksploitasi (*informational noise*). Dampaknya adalah *alert fatigue*, di mana tim pengembang mengabaikan temuan keamanan atau menggunakan bypass tag massal (seperti `// NOSONAR` atau `# nosec`).
3. **Strict Quality Gate vs Delivery Velocity:**
   * Memblokir merge PR atas setiap temuan keparahan `LOW` atau `MEDIUM` akan menghentikan delivery feature bisnis. Rekomendasi enterprise: Blokir merge (`PR blocker`) *hanya* untuk kerentanan `CRITICAL` dan `HIGH` yang memiliki status kepastian tinggi (*High Confidence CWE*), sementara level `MEDIUM` dimasukkan ke dalam tracking backlog security debt.

---

## 13. Edge Cases & Complex Failure Modes

Implementasi SAST sering kali gagal mendeteksi kerentanan (*False Negative*) akibat keterbatasan teoritis berikut:

1. **Refleksi Dinamis dan Dynamic Class Loading:**
   * Di lingkungan Java (`Class.forName(str).newInstance()`), Go (`reflect` package), atau Python (`eval()`, `getattr()`), representasi aliran data terputus pada level pemodelan graph. Engine SAST tidak dapat memprediksi string apa yang akan dievaluasi secara dinamis saat runtime, sehingga propagasi taint terhenti (*broken trace*).
2. **Batas Antar Layanan (*Microservice / RPC Boundaries*):**
   * Taint Analysis standar beroperasi pada batas satu repositori tunggal (*monolithic code base*). Jika Layanan A menerima input HTTP lalu menyimpannya di Kafka Queue atau memanggil Layanan B via gRPC, analisis noda terputus di titik kirim jaringan (*network boundary*). Layanan B menganggap input yang diterima dari RPC sebagai data baru, sehingga potensi eksploitasi di Layanan B gagal diprediksi.
3. **Konteks Sanitasi Tidak Sesuai (Mismatched Sanitization):**
   * Penggunaan sanitizer yang benar untuk satu konteks tidak menjamin keamanan di konteks lain. Contoh: Fungsi `html.EscapeString()` efektif membersihkan payload Cross-Site Scripting (XSS) di dalam body HTML, namun **tidak berguna** jika variabel ditempatkan di dalam atribut konteks JavaScript (`<script>var x = "{{ .Tainted }}";</script>`) atau URL link (`<a href="{{ .Tainted }}">`). Engine SAST yang tidak *context-aware* akan menandai input ini sebagai data aman (*Sanitized*), padahal kerentanan XSS tetap dapat dieksploitasi.
4. **Sanitizer Tersembunyi di Custom Wrapper Framework:**
   * Pengembang enterprise sering kali membuat wrapper validasi internal yang tidak terdaftar dalam kamus standar engine komersial/open source. SAST akan menandai seluruh panggilan ini sebagai *vulnerable* (*False Positive masif*) kecuali tim AppSec mendaftarkan wrapper tersebut ke dalam kamus *custom-sanitizers*.

---

## 14. Anti-Patterns & Common Vulnerabilities

Penerapan SAST yang salah kaprah di level arsitektur dan operasional dapat memunculkan anti-pattern berikut:

### 14.1 The "NOSONAR / nosec" Infection Pattern
```python
# ANTI-PATTERN: Menekan peringatan keamanan tanpa analisis teknis mendalam
import subprocess

def run_backup(path):
    # Pengembang membungkam SAST karena terburu-buru mengejar deadline sprint
    subprocess.Popen(f"tar -czf backup.tar.gz {path}", shell=True)  # nosec # NOSONAR
```
*Dampak:* Penumpukan kerentanan tersembunyi (*hidden technical security debt*). Token pembungkam diabaikan dalam audit umum dan meloloskan RCE langsung ke lingkungan produksi.

### 14.2 Scanning Kode Tanpa Dependency Context (Shallow Scanning)
Menjalankan analisis SAST pada level PR hanya dengan mengisolasi berkas yang berubah (*diff-only mode*) tanpa menyediakan AST lengkap dari dependensi dan fungsi perantara. Hal ini merusak *Inter-procedural Data Flow Analysis*, sehingga taint engine tidak dapat memetakan apakah parameter yang masuk ke fungsi di file tersebut berasal dari input yang aman atau tidak.

### 14.3 Mengandalkan SAST sebagai Satu-Satunya Kontrol Validasi
Mengasumsikan bahwa jika SAST menghasilkan skor *Zero Vulnerabilities*, aplikasi sudah aman sepenuhnya. SAST secara desain buta terhadap masalah arsitektur runtime seperti:
* *Broken Object Level Authorization (BOLA/IDOR)*.
* Masalah konfigurasi infrastruktur TLS/mTLS.
* Race condition tingkat kernel (TOCTOU - *Time-of-Check to Time-of-Use*).

---

## 15. Best Practices & Enterprise Remediation Guide

Terapkan metodologi berikut untuk integrasi SAST skala enterprise:

### 15.1 Clean as You Code (CaYC) Philosophy
Pindahkan fokus tim keamanan: Jangan mencoba menyelesaikan ribuan *legacy security debts* dalam satu malam. Terapkan Quality Gate yang ketat **hanya pada kode baru atau kode yang diubah (New Code Period)**:
* Kode baru harus memiliki 0 *New Vulnerabilities* keparahan Critical/High.
* Kode baru harus memiliki cakupan review rule keamanan 100%.
* Kode lama (*Overall Code*) diisolasi ke dalam backlog remediasi bertahap.

### 15.2 Standard Operating Procedure (SOP) False Positive Triage
Jika pengembang mencurigai temuan SAST merupakan False Positive, proses verifikasi harus mengikuti alur baku berikut:

```
[ Temuan SAST ]
      |
      v
[ 1. Verifikasi Jalur Source-to-Sink ]
      |---> Apakah input berasal dari batas kepercayaan luar?
      |     TIDAK -> Tandai False Positive (Konteks Internal / Batch Job).
      |
      +---> YA: [ 2. Evaluasi Sanitizer ]
                 |---> Apakah ada validasi/encoding yang belum dikenali engine?
                 |     YA -> a. Daftarkan sanitizer ke rule kustom SAST.
                 |           b. Tandai False Positive via dashboard terpusat.
                 |
                 +---> TIDAK: [ 3. Vulnerability Confirmed ]
                               |---> Block PR!
                               |---> Rekomendasikan remediation pattern baku.
```

*Aturan Baku:* Jangan pernah memberikan izin kepada pengembang untuk menambahkan komentar inline suppression (`#nosec`, `//NOSONAR`) langsung ke basis kode tanpa review dan sign-off dari tim Application Security. Seluruh suppression harus dikelola secara tersentralisasi pada dasbor SAST (mis. SonarQube Server / Semgrep Cloud Platform) lengkap dengan *audit trail* dan masa kedaluwarsa (*expiration date*).

### 15.3 Standardisasi Pelaporan Menggunakan SARIF
Konsolidasikan seluruh keluaran pemindai statis lokal (Semgrep, Sonar, Checkov, Trivy) ke format OASIS standar: **SARIF** (*Static Analysis Results Interchange Format - JSON*). SARIF memungkinkan visualisasi terpadu pada antarmuka *GitHub Code Scanning alerts*, GitLab Security Dashboard, atau DefectDojo.

---

## 16. Hands-on Lab Step-by-Step

Lab ini memandu Anda membangun pipeline keamanan lokal lengkap: memindai kerentanan dengan Semgrep, menulis custom rule, dan mengonfigurasi SonarQube pipeline Quality Gate.

### 16.1 Persiapan Lingkungan (Lab Environment)
Buat struktur direktori proyek dan masuk ke lingkungan virtual:

```bash
mkdir -p devsecops-sast-lab/{src,rules,.github/workflows}
cd devsecops-sast-lab

# Instalasi semgrep CLI
python3 -m venv venv
source venv/bin/activate
pip install semgrep==1.65.0
```

### 16.2 Injeksi Target Kode Rentan (Go Code)
Buat berkas `src/server.go`:

```go
package main

import (
	"database/sql"
	"fmt"
	"net/http"
	"os/exec"

	_ "github.com/mattn/go-sqlite3"
)

func queryUser(db *sql.DB, username string) {
	// Kerentanan 1: SQL Injection melalui String Concatenation
	unsafeQuery := fmt.Sprintf("SELECT id, balance FROM accounts WHERE user = '%s'", username)
	rows, err := db.Query(unsafeQuery)
	if err != nil {
		return
	}
	defer rows.Close()
}

func executeSystemDiag(w http.ResponseWriter, req *http.Request) {
	// Source: HTTP Parameter
	targetHost := req.URL.Query().Get("host")

	// Kerentanan 2: Command Injection
	cmd := exec.Command("bash", "-c", "nslookup "+targetHost)
	out, err := cmd.CombinedOutput()
	if err != nil {
		w.WriteHeader(500)
		return
	}
	w.Write(out)
}

func main() {
	http.HandleFunc("/diag", executeSystemDiag)
	http.ListenAndServe(":8080", nil)
}
```

### 16.3 Menulis Custom Rules Validasi
Buat berkas `rules/custom-audit.yaml`:

```yaml
rules:
  - id: audit-sqli-sprintf
    languages: [go]
    severity: ERROR
    message: "Dilarang menyusun query SQL menggunakan fmt.Sprintf. Gunakan parameter bindings!"
    metadata:
      cwe: "CWE-89"
    patterns:
      - pattern: |
          $QUERY = fmt.Sprintf("$SQL...", ...)
          ...
          $DB.Query($QUERY, ...)
      - metavariable-regex:
          metavariable: $SQL
          regex: (?i)(SELECT|INSERT|UPDATE|DELETE).*

  - id: audit-cmdi-bash
    languages: [go]
    severity: CRITICAL
    mode: taint
    message: "Unsanitized user data reached shell interpreter execution sink!"
    metadata:
      cwe: "CWE-78"
    pattern-sources:
      - pattern: ($REQ : *http.Request).URL.Query().Get(...)
    pattern-sinks:
      - pattern: exec.Command("bash", "-c", ...)
```

### 16.4 Eksekusi Pemindaian Semgrep
Jalankan Semgrep menggunakan custom rule yang telah dibuat:

```bash
semgrep scan --config=rules/custom-audit.yaml --sarif --output=sast-results.sarif src/
```

*Verifikasi Hasil:*
Cek keluaran file `sast-results.sarif` untuk memverifikasi bahwa dua kerentanan (CWE-89 dan CWE-78) tertangkap dengan metadata rule yang benar:

```bash
cat sast-results.sarif | grep -E "(audit-sqli-sprintf|audit-cmdi-bash)"
```

### 16.5 Konfigurasi SonarQube Scanner Pipeline Automation
Buat berkas konfigurasi Sonar scanner `sonar-project.properties`:

```properties
sonar.projectKey=enterprise-sast-sample
sonar.projectName=DevSecOps Enterprise SAST
sonar.projectVersion=1.0.0
sonar.sources=src
sonar.exclusions=**/*_test.go,**/vendor/**
sonar.sourceEncoding=UTF-8

# Menghubungkan hasil pemindaian Semgrep SARIF sebagai laporan generic
sonar.sarifReportPaths=sast-results.sarif

# Konfigurasi Metrik Quality Gate
sonar.qualitygate.wait=true
```

### 16.6 Integrasi GitHub Actions Workflow
Buat pipeline CI/CD di `.github/workflows/sast-gate.yml`:

```yaml
name: DevSecOps SAST & Quality Gate

on:
  pull_request:
    branches: [main, master]
  push:
    branches: [main, master]

jobs:
  sast-validation:
    name: Run SAST Engine & Evaluate Gate
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4
        with:
          fetch-depth: 0 # Deep clone diperlukan untuk analisis 'Clean as you Code'

      - name: Setup Python Environment
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install Semgrep & Run Custom Rules
        run: |
          pip install semgrep==1.65.0
          semgrep scan --config=rules/custom-audit.yaml --sarif --output=semgrep-findings.sarif src/

      - name: Upload SARIF to GitHub Security Tab
        uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: semgrep-findings.sarif

      - name: SonarQube Quality Gate Verification
        uses: sonarsource/sonarqube-scan-action@v2
        env:
          SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
          SONAR_HOST_URL: ${{ secrets.SONAR_HOST_URL }}
        with:
          args: >
            -Dsonar.qualitygate.wait=true
            -Dsonar.sarifReportPaths=semgrep-findings.sarif
```

---

## 17. Real-World Case Study Enterprise

### 17.1 Deskripsi Insiden Keamanan (Equifax Apache Struts - CVE-2017-5638)
Pada tahun 2017, salah satu biro kredit terbesar mengalami pembobolan data masif yang mengekspos catatan finansial pribadi milik lebih dari 147 juta individu. Vektor penetrasi awal adalah kerentanan `CVE-2017-5638` pada framework Apache Struts 2. 

*Akar Masalah:* Framework parsing header `Content-Type` yang rusak. Ketika attacker menyisipkan ekspresi OGNL (*Object-Graph Navigation Language*) di dalam header `Content-Type`, parser memicu pengecualian (*exception processing*) yang meneruskan string error tersebut langsung ke method `findValue()` milik library OGNL. Method ini bertindak sebagai interpreter yang mengeksekusi ekspresi string tersebut sebagai perintah native Java virtual machine.

### 17.2 Analisis: Mengapa Regex Gagal dan Bagaimana Taint Engine Mencegahnya
* **Kegagalan Deteksi Regex:** Banyak organisasi mencoba mendeteksi kode rentan ini menggunakan regex pencarian string pada codebase: `find . -name "*.java" | xargs grep "Content-Type"`. Pendekatan ini gagal total karena definisi class parser berada jauh di dalam pustaka komponen pihak ketiga, dan delegasi pemrosesan error string dilakukan melalui multi-layer inheritance interface (`FileUploadInterceptor` $\to$ `JakartaMultiPartRequest` $\to$ `LocalizedTextUtil`).
* **Deteksi Taint Engine SAST:** Taint-based AST Engine modern memodelkan alur ini secara inter-procedural:
  1. **Source:** Input HTTP Request Header (`Content-Type`).
  2. **Propagation:** Header string disalin ke variabel `message` di dalam class penanganan exception.
  3. **Taint Tracking:** Aliran data dilacak melintasi modul kompilasi, melewati *inter-file boundary* menuju fungsi helper formatting text.
  4. **Sink Detection:** Variabel `message` diteruskan tanpa sanitasi ke dalam method `OgnlUtil.compileAndExecute()` atau `TextParseUtil.translateVariables()`, yang secara semantik didaftarkan sebagai RCE execution sink.
* **Resolusi Enterprise:** Organisasi menerapkan pipeline blocking: Setiap pull request yang menyertakan dependensi atau implementasi yang menghubungkan network input header langsung ke evaluator string dinamis langsung digagalkan oleh Quality Gate, memotong waktu paparan dari berbulan-bulan menjadi 0 hari pada level review integrasi.

---

## 18. Quiz Pemahaman & Challenge

### Soal 1 (Konseptual AST vs Regex)
Mengapa pemindaian kode berbasis AST jauh lebih unggul dalam memvalidasi SQL Injection dibandingkan pemindaian berbasis Regex?
* A. Karena AST mengeksekusi kode secara dinamis di dalam sandbox memori terisolasi.
* B. Karena AST mampu mengenali tipe simpul ekspresi secara terstruktur dan membedakan antara string literal murni, nama identifier, dan pemanggilan method tanpa terpengaruh variasi whitespace atau penamaan variabel.
* C. Karena AST membaca biner mesin (.exe atau ELF) secara langsung pasca-kompilasi.
* D. Karena AST bekerja lebih cepat daripada Regex saat memindai berkas mentah berukuran besar tanpa parsing gramatika.

*Rasional Jawaban:* **B**. Regex hanya mengevaluasi teks datar linier tanpa pemahaman struktur gramatika sintaksis. AST memetakan hierarki bahasa pemrograman, mengenali apakah token merupakan perintah logika atau literal data, sehingga menghilangkan false positive akibat format kode, baris baru, atau komentar.

### Soal 2 (Mekanika Taint Analysis)
Perhatikan alur pseudo-code berikut:
```python
def process_data(request):
    raw_path = request.args.get("path")     # [1]
    norm_path = os.path.normpath(raw_path)  # [2]
    clean_path = os.path.basename(norm_path)# [3]
    with open("/var/app/data/" + clean_path, "r") as f: # [4]
        return f.read()
```
Manakah evaluasi Taint Analysis yang paling akurat?
* A. [4] adalah rentan Path Traversal karena `os.path.normpath` bukan sanitizer.
* B. [3] bertindak sebagai Sanitizer yang sah (`os.path.basename`), memotong seluruh awalan direktori (`../`) dan menghapus label tainted dari variabel sebelum mencapai Sink [4].
* C. Terjadi kerentanan Command Injection pada baris [4].
* D. Taint analysis gagal mengevaluasi kode karena fungsi `open` bukan merupakan Sink.

*Rasional Jawaban:* **B**. `os.path.normpath` tidak aman terhadap traversi jika path relatif diteruskan, tetapi pemanggilan fungsi `os.path.basename` mengambil komponen nama berkas murni paling akhir, mengeliminasi kemampuan penyerang melompat ke direktori induk (`../`). Taint engine yang akurat mengenali fungsi ini sebagai sanitizer untuk Path Traversal sink.

### Soal 3 (Quality Gate Strategy)
Dalam pendekatan *Clean as You Code* (CaYC) pada SonarQube, apa tindakan yang harus diambil jika ditemukan 5 kerentanan `CRITICAL` pada *Overall Code* (kode warisan), namun *New Code* pada Pull Request yang sedang diajukan memiliki 0 kerentanan baru?
* A. Pipeline PR harus langsung diblokir dan pengembang dipaksa merefaktor seluruh kode warisan.
* B. PR disetujui (Quality Gate PASS) untuk merge karena kode baru bersih, sedangkan kode warisan ditangani melalui sprint remediasi terpisah untuk menjaga velocity delivery.
* C. Mengubah severity level kerentanan lama menjadi LOW agar Quality Gate tidak gagal.
* D. Menghapus konfigurasi quality gate dari pipeline.

*Rasional Jawaban:* **B**. Filosofi fundamental *Clean as You Code* adalah menghentikan penambahan utang teknis baru pada *New Code Period* tanpa menghentikan roda rilis bisnis karena kode warisan (*leak period containment*). Utang warisan diperbaiki melalui inisiatif terencana tersendiri.

### Soal 4 (Sink Identification)
Dari opsi fungsi runtime Go berikut, manakah yang **BUKAN** merupakan *Sink* potensial untuk kerentanan Command Injection (`CWE-78`)?
* A. `exec.Command("sh", "-c", input)`
* B. `exec.CommandContext(ctx, "/bin/bash", "-c", input)`
* C. `syscall.Exec(binaryPath, args, env)`
* D. `filepath.Walk(input, walkFn)`

*Rasional Jawaban:* **D**. `filepath.Walk` adalah fungsi penelusuran struktur direktori filesystem (terkait I/O dan potensi Path Traversal/DoS), bukan proses pembuatan/eksekusi perintah sistem operasi tingkat kernel atau shell.

### Soal 5 (Sanitizer Scope Mismatch)
Mengapa sanitasi `url.QueryEscape(input)` tetap berbahaya jika outputnya dipetakan langsung ke dalam sink evaluasi SQL query raw string?
* A. Karena `QueryEscape` hanya meng-encode karakter khusus URL seperti `&`, `=`, dan spasi, tetapi tidak mengamankan karakter pembatas SQL seperti single quote `'` jika diurai oleh parser database SQL.
* B. Karena `QueryEscape` otomatis mengubah string menjadi angka.
* C. Karena library `url` selalu menghasilkan exception error runtime.
* D. Karena SQL query tidak dapat menerima data berformat teks.

*Rasional Jawaban:* **A**. Ini adalah contoh klasik dari Sanitizer Context Mismatch. Mengamankan input untuk konteks transmisi URL tidak berarti input tersebut aman untuk interpretasi query database SQL. Karakter berbahaya SQL tetap dapat lolos.

### Challenge Praktik Arsitektur
**Skenario:** Anda adalah Principal AppSec Engineer pada platform fintech. Tim microservice Python (FastAPI) menggunakan wrapper database internal `CustomRepository.raw_sql_search(query_string)`. SonarQube dan Semgrep standar tidak memicu peringatan apapun saat pengembang melakukan konkatenasi input pengguna ke dalam fungsi tersebut, karena fungsi tersebut tidak masuk dalam pustaka umum bawaan engine pemindai.

**Tugas Anda:**
1. Rancang sebuah *custom taint-mode rule* Semgrep YAML yang mendefinisikan:
   * **Source:** Parameter endpoint FastAPI (`def endpoint(data: Schema, q: str = Query(...)):`)
   * **Sanitizer:** Pemanggilan fungsi validasi UUID internal `validators.is_uuid4(val)`
   * **Sink:** Pemanggilan method class `CustomRepository.raw_sql_search(...)`
2. Konfigurasi aturan tersebut agar memblokir build di GitHub Actions (exit code 1) jika pelanggaran terdeteksi.

---

## 19. Summary & Key Takeaways

* **Perbedaan Paradigma:** Pemindaian Regex bekerja pada level string mentah tanpa pemahaman gramatika, menjadikannya rentan terhadap *False Positives* dan *False Negatives*. Pemindaian berbasis AST dan Semantic Taint Analysis membedah representasi struktural kode sumber, alur kendali (*Control Flow*), dan aliran data (*Data Flow*).
* **Mekanika Taint Tracking:** Pondasi analisis statis modern berpusat pada penelusuran propagasi data tak tepercaya dari titik masuk eksternal (**Source**), melintasi variabel/fungsi tanpa pembersihan yang sah (**Sanitizer**), hingga mencapai operasi sensitif tingkat sistem (**Sink**).
* **Enterprise CI/CD Integration:** Integrasi SAST yang berkelanjutan tidak boleh mengandalkan peninjauan manual. SAST harus diotomatisasi pada level pipeline menggunakan standar pelaporan interoperabel seperti **SARIF**, yang dievaluasi secara terpusat oleh **Automated Quality Gates**.
* **Clean as You Code (CaYC):** Memaksa perbaikan instan atas seluruh utang kode masa lalu (*legacy security debt*) menciptakan friksi operasional besar. Fokuskan Quality Gate untuk memblokir penambahan kerentanan baru pada kode yang sedang dikerjakan (*New Code*).
* **Evolusi Aturan Statis:** Engine SAST enterprise hanya seefektif aturan yang dimilikinya. Kemampuan menulis *Custom Rules* (seperti Semgrep YAML Rules) untuk memetakan framework custom internal organisasi adalah keterampilan wajib seorang DevSecOps / AppSec Engineer.

---

## 20. Referensi Resmi & Standar Keamanan

* **OWASP Source Code Analysis Tools:** Panduan evaluasi dan metrik arsitektur SAST engine.
  * [https://owasp.org/www-community/Source_Code_Analysis_Tools](https://owasp.org/www-community/Source_Code_Analysis_Tools)
* **NIST SP 800-218:** Secure Software Development Framework (SSDF) Version 1.1 - Bagian PW.5 s/d PW.8 (Review Software Architecture and Code).
  * [https://csrc.nist.gov/publications/detail/sp/800-218/final](https://csrc.nist.gov/publications/detail/sp/800-218/final)
* **MITRE CWE (Common Weakness Enumeration):** Taksonomi kerentanan perangkat lunak standar industri.
  * CWE-78 (OS Command Injection): [https://cwe.mitre.org/data/definitions/78.html](https://cwe.mitre.org/data/definitions/78.html)
  * CWE-89 (SQL Injection): [https://cwe.mitre.org/data/definitions/89.html](https://cwe.mitre.org/data/definitions/89.html)
* **Semgrep Rule Syntax & Taint Mode Specification:** Dokumentasi formal deklarasi Semgrep AST/Taint.
  * [https://semgrep.dev/docs/writing-rules/taint-mode/](https://semgrep.dev/docs/writing-rules/taint-mode/)
* **OASIS SARIF Standard Specification:** Static Analysis Results Interchange Format (SARIF) Version 2.1.0.
  * [https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html](https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html)
* **SonarQube Clean Code & Quality Gate Documentation:** Metodologi Clean as You Code.
  * [https://docs.sonarsource.com/sonarqube/latest/user-guide/clean-as-you-code/](https://docs.sonarsource.com/sonarqube/latest/user-guide/clean-as-you-code/)