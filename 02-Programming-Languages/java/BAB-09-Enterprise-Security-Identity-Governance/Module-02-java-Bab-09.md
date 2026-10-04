# BAB 09: Enterprise Security, Identity & Governance
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis Internal Runtime Spring Security 6.x & Jakarta Security**: Membedah siklus hidup `SecurityFilterChain`, eksekusi rantai `DelegatingFilterProxy`, dan mekanisme resolusi autentikasi/otorisasi pada level JVM.
- **Mengarsiteksi Identity Propagation pada Java 21 Virtual Threads**: Menyelesaikan problem transmisi `SecurityContext` lintas Virtual Threads (Project Loom) tanpa memicu memory leak atau *carrier thread pinning*.
- **Mengimplementasikan Pola Phantom Token & Token Exchange (RFC 8693)**: Membangun gerbang API yang mentransformasikan Opaque Reference Token dari eksternal menjadi Cryptographically Signed JWT terenkripsi untuk konsumsi internal.
- **Membangun Fine-Grained Dynamic Authorization (ABAC/PBAC)**: Mengintegrasikan Policy Enforcement Point (PEP) berbasis Java dengan Policy Decision Point (PDP) eksternal seperti Open Policy Agent (OPA) menggunakan transport REST/gRPC berlatensi rendah.
- **Menerapkan Mutual TLS (mTLS) & Hardware Security Module (HSM/KMS)**: Mengonfigurasi layer transport Zero-Trust end-to-end serta operasi kriptografi asimetris menggunakan Java Cryptography Architecture (JCA/JCE) dan PKCS#11.
- **Memitigasi Vektor Serangan Enterprise**: Menetralkan Broken Object Level Authorization (BOLA/IDOR), Confused Deputy Problem, Algorithm Confusion, dan Signature Stripping melalui validasi berbasis *fail-closed*.

---

### 2. Prerequisites

Sebelum mempelajari modul ini, Anda wajib menguasai:
1. **JVM Memory Model & Concurrency**: Pemahaman mendalam tentang `ThreadLocal`, `InheritableThreadLocal`, *Memory Visibility*, serta mekanisme *Virtual Threads* (Java 21).
2. **Kriptografi Dasar & PKI**: Konsep X.509 Certificate, ASN.1, Asymmetric Signing (RSA, ECDSA Ed25519), Symmetric Ciphers (AES-256-GCM), Hashing (SHA-256, SHA-3), dan JWK/JWKS/JWT specification (RFC 7519).
3. **Core Spring Framework & Servlet Engine**: Pemahaman mendalam mengenai Jakarta Servlet Lifecycle, Spring Dependency Injection, Bean Lifecycle, dan AOP (Aspect Oriented Programming).
4. **Protokol Jaringan Lanjutan**: TLS 1.3 Handshake, HTTP/2 multiplexing, dan arsitektur Reverse Proxy/API Gateway.

---

### 3. Concept & Internal Architecture

#### 3.1. Anatomi Runtime Spring Security Filter Chain

Spring Security tidak bekerja melalui *magic*; arsitekturnya murni dibangun di atas standar Servlet Filters. Integrasi antara Web Container (Tomcat/Jetty) dan Spring ApplicationContext dijembatani oleh `DelegatingFilterProxy`.

