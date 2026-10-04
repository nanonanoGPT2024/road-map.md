# Kurikulum Enterprise: MongoDB Internals, Distributed Architecture & Production Engineering
**Kategori:** 04-Backend-and-Database  
**Bab 01:** BAB-01-Fondasi-dan-Arsitektur  
**Modul:** Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi  
**Target Tingkat Kemahiran:** Senior Software Engineer, Principal Database Reliability Engineer (DBRE), Enterprise System Architect  

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Mendekonstruksi WiredTiger Engine Internals**: Menganalisis alokasi *hazard pointers*, mekanisme *cache eviction* (dirty vs. clean pages), *write-ahead logging* (journaling), serta algoritma *checkpointing* berbasis B-Tree di tingkat disk block.
2. **Menguasai Konsensus Replikasi & Fault Tolerance**: Mendiagnosis mekanisme konsensus modifikasi Raft (*election protocol v1*), pergerakan *oplog v2*, penanganan partisi jaringan, hingga resolusi *rollback directory* secara deterministik.
3. **Merancang Topologi Horisontal (Sharded Cluster)**: Mengonfigurasi arsitektur sharding skala enterprise berbasis *range* dan *hashed partitioning*, mengontrol kerja *balancer*, mencegah *jumbo chunks*, dan mengoptimalkan performa query melalui perutean `mongos`.
4. **Menerapkan Distributed ACID Transactions & Consistency Guarantees**: Mengimplementasikan kombinasi *Read Concern* (`local`, `majority`, `snapshot`, `linearizable`) dan *Write Concern* (`w:majority`, `j:true`) bersamaan dengan transaksi multi-dokumen terdistribusi berbasis *two-phase commit*.
5. **Melakukan Performance Tuning & Troubleshooting Tingkat Lanjut**: Melakukan profiling metrik *Full-Time Diagnostic Data Capture* (FTDC), mengeliminasi *ticket exhaustion* pada WiredTiger, serta menata kernel OS Linux khusus untuk database berlatensi rendah.

---

## 2. Prerequisite

Sebelum mempelajari materi ini, peserta wajib memahami:
* Fondasi model data BSON dan pemodelan skema dokumen relasional/non-relasional.
* Dasar administrasi Linux: manipulasi memori virtual (`vm.dirty_ratio`, `Transparent Huge Pages`), POSIX threads, IOPS, serta partisi sistem berkas XFS.
* Konsep dasar protokol jaringan, soket TCP/IP, dan model konsistensi terdistribusi (teorema CAP dan PACELC).
* Sintaks dasar kueri MongoDB dan manipulasi indeks B-Tree.

---

## 3. Concept & Internal Architecture

### 3.1. WiredTiger Storage Engine Deep Dive

WiredTiger adalah storage engine *default* MongoDB sejak versi 3.2. Operasional internal WiredTiger berpusat pada pemisahan antara memori *in-cache* dan penyimpanan persisten di disk.

```
+-----------------------------------------------------------------------+
|                         WIREDTIGER STORAGE ENGINE                     |
|                                                                       |
|  +-----------------------------------------------------------------+  |
|  |                    WiredTiger Cache (RAM)                       |  |
|  |                                                                 |  |
|  |   [Clean Page]       [Dirty Page] (Modified)                    |  |
|  |     (B-Tree)          +-- Hazard Pointers (Lock-free ref count) |  |
|  |                       +-- In-memory updates (SkipList / WT_ROW) |  |
|  +-----------------------------------------------------------------+  |
|             |                                        |                |
|      Eviction Server                         Checkpoint Thread        |
|     (Threads sweep dirty                     (Flushes memory snapshot |
|      pages to disk)                           to disk every 60s/2GB)  |
|             |                                        |                |
|             v                                        v                |
|  +-----------------------------------+     +-----------------------+  |
|  |           Block Manager           |     |     WiredTiger.wt     |  |
|  |  (Compression: Snappy/Zlib/zstd)  |     |   Root metadata &     |  |
|  +-----------------------------------+     |   B-tree allocations  |  |
|             |                              +-----------------------+  |
|             v                                                         |
|  +---------------------+                                              |
|  |   Data Files (*.wt) |                                              |
|  +---------------------+                                              |
|                                                                       |
|  Write Path (Journaling):                                             |
|  Client Write ---> WT Cache (WAL Buffer) ---> Journal Log Disk        |
|                                                (Group Commit / fsync) |
+-----------------------------------------------------------------------+
```

#### Cache Architecture & Hazard Pointers
WiredTiger tidak menggunakan algoritma penguncian tradisional (seperti POSIX *mutex lock*) pada setiap pembacaan simpul B-Tree. Untuk mencapai *throughput* konkurensi ekstrem, engine ini menerapkan pola **Hazard Pointers**:
* Ketika sebuah thread mengeksekusi operasi baca pada sebuah halaman memori (*page*), thread tersebut mencatat pointer halaman ke dalam slot hazard pointer thread-local.
* Thread lain yang menjalankan proses pembersihan (*eviction server*) tidak boleh membebaskan atau merealokasi memori fisik halaman tersebut selama nilai hazard pointer masih aktif mereferensikannya.
* Strategi *lock-free reading* ini meminimalkan overhead *context switching* antar thread, namun dapat memicu penipisan alokasi tiket (*ticket exhaustion*) jika terjadi query lambat yang menahan hazard pointer terlalu lama.

#### Cache Eviction Algorithms
Kapasitas memori WiredTiger secara default diset sebesar:
$$\text{WT Cache Size} = 0.50 \times (\text{RAM Total} - 1\text{ GB})$$

Siklus hidup alokasi memori diatur oleh thread *eviction*:
* **Clean Page Eviction**: Jika pemakaian memori melampaui batas batas ambang bersih (*default*: 80%), WiredTiger membuang halaman yang belum termodifikasi dari RAM tanpa operasi I/O disk.
* **Dirty Page Eviction**: Jika modifikasi (*dirty pages*) mencapai batas tertentu (*default*: 20% dari ukuran cache), engine menugaskan thread latar belakang untuk melakukan kompresi dan menulis data halaman ke media persisten (*reconciliation process*).
* **Application Thread Eviction**: Jika dirty pages menyentuh ambang batas kritis (biasanya 95%), thread pemanggil (koneksi aplikasi klien) akan dialihkan fungsinya untuk membantu proses *eviction*. Hal ini berdampak langsung pada lonjakan latensi kueri secara eksponensial.

