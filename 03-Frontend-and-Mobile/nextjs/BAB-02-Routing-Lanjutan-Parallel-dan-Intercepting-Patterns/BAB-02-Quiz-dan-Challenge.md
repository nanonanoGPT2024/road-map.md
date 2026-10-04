# BAB 02: Quiz, Challenge, & Knowledge Check
**Routing Lanjutan, Parallel, & Intercepting Patterns**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Mekanisme Soft Navigation vs. Hard Navigation pada Parallel Slots:**
   Jelaskan perbedaan mendasar perilaku Next.js App Router saat mengeksekusi *soft navigation* (via `<Link>` atau `router.push()`) dibandingkan *hard navigation* (browser refresh/F5 atau direct URL entry) terhadap parallel route slot (`@slot`). Mengapa status slot yang aktif dapat dipertahankan pada skenario pertama namun memicu evaluasi ulang total pada skenario kedua?
2. **Hierarki & Batasan Konvensi Intercepting Routes:**
   Uraikan aturan pencocokan segmen (*matching segment*) untuk operator intercepting: `(.)`, `(..)`, `(..)(..)`, dan `(...)`. Bagaimana keberadaan Route Groups `(groupName)` memengaruhi level pelompatan segmen ketika Anda menggunakan operator `(..)`?
3. **Implicit Slot (`children`) vs. Explicit Parallel Slots:**
   Secara arsitektural, `children` prop pada Next.js layout sebenarnya adalah sebuah parallel slot implisit (`@children`). Bagaimana Next.js Server Components (RSC) engine menggabungkan payload RSC dari slot implisit ini bersama parallel slots eksplisit (misal `@analytics`, `@modal`) ke dalam satu Virtual DOM tree saat rendering fase server?
4. **Lifecycle Request pada Intercepting Modal Pattern:**
   Ketika user mengklik card produk `/photo/123` dari halaman feed `/feed`, aplikasi menampilkan modal via intercepting route `(.)photo/[id]`. Namun, saat URL disalin dan dibuka di tab baru, aplikasi merender halaman penuh `/photo/123` tanpa layout `/feed`. Uraikan diagram alir pemrosesan request HTTP dan resolusi routing yang dilakukan Next.js server untuk dua kondisi tersebut.
5. **Peran Kritis dan Mekanisme Fallback `default.js`:**
   Apa fungsi deterministik dari berkas `default.js` di dalam struktur folder parallel slot? Apa implikasi teknis spesifik yang terjadi pada UI dan konsol runtime Next.js jika terjadi *unmatched hard navigation* pada route bertingkat yang tidak mendefinisikan `default.js`?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Debugging Error 404 pada Hard Refresh di Parallel Routing:**
   Sebuah layout memiliki slot `@modal`. Di dalam folder `@modal`, developer membuat route interceptor `(.)login/page.tsx` dan route biasa `login/page.tsx`. Saat berada di root `/` lalu membuka `/login` via link, modal muncul. Namun, saat user melakukan refresh pada URL `/login`, server mengembalikan status 404 (Not Found). Diagnosis akar masalah pada level arsitektur direktori dan tentukan struktur folder yang presisi untuk memperbaikinya.
2. **Resolusi Prioritas Segmen Dynamic Catch-All vs. Intercepting Routes:**
   Jika sebuah aplikasi memiliki struktur rute:
   * `app/feed/[...slug]/page.tsx`
   * `app/feed/@modal/(.)photo/[id]/page.tsx`
   
   Bagaimana Next.js Router Engine menyelesaikan ambiguitas ketika terjadi soft navigation ke `/feed/photo/42`? Segment mana yang memiliki bobot spesifisitas (*specificity weight*) lebih tinggi, dan bagaimana struktur payload RSC yang dikembalikan ke client?
