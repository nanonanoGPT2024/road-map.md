# OPENCLAW MASTERY: DEPLOY, AUTOMATE, & SECURE
**Panduan Komprehensif Arsitektur & Operasional Personal AI Agent Terdistribusi**  
*Berdasarkan kurikulum resmi [roadmap.sh/openclaw](https://roadmap.sh/openclaw)*

---

## 📌 Course Overview
OpenClaw adalah platform personal AI agent *open-source* dan *self-hosted* yang menghubungkan aplikasi perpesanan harian Anda (Telegram, WhatsApp, Discord, Slack) dengan berbagai model kecerdasan buatan (OpenAI, Anthropic Claude, Google Gemini, dan LLM lokal via Ollama).

Berbeda dengan asisten coding reaktif biasa yang hanya merespons saat jendela terminal dibuka, OpenClaw dirancang sebagai **agen otonom proaktif**:
- Berjalan 24/7 di latar belakang (background daemon) di mesin lokal atau server VPS pribadi.
- Menjalankan tugas berkala secara mandiri (*heartbeat, cron schedules, webhooks*).
- Memiliki akses aman ke sistem file, command line, API pihak ketiga, dan ekosistem tool Model Context Protocol (MCP).
- Menjaga kendali data dan privasi 100% di tangan Anda tanpa ketergantungan vendor (*model-agnostic*).

Kursus ini memandu Anda dari nol: memahami arsitektur gateway, instalasi CLI, integrasi multi-channel, penulisan custom skills, mitigasi celah keamanan (prompt injection & sandboxing), hingga orkestrasi multi-agent dan deployment 24/7 di VPS terisolasi.

---

## 🗺️ Learning Roadmap & Struktur Bab

```text
COURSE: OPENCLAW MASTERY
│
├── BAB 01 — Fondasi & Arsitektur OpenClaw
│   ├── Module 01: Pengenalan OpenClaw, Konsep Gateway Daemon, & Model-Agnostic Agent
│   └── Module 02: Instalasi CLI, Inisialisasi Workspace, & Diagnostic (doctor --deep)
│
├── BAB 02 — Konfigurasi Provider AI & Model Routing
│   ├── Module 01: Integrasi Multi-Provider (OpenAI, Anthropic, Gemini, & Ollama Lokal)
│   └── Module 02: Model Routing, Fallback Provider, & Token Budget Optimization
│
├── BAB 03 — Integrasi Kanal Pesan (Messaging Channels)
│   ├── Module 01: Menghubungkan Telegram & Discord Bot Gateway
│   └── Module 02: Integrasi WhatsApp & Slack (Session Management & Multi-Device)
│
├── BAB 04 — Sistem Memori & Konteks Persisten
│   ├── Module 01: Short-term Session vs Long-term Vector Memory
│   └── Module 02: Dynamic RAG & Knowledge Retrieval untuk Personal Agent
│
├── BAB 05 — Ekosistem Skills, ClawHub, & MCP
│   ├── Module 01: Menggunakan ClawHub & Membuat Custom Skills
│   └── Module 02: Integrasi Model Context Protocol (MCP) Tools
│
├── BAB 06 — Automasi Proaktif: Heartbeats, Cron, & Webhooks
│   ├── Module 01: Proactive Heartbeats & Scheduled Cron Jobs
│   └── Module 02: Inbound Webhooks & Event-Driven Action Triggers
│
├── BAB 07 — Keamanan, Sandboxing, & Mitigasi Risiko
│   ├── Module 01: Permission Model, Shell Sandboxing, & Human-in-the-Loop
│   └── Module 02: Proteksi Prompt Injection, Data Leaks, & Credential Vaults
│
├── BAB 08 — Multi-Agent Orchestration & Deployment 24/7
│   ├── Module 01: Multi-Agent Collaboration & Subagent Delegation
│   └── Module 02: Self-Hosting di VPS 24/7 (Docker, Systemd, Tailscale / Tunnel)
│
└── CAPSTONE PROJECT: Autonomous 24/7 Personal Operations Agent (Executive Butler)
```

---

## 🎯 Navigasi Materi

- [BAB 01 — Fondasi & Arsitektur OpenClaw](./BAB-01-Fondasi-dan-Arsitektur/)
  - [Module 01: Pengenalan OpenClaw, Konsep Gateway Daemon, & Model-Agnostic Agent](./BAB-01-Fondasi-dan-Arsitektur/Module-01-Pengenalan-OpenClaw-dan-Arsitektur-Agent.md)
  - [Module 02: Instalasi CLI, Inisialisasi Workspace, & Diagnostic (doctor --deep)](./BAB-01-Fondasi-dan-Arsitektur/Module-02-Instalasi-CLI-dan-Diagnostic-Healthcheck.md)
  - [Evaluasi & Quiz BAB 01](./BAB-01-Fondasi-dan-Arsitektur/BAB-01-Quiz-dan-Challenge.md)
- [BAB 02 — Konfigurasi Provider AI & Model Routing](./BAB-02-Provider-AI-dan-Model-Routing/)
  - [Module 01: Integrasi Multi-Provider (OpenAI, Anthropic, Gemini, & Ollama Lokal)](./BAB-02-Provider-AI-dan-Model-Routing/Module-01-Integrasi-Multi-Provider.md)
  - [Module 02: Model Routing, Fallback Provider, & Token Budget Optimization](./BAB-02-Provider-AI-dan-Model-Routing/Module-02-Model-Routing-Fallback-dan-Token-Optimization.md)
  - [Evaluasi & Quiz BAB 02](./BAB-02-Provider-AI-dan-Model-Routing/BAB-02-Quiz-dan-Challenge.md)
- [BAB 03 — Integrasi Kanal Pesan (Messaging Channels)](./BAB-03-Integrasi-Kanal-Pesan/)
  - [Module 01: Menghubungkan Telegram & Discord Bot Gateway](./BAB-03-Integrasi-Kanal-Pesan/Module-01-Menghubungkan-Telegram-dan-Discord.md)
  - [Module 02: Integrasi WhatsApp & Slack (Session Management & Multi-Device)](./BAB-03-Integrasi-Kanal-Pesan/Module-02-Integrasi-WhatsApp-dan-Slack.md)
  - [Evaluasi & Quiz BAB 03](./BAB-03-Integrasi-Kanal-Pesan/BAB-03-Quiz-dan-Challenge.md)
- [BAB 04 — Sistem Memori & Konteks Persisten](./BAB-04-Memori-dan-Konteks-Persisten/)
  - [Module 01: Short-term Session vs Long-term Vector Memory](./BAB-04-Memori-dan-Konteks-Persisten/Module-01-Short-Term-vs-Long-Term-Vector-Memory.md)
  - [Module 02: Dynamic RAG & Knowledge Retrieval untuk Personal Agent](./BAB-04-Memori-dan-Konteks-Persisten/Module-02-Dynamic-RAG-dan-Knowledge-Retrieval.md)
  - [Evaluasi & Quiz BAB 04](./BAB-04-Memori-dan-Konteks-Persisten/BAB-04-Quiz-dan-Challenge.md)
- [BAB 05 — Ekosistem Skills, ClawHub, & MCP](./BAB-05-Skills-ClawHub-dan-MCP/)
  - [Module 01: Menggunakan ClawHub & Membuat Custom Skills](./BAB-05-Skills-ClawHub-dan-MCP/Module-01-Menggunakan-ClawHub-dan-Membuat-Custom-Skills.md)
  - [Module 02: Integrasi Model Context Protocol (MCP) Tools](./BAB-05-Skills-ClawHub-dan-MCP/Module-02-Integrasi-Model-Context-Protocol-MCP.md)
  - [Evaluasi & Quiz BAB 05](./BAB-05-Skills-ClawHub-dan-MCP/BAB-05-Quiz-dan-Challenge.md)
- [BAB 06 — Automasi Proaktif: Heartbeats, Cron, & Webhooks](./BAB-06-Automasi-Proaktif-Cron-Webhooks/)
  - [Module 01: Proactive Heartbeats & Scheduled Cron Jobs](./BAB-06-Automasi-Proaktif-Cron-Webhooks/Module-01-Proactive-Heartbeats-dan-Scheduled-Cron-Jobs.md)
  - [Module 02: Inbound Webhooks & Event-Driven Action Triggers](./BAB-06-Automasi-Proaktif-Cron-Webhooks/Module-02-Inbound-Webhooks-dan-Event-Driven-Action-Triggers.md)
  - [Evaluasi & Quiz BAB 06](./BAB-06-Automasi-Proaktif-Cron-Webhooks/BAB-06-Quiz-dan-Challenge.md)
- [BAB 07 — Keamanan, Sandboxing, & Mitigasi Risiko](./BAB-07-Keamanan-Sandboxing-Risiko/)
  - [Module 01: Permission Model, Shell Sandboxing, & Human-in-the-Loop](./BAB-07-Keamanan-Sandboxing-Risiko/Module-01-Permission-Model-Shell-Sandboxing-dan-Human-in-the-Loop.md)
  - [Module 02: Proteksi Prompt Injection, Data Leaks, & Credential Vaults](./BAB-07-Keamanan-Sandboxing-Risiko/Module-02-Proteksi-Prompt-Injection-Data-Leaks-dan-Credential-Vaults.md)
  - [Evaluasi & Quiz BAB 07](./BAB-07-Keamanan-Sandboxing-Risiko/BAB-07-Quiz-dan-Challenge.md)
- [BAB 08 — Multi-Agent Orchestration & Deployment 24/7](./BAB-08-Multi-Agent-dan-Deployment/)
  - [Module 01: Multi-Agent Collaboration & Subagent Delegation](./BAB-08-Multi-Agent-dan-Deployment/Module-01-Multi-Agent-Collaboration-dan-Subagent-Delegation.md)
  - [Module 02: Self-Hosting di VPS 24/7 (Docker, Systemd, & Tailscale)](./BAB-08-Multi-Agent-dan-Deployment/Module-02-Self-Hosting-di-VPS-24-7-Docker-Systemd-dan-Tailscale.md)
  - [Evaluasi & Quiz BAB 08](./BAB-08-Multi-Agent-dan-Deployment/BAB-08-Quiz-dan-Challenge.md)
- [🏆 CAPSTONE PROJECT: Autonomous 24/7 Personal Operations Agent](./CAPSTONE-PROJECT-Autonomous-Personal-Operations-Agent.md)
