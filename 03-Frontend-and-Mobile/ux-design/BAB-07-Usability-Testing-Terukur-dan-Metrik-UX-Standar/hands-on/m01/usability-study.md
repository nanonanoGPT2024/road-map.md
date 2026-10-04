---

### SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi teknis komponen vital dari `UsabilityTelemetryEngine.ts`:

*   **Baris 48–60 (`startTask`)**: Menginisialisasi `performance.now()`. Berbeda dengan `Date.now()`, `performance.now()` menggunakan *monotonically increasing timer* yang tidak terpengaruh oleh penyesuaian waktu OS atau jitter NTP, esensial untuk durasi sub-milidetik. `AbortController` diciptakan untuk mempermudah pelepasan seluruh listener secara bersih saat tugas berakhir.
*   **Baris 63–66 (`recordStateTransition`)**: Merekam perubahan state/rute aplikasi (misal, transisi antar-tahapan checkout). Setiap transisi memeriksa *idle time* untuk memastikan waktu transisi tidak memicu bias dorman.
*   **Baris 82–93 (`TaskResult` aggregation)**: Memisahkan secara ketat antara `totalTimeMs`, `activeTimeMs`, dan `idleTimeMs`. Membantu menganalisis apakah pengguna lambat karena membaca instruksi sistem yang rumit (*high active time*) atau terdistraksi oleh faktor eksternal (*high idle time*).
*   **Baris 95–106 (`calculateLostness`)**: Mengimplementasikan formula Smith secara eksak. Jika pengguna bergerak secara optimal sesuai skenario ($R = N = S$), maka:
    $$L = \sqrt{\left(\frac{R}{R} - 1\right)^2 + \left(\frac{R}{R} - 1\right)^2} = \sqrt{0 + 0} = 0$$
    Jika terjadi banyak *looping* atau redundansi ($N \gg S$), nilai $L$ akan membesar secara signifikan.
*   **Baris 116–135 (`bindDOMObservers`)**: Menggunakan `{ capture: true, passive: true }`. Modus *capture* menjamin event terdeteksi sebelum aplikasi mengeksekusi `event.stopPropagation()`, sementara opsi *passive* memastikan listener tidak memblokir jalur kritis thread rendering UI (*compositor thread*).

---

### SEKSI 09 — STUDI KASUS NYATA

#### Permasalahan: Kegagalan Arsitektur Checkout Multi-Step Perusahaan FinTech

**Konteks**: Platform pembiayaan B2B mengalami drop-off sebesar 42% pada alur pengajuan kredit usaha. Alur terdiri dari 4 tahapan: Identitas Bisnis, Keuangan, Dokumen Legal, dan Tanda Tangan Digital. Tim bisnis menuduh form legal terlalu panjang, sementara tim UI menduga tombol interaksi tidak jelas.

**Data Awal Pengujian Usabilitas Konvensional (Kualitatif, $N = 10$)**:
Partisipan merasa "alur cukup membingungkan", namun tidak ditemukan pola jelas bagian mana yang harus direfaktor.

**Solusi Berbasis Telemetri Metrik Standar**:
Engine telemetri usabilitas diintegrasikan ke alur pengujian dengan parameter:
*   *Optimal Steps ($R$)* = 4 state.
*   Metrik evaluasi: TCR (Adjusted Wald CI 95%), Lognormal Mean Time-on-Task, Lostness Metric ($L$), dan Post-Task SEQ.

**Temuan Data Terukur**:
1.  **Lostness Metric**: Tahap Identitas Bisnis ($L = 0.12$), Tahap Finansial ($L = 0.22$), Tahap Dokumen Legal ($L = 0.68$). Pengguna rata-rata melakukan $N = 14$ perpindahan state untuk mencapai $S = 4$ dokumen legal yang diminta.
2.  **Rage Clicks**: Terjadi 148 kali klik beruntun pada elemen unggah dokumen PDF di perangkat mobile.
3.  **SEQ**: Skor rata-rata Dokumen Legal adalah $2.4 / 7.0$, mengindikasikan beban mental ekstrem.
4.  **Akar Masalah**: Sistem penyerahan berkas menolak format PDF tanpa memberikan indikasi status parsing; pengguna mengklik tombol unggah berkali-kali karena tidak adanya status progress/loading (*feedback vacuum*), menyebabkan pengguna berpindah layar bolak-balik untuk mengecek kesalahan input.

---

### SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi agregator statistik backend untuk mengevaluasi data pengujian usabilitas, mencakup penghitungan *SUS Scoring*, *Adjusted Wald Interval*, dan transformasi *Lognormal Mean*:
