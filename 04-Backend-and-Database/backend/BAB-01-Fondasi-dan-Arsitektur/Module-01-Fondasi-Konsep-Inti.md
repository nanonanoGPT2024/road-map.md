# Bab 01 Module 01: Client-Server Architecture, Network Sockets, dan Siklus Hidup Protokol HTTP/HTTPS

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis** siklus hidup transfer data layer aplikasi dari socket TCP tingkat rendah (POSIX socket) hingga serialisasi payload HTTP.
- **Mengimplementasikan** HTTP server tingkat produksi menggunakan Go yang memiliki mekanisme *graceful shutdown*, isolasi timeout defensif, dan manajemen alokasi koneksi.
- **Mendiagnosis** anomali pada network I/O seperti koneksi zombie, *TCP TIME_WAIT exhaustion*, dan *Head-of-Line (HoL) blocking*.
- **Mengevaluasi** perbandingan performa antara model konkurensi *thread-per-connection*, *event-driven non-blocking I/O*, dan *goroutine-based scheduling* terhadap kapasitas memori dan *throughput*.
- **Mengamankan** antarmuka HTTP terhadap eksploitasi level transport dan parsing, termasuk serangan *Slowloris*, *HTTP Request Smuggling*, dan kebocoran buffer pembacaan body.

---

### 2. Fundamental Concept
Fondasi dari rekayasa backend berakar pada model komputasi terdistribusi **Client-Server**. Dalam model ini, terdapat pemisahan tugas secara tegas (*separation of concerns*) antara penyedia sumber daya (**Server**) dan pemohon layanan (**Client**). 

Secara mekanis, komunikasi antar-mesin pada sistem operasi berbasis UNIX terjadi melalui abstraksi file descriptor yang disebut **Network Socket**. Socket adalah endpoint logis dari tautan komunikasi dua arah (*bidirectional communication channel*). Pada layer transport, komunikasi web modern mayoritas mengandalkan protokol **TCP (Transmission Control Protocol)** yang menjamin pengiriman data byte-stream yang andal, berurutan, dan bebas kesalahan (*reliable, ordered, error-checked*) melalui mekanisme **Three-Way Handshake (SYN, SYN-ACK, ACK)**.

```
       Client                               Server
         |                                    |
         | -------- SYN (Seq=X) ------------> | (Listen queue)
         | <------- SYN-ACK (Seq=Y,Ack=X+1) - | (SYN backlog)
         | -------- ACK (Seq=X+1,Ack=Y+1) --> | (Accept queue)
         |                                    |
 [ESTABLISHED]                           [ESTABLISHED]
```

Di atas lapisan transport ini, protokol **HTTP (Hypertext Transfer Protocol)** berjalan sebagai protokol layer aplikasi berstatus *stateless*. Setiap transaksi *Request-Response* berdiri sendiri secara semantik, meskipun layer transport di bawahnya menggunakan mekanisme *persistent connection* (`Keep-Alive`) untuk menghindari biaya overhead pembentukan koneksi TCP dan negosiasi TLS (*Transport Layer Security*) secara berulang.

---

### 3. Why It Matters
Banyak kegagalan fatal pada sistem backend berskala masif (seperti insiden *cascading failure* saat lonjakan trafik *flash sale*) bukan dipicu oleh bug pada logika bisnis aplikasi, melainkan kegagalan pada lapisan dasar pemrosesan socket dan jaringan.

Jika seorang insinyur backend mengabaikan lapisan ini:
- Server akan rentan terhadap **resource exhaustion**: Kebocoran socket descriptor akibat penanganan I/O yang tidak menutup koneksi (`leak file descriptors`), menyebabkan error sistem operasi `EMFILE: Too many open files`.
- Konfigurasi timeout yang salah pada server gateway dan upstream service dapat memicu penumpukan goroutine/thread, memakan seluruh RAM dan memicu **Out-Of-Memory (OOM) Killer**.
- Kegagalan memahami protokol HTTP/1.1 vs HTTP/2 menyebabkan implementasi arsitektur microservices mengalami latensi tinggi akibat fenomena *connection starvation* dan *serialization bottleneck*.

---

