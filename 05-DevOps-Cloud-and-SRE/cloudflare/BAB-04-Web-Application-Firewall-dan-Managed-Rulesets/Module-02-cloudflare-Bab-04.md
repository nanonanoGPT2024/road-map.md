# Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi (BAB 04: WAF & Managed Rulesets)

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis dan Membedah Arsitektur Ruleset Engine**: Menguasai siklus hidup evaluasi paket HTTP/S pada Rust-based edge engine Cloudflare, termasuk urutan eksekusi fase (Phases DAG), mekanisme *early-exit*, dan penanganan *wirefilter*.
- **Mengonfigurasi Managed Rulesets Secara Terprogram**: Mengimplementasikan Cloudflare Managed Rulesets dan OWASP Core Ruleset (CRS) menggunakan Terraform/OpenTofu dengan konfigurasi *overrides*, *tag-based exclusions*, dan *anomaly scoring system*.
- **Membangun Strategi Mitigasi False Positive Skala Enterprise**: Menerapkan alur kerja *progressive deployment* (Log $\to$ Challenge $\to$ Block) memanfaatkan Cloudflare Logpush, Workers Trace Engine, dan dynamic skip rulesets.
- **Mengoptimalkan Performa & Resource Engine**: Memahami batasan komputasi *regular expression* (PCRE vs RE2), dampak eksekusi payload decoding terhadap CPU cycle edge, dan teknik meminimalkan TTFB (*Time to First Byte*) overhead di bawah 1.5ms.
- **Menangani Insiden Zero-Day (0-Day Mitigation)**: Mengorkestrasi mitigasi darurat pada Layer 7 secara terotomasi via Cloudflare API v4 saat terjadi kerentanan baru (misal: RCE berbasis JNDI/Log4j atau deserialisasi payload multipart).

---

## 2. Prerequisites

Sebelum mempelajari modul ini, Anda wajib menguasai:
- **Jaringan Komputer & Protokol**: RFC 9110/9112 (HTTP/1.1), RFC 9113 (HTTP/2), dan RFC 9000 (HTTP/3/QUIC). Pemahaman mendalam terkait HTTP Request anatomy (Headers, Cookies, Multipart/form-data, URL encoding, Base64 parsing).
- **Konsep Keamanan Aplikasi Web**: OWASP Top 10 (A01:2021 hingga A10:2021), mekanisme serangan Injection (SQLi, NoSQLi, Command Injection), XSS, Path Traversal, SSRF, dan RCE.
- **Infrastructure as Code (IaC)**: Terraform/OpenTofu tingkat menengah, mengerti deklarasi resource provider Cloudflare (`cloudflare_ruleset`, `cloudflare_filter`, HCL expressions, dan dynamic blocks).
- **Penguasaan CLI & Scripting**: `curl`, `jq`, OpenSSL, serta dasar Python/Bash untuk debugging dan load testing.
- **Cloudflare Fundamentals**: Telah menyelesaikan Modul 01 (DNS, Proxy Status `orange-clouded`, SSL/TLS Termination modes, dan Cloudflare Page Rules/Edge Fundamentals).

---

## 3. Concept & Internal Architecture

Arsitektur Web Application Firewall (WAF) modern Cloudflare tidak lagi menggunakan arsitektur legacy berbasis Apache/Nginx ModSecurity (*Lua/Nginx phases*). Arsitektur produksi Cloudflare saat ini ditenagai oleh **Ruleset Engine** yang dibangun di atas bahasa pemrograman **Rust**, terintegrasi langsung ke dalam *traffic pipeline* edge proxy (dikenal secara internal sebagai *Frontline/FL* dan *Pingora*).

```
Incoming L7 Frame
       │
       ▼
┌────────────────────────────────────────────────────────┐
│ Cloudflare Edge (Pingora Proxy - Rust)                 │
│                                                        │
│  [ Phase: http_request_sanitize ]                      │
│        │                                               │
│        ▼                                               │
│  [ Phase: http_ratelimit ]                             │
│        │                                               │
│        ▼                                               │
│  [ Phase: http_request_firewall_custom ] ─────────┐    │
│        │ (Custom WAF Rules / Wirefilter)          │    │
│        ▼                                          │    │
│  [ Phase: http_request_firewall_managed ]         │    │
│        │                                          │    │
│        ├─► Skip Rules (Tag / ID bypass)?          │    │
│        │         │                                │    │
│        │   No    ▼                                │    │
│        ├─► Cloudflare Managed Rules               │    │
│        │         │                                │    │
│        │   No Match                               │    │
│        │         ▼                                │    │
│        └─► Cloudflare OWASP Core Ruleset          │    │
│                  │                                │    │
│                  ▼                                │    │
│        [ Anomaly Score Evaluation ]               │    │
│                  │                                │    │
│                  ▼                                │    │
│       Score >= Threshold?                         │    │
│           ├── Yes ──► Action (Block/Managed Chal.)│    │
│           └── No  ──► Pass to Origin              │    │
│                                                   │    │
└───────────────────────────────────────────────────┼────┘
                                                    │
                   Action Taken? ───────────────────┘
                   (Terminate / Challenge / Log)
```

### 3.1. Ruleset Engine Pipeline & Execution Phases
Edge proxy memproses setiap HTTP request melalui serangkaian fase yang deterministik (*Phases Directed Acyclic Graph* / DAG):

1. **`http_request_transform`**: Normalisasi path, URL rewriting, modifikasi header masuk.
2. **`http_ratelimit`**: Rate limiting evaluasi per IP, session, atau composite fingerprinting.
3. **`http_request_firewall_custom`**: Mengevaluasi Customer Custom Rules (aturan yang didefinisikan secara manual oleh administrator).
4. **`http_request_firewall_managed`**: Mengevaluasi Managed Rulesets (aturan dari tim Cloudflare Threat Intelligence dan OWASP Core Ruleset).
5. **`http_response_firewall_managed`**: Mengevaluasi response body dari origin untuk mencegah data leakage (misal: nomor kartu kredit, SSN, error stack trace).

