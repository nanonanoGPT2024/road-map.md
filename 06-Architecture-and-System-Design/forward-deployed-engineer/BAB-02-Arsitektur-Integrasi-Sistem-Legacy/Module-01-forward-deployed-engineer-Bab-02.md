## SEKSI 01 — IDENTITAS MODUL

* **Jalur Kurikulum:** Forward Deployed Engineer (FDE)
* **Kategori:** 06-Architecture-and-System-Design
* **Bab:** 02 — Integrasi Sistem Skala Besar & Desain Arsitektur Terdistribusi
* **Modul:** 01 — Arsitektur Integrasi & Interoperabilitas Sistem Legacy: Enterprise Service Bus, SOAP to REST/gRPC wrappers, Change Data Capture (CDC), Data Transformation & Translation Layers
* **Tingkat Kesulitan:** Advanced / L4-L5
* **Prasyarat:** Pemahaman mendalam tentang HTTP/1.1, HTTP/2, REST API, RPC dasar, SQL Transaction Isolation, Relational Database Internals (Write-Ahead Logging), dan Event-Driven Architecture dasar.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, engineer diharapkan mampu:

1. **Mendiagnosis & Mengevaluasi Topologi Integrasi Legacy:** Mengidentifikasi *bottleneck*, *single point of failure* (SPOF), dan batas konkurensi pada arsitektur Enterprise Service Bus (ESB) tradisional versus arsitektur modern berbasis event.
2. **Merancang & Mengimplementasikan Wrapper Performa Tinggi:** Membangun *facade layer* berlatensi rendah untuk menerjemahkan protokol legacy (SOAP/XML via HTTP/1.1) ke gRPC/Protobuf dan REST/JSON tanpa menyebabkan *thread exhaustion* pada sistem upstream.
3. **Mengoperasikan Change Data Capture (CDC) Non-Invasif:** Mengonfigurasi dan memelihara pipeline CDC log-based (misal: Debezium/Kafka) untuk mengekstrak mutasi data dari RDBMS legacy tanpa melakukan polling langsung yang membebani CPU database.
4. **Menerapkan Anti-Corruption Layer (ACL) & Canonical Data Model (CDM):** Merancang domain translation layer yang mencegah model domain legacy bocor ke dalam layanan baru (*domain model pollution*), menjaga integritas bounded context.
5. **Membangun Mekanisme Resiliensi Transaksional:** Mengimplementasikan pola *Transactional Outbox*, rekonsiliasi data eventual consistency, dan strategi *graceful degradation* saat berhadapan dengan sistem legacy bertroughput rendah.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```text
Arsitektur Interoperabilitas Legacy
 ├── Pola Integrasi Struktural
 │    ├── Enterprise Service Bus (ESB) -> Analisis Monolitik & Deadlock Integrasi
 │    └── "Smart Endpoints, Dumb Pipes" (Transisi ke Event Streaming & Mesh)
 ├── Protokol & Translation Layer
 │    ├── SOAP/XML Upstream -> Parsing Overhead & Namespace Handling
 │    ├── High-Performance Facade -> SOAP-to-gRPC / REST Wrappers
 │    └── Anti-Corruption Layer (ACL) -> Isolasi Domain & Canonical Data Model (CDM)
 ├── Ekstraksi Data Non-Invasif
 │    ├── Polling Query (Anti-pattern) vs Log-Based Change Data Capture (CDC)
 │    ├── WAL / Redo Log Engine (Debezium, PostgreSQL pgoutput, Oracle GoldenGate)
 │    └── Transactional Outbox Pattern -> Menghindari Dual-Write Hazards
 └── Resiliensi & Mitigasi Beban
      ├── Concurrency Throttling & Rate Limiting (Pelindung Sistem Legacy)
      ├── Backoff, Jitter, & Idempotency Key Engine
      └── Circuit Breaking & Dead Letter Queues (DLQ)
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Seorang Forward Deployed Engineer (FDE) jarang sekali masuk ke lingkungan komputasi yang murni *greenfield*. Di enterprise perbankan, manufaktur, energi, dan logistik, core business senilai miliaran dolar berjalan di atas sistem berumur 15 hingga 40 tahun: mainframe AS/400, SAP monolitik, database Oracle yang tidak boleh di-restart, dan web service berbasis SOAP/XML bertitik integrasi kaku.

Menulis ulang sistem legacy (*rip-and-replace*) memiliki tingkat kegagalan proyek di atas 70% karena dependensi implisit, dokumentasi yang hilang, dan kompleksitas logika bisnis historis. Pendekatan FDE adalah integrasi pragmatis: membungkus (*wrapping*), mengekstrak data secara non-invasif, dan menjembatani performa modern dengan batasan legacy.

Jika salah mengeksekusi integrasi ini:
* Polling database legacy secara berkala akan memicu *table lock*, menghancurkan latency transaksi operasional bisnis utama.
* Wrapper tanpa kendali konkurensi (*concurrency throttling*) akan membanjiri server legacy dengan request gRPC modern berkali-kali lipat, menyebabkan *cascading outage*.
* Ketiadaan Anti-Corruption Layer akan mencemari codebase modern dengan tipe data ganjil (misal: format string tanggal legacy tanpa timezone, binary flags) yang merusak arsitektur baru.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Enterprise Service Bus (ESB) vs Arsitektur Modern
ESB adalah arsitektur integrasi terpusat yang bertanggung jawab atas routing, transformasi, koreografi, dan protokol translasi. ESB menempatkan *business logic* di dalam middleware bus. 
* **Masalah ESB:** Terjadi konsentrasi logika bisnis di middleware (menjadi "Smart Pipe"). Tim integrasi menjadi bottleneck, deployment berisiko tinggi, dan skalabilitas horizontal sangat mahal.
* **Paradigma FDE:** Mengubah sistem menjadi *"Smart Endpoints, Dumb Pipes"*. Pipe (misal: Apache Kafka) hanya bertugas memindahkan byte secara andal, sementara logika transformasi dan isolasi domain diletakkan pada microservices/edge wrapper.

### 2. SOAP to REST/gRPC Facade Layer
Layanan legacy mayoritas menggunakan protokol SOAP (Simple Object Access Protocol) yang berbasis XML dengan validasi ketat via XSD (XML Schema Definition) dan WSDL.
* **Tantangan:** Serialisasi/deserialisasi XML mengonsumsi CPU cycle 4–10x lebih banyak dibandingkan JSON/Protobuf. SOAP juga bersifat stateful pada level sesi tertentu atau memerlukan security header kompleks (WS-Security).
* **Solusi:** Membangun *facade wrapper stateless* yang bertindak sebagai jembatan. Wrapper ini mengekspos endpoint modern (REST/JSON atau gRPC/HTTP/2) kepada downstream service, mengelola *connection pooling*, merakit SOAP Envelope secara internal, memetakan kembali respons XML ke flat protobuf/JSON, dan memetakan SOAP Fault ke gRPC Status Codes secara akurat.

### 3. Change Data Capture (CDC)
CDC adalah pola integrasi di mana setiap mutasi tingkat baris (INSERT, UPDATE, DELETE) pada database legacy ditangkap secara langsung dari transaction log (WAL pada PostgreSQL, Redo Log pada Oracle, Binlog pada MySQL) dan dialirkan sebagai event stream.
* **Keunggulan Non-Invasif:** CDC tidak menjalankan query SQL tambahan (`SELECT * FROM table WHERE updated_at > last_sync`) yang menyebabkan disk I/O dan locking. Transaksi ditangkap asinkron langsung dari storage engine log.

### 4. Anti-Corruption Layer (ACL) & Canonical Data Model (CDM)
Berasal dari prinsip Domain-Driven Design (DDD), ACL adalah subsistem perantara yang menerjemahkan semantik domain model dari sistem legacy ke sistem modern.
* **ACL** memastikan konsep usang (misal: field `CUST_STAT_CD_01` dengan arti `ACTIVE`) tidak merembes ke domain baru.
* **CDM** menyediakan kontrak data standar organisasi sehingga *N* sistem legacy tidak perlu diintegrasikan secara *point-to-point* ($N \times M$ complexity), melainkan setiap sistem hanya perlu bertransformasi ke/dari model kanonikal ($N + M$ complexity).

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

### 1. Pipeline CDC Log-Based Menggunakan Engine Parsing Transaksi
1. **Pemicu:** Aplikasi legacy mengeksekusi transaksi: `UPDATE accounts SET balance = balance - 100 WHERE id = 42;`.
2. **Commit:** Database menulis mutasi ke Write-Ahead Log (WAL) di disk, lalu mengembalikan status commit ke aplikasi.
3. **Capture:** Agent CDC (misalnya Debezium melalui connector engine) membaca bitstream WAL pada logical replication slot. Database tidak memproses parsing query SQL berulang kali.
4. **Enrichment & De-serialization:** Agent mengonversi payload binary database internal ke format terstruktur (Schema Registry Avro/JSON) mencakup metadata: snapshot *before*, snapshot *after*, transaction ID, dan timestamp commit.
5. **Streaming:** Pesan dikirim ke broker (Apache Kafka) dengan partition key berupa Primary Key database (misal: `account_id=42`). Ini menjamin keterurutan (*in-order delivery*) mutasi record tersebut.

### 2. Operasi SOAP-to-gRPC High-Performance Wrapper
1. Modern client memanggil service via gRPC: `accountClient.GetAccount(ctx, &AccountRequest{Id: 42})`.
2. Wrapper menerima HTTP/2 frame, mengekstrak Protobuf payload menjadi struct memory lokal.
3. **Translasi & Templating:** Wrapper menyusun XML payload dari struct menggunakan pool memory zero-allocation buffer (misal: `sync.Pool` di Go) untuk meminimalkan beban Garbage Collector.
4. **Upstream Call:** Wrapper menggunakan HTTP/1.1 persistent connection (Keep-Alive) yang telah di-pool untuk menembak endpoint SOAP legacy, menyertakan header WS-Security / Basic Auth.
5. **Parsing & Mapping:** 
   * Jika upstream merespons HTTP 200 dengan XML Envelope, wrapper menggunakan streaming XML decoder (SAX/StAX pattern) untuk langsung mengekstrak nilai node target ke gRPC Response struct.
   * Jika upstream merespons HTTP 500 dengan SOAP Fault, wrapper mem-parsing `<faultcode>` dan `<faultstring>` lalu memetakannya ke gRPC status code yang setara (misal: `SOAP:Server` -> `codes.Internal`, `SOAP:Client` -> `codes.InvalidArgument`).
6. Wrapper merespons ke Modern Client melalui stream gRPC.

### 3. Pola Anti-Corruption Layer (ACL)
1. Event mutasi diterima oleh ACL Consumer dari CDC atau RPC wrapper.
2. **Tahap 1 - Sanitasi:** Validasi tipe, pengecekan encoding (misal: konversi EBCDIC/Windows-1252 ke UTF-8), dan normalisasi nilai NULL/kosong.
3. **Tahap 2 - Domain Translation:** Pemetaan kode-kode primitif legacy ke Domain Model modern menggunakan deterministic state machine atau lookup cache (Redis/Local in-memory).
4. **Tahap 3 - Enriching & Outbox Execution:** Jika data modern membutuhkan agregasi konteks yang tidak dimiliki legacy, ACL memanggil Read Model lokal, memperkaya data, dan meneruskannya ke domain event bus baru.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### End-to-End Enterprise Integration Architecture

```text
+----------------------------------------------------------------------------------------------------+
|                                    SISTEM LEGACY (CORE TIER)                                       |
|                                                                                                    |
|  +--------------------+         HTTP/1.1 SOAP         +-----------------------------------------+  |
|  | Mainframe / AS400  | <============================ | Web Service SOAP Monolitik (SOAP/XML)   |  |
|  +--------------------+                               +-----------------------------------------+  |
|            |                                                                |                      |
|            | Direct Data Writes                                             | Transaction Updates  |
|            v                                                                v                      |
|  +--------------------------------------------------------------------------------------+          |
|  | Core Relational Database (Oracle / DB2 / PostgreSQL)                                 |          |
|  | +-----------------+             +-------------------------------------------------+  |          |
|  | | Tables / State  |             | Write-Ahead Log (WAL) / Redo Log Engine         |  |          |
|  | +-----------------+             +-------------------------------------------------+  |          |
+--+--------+--------------------------------------------------+--------------------------+----------+
            |                                                  | Low-overhead Log Tailing
            |                                                  v
