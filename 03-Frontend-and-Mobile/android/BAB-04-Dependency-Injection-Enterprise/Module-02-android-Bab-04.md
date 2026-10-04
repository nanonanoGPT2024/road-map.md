# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis dan Membedah Internal Code Generation Dagger/Hilt**: Memahami siklus hidup bytecode yang dihasilkan oleh KSP/KAPT, termasuk mekanisme *Double-Check Locking* pada scoped bindings.
- **Mengimplementasikan Runtime Parameter Injection**: Menguasai integrasi `@AssistedInject` dan `@AssistedFactory` untuk dependency yang membutuhkan parameter runtime dinamis (misalnya ViewModel saved state atau payload intent).
- **Membangun Arsitektur Multi-Module DI Berbasis Dynamic Feature Modules (DFM)**: Memecahkan kendala siklus dependensi terbalik (*inverted dependency*) pada DFM menggunakan Custom Component Dependencies dan `@EntryPoint`.
- **Mendesain Lifecycle-Aware Custom Scopes**: Merancang, mengisolasi, dan membersihkan scope berbasis sesi pengguna (`@UserSessionScope`) guna mencegah memory leak pada state otentikasi.
- **Mengoptimalkan Metrik Performa Build & Runtime**: Mengurangi waktu kompilasi Dagger via KSP, meminimalisir overhead binary size, dan mengaudit graph dependensi secara otomatis via CI/CD.

---

## 2. Prerequisite

Sebelum memulai modul ini, Anda wajib menguasai:
- **Dasar Dependency Injection Android**: Penggunaan dasar `@Inject`, `@Provides`, `@Binds`, `@Singleton`, dan `@InstallIn(SingletonComponent::class)`.
- **Kotlin Advanced Concurrency**: Coroutine Scopes, structured concurrency, dan thread safety (`@Volatile`, mutex).
- **Gradle Multi-Module Architecture**: Konfigurasi multi-project build (`api`, `implementation`, modul fitur, modul core).
- **Android App Bundle & Dynamic Delivery**: Konsep dasar modul on-demand dynamic feature split APK.

---

## 3. Concept & Internal Architecture

### 3.1 Dagger/Hilt Code Generation Mechanics (KSP/KAPT Pipeline)

Dagger tidak menggunakan runtime reflection untuk resolusi dependensi. Dagger adalah sebuah *compile-time graph validation and code generation engine*. Ketika Anda menggunakan KSP (Kotlin Symbol Processing) atau KAPT, Dagger membaca *Abstract Syntax Tree* (AST) kode Anda dan menghasilkan Java/Kotlin class konkret.

```
Source Code (.kt) 
       │
       ▼
 [KSP / KAPT] ──(Dagger Processor)──► Graph Validation (Directed Acyclic Graph)
       │                                     │
       ▼                                     ▼
Generated Code:                       Error: Cyclic Dependency / Missing Binding
  - Foo_Factory.java                  (Compile-time Error)
  - SingletonComponentImpl.java
       │
       ▼
  Bytecode (.class) ──► DEX Compilation
```

Bagi setiap kelas yang dianotasi dengan `@Inject constructor`:
1. Dagger membuat `ClassName_Factory.java` yang mengimplementasikan antarmuka `dagger.internal.Factory<T>`.
2. Antarmuka `Factory<T>` memperluas antarmuka `Provider<T>`, yang menyediakan method `T get()`.

### 3.2 Thread Safety dan Scoping: Anatomi `DoubleCheck.java`

Saat dependensi diberi anotasi scope (misalnya `@Singleton` atau custom scope), Dagger membungkus factory penyedia dependensi tersebut ke dalam `dagger.internal.DoubleCheck<T>`. 

Kelas internal ini mengimplementasikan pola **Double-Checked Locking Pattern** dengan variabel `volatile` untuk memastikan instansiasi thread-safe bernilai tunggal per lifecycle scope tanpa overhead sinkronisasi berlebih:

```java
// Representasi internal dagger.internal.DoubleCheck<T>
public final class DoubleCheck<T> implements Provider<T>, Lazy<T> {
    private static final Object UNINITIALIZED = new Object();
    private volatile Provider<T> provider;
    private volatile Object instance = UNINITIALIZED;

    private DoubleCheck(Provider<T> provider) {
        this.provider = provider;
    }

    @Override
    public T get() {
        Object result = instance;
        if (result == UNINITIALIZED) {
            synchronized (this) {
                result = instance;
                if (result == UNINITIALIZED) {
                    result = provider.get();
                    instance = recheck(instance, result);
                    /* Nulling out the provider to avoid leaking references */
                    provider = null; 
                }
            }
        }
        return (T) result;
    }

    public static Object recheck(Object oldInstance, Object newInstance) {
        if (oldInstance != UNINITIALIZED && oldInstance != newInstance) {
            throw new IllegalStateException("Scoped provider was invoked concurrently "
                + "and returned different results: " + oldInstance + " & " + newInstance);
        }
        return newInstance;
    }
}
```

*Analisis Kritis:* 
Jika sebuah dependency di-scope, ia akan tetap hidup di memori selama instance Component yang menampungnya masih ada. Kesalahan memilih scope dapat mengakibatkan memory leak skala besar (misalnya: menahan Activity Context di dalam `@Singleton`).

---

### 3.3 Subcomponents vs Component Dependencies

Terdapat dua strategi arsitektural untuk memecah graph dependensi:

| Kriteria | Subcomponents (`@Subcomponent`) | Component Dependencies (`dependencies = [...]`) |
| :--- | :--- | :--- |
| **Relasi Graf** | Hubungan induk-anak (*Parent-Child inheritance*). Mengakses seluruh graph Parent secara implisit. | Deklaratif interface (*Explicit Exposure*). Child hanya dapat mengakses method yang di-expose secara publik oleh Parent. |
| **Enkapsulasi** | Rendah; anak mewarisi seluruh binding tanpa restriksi. | Tinggi; parent harus mendeklarasikan eksplisit apa yang boleh diakses modul lain. |
| **Kompilasi** | Kompilasi monolitik; Parent harus mengetahui eksistensi Subcomponent (memicu re-compile Parent saat Subcomponent berubah). | Kompilasi terisolasi; modul dapat dikompilasi secara independen tanpa memicu invalidasi build cache modul core. |
| **Dynamic Feature (DFM)** | **Tidak Kompatibel** secara natural karena ketergantungan circular. | **Wajib Digunakan** untuk DFM. |