### 3.2. Rust Wirefilter & Memory Safety
Inti dari Custom Rules dan parsing Ruleset Engine adalah library open-source bernama **Wirefilter** (dikembangkan oleh Cloudflare dalam Rust). 
- Wirefilter mengompilasi ekspresi penyaringan (filter expressions seperti `http.request.uri.path contains "/admin"`) menjadi bytecode yang dieksekusi secara instan tanpa alokasi memori berlebih (*zero-copy parsing*).
- Berbeda dengan ModSecurity regex tradisional yang rentan terhadap Catastrophic Backtracking ($O(2^n)$ CPU exhaustion), Wirefilter membatasi eksekusi engine parsing string menggunakan algoritma pencocokan linear $O(n)$ dan RE2 deterministic finite automaton (DFA).

### 3.3. Anomaly Scoring System vs. Paranoia Levels
Pada **Cloudflare OWASP Core Ruleset**, pendekatan yang digunakan adalah **Collaborative Anomaly Scoring**, bukan *Immediate Blocking*.
- **Traditional WAF (ModSecurity Paranoia 1-4 standard)**: Jika sebuah rule cocok dengan pola serangan, rule tersebut langsung memblokir request. Hal ini memicu false positive yang sangat tinggi.
- **Cloudflare OWASP Anomaly Scoring**:
  - Request masuk akan dicocokkan dengan puluhan rule deteksi.
  - Setiap rule yang mendeteksi anomali tidak langsung memblokir, melainkan menambahkan nilai numerik ke variabel skor:
    $$\text{Total Anomaly Score} = \sum_{i=1}^{k} \text{Score}(R_i)$$
  - Skor dikelompokkan ke dalam 4 kategori ancaman: *SQLi Score*, *XSS Score*, *RCE Score*, dan *Generic Anomaly Score*.
  - Di akhir fase `http_request_firewall_managed`, total skor dibandingkan dengan ambang batas (*Anomaly Threshold*) yang dikonfigurasi:
    - **Low**: Threshold 60 (Toleransi tinggi, false positive sangat rendah).
    - **Medium**: Threshold 40 (Rekomendasi default production enterprise).
    - **High**: Threshold 25 (Sangat ketat, cocok untuk web banking / checkout kritis).
  - Jika $\text{Total Score} \ge \text{Threshold}$, aksi akhir (*Block*, *Managed Challenge*, *Interactive Challenge*) dieksekusi.

---

## 4. Why & What

| Fitur / Dimensi | Cloudflare Managed Rulesets | OWASP Core Ruleset (CRS) | Custom WAF Rules |
| :--- | :--- | :--- | :--- |
| **Fokus Deteksi** | Eksploitasi CVE spesifik, zero-day aplikasi populer (Wordpress, Apache, Log4j, Struts). | Pola serangan generik berdasarkan tipe serangan (SQLi, XSS, RCE, LFI, SSRF). | Kebutuhan bisnis spesifik (Geo-fencing, IP whitelisting, URL path restriction, header validation). |
| **Metode Evaluasi** | Direct Match / Action Based (Pattern signature spesifik per CVE). | Anomaly Scoring System (Akumulasi skor berdasarkan ambang batas). | Boolean deterministic expression (True/False evaluation). |
| **Maintenance** | Dikelola otomatis oleh Cloudflare Threat Research Team. Divalidasi di edge global. | Standar komunitas global (dikelola Cloudflare dengan porting Rust engine). | Sepenuhnya dikelola oleh tim AppSec internal perusahaan. |
| **False Positive Rate** | Sangat Rendah (karena spesifik terhadap exploit payload). | Sedang hingga Tinggi (membutuhkan tuning berkala via overrides/exceptions). | Bergantung pada kualitas rule yang dibuat internal engineer. |
| **Action Flexibility** | Block, Challenge, JS Challenge, Log, Skip. | Block, Managed Challenge, Interactive Challenge, Log. | Block, Managed Challenge, Interactive Challenge, JS Challenge, Log, Bypass. |

---

## 5. How (Workflow Detail)

Untuk menerapkan Cloudflare WAF pada arsitektur produksi berskala besar tanpa mengakibatkan *service disruption*, pipeline mitigasi wajib mengikuti alur kerja berikut:

```
[Tahap 1: Ingestion & Baseline]
       │
       ▼
Deploy Ruleset pada mode action = "log"
       │
       ▼
Alirkan event log via Cloudflare Logpush ke SIEM (Datadog/Elastic/Splunk)
       │
       ▼
[Tahap 2: Analisis & Identifikasi False Positive]
       │
       ▼
Filter: edge_collo = "all" AND waf_action = "log"
Kalkulasi False Positive Rate (FPR) = (Valid User Flagged) / (Total Requests)
       │
       ├─► FPR > 0.01%? ──► Buat Dynamic WAF Exception / Override Rule Tag
       │                         │
       └◄────────────────────────┘
       │
       ▼
[Tahap 3: Progressive Enforcement]
       │
       ▼
Ubah action dari "log" menjadi "managed_challenge" (untuk menguji CAPTCHA transparan)
       │
       ▼
Pantau metrik "Challenge Solved Rate" dan drop-off user bisnis
       │
       ▼
Ubah action menjadi "block" untuk path kritis (misal: `/api/v1/payment/*`)
```

### Tahap Deployment Aman (Zero Downtime / Zero FP):
1. **Aturan Evaluasi Pre-Flight**: Managed Ruleset ditempatkan dalam mode `log`.
2. **Kueri Verifikasi di SIEM**: Ekstrak request yang memicu `http_request_firewall_managed` dengan regex false positive pada payload yang sah (misal: JSON request yang membawa tag Markdown atau query parameter yang mengandung tanda petik sah).
3. **Penyusunan Ruleset Overrides**: Konfigurasi `action = "skip"` atau nonaktifkan `rule_id` spesifik secara presisi tanpa mematikan seluruh engine Managed Ruleset.
4. **Hardening**: Naikkan Paranoia Level secara inkremental dari PL1 ke PL2 di OWASP Ruleset.

---

## 6. Analogy & Architecture Diagram

### Analogi Dunia Nyata: Sistem Pengamanan Bandara Internasional
- **Pingora Proxy**: Gerbang masuk bandara yang mengatur lalu lintas fisik jutaan penumpang.
- **Custom WAF Rules (Pemeriksaan Tiket Awal)**: Petugas di pintu terdepan yang memeriksa apakah Anda membawa paspor yang valid atau berasal dari negara yang masuk daftar hitam (Cepat, deterministik: ada tiket $\to$ masuk, tidak ada tiket $\to$ usir).
- **Cloudflare Managed Ruleset (Daftar Buronan Interpol / DPO)**: Anjing pelacak dan pemindai biometrik yang mengenali wajah teroris internasional (Mendeteksi tanda/sidik jari spesifik exploit CVE yang sudah diketahui di dunia).
- **OWASP Core Ruleset (X-Ray & Metal Detector dengan Sistem Poin Pelanggaran)**:
  - Bawa cairan > 100ml? +10 poin anomali.
  - Bawa gunting kuku? +15 poin anomali.
  - Bawa serbuk mencurigakan? +30 poin anomali.
  - Jika total akumulasi poin di atas batas toleransi bandara ($\ge 40$), Anda tidak langsung ditembak di tempat, melainkan diarahkan ke **Ruang Pemeriksaan Intensif (Managed Challenge)** atau **Ditolak Terbang (Block)**.

### Arsitektur Edge Pipeline
```
                    INTERNET (CLIENT REQUEST)
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│               CLOUDFLARE EDGE POP (Anycast BGP)              │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ Layer 3 / Layer 4 DDoS Mitigation (Magic Transit/L4)  │  │
│  └───────────────────────────┬───────────────────────────┘  │
│                              │ Clean L7 Stream               │
│                              ▼                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ HTTP Request Firewall Custom (Phase 1)                │  │
│  │ ├─ Rule 1: Block High Risk IP / Geolocation          │  │
│  │ └─ Rule 2: Skip Managed Rules if Internal API Token   │  │
│  └───────────────────────────┬───────────────────────────┘  │
│                              │ Evaluated / Continued         │
│                              ▼                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ HTTP Request Firewall Managed (Phase 2)               │  │
│  │ │                                                     │  │
│  │ ├─ Sub-phase A: Cloudflare Managed Ruleset            │  │
│  │ │   ├─ CVE-2021-44228 (Log4j RCE) ──► Block           │  │
│  │ │   └─ CVE-2023-22515 (Confluence) ──► Block          │  │
│  │ │                                                     │  │
│  │ └─ Sub-phase B: OWASP Core Ruleset                    │  │
│  │     ├─ Ruleset Evaluation (PL1 - PL4)                 │  │
│  │     ├─ Score Accumulator (SQLi, XSS, RCE, PHP, JAVA)  │  │
│  │     └─ Decision Gate: Anomaly Score >= 40?            │  │
│  │           ├─ TRUE  ──► Action: managed_challenge      │  │
│  │           └─ FALSE ──► Forward                        │  │
│  └───────────────────────────┬───────────────────────────┘  │
│                              │ Authenticated Traffic         │
│                              ▼                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ Origin Reverse Proxy (Pingora Engine)                 │  │
│  │ └─ Load Balancer, Argo Smart Routing, mTLS to Origin  │  │
│  └───────────────────────────┬───────────────────────────┘  │
└──────────────────────────────┼──────────────────────────────┘
                               │ Authenticated Tunnel / TLS
                               ▼
                      ENTERPRISE ORIGIN
                   (Kubernetes Ingress Pods)
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Deklarasi Custom WAF Rule (HCL)
Aturan sederhana untuk memblokir akses ke endpoint administrasi kecuali berasal dari Corporate VPN IP:

```hcl
resource "cloudflare_ruleset" "zone_custom_firewall" {
  zone_id     = var.cloudflare_zone_id
  name        = "Zone Custom Firewall Rules"
  description = "Custom rules for administrative path protection"
  kind        = "zone"
  phase       = "http_request_firewall_custom"

  rules {
    action      = "block"
    expression  = "(http.request.uri.path matches \"^/admin/.*\" and not ip.src in {198.51.100.0/24 203.0.113.50})"
    description = "Block unauthorized access to /admin/*"
    enabled     = true
  }
}
```

### 7.2. Practical Example: Production Managed Ruleset Implementation (HCL)
Konfigurasi komprehensif mengintegrasikan Cloudflare Managed Ruleset dan OWASP Ruleset dengan dynamic bypass, tag overrides, dan threshold scoring:

```hcl
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.20.0"
    }
  }
}

variable "cloudflare_zone_id" {
  type        = string
  description = "Target Zone ID"
}

# 1. Ruleset Entrypoint pada Phase: http_request_firewall_managed
resource "cloudflare_ruleset" "managed_waf_deployment" {
  zone_id     = var.cloudflare_zone_id
  name        = "Enterprise Managed WAF Deployment"
  description = "Production OWASP and Cloudflare Managed Rulesets with Overrides"
  kind        = "zone"
  phase       = "http_request_firewall_managed"

  # RULE 1: Global Skip Rule (Bypass WAF untuk Healthcheck internal & Webhook Partner terpercaya)
  rules {
    action = "skip"
    action_parameters {
      ruleset = "current"
    }
    expression  = "(http.request.uri.path eq \"/api/v1/health\" and ip.src in {100.64.0.0/16}) or (http.request.uri.path eq \"/webhooks/stripe\" and http.request.headers[\"stripe-signature\"][0] ne \"\")"
    description = "Bypass all managed rules for authorized internal health checks and Stripe Webhooks"
    enabled     = true
    logging {
      enabled = true
    }
  }

  # RULE 2: Cloudflare Managed Ruleset Execution with Overrides
  rules {
    action = "execute"
    action_parameters {
      # ID Cloudflare Managed Ruleset (Katalog Global Cloudflare)
      id = "efb79576da9d4d3c9038040d37375b0e"
      
      # Overrides untuk menonaktifkan specific rule yang menghasilkan FP pada payment payloads
      overrides {
        rules {
          id          = "922f8a4177d6480b91e9f1a0e5b7fb58" # Rule ID misal: Apache Struts OGNL validation
          action      = "log"                              # Ubah dari Block ke Log
          enabled     = true
        }

        # Override berdasarkan tag kategori
        categories {
          category = "wordpress"
          action   = "disabled" # Matikan kategori wordpress jika origin stack 100% Go/Rust API
        }
      }
    }
    expression  = "true" # Eksekusi untuk semua request yang lolos dari skip rules
    description = "Execute Cloudflare Managed Ruleset"
    enabled     = true
  }

  # RULE 3: Cloudflare OWASP Core Ruleset Execution
  rules {
    action = "execute"
    action_parameters {
      # ID Cloudflare OWASP Core Ruleset
      id = "4814384a9e5d4991ba98123d11c44c91"
      
      overrides {
        # Konfigurasi Anomaly Threshold & Paranoia Level
        rules {
          id          = "6179ae15870a4bb7b2d480d4843b323c" # OWASP Anomaly Evaluation Directive Rule
          action      = "managed_challenge"                # Tantang request jika melewati batas skor
          score_threshold = 40                             # Medium Sensitivity (Skor akumulasi >= 40)
        }

        # Overrides untuk menaikkan/menurunkan rule sensitif
        categories {
          category = "paranoia-level-3"
          enabled  = false # Nonaktifkan Paranoia Level 3 untuk menghindari false positive berlebih
        }
        categories {
          category = "paranoia-level-4"
          enabled  = false # Nonaktifkan Paranoia Level 4
        }
      }
    }
    expression  = "true"
    description = "Execute OWASP Core Ruleset with Anomaly Scoring"
    enabled     = true
  }
}
```

---

## 8. Real World Case Study: E-Commerce Mega Sale 11.11 Flash Attack

### Konteks & Skala
Platform e-commerce regional di Asia Tenggara mengoperasikan sistem checkout yang melayani **120.000 HTTP Requests Per Second (RPS)** saat puncak event Flash Sale 11.11.

### Insiden
Pada pukul 00:02 WIB, origin pod CPU utilization melonjak ke 100% pada kluster Kubernetes Payment Gateway. Tim SRE mendeteksi:
1. Serangan massal kombinasi SQL Injection berbasis sleep/time-delay (`pg_sleep(10)`) pada query parameter searching dan order catalog.
2. Eksploitasi zero-day deserialisasi JSON pada endpoint checkout `/api/v3/cart/checkout`.
3. Peningkatan False Positive di mana pengguna sah yang menggunakan checkout dengan alamat panjang (membawa karakter tanda petik ganda dan kutip tunggal) diblokir oleh WAF default ModSecurity lama.

### Solusi & Langkah Mitigasi

```
[Attacker Botnet] ──┐
                    ├─► [Anycast POP Edge] ──► [Wirefilter / Ruleset Engine]
[Legitimate Users] ─┘                                │
                                                     ├── Match SQLi Attack ──► Drop (403)
                                                     ├── Anomaly Score >= 40 ─► Managed Challenge
                                                     └── Legitimate Payload ──► Clean traffic to Origin
```

1. **Isolasi Cepat & Dynamic Skip Exception**:
   Tim SecOps membuat *WAF Skip Rule* untuk endpoint checkout spesifik, mengecualikan parameter `user_address` dari parsing OWASP CRS SQLi ruleset ID `942100`, dan memvalidasinya menggunakan regular expression yang ketat di Cloudflare Edge.
2. **Aktivasi Cloudflare Managed Emergency Ruleset**:
   Menerapkan zero-day patch CVE ruleset melalui Terraform secara terprogram via Cloudflare API v4.
3. **Penerapan Anomaly Scoring Threshold**:
   - OWASP Ruleset disetel pada:
     - `Paranoia Level`: 2
     - `Action Threshold`: 40 (Managed Challenge)
   - Pendekatan ini membuat bot otomatis terhenti pada tantangan managed challenge (interaksi JavaScript tanpa interupsi manusia), sedangkan pengguna sah tidak terputus karena browser mereka menyelesaikan tantangan secara transparan dalam rentang waktu < 200 milidetik.

### Hasil Metrik Produksi
- **Origin Request Reduction**: Volume request origin turun 38% (traffic berbahaya dipangkas langsung di edge).
- **Origin Latency (p99)**: Turun drastis dari 8.400ms menjadi 185ms.
- **False Positive Rate**: Menurun dari 2.1% menjadi 0.0004% selama jendela promosi 24 jam.

---

## 9. Trade-offs & Engineering Limits

| Parameter | Pendekatan Ringan (Permissive) | Pendekatan Ketat (Paranoid) | Dampak Rekayasa (Engineering Impact) |
| :--- | :--- | :--- | :--- |
| **OWASP Paranoia Level (PL)** | **PL1**: Pola dasar (SQLi/XSS standar). Regex singkat. | **PL3 - PL4**: Pengecekan karakter ASCII kontrol, deteksi nested quote, batas panjang argumen. | **Latency & CPU**: PL4 membutuhkan komputasi regex edge lebih tinggi (+0.5-2.0ms per request). Risiko false positive melonjak drastis pada payload payload modern (REST/GraphQL). |
| **Action: Block vs. Managed Challenge** | **Block**: Koneksi dihentikan seketika dengan respon HTTP 403. | **Managed Challenge**: Cloudflare menyajikan interstitial non-intrusif (Proof-of-Work / JS challenge). | **User Experience**: Block yang salah (*False Positive*) mengakibatkan hilangnya transaksi (Lost Revenue). Managed Challenge melindungi user sah yang terindikasi anomali ringan tanpa memutuskan sesi. |
| **Payload Inspection Size** | **128 KB** (Batas default Cloudflare Business/Enterprise standard). | **Batas Maksimum Tier Enterprise (hingga 500 MB)**. | **Coverage vs. Cost**: Cloudflare WAF hanya memindai byte pertama dari payload request (128KB pada paket standar, hingga 32MB+ pada Enterprise custom). Penyerang dapat melakukan *Payload Smuggling / Padding* (menaruh exploit di offset byte ke-130.000) jika limit tidak diperbesar. |
| **Regex: PCRE vs. RE2** | **PCRE (Perl Compatible Regular Expressions)**: Mendukung backreferences dan lookahead/lookbehind. | **RE2 (Deterministic Finite Automaton Engine)**: Linear time parsing $O(n)$, tidak mendukung backreference. | **Resilience**: PCRE rentan terhadap ReDoS (Regular Expression Denial of Service). Cloudflare Wirefilter membatasi syntax regex ke RE2 subsets demi stabilitas edge. |

---

## 10. Common Mistakes & Troubleshooting

### Mistake 1: Eksekusi Action "Block" Langsung pada OWASP Paranoia Level 2+ di Lingkungan Production
- **Dampak Fatal**: API Mobile dan frontend Single Page Application (SPA) sering mengirim payload Base64, encoded JSON, atau nested HTML entities. Mengaktifkan aksi `block` tanpa periode staging di mode `log` akan langsung melumpuhkan alur checkout atau login pengguna sah.
- **Remediasi**: Jalankan ruleset minimal 7 hari dengan action `log`. Kueri log Cloudflare untuk memetakan False Positive:
  ```sql
  SELECT 
    ClientRequestURI, 
    WAFRuleID, 
    WAFRuleMessage, 
    COUNT(*) as TriggerCount
  FROM cloudflare_waf_logs
  WHERE WAFAction = 'log'
  GROUP BY ClientRequestURI, WAFRuleID, WAFRuleMessage
  ORDER BY TriggerCount DESC;
  ```

### Mistake 2: Ruleset Execution Order Shadowing
- **Penyebab**: Menempatkan aturan pemblokiran umum di atas Skip Ruleset pada fase yang sama. Jika Rule A (Block suspicious User-Agent) ditempatkan sebelum Rule B (Skip WAF for Payment Partner), request webhook mitra yang memiliki User-Agent anomali akan terblokir sebelum aturan skip sempat dievaluasi.
- **Remediasi**: Desain Rule order secara disiplin: `Skip/Bypass Rules` selalu berada di indeks prioritas paling rendah (dieksekusi paling pertama) dalam satu fase ruleset engine.

### Panduan Debugging Menggunakan Trace Engine & cURL
Gunakan Cloudflare Trace API atau lakukan probing dengan payload buatan untuk memvalidasi respons edge:

```bash
# Uji apakah Managed Ruleset mendeteksi eksploitasi Path Traversal
curl -svo /dev/null \
  -H "Host: api.enterprise-target.com" \
  "https://api.enterprise-target.com/v1/download?file=../../../../etc/passwd" \
  --connect-to api.enterprise-target.com:443:104.16.123.96:443

# Verifikasi Response Headers:
# < HTTP/2 403
# < cf-mitigated: waf
# < cf-ray: 82071a9b2c8f0abc-SIN
```

Jika traffic terblokir secara misterius, periksa `CF-RAY` ID pada SIEM Logpush untuk mengekstrak field:
- `EdgePathingStatus`
- `WAFAction`
- `WAFFlags`
- `WAFRuleID`

---

## 11. Best Practices (Production Checklist)

### Fase Desain & Testing
- [ ] Tentukan baseline Paranoia Level (PL1 untuk legacy services, PL2 untuk secure RESTful API).
- [ ] Lakukan audit ukuran body payload: pastikan limit inspeksi WAF (128 KB s.d. 32 MB) mencakup ukuran rata-rata p99 request body aplikasi.
- [ ] Nonaktifkan kategori Managed Ruleset yang tidak relevan dengan teknologi origin stack (contoh: nonaktifkan aturan Drupal/Joomla/Wordpress jika stack backend menggunakan Spring Boot / Go).

### Deployment & Monitoring Pipeline
- [ ] Gunakan Terraform/OpenTofu untuk semua definisi ruleset; jangan pernah mengedit WAF rules langsung dari Cloudflare Dashboard UI di lingkungan Production.
- [ ] Atur Cloudflare Logpush pipeline menuju Object Storage (S3/GCS) atau SIEM dengan filter `Phase = "http_request_firewall_managed"`.
- [ ] Pastikan seluruh Ruleset baru di-deploy pertama kali dengan parameter `action = "log"` minimal $1 \times 168\text{ jam}$ (7 hari siklus traffic mingguan).
- [ ] Buat alert otomatis di SIEM jika `Managed Challenge Rate` melonjak $> 5\%$ dari total traffic normal dalam durasi 5 menit.

### Keamanan Berkelanjutan
- [ ] Aktifkan Cloudflare Automatic CVE Updates pada managed ruleset policies.
- [ ] Terapkan enkripsi end-to-end dengan Cloudflare Full (Strict) SSL/TLS bersama mTLS (Authenticated Origin Pulls) untuk memastikan penyerang tidak dapat melakukan bypass WAF dengan langsung menyerang Origin Public IP.

---

## 12. Hands-on Practice: Implementasi WAF Managed Engine Terotomasi

Praktikum ini akan membangun arsitektur pertahanan WAF menggunakan Terraform pada direktori lokal Anda.

### Struktur Direktori
```
hands-on/m02/
├── versions.tf
├── variables.tf
├── terraform.tfvars
├── main.tf
└── test_waf.sh
```

### File Configuration

#### `hands-on/m02/versions.tf`
```hcl
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.20.0"
    }
    http = {
      source  = "hashicorp/http"
      version = "~> 3.4.0"
    }
  }
}

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}
```

#### `hands-on/m02/variables.tf`
```hcl
variable "cloudflare_api_token" {
  type        = string
  sensitive   = true
  description = "Cloudflare API Token dengan izin Zone.Firewall Services"
}

variable "cloudflare_zone_id" {
  type        = string
  description = "Zone ID Cloudflare target"
}
```

#### `hands-on/m02/main.tf`
```hcl
# Ruleset Konfigurasi Terpusat: Managed + Custom Protection
resource "cloudflare_ruleset" "production_waf_stack" {
  zone_id     = var.cloudflare_zone_id
  name        = "Production Security Stack"
  description = "Managed Rulesets and Advanced Protections"
  kind        = "zone"
  phase       = "http_request_firewall_managed"

  # Rule 1: Skip Exception untuk Healthcheck Endpoint
  rules {
    action = "skip"
    action_parameters {
      ruleset = "current"
    }
    expression  = "(http.request.uri.path eq \"/healthz\")"
    description = "Exempt health checks from Managed WAF inspection"
    enabled     = true
  }

  # Rule 2: Cloudflare Managed Ruleset dengan Safe Deployment Mode (Log-only override)
  rules {
    action = "execute"
    action_parameters {
      id = "efb79576da9d4d3c9038040d37375b0e"
      overrides {
        # Mengubah action default menjadi log untuk proses staging awal
        action = "log"
      }
    }
    expression  = "true"
    description = "Execute Cloudflare Managed Ruleset in Audit/Log Mode"
    enabled     = true
  }

  # Rule 3: OWASP Core Ruleset dengan Anomaly Scoring
  rules {
    action = "execute"
    action_parameters {
      id = "4814384a9e5d4991ba98123d11c44c91"
      overrides {
        rules {
          id              = "6179ae15870a4bb7b2d480d4843b323c"
          action          = "managed_challenge"
          score_threshold = 60 # Set awal: Low sensitivity threshold
        }
      }
    }
    expression  = "true"
    description = "Execute OWASP CRS with Score Evaluation"
    enabled     = true
  }
}
```

#### `hands-on/m02/test_waf.sh`
```bash
#!/usr/bin/env bash
set -euo pipefail

TARGET_DOMAIN="example.com" # Ganti dengan domain yang terpasang pada Cloudflare Zone
ORIGIN_EDGE_IP=""           # Isi jika ingin bypass DNS resolution via --connect-to

echo "=== MEMULAI TEST SIMULASI SERANGAN WAF ==="

# 1. Test Clean Traffic (Harus HTTP 200 / Tidak Terblokir)
echo -n "[TEST 1] Legitimate Request: "
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "https://${TARGET_DOMAIN}/")
echo "HTTP Status: ${HTTP_CODE}"

# 2. Test Path Traversal Protection
echo -n "[TEST 2] LFI / Path Traversal Attack: "
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "https://${TARGET_DOMAIN}/?file=../../../../etc/shadow")
echo "HTTP Status: ${HTTP_CODE} (Expected 403 jika enforce, atau 200 jika Log mode)"

# 3. Test SQL Injection Attack Vector
echo -n "[TEST 3] OWASP Anomaly SQLi Attack: "
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "https://${TARGET_DOMAIN}/search" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "query=' UNION SELECT 1,username,password_hash FROM users WHERE '1'='1")
echo "HTTP Status: ${HTTP_CODE} (Logged / Mitigated)"

# 4. Test Healthcheck Bypass Rule
echo -n "[TEST 4] Bypass Healthcheck URL: "
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "https://${TARGET_DOMAIN}/healthz?payload=<script>alert(1)</script>")
echo "HTTP Status: ${HTTP_CODE} (Bypassed Managed Ruleset)"

echo "=== TEST SELESAI ==="
```

---

## 13. Exercises

### Level 1 - Easy
Tuliskan single Cloudflare expression (Wirefilter syntax) untuk memblokir seluruh traffic HTTP POST ke path `/api/v1/auth/login` yang **tidak** menyertakan custom header `X-Requested-With: XMLHttpRequest` dan bukan berasal dari ASN Cloudflare (ASN 13335).

### Level 2 - Medium
Gunakan Terraform untuk mendeklarasikan Rule pada `http_request_firewall_custom` yang melakukan `managed_challenge` terhadap request dengan kondisi:
- URI path dimulai dengan `/api/checkout/`
- Request method bernilai `POST` atau `PUT`
- Skor reputasi ancaman Cloudflare (`cf.threat_score`) lebih tinggi dari nilai `15`.

### Level 3 - Hard
Sebuah API service menerima payload JSON berukuran besar pada endpoint `/api/v2/bulk-import`. 
Buat arsitektur konfigurasi Ruleset Engine (Terraform) yang:
1. Menonaktifkan Rule OWASP SQLi spesifik (`id: 942100`) **hanya** untuk endpoint tersebut dan **hanya** jika request menyertakan valid Bearer Token format pada `Authorization` header.
2. Tetap memvalidasi semua rule OWASP Remote Code Execution (RCE) dan Command Injection pada endpoint yang sama dengan Anomaly Score Threshold bernilai ketat (`25`).

---

## 14. Real-World Challenges (Production Scenarios)

### Kasus: Zero-Day RCE Attack pada Java Spring Boot Service
**Deskripsi Masalah**:
Perusahaan perbankan tier-1 mengalami ancaman kerentanan zero-day kritis (Spring Framework RCE). Penyerang mengeksploitasi serialization parameter melalui header HTTP `class.module.classLoader` atau payload URL-encoded.
Aplikasi backend utama tidak bisa di-*patch* atau di-*restart* dalam 48 jam ke depan tanpa *downtime window* resmi regulator.

**Batasan & Tantangan Teknis**:
1. Lalu lintas legitimasinya mencapai 80.000 RPS, dengan 15% traffic membawa body multipart/form-data untuk upload dokumen nasabah.
2. Penyerang menyamarkan serangan dengan teknik encoding bertingkat (*Double URL Encoding* dan *Base64 nesting*).
3. Anda tidak diperbolehkan memblokir seluruh HTTP POST method.
4. Anda harus merancang:
   - Aturan deteksi custom (Wirefilter expression) dengan kalkulasi resource time-complexity terendah.
   - Pemanfaatan decoder function bawaan Cloudflare Ruleset Engine (`decode.url()`, `decode.base64()`).
   - Mekanisme mitigasi otomatis jika IP attacker mendistribusikan payload melalui jaringan proxy residential (rotasi ribuan IP per menit).
   - Validasi bahwa latensi tambahan (overhead TTFB) p95 tidak bertambah $> 2.0\text{ ms}$.

Rancang spesifikasi arsitektur konfigurasi, urutan tahapan evaluasi engine, aturan mitigasi darurat, dan prosedur verifikasi post-deployment tanpa menimbulkan *downtime* atau *false positive* pada berkas nasabah yang valid.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Dasar (Basic)
1. **Engine baru yang menggantikan ModSecurity engine di Cloudflare dan ditulis dalam bahasa Rust adalah?**
   - A. V8 Isolate Engine
   - B. Rust Wirefilter / Ruleset Engine
   - C. Nginx Lua Engine
   - D. Envoy C++ Core Filter
   - *Kunci Jawaban: B* — Cloudflare mengganti ModSecurity engine berbasis C/Lua dengan Ruleset Engine generasi baru yang ditenagai oleh library Wirefilter berbasis Rust.

2. **Fase ruleset manakah yang dieksekusi lebih dahulu pada arsitektur pipeline Cloudflare WAF?**
   - A. `http_request_firewall_managed`
   - B. `http_response_firewall_managed`
   - C. `http_request_firewall_custom`
   - D. `http_ratelimit`
   - *Kunci Jawaban: D* — Pipeline memproses `http_ratelimit` terlebih dahulu, disusul oleh `http_request_firewall_custom`, lalu `http_request_firewall_managed`.

3. **Berapa ambang batas default inspeksi body request (payload size limit) untuk zona Cloudflare Business standard sebelum payload terpotong?**
   - A. 64 KB
   - B. 128 KB
   - C. 1 MB
   - D. 10 MB
   - *Kunci Jawaban: B* — Default payload size limit untuk inspeksi WAF standar adalah 128 KB. Request body di atas ukuran tersebut akan dilewatkan tanpa inspeksi (uninspected tail) kecuali limit ditingkatkan pada tier Enterprise.

4. **Pada OWASP Core Ruleset, jika satu rule mendeteksi indikasi serangan SQL Injection, apa yang terjadi secara default pada mode Anomaly Scoring?**
   - A. Request seketika di-drop dengan response connection reset.
   - B. IP penyerang dimasukkan ke daftar blackhole selama 24 jam.
   - C. Rule menambahkan nilai skor ke total SQLi anomaly score tanpa menghentikan inspeksi seketika.
   - D. Cloudflare mengirim alert webhook ke origin server.
   - *Kunci Jawaban: C* — Sistem anomaly scoring bersifat kolaboratif; rule menaikkan counter score dan evaluasi dilanjutkan hingga seluruh rule selesai diuji sebelum tindakan mitigasi diputuskan.

5. **Apa fungsi aksi `managed_challenge` pada Cloudflare WAF?**
   - A. Menolak request secara permanen dengan kode HTTP 401 Unauthorized.
   - B. Memaksa client menyelesaikan teka-teki interaktif CAPTCHA visual berbasis gambar setiap saat.
   - C. Menyajikan tantangan keamanan adaptif (JavaScript Proof-of-Work, browser fingerprinting) yang transparan bagi manusia dan memblokir bot otomatis.
   - D. Mengarahkan request ke honeypot sandbox origin.
   - *Kunci Jawaban: C* — Managed challenge mengevaluasi risiko browser dan hanya menyajikan interaksi interaktif jika browser terindikasi kuat sebagai bot mencurigakan.

---

### Bagian B: Menengah (Intermediate)
6. **Manakah ekspresi Wirefilter yang paling efisien dari segi penggunaan memori edge untuk mencocokkan path direktori `/api/` tanpa memicu regex engine?**
   - A. `http.request.uri.path matches "^/api/.*"`
   - B. `http.request.uri.path contains "/api/"`
   - C. `starts_with(http.request.uri.path, "/api/")`
   - D. `http.request.uri.path wildcard "/api/*"`
   - *Kunci Jawaban: C* — Fungsi `starts_with()` dikompilasi langsung menjadi instruksi perbandingan byte array prefix berkecepatan tinggi tanpa inisialisasi DFA/NFA regex state machine.

7. **Ketika melakukan bypass Managed Ruleset untuk third-party webhook terpercaya menggunakan skip action, parameter apa yang wajib didefinisikan dalam `action_parameters`?**
   - A. `bypass = true`
   - B. `ruleset = "current"`
   - C. `override = "disable"`
   - D. `action = "allow"`
   - *Kunci Jawaban: B* — Pada fase Ruleset Engine v4, melewatkan aturan diatur dengan `action = "skip"` dan parameter `ruleset = "current"` (atau `ruleset = "<ruleset_id>"`).

8. **Mengapa penggunaan PCRE regex dengan nested quantifier (misal: `(a+)+$`) dilarang pada engine Cloudflare Wirefilter?**
   - A. Rust tidak mendukung representasi tipe string ASCII.
   - B. Menghindari Catastrophic Backtracking ($O(2^n)$) yang dapat membekukan worker thread Pingora edge proxy (ReDoS).
   - C. Memori cache edge tidak dapat menyimpan string lebih dari 256 karakter.
   - D. Menyebabkan response SSL handshake handshake_failure.
   - *Kunci Jawaban: B* — Engine Cloudflare menghindari regex backtracking untuk menjamin parsing payload linear $O(n)$ sehingga edge proxy terlindungi dari eksploitasi ReDoS.

9. **Jika Cloudflare OWASP Core Ruleset disetel pada Paranoia Level 4 (PL4), risiko terbesar yang dihadapi sistem backend modern berbasis REST API adalah:**
   - A. Memory leak pada Pingora proxy.
   - B. Response time origin menurun hingga 0 ms.
   - C. Lonjakan False Positive tinggi karena karakter payload umum (seperti JSON quotes, hyphen, format email) memicu aturan deteksi ketat.
   - D. Cloudflare Logpush berhenti mengirim data.
   - *Kunci Jawaban: C* — Paranoia Level 4 mengecek struktur input yang sangat restriktif (bahkan melarang karakter tertentu di header dan payload), sehingga hampir pasti menimbulkan false positive tinggi pada payload JSON/REST kompleks.

10. **Bagaimana cara mengubah aksi dari sebuah specific Rule ID pada Managed Ruleset tanpa menonaktifkan ruleset tersebut secara global?**
    - A. Menghapus zone dari Cloudflare dan mendaftarkannya kembali.
    - B. Menggunakan blok `overrides` pada deklarasi execution ruleset, menentukan `rules.id`, lalu mengubah properti `action` menjadi `log` atau `disabled`.
    - C. Mengubah Page Rules legacy menjadi forward URL.
    - D. Menambahkan DNS TXT record `cf-waf-override`.
    - *Kunci Jawaban: B* — Objek `overrides` di dalam deklarasi eksekusi ruleset memungkinkan penyesuaian granular (fine-tuning) terhadap specific rule ID atau category tanpa mempengaruhi rule lainnya.

---

### Bagian C: Skenario Kasus Produksi (Production Scenarios)

#### Skenario 1
Tim keamanan perusahaan Anda mendapati bahwa penyerang mencoba menyelundupkan SQL Injection pada parameter body JSON yang di-encode secara Base64 bertingkat:
`{"data": "JyBPUiAnMSc9JzE="}` (di mana string tersebut bernilai `' OR '1'='1`).
Managed Ruleset standar gagal mendeteksinya karena body JSON dianggap sebagai string biasa.

*Tindakan arsitektural apa yang paling tepat untuk memitigasi serangan ini pada Cloudflare Edge sebelum mencapai Origin?*
- A. Mengaktifkan Paranoia Level 4 di OWASP Ruleset.
- B. Menulis Custom WAF Rule yang menerapkan fungsi decoding: `lookup_json_string(http.request.body.raw, "data") | decode.base64() contains "' OR '1'='1'"` dan melakukan aksi `block`.
- C. Mengonfigurasi Origin Server untuk menolak semua content type `application/json`.
- D. Mengubah mode SSL Cloudflare menjadi Flexible.
- *Kunci Jawaban: B* — Pendekatan presisi adalah memanfaatkan native function payload decoding (`decode.base64`) pada field JSON spesifik di fase Custom WAF sebelum payload menyentuh origin server.

#### Skenario 2
Setelah mengaktifkan OWASP Managed Ruleset pada level Paranoia Level 2 dengan threshold Anomaly Score = 40 (Action: Block), pengguna setia melaporkan gagal mengunggah dokumen formulir pendaftaran. Hasil penelusuran menunjukkan request tersebut memiliki Anomaly Score = 45 yang terakumulasi dari Rule 942100 (SQLi), 930100 (LFI), dan 920100 (Protocol Violation).

*Langkah mitigasi mana yang mengikuti prinsip keamanan zero trust dan meminimalkan resiko bisnis?*
- A. Menurunkan Paranoia Level global menjadi PL1 dan menaikkan threshold ke 100 untuk seluruh domain.
- B. Mematikan WAF Managed Ruleset secara keseluruhan.
- C. Membuat scoped skip rule atau action override yang mengubah aksi menjadi `managed_challenge` secara spesifik hanya pada URI path `/api/registration/upload`, sembari mempertahankan evaluasi `block` pada rute lainnya.
- D. Menambahkan IP address seluruh pengguna yang komplain ke IP Access List Whitelist.
- *Kunci Jawaban: C* — Memberikan pengecualian presisi (scoped override) berdasarkan URI path menjaga integritas postur keamanan domain secara luas, sembari mengubah aksi memblokir menjadi managed challenge guna memfasilitasi pengguna sah tanpa mengorbankan keamanan.

#### Skenario 3
Sistem e-ticketing bersiap menghadapi event flash sale. Tim DevOps ingin memastikan tidak ada downtime atau lonjakan latensi akibat WAF saat trafik naik dari 2.000 RPS ke 150.000 RPS dalam 30 detik.

*Strategi engineering apa yang paling kritikal dilakukan pada level Cloudflare Ruleset?*
- A. Mengganti semua Custom Rule ekspresi regex berbasis PCRE dengan instruksi set deterministik (`in`, `starts_with`, `eq`), meletakkan Bypass/Skip rule pada urutan prioritas teratas, serta memastikan endpoint statis/aset gambar di-bypass dari fase managed firewall.
- B. Mengaktifkan seluruh ruleset yang ada di dashboard Cloudflare untuk pertahanan maksimal.
- C. Menghapus konfigurasi Terraform dan mengelolanya manual via console web.
- D. Mengubah seluruh SSL/TLS cipher suite ke 3DES.
- *Kunci Jawaban: A* — Pada beban ekstrem (150k RPS), komputasi filter harus linear $O(1)$ atau $O(n)$ menggunakan byte matching murni. Mengecualikan static assets (gambar/font) dan mengeksekusi bypass rule terlebih dahulu mengeliminasi CPU cycle edge yang tidak perlu, mencegah latensi tinggi pada pipeline edge.

---

## 16. Summary

1. **Rust Engine Architecture**: Cloudflare Ruleset Engine mengeksekusi packet processing di edge menggunakan arsitektur memory-safe Rust Wirefilter, menggantikan engine ModSecurity legacy untuk menjamin linear-time evaluation $O(n)$ dan proteksi dari ReDoS.
2. **Phase Execution Pipeline**: Urutan fase bersifat deterministik: normalisasi traffic $\to$ Rate Limiting $\to$ Custom Rules (`http_request_firewall_custom`) $\to$ Managed Rules (`http_request_firewall_managed`). Aksi skip/bypass harus dieksekusi sedini mungkin untuk meminimalisir overhead.
3. **Collaborative Anomaly Scoring**: Cloudflare OWASP CRS tidak melakukan pemblokiran instan melainkan mengakumulasi skor pelanggaran lintas kategori serangan (SQLi, XSS, RCE) dan mengevaluasinya terhadap sensitivitas threshold (Low: 60, Medium: 40, High: 25).
4. **Staging & Iteration Workflow**: Seluruh perubahan Managed Ruleset dan Paranoia Level wajib melalui fase staging dengan aksi `log` sebelum beralih ke `managed_challenge` atau `block`, dengan pemantauan metrik secara terpusat melalui Logpush dan SIEM.
5. **Infrastructure as Code**: Konfigurasi keamanan skala enterprise wajib dikelola menggunakan Terraform/OpenTofu (`cloudflare_ruleset`), menerapkan override granular berbasis rule ID atau tag guna mencegah konfigurasi menyimpang (*configuration drift*).