```
[Incoming HTTP Request]
         │
         ▼
┌────────────────────────────────────────────────────────┐
│ Jakarta Servlet Engine (Tomcat / Jetty)               │
│                                                        │
│  ┌────────────────────────┐                            │
│  │ Standard Filter A      │                            │
│  └───────────┬────────────┘                            │
│              ▼                                         │
│  ┌────────────────────────┐                            │
│  │ DelegatingFilterProxy  │                            │
│  └───────────┬────────────┘                            │
└──────────────┼─────────────────────────────────────────┘
               │ targetBeanName = "springSecurityFilterChain"
               ▼
┌────────────────────────────────────────────────────────┐
│ Spring ApplicationContext (IoC)                       │
│                                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │ FilterChainProxy                                 │  │
│  │  │                                               │  │
│  │  ├─ SecurityFilterChain 1: /api/v1/auth/** (None)│  │
│  │  ├─ SecurityFilterChain 2: /api/v1/admin/**      │  │
│  │  └─ SecurityFilterChain 3: /** (Default)         │  │
│  │       │                                          │  │
│  │       ├─ HeaderWriterFilter                      │  │
│  │       ├─ CorsFilter                              │  │
│  │       ├─ CsrfFilter                              │  │
│  │       ├─ BearerTokenAuthenticationFilter         │  │
│  │       │    └─ AuthenticationManager              │  │
│  │       │         └─ JwtAuthenticationProvider     │  │
│  │       │              └─ JwtDecoder (JWKS)        │  │
│  │       ├─ SecurityContextHolderFilter             │  │
│  │       ├─ AnonymousAuthenticationFilter           │  │
│  │       ├─ ExceptionTranslationFilter              │  │
│  │       └─ AuthorizationFilter                     │  │
│  │            └─ AuthorizationManager (RBAC/ABAC)   │  │
│  └──────────────────────────────────────────────────┘  │
└──────────────────────┬─────────────────────────────────┘
                       │ Validated Authentication & Authorization
                       ▼
            [DispatcherServlet]
                       │
                       ▼
            [@RestController Controller Layer]
```

1. **`DelegatingFilterProxy`**: Servlet filter standar yang didaftarkan ke Web Application Context. Proxy ini mendelegasikan pemanggilan method `doFilter()` ke bean Spring bernama `springSecurityFilterChain`.
2. **`FilterChainProxy`**: Komponen orkestrator yang mengelola satu atau lebih `SecurityFilterChain`. Ia memilih rantai filter mana yang cocok dengan `HttpServletRequest` saat ini menggunakan `RequestMatcher`.
3. **`SecurityContextHolderFilter`**: Komponen modern (menggantikan `SecurityContextPersistenceFilter`) yang memuat dan menyimpan `SecurityContext` ke dalam `SecurityContextHolderStrategy`.
4. **`BearerTokenAuthenticationFilter`**: Mengekstrak Bearer token dari header `Authorization`, memanggil `AuthenticationManager`, dan jika valid, menginjeksikan objek `Authentication` yang telah diautentikasi ke dalam `SecurityContext`.
5. **`AuthorizationFilter`**: Filter terakhir dalam rantai filter Spring Security 6.x (menggantikan `FilterSecurityInterceptor`). Filter ini memanggil `AuthorizationManager<RequestAuthorizationContext>` untuk mengevaluasi apakah subjek memiliki izin mengakses resource target.

#### 3.2. SecurityContext Propagation pada Java 21 Virtual Threads

Secara historis, Spring Security menggunakan `ThreadLocalSecurityContextHolderStrategy` secara default:

```java
// Default internal storage:
private static final ThreadLocal<SecurityContext> contextHolder = new ThreadLocal<>();
```

Pada arsitektur *Platform Thread* (1:1 dengan OS Kernel Thread), `ThreadLocal` berfungsi optimal karena jumlah thread terbatas (misalnya, thread pool Tomcat berisi 200 thread). 

Namun, ketika mengaktifkan Java 21 Virtual Threads (`spring.threads.virtual.enabled=true`):
- Aplikasi dapat mengeksekusi jutaan virtual thread secara serentak.
- Menggunakan `InheritableThreadLocal` (`SecurityContextHolder.MODE_INHERITABLETHREADLOCAL`) menyalin referensi konteks ke setiap child thread baru. Dalam arsitektur reaktif atau multi-branching virtual thread, hal ini memicu overhead alokasi memori yang masif dan risiko kebocoran konteks antar-permintaan (*context cross-contamination*).
- Pola modern di enterprise menuntut migrasi menuju `ScopedValue` (JEP 446 / Java 21 Preview / Java 22+) atau isolasi eksplisit melalui `ContextSnapshot` (Micrometer Context Propagation API) untuk menjamin konteks keamanan tetap *immutable* dan terikat ketat pada siklus eksekusi tugas.

#### 3.3. Arsitektur Pola Phantom Token (Zero-Trust Edge-to-Core)

