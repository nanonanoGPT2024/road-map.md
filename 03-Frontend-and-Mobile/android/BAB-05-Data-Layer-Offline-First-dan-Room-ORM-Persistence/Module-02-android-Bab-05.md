# MODULE 02: DEEP DIVE, IMPLEMENTASI LANJUTAN & ARSITEKTUR PRODUKSI
**Bab 05: Data Layer, Offline-First, dan Room ORM Persistence**
**Kategori: 03-Frontend-and-Mobile (Android Enterprise Track)**

---

## 1. LEARNING OBJECTIVES
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
*   **Menganalisis & Mengonfigurasi Storage Engine**: Memahami arsitektur internal SQLite/Room, mode Write-Ahead Logging (WAL), B-Tree indexing, dan siklus hidup page cache untuk optimasi *read/write throughput*.
*   **Membangun Relasi Kompleks & Skema Lanjutan**: Mengimplementasikan relasi 1:1, 1:N, N:M dengan constraint integritas referensial (`ForeignKey`, composite keys), TypeConverters kustom, serta Full-Text Search (FTS4/FTS5).
*   **Menjalankan Migrasi Skema Teruji (Zero-Data-Loss)**: Mengembangkan manual migration script dan auto-migration kompleks, memvalidasi schema hash, serta mengeksekusi integrasi automated migration testing via Room Testing Artifacts.
*   **Merancang Sistem Offline-First Skala Enterprise**: Mengimplementasikan pola Single Source of Truth (SSOT), sinkronisasi dua arah (*bi-directional sync*), queue management untuk *offline mutations*, dan resolusi konflik deterministik.
*   **Mengintegrasikan Data Pagination Reaktif**: Menghubungkan Room dengan Paging 3 via `RemoteMediator` dengan boundary callback dan validasi transaksi atomik.

---

## 2. PREREQUISITES
Sebelum mempelajari modul ini, engineer wajib menguasai:
1.  **Kotlin Coroutines & Flow**: Pemahaman mendalam tentang *cold/hot streams*, `SharedFlow`, `StateFlow`, context switching (`Dispatchers.IO`), serta exception handling reaktif.
2.  **Dasar Room Persistence**: Entitas dasar, DAO, query CRUD standar, dan setup dasar `RoomDatabase`.
3.  **Dasar SQL & Relational Model**: Normalisasi database (1NF hingga 3NF), JOIN operations, indexing, ACID transactions.
4.  **Dependency Injection**: Integrasi lifecycle database menggunakan Google Hilt (`@Singleton`, scoping).

---

## 3. CONCEPT & INTERNAL ARCHITECTURE

### 3.1 SQLite Under the Hood: B-Tree, Paging, dan Journaling Modes
Room merupakan *abstraction layer* di atas engine SQLite. Pemahaman performa Room menuntut pemahaman terhadap lapisan internal SQLite:

```
+-------------------------------------------------------------------+
|                        Room Generated Code (_Impl)                |
+-------------------------------------------------------------------+
|               Android Framework SQLite Driver (android.database)  |
+-------------------------------------------------------------------+
|                        SQLite C-Core Engine                       |
|   +-----------------------------------------------------------+   |
|   | Parser & Query Optimizer (VDBE: Virtual DB Engine)        |   |
|   +-----------------------------------------------------------+   |
|   | B-Tree Layer (Table B-Tree: 64-bit rowid; Index B-Tree)   |   |
|   +-----------------------------------------------------------+   |
|   | Pager Module (Fixed-size page cache: default 4096 bytes)  |   |
+---+-----------------------------------------------------------+---+
|                     OS Storage Subsystem (Flash Memory)           |
+-------------------------------------------------------------------+
```

#### Rollback Journal vs. Write-Ahead Logging (WAL)
Secara default pada Android 9+, Room mengaktifkan **WAL Mode**.
*   **Rollback Journal (TRADITIONAL)**: Setiap mutasi menulis data asli ke journal file sebelum menimpa database file. Ini membutuhkan locking eksklusif: pembaca (*readers*) memblokir penulis (*writers*), dan penulis memblokir semua pembaca.
*   **Write-Ahead Logging (WAL)**: Perubahan data tidak langsung ditulis ke file database utama (`.db`), melainkan di-append ke file terpisah (`.db-wal`). 
    *   *Reader Concurrency*: Readers membaca state dari `.db` digabungkan dengan entri terbaru di `.db-wal` tanpa di-lock oleh ongoing write transaction.
    *   *Checkpointing*: Data dari WAL dipindahkan kembali ke master `.db` secara berkala via proses `checkpoint` (PASSIVE, FULL, RESTART, atau TRUNCATE).