+-----------|--------------------------------------------------|-------------------------------------+
|           |                                                  |                                     |
|           |                  INTEGRATION & TRANSLATION TIER  v                                     |
|           |                                    +---------------------------+                       |
|           |                                    | Debezium / CDC Connector  |                       |
|           |                                    +---------------------------+                       |
|           |                                                  |                                     |
|           | Sync Path                                        | Publishes CDC Events                |
|           | (RPC Request/Response)                           v                                     |
|           |                                    +---------------------------+                       |
|           |                                    | Kafka Ingress Topics      |                       |
|           |                                    +---------------------------+                       |
|           v                                                  |                                     |
|  +-------------------------------------+                     v                                     |
|  | SOAP-to-gRPC Wrapper / Facade       |       +---------------------------+                       |
|  | - Connection Pooling                |       | Anti-Corruption Layer     |                       |
|  | - XML Parsing Engine (sync.Pool)    |       | (ACL Consumer Worker)     |                       |
|  | - Rate Limiter & Concurrency Buffer |       | - Schema Canonicalization |                       |
|  | - SOAP Fault to gRPC Code Mapper    |       | - Idempotency Validation  |                       |
|  +-------------------------------------+       +---------------------------+                       |
|                   ^                                          |                                     |
+-------------------|------------------------------------------|-------------------------------------+
                    | gRPC / HTTP2                             | Produces Clean Domain Events
                    |                                          v
+-------------------|------------------------------------------|-------------------------------------+
|                   v                                          v                                     |
|  +-------------------------------------+       +---------------------------+                       |
|  | Edge API Gateway (BFF)              |       | Kafka Domain Topics       |                       |
|  +-------------------------------------+       +---------------------------+                       |
|                   ^                                          |                                     |
|                   | Internal Microservices                   v                                     |
|                   | Routing                    +---------------------------+                       |
|                   |                            | Modern Cloud Services     |                       |
|  +-------------------------------------+       | (Event Sourced / CQRS)    |                       |
|  | Modern Client Applications          |       +---------------------------+                       |
|  +-------------------------------------+                                                           |
|                                     MODERN CLOUD ECOSYSTEM                                         |
+----------------------------------------------------------------------------------------------------+
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah contoh konseptual transformasi data XML (SOAP Payload Response) menjadi canonical domain model di memory menggunakan Go standard library dengan penanganan memory buffer yang aman.

```go
package main

import (
	"encoding/xml"
	"errors"
	"fmt"
	"strings"
	"time"
)

// LegacySOAPEnvelope merefleksikan payload raw dari sistem upstream
type LegacySOAPEnvelope struct {
	XMLName xml.Name `xml:"Envelope"`
	Body    struct {
		GetCustomerResponse struct {
			CustID    string `xml:"CUST_ID"`
			FullName  string `xml:"CUST_NM"`
			StatusCode string `xml:"STAT_CD"`
			OpenDate  string `xml:"OPEN_DT"` // Format legacy: YYYYMMDD
		} `xml:"getCustomerResponse"`
		Fault *struct {
			Code   string `xml:"faultcode"`
			String string `xml:"faultstring"`
		} `xml:"Fault"`
	} `xml:"Body"`
}

// CanonicalCustomer adalah representasi Modern Domain Model
type CanonicalCustomer struct {
	ID        string    `json:"id"`
	Name      string    `json:"name"`
	IsActive  bool      `json:"is_active"`
	CreatedAt time.Time `json:"created_at"`
}

// AntiCorruptionTranslator mengeksekusi translasi sanitasi terisolasi
func AntiCorruptionTranslator(rawXML []byte) (*CanonicalCustomer, error) {
	var env LegacySOAPEnvelope
	if err := xml.Unmarshal(rawXML, &env); err != nil {
		return nil, fmt.Errorf("XML_PARSE_FAILURE: %w", err)
	}

	// Tangani SOAP Fault secara deterministik
	if env.Body.Fault != nil {
		return nil, fmt.Errorf("UPSTREAM_SOAP_FAULT: [%s] %s", 
			env.Body.Fault.Code, env.Body.Fault.String)
	}

	resp := env.Body.GetCustomerResponse
	if strings.TrimSpace(resp.CustID) == "" {
		return nil, errors.New("VALIDATION_ERROR: empty customer id")
	}

	// Parsing format tanggal legacy YYYYMMDD
	parsedDate, err := time.Parse("20060102", resp.OpenDate)
	if err != nil {
		// Degradasi anggun: Tetapkan default zero time, jangan biarkan seluruh flow meledak
		parsedDate = time.Time{}
	}

	// Terjemahkan legacy status string ke canonical boolean
	// Status legacy: "01" = Aktif, "02" = Diblokir, "03" = Dihapus
	isActive := resp.StatusCode == "01"

	return &CanonicalCustomer{
		ID:        strings.TrimSpace(resp.CustID),
		Name:      strings.TrimSpace(resp.FullName),
		IsActive:  isActive,
		CreatedAt: parsedDate,
	}, nil
}

func main() {
	rawSuccessXML := `
	<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
		<soap:Body>
			<getCustomerResponse>
				<CUST_ID>C-99481</CUST_ID>
				<CUST_NM>PT Rekayasa Perangkat Modern</CUST_NM>
				<STAT_CD>01</STAT_CD>
				<OPEN_DT>20210817</OPEN_DT>
			</getCustomerResponse>
		</soap:Body>
	</soap:Envelope>`

	cleanCustomer, err := AntiCorruptionTranslator([]byte(rawSuccessXML))
	if err != nil {
		panic(err)
	}
	fmt.Printf("Canonical Data Model Terbentuk: ID=%s, Name=%s, Active=%t, CreatedAt=%s\n",
		cleanCustomer.ID, cleanCustomer.Name, cleanCustomer.IsActive, cleanCustomer.CreatedAt)
}
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Implementasi produksi: **High-Throughput SOAP-to-gRPC Facade** menggunakan Go, dilengkapi koneksi HTTP Keep-Alive terkonfigurasi, *concurrency bulkhead*, alokasi memori efisien via `sync.Pool`, dan pemetaan status error SOAP ke gRPC codes.

```go
package main

import (
	"bytes"
	"context"
	"encoding/xml"
	"fmt"
	"io"
	"net"
	"net/http"
	"sync"
	"time"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// Pool buffer untuk mengurangi overhead alokasi memory heap dan Garbage Collection
var bufferPool = sync.Pool{
	New: func() interface{} {
		return new(bytes.Buffer)
	},
}

// SOAPFault merefleksikan payload standard failure dari upstream legacy
type SOAPFault struct {
	FaultCode   string `xml:"faultcode"`
	FaultString string `xml:"faultstring"`
}

type LegacyEnvelopeResponse struct {
	XMLName xml.Name `xml:"Envelope"`
	Body    struct {
		QueryAccountResponse struct {
			Balance float64 `xml:"AC_BAL"`
			Status  string  `xml:"AC_STAT"`
		} `xml:"queryAccountResponse"`
		Fault *SOAPFault `xml:"Fault"`
	} `xml:"Body"`
}

// LegacySOAPClient mendefinisikan interface ke core legacy banking
type LegacySOAPClient struct {
	httpClient *http.Client
	targetURL  string
	semaphore  chan struct{} // Bulkhead pattern untuk melindungi core sistem legacy
}

func NewLegacySOAPClient(targetURL string, maxConcurrentCalls int) *LegacySOAPClient {
	// Konfigurasi transport agresif untuk interoperabilitas stabil
	transport := &http.Transport{
		Proxy: http.ProxyFromEnvironment,
		DialContext: (&net.Dialer{
			Timeout:   5 * time.Second,  // Batas waktu inisiasi koneksi TCP
			KeepAlive: 30 * time.Second,
		}).DialContext,
		MaxIdleConns:        100,
		MaxIdleConnsPerHost: 50,             // Cegah TCP handshake berulang kali ke server legacy
		IdleConnTimeout:     90 * time.Second,
		TLSHandshakeTimeout: 5 * time.Second,
	}

	return &LegacySOAPClient{
		httpClient: &http.Client{
			Transport: transport,
			Timeout:   10 * time.Second, // Hard timeout SOAP call
		},
		targetURL: targetURL,
		semaphore: make(chan struct{}, maxConcurrentCalls),
	}
}

// QueryAccount memproses request gRPC, membungkusnya ke XML SOAP, dan mengembalikan hasil canonical
func (c *LegacySOAPClient) QueryAccount(ctx context.Context, accountID string) (float64, string, error) {
	// 1. Bulkhead acquisition: proteksi upstream dari lonjakan traffic tiba-tiba
	select {
	case c.semaphore <- struct{}{}:
		defer func() { <-c.semaphore }()
	case <-ctx.Done():
		return 0, "", status.Error(codes.Canceled, "Request canceled while waiting for bulkhead capacity")
	default:
		// Jika antrean upstream penuh, tolak secara instan (fail-fast)
		return 0, "", status.Error(codes.ResourceExhausted, "Legacy backend concurrency limit reached")
	}

	// 2. Ambil buffer dari pool dan bentuk envelope XML
	buf := bufferPool.Get().(*bytes.Buffer)
	buf.Reset()
	defer bufferPool.Put(buf)

	buf.WriteString(`<?xml version="1.0" encoding="UTF-8"?>` +
		`<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:acc="http://corebanking.legacy/account">` +
		`<soapenv:Header/>` +
		`<soapenv:Body>` +
		`<acc:queryAccountRequest>` +
		`<acc:AC_ID>` + accountID + `</acc:AC_ID>` +
		`</acc:queryAccountRequest>` +
		`</soapenv:Body>` +
		`</soapenv:Envelope>`)

	// 3. Bangun request HTTP dengan konteks (memungkinkan tracing & timeout cancellation)
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.targetURL, buf)
	if err != nil {
		return 0, "", status.Errorf(codes.Internal, "Failed to create HTTP request: %v", err)
	}

	req.Header.Set("Content-Type", "text/xml; charset=utf-8")
	req.Header.Set("SOAPAction", "http://corebanking.legacy/account/queryAccount")

	// 4. Eksekusi remote call
	resp, err := c.httpClient.Do(req)
	if err != nil {
		if errorsIsTimeout(err) {
			return 0, "", status.Error(codes.DeadlineExceeded, "Legacy system timed out")
		}
		return 0, "", status.Errorf(codes.Unavailable, "Legacy transport failure: %v", err)
	}
	defer resp.Body.Close()

	// Batasi pembacaan respons maksimal 2MB untuk mencegah XML entity expansion (Billion Laughs attack)
	limitedReader := io.LimitReader(resp.Body, 2*1024*1024)
	bodyBytes, err := io.ReadAll(limitedReader)
	if err != nil {
		return 0, "", status.Errorf(codes.Internal, "Failed reading response payload: %v", err)
	}

	// 5. Unmarshal XML
	var soapResp LegacyEnvelopeResponse
	if err := xml.Unmarshal(bodyBytes, &soapResp); err != nil {
		return 0, "", status.Errorf(codes.DataLoss, "Malformed XML payload from upstream: %v", err)
	}

	// 6. Tangani skenario SOAP Fault
	if soapResp.Body.Fault != nil {
		return 0, "", mapSOAPFaultToGRPC(soapResp.Body.Fault)
	}

	// 7. Kembalikan data murni
	return soapResp.Body.QueryAccountResponse.Balance, soapResp.Body.QueryAccountResponse.Status, nil
}

