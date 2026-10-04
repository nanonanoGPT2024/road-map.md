# BAB 09: Quiz, Challenge, & Knowledge Check
**Enterprise Security & Identity Governance**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **JCA/JCE Architecture & Provider Model**  
   Jelaskan arsitektur *Java Cryptography Architecture* (JCA) dan *Java Cryptography Extension* (JCE), khususnya konsep *engine class* (seperti `Cipher`, `KeyStore`, `MessageDigest`, `SecureRandom`) dan pemisahan berbasis `Provider`. Mengapa enterprise modern lebih memilih *Hardware Security Module* (HSM) atau cloud-based KMS melalui integrasi PKCS#11 provider dibandingkan mengelola cryptographic keys secara lokal di dalam JVM memory via PKCS12 Keystore?

2. **Diferensiasi Semantik: Authentication vs. Authorization Lifecycle**  
   Dalam arsitektur Spring Security, telusuri alur eksekusi internal saat sebuah kredensial mentah (*raw credentials*) masuk melalui request hingga status *authenticated* tersimpan di `SecurityContext`. Jelaskan peran spesifik dan interaksi antara `AuthenticationFilter`, `AuthenticationManager` (`ProviderManager`), `AuthenticationProvider`, dan bagaimana objek `GrantedAuthority` dibedakan dari *fine-grained permission* dalam domain-driven authorization.

3. **OAuth 2.0 vs. OpenID Connect (OIDC) & Token Topologies**  
   Analisis perbedaan mendasar antara OIDC (sebagai lapisan identitas) dan OAuth 2.0 (sebagai kerangka kerja otorisasi delegasi). Bandingkan karakteristik teknis, vektor risiko, dan trade-off antara penggunaan **By-Value Token** (self-contained JWT) dan **By-Reference Token** (Opaque Token yang divalidasi via RFC 7662 Token Introspection) pada skala microservices.

4. **Kelemahan Paradigma Stateless Token & Mitigasi Session Hijacking**  
   Banyak arsitek mempromosikan JWT sebagai mekanisme autentikasi *stateless* tanpa menyadari batasan fundamentalnya dalam hal revocability (*kill-switch*). Jelaskan trade-off antara skalabilitas horizontal murni vs. kebutuhan immediate token revocation (misalnya saat terjadi kompromi kredensial atau perubahan hak akses instan). Bagaimana strategi hybrid (misal: short-lived access token + distributed token deny-list/Bloom filter) memitigasi masalah ini tanpa membebani database?

5. **Mutual TLS (mTLS) & Zero-Trust Architecture**  
   Uraikan proses cryptographic handshake pada Mutual TLS (mTLS) hingga tingkat verifikasi sertifikat X.509. Bagaimana JVM membedakan antara `KeyStore` (identitas klien) dan `TrustStore` (otoritas sertifikat tepercaya)? Mengapa mTLS pada transport-layer dianggap sebagai fondasi penting Zero-Trust, namun tetap membutuhkan application-layer identity context (seperti JWT subject/claim propagation)?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Context Propagation Pitfalls: ThreadLocal, Virtual Threads, & Reactive Streams**  
   Secara default, Spring Security menggunakan `ThreadLocal` (`MODE_THREADLOCAL`) pada `SecurityContextHolder`.  
   * Apa konsekuensi fatal konfigurasi ini ketika kode bermigrasi ke arsitektur asynchronous (`CompletableFuture`, `@Async`), Reactive Streams (Project Reactor/WebFlux), atau Java 21 Project Loom (Virtual Threads)?
   * Bagaimana mekanisme internal `ReactiveSecurityContextHolder` atau penggunaan `ContextRegistry` / `TaskDecorator` menyelesaikan masalah *thread-context bleeding* dan hilangnya konteks keamanan?

2. **JWKS Rotation, Signature Verification, & Cryptographic Performance**  
   Saat memvalidasi JWT dari Identity Provider (Keycloak, Okta, Auth0) secara mandiri, service backend mengambil public keys dari endpoint JWKS (*JSON Web Key Set*).  
   * Debug skenario di mana service downstream mengalami lonjakan CPU 100% dan latency spike ketika IdP melakukan rotasi key (`kid` header mismatch).
   * Bagaimana desain cache JWKS yang tangguh (resilience pattern) harus diimplementasikan untuk mencegah DoS akibat permintaan key lookup yang tidak terbatas (*cache poisoning / endpoint exhaustion*)?

