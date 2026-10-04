# Enterprise Security & Identity Governance

---

## SEKSI 01 — IDENTITAS MODUL

* **Jalur Pembelajaran**: Java Enterprise Architect & Cloud-Native Security
* **Kategori**: `02-Programming-Languages`
* **Modul**: `Bab 09 Module 01`
* **Topik**: Enterprise Security & Identity Governance
* **Prasyarat**:
  * Penguasaan mendalam Java 21+ (*Virtual Threads*, *Record*, *Pattern Matching*, *Sealed Classes*).
  * Pemahaman arsitektur *Spring Framework 6.x* / *Spring Boot 3.x* dan *Jakarta EE*.
  * Konsep dasar kriptografi: *Symmetric/Asymmetric Encryption*, *Public Key Infrastructure* (PKI), *Digital Signature*, *Hashing* (SHA-256, Argon2id).
  * Pemahaman protokol web: HTTP/1.1, HTTP/2, TLS 1.3, RESTful API architecture.
* **Target Audience**: Senior Java Developers, Backend Architects, Security Engineers, Enterprise Solutions Architects.
* **Estimasi Waktu Penyelesaian**: 12 - 16 Jam (Teori, Analisis Kode Mendalam, dan Implementasi Laboratorium Mandiri).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta mampu:

1. **Menganalisis & Mengonfigurasi Arsitektur Keamanan Internal Java**: Menguasai siklus hidup eksekusi *Servlet Filter Chain*, delegasi *SecurityFilterChain* Spring Security 6.x, serta propagasi `SecurityContext` lintas thread (*Platform Threads* dan *Virtual Threads/Project Loom*).
2. **Mengimplementasikan Protokol Identitas Modern (OAuth 2.1 & OIDC)**: Merancang dan membangun *Stateless OAuth 2.1 Resource Server* dengan verifikasi tanda tangan asimetris (*JWKS/RSASSA-PKCS1-v1_5 / Ed25519*), manajemen rotasi kunci publik (*Key Rotation*), dan validasi klaim kriptografis tanpa ketergantungan *stateful database*.
3. **Membangun Sistem Otorisasi Berbutir Halus (*Fine-Grained Authorization*)**: Menerapkan paradigma *Attribute-Based Access Control* (ABAC) dan *Policy Enforcement Points* (PEP) menggunakan *Method Security*, evaluasi ekspresi *SpEL custom*, serta integrasi *Policy Decision Point* (PDP) berbasis konteks dinamis.
4. **Menerapkan Pertahanan Identitas Enterprise & Zero Trust**: Mengonfigurasi arsitektur *Mutual TLS* (mTLS) *end-to-end*, integrasi *Secure Credential Vault* (HashiCorp Vault), serta mitigasi serangan tingkat lanjut (*Timing Attacks, Token Substitution, Replay Attacks, Privilege Escalation*).
5. **Membangun Tata Kelola Identitas & Auditabilitas**: Menyusun subsistem *Identity Governance & Administration* (IGA) dengan dukungan SCIM 2.0 (*System for Cross-domain Identity Management*), audit *trail* terstruktur berbasis standar industri, dan mekanisme pembatalan token terdistribusi (*Distributed Token Revocation via Redis/Bloom Filters*).

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### 1. Pergeseran Paradigma: Dari *Perimeter Security* ke *Zero Trust Architecture*

Dalam arsitektur *monolith legacy*, sistem keamanan kerap menggunakan model *Castle-and-Moat*: perimeter luar dilindungi secara ketat melalui firewall/DMZ, namun jaringan internal diperlakukan sebagai zona tepercaya tanpa verifikasi granular (*implicit trust*). 

Dalam rekayasa sistem enterprise modern, mental model ini ditinggalkan sepenuhnya demi **Zero Trust Architecture (ZTA)**:

$$\text{Zero Trust Axiom: } \forall \text{ Request } R \implies \text{Verify Explicitly}(R) \land \text{Least Privilege}(R) \land \text{Assume Breach}(R)$$

Setiap panggilan jaringan mikro, *inter-service RPC*, maupun akses data internal wajib membuktikan identitasnya (*Authentication*), memvalidasi integritas muatannya (*Cryptographic Verification*), dan dievaluasi kelayakannya berdasarkan atribut kontekstual (*Contextual Authorization*) pada saat eksekusi (*Runtime*).

```
PERIMETER MODEL (LEGACY):
[ Internet ] ---> [ Firewall / WAF ] ---> [ Service A ] <---(No Auth)---> [ Service B ]
                                                  |                              |
                                                  +-------->(DB Intranet)<-------+

ZERO TRUST MODEL (ENTERPRISE STANDARD):
[ Internet ] ---> [ WAF / API Gateway ]
                         | (mTLS + JWT)
                         v
                  [ Service A ] (PEP) <---> [ PDP / Policy Engine ]
                         | (mTLS + Scoped Token Propagation)
                         v
                  [ Service B ] (PEP) <---> [ Local Token Validation + ABAC ]
                         | (mTLS + Dynamic DB Credentials via Vault)
                         v
                  [ Encrypted DB ]
```

### 2. Mental Model Arsitektur Keamanan Java

Keamanan dalam Java Virtual Machine (JVM) bukan sekadar tumpukan *interceptor* HTTP, melainkan serangkaian lapisan abstraksi terkontrol:
* **Java Cryptography Architecture (JCA)**: Fondasi primitif kriptografi (kunci, sertifikat, algoritma tanda tangan).
* **Servlet Filter Pipeline**: Lapisan isolasi berbasis *I/O Interception* sebelum kendali dialihkan ke dispatcher aplikasi.
* **Context Thread Confinement**: Pengikatan identitas pengguna ke eksekusi lokal thread aktif (`ThreadLocal` / `ScopedValue`), yang menuntut kehati-hatian ekstrem ketika bertransisi ke *Virtual Threads*.
* **Declarative vs Programmatic PEP**: Pemisahan tegas antara di mana aturan didefinisikan (*Policy Definition*) dan di mana aturan dieksekusi (*Policy Enforcement*).

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Diagram 1: Spring Security 6 Internal Filter Chain & Execution Flow

Berikut adalah arsitektur internal alur eksekusi sebuah *request* HTTP yang masuk ke dalam runtime Java Spring Security hingga mencapai metode bisnis:

```
[ Inbound HTTP Request ]
       |
       v
+-----------------------------------------------------------------------------+
| Jakarta Servlet Container (Tomcat / Jetty / Undertow)                       |
|                                                                             |
|  +-----------------------------------------------------------------------+  |
|  | DelegatingFilterProxy (Bridge dari Servlet API ke Spring ApplicationContext)|
|  +-----------------------------------------------------------------------+  |
|         |                                                                   |
|         v                                                                   |
|  +-----------------------------------------------------------------------+  |
|  | FilterChainProxy (Mengevaluasi SecurityFilterChain yang sesuai)        |  |
|  +-----------------------------------------------------------------------+  |
|         |                                                                   |
|         v                                                                   |
|  +-----------------------------------------------------------------------+  |
|  | SecurityFilterChain                                                   |  |
|  |                                                                       |  |
|  |  1. CorsFilter / CsrfFilter                                           |  |
|  |  2. HeaderWriterFilter (CSP, HSTS, X-Frame-Options)                    |  |
|  |  3. DistributedTokenRevocationFilter (Custom Blacklist / Redis Check) |  |
|  |  4. BearerTokenAuthenticationFilter (OAuth2 JWT Decoder)               |  |
|  |     +--> Ekstrak Bearer Token dari Header Authorization                |  |
|  |     +--> Panggil JwtAuthenticationProvider / NimbusJwtDecoder          |  |
|  |     +--> Verifikasi JWKS Signature (Asymmetric RSA/ECDSA)              |  |
|  |     +--> Validasi exp, nbf, iss, aud claims                           |  |
|  |     +--> Custom JwtAuthenticationConverter (Claims -> GrantedAuth)     |  |
|  |     +--> Buat JwtAuthenticationToken                                   |  |
|  |     +--> SecurityContextHolder.getContext().setAuthentication(auth)    |  |
|  |  5. ExceptionTranslationFilter (Tangkap AuthException / AccessDenied) |  |
|  |  6. AuthorizationFilter (Request-level Authorization via SpEL)         |  |
|  +-----------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------+
       |
       v
+-----------------------------------------------------------------------------+
| DispatcherServlet & Spring MVC Controller Layer                             |
|                                                                             |
|  +-----------------------------------------------------------------------+  |
|  | AOP MethodSecurityInterceptor / AuthorizationManagerBeforeMethodInterceptor |
|  |                                                                       |  |
|  |  Evaluasi: @PreAuthorize("hasPermission(#account, 'TRANSFER_FUNDS')") |  |
|  |     +--> Delegasi ke Custom PermissionEvaluator / ABAC PDP Engine     |  |
|  |     +--> Evaluasi Atribut Subjek, Sumber Daya, Aksi, & Lingkungan     |  |
|  |     +--> Putusan: GRANTED atau ACCESS_DENIED                          |  |
|  +-----------------------------------------------------------------------+  |
|         | (Jika GRANTED)                                                    |
|         v                                                                   |
|  +-----------------------------------------------------------------------+  |
|  | Service Layer Execution (Domain Business Logic)                       |  |
|  +-----------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------+
```

### Diagram 2: Alur OIDC / OAuth 2.1 Token Validation & ABAC Decision Flow

```
+-----------+          +--------------------+          +---------------------+          +-------------------+
|  Client   |          | API Gateway / PEP  |          | JWKS Identity Prov. |          | ABAC PDP (Engine) |
+-----------+          +--------------------+          +---------------------+          +-------------------+
      |                          |                                |                               |
      | 1. HTTP POST /transfer   |                                |                               |
      |    Bearer: <JWT>         |                                |                               |
      |------------------------->|                                |                               |
      |                          | 2. Periksa Cache Kunci Publik  |                               |
      |                          |    (Kid Cache Lookup)          |                               |
      |                          |--------------------------------+                               |
      |                          | (Jika cache miss / rotasi):    |                               |
      |                          | 3. GET /.well-known/jwks.json  |                               |
      |                          |------------------------------->|                               |
      |                          | 4. Return Public Key Set       |                               |
      |                          |<-------------------------------|                               |
      |                          |                                                                |
      |                          | 5. Verifikasi Signature Kriptografi, Exp, Iss, Aud             |
      |                          | 6. Cek Token Blacklist Status di Distributed Redis Store       |
      |                          |                                                                |
      |                          | 7. Request Evaluasi Kebijakan (Konteks Transfer)               |
      |                          |--------------------------------------------------------------->|
      |                          |                                | 8. Analisis Atribut:          |
      |                          |                                |    - Subjek: Risk Score, Role |
      |                          |                                |    - Objek: Account Balance   |
      |                          |                                |    - Env: Jam Kerja, GeoIP    |
      |                          |                                | 9. Keputusan: PERMIT / DENY   |
      |                          | 10. Return Keputusan Kebijakan |<------------------------------|
      |                          |<-------------------------------|                               |
      |                          |                                                                |
      |                          | 11. Eksekusi Transaksi Finansial                               |
      | 12. HTTP 200 OK / 403    |                                                                |
      |<-------------------------|                                                                |
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Arsitektur `SecurityContextHolder` dan Implikasinya pada Virtual Threads

Secara default, Spring Security menyimpan status otentikasi dalam `SecurityContextHolder` yang didukung oleh strategi penyimpanan internal (`SecurityContextHolderStrategy`).

```
SecurityContextHolder
    ├── SecurityContextHolderStrategy (Interface)
            ├── ThreadLocalSecurityContextHolderStrategy (Default)
            ├── InheritableThreadLocalSecurityContextHolderStrategy
            ├── GlobalSecurityContextHolderStrategy
            └── Custom Strategy (e.g., ScopedValue-backed strategy)
```

* **`ThreadLocalSecurityContextHolderStrategy`**: Mengikat `SecurityContext` ke satu `Thread` OS spesifik menggunakan `java.lang.ThreadLocal`.
* **Dilema Virtual Threads (Java 21 / Project Loom)**: Virtual Threads bersifat murah dan dirancang untuk dibuat-lalu-buang (*ephemeral*). Menggunakan `InheritableThreadLocal` pada Virtual Threads menyebabkan:
  1. *Memory leak* masif jika context membawa graf objek yang besar karena Virtual Threads dibuat jutaan kali.
  2. Beban overhead alokasi struktur data internal thread.
* **Strategi Enterprise Modern**: Mempertahankan `MODE_THREADLOCAL` dengan pembersihan deterministik via `finally` block pada boundary filter, atau memanfaatkan delegasi eksekusi berbasis `DelegatingSecurityContextExecutor` dan Java 21 `ScopedValue` pada lapisan internal framework.

### 2. Delegasi Filter Servlet: `DelegatingFilterProxy` ke `FilterChainProxy`

1. **`DelegatingFilterProxy`**: Merupakan filter servlet standar Jakarta (`jakarta.servlet.Filter`) yang terdaftar pada kontainer servlet (misal: Tomcat). Filter ini tidak memiliki logika keamanan langsung; tugasnya hanya mencari Spring Bean bernama `springSecurityFilterChain` di dalam `WebApplicationContext` dan mendelegasikan pemanggilan metode `doFilter()`.
2. **`FilterChainProxy`**: Inti dari Spring Security runtime. Mempertahankan daftar `SecurityFilterChain` yang dipetakan menggunakan `RequestMatcher`. `FilterChainProxy` bertindak sebagai *single entry point* yang menangani:
   * *Security matching*: Menentukan chain mana yang relevan dengan path dan header request.
   * *Context cleanup*: Memastikan `SecurityContextHolder.clearContext()` dipanggil setelah request selesai dieksekusi guna mencegah *thread contamination*.
   * *HttpFirewall*: Menolak request berbahaya (contoh: *path traversal* `./..`, karakter *semicolon* `;` untuk bypass URL routing).

### 3. Java Cryptography Architecture (JCA) Provider Mechanism

Di balik validasi tanda tangan JWT dan mTLS, JVM bekerja melalui JCA. Engine kriptografi Java berbasis arsitektur *Service Provider Interface* (SPI):

$$\text{Security} \xrightarrow{\text{getInstance("RSA")}} \text{Provider (e.g., SUN, SunJCE, BouncyCastle, SunPKCS11)}$$

* Kunci publik diuraikan ke dalam implementasi `java.security.interfaces.RSAPublicKey` atau `ECPublicKey`.
* Validasi tanda tangan didelegasikan ke `java.security.Signature` dengan algoritma misalnya `SHA256withRSA` atau `Ed25519`.
* Sertifikat x509 untuk mTLS divalidasi oleh `PKIX` `CertPathValidator`, yang memverifikasi rantai sertifikat (*Certificate Chain*) hingga ke *Root Trust Anchor* yang tersimpan di dalam Java `TrustStore`.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Spesifikasi OAuth 2.1 & OpenID Connect (OIDC)

OAuth 2.1 menyederhanakan dan memperketat spesifikasi OAuth 2.0 dengan mengeliminasi elemen-elemen yang rentan secara kriptografis:
* **PKCE (Proof Key for Code Exchange) Diwajibkan**: Menghilangkan serangan intersepsi otorisasi pada seluruh tipe klien (RFC 7636).
* **Deprecasi Resource Owner Password Credentials (ROPC)**: Mencegah aplikasi klien menangani kredensial mentah pengguna.
* **Deprecasi Implicit Flow**: Dilarang sepenuhnya karena risiko kebocoran token pada fragmen URL browser. Digantikan oleh Authorization Code Flow + PKCE.
* **Redirect URI Strict Matching**: Menghindari *open redirector exploits*.

Struktur Token Identitas OIDC vs Access Token:
* **ID Token (OIDC)**: Format JWT yang ditujukan kepada *Client* untuk konsumsi informasi identitas pengguna (*Subject Authentication Assertion*).
* **Access Token (OAuth 2.1)**: Ditujukan kepada *Resource Server* (API) sebagai bukti izin (*Authorization Artifact*), dapat berformat JWT atau *opaque token* terenkripsi.

### 2. Kriptografi Asimetris JWT: JWKS & Rotasi Kunci

Dalam arsitektur *stateless enterprise*, Resource Server tidak melakukan pemanggilan RPC ke Authorization Server untuk setiap request (*Token Introspection* RFC 7662), melainkan memvalidasi tanda tangan JWT secara lokal menggunakan pasangan kunci asimetris.

$$\text{Sign}(\text{Header} \parallel \text{Payload}, K_{\text{private}}) \implies \text{Signature}$$
$$\text{Verify}(\text{Header} \parallel \text{Payload}, \text{Signature}, K_{\text{public}}) \implies \text{Boolean (Valid/Invalid)}$$

* **JWKS (JSON Web Key Set - RFC 7517)**: Endpoint HTTP yang mengekspos kunci publik Authorization Server dalam representasi JSON standar.
* **Header `kid` (Key ID)**: Bagian dari JWT Header yang memberi tahu Resource Server kunci publik mana dari JWKS yang digunakan untuk menandatangani token tersebut.
* **Mekanisme Rotasi Kunci**: Authorizer menerbitkan kunci baru dengan `kid` baru sebelum kunci lama kedaluwarsa. Resource Server harus memiliki cache cerdas: jika menemukan `kid` yang tidak dikenal, cache di-*refresh* secara terkontrol (dengan batasan laju/*rate limit* untuk menghindari DoS) guna mengambil kunci publik terbaru.

### 3. Fine-Grained Authorization: RBAC vs ABAC

* **Role-Based Access Control (RBAC)**: Statis. Hak akses ditentukan berdasarkan peran (`ROLE_ADMIN`, `ROLE_TELLER`). 
  * *Kelemahan*: Mengakibatkan *Role Explosion* (misal: `ROLE_TELLER_BRANCH_A_MAX_10M`).
* **Attribute-Based Access Control (ABAC - NIST SP 800-162)**: Dinamis. Keputusan izin adalah fungsi logis dari empat dimensi atribut:

$$\text{Decision} = f(\text{Subject Attributes}, \text{Resource Attributes}, \text{Action Attributes}, \text{Environment Attributes})$$

1. **Subject**: User ID, Departemen, Tingkat Izin, Skor Risiko Fraud, Lokasi Kantor.
2. **Resource**: Tipe Akun, Saldo, Status Kepemilikan, Batas Likuiditas.
3. **Action**: `TRANSFER`, `APPROVE`, `READ_SENSITIVE_PII`.
4. **Environment**: Waktu Akses, Jaringan Asal (mTLS Verified), Lokasi Geografis (GeoIP), Status Darurat Sistem.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi *Production-Ready* dari **Stateless OAuth 2.1 Resource Server** pada Spring Boot 3.3+ / Java 21 yang mengintegrasikan validasi asimetris JWKS, konversi *custom claims*, dan proteksi filter chain yang ketat.

### File 1: `SecurityConfiguration.java`

```java
package com.enterprise.security.config;

