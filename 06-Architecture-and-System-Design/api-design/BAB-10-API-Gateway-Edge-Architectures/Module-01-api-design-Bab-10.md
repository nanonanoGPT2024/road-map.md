## SEKSI 01 — IDENTITAS MODUL

* **Jalur Kurikulum:** API Design & Engineering
* **Kategori:** 06-Architecture-and-System-Design
* **Nomor Modul:** Bab 10 — Modul 01
* **Judul Modul:** API Gateway Topologies & Edge Architectures: API Gateway vs Service Mesh vs Ingress Controller, Edge Caching, Cache-Control Invalidation, Envoy Proxy & Federation
* **Tingkat Kesulitan:** Advanced / Senior Technical Architect
* **Prasyarat:** Pemahaman mendalam tentang HTTP/1.1, HTTP/2, gRPC, dasar-dasar Kubernetes networking (Services, Pods, ClusterIP), TLS termination, dan arsitektur microservices.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta diharapkan mampu:

1. **Membedakan dan Mengintegrasikan Komponen Jaringan Edge:** Menjelaskan perbedaan fungsional, posisi topologi, dan batas tanggung jawab antara *API Gateway*, *Service Mesh*, dan *Kubernetes Ingress Controller* dalam arsitektur terdistribusi skala besar.
2. **Merancang Topologi Lalu Lintas North-South dan East-West:** Mengimplementasikan pola pemisahan lalu lintas eksternal (klien publik) dan internal (komunikasi antar-layanan) menggunakan perutean berbasis L7 (*Layer 7*).
3. **Mengonfigurasi Mesin Proxy Modern Berbasis Envoy:** Menulis dan mendebug konfigurasi *Envoy Proxy* (Listener, Route, Cluster, Filter Chaining) untuk penanganan pemutusan TLS, rate limiting, dan *header transformation*.
4. **Membangun Strategi Edge Caching dan Cache Invalidation:** Mengimplementasikan kontrol cache L7 tingkat lanjut menggunakan HTTP response headers (`Cache-Control`, `Surrogate-Control`, `stale-while-revalidate`) serta mekanisme invalidasi presisi berbasis *Surrogate-Keys / Cache-Tags*.
5. **Mengarsiteksikan Gateway Federation:** Mendesain topologi gateway multi-wilayah (*multi-region*) atau terfederasi (termasuk skenario *GraphQL Federation* atau *Multi-cluster Envoy Control Plane*) guna meminimalkan latensi dan menghilangkan *single point of failure* (SPOF).

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                       [ Public Client Traffic (Internet) ]
                                       │
                                       ▼
                       ┌───────────────────────────────┐
                       │      Anycast Edge / CDN       │
                       │   (DDoS Shield, Edge Cache)   │
                       └───────────────┬───────────────┘
                                       │
                         North-South   │ (HTTP/2, HTTP/3, TLS Termination)
                           Traffic     ▼
                       ┌───────────────────────────────┐
                       │     Edge Ingress Controller   │ (Layer 4/Layer 7 Routing
                       │       (Envoy-based Ingress)   │  to Cluster Namespaces)
                       └───────────────┬───────────────┘
                                       │
                                       ▼
                       ┌───────────────────────────────┐
                       │       API Gateway Layer       │ (AuthN/AuthZ, Global Rate Limit,
                       │   (BFF / Federated Schema)    │  Request Mutation, Observability)
                       └───────────────┬───────────────┘
                                       │
  ═════════════════════════════════════╪══════════════════════════════════════════════
  KUBERNETES SERVICE MESH BOUNDARY     │ East-West Traffic (mTLS, Retries, Circuit Break)
                                       ▼
         ┌──────────────────────────────────────────────────────────┐
         │  Pod: Service A                 Pod: Service B           │
         │ ┌───────────────┐              ┌───────────────┐         │
         │ │ Envoy Sidecar │◄────────────►│ Envoy Sidecar │         │
         │ └───────┬───────┘    mTLS      └───────┬───────┘         │
         │         │ UDS/Localhost                │ UDS/Localhost   │
         │         ▼                              ▼                 │
         │ ┌───────────────┐              ┌───────────────┐         │
         │ │ App Service A │              │ App Service B │         │
         │ └───────────────┘              └───────────────┘         │
         └──────────────────────────────────────────────────────────┘
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Ketika sistem monolitik bertransformasi menjadi ratusan microservices di berbagai kluster dan region, lapisan *edge* (perbatasan jaringan) menjadi komponen paling kritis penentu keandalan, keamanan, dan latensi sistem. 

Banyak organisasi melakukan kegagalan arsitektur dengan memaksakan satu alat untuk menyelesaikan semua masalah jaringan. Misalnya: menggunakan Ingress Controller dasar untuk menangani token minting/OAuth2 validation kompleks, atau menempatkan logika bisnis API pada Service Mesh sidecar. Kesalahan ini menyebabkan degradasi latensi (*tail latency* meledak), ketidakmampuan melakukan invalidasi cache edge secara granular, dan kerapuhan konfigurasi (*blast radius* tak terkendali).

Memahami topologi perbatasan jaringan memungkinkan tim engineering:
* Menentukan garis demarkasi yang tegas antara keamanan eksternal vs. komunikasi internal.
* Mengurangi beban beban kerja komputasi inti (*backend origin*) hingga 80-90% menggunakan *smart edge caching*.
* Mengisolasi kegagalan jaringan internal agar tidak terekspos langsung ke pengguna akhir.
* Membangun skalabilitas horizontal independen untuk tim API Product tanpa mengganggu konfigurasi infrastruktur Kubernetes dasar.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Taksonomi Komponen Jaringan

| Dimensi | API Gateway | Ingress Controller | Service Mesh |
| :--- | :--- | :--- | :--- |
| **Fokus Utama** | Manajemen API bisnis, Developer Experience, Keamanan Aplikasi | Entry point L7 ke kluster Kubernetes | Komunikasi andal, aman, dan terobservasi antar-layanan internal |
| **Arah Lalu Lintas** | North-South (Klien luar $\to$ Layanan) | North-South (Jaringan luar kluster $\to$ Jaringan dalam kluster) | East-West (Layanan internal $\to$ Layanan internal) |
| **Fitur Khas** | Transformasi Payload, Validasi API Key/JWT, Per-client Quota, Monetisasi API | DNS routing, Path-based routing, Basic TLS Termination | Mutual TLS (mTLS) otomatis, L7 Distributed Tracing, Circuit Breaking, Fault Injection |
| **Implementasi Populer** | Kong, Apache APISIX, Tyk, Envoy Custom Gateway | Traefik, Ingress-Nginx, Emissary-ingress, AWS ALB Controller | Istio, Linkerd, Consul Connect |
| **Lokasi Operasi** | Edge / DMZ / Application Layer | Edge Boundary Kluster Kubernetes | Co-located pada tiap Pod sebagai Sidecar proxy atau Node-level Proxy |

### 2. Edge Caching & Cache Invalidation L7

Edge Caching adalah mekanisme penyimpanan respons HTTP sedekat mungkin dengan klien (biasanya pada titik PoP/Point of Presence CDN atau Reverse Proxy tingkat terluar).

* **`Cache-Control`**: Header standar HTTP/1.1 (RFC 7234 & RFC 9111) yang menginstruksikan peramban (*browser*) dan proksi perantara mengenai durasi dan kemampuan respons disimpan.
* **`Surrogate-Control`**: Header khusus yang ditujukan hanya untuk proksi perantara / CDN (Surrogate), diabaikan oleh browser pengguna. Ini memungkinkan konfigurasi TTL (*Time-to-Live*) yang lebih lama di edge, sementara browser mendapatkan instruksi `no-cache`.
* **Invalidasi Presisi (Surrogate-Keys / Cache-Tags)**: Mekanisme pelabelan respons dengan metadata tag relasional. Ketika data pada database berubah, origin server mengirim sinyal `PURGE` dengan target tag tertentu, menghapus ribuan entri cache terkait secara instan tanpa melakukan flushing massal yang berisiko membuat backend tumbang (*cache stampede*).

### 3. Envoy Proxy & Control Plane

Envoy adalah open-source L7 edge and service proxy berkinerja tinggi yang ditulis dalam C++. Envoy mengabstraksikan jaringan menggunakan arsitektur dynamic data plane yang dikendalikan melalui API streaming gRPC yang disebut **xDS**:
* **LDS (Listener Discovery Service):** Menentukan port dan protokol masuk.
* **RDS (Route Discovery Service):** Menentukan pemetaan path HTTP ke virtual cluster backend.
* **CDS (Cluster Discovery Service):** Menentukan grup host/pod tujuan.
* **EDS (Endpoint Discovery Service):** Resolusi alamat IP pods dinamis secara real-time.

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

### Alur Eksekusi Paket Jaringan (End-to-End Request Flow)

1. **DNS & Edge Entry Point:** Klien mengeksekusi request HTTPS ke `api.enterprise.com`. Anycast DNS merutekan paket ke Edge CDN PoP terdekat.
2. **Evaluasi Cache Edge (CDN):** 
   * CDN memeriksa URL dan header request terhadap cache index internal.
   * Jika *Cache Hit* dan belum stale: Respons langsung dikembalikan ke klien (0ms origin latency).
   * Jika *Cache Miss* atau *Stale*: Request diteruskan (*cache miss forwarding*) ke upstream Ingress IP.
3. **Ingress Controller (L4/L7 Ingress Envoy):**
   * Menyelesaikan handshake TLS publik menggunakan sertifikat wildcard/SNI.
   * Memeriksa VirtualHost dan path. Meneruskan request dari layer infrastruktur ke Pod API Gateway.
4. **API Gateway (North-South Processing):**
   * **Authentication Filter:** Melakukan verifikasi kriptografis JWT atau introspeksi token OAuth2.
   * **Rate Limiting Engine:** Menghubungi shared memory/Redis untuk mengevaluasi sliding-window rate limit klien berdasarkan `client_id`.
   * **Header Transformation:** Menambahkan metadata konteks user (`X-User-Id`, `X-User-Roles`) dan menghapus Authorization header sensitif.
   * **Routing Resolution:** Mengarahkan rute logis ke virtual cluster Service Mesh internal.
5. **Service Mesh (East-West Sidecar Interception):**
   * Request meninggalkan Pod API Gateway, dicegat oleh sidecar proxy Envoy lokal via IPTables rule (PREROUTING/OUTPUT).
   * Envoy lokal menginisiasi koneksi **mTLS** dengan memverifikasi identitas kriptografis (SPIFFE/SPIRE ID) pada sertifikat X.509 milik Envoy Pod target.
   * Sidecar Pod target mendekripsi paket, mengevaluasi kebijakan L7 authorization (RBAC), lalu meneruskannya via `localhost` (loopback) ke port container aplikasi.
6. **Backend Processing & Cache Header Generation:**
   * Aplikasi mengeksekusi logika bisnis dan mengembalikan payload JSON disertai header kontrol cache:
     ```http
     HTTP/1.1 200 OK
     Content-Type: application/json
     Cache-Control: public, max-age=0, must-revalidate
     Surrogate-Control: max-age=86400, stale-while-revalidate=300
     Surrogate-Key: product-1029 category-electronics vendor-88
     ```
7. **Cache Storage di Edge:**
   * Saat respons melintasi balik melalui API Gateway dan CDN, CDN membaca `Surrogate-Control`, mengasosiasikan payload dengan `Surrogate-Key`, mencatat entri cache lokal selama 86400 detik, menghapus header `Surrogate-Control` agar tidak bocor ke publik, lalu meneruskan sisa respons ke klien.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

