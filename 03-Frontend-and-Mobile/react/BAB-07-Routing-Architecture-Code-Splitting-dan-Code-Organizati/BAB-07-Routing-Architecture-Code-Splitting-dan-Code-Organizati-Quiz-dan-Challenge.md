# BAB-07-Routing-Architecture-Code-Splitting-dan-Code-Organizati: Quiz, Challenge, & Knowledge Check

Dokumen ini dirancang sebagai instrumen evaluasi komprehensif untuk menguji pemahaman konseptual, arsitektur perutean modern, strategi *code splitting*, *bundle optimization*, serta struktur organisasi kode React berskala enterprise (Feature-driven / Vertical Slice Architecture).

---

## Bagian 1: Basic Questions (5 Soal)

### Soal 1.1: Client-Side Routing vs Server-Side Routing
**Pertanyaan:**  
Jelaskan perbedaan mendasar mekanisme kerja antara *Client-Side Routing* (CSR) menggunakan React Router dengan *Server-Side Routing* (SSR/MPA konvensional) ketika pengguna mengklik link navigasi, dan mengapa CSR memerlukan penanganan khusus (seperti konfigurasi *fallback* `index.html`) pada web server (Nginx/Cloudflare Pages/S3)?

**Kunci Jawaban & Pembahasan:**  
Pada *Server-Side Routing*, setiap navigasi URL memicu HTTP GET request penuh ke web server. Server membaca path URL, mengeksekusi logika backend, dan merender dokumen HTML baru secara utuh ke browser (terjadi siklus *full page reload*).

Pada *Client-Side Routing*, navigasi diintersepsi oleh JavaScript melalui HTML5 History API (`window.history.pushState` atau `replaceState`). URL bar browser berubah tanpa melakukan request dokumen HTML baru ke server. Router mencocokkan path URL dengan komponen React yang sesuai di memori, lalu melakukan reconcilation pada DOM secara dinamis.

Konfigurasi fallback `index.html` (rewrite rule `try_files $uri /index.html;` pada Nginx) wajib disediakan karena ketika pengguna me-refresh browser pada path non-root (misal `/dashboard/billing`), browser mengirim request HTTP GET langsung untuk file `/dashboard/billing` ke web server. Jika server tidak memiliki direktori atau file fisik tersebut, server akan mengembalikan status HTTP 404. Dengan fallback rewrite, server akan selalu menyajikan `index.html`, sehingga bundle JavaScript React dapat dimuat dan React Router dapat membaca URL serta merender halaman yang tepat.

---

### Soal 1.2: Mekanisme Dynamic Import & `React.lazy`
**Pertanyaan:**  
Bagaimana sintaks `import()` dinamis bekerja bersama `React.lazy()` dan komponen `<Suspense />`? Apa yang terjadi pada siklus render React saat chunk JavaScript yang diminta masih dalam proses pengunduhan (*in-flight*) melalui jaringan?

**Kunci Jawaban & Pembahasan:**  
Sintaks `import('./Component')` mengembalikan sebuah `Promise` yang menyelesaikan (*resolves*) modul ES dengan properti default export. Fungsi `React.lazy(() => import('./Component'))` membungkus pemanggilan promise tersebut ke dalam komponen React khusus yang mengenali status promise (pending, resolved, rejected).

Komponen `<Suspense fallback={<Spinner />}>` bertindak sebagai *boundary asynchronous*. Ketika komponen lazy pertama kali dievaluasi dan chunk JS-nya masih diunduh (promise berstatus *pending*), React "melempar" (*throws*) promise tersebut ke atas component tree. Komponen `<Suspense>` terdekat menangkap promise tersebut, menunda render tree anak, dan merender antarmuka alternatif yang didefinisikan pada prop `fallback`. Begitu promise resolves (chunk JS selesai diunduh dan diparse), React memicu re-render dan menampilkan komponen asli tanpa memuat ulang seluruh halaman.

---

### Soal 1.3: Nested Routes dan Komponen `<Outlet />`
**Pertanyaan:**  
Dalam React Router v6+, apa peran komponen `<Outlet />` dalam arsitektur *Nested Routes*, dan bagaimana data context dapat diteruskan dari layout induk ke route anak menggunakan hook bawaan?