3. **State Inconsistency pada Router Cache Klien:**
   Dalam arsitektur parallel routing dengan dua slot independen (`@dashboard` dan `@activity_feed`), slot `@dashboard` memicu mutasi data via Server Action yang menjalankan `revalidatePath('/dashboard')`. Mengapa dalam kondisi tertentu slot `@activity_feed` tidak memperbarui tampilannya secara otomatis jika client-side Router Cache masih berstatus *fresh*? Bagaimana cara memaksakan sinkronisasi antar-slot tanpa memicu *full page reload*?
4. **Conditional Slot Rendering & SSR Hydration Mismatch:**
   Seorang software engineer membuat layout kondisional:
   ```tsx
   export default function Layout({ role_slot, admin_slot, user_slot }: LayoutProps) {
     const role = cookies().get('user_role')?.value;
     return (
       <main>
         {role === 'admin' ? admin_slot : user_slot}
       </main>
     );
   }
   ```
   Analisis potensi terjadinya hydration mismatch atau kebocoran state slot saat pengguna berpindah sesi (login/logout) menggunakan *soft navigation*. Bagaimana arsitektur App Router menangani unmounting parallel slot yang tidak lagi dirender?
5. **Edge-case Dismissing Modal via `router.back()`:**
   Pola umum untuk menutup intercepting modal adalah memanggil `router.back()`. Namun, jika user mengakses URL modal melalui tautan eksternal (mengakibatkan browser history length = 1), eksekusi `router.back()` akan melempar user keluar dari domain aplikasi atau tidak merespons sama sekali. Rancang strategi mitigasi terprogram untuk menangani dismissal modal secara deterministik dengan mempertimbangkan status history stack.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Produksi pada E-Commerce Flash Sale
*Konteks Sistem:* Marketplace enterprise dengan 20 juta MAU meluncurkan fitur "Quick View" produk menggunakan Parallel & Intercepting Routes (`@quickview/(.)product/[id]`). Infrastruktur menggunakan Next.js di-deploy di atas Kubernetes cluster dengan CDN Cloudflare di depannya.
*Gejala Masalah:* Saat Flash Sale dimulai, jutaan user membuka link produk yang disebarkan via broadcast WhatsApp/Push Notification (direct access). Server mengalami spike CPU 100% dan pod mengalami OOM (Out Of Memory) crash loop. Hasil tracing APM menunjukkan bahwa server merender layout katalog `/catalog` yang sangat berat secara berulang-ulang, padahal user hanya membuka link detail produk `/product/[id]`.
* **Pertanyaan Diagnostik:**
  1. Mengapa direct navigation ke `/product/[id]` justru mengeksekusi render tree layout induk yang tidak seharusnya terbebani?
  2. Bagaimana arsitektur caching CDN berinteraksi dengan intercepting headers (`Next-Url` / `rsc`) pada Next.js, dan mengapa cache poisoning bisa terjadi jika konfigurasi `Vary` header tidak tepat?
  3. Langkah mitigasi arsitektur apa yang harus diimplementasikan untuk memisahkan beban rendering standalone detail page dari layout parallel slot tanpa merusak user experience modal saat soft navigation?

---

### Skenario B: Race Condition State Mutasi pada Multi-pane Kanban Board
*Konteks Sistem:* Aplikasi SaaS Project Management memiliki layout parallel routes dengan tiga slot: `@sidebar`, `@board`, dan `@inspector`. Slot `@inspector` merupakan intercepting drawer `(..)task/[taskId]` yang menampilkan detail subtask.
*Gejala Masalah:* User membuka subtask A di `@inspector`, mengubah statusnya dari "Todo" ke "Done" via Server Action, lalu dengan cepat mengklik subtask B sebelum aksi pertama selesai. Terjadi race condition: data subtask A ter-revalidasi di server dan me-render ulang slot `@board`, namun slot `@inspector` mengalami state desynchronization (menampilkan data form subtask B tetapi dengan layout dan attachment milik subtask A).
* **Pertanyaan Diagnostik:**
  1. Bagaimana siklus hidup concurrent transition pada React 18/19 dan Next.js Router Cache memproses dua navigasi/mutasi yang saling tumpang tindih (*interleaved*) pada parallel slot yang sama?
  2. Komponen apa yang gagal mempertahankan referensi unik per segmen, dan mengapa Next.js secara default tidak mereset state lokal slot saat parameter ID berubah dengan cepat jika `key` tidak ditentukan secara eksplisit?
  3. Rancang perbaikan sistem state orchestration menggunakan React Transition hooks (`useTransition`) dan explicit layout segment keys untuk menjamin serialisasi atau pembatalan (*cancellation*) request yang aman.

---

### Skenario C: Enterprise Analytics Portal dengan 6 Parallel Slots & Streaming SSR
*Konteks Sistem:* Dashboard FinTech Enterprise menggabungkan 6 parallel slots dalam satu halaman dashboard: `@revenue`, `@churn`, `@fraud_alerts`, `@traffic`, `@realtime_logs`, dan `@audit_trail`. Setiap slot mengambil data dari microservices yang berbeda dengan latency bervariasi (50ms hingga 3500ms).
*Gejala Masalah:* Developer mengeluhkan bahwa First Contentful Paint (FCP) dashboard terdegradasi menjadi 3.5 detik (mengikuti microservice terlambat), dan jika satu microservice down (misal `@fraud_alerts`), seluruh halaman dashboard menampilkan error screen generic (`error.tsx` root terpicu).
* **Pertanyaan Diagnostik:**
  1. Mengapa error yang terjadi di dalam salah satu parallel slot menggelembung (*bubble up*) dan menghancurkan seluruh subtree layout jika tidak diisolasi?
  2. Bagaimana cara mengorkestrasi `Suspense`, `loading.tsx`, dan `error.tsx` pada tingkat folder individu untuk setiap slot `@slot` agar rendering 5 slot lainnya tetap berjalan instan secara asynchronous streaming tanpa terblokir oleh slot yang lambat atau gagal?
  3. Analisis trade-off resource consumption (TCP connections, Node.js worker event loop latency) pada server Next.js saat menangani 1.000 concurrent requests untuk sebuah page dengan 6 parallel server-component slots versus rendering via API client-side fetching.

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise Media Asset Inspector Architecture
Rancang dan implementasikan arsitektur routing enterprise untuk sistem Media Asset Management (DAM) yang menggabungkan Parallel Routes, Deep Interception, Isolated Boundary, dan State Preservation.

#### Problem:
Tim multimedia membutuhkan platform review video/gambar di mana user dapat menjelajahi feed asset tanpa kehilangan posisi scroll atau context filter, membuka asset inspector sebagai modal/drawer dengan URL yang dapat dibagikan (*shareable*), memiliki panel secondary parallel untuk komentar live, serta tahan terhadap hard reload dan direct entry.

#### Requirements:
1. **Root Feed & Layout Slot:**
   * Path: `/assets`
   * Menyediakan parallel slot `@inspector` dan `@metadata`.
2. **Deep Intercepting Route:**
   * Saat user mengklik asset di `/assets`, rute di-intercept menjadi modal detail `/assets/[id]` menggunakan pattern `(.)[id]`.
   * URL browser berubah menjadi `/assets/abc-123`.
3. **Dual-View Resolution:**
   * **Soft Navigation:** Menampilkan feed `/assets` di background, dengan asset inspector terbuka di atasnya via slot `@inspector`, dan metadata live-commentary terbuka di slot `@metadata`.
   * **Hard Navigation (Direct Link / F5):** Jika URL `/assets/abc-123` diakses langsung dari luar atau di-refresh, aplikasi **TIDAK BOLEH** menampilkan modal di atas feed kosong, melainkan harus merender **Dedicated Fullscreen Asset Workspace** dengan navigation bar khusus.
