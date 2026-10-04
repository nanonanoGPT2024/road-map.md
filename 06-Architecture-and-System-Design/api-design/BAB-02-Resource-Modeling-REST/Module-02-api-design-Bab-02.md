# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Kategori:** 06-Architecture-and-System-Design  
**Topik:** api-design  
**Bab:** BAB-02-Resource-Modeling-REST  

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Merancang Taksonomi Resource Skala Enterprise:** Menentukan batas agregat (*aggregate roots*) dan memproyeksikannya ke dalam hierarki URI RESTful yang bersih, menghindari perangkap *deep-nesting* antipattern.
2. **Mengimplementasikan State Machine berbasis Hypermedia & RFC:** Memetakan siklus hidup entitas bisnis yang kompleks ke dalam transisi status HTTP standar, memanfaatkan hypermedia formats (HAL/Siren) dan *sub-resource action dispatching*.
3. **Menguasai Mutasi Parsial Tingkat Lanjut:** Mengimplementasikan spesifikasi RFC 6902 (*JSON Patch*) dan RFC 7396 (*JSON Merge Patch*) secara aman, deterministik, dan performan.
4. **Menerapkan Distributed Concurrency Control:** Mengonstruksi mekanisme kontrol konkurensi optimistik menggunakan HTTP headers standar (`ETag`, `If-Match`, `If-None-Match`, `Last-Modified`) untuk mencegah *lost updates*.
5. **Mendesain Pola Batch & Bulk Mutation:** Membangun antarmuka mutasi massal yang menjaga semantik HTTP tanpa mengorbankan isolasi transaksi dan efisiensi *network roundtrip*.

---

## 2. Prerequisite

Sebelum mendalami modul ini, Anda wajib memiliki pemahaman mendalam tentang:
- **RFC 9110 (HTTP Semantics):** Pemahaman absolut atas *safe methods*, *idempotent methods*, status codes (seri 2xx, 3xx, 4xx, 5xx), serta siklus request-response.
- **Domain-Driven Design (DDD) Fundamentals:** Konsep *Aggregate Root*, *Entity*, *Value Object*, dan *Bounded Context*.
- **Dasar-Dasar REST:** Prinsip Fielding dissertation (Bab 5), khususnya pemisahan *Resource* dari *Representation*.
- **Bahasa Pemrograman & Concurrency:** Mahir dalam eksekusi I/O asinkron, manipulasi pointer/struktur data, serta penanganan konkurensi (contoh implementasi modul ini menggunakan Go standar industri).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Mapping DDD Aggregates ke REST Resources
REST sering disalahartikan sebagai antarmuka *Object-Relational Mapping* (ORM) berbasis HTTP di mana setiap tabel basis data dipetakan langsung menjadi endpoint CRUD. Pola ini adalah antipattern fatal di skala enterprise.

Dalam arsitektur produksi:
- **Resource adalah representasi Aggregate Root DDD:** Hanya *Aggregate Root* yang boleh terekspos sebagai *top-level collection* (misalnya `/orders`, `/accounts`).
- **Internal Entities terekspos kondisional:** Entitas internal agregat yang tidak memiliki siklus hidup independen tidak boleh dijadikan *top-level collection*. Akses terhadap entitas internal dilakukan via *sub-resource path* (misal: `/orders/{orderId}/items/{itemId}`) atau direpresentasikan langsung di dalam *document payload* agregat utama.
- **URI Depth Limit:** Batasi kedalaman hierarki URI maksimal 2 level:
  $$\text{Depth} \le 2 \quad \Rightarrow \quad /\text{aggregates}/\{id\}/\text{sub-resources}/\{id\}$$
  Jika navigasi memerlukan level ketiga (misal: `/companies/{id}/departments/{id}/teams/{id}/members/{id}`), pecah menjadi flat resource independen menggunakan *query filters*:
  `GET /members?teamId={id}`

```
[ Antipattern: Anemic CRUD URI ]
GET /tbl_orders_mst/109283
POST /tbl_order_items_dtl

[ Production: Domain-Driven Resource Modeling ]
Aggregate Root: Order
  ├── Internal Entity: OrderItem (Dikelola bersama Order)
  └── Value Object: ShippingAddress

Endpoints:
  GET  /v1/orders/ord_882910              <- Mengambil aggregate
  POST /v1/orders/ord_882910/items        <- Mutasi sub-resource langsung
  GET  /v1/orders?customer_id=cst_123     <- Query boundary flat
```

---

### 3.2 State Machines & Business Process Transitions
Model resource RESTful murni mengandalkan perubahan state representasi. Namun, proses bisnis nyata (misalnya: *Pembatalan Pesanan*, *Persetujuan Klaim Asuransi*, *Pencairan Pinjaman*) tidak selalu cocok dengan operasi `PUT` dokumen utuh.

Terdapat tiga pola enterprise untuk memetakan transisi status:

1. **Sub-resource Command Dispatching (Pola Terpilih untuk REST Pragmatis):**
   Memperlakukan transisi status sebagai *sub-resource lifecycle creation*:
   ```http
   POST /v1/orders/ord_882910/cancellations
   Content-Type: application/json

   {
     "reason": "duplicate_order",
     "note": "Customer mistakenly double-clicked"
   }
   ```
   *Benefit:* Mengikuti prinsip agregat DDD, memungkinkan audit payload tersendiri, dan menghasilkan status `201 Created` untuk entitas pembatalan.