### 3.2 Room InvalidationTracker Internals
Room tidak melakukan *polling* ke storage engine saat mengalirkan data via `Flow<T>`. Room memanfaatkan **SQLite Triggers** dan **InvalidationTracker**.
1.  Saat query DAO me-return `Flow<T>`, Room menganalisis tabel mana saja yang diobservasi.
2.  Room menyuntikkan SQLite Trigger ke dalam database engine:
    ```sql
    CREATE TEMP TRIGGER IF NOT EXISTS room_table_modification_trigger_users
    AFTER UPDATE ON users BEGIN
        INSERT INTO room_table_modification_log VALUES (1, 0);
    END;
    ```
3.  Tabel `room_table_modification_log` bertindak sebagai *bitmask change-log*.
4.  `InvalidationTracker` menjalankan pengecekan terjadwal di `Dispatchers.IO`. Jika bitmask menandakan ada perubahan pada tabel yang relevan, Flow memicu re-query dan memancarkan (*emit*) model data terbaru.

### 3.3 Transaction Processing Engine
Eksekusi transaksi via `withTransaction { ... }` memastikan atomic snapshot isolation:
*   Membuka transaksi SQLite di level connection pool.
*   Memetakan Coroutine Context ke active database thread.
*   Menjaga nested transactions tetap atomik: kegagalan di inner block akan membatalkan (*rollback*) seluruh state execution stack.

---

## 4. WHY & WHAT

| Karakteristik | Raw SQLite (`SQLiteOpenHelper`) | Room ORM (Enterprise Tier) | NoSQL K/V (Proto DataStore) |
| :--- | :--- | :--- | :--- |
| **Type Safety** | Nihil (Raw Cursor casting via strings) | Compile-time strict validation | Compile-time via Protocol Buffers |
| **Relational Queries** | Kompleks, rawan syntax error | Anotasi `@Relation`, `@Embedded`, compile check | Tidak mendukung relasi native |
| **Observation Model** | Manual via ContentObserver | Native reaktif (`Flow`, `PagingSource`) | Native reaktif (`Flow`) |
| **Schema Migration** | Raw SQL scripts, rawan human error | Skema diekspor via JSON, automated testing | Skema backward-compat via Protobuf |
| **Execution Cost** | Minimal overhead | Minimal overhead (KSP code-gen time) | Sedang (Serialization cost) |

---

## 5. HOW (WORKFLOW DETAIL)

### 5.1 Siklus Hidup Transaksi Offline-First Sinkronisasi
```
[User Action / UI]
        │
        ▼
[Repository.mutate()]
        │
        ├──> 1. Tulis mutasi ke Room DB (Status: SYNC_PENDING) ───┐ (SSOT Instant Update)
        │                                                        │
        │                                                        ▼
        ├──> 2. Flow/Paging meng-emit data baru ke UI <──────────┘
        │
        └──> 3. Trigger Sync Worker / Network Engine
                 │
                 ├──> [ONLINE] Kirim mutasi via HTTPS POST/PUT
                 │         │
                 │         ├──> [SUCCESS]: Update Room DB (Status: SYNCED, Server ID)
                 │         │
                 │         └──> [409 CONFLICT]: Jalankan Resolusi Konflik 
                 │                               ├── Server Wins: Overwrite Room DB
                 │                               └── Client Wins: Force Re-sync
                 │
                 └──> [OFFLINE]: Mutasi tetap tersimpan dengan flag PENDING.
                                 WorkManager akan melanjutkan saat network CONNECTED.
```

---

## 6. ANALOGI & DIAGRAM ASCII

Bayangkan Room Database dengan mode **Write-Ahead Logging (WAL)** seperti **Restoran Cepat Saji**:

```
+------------------+         +--------------------+         +---------------------+
| Master Ledger    |         | Scratchpad (WAL)   |         | Customer (Reader)   |
| (Database .db)   |         | (.db-wal)          |         |                     |
|                  |         |                    |         | Membaca Master      |
| Catatan Transaksi|         | Pesanan baru       |         | Ledger + Cek Pesanan|
| Permanen         |         | ditulis di sini    |         |<di Scratchpad       |
|                  |         | secara cepat       |         | (Non-blocking)      |
+------------------+         +--------------------+         +---------------------+
         ▲                            │
         │                            │
         └────── Checkpoint Worker ───┘
           (Menyalin catatan dari
            scratchpad ke ledger utama)
```

Jika menggunakan *Rollback Journal*, pelayan harus menyalin seluruh buku besar (*exclusive lock*) sebelum menulis 1 pesanan baru. Dengan *WAL*, pesanan baru di-append langsung ke *scratchpad*, sehingga antrean pelanggan yang hanya ingin melihat menu (*readers*) tidak pernah terhenti.

---

## 7. SIMPLE EXAMPLE & PRACTICAL EXAMPLE