import com.enterprise.security.converter.EnterpriseJwtAuthenticationConverter;
import com.enterprise.security.filter.DistributedTokenRevocationFilter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.convert.converter.Converter;
import org.springframework.http.HttpMethod;
import org.springframework.security.authentication.AbstractAuthenticationToken;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.oauth2.server.resource.web.authentication.BearerTokenAuthenticationFilter;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.header.writers.ReferrerPolicyHeaderWriter;

import java.time.Duration;

@Configuration
@EnableWebSecurity
@EnableMethodSecurity(prePostEnabled = true, securedEnabled = true, jsr250Enabled = true)
public class SecurityConfiguration {

    private final DistributedTokenRevocationFilter revocationFilter;
    private final EnterpriseSecurityProperties securityProperties;

    public SecurityConfiguration(DistributedTokenRevocationFilter revocationFilter,
                                 EnterpriseSecurityProperties securityProperties) {
        this.revocationFilter = revocationFilter;
        this.securityProperties = securityProperties;
    }

    @Bean
    public SecurityFilterChain enterpriseSecurityFilterChain(
            HttpSecurity http,
            Converter<Jwt, ? extends AbstractAuthenticationToken> jwtAuthenticationConverter,
            JwtDecoder jwtDecoder) throws Exception {

        http
            // 1. Matikan proteksi CSRF karena arsitektur API sepenuhnya stateless menggunakan Bearer Tokens
            .csrf(AbstractHttpConfigurer::disable)

            // 2. Matikan manajemen state session pada kontainer servlet (Stateless API)
            .sessionManagement(session -> 
                session.sessionCreationPolicy(SessionCreationPolicy.STATELESS)
            )

            // 3. Konfigurasi Security Headers berstandar Enterprise
            .headers(headers -> headers
                .contentSecurityPolicy(csp -> csp.policyDirectives("default-src 'self'; frame-ancestors 'none';"))
                .frameOptions(frameOptions -> frameOptions.deny())
                .httpStrictTransportSecurity(hsts -> hsts
                    .includeSubDomains(true)
                    .maxAgeSeconds(31536000)
                    .preload(true)
                )
                .referrerPolicy(referrer -> 
                    referrer.policy(ReferrerPolicyHeaderWriter.ReferrerPolicy.STRICT_ORIGIN_WHEN_CROSS_ORIGIN)
                )
            )

            // 4. Konfigurasi Otorisasi Jalur HTTP (Request-Level Authorization)
            .authorizeHttpRequests(auth -> auth
                .requestMatchers(HttpMethod.GET, "/actuator/health", "/actuator/info").permitAll()
                .requestMatchers(HttpMethod.OPTIONS, "/**").permitAll()
                .requestMatchers("/api/v1/public/**").permitAll()
                .requestMatchers("/api/v1/admin/**").hasRole("ENTERPRISE_ADMIN")
                .anyRequest().authenticated()
            )

            // 5. Registrasi Filter Custom Pembatalan Token Terdistribusi sebelum Filter Autentikasi Inti
            .addFilterBefore(revocationFilter, BearerTokenAuthenticationFilter.class)

            // 6. Konfigurasi OAuth 2.0 Resource Server dengan Custom Converter
            .oauth2ResourceServer(oauth2 -> oauth2
                .jwt(jwt -> jwt
                    .decoder(jwtDecoder)
                    .jwtAuthenticationConverter(jwtAuthenticationConverter)
                )
            );

        return http.build();
    }

    @Bean
    public Converter<Jwt, ? extends AbstractAuthenticationToken> jwtAuthenticationConverter() {
        return new EnterpriseJwtAuthenticationConverter();
    }

    @Bean
    public JwtDecoder jwtDecoder() {
        NimbusJwtDecoder jwtDecoder = NimbusJwtDecoder
                .withJwkSetUri(securityProperties.getJwksUri())
                .build();

        // Validasi toleransi skew waktu kriptografis (maksimum 60 detik)
        jwtDecoder.setJwtValidator(
                EnterpriseJwtValidators.createDefaultWithIssuerAndSkew(
                        securityProperties.getIssuer(),
                        Duration.ofSeconds(60)
                )
        );

        return jwtDecoder;
    }
}
```

### File 2: `EnterpriseJwtAuthenticationConverter.java`

```java
package com.enterprise.security.converter;

import com.enterprise.security.model.EnterpriseUserPrincipal;
import org.springframework.core.convert.converter.Converter;
import org.springframework.lang.NonNull;
import org.springframework.security.authentication.AbstractAuthenticationToken;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.jwt.Jwt;

import java.util.Collection;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;
import java.util.stream.Stream;

public class EnterpriseJwtAuthenticationConverter implements Converter<Jwt, AbstractAuthenticationToken> {

    private static final String REALM_ACCESS_CLAIM = "realm_access";
    private static final String RESOURCE_ACCESS_CLAIM = "resource_access";
    private static final String ROLES_CLAIM = "roles";
    private static final String TENANT_ID_CLAIM = "tenant_id";
    private static final String RISK_TIER_CLAIM = "risk_tier";
    private static final String DEPARTMENT_CLAIM = "department";

    @Override
    public AbstractAuthenticationToken convert(@NonNull Jwt source) {
        Collection<GrantedAuthority> authorities = extractEnterpriseAuthorities(source);
        
        EnterpriseUserPrincipal principal = new EnterpriseUserPrincipal(
                source.getSubject(),
                source.getClaimAsString("preferred_username"),
                source.getClaimAsString(TENANT_ID_CLAIM),
                source.getClaimAsString(DEPARTMENT_CLAIM),
                source.getClaimAsString(RISK_TIER_CLAIM),
                authorities,
                source.getClaims()
        );

        return new UsernamePasswordAuthenticationToken(principal, source, authorities);
    }

    @SuppressWarnings("unchecked")
    private Collection<GrantedAuthority> extractEnterpriseAuthorities(Jwt jwt) {
        // Ekstraksi Realm Roles
        List<String> realmRoles = Collections.emptyList();
        Map<String, Object> realmAccess = jwt.getClaimAsMap(REALM_ACCESS_CLAIM);
        if (realmAccess != null && realmAccess.containsKey(ROLES_CLAIM)) {
            realmRoles = (List<String>) realmAccess.get(ROLES_CLAIM);
        }

        // Ekstraksi Scopes (Standard OAuth2)
        List<String> scopes = jwt.getClaimAsStringList("scope");
        if (scopes == null) {
            scopes = Collections.emptyList();
        }

        Stream<GrantedAuthority> roleAuthorities = realmRoles.stream()
                .map(role -> new SimpleGrantedAuthority("ROLE_" + role.toUpperCase()));

        Stream<GrantedAuthority> scopeAuthorities = scopes.stream()
                .map(scope -> new SimpleGrantedAuthority("SCOPE_" + scope));

        return Stream.concat(roleAuthorities, scopeAuthorities)
                .collect(Collectors.toUnmodifiableSet());
    }
}
```

### File 3: `EnterpriseUserPrincipal.java`

```java
package com.enterprise.security.model;