Mengekspos JWT langsung ke Single Page Application (SPA) atau Mobile Client memicu celah keamanan:
- Ukuran JWT membengkak (*network payload penalty*).
- Informasi internal sistem bocor melalui claims payload.
- Pencabutan token (*revocation*) seketika sulit dilakukan tanpa validasi stateful.

Pola **Phantom Token** menyelesaikan dilema ini:

```
[ Public Client ]
       │
       │ 1. Request with Opaque Token (e.g., 8e3c4b... random UUID)
       ▼
┌────────────────────────────────────────────────────────┐
│ API Gateway / Reverse Proxy (Edge Layer)               │
│                                                        │
│ 2. Introspect / Cache Check                            │
│ 3. Exchange Opaque Token ──► Authorization Server      │
│    (Or Redis Introspection Cache)                      │
│                                                        │
│ 4. Mint/Attach Signed Ephemeral JWT                    │
│    (Claims: sub, roles, org_id, exp: 2 mins)           │
└──────────────────────────┬─────────────────────────────┘
                           │
                           │ 5. Mutual TLS + Signed Short-Lived JWT
                           ▼
┌────────────────────────────────────────────────────────┐
│ Enterprise Java Microservices (Resource Server)        │
│                                                        │
│ - Validate Signature via JWKS (Cached In-Memory)       │
│ - Zero Network I/O for Token Validation                │
│ - Strict ABAC Authorization Engine                     │
└────────────────────────────────────────────────────────┘
```

#### 3.4. ABAC Menggunakan Open Policy Agent (OPA)

Role-Based Access Control (RBAC) gagal mengakomodasi kompleksitas domain modern (*role explosion*). Attribute-Based Access Control (ABAC) mengevaluasi 4 dimensi:
1. **Subject**: User ID, Department, Roles, Clearances.
2. **Resource**: Owner, Classification, Financial Amount, Region.
3. **Action**: Read, Update, Approve, Transfer.
4. **Environment**: Time-of-day, Geolocation IP, Client Certificate Fingerprint, Device Health.

Dalam arsitektur terdistribusi, evaluasi kebijakan didelegasikan ke **Open Policy Agent (OPA)** melalui query engine berbasis bahasa declarative **Rego**. Resource Server Java bertindak murni sebagai **Policy Enforcement Point (PEP)**, sedangkan OPA bertindak sebagai **Policy Decision Point (PDP)**.

---

### 4. Why & What

