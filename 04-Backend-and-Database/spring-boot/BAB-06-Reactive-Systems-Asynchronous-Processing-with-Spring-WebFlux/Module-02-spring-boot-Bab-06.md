# Kurikulum Enterprise: Spring Boot Reactive Architecture & Production Engineering
**Jalur Pembelajaran:** 04-Backend-and-Database  
**Bab 06:** Reactive Systems & Asynchronous Processing with Spring WebFlux  
**Modul 02:** Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis Internal Netty & Project Reactor:** Membedakan siklus hidup I/O non-blocking berbasis *EventLoop*, alokasi memori `ByteBuf`, dan transmisi sinyal Reactive Streams (`onSubscribe`, `request`, `onNext`, `onError`, `onComplete`).
- **Mengimplementasikan Strategi Backpressure Lanjutan:** Menangani lonjakan beban (*traffic spikes*) menggunakan operator `onBackpressureBuffer`, `onBackpressureDrop`, `onBackpressureLatest`, serta *windowing/batching* berbasis window waktu dan ukuran buffer.
- **Membangun Pipeline Data Non-Blocking End-to-End dengan R2DBC:** Mengelola transaksi reaktif menggunakan `TransactionalOperator`, konfigurasi *connection pooling* (`r2dbc-pool`), dan mitigasi resiko *connection starvation*.
- **Menguasai Reactive Context & Distributed Tracing:** Mempropagasi state keamanan (`ReactiveSecurityContextHolder`) dan tracing context (Micrometer Observation, W3C Trace Context) melintasi batas thread *switch* (`publishOn`/`subscribeOn`).
- **Mendesain Resilient Reactive Microservices:** Mengintegrasikan Resilience4j Reactive Circuit Breaker, bulkhead, retry berbobot eksponensial dengan jitter, dan isolasi *thread pool* fallback.
- **Melakukan Diagnostik & Performance Tuning Tingkat Lanjut:** Mengidentifikasi dan memitigasi *EventLoop saturation*, kebocoran *direct memory* (Netty off-heap), serta mengonfigurasi parameter kernel OS untuk performa tinggi.

---

## 2. Prerequisites

Sebelum mempelajari modul ini, peserta wajib menguasai:
- **Core Reactor Abstractions:** Pemahaman operasional terhadap `Mono<T>` dan `Flux<T>`, operator dasar transformasi (`map`, `flatMap`, `concatMap`, `switchMap`).
- **Java Concurrency Fundamentals:** Memahami memori model Java (JMM), *Volatile semantics*, CAS (*Compare-And-Swap*), dan perbedaan thread kernel (OS thread) vs *Virtual Threads* vs *Green Threads*.
- **Networking & I/O Multiplexing:** Konsep I/O multiplexing tingkat OS (`epoll` pada Linux, `kqueue` pada macOS), model soket POSIX, dan cara kerja TCP Three-Way Handshake serta *Receive/Send Window Buffer*.
- **Spring Boot Ecosystem:** Konfigurasi dasar Spring Boot 3.x, dependency injection, dan logging framework (SLF4J/Logback).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Netty EventLoop Execution Model

Spring WebFlux secara default beroperasi di atas Netty. Arsitektur eksekusi Netty berbasis pada model **Single-Threaded EventLoop Multi-Core**:

```
+---------------------------------------------------------------------------------+
|                                OS Kernel Space                                  |
|   epoll_wait() / kqueue()                                                       |
+---------------------------------------+-----------------------------------------+
                                        | Event Notification (FD Read/Write Ready)
                                        v
+---------------------------------------------------------------------------------+
| Netty NioEventLoopGroup / EpollEventLoopGroup                                   |
|                                                                                 |
|  +--------------------------------+       +----------------------------------+  |
|  | EventLoop-1 (Thread-1)         |       | EventLoop-N (Thread-N)           |  |
|  |                                |       |                                  |  |
|  |  +--------------------------+  |       |  +----------------------------+  |  |
|  |  | Task Queue (MPSC Queue)  |  |       |  | Task Queue (MPSC Queue)    |  |  |
|  |  +--------------------------+  |       |  +----------------------------+  |  |
|  |  | Selector (epoll/kqueue)  |  |       |  | Selector (epoll/kqueue)    |  |  |
|  |  +--------------------------+  |       |  +----------------------------+  |  |
|  |  | ChannelPipeline Engine   |  |       |  | ChannelPipeline Engine     |  |  |
|  |  +--------------------------+  |       |  +----------------------------+  |  |
|  +--------------------------------+       +----------------------------------+  |
+---------------------------------------------------------------------------------+
```