---

### 3.4 Dynamic Feature Module (DFM) Inversion Dilemma

Pada arsitektur Dynamic Feature Module:
- Modul `:app` bergantung pada modul `:core`.
- Modul `:feature_payment` (Dynamic Feature) bergantung pada modul `:app`.
- Modul `:app` **TIDAK BISA** memiliki dependensi waktu kompilasi (*compile-time dependency*) ke modul `:feature_payment`.

Hilt secara default mengasumsikan pohon komponen monolitik (`SingletonComponent` berada di `:app`). Jika dynamic feature memerlukan dependency yang tidak diekspos oleh `:app`, atau jika dynamic feature ingin menyediakan sub-graph miliknya sendiri, dependensi standar Hilt akan pecah. Solusinya adalah pola **EntryPoint Bridge Pattern** dan **Custom Dynamic Feature Component**.

---

## 4. Why & What

### Mengapa Pendekatan Hilt Dasar Tidak Cukup untuk Enterprise?
1. **Dynamic Delivery Limitations**: Hilt standar (`@AndroidEntryPoint`) di dalam DFM memicu kegagalan kompilasi karena Hilt mencoba menghasilkan kode ke dalam `SingletonComponent` yang berlokasi di modul `:app`, menyebabkan circular dependency.
2. **Lifecycle Mismatch (User Session)**: Enterprise apps memiliki siklus autentikasi (Login -> Active Token -> Inactive -> Logout). Menyimpan token dan client jaringan di `@Singleton` mengharuskan mutabilitas state (`var token: String?`), yang rawan *race conditions* dan *session leakage* antar akun pengguna yang berbeda pada perangkat yang sama.
3. **Runtime-Assisted Parameter Injection**: Seringkali dependency membutuhkan parameter runtime dinamis yang baru diketahui saat runtime (misal: ID order saat navigasi). Dagger murni mengharuskan pembuatan factory manual tanpa type-safety bawaan jika tidak menggunakan `@AssistedInject`.

---

## 5. How (Workflow Detail)

### Alur Kerja Implementasi DFM EntryPoint & Dynamic Scope Isolation

```
[Dynamic Feature Activity (DFM)]
            │
            ├─► 1. Ambil ApplicationContext via EntryPointAccessors
            │
[EntryPointAccessors]
            │
            ├─► 2. Query SingletonComponent via Interface @EntryPoint
            │
[FeatureDependencies Interface]
            │
            ├─► 3. Dapatkan Shared Core Dependencies (Network, Database)
            │
[DFM Internal Component Builder]
            │
            ├─► 4. Rakit DFM Internal Component (FeatureScope)
            │
[Injected DFM ViewModels / UseCases]
```

### Prosedur Implementasi:
1. **Definisikan Core Component Interface**: Modul `:core` mendefinisikan interface dependensi publik.
2. **Expose Core Dependencies di `:app`**: Modul `:app` mengimplementasikan binding Hilt standar.
3. **Gunakan `@EntryPoint` di Modul Core**: Berfungsi sebagai jembatan tipe aman (*type-safe bridge*).
4. **Definisikan Custom Scope & Component di Modul DFM**: Modul dynamic feature membangun Dagger Component sendiri dengan mendeklarasikan component core sebagai dependency.

---

## 6. Analogy & Diagram ASCII

### Analogi Arsitektur: Listrik Gedung Perkantoran (Subcomponents vs DFM Component Dependencies)

- **Subcomponent (Sistem Terpusat)**: Seperti kabel listrik internal satu lantai. Mengambil daya bebas dari panel pusat gedung. Jika kabel lantai 3 diubah jalurnya, teknisi gedung harus mematikan panel induk satu gedung (Full Re-compilation).
- **Component Dependencies (Sistem Stopkontak Standar/DFM)**: Seperti gedung yang menyewakan ruangan ke pihak ketiga. Gedung hanya menyediakan stopkontak universal standar industri (`@EntryPoint`). Penyewa membawa generator atau panel mereka sendiri (DFM Component) dan mencolokkannya ke stopkontak gedung tanpa perlu gedung mengetahui barang apa yang dicolokkan ke dalamnya.

```
       +---------------------------------------------+
       |             :app (Module)                   |
       |  +---------------------------------------+  |
       |  |          SingletonComponent           |  |
       |  |  Provides: OkHttpClient, Database    |  |
       |  +-------------------+-------------------+  |
       +----------------------|----------------------+
                              |
                     implements & exposes
                              |
       +----------------------v----------------------+
       |             :core (Module)                  |
       |  +---------------------------------------+  |
       |  |  @EntryPoint CoreDependencies         |  |
       |  |  fun provideOkHttpClient(): OkHttp    |  |
       |  +-------------------+-------------------+  |
       +----------------------|----------------------+
                              |
                      consumed at runtime
                              |
       +----------------------v----------------------+
       |      :feature_payment (Dynamic Feature)     |
       |  +---------------------------------------+  |
       |  |  @PaymentFeatureComponent             |  |
       |  |  (dependencies = [CoreDependencies]) |  |
       |  |                                       |  |
       |  |  Provides: PaymentRepository,         |  |
       |  |            PaymentViewModel           |  |
       |  +---------------------------------------+  |
       +---------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Runtime Assisted Injection dengan `@AssistedInject`

Seringkali kita membutuhkan dependency yang hanya tersedia pada runtime (contoh: `orderId` dari safe-args navigation) dikombinasikan dengan dependensi yang di-resolve oleh Dagger (contoh: `PaymentRepository`).

#### Definisi Factory & Injeksi:
```kotlin
package com.enterprise.order.presentation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import com.enterprise.order.domain.PaymentRepository
import dagger.assisted.Assisted
import dagger.assisted.AssistedFactory
import dagger.assisted.AssistedInject