3. **Fine-Grained Authorization: Dynamic RBAC vs. Attribute-Based Access Control (ABAC)**  
   Mekanisme statis berbasis role (`@PreAuthorize("hasRole('ADMIN')")`) gagal ketika aturan otorisasi bergantung pada data relasional dinamis (contoh: *"User hanya boleh mengedit dokumen jika status dokumen DRAFT dan branch ID dokumen cocok dengan assignment branch user"*).  
   * Bagaimana Anda mengarsitekturkan evaluasi otorisasi deklaratif menggunakan Spring Expression Language (SpEL) yang terhubung ke `PermissionEvaluator` kustom?
   * Kapan sistem harus beralih dari evaluasi berbasis kode lokal ke dedicated Policy Engine eksternal seperti Open Policy Agent (OPA) via Rego?

4. **Timing Attacks & Cryptographic Verification Anti-Patterns**  
   Analisis cuplikan kode Java berikut yang digunakan untuk memvalidasi HMAC token atau API Secret:
   ```java
   public boolean validateSecret(String clientSecret, String expectedSecret) {
       return clientSecret.equals(expectedSecret);
   }
   ```
   * Mengapa kode di atas rentan terhadap *Side-Channel Timing Attack*?
   * Tunjukkan perbaikan tingkat rendah menggunakan `MessageDigest.isEqual()` dan jelaskan bagaimana algoritma *constant-time comparison* mencegah penyerang merekonstruksi secret byte-demi-byte.

5. **Security Filter Chain Path Matching Bypass (CVE-2023-34035 & Normalization Issues)**  
   Dalam Spring Security, kesalahan konfigurasi antara `requestMatchers()` (menggunakan Spring MVC pattern matching) dan path matching servlet mentah dapat membuka celah *unauthenticated bypass*.  
   * Jelaskan bagaimana inkonsistensi normalisasi URI (misalnya: path traversal `/api/v1/../admin/users`, encoded characters `%2e`, atau penanganan trailing slash `/users/` vs `/users`) dapat mengecoh filter chain jika konfigurasi routing servlet tidak identik dengan layer filter keamanan.
   * Bagaimana mekanisme Spring Security 6.x mengisolasi dan mengatasi kerentanan ini melalui `HandlerMappingIntrospector`?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: "The JWKS Cache Storm & Cascading Gateway Failure"
Sistem e-commerce skala besar (120 instance Spring Boot microservices diatur oleh Spring Cloud Gateway) memproses 75.000 req/sec saat promo Flash Sale. Tiba-tiba, Identity Team melakukan *emergency signing key rotation* di Keycloak karena insiden kebocoran sertifikat. 
Dalam waktu 15 detik, seluruh microservice mulai menolak request yang masuk dengan error `401 Unauthorized` atau timeout `504 Gateway Timeout`. Metrik menunjukkan load CPU pada internal Keycloak melonjak dari 15% ke 100%, menyebabkan connection pool Keycloak exhaust. Akibatnya, microservice gagal memvalidasi JWT yang baru, dan gateway hancur karena thread contention.

* **Pertanyaan Diagnostik:**
  1. Identifikasi *root cause* dari pola cascading failure ini terkait cara Spring Security JWT decoder menangani public key lookup saat menerima `kid` baru secara serentak.
  2. Rancang arsitektur cache multi-tier untuk JWKS yang tahan terhadap invalid key storming, membatasi *rate of upstream refresh*, dan mempertahankan graceful degradation tanpa melanggar prinsip integritas kriptografi.

---

### Skenario B: "The Cross-Tenant Identity Leak under High Concurrency"
Sebuah platform SaaS perbankan multi-tenant memproses transaksi batch menggunakan Spring Boot 3 dan Java 21 Virtual Threads. Data tenant diekstrak dari JWT claim `tenant_id` dan disimpan dalam custom context holder:
```java
public class TenantContextHolder {
    private static final ThreadLocal<String> CONTEXT = new ThreadLocal<>();
    public static void setTenantId(String tenantId) { CONTEXT.set(tenantId