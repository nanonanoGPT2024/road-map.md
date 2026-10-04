```markdown
# AI Red Teaming: Enterprise Offensive Security for Machine Learning & Generative Systems

[![Standard: GEMINI](https://img.shields.io/badge/Standard-GEMINI-0A84FF?style=flat-square)](https://github.com/)
[![Track: AI Security](https://img.shields.io/badge/Track-AI--Red--Teaming-FF3B30?style=flat-square)](https://roadmap.sh/ai-red-teaming)
[![Target: L6/L7 Security Architect](https://img.shields.io/badge/Target-Senior%20Staff%20Security%20Engineer-34C759?style=flat-square)](https://github.com/)

---

## 1. Course Overview & Adversarial Mindset

Perkembangan pesat adopsi Machine Learning (ML), Large Language Models (LLM), Multimodal Systems, dan Autonomous Agents ke dalam infrastruktur produksi enterprise membuka vektor serangan baru yang tidak dapat dimitigasi hanya dengan perimeter security tradisional (seperti WAF, EDR, atau SAST/DAST konvensional). **AI Red Teaming** adalah disiplin terstruktur untuk mengidentifikasi, mengeksploitasi, dan merekayasa balik kerentanan inheren pada sistem berbasis AI, mencakup aspek *stochastic behavior*, kelemahan arsitektur tensor, *semantic manipulation*, dan eksfiltrasi memori terdistribusi.

### The Adversarial AI Mindset
1. **Model Bukanlah Kotak Hitam Kebal (Deterministic Code vs Stochastic Inference):** Model machine learning membuat inferensi probabilistik berdasarkan manifold data berdimensi tinggi. Setiap celah manifold representasi adalah potensi serangan ekuivalen zero-day.
2. **Data adalah Kode Baru (Code-Data Equivalence):** Pada LLM dan RAG, batasan antara instruksi (*control plane*) dan data pengguna (*data plane*) sangat kabur. *Prompt injection* dan *indirect poisoning* adalah bentuk modern dari *buffer overflow* dan *SQL injection*.
3. **Defense-in-Depth AI:** Red Teaming AI menguji seluruh siklus hidup ML: pengadaan dataset, pipeline pelatihan/fine-tuning, penyimpanan bobot (model registry), layer orkestrasi inferensi, sistem guardrail, hingga eksekusi aksi otonom (*tool execution*).

Kurikulum ini mengintegrasikan standar keamanan global seperti **MITRE ATLAS (Adversarial Threat Landscape for Artificial-Intelligence Systems)**, **OWASP Top 10 for LLM Applications**, dan **NIST AI Risk Management Framework (AI RMF)**, mempersiapkan Senior Security Engineer dan AI Architect untuk memimpin simulasi ancaman mutakhir (*adversarial simulations*) di level enterprise.

---

## 2. Learning Roadmap

```plaintext
AI RED TEAMING CURRICULUM
│
├── [Bab 01] Foundations of AI Red Teaming & Threat Modeling
│   ├── Modul 01: Traditional vs AI Red Teaming Paradigms
│   ├── Modul 02: MITRE ATLAS, OWASP LLM Top 10 & NIST AI RMF
│   └── Modul 03: Adversarial Threat Modeling for ML Pipelines
│
├── [Bab 02] Prompt Injection & Advanced Jailbreaking Techniques
│   ├── Modul 01: Direct & Indirect Prompt Injections
│   ├── Modul 02: Universal Jailbreak Vectors & Adversarial Suffixes (GCG)
│   └── Modul 03: Multilingual, Cipher-based & Many-Shot Jailbreaking
│
├── [Bab 03] Evasion & Multimodal Adversarial Perturbations
│   ├── Modul 01: Gradient-based Evasion Attacks (FGSM, PGD, CW)
│   ├── Modul 02: Multimodal Jailbreak (Vision-Language & Audio Injection)
│   └── Modul 03: Typographic & Physical-World Adversarial Artifacts
│
├── [Bab 04] Data Extraction, Privacy & Model Inversion Attacks
│   ├── Modul 01: Memorization & Training Data Extraction
│   ├── Modul 02: Membership Inference Attacks (MIA) & Shadow Models
│   └── Modul 03: Model Inversion & Sensitive PII Reconstruction
│
├── [Bab 05] Data Poisoning & Supply Chain Backdoors
│   ├── Modul 01: Clean-Label & Targeted Poisoning on Fine-Tuning
│   ├── Modul 02: Neural Trojans & Trigger-based Backdoors
│   └── Modul 03: Model Supply Chain & Pickled Weights Exploitation
│
├── [Bab 06] Model Theft, Extraction & Intellectual Property Inversion
│   ├── Modul 01: Functional Model Stealing & Black-Box Extraction
│   ├── Modul 02: Hyperparameter & Architecture Inference via Side-Channels
│   └── Modul 03: Watermark Evasion & Model Distillation Exploitation
│
├── [Bab 07] Red Teaming Autonomous Agents & Tool-Use Systems
│   ├── Modul 01: Agentic Hijacking & Tool-Augmented Indirect Injections
│   ├── Modul 02: ReAct Loop Exploitation & Infinite Execution Bombs
│   └── Modul 03: Privilege Escalation via Function Calling & MCP
│
├── [Bab 08] RAG Exploitation & Knowledge Base Poisoning
│   ├── Modul 01: Vector Store & Context Poisoning Attacks
│   ├── Modul 02: Embedding Collision & Semantic Hijacking
│   └── Modul 03: Exfiltration of Private Enterprise Knowledge via RAG
│
├── [Bab 09] Automated AI Red Teaming & Attack Orchestration
│   ├── Modul 01: Offensive Tooling Ecosystem (Garak, PyRIT, Promptfoo)
│   ├── Modul 02: LLM-as-a-Judge for Automated Exploitation Loops
│   └── Modul 03: Continuous AI Red Teaming in CI/CD DevSecOps
│
└── [Bab 10] Guardrail Auditing, Evasion & Enterprise Remediation
    ├── Modul 01: Auditing Guardrails (Llama Guard, NeMo, Content Filters)
    ├── Modul 02: Semantic Bypassing & Latent Space Obfuscation
    └── Modul 03: Hardening, Defensive Steering & Executive Reporting
