# Kurikulum Rekayasa Perangkat Lunak Enterprise: Spring Boot
## Kategori: 04-Backend-and-Database
### BAB 05: Enterprise Security Architecture
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, *Senior Backend Engineer* / *Architect* diharapkan mampu:
*   Menganalisis dan membedah lifecycle internal dari `FilterChainProxy`, `SecurityFilterChain`, dan `SecurityContextHolderStrategy` di Spring Security 6.x / Spring Boot 3.x pada thread model konvensional maupun Java 21 *Virtual Threads*.
*   Mendesain dan mengimplementasikan arsitektur *Stateless OAuth2 Resource Server* berbasis verifikasi asimetris (*Public Key Infrastructure* / JWKS URI) dengan proteksi *fail-safe* terhadap *IdP downtime*.
*   Mengembangkan mesin otorisasi granular adaptif (*Attribute-Based Access Control* / ABAC) berbasis custom SpEL (*Spring Expression Language*) evaluators dan method security interceptors.
*   Mengimplementasikan mekanisme *distributed token revocation* berlatensi sub-milidetik memanfaatkan arsitektur *hybrid* (In-Memory Caffeine Cache + Redis Cluster Pub/Sub + Bloom Filter).
*   Menghilangkan celah kerentanan *concurrency leak*, *context propagation failure* pada pemrosesan asinkron, dan miskonfigurasi CORS/CSRF pada REST API enterprise.

---

### 2. Prerequisite
*   **Java Internals:** Pemahaman mendalam tentang Java 17/21 (Record, Sealed Classes, Reflection, ThreadLocal, Memory Model, dan Virtual Threads).
*   **Spring Framework Core:** Penguasaan Bean Lifecycle, Dynamic Proxies (CGLIB & JDK Dynamic Proxy), dan AOP (*Aspect-Oriented Programming*).
*   **Kriptografi & Protokol Web:** Memahami RFC 7519 (JWT), RFC 6749 (OAuth 2.0 Framework), RFC 7517 (JWK), algoritma asimetris (RSA, ECDSA), X.509 certificates, dan arsitektur PKI.
*   **Infrastruktur Terdistribusi:** Pengetahuan operasional mengenai Redis data structures dan message broker (Kafka/Redis PubSub).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1. Arsitektur Filter Chain di Spring Security 6.x
Spring Security bekerja sebagai rantai pemrosesan (*Servlet Filter*) yang didelegasikan oleh Servlet Container (`Tomcat`/`Jetty`) ke Spring Application Context melalui jembatan `DelegatingFilterProxy`.

```
[Servlet Container Engine]
        │
   (HTTP Request)
        ▼
┌─────────────────────────────────┐
│     DelegatingFilterProxy       │ (Standard javax/jakarta.servlet.Filter)
└───────────────┬─────────────────┘
                │ delegates to Spring Bean "springSecurityFilterChain"
                ▼
┌─────────────────────────────────┐
│       FilterChainProxy          │ (Pusat orkestrasi filter internal)
└───────────────┬─────────────────┘
                │ matches RequestMatcher to SecurityFilterChain
                ▼
┌─────────────────────────────────┐
│     SecurityFilterChain (N)     │
│ ┌─────────────────────────────┐ │
│ │ DisableEncodeUrlFilter      │ │
│ │ WebAsyncManagerIntegFilter  │ │
│ │ SecurityContextHolderFilter │ │ -> Menginisialisasi SecurityContext
│ │ HeaderWriterFilter          │ │
│ │ CorsFilter                  │ │
│ │ LogoutFilter                │ │
│ │ BearerTokenAuthFilter       │ │ -> Validasi JWT & JWKS
│ │ RequestCacheAwareFilter     │ │
│ │ SecurityContextHolderAware..│ │
│ │ AnonymousAuthFilter         │ │
│ │ SessionManagementFilter     │ │
│ │ ExceptionTranslationFilter  │ │ -> Konversi AccessDeniedException/
│ │                             │ │    AuthenticationException ke HTTP Code
│ │ AuthorizationFilter         │ │ -> Menggantikan FilterSecurityInterceptor
│ └─────────────────────────────┘ │
└───────────────┬─────────────────┘
                ▼
      [DispatcherServlet] -> [Controller Handler]
```

*   **`DelegatingFilterProxy`**: Filter standar servlet yang tidak mengelola lifecycle keamanan sendiri, melainkan mengambil bean bernama `springSecurityFilterChain` dari `WebApplicationContext` dan meneruskan pemanggilan `doFilter()`.
*   **`FilterChainProxy`**: Komponen inti yang memegang daftar konfigurasi `List<SecurityFilterChain>`. Ia mencocokkan URI path, HTTP header, atau host dari request masuk terhadap *RequestMatcher* masing-masing chain.
*   **`SecurityContextHolderFilter`**: Menggantikan `SecurityContextPersistenceFilter` lama. Filter ini bertugas memuat `SecurityContext` dari `SecurityContextRepository` (misalnya: memori/stateless untuk API) pada awal eksekusi dan menjamin pembersihan context saat request selesai via blok `finally`.
*   **`AuthorizationFilter`**: Filter modern pada Spring Security 6 yang menggantikan `FilterSecurityInterceptor`. Menggunakan API `AuthorizationManager<RequestAuthorizationContext>` yang non-blocking dan thread-safe.

#### 3.2. Lifecycle Autentikasi OAuth2 Resource Server
Pada Resource Server stateless, pemrosesan token melibatkan beberapa layer abstraksi:

1.  **Ekstraksi Token:** `BearerTokenAuthenticationFilter` mengekstrak token dari header `Authorization: Bearer <JWT>`.
2.  **Manajemen Autentikasi:** Meneruskan `BearerTokenAuthenticationToken` ke `AuthenticationManager` (implementasi default: `ProviderManager`).
3.  **Delegasi Provider:** `ProviderManager` memilih `JwtAuthenticationProvider`.
4.  **Dekripsi & Validasi Kriptografi:** `JwtAuthenticationProvider` memanggil `JwtDecoder` (biasanya `NimbusJwtDecoder`). Di sini terjadi fetching Public Key dari IdP (Keycloak, Auth0, Okta) via JWKS URI dengan caching lokal.
5.  **Transformasi Klaim ke Hak Akses:** `JwtAuthenticationConverter` mengubah klaim mentah JWT (misal: `realm_access.roles`, `scope`) menjadi koleksi `GrantedAuthority`.
6.  **Penyimpanan State:** Objek `JwtAuthenticationToken` (yang mengimplementasikan `Authentication`) disimpan ke dalam `SecurityContextHolder`.

#### 3.3. Thread Model & SecurityContextHolderStrategy
Secara historis, Spring Security menggunakan `ThreadLocal` melalui `ThreadLocalSecurityContextHolderStrategy`. Dalam paradigma komputasi modern:
*   **Java 21 Virtual Threads (Project Loom):** Virtual threads dapat diciptakan berjuta-juta. Penggunaan `InheritableThreadLocal` menjadi berbahaya karena overhead memory footprint dan risiko kebocoran konteks antar-carrier thread.
*   **Reactive (Project Reactor):** Thread pool berganti secara dinamis (Worker Threads Netty). Konsep `ThreadLocal` tidak berlaku; konteks harus dialirkan melalui `reactor.util.context.Context`.

---

### 4. Why & What

| Fitur / Pendekatan | Arsitektur Naif (Tutorial Standard) | Arsitektur Enterprise Produksi |
| :--- | :--- | :--- |
| **Kriptografi JWT** | Symmetric Key (HMAC SHA-256) menggunakan secret string statis yang di-hardcode di `application.yml`. | Asymmetric Key (RSA-256/512 atau ECDSA) memanfaatkan Public/Private Key pair via OIDC Discovery Endpoint & JWKS URI. |
| **IdP Decoupling** | Setiap request melakukan introspeksi remote HTTP call ke Identity Provider. | Verifikasi signature kriptografis lokal via cached JWKS. Network trip ke IdP bernilai nol pada path request panas. |
| **Token Revocation** | Mengandalkan masa kedaluwarsa JWT (TTL pendek) tanpa kemampuan revoke instan. | Hybrid Engine: Bloom Filter untuk pre-flight checking + Redis Cluster O(1) blacklist + IdP Backchannel Logout. |
| **Method Security** | `@PreAuthorize("hasRole('ADMIN')")` monolitik yang statis dan kaku. | Dynamic Contextual ABAC menggunakan custom SpEL evaluators yang mengevaluasi domain object dan context bisnis runtime. |
| **Error Handling** | Spring Boot Default Whitelabel Error Page atau stacktrace bocor ke consumer. | Custom `AuthenticationEntryPoint` & `AccessDeniedHandler` dengan output terstandardisasi RFC 7807 (Problem Details). |

---

### 5. How (Workflow Detail)

Alur verifikasi dan otorisasi dari request masuk hingga eksekusi method bisnis:

```
[Client] 
   │ 
   │ (1) HTTP GET /api/v1/accounts/123 (Authorization: Bearer eyJhbGciOi...)
   ▼
[BearerTokenAuthenticationFilter]
   │
   │ (2) Ekstrak JWT String
   ▼
[ProviderManager] ──> [JwtAuthenticationProvider]
                           │
                           │ (3) Invoke decode()
                           ▼
                    [NimbusJwtDecoder]
                      ├──> Cek Cache JWK Lokal (Hit) ──┐
                      └──> (Miss) Fetch JWKS Endpoint ─┘
                           │
                           │ (4) Verifikasi Signature, Validasi nbf, exp, iss, aud
                           ▼
                    [JwtAuthenticationConverter]
                           │
                           │ (5) Map claims ("roles", "perms") -> Collection<GrantedAuthority>
                           ▼
                    [CustomSecurityContextHolderStrategy]
                           │
                           │ (6) Simpan Authentication di SecurityContext
                           ▼
[AuthorizationFilter] ──> Match Request URI -> PERMIT
                           │
                           ▼
[DispatcherServlet] ──> [AccountController#getAccount(id)]
                           │
                           │ (7) Intersepsi Method AOP (@PreAuthorize)
                           ▼
                    [AuthorizationManagerBeforeMethodInterceptor]
                           │
                           │ (8) Evaluasi SpEL: @pms.canAccessAccount(#id, authentication)
                           ▼
                    [CustomPermissionEvaluator / Domain Service]
                      ├── Ambil domain account id 123
                      └── Bandingkan Owner ID == authentication.getName() OR hasRole('AUDITOR')
                           │
                           ├─► [DENIED] ──> Throw AccessDeniedException -> Handle RFC 7807 (HTTP 403)
                           │
                           └─► [GRANTED] ─> Eksekusi Method Controller -> Return Data (HTTP 200)
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Paspor Diplomatik & Visa Elektronik
*   **Authentication (Siapa Anda):** Paspor Diplomatik berkop resmi negara (IdP) yang ditandatangani secara kriptografis (Digital Signature). Konsulat di perbatasan negara lain (Resource Server) tidak perlu menelepon presiden negara pembuat paspor setiap kali Anda lewat; konsulat cukup mencocokkan stempel/tanda tangan dengan buku stempel publik resmi konsuler (JWKS).
*   **Authorization (Apa yang Boleh Anda Lakukan):** Setelah identitas Anda sah, izin masuk ke ruangan brankas negara (Method execution) dievaluasi oleh protokol keamanan setempat (ABAC). Sekalipun Anda adalah duta besar sah (Authenticated), Anda tidak diizinkan masuk ke ruang server militer kecuali Anda memegang mandat misi spesifik hari ini (Contextual Domain Authorization).

#### State Machine Autentikasi & Otorisasi
```
                ┌────────────────────────┐
                │ Request Datang ke Pod  │
                └───────────┬────────────┘
                            │
              Ada Bearer Token Valid Format?
                     /            \
                 (No)              (Yes)
                 /                    \
    Path Terproteksi?             Verifikasi Signature Asimetris
        /          \                     /             \
    (No)            (Yes)            (Gagal)          (Sukses)
    /                  \               /                  \
[Pass ke Dispatcher] [HTTP 401]   [HTTP 401]        Cek Distributed Blacklist
                                                      /             \
                                                  (Ada)             (Tidak)
                                                  /                     \
                                             [HTTP 401]         Evaluasi ABAC Method
                                                                   /             \
                                                              (Gagal)          (Sukses)
                                                                /                  \
                                                           [HTTP 403]       [Eksekusi Bisnis]
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Minimal Spring Boot 3 Resource Server
Konfigurasi dasar OAuth2 Resource Server dengan JWT validation via JWKS.

```java
// File: SecurityConfig.java
package com.enterprise.security.simple;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;

@Configuration
@EnableWebSecurity
public class SimpleSecurityConfig {

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        return http
            .csrf(csrf -> csrf.disable())
            .sessionManagement(sm -> sm.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/public/**").permitAll()
                .anyRequest().authenticated()
            )
            .oauth2ResourceServer(oauth2 -> oauth2.jwt(Customizer.withDefaults()))
            .build();
    }
}
```

```yaml
# File: application.yml
spring:
  security:
    oauth2:
      resourceserver:
        jwt:
          jwk-set-uri: https://auth.enterprise.com/realms/production/protocol/openid-connect/certs
```

