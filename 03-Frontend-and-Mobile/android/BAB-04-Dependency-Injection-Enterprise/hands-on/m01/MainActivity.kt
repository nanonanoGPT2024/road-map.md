---

## SEKSI 11 — TRADE-OFFS & ANALISIS KOMPARATIF

| Parameter Evaluasi | Dagger-Hilt (KSP) | Koin (Core DSL) | Dagger Vanilla (Java APT/KAPT) |
| :--- | :--- | :--- | :--- |
| **Waktu Inisialisasi App (Cold Start)** | **Sangat Cepat (~0 ms overhead)**. Semua Factory terhubung via kode Java statis. | **Lebat/Lambat**. Resolusi graph melalui *reflection/service locator map lookup* di runtime. | **Sangat Cepat**. Menggunakan pendekatan statis yang sama dengan Hilt. |
| **Validasi Compile-Time Safety** | **Total (100%)**. Jika graph ada yang hilang/siklik, proses kompilasi langsung gagal. | **Nihil (0%)**. Runtime crash (`NoBeanDefFoundException`) terjadi jika definisi dependensi terlewat. | **Total (100%)**. Kompilasi gagal jika dependensi tidak terpenuhi. |
| **Kecepatan Build Gradle** | **Cepat**. Berkat pemrosesan AST langsung oleh KSP tanpa Java stub generation. | **Sangat Cepat**. Tidak ada proses code generation atau anotasi compile-time. | **Sangat Lambat**. KAPT menghasilkan jutaan baris stub Java yang membebani disk I/O. |
| **Kompleksitas Multi-Module** | **Menengah-Tinggi**. Membutuhkan modul terisolasi, `@InstallIn`, dan manajemen visibilitas internal. | **Rendah**. Sangat fleksibel memuat modul via DSL di mana saja. | **Sangat Tinggi**. Perlu manual setup subcomponents, component dependencies, dan module bridging. |
| **Penggunaan Heap Memory** | **Rendah**. Hanya instance yang di-resolve yang disimpan. Tidak ada lookup map besar. | **Tinggi**. Mempertahankan global registry berupa hash map dari semua definitions. | **Rendah**. Memory footprint sepenuhnya berbasis pure code reference. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. DFM (Dynamic Feature Module) Graph Inversion
*Problem:* Modul `:app` tidak dapat melihat kode di dalam `:dynamic_feature` (karena arah dependensi Gradle adalah kebalikannya: `:dynamic_feature` $\to$ `:app`). Akibatnya, `@InstallIn(SingletonComponent::class)` yang didefinisikan di dalam DFM akan gagal atau ditolak.
*Mitigasi:* Gunakan `@EntryPoint` di dalam DFM dan pasang Hilt component manager berbasis refleksi class interface atau implementasikan `Component Dependencies` manual untuk menarik graph dari Core Application.

### 2. Retained Fragment View Lifecycle Leak
*Problem:* Melakukan injeksi instance yang memegang referensi ke `Binding` atau `View` ke dalam objek `@FragmentScoped`.
*Mekanisme:* Siklus hidup `Fragment` melebihi siklus hidup `Fragment.view`. Fragment dapat berpindah ke Backstack (View dihancurkan via `onDestroyView()`), tetapi Fragment instance tetap hidup. Jika `@FragmentScoped` menahan view hierarchy, seluruh UI subtree bocor (*leaked*).
*Mitigasi:* Jangan pernah menandai presenter/helper yang menyimpan `View` dengan `@FragmentScoped`. Gunakan dependensi unscoped atau lepaskan referensi view pada `onDestroyView()`.

### 3. Assisted Injection dengan Parameter Tipe Primitif Ganda
*Problem:* Jika interface `@AssistedFactory` memiliki dua parameter bertipe identik (misal: dua buah `String`), Dagger KSP dapat tertukar saat memetakan argumen ke konstruktor jika tidak ditandai secara presisi.
*Mitigasi:* Gunakan `@Assisted("identifier")` dengan parameter string literal yang eksplisit:
