# Modul Pembelajaran: Laravel Advanced Ecosystem

---

## 01: Identitas Modul

* **Kode Modul**: `LAR-ENG-08-01`
* **Kategori**: `04-Backend-and-Database`
* **Domain Kurikulum**: Laravel Advanced Architecture & Real-World Engineering
* **Judul Modul**: `API Engineering, Modern Monolith & Inertia.js`
* **Tingkat Kesulitan**: `Advanced (Level 400)`
* **Prasyarat**:
  * Pemahaman mendalam tentang Laravel Service Container, Routing, dan Eloquent ORM.
  * Pemahaman dasar arsitektur REST, Single Page Applications (SPA), dan Modern JavaScript (Vue.js / React, TypeScript, ESM).
  * Pengalaman menggunakan Composer dan Node.js/NPM/Vite ecosystem.
* **Target Kompetensi**:
  * Menguasai arsitektur API RESTful enterprise menggunakan Laravel API Resources, Content Negotiation, Versioning, dan Standardized Error Envelope.
  * Mampu mendesain dan mengimplementasikan Modern Monolith menggunakan Inertia.js untuk menghilangkan kompleksitas state management ganda (Client-Server synchronization).
  * Mengimplementasikan autentikasi hibrida yang aman (Stateful Session untuk Inertia.js via Laravel Sanctum dan Stateless Token/OAuth untuk API Publik).
  * Menerapkan teknik optimasi performa backend: Partial Reloads, Lazy Data Evaluation, Deferred Props, ETag Caching, dan Fine-grained Rate Limiting.

---

## 02: Learning Objectives

1. **Konseptual**: Menganalisis perbedaan mendasar antara Traditional Multi-Page Applications (MPA), decoupled Client-Side SPAs, dan Modern Monoliths (Inertia.js) dalam konteks latency, developer velocity, dan operational overhead.
2. **Arsitektur API**: Merancang API tier berstandar industri dengan transformasi data deterministik (`JsonResource`), paginasi terisolasi, versioning berbasis URL/Header, dan penanganan exception terpusat (`ProblemDetails` RFC 7807).
3. **Integrasi Modern Monolith**: Membangun pipeline transmisi data Inertia.js yang efisien, memanfaatkan `Inertia::defer()`, `Inertia::lazy()`, and Partial Reloads untuk meminimalkan beban komputasi database dan transit payload.
4. **Keamanan & Autentikasi**: Mengonfigurasi Laravel Sanctum secara simultan untuk web SPA (CSRF protection + HTTP-only cookies) dan mobile/third-party API (Bearer Tokens) dengan isolasi guard yang ketat.
5. **Verifikasi Kualitas**: Menulis test suite otomatis (Unit, Feature, Inertia Asserts) yang memvalidasi integritas response API dan properti payload Inertia tanpa bergantung pada browser automation yang lambat.

---

## 03: Concept Map Diagram ASCII

```text
+---------------------------------------------------------------------------------------------------------+
|                                     LARAVEL CORE RUNTIME ENGINE                                         |
+---------------------------------------------------------------------------------------------------------+
                                                     |
                                            [ HTTP Kernel / Pipeline ]
                                                     |
                         +---------------------------+---------------------------+
                         |                                                       |
        [ Route Group: api/* ]                                  [ Route Group: web/* ]
        (Stateless, Token-based, JSON)                          (Stateful, Session-based, Web/Inertia)
                         |                                                       |
            +------------+------------+                             +------------+------------+
            |                         |                             |                         |
     [ Sanctum Guard: api ]   [ Rate Limiter ]              [ Sanctum: web ]         [ HandleInertiaRequests ]
            |                         |                             |                         |
    [ Versioning Middleware ]         |                             |             +-----------+-----------+
            |                         |                             |             |                       |
   [ Controllers / Actions ]          |                    [ Inertia Middleware ] | [ Shared Props: User, ]
            |                         |                             |             | [ Ziggy, Flash, CSRF  ]
     [ Eloquent Queries ]             |                    [ Inertia::render() ]  +-----------------------+
            |                         |                             |
  [ API Resources / Transformers ]    |               +-------------+-------------+
            |                         |               |                           |
  [ RFC 7807 Exception Envelopes ]    |      (Standard Page Load)         (Inertia Partial Reload)
            |                         |               |                           |
            v                         v               v                           v
  +---------------------------------------+   +-----------------------+   +-------------------------------+
  |   JSON Payload Output (RFC Compliant) |   | Full HTML Document    |   | JSON Response:                |
  |   - data: { ... }                     |   | (Root template +      |   | { component: "...",           |
  |   - meta: { pagination }              |   |  data-page attribute) |   |   props: { ... },             |
  |   - links: { self, next }             |   +-----------------------+   |   version: "sha1..." }        |
  +---------------------------------------+                               +-------------------------------+
```

---

## 04: Mengapa Relevan

Secara historis, pengembangan sistem frontend-backend modern didominasi oleh arsitektur *Fully Decoupled SPA* (Single Page Application). Pola ini mewajibkan pembuatan REST/GraphQL API independen yang dikonsumsi oleh frontend framework terpisah (Vue/React). Walaupun fleksibel, arsitektur ini memperkenalkan friksi engineering yang masif:
* **Duplikasi Logika Bisnis & Validasi**: Aturan validasi dan otorisasi harus dideklarasikan dua kali (backend validator dan client-side state/routing guard).
* **State Management Boilerplate**: Kebutuhan mengelola client-side cache kompleks (Redux, Pinia, TanStack Query) hanya untuk merefleksikan data backend.
* **Overhead Autentikasi & CORS**: Mengelola token refresh, local storage security issues, dan preflight CORS requests.

Modern Monolith menggunakan **Inertia.js** memecahkan dikotomi ini dengan menjadi "jembatan transmisi" (The Modern Monolith). Pengembang mempertahankan produktivitas monolitik Laravel (routing, controllers, database, authorization) sambil mendapatkan kapabilitas interaktif client-side rendering (Vue 3 / React). Di sisi lain, kebutuhan ekosistem aplikasi mobile atau integrasi pihak ketiga tetap menuntut **API Engineering** yang tangguh, deterministik, dan memiliki standardisasi ketat. Menguasai kedua paradigma ini dalam satu codebase Laravel adalah keterampilan inti bagi Senior Software Engineer.

---

## 05: Anatomi Konsep Inti

```text
+------------------------------------------------------------------------------------------------------+
| 1. INERTIA PROTOCOL SPECIFICATION                                                                    |
|    - Initial Visit: Server returns HTML with `<div id="app" data-page='{"component":"...", ...}'>`   |
|    - Subsequent Navigation: Client sends `X-Inertia: true` header via Fetch/Axios.                   |
|    - Server detects header, bypasses Blade wrapper, directly serializes response to JSON.            |
|    - Asset Versioning: Client sends `X-Inertia-Version: <hash>`. If mismatched, server returns 409    |
|      Conflict, prompting client to do a hard refresh to bust browser asset cache.                    |
+------------------------------------------------------------------------------------------------------+
| 2. LARAVEL API RESOURCES & TRANSFORMERS                                                              |
|    - Encapsulation: Explicit mapping layer decoupling Eloquent Models from API Output.              |
|    - N+1 Prevention: Conditionally load relations via `$this->whenLoaded('relation')`.              |
|    - Data Wrapping: Root property normalization (`{"data": [...]}`) & dynamic metadata injection.    |
+------------------------------------------------------------------------------------------------------+
| 3. INERTIA ADVANCED RENDERING LIFECYCLE                                                              |
|    - Lazy Data: Evaluated only when requested via partial reloads (`Inertia::lazy()`).               |
|    - Deferred Props: Server responds instantly, client fetches secondary payload asynchronously      |
|      via `Inertia::defer()`.                                                                         |
|    - Always Props: Injected on every request regardless of partial reload params.                    |
+------------------------------------------------------------------------------------------------------+
| 4. DUAL-PURPOSE SANCTUM AUTHENTICATION                                                               |
|    - Web Context: State-based authentication via secure HTTP-Only session cookies & CSRF tokens.     |
|    - API Context: Cryptographically secure Personal Access Tokens (`Bearer <plainTextToken>`) with   |
|      token abilities/scopes for granular access controls.                                            |
+------------------------------------------------------------------------------------------------------+
```

---

## 06: Panduan Implementasi Step-by-Step

