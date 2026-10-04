# Kurikulum Enterprise: Advanced Prompt Engineering & In-Context Reasoning Architecture

Selamat datang di repositori silabus resmi kurikulum enterprise **Prompt Engineering**. Kurikulum ini dirancang untuk menjembatani kesenjangan antara interaksi intuitif ad-hoc dengan rekayasa sistem berbasis Large Language Models (LLM) yang deterministik, terukur, aman, dan siap diproduksi (*production-ready*).

---

## 1. Course Overview & Mindset

### Filosofi Kurikulum
Prompt Engineering modern bukan sekadar seni menyusun kata-kata (*wordsmithing*), melainkan **rekayasa antarmuka probabilistik** (*probabilistic interface engineering*). Mengontrol LLM menuntut pergeseran paradigma dari pemrograman deterministik tradisional (input deterministik $\to$ fungsi $\to$ output pasti) menuju rekayasa komputasi stokastik (distribusi token, manipulasi *logits*, reduksi entropi, dan *in-context guidance*).

### Mental Models Utama
1. **Model Distribusi Probabilitas**: Memahami bahwa setiap token yang dihasilkan adalah hasil pengambilan sampel (*sampling*) dari distribusi probabilitas bersyarat $P(w_t | w_{<t})$. Prompt adalah proses pengkondisian ruang pencarian (*prior conditioning*).
2. **Context Window sebagai Ephemeral RAM**: Memperlakukan *context window* bukan sekadar kotak teks, melainkan memori kerja dinamis dengan karakteristik atensi terbatas (*attention budget*), degradasi posisi (*Lost-in-the-Middle*), dan biaya tokenomi yang ketat.
3. **Structured & Programmable Execution**: Menggeser LLM dari sekadar antarmuka percakapan natural menjadi mesin penalaran formal melalui pemaksaan skema (*grammar-constrained decoding*), pemanggilan fungsi (*function calling*), dan pola *multi-step reasoning* (ReAct, Reflexion, CoT).
4. **Adversarial & Defensive Posture**: Mengasumsikan bahwa seluruh input dari pihak ketiga berpotensi mengandung vektor serangan (*Prompt Injection*, *Jailbreaking*, *Data Exfiltration*), sehingga memerlukan arsitektur pertahanan berlapis (*defense-in-depth*).

### Target Audiens & Prasyarat
* **Audiens**: Senior Software Engineer, AI/ML Engineer, Data Scientist, dan Solution Architect yang mengintegrasikan LLM ke dalam arsitektur perangkat lunak enterprise.
* **Prasyarat**:
  * Penguasaan bahasa pemrograman Python tingkat lanjut (asynchronous programming, typing, Pydantic).
  * Pemahaman dasar arsitektur Transformer (Self-Attention mechanism, Positional Encoding).
  * Pengalaman menggunakan REST API LLM komersial (OpenAI, Anthropic) maupun model *open-weights* (Llama, Mistral) via vLLM/HuggingFace.

---

## 2. Learning Roadmap

```plaintext
Prompt Engineering Enterprise Roadmap
├── 01: Foundations of LLMs & Generative Inference
│   ├── 01-tokenization-sampling-mechanics
│   ├── 02-attention-and-context-window-limits
│   └── 03-decoding-parameters-hyperparameter-tuning
├── 02: Core Prompt Anatomy & In-Context Learning (ICL)
│   ├── 01-prompt-anatomy-and-role-framing
│   ├── 02-zero-shot-vs-few-shot-heuristics
│   └── 03-exemplar-selection-and-ordering-biases
├── 03: Advanced Reasoning Paradigms
│   ├── 01-chain-of-thought-and-variants
│   ├── 02-self-consistency-and-ensembling
│   └── 03-tree-of-thoughts-and-graph-of-thoughts
├── 04: Structured Output Generation & Schema Enforcement
│   ├── 01-json-yaml-and-structured-extraction
│   ├── 02-instructor-pydantic-and-type-safety
│   └── 03-grammar-constrained-decoding
├── 05: Retrieval-Augmented Generation (RAG) Prompting
│   ├── 01-context-injection-and-chunk-attribution
│   ├── 02-lost-in-the-middle-mitigation
│   └── 03-citation-grounding-and-faithfulness
├── 06: Directional Stimulus, Critique, & Self-Refinement
│   ├── 01-directional-stimulus-prompting
│   ├── 02-self-refine-and-reflexion-architectures
│   └── 03-react-pattern-interleaved-reasoning-and-action
├── 07: Adversarial Robustness, Safety, & Jailbreak Mitigation
│   ├── 01-prompt-injection-taxonomy
│   ├── 02-system-hardening-and-delimiters
│   └── 03-guardrails-and-moderation-layers
├── 08: Context Window Optimization & Cost Engineering
│   ├── 01-token-reduction-and-prompt-compression
│   ├── 02-semantic-caching-architectures
│   └── 03-long-context-performance-engineering
├── 09: Automated Prompt Engineering & Optimization (DSPy)
│   ├── 01-programmatic-prompt-synthesis
│   ├── 02-dspy-programming-and-teleprompters
│   └── 03-gradient-free-prompt-optimization
└── 10: Enterprise LLM Evaluation, Testing, & Observability
    ├── 01-llm-as-a-judge-design-and-biases
    ├── 02-automated-evaluation-frameworks
    └── 03-observability-tracing-and-ci-cd-pipelines
```