// mapSOAPFaultToGRPC memetakan secara presisi pesan error XML ke kode standar gRPC
func mapSOAPFaultToGRPC(fault *SOAPFault) error {
	switch fault.FaultCode {
	case "soap:Client.AuthenticationFailed":
		return status.Error(codes.Unauthenticated, fault.FaultString)
	case "soap:Client.InvalidAccount":
		return status.Error(codes.NotFound, fault.FaultString)
	case "soap:Client":
		return status.Error(codes.InvalidArgument, fault.FaultString)
	case "soap:Server.LockWaitTimeout":
		return status.Error(codes.Aborted, fault.FaultString)
	default:
		return status.Errorf(codes.Internal, "Legacy internal error [%s]: %s", fault.FaultCode, fault.FaultString)
	}
}

func errorsIsTimeout(err error) bool {
	if nErr, ok := err.(net.Error); ok && nErr.Timeout() {
		return true
	}
	return false
}
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi Arsitektur | Opsi A: Enterprise Service Bus (ESB) Terpusat | Opsi B: Micro-Wrappers + Anti-Corruption Layer |
| :--- | :--- | :--- |
| **Kopling Sistem** | **Tinggi.** Seluruh rute integrasi berada di engine tunggal. Rilis satu endpoint berisiko mengganggu aliran pesan service lain. | **Rendah.** Setiap wrapper terisolasi dalam bounded context masing-masing; deployment independen. |
| **Beban Operasional** | Dikelola oleh platform team khusus via proprietary software (e.g., TIBCO, IBM MQ, MuleSoft). Licensing cost tinggi. | Dikelola oleh engineering team via open-source tech stack (Go/Rust/Java, Kafka, Envoy). |
| **Debugging & Observability**| Sangat sulit menembus tracing end-to-end melintasi proprietary bus runtime. Sering terjadi black-box failures. | Standar OpenTelemetry native, distributed tracing via W3C TraceContext headers berjalan mulus. |

---

| Strategi Akses Data | Opsi A: Direct DB Polling (`SELECT ... WHERE updated_at >`) | Opsi B: Log-Based Change Data Capture (Debezium) |
| :--- | :--- | :--- |
| **Dampak Performa DB** | **Tinggi.** CPU spike, table/index scan rutin, berpotensi memicu table locks pada transaksi legacy aktif. | **Minimal.** Membaca log transaksi asinkron dari disk; memori engine query database tidak terbebani. |
| **Deteksi DELETE** | **Gagal.** Operasi hard DELETE menghapus record secara permanen; polling query tidak akan pernah melihatnya. | **Sempurna.** Operasi hard DELETE dicatat di log transaksi sebagai tombstone event. |
| **Latensi Data** | Batch/Scheduled Latency (hitungan menit hingga jam tergantung interval poll). | Near-Real-Time (< 500 milidetik dari saat commit terjadi). |
| **Kompleksitas Setup** | Sangat Rendah. Cukup cron job dan script query SQL sederhana. | Menengah-Tinggi. Memerlukan hak akses replication slot pada RDBMS dan cluster Kafka/ZooKeeper/KRaft. |

---

## SEKSI 11 — BEST PRACTICES