### 7.1 Simple Example: Manual Migration dengan Validasi Integritas
Migrasi skema database dari versi 1 ke versi 2 dengan menambahkan kolom dan index.

```kotlin
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

val MIGRATION_1_2 = object : Migration(1, 2) {
    override fun migrate(db: SupportSQLiteDatabase) {
        // 1. Tambah kolom baru dengan batasan NOT NULL dan default value
        db.execSQL(
            "ALTER TABLE orders ADD COLUMN updated_at INTEGER NOT NULL DEFAULT 0"
        )
        // 2. Buat index baru untuk optimasi filtering
        db.execSQL(
            "CREATE INDEX IF NOT EXISTS index_orders_updated_at ON orders(updated_at)"
        )
    }
}
```

---

### 7.2 Practical Example: Enterprise Offline-First Architecture
Implementasi sistem Order Management yang mencakup *composite relations*, TypeConverters, custom DAO dengan transaksi atomik, dan optimasi query.

#### A. Entitas Skema Relasional
```kotlin
package com.enterprise.data.local.entity

import androidx.room.*

@Entity(
    tableName = "customers",
    indices = [Index(value = ["email"], unique = true)]
)
data class CustomerEntity(
    @PrimaryKey
    @ColumnInfo(name = "customer_id")
    val customerId: String,
    val name: String,
    val email: String
)

enum class SyncStatus { SYNCED, PENDING_INSERT, PENDING_UPDATE, PENDING_DELETE }

@Entity(
    tableName = "orders",
    foreignKeys = [
        ForeignKey(
            entity = CustomerEntity::class,
            parentColumns = ["customer_id"],
            childColumns = ["customer_owner_id"],
            onDelete = ForeignKey.CASCADE,
            onUpdate = ForeignKey.CASCADE
        )
    ],
    indices = [
        Index(value = ["customer_owner_id"]),
        Index(value = ["created_at"]),
        Index(value = ["sync_status"])
    ]
)
data class OrderEntity(
    @PrimaryKey
    @ColumnInfo(name = "order_id")
    val orderId: String,
    @ColumnInfo(name = "customer_owner_id")
    val customerOwnerId: String,
    @ColumnInfo(name = "total_amount")
    val totalAmount: Long, // Menggunakan sen/cents untuk mencegah floating point rounding error
    @ColumnInfo(name = "sync_status")
    val syncStatus: SyncStatus,
    @ColumnInfo(name = "created_at")
    val createdAt: Long = System.currentTimeMillis()
)

@Entity(
    tableName = "order_items",
    primaryKeys = ["order_parent_id", "item_sku"],
    foreignKeys = [
        ForeignKey(
            entity = OrderEntity::class,
            parentColumns = ["order_id"],
            childColumns = ["order_parent_id"],
            onDelete = ForeignKey.CASCADE
        )
    ],
    indices = [Index(value = ["order_parent_id"])]
)
data class OrderItemEntity(
    @ColumnInfo(name = "order_parent_id")
    val orderParentId: String,
    @ColumnInfo(name = "item_sku")
    val itemSku: String,
    val quantity: Int,
    val unitPrice: Long
)
```

#### B. Data Relasi Kompleks (1 to Many)
```kotlin
package com.enterprise.data.local.relation

import androidx.room.Embedded
import androidx.room.Relation
import com.enterprise.data.local.entity.CustomerEntity
import com.enterprise.data.local.entity.OrderEntity
import com.enterprise.data.local.entity.OrderItemEntity

data class OrderWithItemsAggregate(
    @Embedded val order: OrderEntity,
    @Relation(
        parentColumn = "order_id",
        entityColumn = "order_parent_id"
    )
    val items: List<OrderItemEntity>
)

data class CustomerWithFullOrders(
    @Embedded val customer: CustomerEntity,
    @Relation(
        entity = OrderEntity::class,
        parentColumn = "customer_id",
        entityColumn = "customer_owner_id"
    )
    val orders: List<OrderWithItemsAggregate>
)
```

#### C. Type Converter
```kotlin
package com.enterprise.data.local.converter

import androidx.room.TypeConverter
import com.enterprise.data.local.entity.SyncStatus

class CommonTypeConverters {
    @TypeConverter
    fun fromSyncStatus(status: SyncStatus): String = status.name

    @TypeConverter
    fun toSyncStatus(value: String): SyncStatus = runCatching {
        SyncStatus.valueOf(value)
    }.getOrDefault(SyncStatus.PENDING_INSERT)
}
```