class OrderDetailViewModel @AssistedInject constructor(
    private val paymentRepository: PaymentRepository,
    @Assisted private val orderId: String,
    @Assisted private val referralCode: String?
) : ViewModel() {

    @AssistedFactory
    interface Factory {
        fun create(
            orderId: String,
            referralCode: String?
        ): OrderDetailViewModel
    }

    companion object {
        fun provideFactory(
            assistedFactory: Factory,
            orderId: String,
            referralCode: String?
        ): ViewModelProvider.Factory = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return assistedFactory.create(orderId, referralCode) as T
            }
        }
    }
}
```

#### Pemanggilan pada Android Activity / Fragment:
```kotlin
package com.enterprise.order.presentation

import android.os.Bundle
import androidx.activity.viewModels
import androidx.appcompat.app.AppCompatActivity
import dagger.hilt.android.AndroidEntryPoint
import javax.inject.Inject

@AndroidEntryPoint
class OrderDetailActivity : AppCompatActivity() {

    @Inject
    lateinit var viewModelFactory: OrderDetailViewModel.Factory

    private val viewModel: OrderDetailViewModel by viewModels {
        val orderId = intent.getStringExtra("EXTRA_ORDER_ID") 
            ?: throw IllegalStateException("Order ID required")
        val referral = intent.getStringExtra("EXTRA_REFERRAL")
        
        OrderDetailViewModel.provideFactory(viewModelFactory, orderId, referral)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // ViewModel terinisialisasi secara type-safe dengan dependency Dagger + runtime params
    }
}
```

---

### 7.2 Practical Example: Multi-Module Dynamic Feature DI Bridge

#### 1. Modul `:core-di` (Akses Bersama)
Definisikan contract jembatan dependensi:

```kotlin
package com.enterprise.core.di

import okhttp3.OkHttpClient
import retrofit2.Retrofit
import dagger.hilt.EntryPoint
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent

@EntryPoint
@InstallIn(SingletonComponent::class)
interface CoreFeatureDependencies {
    fun okHttpClient(): OkHttpClient
    fun baseRetrofit(): Retrofit
}
```

#### 2. Modul `:feature-lending` (Dynamic Feature Module)
Modul ini di-deliver secara on-demand, sehingga tidak bisa menggunakan `@AndroidEntryPoint` konvensional jika membutuhkan isolasi penuh atau dependensi khusus yang tidak dikompilasi ke `:app`.

**Scope Khusus Fitur:**
```kotlin
package com.enterprise.feature.lending.di

import javax.inject.Scope

@Scope
@Retention(AnnotationRetention.RUNTIME)
annotation class LendingFeatureScope
```

**Custom Component DFM:**
```kotlin
package com.enterprise.feature.lending.di

import com.enterprise.core.di.CoreFeatureDependencies
import com.enterprise.feature.lending.data.LendingApi
import com.enterprise.feature.lending.data.LendingRepositoryImpl
import com.enterprise.feature.lending.domain.LendingRepository
import dagger.Component
import dagger.Module
import dagger.Provides
import retrofit2.Retrofit

@LendingFeatureScope
@Component(
    dependencies = [CoreFeatureDependencies::class],
    modules = [LendingFeatureModule::class]
)
interface LendingFeatureComponent {
    fun inject(activity: com.enterprise.feature.lending.presentation.LendingLoanActivity)

    @Component.Builder
    interface Builder {
        fun coreDependencies(dependencies: CoreFeatureDependencies): Builder
        fun build(): LendingFeatureComponent
    }
}

@Module
object LendingFeatureModule {
    @Provides
    @LendingFeatureScope
    fun provideLendingApi(retrofit: Retrofit): LendingApi {
        return retrofit.create(LendingApi::class.java)
    }

    @Provides
    @LendingFeatureScope
    fun provideLendingRepository(api: LendingApi): LendingRepository {
        return LendingRepositoryImpl(api)
    }
}
```

**DFM Activity Injection:**
```kotlin
package com.enterprise.feature.lending.presentation

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.enterprise.core.di.CoreFeatureDependencies
import com.enterprise.feature.lending.di.DaggerLendingFeatureComponent
import com.enterprise.feature.lending.domain.LendingRepository
import dagger.hilt.android.EntryPointAccessors
import javax.inject.Inject

class LendingLoanActivity : AppCompatActivity() {

    @Inject
    lateinit var lendingRepository: LendingRepository

    override fun onCreate(savedInstanceState: Bundle?) {
        initDaggerInjection()
        super.onCreate(savedInstanceState)
        // LendingRepository siap digunakan tanpa circular dependency di level gradle
    }

    private fun initDaggerInjection() {
        val coreDependencies = EntryPointAccessors.fromApplication(
            applicationContext,
            CoreFeatureDependencies::class.java
        )

        DaggerLendingFeatureComponent.builder()
            .coreDependencies(coreDependencies)
            .build()
            .inject(this)
    }
}
```

---

## 8. Real World Case Study: Multi-Tenant Architecture & Dynamic Session Scoping

### Skenario Masalah Produksi:
Sebuah SuperApp FinTech berskala global melayani lebih dari 10 juta DAU. Fitur perbankan mengharuskan pemisahan otentikasi ketat. Ketika nasabah melakukan *switch profile* (misal: Personal Account -> Corporate Account) atau Logout:
1. `UserAuthToken`, session socket, dan database terenkripsi (SQLCipher) milik akun sebelumnya **HARUS DIHANCURKAN**.
2. Arsitektur lama menyematkan `UserSessionManager` di `@Singleton`. Terjadi insiden P0: Token akun A masih menempel di header interseptor `OkHttpClient` saat akun B login, mengakibatkan kebocoran data (*data leakage across tenants*).

### Solusi Desain Arsitektur: Dynamic Lifecycled Session Scope

Kita akan membuat komponen kustom yang siklus hidupnya dikelola langsung oleh manajer sesi, bukan terikat pada siklus hidup proses Android (`SingletonComponent`).

```
+-----------------------------------------------------------+
|                    Application Lifecycle                  |
|                 (Hilt SingletonComponent)                 |
|  - EncryptedStorageEngine                                 |
|  - AppCoroutineScope                                      |
|  - UserSessionLifecycleManager                            |
|                                                           |
|    +-------------------------------------------------+    |
|    |             UserSessionComponent                |    |
|    |    (Dibuat saat Login, Di-nullify saat Logout)  |    |
|    |                                                 |    |
|    |   - SessionToken                                |    |
|    |   - AuthenticatedOkHttpClient                   |    |
|    |   - TenantDatabaseRepository                    |    |
|    |   - UserScopedSocketManager                     |    |
|    +-------------------------------------------------+    |
+-----------------------------------------------------------+
```

### Implementasi:

#### 1. Scope & Component Definition
```kotlin
package com.enterprise.session.di