### 4. What Problem Does It Solve?
Model Client-Server berbasis HTTP memecahkan sejumlah kendala komputasi fundamental:
1. **Heterogenitas Platform**: Memungkinkan server yang berjalan di Linux x86_64 melayani client yang berjalan pada peramban web, iOS ARM64, perangkat IoT, atau service backend lain melalui kontrak representasi data standar (RFC 9110/9112).
2. **Resource Centralization & Data Consistency**: Penyimpanan data kritikal dan komputasi intensif terkonsentrasi pada infrastruktur terpusat yang dapat diukur skalabilitasnya, diamankan, dan diaudit.
3. **Network Latency Amortization**: Melalui transisi dari koneksi non-persistent (HTTP/1.0: 1 TCP handshake per asset) ke persistent connection (HTTP/1.1) dan multiplexing (HTTP/2), latensi round-trip jaringan (RTT) berhasil dipangkas secara drastis.

---

### 5. How It Works
Siklus penanganan sebuah request HTTP pada sistem backend modern melibatkan urutan subsistem berikut:

1. **System Call Setup**: Server memanggil syscall `socket()` untuk membuat file descriptor jaringan, `bind()` untuk mengikat socket ke alamat IP dan Port tertentu, lalu `listen()` untuk mengubah socket menjadi pasif penerima koneksi.
2. **OS Connection Backlog**: Saat paket SYN masuk, OS memasukkannya ke dalam *SYN Queue*. Setelah Three-Way Handshake selesai, socket dialihkan ke *Accept Queue*.
3. **Application Accept**: Server memanggil syscall `accept()`. Syscall ini memblokir eksekusi thread sampai koneksi baru tersedia, lalu mengembalikan file descriptor koneksi baru khusus untuk pertukaran data dengan client tersebut.
4. **TLS Negotiation (HTTPS)**: Jika TLS aktif, terjadi handshake enkripsi asimetris untuk verifikasi sertifikat server dan pertukaran kunci ephemeral (ECDHE), sebelum beralih ke enkripsi simetris (AES-GCM/ChaCha20).
5. **HTTP Parsing**:
   - Server membaca byte stream dari socket buffer kernel ke user-space buffer aplikasi.
   - Parser membaca baris awal (*Request Line*: Metode, URI, Versi), diikuti oleh blok *Headers* (dipisahkan oleh CRLF `\r\n`), hingga menemukan delimitasi CRLF ganda (`\r\n\r\n`).
   - Jika payload memiliki *Body*, panjang ditentukan oleh header `Content-Length` atau pemrosesan potongan (*Chunked Transfer Encoding*).
6. **Execution Pipeline**: Request dialihkan ke router/mux aplikasi, melewati lapisan middleware (autentikasi, logging, rate limiting), dan dieksekusi oleh Business Logic Handler.
7. **Flushing & Teardown**: Server menulis HTTP Response Line, Headers, dan Body ke buffer socket output, mengalirkan byte ke kartu antarmuka jaringan (NIC), lalu menutup koneksi (`close()`) atau mengembalikannya ke pool *Keep-Alive*.

---

### 6. Architectural / Flow Diagram

```
[ Client Browser / HTTP Client ]
             │
             │  1. DNS Resolve & TCP 3-Way Handshake
             ▼
┌────────────────────────────────────────────────────────┐
│ Linux Kernel Space (Networking Subsystem)             │
│                                                        │
│  [SYN Queue] ──► [Accept Queue]                        │
│                         │                              │
│                         ▼ syscall: accept()            │
│  [Client Socket FD: 4]                                 │
│  ┌────────────────────────┐  ┌───────────────────────┐ │
│  │ RX Buffer (Inbound)    │  │ TX Buffer (Outbound)  │ │
│  └───────────┬────────────┘  └───────────▲───────────┘ │
└──────────────┼───────────────────────────┼─────────────┘
               │ syscall: read()           │ syscall: write()
┌──────────────┼───────────────────────────┼─────────────┐
│ User Space (Backend Runtime Engine / Go)  │             │
│              ▼                           │             │
│  ┌───────────────────────┐               │             │
│  │ HTTP Stream/Buf Parser│               │             │
│  └───────────┬───────────┘               │             │
│              ▼                           │             │
│  ┌─────────────────────────────────────┐ │             │
│  │ Context Initialization & Timers     │ │             │
│  └───────────┬─────────────────────────┘ │             │
│              ▼                           │             │
│  ┌───────────────────────┐               │             │
│  │ Middleware Pipeline   │               │             │
│  │ (Auth, Recovery, CORS)│               │             │
│  └───────────┬───────────┘               │             │
│              ▼                           │             │
│  ┌───────────────────────┐               │             │
│  │ Controller / Handler  │───────────────┘             │
│  └───────────────────────┘                             │
└────────────────────────────────────────────────────────┘
```