1. **Gunakan Bulkhead & Concurrency Throttling:** Sistem legacy memiliki batas konkurensi rendah (seringkali crash jika menerima >50 concurrent queries). Gunakan worker pools atau channel semaphore di layer facade untuk membatasi jumlah paralel request ke legacy.
2. **Karantina Namespace XML dan Gunakan Strict Buffer Limits:** Jangan pernah melakukan parsing XML tanpa membatasi ukuran body menggunakan `io.LimitReader` untuk menghindari kerentanan *XML Entity Expansion* (DoS).
3. **Posisikan Schema Registry sebagai Kontrak:** Saat mengalirkan data melalui CDC, gunakan Apache Avro atau Protobuf bersama Confluent Schema Registry. Terapkan kompatibilitas `BACKWARD` atau `FULL` agar schema drift pada DB legacy tidak mematahkan consumer downstream.
4. **Terapkan Transactional Outbox Pattern pada Legacy Database:** Jika aplikasi baru harus menulis ke sistem legacy dan memicu event stream secara atomik, tulis mutasi dan outbox record dalam satu transaksi database lokal sebelum diteruskan ke bus eksternal.
5. **Gunakan Distributed Idempotency Keys:** Komunikasi legacy rentan mengalami network timeout semu (request sukses diproses di mainframe, tapi response putus di tengah jalan). Setiap RPC wrapper harus menyuntikkan ID idempotensi unik ke header payload legacy jika didukung, atau mengeksekusi *read-before-write validation*.
6. **Desain Degradasi Graceful dengan Local Read Cache:** Jika legacy backend down untuk proses batch harian (*nightly maintenance window* yang umum di perbankan), arahkan query bacaan ke Read Model ter-sinkronisasi (misal: Redis/Elasticsearch yang diisi oleh CDC) sementara write requests ditahan di buffer antrean.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1. **The Dual-Write Trap:** 
   * *Anti-pattern:* Menulis data ke database legacy, lalu memanggil `kafkaProducer.Send()` di kode aplikasi. 
   * *Bencana:* Jika aplikasi crash tepat setelah commit DB tapi sebelum kirim ke Kafka, event hilang selamanya. Jika commit DB gagal tapi kirim event berhasil, terjadi *phantom data*. Gunakan CDC langsung dari write-ahead log untuk menjamin atomisitas!
2. **Leaky Domain Entities:**
   * *Anti-pattern:* Membiarkan DTO auto-generated dari WSDL (SOAP) atau nama kolom DB legacy diekspos langsung ke REST/gRPC client modern.
   * *Bencana:* Kode downstream modern dipenuhi konseptual usang (misal: flag integer `1, 2, 3` tanpa enum, kolom bernilai string `"NULL"`). Segera isolasi menggunakan Anti-Corruption Layer.
3. **Mengabaikan Karakter Set & Encoding Non-UTF-8:**
   * *Anti-pattern:* Mengasumsikan respons legacy selalu UTF-8.
   * *Bencana:* Mainframe seringkali merespons dalam format byte string berbasis Windows-1252, ISO-8859-1, atau bahkan EBCDIC. Parsing langsung ke JSON parser modern akan menghasilkan *unicode replacement characters* (`\uFFFD`) atau silent corruption.
4. **Retry Storms Tanpa Backoff & Jitter:**
   * *Anti-pattern:* Ketika legacy server merespons HTTP 500 atau timeout, client modern langsung melakukan retry agresif instan (loop 3x tanpa delay).
   * *Bencana:* *Thundering herd problem*. Legacy server yang mulai melambat akan langsung *crash* total karena beban request berlipat ganda dari seluruh antrean client.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Tugas: Membangun Anti-Corruption Consumer Engine untuk Data CDC

#### Skenario:
Sistem legacy ERP perbankan memutasi tabel `TB_ACC_MSTR` pada database Oracle. Engine CDC (Debezium) mem-parsing log dan mengirim event JSON mentah ke Kafka topic `legacy.raw.accounts`. Anda diminta membangun layer consumer ACL yang menormalkan data, memvalidasi integritas, membuang data corrupt, dan mempublikasikan data bersih ke topic modern `account.v1.events`.

#### Spesifikasi Input Payload (`legacy.raw.accounts`):
```json
{
  "op": "u",
  "ts_ms": 1698001122334,
  "before": {
    "ACC_NUM": "1000921",
    "BAL_VAL": "15000000",
    "TX_STS": "A"
  },
  "after": {
    "ACC_NUM": "1000921",
    "BAL_VAL": "14500000",
    "TX_STS": "D"
  }
}
```

#### Aturan Transformasi ACL:
1. Kolom `ACC_NUM` diubah menjadi Canonical ID dengan prefix `ACC-` (contoh: `ACC-1000921`).
2. Kolom `BAL_VAL` merupakan integer balance dalam sen (cents). Konversikan ke format desimal akurat: `14500000` -> `145000.00`.
3. Kolom `TX_STS` memiliki pemetaan status:
   * `"A"` -> `STATUS_ACTIVE`
   * `"D"` -> `STATUS_DORMANT`
   * Nilai lainnya -> Invalid, harus diarahkan ke Dead-Letter-Queue (DLQ).
