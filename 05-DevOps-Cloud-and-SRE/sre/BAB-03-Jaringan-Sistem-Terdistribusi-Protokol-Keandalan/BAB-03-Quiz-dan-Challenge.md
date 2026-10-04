# Evaluasi Bab 03: Jaringan Sistem Terdistribusi & Protokol Keandalan

## A. Basic Questions (5 Soal)

1. **Jelaskan perbedaan mendasar antara status socket `TIME_WAIT` dan `CLOSE_WAIT` di sistem operasi Linux! Sisi mana (client atau server) yang biasanya memegang masing-masing status tersebut?**
   - *Kunci Jawaban Singkat*: 
     - `TIME_WAIT`: Dimiliki oleh pihak yang melakukan *active close* (mengirim FIN pertama). Tujuannya adalah menunggu selama $2 \times \text{MSL}$ untuk memastikan ACK terakhir diterima oleh lawan dan paket lama hilang dari jaringan.
     - `CLOSE_WAIT`: Dimiliki oleh pihak yang menerima FIN (*passive close*) dan telah mengirimkan ACK, namun aplikasi lokalnya belum memanggil fungsi `close()` pada socket file descriptor tersebut. Ini hampir selalu mengindikasikan bug/leak aplikasi.

2. **Mengapa algoritma TCP CUBIC rentan terhadap masalah bufferbloat pada jaringan modern berkepasitas tinggi?**
   - *Kunci Jawaban Singkat*:
     TCP CUBIC adalah *loss-based congestion control*. CUBIC terus memperbesar Congestion Window ($cwnd$) sampai terjadi packet drop. Pada router/switch modern dengan buffer antrean yang besar, paket akan terus menumpuk di buffer tanpa di-drop, menyebabkan peningkatan latency (RTT membengkak) sebelum sinyal kongesti disadari oleh CUBIC.

3. **Apa perbedaan antara Exponential Backoff murni (tanpa jitter) dengan Exponential Backoff yang menggunakan Full Jitter?**
   - *Kunci Jawaban Singkat*:
     Tanpa jitter, interval retry bernilai deterministik ($T = \min(T_{max}, T_{base} \times 2^i)$), menyebabkan seluruh client yang gagal pada waktu yang sama akan mengirimkan retry secara serentak di masa depan (Thundering Herd). Full Jitter menambahkan variabel acak ($T_{sleep} = \text{random}(0, T)$), mendistribusikan beban retry secara merata sepanjang waktu.

4. **Sebutkan tiga status pada state machine Circuit Breaker pola Martin Fowler / Netflix Hystrix beserta fungsinya!**
   - *Kunci Jawaban Singkat*:
     - **Closed**: Aliran request normal; metrik kegagalan dipantau.
     - **Open**: Ambang kegagalan terlampaui; semua request digagalkan instan (*fail-fast*) tanpa menyentuh downstream.
     - **Half-Open**: Masa tunggu berakhir; sejumlah kecil request canary dilewatkan untuk menguji apakah downstream sudah pulih.

5. **Mengapa HTTP/2 dan gRPC multiplexing masih dapat mengalami masalah Head-of-Line (HoL) blocking pada layer transport (L4)?**
   - *Kunci Jawaban Singkat*:
     Karena HTTP/2 memultipleks seluruh stream logis ke dalam satu koneksi TCP fisik tunggal. Jika sebuah paket TCP hilang (*packet loss*), layer TCP kernel penerima harus menahan seluruh paket berikutnya di antrean buffer sampai paket yang hilang diretransmisi dan diterima, membekukan semua stream HTTP/2 yang menumpang di koneksi tersebut.

---

## B. Intermediate Questions (5 Soal)

1. **Mengapa TCP Keepalive bawaan OS (kernel default) sering kali tidak memadai untuk mendeteksi microservice downstream yang mengalami dead-lock atau freeze?**
   - *Kunci Jawaban Singkat*:
     TCP Keepalive dikelola langsung oleh network stack kernel Linux, bukan oleh runtime aplikasi. Jika proses aplikasi downstream mengalami infinite loop atau JVM GC pause (freeze) namun kernel OS masih aktif, kernel akan tetap membalas paket TCP Keepalive probe dengan TCP ACK. Akibatnya, client mengira koneksi masih sehat padahal aplikasi tidak lagi memproses request. Diperlukan heartbeat atau health check di L7 (Application layer).

2. **Jelaskan bahaya menerapkan Negative Caching DNS dengan TTL yang terlalu lama pada kluster Kubernetes yang sangat dinamis!**
   - *Kunci Jawaban Singkat*:
     Negative caching menyimpan respons `NXDOMAIN` (domain tidak ditemukan). Jika sebuah service client mencoba mengakses service target yang pod-nya baru saja memulai fase bootstrap, DNS query awal mungkin menghasilkan `NXDOMAIN`. Jika TTL negative caching tinggi (misal: 5 menit), client tersebut tidak akan bisa menyelesaikan alamat DNS service target selama 5 menit penuh, meskipun pod service target sudah berstatus `Ready` 2 detik kemudian.

