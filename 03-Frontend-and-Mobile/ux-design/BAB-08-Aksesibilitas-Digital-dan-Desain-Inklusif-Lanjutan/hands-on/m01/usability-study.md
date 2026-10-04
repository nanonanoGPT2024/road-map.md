---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah bedah struktural kelas `AccessibleDialog`:

* **Baris 24–27 (`this.dialogElement.setAttribute(...)`):**
  * `role="dialog"`: Mengumumkan ke assistive technologies bahwa komponen ini adalah sub-window interaktif terpisah.
  * `aria-modal="true"`: Memberitahu browser a11y engine bahwa elemen di luar kontainer dialog tidak boleh diperhitungkan dalam traversal screen reader (dukungan legacy sebelum spesifikasi `inert`).
  * `hidden`: Menghentikan rendering visual dan menghapus elemen dari a11y tree saat sedang inaktif.
* **Baris 42 (`this.previouslyFocusedElement = document.activeElement as HTMLElement`):** Menyimpan snapshot node fokus saat ini sebelum konteks dialihkan. Kegagalan menyimpan referensi ini menyebabkan *Focus Loss Pitfall*, di mana saat modal ditutup, fokus akan kembali secara acak ke `<body>`, memaksa pengguna keyboard mengulang navigasi dari awal halaman.
* **Baris 48 (`this.appRootElement.setAttribute('inert', '')`):** Fitur krusial. Ini secara otomatis melumpuhkan seluruh pointer, seleksi visual, dan navigasi Tab di seluruh aplikasi induk tanpa perlu memanipulasi `tabindex` setiap elemen individu di halaman luar modal.
* **Baris 63–65 (`this.previouslyFocusedElement.focus()`):** Eksekusi pemulihan fokus (Focus Restoration) deterministik saat modal ditutup.
* **Baris 97–100 (`event.key === 'Escape'`):** Memenuhi WCAG 2.2 Success Criterion 2.1.2 (No Keyboard Trap). Pengguna harus selalu diberikan rute keluar yang konsisten menggunakan tombol standar keyboard `Escape`.
* **Baris 112–126 (`trapFocus` edge routing):** Algoritma kompensasi keyboard trapping fallback. Jika pengguna berada di `lastElement` dan menekan `Tab`, fokus diarahkan ke `firstElement`. Jika berada di `firstElement` dan menekan `Shift + Tab`, fokus ditarik mundur ke `lastElement`.

---

## SEKSI 09 — STUDI KASUS NYATA

### Enterprise Scenario: Financial Core Banking Transaction Data Table

Sebuah perbankan multinasional memiliki antarmuka back-office bernama *ApexTrade* yang digunakan oleh ribuan operator, termasuk staf penyandang disabilitas low vision dan motorik parsial. 

#### Permasalahan Utama:
1. **Navigasi Tab Fatigue:** Halaman memiliki Data Table dengan 100 baris transaksi. Setiap baris memiliki 5 tombol aksi (`Lihat`, `Unduh`, `Setujui`, `Tolak`, `Log`). Untuk melompat dari tabel ke bagian formulir di bawahnya, pengguna keyboard harus menekan tombol `Tab` sebanyak 500 kali (100 baris × 5 tombol).
2. **Dynamic Stock Ticker Polling:** Sistem memperbarui kurs mata uang dan harga saham setiap 3 detik. Developer junior memasang atribut `aria-live="assertive"` pada kontainer harga. Hasilnya: Screen reader terus menerus memotong suara pembacaan dokumen dan membacakan kurs mata uang setiap 3 detik tanpa henti, merusak operasional pengguna tunanetra.
3. **Modal Form Broken Semantics:** Ketika modal konfirmasi transaksi muncul, screen reader tetap membaca transaksi di latar belakang karena pengembang hanya menggunakan CSS `position: fixed; z-index: 9999` tanpa mengisolasi a11y tree.

#### Target Rekayasa Sistem:
* Menghilangkan *Tab Fatigue* dengan mengonversi Data Table menggunakan pola **WAI-ARIA Data Grid Roving Tabindex Composite Widget**. Pengguna cukup menekan `Tab` sekali untuk masuk ke Grid, lalu menavigasi baris dan kolom menggunakan tombol panah (`Arrow Keys`), kemudian menekan `Tab` sekali lagi untuk keluar dari Grid secara langsung.
* Mengisolasi live stream ticker menggunakan decoupled buffer berbasis `aria-live="polite"` yang hanya membacakan perubahan ketika pengguna secara spesifik meminta ringkasan (User-Polled Live Announcer).
* Membangun Focus Boundary and Isolation menggunakan native `inert` controller.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Implementasi Grid Roving Tabindex untuk perbankan skala enterprise menggunakan TypeScript:
