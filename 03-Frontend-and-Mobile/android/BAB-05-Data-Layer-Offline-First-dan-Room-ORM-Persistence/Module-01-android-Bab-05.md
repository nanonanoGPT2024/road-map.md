# Bab 05 Module 01: Data Layer, Offline-First, & Room ORM Persistence

---

## SEKSI 01 — IDENTITAS MODUL
* **Domain:** Android Engineering (Advanced Client-Side Architecture)
* **Kategori:** 03-Frontend-and-Mobile
* **Jalur Kurikulum:** Enterprise-Grade Mobile Application Architecture
* **Topik:** Data Layer Pattern, Offline-First Synchronization Engine, & Room ORM Persistence
* **Tingkat Kesulitan:** Advanced / Staff Engineer Level
* **Prasyarat:** Kotlin Coroutines & Asynchronous Flow, Android Jetpack ViewModel, Dependency Injection (Dagger/Hilt), Fundamental SQLite & Relational Database Design.

---

## SEKSI 02 — LEARNING OBJECTIVES
Setelah menyelesaikan modul ini, peserta ajar diharapkan mampu:
1. **Mengonstruksi Arsitektur Data Layer Skala Besar:** Mengimplementasikan pemisahan batas data layer yang bersih (*clean data boundary*) menggunakan Repository Pattern yang mengabstraksi Data Sources lokal dan remote secara deterministik.
2. **Merancang Sistem Offline-First dengan Room ORM:** Membangun *Single Source of Truth* (SSOT) di mana antarmuka pengguna (UI) hanya mengonsumsi data dari persistence storage lokal yang terikat secara reaktif menggunakan Kotlin `Flow`.
3. **Menguasai Mekanisme Internal Room & SQLite:** Menganalisis lifecycle Room persistence, pembuatan query statement runtime, pemanfaatan database transactions, serta mitigasi *threading hazard* pada Android Run Time (ART).
4. **Menerapkan Skema Migrasi Database Tingkat Produksi:** Mengeksekusi Automated & Manual Database Migrations tanpa data loss melalui `Migration` dan `AutoMigrationSpec` yang divalidasi dengan unit test Room Migration.
5. **Membangun Sinkronisasi Dua Arah (*Bi-Directional Sync Engine*):** Merancang arsitektur sinkronisasi data asinkron berbasis *idempotency keys*, status dirty-flagging, dan resolusi konflik deterministik (*Last-Write-Wins* / *Server-Authoritative*).
6. **Menerapkan Security Hardening pada Data Persistence:** Mengamankan data lokal sensitif menggunakan enkripsi database at-rest via SQLCipher dan Android Keystore integration.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: "Network as an Optimization, Not an Assumption"
Dalam arsitektur aplikasi mobile konvensional, developer sering kali memandang jaringan (network) sebagai penyedia data utama: UI meminta data, Repository memanggil REST API, dan database lokal hanya digunakan sebagai *fallback cache* ketika `IOException` tertangkap. Paradigma ini rapuh, menghasilkan UI yang rentan terhadap *loading spinner flickering*, *state tearing*, dan kegagalan total saat berada di kondisi jaringan fluktuatif (*subway tunnel*, *airplane mode*, atau *congested cell tower*).

```
Paradigma Konvensional (Network-First):
[UI Layer] ---> [Repository] ---> [Remote API] (Sukses) ---> Render UI
                                       |
                                    (Gagal)
                                       v
                             [Local Cache] ---> Render Stale Data

Paradigma Enterprise (Offline-First SSOT):
[UI Layer] <================ (Observasi Reaktif) ================= [Room DB (SSOT)]
                                                                        ^
                                                                        | (Write/Upsert)
[Remote API Engine] ---> [Sync/Conflict Resolution] --------------------+
```

### Mental Model SSOT (Single Source of Truth)
Dalam arsitektur **Offline-First**, Room Local Database adalah **satu-satunya sumber kebenaran**. Network layer bertindak sebagai subsistem sinkronisasi di latar belakang (*background data pipe*). 
* **Read Path:** UI Layer **tidak pernah** membaca respon jaringan secara langsung. UI hanya mengamati stream `Flow<T>` dari Room Database via DAO. UI berada dalam status pasif: ia hanya merender apa yang tersimpan secara lokal.
* **Write Path:** Ketika pengguna melakukan tindakan (misalnya: membuat pesanan atau mengubah profil), perubahan ditulis terlebih dahulu ke database lokal dengan status *pending sync* (optimistic update). Sync Engine kemudian mengambil *uncommitted write* tersebut, mengirimkannya ke Remote API, dan memperbarui database lokal berdasarkan respon remote.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Berikut adalah alur end-to-end arsitektur Offline-First Data Layer yang menggabungkan Repository Pattern, Room ORM, Remote Data Source, serta Sync Engine.

```
+---------------------------------------------------------------------------------------+
|                                     UI LAYER                                          |
|            (Compose / Activities / Fragments / StateFlow Collectors)                  |
+---------------------------------------------------------------------------------------+
                                   ^                        |
                (Read: Flow<T>)    |                        | (Write Intent: suspend)
                                   |                        v
+---------------------------------------------------------------------------------------+
|                                  DOMAIN LAYER                                         |
|                     (Use Cases / Interactors / Business Logic)                        |
+---------------------------------------------------------------------------------------+
                                   ^                        |
                   (Domain Models) |                        | (Domain Intentions)
                                   |                        v
+---------------------------------------------------------------------------------------+
|                                   DATA LAYER                                          |
|                                                                                       |
|   +-------------------------------------------------------------------------------+   |
|   |                              Repository Impl                                  |   |
|   |         Orkestrasi Aliran Data, Pemetaan Entity <-> Domain Model,             |   |
|   |                       dan Koordinasi Sinkronisasi                             |   |
|   +-------------------------------------------------------------------------------+   |
|           |                                                       ^                   |
|           | (Observe / Read)                                      |                   |
|           v                                                       | (Background Sync) |
|   +-----------------------+                               +-----------------------+   |
|   | Local Data Source     |                               | Remote Data Source    |   |
|   | (Room DAO Engine)     |                               | (Retrofit / Ktor API) |   |
|   +-----------------------+                               +-----------------------+   |
|           |                                                       ^                   |
|           | SQLite CRUD                                           | HTTP Engine       |
|           v                                                       v                   |
|   +-----------------------+                               +-----------------------+   |
|   |   Room SQLite DB      |                               |      REST / gRPC      |   |
|   |   (SSOT Persistence)  |<==============================|    Remote Servers     |   |
|   +-----------------------+       (Upsert Transactions)   +-----------------------+   |
+---------------------------------------------------------------------------------------+
```

### Alur Detail Siklus Hidup Data (Data Lifecycle Matrix)

```
[ User Interaction ]
         |
         v
[ Repository.updateResource() ]
         |
         +-----> (1) Room DAO: UPDATE resource SET sync_status = 'PENDING_UPDATE'
         |            |
         |            +--> (Trigger Invalidation Tracker) ---> [ Flow Emits to UI (Optimistic) ]
         |
         +-----> (2) RemoteDataSource.patchResource()
                      |
        +-------------+-------------+
        | Success                   | Network Error / Failure
        v                           v
(3a) Room DAO:              (3b) SyncWorker Enqueue via WorkManager:
     UPDATE resource             Room DB mempertahankan status 'PENDING_UPDATE'
     SET sync_status = 'SYNCED'  Worker akan retry saat konektivitas pulih
     WHERE id = :id              UI tetap konsisten dan responsif
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. InvalidationTracker: Jantung Reaktivitas Room
Bagaimana Room mengetahui bahwa suatu data di database telah berubah sehingga `Flow<T>` dapat memancarkan nilai baru?
* Room **tidak** memantau perubahan data melalui trigger native SQLite yang mahal secara performa memori.
* Room mengompilasi tabel bayangan bernama `room_table_modification_tracker`.
* Ketika Anda mengamati tabel `orders` melalui query DAO `@Query("SELECT * FROM orders") fun getOrders(): Flow<List<OrderEntity>>`, Room mendaftarkan observer internal ke `InvalidationTracker`.
* Setiap kali operasi penulisan (`INSERT`, `UPDATE`, `DELETE`) dieksekusi melalui Room DAO, Room secara otomatis mengeksekusi hook di dalam transaksi SQLite yang memperbarui flag versi pada `room_table_modification_tracker`.
* `InvalidationTracker` secara berkala (atau segera setelah transaksi commit) mengecek dirty flag. Jika tabel `orders` termodifikasi, Room mengeksekusi ulang query SQLite tersebut pada worker thread pool (`Dispatchers.IO`) dan memancarkan hasilnya ke downstream `Flow`.

```
[Write Operation (DAO)] ---> [ SQLite Transaction: Write Data + Update Tracker Flag ]
                                                    |
                                                    v
[ InvalidationTracker Observer ] <--- [ Read Tracker via Transaction Commit Callback ]
        |
 (Flag Dirty?)
        |
       YES ---> Re-evaluasi SELECT Query pada Thread IO ---> Emisikan item baru ke Flow
```

### 2. Thread Dispatching & SQLite Connection Pool
* **SQLite Threading Modes:** SQLite engine dasar dapat berjalan dalam mode *Single-Threaded*, *Multi-Threaded*, atau *Serialized*. Di Android, SQLite beroperasi secara serialized atau multi-threaded bergantung konfigurasi WAL (*Write-Ahead Logging*).
* **Write-Ahead Logging (WAL):** Secara default, Android Pie ke atas mengaktifkan WAL untuk Room. WAL memisahkan operasi pembacaan dan penulisan:
  * Pembacaan data (*Reader Connection*) membaca status data dari file database utama (`.db`) dan sebagian dari file WAL (`.db-wal`).
  * Penulisan data (*Writer Connection*) **hanya** menulis ke file WAL, tidak langsung ke database utama.
  * Implikasi: Pembacaan tidak memblokir penulisan, dan penulisan tidak memblokir pembacaan. Namun, beberapa *writer* yang berjalan bersamaan akan tetap terkunci oleh SQLite single-writer lock.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Relasi Kompleks: Embed vs. Relation
Room menyediakan dua paradigma utama untuk pemodelan data non-trivial:

1. **`@Embedded`**:
   Meratakan properti objek turunan ke dalam kolom-kolom tabel induk yang sama.
   * *Gunakan untuk:* Komposisi objek 1:1 murni yang tidak memiliki tabel terpisah (misalnya: `Address` yang merupakan bagian dari `UserProfile`).
   * *Overhead:* Nol query tambahan. SQLite memperlakukannya sebagai kumpulan kolom biasa di satu tabel fisik.

2. **`@Relation` (1:1, 1:N, N:M)**:
   Mendefinisikan pemetaan deklaratif antar entitas yang terpisah di tabel berbeda.
   * Relasi ini didefinisikan dalam data class perantara (POJO), bukan di `@Entity`.
   * *Mekanisme Internal:* Room mengeksekusi query untuk entitas induk, mengekstrak kunci relasinya, memecah daftar kunci menjadi chunk (`MAX_BIND_PARAMETER` SQLite adalah 999 atau 32766 tergantung level API), lalu mengeksekusi `SELECT ... WHERE parentId IN (...)` untuk mengambil entitas anak. Room kemudian memetakan relasi ini secara otomatis di memori pada thread IO.

### Strategi Migrasi Skema Produksi
Ketika Anda merilis versi baru aplikasi dengan skema tabel yang berbeda:
* **`fallbackToDestructiveMigration()` (BAHAYA TINGKAT TINGGI):** Menghapus seluruh file SQLite lokal saat skema versi dinaikkan dan membuat ulang database dari nol. Ini tidak boleh digunakan di lingkungan produksi enterprise karena akan menghapus seluruh data offline pengguna yang belum tersinkronisasi.
* **Manual Migration:** Anda mendefinisikan kelas turunan dari `Migration(from, to)` dan menulis SQL DDL imperatif murni (`ALTER TABLE`, `CREATE TABLE`).
* **AutoMigration:** Diperkenalkan pada Room modern (v2.40+), Room menghasilkan file skema JSON saat kompilasi via *ksp/kapt*. Room membandingkan skema JSON versi $N$ dan versi $N+1$, lalu menghasilkan script SQL migrasi otomatis secara internal. Jika terjadi ambiguitas (misal: kolom diganti nama atau dihapus), developer wajib mendefinisikan `AutoMigrationSpec`.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi dasar Room ORM lengkap: Entity, DAO dengan Transaction, Invalidation Stream Flow, dan konfigurasi Database.

### 1. Deklarasi Entity & Type Converters
```kotlin
package com.enterprise.core.database.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey
import androidx.room.TypeConverter
import java.time.Instant

enum class SyncState {
    SYNCED, PENDING_INSERT, PENDING_UPDATE, PENDING_DELETE
}

class DatabaseConverters {
    @TypeConverter
    fun fromInstant(value: Instant?): Long? = value?.toEpochMilli()

    @TypeConverter
    fun toInstant(value: Long?): Instant? = value?.let { Instant.ofEpochMilli(it) }

    @TypeConverter
    fun fromSyncState(value: SyncState): String = value.name

    @TypeConverter
    fun toSyncState(value: String): SyncState = SyncState.valueOf(value)
}

@Entity(tableName = "customers")
data class CustomerEntity(
    @PrimaryKey
    @ColumnInfo(name = "customer_id")
    val customerId: String,

    @ColumnInfo(name = "full_name")
    val fullName: String,

    @ColumnInfo(name = "email")
    val email: String,

    @ColumnInfo(name = "updated_at")
    val updatedAt: Instant,

    @ColumnInfo(name = "sync_state", defaultValue = "SYNCED")
    val syncState: SyncState
)
```

### 2. Room DAO
```kotlin
package com.enterprise.core.database.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Transaction
import androidx.room.Update
import com.enterprise.core.database.entity.CustomerEntity
import com.enterprise.core.database.entity.SyncState
import kotlinx.coroutines.flow.Flow

@Dao
interface CustomerDao {

    @Query("SELECT * FROM customers WHERE customer_id = :id LIMIT 1")
    fun getCustomerByIdFlow(id: String): Flow<CustomerEntity?>

    @Query("SELECT * FROM customers WHERE sync_state != 'SYNCED'")
    suspend fun getUnsyncedCustomers(): List<CustomerEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertCustomer(customer: CustomerEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertCustomers(customers: List<CustomerEntity>)

    @Query("UPDATE customers SET sync_state = :syncState WHERE customer_id = :id")
    suspend fun updateSyncState(id: String, syncState: SyncState)

    @Query("DELETE FROM customers WHERE customer_id = :id")
    suspend fun deleteCustomerById(id: String)

    @Transaction
    suspend fun reconcileCustomerState(customer: CustomerEntity, syncState: SyncState) {
        upsertCustomer(customer)
        updateSyncState(customer.customerId, syncState)
    }
}
```

### 3. Room Database Builder Setup
```kotlin
package com.enterprise.core.database

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.TypeConverters
import com.enterprise.core.database.dao.CustomerDao
import com.enterprise.core.database.entity.CustomerEntity
import com.enterprise.core.database.entity.DatabaseConverters

@Database(
    entities = [CustomerEntity::class],
    version = 1,
    exportSchema = true
)
@TypeConverters(DatabaseConverters::class)
abstract class AppDatabase : RoomDatabase() {

    abstract fun customerDao(): CustomerDao