```

---

## 3. Navigasi Detail Modul (Bab 01 – Bab 10)

### [Bab 01: Foundations of AI Red Teaming & Threat Modeling](01-foundations-threat-modeling/)
Fondasi teori, terminologi serang, dan framework formal audit AI.
* [Modul 01: Traditional vs AI Red Teaming Paradigms](01-foundations-threat-modeling/01-traditional-vs-ai-red-teaming.md) – Perbandingan attack surface software konvensional vs sistem ML nondeterministik.
* [Modul 02: MITRE ATLAS, OWASP LLM Top 10 & NIST AI RMF](01-foundations-threat-modeling/02-frameworks-atlas-owasp-nist.md) – Taksonomi ancaman, taktik, teknik, dan prosedur (TTP) standar industri.
* [Modul 03: Adversarial Threat Modeling for ML Pipelines](01-foundations-threat-modeling/03-threat-modeling-ml-pipelines.md) – Penyusunan Threat Matrix terstruktur pada data pipeline, model registry, dan inference serving API.

### [Bab 02: Prompt Injection & Advanced Jailbreaking Techniques](02-prompt-injection-jailbreaks/)
Eksploitasi semantik dan manipulasi instruksi tingkat lanjut pada model berbasis teks.
* [Modul 01: Direct & Indirect Prompt Injections](02-prompt-injection-jailbreaks/01-direct-indirect-injections.md) – Teknik pemisahan instruksi-payload, second-order injections, dan data delimiter breakout.
* [Modul 02: Universal Jailbreak Vectors & Adversarial Suffixes (GCG)](02-prompt-injection-jailbreaks/02-universal-jailbreaks-gcg.md) – Algoritma Greedy Coordinate Gradient (GCG), token optimisasi otomatis, dan roleplay adversarial.
* [Modul 03: Multilingual, Cipher-based & Many-Shot Jailbreaking](02-prompt-injection-jailbreaks/03-multilingual-cipher-manyshot.md) – Cross-lingual exploitation, Base64/Rot13/Pig-Latin bypass, dan long-context window abuse (Many-Shot).

### [Bab 03: Evasion & Multimodal Adversarial Perturbations](03-evasion-multimodal-attacks/)
Manipulasi tensor matematis dan serangan lintas modalitas (Vision-Language Models & Audio).
* [Modul 01: Gradient-based Evasion Attacks (FGSM, PGD, CW)](03-evasion-multimodal-attacks/01-gradient-evasion-fgsm-pgd.md) – Eksploitasi gradient loss function melalui Fast Gradient Sign Method, Projected Gradient Descent, dan Carlini-Wagner attacks.
* [Modul 02: Multimodal Jailbreak (Vision-Language & Audio Injection)](03-evasion-multimodal-attacks/02-multimodal-jailbreaks.md) – Embed prompt injeksi ke dalam noise visual gambar (VLM) dan steganografi audio model.
* [Modul 03: Typographic & Physical-World Adversarial Artifacts](03-evasion-multimodal-attacks/03-typographic-physical-attacks.md) – Patch adversarial, typographic attacks pada visual tokenizers, dan manipulasi fisik OCR/Object Detectors.

### [Bab 04: Data Extraction, Privacy & Model Inversion Attacks](04-data-extraction-privacy/)
Eksfiltrasi data sensitif dari memorisasi bobot dan rekonstruksi data training.
* [Modul 01: Memorization & Training Data Extraction](04-data-extraction-privacy/01-memorization-extraction.md) – Divergence attacks, output repetition exploitation, dan extraction scoring via perplexity analysis.
* [Modul 02: Membership Inference Attacks (MIA) & Shadow Models](04-data-extraction-privacy/02-membership-inference-mia.md) – Deteksi data sampel training menggunakan Shadow Models dan threshold prediction confidence.
* [Modul 03: Model Inversion & Sensitive PII Reconstruction](04-data-extraction-privacy/03-model-inversion-pii.md) – Rekonstruksi wajah/identitas dari target model classifications dan eksfiltrasi PII via prompt probing.

### [Bab 05: Data Poisoning & Supply Chain Backdoors](05-poisoning-supply-chain/)
Kompromi integritas dataset, transfer learning, dan artefak bobot model.
* [Modul 01: Clean-Label & Targeted Poisoning on Fine-Tuning](05-poisoning-supply-chain/01-clean-label-poisoning.md) – Injeksi sampel manipulasi laten tanpa merusak ground-truth label untuk memicu misklasifikasi spesifik.
* [Modul 02: Neural Trojans & Trigger-based Backdoors](05-poisoning-supply-chain/02-neural-trojans-triggers.md) – Pemasangan aktivasi trigger laten pada token/pixel yang menginstruksikan model mengeksekusi payload rahasia.
* [Modul 03: Model Supply Chain & Pickled Weights Exploitation](05-poisoning-supply-chain/03-supply-chain-pickle-deserialization.md) – Remote Code Execution (RCE) via PyTorch/Pickle deserialization, backdoored SafeTensors, dan Hugging Face hub spoofing.

### [Bab 06: Model Theft, Extraction & Intellectual Property Inversion](06-model-theft-extraction/)
Pencurian intellectual property (IP), fungsionalitas model, dan evasion deteksi plagiasi.
* [Modul 01: Functional Model Stealing & Black-Box Extraction](06-model-theft-extraction/01-black-box-stealing.md) – Kloning fungsionalitas model komersial via active learning querying dan API scraping.
* [Modul 02: Hyperparameter & Architecture Inference via Side-Channels](06-model-theft-extraction/02-hyperparameter-architecture-inference.md) – Penentuan kedalaman model, dimensi embedding, dan ukuran vocabulary via timing attacks dan token probability distributions.
* [Modul 03: Watermark Evasion & Model Distillation Exploitation](06-model-theft-extraction/03-watermark-evasion-distillation.md) – Penghapusan cryptographic watermarking pada model outputs dan teknik distilasi tanpa trace forensik.

### [Bab 07: Red Teaming Autonomous Agents & Tool-Use Systems](07-autonomous-agents-exploitation/)
Eksploitasi sistem otonom ReAct, Function Calling, dan integrasi API perantara.
* [Modul 01: Agentic Hijacking & Tool-Augmented Indirect Injections](07-autonomous-agents-exploitation/01-agentic-hijacking.md) – Memaksa agent mengeksekusi aksi unauthorized (SQL queries, API calls, file writes) via input yang tidak tepercaya.
* [Modul 02: ReAct Loop Exploitation & Infinite Execution Bombs](07-autonomous-agents-exploitation/02-react-loop-denial-of-service.md) – Serangan Denial of Wallet/Service dengan memancing recursive loop, context exhaust, dan hallucinated reasoning steps.
* [Modul 03: Privilege Escalation via Function Calling & MCP](07-autonomous-agents-exploitation/03-function-calling-privilege-escalation.md) – Eksploitasi schema definition, Model Context Protocol (MCP), dan bypassing konfirmasi manusia (*Human-in-the-Loop*).

### [Bab 08: RAG Exploitation & Knowledge Base Poisoning](08-rag-exploitation/)
Penetrasi pada ekosistem Retrieval-Augmented Generation dan database vektor.
* [Modul 01: Vector Store & Context Poisoning Attacks](08-rag-exploitation/01-vector-store-poisoning.md) – Injeksi dokumen berbahaya ke dalam corpus index untuk mengontrol konten konteks retrieval LLM.
* [Modul 02: Embedding Collision & Semantic Hijacking](08-rag-exploitation/02-embedding-collision-hijacking.md) – Perancangan teks berlawanan yang menghasilkan vector proximity tinggi terhadap query target (Cos-Sim hijacking).
* [Modul 03: Exfiltration of Private Enterprise Knowledge via RAG](08-rag-exploitation/03-rag-data-exfiltration.md) – Structured prompt leaks untuk merilis unauthorized document chunks yang diproteksi oleh ACL internal.

### [Bab 09: Automated AI Red Teaming & Attack Orchestration](09-automated-red-teaming-orchestration/)
Scale-up operasi red team menggunakan framework otomatis dan pipeline offensive CI/CD.
* [Modul 01: Offensive Tooling Ecosystem (Garak, PyRIT, Promptfoo)](09-automated-red-teaming-orchestration/01-garak-pyrit-promptfoo.md) – Setup, konfigurasi custom probe, dan eksekusi automated vulnerability scanning pada LLM endpoints.
* [Modul 02: LLM-as-a-Judge for Automated Exploitation Loops](09-automated-red-teaming-orchestration/02-llm-as-a-judge-attacker.md) – Merancang loop serang otomatis adaptif: Attacker Model -> Target Endpoint -> Evaluator Model -> Prompt Mutator.
* [Modul 03: Continuous AI Red Teaming in CI/CD DevSecOps](09-automated-red-teaming-orchestration/03-continuous-ai-red-teaming.md) – Integrasi gate test keamanan model ke GitHub Actions/GitLab CI untuk memblokir deployment model regresi.

### [Bab 10: Guardrail Auditing, Evasion & Enterprise Remediation](10-guardrail-auditing-remediation/)
Validasi efektivitas pertahanan, teknik bypass lanjutan, serta mitigasi berbasis arsitektur.
* [Modul 01: Auditing Guardrails (Llama Guard, NeMo, Content Filters)](10-guardrail-auditing-remediation/01-auditing-guardrails.md) – Audit efektivitas input/output filters, semantic classifiers, dan rule-based safety layers.
* [Modul 02: Semantic Bypassing & Latent Space Obfuscation](10-guardrail-auditing-remediation/02-semantic-bypassing-obfuscation.md) – Teknik obfuscation bahasa, character substitution, leetspeak, dan context diluting untuk bypass modern guardrails.
* [Modul 03: Hardening, Defensive Steering & Executive Reporting](10-guardrail-auditing-remediation/03-hardening-mitigation-reporting.md) – Teknik Activation Addition/Representation Steering, System Prompt Hardening, dan format laporan audit teknis standar C-Level/Auditor.

---

## 4. Enterprise Capstone Project

### Judul Proyek:
**"End-to-End Adversarial Assessment & Red Teaming Report on OmniCore Enterprise Autonomous Financial Banking Agent"**

### Arsitektur Target Evaluasi:
Sistem yang diuji adalah simulasi core platform perbankan otonom:
* **LLM Engine:** Multi-turn conversational model (gaya Llama 3 / GPT-4o) dengan system prompt restriktif.
* **Retrieval Pipeline:** Enterprise RAG (Chroma/Qdrant + text-embedding-ada-002) yang mengindeks data regulasi internal bank & data nasabah terisolasi.
* **Agent Execution:** Tool-use framework (ReAct/Function Calling) terhubung ke:
  * `transfer_funds(source_acc, dest_acc, amount)`
  * `query_account_balance(acc_id)`
  * `execute_database_sql(raw_query)`
* **Guardrails System:** Llama Guard 3 + NeMo Guardrails + Output PII Masking Filter.

### Objektif Red Team:
1. **Initial Access & Jailbreak:** Menemukan *zero-shot* atau *multi-shot* jailbreak yang berhasil menonaktifkan safe behavior model perbankan tanpa memicu Llama Guard.
2. **Knowledge Extraction & Context Poisoning:**
   * Melakukan serangan *Indirect Prompt Injection* melalui file invoice PDF/dokumen transaksi yang sengaja ditaruh di corpus vector store untuk memicu transfer dana otomatis.
   * Melakukan *PII exfiltration* untuk membaca saldo nasabah lain melalui manipulasi embedding collision pada RAG.
3. **Privilege Escalation:** Memaksa ReAct loop memanggil fungsi `execute_database_sql` untuk mengekstraksi skema tabel internal tanpa izin validasi administrator.
4. **Automated Attack Harness:** Mengembangkan script PyRIT/Garak kustom untuk mengotomasi eksploitasi dan mengukur Attack Success Rate (ASR) sebelum vs sesudah patching.

### Deliverables Wajib:
1. **Exploitation Code & Harness (`capstone/exploit/`):** Script Python interaktif untuk mereproduksi eksploitasi secara konsisten.
2. **Adversarial Mitigation Patch (`capstone/defense/`):** Konfigurasi hardened guardrails, patched prompt templates, dan input sanitization logic.
3. **Formal AI Red Teaming Report (`capstone/AI_RED_TEAM_REPORT.md`):** Dokumen setebal standar CISO/CRO yang mencakup:
   * Executive Summary & Threat Classification (MITRE ATLAS Mapping).
   * Vulnerability Severity Scoring System (CVSS & AI Risk Rating).
   * Step-by-Step Proof of Concept (PoC) & Payload Reproduction.
   * Hardening Architecture Recommendations & Remediation Roadmap.
```