---

#### 7.2. Practical Example: Production-Grade Hardened Security Architecture
Implementasi nyata untuk *high-throughput system* dengan:
1.  Custom Keycloak/Auth0 Role Extractor.
2.  Distributed Redis Revocation Check Filter.
3.  Resilient JWKS Decoder dengan Timeout dan Cache Circuit Breaker.
4.  Custom Contextual ABAC Expression Evaluator.
5.  RFC 7807 Exception Handlers.

##### A. Konfigurasi Maven Dependensi (`pom.xml`)
```xml
<dependencies>
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
        <artifactId>spring-boot-starter-data-redis</artifactId>
    </dependency>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
</dependencies>
```

##### B. Enterprise Granted Authorities Converter
Mengurai nested roles dari Keycloak (`realm_access.roles` dan `resource_access.{client-id}.roles`).

```java
// File: KeycloakRealmRoleConverter.java
package com.enterprise.security.production.converter;

import org.springframework.core.convert.converter.Converter;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.jwt.Jwt;

import java.util.*;
import java.util.stream.Collectors;

public class KeycloakRealmRoleConverter implements Converter<Jwt, Collection<GrantedAuthority>> {

    private static final String REALM_ACCESS = "realm_access";
    private static final String ROLES = "roles";
    private static final String ROLE_PREFIX = "ROLE_";

    @Override
    @SuppressWarnings("unchecked")
    public Collection<GrantedAuthority> convert(Jwt jwt) {
        Map<String, Object> realmAccess = jwt.getClaimAsMap(REALM_ACCESS);
        if (realmAccess == null || !realmAccess.containsKey(ROLES)) {
            return Collections.emptyList();
        }

        List<String> roles = (List<String>) realmAccess.get(ROLES);
        return roles.stream()
                .map(roleName -> new SimpleGrantedAuthority(ROLE_PREFIX + roleName.toUpperCase()))
                .collect(Collectors.toUnmodifiableSet());
    }
}
```

##### C. Distributed Redis Token Revocation Filter
Mencegah *replay attack* atau penggunaan token yang sudah di-revoke sebelum masa exp habis. Menggunakan Redis dengan format Key `revoked:jti:<jti>`.

```java
// File: TokenRevocationFilter.java
package com.enterprise.security.production.filter;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

public class TokenRevocationFilter extends OncePerRequestFilter {

    private final StringRedisTemplate redisTemplate;
    private static final String REDIS_REVOKE_PREFIX = "revoked:jti:";

    public TokenRevocationFilter(StringRedisTemplate redisTemplate) {
        this.redisTemplate = redisTemplate;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {

        Authentication auth = SecurityContextHolder.getContext().getAuthentication();

        if (auth instanceof JwtAuthenticationToken jwtAuth) {
            String jti = jwtAuth.getToken().getId(); // JWT ID claim (JTI)

            if (jti != null && Boolean.TRUE.equals(redisTemplate.hasKey(REDIS_REVOKE_PREFIX + jti))) {
                response.setStatus(HttpStatus.UNAUTHORIZED.value());
                response.setContentType("application/problem+json");
                response.getWriter().write("""
                    {
                        "type": "https://api.enterprise.com/errors/revoked-token",
                        "title": "Unauthorized",
                        "status": 401,
                        "detail": "Token identifier has been revoked."
                    }
                """);
                return;
            }
        }

        filterChain.doFilter(request, response);
    }
}
```

##### D. Custom Attribute-Based Access Control (ABAC) Evaluator
Evaluator yang memeriksa kepemilikan data dinamis secara terisolasi tanpa mencemari Controller.

```java
// File: SecurityPermissionEvaluator.java
package com.enterprise.security.production.abac;

import org.springframework.security.core.Authentication;
import org.springframework.stereotype.Component;

import java.util.Objects;

@Component("pms")
public class SecurityPermissionEvaluator {

    /**
     * Memverifikasi apakah subjek autentikasi berhak mengakses akun berdasarkan ID.
     */
    public boolean canAccessAccount(Long targetAccountId, Authentication authentication) {
        if (authentication == null || !authentication.isAuthenticated()) {
            return false;
        }

        // Bypass untuk peran Admin/Auditor
        boolean isPrivileged = authentication.getAuthorities().stream()
                .anyMatch(a -> a.getAuthority().equals("ROLE_SYSTEM_AUDITOR") || 
                               a.getAuthority().equals("ROLE_PLATFORM_ADMIN"));
        if (isPrivileged) {
            return true;
        }

        // Ambil User ID internal yang disuntikkan pada klaim sub / custom claims
        String principalId = authentication.getName();
        
        // Asumsi lookup service internal atau perbandingan langsung
        String resolvedOwnerId = fetchAccountOwner(targetAccountId);

        return Objects.equals(principalId, resolvedOwnerId);
    }

    private String fetchAccountOwner(Long accountId) {
        // Simulasi resolusi identitas pemilik via cache/db
        return "user-uuid-" + accountId;
    }
}
```

##### E. Custom Security Configuration & Hardening
Perakitan seluruh komponen menjadi `SecurityFilterChain` yang tangguh untuk kelas perbankan.