---

### 7. Minimal Simple Example
Contoh dasar parsing stream TCP secara mentah untuk memproses HTTP GET Request tanpa framework di Go:

```go
package main

import (
	"bufio"
	"fmt"
	"net"
	"strings"
)

func main() {
	// 1. Bind & Listen pada port 8080
	listener, err := net.Listen("tcp", ":8080")
	if err != nil {
		panic(err)
	}
	defer listener.Close()
	fmt.Println("Server TCP berjalan di :8080...")

	for {
		// 2. Accept koneksi masuk (blocking)
		conn, err := listener.Accept()
		if err != nil {
			fmt.Printf("Gagal menerima koneksi: %v\n", err)
			continue
		}

		// 3. Tangani stream koneksi secara konkuren
		go handleRawConnection(conn)
	}
}

func handleRawConnection(conn net.Conn) {
	defer conn.Close()

	reader := bufio.NewReader(conn)
	// Baca baris pertama (Request Line)
	requestLine, err := reader.ReadString('\n')
	if err != nil {
		return
	}

	parts := strings.Fields(requestLine)
	if len(parts) < 3 {
		return
	}
	method, path, proto := parts[0], parts[1], parts[2]
	fmt.Printf("Menerima: %s %s %s\n", method, path, proto)

	// Format HTTP Response mentah sesuai standar RFC 9112
	body := "{\"message\": \"Halo dari Socket Server Mentah\"}\n"
	response := fmt.Sprintf(
		"HTTP/1.1 200 OK\r\n"+
			"Content-Type: application/json\r\n"+
			"Content-Length: %d\r\n"+
			"Connection: close\r\n"+
			"\r\n"+
			"%s",
		len(body), body,
	)

	// Tulis response kembali ke TCP socket TX buffer
	conn.Write([]byte(response))
}
```

---

### 8. Production-Grade Practical Example
Implementasi HTTP server Go standar industri yang dilengkapi timeout pertahanan anti-Slowloris, penanganan sinyal OS untuk *graceful shutdown*, serta pencegahan kebocoran goroutine.

```go
package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"
)

type SystemStatusResponse struct {
	Status    string    `json:"status"`
	Timestamp time.Time `json:"timestamp"`
	UptimeSec float64   `json:"uptime_sec"`
}

var startTime = time.Now()

func statusHandler(w http.ResponseWriter, r *http.Request) {
	// Batasi hanya method GET
	if r.Method != http.MethodGet {
		w.Header().Set("Allow", http.MethodGet)
		http.Error(w, "Metode HTTP Tidak Diizinkan", http.StatusMethodNotAllowed)
		return
	}

	// Payload response
	resp := SystemStatusResponse{
		Status:    "HEALTHY",
		Timestamp: time.Now().UTC(),
		UptimeSec: time.Since(startTime).Seconds(),
	}

	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(http.StatusOK)
	if err := json.NewEncoder(w).Encode(resp); err != nil {
		slog.Error("Gagal melakukan serialisasi response", "error", err)
	}
}

func main() {
	// Konfigurasi structured logger
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	slog.SetDefault(logger)

	mux := http.NewServeMux()
	mux.HandleFunc("/v1/status", statusHandler)

	// Konstruksi server dengan hard-timeout untuk mitigasi Slowloris
	server := &http.Server{
		Addr:    ":8443",
		Handler: mux,
		// Waktu maksimal membaca seluruh request termasuk body
		ReadTimeout: 5 * time.Second,
		// Waktu maksimal membaca headers saja
		ReadHeaderTimeout: 2 * time.Second,
		// Waktu maksimal menulis response kembali ke client
		WriteTimeout: 10 * time.Second,
		// Waktu maksimal socket idle saat Keep-Alive aktif
		IdleTimeout: 120 * time.Second,
		// Membatasi alokasi memory header parsing untuk mitigasi DoS
		MaxHeaderBytes: 1 << 20, // 1 MB
	}

	// Channel untuk menangkap sinyal terminasi OS
	shutdownChan := make(chan os.Signal, 1)
	signal.Notify(shutdownChan, os.Interrupt, syscall.SIGTERM)

	// Menjalankan listener pada goroutine terpisah
	go func() {
		slog.Info("Server HTTP produksi mendengarkan", "address", server.Addr)
		if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			slog.Error("Kegagalan fatal pada server listener", "error", err)
			os.Exit(1)
		}
	}()

	// Menunggu sinyal SIGINT (Ctrl+C) atau SIGTERM
	sig := <-shutdownChan
	slog.Warn("Sinyal penghentian diterima. Memulai proses graceful shutdown...", "signal", sig.String())

	// Memberikan batas waktu toleransi untuk menyelesaikan inflight requests
	ctxShutdown, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()

	// Menutup listener socket baru, menyelesaikan request berjalan
	if err := server.Shutdown(ctxShutdown); err != nil {
		slog.Error("Shutdown server dipaksa berhenti sebelum selesai", "error", err)
		if errClose := server.Close(); errClose != nil {
			slog.Error("Gagal memaksa penutupan koneksi aktif", "error", errClose)
		}
	}

	slog.Info("Server berhasil dihentikan secara bersih.")
}
```