#### D. Production-Grade Data Access Object (DAO)
```kotlin
package com.enterprise.data.local.dao

import androidx.room.*
import com.enterprise.data.local.entity.OrderEntity
import com.enterprise.data.local.entity.OrderItemEntity
import com.enterprise.data.local.entity.SyncStatus
import com.enterprise.data.local.relation.OrderWithItemsAggregate
import kotlinx.coroutines.flow.Flow

@Dao
interface OrderDao {

    @Transaction
    @Query("SELECT * FROM orders WHERE order_id = :orderId LIMIT 1")
    fun observeOrderById(orderId: String): Flow<OrderWithItemsAggregate?>

    @Transaction
    @Query("SELECT * FROM orders ORDER BY created_at DESC")
    fun observeAllOrdersPaged(): Flow<List<OrderWithItemsAggregate>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertOrder(order: OrderEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertOrderItems(items: List<OrderItemEntity>)

    @Query("UPDATE orders SET sync_status = :status WHERE order_id = :orderId")
    suspend fun updateSyncStatus(orderId: String, status: SyncStatus)

    @Query("DELETE FROM orders WHERE order_id = :orderId")
    suspend fun deleteOrderById(orderId: String): Int

    @Query("SELECT * FROM orders WHERE sync_status != 'SYNCED'")
    suspend fun getPendingSyncOrders(): List<OrderEntity>

    /**
     * Eksekusi transaksi atomik tingkat tinggi:
     * Menyimpan order dan detail item secara bersamaan.
     */
    @Transaction
    suspend fun createOrderWithItems(order: OrderEntity, items: List<OrderItemEntity>) {
        insertOrder(order)
        if (items.isNotEmpty()) {
            insertOrderItems(items)
        }
    }
}
```

#### E. Room Database Konfigurasi Tingkat Lanjut
```kotlin
package com.enterprise.data.local

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.TypeConverters
import androidx.sqlite.db.SupportSQLiteDatabase
import com.enterprise.data.local.converter.CommonTypeConverters
import com.enterprise.data.local.dao.OrderDao
import com.enterprise.data.local.entity.CustomerEntity
import com.enterprise.data.local.entity.OrderEntity
import com.enterprise.data.local.entity.OrderItemEntity

@Database(
    entities = [
        CustomerEntity::class,
        OrderEntity::class,
        OrderItemEntity::class
    ],
    version = 1,
    exportSchema = true
)
@TypeConverters(CommonTypeConverters::class)
abstract class EnterpriseDatabase : RoomDatabase() {

    abstract fun orderDao(): OrderDao

    companion object {
        private const val DB_NAME = "enterprise_commerce.db"

        fun build(context: Context): EnterpriseDatabase {
            return Room.databaseBuilder(
                context.applicationContext,
                EnterpriseDatabase::class.java,
                DB_NAME
            )
            .setJournalMode(JournalMode.WRITE_AHEAD_LOGGING)
            .addCallback(object : Callback() {
                override fun onOpen(db: SupportSQLiteDatabase) {
                    super.onOpen(db)
                    // Mengaktifkan Foreign Key enforcement di level engine SQLite
                    db.execSQL("PRAGMA foreign_keys=ON;")
                }
            })
            .build()
        }
    }
}
```

---

## 8. REAL WORLD CASE STUDY: Enterprise Offline-First POS Engine

### Konteks
Aplikasi Point of Sale (POS) untuk jaringan ritel dengan 5.000+ toko. Tiap toko mengalami *unreliable internet connectivity* (loss signal selama berjam-jam), namun kasir harus dapat melakukan checkout transaksi secara terus-menerus tanpa latensi.

### Arsitektur Sinkronisasi: Two-Way Sync dengan Vector Clocks
1.  **State Mutations**:
    Setiap transaksi POS di-commit langsung ke Room DB dengan status `PENDING_INSERT`.
2.  **Outbox Pattern**:
    Tabel `sync_queue` melacak sequence ID mutasi lokal.
3.  **Conflict Handling Engine**:
    Jika inventory produk diubah di server (misal: harga diskon berubah), server menggunakan strategi *Last-Write-Wins (LWW)* berbasis monotonic timestamp atau Vector Clocks untuk mencocokkan patch mutasi.

```
       [POS Terminal Kasir]                           [Cloud Server Backend]
                │                                                │
1. Transaksi Disimpan ke Room DB                                 │
   (Atomik: Order + Items + SyncQueue)                           │
                │                                                │
2. Background Sync Engine (WorkManager)                          │
   Membaca SyncQueue (Unsynced Payload)                          │
                ├────── POST /api/v1/orders/sync ───────────────>│
                │       (Payload: Order Data + Client Clock)     │
                │                                                ├── Validasi Stok
                │                                                ├── Idempotency Check
                │                                                │   (Berdasarkan UUID)
                │<───── 200 OK (Sync Acknowledged) ──────────────┤
                │                                                │
3. Update Status Room DB -> SYNCED                               │
   Hapus rekaman terkait di SyncQueue                            │
```

---

## 9. TRADE-OFFS

