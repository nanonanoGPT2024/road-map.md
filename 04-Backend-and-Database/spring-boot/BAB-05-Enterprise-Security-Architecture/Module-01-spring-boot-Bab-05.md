# Kurikulum Spring Boot: Backend & Database Engineering
**Kategori:** 04-Backend-and-Database  
**Jalur Pembelajaran:** Advanced Enterprise Architecture

---

## Seksi 01: Identitas Modul

* **Kode Modul:** `SPR-SEC-501`
* **Nama Modul:** Enterprise Security Architecture
* **Tingkat Kesulitan:** Advanced / Enterprise Grade
* **Prasyarat:**
  * Pemahaman mendalam Spring Framework Core & Spring Boot Auto-configuration
  * Konsep RESTful API Design & HTTP Semantic Standards (RFC 7231, RFC 6749, RFC 7519)
  * Pemahaman Dasar Kriptografi Asimetris/Simetris (RSA, EC, AES, HMAC)
  * Java 21 LTS (Virtual Threads, Records, Sealed Interfaces)
* **Estimasi Waktu Penyelesaian:** 120 Menit (Teori & Hands-on Implementation)

---

## Seksi 02: Learning Objectives

Setelah menyelesaikan modul ini, engineer diharapkan mampu:
1. **Mendesain dan Mengonfigurasi** `SecurityFilterChain` non-blocking berbasis stateless architecture menggunakan Spring Security 6.x / Spring Boot 3.x.
2. **Mengimplementasikan** protokol OpenID Connect (OIDC) & OAuth2 Resource Server dengan validasi JWT terdesentralisasi via JSON Web Key Set (JWKS).
3. **Membangun** sistem otorisasi multi-layer mencakup Role-Based Access Control (RBAC) dan Attribute-Based Access Control (ABAC) menggunakan custom `PermissionEvaluator` dan SpEL.
4. **Menerapkan** proteksi perimeter komprehensif terhadap ancaman umum web API (CSRF Stateless, CORS, Strict Content Security Policy, Replay Attacks, dan Timing Attacks).
5. **Menyusun dan Menjalankan** automated integration security tests menggunakan `@AutoConfigureMockMvc` dan Mock Security Context.

---

## Seksi 03: Concept Map Diagram

```
+---------------------------------------------------------------------------------------------------+
|                                 ENTERPRISE CLIENT APPLICATION                                     |
+---------------------------------------------------------------------------------------------------+
                                                  |
                                                  | (1) HTTPS + Bearer JWT
                                                  v
+---------------------------------------------------------------------------------------------------+
| SPRING SECURITY FILTER CHAIN                                                                      |
|                                                                                                   |
|  +-----------------------------+       +-----------------------------+                            |
|  | CorsFilter                  | ----> | CsrfFilter (Disabled/Custom)|                            |
|  +-----------------------------+       +-----------------------------+                            |
|                 |                                     |                                           |
|                 v                                     v                                           |
|  +-----------------------------+       +-----------------------------+                            |
|  | HeaderWriterFilter          | ----> | BearerTokenAuthentication-  |                            |
|  | (HSTS, CSP, X-Frame)        |       | Filter                      |                            |
|  +-----------------------------+       +-----------------------------+                            |
|                                                       |                                           |
|                                                       v                                           |
|                                        +-----------------------------+                            |
|                                        | JwtAuthenticationProvider   |                            |
|                                        |  - Signature Verification   |                            |
|                                        |  - Claim Check (iss, exp)   |                            |
|                                        +-----------------------------+                            |
|                                                       |                                           |
|                                                       v                                           |
|                                        +-----------------------------+                            |
|                                        | CustomJwtGrantedAuthorities-|                            |
|                                        | Converter                   |                            |
|                                        +-----------------------------+                            |
|                                                       |                                           |
|                                                       v                                           |
|                                        +-----------------------------+                            |
|                                        | SecurityContextHolder       |                            |
|                                        | (Populated Authentication)  |                            |
|                                        +-----------------------------+                            |
+-------------------------------------------------------|-------------------------------------------+
                                                        v
+---------------------------------------------------------------------------------------------------+
| AUTHORIZATION LAYER (AOP Proxy / Interceptor)                                                     |
|                                                                                                   |
|  +---------------------------------------------------------------------------------------------+  |
|  | MethodSecurityInterceptor / AuthorizationManagerBeforeMethodInterceptor                     |  |
|  |                                                                                             |  |
|  |   Evaluates: @PreAuthorize("hasRole('ADMIN') and @policy.canAccess(principal, #resource)") |  |
|  |                                                                                             |  |
|  |   Components:                                                                               |  |
|  |   - Role-Based Access Control (RBAC): Evaluates GrantedAuthority (e.g., 'SCOPE_', 'ROLE_')  |  |
|  |   - Attribute-Based Access Control (ABAC): Custom SpEL Beans / PermissionEvaluator          |  |
|  +---------------------------------------------------------------------------------------------+  |
|                                               |                                                   |
|                                               v                                                   |
|                                +-----------------------------+                                    |
|                                | Domain Service Execution    |                                    |
|                                +-----------------------------+                                    |
+---------------------------------------------------------------------------------------------------+
```

---

## Seksi 04: Mengapa Relevan

Dalam arsitektur enterprise modern (Distributed Microservices, Multi-Cloud, dan Zero-Trust Network Architecture), perimeter keamanan berbasis jaringan (seperti VPN atau Firewall tradisional) tidak lagi mencukupi. Setiap service individual dituntut untuk:
* **Stateless & Resilient:** Mengeliminasi shared session storage (seperti `HttpSession` berbasis Redis terpusat) guna menurunkan overhead latensi jaringan dan memory footprints.
* **Decentralized Cryptographic Verification:** Memvalidasi identitas dan integritas payload secara lokal menggunakan asimetris public key (JWKS) tanpa melakukan I/O call bolak-balik ke Identity Provider (IdP) seperti Keycloak, Okta, atau Auth0.
* **Fine-Grained Authorization:** Mengakomodasi dynamic policy yang tidak hanya bergantung pada *siapa* user tersebut (Role), melainkan *apa atribut* dari resource yang diakses, lokasi request, status kepemilikan, dan batas limit finansial (ABAC).

---

## Seksi 05: Anatomi Konsep Inti

### 1. The Modern SecurityFilterChain Architecture
Pada Spring Security 6+, konfigurasi berbasis inheritance (`WebSecurityConfigurerAdapter`) telah dihapus secara total, digantikan oleh model deklaratif berbasis komparasi Bean `SecurityFilterChain`. 

```java
@Bean
public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
    return http
        .sessionManagement(sm -> sm.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
        .authorizeHttpRequests(auth -> auth.anyRequest().authenticated())
        .oauth2ResourceServer(oauth2 -> oauth2.jwt(Customizer.withDefaults()))
        .build();
}
```

Alur eksekusi request:
* **Servlet Container Layer:** Request masuk via `DelegatingFilterProxy`.
* **Spring Engine Layer:** `FilterChainProxy` mengevaluasi URI dan mengarahkan ke rantai filter yang cocok.
* **Security Filter Execution:** Filter berurutan memvalidasi Header, CORS, CSRF, Token Bearer, hingga memasukkan instance `Authentication` ke dalam `SecurityContextHolderStrategy`.

### 2. JWT Processing Flow & JWKS (JSON Web Key Set)
Spring Security Resource Server mengabstraksi validasi token melalui `JwtDecoder`:
* `NimbusJwtDecoder` mengunduh public key dari URI `.well-known/jwks.json` IdP.
* Public keys di-cache secara otomatis di memori lokal.
* Token divalidasi tanda tangannya (Signature Verification) menggunakan algoritma asimetris (RS256/ES256).
* Dilakukan validasi klaim standar RFC 7519: `nbf` (Not Before), `exp` (Expiration Time), `iss` (Issuer URI), dan `aud` (Audience).

### 3. Granular RBAC vs ABAC Mechanics
* **RBAC (Role-Based Access Control):** Menempelkan representasi statis berupa `GrantedAuthority` pada security context (contoh: `ROLE_FINANCE_MANAGER`, `SCOPE_read:reports`). Evaluasi berbasis ekspresi cepat: `hasRole('ADMIN')` atau `hasAuthority('SCOPE_write')`.
* **ABAC (Attribute-Based Access Control):** Menggunakan konteks dinamis runtime. Evaluasi melibatkan entitas target dan kondisi kontekstual. Dieksekusi melalui SpEL kustom, misalnya:  
  `@PreAuthorize("@accountSecurityEvaluator.isOwner(#accountId, authentication) and #amount <= @limitService.getDailyLimit(authentication.name)")`.

---

## Seksi 06: Panduan Implementasi Step-by-Step