import com.enterprise.session.data.TenantDatabase
import com.enterprise.session.data.UserSession
import dagger.BindsInstance
import dagger.Subcomponent
import javax.inject.Scope

@Scope
@Retention(AnnotationRetention.RUNTIME)
annotation class UserSessionScope

@UserSessionScope
@Subcomponent(modules = [UserSessionModule::class])
interface UserSessionComponent {

    fun sessionToken(): String
    fun tenantDatabase(): TenantDatabase

    @Subcomponent.Factory
    interface Factory {
        fun create(
            @BindsInstance session: UserSession
        ): UserSessionComponent
    }
}
```

#### 2. Module Pembuat Dependency Sesi
```kotlin
package com.enterprise.session.di

import com.enterprise.session.data.TenantDatabase
import com.enterprise.session.data.UserSession
import dagger.Module
import dagger.Provides
import okhttp3.Interceptor
import okhttp3.OkHttpClient

@Module
object UserSessionModule {

    @Provides
    @UserSessionScope
    fun provideAuthInterceptor(session: UserSession): Interceptor {
        return Interceptor { chain ->
            val request = chain.request().newBuilder()
                .header("Authorization", "Bearer ${session.authToken}")
                .header("X-Tenant-ID", session.tenantId)
                .build()
            chain.proceed(request)
        }
    }

    @Provides
    @UserSessionScope
    fun provideSessionOkHttpClient(
        baseClient: OkHttpClient, // Didapat dari Parent SingletonComponent
        authInterceptor: Interceptor
    ): OkHttpClient {
        return baseClient.newBuilder()
            .addInterceptor(authInterceptor)
            .build()
    }

    @Provides
    @UserSessionScope
    fun provideTenantDatabase(session: UserSession): TenantDatabase {
        return TenantDatabase.openEncryptedDatabase(
            dbName = "tenant_${session.tenantId}.db",
            passphrase = session.encryptionKey
        )
    }
}
```

#### 3. Thread-Safe Session Lifecycle Manager (Di-inject di Singleton)
```kotlin
package com.enterprise.session.engine

import com.enterprise.session.data.UserSession
import com.enterprise.session.di.UserSessionComponent
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class UserSessionLifecycleManager @Inject constructor(
    private val sessionComponentFactory: UserSessionComponent.Factory
) {
    private val lock = Any()
    
    private var currentComponent: UserSessionComponent? = null

    private val _sessionState = MutableStateFlow<UserSession?>(null)
    val sessionState: StateFlow<UserSession?> = _sessionState.asStateFlow()

    fun onUserLogin(session: UserSession) {
        synchronized(lock) {
            // Bersihkan sesi lama jika belum di-destroy
            if (currentComponent != null) {
                destroyCurrentSessionInternal()
            }
            
            currentComponent = sessionComponentFactory.create(session)
            _sessionState.value = session
        }
    }

    fun onUserLogout() {
        synchronized(lock) {
            destroyCurrentSessionInternal()
        }
    }

    fun getSessionComponent(): UserSessionComponent {
        return synchronized(lock) {
            currentComponent ?: throw IllegalStateException("Tidak ada sesi user aktif.")
        }
    }

    private fun destroyCurrentSessionInternal() {
        currentComponent?.let { component ->
            // Tutup database koneksi secara eksplisit
            component.tenantDatabase().close()
        }
        currentComponent = null
        _sessionState.value = null
    }
}
```

---

## 9. Trade-offs: Komparasi Pola Arsitektur DI Enterprise

```
            Kompleksitas Desain
                  ▲
                  │                                     ● Pure Dagger 2 Multi-Component
                  │                                   (Dynamic Features / Strict Isolation)
                  │
                  │                 ● Hilt + Custom Subcomponents
                  │                   (Session Scoping)
                  │
                  │       ● Standard Hilt
                  │         (Monolithic App)
                  │
                  │ ● Manual DI (Service Locator)
                  │
                  └────────────────────────────────────────► Fleksibilitas & Isolasi Modul
```

| Matriks Perbandingan | Pure Hilt Standar | Hilt + EntryPoint (DFM Bridge) | Custom Multi-Component (Pure Dagger) | Koin (Runtime Service Locator) |
| :--- | :--- | :--- | :--- | :--- |
| **Waktu Kompilasi (Build Time)** | Sedang (Terkena impact monolitik Hilt processor) | Lebih cepat untuk isolasi modul paralel | Sangat Cepat (Isolated build cache terdistribusi) | Sangat Cepat (Tanpa compile-time validation) |
| **Runtime Overhead & Latency** | Nyaris 0 ms (Zero reflection) | Nyaris 0 ms (Direct factory calls) | Mutlak 0 ms (Optimal bytecode direct link) | Ada overhead pencarian graph pada map hash saat runtime |
| **Dynamic Delivery Compatibility** | ❌ Sangat Buruk (Sering gagal resolusi class loader) | ✅ Sangat Baik (Standard DFM support) | ✅ Sempurna (Arsitektur plugin-ready) | ✅ Baik (Namun rentan runtime crash) |
| **Type Safety & Safety Guarantees** | Compile-Time (Tinggi) | Compile-Time (Tinggi) | Compile-Time (Maksimal) | Runtime Verification (Rentan Crash di Prod) |
| **Kompleksitas Kode & Boilerplate** | Rendah | Sedang | Tinggi | Sangat Rendah |

---

## 10. Common Mistakes & Troubleshooting

### Mistake 1: Memory Leak Context pada Scoped Dependency
```kotlin
// FATAL ERROR
@Singleton
class DeviceLocationTracker @Inject constructor(
    private val context: Context // Activity Context terinjeksi karena kelalaian modul
)
```
- **Analisis Dampak**: Karena `DeviceLocationTracker` adalah `@Singleton`, instance Activity yang pertama kali menginjeksinya akan tertahan selamanya di heap memory. Garbage Collector tidak bisa mereklamasi memory saat activity di-destroy.
- **Solusi**: Wajib gunakan anotasi `@ApplicationContext`:
```kotlin
@Singleton
class DeviceLocationTracker @Inject constructor(
    @ApplicationContext private val context: Context
)
```

### Mistake 2: Missing EntryPoint Binding pada DFM
- **Gejala Error**: `java.lang.IllegalStateException: The component was not created. Check that you have added the corresponding EntryPoint extension.`
- **Penyebab**: Class Application di `:app` lupa meng-extend `Hilt_MainApplication` atau lupa mendaftarkan interface dependencies pada modul terkait.
- **Solusi**: Pastikan akses menggunakan `EntryPointAccessors.fromApplication(context, InterfaceName::class.java)` dan interface tersebut memiliki `@InstallIn(SingletonComponent::class)`.

### Mistake 3: Build Error "Dagger does not support cycle dependencies"
- **Gejala Error**: Kompilator memuntahkan log dependensi: `Class A -> Class B -> Class C -> Class A`.
- **Solusi**:
  1. Perbaiki desain domain; pecah relasi mutual dependensi.
  2. Gunakan `dagger.Lazy<T>` atau `javax.inject.Provider<T>` pada titik konsumsi dependensi untuk memecah lingkaran inisialisasi:
```kotlin
class PaymentProcessor @Inject constructor(
    private val orderAnalytics: dagger.Lazy<OrderAnalytics> // Defer dependency resolution
) {
    fun process() {
        orderAnalytics.get().trackEvent("PROCESS_STARTED")
    }
}
```

### Mistake 4: ProGuard/R8 Menghapus Dynamic Component
- **Gejala Error**: `ClassNotFoundException` atau `NullPointerException` hanya pada build release APK (`minifyEnabled true`).
- **Solusi**: Tambahkan keep rules pada `proguard-rules.pro` untuk DFM EntryPoint:
```proguard
# Menjaga interface EntryPoint Dagger/Hilt
-keep,allowobfuscation,allowshrinking interface * extends dagger.hilt.internal.GeneratedComponent
-keep,allowobfuscation,allowshrinking interface * extends dagger.hilt.internal.ComponentEntryPoint
-keep interface **.*EntryPoint { *; }
-keepclassmembers interface **.*EntryPoint { *; }
```

---

## 11. Best Practices (Production Checklist)

1. [ ] **KSP Migration**: Migrasikan Dagger kapt ke KSP (`com.google.dagger:hilt-android-compiler` via plugin `com.google.devtools.ksp`) untuk mereduksi waktu kompilasi Dagger hingga 30-40%.
2. [ ] **API vs Implementation**: Hanya ekspos interface DI di blok `api` Gradle, sembunyikan implementasi konkret di blok `implementation`.
3. [ ] **Hindari `@Singleton` Berlebihan**: Jika kelas bersifat *stateless* (seperti `UseCase` atau `Mapper`), **jangan diberi scope**. Biarkan factory membuat instance baru tanpa overhead synch lock `DoubleCheck`.
4. [ ] **Immutable Injections**: Semua field yang diinjeksi via constructor wajib berstatus `private val`. Jangan izinkan `var` untuk dependency.
5. [ ] **Strict Scoping Lifecycle Management**: Custom Component yang dinamis (`UserSessionComponent`) wajib memiliki fungsi pembersihan koneksi I/O (`.close()`) yang terpanggil serentak saat scope dihancurkan.
6. [ ] **Build Time Tracing**: Tambahkan compiler argument `-Adagger.fastInit=enabled` dan `-Adagger.strictMultibindingValidation=enabled` untuk optimasi compiler Dagger.

---

## 12. Hands-on Practice

Buatlah implementasi factory-assisted dynamic injection pada directory proyek berikut:
`hands-on/m02/`

### Struktur Direktori:
```
hands-on/m02/
├── build.gradle.kts
└── src/
    └── main/
        └── java/
            └── com/enterprise/handson/
                ├── data/
                │   └── SecureVaultManager.kt
                ├── di/
                │   ├── SecurityModule.kt
                │   └── VaultComponent.kt
                └── presentation/
                    └── DynamicVaultViewModel.kt
```

### Langkah Praktikum:

#### Langkah 1: Siapkan `build.gradle.kts`
Pastikan plugin KSP dan Dagger dependencies telah terpasang:
```kotlin
plugins {
    alias(libs.plugins.android.library)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.ksp)
    alias(libs.plugins.hilt.android)
}

dependencies {
    implementation(libs.hilt.android)
    ksp(libs.hilt.compiler)
    implementation(libs.androidx.lifecycle.viewmodel.ktx)
}
```

#### Langkah 2: Buat `SecureVaultManager.kt`
```kotlin
package com.enterprise.handson.data

import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class SecureVaultManager @Inject constructor() {
    fun fetchVaultData(vaultId: String, authCode: String): String {
        return "DecryptedData for Vault $vaultId with token ${authCode.take(4)}****"
    }
}
```

#### Langkah 3: Buat `DynamicVaultViewModel.kt` dengan `@AssistedInject`
```kotlin
package com.enterprise.handson.presentation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import com.enterprise.handson.data.SecureVaultManager
import dagger.assisted.Assisted
import dagger.assisted.AssistedFactory
import dagger.assisted.AssistedInject