---

## 3. Navigasi Silabus Detail

### [Bab 01: Foundations of LLMs & Generative Inference](./01-foundations-of-llms/)
Membedah arsitektur internal LLM dari kacamata rekayasa prompt: mekanika sub-word tokenization, batas representasi, dan kontrol matematis atas sampling stokastik.
* [Modul 01: Tokenization Mechanics, Byte-Pair Encoding, & Vocabulary Discrepancies](./01-foundations-of-llms/01-tokenization-sampling-mechanics.md)
* [Modul 02: Transformer Context Window Dynamics & Quadratic Complexity Constraints](./01-foundations-of-llms/02-attention-and-context-window-limits.md)
* [Modul 03: Decoding Hyperparameters: Temperature, Top-P, Top-K, Min-P, & Frequency/Presence Penalties](./01-foundations-of-llms/03-decoding-parameters-hyperparameter-tuning.md)

### [Bab 02: Core Prompt Anatomy & In-Context Learning (ICL)](./02-core-prompt-anatomy-and-icl/)
Menstandarkan arsitektur prompt formal, rekayasa instruksi, manipulasi peran (System/User/Assistant), serta eliminasi bias posisi pada contoh *few-shot*.
* [Modul 01: Production-Grade Prompt Anatomy, Context Delimiters, & System Framing](./02-core-prompt-anatomy-and-icl/01-prompt-anatomy-and-role-framing.md)
* [Modul 02: In-Context Learning (ICL): Zero-Shot, Few-Shot, & Task Priming](./02-core-prompt-anatomy-and-icl/02-zero-shot-vs-few-shot-heuristics.md)
* [Modul 03: Exemplar Engineering: Selection Strategies, Similarity Clustering, & Order-Sensitivity Mitigation](./02-core-prompt-anatomy-and-icl/03-exemplar-selection-and-ordering-biases.md)

### [Bab 03: Advanced Reasoning Paradigms](./03-advanced-reasoning-paradigms/)
Pola inferensi multi-langkah (*multi-step reasoning*) untuk masalah inferensi simbolik, logika kompleks, dan dekomposisi komputasional.
* [Modul 01: Chain-of-Thought (CoT), Zero-Shot-CoT, & Least-to-Most Decomposition](./03-advanced-reasoning-paradigms/01-chain-of-thought-and-variants.md)
* [Modul 02: Self-Consistency, Sampling Ensembles, & Majority Voting Mechanisms](./03-advanced-reasoning-paradigms/02-self-consistency-and-ensembling.md)
* [Modul 03: Graph & Tree-of-Thoughts (ToT/GoT): State Evaluation, Search Heuristics, & Backtracking](./03-advanced-reasoning-paradigms/03-tree-of-thoughts-and-graph-of-thoughts.md)

### [Bab 04: Structured Output Generation & Schema Enforcement](./04-structured-output-generation/)
Teknik deterministik untuk menjamin output LLM sesuai dengan skema tipe data enterprise (JSON/YAML) tanpa kegagalan parsing (*parser-breaking*).
* [Modul 01: Deterministic Extraction: Native JSON Modes, Schemas, & Parsing Fallbacks](./04-structured-output-generation/01-json-yaml-and-structured-extraction.md)
* [Modul 02: Type-Safe Generation with Pydantic, Instructor, & Native Function Calling API](./04-structured-output-generation/02-instructor-pydantic-and-type-safety.md)
* [Modul 03: Constrained Decoding: Context-Free Grammars (CFG), Regular Expressions, & Outlines/JSONformer](./04-structured-output-generation/03-grammar-constrained-decoding.md)

### [Bab 05: Retrieval-Augmented Generation (RAG) Prompting](./05-rag-prompt-strategies/)
Optimalisasi sintaksis dan semantik prompt khusus untuk augmentasi data eksternal, reduksi halusinasi, dan verifikasi sumber.
* [Modul 01: Context Placement, Chunk Framing, & Source Attribution Protocols](./05-rag-prompt-strategies/01-context-injection-and-chunk-attribution.md)
* [Modul 02: Overcoming Attention Degradation & The Lost-in-the-Middle Phenomenon](./05-rag-prompt-strategies/02-lost-in-the-middle-mitigation.md)
* [Modul 03: Faithfulness Grounding, Citation Engineering, & Negative Constraint Handling](./05-rag-prompt-strategies/03-citation-grounding-and-faithfulness.md)

### [Bab 06: Directional Stimulus, Critique, & Self-Refinement](./06-critique-and-refinement/)
Loop umpan balik otonom yang memungkinkan model mengevaluasi, mengoreksi, dan mengoptimalkan responnya sendiri sebelum disajikan ke pengguna.
* [Modul 01: Directional Stimulus Prompting: Guiding Black-Box LLMs via Small Verifiers](./06-critique-and-refinement/01-directional-stimulus-prompting.md)
* [Modul 02: Reflexion & Self-Refine: Multi-Turn Verbal Reinforcement & Memory Buffers](./06-critique-and-refinement/02-self-refine-and-reflexion-architectures.md)
* [Modul 03: ReAct Architecture: Synergizing Reasoning Traces and Task-Specific Actions](./06-critique-and-refinement/03-react-pattern-interleaved-reasoning-and-action.md)

### [Bab 07: Adversarial Robustness, Safety, & Jailbreak Mitigation](./07-adversarial-robustness-and-safety/)
Metodologi pertahanan terhadap eksploitasi keamanan berbasis teks, serangan injeksi prompt, dan kebocoran data sensitif enterprise.
* [Modul 01: Threat Modeling: Direct/Indirect Injection, Data Exfiltration, & Context Leaks](./07-adversarial-robustness-and-safety/01-prompt-injection-taxonomy.md)
* [Modul 02: Defensive System Prompts, Structured Delimiters, & Canary Tokens](./07-adversarial-robustness-and-safety/02-system-hardening-and-delimiters.md)
* [Modul 03: Dual-LLM Verification, Content Moderation Guardrails, & NeMo/Llama-Guard](./07-adversarial-robustness-and-safety/03-guardrails-and-moderation-layers.md)

### [Bab 08: Context Window Optimization & Cost Engineering](./08-context-optimization-and-cost/)
Strategi mitigasi latensi jaringan, kontrol alokasi biaya tokenomi, dan rekayasa prompt untuk model berkonteks sangat panjang (*million-token context*).
* [Modul 01: Prompt Compression: Token Pruning, Semantic Distillation, & LLMLingua](./08-context-optimization-and-cost/01-token-reduction-and-prompt-compression.md)
* [Modul 02: Exact & Semantic Caching Strategies (Redis, GPTCache) for Production LLMs](./08-context-optimization-and-cost/02-semantic-caching-architectures.md)
* [Modul 03: Million-Token Context Economics: Prompt Caching, Latency-Accuracy Trade-Offs](./08-context-optimization-and-cost/03-long-context-performance-engineering.md)

### [Bab 09: Automated Prompt Engineering & Optimization (DSPy)](./09-automated-prompt-engineering/)
Transisi dari prompt manual ke optimasi berbasis kode dan kompilasi algoritmik menggunakan pendekatan programmatic DSPy (*Declarative Self-improving Python*).
* [Modul 01: Automatic Prompt Engineer (APE): Generating & Scoring Prompts with LLMs](./09-automated-prompt-engineering/01-programmatic-prompt-synthesis.md)
* [Modul 02: DSPy Fundamentals: Signatures, Predictors, Modules, & Teleprompters](./09-automated-prompt-engineering/02-dspy-programming-and-teleprompters.md)
* [Modul 03: Metric-Driven Compiler Optimization: BootstrapFewShot, MIPRO, & Bayesian Tuning](./09-automated-prompt-engineering/03-gradient-free-prompt-optimization.md)

### [Bab 10: Enterprise LLM Evaluation, Testing, & Observability](./10-evaluation-and-observability/)
Pengujian regresi, validasi otomatis, orkestrasi metrik produksi, dan instrumentasi jejak (*tracing*) eksekusi prompt berskala besar.
* [Modul 01: Designing Robust LLM-as-a-Judge Systems: Position, Verbosity, & Self-Enhancement Biases](./10-evaluation-and-observability/01-llm-as-a-judge-design-and-biases.md)
* [Modul 02: Evaluation Frameworks: Ragas, TruLens, & Deepeval for Production Guarding](./10-evaluation-and-observability/02-automated-evaluation-frameworks.md)
* [Modul 03: Telemetry, Prompt Drift Tracking, & CI/CD Regression Harnesses with Langfuse/OpenTelemetry](./10-evaluation-and-observability/03-observability-tracing-and-ci-cd-pipelines.md)

---

## 4. Capstone Project Enterprise

### Project Title:
**Autonomous Financial & Regulatory Compliance Audit System (Auto-Audit Engine)**

### Deskripsi Masalah:
Sebuah institusi perbankan global memproses ribuan dokumen transaksi, memo internal, dan laporan kepatuhan regulasi (seperti OJK, GDPR, dan SOX) setiap kuartal. Dokumen-dokumen ini rentan terhadap kesalahan manusia, manipulasi format, atau upaya adversarial untuk menyembunyikan pelanggaran kepatuhan.

### Sasaran Arsitektur:
Peserta harus merancang, membangun, dan mengevaluasi sistem berbasis prompt mutakhir yang memproses teks regulasi mentah dan menghasilkan laporan audit formal dengan spesifikasi berikut:

```
[Raw Documents / Ingestion] 
       │
       ▼
[Dual-LLM Security Guardrail] ──(Detect Prompt Injections/Indirect Vectors)──► [Drop / Alert]
       │
       ▼ (Sanitized Context)
[RAG Engine with Hybrid Positioning & Dynamic Exemplar Selection]
       │
       ▼ (Attributed Context)
[DSPy-Compiled Multi-Step Pipeline: Decompose ➔ Cross-Examine ➔ Self-Reflect]
       │
       ▼
[Constrained Decoding (Pydantic / CFG)]
       │
       ▼ (Valid Schema Guaranteed)
[LLM-as-a-Judge Evaluation Harness (Ragas / Deepeval)]
       │
       ▼
[JSON/PDF Audit Report + Distributed Tracing Data (Langfuse)]
```

### Kriteria Implementasi:
1. **Adversarial Hardening**:
   * Sistem harus mampu mendeteksi dan menolak sedikitnya 99% serangan *Indirect Prompt Injection* yang disematkan dalam catatan transaksi fiktif tanpa mengalami degradasi respons valid.
   * Implementasi pemisahan peran data dan instruksi menggunakan isolasi *delimiter-tagging* dan deteksi *canary-token*.
2. **Deterministic Output Guarantee**:
   * Ekstraksi temuan audit harus dipetakan langsung ke Pydantic Schema yang merepresentasikan: `Finding`, `SeverityLevel`, `RegulatoryClauseViolated`, `EvidenceSnippet`, dan `ConfidenceScore`.
   * Tingkat kegagalan parsing JSON pada API target harus 0% menggunakan *grammar-constrained decoding* atau *native schema enforcement*.
3. **Advanced Reasoning Loop**:
   * Menerapkan pipeline penalaran berbasis *Reflexion* atau *Tree-of-Thoughts* di mana model mengajukan hipotesis pelanggaran, mengkritik logikanya sendiri berdasarkan klausul regulasi, dan memvalidasi keabsahan bukti (*evidence grounding*).
4. **Programmatic Optimization via DSPy**:
   * Alih-alih menggunakan teks prompt statis, pipeline logika utama harus dioptimalkan menggunakan teleprompter DSPy (`MIPROv2` atau `BootstrapFewShotWithRandomSearch`) untuk memaksimalkan metrik *Faithfulness* dan *Answer Relevance*.
5. **Observability & Continuous Evaluation**:
   * Seluruh jejak eksekusi LLM harus terekam secara terdistribusi via OpenTelemetry/Langfuse, mencakup: konsumsi token, latensi per tahap, dan *confidence score*.
   * Mengintegrasikan *LLM-as-a-Judge* test suite otomatis pada repositori kode (GitHub Actions) yang memvalidasi batas metrik minimal (Faithfulness > 0.85, Groundedness > 0.90) sebelum deployment.

### Deliverables:
1. Kode sumber Python lengkap dengan struktur modular.
2. File konfigurasi DSPy dan dataset evaluasi (minimal 50 skenario uji kompleks).
3. Laporan metrik komparatif antara prompt manual baseline vs pipeline teroptimasi DSPy.
4. Dashboard observabilitas tracing siap pakai (berbasis kontainer lokal atau cloud instance).