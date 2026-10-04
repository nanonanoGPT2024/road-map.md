# BAB 09: Quiz, Challenge, & Knowledge Check
**Bab 09: Prinsip Dasar Sistem Terdistribusi (Distributed Systems Core: Time, Consensus, & Fault Tolerance)**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Monotonic Clocks vs. Wall-Clock (Real-Time Clocks) dalam Penentuan Kausalitas**
   Mengapa penggunaan *Wall-Clock* (seperti `CLOCK_REALTIME` pada Linux atau sinkronisasi berbasis Network Time Protocol / NTP standard) secara fundamental cacat jika digunakan untuk mengurutkan kejadian (*event ordering*) pada sistem terdistribusi skala produksi? Jelaskan fenomena *clock skew*, *clock drift*, serta bahaya *leap seconds* dan koreksi waktu non-monotonik (langkah mundur / *stepping*) terhadap *data integrity*.

2. **Diferensiasi Matematis: Lamport Timestamps vs. Vector Clocks**
   Buktikan keterbatasan mendasar dari *Lamport Timestamps*: jika $L(a) < L(b)$, mengapa kita **tidak dapat** menyimpulkan bahwa kejadian $a$ menyebabkan kejadian $b$ ($a \rightarrow b$)? Bagaimana *Vector Clocks* mengatasi keterbatasan ini secara matematis untuk mendeteksi *concurrent events* (konkurensi murni) dan divergensi state?

3. **Dekonstruksi Teorema CAP & Realitas Teorema PACELC**
   Banyak insinyur salah mengartikan Teorema CAP sebagai kebebasan memilih kombinasi "Consistency, Availability, dan Partition Tolerance". Jelaskan mengapa partisi jaringan ($P$) adalah keniscayaan fisik (*non-negotiable*), bukan sebuah opsi konfigurasi. Lanjutkan dengan mendefinisikan Teorema PACELC: trade-off apa yang harus diambil oleh sebuah sistem ketika partisi jaringan **tidak** sedang terjadi?

4. **Karakteristik Formal: Safety vs. Liveness pada State Machine Replication (SMR)**
   Dalam konteks konsensus terdistribusi (seperti Raft atau Paxos), bedakan properti *Safety* ("nothing bad happens") dan *Liveness* ("something good eventually happens"). Berikan contoh konkret pelanggaran *Safety* versus pelanggaran *Liveness*, lalu jelaskan implikasi dari Teorema Impossibility FLP (Fischer, Lynch, Paterson) terhadap jaminan *Liveness* di jaringan asinkron murni.

5. **Disparitas Arsitektural: Two-Phase Commit (2PC) vs. Raft/Paxos**
   Jelaskan mengapa *Two-Phase Commit* (2PC) diklasifikasikan sebagai *Atomic Commitment Protocol* yang bersifat *blocking*, sedangkan Raft/Paxos adalah *Distributed Consensus Protocol* yang *non-blocking* (selama kuorum mayoritas terpenuhi). Apa yang terjadi pada cluster 2PC jika *Coordinator* mengalami crash permanen di tengah-tengah fase *Prepare* dan *Commit*?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Raft Disruption: Network Partition & Pre-Vote Mechanism**
   Bayangkan cluster Raft 5 node ($S_1, S_2, S_3, S_4, S_5$) di mana $S_1$ adalah Leader. Node $S_5$ terisolasi oleh partisi jaringan parsial. $S_5$ terus mengalami *election timeout*, menaikkan nilai `term`-nya berulang kali, lalu partisi pulih dan $S_5$ menyambung kembali ke cluster.
   - Apa yang terjadi pada $S_1$ dan cluster secara keseluruhan saat pesan dari $S_5$ diterima?
   - Bagaimana algoritma *Pre-Vote Phase* (seperti yang didefinisikan dalam disertasi Diego Ongaro) memitigasi *leadership disruption* ini?

2. **Garbage Collection dan State Explosion pada Vector Clocks**
   Dalam sistem penyimpanan *peer-to-peer* dinamis dengan ratusan klien yang menulis secara independen, array *Vector Clock* dapat membengkak tanpa batas (*state explosion*). Jika Anda menerapkan pemangkasan (*truncation*) atau *pruning* berbasis batas ukuran maksimum atau waktu, apa anomali kausalitas (*false causal dependency* atau penghapusan konflik palsu) yang dapat muncul? Bagaimana sistem seperti Dynamo atau Riak menangani risiko ini?

3. **Linearizability vs. Sequential Consistency dalam Implementasi Register**
   Diberikan trace eksekusi berikut pada register terdistribusi global:
   - Klien A menulis nilai $X = 1$ pada $t_1$, selesai (*ACK*) pada $t_3$.
   - Klien B menulis nilai $X = 2$ pada $t_2$, selesai (*ACK*) pada $t_4$ ($t_1 < t_2 < t_3 < t_4$).
   - Klien C membaca $X = 2$ pada $t_5$ ($t_5 > t_4$).
   - Klien D membaca $X = 1$ pada $t_6$ ($t_6 > t_5$).
   Apakah eksekusi di atas memenuhi kriteria *Sequential Consistency*? Apakah memenuhi kriteria *Linearizability*? Buktikan analisis Anda berdasarkan model waktu real-time eksternal.

4. **Analisis TrueTime API (Google Spanner) dan Wait-Out-The-Uncertainty**
   Google Spanner menggunakan arsitektur *TrueTime* API yang mengembalikan representasi waktu $[t.earliest, t.latest]$ dengan batas ketidakpastian $\epsilon$. Jelaskan bagaimana Spanner memanfaatkan mekanisme *commit wait* untuk menjamin konsistensi eksternal (*external consistency / linearizability*) tanpa perlu koordinasi lintas data center untuk operasi *read-only transaction*. Apa dampaknya terhadap write-latency jika offset ketidakpastian ($\epsilon$) melonjak dari 1ms menjadi 500ms akibat kegagalan GPS/Atomic clock?

5. **Asymmetric Network Partition (Gray Failure) & Flapping Leader**
   Sebuah cluster Paxos 3-node ($A, B, C$) mengalami gangguan switch jaringan yang menyebabkan partisi asimetris:
   - Node $A$ dapat mengirim dan menerima paket ke/dari $B$.
   - Node $B$ dapat mengirim dan menerima paket ke/dari $C$.
   - Node $A$ **tidak dapat** berkomunikasi langsung dengan Node $C$ (drop 100%).
   Analisis apa yang terjadi ketika $A$ mencoba menjadi Leader, lalu $C$ juga mencoba menjadi Leader. Mengapa mekanisme *heartbeat* standar gagal mempertahankan stabilitas cluster, dan modifikasi topologi apa yang wajib diterapkan pada layer transport?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Split-Brain dan Silent Data Corruption akibat Java GC Pause
Sebuah platform perbankan inti menggunakan cluster konsensus 3-node untuk mengelola *ledger* saldo rekening. Sistem mengandalkan mekanisme *Lease-based Leader Election* berdurasi 5 detik. 

**Insiden:**
Node 1 (Leader aktif) mengalami *Garbage Collection (GC) Stop-The-World* pause selama 7 detik akibat penumpukan objek berukuran besar di JVM Old Generation. Pada detik ke-5, Node 2 dan Node 3 mendeteksi hilangnya detak jantung (*heartbeat timeout*) dari Node 1, menggelar pemilu baru, dan mengangkat Node 2 sebagai Leader baru. Klien diarahkan ke Node 2 dan melakukan serangkaian transaksi mutasi dana.

Pada detik ke-7, JVM Node 1 melanjutkan eksekusi (*wake up*). Thread I/O Node 1 yang tertunda langsung mengeksekusi instruksi penyimpanan ke disk dan mengirimkan konfirmasi keberhasilan (*ACK*) ke klien lama tanpa memeriksa validitas kepemilikan *lease*. Terjadi *split-brain window* selama beberapa ratus milidetik yang mengakibatkan state divergensi fatal.

**Pertanyaan Diagnostik:**
1. Mengapa teknik pengecekan *lease* berbasis `System.currentTimeMillis()` di dalam kode aplikasi rentan terhadap anomali eksekusi seperti GC pause, CPU throttling (cgroups), atau VM hypervisor steal-time?
2. Bagaimana teknik **Fencing Tokens** (token yang terus bertambah / *monotonically increasing epoch*) dapat membatalkan mutasi liar dari Leader zombie (Node 1) pada level storage node secara deterministik?
3. Rancang arsitektur defensif pada level sistem operasi dan runtime (JVM) untuk memitigasi jeda tak terduga yang melampaui batas *election timeout*.

---

### Skenario B: Konflik Silent Overwrite pada Multi-Region Cassandra via Last-Write-Wins (LWW)
Sebuah sistem inventaris e-commerce berskala global mereplikasi data katalog produk ke 3 AWS Region (us-east-1, eu-west-1, ap-southeast-1) menggunakan Apache Cassandra dengan level konsistensi `LOCAL_QUORUM` dan resolusi konflik bawaan *Last-Write-Wins* (LWW) yang mengandalkan timestamp sisi klien.

**Insiden:**
Dalam program *Flash Sale*, satu unit produk langka tersisa. 
- Pada $T_{real} = 10:00:00.100$ UTC, Klien di London mengakses *eu-west-1* dan mengurangi stok menjadi 0. Jam sistem pada instance Klien London terkalibrasi secara benar oleh NTP.
- Pada $T_{real} = 10:00:00.050$ UTC (50ms lebih awal secara waktu fisik absolut), Klien di Singapura mengakses *ap-southeast-1* dan melakukan update stok menjadi 0. Namun, server frontend di Singapura mengalami *clock drift* positif ekstrem sebesar +500ms, sehingga mencatat timestamp $T_{req} = 10:00:00.550$ UTC.
- Cassandra menerima kedua mutasi. Karena menggunakan strategi LWW, mutasi dari Singapura menimpa mutasi dari London secara membabi-buta, bahkan membatalkan pembatalan pesanan yang sah.

**Pertanyaan Diagnostik:**
1. Bedah kelemahan mendasar dari model resolusi konflik *Last-Write-Wins* (LWW) dalam skala global tanpa jaminan batasan error waktu (*bounded clock error*).
2. Bagaimana Conflict-Free Replicated Data Types (**CRDTs**)—khususnya tipe data *P-N Counter* (*Positive-Negative Counter*) atau *LWW-Element-Set* dengan causal metadata—menyelesaikan masalah konkurensi inventaris ini secara deterministik tanpa bergantung pada sinkronisasi jam fisik?
3. Jika sistem tetap harus menggunakan database berbasis quorum non-CRDT, trade-off arsitektural apa yang wajib diambil (misal: penunjukan single-leader per SKU via *DynamoDB Global Tables with Strong Consistency* atau *Raft Partitioning*) dan apa dampaknya terhadap *availability* lintas benua?

---

### Skenario C: Kebuntuan Transaksi Terdistribusi Lintas Microservices (2PC vs. Saga)
Sebuah arsitektur microservices travel booking terdiri dari tiga layanan: `Flight-Service` (Database: PostgreSQL), `Hotel-Service` (Database: MySQL), dan `Payment-Service` (Database: Oracle). Arsitek awal memaksakan implementasi *Distributed Transaction* berbasis protokol XA/2PC (Two-Phase Commit) lintas service menggunakan broker transaksi terpusat untuk menjamin sifat ACID.

**Insiden:**
Saat traffic melonjak 10x lipat pada musim liburan, `Hotel-Service` mengalami *deadlock internal* dan degradasi latensi tinggi pada fase *Prepare*. Akibatnya:
- Ratusan koneksi transaksi pada `Flight-Service` dan `Payment-Service` tertahan dalam status *Prepared* dan menahan *row-level locks* pada tabel kunci.
- *Connection pool* pada semua database habis terpakai (*exhausted*), mengakibatkan kaskade kegagalan (*cascading failure*) yang melumpuhkan seluruh platform.
- Koordinator transaksi mengalami *Out-Of-Memory* (OOM) dan crash, meninggalkan puluhan ribu transaksi dalam kondisi menggantung (*in-doubt transactions*) yang tidak dapat di-rollback otomatis tanpa intervensi manual database administrator.

**Pertanyaan Diagnostik:**
1. Identifikasi anti-pattern struktural dari penerapan XA/2PC dalam arsitektur microservices modern yang terdistribusi secara logis dan fisik.
2. Rekonstruksi arsitektur transaksi ini menggunakan **Saga Pattern** (pilih antara *Choreography-based* atau *Orchestration-based*). Jelaskan bagaimana *Compensating Transactions* dieksekusi ketika salah satu tahapan (misal: reservasi hotel) gagal.
3. Karena Saga hanya memberikan jaminan *Eventual Consistency* (mengorbankan sifat *Isolation* / I dari ACID), bagaimana sistem menangani fenomena anomali bacaan (*dirty reads*) di mana pengguna melihat saldo berkurang dan kursi pesawat terpesan sementara reservasi hotel sebenarnya gagal dibatalkan?

---

## 4. Chapter Challenge

### Tantangan Praktis: Implementasi Distributed In-Memory Replicated State Machine (Mini-Raft Consensus Engine)

#### Problem
Anda diminta untuk membangun *core consensus engine* minimal berbasis algoritma Raft secara *from-scratch* (tanpa framework konsensus eksternal seperti etcd, Consul, atau Apache Ratis) untuk mengoordinasikan *in-memory key-value store* 3-node yang toleran terhadap *network partitions* dan *node crashes*.

#### Requirements
1. **Leader Election & State Transitions:**
   - Node harus mengimplementasikan 3 state: `Follower`, `Candidate`, dan `Leader`.
   - Gunakan *randomized election timeout* (misal: 150ms - 300ms) untuk mencegah fenomena *split vote*.
   - Implementasikan transisi term yang strictly monotonic. Kandidat hanya menjadi Leader jika berhasil mengumpulkan suara dari kuorum mayoritas ($\lfloor N/2 \rfloor + 1$).
2. **Log Replication & Heartbeats:**
   - Leader harus mengirimkan *AppendEntries RPC* secara periodik sebagai detak jantung (*heartbeat*) dan membawa muatan log (*log entries*).
   - Log entry hanya boleh di-*commit* ke state machine setelah terplikasi secara konsisten ke kuorum mayoritas.
   - Follower harus memvalidasi konsistensi log (`prevLogIndex` dan `prevLogTerm`). Jika terjadi divergensi log, Follower harus menolak mutasi dan Leader harus mundur (*backtrack*) untuk menyelaraskan log Follower.
3. **Network Fault Injection Harness:**
   - Buat simulasi layer transport (bisa berupa in-memory RPC atau simulated network layer over TCP) yang mampu menginjeksikan:
     - Partisi jaringan total (memisahkan 1 node dari 2 node lainnya).
     - *Packet drop* dan *latency delay* acak.
4. **Safety Verification:**
   - Implementasikan verifikasi kepemilikan nilai: Pastikan tidak ada 2 leader yang aktif secara bersamaan pada term yang sama (*Election Safety*).
   - Pastikan entri yang telah di-*commit* tidak pernah hilang atau ditimpa oleh Leader baru (*Leader Append-Only* & *Log Matching Property*).

#### Constraints
- **Bahasa yang Disarankan:** Go, Rust, atau C++ (karena kontrol konkurensi native, goroutine/threads, dan channel sangat cocok untuk protokol konsensus). Jika menggunakan Python/Node.js, gunakan *asyncio* secara ketat.
- **Dilarang:** Menggunakan third-party distributed sync library (dilarang menggunakan Zookeeper, Redis lock, dll).
- **Format State Machine:** Sederhana, antarmuka `SET key value` dan `GET key`.

#### Expected Output
1. Log eksekusi terminal yang memperlihatkan:
   - Pemilihan Leader awal secara sukses (misal: Node 1 menjadi Leader pada Term 1).
   - Replikasi 3 entri data dengan konfirmasi komit kuorum.
   - Terjadinya partisi buatan: Isolasi Node 1 (Leader). Node 2 & 3 mendeteksi kegagalan, memilih Node 2 sebagai Leader Term 2, dan terus menerima penulisan data baru.
   - Pemulihan jaringan: Node 1 bergabung kembali, mendeteksi Term 2 yang lebih tinggi, turun tahta (*step down*) menjadi Follower, membuang log lokal yang tidak terikat kuorum, dan menyelaraskan log-nya ke Node 2.
2. Pengujian otomatis (*unit/integration test*) yang memvalidasi bahwa nilai state machine pada seluruh node adalah identik (*strictly consistent*) setelah partisi dipulihkan.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan fundamental antara *asynchronous network model*, *synchronous network model*, dan *partially synchronous network model*.
- [ ] Mengapa waktu fisik (*physical clock*) tidak pernah dapat diandalkan 100% untuk kausalitas mutlak tanpa bantuan hardware specialized (seperti GPS receiver & Atomic Clock pada Google TrueTime).
- [ ] Mekanisme formal hubungan *Happened-Before* ($a \rightarrow b$) yang digagas oleh Leslie Lamport.
- [ ] Mengapa algoritma konsensus berbasis kuorum mensyaratkan mayoritas $Q = \lfloor N/2 \rfloor + 1$ untuk mencegah terjadinya dua partisi independen mengambil keputusan yang saling bertentangan.
- [ ] Aturan komit pada Raft: Mengapa seorang Leader Raft dilarang meng-commit log entry dari *term* sebelumnya secara langsung hanya dengan menghitung replika, melainkan harus meng-commit log dari term-nya saat ini.
- [ ] Perbedaan antara konsistensi kuat (*Strong Consistency / Linearizability*), *Sequential Consistency*, *Causal Consistency*, dan *Eventual Consistency*.
- [ ] Alasan mengapa Two-Phase Commit (2PC) rentan terhadap *single-point of failure* (SPOF) pada koordinator dan menahan resource lock tanpa batas.

### Saya tidak perlu menghafal:
- [ ] Format biner spesifik dari paket protokol NTP standar (RFC 5905).
- [ ] Bukti matematis formal 30 halaman dari Teorema Impossibility FLP (cukup pahami intisari batasan teoritisnya).
- [ ] Seluruh varian turunan Multi-Paxos (cukup kuasai algoritma Raft atau Paxos klasik secara mendalam hingga ke tingkat invarian log replication).

### Saya harus bisa melakukan:
- [ ] Mengidentifikasi dan mendeteksi kondisi *split-brain risk* dalam topologi cluster terdistribusi di lingkungan produksi.
- [ ] Mengimplementasikan *fencing tokens* untuk mengamankan resource bersama dari serangan *stale leader / zombie process*.
- [ ] Menentukan arsitektur penyimpanan yang tepat (*Strictly Serialized / Linearizable* vs *Eventual Consistent*) berdasarkan analisis risiko bisnis dan batasan PACELC.
- [ ] Mendiagnosis akar masalah dari *clock drift* server menggunakan tools sistem seperti `chronyc`, `ntpstat`, atau membaca drift offset di level kernel via `adjtimex`.
- [ ] Merancang alur transaksi terdistribusi menggunakan *Saga Orchestrator* dengan jaminan kompensasi kegagalan yang bersifat idempoten (*idempotent consumers*).