2. **Hypermedia State Engine (HATEOAS / HAL):**
   Server merespons representasi resource lengkap dengan link aksi yang valid berdasarkan state mesin internal:
   ```json
   {
     "id": "ord_882910",
     "status": "AWAITING_PAYMENT",
     "total_amount": 150000,
     "_links": {
       "self": { "href": "/v1/orders/ord_882910" },
       "cancel": { "href": "/v1/orders/ord_882910/cancellations" },
       "payment": { "href": "/v1/orders/ord_882910/payments" }
     }
   }
   ```
   Klien tidak perlu melakukan *hardcode* logika bisnis transisi status; klien cukup mengevaluasi ada atau tidaknya relasi link `cancel` pada response.

---

### 3.3 Concurrency Control: Optimistic Locking dengan ETags
Untuk mencegah *Lost Update Problem* pada sistem terdistribusi skala tinggi:

$$T_1: \text{Read}(V_0) \to T_2: \text{Read}(V_0) \to T_1: \text{Write}(V_1) \to T_2: \text{Write}(V_2 \text{ overrides } V_1!)$$

Arsitektur REST menyelesaikan persoalan ini secara elegan menggunakan conditional headers (RFC 9110):

1. **Weak vs Strong ETag:**
   - **Strong ETag (`"33a64df551425fcc"`):** Mengindikasikan kesamaan byte-for-byte representasi payload.
   - **Weak ETag (`W/"33a64df551425fcc"`):** Mengindikasikan kesamaan semantik domain (misalnya data entitas sama, meski urutan serialisasi JSON berbeda). Weak ETag ideal untuk resource modeling enterprise.

2. **Protokol Validasi Mutasi:**
   - Client membaca resource: Klien menerima response dengan header `ETag: W/"v4-hash"`.
   - Client ingin memperbarui (`PUT`, `PATCH`, `DELETE`): Klien wajib menyertakan header `If-Match: W/"v4-hash"`.
   - Engine API Server memverifikasi version hash. Jika tidak cocok, server segera memutus pipeline dan mengembalikan `412 Precondition Failed`.

---

### 3.4 Deep Dive: RFC 6902 (JSON Patch) vs RFC 7396 (JSON Merge Patch)

Ketika memodifikasi resource secara parsial (`PATCH`), ada dua spesifikasi IETF resmi:

| Parameter | RFC 7396 (JSON Merge Patch) | RFC 6902 (JSON Patch) |
| :--- | :--- | :--- |
| **Media Type** | `application/merge-patch+json` | `application/json-patch+json` |
| **Bentuk Payload** | Dokumen JSON target sebagian (delta snapshot) | Deretan instruksi atomik (array of operations) |
| **Operasi Hapus** | Menetapkan key menjadi `null` | Operasi eksplisit: `{"op": "remove", "path": "..."}` |
| **Manipulasi Array** | Mengganti seluruh array (replace all) | Menambah/menyisip/menghapus elemen array spesifik |
| **Kompleksitas Evaluasi** | Rendah ($O(N)$ rekursif) | Menengah-Tinggi (Engine evaluasi pointer atomik) |
| **Transactional Scope** | Implisit pada seluruh field | Eksplisit: All-or-nothing secara transaksional |

---

## 4. Why & What

### Mengapa Pendekatan Ini Diperlukan?
1. **Mencegah "RPC disguised as REST":** Tanpa resource modeling berbasis agregat, URI akan membengkak menjadi `/executePayment`, `/updateAddress`, `/deleteUserDirect`. Hal ini menghancurkan caching HTTP, visibilitas observability, dan konsistensi arsitektur.
2. **Eliminasi Race Conditions:** Pada sistem pemrosesan pesanan atau finansial paralel, dua thread microservice yang mengupdate sub-dokumen yang sama akan saling menimpa data (*silent data corruption*) jika kontrol konkurensi optimistik berbasis RFC diabaikan.
3. **Optimasi Bandwidth Jaringan:** Pada payload domain yang mencapai puluhan kilobyte, mentransmisikan *full representation* berulang-ulang untuk mengubah 1 flag boolean merupakan pemborosan komputasi serialisasi dan *network I/O*.

### Apa Output yang Dihasilkan?
Arsitektur API yang:
- Mengisolasi domain boundary dengan presisi.
- Mengimplementasikan *fine-grained mutation* menggunakan `RFC 6902` / `RFC 7396`.
- Menjamin integritas konkuren melalui protokol `ETag` / `If-Match`.
- Mengeliminasi *leaky abstractions* skema basis data internal ke domain public/inter-service.

---

## 5. How (Workflow Detail)

Alur penanganan mutasi resource kompleks dengan validasi konkurensi dan evaluasi patch:

```
[Client]                [API Gateway]               [Domain API Service]          [Persistence Engine]
   |                          |                              |                             |
   |-- 1. PATCH /orders/123 ->|                              |                             |
   |   (If-Match: W/"v1")     |                              |                             |
   |   (Merge-Patch Payload)  |                              |                             |
   |                          |-- 2. Forward Request ------->|                             |
   |                          |                              |-- 3. Fetch Aggregate ------>|
   |                          |                              |                              |
   |                          |                              |<-- 4. Return Entity & Ver --|
   |                          |                              |    (Entity version: 1)      |
   |                          |                              |                             |
   |                          |                              |-- [Check: ETag == If-Match] |
   |                          |                              |   Match? YES                |
   |                          |                              |                             |
   |                          |                              |-- 5. Apply RFC Patch Logic  |
   |                          |                              |-- 6. Validate Invariants    |
   |                          |                              |                             |
   |                          |                              |-- 7. Persist (Ver = 2) ---->|
   |                          |                              |<-- 8. Commit OK ------------|
   |                          |                              |                             |
   |                          |                              |-- 9. Compute New ETag W/"v2"|
   |                          |<-- 10. HTTP 200 OK ----------|                             |
   |                          |    (ETag: W/"v2")            |                             |
   |<-- 11. Final Response ---|                              |                             |
```

1. **Header Inspection:** Server memeriksa `Content-Type` (`application/merge-patch+json` atau `application/json-patch+json`) dan header `If-Match`.
2. **Precondition Verification:** Ambil versi saat ini dari database. Hitung/bandingkan hash versi. Jika `ETag != If-Match`, gagalkan seketika dengan status code `412 Precondition Failed`. Jangan proses komputasi payload.
3. **Patch Transformation:** Terapkan mutasi ke domain entity memory representation.
4. **Invariant Validation:** Jalankan validasi domain rules (contoh: batas minimum kredit, validitas status transisi).
5. **Persistence & ETag Computation:** Simpan mutasi ke basis data dengan menginkrementasi counter versi secara atomik, buat representasi baru beserta nilai weak ETag terbaru.

---

## 6. Analogy & Diagram ASCII

### Analogi: Kartu Rekam Medis Rumah Sakit
Bayangkan berkas fisik Rekam Medis (Aggregate Root: Pasien).
- **CRUD Naif:** Anda mengganti seluruh map folder berkas pasien hanya untuk menambahkan tensi darah hari ini. Jika ada dokter lain yang sedang membaca map lama, catatan dokter tersebut akan terbuang.
- **REST Enterprise dengan ETag & Patch:**
  1. Map rekam medis diberi cap stempel stiker revisi: `v12`.
  2. Dokter bedah ingin menambahkan catatan sayatan kecil. Dokter mengisi lembar instruksi resmi (*JSON Patch*): `"Pada halaman 4, ganti dosis obat dari 10mg ke 20mg"`.
  3. Dokter menyerahkan instruksi ini ke suster bersama bukti bahwa dia memegang versi `v12` (*If-Match*).
  4. Jika suster melihat ada perawat lain yang sudah mengubah dokumen menjadi `v13`, suster menolak instruksi tersebut (*412 Precondition Failed*). Dokter bedah harus melihat rekam medis versi `v13` terlebih dahulu sebelum memutuskan kembali dosisnya.

### Diagram: State Machine Lifecycle Resource Order

```
       +--------------------------------------------------------+
       |                                                        |
       v                                                        |
  +---------+   POST .../payments   +------+   POST .../shipments   +-----------+
  | DRAFT   | --------------------> | PAID | ---------------------> | FULFILLED |
  +---------+                       +------+                        +-----------+
       |                               |
       | POST .../cancellations        | POST .../refunds
       v                               v
  +-----------+                  +------------+
  | CANCELLED |                  | REFUNDED   |
  +-----------+                  +------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: JSON Patch vs JSON Merge Patch Payload

**Baseline Entity Resource (`GET /v1/servers/srv-9912`):**
```json
{
  "id": "srv-9912",
  "name": "edge-router-sea",
  "tags": ["prod", "edge"],
  "specs": {
    "cpu": 8,
    "memory_gb": 32
  },
  "status": "ACTIVE"
}
```

**RFC 7396 (JSON Merge Patch):** Mengganti tag dan menghapus status (set `null`), menaikkan memory.
```http
PATCH /v1/servers/srv-9912 HTTP/1.1
Host: api.cloud.internal
Content-Type: application/merge-patch+json

{
  "specs": {
    "memory_gb": 64
  },
  "tags": ["prod", "edge", "failover"]
}
```

**RFC 6902 (JSON Patch):** Menambahkan 1 item secara atomik ke dalam array tanpa me-replace seluruh array.
```http
PATCH /v1/servers/srv-9912 HTTP/1.1
Host: api.cloud.internal
Content-Type: application/json-patch+json

[
  { "op": "test", "path": "/status", "value": "ACTIVE" },
  { "op": "add", "path": "/tags/-", "value": "failover" },
  { "op": "replace", "path": "/specs/memory_gb", "value": 64 }
]
```

---

### 7.2 Practical Example: Enterprise Aggregate Pattern with ETag Concurrency in Go

Implementasi production-grade REST endpoint untuk domain *Account Aggregation* dengan dukungan Weak ETag, Conditional Mutation (`If-Match`), dan JSON Merge Patch.

```go
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"sync"
	"time"
)

// Domain Aggregate
type Account struct {
	ID        string    `json:"id"`
	Holder    string    `json:"holder"`
	Balance   int64     `json:"balance"` // Nilai dalam unit satuan terkecil (sen/rupiah)
	Status    string    `json:"status"`  // "ACTIVE", "FROZEN", "TERMINATED"
	Version   uint64    `json:"version"`
	UpdatedAt time.Time `json:"updated_at"`
}

// In-Memory Repository Thread-Safe
type AccountRepository struct {
	mu       sync.RWMutex
	accounts map[string]*Account
}

func NewAccountRepository() *AccountRepository {
	return &AccountRepository{
		accounts: make(map[string]*Account),
	}
}

func (r *AccountRepository) Get(id string) (*Account, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	acc, exists := r.accounts[id]
	if !exists {
		return nil, errors.New("not_found")
	}
	// Salin pointer value untuk menghindari race conditions
	clone := *acc
	return &clone, nil
}

func (r *AccountRepository) Save(acc *Account, expectedVersion uint64) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	current, exists := r.accounts[acc.ID]
	if !exists && expectedVersion != 0 {
		return errors.New("version_conflict")
	}
	if exists && current.Version != expectedVersion {
		return errors.New("version_conflict")
	}

	acc.Version++
	acc.UpdatedAt = time.Now().UTC()
	r.accounts[acc.ID] = acc
	return nil
}

// GenerateWeakETag menghitung representasi ETag semantik
func GenerateWeakETag(acc *Account) string {
	h := sha256.New()
	raw := fmt.Sprintf("%s:%s:%d:%s:%d", acc.ID, acc.Holder, acc.Balance, acc.Status, acc.Version)
	h.Write([]byte(raw))
	return fmt.Sprintf(`W/"%s"`, hex.EncodeToString(h.Sum(nil))[:16])
}

type AccountHandler struct {
	repo *AccountRepository
}

func (h *AccountHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	path := strings.TrimPrefix(r.URL.Path, "/v1/accounts/")
	parts := strings.Split(strings.Trim(path, "/"), "/")

	if len(parts) == 0 || parts[0] == "" {
		http.Error(w, `{"error":"resource_id_required"}`, http.StatusBadRequest)
		return
	}

	accountID := parts[0]

	switch r.Method {
	case http.MethodGet:
		h.handleGet(w, r, accountID)
	case http.MethodPatch:
		h.handlePatch(w, r, accountID)
	default:
		w.Header().Set("Allow", "GET, PATCH")
		http.Error(w, `{"error":"method_not_allowed"}`, http.StatusMethodNotAllowed)
	}
}

func (h *AccountHandler) handleGet(w http.ResponseWriter, r *http.Request, id string) {
	acc, err := h.repo.Get(id)
	if err != nil {
		http.Error(w, `{"error":"resource_not_found"}`, http.StatusNotFound)
		return
	}

	etag := GenerateWeakETag(acc)
	if match := r.Header.Get("If-None-Match"); match != "" {
		if match == etag || match == "*" {
			w.WriteHeader(http.StatusNotModified)
			return
		}
	}

	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("ETag", etag)
	json.NewEncoder(w).Encode(acc)
}

func (h *AccountHandler) handlePatch(w http.ResponseWriter, r *http.Request, id string) {
	contentType := r.Header.Get("Content-Type")
	if !strings.HasPrefix(contentType, "application/merge-patch+json") {
		http.Error(w, `{"error":"unsupported_media_type","expected":"application/merge-patch+json"}`, http.StatusUnsupportedMediaType)
		return
	}

	ifMatch := r.Header.Get("If-Match")
	if ifMatch == "" {
		http.Error(w, `{"error":"precondition_required","message":"If-Match header mandatory"}`, http.StatusPreconditionRequired)
		return
	}

	acc, err := h.repo.Get(id)
	if err != nil {
		http.Error(w, `{"error":"resource_not_found"}`, http.StatusNotFound)
		return
	}

	// Evaluasi ETag
	currentETag := GenerateWeakETag(acc)
	if ifMatch != currentETag && ifMatch != "*" {
		http.Error(w, `{"error":"precondition_failed","message":"Resource modified concurrently"}`, http.StatusPreconditionFailed)
		return
	}

	// Dynamic RFC 7396 In-Memory Patch Unmarshaling
	var patchMap map[string]interface{}
	if err := json.NewDecoder(r.Body).Decode(&patchMap); err != nil {
		http.Error(w, `{"error":"malformed_json"}`, http.StatusBadRequest)
		return
	}

	originalVersion := acc.Version

	// Apply delta to Aggregate
	if val, ok := patchMap["holder"]; ok {
		if str, isStr := val.(string); isStr && len(str) > 0 {
			acc.Holder = str
		} else {
			http.Error(w, `{"error":"invalid_field_type","field":"holder"}`, http.StatusUnprocessableEntity)
			return
		}
	}

	if val, ok := patchMap["status"]; ok {
		if str, isStr := val.(string); isStr {
			if str != "ACTIVE" && str != "FROZEN" && str != "TERMINATED" {
				http.Error(w, `{"error":"invalid_status_transition"}`, http.StatusUnprocessableEntity)
				return
			}
			acc.Status = str
		}
	}

	// Persist Mutasi
	if err := h.repo.Save(acc, originalVersion); err != nil {
		if err.Error() == "version_conflict" {
			http.Error(w, `{"error":"conflict","message":"Atomic update conflict occurred"}`, http.StatusConflict)
			return
		}
		http.Error(w, `{"error":"internal_server_error"}`, http.StatusInternalServerError)
		return
	}

	newETag := GenerateWeakETag(acc)
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("ETag", newETag)
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(acc)
}

func main() {
	repo := NewAccountRepository()
	// Seed Initial Domain State
	_ = repo.Save(&Account{
		ID:      "acc_core_01",
		Holder:  "PT Finansial Teknologi Nusantara",
		Balance: 2500000000,
		Status:  "ACTIVE",
		Version: 0,
	}, 0)

	mux := http.NewServeMux()
	mux.Handle("/v1/accounts/", &AccountHandler{repo: repo})

	server := &http.Server{
		Addr:         ":8080",
		Handler:      mux,
		ReadTimeout:  5 * time.Second,
		WriteTimeout: 10 * time.Second,
	}

	fmt.Println("Aggregate API Server running on port 8080...")
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		panic(err)
	}
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Global Payment Processor Transaction Sub-Resource Orchestration
Sebuah payment gateway memproses 35.000 request per detik pada endpoint transaksi. 

#### Masalah Utama
Model awal memproyeksikan seluruh perubahan siklus pembayaran ke dalam satu rute: `POST /updatePaymentStatus`. 
1. **Payload Contention:** Mutasi konkuren dari *Webhook Gateway*, *Risk Analysis Engine*, dan *Customer Browser Callback* berebut menulis status. Terjadi data overwriting (contoh: status `REFUND_PENDING` tertimpa menjadi `SETTLED`).
2. **Database Row Lock Exhaustion:** Satu baris database di-lock secara eksklusif dalam durasi panjang untuk mengakomodasi seluruh field agregat transaksi.

#### Transformasi Resource Modeling
Gateway tersebut mendesain ulang arsitektur resource menggunakan hierarki DDD:

```
/v1/payment_intents (Aggregate Root)
    │
    ├── POST /v1/payment_intents (Buat intent baru)
    ├── GET  /v1/payment_intents/pi_8839 (Read model + ETag)
    │
    ├── /captures (Sub-resource Lifecycle)
    │   └── POST /v1/payment_intents/pi_8839/captures (Idempotent Capture Command)
    │
    ├── /cancellations (State Machine Transition Resource)
    │   └── POST /v1/payment_intents/pi_8839/cancellations
    │
    └── /refunds (Sub-resource Independent)
        └── POST /v1/payment_intents/pi_8839/refunds
```

#### Hasil Metrik Arsitektur:
- **Zero Inconsistent States:** Concurrency didorong ke level HTTP semantics via `If-Match` dan `Idempotency-Key` headers.
- **Latency P99 Berkurang 42%:** Mengeliminasi transmisi payload berulang dan row locking berkurang karena aksi didelegasikan ke sub-resource tables yang terpisah secara partisi.

---

## 9. Trade-offs

Setiap keputusan permodelan resource memiliki konsekuensi arsitektural:

| Keputusan Desain | Keuntungan (Pros) | Konsekuensi & Mitigasi (Cons) |
| :--- | :--- | :--- |
| **Deep Sub-resources**<br>`/orgs/{a}/teams/{b}/users/{c}` | Hubungan hierarki relasi antar entitas sangat jelas di URI. | Klien mengalami *chatty communication* dan URI sangat kaku. Mitigasi: Ratakan (*flatten*) rute menjadi `/users/{c}` dengan filter relasi di query parameter. |
| **HATEOAS Murni (Hypermedia Engine)** | Client terbebas total dari *hardcoded route paths* dan logika transisi bisnis. | Serialisasi overhead meningkat signifikan (payload size membengkak 20-40% karena hypertext metadata). Mitigasi: Terapkan format selektif hanya untuk flow proses multi-langkah kompleks. |
| **RFC 6902 (JSON Patch)** | Kontrol atomik granular; aman untuk array mutations; intent perubahan terekam jelas. | Developer experience lebih kompleks; klien harus merakit instruksi format JSON patch; komputasi parsing CPU overhead di server lebih tinggi. |
| **Optimistic Locking via ETag** | Skalabilitas sangat tinggi; database connection thread pool tidak terkunci (*no distributed lock contention*). | Klien menerima error `412` saat terjadi beban persaingan tinggi dan wajib mengimplementasikan mekanisme *fetch-retry loop* di sisi aplikasi mereka. |

---

## 10. Common Mistakes & Troubleshooting

### Mistake 1: Verba dalam Path URI
- **Salah:** `POST /v1/orders/123/cancelOrder` atau `POST /v1/users/delete-all`
- **Solusi Benar:** Gunakan kata benda aggregate atau sub-resource command:
  `POST /v1/orders/123/cancellations` atau `DELETE /v1/users`

### Mistake 2: Leaking Database Foreign Keys sebagai Path Parameter Hierarki Semu
- **Salah:** `/v1/warehouses/1/zones/4/aisles/12/shelves/3/products/8991`
- **Dampak Buruk:** Dependensi coupling yang dalam. Jika produk dipindah ke shelf lain, URI berubah dan URL bookmark/caching klien menjadi invalid.
- **Solusi Benar:** Identitas produk bersifat global: `GET /v1/products/8991`. Lokasi merupakan atribut dari representasi resource, bukan penentu alamat global.

### Mistake 3: Status Code `200 OK` untuk Operasi Asinkron Panjang
- **Salah:** Mengembalikan `200 OK` saat menerima mutasi batch 10.000 records yang diproses via background worker.
- **Solusi Benar:** Gunakan `202 Accepted` dengan header `Location: /v1/bulk_jobs/job_991` agar klien dapat memantau status eksekusi agregat tersebut secara terpisah.

---

## 11. Best Practices (Production Checklist)

1. [ ] **Aggregate Isolation:** Pastikan hanya DDD Aggregate Root yang menjadi first-class URI root collection (`/v1/<aggregates>`).
2. [ ] **Plural Naming Consistency:** Gunakan kata benda jamak konsisten (`/orders`, `/customers`, bukan singular `/order`).
3. [ ] **Kebab-case Pathing:** Gunakan `kebab-case` untuk URI path segments (contoh: `/v1/credit-cards`), bukan camelCase atau snake_case.
4. [ ] **Strict ETag Emission:** Wajib menyertakan header `ETag` pada semua respons `GET` entitas tunggal yang *mutable*.
5. [ ] **Conditional Update Enforcement:** Tolak operasi `PUT` dan `PATCH` dengan kode status `428 Precondition Required` jika klien tidak melampirkan header `If-Match`.
6. [ ] **Explicit Patch Media-Types:** Validasi `Content-Type` header secara mutlak: bedakan `application/merge-patch+json` (RFC 7396) dengan `application/json-patch+json` (RFC 6902). Tolak generic `application/json` jika memproses partial update delta.
7. [ ] **Batch/Bulk Standard:** Gunakan sub-resource endpoint `/v1/<aggregates>/batch` dengan representasi array of operations jika mendukung mutasi masif, lengkapi dengan `Idempotency-Key`.

---

## 12. Hands-on Practice

Buat dan simpan struktur project ini di direktori:  
`hands-on/m02/`

### File: `hands-on/m02/go.mod`
```go
module resource-modeling-lab

go 1.22
```

### File: `hands-on/m02/main.go`
Gunakan implementasi server Go yang tertera pada **Seksi 7.2 Practical Example**.

### Langkah Verifikasi & Pengujian Terminal:

1. **Jalankan API Server:**
   ```bash
   cd hands-on/m02
   go run main.go
   ```

2. **Langkah A: Ambil Resource & Simpan ETag**
   ```bash
   curl -i -X GET http://localhost:8080/v1/accounts/acc_core_01
   ```
   *Amati header response:*
   ```http
   HTTP/1.1 200 OK
   Content-Type: application/json
   ETag: W/"..."
   ```

3. **Langkah B: Uji Conditional GET (Caching Mechanism)**
   Salin nilai ETag dari langkah A (contoh: `W/"12345abcdef"`):
   ```bash
   curl -i -X GET http://localhost:8080/v1/accounts/acc_core_01 \
     -H 'If-None-Match: W/"PASTE_ETAG_HERE"'
   ```
   *Harapan Response:* `HTTP/1.1 304 Not Modified` (tanpa payload body).

4. **Langkah C: Uji Concurrency Collision Detection (Lost Update Prevention)**
   Jalankan patch menggunakan ETag kadaluarsa (misal sengaja memasukkan dummy `W/"outdated"`):
   ```bash
   curl -i -X PATCH http://localhost:8080/v1/accounts/acc_core_01 \
     -H "Content-Type: application/merge-patch+json" \
     -H 'If-Match: W/"outdated"' \
     -d '{"holder": "Hacker Overwrite"}'
   ```
   *Harapan Response:* `HTTP/1.1 412 Precondition Failed`.

5. **Langkah D: Eksekusi Valid Atomic Patch**
   Gunakan ETag yang benar dari langkah A:
   ```bash
   curl -i -X PATCH http://localhost:8080/v1/accounts/acc_core_01 \
     -H "Content-Type: application/merge-patch+json" \
     -H 'If-Match: W/"PASTE_VALID_ETAG_HERE"' \
     -d '{"holder": "PT Maju Bersama Makmur", "status": "FROZEN"}'
   ```
   *Harapan Response:* `HTTP/1.1 200 OK` beserta nilai `ETag` baru.

---

## 13. Exercise

### Level Easy
Modifikasi implementasi pada `hands-on/m02/main.go` agar server menolak *request* mutasi `PATCH` dengan status `428 Precondition Required` secara eksplisit apabila header `If-Match` tidak dikirim sama sekali oleh klien.

### Level Medium
Tambahkan penanganan sub-resource lifecycle untuk pembekuan akun:
- Endpoint: `POST /v1/accounts/{id}/freeze-requests`
- Payload: `{"reason": "suspicious_fraud", "investigator_id": "usr_992"}`
- Syarat: Mengubah status account agregat menjadi `FROZEN` secara transaksional dan menghasilkan status HTTP `201 Created` dengan `Location` header mengarah ke record audit pembekuan tersebut.

### Level Hard
Implementasikan RFC 6902 (JSON Patch) handler penuh pada entitas `Account` untuk field bersarang array of objects:
```json
{
  "authorized_signers": [
    {"signer_id": "usr_1", "role": "ADMIN"},
    {"signer_id": "usr_2", "role": "OPERATOR"}
  ]
}
```
Engine harus mendukung operasi patch `"op": "add"` dan `"op": "remove"` pada pointer array path spesifik (misal: `/authorized_signers/1`) serta memvalidasi aturan domain: *Minimal harus selalu tersisa minimal 1 ADMIN*. Jika operasi patch melanggar aturan ini, rollback mutasi dan kembalikan `422 Unprocessable Entity`.

---

## 14. Challenge

Rancang spesifikasi arsitektur Resource Modeling untuk sistem **Supply Chain Freight Shipment**:
- Terdapat entitas `ShipmentAggregate` yang melacak kontainer kargo lintas pelabuhan dunia.
- Kontainer bergerak melalui status: `LOADED` $\to$ `IN_TRANSIT` $\to$ `CUSTOMS_INSPECTION` $\to$ `RELEASED` $\to$ `DELIVERED`.
- Pada tahap `CUSTOMS_INSPECTION`, kontainer bisa ditahan (*hold*) secara parsial per komoditas kargo di dalamnya oleh instansi bea cukai yang berbeda-beda secara paralel.

**Tugas Anda:**
1. Rancang dokumen arsitektur spesifikasi endpoint (URI, HTTP Verbs, Header, Payload Request/Response).
2. Tentukan batasan mana yang menjadi sub-resource actions dan mana yang dipetakan sebagai state attribute merge patch.
3. Definisikan strategi resolusi konflik konkurensi ketika 2 petugas bea cukai di pelabuhan memperbarui status item kargo yang sama pada detik yang sama di back-office yang berbeda (Multi-region Active-Active Architecture).

---

## 15. Quiz Evaluasi Pemahaman

### 5 Pertanyaan Basic
1. Apa perbedaan semantik mendasar antara metode HTTP `PUT` dan `PATCH` menurut standar IETF?
2. Mengapa format `W/"xyz"` (Weak ETag) lebih direkomendasikan pada level domain REST API dibandingkan Strong ETag?
3. Kode status HTTP manakah yang paling tepat dikembalikan server jika klien mencoba memutasi resource namun mengirimkan hash ETag yang sudah usang?
4. Mengapa URI path seperti `/api/v1/create-purchase-order` melanggar kaidah RESTful resource modeling?
5. Berapa batas kedalaman (*depth limit*) hierarki sub-resource yang direkomendasikan dalam perancangan API enterprise?

### 5 Pertanyaan Intermediate
6. Bagaimana cara merepresentasikan penghapusan atribut domain pada sebuah resource jika menggunakan spesifikasi RFC 7396 (JSON Merge Patch)?
7. Mengapa array manipulation (misal: menghapus 1 index array di tengah-tengah) sulit dilakukan secara andal menggunakan JSON Merge Patch (RFC 7396)?
8. Kapan arsitek sistem harus memodelkan transisi status sebagai *sub-resource command* (misal: `/orders/{id}/cancellations`) daripada sekadar field status mutation (`PATCH /orders/{id}`)?
9. Jelaskan perbedaan peran header `If-Match` dengan header `If-None-Match` dalam siklus hidup HTTP cache dan concurrency!
10. Jika klien mengirimkan operasi mutasi batch besar ke resource `/v1/invoices/batch`, dan 3 dari 10 data mengalami validasi error, mengapa status `207 Multi-Status` sering dihindari di skala enterprise dan apa alternatif rancangan REST yang lebih deterministik?

### 3 Skenario Kasus Produksi
11. **Skenario 1:** Frontend Anda secara konstan menerima error `412 Precondition Failed` saat pengguna melakukan drag-and-drop kanban task card secara cepat. Database mencatat bahwa versi dokumen bergerak sangat cepat. Bagaimana arsitektur API client-server dimodifikasi untuk menyelesaikan isu UX tanpa mengorbankan integritas data?
12. **Skenario 2:** Anda mendesain endpoint mutasi profil merchant: `PATCH /v1/merchants/{id}`. Payload menyertakan pembaruan nama toko dan nomor rekening bank pencairan. Perubahan nama toko dapat langsung aktif, namun perubahan nomor rekening memerlukan verifikasi OTP SMS. Bagaimana memodelkan API resource ini agar tidak melanggar prinsip *Single Responsibility* dan atomisitas resource?
13. **Skenario 3:** Sebuah sistem API perbankan memiliki rate limiting ketat dan latensi roundtrip antar benua sebesar 220ms. Klien mobile membutuhkan data ringkasan Akun, 5 Mutasi Terakhir, dan Status Notifikasi sekaligus saat aplikasi dibuka. Pola RESTful modeling apa yang harus diterapkan tanpa merusak kaidah decoupling aggregate?

---

### Kunci Jawaban & Panduan Solusi Quiz

1. **Jawaban Basic 1:** `PUT` menggantikan *seluruh* representasi resource secara utuh (idempotent replacement). Jika ada field yang tidak dikirim, field tersebut dianggap terhapus atau kembali ke default. `PATCH` mengaplikasikan modifikasi *sebagian/parsial* terhadap representasi yang sudah ada.
2. **Jawaban Basic 2:** Weak ETag mengevaluasi kesetaraan semantik domain model, bukan kesamaan byte payload mentah. Variasi minor seperti urutan key JSON, indentasi spasi, atau kompresi gzip tidak akan merusak validitas weak ETag.
3. **Jawaban Basic 3:** `HTTP 412 Precondition Failed`.
4. **Jawaban Basic 4:** Karena menyertakan kata kerja (*create*), yang mengubah semantik HTTP menjadi Remote Procedure Call (RPC). Semantik pembuatan dalam REST sudah diwakili oleh kata kerja protokol: `POST /v1/purchase-orders`.
5. **Jawaban Basic 5:** Maksimal 2 level hierarki (`/parents/{id}/children/{id}`). Level selebihnya harus diratakan (*flattened*) menggunakan filter query string.
6. **Jawaban Intermediate 6:** Dengan menetapkan nilai atribut target menjadi eksplisit `null` di dalam JSON payload.
7. **Jawaban Intermediate 7:** RFC 7396 mendefinisikan bahwa jika sebuah field bertipe array muncul di payload patch, array tersebut akan menimpa (*full replacement*) array yang sudah ada di database, bukan melakukan manipulasi index in-place.
8. **Jawaban Intermediate 8:** Ketika transisi status tersebut memiliki metadata audit kompleks (alasan pembatalan, user yang mengeksekusi, timestamp), memicu side-effect terdistribusi yang signifikan, atau membutuhkan *validation rules* yang berbeda drastis dari mutasi atribut biasa.
9. **Jawaban Intermediate 9:** `If-Match` digunakan pada operasi *write* (`PUT`/`PATCH`/`DELETE`) untuk memastikan klien memutasi data berdasarkan versi yang masih relevan. `If-None-Match` digunakan pada operasi *read* (`GET`) untuk validasi cache conditional; jika data belum berubah, server cukup mengembalikan `304 Not Modified`.
10. **Jawaban Intermediate 10:** `207 Multi-Status` (RFC 4918 WebDAV) rumit diproses oleh API gateway dan client library modern secara seragam. Pola enterprise lebih memilih:
    - **All-or-Nothing Transaction:** Kembalikan `422 Unprocessable Entity` yang berisi daftar detail error seluruh field index yang gagal.
    - **Asynchronous Job Resource:** Buat resource batch processing via `POST /v1/invoices/batch-jobs` yang mengembalikan `202 Accepted` lalu proses per item di background.
11. **Panduan Skenario 1:** Frontend harus mengimplementasikan teknik *optimistic UI* dengan queue buffering internal. Jika server mengembalikan `412`, client service secara transparan melakukan silent `GET` untuk mengambil payload + ETag terbaru, me-reapply perubahan posisi kartu lokal, dan mengulang eksekusi request `PATCH` dengan ETag baru tersebut (*exponential backoff / retry on stale precondition*).
12. **Panduan Skenario 2:** Pisahkan domain rekening bank dari profil publik merchant. Jadikan rekening bank sebagai sub-resource independen:
    - `PATCH /v1/merchants/{id}`: Mutasi profil instan (nama toko, bio).
    - `POST /v1/merchants/{id}/bank-account-change-requests`: Menginisiasi state machine perubahan bank yang menghasilkan challenge OTP dan berstatus `PENDING_VERIFICATION`.
13. **Panduan Skenario 3:** Gunakan pola **API Composition via Composite Resource** atau endpoint **BFF (Backend for Frontend)** yang RESTful, contoh: `GET /v1/dashboard-summaries/me` yang menghasilkan agregasi *read-only projection* dari beberapa aggregate sekaligus, tanpa menggabungkan mutasi write aggregate tersebut di backend.

---

## 16. Summary

- **Resource Modeling RESTful Enterprise berakar pada Domain-Driven Design (DDD):** Endpoint bukan cerminan langsung skema database ORM, melainkan representasi batas agregat bisnis.
- **Hierarki URI harus dangkal (Shallow URLs):** Hindari navigasi path lebih dari 2 level dengan memanfaatkan perataan sumber daya (*flat resources*) dan query parameters.
- **State Machine Transisi Bisnis:** Transisi status entitas kompleks sebaiknya dipetakan menjadi pembuatan *command sub-resource* daripada sekadar pembaruan string status trivial.
- **RFC 7396 vs RFC 6902:** Gunakan Merge Patch untuk pembaruan skalar parsial sederhana; gunakan JSON Patch untuk operasi transaksional granular pada array dan dokumen kompleks.
- **HTTP Concurrency Control:** Wajib menerapkan mekanisme conditional headers (`ETag`, `If-Match`) untuk mencegah bahaya *lost updates* pada arsitektur terdistribusi berperforma tinggi.