#### Checkpointing & Write-Ahead Logging (Journaling)
WiredTiger menjamin persistensi data melalui dua mekanisme komplementer:
1. **Checkpointing**: Proses pembuatan *snapshot* konsisten dari seluruh basis data ke dalam disk. Berjalan secara periodik setiap 60 detik atau jika penulisan log transaksi telah mencapai akumulasi 2 GB. Checkpoint membentuk *recovery point objective* (RPO) minimum.
2. **Journaling (WAL)**: Semua mutasi data dicatat ke dalam log journal disk sebelum *dirty page* ditulis ke berkas basis data utama (`*.wt`). Format journal memanfaatkan teknik *group commit*, di mana puluhan transaksi aplikasi digabungkan dalam satu kali panggilan sistem `fsync()` untuk meminimalkan *write amplification*.

---

### 3.2. Replication Mechanics & Consensus Protocols

Topologi Replica Set MongoDB menerapkan variasi dari algoritma konsensus **Raft** yang dimodifikasi (secara historis berevolusi dari protokol Paxos).

#### Election Protocol & Priority
* Node sekunder mengeksekusi pemantauan *heartbeat* secara periodik (setiap 2000 ms).
* Jika node Primary tidak merespons dalam durasi `electionTimeoutMillis` (default: 10000 ms), Secondary beralih status menjadi *Candidate* dan menginisiasi pemilihan (*election*).
* Node kandidat meminta pemungutan suara (*votes*). Node lain hanya akan memberikan suara persetujuan jika:
  1. Waktu log transaksi kandidat (*oplog entry timestamp*) setara atau lebih baru daripada miliknya.
  2. Kandidat memenuhi kriteria prioritas (`priority` > 0).
  3. Node pemilih belum memberikan suara kepada kandidat lain dalam periode pemilihan (*term*) yang sama.

#### Oplog v2 Architecture
Oplog (Operations Log) adalah *capped collection* khusus (`local.oplog.rs`) yang menyimpan rekaman mutasi data secara logis. Karakteristik teknis Oplog v2 meliputi:
* **Idempotensi**: Setiap operasi diubah formatnya menjadi mutasi mutlak. Sebagai contoh, operasi `$inc` pada dokumen akan direkam ke oplog dalam wujud operator `$set` yang memuat nilai akhir hasil kalkulasi.
* **Wall Clock Times & Lamport Clocks**: Setiap operasi diberi label stempel waktu hibrida (*hybrid logical clock* atau `ts: Timestamp(seconds, increment)`) untuk memastikan pengurutan kejadian secara kausal pada seluruh sistem terdistribusi.

```
+-----------------------------------------------------------------------------------+
|               DISTRIBUTED REPLICATION & ROLLBACK MECHANICS                        |
|                                                                                   |
|  Primary (Node A)               Secondary (Node B)         Secondary (Node C)     |
|   Term 1                          Term 1                     Term 1               |
|  [Op 101][Op 102]                [Op 101]                   [Op 101]              |
|        |                               |                          |               |
|        X (Network Partition isolates Node A)                      |               |
|        |                               |                          |               |
|        |                         (Election runs: Node B becomes Primary, Term 2)  |
|  [Op 103 (Unreplicated)]               |                          |               |
|        |                         [Op 102B]                  [Op 102B]             |
|        |                               \                          /               |
|        |                                (Network Restored: Node A reconnects)     |
|        |                                                                          |
|        v                                                                          |
|  Node A mendeteksi divergens: Common Point = Op 101                               |
|  1. Node A mengekstraksi Op 103 dari WiredTiger storage engine                    |
|  2. Menulis Op 103 ke disk: /data/db/rollback/<collection_uuid>.bson              |
|  3. Memutar balik state engine ke Op 101                                          |
|  4. Mengambil dan mengaplikasikan Op 102B dari Node B (Catchup Phase)             |
+-----------------------------------------------------------------------------------+
```

#### Rollback Processing
Jika Primary menerima penulisan yang belum terdistribusi ke quorum (`w:1`) lalu mengalami kegagalan, node lain akan dipromosikan. Ketika mantan Primary tersebut aktif kembali, terjadi proses rekonsiliasi divergensi data:
1. Node memindai oplog untuk menemukan *Common Point* (titik percabangan terakhir yang sah).
2. Dokumen yang telah dimutasi namun berada di luar *Common Point* akan diekstraksi langsung dari storage engine.
3. Dokumen tersebut diubah menjadi berkas BSON fisik dan disimpan di direktori `rollback/`.
4. Node menyelaraskan rantai oplog dari Primary aktif (*catch-up phase*).

---

### 3.3. Sharding Architecture & Internals

Arsitektur sharding mendistribusikan dataset ke dalam sejumlah replica set independen. Komponen utamanya terdiri dari:
1. **mongos (Query Router)**: Komponen *stateless* yang memetakan kueri dari aplikasi langsung ke shard target menggunakan metadata routing.
2. **Config Database (Config Server Replica Set / CSRS)**: Menyimpan metadata routing, konfigurasi zona, rentang chunk, dan log audit cluster. Bersifat highly-consistent (`w:majority`).
3. **Shard (Data Nodes)**: Tiap shard merupakan Replica Set independen yang menyimpan fraksi partisi data.

```
                      +-------------------+
                      | Application Client|
                      +-------------------+
                                |
                   (Pool of TCP Connections)
                                v
                      +-------------------+
                      |      mongos       |
                      |  (Routing Layer)  |
                      +-------------------+
                       /        |        \
    (Metadata Cache)  /         |         \  (Scatter-Gather or Targeted)
                     v          v          v
          +------------+  +------------+  +------------+
          | Config DB  |  |  Shard 01  |  |  Shard 02  |
          |   (CSRS)   |  | (Repl. Set)|  | (Repl. Set)|
          +------------+  +------------+  +------------+
                                ^                ^
                                |--- Chunk ------|
                                  Migration
                                  (Balancer)
```

#### Chunk Slicing & The Balancer
Data di dalam shard dikelompokkan ke dalam unit logis bernama **Chunks**. Default ukuran chunk adalah 64 MB.
* **Auto-Split Process**: Ketika penulisan data menyebabkan ukuran chunk melampaui ambang batas batas (misalnya 64 MB), engine `mongos` memicu kalkulasi *split points* untuk memecah chunk menjadi dua rentang (*range*) terpisah secara atomik di dalam metadata Config Server.
* **Balancer Thread**: Sebuah daemon internal yang mengevaluasi disparitas jumlah chunk antar shard. Jika migrasi dibutuhkan, primary shard sumber mengeksekusi perintah internal `moveChunk`:
  1. Chunk disalin ke shard tujuan via replikasi streaming.
  2. Selama proses penyalinan, shard sumber tetap melayani penulisan dan mencatat perubahan transien ke dalam log *transfer buffer*.
  3. Shard tujuan mengaplikasikan *transfer buffer*.
  4. Shard tujuan memvalidasi sinkronisasi, lalu memperbarui metadata di Config Server via two-phase commit.

