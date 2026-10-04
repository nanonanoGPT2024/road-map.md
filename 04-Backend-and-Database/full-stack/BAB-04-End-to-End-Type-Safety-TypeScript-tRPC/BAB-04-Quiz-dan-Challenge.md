---
[⬅️ Module 02: tRPC & Zod Validation](./Module-02-tRPC-Zod-Validation-dan-Contract-First-APIs.md) | [📋 Silabus Induk](../README.md) | [BAB 05: Full-Stack Data Layer ➡️](../BAB-05-Data-Layer-ORMs-dan-Serverless-Databases/Module-01-Modern-ORMs-Drizzle-Prisma-Connection-Pooling.md)
---

# BAB 04: Evaluasi Pembelajaran — Quiz, Challenge, & Knowledge Check

## 1. Uji Pemahaman Mandiri (Quiz)

### A. Soal Tingkat Dasar (Basic Questions)
1. **Apa perbedaan mendasar antara *static type checking* TypeScript dengan *runtime validation* Zod?**
2. **Mengapa kata kunci `infer` hanya dapat digunakan di dalam klausa `extends` pada sebuah Conditional Type di TypeScript?**
3. **Bagaimana cara kerja Template Literal Types dalam TypeScript dan apa manfaatnya untuk membatasi format string seperti rute URL atau kode warna Hexadecimal?**
4. **Apa yang dimaksud dengan Discriminated Union (Tagged Union) dan apa peran properti diskriminan dalam proses narrowing tipe data?**
5. **Mengapa saat mengimpor router tRPC ke dalam kode frontend kita diwajibkan menggunakan sintaks `import type { AppRouter }` alih-alih `import { AppRouter }` biasa?**

---

### B. Soal Tingkat Menengah (Intermediate Questions)
6. **Jelaskan bagaimana utilitas tipe bawaan `Omit<T, K>` dan `Pick<T, K>` diimplementasikan di balik layar menggunakan kombinasi Mapped Types dan keyword `keyof`!**
7. **Pada validasi Zod, kapan seorang arsitek software harus memilih menggunakan `safeParse` dibandingkan dengan `parse` biasa? Apa implikasi performa dan alur eksekusi kodenya?**
8. **Bagaimana tRPC mentransmisikan tipe data kompleks seperti `Date`, `BigInt`, atau `Map` melintasi jaringan JSON tanpa kehilangan prototipe objek aslinya pada sisi client?**
9. **Jelaskan cara kerja teknik *Exhaustive Checking* dengan memanfaatkan tipe `never` dalam blok `switch-case`! Apa keuntungan arsitekturalnya saat ada penambahan varian union baru di masa depan?**
10. **Bagaimana arsitektur Middleware pada tRPC dapat memodifikasi atau memperkaya (*enrich*) objek `ctx` (Context) sehingga prosedur di hilir (*downstream*) memperoleh data yang telah terverifikasi secara type-safe?**

---

### C. Soal Berbasis Skenario Arsitektur (Scenario-Based Questions)
11. **Skenario Kasus — Monorepo Financial Tech**:
    Sebuah aplikasi perbankan digital memiliki backend Node.js dan dua client: Next.js Web App dan React Native Mobile App yang berada dalam satu Turborepo. Tim backend memperbarui skema transfer dana dengan menambahkan kolom wajib `twoFactorBiometricToken`.
    - Apa yang akan terjadi pada build pipeline CI/CD di sisi frontend web dan mobile jika menggunakan tRPC?
    - Bagaimana mekanisme ini secara preventif menghentikan pengiriman kode cacat (*broken release*) ke production dibandingkan dengan arsitektur REST biasa tanpa validasi kontrak?
12. **Skenario Kasus — Multi-Tenant Dynamic Role Permission**:
    Anda diminta merancang skema validasi Zod bersyarat: Jika payload berisi properti `organizationType: "ENTERPRISE"`, maka properti `auditLogRetentionDays` wajib bernilai minimal `365`. Namun jika `organizationType: "COMMUNITY"`, properti tersebut bersifat opsional dan maksimal bernilai `30`.
    - Bagaimana Anda menyusun skema ini menggunakan Zod (apakah menggunakan `z.discriminatedUnion` atau `z.refine`)? Jelaskan trade-off dari kedua pendekatan tersebut!
13. **Skenario Kasus — Server Action & tRPC Coexistence**:
    Sebuah tim engineer sedang memigrasikan aplikasi web mereka ke Next.js App Router. Sebagian developer menyukai React Server Actions karena terintegrasi langsung dengan `<form>`, sementara tim lain menyukai tRPC karena manajemen server-state via React Query yang matang di client.
    - Bagaimana strategi Anda memadukan atau memilih antara Server Actions dan tRPC dalam arsitektur sistem enterprise yang sama? Kapan Server Action lebih unggul, dan kapan tRPC menjadi pilihan mutlak?

---

## 2. Chapter Challenge: Mini Type-Safe Event-Driven System

### Deskripsi Tantangan
Anda ditugaskan merancang modul Type-Safe Event Bus & Dispatcher untuk sistem e-commerce berskala besar. Sistem ini harus menjamin bahwa event yang dipublikasikan (*published*) memiliki payload yang 100% valid saat runtime (via Zod) dan tidak dapat memicu event string sembarangan saat kompilasi (via TypeScript Template Literal Types).

### Kebutuhan & Spesifikasi:
1. **Domain Event Namespace**:
   Bentuk event harus mematuhi template literal: `domain:action` (misalnya: `"ORDER:CREATED"`, `"ORDER:CANCELLED"`, `"PAYMENT:RECEIVED"`, `"PAYMENT:FAILED"`).
2. **Strict Schema Mapping**:
   Setiap event harus terikat secara permanen dengan skema Zod spesifik:
   - Event `"ORDER:CREATED"` mewajibkan payload `{ orderId: string (UUID), amount: number (positif), customerEmail: string (email) }`.
   - Event `"PAYMENT:RECEIVED"` mewajibkan payload `{ paymentId: string, referenceNumber: string, gateway: "BCA" | "MANDIRI" | "STRIPE" }`.
3. **Type-Safe Dispatcher Function**:
   Buat fungsi `emitEvent(event, payload)` yang:
   - Hanya menerima event yang terdaftar dalam union tipe yang sah.
   - IDE secara otomatis menyarankan (*autocomplete*) kolom payload yang sesuai begitu nama event diketik.
   - Menjalankan validasi runtime Zod sebelum memproses event ke handler. Jika payload tidak valid, lemparkan error terstruktur tanpa menghentikan proses event lainnya.

---

## 3. Knowledge Check & Mastery Checklist

### Yang Wajib Anda Pahami:
- [ ] Hakikat TypeScript sebagai bahasa manipulasi tipe saat kompilasi (*compile-time*) yang dihilangkan (*erased*) total saat JavaScript dijalankan di runtime.
- [ ] Alasan mengapa skema runtime seperti Zod mutlak dibutuhkan untuk memvalidasi perbatasan eksternal (API body, query string, environment variables, local storage).
- [ ] Konsep *Single Source of Truth*: mendeklarasikan skema Zod satu kali, lalu menurunkan tipe statis menggunakan `z.infer<typeof Schema>`.
- [ ] Cara tRPC mengeliminasi kebutuhan *API code generator* dengan memanfaatkan fitur *type inference* dari router TypeScript.

### Yang Tidak Perlu Anda Hafal di Luar Kepala:
- Regex spesifik untuk validasi email RFC 5322 atau string UUID v4 (cukup gunakan utilitas bawaan `.email()` dan `.uuid()` dari Zod).
- Daftar kode error internal tRPC (`UNAUTHORIZED`, `FORBIDDEN`, `PRECONDITION_FAILED`, dll)—dapat dilihat dengan cepat melalui autocomplete IDE saat mengetik `TRPCError`.

### Yang Harus Bisa Anda Lakukan:
- [ ] Menulis custom Type Guards (`value is TargetType`) dan *Assertion Functions* (`asserts condition`).
- [ ] Mengonstruksi Mapped Types dengan *Key Remapping* (`as`) dan *Template Literal Types*.
- [ ] Membangun router tRPC lengkap dengan Context, Middleware proteksi hak akses, dan Zod Input Validation.
- [ ] Menangani pemanggilan procedure dari komponen frontend dengan penanganan status loading, error, dan caching.

---

## 4. Ringkasan Bab (Chapter Summary)
Bab 04 telah membongkar fondasi terdalam dari **End-to-End Type Safety** dalam rekayasa perangkat lunak full-stack modern:
1. **Advanced Type-Level Programming** memberikan kemampuan untuk mengekspresikan aturan domain yang sangat ketat langsung pada level kompilator TypeScript, meniadakan bug sebelum aplikasi sempat di-*bundle*.
2. **Zod Runtime Validation** melengkapi TypeScript dengan menjadi garda depan yang memverifikasi keabsahan data mentah yang memasuki ekosistem aplikasi saat runtime.
3. **tRPC Framework** menjembatani backend dan frontend secara elegan dengan mengekspos tipe router secara langsung tanpa pembengkakan ukuran bundle client browser.

Dengan menguasai ekosistem type safety ini, Anda siap melangkah ke **BAB 05: Full-Stack Data Layer**, di mana kita akan mempelajari bagaimana tipe data disinkronkan secara mulus dari tabel database SQL ke ORM modern (Drizzle & Prisma), connection pooling di arsitektur serverless, serta strategi caching gateway di edge!

---
[⬅️ Module 02: tRPC & Zod Validation](./Module-02-tRPC-Zod-Validation-dan-Contract-First-APIs.md) | [📋 Silabus Induk](../README.md) | [BAB 05: Full-Stack Data Layer ➡️](../BAB-05-Data-Layer-ORMs-dan-Serverless-Databases/Module-01-Modern-ORMs-Drizzle-Prisma-Connection-Pooling.md)
---