| Fitur / Pola | Pendekatan Naif / Tradisional | Pendekatan Enterprise Modern |
| :--- | :--- | :--- |
| **Penyimpanan Token** | State session berbasis database relasional / JSESSIONID terikat sticky-session. | Stateless Cryptographic Assertion (JWT/PASETO) terdistribusi dengan Edge Opaque Token. |
| **Otorisasi Data** | Pengecekan hardcoded `hasRole('ADMIN')` langsung di business logic layer. | Decoupled ABAC Engine (OPA/Rego) melalui dynamic security evaluation interceptor. |
| **Transport Layer** | Plain HTTP di internal network karena anggapan "internal network aman". | Strict Zero-Trust Mutual TLS (mTLS) antar microservice dengan rotasi sertifikat berkala via SPIFFE/SPIRE. |
| **Manajemen Kunci** | Private key RSA disimpan di file `application.yml` atau local filesystem (JKS). | Hardware Security Module (HSM via PKCS#11) atau Cloud KMS dengan Dynamic Envelope Encryption. |
| **Threading Security** | `ThreadLocal` statis tanpa *cleanup lifecycle hooks*, rentan memory leak saat reuse thread pool. | Context propagation abstraction aman untuk Java 21 Virtual Threads & Structured Concurrency. |

---

### 5. How: Alur Eksekusi Validasi Request Berbasis Zero Trust

Langkah-langkah komputasi yang dilewati oleh setiap request yang masuk ke Resource Server:

```
[Request Inbound]
   │
   ▼
[Phase 1: Transport Verification]
   ├─ TLS 1.3 Termination & Handshake Verification
   ├─ Client Certificate Extraction (mTLS)
   └─ SAN (Subject Alternative Name) Check against Internal Service Whitelist
   │
   ▼
[Phase 2: Security Filter Chain Entry]
   ├─ DelegatingFilterProxy delegates to SecurityFilterChain
   ├─ SecurityContextHolderFilter binds blank Context to Virtual Thread
   └─ CorsFilter & HeaderWriterFilter sanitize incoming & outgoing streams
   │
   ▼
[Phase 3: Cryptographic Token Decryption & Verification]
   ├─ BearerTokenAuthenticationFilter extracts JWT from HTTP Header
   ├─ JwtDecoder checks signature via Cached JWKS Public Key
   ├─ Cryptographic Verification: Validates 'alg' (RS256/ES256), prevents 'none' attacks
   ├─ Claims Verification: Checks 'exp' (Skew < 30s), 'nbf', 'iss', and 'aud'
   └─ Instantiates fully authenticated JwtAuthenticationToken
   │
   ▼
[Phase 4: Policy Enforcement Point (PEP) Processing]
   ├─ MethodSecurityInterceptor or AuthorizationFilter triggers PEP
   ├─ Context Builder aggregates Subject Claims, Target Domain Object, and Request Metadata
   ├─ PEP queries Local Sidecar OPA via High-Speed gRPC/HTTP Pipe
   ├─ OPA PDP evaluates Rego Policy: ALLOW or DENY
   └─ If DENY: Throws AccessDeniedException -> ExceptionTranslationFilter returns 403 Forbidden
   │
   ▼
[Phase 5: Controller & Business Layer Execution]
   ├─ Context available via SecurityContextHolder.getContext().getAuthentication()
   └─ Executes Enterprise Business Logic
```

---

### 6. Analogi & Diagram Arsitektur

#### Analogi Dunia Nyata: Imigrasi Bandara Internasional VVIP
1. **mTLS (Transport Layer)**: Pesawat yang mendarat harus memiliki transponder ICAO terotentikasi dan kode maskapai yang terdaftar di menara pengawas (hanya armada bersertifikat yang bisa mendarat di landasan pacu).
2. **Phantom Token (Edge Layer)**: Penumpang menunjukkan tiket *boarding pass* berkode batang sederhana (Opaque Token). Petugas memindai kode tersebut dan menerbitkan Paspor Diplomatik Tersegel dengan hologram anti-pemalsuan (Signed JWT).
3. **RBAC vs ABAC (Authorization)**:
   - *RBAC*: "Semua pemegang paspor diplomatik boleh masuk ruang VIP." (Beresiko: bagaimana jika diplomat membawa barang selundupan?)
   - *ABAC*: "Pemegang paspor diplomatik HANYA boleh masuk ruang VIP JIKA dia ditugaskan untuk penerbangan hari ini, membawa surat tugas sah untuk negara target, transit tidak melebihi 4 jam, dan tas diplomatiknya telah dipindai sensor biometrik."

#### Diagram Komprehensif Arsitektur Keamanan Enterprise

```
                                  EDGE BOUNDARY (Untrusted)
                                              │
                                              ▼
                                     ┌─────────────────┐
                                     │ Mobile App/SPA  │
                                     └────────┬────────┘
                                              │ HTTPS / Opaque Token
                                              ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ API GATEWAY CLUSTER (Edge Proxy)                                                       │
│                                                                                        │
│  ┌─────────────────────────┐     Introspect Token     ┌─────────────────────────────┐  │
│  │ Envoy / Spring Cloud Gtw├─────────────────────────►│ Enterprise IdP             │  │
│  │ (Token Exchange Engine) │◄─────────────────────────┤ (Keycloak / Okta / Ping)    │  │
│  └────────────┬────────────┘      Mint Signed JWT     └─────────────────────────────┘  │
└───────────────┼────────────────────────────────────────────────────────────────────────┘
                │
                │ mTLS (X.509 Subject Validation) + Short-Lived JWT (Internal Network)
                ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ ZERO-TRUST SERVICE MESH (Java 21 Enterprise Resource Server)                           │
│                                                                                        │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│  │ Spring Security 6.x Execution Sandbox                                            │  │
│  │                                                                                  │  │
│  │  ┌───────────────────────────┐      Fetch Keys     ┌──────────────────────────┐  │  │
│  │  │ NimbusJwtDecoder          ├────────────────────►│ Distributed JWKS Cache   │  │  │
│  │  │ (Signature & Claims Eval) │                     │ (In-Memory Caffeine)     │  │  │
│  │  └─────────────┬─────────────┘                     └──────────────────────────┘  │  │
│  │                ▼                                                                 │  │
│  │  ┌───────────────────────────┐                     ┌──────────────────────────┐  │  │
│  │  │ Policy Enforcement Point  ├────────────────────►│ OPA PDP Sidecar Daemon   │  │  │
│  │  │ (Spring Security PEP AOP) │◄────────────────────┤ (Evaluates Rego Engine)  │  │  │
│  │  └─────────────┬─────────────┘      Allow/Deny     └──────────────────────────┘  │  │
│  │                ▼                                                                 │  │
│  │  ┌───────────────────────────┐                                                   │  │
│  │  │ Core Banking / Domain     │                     ┌──────────────────────────┐  │  │
│  │  │ Service Logic             ├────────────────────►│ Hardware Security Module │  │  │
│  │  │ (Java 21 Virtual Threads) │  Sign/Decrypt Data  │ (HSM via PKCS#11 / KMS)  │  │  │
│  │  └───────────────────────────┘                     └──────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

### 7. Implementasi Kode Produksi

Berikut adalah implementasi sistem Resource Server enterprise lengkap menggunakan **Java 21** dan **Spring Security 6.x** dengan validasi JWT asimetris, penanganan Virtual Threads, verifikasi mTLS, dan Policy Enforcement Point (PEP) yang terhubung ke OPA.

#### 7.1. Konfigurasi `pom.xml` Dependencies

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
    <groupId>com.enterprise.security</groupId>
    <artifactId>enterprise-security-engine</artifactId>
    <version>1.0.0</version>
    <name>enterprise-security-engine</name>
    <description>Production Grade Security Engine</description>

    <properties>
        <java.version>21</java.version>
        <nimbus-jose-jwt.version>9.39.1</nimbus-jose-jwt.version>
        <caffeine.version>3.1.8</caffeine.version>
    </properties>

    <dependencies>
        <!-- Spring Boot Starters -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-security</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-oauth2-resource-server</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-aop</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-validation</artifactId>
        </dependency>

        <!-- High Performance Caching for JWKS & OPA decisions -->
        <dependency>
            <groupId>com.github.ben-manes.caffeine</groupId>
            <artifactId>caffeine</artifactId>
            <version>${caffeine.version}</version>
        </dependency>

        <!-- Nimbus Jose JWT Engine -->
        <dependency>
            <groupId>com.nimbusds</groupId>
            <artifactId>nimbus-jose-jwt</artifactId>
            <version>${nimbus-jose-jwt.version}</version>
        </dependency>

        <!-- DevTools & Annotations -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-configuration-processor</artifactId>
            <optional>true</optional>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>org.springframework.security</groupId>
            <artifactId>spring-security-test</artifactId>
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

#### 7.2. Konfigurasi Security Filter Chain & Validator Kriptografi

```java
package com.enterprise.security.config;

import com.enterprise.security.interceptor.MtlsCertificateValidationFilter;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.jwk.source.JWKSource;
import com.nimbusds.jose.jwk.source.RemoteJWKSet;
import com.nimbusds.jose.proc.JWSKeySelector;
import com.nimbusds.jose.proc.JWSVerificationKeySelector;
import com.nimbusds.jose.proc.SecurityContext;
import com.nimbusds.jwt.proc.ConfigurableJWTProcessor;
import com.nimbusds.jwt.proc.DefaultJWTProcessor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.convert.converter.Converter;
import org.springframework.security.authentication.AbstractAuthenticationToken;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.core.DelegatingOAuth2TokenValidator;
import org.springframework.security.oauth2.core.OAuth2Error;
import org.springframework.security.oauth2.core.OAuth2TokenValidator;
import org.springframework.security.oauth2.core.