# BAB 06: Quiz, Challenge, & Knowledge Check
**Real-Time Streaming & WebSocket Architecture**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Anatomi Transisi Protokol (HTTP Upgrade ke WebSocket)**  
   Jelaskan secara mendalam proses *handshake* ketika klien menginisiasi koneksi ke endpoint Action Cable (misal: `/cable`). Bagaimana header `Upgrade: websocket` dan `Connection: Upgrade` diproses oleh Rack server (Puma) dan dibajak (*socket hijacking*) dari siklus hidup HTTP reguler? Apa implikasi struktural dari proses ini terhadap *thread pool* dan alokasi resource server?

2. **Topologi Pub/Sub Action Cable: Connection, Channel, dan Adapter**  
   Uraikan relasi arsitektural dan siklus hidup antara `ApplicationCable::Connection`, `ApplicationCable::Channel`, stream identifier, dan Pub/Sub adapter (Redis/Solid Cable). Ketika sebuah pemanggilan `ActionCable.server.broadcast("room_1", payload)` dieksekusi di background worker (Sidekiq), bagaimana alur teknis pesan tersebut hingga sampai ke socket client tertentu?

3. **Mekanisme Otentikasi dan Identifikasi State pada WebSocket**  
   Mengapa autentikasi berbasis token anti-CSRF konvensional pada form HTTP tidak dapat langsung diterapkan begitu koneksi WebSocket terbentuk? Bagaimana `identified_by` pada `ApplicationCable::Connection` bekerja, bagaimana cara membaca session/cookie yang terenkripsi secara aman saat handshake, dan bagaimana strategi Action Cable menangani invalidasi sesi (misal: user *logout* atau akun di-*banned*) secara *real-time* tanpa menunggu koneksi terputus?

4. **Karakteristik & Trade-Off: WebSockets vs Server-Sent Events (SSE) vs Long Polling**  
   Bandingkan arsitektur komunikasi dupleks penuh (*full-duplex*) WebSockets dengan *unidirectional streaming* pada Server-Sent Events (`ActionController::Live`) dan HTTP Long Polling. Dalam konteks aplikasi enterprise Rails, pada skenario sistem seperti apa SSE secara teknis jauh lebih superior dan efisien dalam penggunaan resource dibandingkan Action Cable?

5. **Turbo Streams over Action Cable: HTML Over the Wire vs Data API**  
   Dalam paradigma Hotwire, Turbo Streams dapat disalurkan melalui Action Cable channels. Analisis perbandingan arsitektural antara menyiarkan potongan HTML ter-render (`render_to_string` dari Turbo Stream templates) dibandingkan menyiarkan *payload* JSON murni yang kemudian di-parse oleh client-side framework. Tinjau dari sudut pandang CPU load di server, latensi jaringan, *caching strategy*, dan *payload overhead*.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Thread-Safety dan Lifecycle State pada Channel Instances**  
   Sebutkan dan jelaskan bahaya penggunaan *instance variables* (misal: `@current_bid`) di dalam metode `ApplicationCable::Channel`. Bagaimana Action Cable menginstansiasi objek Channel untuk setiap subscriber, dan bagaimana relasinya dengan Puma Worker pool? Skenario *race condition* seperti apa yang dapat terjadi jika engineer memperlakukan instance channel layaknya stateful server actor?

2. **Puma Reactor, NIO4r, dan Ancaman Worker Pool Exhaustion**  
   Action Cable menggunakan gem `nio4r` (New I/O for Ruby) untuk menangani ribuan soket idle melalui reactor loop non-blocking. Namun, eksekusi kode Ruby di dalam channel action (`receive`, `perform`) didelegasikan ke thread worker pool. Jelaskan bagaimana satu pemanggilan database yang lambat (*slow query*) atau pemanggilan HTTP API eksternal yang sinkron di dalam method Channel dapat melumpuhkan seluruh Puma worker pool dan menyebabkan *connection dropping* masal (*denial-of-service* internal).

3. **Pub/Sub Broker Failure Modes: Redis Pub/Sub vs Solid Cable**  
   Bandingkan karakteristik kegagalan (*failure modes*) antara Redis Pub/Sub dan Solid Cable (berbasis PostgreSQL/MySQL). Apa konsekuensi teknis dari sifat Redis Pub/Sub yang bersifat *at-most-once* (fire-and-forget) terhadap integritas data saat terjadi *network partition* atau *broker restart*? Bagaimana Solid Cable memanfaatkan polling/listen-notify database untuk menjamin keandalan, dan apa biaya performa (*performance cost*) yang harus dibayar?

4. **Arsitektur AnyCable: Mengatasi MRI GIL dan Memory Footprint**  
   Pada skala puluhan ribu koneksi konkuren, arsitektur native Action Cable di CRuby (MRI) sering kali membentur limitasi Global VM Lock (GVL) dan konsumsi memori tinggi (~30-50MB per proses koneksi Ruby). Jelaskan bagaimana AnyCable memecahkan masalah ini dengan memisahkan terminasi koneksi WebSocket (AnyCable-Go) dari eksekusi *business logic* Rails via gRPC. Bagaimana alur data RPC bekerja saat ada event masuk dari klien?

5. **Thundering Herd Problem dan Mitigasi Reconnection Storm**  
   Ketika proses Puma di-restart saat *rolling deployment*, puluhan ribu WebSocket clients akan terputus secara bersamaan dan mencoba melakukan *reconnection* secara instan (*thundering herd*). Parameter dan arsitektur apa yang harus dikonfigurasi pada level klien (Action Cable JS / Turbo) dan level reverse proxy (NGINX/Envoy) untuk memitigasi *exponential reconnection storm* yang dapat menumbangkan database authentication layer?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck dan Connection Drop pada Flash-Sale Dashboard (High-Concurrence Scaling)
Sebuah platform e-commerce meluncurkan flash-sale berskala masif. Sekitar 100.000 pengguna membuka halaman produk yang sama secara bersamaan. Halaman ini menggunakan Turbo Streams over Action Cable untuk menampilkan sisa stok barang secara *real-time*. 
Beberapa menit sebelum event dimulai:
* Utilisasi memori pada cluster server Puma melonjak hingga 100%, memicu kernel OOM (*Out of Memory*) Killer untuk membunuh worker Puma.
* Database PostgreSQL mencatat lonjakan koneksi hingga mencapai limit `max_connections`, menyebabkan *ActiveRecord::ConnectionTimeoutError*.
* Client melaporkan bahwa status WebSocket konstan mengalami siklus *connecting -> disconnected -> reconnecting*.

**Tugas Diagnostik & Arsitektural:**
1. Mengapa Action Cable default menghabiskan connection pool database untuk setiap koneksi WebSocket yang masuk, dan bagaimana cara memutus ketergantungan DB connection pool pada soket yang sedang idle?
2. Bagaimana strategi Anda meredam broadcast overhead agar sistem tidak melakukan 100.000 rendering HTML fragment terpisah di server untuk satu perubahan angka stok yang sama?
3. Rancang arsitektur transisi (misal: isolasi Cable server terpisah, AnyCable, atau *throttled broadcasting*) untuk menstabilkan platform di bawah beban 100k concurrent WebSocket connections.

---

### Skenario B: Race Condition dan Out-of-Order Broadcasting pada Platform Real-Time Bidding
Aplikasi lelang online (*online auction*) menggunakan Action Cable untuk menerima tawaran (*bids*) dan menyiarkan penawaran tertinggi saat ini. Alur kode diimplementasikan sebagai berikut pada `AuctionChannel`:

```ruby
def place_bid(data)
  auction = Auction.find(data["auction_id"])
  new_bid = data["amount"].to_f

  if new_bid > auction.current_price
    auction.update!(current_price: new_bid, highest_bidder: current_user)
    ActionCable.server.broadcast("auction_#{auction.id}", {
      price: auction.current_price,
      bidder: current_user.name
    })
  end
end
```

Di lingkungan produksi dengan traffic lelang tinggi:
* Terjadi kasus di mana Penawar B menawar \$105 setelah Penawar A menawar \$100. Namun di layar para penonton lelang, harga terakhir yang tampil adalah \$100 milik Penawar A, meskipun di dalam database tercatat pemenang lelang adalah Penawar B dengan \$105.
* Pada beberapa kasus ekstrem, broadcast terkirim ke klien tetapi data di database *rollback* karena kegagalan constraint/network ke DB.

**Tugas Diagnostik & Perbaikan:**
1. Bedah dua kecacatan fatal pada kode di atas terkait ketiadaan transaksi database, *pessimistic/optimistic locking*, dan eksekusi *side-effect* (broadcast) di luar lifecycle DB commit.
2. Mengapa broadcasting langsung di dalam channel method melanggar prinsip *thread isolation* dan *message ordering*?
3. Tulis ulang kode penanganan lelang tersebut menggunakan Service Object / Command Pattern, memanfaatkan locking mekanisme yang tepat (`with_lock`), serta integrasi `after_commit` hook untuk menjamin integritas urutan pesan di WebSocket.

---

### Skenario C: Antipattern Ingestion Data Real-Time (IoT / Fleet Tracking Architecture)
Sebuah perusahaan logistik memiliki 20.000 armada truk yang mengirimkan koordinat GPS setiap 2 detik. Arsitek sebelumnya merancang agar setiap perangkat IoT armada truk membuka koneksi Action Cable langsung ke aplikasi Rails utama dan memanggil method `FleetChannel#update_coordinates(lat, lng)`. 

Dampaknya di server produksi:
* Web server Rails mengalami utilisasi CPU konstan di atas 90% hanya untuk mengurus I/O parsing dan serialization string koordinat.
* Database pool habis total karena setiap *receive* melakukan `Truck.update(...)`.
* Klien web dashboard admin (yang memantau pergerakan truk pada peta) mengalami lag visual hingga 30-45 detik di belakang waktu nyata.

**Tugas Diagnostik & Redesain Sistem:**
1. Analisis mengapa menggunakan Action Cable sebagai protokol *ingestion* data berskala tinggi merupakan antipattern fatal dalam ekosistem Rails.
2. Rancang arsitektur baru yang memisahkan antara jalur *Ingestion Pipeline* (masuknya data dari armada) dengan jalur *Distribution/Broadcasting Pipeline* (tampilan ke peta browser admin).
3. Komponen teknologi apa yang akan Anda sisipkan di depan Rails (misal: MQTT broker, Kafka, Redis Streams, Go-ingestor) dan bagaimana Anda memfilter broadcast agar admin hanya menerima koordinat truk yang berada di dalam *bounding-box* viewport peta mereka, bukan 20.000 truk sekaligus?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Collaborative State Engine dengan Action Cable & Idempotent Stream Catch-up

#### Deskripsi Skenario
Anda diminta membangun sistem kolaboratif multi-user untuk **"Live Document Conflict-Free Locking System"** (semacam sistem checkout seat tiket pesawat atau editing blok dokumen). Ketika seorang pengguna mulai mengedit sebuah section/blok, blok tersebut harus di-lock secara instan untuk semua pengguna lain di channel yang sama, dan jika pengguna tersebut terputus (jaringan mati, browser ditutup), lock harus otomatis lepas dalam durasi timeout yang ditentukan. Sistem juga harus mampu menyinkronkan state terkini kepada pengguna yang baru bergabung atau baru saja *reconnect* tanpa terjadi *split-brain*.

#### Kebutuhan Teknis (Requirements):
1. **Connection Authentication & State**:
   * Implementasikan otentikasi di `ApplicationCable::Connection` yang memvalidasi signed/encrypted session token.
   * Setiap koneksi harus mencatat ID unik sesi di memory store (Redis) dengan status *connected*.
2. **Channel Implementation (`DocumentSyncChannel`)**:
   * Pengguna dapat subscribe ke channel dokumen spesifik: `DocumentSyncChannel.for(document_id)`.
   * Action `acquire_lock(block_id)`: Memastikan hanya satu user yang memegang lock blok tertentu pada satu waktu.
   * Action `release_lock(block_id)`: Melepas lock dan menyiarkan pelepasan ke semua subscriber.
   * Gunakan Redis via atomic commands (`SET resource_name my_random_value NX PX 30000` atau Redis scripts) sebagai Distributed Lock Manager, jangan gunakan locking langsung pada relational database untuk *transient lock*.
3. **Heartbeat & Ephemeral Presence**:
   * Implementasikan mekanisme *heartbeat* di channel. Jika client gagal mengirim sinyal refresh lock dalam 10 detik, lock dianggap hangus dan sistem secara otomatis menyiarkan event `lock_expired` ke seluruh pengguna di dokumen tersebut.
