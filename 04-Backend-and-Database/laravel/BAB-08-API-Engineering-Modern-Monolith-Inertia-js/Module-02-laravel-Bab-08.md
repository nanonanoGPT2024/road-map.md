# Kurikulum Rekayasa Perangkat Lunak Enterprise: Laravel
## Bab 08: API Engineering & Modern Monolith (Inertia.js)
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Principal Engineer/Senior Backend Engineer diharapkan mampu:
- Menganalisis protokol internal Inertia.js (siklus *request/response*, evaluasi header HTTP, dan enkapsulasi JSON payload).
- Mengimplementasikan teknik optimasi payload tingkat lanjut menggunakan *Partial Reloads*, *Lazy Data Evaluation*, dan *Deferred Props* (Inertia v2).
- Merancang dan men-deploy arsitektur *Server-Side Rendering* (SSR) berbasis Node.js/Bun yang terisolasi dengan supervisor process daemon.
- Mengintegrasikan strategi *Asset Versioning* dan proteksi *Cache Busting* otomatis berbasis Vite manifest hash.
- Membangun arsitektur hibrida: *Modern Monolith* (Inertia.js) dan *Headless API* (Laravel Sanctum/Passport) dalam satu *codebase* terpadu tanpa duplikasi *domain logic*.
- Menyelesaikan permasalahan *concurrency*, *state leakage*, dan penanganan *file upload* skala besar (S3 direct/multipart) dalam ekosistem Inertia.

---

### 2. Prerequisites
- Pemahaman mendalam mengenai siklus hidup Laravel 11.x (*Service Container, Middleware Pipeline, HTTP Kernel*).
- Pemahaman solid tentang SPA (*Single Page Application*) rendering, DOM Hydration, dan *Client-side Routing*.
- Penguasaan TypeScript dan salah satu pustaka UI modern: Vue 3 (Composition API) atau React 18+.
- Pemahaman networking: HTTP/2, TLS termination, Reverse Proxy (Nginx/Traefik), dan process managers (systemd/Supervisor).

---

### 3. Concept & Internal Architecture (Mendalam)

Inertia.js bukanlah *framework* frontend maupun backend independen; Inertia adalah sebuah **spesifikasi protokol komunikasi** yang menjembatani server-side framework (Laravel) dengan reactive client framework (Vue/React/Svelte) tanpa memerlukan REST atau GraphQL API endpoint secara eksplisit.

#### 3.1 Protokol Internal Inertia.js
Siklus komunikasi Inertia diatur oleh header HTTP kustom:
1. **Initial Page Visit**:
   - Klien mengirimkan request standar `GET /orders/100` (`Accept: text/html`).
   - Laravel merender view root blade (misal: `app.blade.php`) yang memuat tag HTML:
     ```html
     <div id="app" data-page='{"component":"Orders/Show","props":{"order":{...}},"url":"/orders/100","version":"c8b4..."}'></div>
     ```
   - Client bundle mengeksekusi `createInertiaApp()`, mem-parsing atribut `data-page`, me-mount komponen target, dan melakukan inisiasi Virtual DOM.

2. **Subsequent Inertia Visit**:
   - Ketika pengguna mengklik link atau mentrigger action, runtime Inertia mengintersepsi event dan mengirimkan XHR/Fetch request dengan header:
     - `X-Inertia: true`
     - `X-Inertia-Version: <hash>`
   - Middleware `HandleInertiaRequests` mendeteksi header `X-Inertia`.
   - Controller mengeksekusi `Inertia::render('Orders/Show', [...])`.
   - Laravel memotong render Blade dan mengembalikan response JSON murni (HTTP 200) dengan header `X-Inertia: true`:
     ```json
     {
       "component": "Orders/Show",
       "props": { "order": { "id": 100, "status": "COMPLETED" } },
       "url": "/orders/100",
       "version": "c8b4d8a1e2f3..."
     }
     ```
   - Client-side router Inertia menerima JSON tersebut, menukar komponen aktif di DOM, memperbarui state via `history.pushState`, dan tidak memicu *full page reload*.

#### 3.2 Siklus Evaluasi Data (Lazy & Deferred Execution)
Secara default, seluruh array props dalam `Inertia::render()` dievaluasi oleh PHP sebelum serialisasi JSON:
- **Immediate Props**: Dievaluasi pada setiap request.
- **Lazy Props (`Inertia::lazy()`)**: Dibungkus dalam closure. Prop ini **diabaikan** pada *initial load* dan hanya dieksekusi jika diminta secara spesifik melalui header `X-Inertia-Partial-Data`.
- **Deferred Props (`Inertia::defer()`)**: Diperkenalkan pada Inertia v2. Server langsung mengembalikan payload awal tanpa prop ini, lalu runtime client secara paralel menembak request susulan di background untuk meresolusi prop tersebut.