**Kunci Jawaban & Pembahasan:**  
Komponen `<Outlet />` berfungsi sebagai placeholder visual di dalam layout induk tempat komponen anak (*child route matches*) dirender. Ini memungkinkan pembuatan layout bersarang (*nested layout*) seperti header, sidebar navigasi, dan footer yang tetap persisten tanpa me-remount DOM ketika pengguna berpindah antar sub-route.

Untuk meneruskan data atau state dari layout induk ke child route yang dirender di dalam `<Outlet />`, React Router menyediakan prop `context` pada `<Outlet context={data} />`. Di sisi komponen anak, data tersebut dapat diakses secara langsung dan reaktif menggunakan hook `useOutletContext<ContextType>()`.

---

### Soal 1.4: Perbedaan `useNavigate` vs `<Navigate />`
**Pertanyaan:**  
Kapan seorang software engineer harus menggunakan imperative navigation hook `useNavigate()` dibanding declarative navigation component `<Navigate />`? Berikan contoh anti-pattern penggunaan keduanya.

**Kunci Jawaban & Pembahasan:**  
- `useNavigate()` digunakan untuk navigasi *imperative* yang dipicu oleh interaksi event handler atau side-effect asynchronous (misalnya: setelah mutasi API selesai pada form submission, setelah timeout, atau pada tombol event click).
- `<Navigate />` digunakan untuk navigasi *declarative* di level rendering JSX (misalnya: redirect langsung di dalam guard component ketika kondisi auth tidak terpenuhi: `if (!isAuthenticated) return <Navigate to="/login" replace />;`).

**Anti-pattern:**  
Menggunakan `useNavigate()` di dalam tubuh utama fungsi komponen (*during render phase*) tanpa dibungkus `useEffect`. Hal ini melanggar aturan rendering murni React dan menyebabkan *side-effect during render warning* atau siklus render loop tak terduga. Sebaliknya, merender `<Navigate />` di dalam event handler (misal `onClick={() => <Navigate to="/home" />}`) tidak akan melakukan navigasi karena return JSX dari event callback diabaikan oleh React.

---

### Soal 1.5: URL Query Parameters vs Route Path Parameters
**Pertanyaan:**  
Jelaskan perbedaan semantik dan teknis antara Route Path Parameter (contoh: `/users/:userId`) dan URL Search Query Parameter (contoh: `/users?role=admin&page=2`), serta sebutkan hook React Router yang digunakan untuk membaca masing-masing parameter tersebut.

**Kunci Jawaban & Pembahasan:**  
- **Route Path Parameter (`/users/:userId`):** Digunakan untuk mengidentifikasi *resource* spesifik yang hierarkis dan esensial. Parameter ini wajib ada untuk menentukan identitas rute dan view yang akan dirender. Dibaca menggunakan hook `useParams()`.
- **URL Search Query Parameter (`/users?role=admin&page=2`):** Digunakan untuk data opsional yang memodifikasi representasi koleksi data, seperti filter, sorting, pagination, search term, atau view mode. URL query parameter tidak mengubah hierarki resource utama. Dibaca dan dimodifikasi menggunakan hook `useSearchParams()`.

---

## Bagian 2: Intermediate Questions (5 Soal)

### Soal 2.1: Data Loaders & Actions (Data APIs) vs `useEffect` Data Fetching
**Pertanyaan:**  
Mengapa arsitektur Data APIs pada React Router v6.4+ (`createBrowserRouter`, `loader`, `action`) mengeliminasi masalah *Network Waterfalls* yang umum terjadi pada pendekatan tradisional `useEffect` di dalam komponen? Jelaskan aliran eksekusinya.

**Kunci Jawaban & Pembahasan:**  
Pada pendekatan tradisional berbasis `useEffect`, browser harus:
1. Mengunduh bundle JS layout induk.
2. Mengeksekusi JS dan me-mount layout induk.
3. Menjalankan `useEffect` induk untuk fetch data A.
4. Menunggu response data A selesai, lalu merender child component.
5. Child component mengunduh chunk JS anak, me-mount, lalu menjalankan `useEffect` anak untuk fetch data B.  
Rangkaian berurutan ini menciptakan *Network Waterfall* yang memperlambat LCP (*Largest Contentful Paint*).

Dengan Data APIs (`createBrowserRouter`):
React Router memisahkan pendefinisian data fetching dari siklus hidup render komponen. Saat transisi URL terjadi, React Router langsung mencocokkan seluruh segmen hierarki route dan mengeksekusi semua fungsi `loader` terkait secara paralel sebelum atau berbarengan dengan pengunduhan komponen lazy. Router mengunduh data secara serentak di level network layer tanpa menunggu rantai komponen selesai me-mount satu per satu.

---

### Soal 2.2: Chunk Splitting Strategy pada Vite/Rollup
**Pertanyaan:**  
Perhatikan konfigurasi `manualChunks` Rollup berikut:
```typescript
// vite.config.ts
export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          charts: ['echarts', 'zrender'],
        },
      },
    },
  },
});
```
Apa tujuan pemisahan vendor chunks tersebut terhadap browser caching (*Long-term Caching*), dan apa risiko arsitektural jika dependency internal app secara sirkular mengimpor modul di antara chunk tersebut?

**Kunci Jawaban & Pembahasan:**  
Pemisahan vendor ke dalam chunk terisolasi bertujuan untuk memaksimalkan *Long-term Caching* pada browser. Kode framework dan library pihak ketiga (`react`, `react-dom`) jarang berubah dibanding kode bisnis aplikasi. Dengan memisahkan vendor ke chunk tersendiri yang memiliki hash unik, browser dapat menyimpan cache vendor chunk secara permanen (HTTP header `Cache-Control: max-age=31536000, immutable`). Ketika developer merilis pembaruan kode bisnis, pengguna hanya perlu mengunduh chunk aplikasi yang berubah hash-nya tanpa perlu mengunduh ulang gigabyte/megabyte library pihak ketiga.

**Risiko Sirkular:**  
Jika modul di dalam chunk A mengimpor modul dari chunk B dan sebaliknya, Rollup akan kesulitan menentukan urutan eksekusi inisialisasi modul atau bahkan terpaksa menggabungkan kembali kedua chunk tersebut (*chunk bleeding*) atau menghasilkan runtime error berupa `TDZ (Temporal Dead Zone)` / `undefined import` saat runtime browser.

---

### Soal 2.3: Route-based Code Splitting vs Component-based Code Splitting
**Pertanyaan:**  
Bandingkan efektivitas antara *Route-based Code Splitting* (membagi chunk per halaman) dengan *Component-based / Interaction-based Code Splitting* (membagi chunk untuk modal besar, editor teks WYSIWYG, atau viewer 3D yang hanya dibuka saat tombol ditekan). Kapan Component-based splitting menjadi wajib diterapkan?

**Kunci Jawaban & Pembahasan:**  
- **Route-based Code Splitting:** Praktik dasar memecah bundle berdasarkan boundary halaman URL (`/analytics`, `/settings`). Pendekatan ini efektif menurunkan Initial Bundle Size saat kunjungan pertama ke aplikasi, tetapi seluruh kode yang ada di halaman tersebut (termasuk komponen tersembunyi seperti drawer, modal konfirmasi, atau dialog export kompleks) tetap diunduh saat halaman tersebut dibuka.
- **Component-based / Interaction-based Code Splitting:** Memecah komponen berat yang berada di dalam halaman yang sama menggunakan `React.lazy` atau dynamic import kondisional (`const Editor = lazy(() => import('./MonacoEditor'))`), yang hanya dipicu saat pengguna melakukan interaksi tertentu (misalnya mengklik tombol "Buka Editor").

**Kondisi Wajib:**  
Component-based splitting wajib diterapkan ketika sebuah halaman memuat library pihak ketiga berukuran sangat besar (>100-300 KB gzipped) seperti rich-text editor (TinyMCE/Draft.js/Monaco), PDF Renderer (PDF.js), Charting engine (ECharts/D3), atau 3D Canvas (Three.js/Fiber) yang hanya diakses oleh sebagian kecil pengguna (<20% sesi) atau berada di balik modal interaktif. Mengunduh library ini di awal kunjungan halaman akan membuang bandwidth dan menghambat TBT (*Total Blocking Time*).

---

### Soal 2.4: Feature-driven Architecture vs Layer-first Architecture
**Pertanyaan:**  
Analisis kelemahan struktur folder *Layer-first* (`src/components`, `src/hooks`, `src/services`, `src/types`) ketika aplikasi berkembang menjadi lebih dari 100 fitur dan 50 engineer, serta bagaimana *Feature-driven Architecture* (`src/features/auth`, `src/features/billing`) mengatasi problem skalabilitas dan *coupling* tersebut.

**Kunci Jawaban & Pembahasan:**  
**Kelemahan Layer-first:**
1. **High Cognitive Load:** Developer yang mengerjakan satu fitur (misal: "Billing Invoices") harus berpindah-pindah di antara folder yang berjauhan: `src/components/BillingTable.tsx`, `src/hooks/useBilling.ts`, `src/services/billingApi.ts`, dan `src/types/billing.d.ts`.
2. **Accidental Coupling:** Tidak ada batas isolasi yang jelas; komponen fitur Billing dengan mudah diimpor oleh modul Auth atau Profile tanpa aturan tegas, menciptakan jaring ketergantungan rumit (*spaghetti dependencies*).
3. **Dead Code Accumulation:** Saat suatu fitur dihapus atau dihentikan (*deprecated*), sangat sulit menghapus semua file terkait di berbagai layer tanpa memicu error referensi tak terduga.

**Solusi Feature-driven Architecture:**  
Setiap domain bisnis dibungkus ke dalam *self-contained vertical slice* (`src/features/[featureName]/`) yang memiliki komponen, API, hook, dan tipe lokalnya sendiri. Komunikasi antar fitur hanya diperbolehkan melalui public interface yang diekspos melalui `index.ts` fitur tersebut (*barrel file*). Hal ini membatasi *blast radius* refactoring, mempermudah *ownership* per tim, dan memungkinkan penghapusan fitur secara bersih cukup dengan menghapus folder fiturnya saja.

---

### Soal 2.5: Route Preloading & Prefetching
**Pertanyaan:**  
Mengapa *Route-based Code Splitting* dapat memicu penurunan UX berupa latensi visual ("flash of loading spinner") saat pengguna mengklik tautan antar halaman, dan bagaimana teknik *Intent-based Prefetching* (misal pada `onMouseEnter` atau `onFocus`) mengatasi masalah ini tanpa membebani bandwidth secara berlebihan?

**Kunci Jawaban & Pembahasan:**  
Ketika rute di-*lazy load*, chunk JS baru mulai diunduh dari CDN/server hanya **setelah** event klik terjadi dan URL bar berubah. Akibatnya, browser harus menahan tampilan dan menampilkan `<Suspense fallback={<Spinner />}>` selama latensi jaringan berlangsung (100ms - 2s pada koneksi mobile). Transisi visual yang terputus-putus ini menurunkan persepsi responsivitas aplikasi.

**Solusi Intent-based Prefetching:**  
Rata-rata terdapat selisih waktu 200ms–400ms antara saat kursor mouse pengguna melayang di atas link navigasi (`onMouseEnter`/`onFocus`) dengan saat klik fisik terjadi. Dengan mengeksekusi dynamic import `const loadDashboard = () => import('./Dashboard')` saat mouse hover, browser mulai mengunduh chunk JS dan menyimpannya di browser cache sebelum klik dieksekusi. Saat link benar-benar diklik, chunk JS sudah tersedia di memori atau disk cache lokal, sehingga Suspense fallback tidak perlu muncul dan halaman beralih secara instan (*near zero latency*). Jika pengguna tidak jadi mengklik, bandwidth yang terpakai minimal dan tidak memblokir thread rendering utama.

---

## Bagian 3: Skenario Kasus Nyata Produksi (3 Skenario)

### Skenario 3.1: Chunk Load Error saat Deployment Baru (*Stale Asset Failure*)
**Konteks Masalah:**  
Aplikasi SaaS Enterprise dengan ribuan pengguna aktif baru saja merilis versi `v2.4.0` ke produksi melalui pipeline CI/CD (hosting di AWS S3 + Cloudflare CDN). Sekitar 10 menit setelah rilis, customer support menerima puluhan tiket dari pengguna yang sedang aktif menggunakan aplikasi: ketika mereka membuka menu "Invoices", layar mendadak blank putih atau menampilkan crash message. Console browser mencatat error:
`Failed to fetch dynamically imported module: https://app.saas.com/assets/Invoices-ab12cd34.js (HTTP 404 Not Found)`.

**Analisis Akar Masalah:**  
Aplikasi menggunakan hashing konten pada build bundler (`[name]-[contenthash].js`). Saat deployment `v2.4.0` dijalankan, pipeline build menghapus aset lama di S3 dan menggantikannya dengan file baru ber-hash baru (`Invoices-ef56gh78.js`). Pengguna yang telah membuka tab browser sejak sebelum deployment masih memegang `index.html` versi lama di memori mereka, yang mereferensikan chunk lazy `Invoices-ab12cd34.js`. Saat pengguna menavigasi ke halaman Invoices, browser meminta file chunk lama yang sudah dihapus dari server, menghasilkan status 404 yang memicu Promise rejection pada `React.lazy`.

**Solusi Arsitektur Komprehensif:**
1. **Immutable CDN Versioning Retention:** Konfigurasikan S3 bucket/CDN agar tidak menghapus aset statis build sebelumnya (*incremental upload / keep old assets for at least 7-14 days*). Hanya file `index.html` yang selalu di-overwrite dan disajikan dengan header `Cache-Control: no-cache, no-store, must-revalidate`.
2. **Dynamic Import Error Boundary with Auto-Recovery:** Bungkus komponen lazy dengan wrapper khusus yang menangkap error import chunk dan memicu *hard reload* terkontrol jika versi baru terdeteksi:
```typescript
// src/utils/lazyWithRetry.ts
import { ComponentType, lazy } from 'react';

export function lazyWithRetry<T extends ComponentType<any>>(
  componentImport: () => Promise<{ default: T }>
) {
  return lazy(async () => {
    const pageHasBeenForceRefreshed = JSON.parse(
      window.sessionStorage.getItem('chunk_retry_refreshed') || 'false'
    );

    try {
      return await componentImport();
    } catch (error) {
      if (!pageHasBeenForceRefreshed) {
        // Simpan penanda agar tidak terjadi reload loop jika server benar-benar bermasalah
        window.sessionStorage.setItem('chunk_retry_refreshed', 'true');
        window.location.reload();
        return new Promise(() => {}); // Gantung promise sampai halaman selesai di-reload
      }
      // Bersihkan penanda jika sudah pernah direfresh dan tetap error
      window.sessionStorage.removeItem('chunk_retry_refreshed');
      throw error;
    }
  });
}
```
3. **Global Error Boundary Fallback:** Pasang Error Boundary khusus di level root atau layout router yang mendeteksi chunk failure dan menampilkan UI dialog ramah: *"Versi baru aplikasi telah tersedia. Silakan klik tombol di bawah untuk menyegarkan halaman."*

---

### Skenario 3.2: Role-based Protected Route Flashing & Unauthorized Data Leak
**Konteks Masalah:**  
Sebuah aplikasi portal internal B2B memiliki beberapa peran pengguna: `SUPER_ADMIN`, `FINANCE`, dan `EMPLOYEE`. Halaman `/finance/payroll` dilindungi oleh Protected Route Component. Namun, pengguna dengan role `EMPLOYEE` yang sengaja mengetik URL `/finance/payroll` melaporkan bahwa layout tabel payroll dan nama-nama pegawai sempat terlihat selama ~300ms sebelum akhirnya browser menendang (*redirect*) mereka ke halaman `/unauthorized`. Selain itu, tab Network mencatat bahwa request `GET /api/v1/payroll` tetap terkirim ke backend dan mengembalikan status 403.

**Analisis Akar Masalah:**  
1. **Flashing Visual:** Komponen Protected Route mengevaluasi hak akses secara asynchronous atau setelah child component sempat me-mount:
   ```tsx
   // Anti-pattern
   function ProtectedRoute({ children }) {
     const { user, isLoading } = useAuth();
     useEffect(() => {
       if (!isLoading && user.role !== 'FINANCE') navigate('/unauthorized');
     }, [user, isLoading]);
     return children; // Komponen anak langsung dirender sebelum useEffect dieksekusi!
   }
   ```
2. **Data Leakage:** Child component memiliki `useEffect` data fetching independen yang langsung ditembakkan pada render pertama, sebelum navigasi redirect sempat diproses oleh browser.

**Solusi Arsitektur Komprehensif:**
1. **Strict Guard Boundary sebelum Render:**
   Evaluasi otentikasi dan otorisasi harus bersifat *synchronous blocker* terhadap sub-tree anak:
```tsx
// src/routes/RoleGuard.tsx
import { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/features/auth/hooks/useAuth';

interface RoleGuardProps {
  allowedRoles: Array<'SUPER_ADMIN' | 'FINANCE' | 'EMPLOYEE'>;
  children: ReactNode;
}

export function RoleGuard({ allowedRoles, children }: RoleGuardProps) {
  const { user, status } = useAuth();
  const location = useLocation();

  if (status === 'loading') {
    return <FullScreenSkeletonLoader />;
  }

  if (status === 'unauthenticated' || !user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (!allowedRoles.includes(user.role)) {
    return <Navigate to="/unauthorized" replace />;
  }

  // Anak HANYA dirender jika seluruh validasi auth dan role terpenuhi secara pasti
  return <>{children}</>;
}
```
2. **Backend Defense-in-depth:** Frontend guard hanyalah mekanisme UX. Backend API endpoint `/api/v1/payroll` wajib memvalidasi token JWT / session cookie dan menolak request dengan status `HTTP 401/403` tanpa menyertakan payload data sensitif apapun.

---

### Skenario 3.3: Large Shared Vendor Bloat & Circular Barrel Import
**Konteks Masalah:**  
Pada tim enterprise yang mengadopsi monorepo atau shared feature folder, developer menggunakan pattern *barrel file* (`index.ts` yang mengekspor seluruh modul di dalam folder). Setelah audit performa dengan `rollup-plugin-visualizer`, tech lead menemukan bahwa chunk untuk halaman login sederhana (`Login.js`) berukuran lebih dari 1.8 MB (uncompressed). Padahal halaman login hanya berisi dua input text dan satu tombol. Analisis bundle menunjukkan bahwa icon library (`lucide-react`), chart library (`recharts`), dan utility date (`date-fns`) ikut ter-bundle ke dalam chunk login.

**Analisis Akar Masalah:**  
1. **Over-exporting pada Barrel File:** Di `src/components/index.ts`, developer mengekspor `Button`, `Input`, `DatePicker`, dan `AnalyticsChart`. Saat `Login.tsx` mengimpor `{ Button, Input } from '@/components'`, bundler mengevaluasi seluruh file yang direferensikan oleh barrel file tersebut.
2. **Broken Tree-shaking:** Komponen `AnalyticsChart` memiliki *side-effects* level modul (misalnya registrasi plugin chart di global scope), sehingga bundler tidak dapat melakukan tree-shaking dan terpaksa menyertakan seluruh bundle chart beserta dependensinya ke dalam chunk mana pun yang menyentuh `src/components`.

**Solusi Arsitektur Komprehensif:**
1. **Direct Subpath Imports atau Fine-grained Boundaries:** Hindari mega-barrel files di root shared components. Impor langsung dari modul spesifik atau gunakan package internal terisolasi:
   ```typescript
   // Buruk (memicu bundling seluruh library yang ada di index.ts)
   import { Button, Input } from '@/components';

   // Baik (tree-shaking presisi)
   import { Button } from '@/components/ui/Button';
   import { Input } from '@/components/ui/Input';
   ```
2. **Konfigurasi `sideEffects: false` pada `package.json`:** Beritahu Rollup/Webpack bahwa modul internal bebas dari side-effects global sehingga komponen yang tidak terpakai dapat dieliminasi secara total saat tree-shaking:
   ```json
   {
     "name": "ui-kit",
     "sideEffects": false
   }
   ```
3. **Lint Enforcement:** Pasang rule ESLint `no-restricted-imports` untuk melarang impor langsung dari barrel file root untuk komponen berat, dan gunakan linting arsitektur seperti `eslint-plugin-boundaries` atau `dependency-cruiser` untuk mencegah circular dependency.

---

## Bagian 4: Practical Chapter Challenge (Hands-on Implementation)

### Judul Challenge:
**"Membangun Arsitektur Router Enterprise dengan Code Splitting, Protected Guard, Lazy Loading dengan Fallback Skeleton, dan Feature-Driven Organization."**

### Spesifikasi Kebutuhan Proyek:
Anda ditugaskan merancang arsitektur rute untuk aplikasi dashboard multi-tier dengan struktur direktori Feature-driven sebagai berikut:

```text
src/
├── app/
│   ├── providers/
│   └── routes/
│       ├── AppRoutes.tsx
│       ├── guards/
│       │   └── AuthGuard.tsx
│       └── layouts/
│           ├── RootLayout.tsx
│           └── DashboardLayout.tsx
├── features/
│   ├── auth/
│   │   ├── api/
│   │   ├── components/
│   │   │   └── LoginForm.tsx
│   │   ├── hooks/
│   │   │   └── useAuth.ts
│   │   ├── routes/
│   │   │   └── LoginPage.tsx
│   │   └── index.ts
│   └── analytics/
│       ├── components/
│       │   └── HeavyChartWidget.tsx
│       ├── routes/
│       │   └── AnalyticsDashboardPage.tsx
│       └── index.ts
└── shared/
    └── components/
        └── FullPageSkeleton.tsx
```