### Langkah 1: Inisialisasi Stack Modern Monolith & API Dependencies

Jalankan instalasi paket inti untuk Inertia.js adapter dan Sanctum via Composer:

```bash
composer require inertiajs/inertia-laravel:^2.0
composer require laravel/sanctum:^4.0
composer require tightenco/ziggy:^2.0

# Install Client-side Dependencies
npm install @inertiajs/vue3 @vitejs/plugin-vue vue axios
```

### Langkah 2: Publikasi Middleware dan Konfigurasi Sanctum

Inisialisasi middleware Inertia dan daftarkan ke HTTP Kernel Laravel (Laravel 11+ via `bootstrap/app.php`):

```bash
php artisan inertia:middleware
```

Konfigurasi `bootstrap/app.php` untuk mengaktifkan stateful API domains dan middleware:

```php
<?php

use App\Http\Middleware\HandleInertiaRequests;
use Illuminate\Foundation\Application;
use Illuminate\Foundation\Configuration\Exceptions;
use Illuminate\Foundation\Configuration\Middleware;
use Illuminate\Http\Request;
use Laravel\Sanctum\Http\Middleware\EnsureFrontendRequestsAreStateful;
use Symfony\Component\HttpKernel\Exception\NotFoundHttpException;
use Symfony\Component\HttpKernel\Exception\AccessDeniedHttpException;

return Application::configure(basePath: dirname(__DIR__))
    ->withRouting(
        web: __DIR__.'/../routes/web.php',
        api: __DIR__.'/../routes/api.php',
        commands: __DIR__.'/../routes/console.php',
        health: '/up',
    )
    ->withMiddleware(function (Middleware $middleware) {
        $middleware->web(append: [
            HandleInertiaRequests::class,
        ]);

        $middleware->api(prepend: [
            EnsureFrontendRequestsAreStateful::class,
        ]);

        $middleware->statefulApi();
    })
    ->withExceptions(function (Exceptions $exceptions) {
        $exceptions->render(function (Throwable $e, Request $request) {
            if ($request->is('api/*') || $request->wantsJson()) {
                $status = method_exists($e, 'getStatusCode') ? $e->getStatusCode() : 500;
                
                return response()->json([
                    'type' => 'https://errors.enterprise.internal/errors/' . class_basename($e),
                    'title' => class_basename($e),
                    'status' => $status,
                    'detail' => $e->getMessage() ?: 'An unhandled server exception occurred.',
                    'instance' => $request->path(),
                    'code' => $e->getCode(),
                ], $status);
            }
        });
    })->create();
```

---

## 07: Contoh Kasus Sederhana

Implementasi endpoint API Resource standar beserta Controller penanganannya.

### Resource Transformer: `OrderResource.php`

```php
<?php

declare(strict_types=1);

namespace App\Http\Resources\Api\V1;

use App\Models\Order;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

/**
 * @mixin Order
 */
final class OrderResource extends JsonResource
{
    /**
     * Transform the resource into an array.
     *
     * @return array<string, mixed>
     */
    public function toArray(Request $request): array
    {
        return [
            'id' => $this->id,
            'reference_number' => $this->reference_number,
            'total_amount' => [
                'raw' => $this->total_cents,
                'formatted' => '$' . number_format($this->total_cents / 100, 2),
                'currency' => $this->currency,
            ],
            'status' => $this->status->value,
            'customer' => CustomerResource::make($this->whenLoaded('customer')),
            'items' => OrderItemResource::collection($this->whenLoaded('items')),
            'created_at' => $this->created_at?->toISOString(),
            'updated_at' => $this->updated_at?->toISOString(),
        ];
    }
}
```

### Controller API: `OrderController.php`

```php
<?php

declare(strict_types=1);

namespace App\Http\Controllers\Api\V1;

use App\Http\Controllers\Controller;
use App\Http\Resources\Api\V1\OrderResource;
use App\Models\Order;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\AnonymousResourceCollection;

final class OrderController extends Controller
{
    public function index(Request $request): AnonymousResourceCollection
    {
        $orders = Order::query()
            ->with(['customer', 'items'])
            ->where('merchant_id', $request->user()->merchant_id)
            ->latest('id')
            ->paginate($request->integer('per_page', 15))
            ->appends($request->query());

        return OrderResource::collection($orders);
    }

    public function show(Request $request, Order $order): JsonResource
    {
        $this->authorize('view', $order);

        $order->loadMissing(['customer', 'items.product']);

        return OrderResource::make($order);
    }
}
```

