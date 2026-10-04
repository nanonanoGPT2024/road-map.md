---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi mekanis dari implementasi `InformationArchitectureGraph`:

1. **Baris 2–18 (`ia-core-types.ts`):** 
   Mendefinisikan tipe primitif penopang arsitektur. Penggunaan `Set<Role>` pada `UserContext` menjamin lookup otorisasi dalam kompleksitas waktu $O(1)$. Properti `informationScentWeight` menjadi dasar heuristik perutean cerdas, sedangkan `isCanonicalParent` memecahkan ambiguitas polihierarkis.
2. **Baris 22–33 (`registerNode`):**
   Mendaftarkan simpul secara defensif. Operasi memeriksa keunikan ID secara instan pada memori $O(1)$ `Map`. Mengkloning `parentIds` untuk memastikan tidak ada referensi eksternal yang merusak mutasi state secara acak.
3. **Baris 35–52 (`connectEdge`):**
   Membangun relasi dwiarah antarsimpul. Tidak hanya menghubungkan pointer relasi, metode ini mewajibkan pemanggilan `this.assertAcyclic()`. Ini mencegah regresi arsitektural fatal di mana pengguna dapat terjebak dalam putaran navigasi breadcrumb tak terbatas.
4. **Baris 54–84 (`assertAcyclic`):**
   Algoritma deteksi siklus terisolasi berbasis DFS. Menggunakan struktur `recursionStack` aktif. Ketika algoritma menyusuri simpul anak dan mendapati simpul tersebut sudah ada di `recursionStack` pemanggilan saat ini, terjadi kontradiksi hierarki (Back-edge pada directed graph). Sistem secara keras melempar error (*fail-fast*), mencegah compile build UI korup.
5. **Baris 86–126 (`resolvePath`):**
   Mekanisme penelusuran balik (*Backtracking Resolution*) breadcrumb. Alih-alih mengandalkan pembacaan URL mentah (`window.location.pathname.split('/')`), sistem menelusuri simpul aktual ke atas.
6. **Baris 112–122 (Resolusi Jalur Polihierarkis):**
   Menyelesaikan dilema simpul yang memiliki banyak induk. Pertama, mesin memeriksa apakah perancang telah menentukan simpul kanonikal (`isCanonicalParent`). Jika tidak, mesin beralih ke pengecekan berbasis hak akses runtime menggunakan `find()` terhadapan peran pengguna saat ini.
7. **Baris 133–147 (`getSubtreeForUser`):**
   Penyaringan pohon navigasi secara rekursif (*Top-Down Tree Pruning*). Menghasilkan pohon presentasi virtual yang aman. Simpul yang tidak berhak dilihat oleh pengguna tidak hanya disembunyikan secara kosmetik di UI; simpul tersebut dieliminasi dari representasi graf di level memori, mencegah kebocoran struktur data internal melalui DOM inspection.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: Rekonstruksi Navigasi Multi-Tenant Enterprise Platform (FinCloud Global)
* **Latar Belakang:** FinCloud Global memiliki aplikasi perbankan B2B dengan 400+ halaman menu. Sistem awal menggunakan menu multi-level statis (JSON hardcoded dengan 5 lapis submenu melayang).
* **Masalah Kritis Pengguna:**
  * Pengguna tingkat manajer keuangan tersesat saat ingin mengesahkan transaksi. Rata-rata *Time-to-Task-Completion* (TTC) mencapai 42 detik.
  * *Disorientasi Mental:* Pengguna menganggap modul *Laporan Pajak* adalah bagian dari menu *Kepatuhan Legal*, sementara sistem backend mengelompokkannya di bawah modul *Pembukuan Akuntansi*. Hal ini menghasilkan 28% tiket bantuan bulanan yang menanyakan lokasi dokumen.
  * Tingkat klik salah (*Misclick Rate*) mencapai 31% akibat *flyout menu hover* yang tertutup tidak sengaja saat kursor bergerak miring (kegagalan Fitts' Law dan Steering Law).
* **Solusi Rekayasa:**
  * Membongkar menu statis dan mengimplementasikan **Polihierarchical Faceted Graph Architecture**.
  * Modul *Laporan Pajak* diregistrasi ulang dengan dua parent node yang valid (*Akuntansi* dan *Kepatuhan*).
  * Mengganti hover cascade flyout dengan kombinasi: **Command Palette / Semantic Search Engine** dan **Breadcrumb Graph Navigator** kontekstual.
  * Hasil: Waktu pencarian turun dari 42 detik menjadi 8,4 detik, misclick rate turun hingga < 2%, dan retensi penggunaan modul audit naik 64%.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi skala produksi mesin resolusi Arsitektur Informasi dinamis berbasis Custom Hook React dan State Graph.
