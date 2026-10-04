# Bab 06: Serverless Architecture & Event-Driven Systems — Quiz & Challenge

---

## Bagian 1: Basic Questions (5 Soal)

### Soal 1
Fase manakah dalam siklus hidup eksekusi AWS Lambda yang bertanggung jawab atas terjadinya latensi *Cold Start*?
- A. Handler execution phase saat fungsi menerima payload JSON.
- B. Shutdown phase saat container dimatikan secara mendadak.
- C. Init phase yang mencakup Extension init, Runtime init, dan Function/Static init.
- D. Callback phase saat fungsi mengirimkan status code HTTP ke API Gateway.

> **Kunci Jawaban**: **C**  
> **Penjelasan**: *Cold start* terjadi selama *Init phase*. Pada fase ini, sistem AWS Lambda mengalokasikan microVM Firecracker, mengunduh arsip kode, menginisialisasi runtime bahasa pemrograman, dan mengeksekusi kode statis yang berada di luar blok *handler*.

---

### Soal 2
Manakah pernyataan yang benar mengenai perbedaan karakteristik performa dan fungsionalitas antara API Gateway HTTP API dan API Gateway REST API?
- A. REST API memiliki latensi jauh lebih rendah dan biaya 70% lebih murah daripada HTTP API.
- B. HTTP API mendukung validasi request berbasis schema JSON secara native tanpa bantuan Lambda.
- C. HTTP API dirancang untuk latensi ultra-rendah dan biaya lebih murah, namun tidak memiliki fitur native Request Validation dan API Keys Usage Plans yang dimiliki REST API.
- D. REST API hanya mendukung integrasi ke fungsi Lambda dan tidak dapat terhubung langsung ke HTTP endpoint eksternal.

> **Kunci Jawaban**: **C**  
> **Penjelasan**: HTTP API dipangkas secara arsitektural untuk memberikan latensi minimal (~50% lebih cepat) dan harga yang jauh lebih hemat dibanding REST API, namun fitur enterprise seperti native payload schema validation, XML translation, dan Usage Plans hanya tersedia di REST API.

---

### Soal 3
Apa peran utama parameter `VisibilityTimeout` pada Amazon SQS?
- A. Mengatur masa hidup maksimal sebuah pesan di dalam antrean sebelum dihapus secara otomatis.
- B. Menyembunyikan pesan dari consumer lain selama durasi waktu tertentu setelah pesan tersebut berhasil di-pull oleh sebuah consumer worker.
- C. Menunda pengiriman pesan baru ke antrean selama rentang waktu yang ditentukan (Delivery Delay).
- D. Mengunci seluruh partisi antrean FIFO agar tidak dapat diakses oleh thread paralel.

> **Kunci Jawaban**: **B**  
> **Penjelasan**: `VisibilityTimeout` mencegah worker lain mengambil dan memproses pesan yang sama saat pesan tersebut sedang diproses oleh consumer pertama. Jika worker pertama gagal atau mati sebelum menghapus pesan dan batas waktu habis, pesan tersebut akan kembali terlihat (*visible*) untuk diproses ulang.

---

### Soal 4
Dalam pola arsitektur *Fan-Out*, kombinasi layanan AWS manakah yang paling umum digunakan untuk mengirimkan satu event ke banyak antrean pemrosesan yang terisolasi?
- A. AWS Step Functions ke AWS CloudTrail.
- B. AWS Lambda ke Amazon Kinesis Video Streams.
- C. Amazon SNS Topic yang mendistribusikan pesan ke beberapa Amazon SQS Queues.
- D. Amazon EventBridge yang meneruskan data langsung ke Amazon Redshift tanpa perantara.

> **Kunci Jawaban**: **C**  
> **Penjelasan**: Pola Fan-out standar di AWS mengarahkan producer untuk mengirimkan pesan ke satu Amazon SNS Topic, yang kemudian secara otomatis menggandakan dan mendorong pesan tersebut ke beberapa Amazon SQS queues yang berlangganan secara paralel.

---

### Soal 5
Pada AWS Step Functions, jenis workflow manakah yang menjamin semantik eksekusi *Exactly-Once*, dapat berjalan hingga durasi 1 tahun, dan mencatat riwayat transisi status (*state execution history*) secara lengkap?
- A. Express Workflows.
- B. Standard Workflows.
- C. Synchronous Task Workflows.
- D. Dynamic Map Workflows.

> **Kunci Jawaban**: **B**  
> **Penjelasan**: Standard Workflows dirancang untuk proses bisnis berdurasi panjang (hingga 1 tahun) dengan auditabilitas penuh dan jaminan eksekusi *exactly-once execution*. Sebaliknya, Express Workflows memiliki durasi maksimum 5 menit dengan model eksekusi *at-least-once*.

---

## Bagian 2: Intermediate Questions (5 Soal)

### Soal 6
Sebuah fungsi AWS Lambda diintegrasikan dengan antrean Amazon SQS. Lambda tersebut dikonfigurasi dengan timeout 30 detik. Berapakah nilai `VisibilityTimeout` minimal yang direkomendasikan pada antrean SQS untuk mencegah *duplicate processing* yang tidak disengaja?
- A. Tepat 30 detik.
- B. Minimal 180 detik (6 kali batas timeout Lambda).
- C. 15 detik (setengah dari batas timeout).
- D. Tidak bergantung pada timeout Lambda asalkan Dead-Letter Queue telah dikonfigurasi.

> **Kunci Jawaban**: **B**  
> **Penjelasan**: AWS Best Practice secara eksplisit menetapkan bahwa `VisibilityTimeout` pada Amazon SQS harus disetel minimal 6 kali durasi timeout fungsi Lambda consumer. Hal ini memberikan jeda waktu yang cukup bagi Lambda Event Source Mapping untuk melakukan *retries* internal dan menangani proses *in-flight* sebelum pesan dilepaskan kembali ke antrean.

---

### Soal 7
Manakah konfigurasi Amazon SQS FIFO yang harus disertakan oleh producer untuk menjamin urutan pesan strictly sequential di dalam sebuah kategori transaksi pelanggan tertentu, tanpa memblokir pemrosesan paralel transaksi pelanggan lainnya?
- A. Mengisi `MessageDeduplicationId` yang identik untuk seluruh transaksi.
- B. Menetapkan nilai `MessageGroupId` unik berbasis ID Pelanggan (`customer_id`).
- C. Menonaktifkan fitur high-throughput mode pada konfigurasi antrean.
- D. Mengubah konfigurasi Lambda consumer menjadi *single-concurrency mode*.

> **Kunci Jawaban**: **B**  
> **Penjelasan**: `MessageGroupId` pada FIFO SQS bertindak sebagai kunci partisi. Pesan yang memiliki `MessageGroupId` yang sama dijamin akan diproses secara berurutan (*strictly in-order*), sementara pesan dengan `MessageGroupId` yang berbeda dapat dikonsumsi dan diproses secara paralel oleh consumer pool.

---

### Soal 8
Bagaimana cara kerja mekanisme *Partial Batch Response* (`ReportBatchItemFailures`) pada AWS Lambda yang mengonsumsi antrean SQS batch berukuran 10 pesan?
- A. Jika 1 pesan gagal, Lambda otomatis menghapus 9 pesan yang sukses dan melempar *runtime exception*.
- B. Lambda mengembalikan daftar objek ID pesan yang gagal (`batchItemFailures: [{"itemIdentifier": "id"}]`); SQS hanya akan mempertahankan pesan yang gagal tersebut agar tetap ada di antrean, sedangkan pesan yang sukses dihapus secara otomatis.
- C. Seluruh batch ditandai sebagai gagal dan dikirim langsung ke Dead-Letter Queue pada percobaan pertama.
- D. SQS memblokir seluruh consumer hingga batch yang gagal diperbaiki secara manual melalui AWS CLI.

> **Kunci Jawaban**: **B**  
> **Penjelasan**: Dengan menyalakan parameter `ReportBatchItemFailures`, fungsi Lambda tidak perlu menggagalkan seluruh batch jika hanya sebagian kecil pesan yang mengalami error. Lambda cukup mengembalikan array identifier dari pesan yang gagal, sehingga hanya pesan tersebut yang tetap berada di antrean atau di-retry, menghemat biaya komputasi dan mencegah redundansi.

---

### Soal 9
Kapan arsitek sistem harus memilih **Amazon EventBridge** dibandingkan **Amazon SNS** dalam arsitektur berbasis event?
- A. Ketika kebutuhan throughput melebihi 10 juta pesan per detik dengan latensi wajib di bawah 10ms.
- B. Ketika sistem membutuhkan perutean berbasis konten JSON yang kompleks (*content-based filtering*), integrasi SaaS pihak ketiga, dan fitur pencatatan schema (*Schema Registry*).
- C. Ketika sistem hanya perlu mengirimkan push notification via SMS ke perangkat seluler pelanggan.
- D. Ketika pengiriman data ditujukan secara eksklusif ke fungsi Lambda tanpa perlu filtering payload.

> **Kunci Jawaban**: **B**  
> **Penjelasan**: EventBridge dirancang secara khusus untuk perutean cerdas berbasis evaluasi struktur payload JSON tingkat lanjut, integrasi out-of-the-box dengan aplikasi SaaS (Salesforce, Datadog), serta memiliki Schema Registry dan kemampuan event archive/replay, sedangkan SNS lebih fokus pada pub/sub direct fan-out berlatensi sangat rendah.

---

### Soal 10
Pada AWS Step Functions yang mengimplementasikan **Distributed Saga Pattern**, bagaimana penanganan kegagalan transaksi lokal (misal: pembayaran kartu kredit ditolak) dijalankan secara arsitektural?
- A. Step Functions memanggil rollback native pada level database storage instance.
- B. Step Functions mengeksekusi blok status `Catch` yang memicu eksekusi *Compensating Transactions* (kebalikan dari tindakan sebelumnya, seperti membatalkan reservasi inventaris) untuk mengembalikan sistem ke status konsisten.
- C. Seluruh instance microservices dihentikan paksa (*terminated*) dan digantikan oleh instance baru.
- D. Klien menerima notifikasi timeout dan diwajibkan mengirimkan payload pembatalan secara manual.

> **Kunci Jawaban**: **B**  
> **Penjelasan**: Pada distributed systems, Saga Pattern menangani kegagalan dengan mengeksekusi transaksi kompensasi (*compensating transactions*). Jika sebuah tahapan gagal di tengah alur, blok `Catch` pada State Machine akan menangkap kegagalan tersebut dan memanggil fungsi-fungsi pembersih (misal: melepaskan inventaris yang sudah telanjur dipesan sebelumnya) untuk menjamin konsistensi data akhir (*eventual consistency*).

---

## Bagian 3: Scenario-Based Questions (3 Soal Kasus Nyata)

### Skenario 1: The Cascading Database Collapse
Sebuah platform e-commerce meluncurkan flash sale berskala masif. Tim arsitektur mengimplementasikan API Gateway HTTP API yang terhubung langsung ke AWS Lambda (`OrderProcessor`), yang kemudian menulis langsung ke basis data Amazon RDS PostgreSQL.
Saat flash sale dibuka, Lambda concurrency melonjak dari 100 ke 4.500 instance dalam waktu 45 detik. Akibatnya, RDS PostgreSQL mengalami kehabisan koneksi (*max connections reached*), CPU RDS mencapai 100%, seluruh transaksi checkout gagal dengan status HTTP 500, dan aplikasi mobile klien terus melakukan retry otomatis, memperburuk kondisi backend.

**Pertanyaan Kasus**:
Sebagai Lead Cloud & SRE Architect, desain ulang arsitektur sistem ini untuk melindungi database relasional downstream tanpa membatalkan pesanan pengguna, serta jelaskan parameter konfigurasi kunci yang harus diubah!

> **Solusi dan Analisis Komprehensif**:
> 1. **Penerapan Asynchronous Decoupling Boundary**:
>    - Hapus panggilan sinkron dari API Gateway langsung ke Lambda `OrderProcessor`.
>    - Sisipkan **Amazon SQS** di antara lapisan API Gateway dan Lambda. API Gateway dapat langsung memicu integrasi SQS secara langsung (*Direct Service Integration*) tanpa perantara komputasi, atau menggunakan Lambda ingestor tipis yang hanya memvalidasi token dan meletakkan pesan ke SQS.
>    - API Gateway segera mengembalikan respons HTTP `202 Accepted` beserta nomor resi/tracking order ke pengguna.
> 2. **Implementasi RDS Proxy**:
>    - Letakkan **Amazon RDS Proxy** di depan klaster Aurora/RDS PostgreSQL. RDS Proxy akan melakukan *connection pooling*, membagi ulang ribuan koneksi Lambda ke dalam pool koneksi database statis yang efisien, dan mencegah *connection starvation*.
> 3. **Concurrency Throttling & Smoothing Control**:
>    - Konfigurasikan **Maximum Concurrency** pada Event Source Mapping (ESM) Lambda yang membaca antrean SQS (misalnya dibatasi maksimum 150 concurrent workers).
>    - Dengan demikian, antrean SQS bertindak sebagai *shock absorber* (*load leveling*). Lonjakan 80.000 order ditampung secara aman di antrean dan diserap secara terukur oleh database sesuai kapasitas throughput penulisan maksimal tanpa pernah memicu *saturation crash*.

---

### Skenario 2: The E-Commerce Poison Pill Lockdown
Sistem pemrosesan pesanan menggunakan antrean Amazon SQS FIFO yang memicu fungsi AWS Lambda. Tiba-tiba, sebuah pesan dengan format JSON cacat (hilang atribut `order_id` akibat bug pada versi aplikasi klien lama) masuk ke dalam antrean.
Lambda melempar exception fatal (`KeyError: order_id`), gagal memproses pesan, dan terminasi secara abnormal. Karena antrean bertipe FIFO, seluruh proses pemrosesan pesanan untuk grup pelanggan tersebut terhenti total (*blocked*) selama 4 jam berturut-turut karena pesan cacat tersebut terus di-retry berulang kali di baris terdepan antrean.

**Pertanyaan Kasus**:
Identifikasi kesalahan konfigurasi pada antrean SQS FIFO tersebut dan rancang solusi komprehensif agar bug pada satu payload tidak memicu sistem terhenti total (*single point of pipeline failure*)!

> **Solusi dan Analisis Komprehensif**:
> 1. **Penyebab Utama**:
>    - Antrean FIFO memprioritaskan urutan strictly ordered per `MessageGroupId`. Jika pesan terdepan gagal dan tidak ada mekanisme pengalihan otomatis, SQS akan terus menyajikan pesan yang sama berulang kali setiap kali `VisibilityTimeout` berakhir, menyebabkan antrean terblokir (*poison pill scenario*).
> 2. **Konfigurasi Dead-Letter Queue (DLQ) & Redrive Policy**:
>    - Buat antrean **SQS FIFO DLQ** terdedikasi (`order-dlq.fifo`).
>    - Terapkan `RedrivePolicy` pada antrean utama dengan parameter `maxReceiveCount` disetel ke nilai moderat (misalnya: 3 atau 5).
>    - Setelah 3 kali percobaan gagal, SQS secara otomatis memindahkan pesan beracun tersebut ke DLQ tanpa campur tangan manual, sehingga pesan urutan berikutnya di antrean utama dapat kembali diproses.
> 3. **Defensive Programming pada Lambda Handler**:
>    - Gunakan penanganan error terstruktur (`try-except`) di dalam handler. Jika validasi skema pesan gagal akibat malformed format, kirimkan alert log terstruktur ke CloudWatch, simpan payload ke S3 bucket penampung invalid order, dan tangani error tersebut secara elegan tanpa membiarkan fungsi melempar uncaught runtime exception yang memicu retry tak berujung.
> 4. **Observabilitas**:
>    - Pasang CloudWatch Alarm pada metrik `ApproximateNumberOfMessagesVisible` milik DLQ untuk segera memberitahukan tim *on-call* SRE via PagerDuty/SNS saat ada pesan yang terisolasi ke DLQ.

---

### Skenario 3: Cross-Account Multi-Tenant Event Routing
Sebuah perusahaan SaaS enterprise memiliki arsitektur multi-akun AWS: Akun `Billing`, Akun `Logistics`, dan Akun `Notification`. Ketika pembayaran berhasil dicatat pada Akun `Billing`, sistem harus:
1. Memicu workflow provisioning di Akun `Logistics`.
2. Memicu pengiriman email invoice di Akun `Notification`.
3. Memastikan bahwa kegagalan sistem pada Akun `Logistics` tidak berdampak pada Akun `Notification`.
4. Menyediakan audit trail yang dapat di-replay jika terjadi insiden kepatuhan data finansial.

**Pertanyaan Kasus**:
Rancang arsitektur event bus terdistribusi menggunakan AWS EventBridge lintas akun (cross-account) yang memenuhi kebutuhan isolasi, reliabilitas, dan auditabilitas di atas!

