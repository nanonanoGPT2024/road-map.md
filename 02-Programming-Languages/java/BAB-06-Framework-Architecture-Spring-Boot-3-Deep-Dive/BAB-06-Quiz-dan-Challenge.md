# BAB 06: Quiz, Challenge, & Knowledge Check
**Framework Architecture: Spring Boot 3 Deep Dive**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Evolusi Auto-Configuration Discovery Mechanism
Pada Spring Boot 2.7 ke bawah, mekanisme auto-configuration bergantung penuh pada berkas `META-INF/spring.factories` di bawah antarmuka `EnableAutoConfiguration`. Namun, sejak Spring Boot 3.0, arsitektur ini digantikan secara permanen oleh `META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`.
* **Pertanyaan:** Jelaskan motivasi arsitektural di balik pemisahan ini terkait pemisahan *concern* (separation of concerns), performa *context startup*, dan kesiapan kompilasi AOT (*Ahead-Of-Time*) pada Spring Framework 6. Bagaimana annotasi `@AutoConfiguration` menggantikan `@Configuration` biasa dalam konteks urutan pemuatan (*ordering phase*)?

### Soal 1.2: Siklus Hidup ApplicationContext dan Fase Intersepsi Bean
`ApplicationContext` mengelola siklus hidup komponen dari pembacaan metadata hingga penghancuran (*destruction*).
* **Pertanyaan:** Uraikan fase eksekusi kronologis yang dilalui sebuah bean di dalam `DefaultListableBeanFactory` ketika Spring Boot melakukan *bootstrap*. Secara spesifik, bedakan peran dan *execution timing* antara `BeanFactoryPostProcessor` (misal: penanganan `@ConfigurationProperties` atau resolving place-holder) dan `BeanPostProcessor` (misal: inisialisasi proxy CGLIB/JDK Dynamic Proxy). Pada fase mana tepatnya dependensi diinjeksi?

### Soal 1.3: Migrasi Namespace Jakarta EE 10 dan Dampak Bytecode Runtime
Spring Boot 3 mewajibkan baseline minimum Java 17 dan migrasi total dari Java EE (`javax.*`) ke Jakarta EE 9/10 (`jakarta.*`).
* **Pertanyaan:** Mengapa transisi ini bukan sekadar operasi *search-and-replace* impor package biasa pada tingkat kompilasi? Jelaskan dampaknya terhadap manipulasi *bytecode* runtime (seperti CGLIB, Byte Buddy), serialisasi data, integrasi *third-party legacy reflection*, dan validasi spesifikasi (*Jakarta Bean Validation* vs *Hibernate Validator engine*).

### Soal 1.4: Mekanisme Dynamic Proxying dan *Self-Invocation Trap*
Spring Framework menggunakan CGLIB (secara default di Spring Boot via `proxyTargetClass=true`) atau JDK Dynamic Proxies untuk menerapkan fitur deklaratif seperti `@Transactional`, `@Async`, dan `@Cacheable`.
* **Pertanyaan:** Jelaskan secara mekanistis bagaimana objek proxy mencegat panggilan method (*invocation interception*). Mengapa *self-invocation* (sebuah method memanggil method beranotasi transaksi lain dalam bean yang sama melalui referensi `this`) menyebabkan interceptor transaksi dilewati sepenuhnya? Bagaimana arsitektur `AopContext.currentProxy()` mengatasi batasan ini dan apa konsekuensi perancangannya?

### Soal 1.5: Unifikasi Observabilitas: Micrometer Observation API
Pada rilis sebelumnya, instrumentasi metrik dan tracing dilakukan secara terpisah (misalnya melalui Micrometer Metrics dan Spring Cloud Sleuth). Spring Boot 3 mengadopsi Micrometer 1.10+ Observation API sebagai layer abstraksi tunggal.
* **Pertanyaan:** Bagaimana antarmuka `Observation` menyatukan *lifecycle* pengumpulan metrik (timings/counters) dan tracing kontekstual (span/trace ID)? Jelaskan peran `ObservationHandler` dan bagaimana tracing context dipropagasikan melintasi batas thread secara deterministik tanpa terjadi *memory leak* pada `ThreadLocal`.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Resolusi Circular Dependency dan Penghapusan Default Permissive
Mulai Spring Boot 2.6 dan diperketat pada Spring Boot 3.0, *circular references* antar-bean dinonaktifkan secara bawaan (`spring.main.allow-circular-references=false`).
* **Pertanyaan:** Jelaskan cara kerja *three-level cache* pada `DefaultSingletonBeanRegistry` (`singletonObjects`, `earlySingletonObjects`, `singletonFactories`) dalam menangani siklus dependensi. Mengapa penggunaan bean ber-proxy (seperti yang dianotasikan `@Async`) membuat resolusi *circular reference* gagal secara fatal dengan melempar `BeanCurrentlyInCreationException`, meskipun dependensi sirkular secara teori diizinkan?

### Soal 2.2: AOT Engine, Closed-World Assumption, dan RuntimeHintsRegistrar
Spring Boot 3 mendukung kompilasi native GraalVM melalui Spring AOT Engine. AOT bekerja di bawah paradigma *Closed-World Assumption*.
* **Pertanyaan:** Debug kasus berikut: Sebuah aplikasi Spring Boot 3 berjalan sukses di JVM standar, namun saat dikompilasi menjadi GraalVM Native Image, aplikasi mengalami crash saat startup dengan error `InstantiationException` atau menghasilkan `null` saat memetakan payload JSON dinamis menggunakan Jackson. Bagaimana AOT Engine memproses Bean Definition saat *build-time*, dan bagaimana Anda mengimplementasikan `RuntimeHintsRegistrar` untuk mendaftarkan refleksi, serialisasi, dan resource metadata secara presisi?

### Soal 2.3: Virtual Threads (Project Loom) dan Ancaman Carrier Thread Pinning
Spring Boot 3.2+ menyediakan integrasi satu baris perintah untuk Java 21 Virtual Threads: `spring.threads.virtual.enabled=true`.
* **Pertanyaan:** Bagaimana integrasi ini mengubah model konkurensi pada embedded Tomcat dan task execution `@Async`? Analisis kondisi struktural kode Java yang memicu *Carrier Thread Pinning* (misalnya penggunaan blok `synchronized` yang membatalkan unmounting dari OS carrier thread vs `ReentrantLock`). Bagaimana Anda mendeteksi kejadian pinning ini menggunakan JDK Flight Recorder (JFR) dan event `jdk.VirtualThreadPinned`?

### Soal 2.4: Determinisme Evaluasi Kondisional (@Conditional Architecture)
Ketika merancang enterprise starter kustom, urutan evaluasi kondisi menjadi sangat kritis.
* **Pertanyaan:** Misalkan Anda memiliki auto-configuration class yang dianotasikan dengan `@ConditionalOnClass(A.class)`, `@ConditionalOnMissingBean(B.class)`, dan `@ConditionalOnBean(C.class)`. Jika `B` didefinisikan oleh auto-configuration lain, bagaimana Spring Boot menjamin bahwa auto-configuration Anda tidak dievaluasi terlalu dini sebelum bean `B` sempat terdaftar? Jelaskan peran `@AutoConfigureBefore`, `@AutoConfigureAfter`, dan bagaimana menguji skenario ini menggunakan `ApplicationContextRunner`.

### Soal 2.5: Binding Engine @ConfigurationProperties dan Custom Converters
Mekanisme validasi dan data-binding properties mengalami refactoring menyeluruh di Spring Boot 3, terutama pada dukungan immutable records.
* **Pertanyaan:** Bagaimana `ConfigurationPropertiesBindingPostProcessor` memanfaatkan `Binder` API internal untuk mengikat konfigurasi hierarchical YAML ke dalam Java Record (Constructor Binding)? Jika terdapat custom data type (misalnya durasi dalam format kompleks `7d:12h` atau representasi IP CIDR), jelaskan tahapan teknis menginjeksi `@ConfigurationPropertiesBinding` kustom tanpa merusak fallback mekanisme `ConversionService` bawaan Spring.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Large-Scale Starvation & Virtual Thread Carrier Pinning Incident
**Konteks Sistem:**
Sebuah payment gateway berbasis Spring Boot 3.2 (Java 21) menangani rata-rata 12.000 Request Per Second (RPS). Arsitektur dijalankan di atas AWS EKS dengan konfigurasi `spring.threads.virtual.enabled=true`. Pool koneksi database menggunakan HikariCP terhubung ke Amazon Aurora PostgreSQL. Aplikasi menggunakan legacy SDK internal untuk melakukan enkripsi token kartu sebelum menulis ke database.

**Insiden:**
Saat traffic melonjak pada event belanja nasional, latensi P99 meroket dari 45ms menjadi 28 detik. Utilisasi CPU pada pod aplikasi mendekati 100%, metrik aktif virtual thread meningkat eksponensial hingga 80.000+, namun *throughput* turun drastis ke 400 RPS. HikariCP melaporkan error:
```text
Connection is not available, request timed out after 30000ms (total=50, active=50, idle=0, waiting=1240)
```
Thread dump menunjukkan ribuan Virtual Thread dalam state `BLOCKED` atau `WAITING`, dan ratusan event JFR mencatat `jdk.VirtualThreadPinned`.

