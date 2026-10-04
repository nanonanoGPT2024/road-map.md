---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

Mendedah arsitektur internal dari implementasi `BaseSelect.vue`:

*   **Baris 1:** `<script setup lang="ts" generic="TValue extends string | number, TOption extends { label: string; value: TValue }">`
    *Mekanisme:* Mendeklarasikan parameter generic level SFC. `TValue` dikunci agar hanya berupa tipe primitif yang valid sebagai identifier (`string | number`). `TOption` mewajibkan tipe data minimal memiliki properti `label` dan `value` bertipe `TValue`. Compiler Vue mengubah seluruh inferensi template terhadap komponen ini secara type-safe.
*   **Baris 5–10:** `interface Props { options: TOption[]; ... }` & `withDefaults(defineProps<Props>(), { ... })`
    *Mekanisme:* Mengikat props dengan contract static interface murni. Macro `withDefaults` menyuntikkan fallback value pada fase kompilasi tanpa menciptakan mutasi reaktif buatan runtime.
*   **Baris 18–21:** `interface Emits { (e: 'update:modelValue', value: TValue): void; ... }`
    *Mekanisme:* Mendefinisikan signature payload type-safe untuk implementasi dua-arah `v-model`. Emit `update:modelValue` hanya menerima argumen tipe `TValue`, mencegah lolosnya tipe yang salah ke parent.
*   **Baris 26–29:** `defineSlots<{ default?(props: { option: TOption; isSelected: boolean }): any; ... }>()`
    *Mekanisme:* Melakukan registrasi tipe scoped slots. Ketika developer memanfaatkan template slot default, compiler Vue Language Tools (Volar) mengekstrapolasi bahwa parameter slot tersebut membawa properti `option` bertipe `TOption` secara presisi.
*   **Baris 33–35:** `computed<TOption | undefined>(() => { ... })`
    *Mekanisme:* Pipeline caching memori. Komputasi hanya dijalankan ulang ketika pointer reaktivitas `props.options` atau `props.modelValue` mengalami mutasi referensial.
*   **Baris 48–53:** `defineExpose({ reset, isOpen: computed(...) })`
    *Mekanisme:* Menjalankan isolasi *public API boundary*. Hanya fungsi `reset` dan `isOpen` yang dapat diakses oleh Parent component via template refs. Seluruh internal method (`handleSelect`, dll) disegel secara privat di dalam scope lexical SFC.

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario: Multi-Tenant Enterprise Data Query Orchestrator
**Domain:** Sistem Analytics Core SaaS Perbankan.
**Masalah:**
Tim frontend menghadapi ledakan duplikasi kode pada 12 dashboard analitik yang berbeda. Tim sebelumnya membangun sebuah "God Component" bernama `<MasterTable.vue>` yang menerima lebih dari 65 props (handling pagination, sorting, row expansion, inline editing, column toggling, batch selection, server sync). 

Setiap kali modul analitik baru membutuhkan variasi kolom atau aksi baru:
1. File komponen raksasa (3,500 baris) tersebut dimodifikasi, memicu regresi pengujian (*regression bugs*) pada modul lain.
2. Render payload tree menjadi lambat: Perubahan filter pada satu field memicu re-render keseluruhan 500 VNodes baris data karena isolasi reaktivitas yang bocor.
3. Sulitnya kustomisasi UI per tenant (misal: beberapa tenant menuntut kustom cell rendering berupa sparkline visual, tenant lain hanya teks angka biasa).

**Solusi Arsitektur:**
Merekonstruksi modul tabel analitik menggunakan arsitektur **Compound Component Contract Pattern**:
*   `DataTableProvider`: Mengorkestrasi state transaksi server, sorting, dan multi-row selections.
*   `DataTable`: Komponen layout murni pembungkus semantic markup.
*   `DataColumn`: Komponen deklarator struktur metadata kolom dan slot visual.
*   `DataTableToolbar`: Inversion of control untuk aksi batch dan konfigurasi filter.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Arsitektur Compound Component: Modular, Type-Safe, Production-Ready.

#### 1. Kontrak Komponen & Injection Token (`types.ts`)
