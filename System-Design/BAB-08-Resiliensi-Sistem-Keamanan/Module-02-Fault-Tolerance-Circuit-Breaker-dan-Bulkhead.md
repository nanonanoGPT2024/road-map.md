# Module 02: Fault Tolerance — Circuit Breaker, Retry with Jitter, & Bulkhead

## 1. Learning Objective
Setelah menyelesaikan modul ini, Anda akan mampu:
- Memahami bagaimana satu microservice yang lambat dapat meruntuhkan seluruh ekosistem sistem (*Cascading Failure & Thread Pool Starvation*).
- Menguasai Finite State Machine dari **Circuit Breaker Pattern** (State: *CLOSED*, *OPEN*, *HALF-OPEN*).
- Merancang strategi pemulihan otomatis dengan **Exponential Backoff dan Jitter** untuk mencegah *Retry Storms*.
- Menerapkan **Bulkhead Pattern** untuk mengisolasi kegagalan pada kolam resource (*resource pools*) tertentu.

## 2. Prerequisite
- Memahami konsep Reverse Proxy, Gateway, dan Latency/Timeout dari Bab-bab sebelumnya.
- Pemahaman dasar thread pool dan koneksi socket TCP.

## 3. Concept
Dalam arsitektur microservices, kegagalan adalah sebuah kepastian, bukan pengecualian (*Failure is inevitable*). Yang membedakan arsitektur amatir dengan arsitektur enterprise adalah ketahanan terhadap kegagalan (*Fault Tolerance & Graceful Degradation*).

Jika Service A memanggil Service B, dan Service B mengalami degradasi (misal response time melambat dari 10ms menjadi 30 detik), thread pada Service A akan tertahan menunggu respon. Dalam hitungan detik, seluruh thread worker Service A habis (*thread exhaustion*). Akibatnya, Service A tidak bisa melayani request apapun dan ikut tumbang. Pola keruntuhan beruntun ini disebut **Cascading Failure**.

Tiga pola utama untuk menahan keruntuhan ini adalah:
1. **Circuit Breaker**: Memutuskan aliran request ke downstream service yang sedang sakit dan langsung mengembalikan fallback instan (*fail-fast*).
2. **Retry with Exponential Backoff & Jitter**: Memberi jeda eksponensial acak saat mencoba ulang request sementara.
3. **Bulkhead**: Memisahkan resource (thread pool/memory) per dependensi agar masalah di satu layanan tidak menenggelamkan layanan lain.

## 4. Why?
- **Melindungi Diri Sendiri (Self-Preservation)**: Jangan biarkan thread server Anda hang selama puluhan detik menunggu layanan partner yang sedang down.
- **Memberi Ruang Bernapas bagi Layanan yang Sakit**: Jika sebuah database sedang overload, membanjirinya dengan jutaan retry agresif dari 50 microservices akan memastikan database tersebut tidak akan pernah bisa bangkit kembali (*Thundering Herd*).

## 5. What?
### Finite State Machine Circuit Breaker (Michael Nygard Pattern):
1. **CLOSED (Normal)**:
   - Request diteruskan ke downstream service seperti biasa.
   - Circuit breaker menghitung jumlah kegagalan (atau rasio error rate) dalam jendela geser.
   - Jika rasio error melebihi ambang batas (misal: > 50% kegagalan dalam 10 detik), circuit breaker beralih ke state **OPEN**.
2. **OPEN (Putus / Sakit)**:
   - Semua request yang datang **langsung ditolak seketika (Fail-Fast)** tanpa memanggil downstream service sama sekali.
   - Circuit breaker mengeksekusi *Fallback Action* (misal: mengambil data dari cache lokal atau mengembalikan pesan default).
   - Timer *Cool-down / Reset Timeout* berjalan (misal: 10 detik).
3. **HALF-OPEN (Uji Coba Pemulihan)**:
   - Setelah cooldown timeout habis, circuit breaker mengizinkan sejumlah kecil request percobaan (*trial/probe requests*) lolos ke downstream.
   - Jika request percobaan sukses: downstream dianggap sudah sembuh, state kembali ke **CLOSED**.
   - Jika request percobaan gagal: downstream masih sakit, state kembali ke **OPEN** dan timer di-reset ulang.

### Exponential Backoff dengan Full Jitter
Rumus backoff murni:
$$\text{Wait Time} = \min(\text{Cap}, \text{Base} \times 2^{\text{attempt}})$$
Bahaya dari backoff murni: jika 1.000 client gagal bersamaan di detik $0$, semuanya akan me-retry bersamaan persis di detik $2$, lalu di detik $4$.  
**Full Jitter** menambahkan keacakan (*randomness*):
$$\text{Sleep} = \text{random}(0, \text{Wait Time})$$
Ini menyebarkan beban retry secara merata sepanjang garis waktu (*smoothes out the traffic spike*).

### Bulkhead Pattern
Mengambil inspirasi dari sekat kedap air kapal laut. Jika lambung kapal bocor di kompartemen 1, sekat kedap air mencegah air merembes ke kompartemen 2, 3, dan 4, sehingga kapal tetap terapung. Dalam software, pisahkan thread pool untuk masing-masing dependency:
- Pool A (50 threads): Untuk Core Payment Service.
- Pool B (10 threads): Untuk Recommendation Service.
Jika Recommendation Service macet, hanya 10 thread yang hang. 50 thread Payment tetap berjalan mulus!

## 6. How?
### Alur Integrasi Circuit Breaker & Fallback:
```text
[Client Request] ──> [Circuit Breaker Wrapper]
                            │
              ┌─────────────┴─────────────┐
        [State: CLOSED]             [State: OPEN]
              │                           │
    [Call Remote Service]                 │ (Fail Fast!)
         │          │                     ▼
     (Sukses)    (Timeout/5xx)     [Execute Fallback]
         │          │                     │
      (Return)   (Catat Error)            └──> Return Cached / Default Data
                    │
           (Error Rate > 50%?)
                    │
            [Transisi ke OPEN]
```

## 7. Analogy
- **Circuit Breaker = Sekring Listrik Rumah**: Jika terjadi korsleting pada mesin cuci, sekring MCB di meteran listrik langsung "jeglek" (trip / OPEN) untuk memutus arus. Rumah Anda tidak terbakar dan lampu ruang tamu tetap bisa menyala.
- **Bulkhead = Kompartemen Kapal Titanic**: Air yang masuk ke satu tangki tidak boleh membanjiri ruang mesin utama.
- **Retry with Jitter = Mengantri di Pintu Toilet Pesawat**: Jika pintu toilet terkunci, Anda tidak mengetuk pintu setiap 1 detik. Anda kembali duduk, lalu menunggu secara acak antara 1 sampai 5 menit sebelum mengecek kembali.

## 8. Diagram

```text
               ┌────────────────────────────────────────┐
               │                                        │
               │   Semua Trial Requests Berhasil       │
               ▼                                        │
        ┌─────────────┐     Error Rate > Threshold    ┌────────────┐
        │   CLOSED    │──────────────────────────────>│    OPEN    │
        └─────────────┘                               └────────────┘
               ▲                                            │
               │                                            │ Cooldown
               │                                            │ Timer Habis
               │        Trial Request Gagal                 ▼
               └──────────────────────────────────────┌─────────────┐
                                                      │  HALF-OPEN  │
                                                      └─────────────┘
```

## 9. Simple Example
Fallback Skenario:
- Layanan Berita / Feed: Jika News Service down, fallback mengembalikan 5 berita terpopuler kemarin yang tersimpan di hardcoded JSON lokal. Pengguna tetap melihat halaman berisi berita daripada layar putih error `500 Internal Server Error`.
- E-Commerce Product Detail: Jika Review Service down, halaman produk tetap menampilkan tombol "Beli", foto produk, dan harga. Hanya tab ulasan yang bertuliskan *"Ulasan sementara tidak dapat dimuat"*.

## 10. Practical Example: Netflix Hystrix / Resilience4j
Netflix menciptakan pustaka legendaris *Hystrix* setelah insiden di mana microservice rekomendasi film mereka down dan menghabiskan seluruh Tomcat HTTP thread pool di ribuan server streaming, menyebabkan seluruh homepage Netflix mati total di seluruh dunia. Dengan Circuit Breaker, saat rekomendasi film down, homepage tetap terbuka dalam 15ms dengan menyajikan fallback daftar default tanpa rekomendasi personal.

## 11. Real World Example
- **AWS SDK**: Secara default mengimplementasikan *Exponential Backoff with Full Jitter* pada semua panggilan API S3, DynamoDB, dan EC2.
- **Uber**: Menerapkan bulkhead ketat antara proses dispatch pengemudi (*critical path*) dan sistem estimasi waktu tiba (ETA). Jika satelit routing traffic macet, pengemudi tetap bisa menerima order pesanan.

## 12. Trade-offs

| Pendekatan | Keuntungan | Kerugian |
|---|---|---|
| **No Circuit Breaker** | Kode sangat sederhana, tanpa state | Rentan total cascading system failure |
| **Circuit Breaker** | Isolasi kegagalan, fail-fast instan, melindungi downstream | Butuh penanganan Fallback yang elegan, overhead monitoring |
| **Aggressive Retry** | Cepat pulih jika kegagalan murni sesaat (*packet drop*) | Memperparah overload server downstream (*Retry Storm*) |
| **Exponential Backoff + Jitter**| Sangat aman bagi downstream, meratakan lonjakan traffic | Menambah latensi untuk client yang gagal |
| **Bulkhead Pattern** | Mencegah kehabisan thread total | Overhead memory untuk mengelola multiple thread/connection pools |

## 13. When To Use
- Pada **setiap panggilan RPC / HTTP lintas jaringan** antar microservices.
- Pada setiap integrasi API pihak ketiga (Payment Gateway, Kurir Logistik, SMS Provider, Email Service).
- Panggilan ke database atau cache cluster eksternal.

## 14. When NOT To Use
- Panggilan in-memory internal (fungsi lokal di dalam runtime proses yang sama).
- Idempotent background batch jobs yang tidak memiliki interaksi pengguna real-time (cukup gunakan antrian retry bertahap).

## 15. Common Mistakes
1. **Menggunakan Timeout yang Terlalu Panjang**: Default timeout HTTP client di banyak bahasa pemrograman adalah tidak terbatas (*infinite*) atau 60 detik! Jika downstream hang, ratusan koneksi akan tertahan selama 1 menit penuh. Selalu set timeout agresif (misal: 1 - 2 detik).
2. **Me-retry Pesan Non-Idempoten**: Me-retry request `POST /charges` yang timeout jaringan bisa menyebabkan kartu kredit pelanggan terdebit dua kali jika tidak ada idempotency key!
3. **Fallback Melemparkan Error Baru**: Fungsi fallback mencoba memanggil database sekunder yang ternyata juga down, menyebabkan crash tak tertangani. Fallback harus sesederhana mungkin (memory/cache).

## 16. Best Practices
- **Fail Fast**: Lebih baik mengembalikan error dalam 10 milidetik daripada membuat pengguna menunggu 30 detik untuk hasil error yang sama.
- **Dynamic Threshold Tuning**: Atur threshold (misal: buka sirkuit jika 5 dari 10 request terakhir gagal, atau jika latency p99 > 3 detik).
- **Circuit Breaker Metrics Dashboard**: Pantau state circuit breaker di Prometheus/Grafana. Peringatkan tim (*alert*) segera setelah circuit breaker berpindah ke state *OPEN*.

## 17. Troubleshooting
- **Masalah: Circuit Breaker langsung loncat ke OPEN padahal downstream service normal**.
  - *Sebab*: Batas volume minimum (*minimum request volume*) terlalu kecil (misal: threshold diset 50% error, dan dari 2 request pertama ada 1 request gagal karena validasi 400).
  - *Solusi*: Tambahkan syarat *minimum throughput* (misal: baru evaluasi persentase error setelah minimal ada 20 request dalam jendela evaluasi).

## 18. Hands-on Practice
Mari kita buktikan secara visual bagaimana Circuit Breaker bertransisi dari *CLOSED* $\rightarrow$ *OPEN* (fail fast) $\rightarrow$ *HALF-OPEN* (probe test) $\rightarrow$ pulih ke *CLOSED* melalui script simulasi di `hands-on/m02/circuit_breaker_demo.js`.

## 19. Exercises & Challenge
- **Exercise**: Jika base backoff adalah 100ms dan multiplier adalah 2, hitung batas maksimum waktu tunggu pada retry ke-4 dengan rumus exponential backoff sebelum jitter. (Jawaban: $100 \times 2^4 = 1600\text{ms}$).
- **Challenge**: Rancang implementasi Bulkhead sederhana menggunakan `Semaphore` atau Worker Pool terbatas di mana pemanggilan ke Payment API dibatasi maksimal 5 concurrent calls, sedangkan pemanggilan ke Inventory dibatasi 20 concurrent calls.

## 20. Summary
Resiliensi adalah pilar utama keandalan sistem berskala besar. Melalui kombinasi **Circuit Breaker** untuk memotong rantai kegagalan, **Retry with Jitter** untuk mencegah badai trafik, dan **Bulkhead** untuk menyekat kolam resource, sistem dapat bertahan dan tetap melayani pelanggan meskipun beberapa komponen internalnya sedang mengalami gangguan.