```java
// Snippet Legacy Tokenizer SDK yang digunakan di Controller/Service
public class LegacyCardTokenizer {
    private final MessageDigest digest; // Non-thread-safe legacy instance

    public LegacyCardTokenizer() throws NoSuchAlgorithmException {
        this.digest = MessageDigest.getInstance("SHA-256");
    }

    public synchronized String tokenize(String pan) {
        digest.reset();
        byte[] hash = digest.digest(pan.getBytes(StandardCharsets.UTF_8));
        return Base64.getEncoder().encodeToString(hash);
    }
}
```

**Pertanyaan Diagnostik:**
1. Bedah akar penyebab struktural (*root cause*) mengapa kombinasi Virtual Threads, method `synchronized` pada `LegacyCardTokenizer`, dan HikariCP pool menyebabkan *deadlock* semu dan kehabisan carrier thread pada sistem tersebut.
2. Mengapa menaikkan kapasitas HikariCP pool (misal: menjadi 500 koneksi) pada skenario ini justru memperparah kondisi kegagalan sistem (*catastrophic cascade failure*)?
3. Rancang arsitektur perbaikan komprehensif tanpa mematikan fitur Virtual Threads, mencakup refactoring konkurensi tokenizer, rekonfigurasi HikariCP, dan implementasi isolasi pool (bulkhead).

---

### Skenario B: Race Condition dan Transaction Boundary Leakage pada Asynchronous Pipeline
**Konteks Sistem:**
Platform e-commerce menggunakan Spring Boot 3.1 untuk memproses checkout inventaris tinggi. Alur pemrosesan pesanan melibatkan pemotongan saldo dompet pelanggan, alokasi inventaris gudang, dan pengiriman notifikasi email/webhook.

**Implementasi Kode Bermasalah:**
```java
@Service
public class OrderProcessingService {

    @Autowired
    private InventoryRepository inventoryRepository;
    @Autowired
    private OrderRepository orderRepository;
    @Autowired
    private NotificationDispatcher notificationDispatcher;

    @Transactional
    public OrderResponse processOrder(OrderRequest request) {
        Inventory inventory = inventoryRepository.findByProductIdForUpdate(request.getProductId())
                .orElseThrow(() -> new StockNotFoundException());

        if (inventory.getAvailableStock() < request.getQuantity()) {
            throw new InsufficientStockException("Out of stock");
        }

        inventory.setAvailableStock(inventory.getAvailableStock() - request.getQuantity());
        inventoryRepository.save(inventory);

        Order order = new Order(request.getUserId(), request.getProductId(), request.getQuantity());
        order = orderRepository.save(order);

        // Memanggil asynchronous dispatch
        notificationDispatcher.dispatchOrderCreatedNotification(order);

        return new OrderResponse(order.getId(), OrderStatus.CONFIRMED);
    }
}

@Component
public class NotificationDispatcher {

    @Autowired
    private OrderRepository orderRepository;
    @Autowired
    private AuditLogClient auditLogClient;

    @Async
    public void dispatchOrderCreatedNotification(Order order) {
        // Query status terbaru pesanan untuk verifikasi
        Order freshOrder = orderRepository.findById(order.getId())
                .orElseThrow(() -> new EntityNotFoundException("Order ID not found in Read-Committed DB!"));

        auditLogClient.publish(freshOrder);
    }
}
```

**Insiden:**
Di bawah beban konkurensi moderat (~800 checkout per detik untuk produk diskon), log sistem mencatat ratusan `EntityNotFoundException: Order ID not found in Read-Committed DB!` yang dilempar dari `NotificationDispatcher`. Lebih parah lagi, terdapat anomali di mana inventory terpotong, notifikasi gagal, namun respons ke pengguna menyatakan `CONFIRMED`.

**Pertanyaan Diagnostik:**
1. Jelaskan mengapa `orderRepository.findById(order.getId())` di dalam method `@Async` menghasilkan `EntityNotFoundException` meskipun method `save()` telah dipanggil sebelum pemanggilan task async.
2. Analisis interaksi transaksi database (tingkat isolasi *Read Committed*) terhadap pemisahan thread worker `@Async` dan siklus *flushing/commit* Hibernate. Mengapa objek `Order` belum tentu persisten saat thread async dieksekusi?
3. Bagaimana Anda merekayasa ulang arsitektur pemanggilan event ini menggunakan Spring `TransactionalEventListener` dan phase `TransactionPhase.AFTER_COMMIT`? Apa mitigasi yang harus diterapkan jika transaksi berhasil commit namun pengiriman notifikasi gagal?

---

### Skenario C: Trade-off Arsitektur Runtime: GraalVM Native Image vs. JIT with CRaC vs. JVM AppCDS
**Konteks Sistem:**
Sebuah platform perbankan digital berskala enterprise memiliki 150+ microservices Spring Boot 3.3. Arsitektur runtime saat ini menghadapi dua tantangan utama:
1. **Auto-scaling Latency:** Startup time microservice berbasis JVM standar memakan waktu 12–25 detik, terlalu lambat untuk merespons lonjakan lalu lintas mendadak pada sistem cloud-native (Kubernetes Horizontal Pod Autoscaler).
2. **Resource Footprint:** Setiap container rata-rata mengonsumsi 600MiB–1GiB memory RSS saat idle, menyebabkan pembengkakan tagihan infrastruktur cloud bulanan.

Divisi Enterprise Architecture mempertimbangkan tiga arah strategi runtime untuk modernisasi seluruh ekosistem:
* **Opsi 1:** GraalVM Native Image (AOT Compilation).
* **Opsi 2:** OpenJDK standard dengan CRaC (Coordinated Restore at Checkpoint).
* **Opsi 3:** OpenJDK HotSpot standar dengan AppCDS (Application Class Data Sharing) + Leyden optimizations.

**Pertanyaan Diagnostik:**
1. Bandingkan karakteristik arsitektur ketiga opsi di atas berdasarkan matriks:
   * Startup Time & Time-to-First-Request.
   * Peak Throughput (P99 Latency under heavy JIT C2 optimization vs GraalVM PGO).
   * Memory Footprint (Idle vs Peak Load RSS).
   * Kompleksitas Pipeline CI/CD dan Developer Experience (DevEx).
2. Pada jenis microservice seperti apa (misal: batch processing/event-driven vs long-running low-latency core banking transaction processing) GraalVM Native Image justru menjadi pilihan yang *suboptimal* dibandingkan standard HotSpot JIT?
3. Jika arsitektur mengadopsi CRaC (Checkpoint/Restore), jelaskan adaptasi siklus hidup bean Spring Boot yang harus dilakukan melalui antarmuka `org.crac.Resource` untuk menangani resource terbuka seperti koneksi TCP database (HikariCP) dan Kafka consumer offsets saat fase checkpointing dan restoration.

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise Multi-Tenant Dynamic Routing Starter dengan Observabilitas Terpadu & Keselarasan AOT

#### Problem Statement
Organisasi SaaS B2B Anda membutuhkan modularisasi engine multi-tenancy. Setiap kali ada HTTP request masuk, tenant ID diidentifikasi melalui header `X-Tenant-ID`. Sistem harus secara transparan mengarahkan koneksi database ke schema/database tenant yang bersangkutan melalui HikariCP connection pool terisolasi, menginjeksi observabilitas (Micrometer metrics & OpenTelemetry tracing) dengan tag `tenant.id`, serta mencegah *connection leakage*. Modul ini harus dibungkus dalam bentuk auto-configurable Spring Boot 3 Starter library (`tenant-routing-spring-boot-starter`).

#### Requirements
1. **Dynamic Routing Engine:**
   * Implementasikan `AbstractRoutingDataSource` yang dapat me-resolve database tenant berdasarkan konteks eksekusi saat ini.
   * Gunakan `ThreadLocal` berbasis context holder yang *leak-safe* (mengimplementasikan `AutoCloseable` untuk pembersihan via `try-with-resources`).
   * Jika header `X-Tenant-ID` tidak ditemukan atau tenant tidak valid, sistem harus melempar custom exception yang ditangani oleh Spring Boot `FailureAnalyzer` khusus untuk menghasilkan pesan diagnosa startup/runtime yang presisi.

2. **Custom Auto-Configuration:**
   * Buat auto-configuration terpisah menggunakan metadata Spring Boot 3: `META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`.
   * Konfigurasi harus bersifat *back-off* conditional (`@ConditionalOnMissingBean`, `@ConditionalOnClass`).
   * Bind properties konfigurasi tenant menggunakan Immutable Record beranotasi `@ConfigurationProperties(prefix = "enterprise.tenancy")`.

3. **Unified Observability Integration:**
   * Buat custom `ObservationConvention` atau `ObservationHandler` via Micrometer 1.10+.
   * Setiap query database dan HTTP transaction wajib memiliki high-cardinality/low-cardinality tag `tenant.id` pada span OpenTelemetry dan metrics counter.

4. **GraalVM Native Image Compatibility:**
   * Sediakan `RuntimeHintsRegistrar` kustom.
   * Pastikan dynamic proxy reflection untuk datasource dan binding record terdaftar eksplisit sehingga starter ini tidak gagal saat dikompilasi menjadi GraalVM native binary.

#### Constraints
* **Baseline Framework:** Spring Boot 3.2.x atau 3.3.x, Java 21.
* **Concurrency:** Tidak boleh menggunakan blok `synchronized` yang memicu carrier thread pinning; gunakan struktur Java Concurrency non-blocking atau `ReentrantLock`.
* **Zero Legacy Namespace:** Tidak boleh ada satupun package berawalan `javax.*`.
* **Reliability:** Context thread local tidak boleh bocor ke worker pool Tomcat berikutnya (cegah *ThreadLocal pollution*).

#### Expected Output
1. **Kode Struktur Kelas Inti:**
   * `TenantContextHolder` (Context Management).
   * `TenantRoutingDataSource` (Dynamic Datasource Router).
   * `TenantProperties` (Record Configuration Properties).
   * `TenantRoutingAutoConfiguration` (Auto-configuration declaration).
   * `TenantFailureAnalyzer` (Penyaji diagnosa kegagalan).
   * `TenantRuntimeHints` (GraalVM AOT Registration).
2. **Metadata Files:**
   * Isi direktori `META-INF/spring/` dengan konfigurasi registrasi imports yang valid.
3. **Verification Test Case:**
   * Unit test menggunakan `ApplicationContextRunner` untuk memverifikasi kondisi context startup (sukses vs back-off).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Mekanisme parsing berkas `META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports` oleh `AutoConfigurationImportSelector`.
- [ ] Perbedaan fundamental antara `BeanFactoryPostProcessor`, `BeanDefinitionRegistryPostProcessor`, dan `BeanPostProcessor`.
- [ ] Alur proxying Spring AOP via CGLIB subclassing vs JDK dynamic interface proxy, serta mitigasi *self-invocation issue*.
- [ ] Cara kerja three-level cache Spring dalam inisialisasi bean dan mengapa circular reference dilarang secara default pada arsitektur modern.
- [ ] Closed-World Assumption pada GraalVM AOT dan mengapa reflection, serialization, serta dynamic proxy memerlukan explicit hints.
- [ ] Mekanisme internal Virtual Threads, perbedaannya dengan platform thread Tomcat, dan konsep *Carrier Thread Pinning*.
- [ ] Pola integrasi observabilitas Micrometer Observation API melintasi metrik, logging kontekstual (Baggage), dan tracing spans.
- [ ] Batasan propagasi transaksi deklaratif `@Transactional` saat melintasi batas thread async (`@Async`).

### Saya tidak perlu menghafal:
- [ ] Nama seluruh kelas internal auto-configuration bawaan Spring Boot (cukup pahami cara mencarinya via debug log `--debug`).
- [ ] Sintaks JSON eksak untuk GraalVM `reflect-config.json` manual (gunakan programmatic `RuntimeHintsRegistrar`).
- [ ] Parameter konfigurasi low-level Tomcat native APR (fokus pada abstraksi embedded container properties).
- [ ] Seluruh bytecode instruction yang dieksekusi CGLIB/Byte Buddy saat weaving proxy.

### Saya harus bisa melakukan:
- [ ] Mengembangkan custom enterprise production-ready Spring Boot Starter dengan modularitas penuh dan auto-configuration imports.
- [ ] Mendiagnosa dan memecahkan Carrier Thread Pinning menggunakan JDK Flight Recorder (JFR) dan Java Mission Control (JMC).
- [ ] Mengimplementasikan `ApplicationContextRunner` untuk menguji skenario startup bean dan kegagalan konfigurasi kondisional secara komprehensif.
- [ ] Menulis custom `RuntimeHintsRegistrar` untuk registrasi AOT hints pada aplikasi yang menargetkan native binary image.
- [ ] Mengonfigurasi `TransactionalEventListener` dengan fase commit database yang deterministik untuk mencegah race conditions pada arsitektur asinkron.
- [ ] Mengonfigurasi Micrometer `ObservationRegistry` untuk menyematkan custom enterprise tags ke seluruh span tracing dan metrik sistem.