3. **Bagaimana algoritma TCP BBR menentukan laju pengiriman paket tanpa mengandalkan packet drop sebagai indikator kongesti?**
   - *Kunci Jawaban Singkat*:
     BBR secara konstan membuat model estimasi dari physical path dengan mengukur dua parameter: Bottleneck Bandwidth ($\text{BtlBw}$) maksimum melalui pelacakan laju pengiriman tertinggi, dan Round-Trip Propagation Time ($\text{RTprop}$) minimum saat antrean kosong. Pengiriman data dibatasi pada nilai Bandwidth-Delay Product ($\text{BDP} = \text{BtlBw} \times \text{RTprop}$) untuk mencegah terjadinya antrean paket di buffer perantara.

4. **Kapan teknik Request Hedging aman digunakan, dan kapan teknik ini sangat terlarang? Berikan alasannya berdasarkan prinsip REST/RPC!**
   - *Kunci Jawaban Singkat*:
     - **Aman**: Pada operasi yang bersifat *idempotent* dan *side-effect free* (seperti query read-only `GET`, retrieval cache), di mana eksekusi berulang tidak mengubah state data.
     - **Terlarang**: Pada operasi *non-idempotent* (seperti `POST` pembayaran atau mutasi inventory), karena jika kedua request diproses bersamaan oleh downstream, akan terjadi duplikasi transaksi finansial atau inkonsistensi data.

5. **Apa fungsi parameter kernel `net.ipv4.tcp_tw_reuse = 1` dan apa prasyarat protokol yang harus aktif agar parameter ini bekerja secara aman?**
   - *Kunci Jawaban Singkat*:
     Parameter ini mengizinkan Linux kernel mereklamasi socket dalam status `TIME_WAIT` untuk koneksi keluar (*outgoing*) baru jika dinilai aman dari sisi protokol. Prasyarat utamanya adalah TCP Timestamps (`net.ipv4.tcp_timestamps = 1`) harus aktif di kedua sisi endpoint agar paket lama yang tersesat di jaringan dapat dibedakan dari paket koneksi baru berdasarkan validitas timestamp PAWS (*Protection Against Wrapped Sequence numbers*).

---

## C. Scenario-Based Questions (3 Kasus Nyata)

### Skenario 1: The Cascading Connection Pool Collapse
Sebuah layanan perbankan memiliki arsitektur: API Gateway -> Account Service -> PostgreSQL. Saat jam sibuk, database mengalami *lock contention* yang meningkatkan durasi query dari 20ms menjadi 8000ms. Dalam waktu 45 detik, API Gateway menolak semua koneksi baru dengan pesan error: `HTTP 500: dial tcp: lookup account-svc: socket: too many open files`.
- **Pertanyaan**:
  1. Jelaskan rantai kejadian teknis yang menyebabkan kehabisan file descriptor di API Gateway!
  2. Solusi L7 apa yang harus dipasang pada upstream client (API Gateway) untuk menghentikan degradasi ini dalam waktu < 2 detik?
- **Panduan Jawaban**:
  1. Query lambat -> thread/koneksi pada Account Service tertahan -> connection pool dari API Gateway ke Account Service habis -> API Gateway membuka koneksi TCP baru secara terus menerus untuk setiap request masuk -> koneksi TCP tidak kunjung selesai -> pemakaian File Descriptor (FD) melampaui `ulimit -n` host gateway -> penolakan alokasi socket baru.
  2. Implementasikan **Circuit Breaker** (dengan timeout ketat per call 500ms, ambang batas kegagalan 50% dalam window 2 detik) dan batasi ukuran maksimum connection pool dengan mekanisme fail-fast backpressure. Begitu circuit breaker berstatus `Open`, gateway langsung mengembalikan respons error dalam hitungan milidetik tanpa mengonsumsi socket baru.

### Skenario 2: The CoreDNS Thundering Herd
Sebuah kluster Kubernetes dengan 400 worker node menjalankan 5.000 pod worker yang melakukan polling setiap 1 detik ke domain internal `metadata.internal.corp`. Suatu ketika, switch jaringan rack utama mengalami restart selama 10 detik. Begitu switch online kembali, CoreDNS mengalami CPU throttling hingga 100% dan pod-pod melaporkan timeout resolusi DNS secara masif selama 30 menit berikutnya.
- **Pertanyaan**:
  1. Mengapa CoreDNS tidak mampu pulih secara mandiri meskipun jaringan fisik sudah kembali normal?
  2. Apa saja langkah arsitektural untuk menyelesaikan masalah ini secara permanen di level kluster dan aplikasi?
- **Panduan Jawaban**:
  1. Terjadi fenomena *Thundering Herd*: 5.000 pod melakukan retry koneksi secara bersamaan tanpa backoff/jitter. Semua pod mengirim query UDP DNS secara serentak ke CoreDNS. CoreDNS kehabisan antrean buffer UDP/CPU, menjatuhkan paket query, yang memicu 5.000 pod tersebut melakukan retry query DNS kembali dalam putaran loop yang tiada henti.
  2. Solusi:
     - Implementasikan **NodeLocal DNSCache** di Kubernetes untuk mengubah arsitektur query dari terpusat menjadi daemonset lokal di tiap node (mengeliminasi conntrack table locks dan network hop CoreDNS).
     - Perbaiki logic aplikasi client agar menyertakan **Exponential Backoff dengan Full Jitter** pada polling loop-nya.
     - Konfigurasikan cache TTL pada CoreDNS dan client runtime agar tidak melakukan query instan ulang saat terjadi kegagalan (*negative caching control*).

### Skenario 3: Tail-Latency pada Fan-Out Architecture
Layanan agregator *E-Commerce Search* mengirimkan sub-query paralel ke 30 search-shard services yang berbeda via gRPC untuk merender 1 halaman hasil pencarian. Latensi rata-rata ($p50$) tiap shard adalah 15ms, namun latensi $p99$ shard adalah 600ms. Akibatnya, latensi $p99$ agregator secara keseluruhan menjadi 650ms, merusak User Experience.
- **Pertanyaan**:
  1. Mengapa agregasi fan-out ke 30 backend menyebabkan latensi $p99$ agregator mendekati latensi terburuk shard secara konsisten?
  2. Bagaimana arsitektur **Request Hedging** dapat diimplementasikan di client agregator untuk menekan latensi $p99$ agregator mendekati angka < 50ms tanpa membebani backend berlebihan?
- **Panduan Jawaban**:
  1. Probabilitas sebuah request keseluruhan berjalan cepat ditentukan oleh komponen terlambat: $P(\text{all succeed in } t) = (P(\text{shard} < t))^{30}$. Jika peluang satu shard melampaui $p99$ adalah 1%, probabilitas setidaknya satu dari 30 shard mengalami lambat $p99$ adalah $1 - (1 - 0.01)^{30} \approx 26.2\%$. Artinya, 1 dari 4 request agregasi akan terkena dampak kelambatan $p99$.
  2. Terapkan Request Hedging terukur:
     - Tetapkan threshold p95 dari riwayat komunikasi shard (misal: 30ms).
     - Kirim request pertama ke Shard Replica A. Jalankan timer asinkron 30ms.
     - Jika respons belum tiba saat timer habis, kirim request spekulatif (hedged request) ke Shard Replica B.
     - Ambil respons pertama yang selesai, lalu batalkan (cancel) context stream gRPC pada request yang kalah.
     - Batasi *maximum hedging quota* (misal: maksimal 5% dari total traffic) agar backend tidak mengalami overload jika sistem mengalami degradasi kapasitas global.

---

## D. Practical Chapter Challenge

### Judul Tantangan:
**Membangun Jaringan Terdistribusi Tangguh (High-Reliability Client Layer) Melawan Network Partition dan Latency Spikes.**

### Skenario:
Anda adalah Staff SRE yang ditugaskan membangun library client HTTP inter-service resilient dalam ekosistem internal perusahaan. Anda diminta membuat simulasi mandiri dan pembuktian performa protokol keandalan dalam menangani backend server yang memiliki karakteristik:
1. $70\%$ request selesai normal dalam 10ms.
2. $20\%$ request mengalami lonjakan tail-latency hingga 800ms (akibat GC pause spekulatif).
3. $10\%$ request gagal dengan status error HTTP 500 / Network Drop.

### Tugas yang Harus Diselesaikan:
1. Buat kode simulasi client yang menerapkan gabungan:
   - **Circuit Breaker** (State: Closed, Open, Half-Open).
   - **Exponential Backoff dengan Full Jitter**.
   - **Request Hedging** untuk memotong kelambatan request yang melampaui ambang latensi $p90$.
2. Buktikan melalui output statistik perbandingan antara:
   - **Client Tanpa Protokol Keandalan (Baseline)**: Menghasilkan kegagalan tinggi dan latency $p99$ tinggi.
   - **Client Resilient (CB + Jitter + Hedging)**: Menurunkan latensi $p99$ secara drastis dan mengisolasi downstream failure.

*(Implementasi teknis lengkap tantangan ini tersedia pada file `hands-on/m01/circuit_breaker_backoff_sim.py`)*.