### Instruksi Step-by-Step:

#### Langkah 1: Implementasi Lazy Loading dengan Custom Delay/Retry Wrapper
Buat helper `lazyWithFallback` yang mengimpor komponen halaman secara lazy dan menangani visual skeleton fallback saat loading.

#### Langkah 2: Implementasi `AuthGuard` dan `RootLayout`
Pastikan rute `/dashboard` dan sub-rutenya hanya bisa diakses oleh pengguna yang memiliki token valid di `useAuth`. Jika unauthenticated, redirect ke `/login` dengan menyimpan rute asal pada `location.state.from`.

#### Langkah 3: Konfigurasi Centralized Route Definition
Gunakan `createBrowserRouter` React Router v6+ dengan struktur hierarki:
- `/` -> Redirect ke `/dashboard`
- `/login` -> Public Route (Lazy loaded)
- `/dashboard` -> Protected via `AuthGuard` -> Menggunakan `DashboardLayout` dengan persistent Sidebar
  - `/dashboard/overview` -> Lazy loaded overview
  - `/dashboard/analytics` -> Lazy loaded analytics dengan child chunk terpisah untuk widget chart

### Kriteria Penerimaan (Acceptance Criteria):
1. **Bundle Isolation:** File bundle awal (*initial entry chunk*) tidak boleh memuat kode dari komponen `AnalyticsDashboardPage` maupun library chart.
2. **Zero Waterfall Auth:** Validasi otentikasi pada `AuthGuard` tidak boleh menampilkan flicker tampilan dashboard saat user unauthenticated.
3. **Smooth Transition:** Transisi navigasi antar rute dashboard mempertahankan state sidebar navigasi tanpa me-remount layout utama.
4. **Resilient Network:** Terdapat penanganan error terisolasi jika chunk lazy gagal dimuat melalui `errorElement` pada router.

---

## Bagian 5: Checklist Pemahaman Mandiri

Gunakan rubrik penilaian mandiri berikut untuk mengukur kesiapan teknis Anda sebelum melangkah ke bab berikutnya:

| No | Topik Kompetensi | Indikator Penguasaan | Status (Paham / Butuh Review) |
|---|---|---|---|
| 1 | **History API & CSR Fundamentals** | Mampu menjelaskan fungsi `pushState`, `replaceState`, dan konfigurasi rewrite Nginx `try_files` untuk mencegah error 404 pada CSR. | [ ] |
| 2 | **Dynamic Import & Suspense Boundary** | Memahami siklus hidup Promise yang dilempar oleh `React.lazy` dan bagaimana `<Suspense fallback={...}>` menangani rendering state secara deklaratif. | [ ] |
| 3 | **Nested Routing & Persistent Layouts** | Mampu menyusun hierarki route menggunakan komponen `<Outlet />` dan mengoper state layout menggunakan `useOutletContext`. | [ ] |
| 4 | **Data Loaders & Actions Architecture** | Mampu membandingkan keuntungan eliminasi network waterfalls pada Data APIs (`createBrowserRouter`) dibandingkan `useEffect` data fetching tradisional. | [ ] |
| 5 | **Vendor Chunking & Caching Strategy** | Mampu mengonfigurasi `manualChunks` pada Vite/Rollup untuk memisahkan library besar dan mengoptimalkan browser long-term caching. | [ ] |
| 6 | **Feature-driven Folder Architecture** | Memahami cara mengisolasi modul ke dalam domain slice (`src/features/*`) dengan public API boundary (`index.ts`) untuk mencegah tight coupling. | [ ] |
| 7 | **Production Stale Chunk Recovery** | Memahami penyebab error `Failed to fetch dynamically imported module` pada deployment baru dan mampu mengimplementasikan recovery strategy berbasis reload/retention. | [ ] |
| 8 | **Zero-leak Protected Routes** | Mampu mendesain Route Guard yang aman secara synchronous-first untuk mencegah kebocoran data visual dan pemanggilan API unauthorized. | [ ] |