```
CLIENT              CDN EDGE             INGRESS ENVOY          API GATEWAY            SVC-A (POD)           SVC-B (POD)
  │                    │                       │                     │                      │                      │
  │──GET /products/10─►│                       │                     │                      │                      │
  │   [Query Init]     │                       │                     │                      │                      │
  │                    ├──Cache Lookup (Miss)─┐│                     │                      │                      │
  │                    │◄─────────────────────┘│                     │                      │                      │
  │                    │──Forward Upstream────►│                     │                      │                      │
  │                    │  [SNI: api.ent.com]   │                     │                      │                      │
  │                    │                       ├──TLS Termination───┐│                      │                      │
  │                    │                       │◄───────────────────┘│                      │                      │
  │                    │                       │──L7 Route to GW────►│                      │                      │
  │                    │                       │  (Cleartext/mTLS)   │                      │                      │
  │                    │                       │                     ├──Verify JWT Token───┐│                      │
  │                    │                       │                     │◄────────────────────┘│                      │
  │                    │                       │                     ├──RateLimit Check────┐│                      │
  │                    │                       │                     │◄────────────────────┘│                      │
  │                    │                       │                     │──Mutate (Add X-UID)─►│ [Sidecar Envoy]      │
  │                    │                       │                     │                      │──mTLS Handshake─────►│ [Sidecar Envoy]
  │                    │                       │                     │                      │  (SPIFFE Validated)  │──Localhost──►[App]
  │                    │                       │                     │                      │                      │              │
  │                    │                       │                     │                      │                      │◄──JSON Payld─┘
  │                    │                       │                     │                      │◄─Encrypted mTLS Resp─│
  │                    │                       │                     │◄──Internal Response──│
  │                    │                       │◄──Gateway Resp──────│   (Cache Headers)    
  │                    │◄──Return Response─────│
  │                    │   Surrogate-Key: prod-10
  │                    ├──Commit to Edge Store─┐
  │                    │◄──────────────────────┘
  │◄──200 OK Response──│
  │   Cache-Control: public, max-age=0, must-revalidate
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah skenario sederhana konfigurasi deklaratif **Envoy Proxy L7** (`envoy.yaml`) mandiri yang bertindak sebagai Edge Reverse Proxy dengan penanganan header dan routing path.

```yaml
static_resources:
  listeners:
  - name: external_edge_listener
    address:
      socket_address:
        address: 0.0.0.0
        port_value: 8080
    filter_chains:
    - filters:
      - name: envoy.filters.network.http_connection_manager
        typed_config:
          "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
          stat_prefix: ingress_http
          codec_type: AUTO
          route_config:
            name: local_route
            virtual_hosts:
            - name: api_service
              domains: ["api.example.com"]
              routes:
              - match:
                  prefix: "/v1/users"
                route:
                  cluster: user_backend_cluster
                  timeout: 3s
                request_headers_to_add:
                  - header:
                      key: "X-Forwarded-Gateway"
                      value: "Edge-Core-01"
                    append_action: OVERWRITE_IF_EXISTS_OR_ADD
          http_filters:
          - name: envoy.filters.http.router
            typed_config:
              "@type": type.googleapis.com/envoy.extensions.filters.http.router.v3.Router

  clusters:
  - name: user_backend_cluster
    connect_timeout: 0.25s
    type: STRICT_DNS
    lb_policy: ROUND_ROBIN
    load_assignment:
      cluster_name: user_backend_cluster
      endpoints:
      - lb_endpoints:
        - endpoint:
            address:
              socket_address:
                address: 127.0.0.1
                port_value: 9001
```

**Penjelasan:**
* **`listener`**: Menerima koneksi HTTP inbound pada port `8080`.
* **`HttpConnectionManager`**: Abstraksi L7 pemrosesan protokol HTTP/1.1 dan HTTP/2.
* **`route_config`**: Memeriksa header HTTP `Host` / `:authority` (`api.example.com`) dan prefix URI (`/v1/users`).
* **`request_headers_to_add`**: Menuntaskan mutasi dasar data sebelum diteruskan ke cluster tujuan.
* **`clusters`**: Mendefinisikan backend upstream pool (`user_backend_cluster`) menggunakan round-robin load balancing ke port lokal `9001`.

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Kasus Produksi: Arsitektur e-Commerce Skala Tinggi yang mengimplementasikan **Granular Cache Invalidation (Surrogate Keys)** pada Golang Origin Backend, terintegrasi dengan Edge Gateway.

### 1. Implementasi Backend HTTP Service (Golang)

Backend menyematkan metadata caching yang sangat spesifik untuk CDN/Edge API Gateway:

```go
package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"time"
)

type Product struct {
	ID         string    `json:"id"`
	Name       string    `json:"name"`
	Price      float64   `json:"price"`
	CategoryID string    `json:"category_id"`
	MerchantID string    `json:"merchant_id"`
	UpdatedAt  time.Time `json:"updated_at"`
}

func ProductDetailHandler(w http.ResponseWriter, r *http.Request) {
	productID := r.URL.Query().Get("id")
	if productID == "" {
		http.Error(w, `{"error":"missing id parameter"}`, http.StatusBadRequest)
		return
	}

	// Simulasi pemanggilan database/repository
	prod := Product{
		ID:         productID,
		Name:       "Mechanical Keyboard RGB",
		Price:      149.99,
		CategoryID: "cat-electronics-99",
		MerchantID: "merch-tokotekno-01",
		UpdatedAt:  time.Now().UTC(),
	}

	// KONTROL CACHE EDGE:
	// Browser: max-age=0, must-revalidate (klien browser selalu validasi ke edge)
	w.Header().Set("Cache-Control", "public, max-age=0, must-revalidate")
	
	// CDN Edge (Fastly/Cloudflare/Envoy Edge Cache):
	// Simpan data 24 jam (86400s), layani stale data hingga 60s saat origin down/fetch ulang
	w.Header().Set("Surrogate-Control", "max-age=86400, stale-while-revalidate=60")

	// Surrogate Keys (Cache Tags): Menyematkan relasi dependensi entitas
	surrogateKeys := fmt.Sprintf("product-%s category-%s merchant-%s", prod.ID, prod.CategoryID, prod.MerchantID)
	w.Header().Set("Surrogate-Key", surrogateKeys)

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(prod)
}

func main() {
	http.HandleFunc("/api/v1/product", ProductDetailHandler)
	_ = http.ListenAndServe(":9001", nil)
}
```

### 2. Mekanisme Invalidasi Cache Instan via Invalidation Worker

Ketika harga produk diperbarui, service tidak menghapus cache per URL (karena produk bisa muncul di halaman detail, search, atau rekomendasi). Service memicu purging berdasarkan **Surrogate-Key**:

```go
package main

import (
	"bytes"
	"context"
	"fmt"
	"net/http"
	"time"
)

type CachePurger struct {
	EdgeGatewayURL string
	AdminToken     string
	HTTPClient     *http.Client
}

func NewCachePurger(edgeURL, token string) *CachePurger {
	return &CachePurger{
		EdgeGatewayURL: edgeURL,
		AdminToken:     token,
		HTTPClient:     &http.Client{Timeout: 5 * time.Second},
	}
}

// InvalidateBySurrogateKey menembak API control plane Edge untuk flush instan
func (p *CachePurger) InvalidateBySurrogateKey(ctx context.Context, tag string) error {
	reqURL := fmt.Sprintf("%s/api/v1/cache/purge-tag", p.EdgeGatewayURL)
	
	payload := []byte(fmt.Sprintf(`{"tag":"%s"}`, tag))
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, reqURL, bytes.NewBuffer(payload))
	if err != nil {
		return fmt.Errorf("failed to create purge request: %w", err)
	}

	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", p.AdminToken))
	req.Header.Set("Content-Type", "application/json")

	resp, err := p.HTTPClient.Do(req)
	if err != nil {
		return fmt.Errorf("purge network execution failure: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusAccepted {
		return fmt.Errorf("purge failed with edge status code: %d", resp.StatusCode)
	}

	return nil
}

// Simulasi eksekusi saat Admin merchant mengubah harga produk:
func OnProductPriceUpdated(productID string) {
	purger := NewCachePurger("http://edge-ingress.internal:8001", "edge-secret-purge-token")
	
	// Tag yang dihapus: Hanya produk terkait!
	tagTarget := fmt.Sprintf("product-%s", productID)
	
	err := purger.InvalidateBySurrogateKey(context.Background(), tagTarget)
	if err != nil {
		// Fallback ke asynchronous retry queue (Kafka/RabbitMQ)
		fmt.Printf("[CRITICAL ERROR] Failed to purge edge cache: %v\n", err)
		return
	}
	fmt.Printf("[SUCCESS] Edge cache successfully purged for key: %s\n", tagTarget)
}
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Keputusan Arsitektur | Keuntungan | Kerugian & Konsekuensi |
| :--- | :--- | :--- |
| **All-in-One Gateway** (API Gateway menangani Auth, Ingress, Routing, dan Mesh) | Biaya setup awal rendah, manajemen konfigurasi terpusat tunggal. | Kopling tinggi, rawan kegagalan masif (*blast radius* tak terbatas), menjadi *chokepoint* komputasi saat traffic masif. |
| **Pemisahan Tegas 3-Layer** (Ingress $\to$ API Gateway $\to$ Service Mesh) | Tanggung jawab jelas: Platform engineer mengelola Ingress, Tim API mengelola Gateway, App engineer mengelola Service Mesh. Isolasi performa optimal. | Kompleksitas operasional sangat tinggi, meningkatkan latensi jaringan dasar (*multi-hop network penalty*, ~1-3ms tambahan per hop). |
| **Aggressive Edge Caching** (`Cache-Control` + Surrogate Keys) | Mengurangi utilisasi CPU & DB backend hingga 90%+, response time sub-millisecond bagi end-user. | Resiko *data inconsistency* (*stale reads*), kompleksitas pengujian (*cache-busting debugging*), kebutuhan sistem webhook purge yang andal. |
| **Client-side vs Gateway Federation** (GraphQL Federation / Aggregator) | Menggabungkan multiple microservices ke dalam satu endpoint terpadu tanpa exposing internal schema. | Gateway menjadi CPU-bound (komputasi deserialisasi & parsing query kompleks), debugging distributed graph trace menjadi rumit. |

---

## SEKSI 11 — BEST PRACTICES

1. **Gunakan Header `Surrogate-Control` untuk Edge, `Cache-Control` untuk Browser:** Jangan pernah membiarkan browser publik menyimpan data dinamis terlalu lama. Kirim `Cache-Control: private, no-cache, no-store` atau `max-age=0` ke browser, namun pasang `Surrogate-Control: max-age=3600` untuk Edge CDN.
2. **Implementasikan `stale-while-revalidate`:** Hindari efek *thundering herd* ketika cache kedaluwarsa. Dengan direktif ini, proksi edge dapat memberikan data kadaluwarsa kepada pembaca baru sementara secara asinkron mengambil data segar dari origin.
3. **Pemisahan Namespace Jaringan (Security Boundaries):** Jangan biarkan API Gateway mengekspos port database atau interface admin service internal. API Gateway hanya boleh berkomunikasi dengan interface internal yang telah diproteksi via Service Mesh mTLS.
4. **Desentralisasi Definisi Rute (GitOps Integration):** Hindari file konfigurasi gateway raksasa (*monolithic yaml*). Terapkan pola *Federated Route CRD* (misalnya menggunakan Kubernetes Gateway API: `HTTPRoute`) sehingga masing-masing tim layanan mikro memiliki kepemilikan independen atas routing mereka.
5. **Fail-Closed pada Edge Purging Failure:** Jika sistem event bus invalidasi cache gagal mengirim sinyal PURGE, sediakan mekanisme *hard TTL safety limit* maksimum (misal: TTL absolut tidak boleh melebihi 1 jam terlepas dari strategi invalidasi).

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1. **Mencampuradukkan Logika Bisnis Domain ke dalam API Gateway:**
   * *Anti-pattern:* Menulis ribuan baris kode Lua / JavaScript di dalam Gateway untuk parsing data database, validasi format nomor KTP, atau komputasi diskon.
   * *Solusi:* API Gateway hanya bertindak sebagai orkestrator L7 murni (Autentikasi token, TLS, Routing, Circuit Breaking). Letakkan logika bisnis di layanan hilir (*downstream services*).
2. **Ketiadaan Perlindungan Cache Stampede (Dogpiling):**
   * *Anti-pattern:* Membiarkan 10.000 concurrent request secara serentak memicu origin request ketika sebuah item viral habis masa cache-nya.
   * *Solusi:* Aktifkan fitur *Origin Request Collapsing* / *Cache Lock* di Envoy atau CDN, di mana hanya 1 request yang diteruskan ke origin, sementara 9.999 request lainnya menunggu hingga cache baru terisi.
3. **Menjalankan Service Mesh Menggantikan API Gateway:**
   * *Anti-pattern:* Berasumsi bahwa memasang Istio sudah otomatis menggantikan fungsi Kong atau Apisix.
   * *Solusi:* Sadari bahwa Service Mesh tidak didesain untuk menangani klien eksternal publik yang tidak tepercaya (kurang memiliki fitur self-service developer portal, billing metrics, integrasi OAuth2 fine-grained, dynamic request throttling per API-key).
4. **Mengabaikan Header `Vary`:**
   * *Anti-pattern:* Melakukan caching pada endpoint yang menghasilkan representasi berbeda berdasarkan header `Accept-Encoding`, `Origin`, atau `Authorization` tanpa menyertakan `Vary: Accept-Encoding, Origin`. Akibatnya, klien non-Gzip menerima payload Gzip terkompresi rusak, atau terjadi insiden kebocoran data antar-user.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Skenario Latihan
Anda diminta mendesain dan mengonfigurasi routing layer Envoy untuk merutekan lalu lintas berdasarkan header inspeksi versi dan memproteksi backend dengan Circuit Breaker.

### Tugas:
1. Buat file konfigurasi `envoy-lab.yaml` yang membuka HTTP Listener pada port `10000`.
2. Konfigurasikan dua Upstream Clusters:
   * `service_v1` menunjuk ke `127.0.0.1:8081`
   * `service_v2` menunjuk ke `127.0.0.1:8082`
3. Terapkan aturan routing:
   * Jika request memiliki Header `X-API-Version: v2`, rutekan ke `service_v2`.
   * Jika header tidak ada atau nilainya lain, lakukan default routing ke `service_v1`.
4. Pasang konfigurasi Circuit Breaker pada `service_v1` dengan batasan:
   * `max_connections`: 100
   * `max_pending_requests`: 50
   * `max_requests`: 200

### Panduan Solusi Verifikasi (Snippet YAML):
```yaml
# Tambahkan bagian routes di bawah virtual_hosts:
routes:
- match:
    prefix: "/"
    headers:
      - name: "X-API-Version"
        exact_match: "v2"
  route:
    cluster: service_v2
- match:
    prefix: "/"
  route:
    cluster: service_v1

# Tambahkan bagian circuit_breakers di cluster service_v1:
clusters:
- name: service_v1
  connect_timeout: 0.5s
  type: STATIC
  lb_policy: ROUND_ROBIN
  circuit_breakers:
    thresholds:
      - priority: DEFAULT
        max_connections: 100
        max_pending_requests: 50
        max_requests: 200
  load_assignment:
    cluster_name: service_v1
    endpoints:
    - lb_endpoints:
      - endpoint:
          address:
            socket_address:
              address: 127.0.0.1
              port_value: 8081
```

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

Jawab pertanyaan berikut untuk mengevaluasi pemahaman arsitektur Anda:

1. **Apa perbedaan mendasar antara lalu lintas North-South dan East-West dalam konteks API architecture?**
   * *Jawaban:* North-South adalah lalu lintas yang masuk dari luar sistem/klien publik menuju perimeter infrastruktur internal (klien ke server). East-West adalah komunikasi antar-layanan komputasi internal di dalam perimeter aman (antar microservice atau pod ke pod).

2. **Mengapa header `Cache-Control: no-cache` tidak berarti "jangan pernah simpan data ini di penyimpanan"?**
   * *Jawaban:* Secara spesifikasi RFC 9111, `no-cache` menginstruksikan cache engine bahwa entri respons *dapat* disimpan, namun *wajib* divalidasi ulang (*revalidated*) ke origin server menggunakan conditional requests (`ETag` atau `If-Modified-Since`) sebelum disajikan ke klien. Direktif yang melarang penyimpanan sama sekali adalah `no-store`.

3. **Komponen discovery manakah dalam Envoy xDS API yang bertugas mengambil daftar IP dinamis dari Pods backend secara real-time?**
   * *Jawaban:* Endpoint Discovery Service (EDS).

4. **Bagaimana mekanisme `Surrogate-Key` mencegah masalah thundering herd pasca-invalidasi?**
   * *Jawaban:* `Surrogate-Key` memungkinkan invalidasi granular per objek tanpa menghapus seluruh cache. Ketika dikombinasikan dengan direktif `stale-while-revalidate`, saat sebuah key diinvalidsi, sistem dapat menyajikan versi stale ke request pertama yang datang bersamaan sambil me-lock satu background fetch ke backend origin, menjaga kestabilan load server.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **RFC Spesifikasi Inti:**
  * [RFC 9111: HTTP Caching](https://www.rfc-editor.org/rfc/rfc9111.html)
  * [RFC 7234: Hypertext Transfer Protocol (HTTP/1.1): Caching](https://tools.ietf.org/html/rfc7234)
* **Dokumentasi Resmi Engine:**
  * [Envoy Proxy Architecture & Concepts Documentation](https://www.envoyproxy.io/docs/envoy/latest/intro/arch_overview/arch_overview)
  * [Kubernetes Gateway API Specifications](https://gateway-api.sigs.k8s.io/)
* **Buku Referensi:**
  * *"Designing Data-Intensive Applications"* oleh Martin Kleppmann (O'Reilly Media).
  * *"Cloud Native Patterns: Designing infrastructure and applications"* oleh Cornelia Davis (Manning).

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. **Boundary Jelas:** Ingress Controller mengelola akses masuk L4/L7 ke kluster; API Gateway mengelola kontrak bisnis, identitas, dan kebijakan API North-South; Service Mesh mengamankan dan mengamati lalu lintas East-West via sidecar proxy.
2. **Kekuatan Envoy Data Plane:** Envoy telah menjadi standar de-facto cloud-native data plane untuk Ingress, Gateway, dan Mesh karena model non-blocking threading dan antarmuka dinamis xDS API.
3. **Presisi Edge Caching:** Penggunaan kombinasi `Cache-Control` (untuk peramban) dan `Surrogate-Control` / `Surrogate-Keys` (untuk Edge CDN) memungkinkan pencapaian hit-ratio tinggi tanpa mengorbankan konsistensi data riil saat update terjadi.
4. **Resiliensi Terdistribusi:** Pola federasi gateway dan isolasi perbatasan mencegah cascading failures di seluruh ekosistem microservices skala global.

---

## SEKSI 17 — GLOSARIUM

* **mTLS (Mutual TLS):** Proses autentikasi dua arah di mana klien dan server sama-sama memverifikasi sertifikat kriptografis X.509 satu sama lain sebelum membuka kanal transmisi data terenkripsi.
* **Control Plane:** Lapisan manajemen yang mengonversi metadata deklaratif tingkat tinggi menjadi konfigurasi runtime untuk proxy (contoh: Istiod, Kong Control Plane).
* **Data Plane:** Komponen infrastruktur yang secara langsung mencegat, memeriksa, dan merutekan setiap paket lalu lintas jaringan (contoh: Envoy Proxy core).
* **Surrogate Key:** Token identifier unik yang disematkan dalam HTTP response header untuk memetakan resource cache ke entitas bisnis tertentu (dikenal juga sebagai *Cache-Tags*).
* **Thundering Herd:** Lonjakan beban masif yang menyerang backend origin server secara mendadak ketika objek cache populer kedaluwarsa serentak dan diakses oleh ribuan koneksi paralel.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Poin Penekanan:** Pastikan siswa tidak menyamakan konsep "Ingress" dengan "API Gateway". Berikan analogi: *Ingress adalah gerbang pos satpam perumahan (menentukan mobil masuk ke blok mana), sedangkan API Gateway adalah resepsionis gedung kantor (memeriksa KTP, memberikan visitor pass, mencatat buku tamu, dan mengantar ke ruangan yang benar).*
* **Skenario Lab Interaktif:** Jalankan simulasi lokal menggunakan Docker Compose yang menjalankan:
  1. Satu container Envoy (sebagai Edge Gateway).
  2. Dua container Go HTTP Mock Server.
  3. Perintahkan peserta untuk memicu load test sederhana (misal menggunakan tool `k6` atau `hey`) lalu inspect perbedaan latensi antara rute yang ter-cache via header vs rute bypass.
* **Jebakan Mahasiswa:** Peserta seringkali bingung menentukan lokasi penanganan autentikasi JWT: *Apakah di Ingress, API Gateway, atau Microservice tujuan?* Tegaskan bahwa decoding dan cryptographic signature verification dilakukan di **API Gateway**, sedangkan klaim autorisasi mendalam berbasis kepemilikan data dieksekusi di **Microservice tujuan**.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi 1.0.0 (Oktober 2023):**
  * Rilis inisial materi Edge Architecture & Gateway Topologies.
  * Penambahan konfigurasi Envoy v3 filter chains.
  * Penyusunan arsitektur Surrogate-Key invalidation pattern berbasis Go.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya:** `06-Architecture-and-System-Design / Bab 09 - Modul 02: Event-Driven API Architectures & Webhooks Engine Design`
* **Modul Berikutnya:** `06-Architecture-and-System-Design / Bab 10 - Modul 02: Resiliency Patterns: Advanced Rate Limiting, Dynamic Throttling, Circuit Breaking & Shedding`