---

### 9. Trade-offs & Engineering Decisions

#### Model I/O & Konkurensi
| Model | Kelebihan | Kekurangan | Kapan Digunakan |
| :--- | :--- | :--- | :--- |
| **Thread-per-Connection** (mis. Apache MPM worker lawas) | Model mental pemrograman prosedural yang sederhana. Isolasi kegagalan antar thread baik. | Konsumsi memori per-thread besar (~1-8MB stack), *context-switching* kernel overhead tinggi di atas 10k koneksi. | Sistem legacy atau komputasi paralel berat berbasis CPU murni. |
| **Event-Driven Non-Blocking** (mis. Node.js, Nginx) | Efisiensi memori tinggi, mampu menangani 100k+ koneksi per instance via `epoll`/`kqueue`. | Kode callback/promise rawan *event-loop lag*; operasi komputasi sinkron tunggal akan memblokir seluruh server. | High I/O concurrency, WebSockets, real-time messaging, API Gateway sederhana. |
| **Goroutines / Green Threads** (mis. Go Runtime) | Ringan (stack awal ~2KB), integrasi scheduler OS efisien (*M:N scheduler*), sintaks sinkron tapi non-blocking di tingkat runtime. | Potensi kebocoran goroutine tak terkendali jika konteks tidak dipantau secara benar. | Microservices backend modern, data pipeline konkuren, high-throughput REST/gRPC. |

---

### 10. Edge Cases & Failure Modes
- **TCP Reset (RST) Mid-Stream**: Terjadi ketika client menutup socket secara instan (mis. tab ditutup atau aplikasi mobile kehilangan sinyal seluler) sebelum server tuntas menulis response. Server yang mencoba menulis ke socket ini akan memicu error `Broken pipe` (syscall `EPIPE`) atau `Connection reset by peer` (`ECONNRESET`).
- **Half-Open TCP Connections**: Firewall atau router perantara memutus koneksi secara sepihak tanpa mengirim paket FIN/RST. Server mengira client masih terhubung; jika *TCP Keep-Alive* atau *Application Timeout* tidak diaktifkan, socket FD tersebut akan menggantung selamanya.
- **Client Body Underflow**: Client mengirimkan header `Content-Length: 10000`, tetapi hanya mengirimkan 50 byte lalu berhenti mentransmisi data. Tanpa batas waktu `ReadTimeout`, alokasi buffer pemrosesan parser akan tertahan tanpa batas waktu.

---

### 11. Common Anti-Patterns

#### Anti-Pattern 1: Default Client/Server Tanpa Timeout
```go
// BURUK: Rentan terhadap koneksi zombie dan serangan Slowloris
server := &http.Server{
    Addr: ":8080",
    // Tidak mendefinisikan ReadTimeout, WriteTimeout, IdleTimeout
}
```
*Dampak*: Penyerang dapat membuka ribuan soket dan mengirim 1 byte per menit, menghabiskan pool koneksi hingga server mati.

```go
// REFAKTORISASI: Selalu tetapkan batas waktu konkret
server := &http.Server{
    Addr:              ":8080",
    ReadHeaderTimeout: 2 * time.Second,
    ReadTimeout:       5 * time.Second,
    WriteTimeout:      10 * time.Second,
    IdleTimeout:       60 * time.Second,
}
```

#### Anti-Pattern 2: Unbounded Body Reading Tanpa Limitasi
```go
// BURUK: Rawan Out-Of-Memory (OOM) Denial of Service
bodyBytes, err := io.ReadAll(r.Body)
```
*Dampak*: Jika penyerang mengirimkan payload sebesar 4 GB, server akan mencoba mengalokasikan byte array sebesar 4 GB ke dalam RAM hingga memicu crash sistem operasi.

```go
// REFAKTORISASI: Batasi buffer pembacaan body menggunakan MaxBytesReader
r.Body = http.MaxBytesReader(w, r.Body, 2<<20) // Maksimal 2 Megabytes
bodyBytes, err := io.ReadAll(r.Body)
if err != nil {
    http.Error(w, "Request Entity Too Large", http.StatusRequestEntityTooLarge)
    return
}
```

---

### 12. Security Considerations
1. **Mitigasi Serangan Slowloris**: Penyerang membuka ratusan koneksi TCP dan mentransmisikan HTTP header secara sangat lambat (misal 1 baris header per 10 detik) untuk menguras kapasitas pool thread server. Penanggulangannya adalah penetapan `ReadHeaderTimeout` ketat (maksimal 2-5 detik).
2. **HTTP Request Smuggling**: Terjadi akibat ketidaksesuaian interpretasi batas request antara Reverse Proxy (mis. Nginx/HAProxy) dan Server Backend saat membaca kombinasi header `Content-Length` dan `Transfer-Encoding: chunked`. Sesuai standar RFC 9112, server modern harus menolak request yang mengandung kedua header tersebut sekaligus (`HTTP 400 Bad Request`).
3. **CORS (Cross-Origin Resource Sharing) Misconfiguration**: Mengembalikan header `Access-Control-Allow-Origin: *` pada endpoint yang mengandung kredensial autentikasi (`Access-Control-Allow-Credentials: true`) mengekspos data privat kepada peramban pihak ketiga yang mengeksekusi skrip berbahaya.

---

### 13. Performance & Resource Characteristics
- **TCP TIME_WAIT**: Setelah penutupan koneksi (sisi yang memanggil `close()` pertama kali), status koneksi masuk ke state `TIME_WAIT` selama $2 \times \text{MSL}$ (Maximum Segment Lifetime, umumnya 60 detik) untuk memastikan paket lama tidak mengotori koneksi baru. Membuka dan menutup koneksi secara masif tanpa mekanisme *Keep-Alive* akan menghabiskan *ephemeral port* (rentang port lokal 32768–60999) dan memicu error `EADDRNOTAVAIL` (*Cannot assign requested address*).
- **Kompleksitas Memori Parsing**: Parsing header berkisar pada $O(N)$ di mana $N$ adalah total panjang byte representasi ASCII header. 
- **Zero-Copy Optimization**: Pada pengiriman file statis dari media penyimpanan ke client, memanggil syscall `sendfile()` memungkinkan kernel memindahkan byte langsung dari cache disk ke socket buffer tanpa melalui proses salin memori (*memory copy*) ke ruang memori aplikasi (*user space*).

---

### 14. Observability & Debugging
Metrik dan instruksi esensial untuk memeriksa kesehatan layer transport HTTP:

#### Diagnostik CLI Jaringan
```bash
# 1. Menampilkan jumlah soket TCP aktif berdasarkan state
ss -s

# 2. Melihat koneksi yang listening dan memproses port 8443 beserta ukuran receive/send queue
ss -ltnp 'sport = :8443'

# 3. Menghitung jumlah koneksi dalam fase TIME_WAIT
ss -tan state time-wait | wc -l

# 4. Inspeksi paket real-time menggunakan tcpdump untuk port 8443
sudo tcpdump -nn -i any port 8443 -A
```

#### Metrik Standar Observability (Prometheus)
- `http_server_active_connections`: Metrik Gauge untuk memantau soket aktif saat ini.
- `http_request_duration_seconds_bucket`: Histogram latensi total per endpoint.
- `http_requests_total{status=~"5.."}`: Counter untuk mendeteksi lonjakan error level protokol atau internal.

---

### 15. Testing Strategies
Pengujian integrasi lapisan transport menggunakan helper server in-memory standar:

```go
package main

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestStatusHandler_Success(t *testing.T) {
	// Inisialisasi request buatan
	req, err := http.NewRequest(http.MethodGet, "/v1/status", nil)
	if err != nil {
		t.Fatalf("Gagal membuat request: %v", err)
	}

	// Inisialisasi ResponseRecorder untuk merekam byte response
	rr := httptest.NewRecorder()
	handler := http.HandlerFunc(statusHandler)

	handler.ServeHTTP(rr, req)

	// Validasi Status Code
	if status := rr.Code; status != http.StatusOK {
		t.Errorf("Handler menghasilkan status salah: didapat %v seharusnya %v", status, http.StatusOK)
	}

	// Validasi Header MIME Type
	expectedContentType := "application/json; charset=utf-8"
	if cType := rr.Header().Get("Content-Type"); cType != expectedContentType {
		t.Errorf("Header Content-Type salah: didapat %s seharusnya %s", cType, expectedContentType)
	}
}

func TestServer_ClientCancellation(t *testing.T) {
	// Menyiapkan server test nyata menggunakan ephemeral port
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		select {
		case <-time.After(2 * time.Second):
			w.WriteHeader(http.StatusOK)
		case <-r.Context().Done():
			// Context terbatalkan menandakan sinyal disconnect diterima oleh handler
			return
		}
	}))
	defer ts.Close()

	// Buat client dengan context yang dibatalkan secara cepat
	ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
	defer cancel()

	req, _ := http.NewRequestWithContext(ctx, http.MethodGet, ts.URL, nil)
	client := &http.Client{}
	_, err := client.Do(req)

	if err == nil {
		t.Fatal("Request seharusnya gagal akibat context deadline exceeded")
	}
}
```

---

### 16. Scalability & Operational Aspects
- **Reverse Proxy Offloading**: Tempatkan Layer-7 Proxy (Nginx, Envoy, atau Traefik) di depan server backend aplikasi. Proxy ini berfungsi mengeksekusi *TLS Termination*, kompresi data (*Gzip/Brotli*), mitigasi buffering DDoS, dan *HTTP/2 to HTTP/1.1 multiplex unwrapping*.
- **Keep-Alive Configuration**: Sesuaikan parameter `Keep-Alive Timeout` antara load balancer dan upstream backend. Jika backend menutup koneksi Keep-Alive lebih cepat dari Load Balancer tanpa notifikasi, Load Balancer berpotensi meneruskan request client ke soket yang sedang ditutup (*502 Bad Gateway race condition*).
- **Stateless Architecture**: Server backend tidak boleh menyimpan state autentikasi (seperti session memori lokal) pada memory runtime proses. Setiap interaksi harus membawa status stateful yang dapat diverifikasi secara terisolasi (mis. token JWT yang ditandatangani) atau dialihkan ke cache storage terpusat berlatensi rendah (mis. Redis).

---

### 17. Real-World Case Study
**Skenario**: Layanan API e-commerce skala besar mengalami lonjakan respons `HTTP 502 Bad Gateway` acak selama periode promosi dengan trafik mencapai 80.000 RPS.

**Investigasi**:
1. Metrik CPU dan RAM server backend terpantau normal (< 40%).
2. Output perintah `netstat -s` di server Nginx gateway menunjukkan ribuan log `connect() failed (99: Cannot assign requested address)`.
3. Analisis lanjutan mendapati bahwa Nginx membuka koneksi TCP baru untuk setiap HTTP request yang diteruskan ke upstream backend (`proxy_set_header Connection "close"`).

**Akar Masalah**:
Tingginya frekuensi siklus buka-tutup koneksi membuat host Nginx kehabisan *ephemeral port* akibat tumpukan puluhan ribu koneksi yang tertahan di state `TIME_WAIT`.