class DynamicVaultViewModel @AssistedInject constructor(
    private val vaultManager: SecureVaultManager,
    @Assisted("vaultId") private val vaultId: String,
    @Assisted("authCode") private val authCode: String
) : ViewModel() {

    @AssistedFactory
    interface Factory {
        fun create(
            @Assisted("vaultId") vaultId: String,
            @Assisted("authCode") authCode: String
        ): DynamicVaultViewModel
    }

    fun getDecryptedPayload(): String {
        return vaultManager.fetchVaultData(vaultId, authCode)
    }

    companion object {
        fun provideFactory(
            assistedFactory: Factory,
            vaultId: String,
            authCode: String
        ): ViewModelProvider.Factory = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return assistedFactory.create(vaultId, authCode) as T
            }
        }
    }
}
```

#### Langkah 4: Validasi Kompilasi Bytecode
Jalankan perintah berikut di terminal:
```bash
./gradlew :hands-on:m02:compileDebugKotlin
```
Verifikasi bahwa file `DynamicVaultViewModel_Factory.java` dan `DynamicVaultViewModel_AssistedFactory.java` berhasil dihasilkan di direktori `build/generated/ksp/debug/java/com/enterprise/handson/presentation/`.

---

## 13. Exercise

### Exercise 1 (Easy): Runtime Parameter Binding Fix
*Instruksi*: Perbaiki kode ViewModel di bawah ini agar lolos kompilasi Dagger saat membutuhkan parameter dinamis `userId` dari bundle navigasi.

```kotlin
// KODE BERMASALAH (Kompilasi Gagal)
@HiltViewModel
class ProfileViewModel @Inject constructor(
    private val repository: ProfileRepository,
    private val userId: String // Penyebab error: Hilt tidak tahu cara inject String ini
) : ViewModel()
```
*Kriteria Penerimaan*:
- Migrasikan ke `@AssistedInject`.
- Buat interface `@AssistedFactory`.
- ViewModel instansiasi aman tanpa error kompilasi Hilt graph.

---

### Exercise 2 (Medium): Isolasi Shared Network Component
*Instruksi*: Buat modul library bernama `:core:network` yang mengekspos `@EntryPoint` bernama `NetworkBridge`. 
*Kriteria Penerimaan*:
- Library tidak boleh memiliki dependensi balik ke modul `:app`.
- Menghasilkan singleton instance dari `OkHttpClient` dengan konfigurasi timeout: connect 15s, read 15s.
- Harus dapat di-resolve dari modul lain via `EntryPointAccessors.fromApplication`.

---

### Exercise 3 (Hard): Scoped Multi-Database Session Switcher
*Instruksi*: Rancang komponen berbasis `@UserSessionScope` yang memuat database lokal independen per userId (`user_123.db`). Ketika fungsi `switchUser(newId)` dipanggil pada session manager:
1. File SQLite database sebelumnya harus di-flush dan ditutup.
2. Seluruh binding repository di dalam scope harus menunjuk ke instance database yang baru.
3. Tidak boleh memicu exception `SQLiteDatabaseLockedException`.
*Kriteria Penerimaan*:
- Menulis unit test yang memverifikasi dua instance repository berbeda dihasilkan setelah sesi berganti, dan instance lama tidak lagi valid.

---

## 14. Challenge (Arsitektur Enterprise Skala Besar)

**Skenario**: Anda adalah Principal Android Architect di sebuah platform e-commerce konglomerasi. Aplikasi Anda menerapkan sistem Dynamic Split APK Feature dengan 12 Dynamic Feature Modules (misal: `:feature:paylater`, `:feature:travel`, `:feature:insurance`).

**Persyaratan Tantangan**:
1. Bangun engine dependency injection dinamis yang **100% Zero-Reflection** pada level DFM.
2. Modul `:app` tidak boleh memiliki satupun deklarasi dependensi gradle ke Dynamic Modules (`:feature:*`).
3. DFM diunduh pada saat runtime via Google Play Core SplitCompat.
4. Setiap DFM harus bisa meminta dependensi terisolasi (misal: API endpoint khusus, analytics payload interceptor) yang hanya hidup ketika fragment DFM tersebut berada di backstack, dan otomatis di-garbage collect saat fragment di-*pop* dari backstack.
5. Tangani skenario token expiration serentak pada 3 DFM yang sedang aktif bersamaan di layar lipat (*foldable split-screen mode*) menggunakan structured dynamic scope termination.

*Deliverable*:
- Rancang diagram interaksi arsitektur ASCII lengkap.
- Tuliskan contract interface core, custom lifecycle manager, dan implementasi injection bridge tanpa memanfaatkan nama class string reflection (`Class.forName(...)` diharamkan demi mematuhi R8 hard obfuscation).

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Pertanyaan Basic (Pilihan Ganda)

#### Q1: Kapan Anda harus menggunakan `@AssistedInject` dibandingkan `@Inject` konvensional?
- [ ] A. Saat dependensi membutuhkan Context aplikasi.
- [ ] B. Saat beberapa parameter dependency baru tersedia saat runtime (misal ID order atau argument navigasi).
- [ ] C. Saat class tersebut berupa Singleton.
- [ ] D. Saat class ingin diinject ke dalam composable function secara langsung.
*Kunci: B*  
*Rasional: `@AssistedInject` dirancang khusus untuk memecah dependency menjadi dua sumber: dependensi yang disediakan oleh Dagger graph dan parameter runtime yang di-pass secara manual oleh pemanggil.*

#### Q2: Apa fungsi utama dari internal class `dagger.internal.DoubleCheck` pada Dagger?
- [ ] A. Memastikan validasi lint graph berjalan dua kali sebelum kompilasi.
- [ ] B. Mengimplementasikan Thread-Safe Lazy Initialization dengan double-checked locking untuk scoped instance.
- [ ] C. Memeriksa apakah terjadi circular dependency di antara dua class.
- [ ] D. Melakukan de-alokasi memori secara otomatis saat Activity destroy.
*Kunci: B*  
*Rasional: `DoubleCheck` membungkus `Provider` Dagger untuk memastikan hanya satu instance yang dibuat di multi-threaded environment menggunakan pola Double-Checked Locking.*

#### Q3: Jika Anda mendeklarasikan class dengan `@Singleton`, di manakah instance tersebut disimpan di Hilt?
- [ ] A. Di cache filesystem aplikasi.
- [ ] B. Di dalam lifecycle `SingletonComponentImpl` yang terikat pada instance `Application`.
- [ ] C. Di dalam static variable global dari Activity utama.
- [ ] D. Di memory space Zygote process Android.
*Kunci: B*  
*Rasional: Hilt meletakkan instansiasi `@Singleton` di dalam `SingletonComponent`, yang siklus hidupnya sama dengan lifecycle object `android.app.Application`.*

#### Q4: Apa perbedaan esensial antara Subcomponent dan Component Dependencies?
- [ ] A. Subcomponent tidak bisa memiliki Scope.
- [ ] B. Component Dependencies mewarisi seluruh isi graph parent tanpa deklarasi eksplisit.
- [ ] C. Subcomponent memiliki akses penuh ke seluruh graph Parent secara implisit, sedangkan Component Dependencies hanya dapat mengakses apa yang diekspos secara eksplisit oleh contract interface Parent.
- [ ] D. Subcomponent hanya bisa digunakan di modul Dynamic Feature.
*Kunci: C*  
*Rasional: Subcomponent merusak enkapsulasi parent dengan mengambil seluruh graph, sedangkan Component Dependencies menegakkan enkapsulasi melalui interface kontraktual.*

#### Q5: Mengapa annotasi `@AndroidEntryPoint` tidak dapat digunakan secara default di modul Dynamic Feature (DFM) yang terpisah tanpa konfigurasi khusus?
- [ ] A. Karena DFM tidak mendukung Kotlin.
- [ ] B. Karena Hilt monolitik mengasumsikan seluruh class turunan dapat dilihat langsung oleh `SingletonComponent` di modul `:app` pada saat compile time.
- [ ] C. Karena DFM tidak memiliki akses ke Android Manifest.
- [ ] D. Karena ProGuard selalu menghapus file DFM.
*Kunci: B*  
*Rasional: DFM memiliki arah kompilasi terbalik (`:feature` -> `:app`), sehingga modul `:app` tidak dapat melihat class di DFM saat mengompilasi `SingletonComponent` tanpa bantuan EntryPoint bridge.*

---

### 15.2 Pertanyaan Intermediate (Pilihan Ganda)

#### Q6: Pada implementasi multi-module enterprise, mengapa praktik mengekspos class implementasi konkret di file `build.gradle.kts` via `api(project(":core:database"))` dihindari?
- [ ] A. Karena Dagger akan menolak mengompilasi tipe konkret.
- [ ] B. Karena merusak build cache isolation; perubahan kecil pada implementasi akan memaksa seluruh modul yang bergantung untuk melakukan re-compile (ABI invalidation).
- [ ] C. Karena SQLite tidak mendukung visibilitas publik.
- [ ] D. Karena Hilt hanya mendukung visibilitas `internal`.
*Kunci: B*  
*Rasional: Mengekspos implementasi via `api` membocorkan ABI (Application Binary Interface), memicu kompilasi berantai pada downstream dependencies dan memperlambat build time enterprise.*

#### Q7: Apa resiko utama dari penggunaan `Provider<T>` yang di-resolve berulang kali tanpa scope?
- [ ] A. Memicu ANR secara instan.
- [ ] B. Membuat objek baru pada heap setiap kali method `.get()` dipanggil, berpotensi memicu GC churn (alokasi memori berlebih).
- [ ] C. Dagger akan melempar exception `ConcurrentModificationException`.
- [ ] D. Class loader akan mengunci file DEX.
*Kunci: B*  
*Rasional: Factory un-scoped yang dipanggil via `Provider.get()` mengeksekusi instantiation `new Instance()` setiap pemanggilan, yang jika dilakukan di loop atau render pipeline akan memicu lonjakan memori dan Garbage Collection pause.*

#### Q8: Bagaimana cara paling tepat menghancurkan instance yang disimpan di custom scope (misal `@UserSessionScope`) ketika user melakukan Logout?
- [ ] A. Memanggil `System.gc()`.
- [ ] B. Memutus koneksi internet.
- [ ] C. Mengeset referensi instance Dagger Subcomponent/Component manager menjadi `null` sehingga seluruh graph scoped di dalamnya eligible untuk Garbage Collection.
- [ ] D. Menutup paksa aplikasi menggunakan `exitProcess(0)`.
*Kunci: C*  
*Rasional: DI scope hidup selama object Component-nya dipegang di memori. Menghilangkan referensi induk (`component = null`) membuat seluruh sub-graph dependensi di bawahnya terputus dari root GC.*

#### Q9: Di bawah ini, manakah konfigurasi kapt/ksp Dagger yang dapat mempercepat build time secara signifikan pada multi-module project besar?
- [ ] A. `-Adagger.ignoreUnusedBindings=true`
- [ ] B. `-Adagger.fastInit=enabled`
- [ ] C. Menghapus file `proguard-rules.pro`
- [ ] D. Mematikan fitur incremental compilation
*Kunci: B*  
*Rasional: `-Adagger.fastInit=enabled` mengubah cara Dagger membuat factory internal, beralih ke switch-based provider yang memangkas jumlah class bytecode yang digenerate dan mempercepat compile time.*

#### Q10: Apa penyebab umum terjadinya crash `IllegalStateException: Scoped provider was invoked concurrently and returned different results` pada internal Dagger `DoubleCheck`?
- [ ] A. Bug pada Android OS runtime.
- [ ] B. Terdapat implementasi `@Provides` method yang tidak thread-safe dan mengembalikan referensi objek yang tidak deterministik saat dipanggil berbarengan sebelum lock stabil.
- [ ] C. Handphone kekurangan memori RAM.
- [ ] D. Penggunaan coroutine pada fungsi UI.
*Kunci: B*  
*Rasional: Method provider yang memiliki side effect non-deterministik pada proses inisialisasi awal saat dua thread masuk secara balapan dapat memicu assertion failure di method `DoubleCheck.recheck()`.*

---

### 15.3 Skenario Kasus Produksi (Analisis Kasus)

#### Skenario Kasus 1: Insiden "Ghost Session" Pasca-Logout
*Konteks*: Aplikasi mobile perbankan menerima laporan audit keamanan: Nasabah A login di perangkat, lalu menekan tombol logout. Nasabah B login di perangkat yang sama. Sesaat setelah Nasabah B membuka halaman profil, saldo dan nomor rekening Nasabah A tampil selama 1 detik sebelum akhirnya berganti ke data Nasabah B.
*Temuan Investigasi*:
Developer menyimpan instance repository berikut di `@Singleton`:
```kotlin
@Singleton
class AccountRepository @Inject constructor(
    private val api: AccountApi
) {
    var cachedAccount: AccountEntity? = null // Data tersimpan di memory variable
}
```
*Pertanyaan*: Jelaskan mengapa arsitektur di atas gagal secara sistemik, dan bagaimana restrukturisasi DI harus dilakukan secara komprehensif!

*Rekomendasi Jawaban Enterprise*:
1. **Root Cause**: `@Singleton` terikat pada lifecycle proses aplikasi OS. Logout tidak menghentikan proses OS, sehingga field mutabel `cachedAccount` pada class singleton tetap hidup di memory heap. Saat Nasabah B login, data cache lama milik Nasabah A disajikan secara keliru.
2. **Remediasi Arsitektur**:
   - Hapus state cache mutabel dari singleton.
   - Pindahkan `AccountRepository` ke dalam komponen bertingkat: `@UserSessionScope`.
   - Komponen ini hanya dibuat ketika autentikasi tervalidasi via `UserSessionComponent`.
   - Pada saat callback `onLogout()` dieksekusi, referensi ke `UserSessionComponent` di-nullify, memusnahkan seluruh cache repository secara atomik tanpa menyisakan jejak di memori.

---

#### Skenario Kasus 2: Crash Out-of-Memory (OOM) Akibat Injection CoroutineScope
*Konteks*: SuperApp mengalami lonjakan crash `OutOfMemoryError` secara acak di latar belakang. Crash logs menunjukkan jutaan instance coroutine jobs menumpuk di heap.
*Temuan Investigasi*:
```kotlin
@Module
@InstallIn(SingletonComponent::class)
object AppModule {
    @Provides
    @Singleton
    fun provideCoroutineScope(): CoroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
}