```java
// File: EnterpriseSecurityConfig.java
package com.enterprise.security.production.config;

import com.enterprise.security.production.converter.KeycloakRealmRoleConverter;
import com.enterprise.security.production.filter.TokenRevocationFilter;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationConverter;
import org.springframework.security.oauth2.server.resource.web.authentication.BearerTokenAuthenticationFilter;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.header.writers.ReferrerPolicyHeaderWriter;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

import java.time.Duration;
import java.util.List;

@Configuration
@EnableWebSecurity
@EnableMethodSecurity(prePostEnabled = true, securedEnabled = true)
public class EnterpriseSecurityConfig {

    @Value("${spring.security.oauth2.resourceserver.jwt.jwk-set-uri}")
    private String jwkSetUri;

    @Bean
    public SecurityFilterChain enterpriseFilterChain(HttpSecurity http, 
                                                    StringRedisTemplate redisTemplate) throws Exception {
        return http
            // 1. Matikan state & CSRF (wajib stateless untuk REST API)
            .csrf(csrf -> csrf.disable())
            .sessionManagement(sm -> sm.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            
            // 2. Strict Transport Security & Enterprise Secure Headers
            .headers(headers -> headers
                .contentSecurityPolicy(csp -> csp.policyDirectives("default-src 'self'"))
                .frameOptions(frame -> frame.deny())
                .xssProtection(xss -> xss.disable()) // Dinonaktifkan sesuai modern OWASP, digantikan CSP
                .httpStrictTransportSecurity(hsts -> hsts
                    .includeSubDomains(true)
                    .maxAgeInSeconds(31536000)
                    .preload(true)
                )
                .referrerPolicy(ref -> ref.policy(ReferrerPolicyHeaderWriter.ReferrerPolicy.STRICT_ORIGIN_WHEN_CROSS_ORIGIN))
            )

            // 3. CORS Enforcement
            .cors(cors -> cors.configurationSource(corsConfigurationSource()))

            // 4. Request Authorization Rules
            .authorizeHttpRequests(auth -> auth
                .requestMatchers(HttpMethod.GET, "/actuator/health/**", "/actuator/info").permitAll()
                .requestMatchers(HttpMethod.OPTIONS, "/**").permitAll()
                .requestMatchers("/api/v1/public/**").permitAll()
                .requestMatchers("/api/v1/management/**").hasRole("PLATFORM_ADMIN")
                .anyRequest().authenticated()
            )

            // 5. JWT Resource Server Integration
            .oauth2ResourceServer(oauth2 -> oauth2
                .jwt(jwt -> jwt
                    .decoder(customJwtDecoder())
                    .jwtAuthenticationConverter(jwtAuthenticationConverter())
                )
            )

            // 6. Inject Distributed Revocation Filter sesudah BearerTokenAuthenticationFilter
            .addFilterAfter(new TokenRevocationFilter(redisTemplate), BearerTokenAuthenticationFilter.class)
            
            .build();
    }

    @Bean
    public JwtDecoder customJwtDecoder() {
        // Menggunakan NimbusJwtDecoder dengan cache internal dan validasi clock skew toleran (60 detik)
        return NimbusJwtDecoder.withJwkSetUri(this.jwkSetUri)
                .cacheDefaults() // Default LRU memory caching untuk public keys
                .build();
    }

    @Bean
    public JwtAuthenticationConverter jwtAuthenticationConverter() {
        JwtAuthenticationConverter converter = new JwtAuthenticationConverter();
        converter.setJwtGrantedAuthoritiesConverter(new KeycloakRealmRoleConverter());
        return converter;
    }

    @Bean
    public CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration config = new CorsConfiguration();
        config.setAllowedOrigins(List.of("https://dashboard.enterprise.com"));
        config.setAllowedMethods(List.of("GET", "POST", "PUT", "PATCH", "DELETE"));
        config.setAllowedHeaders(List.of("Authorization", "Content-Type", "Idempotency-Key"));
        config.setExposedHeaders(List.of("X-Trace-Id"));
        config.setAllowCredentials(false);
        config.setMaxAge(Duration.ofHours(1));

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/api/**", config);
        return source;
    }
}
```

##### F. Controller Menggunakan Fine-Grained Authorization
```java
// File: AccountController.java
package com.enterprise.security.production.controller;

import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/accounts")
public class AccountController {

    @GetMapping("/{id}")
    @PreAuthorize("@pms.canAccessAccount(#id, authentication)")
    public ResponseEntity<?> getAccountBalance(@PathVariable("id") Long id, Authentication authentication) {
        return ResponseEntity.ok(Map.of(
                "accountId", id,
                "ownerPrincipal", authentication.getName(),
                "balance", 1250000.00,
                "status", "ACTIVE"
        ));
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### 8.1. Konteks Skenario
Sebuah platform *Payment Processing Core-Banking* memproses $45.000$ *transactions per second* (TPS) pada jam sibuk. Sistem didistribusikan ke $250$ pod microservices di Kubernetes.

#### 8.2. Permasalahan Arsitektur
1.  **IdP Overload:** Arsitektur awal menggunakan pendekatan *Remote Token Introspection* (OAuth2 RFC 7662). Setiap transaksi melakukan panggilan network HTTP POST ke Identity Provider (Keycloak Cluster). Keycloak mengalami starvation connection pool, latensi naik dari $5\text{ms}$ menjadi $3.200\text{ms}$, menyebabkan *cascading timeout* di seluruh platform.
2.  **Symmetric Secret Leakage:** Tim menggunakan Shared Secret HMAC-SHA256 yang dibagikan ke 15 repositori microservices. Satu tim magang secara tidak sengaja mengunggah file `application-dev.yml` ke public repository, memaksa rotasi darurat seluruh credential sistem perbankan.
3.  **Emergency Revocation:** Regulasi OJK/PCI-DSS mewajibkan bahwa jika kartu debit/akun pengguna diblokir via Fraud Engine, semua token aktif milik pengguna tersebut harus langsung ditolak dalam waktu $\le 500\text{ms}$.

#### 8.3. Solusi Arsitektur
1.  **Migrasi ke Asymmetric JWKS:** Menghentikan remote introspection. Microservices hanya mengunduh Public Key (via JSON Web Key Set) dari OIDC Provider. JWT divalidasi langsung di dalam CPU memory masing-masing microservice ($< 0.1\text{ms}$).
2.  **Circuit-Breaker Protected JWKS Caching:** Mengonfigurasi layer in-memory cache untuk public keys dengan fallback TTL 24 jam. Jika IdP down, microservices tetap dapat memvalidasi token yang ada tanpa gangguan.
3.  **Tiered Revocation Architecture:**
    *   **Layer 1 (Lokal):** Caffeine In-Memory Cache pada pod menyimpan set `revoked_jti` terbaru (cek $O(1)$, zero latency).
    *   **Layer 2 (Terdistribusi):** Redis Cluster dengan *Bloom Filter* untuk memfilter $99.9\%$ token valid tanpa overhead query Redis String key.
    *   **Layer 3 (Event-Driven Invalidation):** Ketika Fraud Engine mendeteksi serangan, event `TokenRevokedEvent` di-publish ke Redis Pub/Sub topic. Seluruh 250 pods menerima pesan tersebut secara real-time ($< 80\text{ms}$) dan menyimpannya ke Caffeine local cache masing-masing.

---

### 9. Trade-offs

```
                  ┌────────────────────────────────────────┐
                  │    Trade-off Matriks Desain Token      │
                  └────────────────────────────────────────┘
                       
           KEAMANAN TINGGI (Stateful)
                     ▲
                     │          • Remote Introspection (RFC 7662)
                     │            [Latency: Tinggi | Beban IdP: Maksimal]
                     │
                     │          • Asymmetric JWT + Redis Revocation Pub/Sub
                     │            [Latency: Rendah | Kompleksitas: Menengah]
                     │
                     │          • Stateless Pure Asymmetric JWT (Short TTL)
                     │            [Latency: Tercepat | Revoke: Menunggu Expire]
                     │
                     ▼
           PERFORMA TINGGI (Stateless)
                     
◄──────────────────────────────────────────────────────────────────────────►
RENDAH                     KOMPLEKSITAS OPERASIONAL                   TINGGI
```

| Pendekatan | Latency Impact | Scalability | Biaya Infrastruktur | Risiko Keamanan |
| :--- | :--- | :--- | :--- | :--- |
| **Pure Stateless JWT (Short TTL, eg: 5 min)** | Hampir nol ($< 0.1\text{ms}$) | Tidak terbatas (*embarrassingly parallel*) | Rendah (tidak butuh Redis/DB state) | Jendela eksploitasi terbuka selama masa validitas jika token dicuri sebelum kadaluwarsa. |
| **Stateless JWT + Redis Revocation Lookup** | Sangat rendah ($0.5 - 1.5\text{ms}$) | Sangat tinggi (dibatasi oleh memory & RPS Redis Cluster) | Menengah (butuh maintenance cluster Redis) | Optimal untuk standar finansial. Token dapat dibatalkan instan melalui ID blacklist. |
| **Full Remote Token Introspection** | Sangat tinggi ($15 - 80\text{ms}$) | Rendah (IdP menjadi single point of failure dan bottleneck) | Sangat mahal (skalabilitas IdP horizontal masif) | Sangat aman (state diperiksa ke database pusat setiap detik). |
| **Opaque Session via Distributed DB** | Sedang ($2 - 5\text{ms}$) | Terbatas pada performa write/read DB session | Tinggi | Zero footprint cryptographic context pada client. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Kesalahan Fatal `ThreadLocal` pada Asynchronous / Virtual Threads
*   **Gejala:** Nilai `SecurityContextHolder.getContext().getAuthentication()` mengembalikan `null` atau, lebih berbahaya lagi, mengembalikan kredensial transaksi dari pengguna lain (*identity leakage*) saat menggunakan `@Async`, `CompletableFuture`, atau executor baru.
*   **Penyebab:** Strategi default adalah `MODE_THREADLOCAL`. Saat thread berganti, context tidak dibawa. Jika developer beralih ke `MODE_INHERITABLETHREADLOCAL` pada Virtual Threads Java 21, carrier thread pool dapat mengalami memory leak dan overhead carrier switching.
*   **Solusi:**
    Gunakan `DelegatingSecurityContextAsyncTaskExecutor` atau bungkus runnable via `SecurityContextUtils`:

```java
@Configuration
public class AsyncSecurityConfig {

    @Bean
    public AsyncTaskExecutor applicationTaskExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(16);
        executor.setMaxPoolSize(64);
        executor.initialize();
        // Wajib membungkus task executor agar SecurityContext dipropagasikan
        return new DelegatingSecurityContextAsyncTaskExecutor(executor);
    }
}
```

#### 10.2. CORS Preflight 401/403 Failure
*   **Gejala:** Browser client memblokir panggilan API dengan error: *`Response to preflight request doesn't pass access control check: No 'Access-Control-Allow-Origin' header is present`*.
*   **Penyebab:** Request HTTP `OPTIONS` dihentikan oleh filter autentikasi sebelum mencapai `CorsFilter` karena tidak memuat header `Authorization`.
*   **Solusi:**
    Daftarkan `CorsFilter` di urutan paling awal sebelum filter autentikasi dan definisikan rule eksplisit:
    `.requestMatchers(HttpMethod.OPTIONS, "/**").permitAll()` atau gunakan integrasi native `.cors(Customizer.withDefaults())`.

#### 10.3. JWKS Out-of-Sync Saat Key Rotation
*   **Gejala:** Identity Provider merotasi private signing key. Tiba-tiba $100\%$ request yang menggunakan token baru ditolak dengan error `Signed JWT rejected: Another algorithm expected, or no matching key found in JWK set`.
*   **Troubleshooting:**
    Periksa cache TTL pada `NimbusJwtDecoder`. Pastikan library menggunakan `DefaultJWTProcessor` yang mendukung background refresh otomatis saat menerima `kid` (Key ID) baru yang belum terdaftar di local cache.

---

### 11. Best Practices (Production Checklist)

1.  [ ] **Non-blocking Signature Verification:** Pastikan public key JWKS di-cache di memori dan dimuat ulang secara asinkron atau terjadwal.
2.  [ ] **Enforce JTI Claim:** Wajibkan setiap JWT memuat claim unik `jti` (UUIDv4) untuk pelacakan audit dan pencegahan token reuse.
3.  [ ] **Audience Restriction (`aud`):** Validasi claim `aud` agar token yang diterbitkan untuk Service B tidak dapat disalahgunakan untuk mengakses Service A.
4.  [ ] **Issuer Enforcement (`iss`):** Verifikasi identitas issuer secara ketat menggunakan HTTPS URI absolut.
5.  [ ] **Stateless Session Management:** Pastikan `.sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))` terkonfigurasi.
6.  [ ] **Matikan CSRF untuk Pure REST:** Nonaktifkan CSRF `.csrf(csrf -> csrf.disable())` hanya jika API tidak menggunakan session cookie sebagai mekanisme autentikasi.
7.  [ ] **Explicit CORS Configuration:** Jangan gunakan wildcard `allowedOrigins("*")` bersamaan dengan `allowCredentials(true)`. Tentukan domain origin whitelist secara spesifik.
8.  [ ] **Enforce Strict Method Security:** Aktifkan `@EnableMethodSecurity(prePostEnabled = true)` dan hindari dependensi otorisasi yang hanya mengandalkan URI AntMatchers.
9.  [ ] **HSTS Preload:** Aktifkan header `Strict-Transport-Security` dengan flag `includeSubDomains` dan waktu simpan minimal 1 tahun ($31536000$ detik).
10. [ ] **Frame Embedding Protection:** Terapkan header `X-Frame-Options: DENY` untuk mencegah serangan clickjacking.
11. [ ] **Disable Content Sniffing:** Setel header `X-Content-Type-Options: nosniff`.
12. [ ] **Masked Sensitive Payload Logging:** Cegah penulisan header `Authorization` dan token JWT ke dalam log application server (gunakan Logback Masking Pattern / Logstash Filter).
13. [ ] **No Monolithic Role Strings:** Hindari penyebaran string `"ROLE_ADMIN"` mentah di seluruh service; gunakan konstanta terpusat atau custom annotations (meta-annotations).
14. [ ] **Fail-Closed Security Posture:** Pastikan handler kegagalan otorisasi melempar HTTP 403 Forbidden secara deterministik jika terjadi runtime error saat pengecekan domain logic.

---

### 12. Hands-on Practice

Buat dan uji implementasi arsitektur keamanan tingkat lanjut pada direktori `hands-on/m02/`.