**Solusi & Mitigasi**:
1. Aktifkan koneksi persistent antara reverse proxy dan backend cluster:
   ```nginx
   upstream backend_nodes {
       server 10.0.0.10:8443;
       server 10.0.0.11:8443;
       keepalive 512; // Menjaga 512 soket idle tetap terbuka
   }
   server {
       location / {
           proxy_pass http://backend_nodes;
           proxy_http_version 1.1;
           proxy_set_header Connection "";
       }
   }
   ```
2. Mengubah batas parameter kernel OS Linux pada file `/etc/sysctl.conf`:
   ```sysctl
   net.ipv4.tcp_tw_reuse = 1
   net.ipv4.ip_local_port_range = 10240 65535
   ```
**Hasil**: Kasus respons 502 Bad Gateway langsung menurun ke angka 0% dan latensi $P99$ request terpangkas sebesar 65% karena dihilangkannya fase negosiasi TCP Three-Way Handshake pada setiap request mikro.

---

### 18. Best Practices Checklist
- [x] **Jangan gunakan DefaultServeMux langsung di Go** tanpa pembungkus yang mendefinisikan isolasi timeouts.
- [x] **Konfigurasikan seluruh limitasi waktu soket**: `ReadHeaderTimeout`, `ReadTimeout`, `WriteTimeout`, dan `IdleTimeout`.
- [x] **Batasi ukuran payload inbound** menggunakan `http.MaxBytesReader` sebelum parsing JSON/Body untuk mencegah serangan kehabisan memori (*Memory Exhaustion DoS*).
- [x] **Dengarkan sinyal OS (SIGTERM/SIGINT)** untuk mengeksekusi *graceful shutdown* agar proses deployment rolling-update tidak memutus request aktif yang sedang berjalan.
- [x] **Gunakan pool koneksi HTTP (`Transport` pooling)** jika aplikasi Anda berperan sebagai client yang memanggil microservice lain.
- [ ] **JANGAN** pernah mengabaikan pembacaan dan penutupan `response.Body.Close()` pada HTTP client Go untuk mencegah *leaking connection FD*.
- [ ] **JANGAN** menyimpan referensi status user secara memori in-process di dalam handler jika server didesain untuk *horizontal autoscaling*.

---

### 19. Exercises & Hands-on Challenges
1. **Tingkat Dasar (Basic)**: Modifikasi contoh pada Bagian 7 (*Minimal Simple Example*) agar parser raw socket dapat mengekstrak HTTP Request Header tertentu (misal: mencari header `User-Agent` dan `Authorization`) dan menampilkannya pada console log.
2. **Tingkat Menengah (Intermediate)**: Buat custom HTTP handler middleware di Go yang membatasi durasi eksekusi handler maksimum 2 detik menggunakan package `context.WithTimeout`. Jika handler melebihi waktu tersebut, kirim respons balik `504 Gateway Timeout` ke client dan batalkan operasi database simulasi di belakangnya.
3. **Tingkat Lanjutan (Advanced)**: Kembangkan program TCP testing berbasis CLI yang mensimulasikan serangan *Slowloris* skala kecil. Program harus membuka 50 soket TCP konkuren ke endpoint HTTP lokal, mengirim fragmen header secara bertahap setiap 3 detik, dan mengukur apakah server Anda berhasil mendeteksi serta memutuskan koneksi tersebut sesuai konfigurasi `ReadHeaderTimeout`.

---

### 20. Further Deep Dive Resources
- **RFC 9110**: *HTTP Semantics* (Dokumen resmi standar arsitektur dan semantik protokol HTTP). [https://www.rfc-editor.org/rfc/rfc9110.html](https://www.rfc-editor.org/rfc/rfc9110.html)
- **RFC 9112**: *HTTP/1.1 Specification* (Detail teknis mekanisme framing berbasis string, parsing, dan penanganan koneksi). [https://www.rfc-editor.org/rfc/rfc9112.html](https://www.rfc-editor.org/rfc/rfc9112.html)
- **UNIX Network Programming, Volume 1: The Sockets Networking API** oleh W. Richard Stevens. (Buku panduan definitif sistem soket POSIX dan komunikasi transport TCP).
- **The Go net/http Package Internals**: *The complete guide to Go net/http timeouts* oleh Filippo Valsorda. (Analisis mendalam alur parsing soket runtime Go).