class PollingService @Inject constructor(
    private val scope: CoroutineScope // Mengambil Singleton CoroutineScope
) {
    fun startPolling(topicId: String) {
        scope.launch {
            // Long running network poll
        }
    }
}
```
*Pertanyaan*: Mengapa konfigurasi injection scope di atas menyebabkan leak coroutine raksasa, dan bagaimana memperbaikinya menggunakan Lifecycle-bound Injection?

*Rekomendasi Jawaban Enterprise*:
1. **Root Cause**: Menyediakan `CoroutineScope` monolitik di `@Singleton` tanpa mekanisme pembatalan (*cancellation contract*) membuat setiap `scope.launch` menempel pada satu `SupervisorJob` global yang tidak pernah selesai. Ketika `PollingService` dipanggil berulang-ulang, job lama tidak pernah di-cancel, menahan referensi konteks dan memory stream secara kumulatif hingga memory habis.
2. **Remediasi Arsitektur**:
   - Jangan pernah melakukan inject single naked `CoroutineScope` tanpa lifecycle batas hidup yang jelas.
   - Untuk background tasks, gunakan WorkManager dengan `@HiltWorker` dan `AssistedInject`.
   - Jika background tracking terikat pada UI, pasang pada `viewModelScope` yang otomatis membatalkan job saat UI hancur.
   - Jika scope independen diperlukan, definisikan wrapper class yang mengimplementasikan lifecycle listener yang memanggil `job.cancelChildren()` saat transisi state terjadi.

---

#### Skenario Kasus 3: Dynamic Feature Class Not Found Exception di Release Mode
*Konteks*: Sebuah modul Dynamic Feature `:feature:lending` bekerja mulus pada build varian `debug`. Namun saat build varian `release` (dengan R8 enabled) diunggah ke Google Play Internal Testing, aplikasi langsung crash saat membuka modul fitur tersebut dengan stack trace:
`java.lang.ClassNotFoundException: Didn't find class "com.enterprise.feature.lending.di.DaggerLendingFeatureComponent"`
*Pertanyaan*: Mengapa class tersebut hilang di release build, dan bagaimana solusi build script serta ProGuard yang tepat untuk mengatasinya?