---

## 08: Implementasi Production-Grade Lengkap Kode

Berikut adalah implementasi modul manajemen inventaris (*Inventory System*) berskala enterprise yang mengombinasikan **Inertia.js v2 Dashboard** (Modern Monolith) dan **Stateless Public API v1**.

### 1. Custom Problem Details Exception Handler

```php
<?php

declare(strict_types=1);

namespace App\Exceptions;

use Exception;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

final class BusinessLogicException extends Exception
{
    public function __construct(
        string $message = 'A business rule violation occurred.',
        private readonly string $errorType = 'https://api.domain.com/errors/business-violation',
        private readonly int $httpStatus = Response::HTTP_UNPROCESSABLE_ENTITY,
        private readonly array $context = []
    ) {
        parent::__construct($message, $httpStatus);
    }

    public function render(Request $request): JsonResponse
    {
        return response()->json([
            'type' => $this->errorType,
            'title' => 'Unprocessable Entity Business Rule Violation',
            'status' => $this->httpStatus,
            'detail' => $this->getMessage(),
            'invalid_params' => $this->context,
            'timestamp' => now()->toISOString(),
        ], $this->httpStatus);
    }
}
```

### 2. HandleInertiaRequests Middleware

```php
<?php

declare(strict_types=1);

namespace App\Http\Middleware;

use Illuminate\Http\Request;
use Inertia\Middleware;
use Tighten\Ziggy\Ziggy;

final class HandleInertiaRequests extends Middleware
{
    /**
     * The root template that's loaded on the first page visit.
     *
     * @see https://inertiajs.com/server-side-setup#root-template
     * @var string
     */
    protected $rootView = 'app';

    /**
     * Determines the current asset version.
     *
     * @see https://inertiajs.com/asset-versioning
     */
    public function version(Request $request): ?string
    {
        return parent::version($request);
    }

    /**
     * Defines the props that are shared by default.
     *
     * @see https://inertiajs.com/shared-data
     * @return array<string, mixed>
     */
    public function share(Request $request): array
    {
        return [
            ...parent::share($request),
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
            ],
            'ziggy' => fn () => [
                ...(new Ziggy)->toArray(),
                'location' => $request->url(),
            ],
        ];
    }
}
```

### 3. Dedicated Inventory Inertia Controller with Lazy & Deferred Props

```php
<?php

declare(strict_types=1);

namespace App\Http\Controllers\Web;

use App\Http\Controllers\Controller;
use App\Models\Product;
use App\Models\Warehouse;
use Illuminate\Http\Request;
use Inertia\Inertia;
use Inertia\Response;

final class InventoryDashboardController extends Controller
{
    public function index(Request $request): Response
    {
        return Inertia::render('Inventory/Index', [
            // Standard prop loaded synchronously on first visit and subsequent visits
            'filters' => $request->only(['search', 'warehouse_id', 'status']),
            
            // Primary data payload
            'products' => Product::query()
                ->select(['id', 'sku', 'name', 'warehouse_id', 'stock_level', 'unit_cost', 'updated_at'])
                ->with('warehouse:id,name')
                ->when($request->input('search'), function ($query, $search) {
                    $query->where(function ($q) use ($search) {
                        $q->where('name', 'like', "%{$search}%")
                          ->orWhere('sku', 'like', "%{$search}%");
                    });
                })
                ->when($request->input('warehouse_id'), function ($query, $warehouseId) {
                    $query->where('warehouse_id', $warehouseId);
                })
                ->paginate(15)
                ->through(fn ($product) => [
                    'id' => $product->id,
                    'sku' => $product->sku,
                    'name' => $product->name,
                    'warehouse' => $product->warehouse?->name,
                    'stock_level' => $product->stock_level,
                    'unit_cost' => $product->unit_cost,
                    'last_updated' => $product->updated_at->diffForHumans(),
                ])
                ->withQueryString(),

            // Lazy Prop: Evaluated ONLY when specifically requested by client partial reload
            'warehouses' => Inertia::lazy(fn () => Warehouse::query()
                ->select(['id', 'name', 'code'])
                ->orderBy('name')
                ->get()
            ),

            // Deferred Prop (Inertia v2): Allows initial page render without waiting for heavy analytics query
            'analyticsSummary' => Inertia::defer(fn () => [
                'total_valuation_cents' => (int) Product::query()->sum('unit_cost * stock_level'),
                'low_stock_alerts_count' => Product::query()->where('stock_level', '<', 10)->count(),
                'out_of_stock_count' => Product::query()->where('stock_level', '=', 0)->count(),
            ]),
        ]);
    }
}
```

### 4. Enterprise API Controller: `Api/V1/ProductApiController.php`

```php
<?php

declare(strict_types=1);

namespace App\Http\Controllers\Api\V1;

use App\Exceptions\BusinessLogicException;
use App\Http\Controllers\Controller;
use App\Http\Requests\Api\V1\StoreProductRequest;
use App\Http\Resources\Api\V1\ProductResource;
use App\Models\Product;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\AnonymousResourceCollection;
use Illuminate\Support\Facades\DB;
use Symfony\Component\HttpFoundation\Response;

final class ProductApiController extends Controller
{
    public function index(Request $request): AnonymousResourceCollection
    {
        $products = Product::query()
            ->with(['warehouse', 'category'])
            ->when($request->filled('category_id'), fn ($q) => $q->where('category_id', $request->input('category_id')))
            ->paginate($request->integer('per_page', 25));

        return ProductResource::collection($products);
    }

    public function store(StoreProductRequest $request): JsonResponse
    {
        $validated = $request->validated();

        $product = DB::transaction(function () use ($validated) {
            // Check SKU uniqueness logic defensively
            if (Product::where('sku', $validated['sku'])->lockForUpdate()->exists()) {
                throw new BusinessLogicException(
                    message: "The specified SKU {$validated['sku']} is already reserved or active.",
                    context: ['sku' => $validated['sku']]
                );
            }

            return Product::create($validated);
        });

        return ProductResource::make($product)
            ->response()
            ->setStatusCode(Response::HTTP_CREATED)
            ->header('Location', route('api.v1.products.show', ['product' => $product->id]));
    }

    public function show(Product $product): ProductResource
    {
        $product->loadMissing(['warehouse', 'category', 'auditLogs']);

        return ProductResource::make($product);
    }
}
```

### 5. Frontend Vue 3 Component: `resources/js/Pages/Inventory/Index.vue`

```vue
<script setup lang="ts">
import { ref, watch } from 'vue';
import { router, Deferred } from '@inertiajs/vue3';
import debounce from 'lodash/debounce';

interface Product {
  id: number;
  sku: string;
  name: string;
  warehouse: string;
  stock_level: number;
  unit_cost: number;
  last_updated: string;
}

interface Analytics {
  total_valuation_cents: number;
  low_stock_alerts_count: number;
  out_of_stock_count: number;
}

interface Props {
  products: {
    data: Product[];
    links: Array<{ url: string | null; label: string; active: boolean }>;
  };
  filters: {
    search?: string;
    warehouse_id?: string;
  };
  warehouses?: Array<{ id: number; name: string; code: string }>;
  analyticsSummary?: Analytics;
}

const props = defineProps<Props>();

const search = ref(props.filters.search || '');
const selectedWarehouse = ref(props.filters.warehouse_id || '');

const executeSearch = debounce(() => {
  router.get(
    '/inventory',
    { search: search.value, warehouse_id: selectedWarehouse.value },
    {
      preserveState: true,
      preserveScroll: true,
      replace: true,
      only: ['products', 'filters'],
    }
  );
}, 300);

watch([search, selectedWarehouse], () => {
  executeSearch();
});

const loadWarehouses = () => {
  router.reload({ only: ['warehouses'] });
};
</script>

<template>
  <div class="p-6 max-w-7xl mx-auto space-y-6">
    <div class="flex justify-between items-center">
      <h1 class="text-2xl font-bold tracking-tight text-gray-900">Enterprise Inventory</h1>
      <button 
        @click="loadWarehouses" 
        class="px-4 py-2 bg-slate-800 text-white rounded text-sm hover:bg-slate-700"
      >
        Lazy Load Warehouses
      </button>
    </div>

    <!-- Inertia Deferred Metrics Component -->
    <Deferred data="analyticsSummary">
      <template #fallback>
        <div class="grid grid-cols-3 gap-4 animate-pulse">
          <div class="h-24 bg-gray-200 rounded"></div>
          <div class="h-24 bg-gray-200 rounded"></div>
          <div class="h-24 bg-gray-200 rounded"></div>
        </div>
      </template>
      
      <div v-if="analyticsSummary" class="grid grid-cols-3 gap-4">
        <div class="p-4 bg-white shadow rounded-lg border border-gray-100">
          <span class="text-sm text-gray-500">Valuation</span>
          <p class="text-xl font-bold">${{ (analyticsSummary.total_valuation_cents / 100).toLocaleString() }}</p>
        </div>
        <div class="p-4 bg-white shadow rounded-lg border border-gray-100">
          <span class="text-sm text-yellow-600">Low Stock Warnings</span>
          <p class="text-xl font-bold text-yellow-600">{{ analyticsSummary.low_stock_alerts_count }}</p>
        </div>
        <div class="p-4 bg-white shadow rounded-lg border border-gray-100">
          <span class="text-sm text-red-600">Stockouts</span>
          <p class="text-xl font-bold text-red-600">{{ analyticsSummary.out_of_stock_count }}</p>
        </div>
      </div>
    </Deferred>

    <!-- Filters -->
    <div class="flex gap-4">
      <input
        v-model="search"
        type="text"
        placeholder="Search SKU or Name..."
        class="w-1/3 rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
      />
    </div>

    <!-- Product Table -->
    <div class="bg-white shadow overflow-hidden rounded-lg border border-gray-200">
      <table class="min-w-full divide-y divide-gray-200">
        <thead class="bg-gray-50">
          <tr>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">SKU</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Product Name</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Warehouse</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Stock</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Updated</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-200">
          <tr v-for="product in products.data" :key="product.id">
            <td class="px-6 py-4 whitespace-nowrap text-sm font-mono text-gray-700">{{ product.sku }}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{{ product.name }}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ product.warehouse }}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{{ product.stock_level }}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-400">{{ product.last_updated }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
```

---

## 09: Diagram Alur Kerja ASCII

### Alur Navigasi Klien via Inertia vs Direct API

```text
[ CLIENT BROWSER: Inertia App ]                     [ LARAVEL BACKEND ENGINE ]
             |                                                  |
             |--- 1. Inertia Visit Request (e.g. router.visit) ->
             |    Headers: {                                    |
             |      "X-Inertia": "true",                        |
             |      "X-Inertia-Version": "b48c90..."            |
             |    }                                             |
             |                                                  |
             |                                      [ HandleInertiaRequests ]
             |                                      Check Asset Version Hash
             |                                                  |
             |                                      Version Match?
             |                                      +--- NO  --> [ Return 409 Conflict ]
             |                                      |            (Forces Hard Refresh)
             |                                      +--- YES
             |                                                  |
             |                                      [ Controller Processing ]
             |                                      - Evaluate regular props
             |                                      - Skip 'Inertia::lazy()' unless in 'only'
             |                                      - Wrap 'Inertia::defer()'
             |                                                  |
             |<-- 2. Return JSON Response ----------------------+
             |    Headers: { "X-Inertia": "true" }
             |    Body: {
             |      "component": "Inventory/Index",
             |      "props": { ... },
             |      "version": "b48c90..."
             |    }
             |
   [ Dynamic Component Swapping ]
   - Updates Vue/React View
   - No Browser Reload
   - PushState URL Update
             |
             |--- 3. Client Resolves Deferred Props (Async) --->
             |<-- 4. Server Returns Deferred Payload -----------+
```

---

## 10: Analisis Trade-offs

| Dimensi Arsitektural | Fully Decoupled SPA (React/Vue API Standalone) | Modern Monolith (Inertia.js + Laravel) |
| :--- | :--- | :--- |
| **Development Velocity** | **Rendah**: Membutuhkan sinkronisasi DTO, router duplikat, dan manajemen state client (Redux/Pinia). | **Sangat Tinggi**: Routing dan validasi ditangani backend, data diteruskan langsung via props. |
| **API Reusability** | **Tinggi**: Endpoint API yang dibuat dapat langsung dipakai aplikasi Mobile/Pihak Ketiga. | **Rendah**: Inertia responses didesain untuk views internal; API terpisah tetap dibutuhkan. |
| **Latency / Payload** | **Variatif**: Sering terjadi *waterfall requests* jika tidak dirancang dengan agregasi cermat. | **Rendah-Optimal**: Data dikirim langsung pada render tree pertama; mendukung deferred loads. |
| **Authentication Complexity** | **Tinggi**: Memerlukan arsitektur OAuth2/JWT kompleks, token refresh flows, dan local state security. | **Sangat Rendah**: Memanfaatkan default stateful HTTP-only session cookies yang kebal eksfiltrasi token JS. |
| **Operational Overhead** | **Tinggi**: Dua deployment pipeline terpisah, konfigurasi CORS, dan multiple infrastructure hosts. | **Minimal**: Single deployment artifact, zero CORS configuration, shared CI/CD workflow. |

---

## 11: Best Practices & Antipatterns

### ✅ Best Practices

* **Terapkan `whenLoaded()` pada API Resources**: Jangan pernah membiarkan relation terpanggil secara tidak sengaja di Resource class untuk mencegah degradasi N+1 database queries.
* **Gunakan Explicit Inertia Partial Reloading**: Batasi pengiriman payload dengan `only: ['property']` saat membuat search filter, pagination, atau sorting.
* **Standarisasi Error Envelope**: Patuhi RFC 7807 (`application/problem+json`) untuk response API errors, hindari format generic tanpa schema.
* **Kompilasi Asset Hash Otomatis**: Gunakan checksum file manifest Vite pada `HandleInertiaRequests::version()` untuk memaksa update klien secara deterministik saat deployment terjadi.

### ❌ Antipatterns

* **Mass Assignment Serialization**: Me-return instance Eloquent langsung dari controller (`return response()->json($product);`). Hal ini menyebabkan kebocoran atribut sensitif (`hidden_attributes`, data struktur DB).
* **Duplikasi Logika Validasi**: Membuat validasi manual di JS dan meniadakan Laravel `FormRequest` di sisi backend.
* **Over-sharing Global Props**: Memasukkan dataset besar ke dalam middleware `HandleInertiaRequests::share()`. Hal ini membengkakkan ukuran payload pada setiap request routing.
* **Menggunakan JWT pada First-Party Web SPA**: Menyimpan token JWT di `localStorage` daripada menggunakan secure HTTP-only cookies Sanctum.

---

## 12: Security Hardening

### 1. Granular Personal Access Token Scopes (Sanctum)

Pastikan token memiliki batasan izin (*abilities*) spesifik dan divalidasi via middleware:

```php
// Route Definition
Route::middleware(['auth:sanctum', 'abilities:inventory:write'])->group(function () {
    Route::post('/v1/products', [ProductApiController::class, 'store']);
});

// Middleware Check Logic
if (! $request->user()->tokenCan('inventory:write')) {
    throw new AccessDeniedHttpException('Insufficient cryptographic token abilities.');
}
```

### 2. Strict Content Negotiation Guard Middleware

Cegah penyerang mengirim header invalid yang dapat merusak parsing output:

```php
<?php

declare(strict_types=1);

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\HttpKernel\Exception\NotAcceptableHttpException;

final class EnforceJsonContentNegotiation
{
    public function handle(Request $request, Closure $next): Response
    {
        if (! $request->is('api/*')) {
            return $next($request);
        }

        $accept = $request->header('Accept');
        
        if ($accept !== null && $accept !== '*/*' && ! str_contains($accept, 'application/json')) {
            throw new NotAcceptableHttpException('API accepts only application/json payloads.');
        }

        return $next($request);
    }
}
```

---

## 13: Observabilitas & Debugging

### Trace Context Injection & Sentry Integration

Untuk membedakan error API dan interaksi Inertia, inject contextual tags ke dalam monitoring pipeline:

```php
// Di dalam AppServiceProvider.php
use Illuminate\Support\Facades\Context;
use Illuminate\Support\Str;

public function boot(): void
{
    Context::add('request_