4. **Resilience & State Synchronization on Reconnect**:
   * Buat method `sync_state` yang mengembalikan seluruh peta lock aktif dokumen saat ini kepada client yang baru terhubung kembali, untuk mencegah kondisi di mana client menampilkan status lock *stale* karena kehilangan event broadcast saat transit jaringan terputus.
5. **Turbo Streams Integration**:
   * Penyiaran status lock tidak boleh membebani client dengan parsing custom JavaScript secara berlebihan; manfaatkan Turbo Streams over Action Cable untuk mengganti elemen UI blok dokumen secara dinamis (`replace` target DOM).

#### Batasan Implementasi (Constraints):
* Tidak boleh menyisakan koneksi ActiveRecord yang terbuka (*held connection*) saat soket berada dalam kondisi idle di reactor.
* Seluruh operasi lock/unlock harus idempotent: jika sebuah pesan `acquire_lock` terkirim dua kali karena network retry, sistem tidak boleh crash atau deadlock.
* Kode harus *thread-safe* dan kompatibel dengan lingkungan multi-process multi-threaded (Puma cluster mode).

#### Output yang Diharapkan:
1. File `app/channels/application_cable/connection.rb` lengkap dengan error-handling koneksi.
2. File `app/channels/document_sync_channel.rb` yang mencakup *subscription*, *actions*, *cleanup/unsubscribed*, dan integrasi distributed locking.
3. Service Class `DocumentLockManager` (PORO) yang mengkapsulasi logika Redis (SET NX, TTL renewal, release with token verification).
4. Penjelasan singkat mengenai mitigasi *race condition* jika dua user menekan tombol edit pada milidetik yang identik.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Siklus hidup koneksi WebSocket dari HTTP `101 Switching Protocols` hingga penutupan socket (`CLOSE` frame).
- [ ] Perbedaan fundamental antara Action Cable channel instance dan connection instance dalam alokasi memori.
- [ ] Cara kerja Puma reactor (`nio4r`) dalam memisahkan socket I/O listening dari thread pool eksekusi bisnis.
- [ ] Bahaya ActiveRecord Connection Pool starvation akibat Action Cable dan strategi mitigasinya (`config.action_cable.mount_path`, manual connection checkout/release).
- [ ] Mekanisme kerja Pub/Sub adapter backend (Redis channel patterns vs Solid Cable database polling/LISTEN-NOTIFY).
- [ ] Mengapa transaksi database harus selesai di-commit (`after_commit`) sebelum menyiarkan event ke Action Cable channel.
- [ ] Batasan komputasi MRI Ruby (GIL) dalam menangani C10K/C100K WebSockets dan kapan sistem harus bermigrasi ke AnyCable.
- [ ] Konsep dasar Turbo Streams: protokol broadcast berbasis DOM-replacement tanpa client-side state machine yang kompleks.

### Saya tidak perlu menghafal:
- [ ] Spesifikasi byte-level WebSocket frame masking key RFC 6455.
- [ ] Kode implementasi internal C-extension `nio4r` atau libev selector loop.
- [ ] Seluruh flag konfigurasi Redis configuration file (`redis.conf`) untuk Pub/Sub buffer limitations.
- [ ] Sintaks exact gRPC protobuf definition file internal milik AnyCable.

### Saya harus bisa melakukan:
- [ ] Melakukan otentikasi koneksi Action Cable secara aman menggunakan Devise/Warden session cookies atau encrypted JWT tokens.
- [ ] Memisahkan mounting endpoint Action Cable ke proses/server terpisah dari server HTTP aplikasi Rails standar.
- [ ] Mengimplementasikan distributed locking (Redis-based) untuk mencegah race condition pada shared real-time states.
- [ ] Menulis integration tests dan channel tests komprehensif menggunakan `ActionCable::Channel::TestCase`.
- [ ] Men-debug insiden koneksi drop, slow consumers, dan memory leak pada WebSocket channels menggunakan log level internal dan monitoring metrics.
- [ ] Mengonfigurasi broadcast backgrounding secara asinkron via ActiveJob agar rendering fragment view tidak memblokir thread web request.