*Rekomendasi Jawaban Enterprise*:
1. **Root Cause**: R8 melakukan *Tree-Shaking* agresif. Karena modul `:app` tidak memiliki dependensi statis ke `:feature:lending`, dan `DaggerLendingFeatureComponent` diakses secara isolasi di dalam DFM melalui mekanisme runtime dynamic class loading, R8 menganggap kelas factory hasil generate tersebut *dead code* atau menghapus mapping package-nya.
2. **Remediasi**:
   - Tambahkan keep rules eksplisit pada modul DFM:
     ```proguard
     -keepnames class com.enterprise.feature.lending.di.DaggerLendingFeatureComponent { *; }
     -keepclassmembers class * implements dagger.internal.Factory { *; }
     ```
   - Pastikan pada konfigurasi Gradle DFM, consumer proguard rules diikutsertakan:
     ```kotlin
     buildTypes {
         release {
             consumerProguardFiles("consumer-rules.pro")
         }
     }
     ```
   - Pastikan inisialisasi dynamic component menggunakan wrapper factory yang aman dari pembersihan nama simbolik (*obfuscation*).

---

## 16. Summary

1. **Internal Codegen**: Dagger mentransformasikan anotasi compile-time ke dalam direct class method calls (Zero-Reflection) dengan membungkus dependency scoped ke dalam pola `DoubleCheck` locking untuk menjamin konkurensi thread-safe.
2. **Dynamic Assisted Injection**: `@AssistedInject` dan `@AssistedFactory` menghilangkan kebutuhan penulisan manual Factory boilerplate pada ViewModel atau WorkManager yang membutuhkan gabungan parameter runtime dan compile-time dependencies.
3. **Dynamic Delivery Isolation**: Hilt monolitik tidak kompatibel secara *out-of-the-box* dengan Dynamic Feature Module. Pola `@EntryPoint` dikombinasikan dengan Custom Component Dependencies memecahkan limitasi circular dependency Gradle.
4. **Lifecycle & Security Scoping**: Menyimpan data sensitif dan koneksi jaringan pada `@Singleton` adalah anti-pattern enterprise. Gunakan scoped lifecycle components dinamis (seperti `@UserSessionScope`) untuk memastikan pembersihan memori (*memory sanitization*) instan saat sesi pengguna berganti atau dihentikan.