#### 3.3 Arsitektur Server-Side Rendering (SSR)
Pada mode SSR:
- Node.js runtime (atau Bun) dijalankan secara lokal di port privat (contoh: `127.0.0.1:13714`).
- Middleware Laravel mengintersepsi request pertama dari bot/crawler atau end-user.
- Laravel mengirimkan payload JSON halaman ke daemon SSR lokal via cURL/Socket HTTP request.
- Daemon SSR mengeksekusi JavaScript bundle (dihasilkan oleh `vite build --ssr`), merender komponen ke string HTML mentah, dan mengembalikannya ke Laravel.
- Laravel menyisipkan string HTML tersebut ke dalam root element `<div id="app">...</div>` sehingga klien menerima DOM utuh (SEO ready & First Contentful Paint optimal).

```
                      ARSHITEKTUR INERTIA SSR RUNTIME
                      
+------------------+             +--------------------+
|  Browser / Client|             | Nginx / Edge Proxy |
+--------+---------+             +---------+----------+
         |                                 |
         | HTTP GET /dashboard             |
         +-------------------------------->|
                                           | Forward to PHP-FPM
                                           v
                             +-------------+------------+
                             |   Laravel Application    |
                             | (HandleInertiaRequests)  |
                             +-------------+------------+
                                           |
                                  Is Initial Visit &
                                  SSR Enabled?
                                           |
                     +---------------------+---------------------+
                     | YES                                       | NO
                     v                                           v
       +-------------+------------+               +--------------+-------------+
       | HTTP POST to SSR Daemon  |               | Return Base Blade Template |
       | http://127.0.0.1:13714   |               | with data-page attributes  |
       +-------------+------------+               +--------------+-------------+
                     |                                           |
                     v                                           |
       +-------------+------------+                              |
       |  Node.js / Bun Daemon    |                              |
       |  (ssr.js via Supervisor) |                              |
       +-------------+------------+                              |
                     |                                           |
                     | Render Vue/React to String                |
                     v                                           |
       +-------------+------------+                              |
       | Return { head, body }    |                              |
       +-------------+------------+                              |
                     |                                           |
                     +---------------------+---------------------+
                                           |
                                           v
                               +-----------+-----------+
                               | Response (HTML/JSON)  |
                               +-----------+-----------+
                                           |
         <---------------------------------+
         | Klien melakukan Hydration 
```

---

### 4. Why & What

| Dimensi | Traditional SPA (React/Vue + API) | Inertia.js Monolith | Server-Rendered (Blade/Livewire) |
| :--- | :--- | :--- | :--- |
| **API Boundary** | Ekstensif (Endpoint, Resource, DTO, Client SDK, Auth) | Nol (Langsung memetakan state controller ke props) | Nol (State server disinkronisasikan via DOM diffing) |
| **Client Routing** | Client-side (React-Router/Vue-Router) | Inertia Protocol Interceptor | Server-side Navigation / Wire Morphing |
| **Type Safety** | Membutuhkan generator OpenAPI/tRPC | End-to-end via Wayfind / Inertia TypeScript types | Terbatas pada Server Blade context |
| **Initial Latency**| Tinggi (Multi-roundtrip: HTML -> JS -> API Data) | Rendah (HTML langsung memuat payload data-page) | Terendah (HTML komplit langsung disajikan) |
| **Maintenance Cost**| Sangat Tinggi (Dua pipeline deployment terpisah) | Rendah (Satu repository, satu pipeline deployment) | Rendah (Satu ekosistem bahasa PHP) |

**Kapan Menggunakan Arsitektur Ini?**
- Sistem Enterprise B2B SaaS dengan interaksi antarmuka kompleks yang membutuhkan UI reactivity tingkat tinggi.
- Tim yang ingin mempertahankan kecepatan pengembangan Laravel tanpa harus membangun overhead API REST/GraphQL internal untuk konsumsi aplikasi web sendiri.

**Kapan Menghindari Arsitektur Ini?**
- Sistem yang murni dikonsumsi oleh ribuan integrasi pihak ketiga (Third-party public API).
- Aplikasi yang mengharuskan ekosistem micro-frontend independen dengan deployment lifecycle terisolasi antar departemen.

---

### 5. How (Workflow Detail)

1. **Asset Version Fingerprinting**:
   Setiap build frontend via Vite menghasilkan manifest file. Nilai hash dari manifest digunakan sebagai `Inertia::version()`.
2. **Detection of Outdated Assets**:
   Ketika user berada di halaman web dan developer melakukan deploy versi baru, request Inertia berikutnya mengirimkan header `X-Inertia-Version: old_hash`.
3. **HTTP 409 Conflict Handling**:
   Middleware `HandleInertiaRequests` mendeteksi disparitas hash. Laravel secara otomatis membatalkan eksekusi controller dan mengembalikan response status `HTTP 409 Conflict` dengan header `X-Inertia-Location: /current-url`.
4. **Hard Refresh**:
   Client Inertia menangkap status 409 dan mengeksekusi `window.location.href = response.headers['x-inertia-location']`. Ini memicu browser melakukan download aset JS/CSS baru secara deterministik tanpa crash di sisi klien.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Pengiriman Kontainer & Dokumen Manifest
Bayangkan SPA Tradisional seperti **Membeli Tanah Kosong lalu Mengimpor Rumah Cetak**:
Anda mendapatkan tanah (HTML kosong), lalu mendatangkan kontraktor (JavaScript runtime), kemudian kontraktor menelepon gudang material berkali-kali untuk memesan semen, pasir, dan bata (Fetch REST API) sebelum rumah bisa dihuni.

Inertia.js seperti **Pengiriman Rumah Kontainer Modular Siap Huni**:
Truk pengangkut datang membawa struktur kontainer lengkap yang sudah terisi interior dan perabotan (HTML + data-page JSON). Ketika Anda ingin mengubah ruang tamu menjadi ruang kerja (Subsequent Visit), Anda tidak perlu merobohkan seluruh rumah; Anda hanya memesan set modular meja kantor, dan kru langsung menukarnya di tempat secara instan tanpa memutus aliran listrik.

```
ALUR VALIDASI VERSI ASSET (CONFLICT DETECTION)

Browser                           Laravel Middleware (HandleInertiaRequests)
   |                                                    |
   |--- GET /billing (X-Inertia-Version: v1) ---------->|
   |                                                    | Compare: v1 == v2?
   |                                                    | Result: FALSE (Deploy Baru)
   |                                                    |
   |<-- 409 Conflict (X-Inertia-Location: /billing) ----|
   |                                                    |
[Hard Refresh Otomatis: window.location.href]           |
   |                                                    |
   |--- GET /billing (Browser standard HTTP GET) ------>|
   |                                                    | Process standard request
   |<-- 200 OK (HTML baru memuat aset JS v2) -----------|
```

---

### 7. Implementation: Simple vs Production Practical Example

#### 7.1 Simple Example (Dasar Inertia Controller)
```php
<?php

namespace App\Http\Controllers;

use App\Models\User;
use Inertia\Inertia;
use Inertia\Response;

class UserController extends Controller
{
    public function index(): Response
    {
        return Inertia::render('Users/Index', [
            'users' => User::paginate(10),
        ]);
    }
}
```

#### 7.2 Practical Example (Production-Grade Architecture)

##### Domain Action: Orchestrating Data & Partial Reloads
```php
<?php

declare(strict_types=1);

namespace App\Http\Controllers\Enterprise;

use App\Http\Controllers\Controller;
use App\Models\Order;
use App\Models\AuditLog;
use Illuminate\Http\Request;
use Inertia\Inertia;
use Inertia\Response;
use Illuminate\Support\Facades\Gate;

final class OrderManagementController extends Controller
{
    public function show(Request $request, string $uuid): Response
    {
        $order = Order::with(['items.product', 'customer'])
            ->where('uuid', $uuid)
            ->firstOrFail();

        Gate::authorize('view', $order);

        return Inertia::render('Orders/Show', [
            // Core Prop: Selalu dimuat pada initial visit
            'order' => [
                'id' => $order->id,
                'uuid' => $order->uuid,
                'status' => $order->status->value,
                'total_amount' => $order->total_amount->getAmount(),
                'currency' => $order->total_amount->getCurrency()->getCurrencyCode(),
                'created_at' => $order->created_at->toIso8601String(),
                'customer' => [
                    'name' => $order->customer->name,
                    'email' => $order->customer->email,
                ],
                'items' => $order->items->map(fn ($item) => [
                    'id' => $item->id,
                    'product_name' => $item->product->name,
                    'quantity' => $item->quantity,
                    'unit_price' => $item->unit_price,
                ]),
            ],

            // Lazy Prop: Hanya dievaluasi jika frontend memintanya secara eksplisit
            // Mencegah query N+1 dan payload overhead pada initial page render
            'auditLogs' => Inertia::lazy(fn () => 
                AuditLog::where('auditable_type', Order::class)
                    ->where('auditable_id', $order->id)
                    ->latest()
                    ->limit(50)
                    ->get()
                    ->map(fn ($log) => [
                        'action' => $log->action,
                        'actor' => $log->causer?->name ?? 'System',
                        'timestamp' => $log->created_at->toIso8601String(),
                        'payload' => $log->properties,
                    ])
            ),

            // Deferred Prop (Inertia v2): Browser merender halaman terlebih dahulu,
            // lalu prop ini di-fetch secara asynchronous via background request
            'analyticsSummary' => Inertia::defer(fn () => [
                'customer_lifetime_value' => $order->customer->calculateLTV(),
                'churn_risk_score' => $order->customer->getChurnRisk(),
            ]),
        ]);
    }
}
```

##### Production Middleware Configuration
```php
<?php

declare(strict_types=1);

namespace App\Http\Middleware;

use Illuminate\Http\Request;
use Inertia\Middleware;
use Tighten\Ziggy\Ziggy;

final class HandleInertiaRequests extends Middleware
{
    protected $rootView = 'app';

    public function version(Request $request): ?string
    {
        // Hash Vite manifest untuk cache-busting otomatis
        $manifestPath = public_path('build/manifest.json');
        
        return file_exists($manifestPath) 
            ? hash_file('xxh128', $manifestPath) 
            : parent::version($request);
    }

    public function share(Request $request): array
    {
        return array_merge(parent::share($request), [
            'auth' => [
                'user' => fn () => $request->user() ? [
                    'id' => $request->user()->id,
                    'name' => $request->user()->name,
                    'email' => $request->user()->email,
                    'roles' => $request->user()->getRoleNames(),
                    'permissions' => $request->user()->getAllPermissions()->pluck('name'),
                ] : null,
            ],
            'flash' => [
                'success' => fn () => $request->session()->get('success'),
                'error' => fn () => $request->session()->get('error'),
                'token' => fn () => $request->session()->get('token'),
            ],
            // Inject dynamic routing schema secara efisien
            'ziggy' => fn () => array_merge((new Ziggy)->toArray(), [
                'location' => $request->url(),
            ]),
        ]);
    }
}
```

##### TypeScript Client Component (Vue 3 Composition API)
```vue
<script setup lang="ts">
import { ref } from 'vue';
import { router } from '@inertiajs/vue3';
import AppLayout from '@/Layouts/AppLayout.vue';

interface OrderItem {
  id: number;
  product_name: string;
  quantity: number;
  unit_price: number;
}

interface OrderProps {
  order: {
    id: number;
    uuid: string;
    status: string;
    total_amount: number;
    currency: string;
    items: OrderItem[];
  };
  auditLogs?: Array<{
    action: string;
    actor: string;
    timestamp: string;
    payload: Record<string, unknown>;
  }>;
  analyticsSummary?: {
    customer_lifetime_value: number;
    churn_risk_score: number;
  };
}

const props = defineProps<OrderProps>();
const isLoadingAudit = ref<boolean>(false);

const fetchAuditLogs = (): void => {
  isLoadingAudit.value = true;
  router.reload({
    only: ['auditLogs'],
    onFinish: () => {
      isLoadingAudit.value = false;
    },
  });
};
</script>

<template>
  <AppLayout :title="`Order #${order.uuid}`">
    <div class="p-8 max-w-7xl mx-auto space-y-6">
      <div class="bg-white rounded-xl shadow p-6 border border-slate-100">
        <h1 class="text-2xl font-bold">Order Details: {{ order.uuid }}</h1>
        <p class="text-slate-500">Status: {{ order.status }}</p>
        <p class="text-slate-900 font-semibold mt-2">
          Total: {{ order.currency }} {{ (order.total_amount / 100).toFixed(2) }}
        </p>
      </div>

      <!-- Deferred Data Slot -->
      <div class="bg-slate-50 rounded-xl p-6 border border-slate-200">
        <h2 class="text-lg font-semibold">Customer Metrics</h2>
        <div v-if="analyticsSummary" class="grid grid-cols-2 gap-4 mt-4">
          <div>LTV: ${{ analyticsSummary.customer_lifetime_value }}</div>
          <div>Risk Score: {{ analyticsSummary.churn_risk_score }}%</div>
        </div>
        <div v-else class="animate-pulse flex space-x-4 mt-4">
          <div class="h-4 bg-slate-300 rounded w-1/4"></div>
          <div class="h-4 bg-slate-300 rounded w-1/4"></div>
        </div>
      </div>

      <!-- Partial Reload Section -->
      <div class="bg-white rounded-xl shadow p-6 border border-slate-100">
        <div class="flex justify-between items-center mb-4">
          <h2 class="text-lg font-semibold">Audit Logs</h2>
          <button
            v-if="!auditLogs"
            @click="fetchAuditLogs"
            :disabled="isLoadingAudit"
            class="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
          >
            {{ isLoadingAudit ? 'Fetching...' : 'Load Audit Trail' }}
          </button>
        </div>

        <ul v-if="auditLogs" class="divide-y divide-slate-100">
          <li v-for="(log, idx) in auditLogs" :key="idx" class="py-2 text-sm">
            <span class="font-medium">{{ log.actor }}</span>: {{ log.action }}
            <span class="text-slate-400 text-xs ml-2">{{ log.timestamp }}</span>
          </li>
        </ul>
      </div>
    </div>
  </AppLayout>
</template>
```

---

### 8. Real-World Case Study (Enterprise Scale)

#### Kasus: Fintech Core Dashboard Migration (OmniPay Financial)
- **Kondisi Awal**: 
  - OmniPay menggunakan stack terpisah: Laravel REST API + React SPA (Create React App/Vite).
  - Terdapat 120+ endpoint API internal hanya untuk rendering UI dashboard admin.
  - Sering terjadi desinkronisasi kontrak OpenAPI schema, serialisasi JSON redundant, dan overhead autentikasi Bearer Token (Sanctum stateful mismatch).
  - *Initial Load Time* (TTI) mencapai 4.2 detik karena eksekusi CSS, JS, lalu cascade 5-7 HTTP requests untuk data agregasi.

- **Implementasi Solusi**:
  1. **Monolith Consolidation**: Menggabungkan repository frontend ke Laravel 11 dengan Inertia.js (React 18 + TypeScript).
  2. **Inertia SSR Engine**: Mengimplementasikan daemon SSR dengan Bun di port 13714 di belakang Nginx reverse proxy.
  3. **Data Splitting**:
     - Data profil user, limit saldo, dan notifikasi dialirkan melalui `HandleInertiaRequests::share()`.
     - Data tabel ledger transaksi berat diisolasi menggunakan `Inertia::lazy()`.
     - Metrik chart transaksi bulanan menggunakan `Inertia::defer()`.
  4. **Optimistic UI Form Handling**:
     Menggunakan `useForm` Inertia dengan preserving state untuk mencegah freeze UI pada interaksi approval massal.

- **Hasil Metrik Produksi**:
  - **First Contentful Paint (FCP)**: Turun dari 2.8s menjadi **0.6s** (didukung oleh SSR + Zero API Roundtrips).
  - **Time to Interactive (TTI)**: Turun dari 4.2s ke **1.1s**.
  - **Bandwidth Server**: Payload data berkurang hingga **62%** karena eliminasi duplikasi response meta API dan implementasi *Partial Reloads*.
  - **Lines of Code (LoC)**: Reduksi 35.000 baris kode boilerplate (penghapusan Axios clients, Redux thunks, dan redundansi Form Request DTOs).

---

### 9. Trade-offs

| Aspek Arsitektur | Keuntungan | Kerugian / Risiko | Strategi Mitigasi |
| :--- | :--- | :--- | :--- |
| **Monolithic Coupling** | Produktivitas tinggi, tidak ada kontrak API formal yang harus di-maintain. | Frontend dan backend harus di-deploy secara serentak. | Gunakan CI/CD atomik dengan zero-downtime deployment (Laravel Envoyer / Deployer). |
| **Server Memory Footprint (SSR)** | SEO optimal dan FCP instan untuk rendering pertama. | Node/Bun daemon mengonsumsi RAM tambahan (~150MB per thread worker). | Batasi worker SSR via Supervisor, isolasi daemon di cluster container privat. |
| **Initial Request Payload** | Tidak ada cascading roundtrips setelah download HTML. | Ukuran file HTML pertama lebih besar karena memuat JSON `data-page`. | Gunakan `Inertia::lazy()` dan `Inertia::defer()` untuk payload non-kritis. |
| **Cross-Platform Reusability** | Tidak ada overhead mapping DTO untuk web application. | Endpoint Inertia tidak bisa dikonsumsi langsung oleh native Mobile App (iOS/Android). | Terapkan arsitektur hibrida: Controller memanggil *Action Classes/Domain Services* yang dipakai bersama oleh API & Inertia. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Masalah Memory Leak pada Inertia SSR Process Daemon
- **Gejala**: RAM server membengkak secara eksponensial setelah runtime SSR berjalan beberapa jam, hingga dihentikan oleh OOM (*Out Of Memory*) killer.
- **Penyebab**: Global state pollution di script `ssr.ts`/`ssr.js`. Penggunaan single instance variable di luar scope `createInertiaApp` me-retain memory antar user requests.
- **Solusi**: Pastikan instance app dan state stores dibuat *fresh* di setiap eksekusi render request:
  ```typescript
  // SALAH (Global leak)
  const pinia = createPinia();
  export default function render(page) {
    return createInertiaApp({ /* ... */ plugins: [pinia] });
  }

  // BENAR (Per-request isolation)
  export default function render(page) {
    const pinia = createPinia();
    return createInertiaApp({ /* ... */ plugins: [pinia] });
  }
  ```

#### 2. Flash State Overwrites pada Concurrent Request
- **Gejala**: Pesan notifikasi flash session hilang mendadak atau muncul pada browser tab yang salah saat user membuka beberapa tab bersamaan.
- **Penyebab**: Penggunaan standard session flash Laravel `session()->flash()` pada background partial reloads yang tereksekusi paralel.
- **Solusi**: Konfigurasikan response custom header atau kembalikan response Inertia tanpa merusak session bag, atau gunakan flash message berbasis event/UUID di level frontend state.

#### 3. Kehilangan Scroll Position pada Navigasi Dinamis
- **Gejala**: Pengguna melakukan click load-more atau filter tabel, namun viewport melompat kembali ke paling atas halaman.
- **Solusi**: Atur router visit secara eksplisit:
  ```typescript
  router.visit('/transactions', {
    preserveScroll: true,
    preserveState: true,
    only: ['transactions'],
  });
  ```

---

### 11. Best Practices (Production Checklist)

- [ ] **Asset Hashing**: Implementasikan hashing manifest di `HandleInertiaRequests::version()` untuk auto-conflict detection (HTTP 409).
- [ ] **Data Serialization**: Jangan melewatkan model Eloquent mentah ke `Inertia::render()`. Gunakan JsonResource atau manual mapping array untuk mencegah kebocoran atribut sensitif (`password_hash`, `two_factor_secret`).
- [ ] **Shared Data Minimization**: Jaga agar `HandleInertiaRequests::share()` tetap seringan mungkin (< 5KB). Shared data dievaluasi dan dikirim pada setiap request.
- [ ] **SSR Daemon Supervisor**: Pastikan daemon SSR di-monitor oleh Supervisor dengan parameter `autostart=true`, `autorestart=true`, dan batasan `max_memory_restart`.
- [ ] **Type Safety Pipeline**: Integrasikan tools generator deklarasi TypeScript (seperti Laravel Precision atau Wayfind) di pipeline CI untuk auto-generate tipe dari Controller ke Komponen Frontend.
- [ ] **Direct S3 Uploads**: Untuk file berukuran > 10MB, hindari multipart form upload melalui middleware Inertia. Gunakan presigned S3 URLs untuk upload langsung dari browser, lalu kirim metadata S3 ke Inertia controller.

---

### 12. Hands-on Practice

Buat dan simpan seluruh berkas berikut dalam path: `hands-on/m02/`

#### Langkah 1: Inisialisasi Service Layer & Controller
Simpan di `hands-on/m02/app/Http/Controllers/ProductCatalogController.php`:
```php
<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Models\Product;
use Illuminate\Http\Request;
use Inertia\Inertia;
use Inertia\Response;