#### Range-based vs Hashed Partitioning
* **Range-based Sharding**:
  * Membagi data berdasarkan domain nilai riil dari Shard Key.
  * *Kelebihan*: Sangat efisien untuk *range queries* (`$gte`, `$lte`). Query dapat dialokasikan langsung ke satu shard (*targeted query*).
  * *Kekurangan*: Rentan terhadap *hotspotting* jika menggunakan nilai yang monoton meningkat seperti timestamp atau UUID terurut (*Monotonic Ingestion Saturation*).
* **Hashed Sharding**:
  * Menggunakan kalkulasi hashing MD5 dari nilai Shard Key untuk menentukan lokasi chunk secara acak namun deterministik.
  * *Kelebihan*: Distribusi penulisan merata secara absolut ke seluruh shard.
  * *Kekurangan*: Memaksa operasi *scatter-gather* pada pembacaan rentang, di mana `mongos` harus memancarkan kueri ke seluruh shard yang ada lalu menggabungkan hasilnya di memori.

---

### 3.4. Distributed Read & Write Concerns

Model konsistensi MongoDB dikontrol oleh parameter *Read Concern* dan *Write Concern*:

| Write Concern | Mekanisme Eksekusi | Tingkat Ketahanan Durabilitas |
| :--- | :--- | :--- |
| `w: 1` | Mengakui penulisan segera setelah dieksekusi di memori/cache node Primary lokal. | Rendah. Berpotensi kehilangan data jika Primary mengalami crash sebelum data tereplikasi. |
| `w: majority` | Mengakui penulisan setelah data direplikasi ke mayoritas node voting dalam Replica Set. | Sangat Tinggi. Menjamin resistensi terhadap rollback pada kegagalan simpul. |
| `j: true` | Memaksa proses sinkronisasi log transaksi (*fsync*) ke disk journal sebelum mengembalikan respons. | Maksimal. Menjamin persistensi penuh bahkan jika terjadi kegagalan daya serentak. |

| Read Concern | Mekanisme Eksekusi | Fenomena Konsistensi |
| :--- | :--- | :--- |
| `local` | Mengembalikan snapshot data node terkini tanpa validasi konsensus quorum. | Rentan terhadap *dirty read* jika node mengalami partisi dan data di-rollback. |
| `majority` | Membaca data dari snapshot memori yang telah diakui oleh mayoritas node voting. | Bebas dari skenario rollback data. |
| `linearizable` | Memaksa node Primary memvalidasi posisinya dengan mengirimkan probe *heartbeat* ke mayoritas node sebelum merespons. | Menghindari *stale reads* pada kondisi split-brain parsial. Latensi sangat tinggi. |
| `snapshot` | Mengambil data berdasarkan *Global Cluster Time* terpadu menggunakan timestamp WiredTiger. | Mengisolasi transaksi multi-dokumen (setara ACID serializability). |

---

## 4. Why & What

### Mengapa Memahami Internals Sangat Krusial?
Sebagian besar implementasi MongoDB tingkat produksi mengalami degradasi performa bukan karena keterbatasan teknologi database, melainkan karena kesalahan fundamental dalam pemahaman arsitektur internal:
1. **Cache thrashing**: Salah mengalokasikan RAM sehingga WiredTiger terbebani siklus *dirty page eviction* secara konstan, memicu IOPS disk 100%.
2. **Scatter-Gather Disasters**: Memilih *shard key* dengan kardinalitas rendah yang memicu kueri global ke seluruh shard alih-alih *targeted routing*.
3. **Ghost Writes & Data Divergence**: Menjalankan transaksi finansial menggunakan `w:1` dan `readConcern: "local"`, yang memicu anomali hilangnya pencatatan saat terjadi pergantian node (*failover*).

---

## 5. How (Workflow Detail)

### Alur Eksekusi Penulisan (Write Path) - Distributed Quorum

```
[Client] 
   |
   | 1. Perintah Write (w:majority, j:true)
   v
[mongos] 
   |
   | 2. Resolusi Routing via Cached Chunk Metadata
   v
[Primary mongod]
   |-- 3. Mengambil Ticket Penulisan WiredTiger (wt_ticket_acquire)
   |-- 4. Modifikasi In-Memory B-Tree (WT Cache)
   |-- 5. Penulisan ke WiredTiger WAL / Journal Log Buffer
   |-- 6. Trigger fsync() pada Journal Disk File (j:true)
   |-- 7. Menambahkan entri ke local.oplog.rs
   |-- 8. Menyerahkan kembali Ticket Penulisan (wt_ticket_release)
   |
   |-- 9. Replikasi Streaming (Tailable Cursor Push/Pull)
   |-----------------------------+
   |                             |
   v                             v
[Secondary Node 1]         [Secondary Node 2]
   |-- 10. Terapkan Oplog     |-- 10. Terapkan Oplog
   |-- 11. Kirim ACK           |-- 11. Kirim ACK
   +-----------------------------+
   |
   v (Mayoritas Quorum Tercapai: 1 Primary + 1 Secondary dari 3 nodes)
[Primary mongod]
   |
   | 12. Kirim Write Result OK ke mongos
   v
[mongos]
   |
   | 13. Kirim Respons Berhasil ke Aplikasi
   v
[Client]
```

### Alur Eksekusi Transaksi Multi-Dokumen Terdistribusi
1. **Inisiasi Sesi**: Klien menginisiasi sesi logis (`ClientSession`) yang menghasilkan identifier global transaksional (`lsid`) dan `TxnNumber`.
2. **Snapshot Allocation**: Primary mengalokasikan *read timestamp* WiredTiger berdasarkan Lamport Clock kluster (`clusterTime`).
3. **Two-Phase Commit Coordination**:
   * **Prepare Phase**: Jika transaksi melibatkan lebih dari satu shard, *mongos* bertindak sebagai koordinator transaksi. Koordinator mengirim perintah `prepareTransaction` ke semua shard partisipan. Masing-masing shard mengunci dokumen di tingkat storage engine dan mencatat state `prepared` ke oplog.
   * **Commit Phase**: Setelah seluruh partisipan merespons kesiapan (*prepared*), koordinator menulis entri `commitTransaction` ke Config Server lalu menyiarkan perintah eksekusi komit ke semua shard.

---

## 6. Analogy & Diagram ASCII

### Analogi Sederhana: Sistem Restoran Bintang Lima

* **WiredTiger Cache**: Meja *kitchen prep* koki. Bahan makanan (data) ditaruh di sini agar bisa diracik dengan cepat tanpa bolak-balik ke gudang pendingin.
* **Eviction Server**: Asisten dapur yang membersihkan sisa bahan dari meja *prep* saat meja mulai penuh (80%), agar koki utama tidak kehabisan ruang kerja.
* **Checkpoint**: Foto inventaris dapur yang diambil setiap 60 detik untuk mendokumentasikan kondisi terkini bahan makanan.
* **Journal (WAL)**: Buku pesanan kecil yang tergantung di saku koki. Setiap ada pesanan masuk, koki mencatatnya di buku saku terlebih dahulu sebelum meracik bahan, sehingga jika listrik tiba-tiba padam, koki tahu persis pesanan mana yang belum selesai diracik.
* **Replica Set**: Tiga koki yang memasak menu yang sama secara serentak. Koki utama (Primary) meracik menu, dua asistennya (Secondary) menyalin langkah koki utama secara langsung.
* **mongos**: Kepala pelayan (*Maitre D'*) yang memegang denah meja dan mengarahkan pelayan mana yang harus mengantarkan pesanan ke dapur yang tepat (Shard).

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Demonstrasi Causal Consistency Session

Contoh berikut menunjukkan eksekusi pembaruan data dan pembacaan beruntun menggunakan sesi konsistensi kausal (*Causal Consistency*) langsung via MongoDB Node.js Driver.

```typescript
import { MongoClient } from 'mongodb';

async function causalConsistencyDemo() {
  const uri = "mongodb://localhost:27017,localhost:27018/?replicaSet=rs0";
  const client = new MongoClient(uri);

  await client.connect();
  const db = client.db("inventory_system");
  const collection = db.collection("stock");

  // Membuka Causal Consistent Session
  const session = client.startSession({ causalConsistency: true });

  try {
    session.startTransaction({
      readConcern: { level: "majority" },
      writeConcern: { w: "majority" }
    });

    console.log("Mengeksekusi mutasi pada sesi...");
    await collection.updateOne(
      { sku: "SKU-PROD-001" },
      { $inc: { availableQty: -5 } },
      { session }
    );

    // Pembacaan berikutnya dalam sesi ini DIJAMIN melihat dampak penulisan di atas,
    // meskipun kueri dialihkan ke Secondary node yang memiliki replikasi mikro-lag.
    const result = await collection.findOne(
      { sku: "SKU-PROD-001" },
      { session, readPreference: "secondary" }
    );

    console.log("Hasil pembacaan konsisten:", result);

    await session.commitTransaction();
  } catch (error) {
    console.error("Transaksi gagal, melakukan rollback:", error);
    await session.abortTransaction();
  } finally {
    await session.endSession();
    await client.close();
  }
}

causalConsistencyDemo().catch(console.dir);
```

---

### 7.2. Practical Example: Production-Grade Resilient Transaction Processor

Contoh produksi enterprise berikut mengimplementasikan transaksi multi-dokumen terdistribusi dengan penanganan komprehensif terhadap galat transien (*transient transaction errors*) dan *commit uncertainties* menggunakan Go Driver.

```go
package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"time"

	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"
	"go.mongodb.org/mongo-driver/mongo/readconcern"
	"go.mongodb.org/mongo-driver/mongo/readpref"
	"go.mongodb.org/mongo-driver/mongo/writeconcern"
)

type AccountRepository struct {
	client *mongo.Client
	dbName string
}

func NewAccountRepository(client *mongo.Client, dbName string) *AccountRepository {
	return &AccountRepository{client: client, dbName: dbName}
}

// TransferFunds mengeksekusi pemindahan dana antar-akun dengan protokol ACID penuh
func (r *AccountRepository) TransferFunds(ctx context.Context, fromAcc string, toAcc string, amount float64) error {
	if amount <= 0 {
		return errors.New("invalid transfer amount: must be positive")
	}

	// 1. Definisikan opsi transaksi enterprise
	txnOptions := options.Transaction().
		SetReadConcern(readconcern.Snapshot()).
		SetWriteConcern(writeconcern.New(writeconcern.WMajority(), writeconcern.WTimeout(5*time.Second))).
		SetReadPreference(readpref.Primary())

	session, err := r.client.StartSession()
	if err != nil {
		return fmt.Errorf("failed to initiate client session: %w", err)
	}
	defer session.EndSession(ctx)

	// 2. Jalankan wrapper transaksional dengan mekanisme auto-retry
	callback := func(sc mongo.SessionContext) (interface{}, error) {
		accColl := r.client.Database(r.dbName).Collection("accounts")
		auditColl := r.client.Database(r.dbName).Collection("transfer_audits")

		// Potong dana dari rekening pengirim
		var senderAccount bson.M
		err := accColl.FindOneAndUpdate(
			sc,
			bson.M{"account_id": fromAcc, "balance": bson.M{"$gte": amount}},
			bson.M{"$inc": bson.M{"balance": -amount}},
			options.FindOneAndUpdate().SetReturnDocument(options.After),
		).Decode(&senderAccount)

		if err != nil {
			if errors.Is(err, mongo.ErrNoDocuments) {
				return nil, fmt.Errorf("insufficient funds or account %s not found", fromAcc)
			}
			return nil, err
		}

		// Tambahkan dana ke rekening penerima
		receiverResult, err := accColl.UpdateOne(
			sc,
			bson.M{"account_id": toAcc},
			bson.M{"$inc": bson.M{"balance": amount}},
		)
		if err != nil {
			return nil, err
		}
		if receiverResult.MatchedCount == 0 {
			return nil, fmt.Errorf("recipient account %s not found", toAcc)
		}

		// Tulis audit trail terdistribusi
		auditPayload := bson.M{
			"from_account": fromAcc,
			"to_account":   toAcc,
			"amount":       amount,
			"timestamp":    time.Now().UTC(),
			"status":       "SUCCESS",
		}
		if _, err := auditColl.InsertOne(sc, auditPayload); err != nil {
			return nil, err
		}

		return nil, nil
	}

	// WithTransaction mengotomatiskan retry pada TransientTransactionError
	// dan UnknownTransactionCommitResult
	_, err = session.WithTransaction(ctx, callback, txnOptions)
	if err != nil {
		return fmt.Errorf("transaction failed after retry evaluations: %w", err)
	}

	return nil
}

func main() {
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()

	// Pool konfigurasi koneksi enterprise
	clientOpts := options.Client().
		ApplyURI("mongodb://10.0.1.10:27017,10.0.1.11:27017,10.0.1.12:27017/?replicaSet=prod-rs").
		SetMaxPoolSize(100).
		SetMinPoolSize(20).
		SetMaxConnIdleTime(30 * time.Second)

	client, err := mongo.Connect(ctx, clientOpts)
	if err != nil {
		log.Fatalf("Critical error initiating MongoDB connection pool: %v", err)
	}
	defer client.Disconnect(ctx)

	repo := NewAccountRepository(client, "core_banking")
	err = repo.TransferFunds(ctx, "ACC_ID_CORP_001", "ACC_ID_RETAIL_999", 50000000.00)
	if err != nil {
		log.Fatalf("Funds transfer execution failed: %v", err)
	}

	log.Println("Distributed transaction committed successfully.")
}
```

---

## 8. Real World Case Study: High-Throughput Payment Gateway

### Profil Skenario & Skala Beban
Sebuah unicorn platform payment processing di Asia Tenggara menangani transaksi puncak sebesar **45.000 transaksi pembayaran per detik (TPS)** pada momentum promosi nasional (*flash sale*). 

* **Permasalahan Arsitektur**:
  1. Penggunaan Shard Key monotonik (`timestamp` + `transaction_id`) memicu fenomena **Monotonic Insertion Saturation**. Lebih dari 90% penulisan terkonsentrasi hanya pada satu shard tertentu (*hotshard*), sementara tiga shard lainnya dalam status *idle*.
  2. Latensi rata-rata kueri melonjak dari 15ms menjadi 2.400ms. Metrik FTDC menunjukkan WiredTiger `tickets available` anjlok ke angka 0 (Ticket Exhaustion).
  3. Proses *Chunk Balancer* berjalan tanpa kendali di jam sibuk, memicu migrasi I/O masif yang menghabiskan *disk throughput* hingga batas *saturation* IOPS EBS AWS.

```
SEBELUM OPTIMASI (Anti-Pattern: Monotonic Key & Single Shard Hotspot)
---------------------------------------------------------------------
Ingestion (45k TPS) ----> [mongos]
                             |
             +---------------+---------------+
             | (95% Penulisan)               | (5% Penulisan)
             v                               v
       [Shard 01 (HOT)]                [Shard 02 (IDLE)]
     - CPU: 98%, IOPS Maxed          - CPU: 5%, IOPS Idle
     - WT Cache: 95% Dirty           - WT Cache: 2% Dirty
     - Available Tickets: 0          - Available Tickets: 128


SETELAH OPTIMASI (Compound Hashed Shard Key & Balancer Window)
---------------------------------------------------------------------
Ingestion (45k TPS) ----> [mongos]
                             |
             +---------------+---------------+
             | (50% Penulisan)               | (50% Penulisan)
             v                               v
       [Shard 01]                      [Shard 02]
     - CPU: 42%, IOPS Stable         - CPU: 44%, IOPS Stable
     - WT Cache: 12% Dirty           - WT Cache: 11% Dirty
     - Tickets Available: 128        - Tickets Available: 128
```

### Investigasi Metrik & Root Cause
Melalui penelusuran `db.serverStatus().wiredTiger.concurrentTransactions`, tim mendeteksi:
```json
"concurrentTransactions": {
  "write": {
    "out": 128,
    "available": 0,
    "totalTickets": 128
  }
}
```
Kueri penulisan antre (*stalling*) karena operasi I/O terhambat migrasi chunk yang diinisiasi Balancer di tengah beban tinggi. Pada saat yang sama, dirty cache WiredTiger menyentuh 24%, sehingga thread aplikasi dipaksa melakukan *eviction*.

### Intervensi Rekayasa Sistem
1. **Redesain Shard Key**: Mengubah shard key dari `{ createdAt: 1 }` menjadi **Compound Hashed Shard Key**:
   ```javascript
   sh.shardCollection("payment_gateway.transactions", { "merchant_id": "hashed", "transaction_id": 1 })
   ```
   Kombinasi ini mendistribusikan beban penulisan merchant secara seragam di seluruh cluster via hashing, sekaligus mempertahankan performa *targeted range query* untuk transaksi pada satu merchant tertentu.

2. **Pengendalian Balancer Window**:
   Membatasi operasional penyeimbangan chunk hanya pada jam non-puncak (*off-peak window*):
   ```javascript
   db.settings.updateOne(
     { _id: "balancer" },
     { 
       $set: { 
         activeWindow: { start: "02:00", stop: "05:00" },
         mode: "full"
       } 
     },
     { upsert: true }
   );
   ```

3. **Tuning Storage Engine Concurrency**:
   Menaikkan batas concurrency ticket WiredTiger melalui parameter konfigurasi `/etc/mongod.conf`:
   ```yaml
   setParameter:
     wiredTigerConcurrentWriteTransactions: 256
     wiredTigerConcurrentReadTransactions: 256
   ```

### Hasil Pasca Implementasi
* Beban penulisan tersebar simetris dengan varians antar-shard < 4%.
* P99 Write Latency terpangkas dari **2.400 ms** menjadi **11 ms**.
* Utilisasi dirty page WiredTiger stabil pada angka 8-12%, menghilangkan sepenuhnya pembebanan *application thread eviction*.

---

## 9. Trade-offs

| Parameter Desain | Opsi A | Opsi B | Trade-off Analysis |
| :--- | :--- | :--- | :--- |
| **Write Durability** | `w: 1` | `w: majority, j: true` | Opsi A memberikan throughput penulisan maksimum (~300% lebih tinggi) dan latensi minimal, namun membuka celah hilangnya data (*data loss*) jika node Primary mati sebelum replikasi. Opsi B memberikan durabilitas mutlak, namun latensi meningkat drastis mengikuti RTT (*round-trip time*) jaringan dan latensi I/O `fsync`. |
| **Read Consistency** | `readConcern: "local"` | `readConcern: "linearizable"` | Opsi A mengeliminasi koordinasi lintas-node, pembacaan selesai seketika. Opsi B menjamin pembacaan data yang selalu segar dan tidak mungkin di-rollback, namun latensi membaca melonjak tajam karena Primary wajib memverifikasi posisinya ke node lain melalui *heartbeat quorum* sebelum melayani kueri. |
| **Sharding Strategy** | `Range Partitioning` | `Hashed Partitioning` | Opsi A sangat ideal untuk *range scan* namun rentan menciptakan *hotshard* jika pola data berurutan. Opsi B menjamin pemerataan beban penulisan secara matematis, namun mengubah kueri berbasis rentang menjadi operasi *scatter-gather* yang boros CPU dan memori di seluruh shard. |
| **Storage Compression**| `snappy` | `zstd` | Opsi A dioptimalkan untuk utilisasi CPU minimal dengan kompresi medium. Opsi B menghemat kapasitas disk hingga 40-50% lebih baik dibanding snappy, tetapi membutuhkan konsumsi siklus CPU 15-25% lebih tinggi saat dekompresi data. |

---

## 10. Common Mistakes & Troubleshooting

### Kesalahan Kritis 1: Secondary Reads Tanpa Causal Consistency
* **Gejala**: Aplikasi membaca data dari node Secondary untuk membagi beban (*read offloading*), namun pengguna melihat saldo akun atau status pesanan yang baru saja diubah kembali ke status lama.
* **Akar Masalah**: Replikasi asynchronous menghasilkan jeda waktu (*replication lag*). Pembacaan dengan *Read Preference* `secondary` tanpa `session` kausal membaca data yang belum tersinkronisasi.
* **Solusi**: Jika membaca dari secondary merupakan keharusan arsitektur, gunakan `ClientSession` dengan flag `causalConsistency: true` atau gunakan `readPreference: "primaryPreferred"`.

### Kesalahan Kritis 2: Pembentukan Jumbo Chunks yang Tidak Bisa Dimigrasikan
* **Gejala**: Log balancer menampilkan galat: `[Balancer] could not move chunk: chunk is too large to move (jumbo)`.
* **Akar Masalah**: Kardinalitas *shard key* terlalu rendah (misalnya status transaksi: `PENDING`, `SUCCESS`, `FAILED`). Data menumpuk pada satu nilai yang sama hingga ukuran chunk melampaui limit migrasi (default: 2x max chunk size) dan tidak dapat di-split karena semua data memiliki kunci yang identik.
* **Solusi**: Tambahkan suffix unik untuk meningkatkan kardinalitas shard key (*Compound Shard Key*):
  ```javascript
  // Menggunakan compound key yang menggabungkan status dan entitas unik
  sh.shardCollection("app.orders", { "status": 1, "_id": 1 })
  ```

### Panduan Troubleshooting: Diagnosa WiredTiger Ticket Exhaustion
Jika kueri melambat secara menyeluruh, periksa status ketersediaan tiket konkurensi:

```javascript
// Jalankan pada mongo shell
db.serverStatus().wiredTiger.concurrentTransactions

// Output jika terjadi exhaustion:
{
  "read": {
    "out": 128,
    "available": 0,    // <--- CRITICAL WARNING: Antrean blokade pembacaan
    "totalTickets": 128
  },
  "write": {
    "out": 128,
    "available": 0,    // <--- CRITICAL WARNING: Antrean blokade penulisan
    "totalTickets": 128
  }
}
```

**Langkah Mitigasi Taktis**:
1. Identifikasi query pembawa bencana dengan melacak operasi berjalan lambat:
   ```javascript
   db.currentOp({
     "active": true,
     "secs_running": { "$gt": 5 },
     "waitingForLock": false
   })
   ```
2. Terminasi query bermasalah tersebut:
   ```javascript
   db.killOp(<opid>)
   ```

---

## 11. Best Practices (Production Checklist)

### 11.1. Operating System (OS) & Kernel Tuning (Linux)
* [ ] **Non-Uniform Memory Access (NUMA)**: Nonaktifkan NUMA zone interleaving. Jalankan mongod via `numactl --interleave=all /usr/bin/mongod`.
* [ ] **Transparent Huge Pages (THP)**: Nonaktifkan THP secara permanen. THP memicu fragmentasi alokasi memori internal WiredTiger:
  ```bash
  echo "never" | sudo tee /sys/kernel/mm/transparent_hugepage/enabled
  echo "never" | sudo tee /sys/kernel/mm/transparent_hugepage/defrag
  ```
* [ ] **File System**: Gunakan sistem berkas **XFS**. Hindari EXT4 karena berpotensi mengalami stall alokasi blok saat berkas membesar secara dinamis.
* [ ] **Disk Mount Options**: Pasang disk data dengan parameter `noatime,nodiratime`.
* [ ] **Virtual Memory Configuration**:
  ```sysctl
  vm.dirty_background_ratio = 5
  vm.dirty_ratio = 10
  vm.swappiness = 1
  ```
* [ ] **Ulimits System**: Pastikan file descriptor (`nofile`) diset minimal `64000` dan proses maksimal (`nproc`) `64000`.

### 11.2. Database Configuration
* [ ] **Storage Cache Constraint**: Jangan biarkan cache WiredTiger mengambil 100% kapasitas RAM server. Sisakan ruang minimum 40% memori untuk filesystem page cache OS dan buffer proses sistem.
* [ ] **Replica Set Quorum**: Gunakan selalu jumlah anggota voting *ganjil* (misal: 3, 5, atau 7) untuk mencegah skenario *split-brain deadlock*. Hindari penggunaan *Arbiter* pada lingkungan enterprise karena keterbatasan replikasi oplog.
* [ ] **Network Compression**: Aktifkan kompresi lalu lintas data antar mongos dan mongod dengan `snappy` atau `zstandard` untuk menghemat utilisasi *bandwidth* VPC.

---

## 12. Hands-on Practice

Simulasi ini akan memandu deployment arsitektur **Sharded Cluster** terlengkap pada satu mesin menggunakan `docker-compose`. Arsitektur terdiri dari:
* 1 Config Server Replica Set (`csrs` - 1 node untuk kebutuhan lab)
* 1 Shard Replica Set (`shard1` - 1 node)
* 1 Shard Replica Set (`shard2` - 1 node)
* 1 Query Router (`mongos`)

Simpan semua berkas berikut di direktori: `hands-on/m02/`

### 12.1. File: `hands-on/m02/docker-compose.yaml`
```yaml
version: '3.8'

services:
  # Config Server
  configsvr:
    image: mongo:6.0
    container_name: configsvr
    command: mongod --configsvr --replSet csrs --port 27019 --bind_ip_all
    volumes:
      - config_data:/data/db
    ports:
      - "27019:27019"
    networks:
      mongo-net:

  # Shard 01
  shard1:
    image: mongo:6.0
    container_name: shard1
    command: mongod --shardsvr --replSet shard1rs --port 27018 --bind_ip_all
    volumes:
      - shard1_data:/data/db
    ports:
      - "27018:27018"
    networks:
      mongo-net:

  # Shard 02
  shard2:
    image: mongo:6.0
    container_name: shard2
    command: mongod --shardsvr --replSet shard2rs --port 27020 --bind_ip_all
    volumes:
      - shard2_data:/data/db
    ports:
      - "27020:27020"
    networks:
      mongo-net:

  # Router (mongos)
  mongos:
    image: mongo:6.0
    container_name: mongos
    depends_on:
      - configsvr
      - shard1
      - shard2
    command: mongos --configdb csrs/configsvr:27019 --port 27017 --bind_ip_all
    ports:
      - "27017:27017"
    networks:
      mongo-net:

volumes:
  config_data:
  shard1_data:
  shard2_data:

networks:
  mongo-net:
    driver: bridge
```

### 12.2. File Eksekusi Otomatisasi: `hands-on/m02/init-cluster.sh`
```bash
#!/usr/bin/env bash
set -e

echo "[1/5] Memulai kontainer Docker..."
docker-compose up -d

echo "[2/5] Menunggu inisialisasi daemon mongod (10 detik)..."
sleep 10

echo "[3/5] Menginisialisasi Config Server Replica Set..."
docker exec -it configsvr mongosh --port 27019 --eval '
rs.initiate({
  _id: "csrs",
  configsvr: true,
  members: [{ _id: 0, host: "configsvr:27019" }]
})
'

echo "[4/5] Menginisialisasi Shard 1 & Shard 2 Replica Sets..."
docker exec -it shard1 mongosh --port 27018 --eval '
rs.initiate({
  _id: "shard1rs",
  members: [{ _id: 0, host: "shard1:27018" }]
})
'

docker exec -it shard2 mongosh --port 27020 --eval '
rs.initiate({
  _id: "shard2rs",
  members: [{ _id: 0, host: "shard2:27020" }]
})
'

echo "[5/5] Mendaftarkan Shards ke mongos router..."
sleep 5
docker exec -it mongos mongosh --port 27017 --eval '
sh.addShard("shard1rs/shard1:27018");
sh.addShard("shard2rs/shard2:27020");
sh.status();
'

echo "Kluster MongoDB Sharded Enterprise siap digunakan!"
```

### 12.3. Langkah Verifikasi Partitioning & Routing
Jalankan perintah ini di terminal:
```bash
# 1. Berikan hak akses eksekusi dan jalankan inisialisasi
chmod +x hands-on/m02/init-cluster.sh
./hands-on/m02/init-cluster.sh

# 2. Masuk ke mongos router
docker exec -it mongos mongosh --port 27017

# 3. Buat database baru dan aktifkan sharding
use enterprise_catalog;
sh.enableSharding("enterprise_catalog");

# 4. Terapkan Hashed Sharding pada koleksi items
sh.shardCollection("enterprise_catalog.items", { "item_uuid": "hashed" });

# 5. Injeksi 10.000 dokumen dummy
for (let i = 0; i < 10000; i++) {
  db.items.insertOne({
    item_uuid: "item_" + i,
    name: "Enterprise Hardware " + i,
    timestamp: new Date()
  });
}

# 6. Analisis persebaran data pada tiap shard
db.items.getShardDistribution();
```

---

## 13. Exercise

### Level Easy
Modifikasi konfigurasi cache WiredTiger pada node `shard1` yang sedang berjalan secara dinamis melalui console `mongosh`. Ubah batas penggunaan cache maksimum menjadi 1.5 GB tanpa me-restart container, lalu verifikasi perubahannya via `db.serverStatus()`.

### Level Medium
Simulasikan kegagalan jaringan (*split-brain*) parsial menggunakan `iptables` atau manipulasi jaringan Docker. Putuskan komunikasi antar node Primary pada replika set sehingga memicu fase pemilihan (*election*). Amati transisi perubahan state melalui `rs.status()` dan ekstrak log perpindahan kepemimpinan primary term.

### Level Hard
Buat kondisi buatan yang menghasilkan *jumbo chunk* dengan memasukkan data sebesar 70 MB dengan nilai shard key yang identik pada sebuah collection dengan range sharding. Amati penolakan balancer ketika mencoba memigrasikan chunk tersebut, lalu eksekusi prosedur manual pemecahan chunk menggunakan perintah `sh.splitFind()` atau `sh.splitAt()`.

---

## 14. Challenge

Rancang arsitektur data multi-kawasan (*Global Multi-Region Deployment*) untuk entitas perbankan multinasional yang beroperasi di 3 kawasan regulasi ketat: **Asia (Singapura)**, **Eropa (Frankfurt)**, dan **Amerika (Virginia)**.

### Ketentuan Desain:
1. **Regulasi Kedaulatan Data (GDPR/Compliance)**: Data nasabah domisili Eropa dilarang keras disimpan di luar regional Frankfurt. Hal serupa berlaku untuk data nasabah Asia dan Amerika.
2. **Global Single System Image**: Aplikasi global harus mengakses database melalui string koneksi tunggal tanpa perlu mengetahui shard regional secara manual.
3. **Ketahanan Bencana (Disaster Recovery)**: Jika kawasan Frankfurt mengalami pemadaman total (*total regional outage*), cluster harus tetap dapat diakses untuk regional Asia dan Amerika tanpa mengalami kegagalan konsensus kluster.

### Output yang Diharapkan:
* Buat cetak biru topologi lengkap (*ASCII Architecture Blueprint*) yang memetakan CSRS, mongos, dan Shard Zones (`Zone Sharding` / `Tag-Aware Sharding`).
* Definisikan perintah konfigurasi skema sharding, penandaan zona (`sh.addShardTag`), penetapan rentang zona (`sh.addTagRange`), serta aturan penempatan replica set voting members untuk mencegah hilangnya kuorum global.

---

## 15. Quiz Evaluasi Pemahaman

### 5 Pertanyaan Basic
1. Apa fungsi dari *hazard pointers* di dalam arsitektur in-memory WiredTiger?
2. Parameter apa yang menentukan interval rutin pembuatan *checkpoint* pada WiredTiger storage engine?
3. Mengapa penulisan dokumen dengan flag `w: 1` memiliki risiko kehilangan data (*data loss*)?
4. Mengapa operasi pembacaan pada *Secondary* tanpa sesi kausal rentan mengembalikan status data yang usang (*stale read*)?
5. Berapa ukuran default logis dari sebuah *chunk* pada MongoDB Sharded Cluster?

### 5 Pertanyaan Intermediate
6. Jelaskan apa yang terjadi secara internal jika *dirty page* pada cache WiredTiger mencapai ambang batas 95%!
7. Mengapa penggunaan nilai `timestamp` inkremental sebagai tunggal shard key sangat tidak direkomendasikan pada ingest data bervolume tinggi?
8. Bagaimana WiredTiger memitigasi overhead I/O saat mengeksekusi operasi `fsync` pada transaksi penulisan beruntun?
9. Apa perbedaan esensial dari read concern level `majority` dibandingkan dengan `linearizable`?
10. Pada fase replikasi data, jelaskan apa yang dimaksud dengan proses idempotensi pada format Oplog v2!

### 3 Skenario Kasus Produksi
11. **Skenario Partisi Jaringan**: Sebuah Replica Set 3-node mengalami isolasi jaringan di mana node Primary terputus dari 2 node Secondary-nya, tetapi masih menerima trafik penulisan dari aplikasi klien yang terhubung ke jaringan lokalnya selama 8 detik sebelum timeout. Jika klien menulis data dengan `w: 1`, apa yang akan terjadi secara fisik terhadap data tersebut saat koneksi jaringan antar-node pulih?
12. **Skenario Balancer Starvation**: Di sebuah kluster sharded dengan kapasitas dataset 12 TB, proses migrasi chunk otomatis terhenti total. Disk pada salah satu shard terisi 98% sementara shard lain baru 40%. Saat dicegah, log menunjukkan `LockBusy: could not acquire balance lock`. Analisis penyebab dan susun rencana tindakan penyelamatan!
13. **Skenario IOPS EBS Saturation**: Sebuah sistem e-commerce mencatat utilisasi volume penyimpanan I/O (IOPS) menyentuh batas baseline 100% secara permanen, padahal jumlah query penulisan aplikasi (QPS) normal. Analisis metrik server menunjukkan laju checkpointing WiredTiger berjalan setiap 12 detik alih-alih 60 detik. Faktor arsitektur internal apa yang memicu percepatan checkpointing ini?

---

### Kunci Jawaban & Pembahasan Quiz

#### Jawaban Basic
1. Hazard pointer berfungsi sebagai referensi memori *lock-free* yang menandai halaman B-Tree di cache yang sedang diakses oleh thread pembaca, mencegah *eviction thread* menghapus atau merealokasi halaman tersebut dari RAM secara bersamaan tanpa memerlukan sistem locking yang berat.
2. Checkpoint dipicu setiap interval waktu 60 detik tercapai, atau akumulasi penulisan berkas journal telah melampaui 2 Gigabyte data baru.
3. Karena `w: 1` hanya memvalidasi bahwa data telah diterima dan ditulis ke memori cache node Primary lokal. Jika Primary mengalami kerusakan fisik sebelum sempat menyiarkan data ke Secondary melalui oplog, data tersebut akan hilang permanen saat node lain dipromosikan menjadi Primary baru.
4. Karena replikasi ke node Secondary bersifat *asynchronous*. Terdapat jeda propagasi (*replication lag*) alami di tingkat jaringan dan eksekusi oplog pada node sekunder.
5. Ukuran default satu chunk adalah 64 Megabyte.

#### Jawaban Intermediate
6. Jika *dirty page* menyentuh 95%, WiredTiger masuk ke mode defensif kritis: thread milik aplikasi klien yang mengirim permintaan penulisan dialihkan secara paksa untuk bertindak sebagai *eviction threads*. Latensi kueri aplikasi akan melonjak sangat tinggi karena aplikasi harus membersihkan memori database sebelum permintaannya dapat diproses.
7. Karena seluruh dokumen baru akan memiliki nilai stempel waktu yang selalu lebih besar dari dokumen sebelumnya, mengarahkan penulisan hanya pada rentang chunk paling akhir yang berlokasi di satu shard spesifik (*hotshard*), mematikan efisiensi distribusi penulisan paralel cluster.
8. Melalui teknik *Group Commit*, yaitu menggabungkan puluhan hingga ratusan permintaan penulisan journal dari berbagai koneksi transaksi yang terjadi dalam jendela mikrodetik yang sama ke dalam satu panggilan fisik `fsync()` tunggal ke media disk.
9. `majority` membaca data dari snapshot in-memory yang telah diakui oleh mayoritas voting node tanpa perlu berbicara dengan node lain pada saat kueri masuk. Sebaliknya, `linearizable` memaksa node Primary melakukan pertukaran *heartbeat quorum* secara *real-time* dengan anggota replika set lain saat kueri tiba untuk memvalidasi bahwa dirinya belum terisolasi oleh skenario partisi jaringan baru.
10. Idempotensi memastikan bahwa menerapkan entri oplog yang sama berulang kali (misalnya setelah crash recovery) akan menghasilkan state data akhir yang persis sama. Oplog v2 mengubah ekspresi mutasi relatif (misal `$inc: { view: 1 }`) menjadi deklarasi mutlak (misal `$set: { view: 42 }`).

#### Jawaban Skenario Kasus Produksi
11. **Analisis**: Saat koneksi pulih, node Primary lama akan mendeteksi keberadaan Primary baru yang memiliki Term pemilihan lebih tinggi. Node Primary lama diturunkan statusnya menjadi Secondary. Semua penulisan `w:1` yang sempat ia layani saat terisolasi dikategorikan sebagai mutasi divergen (*uncommitted data*). Node mengekstraksi dokumen-dokumen tersebut dari engine, membuangnya dari dataset aktif, menulisnya ke direktori berkas fisik `/data/db/rollback/<coll_uuid>.bson`, lalu menyelaraskan state datanya mengikuti Primary baru. Data tersebut hilang dari akses aplikasi aktif kecuali diinjeksi manual dari berkas BSON hasil rollback.
12. **Analisis**: Galat `LockBusy` menandakan adanya operasi lain yang menahan lock metadata Config Server secara eksklusif. Skenario umum penyebabnya adalah transaksi multi-dokumen terdistribusi yang macet (*hung transaction*) dalam status `prepared` atau proses *metadata refresh* yang deadlock. Tindakan: Identifikasi sesi yang menahan lock dengan memeriksa kueri aktif pada Config Server menggunakan `db.currentOp({ "waitingForLock": true })`, lakukan eliminasi operasi (`killOp`), dan jika chunk tersebut ternyata tergolong *jumbo chunk*, matikan flag jumbo sementara atau ubah batas ukuran chunk maksimum via `db.settings.updateOne({ _id: "chunksize" }, { $set: { value: 128 } })` agar balancer dapat mengeksekusi transfer sebelum diturunkan kembali ke 64 MB.
13. **Analisis**: Pemicu checkpointing WiredTiger bukan hanya berbasis waktu (60 detik), melainkan juga akumulasi volume data pada journal log (2 GB). Jika sistem penulisan aplikasi mengeksekusi operasi modifikasi yang memicu penulisan journal intensif (seperti pembaruan dokumen array yang membesar, penghapusan masif, atau konfigurasi indeks yang berat), log buffer terisi hingga ambang 2 GB hanya dalam 12 detik. Hal ini memaksa engine melakukan siklus checkpointing disk 5 kali lebih sering dari kondisi normal, yang menyedot limit baseline IOPS penyimpanan EBS.

---

## 16. Summary

1. **WiredTiger Engine** mengisolasi eksekusi data melalui pemanfaatan struktur memori B-Tree berbasis *hazard pointers* dan memisahkan persistensi disk ke dalam siklus periodik *checkpoint* (RPO) dan *write-ahead journal* (durabilitas instan).
2. Mekanisme konsensus replikasi MongoDB adalah turunan dari protokol **Raft**, di mana ketergantungan urutan log dijamin oleh **Hybrid Logical Clocks** (stempel waktu HLC) dan format **Oplog v2** yang bersifat absolut idempoten.
3. Durabilitas dan isolasi data terdistribusi dikendalikan oleh konfigurasi kombinasi **Read Concern** (dari `local` hingga `snapshot`) dan **Write Concern** (dari `w:1` hingga `w:majority, j:true`), yang secara fundamental menyeimbangkan pertukaran (*trade-off*) antara latensi transmisi jaringan dan jaminan integritas data.
4. **Sharding Cluster** mendistribusikan dataset melalui unit logis *chunk*. Pemilihan skema *shard key* (Range vs Hashed) menentukan model rute kueri pada layer `mongos`—antara perutean langsung (*targeted routing*) atau *scatter-gather* yang membebani seluruh node data.
5. Ketahanan sistem enterprise menuntut penyelarasan parameter level kernel OS (eliminasi **Transparent Huge Pages**, konfigurasi alokasi memori virtual agresif, dan adopsi partisi **XFS**) serta penataan batasan memori kerja database guna mencegah fenomena kritis seperti *ticket exhaustion* dan *cache eviction thrashing*.