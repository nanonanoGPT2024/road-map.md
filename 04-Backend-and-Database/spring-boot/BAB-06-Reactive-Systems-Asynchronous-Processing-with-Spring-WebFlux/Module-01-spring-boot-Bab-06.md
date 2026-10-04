# Bab 06 Module 01: Reactive Systems & Asynchronous Processing with Spring WebFlux

---

## 01: Identitas Modul

* **Track:** Backend Engineering & Cloud-Native Architectures
* **Kategori:** 04-Backend-and-Database
* **Topik:** Reactive Programming, Non-blocking I/O, Event Loop Engine, Backpressure Handling
* **Level:** Advanced (L4/Principal Track)
* **Prasyarat:** Java 17/21+, Core Spring Framework, Concurrency Utilities (`java.util.concurrent`), Functional Programming (Lambda/Streams), Dasar-dasar Networking (TCP, HTTP/1.1 vs HTTP/2)
* **Alokasi Waktu:** 8 Jam (Teori Mendalam, Hands-on Lab, Performance Tuning)
* **Tech Stack:** 
  * Spring Boot 3.3+
  * Spring WebFlux
  * Project Reactor (Reactor Core 3.6+)
  * Netty 4.1+ (Epoll/KQueue transport)
  * R2DBC (Reactive Relational Database Connectivity - PostgreSQL Driver)
  * Micrometer & Micrometer Tracing (Otel Bridge)
  * BlockHound 1.0+

---

## 02: Learning Objectives

1. **Memahami Arsitektur Event-Driven Non-Blocking:** Menguraikan perbedaan mendasar antara model *Thread-per-Request* (Tomcat) dan *Event Loop Pattern* berbasis non-blocking I/O (Reactor Netty).
2. **Menguasai Abstraksi Project Reactor:** Mengimplementasikan pipeline pemrosesan data asinkron menggunakan publisher `Mono<T>` dan `Flux<T>` secara deterministik tanpa merusak reaktivitas pipeline.
3. **Menerapkan Backpressure Handling:** Mengonfigurasi strategi backpressure (`BUFFER`, `DROP`, `LATEST`, `ERROR`) untuk melindungi microservice dari *memory saturation* akibat produsen data yang agresif.
4. **Membangun Arsitektur Non-Blocking End-to-End:** Mengintegrasikan Spring WebFlux, WebClient, dan R2DBC untuk memastikan tidak ada pemblokiran thread pada layer komputasi maupun data access.
5. **Mendeteksi & Mengeliminasi Blocking Call:** Mengotomatiskan runtime verification menggunakan **BlockHound** untuk mendeteksi invokasi blocking I/O pada thread Event Loop.
6. **Menerapkan Observabilitas Reaktif:** Mengonfigurasi distributed tracing, konteks reaktif propagasi (*Reactor Context*), dan metrics streaming menggunakan Micrometer.

---

## 03: Concept Map Diagram ASCII

```
                                  [Reactive Streams Specification]
                                                 │
                   ┌─────────────────────────────┴─────────────────────────────┐
                   ▼                                                           ▼
         [Publisher Interface]                                       [Subscriber Interface]
                   │                                                           │
        ┌──────────┴──────────┐                                                │
        ▼                     ▼                                                │
    [Mono<T>]             [Flux<T>]                                            │
   (0..1 Item)          (0..N Items)                                           │
        │                     │                                                │
        └──────────┬──────────┘                                                │
                   │ (onSubscribe -> request(n)) <─────────────────────────────┘
                   ▼                               (Backpressure Signals)
       [Reactive Pipeline Operators]
       (map, flatMap, filter, zip, etc.)
                   │
                   ▼
     [Schedulers & Concurrency Engine]
    ┌──────────────┴──────────────┐
    ▼                             ▼
[Schedulers.parallel()]     [Schedulers.boundedElastic()]
(CPU-Bound Workload)       (Blocking/Legacy I/O Wrapping)
                   │
                   ▼
       [Underlying Runtime Engine]
        (Reactor Netty EventLoop)
                   │
    ┌──────────────┴──────────────┐
    ▼                             ▼
[R2DBC PostgreSQL Driver]   [WebClient Non-Blocking HTTP]
```

---

## 04: Mengapa Relevan

Secara historis, model MVC tradisional (Spring WebMVC) mengalokasikan satu thread untuk setiap request HTTP yang masuk (*thread-per-request*). Ketika request tersebut menunggu I/O dari basis data atau dependensi downstream HTTP, thread tersebut masuk ke status `WAITING`/`BLOCKED`, mengonsumsi stack memory (~1MB per thread di Linux 64-bit OS default) tanpa melakukan komputasi aktif. Pada traffic ribuan concurrent connection, model ini memicu context switching overhead tinggi, kehabisan pool thread, dan latensi tinggi (*Tail Latency Spikes*).

Spring WebFlux memecahkan masalah ini dengan mengadopsi model *Non-Blocking Reactive Streams* di atas Netty. Dengan memanfaatkan sejumlah kecil thread (biasanya setara dengan jumlah CPU core yang tersedia), Spring WebFlux menangani puluhan ribu koneksi konkuren secara efisien melalui mekanisme event notification (`epoll` di Linux atau `kqueue` di macOS). Hal ini memungkinkan pemanfaatan hardware secara maksimal, penurunan drastically cost infrastruktur cloud, dan stabilitas latensi tinggi pada skenario high-throughput I/O-intensive application.

---

## 05: Anatomi Konsep Inti

### 1. The Reactive Streams Spec: 4 Interfaces Fundamental

Reactive Streams adalah standar inisiatif bersama yang mendefinisikan standar pemrosesan stream asinkron non-blocking dengan backpressure:

* `Publisher<T>`: Penghasil data stream.
  ```java
  public interface Publisher<T> {
      void subscribe(Subscriber<? super T> s);
  }
  ```
* `Subscriber<T>`: Konsumen data stream.
  ```java
  public interface Subscriber<T> {
      void onSubscribe(Subscription s);
      void onNext(T t);
      void onError(Throwable t);
      void onComplete();
  }
  ```
* `Subscription`: Jembatan antara publisher dan subscriber untuk menegosiasikan aliran data dan backpressure.
  ```java
  public interface Subscription {
      void request(long n);
      void cancel();
  }
  ```
* `Processor<T, R>`: Komponen perantara yang bertindak sebagai `Subscriber` sekaligus `Publisher`.

### 2. Reactor Core Types: Mono vs Flux

* **`Mono<T>`**: Merepresentasikan nilai asinkron tunggal atau kosong ($[0..1]$ item). Cocok untuk operasi seperti `findById()`, HTTP POST response, atau operasi transaksional tunggal.
* **`Flux<T>`**: Merepresentasikan aliran data asinkron tak terbatas atau berurutan ($[0..N]$ item). Cocok untuk streaming real-time, query multi-records, atau event aggregation.

### 3. Concurrency Model: EventLoop vs Worker Threads

WebFlux mengandalkan Reactor Netty. Arsitektur runtime-nya menggunakan pola Non-blocking I/O multiplexing:
* **Selector/Boss Group**: Menerima koneksi TCP yang masuk dan mendaftarkannya ke channel non-blocking.
* **Worker Group (EventLoop Threads)**: Memproses event read/write dari channel yang telah dibuka. Karena satu thread menangani banyak koneksi konkuren, **thread ini tidak boleh diblokir oleh pemanggilan blocking API (seperti JDBC konvensional, `Thread.sleep()`, atau disk I/O sinkron)**.

### 4. Backpressure Handling

Mekanisme saat subscriber memberi tahu publisher seberapa banyak data yang dapat diproses melalui `Subscription.request(n)`. Jika publisher menghasilkan data lebih cepat daripada kemampuan pemrosesan subscriber, WebFlux menyediakan buffering/dropping strategies:
* `onBackpressureBuffer()`: Menyimpan elemen pada in-memory bounded buffer.
* `onBackpressureDrop()`: Membuang elemen baru jika subscriber tidak siap.
* `onBackpressureLatest()`: Hanya menyimpan data paling mutakhir, membuang data transisi.
* `onBackpressureError()`: Menghentikan stream dengan melemparkan `Exceptions.OverflowException`.

### 5. Schedulers & Thread Switching (`subscribeOn` vs `publishOn`)

* `publishOn(Scheduler)`: Mengubah context eksekusi untuk semua operator yang berada **setelah** deklarasi operator tersebut dalam rantai pemrosesan.
* `subscribeOn(Scheduler)`: Mengubah context thread tempat proses inisiasi data stream (*subscription*) dimulai, terlepas dari letak posisinya di dalam pipeline.

---

## 06: Panduan Implementasi Step-by-Step

### Step 1: Konfigurasi Maven Dependency (`pom.xml`)

Gunakan Spring Boot Starter WebFlux, Driver R2DBC, Reactor Core, dan BlockHound untuk verifikasi thread safety.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0" 
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 
         https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.3.0</version>
        <relativePath/>
    </parent>
    <groupId>com.enterprise.reactive</groupId>
    <artifactId>webflux-core-engine</artifactId>
    <version>1.0.0-SNAPSHOT</version>
    <name>webflux-core-engine</name>
    <description>Enterprise Reactive Pipeline Engine</description>

    <properties>
        <java.version>21</java.version>
        <blockhound.version>1.0.8.RELEASE</blockhound.version>
    </properties>

    <dependencies>
        <!-- Spring Boot Starters -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-webflux</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-r2dbc</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-validation</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-actuator</artifactId>
        </dependency>

        <!-- Reactive Drivers -->
        <dependency>
            <groupId>org.postgresql</groupId>
            <artifactId>r2dbc-postgresql</artifactId>
            <scope>runtime</scope>
        </dependency>

        <!-- BlockHound for Blocking Detection -->
        <dependency>
            <groupId>io.projectreactor.tools</groupId>
            <artifactId>blockhound</artifactId>
            <version>${blockhound.version}</version>
        </dependency>

        <!-- Observability -->
        <dependency>
            <groupId>io.micrometer</groupId>
            <artifactId>micrometer-registry-prometheus</artifactId>
        </dependency>
        <dependency>
            <groupId>io.micrometer</groupId>
            <artifactId>micrometer-tracing-bridge-otel</artifactId>
        </dependency>

        <!-- Testing -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>io.projectreactor</groupId>
            <artifactId>reactor-test</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>
    
    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
            </plugin>
        </plugins>
    </build>
</project>
```

### Step 2: Konfigurasi Application Properties (`application.yml`)

```yaml
server:
  port: 8443
  netty:
    connection-timeout: 5000ms
    idle-timeout: 10000ms

spring:
  r2dbc:
    url: r2dbc:postgresql://localhost:5432/reactive_db
    username: postgres_user
    password: postgres_secure_password
    pool:
      enabled: true
      initial-size: 10
      max-size: 30
      max-idle-time: 30m
      validation-query: SELECT 1

management:
  endpoints:
    web:
      exposure:
        include: health,metrics,prometheus
  metrics:
    distribution:
      percentiles-histogram:
        http.server.requests: true
```

---

## 07: Contoh Kasus Sederhana (Minimal Working Example)

Implementasi endpoint reaktif yang mengeksekusi operasi data stream tanpa memblokir thread.

```java
package com.enterprise.reactive.simple;

import org.springframework.boot.SpringApplication;
import org.