| Keputusan Arsitektur | Keuntungan | Biaya / Trade-off |
| :--- | :--- | :--- |
| **Write-Ahead Logging (WAL)** | Concurrency tinggi: Pembaca tidak memblokir penulis dan sebaliknya. Latensi write drop drastis. | Memerlukan 3 file terpisah (`.db`, `.db-wal`, `.db-shm`). Potensi *WAL file bloating* jika ada transaksi read yang menggantung lama (*starvation*). |
| **Normalisasi Penuh (Relational)** | Integritas data terjamin via Foreign Key; reduksi anomali update data. | Memerlukan `JOIN` kompleks; Room membutuhkan multi-step queries via `@Relation` yang memicu pemrosesan ekstra pada memori. |
| **Paging 3 + RemoteMediator** | Konsumsi memori sangat rendah saat menangani jutaan baris data; load data transparan dari Network ke DB. | Kompleksitas tinggi dalam implementasi key pagination, reset cache invalidation, dan potensi *UI flicker* saat boundary dipicu. |
| **SQLCipher (Encryption at Rest)** | Keamanan standar finansial/perbankan; melindungi file DB dari inspeksi fisik (root device). | CPU overhead sebesar 5-15% pada tiap operasi read/write; ukuran APK bertambah (~3-5 MB native `.so` engine). |

---

## 10. COMMON MISTAKES & TROUBLESHOOTING

### 10.1 Schema Hash Mismatch (`IllegalStateException`)
*   **Gejala**: Crash saat startup aplikasi: `IllegalStateException: Room cannot verify the data integrity. Looks like you've changed the schema but forgot to update the version number. You can simply bump the version number.`
*   **Penyebab Internal**: Room menyimpan hash skema database di tabel metadata internal `room_master_table`. Saat entity berubah tanpa kenaikan versi database dan migrasi yang sesuai, hash identitas SQLite tidak cocok dengan hash class yang dihasilkan KSP/APT.
*   **Solusi**:
    1. Naikkan versi database (`version = N + 1`).
    2. Tulis implementasi `Migration(N, N + 1)`.
    3. Tambahkan migrasi ke Room builder: `.addMigrations(MIGRATION_N_N1)`.

### 10.2 Room Foreign Key Foreign Constraints Disabled
*   **Gejala**: Penghapusan data parent tidak memicu `CASCADE` pada child table, meninggalkan *orphaned rows*.
*   **Penyebab Internal**: Engine SQLite secara historis menonaktifkan enforcement Foreign Key demi alasan *backward-compatibility*.
*   **Solusi**: Eksekusi perintah `PRAGMA foreign_keys = ON;` pada callback `onOpen` database (lihat Seksi 7.2.E).

### 10.3 Unindexed Foreign Key Columns
*   **Gejala**: Penurunan drastis performa write/delete pada tabel berukuran besar (>50.000 baris).
*   **Penyebab Internal**: Jika child table tidak memiliki index eksplisit pada kolom foreign key, SQLite akan melakukan **Full Table Scan** setiap kali parent record diperbarui atau dihapus guna memvalidasi integrity constraint.
*   **Solusi**: Selalu daftarkan kolom foreign key ke dalam parameter `indices` pada anotasi `@Entity`:
    ```kotlin
    @Entity(
        tableName = "order_items",
        indices = [Index(value = ["order_parent_id"])]
    )
    ```

---

## 11. BEST PRACTICES (PRODUCTION CHECKLIST)

- [ ] **Aktifkan Schema Export**: Konfigurasikan `exportSchema = true` dan tentukan lokasi schema folder di `build.gradle.kts` via KSP options.
- [ ] **Automated Migration Testing**: Gunakan library `androidx.room:room-testing` untuk memverifikasi eksekusi migrasi dari skema riil versi terdahulu.
- [ ] **Hindari Objek Kompleks di Entity**: Gunakan TypeConverter hanya untuk tipe primitif representasional (e.g., Enum ke String, Epoch Time ke Long). Jangan serialize nested JSON objek besar ke dalam satu kolom teks (melanggar 1NF dan sulit di-query).
- [ ] **Gunakan @Transaction pada Flow Multi-Tabel**: Query yang menggabungkan `@Relation` harus ditandai dengan `@Transaction` guna menjamin isolasi read konsisten (mencegah inkonsistensi saat child row diubah bersamaan).
- [ ] **Hindari Global State Mutable di Entity**: Jadikan seluruh field entity `val` (immutable data class) untuk mencegah concurrency bugs dalam asynchronous pipelines.
- [ ] **Audit Indexing**: Tambahkan index hanya pada kolom yang sering digunakan dalam klausa `WHERE`, `ORDER BY`, dan `JOIN`. Over-indexing memicu degradasi write performance.

---

## 12. HANDS-ON PRACTICE