import org.springframework.security.core.AuthenticatedPrincipal;
import org.springframework.security.core.GrantedAuthority;

import java.io.Serializable;
import java.util.Collection;
import java.util.Collections;
import java.util.Map;
import java.util.Objects;

public final class EnterpriseUserPrincipal implements AuthenticatedPrincipal, Serializable {

    private final String userId;
    private final String username;
    private final String tenantId;
    private final String department;
    private final String riskTier;
    private final Collection<GrantedAuthority> authorities;
    private final Map<String, Object> attributes;

    public EnterpriseUserPrincipal(String userId,
                                   String username,
                                   String tenantId,
                                   String department,
                                   String riskTier,
                                   Collection<GrantedAuthority> authorities,
                                   Map<String, Object> attributes) {
        this.userId = Objects.requireNonNull(userId, "userId must not be null");
        this.username = username != null ? username : userId;
        this.tenantId = Objects.requireNonNull(tenantId, "tenantId must not be null");
        this.department = department;
        this.riskTier = riskTier != null ? riskTier : "STANDARD";
        this.authorities = authorities != null ? Collections.unmodifiableCollection(authorities) : Collections.emptyList();
        this.attributes = attributes != null ? Collections.unmodifiableMap(attributes) : Collections.emptyMap();
    }

    @Override
    public String getName() {
        return this.userId;
    }

