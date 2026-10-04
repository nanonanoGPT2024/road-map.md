# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 04: Konkurensi, Transaksi, dan Eksekusi Server-Side Scripting**  
**Kategori: 04-Backend-and-Database**

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Menganalisis model konkurensi Redis secara mendalam (single-threaded event loop, multiplexing I/O, dan isolasi eksekusi atomik).
- Menguasai implementasi transaksi menggunakan primitif `MULTI`, `EXEC`, `DISCARD`, dan `WATCH` (Optimistic Concurrency Control / OCC).
- Mendesain, men-debug, dan mengoptimalkan eksekusi server-side scripting menggunakan Lua Scripts (`EVAL`, `EVALSHA`) dan Redis 7+ Functions (`FUNCTION LOAD`, `FCALL`).
- Mengidentifikasi batasan atomisitas Redis (ketiadaan mekanisme *rollback* konvensional) serta mengelola mitigasi kegagalan pada runtime.
- Mengimplementasikan pola arsitektur terdistribusi tingkat lanjut: Atomic Rate Limiter, Sliding-Window Counter, dan Distributed Lock dengan *fencing token* yang aman untuk Redis Cluster (menghindari isu *cross-slot*).
- Mengaudit performa eksekusi server-side script, mendeteksi script blocking via `SLOWLOG` dan monitoring latency engine.

---

## 2. Prerequisite
Untuk mencerna materi ini secara optimal, peserta wajib memahami:
- Arsitektur dasar Redis (in-memory data structure, persistence RDB/AOF, master-replica).
- Struktur data Redis fundamental: Strings, Hashes, Lists, Sets, dan Sorted Sets.
- Konsep dasar konkurensi: *race conditions*, *deadlocks*, *mutual exclusion*, dan *atomicity*.
- Sintaks dasar bahasa pemrograman Lua (tipe data, tabel, kontrol alur logika).
- Pengoperasian Docker dan Redis CLI (`redis-cli`).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1. Single-Threaded Core vs Concurrency
Meskipun Redis menggunakan background thread untuk operasi I/O tertentu (sejak v4.0 untuk bio threads seperti `UNLINK`, `lazy free`, dan v6.0 untuk threaded I/O socket read/write), eksekusi perintah (command processing engine) **selalu bersifat single-threaded**. 

Semua operasi dieksekusi secara serial dari antrean event loop (*ae event loop*) berbasis `epoll`, `kqueue`, atau `select`. Karakteristik ini memberikan jaminan:
- **No Race Condition Antar-Instruksi Internal:** Tidak ada dua instruksi Redis native yang dieksekusi bersamaan di core engine.
- **Serializability Implisit:** Semua interaksi diproses dalam urutan linier (*linearizable execution timeline*).

Namun, race condition muncul di tingkat aplikasi saat terjadi pola **Read-Modify-Write (RMW)** melalui beberapa round-trip jaringan.

```
Client A: GET balance (100) -----------------------------------> SET balance (100 - 30 = 70)
Client B:      GET balance (100) -> SET balance (100 - 50 = 50) -/  [LOST UPDATE!]
Timeline: ----t1-----------------t2------------------------------t3------------------------>
```

### 3.2. Redis Transactions: MULTI/EXEC dan Keterbatasannya
Primitif transaksi Redis terdiri dari:
1. `MULTI`: Mengubah status koneksi client menjadi *transactional mode*. Perintah berikutnya tidak dieksekusi langsung, melainkan dimasukkan ke dalam antrean in-memory per-koneksi (*command queue*).
2. `EXEC`: Menjalankan seluruh antrean perintah secara serial dan tanpa interupsi dari koneksi lain.
3. `DISCARD`: Menghapus antrean transaksi dan mengembalikan status koneksi ke normal.
4. `WATCH`: Mengaktifkan *Optimistic Concurrency Control* (OCC). Redis menandai (flags) satu atau beberapa key. Jika salah satu key yang di-watch dimodifikasi oleh client lain sebelum `EXEC` dipanggil, transaksi dibatalkan seluruhnya (`EXEC` me-return `nil`).

#### Ketiadaan Rollback (No Rollback Semantics)
Penting dicatat: **Redis bukan basis data ACID relasional standar.**
- **Syntax Error (Compile-time error):** Jika perintah gagal diparse saat antrean `MULTI` dibangun (misal: jumlah argumen salah), Redis v2.6.5+ akan menolak eksekusi dan membatalkan seluruh transaksi saat `EXEC` dipanggil.
- **Runtime Error (Type Mismatch):** Jika perintah gagal saat eksekusi (misal: mengeksekusi `HSET` pada key yang berisi String via `INCR`), **perintah lain di dalam blok transaksi tetap dieksekusi**. Redis **tidak membatalkan (rollback)** modifikasi yang sudah terjadi.

### 3.3. Server-Side Scripting: Lua Engine vs Redis 7+ Functions
Untuk mengatasi kelemahan RMW dan transaksi tanpa rollback kondisional, Redis mengintegrasikan runtime Lua embedded.

#### A. Lua Scripts (`EVAL` & `EVALSHA`)
- Script dieksekusi secara atomik. Ketika script Lua berjalan, seluruh event loop terblokir; tidak ada perintah lain yang dapat disisipkan.
- Script dikompilasi menjadi bytecode dan di-cache dalam internal memory menggunakan SHA-1 digest.
- **Kelemahan Lua Scripting Legasi:**
  - Script tidak persisten terhadap restart tanpa AOF/RDB reload yang kompleks.
  - Script tidak terikat namespace; `SCRIPT FLUSH` menghapus seluruh cache.
  - Replikasi script lama berbasis text payload (`eval` expression) menyebabkan disparitas jika terdapat logika non-deterministik.