### Step 1: Inisialisasi Dependensi (Maven `pom.xml`)
Gunakan dependensi minimal terisolasi untuk enterprise resource server:

```xml
<dependencies>
    <!-- Spring Boot Web Starter -->
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
    
    <!-- Spring Security Starter -->
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-security</artifactId>
    </dependency>

    <!-- OAuth2 Resource Server with Jose (JWT) engine -->
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-oauth2-resource-server</artifactId>
    </dependency>

    <!-- Validation API -->
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-validation</artifactId>
    </dependency>
</dependencies>
```

### Step 2: Konfigurasi Identity Provider Provider URI (`application.yml`)
Konfigurasikan endpoint IdP Anda secara terstruktur:

```yaml
spring:
  application:
    name: enterprise-security-service
  security:
    oauth2:
      resourceserver:
        jwt:
          issuer-uri: https://idp.enterprise.internal/realms/production
          jwk-set-uri: https://idp.enterprise.internal/realms/production/protocol/openid-connect/certs
          audiences:
            - enterprise-core-api

server:
  port: 8443
  ssl:
    enabled: false # Di-offload ke API Gateway/Ingress jika di Cloud Environment
```

---

## Seksi 07: Contoh Kasus Sederhana

Implementasi minimal `SecurityFilterChain` yang memproteksi endpoint `/api/public/**` vs `/api/secure/**` secara stateless:

```java
package com.enterprise.security.simple;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;

@Configuration
@EnableWebSecurity
public class SimpleSecurityConfig {

    @Bean
    public SecurityFilterChain simpleFilterChain(HttpSecurity http) throws Exception {
        http
            .csrf(csrf -> csrf.disable())
            .sessionManagement(sm -> sm.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/api/public/**").permitAll()
                .requestMatchers("/api/secure/**").authenticated()
                .anyRequest().denyAll()
            );
        return http.build();
    }
}
```

---

## Seksi 08: Implementasi Production-Grade Lengkap Kode

Berikut adalah implementasi enterprise-ready utuh yang mencakup konversi JWT Claim khusus, validasi audience kustom, Custom Entry Point/Access Denied Handler JSON, dan evaluasi ABAC berbasis Spring Bean.

### 1. Error Handling Components: RFC 7807 Problem Detail

```java
package com.enterprise.security.exception;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ProblemDetail;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.web.AuthenticationEntryPoint;
import org.springframework.security.web.access.AccessDeniedHandler;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.net.URI;
import java.time.Instant;

@Component
public class SecurityProblemSupport implements AuthenticationEntryPoint, AccessDeniedHandler {

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Override
    public void commence(HttpServletRequest request, HttpServletResponse response, 
                         AuthenticationException authException) throws IOException {
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(
                HttpStatus.UNAUTHORIZED, 
                authException.getMessage()
        );
        problem.setTitle("Unauthorized Access");
        problem.setType(URI.create("https://enterprise.internal/errors/unauthorized"));
        problem.setProperty("timestamp", Instant.now().toString());
        problem.setProperty("path", request.getRequestURI());

        writeResponse(response, HttpStatus.UNAUTHORIZED, problem);
    }

    @Override
    public void handle(HttpServletRequest request, HttpServletResponse response, 
                       AccessDeniedException accessDeniedException) throws IOException {
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(
                HttpStatus.FORBIDDEN, 
                accessDeniedException.getMessage()
        );
        problem.setTitle("Access Forbidden");
        problem.setType(URI.create("https://enterprise.internal/errors/forbidden"));
        problem.setProperty("timestamp", Instant.now().toString());
        problem.setProperty("path", request.getRequestURI());

        writeResponse(response, HttpStatus.FORBIDDEN, problem);
    }

    private void writeResponse(HttpServletResponse response, HttpStatus status, ProblemDetail problem) throws IOException {
        response.setStatus(status.value());
        response.setContentType(MediaType.APPLICATION_PROBLEM_JSON_VALUE);
        response.setCharacterEncoding("UTF-8");
        objectMapper.writeValue(response.getWriter(), problem);
    }
}
```

### 2. Token Converter & Audience Validator

```java
package com.enterprise.security.converter;

import org.springframework.core.convert.converter.Converter;
import org.springframework.lang.NonNull;
import org.springframework.security.authentication.AbstractAuthenticationToken;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.core.OAuth2Error;
import org.springframework.security.oauth2.core.OAuth2TokenValidator;
import org.springframework.security.oauth2.core.OAuth2TokenValidator