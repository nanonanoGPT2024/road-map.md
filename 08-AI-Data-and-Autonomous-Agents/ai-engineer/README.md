# 🤖 AI Engineer Mastery: LLM Internals, Prompt Engineering, RAG Systems, & Autonomous Multi-Agent Workflows

> **Kurikulum Komprehensif untuk AI Engineer Modern — Dari Fondasi LLM hingga Production-Grade Autonomous Systems**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Level: Intermediate to Advanced](https://img.shields.io/badge/Level-Intermediate%20to%20Advanced-red.svg)]()
[![Duration: 16-20 Weeks](https://img.shields.io/badge/Duration-16--20%20Weeks-blue.svg)]()
[![Bahasa: Indonesia](https://img.shields.io/badge/Bahasa-Indonesia-green.svg)]()
[![Roadmap: roadmap.sh/ai-engineer](https://img.shields.io/badge/Roadmap-roadmap.sh%2Fai--engineer-purple.svg)](https://roadmap.sh/ai-engineer)

---

## 📋 Daftar Isi

- [Deskripsi Kursus](#-deskripsi-kursus)
- [Prinsip Utama Pembelajaran](#-prinsip-utama-pembelajaran-learn--master)
- [Prasyarat](#-prasyarat)
- [Learning Roadmap Overview](#-learning-roadmap-overview)
- [Struktur Kurikulum](#-struktur-kurikulum)
  - [BAB 01 — Fondasi LLM & AI Engineering Landscape](#bab-01--fondasi-llm--ai-engineering-landscape)
  - [BAB 02 — LLM Internals: Arsitektur Transformer & Mekanisme Inferensi](#bab-02--llm-internals-arsitektur-transformer--mekanisme-inferensi)
  - [BAB 03 — Prompt Engineering: Teknik, Strategi & Optimasi](#bab-03--prompt-engineering-teknik-strategi--optimasi)
  - [BAB 04 — LLM APIs, Tooling & Orkestrasi Model](#bab-04--llm-apis-tooling--orkestrasi-model)
  - [BAB 05 — Retrieval-Augmented Generation (RAG): Fondasi & Arsitektur](#bab-05--retrieval-augmented-generation-rag-fondasi--arsitektur)
  - [BAB 06 — Advanced RAG: Optimasi, Evaluasi & Production Pipeline](#bab-06--advanced-rag-optimasi-evaluasi--production-pipeline)
  - [BAB 07 — Fine-Tuning, Alignment & Model Customization](#bab-07--fine-tuning-alignment--model-customization)
  - [BAB 08 — AI Agents: Desain, Reasoning & Tool Use](#bab-08--ai-agents-desain-reasoning--tool-use)
  - [BAB 09 — Multi-Agent Systems & Autonomous Workflows](#bab-09--multi-agent-systems--autonomous-workflows)
  - [BAB 10 — Production AI Engineering: Deployment, Observability & Governance](#bab-10--production-ai-engineering-deployment-observability--governance)
- [Capstone Project](#-capstone-project)
- [Cara Menggunakan Materi Ini](#-cara-menggunakan-materi-ini)
- [Tools & Tech Stack](#-tools--tech-stack)
- [Kontribusi](#-kontribusi)

---

## 🎯 Deskripsi Kursus

Kurikulum **AI Engineer Mastery** dirancang sebagai jalur pembelajaran komprehensif bagi software engineer, data scientist, dan ML practitioner yang ingin menguasai seluruh spektrum rekayasa sistem AI modern — mulai dari **pemahaman mendalam internal LLM** hingga **membangun sistem multi-agent otonom siap produksi**.

Berbeda dari kursus AI generik, kurikulum ini mengadopsi pendekatan **engineer-first**: setiap konsep teoritis langsung dipasangkan dengan implementasi nyata, benchmark kuantitatif, dan pola arsitektur yang digunakan di industri. Referensi utama mengacu pada **[roadmap.sh/ai-engineer](https://roadmap.sh/ai-engineer)** yang merupakan standar industri global untuk jalur karier AI Engineer.

### 🌟 Apa yang Akan Anda Kuasai

| Domain | Kemampuan yang Dibangun |
|--------|------------------------|
| **LLM Internals** | Memahami arsitektur Transformer, attention mechanism, tokenisasi, dan proses inferensi dari level matematis hingga implementasi |
| **Prompt Engineering** | Merancang prompt sistem yang robust, teknik chain-of-thought, few-shot learning, dan prompt optimization pipeline |
| **RAG Systems** | Membangun pipeline RAG end-to-end: chunking, embedding, vector search, reranking, hingga evaluasi dengan RAGAS |
| **Fine-Tuning** | Menerapkan LoRA/QLoRA, instruction tuning, RLHF, dan DPO untuk customisasi model domain-spesifik |
| **AI Agents** | Merancang agent dengan ReAct, Reflexion, dan tool-use patterns menggunakan LangChain, LlamaIndex, dan AutoGen |
| **Multi-Agent Systems** | Mengorkestrasikan sistem multi-agent dengan supervisor pattern, shared memory, dan inter-agent communication |
| **Production Engineering** | Deploy, monitor, observasi, dan govern sistem AI di skala enterprise dengan LangSmith, Prometheus, dan MLflow |

### 👥 Target Peserta

- **Software Engineer** yang ingin transisi ke AI Engineering
- **ML Engineer / Data Scientist** yang ingin memperluas kemampuan ke LLM systems
- **Backend Engineer** yang membangun aplikasi berbasis AI/LLM
- **Tech Lead / Architect** yang merancang arsitektur sistem AI enterprise

---

## 🧠 Prinsip Utama Pembelajaran: LEARN → MASTER

Kurikulum ini dibangun di atas kerangka **LEARN → MASTER** yang memastikan setiap peserta tidak sekadar memahami konsep, tetapi benar-benar mampu mengimplementasikan dan mengoptimalkan sistem AI di lingkungan produksi nyata.

```
╔══════════════════════════════════════════════════════════════════════════╗
║                    KERANGKA LEARN → MASTER                              ║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║  L — Layered Fundamentals                                                ║
║      Setiap topik dibangun berlapis: teori → mekanisme → implementasi   ║
║      Tidak ada "magic" — semua dijelaskan dari prinsip pertama          ║
║                                                                          ║
║  E — Engineer-First Approach                                             ║
║      Setiap konsep langsung dikodekan, diukur, dan dioptimalkan         ║
║      Hands-on labs wajib selesai sebelum lanjut ke modul berikutnya    ║
║                                                                          ║
║  A — Applied Pattern Recognition                                         ║
║      Belajar mengenali pola masalah → memilih solusi yang tepat         ║
║      Decision framework untuk setiap skenario arsitektur                ║
║                                                                          ║
║  R — Real-World Benchmarking                                             ║
║      Setiap implementasi dievaluasi dengan metrik kuantitatif           ║
║      Perbandingan pendekatan: biaya, latensi, akurasi, skalabilitas     ║
║                                                                          ║
║  N — Networked Knowledge Building                                        ║
║      Koneksi eksplisit antar konsep lintas bab                          ║
║      Setiap bab membangun di atas fondasi bab sebelumnya                ║
║                                                                          ║
║  ──────────────────────────────────────────────────────────────────────  ║
║                                                                          ║
║  M — Mastery Through Iteration                                           ║
║      Konsep kunci diulang dalam konteks yang semakin kompleks           ║
║      Spiral learning: fondasi → intermediate → advanced → production    ║
║                                                                          ║
║  A — Autonomous Problem Solving                                          ║
║      Latihan open-ended yang tidak memiliki satu jawaban benar          ║
║      Membangun intuisi engineering melalui eksplorasi mandiri           ║
║                                                                          ║
║  S — System Thinking Integration                                         ║
║      Memandang setiap komponen dalam konteks sistem yang lebih besar    ║
║      Tradeoff analysis: performa vs biaya vs maintainability            ║
║                                                                          ║
║  T — Test-Driven Quality                                                 ║
║      Evaluasi otomatis untuk setiap pipeline AI yang dibangun           ║
║      LLM-as-judge, unit testing untuk prompt, integration testing RAG   ║
║                                                                          ║
║  E — Enterprise-Grade Production Mindset                                 ║
║      Setiap solusi dirancang untuk skalabilitas dan reliabilitas        ║
║      Security, governance, observability bukan afterthought             ║
║                                                                          ║
║  R — Reflective Portfolio Building                                       ║
║      Setiap lab menghasilkan artefak yang masuk ke portfolio            ║
║      Capstone project sebagai demonstrasi kemampuan holistik            ║
║                                                                          ║
╚══════════════════════════════════════════════════════════════════════════╝
```

---

## 📦 Prasyarat

Sebelum memulai kurikulum ini, pastikan Anda memiliki fondasi berikut:

### Wajib
- ✅ **Python** — Profisiensi menengah ke atas (OOP, async/await, type hints, decorators)
- ✅ **Machine Learning Dasar** — Pemahaman konsep: gradient descent, loss function, neural network
- ✅ **REST API** — Konsumsi dan pembuatan API dengan Python (requests, FastAPI/Flask)
- ✅ **Git & Version Control** — Workflow kolaborasi standar

### Sangat Direkomendasikan
- 🔵 **Linear Algebra** — Matrix multiplication, vector operations (untuk memahami attention)
- 🔵 **Docker** — Container basics untuk deployment lab environments
- 🔵 **SQL / NoSQL** — Query dasar untuk integrasi data pipeline
- 🔵 **Cloud Basics** — Familiar dengan AWS/GCP/Azure (untuk modul production)

### Tidak Diwajibkan
- ❌ Pengalaman sebelumnya dengan LLM atau AI Engineering
- ❌ Matematika tingkat lanjut (kalkulus, statistik advanced)
- ❌ Background research/akademis di NLP

---

## 🗺️ Learning Roadmap Overview

```
╔═══════════════════════════════════════════════════════════════════════════════════╗
║           AI ENGINEER MASTERY — LEARNING ROADMAP (16-20 Minggu)                 ║
╚═══════════════════════════════════════════════════════════════════════════════════╝

    FASE 1: FOUNDATION                FASE 2: CORE SYSTEMS
    (Minggu 1-4)                      (Minggu 5-10)
    ┌─────────────────────┐           ┌─────────────────────────────────────┐
    │                     │           │                                     │
    │  BAB 01             │           │  BAB 05                             │
    │  AI Engineering     │           │  RAG Fondasi &                      │
    │  Landscape & Setup  │──────────▶│  Arsitektur Core                   │
    │                     │           │                                     │
    │  BAB 02             │           │  BAB 06                             │
    │  LLM Internals &    │           │  Advanced RAG:                      │
    │  Transformer Arch   │──────────▶│  Optimasi & Evaluasi               │
    │                     │           │                                     │
    │  BAB 03             │           │  BAB 07                             │
    │  Prompt Engineering │           │  Fine-Tuning &                      │
    │  & Optimization     │──────────▶│  Model Customization               │
    │                     │           │                                     │
    │  BAB 04             │           │                                     │
    │  LLM APIs &         │           │                                     │
    │  Tool Orchestration │           │                                     │
    └─────────────────────┘           └─────────────────────────────────────┘
              │                                         │
              │                                         │
              ▼                                         ▼
    FASE 3: AGENT SYSTEMS             FASE 4: PRODUCTION MASTERY
    (Minggu 11-14)                    (Minggu 15-20)
    ┌─────────────────────┐           ┌─────────────────────────────────────┐
    │                     │           │                                     │
    │  BAB 08             │           │  BAB 10                             │
    │  AI Agents:         │           │  Production AI:                     │
    │  Reasoning & Tools  │──────────▶│  Deploy, Observe, Govern           │
    │                     │           │                                     │
    │  BAB 09             │           │  CAPSTONE PROJECT                   │
    │  Multi-Agent        │           │  NusantaraAgent:                    │
    │  Systems &          │──────────▶│  Autonomous Enterprise              │
    │  Autonomous Flows   │           │  Research Platform                  │
    │                     │           │                                     │
    └─────────────────────┘           └─────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════════

DETAIL KOMPONEN SETIAP BAB:

    ┌──────────────────────────────────────────────────────────────────────────┐
    │  SETIAP BAB TERDIRI DARI:                                                │
    │                                                                          │
    │  📖 MODUL 1 ──▶ 📖 MODUL 2 ──▶ 🔬 HANDS-ON LAB ──▶ 📝 QUIZ           │
    │     (Teori)       (Aplikasi)      (Implementasi)      (Validasi)        │
    │                                                                          │
    │  Setiap Modul:          Setiap Lab:          Setiap Quiz:               │
    │  • Konsep inti          • Setup environment  • 15-20 soal               │
    │  • Diagram arsitektur   • Step-by-step code  • Multiple choice          │
    │  • Code examples        • Eksperimen mandiri • Coding challenge         │
    │  • Best practices       • Deliverable nyata  • Case analysis            │
    │  • Anti-patterns        • Benchmark & eval   • Passing score: 80%       │
    └──────────────────────────────────────
