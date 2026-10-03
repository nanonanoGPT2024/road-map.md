# 🚀 Golang Mastery: Concurrent Systems, Memory Model, Profiling, & Cloud-Native Microservices

> **Kurikulum Komprehensif untuk Menguasai Go dari Internals hingga Production-Grade Distributed Systems**

[![Go Version](https://img.shields.io/badge/Go-1.22+-00ADD8?style=flat-square&logo=go)](https://golang.org)
[![Level](https://img.shields.io/badge/Level-Intermediate%20to%20Expert-red?style=flat-square)](.)
[![Modules](https://img.shields.io/badge/Modules-20%20Modul-green?style=flat-square)](.)
[![Labs](https://img.shields.io/badge/Hands--On%20Labs-40%2B%20Lab-orange?style=flat-square)](.)
[![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](./LICENSE)
[![Roadmap](https://img.shields.io/badge/Referensi-roadmap.sh%2Fgolang-blueviolet?style=flat-square)](https://roadmap.sh/golang)

---

## 📋 Daftar Isi

- [Deskripsi Kursus](#-deskripsi-kursus)
- [Prinsip Utama Pembelajaran](#-prinsip-utama-pembelajaran-learn--master)
- [Prasyarat](#-prasyarat)
- [Learning Roadmap Overview](#-learning-roadmap-overview)
- [Daftar Bab & Modul Pembelajaran](#-daftar-bab--modul-pembelajaran)
  - [BAB 01 — Go Internals & Runtime Architecture](#bab-01--go-internals--runtime-architecture)
  - [BAB 02 — Memory Model, Allocator & Garbage Collector](#bab-02--memory-model-allocator--garbage-collector)
  - [BAB 03 — Concurrency Primitives & Goroutine Scheduler](#bab-03--concurrency-primitives--goroutine-scheduler)
  - [BAB 04 — Advanced Concurrency Patterns](#bab-04--advanced-concurrency-patterns)
  - [BAB 05 — Profiling, Tracing & Performance Engineering](#bab-05--profiling-tracing--performance-engineering)
  - [BAB 06 — Networking, I/O & Protocol Design](#bab-06--networking-io--protocol-design)
  - [BAB 07 — Microservices Architecture & API Design](#bab-07--microservices-architecture--api-design)
  - [BAB 08 — Data Persistence, Caching & Event Streaming](#bab-08--data-persistence-caching--event-streaming)
  - [BAB 09 — Cloud-Native Infrastructure & Observability](#bab-09--cloud-native-infrastructure--observability)
  - [BAB 10 — Production Hardening, Security & SRE Practices](#bab-10--production-hardening-security--sre-practices)
- [Capstone Project](#-capstone-project)
- [Cara Menggunakan Materi Ini](#-cara-menggunakan-materi-ini)
- [Tools & Teknologi](#-tools--teknologi)
- [Kontributor](#-kontributor)

---

## 📖 Deskripsi Kursus

Kurikulum **Golang Mastery** ini dirancang sebagai jalur pembelajaran sistematis dan terstruktur bagi para engineer yang ingin menguasai Go secara mendalam — bukan sekadar sintaks, tetapi hingga ke lapisan **runtime internals**, **memory model**, **concurrent systems design**, dan **cloud-native production architecture**.

Mengacu pada [roadmap.sh/golang](https://roadmap.sh/golang) sebagai kerangka referensi utama, kurikulum ini memperluas setiap node roadmap menjadi modul pembelajaran yang kaya dengan **teori mendalam**, **hands-on labs berbasis skenario nyata**, dan **quiz evaluasi** yang mengukur pemahaman konseptual maupun kemampuan implementasi.

### 🎯 Tujuan Pembelajaran Utama

| Dimensi | Target Kompetensi |
|---|---|
| **Internals** | Memahami cara kerja Go runtime, scheduler GMP, memory allocator, dan GC secara detail |
| **Concurrency** | Merancang dan mengimplementasikan concurrent systems yang aman, efisien, dan scalable |
| **Performance** | Melakukan profiling end-to-end, tracing, benchmarking, dan optimasi sistematis |
| **Networking** | Membangun high-performance network services dengan custom protocol dan I/O model |
| **Microservices** | Merancang arsitektur microservices production-grade dengan gRPC, REST, dan event-driven patterns |
| **Cloud-Native** | Deploy, orchestrate, dan operate Go services di Kubernetes dengan full observability stack |
| **SRE** | Menerapkan reliability engineering: SLO/SLI, chaos engineering, dan incident response |

### 👥 Target Peserta

```
┌─────────────────────────────────────────────────────────────────┐
│  ✅ Go developer dengan pengalaman 6+ bulan yang ingin naik level │
│  ✅ Backend engineer dari bahasa lain (Java/Python/Node.js)       │
│  ✅ Platform/infrastructure engineer yang menggunakan Go          │
│  ✅ Architect yang merancang distributed systems dengan Go        │
│  ❌ Pemula absolut tanpa pengalaman programming apapun            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🧭 Prinsip Utama Pembelajaran: LEARN → MASTER

Kurikulum ini mengikuti filosofi pembelajaran **LEARN → MASTER** yang memastikan setiap konsep dipelajari secara progresif dan menyeluruh:

```
╔══════════════════════════════════════════════════════════════════════╗
║              FILOSOFI PEMBELAJARAN: LEARN → MASTER                   ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  L — Layer by Layer    : Dari fundamental runtime hingga production  ║
║  E — Experiment First  : Setiap konsep dibuktikan dengan kode nyata  ║
║  A — Apply Immediately : Labs langsung mengaplikasikan teori         ║
║  R — Reflect & Debug   : Analisis mendalam via profiler dan tracer   ║
║  N — Navigate Tradeoffs: Pahami kapan dan mengapa memilih solusi     ║
║                                                                      ║
║  ──────────────────────────────────────────────────────────────────  ║
║                                                                      ║
║  M — Measure Everything : Benchmark, profile, dan trace setiap kode  ║
║  A — Architect Systems  : Rancang dari component hingga distributed  ║
║  S — Secure by Design   : Security bukan afterthought, tapi fondasi  ║
║  T — Test Rigorously    : Unit, integration, load, dan chaos test    ║
║  E — Evolve Continuously: Iterasi berbasis data observability        ║
║  R — Run in Production  : Deploy nyata dengan SLO dan runbook        ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
```

### 📐 Pendekatan Pedagogis Per Modul

Setiap modul dalam kurikulum ini mengikuti struktur **4-Phase Learning Cycle**:

```
  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
  │  THEORY  │───▶│  DEMO    │───▶│  LAB     │───▶│  QUIZ    │
  │          │    │          │    │          │    │          │
  │ Konsep & │    │ Live code│    │ Hands-on │    │ Evaluasi │
  │ Internals│    │ walkthru │    │ scenario │    │ & Review │
  └──────────┘    └──────────┘    └──────────┘    └──────────┘
       │                │               │               │
    30 menit        20 menit        60-90 menit      15 menit
```

---

## ✅ Prasyarat

### Pengetahuan Wajib
- [ ] Sintaks dasar Go: variabel, fungsi, struct, interface, pointer
- [ ] Package management dengan Go Modules (`go mod`)
- [ ] Dasar goroutine dan channel (konsep, bukan mastery)
- [ ] Pemahaman umum HTTP dan REST API
- [ ] Pengalaman dengan Git dan command line Linux/macOS

### Pengetahuan Direkomendasikan
- [ ] Dasar-dasar sistem operasi: process, thread, memory management
- [ ] Konsep networking: TCP/IP, DNS, TLS
- [ ] Familiar dengan Docker dan container basics
- [ ] Pengalaman dengan database (SQL maupun NoSQL)

### Toolchain yang Diperlukan

```bash
# Verifikasi instalasi Go
go version   # Minimum: go1.22.0

# Tools yang akan digunakan sepanjang kurikulum
go install golang.org/x/tools/cmd/godoc@latest
go install github.com/go-delve/delve/cmd/dlv@latest
go install golang.org/x/perf/cmd/benchstat@latest
go install github.com/google/pprof@latest
go install github.com/rakyll/hey@latest
go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest
```

---

## 🗺️ Learning Roadmap Overview

```
╔═══════════════════════════════════════════════════════════════════════════════════════╗
║          GOLANG MASTERY — LEARNING ROADMAP (Fundamental → Production)                 ║
╠═══════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                       ║
║  PHASE 1: INTERNALS & RUNTIME FOUNDATION  [BAB 01-02]                                 ║
║  ═══════════════════════════════════════                                               ║
║                                                                                       ║
║  ┌─────────────────────────────────┐   ┌─────────────────────────────────┐            ║
║  │  BAB 01: Go Internals &         │   │  BAB 02: Memory Model,          │            ║
║  │          Runtime Architecture   │──▶│          Allocator & GC         │            ║
║  │                                 │   │                                 │            ║
║  │  • Compilation pipeline         │   │  • Go Memory Model (HB rules)   │            ║
║  │  • Binary structure & linking   │   │  • TCMalloc-inspired allocator  │            ║
║  │  • Runtime bootstrap sequence   │   │  • GC: tri-color mark-sweep     │            ║
║  │  • Stack vs Heap internals      │   │  • Escape analysis deep dive    │            ║
║  └─────────────────────────────────┘   └─────────────────────────────────┘            ║
║                                                      │                                ║
║  PHASE 2: CONCURRENCY MASTERY  [BAB 03-04]           │                                ║
║  ═════════════════════════════                        ▼                                ║
║                                                                                       ║
║  ┌─────────────────────────────────┐   ┌─────────────────────────────────┐            ║
║  │  BAB 03: Concurrency Primitives │   │  BAB 04: Advanced Concurrency   │            ║
║  │          & Goroutine Scheduler  │──▶│          Patterns               │            ║
║  │                                 │   │                                 │            ║
║  │  • GMP scheduler model          │   │  • Pipeline & fan-out/fan-in    │            ║
║  │  • Channel internals & hchan    │   │  • Worker pool & semaphore      │            ║
║  │  • sync primitives deep dive    │   │  • Rate limiter (token bucket)  │            ║
║  │  • atomic & memory ordering     │   │  • Lock-free data structures    │            ║
║  └─────────────────────────────────┘   └─────────────────────────────────┘            ║
║                                                      │                                ║
║  PHASE 3: PERFORMANCE ENGINEERING  [BAB 05]          │                                ║
║  ══════════════════════════════════                   ▼                                ║
║                                                                                       ║
║  ┌───────────────────────────────────────────────────────────────────┐                ║
║  │  BAB 05: Profiling, Tracing & Performance Engineering             │                ║
║  │                                                                   │                ║
║  │  • pprof: CPU, memory, goroutine, mutex, block profiling          │                ║
║  │  • Execution tracer (go tool trace) — scheduler & GC events       │                ║
║  │  • Benchmark engineering: -benchmem, -cpuprofile, benchstat       │                ║
║  │  • Flame graphs, latency percentiles, optimization workflow       │                ║
║  └───────────────────────────────────────────────────────────────────┘                ║
║                                                      │                                ║
║  PHASE 4: NETWORKING & SERVICES  [BAB 06-07]         │                                ║
║  ═══════════════════════════════                      ▼                                ║
║                                                                                       ║
║  ┌─────────────────────────────────┐   ┌─────────────────────────────────┐            ║
║  │  BAB 06: Networking, I/O &      │   │  BAB 07: Microservices          │            ║
║  │          Protocol Design        │──▶│          Architecture & API     │            ║
║  │                                 │   │                                 │            ║
║  │  • net/http internals & tuning  │   │  • gRPC: proto3, streaming      │            ║
║  │  • TCP/UDP raw socket & TLS     │   │  • Service mesh & discovery     │            ║
║  │  • Custom binary protocol       │   │  • API gateway & BFF pattern    │            ║
║  │  • WebSocket & SSE              │   │  • Saga & outbox pattern        │            ║
║  └─────────────────────────────────┘   └─────────────────────────────────┘            ║
║                                                      │                                ║
║  PHASE 5: DATA & CLOUD-NATIVE  [BAB 08-09]           │                                ║
║  ═══════════════════════════════                      ▼                                ║
║                                                                                       ║
║  ┌─────────────────────────────────┐   ┌─────────────────