    companion object {
        @Volatile
        private var INSTANCE: AppDatabase? = null

        fun getInstance(context: Context): AppDatabase {
            return INSTANCE ?: synchronized(this) {
                INSTANCE ?: Room.databaseBuilder(
                    context.applicationContext,
                    AppDatabase::class.java,
                    "enterprise_commerce.db"
                )
                .build()
                .also { INSTANCE = it }
            }
        }
    }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Mari kita bedah arsitektur kode di atas:

1. **`exportSchema = true` di `@Database`:**
   Mengharuskan Room meng-export skema skrip JSON ke direktori build yang telah dikonfigurasi di file `build.gradle.kts` via KSP. Skema JSON ini menyimpan representasi SHA-256 dari seluruh hash tabel yang diverifikasi pada runtime SQLite untuk memvalidasi kompatibilitas versi saat inisialisasi aplikasi.
2. **`@TypeConverters(DatabaseConverters::class)`:**
   SQLite hanya mendukung tipe data primitif: `NULL`, `INTEGER`, `REAL`, `TEXT`, dan `BLOB`. Custom Type Converter memungkinkan konversi transparan dua arah antara tipe kelas Kotlin kompleks (seperti `java.time.Instant`) dengan nilai primitif (`Long` / Epoch Milliseconds) tanpa mengorbankan type safety.
3. **`fun getCustomerByIdFlow(id: String): Flow<CustomerEntity?>`:**
   Perhatikan ketiadaan kata kunci `suspend`. Fungsi DAO yang mengembalikan `Flow` **tidak boleh** dideklarasikan dengan `suspend`. Room secara otomatis mendaftarkan Invalidation Tracker secara asinkron dan mengeksekusi pembacaan pada *Room background query dispatcher*.
4. **`@Transaction suspend fun reconcileCustomerState(...)`:**
   Anotasi `@Transaction` membungkus seluruh instruksi di dalam blok metode tersebut menggunakan:
   ```sql
   BEGIN TRANSACTION;
   -- Eksekusi upsertCustomer()
   -- Eksekusi updateSyncState()
   COMMIT;
   ```
   Jika terjadi `SQLException` atau kegagalan sistem di tengah proses, transaksi di-*rollback* secara otomatis. Anotasi ini menjamin integritas data (prinsip *Atomicity* ACID).
5. **`@Volatile private var INSTANCE`:**
   Kata kunci `@Volatile` menjamin visibilitas perubahan nilai variabel `INSTANCE` secara langsung ke seluruh CPU core caches. Operasi double-checked locking mencegah terjadinya duplikasi alokasi instance RoomDatabase (yang merupakan objek berat pemakan resource SQLite connection pool) ketika dua thread mencoba memanggil `getInstance` secara paralel.

---

## SEKSI 09 — STUDI KASUS NYATA
**Domain:** Logistik & Distribusi Enterprise (Last-Mile Parcel Delivery Engine).

### Masalah Nyata di Lapangan
Kurir pengiriman logistik sering beroperasi di wilayah terpencil, basemen gedung bertingkat, atau pedesaan dengan status jaringan *intermittent* (terputus-putus) atau *zero-connectivity*. 
* Kurir harus tetap dapat mengonfirmasi pengiriman barang (Proof of Delivery / POD) beserta tanda tangan digital, koordinat GPS, dan foto penerima.
* Jika kurir menekan "Submit Delivery", data tidak boleh hilang meskipun aplikasi di-kill paksa oleh OS (Android LMK - Low Memory Killer).
* Begitu jaringan terhubung kembali, aplikasi harus mengeksekusi proses pengiriman data secara otomatis dan menyelesaikan konflik jika status delivery package telah dibatalkan oleh dispatcher server.

### Solusi Arsitektural
1. **SSOT Local-First Store:** Menggunakan Room ORM sebagai penyimpanan mutlak setiap status paket.
2. **Optimistic Status Mutation:** Data POD dicatat langsung dengan flag `sync_status = PENDING_UPLOAD`.
3. **Guaranteed Delivery dengan WorkManager:** WorkManager mengonsumsi tabel Room, membaca entity yang belum tersinkronisasi, dan menjamin eksekusi pengiriman HTTP multipart dengan kebijakan *exponential backoff retry*.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi sistematis production-ready untuk *Offline-First Delivery Processing Engine*.

### 1. Entitas & Relasi
```kotlin
package com.enterprise.logistics.data.local.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey
import java.time.Instant

enum class ParcelStatus {
    IN_TRANSIT, DELIVERED, RETURNED, FAILED
}

enum class MutationSyncStatus {
    SYNCED, PENDING_SYNC, FAILED_FATAL
}

@Entity(
    tableName = "parcels",
    indices = [Index(value = ["tracking_number"], unique = true)]
)
data class ParcelEntity(
    @PrimaryKey
    @ColumnInfo(name = "parcel_id")
    val parcelId: String,

    @ColumnInfo(name = "tracking_number")
    val trackingNumber: String,

    @ColumnInfo(name = "recipient_name")
    val recipientName: String,

    @ColumnInfo(name = "delivery_address")
    val deliveryAddress: String,

    @ColumnInfo(name = "status")
    val status: ParcelStatus,

    @ColumnInfo(name = "sync_status")
    val syncStatus: MutationSyncStatus,

    @ColumnInfo(name = "version_stamp")
    val versionStamp: Long,

    @ColumnInfo(name = "updated_at")
    val updatedAt: Instant
)

@Entity(
    tableName = "delivery_proofs",
    foreignKeys = [
        ForeignKey(
            entity = ParcelEntity::class,
            parentColumns = ["parcel_id"],
            childColumns = ["parcel_parent_id"],
            onDelete = ForeignKey.CASCADE
        )
    ],
    indices = [Index(value = ["parcel_parent_id"], unique = true)]
)
data class DeliveryProofEntity(
    @PrimaryKey
    @ColumnInfo(name = "proof_id")
    val proofId: String,

    @ColumnInfo(name = "parcel_parent_id")
    val parcelParentId: String,

    @ColumnInfo(name = "signature_svg")
    val signatureSvg: String,

    @ColumnInfo(name = "latitude")
    val latitude: Double,

    @ColumnInfo(name = "longitude")
    val longitude: Double,

    @ColumnInfo(name = "captured_at")
    val capturedAt: Instant
)
```

### 2. DAO Tingkat Lanjut dengan Atomic Upsert
```kotlin
package com.enterprise.logistics.data.local.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Transaction
import com.enterprise.logistics.data.local.entity.DeliveryProofEntity
import com.enterprise.logistics.data.local.entity.MutationSyncStatus
import com.enterprise.logistics.data.local.entity.ParcelEntity
import com.enterprise.logistics.data.local.entity.ParcelStatus
import kotlinx.coroutines.flow.Flow
import java.time.Instant

@Dao
interface LogisticsDao {

    @Query("SELECT * FROM parcels ORDER BY updated_at DESC")
    fun observeAllParcels(): Flow<List<ParcelEntity>>

    @Query("SELECT * FROM parcels WHERE parcel_id = :parcelId LIMIT 1")
    fun observeParcelById(parcelId: String): Flow<ParcelEntity?>

    @Query("SELECT * FROM parcels WHERE sync_status = 'PENDING_SYNC'")
    suspend fun getPendingSyncParcels(): List<ParcelEntity>

    @Query("SELECT * FROM delivery_proofs WHERE parcel_parent_id = :parcelId LIMIT 1")
    suspend fun getProofForParcel(parcelId: String): DeliveryProofEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertParcels(parcels: List<ParcelEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertProof(proof: DeliveryProofEntity)

    @Query("UPDATE parcels SET status = :status, sync_status = :syncStatus, updated_at = :timestamp WHERE parcel_id = :parcelId")
    suspend fun updateParcelStatus(
        parcelId: String,
        status: ParcelStatus,
        syncStatus: MutationSyncStatus,
        timestamp: Instant
    )

    @Transaction
    suspend fun submitDeliveryProof(
        parcelId: String,
        proof: DeliveryProofEntity,
        timestamp: Instant
    ) {
        insertProof(proof)
        updateParcelStatus(
            parcelId = parcelId,
            status = ParcelStatus.DELIVERED,
            syncStatus = MutationSyncStatus.PENDING_SYNC,
            timestamp = timestamp
        )
    }
}
```

### 3. Remote Data Source & Network Models
```kotlin
package com.enterprise.logistics.data.remote

import com.enterprise.logistics.data.local.entity.ParcelStatus
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.PUT
import retrofit2.http.Path

data class ParcelNetworkDto(
    val id: String,
    val trackingNumber: String,
    val recipient: String,
    val address: String,
    val parcelStatus: String,
    val version: Long,
    val lastModifiedEpoch: Long
)

data class DeliveryConfirmationPayload(
    val parcelId: String,
    val proofSignature: String,
    val lat: Double,
    val lng: Double,
    val deliveryTimestamp: Long,
    val localVersionStamp: Long
)

data class SyncResponseDto(
    val serverAccepted: Boolean,
    val currentServerVersion: Long,
    val conflictResolvedState: String?
)

interface LogisticsApiService {
    @GET("/v1/courier/parcels")
    suspend fun fetchAssignedParcels(): Response<List<ParcelNetworkDto>>

    @PUT("/v1/courier/parcels/{id}/confirm-delivery")
    suspend fun syncDeliveryConfirmation(
        @Path("id") id: String,
        @Body payload: DeliveryConfirmationPayload
    ): Response<SyncResponseDto>
}
```

### 4. Enterprise Repository Implementation
```kotlin
package com.enterprise.logistics.data.repository

import com.enterprise.logistics.data.local.dao.LogisticsDao
import com.enterprise.logistics.data.local.entity.DeliveryProofEntity
import com.enterprise.logistics.data.local.entity.MutationSyncStatus
import com.enterprise.logistics.data.local.entity.ParcelEntity
import com.enterprise.logistics.data.local.entity.ParcelStatus
import com.enterprise.logistics.data.remote.DeliveryConfirmationPayload
import com.enterprise.logistics.data.remote.LogisticsApiService
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.withContext
import java.io.IOException
import java.time.Instant
import java.util.UUID

interface ParcelRepository {
    fun getParcelsStream(): Flow<List<ParcelEntity>>
    suspend fun refreshParcelsFromServer(): Result<Unit>
    suspend fun recordDeliveryLocally(parcelId: String, signatureSvg: String, lat: Double, lng: Double): Result<Unit>
    suspend fun syncPendingParcels(): Result<Unit>
}

class ParcelRepositoryImpl(
    private val localDao: LogisticsDao,
    private val remoteApi: LogisticsApiService,
    private val ioDispatcher: CoroutineDispatcher
) : ParcelRepository {

    override fun getParcelsStream(): Flow<List<ParcelEntity>> = localDao.observeAllParcels()

    override suspend fun refreshParcelsFromServer(): Result<Unit> = withContext(ioDispatcher) {
        runCatching {
            val response = remoteApi.fetchAssignedParcels()
            if (!response.isSuccessful) {
                throw IOException("Server returned HTTP error: ${response.code()}")
            }

            val body = response.body().orEmpty()
            val entities = body.map { dto ->
                ParcelEntity(
                    parcelId = dto.id,
                    trackingNumber = dto.trackingNumber,
                    recipientName = dto.recipient,
                    deliveryAddress = dto.address,
                    status = ParcelStatus.valueOf(dto.parcelStatus),
                    syncStatus = MutationSyncStatus.SYNCED,
                    versionStamp = dto.version,
                    updatedAt = Instant.ofEpochMilli(dto.lastModifiedEpoch)
                )
            }
            localDao.upsertParcels(entities)
        }
    }

    override suspend fun recordDeliveryLocally(
        parcelId: String,
        signatureSvg: String,
        lat: Double,
        lng: Double
    ): Result<Unit> = withContext(ioDispatcher) {
        runCatching {
            val now = Instant.now()
            val proof = DeliveryProofEntity(
                proofId = UUID.randomUUID().toString(),
                parcelParentId = parcelId,
                signatureSvg = signatureSvg,
                latitude = lat,
                longitude = lng,
                capturedAt = now
            )
            localDao.submitDeliveryProof(parcelId, proof, now)
        }
    }

    override suspend fun syncPendingParcels(): Result<Unit> = withContext(ioDispatcher) {
        runCatching {
            val pendingItems = localDao.getPendingSyncParcels()
            
            for (parcel in pendingItems) {
                val proof = localDao.getProofForParcel(parcel.parcelId) ?: continue
                
                val payload = DeliveryConfirmationPayload(
                    parcelId = parcel.parcelId,
                    proofSignature = proof.signatureSvg,
                    lat = proof.latitude,
                    lng = proof.longitude,
                    deliveryTimestamp = proof.capturedAt.toEpochMilli(),
                    localVersionStamp = parcel.versionStamp
                )

                try {
                    val response = remoteApi.syncDeliveryConfirmation(parcel.parcelId, payload)
                    if (response.isSuccessful && response.body()?.serverAccepted == true) {
                        localDao.updateParcelStatus(
                            parcelId = parcel.parcelId,
                            status = parcel.status,
                            syncStatus = MutationSyncStatus.SYNCED,
                            timestamp = Instant.now()
                        )
                    } else if (response.code() == 409) {
                        // Resolusi Konflik: State ditolak oleh Server Engine
                        val syncResponse = response.body()
                        val serverState = syncResponse?.conflictResolvedState?.let {
                            ParcelStatus.valueOf(it)
                        } ?: ParcelStatus.FAILED

                        localDao.updateParcelStatus(
                            parcelId = parcel.parcelId,
                            status = serverState,
                            syncStatus = MutationSyncStatus.FAILED_FATAL,
                            timestamp = Instant.now()
                        )
                    }
                } catch (e: Exception) {
                    // Kegagalan transmisi: Biarkan item tetap PENDING_SYNC untuk siklus berikutnya
                    continue
                }
            }
        }
    }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Fitur / Dimensi | Room ORM | Raw SQLite (`SQLiteOpenHelper`) | DataStore (Preferences/Proto) | Realm / Mongo Device Sync |
| :--- | :--- | :--- | :--- | :--- |
| **Abstraksi & Boilerplate** | Rendah (Anotasi KSP/Kapt otomatis) | Sangat Tinggi (Manual cursor mapping) | Sangat Rendah (Key-value sederhana) | Rendah (Model deklaratif) |
| **Validasi Skema Kompilasi** | **Ya** (Compile-time query verification) | **Tidak** (Runtime SQL crash risk) | Parsial (Hanya Proto Schema) | Tidak |
| **Relasi Kompleks (1:N, N:M)** | Sangat Baik (Native `@Relation`, `@Junction`) | Manual via Join Queries | **Tidak Cocok** (Hanya untuk Flat Models) | Sangat Baik (Graph Model) |
| **Ukuran Binary (APK Size)** | Minimal (~150 KB library dependency) | 0 KB (Native Android Framework) | Minimal (~50 KB) | Besar (+3 MB native C++ SO files) |
| **Reactive Observability** | Native Kotlin `Flow`, RxJava, Paging 3 | Tidak (Harus bangun wrapper manual) | Native Kotlin `Flow` | Live Data / Built-in Change Listeners |
| **Multiplatform Readiness** | Tersedia (Room KMP di rilis terbaru) | Terikat pada Platform Android | Tersedia KMP | Tersedia KMP |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. SQLite Cursor Window Allocation Overhead ( Ukuran Baris > 2MB )
* **Mekanisme Kegagalan:** SQLite membaca data dari disk ke antarmuka runtime Android melalui `CursorWindow`. Buffer default `CursorWindow` dibatasi hingga 2 MB per baris data. Jika Anda menyimpan string Base64 gambar POD atau blob besar langsung di dalam entity, query Room akan memicu `android.database.sqlite.SQLiteBlobTooBigException: Row too big to fit into CursorWindow`.
* **Mitigasi:** Jangan simpan data biner (foto, audio, PDF) langsung di kolom SQLite. Simpan biner tersebut ke Private File Storage Android (`context.filesDir`), dan simpan **path string** file tersebut ke kolom database Room.

### 2. State Tearing Akibat Transaksi Parsial
* **Mekanisme Kegagalan:** Jika pembaruan beberapa tabel dilakukan tanpa membungkusnya dalam satu `@Transaction`, dan OS mematikan proses di tengah eksekusi, database akan berada dalam kondisi inkonsisten (*torn state*). Misalnya: baris `delivery_proof` tersimpan, tetapi status tabel `parcels` tetap `IN_TRANSIT`.
* **Mitigasi:** Seluruh mutasi multitable pada DAO **wajib** menggunakan anotasi `@Transaction` atau `RoomDatabase.withTransaction {}`.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Memanggil Query Database pada Main Thread
* **Dampak:** Membekukan antarmuka pengguna, memicu frame drop, dan melempar exception:
  `java.lang.IllegalStateException: Cannot access database on the main thread since it may potentially lock the UI for a long period of time.`
* **Solusi Anti-Pola:** Jangan pernah menggunakan `.allowMainThreadQueries()` di production! Selalu definisikan fungsi DAO sebagai `suspend` atau kembalikan `Flow<T>`, dan pastikan eksekusi dipindahkan ke thread pool latar belakang:
```kotlin
// SALAH
val parcels = database.logisticsDao().getAllParcelsSync()

// BENAR
val parcels = withContext(Dispatchers.IO) {
    database.logisticsDao().getAllParcels()
}
```

### 2. N+1 Query Problem Saat Mengambil Relasi
* **Dampak:** Mengeksekusi satu query untuk mendapatkan list parent, lalu melakukan loop imperatif untuk query entitas child dari masing-masing parent:
```kotlin
// ANTI-PATTERN: N+1 Database Calls!
val parcels = dao.getAllParcels()
parcels.forEach { parcel ->
    parcel.proof = dao.getProofByParcelId(parcel.id) // Query dieksekusi N kali
}
```
* **Solusi Benar:** Gunakan POJO class dengan anotasi `@Relation` sehingga Room mengeksekusi fetch secara batch dalam 2 query SQLite:
```kotlin
data class ParcelWithProof(
    @Embedded val parcel: ParcelEntity,