> **Solusi dan Analisis Komprehensif**:
> 1. **Topology Amazon EventBridge Multi-Account**:
>    - Di Akun `Billing`, buat Custom Event Bus: `billing-event-bus`.
>    - Di Akun `Logistics` dan Akun `Notification`, buat event bus lokal di masing-masing akun (`logistics-bus` dan `notification-bus`).
> 2. **Cross-Account Permissions**:
>    - Konfigurasikan **Resource-based Policy** pada event bus di Akun `Logistics` dan `Notification` untuk mengizinkan aksi `events:PutEvents` yang berasal dari IAM Role atau AWS Principal Akun `Billing`.
> 3. **Content-Based Routing Rules**:
>    - Pada `billing-event-bus`, buat dua Rule EventBridge:
>      - **Rule 1 (Logistics Target)**: Evaluasi event pattern `{"detail-type": ["PaymentSuccess"]}` $\rightarrow$ Target: ARN `logistics-bus` di Akun `Logistics`.
>      - **Rule 2 (Notification Target)**: Evaluasi event pattern `{"detail-type": ["PaymentSuccess"]}` $\rightarrow$ Target: ARN `notification-bus` di Akun `Notification`.
>    - Karena EventBridge mengirimkan pesan secara independen ke masing-masing target, kegagalan pemrosesan atau keterlambatan pada Akun `Logistics` sama sekali tidak memengaruhi pengiriman event ke Akun `Notification` (*fault isolation*).
> 4. **Event Archiving and Replay**:
>    - Aktifkan fitur **EventBridge Archive** pada `billing-event-bus` dengan durasi retensi yang ditentukan (misalnya 365 hari).
>    - Jika terjadi insiden bug sistem pada Akun `Logistics` yang menyebabkan event gagal diproses selama 12 jam, tim SRE dapat memperbaiki bug aplikasi terlebih dahulu, kemudian menjalankan fitur **Replay** pada arsip event tersebut untuk memproses ulang event yang hilang tanpa perlu merekayasa ulang transaksi billing.

---

## Bagian 4: Practical Chapter Challenge

### Judul Tantangan:
**Membangun Distributed Flight Booking Saga Orchestrator dengan AWS Step Functions, EventBridge, SQS DLQ, dan Fault-Tolerance Recovery.**

### Deskripsi Masalah:
Anda ditugaskan merancang *Distributed Saga Pattern* untuk proses pemesanan tiket penerbangan (*Flight Booking System*) yang melibatkan 3 microservices independen:
1. **Seat Reservation Service**: Mengalokasikan kursi penerbangan sementara.
2. **Payment Processing Service**: Menagih dana ke gateway pembayaran perbankan.
3. **Customer Notification Service**: Menerbitkan boarding pass dan struk pembayaran.

Jika proses pembayaran gagal (misal: kartu kredit ditolak atau limit tidak mencukupi), sistem **wajib** mengeksekusi kompensasi atomik: membatalkan reservasi kursi penerbangan yang telah dilakukan di langkah pertama sehingga kursi tersebut kembali tersedia bagi pelanggan lain.

### Spesifikasi Teknis yang Wajib Dipenuhi:
1. **Orkestrasi State Machine**: Ditulis menggunakan format JSON Amazon States Language (ASL).
2. **Retry Strategy**: Pada status `ProcessPayment`, konfigurasikan strategi `Retry` dengan:
   - `ErrorEquals`: `["BankServiceUnavailableException"]`
   - `IntervalSeconds`: 2
   - `MaxAttempts`: 3
   - `BackoffRate`: 2.0
3. **Catch & Compensation Mechanism**:
   - Jika pembayaran gagal permanen (`PaymentDeclinedException` atau kehabisan retry), tangkap error tersebut via blok `Catch` dan alihkan alur secara visual ke state `CompensateSeatReservation`.
4. **Publish Event**:
   - Jika alur sukses penuh, kirim event `BookingSuccess` ke Amazon EventBridge.
   - Jika alur gagal total setelah kompensasi, kirim event `BookingFailed` ke Amazon EventBridge.
5. **Observabilitas**: Seluruh state transisi harus menyertakan pelacakan execution id / correlation id.

### Rubrik Penilaian:
- **Ketepatan Logika Saga (30%)**: Alur eksekusi maju (*forward path*) dan alur kompensasi (*rollback path*) terhubung tanpa celah konsistensi.
- **Konfigurasi Resilience (25%)**: Implementasi Retry, Catch, Exponential Backoff, dan pengalihan kegagalan terdefinisi secara presisi.
- **Standar Format ASL (25%)**: Validitas sintaks JSON Amazon States Language.
- **Observabilitas & Integrasi Event (20%)**: Emisi status akhir ke EventBridge event bus untuk integrasi downstream.

---