4. Buat file implementasi menggunakan Go, Python, atau Rust yang memproses stream event ini secara aman tanpa runtime crash. Sertakan mekanisme recovery panic.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Mengapa membaca log transaksi (WAL/Redo Log) melalui CDC lebih diunggulkan daripada mengeksekusi query database polling berbasis timestamp secara terjadwal?**
   * A. Karena CDC dapat mem-bypass seluruh sistem otorisasi database.
   * B. Karena query polling tidak dapat menangkap mutasi hard DELETE dan memberikan beban parsing/locking langsung pada RDBMS legacy.
   * C. Karena CDC secara otomatis mengonversi data ke skema NoSQL tanpa konfigurasi tambahan.
   * D. Karena query polling memiliki latensi di bawah 10 milidetik.
   * *Jawaban yang Benar:* **B** — Query polling mengeksekusi `SELECT` berulang yang memicu pemakaian CPU, disk I/O, dan berpotensi locking. Selain itu, record yang di-hard delete sudah lenyap dari tabel saat cron dijalankan, sedangkan CDC menangkap mutasi delete langsung dari storage log commit.

2. **Peran utama dari Anti-Corruption Layer (ACL) dalam arsitektur Domain-Driven Design adalah:**
   * A. Mempercepat koneksi TCP fisik antara client dan server.
   * B. Mengonversi data database relasional menjadi raw JSON string.
   * C. Menjembatani dua subsistem yang memiliki model semantik domain berbeda agar konsep domain legacy tidak mencemari domain service modern.
   * D. Menggantikan peran firewall dan anti-DDOS protection pada layer network.
   * *Jawaban yang Benar:* **C** — ACL bertanggung jawab melakukan isolasi semantik sehingga desain arsitektur baru tidak terikat pada terminologi usang, format ganjil, dan kelemahan domain milik arsitektur upstream legacy.

3. **Manakah dari pola berikut yang efektif digunakan untuk mencegah sistem legacy backend bertroughput rendah tumbang akibat lonjakan request dari microservices modern?**
   * A. Saga Pattern.
   * B. Bulkhead Concurrency Limiting dan Rate Limiter pada Facade Layer.
   * C. Direct Read-Replication Bypass.
   * D. Immediate Retry Loop tanpa Backoff.
   * *Jawaban yang Benar:* **B** — Bulkhead membatasi jumlah eksekusi simultan yang dapat mengakses sistem upstream legacy, sehingga server backend tua tidak kehabisan thread atau database connection pool.

4. **Kelemahan paling fatal dari strategi Dual-Write (menulis ke database dan mempublikasikan event ke message broker secara berurutan dalam aplikasi) adalah:**
   * A. Menggunakan terlalu banyak bandwidth jaringan.
   * B. Format pesan Kafka tidak kompatibel dengan SQL.
   * C. Ketidakmampuan menjamin atomisitas transaksional jika terjadi crash parsial antara operasi pertama dan kedua.
   * D. Memperlambat proses serialisasi data di memori aplikasi.
   * *Jawaban yang Benar:* **C** — Dual-write rentan terhadap partial failure: jika aplikasi mati tepat setelah commit DB berhasil tetapi broker belum menerima pesan, data menjadi inkonsisten secara permanen.

5. **Saat membungkus payload SOAP/XML ke REST/JSON, mengapa penggunaan `sync.Pool` pada Go atau streaming parser (SAX/StAX) lebih direkomendasikan daripada standard tree-based parser (DOM)?**
   * A. Karena parser DOM tidak mendukung encoding XML versi terbaru.
   * B. Parser DOM memuat seluruh struktur XML ke dalam memory tree, menyebabkan alokasi memori heap tinggi dan memicu lonjakan Garbage Collection pause pada traffic tinggi.
   * C. Streaming parser menjamin enkripsi HTTPS end-to-end secara otomatis.
   * D. XML standar tidak dapat diuraikan oleh runtime 64-bit tanpa streaming parser.
   * *Jawaban yang Benar:* **B** — Parsing XML bertipe DOM mengonsumsi banyak alokasi memori. Pada sistem integrasi enterprise yang menangani dokumen XML berukuran ratusan kilobyte atau megabyte, ini memicu GC overhead masif. Streaming parser atau pool memori memproses data dengan alokasi heap mendekati nol.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Buku:**
  * *"Enterprise Integration Patterns: Designing, Building, and Deploying Messaging Solutions"* oleh Gregor Hohpe & Bobby Woolf. (Kompilasi wajib arsitektur pesan, canonical model, dan adapter).
  * *"Designing Data-Intensive Applications"* (Chapter 11: Stream Processing - CDC & Outbox) oleh Martin Kleppmann.
  * *"Domain-Driven Design: Tackling Complexity in the Heart of Software"* (Chapter 14: Strategic Design - Anti-Corruption Layer) oleh Eric Evans.
* **Whitepaper & Dokumentasi Arsitektur:**
  * Debezium Documentation: Architecture and Change Data Capture Mechanics on PostgreSQL and Oracle Engine (`https://debezium.io/documentation/`).
  * Confluent: The Outbox Pattern and Microservices Event Sourcing using CDC.
* **Standar Spesifikasi Industri:**
  * W3C SOAP Version 1.2 Specification (`https://www.w3.org/TR/soap12/`).
  * gRPC over HTTP/2 Wire Protocol Specification.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. Sistem legacy adalah realitas enterprise yang tidak dapat disingkirkan secara instan; FDE harus menguasai strategi integrasi non-invasif untuk menjaga reliabilitas bisnis.
2. Arsitektur terpusat seperti ESB telah bergeser ke arah arsitektur *"Smart Endpoints, Dumb Pipes"*, di mana kecerdasan translasi berada pada service edge (wrapper/ACL) dan transport dihandle oleh streaming platform modern.
3. Log-Based Change Data Capture (CDC) menyelesaikan krisis integritas data tanpa membebani CPU sistem database operasional, sekaligus mengeliminasi bahaya transaksi parsial (*Dual-Write trap*).
4. SOAP-to-gRPC Facade modern memerlukan rekayasa resource yang ketat: kontrol batas konkurensi (Bulkhead), optimalisasi memori (Buffer Pools), parsing streaming payload, dan pemetaan error code yang deterministik.
5. Anti-Corruption Layer (ACL) bertindak sebagai benteng pertahanan semantik kode modern, memastikan bahwa kompleksitas teknis dan *technical debt* dari sistem legacy tidak mencemari Domain Context baru.

---

## SEKSI 17 — GLOSARIUM

* **Anti-Corruption Layer (ACL):** Komponen arsitektural yang menerjemahkan model domain yang berbeda tanpa membiarkan semantik satu domain mencemari domain lainnya.
* **Bulkhead Pattern:** Pola isolasi kegagalan yang membatasi alokasi resource maksimum (misal: connection/thread/concurrency slot) untuk operasi tertentu agar kegagalan upstream tidak menghabiskan seluruh resource sistem.
* **Change Data Capture (CDC):** Teknik merekam mutasi data level baris pada database secara asinkron langsung dari transaction commit log.
* **Canonical Data Model (CDM):** Format data netral yang disepakati secara organisasi untuk menghubungkan berbagai sistem heterogen.
* **Dual-Write Hazard:** Kondisi anomali data inkonsisten yang terjadi ketika sebuah aplikasi mencoba menulis mutasi ke dua media storage terpisah tanpa algoritma konsensus transaksional terdistribusi (2PC).
* **Enterprise Service Bus (ESB):** Middleware terpusat yang menangani orkestrasi, transformasi format, dan perutean protokol komunikasi antar aplikasi enterprise.
* **SOAP Fault:** Spesifikasi struktur pesan kegagalan standar pada protokol SOAP XML.
* **Transactional Outbox:** Pola di mana event pesan disimpan ke tabel database lokal dalam satu transaksi atomik bersama state aplikasi, lalu dibaca oleh CDC untuk dialirkan ke message broker.
* **Write-Ahead Logging (WAL):** Mekanisme database engine di mana semua perubahan data harus dicatat ke disk log sebelum diterapkan ke data file aktual guna menjamin durabilitas transaksi (ACID).

---

## SEKSI 18 — CATATAN INSTRUKTUR

### Pacing & Pembagian Durasi (Total 3 Jam Teori + 2 Jam Lab)
* **Jam 1:** Bedah Anatomi ESB vs Modern Streaming. Diskusikan realita lapangan (perbankan, telekomunikasi) di mana arsitektur ESB runtuh akibat logic bloat.
* **Jam 2:** Deep Dive SOAP to gRPC/REST Facade: Manajemen konkurensi, memory pool, dan error mapping.
* **Jam 3:** Change Data Capture internals (WAL replication stream, Postgres `test_decoding`/`pgoutput`, Debezium mechanics) dan ACL pattern.
* **Sesi Lab (2 Jam):** Peserta melakukan hands-on debugging integrasi di mana upstream SOAP sengaja dibuat lambat dan mengeluarkan format XML corrupt.

### Analogi Pengajaran
Gunakan analogi **"Keduataan Besar dan Penerjemah Diplomatik"** untuk menjelaskan Anti-Corruption Layer:
* Anda tidak membiarkan hukum dan bahasa negara asing (legacy system) langsung diberlakukan di teritori internal negara Anda (modern microservices).
* Setiap kali ada interaksi, utusan harus melewati *Kedutaan Besar* (ACL) yang menolak dokumen ilegal, menolak bahasa asing yang tidak dimengerti, dan menerjemahkannya ke dalam hukum serta bahasa resmi negara setempat (Canonical Domain Model).

### War Story dari Lapangan
*Skenario:* Sebuah perusahaan fintech terkemuka mengalami insiden downtime 8 jam pada core transaksi mereka saat meluncurkan microservice baru. Microservice tersebut melakukan pooling interval 2 detik menggunakan query SQL `SELECT * FROM tbl_user WHERE updated_at > NOW() - INTERVAL '5 seconds'` pada tabel legacy Oracle dengan 80 juta baris data tanpa indeks komposit yang tepat. Hal ini memicu *Full Table Scan* terus-menerus, memakan 100% CPU core database, dan membuat teller bank di seluruh cabang nasional mengalami freeze transaksi kasir.
*Pelajaran:* Terapkan CDC log-based; jangan pernah melakukan polling query langsung pada tabel operasional tier 1 sistem legacy.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi 1.0.0 (Oktober 2023):**
  * Rilis inisial materi kurikulum FDE.
  * Penambahan implementasi produksi Go SOAP-to-gRPC wrapper dengan `sync.Pool` dan bulkhead semaphore.
  * Penyusunan modul mitigasi Dual-Write dan arsitektur CDC Debezium.
  * Integrasi latihan hands-on translasi Anti-Corruption Layer.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya:** Kategori 05 — Advanced Distributed Database & Consensus Mechanics
* **Modul Berikutnya:** Kategori 06, Bab 02, Modul 02 — *High-Throughput Event-Driven Microservices: Kafka Topology, Exactly-Once Processing Semantics (EOS), & Dead-Letter Recovery*
* **Tautan Silang Terkait:**
  * Kategori 03: *High-Performance Networking & Protocol Translation*
  * Kategori 04: *Observability, Distributed Tracing (OpenTelemetry), & Site Reliability Engineering*