- **Ukuran Thread Pool Default:** Netty mengalokasikan thread `EventLoop` sebanyak `Math.max(1, Runtime.getRuntime().availableProcessors() * 2)`.
- **Invariansi Thread Safety:** Setiap network connection (Channel) didaftarkan secara eksklusif ke **satu** `EventLoop` selama masa hidupnya. Ini mengeliminasi kebutuhan sinkronisasi muteks (`synchronized`, locks) pada level I/O network soket.
- **EventLoop Saturation Risk:** Jika eksekusi dalam `EventLoop` memanggil fungsi *blocking* (misal: JDBC konvensional, `Thread.sleep()`, kalkulasi hashing kriptografi berat), thread tersebut membeku. Akibatnya, seluruh ratusan atau ribuan koneksi soket lain yang terikat pada `EventLoop` yang sama akan mengalami *latency spike* drastis atau timeout total.

### 3.2 Reactive Streams Protocol: Mekanika Sinyal dan Backpressure Flow

Mekanika Reactive Streams (JSR-166 / Flow API) berjalan berdasarkan kontrol sinyal terbalik (*push-pull hybrid*). Data tidak dipompa secara buta oleh Publisher, melainkan ditarik berdasarkan kapasitas Subscriber:

```
 Subscriber                                                          Publisher
    |                                                                    |
    |------------------------ 1. subscribe(Subscriber) ---------------->|
    |                                                                    |
    |<----------------------- 2. onSubscribe(Subscription) ------------|
    |                                                                    |
    |------------------------ 3. Subscription.request(n) --------------->|
    |                         (Demand Signal: "Kirim n item")           |
    |                                                                    |
    |<----------------------- 4. onNext(item_1) -------------------------|
    |<----------------------- 5. onNext(item_2) ... [sampai n item] ----|
    |                                                                    |
    |-- 6. Subscription.request(m) ATAU Subscription.cancel() --------->|
    |                                                                    |
    |<-- 7. onComplete() ATAU onError(Throwable) ------------------------|
```

- **Mekanisme Backpressure:** Mengatur parameter `n` pada `Subscription.request(long n)`. Apabila `request(Long.MAX_VALUE)`, aliran berubah menjadi murni *push* (*unbounded demand*). Pada WebFlux, level transport (Netty) memetakan `request(n)` secara cerdas ke *TCP Receive Window*. Jika buffer lokal penuh, Netty menghentikan pembacaan frame dari soket kernel, menyebabkan TCP flow control menahan pengiriman paket oleh upstream client.

### 3.3 Schedulers, Thread Context Switching, dan Memory Allocations

Project Reactor menyediakan abstraksi `Schedulers` untuk mengalihkan eksekusi:
- **`Schedulers.immediate()`:** Mengeksekusi runnable langsung pada thread pemanggil saat ini.
- **`Schedulers.single()`:** Thread tunggal yang persisten untuk tugas background sekuensial.
- **`Schedulers.boundedElastic()`:** Thread pool dinamis berbasis kapasitas terikat (default: `10 * availableProcessors`, queue size: `100,000`). Digunakan khusus untuk membungkus library legasi atau panggilan I/O blocking.
- **`Schedulers.parallel()`:** Worker pool dengan jumlah thread sesuai jumlah core CPU, optimal untuk komputasi analitik atau validasi JSON berukuran gigantik.

**Perbedaan Kritis Antara `publishOn` dan `subscribeOn`:**

```
Flux.just("A", "B")                       // Thread X (Thread awal eksekusi assembly/subscription)
    .subscribeOn(Schedulers.boundedElastic()) // Mengubah thread tempat publisher mulai subscribe (Hingga ke hulu)
    .map(val -> val.toLowerCase())        // Dijalankan di Scheduler boundedElastic
    .publishOn(Schedulers.parallel())     // Mengubah thread untuk SELURUH downstream berikutnya
    .map(val -> val + "_processed")       // Dijalankan di Scheduler parallel
    .subscribe();
```