Langkah-langkah berikut dirancang untuk diimplementasikan pada direktori proyek `hands-on/m02/`.

### Setup Struktur Direktori
```
hands-on/m02/
├── app/
│   ├── schemas/
│   └── src/
│       ├── androidTest/java/com/enterprise/data/MigrationTest.kt
│       └── main/java/com/enterprise/data/
│           ├── local/
│           │   ├── EnterpriseDatabase.kt
│           │   ├── dao/
│           │   └── entity/
│           └── repository/
```

### Langkah 1: Konfigurasi Schema Location (build.gradle.kts)
```kotlin
plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.ksp)
}

android {
    defaultConfig {
        ksp {
            arg("room.schemaLocation", "$projectDir/schemas")
            arg("room.incremental", "true")
            arg("room.expandProjection", "true")
        }
    }
}

dependencies {
    implementation(libs.androidx.room.runtime)
    implementation(libs.androidx.room.ktx)
    implementation(libs.androidx.room.paging)
    ksp(libs.androidx.room.compiler)
    androidTestImplementation(libs.androidx.room.testing)
}
```

### Langkah 2: Buat Test Otomasi Migrasi Database
Implementasikan unit test migrasi menggunakan `MigrationTestHelper`:

```kotlin
package com.enterprise.data

import androidx.room.testing.MigrationTestHelper
import androidx.sqlite.db.framework.FrameworkSQLiteOpenHelperFactory
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.enterprise.data.local.EnterpriseDatabase
import com.enterprise.data.local.MIGRATION_1_2
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.io.IOException

@RunWith(AndroidJUnit4::class)
class EnterpriseDatabaseMigrationTest {

    private val TEST_DB = "migration-test.db"

    @get:Rule
    val helper: MigrationTestHelper = MigrationTestHelper(
        InstrumentationRegistry.getInstrumentation(),
        EnterpriseDatabase::class.java,
        emptyList(),
        FrameworkSQLiteOpenHelperFactory()
    )

    @Test
    @Throws(IOException::class)
    fun migrate1To2_containsAllValidColumns() {
        // Buat DB versi 1
        var db = helper.createDatabase(TEST_DB, 1).apply {
            execSQL("INSERT INTO customers (customer_id, name, email) VALUES ('c1', 'John Doe', 'john@test.com')")
            execSQL("INSERT INTO orders (order_id, customer_owner_id, total_amount, sync_status) VALUES ('o1', 'c1', 15000, 'SYNCED')")
            close()
        }

        // Jalankan migrasi ke versi 2
        db = helper.runMigrationsAndValidate(TEST_DB, 2, true, MIGRATION_1_2)

        // Verifikasi skema baru dan validitas persistensi data lama
        val cursor = db.query("SELECT updated_at FROM orders WHERE order_id = 'o1'")
        assert(cursor.moveToFirst())
        val updatedAtValue = cursor.getLong(0)
        assert(updatedAtValue == 0L) // Default value check
        cursor.close()
    }
}
```

---

## 13. EXERCISES

### Level: Easy
Tambahkan entitas `ProductFtsEntity` yang memanfaatkan SQLite Full-Text Search (FTS4) untuk pencarian katalog produk berkecepatan tinggi pada tabel produk. Buat query DAO untuk melakukan pencarian berbasis teks bebas (*full-text query match*).

### Level: Medium
Rancang migrasi manual `MIGRATION_2_3` yang mengubah struktur skema:
Memecah kolom `name` pada tabel `customers` menjadi `first_name` dan `last_name`. Migrasi harus menyalin data lama secara aman tanpa menyebabkan *data truncation* atau *null pointer exception*.

### Level: Hard
Kembangkan custom transactional `OutboxRepository` yang mengimplementasikan **Atomic Write Queue Engine**:
Setiap kali terjadi modifikasi pada entitas bisnis lokal, record event JSON harus di-generate dan ditulis ke dalam tabel `outbox_events` di dalam blok transaksi Room yang sama (`withTransaction`). Jika penulisan entitas bisnis gagal, outbox event juga harus di-rollback secara otomatis.

---

## 14. CHALLENGES

### Skenario: Multi-Master Conflict-Free Distributed Synchronization (CRDT Engine)
Perusahaan Anda mengoperasikan perangkat kasir cerdas yang dapat bekerja secara peer-to-peer (P2P) via Local Wi-Fi saat internet padam total. Tiap kasir dapat memperbarui item cart dan inventory lokal.

**Tugas Rekayasa:**
1.  Rancang skema tabel Room yang tidak mengandalkan auto-increment integer, melainkan UUIDv7 atau KSUID (K-Sortable Globally Unique Identifiers).
2.  Implementasikan mekanisme **State-based CRDT (Conflict-Free Replicated Data Type)** (misal: LWW-Element-Set atau Observed-Remove Set) langsung di atas engine Room ORM.
3.  Tuliskan algoritma *Sync Resolver* yang menangani kasus *concurrent mutations* ketika dua kasir memodifikasi kuantitas inventory produk yang sama pada detik yang sama secara offline.
4.  Pastikan solusi Anda memiliki overhead kompleksitas komputasi maksimal $O(N)$ di mana $N$ adalah jumlah mutasi yang belum tersinkronisasi.

---

## 15. EVALUATION QUIZ

### Basic Questions
1.  **Mengapa Write-Ahead Logging (WAL) mode secara dramatis meningkatkan konkurensi pembacaan dan penulisan dibandingkan Rollback Journal?**
    *   *Jawaban*: Karena pada WAL, operasi penulisan (*write*) dilakukan dengan menambahkan log pada file terpisah (`.db-wal`) dan tidak langsung menimpa file database utama (`.db`). Hal ini memungkinkan proses pembacaan (*reader*) tetap berjalan membaca snapshot database utama tanpa terblokir oleh transaksi penulisan.
2.  **Apa fungsi dari tabel `room_master_table` yang dibuat secara otomatis oleh Room?**
    *   *Jawaban*: Tabel ini digunakan oleh Room untuk menyimpan hash identitas skema database (`identity_hash`). Saat aplikasi runtime berjalan, Room mencocokkan hash yang ada di tabel ini dengan hash skema kode yang di-generate saat compile-time untuk memvalidasi integritas skema.
3.  **Mengapa anotasi `@TypeConverter` tidak disarankan untuk menyimpan relasi kompleks seperti `List<ChildObject>` dalam format JSON String?**
    *   *Jawaban*: Karena merusak normalisasi database relasional (melanggar 1NF), menghilangkan kemampuan pengindeksan parsial dan query bersyarat langsung via SQL engine, serta memicu overhead parsing JSON yang membebani CPU dan alokasi memori.
4.  **Apa yang terjadi jika Anda memanggil operasi DAO pemblokir (blocking query) di Main Thread secara default pada Room?**
    *   *Jawaban*: Room akan memicu `IllegalStateException: Cannot access database on the main thread since it may potentially lock the UI for a long period of time`, yang menyebabkan crash aplikasi seketika.
5.  **Bagaimana Room mendeteksi bahwa ada perubahan data pada tabel sehingga memicu emisi baru pada `Flow<T>`?**
    *   *Jawaban*: Room menginjeksikan temporary triggers pada tabel yang relevan di SQLite. Trigger ini memperbarui tabel pelacak internal (`room_table_modification_log`), yang secara reaktif dipantau oleh `InvalidationTracker`.

### Intermediate Questions
6.  **Apa perbedaan mendasar antara `@Embedded` dan `@Relation` pada Room?**
    *   *Jawaban*: `@Embedded` mengintegrasikan seluruh kolom dari sub-objek langsung ke dalam baris tabel induk yang sama (flat hierarchy). Sedangkan `@Relation` memuat data dari entitas yang berada di tabel terpisah melalui sub-queries otomatis berdasarkan parent and entity columns.
7.  **Mengapa setiap kolom anak yang direferensikan dalam `ForeignKey` wajib memiliki index eksplisit di SQLite?**
    *   *Jawaban*: Jika tidak diindeks, setiap operasi `DELETE` atau `UPDATE` pada entitas induk akan memaksa SQLite melakukan *Full Table Scan* pada seluruh tabel anak guna memvalidasi batasan integritas referensial, yang berakibat degradasi drastis performa sistem.
8.  **Apa fungsi method `room.expandProjection` pada argumen KSP compiler?**
    *   *Jawaban*: Argumen ini menginstruksikan Room untuk mendefinisikan seluruh nama kolom secara eksplisit pada query yang menggunakan `SELECT *`, sehingga mengeliminasi variabilitas urutan kolom dari Cursor framework Android dan mengurangi overhead runtime parsing.
9.  **Bagaimana cara kerja atomisitas pada method DAO yang dianotasi `@Transaction` saat mengeksekusi operasi asinkron coroutine?**
    *   *Jawaban*: Room mengalokasikan satu koneksi thread database eksklusif dari connection pool untuk coroutine context tersebut, membungkus eksekusi kode di dalam block `BEGIN TRANSACTION` dan `COMMIT`/`ROLLBACK`, serta menghentikan pembebasan koneksi sampai seluruh inner block coroutine tuntas.
10. **Kapan Anda harus memilih migrasi destruktif (`fallbackToDestructiveMigration`) dan apa bahayanya di lingkungan produksi?**
    *   *Jawaban*: Migrasi destruktif hanya boleh digunakan pada tahap prototyping atau internal testing. Di lingkungan produksi, konfigurasi ini sangat berbahaya karena jika versi skema naik tanpa adanya skrip migrasi, Room akan menghapus seluruh file database beserta seluruh data pengguna lokal yang belum disinkronisasikan (*data loss* total).

### Skenario Kasus Produksi
11. **Skenario 1**: Aplikasi perbankan enterprise mengalami crash bertubi-tubi di produksi dengan stack trace `SQLiteDiskIOException: disk I/O error (code 1802)`. Investigasi menunjukkan ini sering terjadi saat proses sinkronisasi massal data riwayat transaksi offline. Analisis akar penyebabnya dan berikan solusi arsitektural.
    *   *Solusi*: Akar penyebabnya adalah kehabisan *disk space* atau proses checkpoint WAL yang tersendat akibat *transaction starvation* (ada transaksi pembacaan yang tidak pernah ditutup/menggantung lama, mencegah file `.db-wal` di-checkpoint sehingga ukurannya membengkak hingga storage flash memory penuh). Solusinya:
        *   Terapkan batching pada operasi insert (misal: pecah transaksi menjadi chunks sebesar 500-1000 item).
        *   Pastikan tidak ada background Flow observer yang *leaking* (selalu gunakan lifecycle-aware collectors seperti `repeatOnLifecycle`).
        *   Jalankan checkpoint berkala via `PRAGMA wal_checkpoint(TRUNCATE)` saat background sync tuntas dan aplikasi dalam status idle.

12. **Skenario 2**: Anda memperbarui aplikasi dengan menambahkan satu index baru pada entitas `orders`. Anda membuat `Migration(2, 3)` dan menambahkan kode SQL: `CREATE INDEX index_orders_created_at ON orders(created_at)`. Namun saat unit testing dijalankan, `MigrationTestHelper` gagal dengan pesan `Migration didn't properly handle: orders. Expected index ... but found ...`. Mengapa ini terjadi?
    *   *Solusi*: Ini biasanya terjadi karena perbedaan definisi nama index atau flag keunikan (*uniqueness*) antara skema yang di-generate Room (di JSON schema export) dengan perintah SQL manual. Jika di entity Anda menulis `@Index(value = ["created_at"])`, Room meng-generate nama index spesifik (misal: `index_orders_created_at`). Jika SQL manual berbeda karakter (misal: case sensitivity, flag `UNIQUE` terlewat, atau urutan kolom berbeda), Room testing engine akan menganggap skema hasil migrasi tidak identik dengan skema resmi yang diharapkan.

13. **Skenario 3**: Sebuah aplikasi logistik menggunakan Room untuk menampung data pelacakan GPS kurir yang di-update setiap 2 detik. UI menggunakan Flow untuk membaca koordinat terakhir. Kasir mengeluhkan aplikasi sering mengalami micro-stutter (UI thread jank/frame drop). Profiling menunjukkan memory churn tinggi akibat GC (Garbage Collection). Di mana letak kesalahannya?
    *   *Solusi*: `InvalidationTracker` memicu re-query penuh setiap kali tabel termutasi. Emisi update setiap 2 detik menyebabkan DAO query dijalankan terus-menerus, memicu instansiasi objek Entity dan Cursor window buffer baru secara intensif di heap memory, yang akhirnya memicu Stop-The-World Garbage Collection. Solusinya:
        *   Pisahkan state realtime volatile (koordinat kurir) ke dalam *in-memory cache* (`StateFlow` di repository/memory layer).
        *   Tulis batch koordinat ke Room hanya secara periodik (misal: tiap 30 detik atau 1 menit sekali) atau saat aplikasi berpindah ke background, sehingga InvalidationTracker tidak membanjiri pipeline reaktif dengan re-query yang konstan.

---

## 16. SUMMARY
Arsitektur persistence tingkat lanjut pada Android menuntut penguasaan internal database melebihi sekadar operasi CRUD dasar:
1.  **Storage Concurrency**: Pemanfaatan mode WAL memberikan efisiensi tinggi melalui separasi operasi read dan write, namun menuntut manajemen lifecycle koneksi untuk mencegah *checkpoint starvation*.
2.  **Referential Integrity**: Pemanfaatan foreign key constraints, composite index, dan index pada child columns sangat penting untuk menjamin konsistensi data sekaligus mencegah degradasi performa pada tabel berskala masif.
3.  **Schema Evolution**: Skema database di tingkat enterprise harus diperlakukan secara ketat melalui ekspor skema reguler, manual migrations script yang teruji via automated testing, dan eliminasi migrasi destruktif di produksi.
4.  **SSOT & Offline Synchronization**: Penerapan pola Single Source of Truth yang dipadukan dengan Outbox pattern dan resolusi konflik deterministik menjamin keandalan sistem dalam kondisi jaringan marjinal.