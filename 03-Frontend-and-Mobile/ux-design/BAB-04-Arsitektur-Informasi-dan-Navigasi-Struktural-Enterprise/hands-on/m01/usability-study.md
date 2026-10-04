---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi teknis logika penyusun engine navigasi di atas:

*   **Baris 3–19 (`types/navigation.ts`):** Menggunakan pola *Discriminated Union* (`type: 'LEAF' | 'BRANCH'`). Pendekatan ini mewajibkan TypeScript mengecek ketersediaan `path` hanya pada `LEAF`, dan keberadaan sub-array `children` hanya pada `BRANCH`, mengeliminasi bug runtime `undefined reading 'children'`.
*   **Baris 21–26 (`UserSecurityContext`):** Menggunakan `Set<PermissionCode>` alih-alih `Array<PermissionCode>`. Evaluasi `has()` beroperasi dalam kompleksitas waktu konstan $O(1)$, menjamin pemrosesan ratusan simpul navigasi berjalan instan tanpa bottleneck mikro-komputasi.
*   **Baris 35–52 (`navigationResolver.ts`):** Tahap evaluasi RBAC dan Feature Flag. Penggunaan operator `.every()` memaksakan kebijakan *fail-closed* / keamanan ketat: jika sebuah simpul memerlukan 3 perizinan, ketiadaan salah satu izin akan memblokir simpul tersebut secara instan.
*   **Baris 62–73 (`Pembersihan Ghost Branch`):** Inti dari algoritma rekursif hierarkis. Jika pengguna memiliki izin melihat node induk, namun izin seluruh node anak di dalamnya di-revokasi (*revoked*), node induk tersebut menjadi *ghost branch* (cabang kosong tak berujung). Logika `if (filteredChildren.length > 0)` secara otomatis memangkas cabang tersebut, menjaga kerapihan visual antarmuka navigasi.
*   **Baris 89–110 (`flattenNavigationTree`):** Algoritma Depth-First Search (DFS) yang mengekstraksi struktur pohon bertingkat menjadi array datar. Penyimpanan `ancestorLabels` menyediakan jejak kontekstual penuh (misal: `"Finance" > "Ledgers" > "AP"`) yang krusial untuk pencarian global command palette berpresisi tinggi.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: ERP Konsolidasi Global Multi-Tenant (OmniLogix Global)

*   **Latar Belakang Industri:** OmniLogix Global mengoperasikan platform rantai pasok global dengan 42 modul fungsional, 1.200 tampilan rute berbeda, dan melayani 4 hierarki persona utama: *Global Enterprise Admin*, *Regional Logistics Officer*, *Third-Party Carrier*, dan *Financial Compliance Auditor*.
*   **Masalah Arsitektur Awal:**
    1.  Sidebar monolitik menampilkan menu setinggi 6 tingkat folder dengan total 180 tautan aktif di layar secara serentak.
    2.  *Lostness Metric* pengguna audit mencapai skor buruk: 0.68 (skor di atas 0.4 menandakan kegagalan navigasi parah).
    3.  Tingginya angka tiket dukungan teknis internal: 34% dari seluruh tiket pelaporan pengguna adalah masalah kegagalan menemukan fitur (*"Saya tidak dapat menemukan modul rekonsiliasi PPN"*).
    4.  Perubahan perizinan IAM backend sering kali meninggalkan cabang menu kosong di sisi frontend, yang membingungkan pengguna ketika diklik (*broken interaction*).
*   **Intervensi Arsitektur Informasi Baru:**
    1.  **Dekomposisi Topologi Menjadi L1-L2-L3:** Mengubah sistem menjadi 3 bidang navigasi:
        *   **L1 (Global Hub Bar):** Pembagian berdasarkan domain bisnis (Operasional, Pergudangan, Keuangan, Pengaturan Sistem).
        *   **L2 (Dynamic Contextual Tree Sidebar):** Dibatasi maksimal 2 tingkat kedalaman hierarkis murni per domain.
        *   **L3 (In-Workspace Structural Tabs):** Memecah entitas data detail menjadi tampilan faset horizontal di dalam area kerja kanvas.
    2.  **Engine Navigasi Dinamis Berbasis RBAC & Bitmask Filtering:** Menjamin eliminasi total cabang kosong (*ghost branches*).
    3.  **Command Palette Terintegrasi:** Memungkinkan pencarian pintas berbasis token faset semantik dengan latensi instan.
*   **Hasil Metrik:**
    *   Waktu penyelesaian tugas audit berkurang sebesar 42%.
    *   *Lostness Metric* turun drastis ke 0.12.
    *   Tiket bantuan terkait wayfinding berkurang hingga 88% dalam kurun waktu 90 hari pasca rilis.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Di bawah ini adalah implementasi komponen Navigation Sidebar Enterprise menggunakan React, Tailwind CSS, dan pola aksesibilitas WAI-ARIA Disclosure. Komponen ini mendukung *recursive auto-expansion*, state persistence melalui *session context*, dan pemantauan fokus keyboard yang ketat.
