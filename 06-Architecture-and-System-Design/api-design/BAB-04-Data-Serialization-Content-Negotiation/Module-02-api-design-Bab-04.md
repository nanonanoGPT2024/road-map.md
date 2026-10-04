# Kurikulum Enterprise: Arsitektur API & Desain Sistem
## Kategori: 06-Architecture-and-System-Design
### BAB-04: Data Serialization & Content Negotiation
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Principal Architect / Senior Software Engineer diharapkan mampu:
- **Menganalisis & Mengeliminasi Bottleneck Serialisasi**: Mengidentifikasi inefisiensi alokasi memori, *garbage collection churn*, dan CPU *overhead* yang disebabkan oleh parser berbasis teks (JSON/XML) pada *high-throughput service* (100k+ RPS).
- **Merancang Mesin Negosiasi Konten RFC 7231 / RFC 9110**: Mengimplementasikan algoritma *proactive content negotiation* berbasis bobot prioritas (*q-factor weighting*) dengan resolusi MIME *wildcard* dan *fallback strategy* deterministik.
- **Mengimplementasikan Dual-Protocol API Engine**: Membangun *pipeline* terintegrasi yang melayani JSON dan Protocol Buffers secara transparan pada satu endpoint HTTP/2 atau HTTP/3 menggunakan *zero-allocation buffer pooling*.
- **Mengelola Evolusi Skema Lintas Protokol**: Menerapkan tata kelola kompatibilitas skema (*backward, forward, full compatibility*) menggunakan *Schema Registry* dan *canary deployment* tanpa *downtime*.
- **Mengoptimasi Payload Compression Pipeline**: Menerapkan kompresi dinamis multi-algoritma (Zstandard, Brotli, Gzip) dengan evaluasi ambang batas ukuran (*dynamic thresholding*) berbasis utilisasi CPU *core*.

---

### 2. Prerequisites
Sebelum menelaah materi ini, peserta wajib menguasai:
- **HTTP Semantics & Internals**: Pemahaman mendalam RFC 9110 (HTTP Semantics), khususnya *headers* `Accept`, `Content-Type`, `Accept-Encoding`, dan representasi status code `406 Not Acceptable` serta `415 Unsupported Media Type`.
- **Sistem Memori & Concurrency**: Memahami konsep *stack vs heap allocation*, *pointer chasing*, *cache locality (L1/L2/L3)*, alokasi memori dinamis, serta mekanisme *Garbage Collector (GC)*.
- **Binary Encoding Fundamentals**: Penguasaan konsep *Varints (Variable-length quantities)*, *ZigZag encoding*, *Little/Big Endianness*, serta representasi *Type-Length-Value (TLV)*.
- **Tooling**: Kemampuan menggunakan Golang (v1.22+), `curl`, `protoc`, Google Benchmark/Go Test Benchmark, dan profiling tools (`pprof`, `perf`).

---

### 3. Concept & Internal Architecture

#### 3.1. Anatomi Serialisasi: Teks vs Biner di Level Hardware
Serialisasi teks (seperti JSON) menuntut parser memindai *byte-by-byte*, memvalidasi sintaks kurung kurawal, mengonversi teks ASCII/UTF-8 menjadi representasi numerik CPU via algoritma string scanning, dan menghasilkan *heap allocations* masif untuk setiap *field*.

Sebaliknya, serialisasi biner terstruktur (Protobuf/FlatBuffers):
- Menggunakan skema tetap yang dikompilasi ke dalam representasi kode native.
- Membaca field menggunakan *tag* biner (Field Number + Wire Type) yang diproses langsung melalui instruksi bitwise CPU.
- Memanfaatkan *Zero-Copy Deserialization* (khususnya FlatBuffers/Cap'n Proto): *in-memory representation* pada wire identik dengan layout struct di RAM, mengeliminasi fase parsing sepenuhnya dan meniadakan pointer chasing.

```
JSON Wire Format:
[ '{' ] [ '"' ] [ 'i' ] [ 'd' ] [ '"' ] [ ':' ] [ '1' ] [ '2' ] [ '3' ] ...
  ↳ Parser harus memindai setiap byte, verifikasi string, parse int dari char '1','2','3'.

Protobuf Wire Format:
[ 00001 000 ] [ 01111011 ]
   Tag (1)       Value (123)
   WireType(0)   Varint (Direct bitwise shift & mask)
```

#### 3.2. Proactive vs Reactive Content Negotiation Internals
RFC 9110 Section 12 mendefinisikan dua strategi utama negosiasi konten:
1. **Server-driven (Proactive)**: Klien mendeklarasikan kapabilitas dan preferensinya melalui header HTTP (`Accept`, `Accept-Encoding`, `Accept-Language`). Server mengevaluasi preferensi ini menggunakan kalkulasi *Quality Value* ($q$) dari rentang $0.000$ hingga $1.000$.
2. **Agent-driven (Reactive)**: Server merespons dengan status `300 Multiple Choices` atau `406 Not Acceptable` disertai metadata daftar representasi alternatif, membiarkan klien memilih secara eksplisit via round-trip kedua. *Dalam sistem backend enterprise berlatensi rendah, proactive negotiation hampir selalu digunakan secara eksklusif guna menghindari network round-trip penalty.*

```
Priority Engine:
Accept: application/protobuf;q=0.9, application/json;q=0.8, */*;q=0.1

1. Tokenize Header -> Extract [MIME, Parameters, Q-Factor]
2. Sort Descending by Q-Factor
3. Resolusi Match terhadap Available Server Mimes:
   - Match Specific: type/subtype == available/subtype
   - Match Wildcard Subtype: type/* == available/*
   - Match Full Wildcard: */*
4. Evaluasi Format Mutu Tertinggi -> Inisialisasi Encoder Context
```

---

### 4. Why & What

| Dimensi | Mengapa Pendekatan Tradisional (Naive JSON) Gagal | Solusi Enterprise: Hybrid Multi-Format Architecture |
| :--- | :--- | :--- |
| **CPU Utilization** | Deserialisasi string JSON mengonsumsi hingga 30-40% total siklus CPU pada node edge gateway skala besar akibat alokasi memori berulang dan parsing teks. | Serialisasi biner (Protobuf/FlatBuffers) menurunkan beban CPU hingga 70-80% untuk *high-frequency payloads*, menyisakan siklus CPU untuk logika bisnis. |
| **Network Bandwidth** | JSON mentransmisikan metadata (nama field) secara berulang di setiap pesan. Kompresi teks (Gzip) menambah latensi CPU signifikan di edge. | Binary format hanya mengirim *field index* numerik. Dikombinasikan dengan Zstandard tingkat lanjut, ukuran payload menyusut hingga 85% tanpa lonjakan latensi dekompresi. |
| **API Consumer Diversity** | Memaksa satu protokol serialisasi (hanya JSON atau hanya gRPC) mengorbankan kompatibilitas: Web client butuh JSON, service-to-service butuh binary streaming. | Menerapkan *Dynamic Content Negotiation Middleware* transparan pada HTTP layer: Web/Mobile lama menerima JSON, microservice performa tinggi menerima Protobuf via endpoint yang sama. |
| **Contract Stability** | Format teks tanpa schema registry rentan terhadap perubahan data tak terduga (*type-coercion bugs*, *missing fields*). | Skema Protobuf/Avro terikat *schema evolution rules* yang didefinisikan secara deklaratif di pipeline CI/CD. |

---

### 5. How (Workflow Detail)

Alur eksekusi internal sebuah request yang melewati *High-Performance Content Negotiation & Serialization Pipeline*:

```
[ Incoming Client TCP/HTTP Stream ]
               │
               ▼
[ 1. HTTP Header Interceptor ] ──> Cek Header `Accept` & `Content-Type`
               │
               ▼
[ 2. Matrix Weight Parser ] ────> Ekstraksi q-values, parsing media-type (RFC-compliant)
               │
               ▼
[ 3. Negotiator Resolver ] ────> Cocokkan dengan Provider Registry:
               │                 - application/x-protobuf
               │                 - application/json
               │                 Fallback: Return 406 Not Acceptable (jika */* dilarang)
               │
               ▼
[ 4. Zero-Copy Deserializer ] ──> Ambil struct dari sync.Pool
               │                 Deserialize payload sesuai Content-Type
               │                 Eksekusi Core Domain Logic
               │
               ▼
[ 5. Dynamic Compression ] ────> Baca Accept-Encoding (zstd, br, gzip)
               │                 Bypass jika payload < ambang batas (e.g., 1024 bytes)
               │
               ▼
[ 6. Zero-Alloc Serializer ] ───> Encode Domain Struct ke buffer tujuan (sync.Pool)
               │                 Tulis Content-Type & Vary Header
               │
               ▼
[ Outgoing Byte Stream to Socket ]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Sistem
Bayangkan terminal logistik internasional:
- **Naive JSON**: Barang dikirim bersama manual instruksi lengkap dalam bahasa Inggris yang dicetak ulang di setiap kotak. Petugas bongkar muat harus membaca dokumen tersebut dari awal sampai akhir setiap kali paket tiba, lalu menerjemahkannya.
- **Binary Serialization (Protobuf)**: Barang dikemas dalam kontainer terstandarisasi dengan kode numerik batang (*barcode*). Mesin pemindai langsung mengetahui isi boks dalam mikrodetik berdasarkan katalog global yang telah disimpan sebelumnya di terminal.
- **Content Negotiation**: Petugas bea cukai memeriksa preferensi bahasa penerima; jika penerima memahami kode mesin (*barcode scanner*), paket dikirim dalam kontainer biner murni. Jika penerima adalah kurir lokal reguler, paket dialihkan secara otomatis ke mesin pengemas yang mencetak dokumen bahasa manusia (JSON).

#### Diagram Arsitektur Memory Buffer Pool & Content Negotiation Engine

```
+---------------------------------------------------------------------------------------+
| HTTP Ingress (e.g., Kernel Socket -> Go Runtime Netpoll)                             |
+---------------------------------------------------------------------------------------+
                                           │
                                           ▼
+---------------------------------------------------------------------------------------+
| Middleware: RFC-9110 Content Negotiator                                              |
|                                                                                       |
|  Request Header:                                                                      |
|  Accept: application/x-protobuf;q=1.0, application/json;q=0.5                         |
|                                                                                       |
|  +---------------------------+       Match Found:                                     |
|  | Matched Content Encoders: | ────> [ application/x-protobuf ]                       |
|  +---------------------------+       (Highest weight, fully supported)                |
+---------------------------------------------------------------------------------------+
                                           │
                                           ▼
+---------------------------------------------------------------------------------------+
| Execution Layer (Zero-Allocation Pipeline)                                            |
|                                                                                       |
|  +---------------------+                                                              |
|  | sync.Pool (Buffers) | <─── Meminjam slice byte pra-alokasi (Mencegah GC Churn)     |
|  +---------------------+                                                              |
|             │                                                                         |
|             ▼                                                                         |
|  +---------------------+         +---------------------+        +------------------+  |
|  | Proto/JSON Encoder  | ──────> | Compression Engine  | ─────> | HTTP Response    |  |
|  | (Writes to Buffer)  |         | (Zstandard dynamic) |        | Writer           |  |
|  +---------------------+         +---------------------+        +------------------+  |
|             │                                                                         |
|             ▼                                                                         |
|  +---------------------+                                                              |
|  | sync.Pool (Put)     | ───> Mengembalikan buffer setelah flush ke socket           |
|  +---------------------+                                                              |
+---------------------------------------------------------------------------------------+
```

---

### 7. Code Implementations

#### 7.1. Protobuf Schema Definition
Simpan skema ini sebagai `account.proto`:

```protobuf
syntax = "proto3";

package enterprise.finance.v1;

option go_package = "enterprise/finance/v1;financev1";

message BalanceSnapshot {
  string account_id = 1;
  string currency = 2;
  int64 available_balance_cents = 3;
  int64 reserved_balance_cents = 4;
  uint64 sequence_number = 5;
  int64 last_updated_epoch_ms = 6;
}
```

Kompilasi skema:
```bash
protoc --go_out=. --go_opt=paths=source_relative account.proto
```

#### 7.2. Implementasi RFC-9110 Negotiator & Handler Standar Industri
Berikut adalah implementasi *production-ready* dalam Go yang menangani negosiasi konten, *buffer pooling*, parsing bobot `q-factor`, dan kompresi Zstandard secara optimal.

```go
package main

import (
	"bytes"
	"errors"
	"io"
	"net/http"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"

	financev1 "enterprise/finance/v1"

	"github.com/klauspost/compress/zstd"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/encoding/protojson"
)

// MediaType merepresentasikan MIME type beserta bobot q-factor-nya.
type MediaType struct {
	Type    string
	Subtype string
	Quality float64
	Raw     string
}

// MediaTypeDefs konstanta representasi media.
const (
	MIMEApplicationProtobuf = "application/x-protobuf"
	MIMEApplicationJSON     = "application/json"
	MIMEWildcard            = "*/*"
)

var (
	// Buffer pool untuk menekan alokasi memory heap secara agresif.
	bufPool = sync.Pool{
		New: func() any {
			return new(bytes.Buffer)
		},
	}

	// Inisialisasi zstd encoder & decoder pool.
	zstdEncoder, _ = zstd.NewWriter(nil, zstd.WithEncoderLevel(zstd.SpeedDefault))
)

// ParseAcceptHeader mem-parsing header Accept sesuai RFC 9110 Section 12.5.1.
func ParseAcceptHeader(header string) []MediaType {
	if header == "" {
		return []MediaType{{Type: "*", Subtype: "*", Quality: 1.0, Raw: MIMEWildcard}}
	}

	parts := strings.Split(header, ",")
	results := make([]MediaType, 0, len(parts))

	for _, part := range parts {
		subparts := strings.Split(strings.TrimSpace(part), ";")
		media := subparts[0]
		quality := 1.0

		for _, param := range subparts[1:] {
			param = strings.TrimSpace(param)
			if strings.HasPrefix(param, "q=") {
				if qVal, err := strconv.ParseFloat(param[2:], 64); err == nil {
					quality = qVal
				}
			}
		}

		types := strings.Split(media, "/")
		if len(types) == 2 {
			results = append(results, MediaType{
				Type:    strings.TrimSpace(types[0]),
				Subtype: strings.TrimSpace(types[1]),
				Quality: quality,
				Raw:     media,
			})
		}
	}

	// Urutkan preferensi berdasarkan bobot Quality secara descending
	sort.SliceStable(results, func(i, j int) bool {
		return results[i].Quality > results[j].Quality
	})

	return results
}

// SelectBestMediaType mencocokkan media types klien terhadap kapabilitas server.
func SelectBestMediaType(acceptHeader string, serverSupported []string) (string, error) {
	parsedAccepts := ParseAcceptHeader(acceptHeader)

	for _, clientMedia := range parsedAccepts {
		if clientMedia.Quality <= 0 {
			continue // Menolak representasi yang secara eksplisit tidak dikehendaki (q=0)
		}

		for _, serverMedia := range serverSupported {
			if clientMedia.Raw == MIMEWildcard || clientMedia.Raw == serverMedia {
				return serverMedia, nil
			}

			// Penanganan wildcard sebagian, e.g. "application/*"
			if clientMedia.Subtype == "*" {
				serverParts := strings.Split(serverMedia, "/")
				if clientMedia.Type == serverParts[0] {
					return serverMedia, nil
				}
			}
		}
	}

	return "", errors.New("tidak ada representasi media yang cocok (406 Not Acceptable)")
}

// BalanceServiceHandler bertindak sebagai endpoint terpadu multi-protokol.
func BalanceServiceHandler(w http.ResponseWriter, r *http.Request) {
	// Menjamin HTTP caching proksi menghormati negosiasi konten
	w.Header().Add("Vary", "Accept, Accept-Encoding")

	if r.Method != http.MethodGet {
		http.Error(w, "Metode HTTP dilarang", http.StatusMethodNotAllowed)
		return
	}

	// 1. Content Negotiation
	supportedMedia := []string{MIMEApplicationProtobuf, MIMEApplicationJSON}
	bestMedia, err := SelectBestMediaType(r.Header.Get("Accept"), supportedMedia)
	if err != nil {
		w.Header().Set("Content-Type", "application/problem+json")
		w.WriteHeader(http.StatusNotAcceptable)
		w.Write([]byte(`{"status":406,"detail":"Format yang diminta tidak didukung oleh resource ini."}`))
		return
	}

	// 2. Fetch/Build Domain Model (Simulasi Enterprise State)
	data := &financev1.BalanceSnapshot{
		AccountId:              "acc_corp_9948271048",
		Currency:               "USD",
		AvailableBalanceCents:  1050045099, // $10,500,450.99
		ReservedBalanceCents:   45000000,   // $450,000.00
		SequenceNumber:         1049281,
		LastUpdatedEpochMs:     time.Now().UnixMilli(),
	}

	// 3. Serialisasi Menggunakan Memory Buffer Pool
	buf := bufPool.Get().(*bytes.Buffer)
	buf.Reset()
	defer bufPool.Put(buf)

	switch bestMedia {
	case MIMEApplicationProtobuf:
		bytesPayload, protoErr := proto.Marshal(data)
		if protoErr != nil {
			http.Error(w, "Gagal serialisasi protobuf", http.StatusInternalServerError)
			return
		}
		buf.Write(bytesPayload)

	case MIMEApplicationJSON:
		// Menggunakan protojson standard runtime untuk compliance Protobuf Schema-JSON
		jsonOpts := protojson.MarshalOptions{
			UseProtoNames:   true,
			EmitUnpopulated: true,
		}
		bytesPayload, jsonErr := jsonOpts.Marshal(data)
		if jsonErr != nil {
			http.Error(w, "Gagal serialisasi json", http.StatusInternalServerError)
			return
		}
		buf.Write(bytesPayload)
	}

	// 4. Content Encoding / Compression Decision
	acceptEncoding := r.Header.Get("Accept-Encoding")
	w.Header().Set("Content-Type", bestMedia)

	// Batas ambang kompresi: Jangan kompresi jika buffer di bawah 1024 bytes (overhead CPU > keuntungan bandwidth)
	const compressionThreshold = 1024
	if strings.Contains(acceptEncoding, "zstd") && buf.Len() >= compressionThreshold {
		w.Header().Set("Content-Encoding", "zstd")
		w.WriteHeader(http.StatusOK)

		zstdWriter := zstdEncoder
		zstdWriter.Reset(w)
		defer zstdWriter.Close()

		if _, copyErr := io.Copy(zstdWriter, buf); copyErr != nil {
			// Pada titik ini headers sudah terkirim, tangani failure di log
			return
		}
	} else {
		w.WriteHeader(http.StatusOK)
		w.Write(buf.Bytes())
	}
}

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("/v1/accounts/balance", BalanceServiceHandler)

	server := &http.Server{
		Addr:         ":8080",
		Handler:      mux,
		ReadTimeout:  5 * time.Second,
		WriteTimeout: 10 * time.Second,
		IdleTimeout:  120 * time.Second,
	}

	if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		panic(err)
	}
}
```

---

### 8. Real-World Case Study (Enterprise Scale)

#### Kasus: Migrasi Payment Ingress Gateway Skala 250,000 RPS
- **Latar Belakang**: Sebuah platform pembayaran global memproses transaksi debit instan dengan volume puncak 250k RPS. Arsitektur lama mengekspos REST JSON murni melalui HTTP/1.1.
- **Problem**:
  - *Garbage Collection (GC) STW (Stop-The-World) Spikes*: Parsing teks JSON menghasilkan jutaan obyek sementara di heap per detik, memicu *latency degradation* p99 melonjak dari 15ms menjadi 280ms di bawah beban puncak.
  - *Network Egress Cost*: Pembengkakan payload bulanan menelan biaya egress cloud lebih dari $85,000/bulan.
- **Arsitektur Solusi**:
  1. Diterapkan *Dual-Stack Negotiation Engine* di level Edge (Envoy Proxy + Golang Core Service).
  2. SDK internal klien (Mobile Apps versi baru dan Service-to-Service callers) diperbarui untuk menyertakan `Accept: application/x-protobuf` dan `Accept-Encoding: zstd`.
  3. Klien lama (legacy web consumers) tetap mengirim `Accept: application/json`.
  4. Penyimpanan Skema diatur tersentralisasi via Confluent/Apicurio Schema Registry dengan *Full-Compatibility Enforced* pada CI/CD.
- **Hasil Metrik Produksi**:
  - P99 Latency turun 82% (dari 280ms menjadi 12ms pada beban 250,000 RPS).
  - CPU usage pada ingress container cluster turun dari 78% menjadi 24%, memungkinkan penghematan kapasitas pod hingga 60%.
  - Total ukuran payload rata-rata terpangkas sebesar 76%, memotong tagihan network egress sebesar ~$62,000 per bulan.

---

### 9. Trade-offs: Komparasi Format & Kompresi

#### 9.1. Matriks Karakteristik Serialisasi

| Format | Parsing Speed (Throughput) | CPU Overhead | Payload Footprint | Human Readable | Skema Wajib? |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **JSON** | Rendah (~150 MB/s) | Ekstrem Tinggi (String scanning, GC churn) | Besar (Termasuk key fields) | Ya | Tidak (Opsional: JSON Schema) |
| **Protobuf** | Sangat Tinggi (~1.8 GB/s) | Rendah (Operasi bitwise & varint masks) | Sangat Ringkas (Field ID binary) | Tidak | Ya (`.proto` file) |
| **MessagePack** | Menengah (~450 MB/s) | Menengah (Binary tag + metadata dynamic) | Sedang (Lebih kecil dari JSON) | Tidak | Tidak |
| **FlatBuffers** | Tak Tertandingi (Zero-Copy) | Mendekati Nol (Akses offset langsung) | Sedang-Ringkas (Ada padding alignment) | Tidak | Ya (`fbs` schema) |

#### 9.2. Matriks Kompresi: Zstd vs Brotli vs Gzip

| Algoritma | Kecepatan Kompresi | Kecepatan Dekompresi | Rasio Kompresi | Rekomendasi Skenario Produksi |
| :--- | :--- | :--- | :--- | :--- |
| **Gzip** | Lambat | Menengah | Standar | Warisan (Legacy compatibility), sistem non-kritis. |
| **Brotli** | Sangat Lambat (High levels) | Sangat Cepat | Maksimal | Aset Statis (CDN/Front-End CSS/JS/WASM). |
| **Zstandard (zstd)** | Sangat Cepat (Level 1-3) | Sangat Cepat konstan | Unggul pada data dinamis | Dynamic RPC payloads, streaming data finansial, edge-to-core. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Umum (Anti-Patterns)
1. **Mengabaikan Header `Vary: Accept, Accept-Encoding`**: Mengakibatkan Intermediate Proxy / CDN menyajikan representasi cache Protobuf kepada klien browser biasa yang meminta JSON, merusak rendering aplikasi web.
2. **Double-Parsing di Middleware**: Menginspeksi payload biner dengan mem-parsingnya menjadi interface generic (`interface{}` atau DTO dynamic) di layer otentikasi/logging, lalu mem-parsingnya kembali di business handler. Hal ini menggandakan latensi CPU.
3. **Mengabaikan Ambang Batas (*Threshold*) Kompresi**: Mengompresi payload yang sangat kecil (< 512 bytes). Kompresi pada ukuran payload kecil justru menambah ukuran file (akibat penambahan *compression header*) dan membuang siklus CPU secara sia-sia.
4. **Alokasi Buffer `io.ReadAll`**: Membaca stream HTTP body tanpa membatasi ukuran (`io.LimitReader`) dan membiarkan *heap allocation* tumbuh tak terkendali, membuka celah eksploitasi Denial-of-Service (*OOM Crash*).

#### Panduan Troubleshooting
- **Deteksi Memory GC Pressure**: Jalankan profiling berkala:
  ```bash
  go tool pprof -alloc_space http://localhost:8080/debug/pprof/heap
  ```
  Jika `runtime.stringtoslicebyte` atau `encoding/json.Unmarshal` mendominasi grafik alokasi, alihkan traffic tersebut ke pipeline Protobuf dan aktifkan `sync.Pool`.
- **Debugging Negosiasi Gagal**:
  Simulasikan berbagai profil klien melalui perintah CLI cURL:
  ```bash
  # Uji Protobuf Negotiation
  curl -i -H "Accept: application/x-protobuf" http://localhost:8080/v1/accounts/balance

  # Uji Broken Client Negotiation (Harus mengembalikan 406 Not Acceptable)
  curl -i -H "Accept: application/xml" http://localhost:8080/v1/accounts/balance
  ```

---

### 11. Best Practices (Production Checklist)

- [ ] **Vary Header**: Wajib menyertakan `Vary: Accept, Accept-Encoding` pada setiap response dinamis.
- [ ] **Default Safe Fallback**: Konfigurasikan fallback deterministik (biasanya JSON) jika header `Accept` tidak disediakan atau menggunakan wildcard `*/*`.
- [ ] **Strict Status Codes**: Kembalikan `406 Not Acceptable` jika klien meminta representasi yang tidak didukung secara spesifik tanpa wildcard; kembalikan `415 Unsupported Media Type` jika `Content-Type` body request ditolak server.
- [ ] **Zero-Allocation Buffering**: Gunakan `sync.Pool` untuk pooling buffer serialisasi dan re-use buffer encoder.
- [ ] **Schema Backward Compatibility**: Dilarang mengubah ID field numerik pada Protobuf. Hanya tambahkan field baru sebagai opsional guna menjaga interoperabilitas lintas versi.
- [ ] **Dynamic Compression Gates**: Batasi kompresi payload hanya untuk data $\ge 1024$ bytes.
- [ ] **Security Bounds**: Pasang `http.MaxBytesReader` sebelum membaca request stream guna mencegah *Buffer Overflow* dan serangan *Decompression Bomb*.

---

### 12. Hands-on Practice

Struktur direktori kerja:
```
hands-on/m02/
├── proto/
│   └── account.proto
├── server/
│   └── main.go
├── go.mod
└── go.sum
```

#### Langkah 1: Inisialisasi Modul & Dependensi
```bash
mkdir -p hands-on/m02/proto hands-on/m02/server
cd hands-on/m02
go mod init enterprise/serialization
go get google.golang.org/protobuf@latest
go get github.com/klauspost/compress/zstd@latest
```

#### Langkah 2: Definisikan dan Kompilasi Skema Proto
Tulis file `proto/account.proto` sesuai isi Sub-seksi 7.1. Jalankan:
```bash
protoc --go_out=. --go_opt=paths=source_relative proto/account.proto
```

#### Langkah 3: Eksekusi Server
Salin kode dari Sub-seksi 7.2 ke dalam `server/main.go`. Jalankan server:
```bash
go run server/main.go
```

#### Langkah 4: Verifikasi & Benchmark Real-Time
Buka terminal terpisah dan jalankan uji komparasi berikut:

```bash
# 1. Minta JSON
curl -s -i -H "Accept: application/json" http://localhost:8080/v1/accounts/balance | grep -E "Content-Type|available_balance"

# 2. Minta Binary Protobuf (Output berupa raw binary representation)
curl -s -i -H "Accept: application/x-protobuf" http://localhost:8080/v1/accounts/balance

# 3. Uji Invalid Format
curl -s -i -H "Accept: application/xml" http://localhost:8080/v1/accounts/balance | grep "406 Not Acceptable"
```

---

### 13. Exercises

#### Level Easy
Tuliskan parser fungsi Go sederhana `ExtractPreferredEncoding(header string) string` yang menerima string `Accept-Encoding` (misalnya: `gzip;q=0.5, zstd;q=1.0, br;q=0.8`) dan secara deterministik mengembalikan encoding dengan prioritas tertinggi yang didukung server (`zstd`).

#### Level Medium
Ubah handler pada `server/main.go` agar mendukung metode **HTTP POST**:
1. Server harus menerima *inbound* request payload data transaksi baik dalam bentuk Protobuf maupun JSON berdasarkan header `Content-Type`.
2. Validasi input, perbarui balance di state memory secara thread-safe menggunakan `sync.RWMutex`.
3. Kembalikan response sesuai header `Accept` yang diminta.

#### Level Hard
Buat implementasi custom serialization middleware yang mengintegrasikan `simdjson-go` (SIMD-accelerated JSON parser) dan `Protobuf`. Jika klien meminta JSON, middleware harus mendeteksi ketersediaan instruksi AVX2/AVX-512 pada arsitektur CPU server secara runtime:
- Jika AVX2 tersedia: Gunakan jalur SIMD-accelerated serialization/deserialization.
- Jika AVX2 tidak tersedia: Fallback ke standard library tanpa memicu *panic* atau alokasi berlebih.

---

### 14. Challenge

#### Skenario: "The Zero-Downtime Wire Migration Crisis"
Anda adalah Enterprise Platform Architect di sebuah bursa pertukaran kripto/fintech. Layanan settlement inti Anda saat ini menangani transaksi sebesar $1.2B per hari melalui REST API berbasis JSON. 

Kapasitas cluster komputasi Anda di Kubernetes saat ini mencapai 92% CPU utilitas murni akibat parsing JSON berukuran 45 KB per invoice. Latensi p99 berada di angka 450ms. Rencana migrasi penuh ke gRPC ditolak karena 40% klien eksternal Anda adalah institusi legacy yang tidak dapat memperbarui core engine mereka ke gRPC/HTTP/2 dalam 12 bulan ke depan.

#### Tugas Arsitektur Anda:
1. Rancang blueprint arsitektur sistem serialisasi hibrida yang memungkinkan klien institusi baru beralih menggunakan payload binary over HTTP/1.1 atau HTTP/2 tanpa memutus satupun koneksi klien legacy.
2. Definisikan strategi mitigasi untuk menangani "Poison Payloads", yaitu jika klien salah mendeklarasikan header `Content-Type: application/x-protobuf` padahal mengirimkan payload teks JSON rusak, sehingga tidak memicu *infinite loop*, *panic*, atau *memory leakage* pada buffer pool.
3. Rancang mekanisme *Graceful Schema Evolution* 3-tahap (N-1, N, N+1) untuk payload Protobuf tersebut saat tim compliance menambahkan 5 field regulasi audit baru ke struktur invoice tanpa merusak consumer lama.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda & Konseptual)
1. Manakah status code HTTP yang paling tepat dikembalikan server jika klien mengirimkan request body berupa XML ke endpoint yang hanya menerima Protobuf dan JSON?
   - A. `400 Bad Request`
   - B. `406 Not Acceptable`
   - C. `415 Unsupported Media Type`
   - D. `501 Not Implemented`

2. Apa implikasi struktural dari nilai $q=0$ dalam header `Accept: text/html, application/xhtml+xml, application/xml;q=0.9, */*;q=0`?
   - A. Format `*/*` memiliki prioritas terendah tetapi tetap diterima.
   - B. Klien secara eksplisit menolak representasi apapun di luar yang telah didefinisikan secara spesifik.
   - C. Klien meminta representasi default dari server.
   - D. Nilai $q=0$ merupakan kesalahan sintaksis menurut RFC 9110.

3. Mengapa *zero-allocation buffer pool* (`sync.Pool`) sangat penting dalam arsitektur serialisasi throughput tinggi di Go?
   - A. Mencegah race condition antar thread secara otomatis.
   - B. Menghilangkan overhead kompilasi kode runtime.
   - C. Mengurangi beban Garbage Collector dengan mendaur ulang objek byte buffer yang sering dialokasikan di heap.
   - D. Menghindari kebutuhan penulisan data ke socket buffer kernel.

4. Apa peran header HTTP `Vary: Accept` pada arsitektur sistem terdistribusi?
   - A. Memaksa server memvalidasi schema request ke central registry.
   - B. Memberi tahu caching proxy (e.g., CDN) bahwa response yang disimpan terikat secara unik dengan nilai header `Accept` dari request.
   - C. Menginstruksikan client untuk mengganti protokol TCP ke UDP.
   - D. Mengubah format enkripsi TLS secara dinamis.

5. Manakah karakteristik kompresi Zstandard (zstd) yang membuatnya lebih superior dibanding Gzip untuk microservice payloads?
   - A. Menggunakan kamus statis yang tidak membutuhkan memori RAM.
   - B. Memiliki decompression speed yang konstan dan tinggi hampir di semua compression ratio levels.
   - C. Merupakan algoritma kompresi eksklusif untuk data berformat gambar dan media.
   - D. Tidak membutuhkan CPU cycle saat dijalankan di lingkungan Linux.

#### Bagian 2: Intermediate (Analisis Arsitektur)
6. Jelaskan bagaimana mekanisme Varint encoding pada Protocol Buffers merepresentasikan angka integer kecil (misal: int32 bernilai 1) dibandingkan representasi fixed integer standar 4-byte!
7. Dalam kondisi beban kerja sistem seperti apa penggunaan kompresi response HTTP justru menurunkan performa throughput server secara keseluruhan?
8. Mengapa manipulasi struct field index (tag numbers) pada skema Protobuf yang sedang berjalan di produksi dapat merusak integritas data (*data corruption*) secara silent?
9. Apa perbedaan mendasar antara *Zero-Copy Deserialization* pada FlatBuffers dibanding deserialisasi standar pada Google Protocol Buffers v3?
10. Bagaimana Anda mendesain skema fallback pada Content Negotiation jika klien mengirimkan header `Accept: */*`?

#### Bagian 3: Skenario Kasus Produksi
11. **Skenario 1**: Layanan API Gateway Anda mendadak mengalami lonjakan alokasi memori hingga memicu OOM (Out Of Memory) killer setelah tim menambahkan logging middleware yang membaca `r.Body` menggunakan `io.ReadAll(r.Body)` sebelum handler deserialisasi Protobuf berjalan. Analisis akar masalah internal Go runtimenya dan berikan arsitektur solusinya!
12. **Skenario 2**: Dua microservice berkomunikasi melalui HTTP/2 dengan pertukaran format data Protobuf. Microservice Producer memperbarui field `int32 sequence = 4;` menjadi `int64 sequence = 4;`. Apa yang terjadi pada level wire protocol saat Consumer lama membaca data tersebut? Apakah binary stream tersebut crash atau corrupt?
13. **Skenario 3**: Sebuah reverse proxy edge (CDN) mengabaikan header `Vary: Accept` dari response backend Anda. Uraikan konsekuensi teknis langsung terhadap end-user dan bagaimana langkah mitigasi arsitektur sementara dari sisi backend application layer!

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Bagian 1: Basic
1. **C** (`415 Unsupported Media Type`). `Content-Type` pada request payload yang tidak didukung memicu 415. Sebaliknya, jika `Accept` yang tidak dapat dipenuhi, server merespons dengan `406 Not Acceptable`.
2. **B**. Mengacu pada RFC 9110, nilai $q=0$ merepresentasikan bahwa media range tersebut "not acceptable" bagi klien.
3. **C**. Di Go, alokasi memori berulang untuk `[]byte` berukuran besar saat serialisasi/deserialisasi akan memicu fragmentasi heap dan memaksa GC berjalan lebih sering (*GC STW pauses*). `sync.Pool` mendaur ulang slice ini.
4. **B**. Header `Vary` memastikan cache key di level proxy/CDN menyertakan variasi header terkait, mencegah penyajian konten binary Protobuf kepada browser yang meminta JSON.
5. **B**. Zstandard dirancang secara spesifik untuk memiliki kecepatan dekompresi super cepat yang independen terhadap rasio kompresi, sangat ideal untuk backend inter-service communication.

#### Bagian 2: Intermediate
6. **Varint Encoding**: Menggunakan bit paling signifikan (*Most Significant Bit / MSB*) dari setiap byte sebagai penanda apakah byte berikutnya masih merupakan bagian dari integer yang sama. Integer `1` hanya membutuhkan 1 byte (`00000001`), sedangkan fixed int32 memakan 4 byte (`00000000 00000000 00000000 00000001`). Ini menghemat 75% bandwidth wire untuk angka kecil.
7. **Kondisi Kompresi Kontraproduktif**: Saat ukuran payload di bawah 1 KB (overhead kompresi header melebihi penghematan data) dan ketika utilisasi CPU server sudah mencapai batas kritis (>85%). Pada kondisi ini, siklus CPU terbuang untuk kompresi alih-alih melayani request baru, sementara penghematan transfer jaringan tidak signifikan.
8. **Protobuf Field Tag Numbers**: Wire format Protobuf tidak menyimpan nama field, melainkan nomor tag (`field_number << 3 | wire_type`). Mengubah tag number 2 menjadi 3 akan membuat parser membaca data baru ke field yang salah atau memperlakukannya sebagai *unknown field*, mengakibatkan hilangnya data (*silent data corruption*) tanpa memicu error parsing.
9. **Zero-Copy FlatBuffers**: FlatBuffers menyusun struktur data pada wire memory layout secara berurutan sesuai word alignment CPU. Deserialisasi hanyalah *type-casting pointer* langsung ke buffer RAM, tanpa traversing atau alokasi heap baru. Protobuf masih harus membaca varint, mengalokasikan struct di heap, dan menyalin data field-by-field.
10. **Fallback `*/*`**: Server harus memiliki *preference list* internal yang terurut (misal: JSON sebagai prioritas universal atau Protobuf jika targetnya purely backend). Jika `*/*` diterima, ambil format paling efisien yang didukung oleh ekosistem klien umum tanpa mengembalikan error.

#### Bagian 3: Skenario Kasus Produksi
11. **Analisis Skenario 1**:
    - *Akar Masalah*: `io.ReadAll` membaca seluruh payload dari TCP socket ke buffer memori dinamis yang menggandakan ukurannya (*slice growth amortized allocation*) di heap, dan mengonsumsi stream socket body sehingga pointer reader bergeser ke EOF. Middleware kemudian membuat copy byte baru untuk logging.
    - *Solusi*: Terapkan `io.LimitReader` untuk membatasi ukuran maksimum yang boleh dibaca. Gunakan buffer pool untuk logging atau gunakan `teeReader` yang langsung dialirkan ke parser tanpa menahan alokasi ganda di memory heap.
12. **Analisis Skenario 2**:
    - *Wire Level Impact*: Wire type untuk `int32` dan `int64` adalah sama, yaitu `WireType = 0 (Varint)`. Di wire, data dikirim sebagai byte varint yang identik. Consumer lama dengan tipe field `int32` akan tetap sukses mendeserialisasi data dari producer `int64`, **selama** nilai integer tersebut tidak melebihi kapasitas $2^{31}-1$. Jika nilainya meluap (*overflow*), parser consumer akan memotong bit integer tersebut atau mengalami truncation error tergantung runtime, namun tidak akan menyebabkan structural parsing crash.
13. **Analisis Skenario 3**:
    - *Dampak*: Kerusakan tampilan/fungsional fatal. Browser web yang meminta JSON dapat menerima raw binary Protobuf yang tersimpan di CDN cache dari request klien lain sebelumnya, menghasilkan blank screen atau error parsing script di frontend.
    - *Mitigasi Backend*: Pisahkan URI path endpoint secara eksplisit jika CDN tidak RFC-compliant terhadap `Vary` header (misal: `/v1/accounts/balance` default ke JSON, dan `/v1/accounts/balance.pb` atau `/v1/pb/accounts/balance` khusus biner Protobuf), atau paksa header `Cache-Control: private, no-cache` untuk representasi biner agar CDN tidak menyimpannya di shared edge cache.

---

### 16. Summary
1. **Serialisasi adalah Penentu Latensi**: Pada sistem skala masif, CPU overhead parsing JSON berbasis string merupakan salah satu penghambat utama throughput sistem. Mengadopsi format biner (seperti Protobuf) memangkas latensi p99 dan beban alokasi memori secara signifikan.
2. **Kepatuhan RFC 9110**: Content negotiation modern harus mematuhi standardisasi bobot $q$-factor secara deterministik, melindungi intermediate caching melalui `Vary: Accept, Accept-Encoding`, dan menangani invalid states via kode status `406 Not Acceptable` atau `415 Unsupported Media Type`.
3. **Optimasi Alokasi Memori**: Penggunaan `sync.Pool` untuk buffer serialisasi dan dynamic compression gate ($\ge 1024$ bytes) adalah prasyarat mutlak arsitektur performa tinggi guna mencegah *GC pauses* dan kompresi kontraproduktif.
4. **Strategi Migrasi Hibrida**: Arsitektur enterprise tidak memaksakan *breaking change*. Mengimplementasikan endpoint tunggal yang melayani JSON sekaligus Protobuf secara adaptif memungkinkan evolusi sistem secara zero-downtime, aman, dan kompatibel lintas generasi platform.