    public String getUserId() { return userId; }
    public String getUsername() { return username; }
    public String getTenantId() { return tenantId; }
    public String getDepartment() { return department; }
    public String getRiskTier() { return riskTier; }
    public Collection<GrantedAuthority> getAuthorities() { return authorities; }
    public Map<String, Object> getAttributes() { return attributes; }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi teknis terperinci atas komponen arsitektur pada Seksi 07:

### 1. `SecurityConfiguration.java`
* **Baris 24**: `@EnableMethodSecurity(prePostEnabled = true, securedEnabled = true, jsr250Enabled = true)` mengaktifkan mesin Spring AOP untuk mengintersepsi pemanggilan metode Java sebelum (*Pre*) dan sesudah (*Post*) eksekusi berbasis anotasi `@PreAuthorize`, `@Secured`, atau `@RolesAllowed`.
* **Baris 41**: `.csrf(AbstractHttpConfigurer::disable)` — Cross-Site Request Forgery (CSRF) dinonaktifkan secara aman karena komunikasi antarmuka API menggunakan skema *stateless Bearer authentication* yang kebal terhadap eksploitasi ambient credentials berbasis cookie browser.
* **Baris 44-46**: `.sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))` — Menginstruksikan kontainer servlet untuk *tidak pernah* mengalokasikan objek `HttpSession` di memori JVM. Setiap request harus membawa bukti otentikasi mandiri.
* **Baris 49-59**: Konfigurasi header pertahanan browser defensif:
  * `Content-Security-Policy`: Mencegah eksekusi script injeksi dan pemuatan resource tidak sah.
  * `HSTS` (31536000 detik = 1 tahun): Memaksa *user agent* berkomunikasi secara eksklusif melalui enkripsi TLS.
* **Baris 69**: `.addFilterBefore(revocationFilter, BearerTokenAuthenticationFilter.class)` — Memposisikan filter pencabutan token terdistribusi *tepat sebelum* parsing JWT standar dimulai. Jika token teridentifikasi ada di daftar hitam (misal: akibat sesi di-logout paksa), filter memutus pipeline tanpa membuang siklus CPU untuk verifikasi kriptografi yang lebih berat.
* **Baris 89-98**: `NimbusJwtDecoder.withJwkSetUri(...)` — Membangun instance decoder yang memegang cache thread-safe dari *Public Key Set* otoritas identitas, diverifikasi secara berkala dengan mematuhi spesifikasi toleransi skew waktu (`Duration.ofSeconds(60)`).

### 2. `EnterpriseJwtAuthenticationConverter.java`
* **Baris 27**: Mengonversi kontrak `Jwt` mentah dari engine parsing Nimbus ke domain model kuat `EnterpriseUserPrincipal`.
* **Baris 44-63**: Mengekstraksi struktur nested JSON (`realm_access.roles`) yang merupakan format standar Identity Provider enterprise seperti Keycloak/RedHat SSO, serta mengubahnya menjadi representasi standar Spring Security `GrantedAuthority` dengan prefix `ROLE_`.
* **Baris 38**: Mengembalikan instance `UsernamePasswordAuthenticationToken` yang membungkus subjek kustom, token asli, dan hak akses yang telah dinormalisasi.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: Multi-Tenant Core Banking System (Global Settlement Service)

Sebuah bank multinasional membangun subsistem *Cross-Border Dynamic Wire Transfer*. Sistem ini memiliki persyaratan keamanan tingkat tinggi:
1. **Multi-Tenancy Isolation**: Setiap panggilan API harus divalidasi bahwa `tenant_id` pada JWT cocok dengan rekening sumber mutasi bank. Rekening dari Tenant A tidak boleh diakses oleh Teller dari Tenant B dalam kondisi apa pun (*Strict Multi-Tenant Confinement*).
2. **Dynamic ABAC Authorization**:
   * Transaksi di bawah **\$100,000 USD** dapat disetujui langsung oleh user dengan role `TELLER` pada jam kerja operasional (08:00 - 17:00 UTC).
   * Transaksi sebesar **\$100,000 USD hingga \$1,000,000 USD** membutuhkan role `SENIOR_TELLER` dan verifikasi skor risiko pengguna (`risk_tier` == `LOW`).
   * Transaksi di atas **\$1,000,000 USD** atau transaksi di luar jam operasional membutuhkan otorisasi ganda (*Maker-Checker Policy*) dan level step-up authentication.
3. **Instant Token Invalidation**: Jika tim Cyber Threat Intelligence mendeteksi anomali fraud pada sesi Teller, token JWT subjek tersebut harus dapat dibatalkan seketika pada kluster microservices terdistribusi dalam latensi sub-milidetik (tanpa menunggu kedaluwarsa JWT exp).

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi sistematis lengkap dari skenario Core Banking di atas.

### File 1: DTO Domain `TransferRequest.java`

```java
package com.enterprise.banking.dto;

import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.math.BigDecimal;

public record TransferRequest(
        @NotBlank(message = "Source account must not be blank")
        String sourceAccountNumber,

        @NotBlank(message = "Destination account must not be blank")
        String destinationAccountNumber,

        @NotNull(message = "Transfer amount is required")
        @DecimalMin(value = "0.01", inclusive = true, message = "Amount must be strictly positive")
        BigDecimal amount,

        @NotBlank(message = "Currency must be specified")
        @Size(min = 3, max = 3, message = "Currency must be a valid 3-letter ISO-4217 code")
        String currency,

        @NotBlank(message = "Tenant identifier is required")
        String targetTenantId
) {}
```

### File 2: Custom ABAC Permission Evaluator `BankingPermissionEvaluator.java`

```java
package com.enterprise.banking.security.abac;

import com.enterprise.banking.dto.TransferRequest;
import com.enterprise.security.model.EnterpriseUserPrincipal;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.security.access.PermissionEvaluator;
import org.springframework.security.core.Authentication;
import org.springframework.stereotype.Component;

import java.io.Serializable;
import java.math.BigDecimal;
import java.time.Clock;
import java.time.LocalTime;
import java.time.ZoneId;

@Component("bankingPermissionEvaluator")
public class BankingPermissionEvaluator implements PermissionEvaluator {

    private static final Logger log = LoggerFactory.getLogger(BankingPermissionEvaluator.class);
    
    private static final BigDecimal MEDIUM_THRESHOLD = new BigDecimal("100000.00");
    private static final BigDecimal HIGH_THRESHOLD = new BigDecimal("1000000.00");
    
    private static final LocalTime BUSINESS_HOURS_START = LocalTime.of(8, 0);
    private static final LocalTime BUSINESS_HOURS_END = LocalTime.of(17, 0);
    private static final ZoneId BANK_OPERATIONAL_ZONE = ZoneId.of("UTC");

    private final Clock operationalClock;

    public BankingPermissionEvaluator(Clock operationalClock) {
        this.operationalClock = operationalClock;
    }

    @Override
    public boolean hasPermission(Authentication authentication, Object targetDomainObject, Object permission) {
        if (!(authentication.getPrincipal() instanceof EnterpriseUserPrincipal principal)) {
            log.warn("Access denied: Principal is not an instance of EnterpriseUserPrincipal");
            return false;
        }

        if (!(targetDomainObject instanceof TransferRequest request)) {
            log.warn("Access denied: Target domain object is not a TransferRequest");
            return false;
        }

        String action = permission.toString();
        return evaluateTransferPolicy(principal, request, action);
    }

    @Override
    public boolean hasPermission(Authentication authentication, Serializable targetId, String targetType, Object permission) {
        // Digunakan jika otorisasi hanya memegang ID entitas (ditolak secara default demi ketegasan ABAC)
        return false;
    }

    private boolean evaluateTransferPolicy(EnterpriseUserPrincipal principal, TransferRequest request, String action) {
        // Dimensi 1: Multi-Tenancy Confinement Rule
        if (!principal.getTenantId().equals(request.targetTenantId())) {
            log.error("SECURITY VIOLATION: Tenant mismatch! Principal Tenant: {}, Target Tenant: {}",
                    principal.getTenantId(), request.targetTenantId());
            return false;
        }

        if (!"EXECUTE_TRANSFER".equalsIgnoreCase(action)) {
            return false;
        }

        // Dimensi 2: Evaluasi Atribut Lingkungan (Waktu Akses)
        LocalTime currentTime = LocalTime.now(operationalClock.withZone(BANK_OPERATIONAL_ZONE));
        boolean isBusinessHours = !currentTime.isBefore(BUSINESS_HOURS_START) && !currentTime.isAfter(BUSINESS_HOURS_END);

        BigDecimal amount = request.amount();

        // Evaluasi Berdasarkan Matriks Kebijakan ABAC
        if (amount.compareTo(MEDIUM_THRESHOLD) < 0) {
            // Policy Tier 1: Di bawah $100K butuh role TELLER & Jam Operasional
            boolean hasTellerRole = hasAuthority(principal, "ROLE_TELLER");
            return hasTellerRole && isBusinessHours;
        } else if (amount.compareTo(HIGH_THRESHOLD) <= 0) {
            // Policy Tier 2: $100K - $1M butuh SENIOR_TELLER, Jam Operasional, dan Risk Tier LOW
            boolean hasSeniorTellerRole = hasAuthority(principal, "ROLE_SENIOR_TELLER");
            boolean isLowRisk = "LOW".equalsIgnoreCase(principal.getRiskTier());
            return hasSeniorTellerRole && isBusinessHours && isLowRisk;
        } else {
            // Policy Tier 3: > $1M butuh ROLE_TREASURY_OFFICER (Otorisasi Khusus)
            boolean hasTreasuryRole = hasAuthority(principal, "ROLE_TREASURY_OFFICER");
            log.info("Evaluating high-value wire transfer for Principal: {}, Approved: {}", 
                    principal.getUserId(), hasTreasuryRole);
            return hasTreasuryRole;
        }
    }

    private boolean hasAuthority(EnterpriseUserPrincipal principal, String expectedRole) {
        return principal.getAuthorities().stream()
                .anyMatch(auth -> auth.getAuthority().equalsIgnoreCase(expectedRole));
    }
}
```

### File 3: Distributed Token Revocation Store & Filter `DistributedTokenRevocationFilter.java`

```java
package com.enterprise.security.filter;

import com.enterprise.security.service.TokenRevocationService;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.lang.NonNull;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtException;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

@Component
public class DistributedTokenRevocationFilter extends OncePerRequestFilter {

    private static final Logger log = LoggerFactory.getLogger(DistributedTokenRevocationFilter.class);
    private static final String BEARER_PREFIX = "Bearer ";

    private final TokenRevocationService revocationService;
    private final JwtDecoder fastHeaderJwtDecoder;

    public DistributedTokenRevocationFilter(TokenRevocationService revocationService,
                                            JwtDecoder fastHeaderJwtDecoder) {
        this.revocationService = revocationService;
        this.fastHeaderJwtDecoder = fastHeaderJwtDecoder;
    }

    @Override
    protected void doFilterInternal(@NonNull HttpServletRequest request,
                                    @NonNull HttpServletResponse response,
                                    @NonNull FilterChain filterChain) throws ServletException, IOException {

        String authHeader = request.getHeader(HttpHeaders.AUTHORIZATION);

        if (!StringUtils.hasText(authHeader) || !authHeader.startsWith(BEARER_PREFIX)) {
            // Bukan request dengan Bearer token, lewati ke filter berikutnya
            filterChain.doFilter(request, response);
            return;
        }

        String tokenValue = authHeader.substring(BEARER_PREFIX.length()).trim();

        try {
            // Ekstraksi identitas JWT ID (jti) untuk pengecekan revocation
            Jwt jwt = fastHeaderJwtDecoder.decode(tokenValue);
            String tokenId = jwt.getId();

            if (tokenId != null && revocationService.isTokenRevoked(tokenId)) {
                log.warn("SECURITY ALERT: Intercepted revoked token access attempt. JTI: {}", tokenId);
                writeSecurityErrorResponse(response, HttpStatus.UNAUTHORIZED, "Token has been revoked by security administration");
                return;
            }

            // Periksa apakah seluruh subjek (User ID) telah di-blacklist secara global
            String subject = jwt.getSubject();
            if (subject != null && revocationService.isSubjectBlacklisted(subject)) {
                log.warn("SECURITY ALERT: Intercepted blacklisted subject access attempt. Sub: {}", subject);
                writeSecurityErrorResponse(response, HttpStatus.UNAUTHORIZED, "User session has been forcefully terminated");
                return;
            }

        } catch (JwtException ex) {
            // Parsing gagal, delegasikan ke BearerTokenAuthenticationFilter untuk standard handling error
            log.debug("JWT pre-parsing failed in revocation filter: {}", ex.getMessage());
        }

        filterChain.doFilter(request, response);
    }

    private void writeSecurityErrorResponse(HttpServletResponse response, HttpStatus status, String message) 
            throws IOException {
        response.setStatus(status.value());
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.getWriter().write(String.format("{\"error\": \"unauthorized\", \"message\": \"%s\"}", message));
    }
}
```

### File 4: Token Revocation Service via Redis Interface `TokenRevocationService.java`

```java
package com.enterprise.security.service;

import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.util.Objects;

@Service
public class TokenRevocationService {

    private static final String REVOKED_TOKEN_PREFIX = "revoked:token:jti:";
    private static final String BLACKLISTED_USER_PREFIX = "blacklisted:user:sub:";

    private final StringRedisTemplate redisTemplate;

    public TokenRevocationService(StringRedisTemplate redisTemplate) {
        this.redisTemplate = redisTemplate;
    }

    public void revokeToken(String jti, Duration remainingTtl) {
        Objects.requireNonNull(jti, "JTI must not be null");
        String key = REVOKED_TOKEN_PREFIX + jti;
        redisTemplate.opsForValue().set(key, "REVOKED", remainingTtl);
    }

    public void blacklistSubject(String subject, Duration duration) {
        Objects.requireNonNull(subject, "Subject must not be null");
        String key = BLACKLISTED_USER_PREFIX + subject;
        redisTemplate.opsForValue().set(key, "TERMINATED", duration);
    }

    public boolean isTokenRevoked(String jti) {
        if (jti == null) return false;
        return Boolean.TRUE.equals(redisTemplate.hasKey(REVOKED_TOKEN_PREFIX + jti));
    }

    public boolean isSubjectBlacklisted(String subject) {
        if (subject == null) return false;
        return Boolean.TRUE.equals(redisTemplate.hasKey(BLACKLISTED_USER_PREFIX + subject));
    }
}
```

### File 5: Core Financial Transaction Service `BankingTransferService.java`

```java
package com.enterprise.banking.service;

import com.enterprise.banking.dto.TransferRequest;
import com.enterprise.banking.dto.TransferResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Isolation;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.UUID;

@Service
public class BankingTransferService {

    private static final Logger log = LoggerFactory.getLogger(BankingTransferService.class);

    @PreAuthorize("@bankingPermissionEvaluator.hasPermission(authentication, #request, 'EXECUTE_TRANSFER')")
    @Transactional(isolation = Isolation.SERIALIZABLE)
    public TransferResponse executeFundTransfer(TransferRequest request) {
        log.info("Executing settlement from account: {} to account: {} for amount: {} {}",
                request.sourceAccountNumber(),
                request.destinationAccountNumber(),
                request.amount(),
                request.currency());

        // Domain Logic Transaksi Mutasi Rekening
        String transactionReference = "TX-" + UUID.randomUUID().toString().toUpperCase();

        return new TransferResponse(
                transactionReference,
                "SETTLED",
                request.amount(),
                request.currency(),
                Instant.now()
        );
    }
}
```

### File 6: Response DTO `TransferResponse.java`

```java
package com.enterprise.banking.dto;

import java.math.BigDecimal;
import java.time.Instant;

public record TransferResponse(
        String transactionReference,
        String status,
        BigDecimal amount,
        String currency,
        Instant executionTimestamp
) {}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Di bawah ini adalah evaluasi rekayasa tingkat mendalam antara berbagai pendekatan arsitektur otentikasi dan otorisasi:

### 1. Perbandingan Paradigma Kontrol Akses

| Kriteria Analisis | Role-Based Access Control (RBAC) | Attribute-Based Access Control (ABAC) | Relation-Based Access Control (ReBAC / Zanzibar) |
| :--- | :--- | :--- | :--- |
| **Prinsip Evaluasi** | Kecocokan nama peran statis (`ROLE_USER`). | Evaluasi rumus predikat atas multi-atribut (User, Resource, Env). | Penelusuran graf relasi antar objek (*Object-to-Subject Graph*). |
| **Fleksibilitas Logika** | Sangat Rendah. Kaku terhadap batas kontekstual (jam, IP, nilai transaksi). | **Sangat Tinggi**. Dapat mengekspresikan aturan bisnis multidimensi. | Sangat Tinggi untuk domain bersarang (*Google Drive Sharing*). |
| **Kompleksitas Implementasi** | Rendah (`@RolesAllowed`). | Sedang - Tinggi (Membutuhkan PDP Engine & integrasi metadata). | Sangat Tinggi (Membutuhkan distributed graph database seperti OpenFGA/Ory Keto). |
| **Overhead Komputasi** | $O(1)$ — String matching sederhana pada set memori. | $O(K)$ — Evaluasi serangkaian $K$ predikat logika. | $O(V + E)$ — Traversal graf relasi objek. |
| **Skalabilitas Organisasi** | Buruk (Rentan *Role Explosion*). | **Unggul**. Aturan tetap ringkas meski atribut bertambah. | Unggul untuk data relasional hierarkis kompleks. |

### 2. Validasi Token: Stateless JWT Signature vs. Stateful Token Introspection

```
+---------------------------------------------------------------------------------------------------+
| METODE 1: PURE STATELESS JWT DECODING                                                             |
| Keuntungan: Latensi sub-milidetik, tanpa dependensi DB/Network I/O pada path autentikasi.        |
| Kelemahan : Tidak dapat mendeteksi pencabutan token seketika (window kerentanan = JWT lifetime). |
+---------------------------------------------------------------------------------------------------+
| METODE 2: OAUTH2 TOKEN INTROSPECTION (RFC 7662)                                                   |
| Keuntungan: Status token selalu 100% akurat dan terverifikasi secara real-time.                   |
| Kelemahan : Latensi tinggi (setiap request memicu HTTP POST ke Auth Server), Auth Server = SPOF. |
+---------------------------------------------------------------------------------------------------+
| METODE 3: HYBRID ENGINE (PENDEKATAN ENTERPRISE KITA)                                              |
| JWT divalidasi asimetris secara lokal, sedangkan pencabutan diverifikasi melalui in-memory       |
| high-throughput distributed Redis filter (Kompromi Optimal antara Latensi vs Keamanan).          |
+---------------------------------------------------------------------------------------------------+
```

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Hilangnya Konteks Keamanan pada Virtual Threads & Async Processing

* **Masalah**: Ketika memanggil metode `@Async` atau meluncurkan *task* menggunakan `Thread.startVirtualThread(...)`, `SecurityContext` default Spring Security yang berbasis `ThreadLocal` tidak otomatis berpindah (*propagated*) ke thread baru. Akibatnya, `SecurityContextHolder.getContext().getAuthentication()` bernilai `null`, menyebabkan runtime `AccessDeniedException` atau eksekusi anomali tanpa identitas.
* **Solusi Arsitektural**: Wajib membungkus *Task Executor* menggunakan `DelegatingSecurityContextAsyncTaskExecutor` atau memanfaatkan Java 21 Virtual Thread Context Propagation Wrapper:

```java
ExecutorService virtualExecutor = Executors.newVirtualThreadPerTaskExecutor();
SecurityContext context = SecurityContextHolder.getContext();

virtualExecutor.submit(() -> {
    SecurityContextHolder.setContext(context);
    try {
        bankingTransferService.executeFundTransfer(request);
    } finally {
        SecurityContextHolder.clearContext(); // Hindari kontaminasi thread pool
    }
});
```

### 2. Algoritma Kriptografis Kritis: *Algorithm Confusion Attack*

* **Masalah**: Penyerang memodifikasi header JWT dari `{"alg": "RS256"}` menjadi `{"alg": "HS256"}` dan menandatangani payload menggunakan *Public Key* server (yang bersifat publik). Jika Resource Server menggunakan parser yang salah dikonfigurasi, server akan memverifikasi tanda tangan menggunakan public key sebagai secret HMAC, dan token palsu dianggap valid.
* **Solusi**: Wajib menerapkan pembatasan eksplisit algoritma pada `NimbusJwtDecoder`:

```java
NimbusJwtDecoder jwtDecoder = NimbusJwtDecoder.withJwkSetUri(jwkSetUri)
        .jwsAlgorithm(SignatureAlgorithm.RS256) // Paksa HANYA menerima RS256
        .build();
```

### 3. Drift Jam Kriptografis (*Clock Skew*)

* **Masalah**: Server aplikasi Resource Server dan Authorization Server memiliki selisih waktu beberapa detik. Token yang baru saja diterbitkan dapat langsung ditolak dengan pesan `Jwt validation failed: Token is not active yet (nbf claim)`.
* **Solusi**: Terapkan toleransi skew waktu secara konsisten (`Duration.ofSeconds(60)`), namun jangan lebih dari 120 detik untuk mencegah eksploitasi perpanjangan validitas token yang kedaluwarsa.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Anti-Pattern 1: Menyimpan Informasi Rahasia Sensitif di Payload JWT

```java
// KODE SALAH (ANTI-PATTERN):
// JWT Payload hanya di-Base64Url encoded, BUKAN dienkripsi!
{
  "sub": "12345",
  "credit_card_pin": "9921",       // KRITIS: Kebocoran Data Sensitif!
  "db_password": "root_password"    // KRITIS: Kredensial bocor ke klien!
}
```

```java
// KODE BENAR:
// Hanya masukkan identitas subjek dan klaim non-sensitif/referensial
{
  "sub": "usr_9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "tenant_id": "tenant_apac_01",
  "scope": "banking:wire:execute"
}
```

### Anti-Pattern 2: Pengecekan Otorisasi Berbasis String URL yang Rapuh

```java
// KODE SALAH: Logika bisnis ditempatkan pada matcher antarmuka HTTP
http.authorizeHttpRequests(auth -> auth
    .requestMatchers("/api/v1/accounts/*/transfer").hasRole("TELLER") // Tidak mengecek kepemilikan tenant!
);
```

```java
// KODE BENAR: Gunakan ABAC Method Security di Service Layer untuk memvalidasi isi muatan objek
@PreAuthorize("@bankingPermissionEvaluator.hasPermission(authentication, #request, 'EXECUTE_TRANSFER')")
public TransferResponse executeFundTransfer(TransferRequest request) { ... }
```

### Anti-Pattern 3: Evaluasi String Token Mentah Menggunakan `String.equals()`

```java
// KODE SALAH: Rentan terhadap Side-Channel Timing Attack
public boolean validateSecret(String providedSecret, String actualSecret) {
    return providedSecret.equals(actualSecret); // Bocor informasi melalui perbedaan waktu eksekusi byte-by-byte
}
```

```java
// KODE BENAR: Gunakan Constant-Time Comparison
public boolean validateSecret(String providedSecret, String actualSecret) {
    byte[] a = providedSecret.getBytes(StandardCharsets.UTF_8);
    byte[] b = actualSecret.getBytes(StandardCharsets.UTF_8);
    return java.security.MessageDigest.isEqual(a, b); // Waktu eksekusi konstan (Constant-Time)
}
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Principle of Least Privilege (PoLP)**: Token OAuth2 tidak boleh membawa hak akses tak terbatas. Gunakan *Fine-Grained Scopes* (`transfer:write`, `account:read`) yang dibatasi umur aktifnya (*TTL pendek: 5 - 15 menit*).
2. **Defensive Secrets Management**: Dilarang keras meng-hardcode kunci privat, password keystore, atau sertifikat di dalam repository git atau file `application.yml`. Kunci wajib diinjeksi saat runtime melalui integrasi *HashiCorp Vault* atau *AWS Secrets Manager* dengan rotasi otomatis.
3. **Password Hashing Standard**: Jika aplikasi mengelola kredensial langsung (pada skenario IAM Identity Store), gunakan fungsi derivasi kunci **Argon2id** (pemenang Password Hashing Competition) atau **PBKDF2** dengan iterasi minimal $600,000$, meninggalkan *BCrypt* standar untuk instalasi enterprise baru.
4. **Enforce Mutual TLS (mTLS) pada Service-to-Service Communication**: Di samping JWT pada layer aplikasi, layer transport antar microservices wajib dilindungi mTLS dengan validasi *Subject Alternative Name* (SAN) sertifikat x509.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Strategi Caching JWKS yang Resilien

Memvalidasi JWT membutuhkan kunci publik dari Identity Provider. Jika setiap request melakukan panggilan jaringan ke endpoint `/.well-known/jwks.json`, throughput sistem akan hancur.
* **Implementasi**: Nimbus JWT Decoder secara internal mempertahankan cache thread-safe (`DefaultJWKSetCache`). Konfigurasikan cache dengan *Time-To-Live* (TTL) 24 jam dan *Refresh-Ahead* asynchronous untuk menghindari latensi spike saat cache invalidasi.

### 2. Menghindari Alokasi Memori Berlebih saat Parsing Otorisasi

Pada jalur throughput tinggi (misal: 100,000 req/sec), pembuatan stream dan koleksi baru di dalam `JwtAuthenticationConverter` dapat memicu beban *Garbage Collection* (GC) minor.
* Gunakan set yang tidak dapat dimodifikasi (`Collections.unmodifiableSet` atau `Set.of()`) dan instansiasi `SimpleGrantedAuthority` secara terstruktur tanpa melakukan *string concatenation* berulang di memori.

---

## SEKSI 16 — KEAMANAN & HARDENING

### 1. Matriks Hardening OWASP API Security Top 10 (2023)

* **API1:2023 - Broken Object Level Authorization (BOLA)**: Dimitigasi langsung oleh custom `BankingPermissionEvaluator` yang memvalidasi kepemilikan rekening dan tenant subjek secara eksplisit pada setiap request domain.
* **API2:2023 - Broken Authentication**: Dimitigasi melalui penegakan spesifikasi OAuth 2.1 (tanpa ROPC/Implicit), verifikasi tanda tangan kriptografis asimetris, dan perlindungan *Timing-Attack-Safe comparison*.
* **API3:2023 - Broken Object Property Level Authorization**: Gunakan Jackson `@JsonView` atau Record DTO ketat untuk memastikan field sensitif internal tidak bocor ke output JSON.
* **API8:2023 - Security Misconfiguration**: Seluruh stack mematikan header server default (`server: Apache-Coyote`), menerapkan CORS whitelist eksplisit (tanpa `Access-Control-Allow-Origin: *`), dan mewajibkan HSTS.

### 2. Regular Expression Denial of Service (ReDoS) Defense

Validasi input berbasis Regex pada filter keamanan wajib dilindungi dari kompleksitas komputasi eksponensial. Batasi panjang string masukan sebelum dievaluasi oleh engine Regex Java:

```java
public boolean isValidAccountNumber(String input) {
    if (input == null || input.length() > 34) { // Batasi ukuran input maksimal (IBAN max 34 char)
        return false;
    }
    return ACCOUNT_PATTERN.matcher(input).matches();
}
```

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### 1. Structured Security Audit Logging (RFC 5424)

Setiap peristiwa keamanan (Otentikasi berhasil, Otentikasi gagal, Akses Ditolak oleh ABAC, Deteksi Token Revoked) wajib dicatat dalam format JSON terstruktur dengan level log yang tepat tanpa mencemari log dengan PII (*Personally Identifiable Information*).

```java
package com.enterprise.security.audit;

import net.logstash.logback.argument.StructuredArguments;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.time.Instant;
import java.util.Map;

@Component
public class SecurityAuditLogger {

    private static final Logger auditLog = LoggerFactory.getLogger("SECURITY_AUDIT_LOG");

    public void logAccessDenied(String userId, String tenantId, String resource, String action, String reason) {
        auditLog.warn("SECURITY EVENT: Authorization Failure",
                StructuredArguments.entries(Map.of(
                        "event_type", "AUTHORIZATION_FAILURE",
                        "timestamp", Instant.now().toString(),
                        "user_id", userId != null ? userId : "ANONYMOUS",
                        "tenant_id", tenantId != null ? tenantId : "UNKNOWN",
                        "resource", resource,
                        "action", action,
                        "rejection_reason", reason
                ))
        );
    }
}
```

### 2. Metrik Micrometer & PromQL untuk Security Monitoring

Tambahkan meter custom untuk memantau serangan brute-force atau token injection:

```java
// Registrasi Counter Kegagalan Otorisasi
Counter.builder("security.authorization.failures")
    .tag("tenant", tenantId)
    .tag("reason", "ABAC_POLICY_VIOLATION")
    .register(meterRegistry)
    .increment();
```

Query Peringatan Prometheus:
```promql
# Deteksi Lonjakan Anomali Akses Ditolak (> 50 kegagalan/menit pada satu tenant)
rate(security_authorization_failures_total[1m]) * 60 > 50
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

### 1. Ringkasan Eksekutif Arsitektur

* **SecurityFilterChain**: Inti interceptor request HTTP; prioritaskan konfigurasi *stateless*, matikan *CSRF* jika murni REST API dengan Bearer token, pasang security headers lengkap.
* **OAuth 2.1**: Buang *Resource Owner Password Credentials* & *Implicit Flow*. Wajibkan *PKCE* dan *Authorization Code Flow*.
* **ABAC Policy Engine**: Pindahkan logika otorisasi kompleks dari controller ke service layer dengan `@PreAuthorize` dan custom `PermissionEvaluator`.
* **Revocation Defense**: Kombinasikan validasi asimetris JWT lokal dengan Redis in-memory blacklist filter untuk pembatalan instan.

### 2. CLI Key Management Quick Reference

```bash
# 1. Generate RSA 4096-bit Private Key
openssl genpkey -algorithm RSA -out private_key.pem -pkeyopt rsa_keygen_bits:4096

# 2. Ekstrak Public Key dari Private Key (untuk verifikasi JWKS)
openssl rsa -pubout -in private_key.pem -out public_key.pem

# 3. Konversi Private Key ke Format PKCS#8 (Dibutuhkan oleh Java KeyFactory)
openssl pkcs8 -topk8 -inform PEM -outform DER -in private_key.pem -out private_key.der -nocrypt

# 4. Periksa Sertifikat x509 untuk mTLS
keytool -printcert -file service_certificate.crt
```

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

Pilihlah satu jawaban yang paling tepat untuk setiap pertanyaan berikut:

### Soal Basic (1 - 5)

**1. Mengapa CSRF (Cross-Site Request Forgery) protection dapat dinonaktifkan secara aman pada arsitektur API murni yang menggunakan OAuth 2.1 Bearer Token?**
A. Karena CSRF protection hanya bekerja pada aplikasi berbasis PHP.  
B. Karena Bearer token dikirimkan secara eksplisit via header `Authorization` dan tidak dilampirkan secara otomatis oleh browser seperti halnya ambient credentials (cookies).  
C. Karena Spring Security 6.x secara otomatis mengenkripsi semua cookie HTTP.  
D. Karena CSRF protection menurunkan performa enkripsi RSA secara drastis.

**2. Apa fungsi utama dari kelas `DelegatingFilterProxy` dalam runtime Spring Security?**
A. Menandatangani token JWT menggunakan algoritma Ed25519.  
B. Bertindak sebagai jembatan antara siklus hidup servlet container (Jakarta EE) dengan Spring `ApplicationContext` untuk memanggil `FilterChainProxy`.  
C. Menyimpan sesi pengguna langsung ke dalam database relational.  
D. Melakukan parsing header HTTP Authorization dan mengubahnya menjadi array byte.

**3. Manakah komponen JWT yang TIDAK dapat dibaca oleh publik saat ditransmisikan jika token hanya menggunakan standar JWS (JSON Web Signature)?**
A. Header.  
B. Payload/Claims.  
C. Signature.  
D. Tidak ada; seluruh komponen Header dan Payload pada JWS terbuka dalam format Base64Url decoded (hanya integritasnya yang dilindungi tanda tangan).

**4. Di mana letak bahaya penggunaan strategi `SecurityContextHolder.MODE_INHERITABLETHREADLOCAL` pada aplikasi enterprise modern dengan Java 21?**
A. Mengakibatkan JVM langsung crash saat garbage collection.  
B. Virtual threads yang diciptakan dalam jumlah jutaan akan mewarisi context secara berlebihan, memicu kebocoran memori (memory leak) dan kontaminasi identitas.  
C. Membuat seluruh koneksi TLS terdegradasi menjadi HTTP/1.0.  
D. Menghapus seluruh sertifikat dari Java TrustStore secara permanen.

**5. Klaim JWT standar mana yang mendefinisikan batas waktu sebelum token TIDAK BOLEH dianggap sah/valid untuk diproses?**
A. `exp` (Expiration Time).  
B. `iss` (Issuer).  
C. `nbf` (Not Before).  
D. `jti` (JWT ID).

---

### Soal Intermediate (6 - 10)

**6. Pada skenario Algorithm Confusion Attack, bagaimana penyerang mengeksploitasi Resource Server yang tidak terproteksi?**
A. Mengirimkan payload JSON dengan struktur rekursif tanpa batas.  
B. Mengubah header algoritma dari `RS256` menjadi `HS256`, lalu menandatangani token menggunakan Public Key server sebagai secret key HMAC.  
C. Menghapus seluruh sertifikat dari keystore server melalui port HTTP.  
D. Memaksa server memvalidasi hash MD5 pada koneksi database.

**7. Mengapa implementasi otorisasi `hasRole('ADMIN')` statis tidak memadai untuk sistem Multi-Tenant Banking, dan harus ditingkatkan ke Attribute-Based Access Control (ABAC)?**
A. Karena peran `ADMIN` tidak dapat disimpan di dalam tabel database relasional.  
B. Karena RBAC tidak dapat mengevaluasi batasan kontekstual dinamis seperti kepemilikan Tenant ID, batas nominal transaksi, dan jam kerja secara bersamaan tanpa menimbulkan ledakan variasi role (*Role Explosion*).  
C. Karena Spring Security tidak mendukung evaluasi multi-role.  
D. Karena ABAC menghapus kebutuhan akan enkripsi TLS.

**8. Metode perbandingan string mana yang WAJIB digunakan untuk memvalidasi shared secret / signature kriptografis guna mencegah serangan *Side-Channel Timing Attack*?**
A. `providedSecret.equalsIgnoreCase(actualSecret)`  
B. `providedSecret.contentEquals(actualSecret)`  
C. `java.security.MessageDigest.isEqual(bytesA, bytesB)`  
D. Operator perbandingan referensi langsung `providedSecret == actualSecret`

**9. Bagaimana mekanisme kerja integrasi cache JWKS pada Resource Server untuk menangani rotasi kunci publik Authorization Server tanpa downtime?**
A. Server me-restart JVM secara otomatis setiap kali ada kunci baru.  
B. Server menyimpan cache kunci publik lokal, dan jika menemukan JWT dengan header `kid` yang tidak dikenali, server memicu refresh terkontrol ke endpoint `/.well-known/jwks.json`.  
C. Server meminta klien mengirimkan private key di dalam header HTTP.  
D. Kunci publik di-hardcode di dalam file `.class` Java saat proses kompilasi Maven.

**10. Dalam arsitektur Zero Trust, apa peran dari komponen *Policy Enforcement Point* (PEP) versus *Policy Decision Point* (PDP)?**
A. PEP membuat keputusan matematis, sedangkan PDP mengeksekusi filter servlet.  
B. PEP mengintersepsi request dan menegakkan putusan izin pada batas eksekusi, sedangkan PDP menganalisis atribut kebijakan untuk menghasilkan putusan (PERMIT/DENY).  
C. PEP bertugas mengenkripsi disk database, sedangkan PDP menerbitkan sertifikat SSL.  
D. Tidak ada perbedaan; keduanya adalah istilah sinonim untuk firewall jaringan.

---

### Kunci Jawaban & Pembahasan Singkat

1. **B** — Bearer token dikirim via header eksplisit, sehingga permintaan palsu lintas situs (CSRF) via browser tidak dapat menyematkannya secara otomatis.
2. **B** — `DelegatingFilterProxy` adalah servlet filter bridge standar menuju Spring `ApplicationContext`.
3. **D** — JWS hanya menandatangani data, tidak mengenkripsi. Header dan payload dapat dibaca siapa saja dengan Base64Url decode. Enkripsi muatan membutuhkan JWE (JSON Web Encryption).
4. **B** — InheritableThreadLocal menyalin context ke setiap child thread; pada virtual threads yang berjumlah jutaan, ini memicu overhead dan potensi kontaminasi context.
5. **C** — `nbf` (Not Before) menyatakan token tidak valid sebelum timestamp tersebut.
6. **B** — Penyerang memanfaatkan verifikasi HMAC menggunakan Public Key RSA yang mereka ketahui secara publik sebagai symmetric secret.
7. **B** — RBAC murni gagal menangani dimensi kontekstual multi-atribut tanpa membuat ribuan variasi role yang tidak dapat dikelola.
8. **C** — `MessageDigest.isEqual` mengeksekusi perbandingan dalam waktu konstan (*constant-time*), menggagalkan analisis timing side-channel.
9. **B** — Cache JWKS yang cerdas me-refresh entri kunci publik saat mendeteksi `kid` baru yang valid untuk mengakomodasi rotasi kunci berkala.
10. **B** — Standar XACML/NIST: PEP mengintersepsi dan menegakkan izin (*enforce*), PDP mengevaluasi atribut untuk menghasilkan putusan (*decide*).

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Proyek: "Zero-Trust Financial Settlement Gateway with Dynamic ABAC and Token Revocation Engine"

#### Deskripsi Tugas
Bangun sebuah subsistem microservice Java 21 / Spring Boot 3.3+ yang berfungsi sebagai *Secure Settlement Gateway* perbankan dengan spesifikasi produksi:

#### Persyaratan Fungsional & Teknis:
1. **Endpoint Implementasi**:
   * `POST /api/v1/settlements/execute`: Menerima JSON transfer dana antar institusi perbankan.
   * `POST /api/v1/auth/admin/revoke-token`: Endpoint khusus Administrator untuk mencabut `jti` tertentu seketika.
   * `POST /api/v1/auth/admin/blacklist-user`: Endpoint darurat untuk memutus seluruh sesi aktif seorang User ID.
2. **Skema Proteksi Otentikasi**:
   * Konfigurasi Resource Server dengan decoder Nimbus JWT yang memvalidasi token berformat RSA-256.
   * Buat unit test yang memverifikasi bahwa token dengan header `"alg": "HS256"` atau `"alg": "none"` ditolak secara mutlak (*Algorithm Confusion Defense*).
3. **Engine Otorisasi ABAC**:
   * Tulis custom `@PreAuthorize` evaluator yang memeriksa 4 atribut:
     * Subjek: Departemen (`TREASURY`), Peran (`ROLE_SETTLEMENT_OFFICER`), Skor Risiko Fraud subjek $< 30$.
     * Objek: Mata uang transaksi (Transaksi valas / non-USD wajib memiliki izin instrumen derivatif).
     * Lingkungan: Permintaan hanya diizinkan jika header `X-Forwarded-Client-Cert` (simulasi mTLS) terpasang dan valid.
4. **Distributed Revocation Layer**:
   * Gunakan Testcontainers Redis dalam integration test untuk membuktikan bahwa setelah `jti` dicabut via endpoint revoke, request berikutnya yang membawa JWT tersebut langsung menghasilkan HTTP 401 Unauthorized dalam waktu $< 2\text{ ms}$.

#### Kriteria Pengujian Keberhasilan (Acceptance Tests):
* [ ] Seluruh unit dan integration tests wajib lulus 100% menggunakan JUnit 5 dan AssertJ.
* [ ] Tidak ada alokasi `ThreadLocal` yang tertinggal setelah request selesai (Buktikan dengan logging *Clean Context Assertion* pada filter boundary).
* [ ] Log keamanan tercatat dalam format structured JSON (RFC 5424) dan bebas dari kebocoran PII/Kredensial.