---

## 4. Why & What

### Mengapa Paradigma Reaktif Esensial di Skala Enterprise?
Pada arsitektur *Thread-per-Request* (Spring MVC klasik dengan Tomcat):
- Setiap request client memakan 1 thread kernel OS.
- Konsumsi memori stack thread default Java berkisar antara 512KB hingga 1MB per thread.
- Skala 10.000 koneksi concurrent idle (misalnya WebSocket, SSE, atau microservice downstream yang lambat) membutuhkan alokasi memori $\approx 10\text{ GB}$ hanya untuk alokasi thread stack, di luar beban context switching pada kernel scheduler.

Pada Spring WebFlux (Event-Driven Non-blocking):
- 10.000 koneksi concurrent dapat ditangani oleh thread sejumlah core CPU (misal: 8 atau 16 thread).
- Footprint memori stabil, CPU *cache locality* tetap terjaga, dan latensi p99 lebih konsisten di bawah saturasi beban I/O tinggi.

### Apa yang Terjadi di Bawah Kap Mesin Spring WebFlux?
WebFlux tidak menghilangkan latensi I/O downstream; WebFlux **menghilangkan biaya menunggu (blocking wait)**. Alih-alih thread CPU tidur (*idle waiting*) menanti respons soket jaringan basis data atau REST API pihak ketiga, thread tersebut dilepaskan kembali ke Netty `EventLoop` untuk memproses ratusan request lain. Ketika paket respons TCP tiba di kartu jaringan (NIC), kernel memicu interupsi hardware $\to$ OS membangkitkan sinyal `epoll` $\to$ Netty membungkus payload ke dalam `ByteBuf` $\to$ Reactor memicu pemanggilan `onNext()` pada pipeline reaktif.

---

## 5. How (Workflow Detail)

Alur eksekusi request masuk hingga respons keluar pada Spring WebFlux:

1. **TCP Connection Ingestion:** Klien menginisiasi koneksi TCP. OS Kernel meloloskan handshake dan memasukkannya ke accept queue.
2. **Netty Channel Initialization:** Boss `EventLoop` menerima koneksi, membungkusnya dalam instance `NioSocketChannel` (atau `EpollSocketChannel`), lalu mendaftarkannya ke Worker `EventLoop`.
3. **Pipeline Inbound Execution:** Worker thread mengeksekusi Netty `ChannelHandler` chains:
   - `HttpServerCodec`: Mendekode bytes dari TCP buffer menjadi `HttpRequest` parts.
   - `HttpTrafficHandler`: Menangani agregasi HTTP payload (bila dikonfigurasi) atau streaming `ByteBuf`.
4. **Adapter ke Spring WebFlux:** Netty `HttpServerRequest` diadaptasi menjadi Spring `ServerHttpRequest` dan `ServerWebExchange`.
5. **DispatcherHandler Routing:** `DispatcherHandler` memindai `HandlerMapping` (Router Function atau `@Controller`).
6. **Execution via HandlerAdapter:** Handler dieksekusi, menghasilkan objek `Mono<?>` atau `Flux<?>`.
7. **Downstream Subscription:** WebFlux melakukan `subscribe()` pada Publisher yang dikembalikan. Pada titik ini, pipeline bisnis, eksekusi query R2DBC, atau outbound WebClient diaktifkan.
8. **Asynchronous Streaming Response:** Data streaming (`onNext`) di-*encode* menjadi data buffer Netty dan dikirim kembali melalui kernel socket buffer. Setelah selesai, sinyal `onComplete()` memicu Netty untuk menutup atau me-reuse connection (Keep-Alive).

---

## 6. Analogy & Diagram ASCII

### Analogi Restoran: Tradisional vs. Reaktif

- **Model Servlet Konvensional (Thread-per-Request):**
  Restoran memiliki 100 pelayan untuk 100 meja. Setiap pelayan mendatangi satu meja, mencatat pesanan, pergi ke dapur, dan **berdiri diam di depan koki selama 20 menit** menunggu masakan selesai. Selama pelayan itu berdiri menunggu, tidak ada pelanggan baru yang bisa dilayani meskipun pelayan tersebut hanya menganggur. Bila ada 101 pelanggan datang bersamaan, pelanggan ke-101 harus antre di luar.