4. **Resilient Dismissal Strategy:**
   * Menyediakan tombol close modal yang cerdas: jika user datang dari soft navigation, gunakan `router.back()`. Jika direct entry, arahkan secara aman via `router.push('/assets')` tanpa merusak browser stack.
5. **Sub-slot Boundary Isolation:**
   * Slot `@metadata` harus dibungkus dengan `error.tsx` dan `loading.tsx` independen. Jika API metadata asset timeout, slot feed dan slot `@inspector` harus tetap interaktif tanpa crash.
6. **Slot Clearing Logic:**
   * Saat modal ditutup, slot `@inspector` dan `@metadata` harus di-unmount secara sempurna dan URL kembali ke `/assets` tanpa meninggalkan orphan parallel RSC payload di memory client.

#### Constraints:
* **Framework:** Next.js 14+ (App Router).
* **State Management:** Dilarang menggunakan global client state (Redux/Zustand) untuk mengontrol visibilitas modal. Wajib sepenuhnya dikendalikan oleh Next.js Parallel & Intercepting Routing state.
* **Typing:** Strict TypeScript (no `any`), validasi dynamic segment props dengan Next.js typed routes.
* **Component Paradigm:** Default Server Components; `'use client'` hanya diizinkan pada leaf components yang membutuhkan event listener atau browser API.

#### Expected Output:
* Skema pohon direktori project (`app/...`) yang mendemonstrasikan penempatan folder `@slots`, interceptor `(.)`, dan fallback `default.tsx`.
* Kode implementasi `app/assets/layout.tsx`.
* Kode implementasi route interceptor `app/assets/@inspector/(.)[id]/page.tsx`.
* Kode implementasi fallback `app/assets/@inspector/default.tsx` dan `app/assets/@metadata/default.tsx`.
* Kode leaf component untuk Close Button logic (`DismissButton.tsx`).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan fundamental antara soft navigation (client-side transitions) dan hard navigation (SSR evaluation) dalam eksekusi parallel routes.
- [ ] Aturan resolusi path untuk intercepting tokens: `(.)` (same level), `(..)` (one level up), `(..)(..)` (two levels up), dan `(...)` (root level).
- [ ] Peran dan mekanisme kerja berkas `default.js` sebagai server-side fallback untuk mempertahankan slot state yang tidak berubah saat navigasi URL parsial.
- [ ] Struktur data Next.js Server Components (RSC) payload yang dikirimkan melalui HTTP header saat intercepting route aktif.
- [ ] Bagaimana Route Groups `(groupName)` diabaikan dalam segment URL traversal namun diperhitungkan dalam path hierarki direktori file system.
- [ ] Mekanisme Error Boundary (`error.js`) dan Suspense Boundary (`loading.js`) yang terisolasi di dalam masing-masing parallel slot.
- [ ] Implikasi HTTP Caching & CDN edge caching terhadap response header `Vary: RSC, Next-Router-State-Tree`.

### Saya tidak perlu menghafal:
- [ ] String hash internal yang digunakan Next.js untuk mengidentifikasi build flight ID di RSC payload.
- [ ] Algoritma internal exact character matching parser rute di source code Next.js compiler (Rust/Turbopack).
- [ ] Seluruh konfigurasi legacy Webpack rewrite rule untuk intercepting routes versi lama.

### Saya harus bisa melakukan:
- [ ] Membangun layout dengan multiple dynamic parallel slots yang stabil terhadap hard navigation dan direct linking.
- [ ] Mengimplementasikan pola Intercepting Modals/Drawers dengan deep-linking support yang dapat di-share antar-user.
- [ ] Mencegah dan mendebug error 404 unhandled parallel route saat hard refresh menggunakan berkas `default.tsx`.
- [ ] Mengisolasi runtime crash antar-parallel-slot menggunakan granular `error.tsx` sub-boundaries.
- [ ] Mengimplementasikan programmatic dismissal logic yang aman antara history-back dan route fallback.
- [ ] Mengoptimalkan rendering latency parallel slots menggunakan streaming SSR dengan React Suspense.