#### B. Redis 7+ Functions
Redis 7 memperkenalkan *Functions* sebagai evolusi dari Lua scripts:
- **First-class Citizen:** Dideklarasikan ke dalam *Library* (`FUNCTION LOAD`).
- **Persistence & Replication:** Library disimpan langsung di dalam file RDB dan AOF, serta direplikasi ke replica node sebagai *engine library definitions*, bukan per-eval string.
- **Namespacing & Modularization:** Mengelompokkan fungsi-fungsi terkait di bawah satu modul metadata yang terisolasi.

```
+-------------------------------------------------------------------+
|                        Redis Engine Context                       |
|                                                                   |
|   +-----------------------+              +--------------------+   |
|   |  aeEventLoop (Core)   |              | Lua 5.1 Sandbox    |   |
|   |                       |              |                    |   |
|   |  - Socket Read (I/O)  |              | - redis.call()     |   |
|   |  - Dispatcher         | <--------->  | - redis.pcall()    |   |
|   |  - Execution Engine   |              | - Fast Table Ops   |   |
|   +-----------------------+              +--------------------+   |
|               ^                                    ^              |
|               |                                    |              |
|   +-----------------------+              +--------------------+   |
|   | Client Command Queue  |              | Function Registry  |   |
|   | (MULTI/EXEC pipeline) |              | (Libraries cache)  |   |
|   +-----------------------+              +--------------------+   |
+-------------------------------------------------------------------+
```

---

## 4. Why & What

| Dimensi | MULTI / EXEC (`WATCH`) | Lua Scripting (`EVALSHA`) | Redis 7+ Functions (`FCALL`) |
| :--- | :--- | :--- | :--- |
| **Model Eksekusi** | Antrean buffer client-side & batching server-side | Server-side procedural bytecode execution | Server-side modular library execution |
| **Conditional Logic** | Terbatas. Client harus membaca data dulu via `WATCH` | Penuh. Mendukung logika `if-else`, loop, error throw | Penuh. Modular, mendukung library reusability |
| **Round Trips** | Minimal 2 RTT (WATCH/GET -> EXEC) | 1 RTT (Kirim SHA1 hash + argument) | 1 RTT (Kirim Function name + argument) |
| **Aborsi/Rollback** | Abort jika key termodifikasi; runtime error tidak rollback | Abort eksekusi di tengah; state sebelum error tetap termutasi | Abort eksekusi di tengah; state sebelum error tetap termutasi |
| **Distribusi Kode** | Di-embed pada kode aplikasi client | Aplikasi client harus memastikan `SCRIPT LOAD` | Didaftarkan sekali di cluster/server via CI/CD |

### Mengapa Lua/Functions Menggantikan `WATCH`?
Pada skenario dengan tingkat konkurensi tinggi (*high contention*), `WATCH` mengalami degradasi performa drastis akibat kegagalan transaksi (*aborts*). Jika 1.000 thread memperebutkan stok barang yang sama, hampir seluruh client akan mengalami abort dan dipaksa melakukan *retry loop* berulang kali. 

Dengan server-side Lua/Functions, logika *read-and-commit* dilakukan langsung di dalam core engine: tidak ada abort, tidak ada retry loop, dan throughput melonjak secara deterministik.

---

## 5. How (Workflow Detail)

### 5.1. Siklus Hidup Eksekusi Redis Functions (Redis 7+)
1. **Pendaftaran (Deployment phase):** Library didefinisikan dengan metadata dan dieksekusi via `FUNCTION LOAD`.
2. **Kompilasi & Pendaftaran Engine:** Redis mengompilasi kode Lua ke dalam *Lua State sandbox*, memetakan fungsi ke internal registry.
3. **Eksekusi:** Klien memanggil fungsi menggunakan perintah `FCALL` atau `FCALL_RO` (read-only).
4. **Replikasi:** Payload library dicatat ke dalam Append-Only File (AOF) dan direplikasi ke seluruh node replika secara deterministik.

### 5.2. Penanganan Error: `redis.call()` vs `redis.pcall()`
- `redis.call()`: Jika perintah Redis internal gagal (misal syntax error atau OOM), script langsung berhenti seketika (*fail-fast*), dan me-raise runtime error kembali ke pemanggil client.
- `redis.pcall()`: Menangkap error (*protected call*), mengembalikan objek Lua table berupa `{["err"] = "PESAN ERROR"}`. Eksekusi script dapat berlanjut secara kondisional, memungkinkan implementasi kompensasi logika manual.

---

## 6. Analogy & Diagram ASCII

### Analogi: Kasir Bank
- **MULTI / EXEC:** Nasabah menuliskan 3 instruksi di secarik kertas (Tarik Rp50k, Setor Rp20k, Cetak Buku). Kasir mengeksekusi ketiganya berturut-turut tanpa melayani orang lain. Jika instruksi kedua gagal karena uang palsu, kasir tetap menjalankan instruksi ketiga.
- **WATCH:** Nasabah melihat saldo di layar, lalu mulai antre. Saat tiba di depan kasir, kasir memeriksa apakah saldo berubah sejak nasabah melihat layar. Jika berubah, kasir menolak seluruh kertas dan meminta nasabah keluar antrean untuk mengecek ulang.
- **Lua / Functions:** Nasabah menyewa analis bank (eksekutor di sisi server). Analis masuk ke bilik kasir, mengunci pintu, mengecek saldo, mengambil keputusan bersyarat ("Jika saldo > 50k, kurangi 50k, lalu catat log; jika tidak, tolak"), menyelesaikan pekerjaan, lalu keluar dan membuka pintu kembali.

```
ALUR KOMPARASI KONKURENSI (Contention Level: High)

A. WATCH / EXEC Loop Pattern:
Client 1 ---> WATCH key ---> GET key (val=10)
Client 2 ------------------> WATCH key ---> GET key (val=10) ---> SET key 15 ---> COMMITTED
Client 1 ---> MULTI ---> SET key 20 ---> EXEC ---> [NIL / ABORTED] (Client 1 RETRY LENGKAP!)

B. Lua / Function Pattern:
Client 1 ---> FCALL "reserve_stock" 1 key 5  \  (Masuk aeEventLoop)
Client 2 ---> FCALL "reserve_stock" 1 key 5   \  (Antre di Socket Buffer)

[Redis Core Execution Engine]
1. Lockless serial execution Client 1:
   GET key -> 10 >= 5 ? YES -> DECRBY key 5 (sisa 5) -> Return OK.
2. Next event processed (Client 2):
   GET key -> 5 >= 5 ? YES -> DECRBY key 5 (sisa 0) -> Return OK.
Keduanya sukses tanpa rollback loop!
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Pendaftaran dan Pemanggilan Redis 7 Function
Kode pembuatan library Function (`inventory.lua`):
```lua
#!lua name=InventoryLib
-- Definisi Library: InventoryLib

local function reserve_item(keys, args)
    local item_key = keys[1]
    local requested_qty = tonumber(args[1])

    -- Validasi input
    if not requested_qty or requested_qty <= 0 then
        return redis.error_reply("ERR: Kuantitas harus bernilai numerik positif")
    end

    -- Ambil stok saat ini
    local current_stock = tonumber(redis.call('GET', item_key) or "0")

    if current_stock >= requested_qty then
        -- Mutasi state secara atomik
        redis.call('DECRBY', item_key, requested_qty)
        local remaining = current_stock - requested_qty
        return { "SUCCESS", remaining }
    else
        return { "INSUFFICIENT_STOCK", current_stock }
    end
end

-- Daftarkan fungsi ke engine
redis.register_function('reserve', reserve_item)
```

Perintah pendaftaran via terminal:
```bash
# Load library ke Redis server
redis-cli -p 6379 FUNCTION LOAD "#!lua name=InventoryLib\nlocal function reserve_item(keys, args)\nlocal item_key = keys[1]\nlocal requested_qty = tonumber(args[1])\nif not requested_qty or requested_qty <= 0 then return redis.error_reply('ERR: Kuantitas salah') end\nlocal current_stock = tonumber(redis.call('GET', item_key) or '0')\nif current_stock >= requested_qty then\nredis.call('DECRBY', item_key, requested_qty)\nreturn {'SUCCESS', current_stock - requested_qty}\nelse\nreturn {'INSUFFICIENT_STOCK', current_stock}\nend\nend\nredis.register_function('reserve', reserve_item)"

# Inisialisasi data
redis-cli SET inventory:SKU-990 10

# Eksekusi Function (Argumen: function_name, numkeys, key, arg)
redis-cli FCALL reserve 1 inventory:SKU-990 3
# Output: 1) "SUCCESS" 2) (integer) 7
```

---

### 7.2. Practical Example: Production-Grade Sliding-Window Rate Limiter (Python + Redis)

Arsitektur rate limiter berbasis algoritma sliding-window log menggunakan kombinasi Sorted Set (`ZSET`) via Lua Scripting. Skrip ini menjamin akurasi presisi tinggi tanpa race conditions.

```python
#!/usr/bin/env python3
"""
Rate Limiter Produksi - Implementasi Redis EVALSHA Atomic Engine
"""
import time
import uuid
import redis

SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window_size = tonumber(ARGV[2])
local max_capacity = tonumber(ARGV[3])
local request_id = ARGV[4]

local clear_before = now - window_size

-- 1. Hapus event kadaluarsa di luar sliding window
redis.call('ZREMRANGEBYSCORE', key, '-inf', clear_before)

-- 2. Dapatkan volume request aktif saat ini
local current_requests = redis.call('ZCARD', key)

if current_requests < max_capacity then
    -- 3. Catat request baru dengan skor timestamp epoch (mikrodetik)
    redis.call('ZADD', key, now, request_id)
    -- Pasang dynamic TTL untuk mencegah memory leak
    redis.call('PEXPIRE', key, math.ceil(window_size / 1000))
    return {1, max_capacity - current_requests - 1} -- Allowed, remaining quota
else
    return {0, 0} -- Blocked, 0 remaining
end
"""

class ProductionRateLimiter:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        # Pra-registrasi script ke Redis Script Cache
        self.script_sha = self.redis.script_load(SLIDING_WINDOW_LUA)

    def is_allowed(self, rate_key: str, window_ms: int, max_limit: int) -> tuple[bool, int]:
        now_us = int(time.time() * 1000000) # Epoch microseconds
        req_id = f"{now_us}:{uuid.uuid4().hex[:6]}"

        try:
            allowed, remaining = self.redis.evalsha(
                self.script_sha, 1, rate_key, now_us, window_ms * 1000, max_limit, req_id
            )
            return bool(allowed), remaining
        except redis.exceptions.NoScriptError:
            # Fallback jika Redis di-restart dan script cache hilang
            self.script_sha = self.redis.script_load(SLIDING_WINDOW_LUA)
            allowed, remaining = self.redis.evalsha(
                self.script_sha, 1, rate_key, now_us, window_ms * 1000, max_limit, req_id
            )
            return bool(allowed), remaining

# --- Simulasi Driver ---
if __name__ == "__main__":
    client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    limiter = ProductionRateLimiter(client)

    user_identifier = "user_tenant_0192a"
    limit_key = f"ratelimit:{user_identifier}"
    
    # Kapasitas: Maksimum 5 request per window 2000 ms (2 detik)
    for i in range(1, 8):
        allowed, rem = limiter.is_allowed(limit_key, window_ms=2000, max_limit=5)
        status = "PASSED" if allowed else "BLOCKED (429 Too Many Requests)"
        print(f"Request #{i}: Status={status}, Quota Tersisa={rem}")
        time.sleep(0.2)
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: Flash Sale Tiket Konser Berskala Global (Tier-1 Ticketing Platform)
- **Trafik:** 150.000 requests/second pada pembukaan antrean.
- **Masalah:** Stok tiket hanya 5.000 kursi. Menggunakan arsitektur RDBMS (`SELECT FOR UPDATE`) menyebabkan *connection pool exhaustion*, deadlock antar row database, dan latensi sistem mencapai 18 detik sebelum akhirnya tumbang (*cascading failure*).
- **Kebutuhan Sistem:**
  1. Latensi eksekusi < 5 ms.
  2. Garansi absolut tidak boleh terjadi *overselling* (stok terjual > 5.000).
  3. Mengakomodasi *Fencing Token* untuk reservasi sementara selama 10 menit (jika checkout tidak dibayar, stok kembali otomatis).
  4. Kompatibel dengan **Redis Cluster Multi-Node Sharding**.

### Solusi Arsitektur
Menggunakan Redis Cluster dengan pemanfaatan **Hash Tags** `{...}` untuk memastikan seluruh data transaksi satu venue berada pada hash slot yang sama, dipadukan dengan Redis Function untuk reservasi atomik.

```
Redis Cluster Topology (Master Nodes)
+-----------------------+    +-----------------------+    +-----------------------+
|        Node A         |    |        Node B         |    |        Node C         |
|  Slot 0 - 5460        |    |  Slot 5461 - 10922    |    |  Slot 10923 - 16383   |
|                       |    |                       |    |                       |
|   {CONCERT-99}:STOK   |    |                       |    |                       |
|   {CONCERT-99}:HOLD   |    |                       |    |                       |
|   (Routed via Tag)    |    |                       |    |                       |
+-----------------------+    +-----------------------+    +-----------------------+
```

#### Naskah Function: `fencing_reservation.lua`
```lua
#!lua name=TicketingSystem
-- Engine Reservasi Tiket Atomik dengan Fencing Token dan Timeout

local function reserve_ticket(keys, args)
    -- KEYS[1]: Inventory Key -> {CONCERT-99}:available
    -- KEYS[2]: Hold Set Key  -> {CONCERT-99}:holds
    -- ARGV[1]: User ID
    -- ARGV[2]: Expiration TTL (detik)
    -- ARGV[3]: Current Epoch Timestamp
    
    local inv_key = KEYS[1]
    local hold_key = KEYS[2]
    local user_id = ARGV[1]
    local ttl_sec = tonumber(ARGV[2])
    local now_epoch = tonumber(ARGV[3])
    
    -- Validasi apakah user sudah memiliki active hold
    local existing_hold = redis.call('ZSCORE', hold_key, user_id)
    if existing_hold and tonumber(existing_hold) > now_epoch then
        return { "ALREADY_HELD", "User telah memesan antrean tiket ini" }
    end
    
    local available_stock = tonumber(redis.call('GET', inv_key) or "0")
    
    if available_stock > 0 then
        -- 1. Kurangi inventori tersedia
        redis.call('DECR', inv_key)
        
        -- 2. Masukkan ke holding sorted set dengan masa expire
        local expiry_time = now_epoch + ttl_sec
        redis.call('ZADD', hold_key, expiry_time, user_id)
        
        -- 3. Terbitkan Fencing Token unik berbasis counter monotonic
        local fencing_token = redis.call('INCR', '{CONCERT-99}:fencing_seq')
        
        return { "SUCCESS", fencing_token, expiry_time }
    else
        return { "SOLD_OUT", 0, 0 }
    end
end

redis.register_function('reserve_ticket', reserve_ticket)
```

---

## 9. Trade-offs

```
                  +-----------------------------------+
                  |      Architectural Decision       |
                  |     Server-Side Execution Mode    |
                  +-----------------------------------+
                                    |
            +-----------------------+-----------------------+
            |                                               |
     [ Lua Scripts ]                                 [ Redis 7+ Functions ]
            |                                               |
  +---------+---------+                           +---------+---------+
  |                   |                           |                   |
Pros:               Cons:                       Pros:               Cons:
- Kompatibel        - Cache terhapus            - Persistensi RDB   - Butuh v7.0+
  dengan versi        jika server restart.        & AOF terjamin.   - Syntax setup
  lama (v2.6+).     - Sulit didebug             - Terorganisir        lebih ketat.
- Mudah dibuat        di scale besar.             dalam library.    - Migrasi kode
  scr inline.       - Potensi cross-slot        - Replikasi           eksisting butuh
                      error di cluster.           deterministik.      effort refactor.
```

### Analisis Kritis Karakteristik Produksi:
1. **Performance & Latency:**
   - **Lua/Functions:** Mengeliminasi latensi RTT jaringan secara total untuk multi-step logic.
   - **Risiko Latensi:** Karena dieksekusi secara sinkronus di engine thread utama, script yang berjalan lambat (*looping* besar atau $O(N)$ scanning) akan **membekukan seluruh command server lain**. Latensi P99 sistem dapat melonjak drastis.
2. **Scalability:**
   - Script yang menyentuh lebih dari satu key pada Redis Cluster **wajib** menggunakan *Hash Tag* (misal: `{order:123}:items` dan `{order:123}:status`). Jika tidak, Redis akan mengembalikan error: `CROSSSLOT Keys in request don't hash to the same slot`.
3. **Cost vs Durability:**
   - Eksekusi transaksi berskala tinggi di memori membutuhkan alokasi RAM yang memadai untuk holding state. Kesalahan kalkulasi TTL pada holding token akan menyebabkan data leak dan *eviction pressure* yang tinggi.

---

## 10. Common Mistakes & Troubleshooting

### Skenario 1: `BUSY Redis is busy running a script`
- **Penyebab:** Script Lua berjalan melebihi batas konfigurasi `busy-reply-timeout` (standar: 5000 ms). Klien lain yang mengirim instruksi akan diblokir dan menerima error ini.
- **Troubleshooting & Remediasi:**
  1. Cek command yang sedang berjalan via terminal:
     ```bash
     redis-cli SCRIPT KILL
     ```
     *Catatan: Perintah ini hanya berhasil jika script BELUM memanggil perintah mutasi data (hanya operasi read-only).*
  2. Jika script telah memutasi data, `SCRIPT KILL` ditolak demi menjaga konsistensi state. Solusi darurat satu-satunya adalah mematikan server secara terencana:
     ```bash
     redis-cli SHUTDOWN NOSAVE
     ```
  3. **Pencegahan:** Audit script; hindari perulangan `while true` tanpa exit condition, atau kalkulasi $O(N)$ pada payload besar.

### Skenario 2: `CROSSSLOT Keys in request don't hash to the same slot`
- **Penyebab:** Script Lua atau perintah `MULTI`/`EXEC` dijalankan pada arsitektur Redis Cluster, di mana keys yang diakses terdistribusi pada shard/master node yang berbeda secara fisik.
- **Troubleshooting:**
  - Audit argumen script. Semua key yang dikirimkan ke dalam `KEYS[]` wajib memiliki token kurung kurawal `{...}` yang identik.
  - *Salah:* `KEYS[1] = "user:100"`, `KEYS[2] = "order:500"`
  - *Benar:* `KEYS[1] = "{order:500}:user"`, `KEYS[2] = "{order:500}:details"`

### Skenario 3: Data Inconsistency Akibat Script Crash Parsial
- **Penyebab:** Menggunakan `redis.call()` di tengah script setelah perintah mutasi berhasil dijalankan, lalu operasi berikutnya mengalami failure akibat tipe data yang tidak valid (runtime error).
- **Troubleshooting:**
  - Ingat: Redis **tidak memiliki engine rollback**. Modifikasi sebelum crash tetap tersimpan di memory.
  - Gunakan `redis.pcall()` untuk menangkap error dan lakukan logika kompensasi manual di script, atau lakukan validasi tipe data di baris-baris pertama script sebelum mutasi dimulai.

---

## 11. Best Practices (Production Checklist)

| No | Item Checklist | Status | Catatan Teknis Produksi |
|---|---|:---:|---|
| 1 | **Gunakan Dynamic Keys via KEYS[]** | [ ] | Jangan pernah me-hardcode nama key di dalam string script Lua. Driver clustering memerlukan parameter `KEYS[]` untuk memetakan routing node target. |
| 2 | **Eksplisitkan Read-Only Scripts** | [ ] | Pada Redis 7+, gunakan flag `no-writes` saat load library, atau panggil via `FCALL_RO` agar bisa dirutekan secara aman ke Replicas/Read-only nodes. |
| 3 | **Hindari Logika Non-Deterministik** | [ ] | Dilarang keras memakai fungsi internal Lua yang menghasilkan output acak seperti `math.random()` tanpa seed deterministik, atau membaca jam sistem dari external library secara asinkron. Replikasi Redis Cluster berbasis command execution bisa mengalami *state drift*. |
| 4 | **Tetapkan Parameter Evaluasi Ketat** | [ ] | Pelihara eksekusi script Lua di bawah budget waktu **< 5 milidetik**. Monitor secara konsisten via `redis-cli SLOWLOG GET 10`. |
| 5 | **Gunakan Hash Tags untuk Cluster** | [ ] | Terapkan hashing grouping `{tenant_id:entity_id}` pada seluruh key multi-transaksi. |
| 6 | **Handle NOSCRIPT Exception** | [ ] | Pada sisi client driver, selalu tangani *exception* `NOSCRIPT`. Jika error muncul, tangkap lalu jalankan sequence `SCRIPT LOAD` secara on-the-fly sebelum retry. |

---

## 12. Hands-on Practice

Dalam latihan ini, Anda akan membangun skrip shell automated dan engine Lua untuk memverifikasi eksekusi Function serta mekanisme penolakan concurrency.

### Direktori Kerja: `hands-on/m02/`

```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
```

### Langkah 1: Buat Library Redis 7 (`bank_lib.lua`)
Simpan file ini dengan nama `bank_lib.lua`:

```lua
#!lua name=BankingEngine
-- Library Transfer Dana Antar Rekening Atomik

local function transfer(keys, args)
    local from_account = keys[1]
    local to_account = keys[2]
    local amount = tonumber(args[1])

    if not amount or amount <= 0 then
        return redis.error_reply("ERR: Nominal transfer harus lebih besar dari 0")
    end

    -- Validasi keberadaan dan saldo pengirim
    local from_bal = tonumber(redis.call('GET', from_account) or "0")
    if from_bal < amount then
        return { "FAILED_INSUFFICIENT_FUNDS", from_bal }
    end

    -- Eksekusi Mutasi Atomik
    redis.call('DECRBY', from_account, amount)
    redis.call('INCRBY', to_account, amount)

    local updated_from_bal = from_bal - amount
    local updated_to_bal = tonumber(redis.call('GET', to_account))

    return { "SUCCESS", updated_from_bal, updated_to_bal }
end

redis.register_function('transfer', transfer)
```

### Langkah 2: Deploy Script Automasi Pengujian (`test_runner.sh`)
Simpan file ini dengan nama `test_runner.sh`:

```bash
#!/usr/bin/env bash
set -e

REDIS_HOST="127.0.0.1"
REDIS_PORT="6379"

echo "=== 1. Inisialisasi Lingkungan Redis ==="
redis-cli -h $REDIS_HOST -p $REDIS_PORT FLUSHALL
redis-cli -h $REDIS_HOST -p $REDIS_PORT FUNCTION FLUSH

echo "=== 2. Mendaftarkan Redis 7 Function Library ==="
FUNCTION_PAYLOAD=$(cat bank_lib.lua)
redis-cli -h $REDIS_HOST -p $REDIS_PORT FUNCTION LOAD "$FUNCTION_PAYLOAD"

echo "=== 3. Setup Akun Percobaan (Gunakan Hash Tag {bank}) ==="
# Hash Tag {bank} memastikan kedua key dialokasikan ke hash slot yang identik di Redis Cluster
redis-cli -h $REDIS_HOST -p $REDIS_PORT SET "{bank}:acc:alice" 500
redis-cli -h $REDIS_HOST -p $REDIS_PORT SET "{bank}:acc:bob" 100

echo "=== 4. Tes Skenario A: Transfer Valid (200 Unit) ==="
redis-cli -h $REDIS_HOST -p $REDIS_PORT FCALL transfer 2 "{bank}:acc:alice" "{bank}:acc:bob" 200

echo "=== 5. Tes Skenario B: Transfer Melebihi Saldo (400 Unit) ==="
redis-cli -h $REDIS_HOST -p $REDIS_PORT FCALL transfer 2 "{bank}:acc:alice" "{bank}:acc:bob" 400

echo "=== 6. Cek Saldo Akhir ==="
echo -n "Saldo Alice: "
redis-cli -h $REDIS_HOST -p $REDIS_PORT GET "{bank}:acc:alice"
echo -n "Saldo Bob: "
redis-cli -h $REDIS_HOST -p $REDIS_PORT GET "{bank}:acc:bob"

echo "=== Hands-on Berhasil Diselesaikan Tanpa Kebocoran Data! ==="
```

### Langkah 3: Eksekusi dan Verifikasi
Jalankan di terminal Anda:
```bash
chmod +x test_runner.sh
./test_runner.sh
```

---

## 13. Exercise

### Level Easy
Tuliskan blok instruksi primitif Redis (`MULTI`, `WATCH`, `EXEC`) murni via Redis CLI untuk mengimplementasikan counter yang hanya dapat ditambah (`INCRBY`) jika nilainya saat ini masih berada di bawah angka 50. Batalkan transaksi jika nilainya sudah melampaui limit.

### Level Medium
Kembangkan script Lua sederhana untuk membersihkan (eviction) session keys yang memiliki status `inactive`. Script menerima satu key berupa `HASH` session (misal: `session:user_123`). Jika field `last_active` (epoch second) lebih lama dari 3600 detik dibandingkan argumen `current_time`, hapus key hash tersebut secara permanen (`DEL`), jika tidak, pasang dynamic expire 1800 detik.

### Level Hard
Rancang Redis Function bernama `idempotent_consume`. Fungsi ini harus menerima parameter:
- `KEYS[1]`: Stream / Queue Key
- `KEYS[2]`: Processed Tracking Set Key
- `ARGV[1]`: Unique Event ID
- `ARGV[2]`: Payload Event (JSON string)

Fungsi harus:
1. Memeriksa apakah `Event ID` sudah ada di dalam Processed Tracking Set (`SISMEMBER`).
2. Jika SUDAH ADA: Mengembalikan status `"DUPLICATE_IGNORED"`.
3. Jika BELUM ADA: Menyimpan payload ke List/Queue, memasukkan ID ke Tracking Set, menyetel TTL 24 jam pada Tracking Set (jika belum ada), dan mengembalikan status `"PROCESSED"`.
4. Semua operasi ini wajib diselesaikan secara atomik tanpa celah interupsi konkurensi.

---

## 14. Challenge

### Studi Kasus: "Distributed Deadlock-Free High-Contention Flash-Ticket Reservation"
Sebuah perusahaan transportasi kereta api cepat nasional menghadapi masalah sistemik saat tiket mudik dibuka. Ratusan ribu penumpang memesan rute antarkota yang sama pada detik yang sama. 

Spesifikasi Gerbong:
- 1 Kereta = 8 Gerbong.
- Setiap Gerbong = 80 Nomor Kursi (Total 640 kursi per nomor KA).
- Key layout di redis cluster: `{KA-ARGO-77}:carriage:1` s.d `{KA-ARGO-77}:carriage:8` (format bitfield atau hash).

**Persyaratan Tantangan:**
1. Desain arsitektur script Redis Function yang mampu memproses alokasi pemilihan kursi dinamis:
   - Pengguna meminta kuantitas kursi (1 sampai 4 kursi berurutan).
   - Script harus mencari kursi yang bersebelahan dalam gerbong yang sama secara atomik.
   - Jika kursi bersebelahan tidak ditemukan, kembalikan alokasi terpisah (non-contiguous) yang masih tersedia.
   - Jika total sisa kursi < permintaan, gagalkan transaksi secara bersih tanpa mengubah state.
2. Script harus memiliki batas latensi eksekusi maksimal **under 3 ms** di bawah beban load concurrency 20.000 QPS.
3. Berikan rincian proteksi terhadap skenario: Node Master pengelola `{KA-ARGO-77}` mendadak mati (failover) saat script sedang berjalan di tengah jalan. Bagaimana klien mendeteksi apakah pemesanan berhasil dicatat atau hilang saat failover ke Replica node? (Petunjuk: Integrasi *Idempotency Token* & *WAL/Outbox Pattern*).

---

## 15. Quiz Evaluasi Pemahaman

### 15.1. Pertanyaan Basic
1. Mengapa Redis tidak menyediakan mekanisme *rollback* otomatis ketika sebuah instruksi di dalam blok `MULTI`/`EXEC` mengalami kesalahan runtime (misalnya operasi `INCR` pada key bertipe string non-angka)?
2. Apa perbedaan fungsional utama antara perintah `redis.call()` dan `redis.pcall()` di dalam script Lua?
3. Mengapa eksekusi script Lua yang membutuhkan waktu berjalan 2 detik dianggap sebagai masalah kritis (*antipattern*) pada arsitektur Redis?
4. Apa fungsi dari perintah `SCRIPT LOAD` dan bagaimana perannya dalam menekan pemborosan bandwidth jaringan?
5. Mengapa perintah `WATCH` digolongkan ke dalam mekanisme *Optimistic Concurrency Control* (OCC) dan bukan *Pessimistic Concurrency Control*?

### 15.2. Pertanyaan Intermediate
6. Bagaimana cara kerja internal penanganan error pada transaksi Redis saat terjadi kesalahan sintaksis perintah (*syntax error*) pada saat client mem-buffer perintah setelah `MULTI`?
7. Jelaskan bagaimana mekanisme replikasi Redis 7+ Functions bekerja dari node Master ke Replica, dan mengapa metode ini lebih unggul dibandingkan replikasi script lama pada versi 2.6?
8. Bagaimana implementasi *Hash Tag* `{...}` menyelesaikan kendala error `CROSSSLOT` pada lingkungan Redis Cluster yang menjalankan transaksi multi-key?
9. Apa yang terjadi jika sebuah client mengeksekusi `SCRIPT KILL` terhadap script Lua yang telah memanggil instruksi mutasi `redis.call('SET', ...)`?
10. Pada skenario konkurensi ekstrem, mengapa pola `WATCH` / `EXEC` loop sering kali mengalami degradasi throughput (*live-lock / starvation*) dibandingkan dengan eksekusi atomik server-side Lua?

### 15.3. Skenario Kasus Produksi
11. **Skenario Insiden Latensi:** Sistem monitoring mendeteksi lonjakan latency (P99 > 3000ms) pada Redis cluster. Log aplikasi dibanjiri error `BUSY Redis is busy running a script`. Bagaimana langkah operasional terstruktur untuk mengidentifikasi skrip penyebab tanpa me-restart server Redis utama?
12. **Skenario Distributed Lock Leak:** Sebuah worker microservice mengambil *Distributed Lock* menggunakan Lua Script yang mengimplementasikan algoritma Redlock. Worker tersebut mengalami *Out Of Memory (OOM) killed* tepat setelah Redis mengeksekusi locking namun sebelum TTL disetel. Bagaimana cara memastikan ketiadaan *deadlock* permanen tanpa intervensi manual?
13. **Skenario Split-Brain / Failover:** Dua client (Client X dan Client Y) menjalankan Function reservasi inventori. Master mengalami crash tepat saat instruksi Function Client X selesai diproses di memori, namun replikasi asinkron ke Replica belum terjadi. Sentinel/Cluster mempromosikan Replica menjadi Master baru. Client Y mengirim permintaan yang sama ke Master baru. Jelaskan konsekuensi integritas datanya dan arsitektur mitigasi yang wajib dipasang.

---

### Jawaban Evaluasi Pemahaman

#### Kunci Jawaban Pertanyaan Basic
1. **Ketiadaan Rollback:** Pembuat Redis (Salvatore Sanfilippo) merancang Redis dengan filosofi kesederhanaan internal dan performa tinggi. Kesalahan runtime diakibatkan oleh bug logika pemrograman aplikasi (misal salah tipe data), bukan kegagalan disk/hardware. Menghapus rollback membebaskan Redis dari overhead manajemen *undo log* yang kompleks dan memakan memori.
2. **`redis.call()` vs `redis.pcall()`:** `redis.call()` akan langsung menghentikan script dan melempar *fatal error* kembali ke client ketika sebuah perintah gagal. Sebaliknya, `redis.pcall()` menangkap error tersebut dalam format tabel Lua, sehingga programmer dapat mengevaluasi error dan melanjutkan sisa eksekusi secara kondisional.
3. **Bahaya Script 2 Detik:** Karena Redis single-threaded, script 2 detik memblokir total *event loop*. Ribuan perintah dari ratusan klien lain akan tertahan di buffer koneksi TCP, memicu timeout massal di sisi backend microservices.
4. **`SCRIPT LOAD` & Bandwidth:** `SCRIPT LOAD` mengirimkan source code script sekali untuk dikompilasi di memory Redis, menghasilkan digest SHA-1 40 karakter. Untuk pemanggilan selanjutnya, klien hanya mengirimkan `EVALSHA <sha1>` yang sangat kecil, menghemat bandwidth jaringan daripada mengirimkan puluhan baris string script berulang-ulang.
5. **OCC pada `WATCH`:** Mengapa OCC? Karena Redis tidak mengunci (lock) record/key secara eksklusif. Klien lain bebas membaca dan menulis data key yang sedang di-watch. Redis hanya melakukan verifikasi di akhir (fase validasi saat `EXEC`) untuk melihat apakah state berubah (*optimistic* bahwa benturan jarang terjadi).

#### Kunci Jawaban Pertanyaan Intermediate
6. **Syntax Error di Antrean `MULTI`:** Sejak Redis 2.6.5, jika terjadi kesalahan parsing (misal penamaan command typo atau argumen kurang) saat mem-buffer perintah, Redis mencatat flag error pada state koneksi. Saat `EXEC` dipanggil, Redis **menolak menjalankan seluruh antrean** dan mengembalikan error `EXECABORT Transaction discarded because of previous errors.`.
7. **Replikasi Redis 7 Functions:** Script Lua lama direplikasi secara ekspresi teks atau mutasi efek samping command. Redis 7 Functions menduplikasi source library secara penuh ke dalam persistence file (RDB/AOF) dan mereplikasikannya ke replica node via stream replikasi sebagai metadata library, memastikan byte-per-byte keselarasan kode antar node secara terstruktur dan terisolasi.
8. **Hash Tag `{...}`:** Redis Cluster menghitung CRC16 dari nama key untuk menentukan penempatan slot (0-16383). Jika string memiliki tanda kurung kurawal, misalnya `{cust:10}:profile` dan `{cust:10}:orders`, hanya teks di dalam kurung kurawal (`cust:10`) yang di-hash. Hasilnya, kedua key dipaksa berada pada satu hash slot yang sama di node yang sama, menghindari error `CROSSSLOT`.
9. **`SCRIPT KILL` pada State Termutasi:** Redis akan **menolak** perintah `SCRIPT KILL` dan mengembalikan respons error: `UNKILLABLE You cannot kill a script with write operations...`. Hal ini dilakukan guna mencegah kondisi memori inkonsisten (setengah termutasi). Solusinya adalah menjalankan `SHUTDOWN NOSAVE` atau membiarkan script selesai.
10. **Starvation pada `WATCH`:** Jika 100 thread bersaing memodifikasi satu key, 1 thread berhasil melakukan commit, sedangkan 99 thread lainnya ter-abort oleh `WATCH`. Jika ke-99 thread melakukan retry secara agresif, contention meningkat eksponensial, mengakibatkan latensi tinggi dan mayoritas resource CPU habis hanya untuk retry loop yang gagal terus-menerus.

#### Kunci Jawaban Skenario Kasus Produksi
11. **Skenario Penanganan Latensi:**
    - Hubungi instance via terminal non-blocking: jalankan `redis-cli SLOWLOG GET 5` untuk melihat SHA-1 script yang sedang/baru saja memakan durasi abnormal.
    - Cek status eksekusi menggunakan `redis-cli SCRIPT KILL` secara aman (jika skrip read-only, eksekusi akan langsung dibatalkan).
    - Lakukan profiling stack trace via `redis-cli --latency` atau inspeksi `INFO commandstats` untuk mengidentifikasi apakah utilisasi CPU terkonsentrasi pada `eval` / `fcall`.
    - Perbaiki bug di layer aplikasi dan bersihkan antrean worker yang membombardir script tersebut.
12. **Skenario Locking OOM Leak:**
    - Distributed Lock wajib diakuisisi menggunakan atomic command: `SET lock:resource random_worker_token NX PX 30000` (menggabungkan lock acquisition dan set TTL dalam 1 atomic CPU cycle).
    - Memisahkan akuisisi lock dan setting TTL ke dalam dua perintah terpisah adalah *flaw* desain fatal. Dengan penggabungan `NX PX`, jika proses worker mati mendadak (OOM), kunci akan kedaluwarsa secara otomatis via internal TTL Redis tanpa menyebabkan dead-lock abadi.
13. **Skenario Failover Inconsistency:**
    - **Dampak:** Terjadi *data loss* (reservasi Client X hilang karena asinkron replikasi ke Replica belum selesai saat Master crash), membuka peluang *double-booking* saat Client Y mengeksekusi request di Master baru.
    - **Mitigasi:**
      1. Terapkan perintah `WAIT 1 1000` pada transaksi kritis untuk memverifikasi bahwa mutasi berhasil disalin ke minimal 1 replika secara semi-sinkron sebelum mengembalikan respons sukses ke client.
      2. Pasang sistem verifikasi rekonsiliasi sekunder (Outbox pattern pada database transaksional ACID di background) yang memvalidasi kesesuaian tiket dan payment payload secara definitif sebelum tiket final diterbitkan.

---

## 16. Summary
- Konkurensi Redis berpusat pada **single-threaded sequential execution** berbasis event-loop, yang secara alamiah mengeliminasi *internal low-level data race conditions*, namun tetap rentan terhadap *application-level race condition* pada skenario Read-Modify-Write.
- Blok transaksi `MULTI`/`EXEC` menyediakan isolasi dasar, tetapi memiliki kelemahan mendasar: **tidak mendukung logika kondisional runtime, ketiadaan rollback, dan potensi abort tinggi jika digabung dengan `WATCH` pada beban kontensi tinggi**.
- **Lua Scripting dan Redis 7+ Functions** menjadi pilar utama eksekusi atomik server-side berskala enterprise. Seluruh blok kode dieksekusi secara terisolasi tanpa interupsi, mengubah pola validasi dari spekulatif (OCC) menjadi deterministik.
- Pada arsitektur terdistribusi seperti Redis Cluster, server-side scripting menuntut kehati-hatian tingkat tinggi: pemanfaatan **Hash Tags** untuk menghindari `CROSSSLOT` error, pembatasan ketat terhadap eksekusi command berat guna mencegah pembekuan *aeEventLoop*, serta penulisan script yang murni **deterministik**.