- **Model WebFlux Reaktif (EventLoop & Reactive Streams):**
  Restoran hanya memiliki 4 pelayan lincah (sejumlah core CPU) untuk 10.000 meja. Pelayan mencatat pesanan dari Meja 1, langsung menyerahkan tiket pesanan ke dapur dengan nomor meja (kemitraan asinkron), lalu **langsung berbalik melayani Meja 2, Meja 3, dan seterusnya**. Ketika koki menyelesaikan masakan Meja 1, koki membunyikan bel (*event notification*). Pelayan terdekat yang sedang tidak mencatat pesanan akan mengambil piring tersebut dan menyajikannya ke Meja 1.

### Diagram Arsitektur Internal: WebFlux Context & Engine

```
[ Client Request ]
       |
       v
+-----------------------------------------------------------------------+
| Netty Epoll / NIO Socket Channel (Worker EventLoop)                   |
|                                                                       |
|  +-----------------------------------------------------------------+  |
|  | ServerWebExchange (Mutated Attributes, Reactor Context)         |  |
|  +-----------------------------------------------------------------+  |
|                                |                                      |
|                                v                                      |
|  +-----------------------------------------------------------------+  |
|  | DispatcherHandler -> Controller / Functional Route              |  |
|  +-----------------------------------------------------------------+  |
|                                |                                      |
|                                v                                      |
|  +-----------------------------------------------------------------+  |
|  | Reactive Pipeline Execution Engine                              |  |
|  |                                                                 |  |
|  |   Mono/Flux Operator Chain                                      |  |
|  |      |                                                          |  |
|  |      v [publishOn(Schedulers.boundedElastic())]                 |  |
|  |   +----------------------------------------------------------+  |  |
|  |   | Outbound I/O (R2DBC Postgres Pool / Non-blocking Socket) |  |  |
|  |   +----------------------------------------------------------+  |  |
|  |      |                                                          |  |
|  |      v [Reactive Context Write: Security / OpenTelemetry Trace] |  |
|  |   +----------------------------------------------------------+  |  |
|  |   | ContextSnapshot.capture() & Propagate                    |  |  |
|  |   +----------------------------------------------------------+  |  |
|  +-----------------------------------------------------------------+  |
|                                |                                      |
|                                v                                      |
|  +-----------------------------------------------------------------+  |
|  | ChannelOutboundBuffer -> Flush to TCP Send Buffer               |  |
|  +-----------------------------------------------------------------+  |
+-----------------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Pipeline Dasar dengan Rate-Limiting & Context

Contoh ini menunjukkan penggunaan `ContextView` untuk ekstraksi Metadata User secara non-blocking tanpa `ThreadLocal`.

```java
package com.enterprise.reactive.basic;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Mono;
import reactor.util.context.Context;

@RestController
public class SimpleReactiveController {

    private static final String CONTEXT_KEY_USER_ID = "X-User-Id";

    @GetMapping("/api/v1/context-demo")
    public Mono<String> getContextualData() {
        return Mono.deferContextual(ctx -> {
            String userId = ctx.getOrDefault(CONTEXT_KEY_USER_ID, "Anonymous");
            return Mono.just("Secure Payload for User: " + userId);
        })
        .contextWrite(Context.of(CONTEXT_KEY_USER_ID, "USR-88219"));
    }
}
```

### 7.2 Practical Example: Enterprise-Grade Order Processing Pipeline

Contoh implementasi menyeluruh meliputi:
1. R2DBC Transaction Boundary menggunakan `TransactionalOperator`.
2. Resilience4j Circuit Breaker terpasang pada external microservice call via `WebClient`.
3. Backpressure handling dengan fallback strategy.
4. Distributed tracing propagation context.

#### Service Implementation

```java
package com.enterprise.reactive.order;

import io.github.resilience4j.circuitbreaker.CircuitBreakerRegistry;
import io.github.resilience4j.reactor.circuitbreaker.operator.CircuitBreakerOperator;
import io.netty.channel.ChannelOption;
import io.netty.handler