final class ProductCatalogController extends Controller
{
    public function index(Request $request): Response
    {
        $category = $request->string('category')->toString();

        return Inertia::render('Catalog/Index', [
            'filters' => [
                'category' => $category,
                'search' => $request->string('search')->toString(),
            ],
            // Core data: Paginasi produk dasar
            'products' => Product::query()
                ->when($category, fn ($q) => $q->where('category', $category))
                ->select(['id', 'sku', 'name', 'price', 'category'])
                ->paginate(15)
                ->withQueryString(),

            // Lazy Prop: Hanya dimuat saat user membuka panel statistik
            'metrics' => Inertia::lazy(fn () => [
                'total_inventory_value' => Product::sum('price'),
                'low_stock_count' => Product::where('stock', '<', 5)->count(),
            ]),
        ]);
    }
}
```

#### Langkah 2: Konfigurasi Entry Point SSR
Simpan di `hands-on/m02/resources/js/ssr.ts`:
```typescript
import { createSSRApp, h, DefineComponent } from 'vue';
import { renderToString } from '@vue/server-renderer';
import { createInertiaApp } from '@inertiajs/vue3';
import createServer from '@inertiajs/vue3/server';
import { resolvePageComponent } from 'laravel-vite-plugin/inertia-helpers';

createServer((page) =>
  createInertiaApp({
    page,
    render: renderToString,
    resolve: (name) =>
      resolvePageComponent(
        `./Pages/${name}.vue`,
        import.meta.glob<DefineComponent>('./Pages/**/*.vue')
      ),
    setup({ App, props, plugin }) {
      return createSSRApp({ render: () => h(App, props) }).use(plugin);
    },
  })
);
```

#### Langkah 3: Konfigurasi Supervisor Daemon
Simpan konfigurasi proses di `hands-on/m02/supervisor/inertia-ssr.conf`:
```ini
[program:inertia-ssr]
directory=/var/www/enterprise-app
command=node resources/js/ssr.js
autostart=true
autorestart=true
user=www-data
redirect_stderr=true
stdout_logfile=/var/www/enterprise-app/storage/logs/inertia-ssr.log
stopwaitsecs=10
environment=NODE_ENV="production"
```

---

### 13. Exercises

#### Level Easy
1. Buat controller `SettingController` yang mengembalikan shared props global `theme_color` dan `timezone` hanya untuk pengguna terotentikasi via `HandleInertiaRequests`.
2. Implementasikan partial reload sederhana pada tombol "Refresh Status" yang hanya meminta key `order_status` tanpa merefresh data master customer.

#### Level Medium
1. Bangun arsitektur modal/dialog URL-driven menggunakan Inertia. Saat user mengklik list item, URL browser berubah menjadi `/orders/{id}/details`, membuka dialog modal di atas layar katalog tanpa kehilangan pagination & scroll state dari parent view.
2. Implementasikan pipeline upload file massal (CSV Import): gunakan `useForm` dari Inertia, tangkap progress event (`onProgress`), dan implementasikan abort controller saat user menekan tombol "Cancel".

#### Level Hard
1. Rancang arsitektur enkripsi *client-history state* untuk dashboard perbankan. Pastikan data sensitif yang tersimpan di `window.history.state` milik browser dienkripsi secara lokal menggunakan Web Cryptography API sebelum ditinggalkan oleh navigasi Inertia, untuk mencegah kebocoran data saat tombol "Back" browser ditekan pada perangkat publik.

---

### 14. Challenges

Implementasikan sistem **Real-Time Collaborative Monolith**:
- **Deskripsi Kasus**: Anda memegang sistem ERP manufaktur di mana beberapa operator admin memproses purchasing orders (PO) yang sama.
- **Syarat Desain**:
  1. Integrasikan Laravel Reverb (WebSocket) dengan Inertia.js.
  2. Ketika Operator A melakukan update terhadap sebuah record PO di halaman detail, Operator B yang sedang membuka halaman yang sama harus menerima sinyal broadcast WebSocket.
  3. Alih-alih melakukan *full page reload*, client harus mengeksekusi *Partial Reload* selektif menggunakan router Inertia (`preserveScroll: true`, `preserveState: true`) hanya untuk keys item yang berubah.
  4. Tangani skenario *Race Condition*: Jika Operator B sedang mengetik input komentar di form yang sama, state lokal input tersebut tidak boleh ter-reset ketika background partial reload selesai.
  5. Sediakan skema fail-safe jika server WebSocket down (graceful degradation ke manual polling via `Inertia::lazy`).

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Pertanyaan)
1. **Apa fungsi utama dari header HTTP `X-Inertia: true`?**
   - A. Mengindikasikan browser untuk memvalidasi CORS token.
   - B. Memberitahu Laravel bahwa request dikirim melalui client-side router Inertia, sehingga response harus berupa JSON komponen, bukan dokumen HTML blade lengkap.
   - C. Menginstruksikan Nginx untuk mengaktifkan kompresi Gzip pada assets JS.
   - D. Menyalakan bypass CSRF verification untuk request asinkron.
   *(Jawaban: B)*

2. **Kapan response HTTP `409 Conflict` dilempar oleh Laravel Inertia middleware?**
   - A. Ketika dua user mengupdate record database pada mikrodetik yang sama.
   - B. Ketika format JSON request tidak valid.
   - C. Ketika hash aset frontend di client (`X-Inertia-Version`) berbeda dengan hash manifest di server.
   - D. Ketika autentikasi session cookie expired.
   *(Jawaban: C)*

3. **Bagaimana sifat evaluasi data dari method `Inertia::lazy()`?**
   - A. Dijalankan di background thread menggunakan Laravel Queue worker.
   - B. Hanya dievaluasi jika secara eksplisit dimasukkan ke dalam query `only` pada partial reload request.
   - C. Disimpan permanen di Redis memory cache server.
   - D. Dieksekusi seketika saat controller class di-instansiasi.
   *(Jawaban: B)*

4. **Di mana root element DOM tempat payload Inertia awal disuntikkan secara standar?**
   - A. `<meta name="inertia-payload">`
   - B. LocalStorage browser
   - C. Atribut `data-page` pada elemen HTML `<div id="app"></div>`
   - D. Header HTTP `Authorization`
   *(Jawaban: C)*

5. **Apa fungsi flag `preserveState: true` pada pemanggilan router Inertia?**
   - A. Menjaga koneksi database MySQL tetap persistent.
   - B. Mencegah komponen frontend me-reset state lokal (seperti form inputs & modal visibility) saat data baru diterima dari server.
   - C. Memaksa server mempertahankan cache session selama 24 jam.
   - D. Menyimpan response ke dalam IndexedDB klien.
   *(Jawaban: B)*

#### Intermediate (5 Pertanyaan)
6. **Mengapa menaruh query database berukuran besar langsung di dalam method `share()` pada `HandleInertiaRequests` merupakan anti-pattern?**
   - A. Karena method `share()` dieksekusi pada setiap request (termasuk partial reloads), yang akan memicu overhead eksekusi query redundant secara massal.
   - B. Karena method `share()` tidak mendukung eksekusi kode asynchronous.
   - C. Karena data di dalam `share()` tidak di-enkripsi oleh Laravel.
   - D. Karena `share()` hanya bisa menerima tipe data string primitif.
   *(Jawaban: A)*

7. **Bagaimana cara kerja Inertia v2 `Deferred Props` secara arsitektural?**
   - A. Server menunda response HTTP utama selama 5 detik hingga background job selesai.
   - B. Server merespon request awal tanpa prop tersebut, kemudian client runtime secara otomatis memicu request sekunder terpisah untuk mengambil data yang di-defer.
   - C. Browser mengompilasi kode PHP menjadi WebAssembly di sisi client.
   - D. Data di-stream menggunakan Server-Sent Events (SSE) dalam satu HTTP connection.
   *(Jawaban: B)*

8. **Dalam arsitektur SSR Inertia, apa tanggung jawab daemon Node.js/Bun yang berjalan di background?**
   - A. Menggantikan tugas Nginx sebagai static file server.
   - B. Melakukan query langsung ke database MySQL/PostgreSQL.
   - C. Mengeksekusi bundle JavaScript frontend untuk merender komponen menjadi representasi string HTML sebelum dikirimkan ke client.
   - D. Melakukan validasi autentikasi password user.
   *(Jawaban: C)*

9. **Apa konsekuensi dari tidak mengembalikan closure (`fn () => ...`) pada value array di `HandleInertiaRequests::share()`?**
   - A. Data tersebut akan otomatis terkena sanitasi HTML strip tags.
   - B. Expression akan langsung dievaluasi seketika pada siklus hidup request sekalipun request tersebut tidak membutuhkannya, menghilangkan manfaat lazy-loading.
   - C. Menghasilkan fatal error `TypeMismatchException`.
   - D. Mengakibatkan memory leak pada PHP-FPM pool.
   *(Jawaban: B)*

10. **Bagaimana cara mengunggah file tanpa memicu encoding form multipart standar yang memblokir streaming payload besar di Inertia?**
    - A. Mengonversi seluruh file menjadi base64 string di dalam form JSON payload.
    - B. Meminta Presigned URL dari Laravel backend ke storage bucket (misal: S3), lalu melakukan upload langsung via `fetch`/`axios` dari browser ke storage, kemudian mem-passing file ID ke Inertia form action.
    - C. Membagi file menjadi 100 props teks berbeda di Vue/React.
    - D. Mematikan proteksi CSRF di middleware web.
    *(Jawaban: B)*

#### Skenario Kasus Produksi (3 Pertanyaan)

11. **Skenario Kasus 1**:
    Sebuah aplikasi FinTech mengalami insiden di mana ketika developer merilis patch darurat JS (deploy versi v1.0.1), pengguna yang sedang mengisi form transaksi 20-field mendadak mengalami reset form dan layar me-reload sendiri saat mereka mengklik submit.
    *Pertanyaan*: Apa konfigurasi Inertia yang terpicu, dan bagaimana cara memitigasi agar user tidak kehilangan input data saat versi asset berubah di tengah sesi pengisian form?
    - **Solusi Arsitektural**: Terjadi *HTTP 409 Conflict* karena mismatch version hash. Mitigasi: Simpan input state ke `localStorage` melalui plugin form auto-save di frontend, atau tangani exception router visit error secara global: sebelum me-reload halaman akibat status 409, simpan uncommitted state ke SessionStorage dan lakukan re-hydration setelah window reload selesai.

12. **Skenario Kasus 2**:
    Pada endpoint katalog produk e-commerce berskala 50.000 SKU, initial visit memakan waktu TTFB (Time to First Byte) hingga 1.8 detik. Analisis profiler menunjukkan bahwa ada 3 relasi Eloquent yang dimuat untuk menghitung filter facet (daftar brand, rentang harga, dan kategori pohon nested) yang dieksekusi di root controller.
    *Pertanyaan*: Bagaimana Anda merefaktor struktur response Inertia untuk memangkas TTFB hingga di bawah 300ms tanpa merusak UX antarmuka?
    - **Solusi Arsitektural**: Ubah relasi penghitungan facet filter menjadi `Inertia::defer()`. Controller hanya merender produk esensial (15 item pertama) pada initial response HTML. Begitu komponen katalog ter-mount di browser, runtime client akan menarik data facet filter di background secara paralel, sehingga browser menampilkan layout utama secara instan.

13. **Skenario Kasus 3**:
    Cluster aplikasi Anda berada di balik AWS ALB (Application Load Balancer) dengan auto-scaling group (ASG) 2 hingga 8 instance. Ketika fitur SSR diaktifkan, load average server melonjak 100% CPU usage dan banyak request SSR gagal (*cURL timeout 7 to 127.0.0.1:13714*).
    *Pertanyaan*: Di mana letak bottleneck arsitekturalnya dan bagaimana blueprint solusinya?
    - **Solusi Arsitektural**: Daemon SSR (Node.js) bersifat single-threaded dan tidak mampu mengimbangi concurrency tinggi dari pool PHP-FPM yang memiliki ratusan worker thread. Solusi:
      1. Jalankan SSR daemon dengan cluster mode (menggunakan PM2 / Bun clustered runtime) dengan jumlah worker proporsional terhadap CPU core.
      2. Terapkan fallback catch block di Laravel: jika cURL request ke SSR daemon mengalami timeout (> 500ms), *gracefully fallback* ke CSR (render template blade standar dengan `data-page`) sehingga user tetap mendapatkan response meski tanpa pre-rendered HTML.
      3. Pasang reverse-proxy micro-caching (Nginx FastCGI cache / Redis) untuk menyimpan rendered HTML halaman guest publik selama beberapa detik.

---

### 16. Summary

- Protokol Inertia.js menghilangkan abstraksi REST API layer untuk internal web app dengan mempertahankan kesederhanaan *Monolith* dan reaktivitas *SPA*.
- Mekanisme **Asset Versioning** menjamin klien tidak pernah menjalankan bundle JS yang usang (*outdated bundle state*) di lingkungan produksi melalui siklus proteksi status **HTTP 409 Conflict**.
- Optimasi performa tingkat tinggi pada aplikasi enterprise berskala besar bertumpu pada isolasi evaluasi data:
  - **Core Props**: Untuk data visual viewport utama.
  - **Lazy Props**: Menghindari eksekusi database berat pada initial visit, dimuat *on-demand*.
  - **Deferred Props**: Mengoptimalkan TTFB dengan memecah rendering synchronous menjadi async streams.
- Arsitektur **Server-Side Rendering (SSR)** Inertia memisahkan rendering worker ke background runtime (Node/Bun) yang dikelola oleh process supervisor, memberikan skor SEO optimal dan First Contentful Paint yang instan.
- Penerapan pemisahan tanggung jawab yang disiplin (domain logic pada *Actions/Services*, penyajian data via *Data Transfer Objects/Resources*) memungkinkan ekosistem Laravel melayani aplikasi modern monolitik (Inertia) dan public client (Native Mobile/3rd Party) secara harmonis dalam satu arsitektur terintegrasi.