#### Struktur Direktori
```text
hands-on/m02/
├── pom.xml
├── src/
│   ├── main/
│   │   ├── java/com/enterprise/security/
│   │   │   ├── Application.java
│   │   │   ├── config/EnterpriseSecurityConfig.java
│   │   │   ├── controller/SecureVaultController.java
│   │   │   ├── converter/CustomJwtGrantedAuthoritiesConverter.java
│   │   │   ├── evaluator/VaultPermissionEvaluator.java
│   │   │   └── filter/DistributedRevocationFilter.java
│   │   └── resources/
│   │       └── application.yml
│   └── test/
│       └── java/com/enterprise/security/SecurityIntegrationTest.java
```

#### Langkah 1: Siapkan Konfigurasi `application.yml`
```yaml
server:
  port: 8443

spring:
  application:
    name: hardened-vault-service
  data:
    redis:
      host: localhost
      port: 6379
  security:
    oauth2:
      resourceserver:
        jwt:
          jwk-set-uri: http://localhost:8080/realms/enterprise/protocol/openid-connect/certs
          issuer-uri: http://localhost:8080/realms/enterprise

logging:
  level:
    org.springframework.security: DEBUG
```

#### Langkah 2: Implementasi Controller dengan Dynamic SpEL
```java
package com.enterprise.security.controller;

import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/vault")
public class SecureVaultController {

    @GetMapping("/{vaultId}/data")
    @PreAuthorize("@vaultSecurity.canAccessVault(#vaultId, authentication)")
    public ResponseEntity<String> readVaultData(@PathVariable("vaultId") String vaultId) {
        return ResponseEntity.ok("Highly confidential payload for vault: " + vaultId);
    }
}
```

#### Langkah 3: Evaluator Implementasi
```java
package com.enterprise.security.evaluator;

import org.springframework.security.core.Authentication;
import org.springframework.stereotype.Component;

@Component("vaultSecurity")
public class VaultPermissionEvaluator {

    public boolean canAccessVault(String vaultId, Authentication authentication) {
        if (authentication == null) return false;
        // Business logic: Hanya vaultId yang berawalan dengan nama principal atau admin yang diizinkan
        String principal = authentication.getName();
        boolean isAdmin = authentication.getAuthorities().stream()
                .anyMatch(a -> a.getAuthority().equals("ROLE_VAULT_ADMIN"));

        return isAdmin || vaultId.startsWith(principal);
    }
}
```

#### Langkah 4: Uji Integrasi via MockMvc (`SecurityIntegrationTest.java`)
```java
package com.enterprise.security;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.security.test.context.support.WithMockUser;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
class SecurityIntegrationTest {

    @Autowired
    private MockMvc mockMvc;

    @Test
    void whenUnauthenticated_thenReturns401() throws Exception {
        mockMvc.perform(get("/api/v1/vault/john-101/data"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    @WithMockUser(username = "john", authorities = {"ROLE_USER"})
    void whenAuthorizedOwner_thenReturns200() throws Exception {
        mockMvc.perform(get("/api/v1/vault/john-101/data"))
                .andExpect(status().isOk());
    }

    @Test
    @WithMockUser(username = "alice", authorities = {"ROLE_USER"})
    void whenUnauthorizedOwner_thenReturns403() throws Exception {
        mockMvc.perform(get("/api/v1/vault/john-101/data"))
                .andExpect(status().isForbidden());
    }

    @Test
    @WithMockUser(username = "superadmin", authorities = {"ROLE_VAULT_ADMIN"})
    void whenAdmin_thenReturns200() throws Exception {
        mockMvc.perform(get("/api/v1/vault/john-101/data"))
                .andExpect(status().isOk());
    }
}
```

---

### 13. Exercise

#### Level: Easy
1.  Buat custom `AuthenticationEntryPoint` yang mengintersepsi kegagalan autentikasi (401) dan mengembalikan respons berformat JSON RFC 7807 (`application/problem+json`) lengkap dengan correlation ID unik (`X-Trace-Id`).
2.  Batasi API path `/api/v1/public/ping` agar dapat diakses tanpa autentikasi sama sekali (*anonymous*), namun tetap memiliki proteksi HTTP Secure Headers (misal: HSTS, Anti-Sniffing).

#### Level: Medium
1.  Implementasikan custom `JwtGrantedAuthoritiesConverter` yang menggabungkan:
    *   Klaim array `groups` dari identity provider menjadi authorities berawalan `GROUP_`.
    *   Klaim standard `scope` yang dipisah spasi menjadi authorities berawalan `SCOPE_`.
2.  Bangun Custom Method Security Annotation bernama `@RequiresDepartmentClearance(department = "FINANCE")` menggunakan Spring Security Meta-Annotations dan SpEL evaluator internal.

#### Level: Hard
1.  Rancang mekanisme dynamic IP Whitelisting authorization engine. Setiap request yang masuk ke method `@PreAuthorize("@networkGate.check(authentication, #request)")` harus mencocokkan IP remote request terhadap subnet CIDR (Classless Inter-Domain Routing) dinamis yang dimuat dari database dan di-cache dalam distributed memory.
2.  Tulis unit test multithreaded yang membuktikan bahwa propagasi `SecurityContext` berhasil diwariskan ke thread pool pekerja kustom tanpa kebocoran data (*cross-tenant pollution*) pada beban 1.000 concurrent tasks.

---

### 14. Challenge

#### Skenario Kasus: Zero-Downtime Multi-Region Key Rotation & Distributed Session Drain

Sebuah bank digital multinasional memiliki Resource Server yang tersebar di region Singapura (`ap-southeast-1`) dan Frankfurt (`eu-central-1`). Bank ini menggunakan infrastruktur Keycloak yang terpisah secara aktif-aktif.

**Persyaratan Tantangan:**
1.  **Dual JWKS Resolution:** Sistem harus mampu mengenali token yang diterbitkan oleh Keycloak Region A maupun Keycloak Region B secara bersamaan tanpa menimbulkan network call antar-region jika validasi signature lokal berhasil.
2.  **Autonomous Key Rotation:** Jika Identity Provider melakukan rotasi *Private Key* darurat karena insiden keamanan, Resource Server harus mampu mendeteksi key ID (`kid`) yang tidak dikenal, memperbarui local cache secara thread-safe tanpa memblokir request lain (*zero lock contention*), dan memvalidasi token baru secara transparan tanpa perlu restart aplikasi.
3.  **Emergency Drain (Blacklisting):** Buat implementasi token revocation engine menggunakan Redis Bloom Filter terdistribusi yang mampu menangani $10.000.000$ JTI revocations dengan false-positive rate di bawah $0.01\%$. Jika Bloom Filter mendeteksi bahwa JTI mungkin telah di-revoke, fallback ke Redis SET untuk verifikasi pasti.

**Batasan Teknis:**
*   Dilarang menggunakan blocking I/O pada path autentikasi utama selain interaksi network yang dikontrol ketat oleh circuit breaker (Resilience4j).
*   Gunakan Spring Security 6.x dan Spring Boot 3.x murni.
*   Waktu respons per request tidak boleh bertambah lebih dari $2.5\text{ms}$ untuk overhead layer keamanan.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Basic (Pilihan Ganda)
1.  **Komponen manakah pada Spring Security yang menjadi jembatan antara Servlet Container standard dan Spring ApplicationContext?**
    *   A. `SecurityFilterChain`
    *   B. `DelegatingFilterProxy`
    *   C. `FilterChainProxy`
    *   D. `AuthenticationManager`
    *   *Jawaban yang Benar:* B.
    *   *Analisis:* `DelegatingFilterProxy` adalah implementasi `jakarta.servlet.Filter` standar yang dicatat pada Servlet Container. Ia mendelegasikan pemanggilan ke bean Spring bernama `springSecurityFilterChain` (`FilterChainProxy`).

2.  **Filter manakah yang bertugas membersihkan `SecurityContext` di akhir siklus hidup request pada Spring Security 6?**
    *   A. `SecurityContextPersistenceFilter`
    *   B. `SecurityContextHolderFilter`
    *   C. `AuthorizationFilter`
    *   D. `LogoutFilter`
    *   *Jawaban yang Benar:* B.
    *   *Analisis:* Di Spring Security 6, `SecurityContextPersistenceFilter` didepresiasi dan digantikan sepenuhnya oleh `SecurityContextHolderFilter`, yang menjamin pembersihan context melalui blok `finally`.

3.  **Mengapa HTTP CSRF protection umumnya dinonaktifkan pada stateless REST API yang menggunakan JWT?**
    *   A. Karena JWT tidak dapat dibaca oleh peretas.
    *   B. Karena CSRF exploit hanya mengeksploitasi mekanisme kredensial otomatis browser (seperti Cookies dan HTTP Basic Auth), sedangkan Authorization Bearer header tidak dikirimkan otomatis oleh browser.
    *   C. Karena CSRF memperlambat pemrosesan enkripsi JWT.
    *   D. Karena Spring Security 6 otomatis memblokir semua request non-GET.
    *   *Jawaban yang Benar:* B.
    *   *Analisis:* Serangan CSRF mengandalkan perilaku browser yang otomatis menyertakan cookie pada request cross-origin. Bearer token yang disimpan manual di memory/client app tidak otomatis disertakan oleh browser saat terjadi cross-origin call.

4.  **Pada arsitektur stateless token, di mana idealnya proses validasi cryptographic signature JWT dilakukan oleh Resource Server?**
    *   A. Di Identity Provider melalui remote REST call setiap request.
    *   B. Secara lokal di memori Resource Server menggunakan Public Key IdP yang di-cache.
    *   C. Di Database utama aplikasi melalui SQL queries.
    *   D. Di API Gateway saja tanpa validasi di Resource Server.
    *   *Jawaban yang Benar:* B.
    *   *Analisis:* Validasi kriptografi lokal menggunakan public key dari JWKS IdP menghasilkan performa sub-milidetik dan menghilangkan ketergantungan jaringan ke IdP pada setiap request.

5.  **Secara default, ThreadLocalStrategy apa yang aktif pada `SecurityContextHolder`?**
    *   A. `MODE_GLOBAL`
    *   B. `MODE_INHERITABLETHREADLOCAL`
    *   C. `MODE_THREADLOCAL`
    *   D. `MODE_VIRTUALTHREAD`
    *   *Jawaban yang Benar:* C.
    *   *Analisis:* Default strategi adalah `MODE_THREADLOCAL`, yang mengikat objek `SecurityContext` ke satu thread tunggal yang sedang melayani request.

---

#### Bagian B: Intermediate (Pilihan Ganda & Analisis Kasus Singkat)
6.  **Apa dampak menggunakan `SecurityContextHolder.setStrategyName(SecurityContextHolder.MODE_INHERITABLETHREADLOCAL)` pada aplikasi yang menggunakan thread pool konvensional atau Java 21 Virtual Threads?**
    *   A. Tidak ada dampak; ini adalah praktik terbaik enterprise.
    *   B. Menyebabkan overhead memory masif dan potensi bahaya keamanan fatal di mana security context dari request lama di thread pool diwariskan ke request baru.
    *   C. Meningkatkan kecepatan verifikasi JWT hingga 50%.
    *   D. Menyebabkan JVM crash karena memori pointer rusak.
    *   *Jawaban yang Benar:* B.
    *   *Analisis:* Pada thread pool yang me-reuse thread, `InheritableThreadLocal` dapat menyebabkan thread anak mewarisi state pengguna sebelumnya jika pembersihan tidak dilakukan secara ketat, menimbulkan kebocoran hak akses antar pengguna.

7.  **Sebuah aplikasi mikroservis melempar `AccessDeniedException` dari dalam `@Service` bean saat mengevaluasi `@PreAuthorize`. Komponen manakah yang menangkap exception ini dan mengubahnya menjadi HTTP status code 403?**
    *   A. `DispatcherServlet`
    *   B. `ExceptionTranslationFilter`
    *   C. `AuthorizationFilter`
    *   D. `BearerTokenAuthenticationFilter`
    *   *Jawaban yang Benar:* B.
    *   *Analisis:* `ExceptionTranslationFilter` menangkap `AccessDeniedException` dan `AuthenticationException` yang meluap dari filter chain atau controller layer, kemudian memicu `AccessDeniedHandler` atau `AuthenticationEntryPoint`.

8.  **Bagaimana Spring Security 6 menangani method security authorization secara internal?**
    *   A. Menggunakan servlet filters konvensional.
    *   B. Menggunakan Spring AOP proxies yang mencegat eksekusi method melalui `AuthorizationManagerBeforeMethodInterceptor`.
    *   C. Melakukan patching bytecode JVM saat runtime melalui Agent.
    *   D. Mengintersepsi query database melalui Hibernate Interceptor.
    *   *Jawaban yang Benar:* B.
    *   *Analisis:* Method security di Spring Security diimplementasikan menggunakan Spring AOP. Interceptor `AuthorizationManagerBeforeMethodInterceptor` mengevaluasi ekspresi sebelum delegasi diteruskan ke instance method target.

9.  **Format header authorization HTTP manakah yang sesuai dengan standar RFC 6750 untuk Resource Server?**
    *   A. `Authorization: Token <JWT>`
    *   B. `Authorization: Bearer <JWT>`
    *   C. `X-Auth-Token: <JWT>`
    *   D. `Authorization: Signature <KeyID>:<JWT>`
    *   *Jawaban yang Benar:* B.
    *   *Analisis:* Standar OAuth 2.0 Bearer Token (RFC 6750) mewajibkan penggunaan skema `Bearer` pada HTTP header `Authorization`.

10. **Ketika request browser CORS Preflight (OPTIONS) dikirimkan, mengapa request tersebut tidak boleh diarahkan ke filter autentikasi token?**
    *   A. Karena browser tidak menyertakan payload body.
    *   B. Karena spesifikasi W3C/WHATWG CORS melarang browser menyertakan header custom seperti `Authorization` pada request preflight.
    *   C. Karena request OPTIONS dienkripsi dengan SSL level yang berbeda.
    *   D. Karena Spring Security tidak mendukung HTTP method OPTIONS.
    *   *Jawaban yang Benar:* B.
    *   *Analisis:* Browser tidak menyertakan kredensial autentikasi pada preflight OPTIONS. Jika Resource Server mewajibkan autentikasi pada preflight, panggilan lintas domain akan selalu gagal dengan status 401/403.

---

#### Bagian C: Skenario Kasus Produksi (Analisis & Solusi)

11. **Skenario 1: The "Vanishing Context" Mystery**
    *   *Kasus:* Tim backend meluncurkan endpoint `/api/v1/export-report`. Controller memanggil service asinkron:
        ```java
        @Async
        public CompletableFuture<Report> generate(Long id) {
            Authentication auth = SecurityContextHolder.getContext().getAuthentication();
            String user = auth.getName(); // Throws NullPointerException!
            ...
        }
        ```
    *   *Pertanyaan:* Mengapa `SecurityContextHolder.getContext().getAuthentication()` mengembalikan `null`? Bagaimana arsitektur fix yang paling tepat tanpa mengorbankan performa Virtual Threads?
    *   *Solusi Teknis:*
        Method `@Async` dieksekusi di thread pool yang berbeda dari thread servlet request. Karena default context holder menggunakan `ThreadLocal`, context tidak ditransfer ke thread baru.
        Solusi yang benar: Konfigurasikan task executor aplikasi menggunakan `DelegatingSecurityContextAsyncTaskExecutor` atau kirimkan parameter identitas pengguna secara eksplisit ke method service (`generate(Long id, String username)`), menjauhkan context container security dari domain processing murni.

12. **Skenario 2: Token Revocation Race Condition**
    *   *Kasus:* Akun nasabah bank disusupi. Staf keamanan menekan tombol "Lock Account" di dashboard. Operasi ini menandai database nasabah sebagai `LOCKED`. Namun, peretas masih berhasil menarik dana $10.000 via API transfer selama 12 menit berikutnya sebelum transaksi akhirnya ditolak. Token JWT diketahui memiliki expiry 15 menit.
    *   *Pertanyaan:* Mengapa transaksi peretas tetap berhasil dieksekusi meskipun database sudah mencatat status nasabah `LOCKED`? Solusi terdistribusi apa yang harus dipasang pada pipeline security?
    *   *Solusi Teknis:*
        Resource Server bersifat stateless dan hanya memeriksa masa validitas kriptografis (`exp` claim) pada JWT secara lokal tanpa memeriksa state database nasabah pada setiap request.
        Solusi:
        1. Pasang `TokenRevocationFilter` di awal Security Filter Chain.
        2. Ketika status `LOCKED` disetel, publish event ke Redis Cluster yang mencatat pembatalan seluruh JWT milik nasabah (berdasarkan `userId` atau `jti`).
        3. Filter keamanan memeriksa status pembatalan di Redis atau local bloom-filter/in-memory cache sebelum request diizinkan masuk ke controller.

13. **Skenario 3: Cascading Failure Akibat IdP Outage**
    *   *Kasus:* Server Identity Provider (Keycloak) mengalami failure hardware dan restart selama 10 menit. Seluruh microservices Spring Boot di cluster tiba-tiba menolak 100% traffic pengguna yang sah dengan pesan `500 Internal Server Error` atau `401 Unauthorized`, dan utilisasi CPU melonjak drastis hingga pod berjatuhan (OOM / CrashLoopBackOff).
    *   *Pertanyaan:* Analisis akar masalah pada layer `NimbusJwtDecoder` dan bagaimana rekayasa arsitektur untuk menahan kondisi kegagalan IdP tersebut (*fault-tolerant security architecture*)?
    *   *Solusi Teknis:*
        Akar masalah: Microservices tidak mengonfigurasi cache JWKS yang resilien. Setiap kali token baru masuk atau cache expired, implementasi default mencoba membuka koneksi HTTP baru ke JWKS URI yang mati. Kegagalan socket connection dengan timeout yang tidak tepat menghabiskan thread pool servlet (Tomcat thread starvation).
        Solusi:
        1. Bungkus `JwkSetRetriever` dengan memory cache berdurasi panjang (stale-while-revalidate pattern) menggunakan Resilience4j Circuit Breaker.
        2. Pertahankan keys lama di memory selama IdP down.
        3. Konfigurasikan socket & read timeout pendek (misal: 2 detik) pada rest client JWKS untuk mencegah thread exhaustion.

---

### 16. Summary

*   **Arsitektur Inti:** Spring Security 6.x adalah ekosistem berbasis *Filter Chain* di mana request diproses secara berurutan oleh rantai interceptor terspesialisasi sebelum mencapai layer MVC, dengan `SecurityContextHolderFilter` dan `AuthorizationFilter` sebagai tulang punggung stateless security modern.
*   **Decoupled Authentication:** Paradigma Resource Server modern bertumpu pada verifikasi asimetris berbasis JWKS (JSON Web Key Set). Autentikasi dilakukan sepenuhnya secara in-memory lokal sub-milidetik, memutus ketergantungan synchronous RPC trip ke Identity Provider pada hot-path request.
*   **Granular Authorization:** Otorisasi enterprise bergerak melampaui Role-Based Access Control (RBAC) primitif menuju Attribute-Based Access Control (ABAC) dinamis yang mengevaluasi relasi kontekstual antara subjek (pengguna), objek (domain resource), dan aksi bisnis menggunakan integrasi Spring AOP dan custom SpEL expressions.
*   **Defense-in-Depth:** Keamanan produksi menuntut integrasi Distributed Revocation Checks (Redis / Bloom Filters), hardening HTTP Security Headers (CSP, Strict HSTS, Frame Options), pencegahan kebocoran konteks pada pemrosesan asinkron/Virtual Threads, serta perlakuan error terstandarisasi berbasis RFC 7807 Problem Details.