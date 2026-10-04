# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi (Modern View Layer: Hotwire & ViewComponents)

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis dan Mengimplementasikan Arsitektur DOM Morphing**: Memahami cara kerja mesin *diffing* DOM (Idiomorph) pada Turbo 8, mengontrol siklus hidup mutasi DOM, dan mencegah hilangnya *ephemeral state* (fokus input, status gulir, seleksi teks).
2. **Merancang Komponen UI Skalabel dengan ViewComponent**: Membangun pohon komponen modular berbasis slot struktural (`renders_one`, `renders_many`), menerapkan pengetikan parameter yang ketat, serta mengisolasi logika presentasi dari domain model.
3. **Mengorkestrasikan Reaktivitas Real-Time Skala Enterprise**: Mengonfigurasi *broadcasting pipeline* Turbo Streams melalui ActiveJob dan AnyCable untuk menangani ribuan koneksi konkuren tanpa membebani *thread pool* Ruby web server.
4. **Menerapkan Pola Komunikasi Antar-Controller Stimulus**: Menggunakan Stimulus Outlets API, Values API, dan Custom Event Buses untuk membangun interaksi antarmuka yang terdesentralisasi tanpa *spaghetti code*.
5. **Mengoptimalkan Kinerja dan Memitigasi Bottleneck**: Mendiagnosis masalah N+1 pada *component rendering*, kebocoran memori WebSocket pada koneksi persisten, serta *cache stampede* pada *view caching*.

---

## 2. Prerequisite

Peserta wajib menguasai:
- Pengetahuan fundamental Ruby on Rails (MVC lifecycle, ActiveRecord, ActionView ERB, Routing).
- Konsep dasar Hotwire (perbedaan Turbo Drive, Turbo Frames, dan Turbo Streams tingkat pengenalan).
- Sintaksis modern JavaScript (ES6+ Modules, Classes, Custom Events, MutationObserver).
- Dasar-dasar protokol WebSocket, pub/sub messaging (Redis), dan konkurensi model Puma (Thread vs Process).
- Tooling: Ruby 3.2+, Rails 7.1+, Node.js 18+, Redis 7+.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Turbo 8 Page Refreshes & Morphing Engine (Idiomorph)
Arsitektur klasik Hotwire mengandalkan penggantian elemen DOM secara granular menggunakan Turbo Frames atau Turbo Streams (`replace`, `update`, `append`). Pendekatan ini menuntut pemeliharaan puluhan berkas parsial `.turbo_stream.erb`.

Turbo 8 memperkenalkan paradigma **Page Refreshes with Morphing**. Alih-alih merender ulang fragmen HTML dan menimpa *node* secara destruktif (`innerHTML = ...`), Turbo 8 menggunakan pustaka **Idiomorph** untuk melakukan *tree diffing* antara DOM aktif di peramban dengan DOM baru hasil render server:

```
[Server Response (HTML Baru)] 
          │
          ▼
   [Idiomorph Engine] ◄─── Compare with ─── [Live Browser DOM]
          │
   ┌──────┴─────────────────────────────────────────┐
   │ Algoritma Mutasi:                              │
   │ 1. Identifikasi Node via ID / Tag Match        │
   │ 2. Bandingkan Atribut & Ubah In-Place          │
   │ 3. Pertahankan State (Scroll, Focus, Selection)│
   │ 4. Tambah/Hapus Node yang Berbeda Saja         │
   └────────────────────────────────────────────────┘
          │
          ▼
[Mutated Live DOM (Zero layout thrashing, No state loss)]
```

#### Mekanisme Idiomorph:
1. **Node Matching**: Mencocokkan elemen berdasarkan atribut `id`. Jika elemen memiliki ID yang sama, mesin menganggapnya sebagai entitas yang sama dan hanya memutasi atribut serta *children*-nya.
2. **Preservation**: Atribut `data-turbo-permanent` memerintahkan Idiomorph untuk mengabaikan perubahan pada sub-pohon tertentu (misalnya pemutar video, formulir draf, *canvas*).
3. **Scroll Preservation**: Turbo mendeteksi posisi `window.scrollY` dan elemen dengan overflow, memulihkannya secara mulus pasca-mutasi.

### 3.2 ViewComponent Internal Architecture
ViewComponent (awalnya dikembangkan oleh GitHub) menggantikan pola `ApplicationHelper` dan ERB Partials yang prosedural dengan objek Ruby berorientasi objek murni yang dapat diuji secara terisolasi.

```
                    ┌────────────────────────────┐
                    │      Rails Controller      │
                    └─────────────┬──────────────┘
                                  │ passes data
                                  ▼
                    ┌────────────────────────────┐
                    │    OrderSummaryComponent   │ <── Unit Tested
                    │       (Ruby Object)        │
                    └─────────────┬──────────────┘
                                  │ renders slots
                   ┌──────────────┴──────────────┐
                   ▼                             ▼
        ┌─────────────────────┐       ┌─────────────────────┐
        │  HeaderSlot (Slot)  │       │ LineItemSlot (Slot) │
        └──────────┬──────────┘       └──────────┬──────────┘
                   │                             │
                   └──────────────┬──────────────┘
                                  │ compiles into
                                  ▼
                    ┌────────────────────────────┐
                    │    Output Buffer (HTML)    │
                    └────────────────────────────┘
```

#### Lifecycle ViewComponent:
1. **Initialization (`initialize`)**: Validasi tipe data masukan menggunakan `dry-initializer` atau *keyword arguments* standar. Tidak ada rendering di tahap ini.
2. **Before Render Hook (`before_render`)**: Dijalankan tepat sebelum template diproses. Tempat yang aman untuk kalkulasi turunan yang membutuhkan konteks view Rails (`helpers`).
3. **Slot Resolution**: Slot yang didaftarkan melalui `renders_one` atau `renders_many` dievaluasi menjadi sub-komponen terstruktur.
4. **Template Compilation**: Engine mengompilasi template (ERB/Haml) menjadi metode Ruby internal di dalam kelas komponen (`call` atau berkas `.html.erb` terkait). Kompilasi ini hanya terjadi sekali pada mode produksi, menghasilkan performa render hingga 10x lebih cepat dibanding `render partial: ...`.

### 3.3 AnyCable Integration Architecture
ActionCable bawaan Rails mengeksekusi satu Ruby thread per koneksi WebSocket. Pada skala 10.000+ koneksi konkuren, konsumsi memori Ruby VM membengkak secara drastis (skala Gigabytes) dan Global VM Lock (GVL) membatasi *throughput*.

AnyCable memisahkan lapisan koneksi real-time dari logika aplikasi bisnis:
- **AnyCable-Go**: Server berbasis Go (atau Erlang) yang mengelola ratusan ribu koneksi WebSocket klien dengan jejak memori sangat rendah (~10-20 KB per koneksi).
- **RPC Worker**: Ketika ada aksi masuk (misal: subscribe, perform), AnyCable-Go mengirimkan request gRPC berkecepatan tinggi ke *pool* worker Ruby standar.
- **Broadcast Pipeline**: Server Rails mempublikasikan pesan broadcast langsung ke Redis/NATS/HTTP Broadcast API AnyCable-Go, yang kemudian mendistribusikannya langsung ke socket klien tanpa menyentuh Ruby runtime lagi.

---

## 4. Why & What

| Pendekatan Tradisional (SPA + JSON API) | Pendekatan Modern Rails View Layer (Hotwire + ViewComponent) |
| :--- | :--- |
| **Duplikasi Logika Validasi**: Validasi aturan bisnis diimplementasikan ulang di TypeScript/React dan di Ruby/Rails. | **Single Source of Truth**: Aturan bisnis, validasi, dan otorisasi sepenuhnya hidup di server Ruby. |
| **State Synchronization Hell**: Klien harus mengelola Redux/Zustand cache, sinkronisasi token autentikasi, dan serialisasi JSON. | **Server-Driven State**: Klien adalah *dumb terminal*. Server mengirimkan representasi HTML mutakhir (HTML-over-the-wire). |
| **Overhead Kompilasi & Bundle Size**: Pengguna mengunduh Megabytes bundel JavaScript sebelum interaksi pertama terjadi. | **Zero/Minimal Client Bundle**: Stimulus JS hanya menyediakan *behavior*, Turbo mengelola navigasi dan pembaruan DOM. |
| **Uji View yang Lambat**: Menguji UI membutuhkan browser headless (Cypress/Playwright) yang memakan waktu lama. | **Fast Isolated Unit Testing**: ViewComponent dapat diuji menggunakan unit test Ruby standar dalam hitungan milidetik tanpa headless browser. |

---

## 5. How (Workflow Detail)

Alur kerja berikut mendemonstrasikan orkestrasi pembaruan state sistemik:

```
[1. User Action] ---> Submit form pembayaran via Turbo Drive
                             │
                             ▼
[2. Controller]  ---> PaymentsController#create
                             │
                             ├─► Simpan mutasi data ke Database (PostgreSQL)
                             │
                             ├─► Enqueue ActiveJob: BroadcastPaymentUpdateJob
                             │
                             ▼
[3. ActiveJob]   ---> Memproses payload secara asinkron
                             │
                             ├─► Render OrderSummaryComponent(order: @order)
                             │
                             ├─► Kirim stream via Turbo::StreamsChannel ke AnyCable
                             │
                             ▼
[4. Redis PubSub]---> AnyCable-Go membaca pesan dari Redis Channel
                             │
                             ▼
[5. WebSocket]   ---> Push frame <turbo-stream action="morph"> ke browser
                             │
                             ▼
[6. Idiomorph]   ---> Browser Turbo mendeteksi stream, menjalankan diffing
                             │
                             ├─► Ubah status dari "Pending" ke "Paid"
                             │
                             ├─► Stimulus Controller mendeteksi mutasi DOM
                             │
                             ▼
[7. Stimulus]    ---> Trigger animasi sukses via Web Animations API & mainkan audio
```

---

## 6. Analogy & Diagram ASCII

### Analogi Perakitan Mobil vs Reparasi Komponen
- **Pendekatan SPA**: Anda membawa seluruh pabrik perakitan mobil (React, Redux, Webpack) ke garasi pelanggan (Browser). Klien harus merakit bahan baku (JSON) menjadi mobil utuh (DOM).
- **Turbo Streams Granular**: Pelanggan memesan suku cadang pengganti secara terpisah via kurir: spion baru (`replace`), knalpot baru (`append`). Jika ada 50 komponen yang berubah, kurir bolak-balik 50 kali.
- **Turbo 8 Page Refresh (Idiomorph)**: Server memiliki cetak biru digital 3D utuh dari mobil tersebut. Server mengirimkan hologram mobil baru. Sebuah alat canggih (Idiomorph) memindai mobil lama dan mobil baru, lalu mengubah cat, mengencangkan baut, dan mengganti bagian yang rusak secara instan **tanpa menurunkan penumpang atau mematikan mesin radio yang sedang menyala**.

### Topologi Koneksi AnyCable vs ActionCable

```
  Traditional ActionCable Architecture:
  [Client 1] ───(WS)───┐
  [Client 2] ───(WS)───┼──► [Rails Puma Server (Ruby VM)] ──► [PostgreSQL]
  [Client N] ───(WS)───┘     (High Memory, GVL Contention)

  AnyCable Enterprise Architecture:
  [Client 1] ───(WS)───┐
  [Client 2] ───(WS)───┼──► [AnyCable-Go] ──(Redis PubSub)── [Rails Background Job]
  [Client N] ───(WS)───┘          │                                   ▲
                                  │ (gRPC on action)                  │
                                  ▼                                   │
                           [AnyCable RPC Worker] ─────────────────────┘
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Stimulus Outlets
Stimulus Outlets memungkinkan komunikasi eksplisit antar-controller tanpa memicu *event bubbling* secara manual.

```javascript
// app/javascript/controllers/item_controller.js
import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  static values = { price: Number }

  markAsSelected() {
    this.element.classList.toggle("bg-blue-100")
  }
}
```

```javascript
// app/javascript/controllers/cart_controller.js
import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  static outlets = [ "item" ]
  static targets = [ "total" ]

  calculateTotal() {
    const total = this.itemOutlets.reduce((sum, item) => sum + item.priceValue, 0)
    this.totalTarget.textContent = new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR' }).format(total)
  }

  itemOutletConnected(outlet, element) {
    this.calculateTotal()
  }

  itemOutletDisconnected(outlet, element) {
    this.calculateTotal()
  }
}
```

```html
<!-- app/views/orders/new.html.erb -->
<div data-controller="cart">
  <p>Total: <span data-cart-target="total">Rp 0</span></p>

  <div id="item_1" 
       data-controller="item" 
       data-item-price-value="150000"
       data-cart-item-outlet="#item_1">
    <span>Produk A - Rp 150.000</span>
  </div>

  <div id="item_2" 
       data-controller="item" 
       data-item-price-value="250000"
       data-cart-item-outlet="#item_2">
    <span>Produk B - Rp 250.000</span>
  </div>
</div>
```

---

### 7.2 Practical Example: Enterprise Real-Time Order Execution Dashboard

Kita akan membangun sistem *Trading/Order Execution Desk* multi-tenant berkinerja tinggi menggunakan ViewComponents terstruktur, Turbo 8 Morphing, dan asinkron broadcasting.

#### Domain Model & ViewComponent Setup

```ruby
# app/models/order.rb
class Order < ApplicationRecord
  enum :status, { draft: 0, pending: 1, executed: 2, cancelled: 3 }

  validates :symbol, presence: true
  validates :price_cents, numericality: { greater_than: 0 }
  validates :quantity, numericality: { greater_than: 0 }

  after_update_commit :broadcast_order_execution

  private

  def broadcast_order_execution
    # Broadcast menggunakan ActiveJob untuk menghindari blocking database transaction
    OrderExecutionBroadcastJob.perform_later(id)
  end
end
```

```ruby
# app/components/orders/data_table_component.rb
# frozen_string_literal: true

module Orders
  class DataTableComponent < ViewComponent::Base
    renders_one :header
    renders_many :rows, "RowComponent"

    attr_reader :desk_id

    def initialize(desk_id:)
      @desk_id = desk_id
      super
    end

    class RowComponent < ViewComponent::Base
      attr_reader :order

      def initialize(order:)
        @order = order
        super
      end

      def status_color
        case order.status
        when "executed" then "text-emerald-700 bg-emerald-50 border-emerald-200"
        when "cancelled" then "text-rose-700 bg-rose-50 border-rose-200"
        when "pending"   then "text-amber-700 bg-amber-50 border-amber-200"
        else "text-slate-700 bg-slate-50 border-slate-200"
        end
      end
    end
  end
end
```

```erb
<%# app/components/orders/data_table_component.html.erb %>
<div class="relative overflow-x-auto shadow-md sm:rounded-lg border border-slate-200"
     data-controller="order-monitor"
     data-order-monitor-desk-id-value="<%= desk_id %>"
     id="order_table_desk_<%= desk_id %>">
  
  <table class="w-full text-sm text-left text-slate-500">
    <thead class="text-xs text-slate-700 uppercase bg-slate-50 border-b">
      <% if header %>
        <%= header %>
      <% else %>
        <tr>
          <th scope="col" class="px-6 py-3">Order ID</th>
          <th scope="col" class="px-6 py-3">Symbol</th>
          <th scope="col" class="px-6 py-3">Quantity</th>
          <th scope="col" class="px-6 py-3">Price</th>
          <th scope="col" class="px-6 py-3">Status</th>
          <th scope="col" class="px-6 py-3 text-right">Actions</th>
        </tr>
      <% end %>
    </thead>
    <tbody id="orders_body" class="divide-y divide-slate-100">
      <% rows.each do |row| %>
        <%= row %>
      <% end %>
    </tbody>
  </table>
</div>
```

```erb
<%# app/components/orders/data_table_component/row_component.html.erb %>
<tr id="<%= dom_id(order) %>" 
    class="bg-white hover:bg-slate-50 transition duration-150"
    data-order-monitor-target="row"
    data-order-id="<%= order.id %>"
    data-order-status="<%= order.status %>">
  <td class="px-6 py-4 font-mono font-medium text-slate-900">#<%= order.id %></td>
  <td class="px-6 py-4 font-semibold"><%= order.symbol %></td>
  <td class="px-6 py-4"><%= number_with_delimiter(order.quantity) %></td>
  <td class="px-6 py-4 font-mono">IDR <%= number_to_currency(order.price_cents / 100.0, unit: "") %></td>
  <td class="px-6 py-4">
    <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border <%= status_color %>">
      <%= order.status.humanize %>
    </span>
  </td>
  <td class="px-6 py-4 text-right">
    <% if order.pending? %>
      <%= button_to "Cancel", 
                    order_path(order, order: { status: :cancelled }), 
                    method: :patch, 
                    class: "text-rose-600 hover:text-rose-900 font-medium text-xs underline cursor-pointer",
                    form: { data: { turbo_confirm: "Batalkan order ini?" } } %>
    <% end %>
  </td>
</tr>
```

#### Background Asynchronous Broadcast Job

```ruby
# app/jobs/order_execution_broadcast_job.rb
class OrderExecutionBroadcastJob < ApplicationJob
  queue_as :high_priority

  def perform(order_id)
    order = Order.find_by(id: order_id)
    return unless order

    # Morphing targeted replace broadcast
    # Menggunakan ViewComponent untuk me-render HTML fragmen yang dikirimkan via stream
    Turbo::StreamsChannel.broadcast_replace_to(
      "desk_#{order.desk_id}_stream",
      target: ActionView::RecordIdentifier.dom_id(order),
      component: Orders::DataTableComponent::RowComponent.new(order: order),
      attributes: { morph: true }
    )
  end
end
```

#### Client-side Stimulus Reactive Controller

```javascript
// app/javascript/controllers/order_monitor_controller.js
import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  static targets = [ "row" ]
  static values = { deskId: String }

  connect() {
    this.highlightAudio = new Audio("/sounds/execution-ping.mp3")
    this.highlightAudio.volume = 0.5
  }

  // Dipanggil otomatis ketika Idiomorph memutasi atribut atau node DOM
  rowTargetConnected(element) {
    const status = element.dataset.orderStatus
    if (status === "executed") {
      this.flashRow(element)
    }
  }

  flashRow(element) {
    element.animate([
      { backgroundColor: 'rgba(16, 185, 129, 0.4)' },
      { backgroundColor: 'rgba(255, 255, 255, 1)' }
    ], {
      duration: 1200,
      iterations: 1,
      easing: 'ease-out'
    })

    this.playAudioFeedback()
  }

  playAudioFeedback() {
    if (this.highlightAudio.readyState >= 2) {
      this.highlightAudio.currentTime = 0
      this.highlightAudio.play().catch(() => {
        // Autoplay policy browser mungkin memblokir audio tanpa gesture
      })
    }
  }
}
```

```erb
<%# app/views/desks/show.html.erb %>
<div class="max-w-7xl mx-auto py-8 px-4">
  <div class="flex justify-between items-center mb-6">
    <h1 class="text-2xl font-bold tracking-tight text-slate-900">Execution Desk #<%= @desk.id %></h1>
    
    <%# Mengaktifkan Page Refreshes Morphing untuk seluruh channel ini %>
    <%= turbo_stream_from "desk_#{@desk.id}_stream" %>
  </div>

  <%= render Orders::DataTableComponent.new(desk_id: @desk.id) do |component| %>
    <% component.with_header do %>
      <tr class="border-b bg-slate-100">
        <th class="px-6 py-3">Order Token</th>
        <th class="px-6 py-3">Ticker</th>
        <th class="px-6 py-3">Lot</th>
        <th class="px-6 py-3">Limit Price</th>
        <th class="px-6 py-3">State</th>
        <th class="px-6 py-3 text-right">Action</th>
      </tr>
    <% end %>

    <% @orders.each do |order| %>
      <% component.with_row(order: order) %>
    <% end %>
  <% end %>
</div>
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Real-Time Order Book Flash Sale E-Commerce Tier-1
Sebuah platform e-commerce menyelenggarakan program flash sale mingguan dengan beban puncak 45.000 pesanan per menit. 

### Permasalahan Arsitektural Awal:
1. Setiap mutasi inventaris menyiarkan Turbo Streams parsial menggunakan ActionCable bawaan.
2. Ketika 30.000 pembeli melihat laman inventaris flash sale, 1 perubahan stok memicu 30.000 render ERB di dalam proses Ruby Puma via `ActionCable.server.broadcast`.
3. CPU Puma server mencapai 100% (GVL starvation), *memory consumption* mencapai 24 GB per node, menyebabkan HTTP request biasa *timeout* (HTTP 502).

### Solusi Arsitektural Terapan:
1. **Migrasi WebSocket Layer ke AnyCable-Go**:
   - Memindahkan penanganan 30.000 koneksi WebSocket ke 2 instance kontainer AnyCable-Go (Go binary).
   - Penggunaan RAM turun dari 24 GB (Rails worker) menjadi 650 MB (AnyCable-Go).
2. **Adopsi Turbo 8 Page Refresh Throttle Pattern**:
   - Alih-alih menyiarkan stream granular per mutasi transaksi DB, sistem mengadopsi mekanisme *Debounced Broadcast*:

```ruby
# app/models/concerns/throttled_broadcastable.rb
module ThrottledBroadcastable
  extend ActiveSupport::Concern

  included do
    def broadcast_inventory_refresh_throttled(interval: 250.milliseconds)
      cache_key = "throttle_broadcast:#{self.class.name}:#{id}"
      
      # Set Redis lock/flag dengan TTL singkat
      return if Rails.cache.read(cache_key)

      Rails.cache.write(cache_key, true, expires_in: interval)

      TurboThrottledRefreshJob.set(wait: interval).perform_later(self.class.name, id)
    end
  end
end
```

3. **Client-Side Preservation**:
   - Kolom pencarian produk dan filter harga diberi flag `data-turbo-permanent` agar interaksi pengetikan pengguna tidak pernah di-reset ketika event morphing terjadi secara periodik (setiap 250 milidetik).

Hasil Implementasi: Latensi p99 rendering turun dari 4.800 ms menjadi 120 ms, kapasitas konkurensi meningkat 12x tanpa penambahan server web Puma.

---

## 9. Trade-offs

| Dimensi | Granular Turbo Streams | Turbo 8 Morphing (Idiomorph) | SPA Component Hydration (Inertia/React) |
| :--- | :--- | :--- | :--- |
| **Throughput Server** | Sedang. Harus merender parsial spesifik berulang kali. | Tinggi jika di-cache, Rendah jika merender ulang seluruh halaman penuh tanpa caching. | Sangat Tinggi. Server hanya memvalidasi & mengirimkan payload JSON ringkas. |
| **Beban Jaringan (Bandwidth)** | Sangat Rendah. Mengirim hanya fragmen HTML tag yang berubah (< 1 KB). | Rendah hingga Sedang. Mengirim representasi HTML halaman utuh / fragmen besar. | Paling Rendah. JSON payload minimal. |
| **Kompleksitas Koding** | Tinggi. Developer harus menulis lusinan template `.turbo_stream.erb` dan ID mapping. | Sangat Rendah. Mendukung auto-refresh controller tanpa custom streams view. | Sangat Tinggi. Mengelola API serializer, types, router klien, dan state management. |
| **Kebutuhan Memori Klien** | Rendah. Penanganan node murni. | Rendah. Idiomorph efisien dalam in-memory tree traversal. | Tinggi. DOM Virtual (V-DOM) disimpan di memori klien bersama library runtime SPA. |
| **Kerapuhan State UI** | Sangat Rendah. Target ID langsung ditimpa. | Sedang. Risiko tinggi kehilangan status elemen non-standar (Custom canvas, unkeyed inputs). | Rendah. Virtual DOM mengontrol state stateful lifecycle secara native. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 ID Duplikasi Merusak Morphing (Idiomorph Collapse)
* **Penyebab**: Jika terdapat dua elemen berbeda yang memiliki atribut `id` yang sama, Idiomorph akan mencocokkan *node* pertama dan menghapus *node* kedua secara tidak sengaja.
* **Gejala**: Elemen UI menghilang dari layar secara acak setelah refresh otomatis.
* **Solusi**: Gunakan helper `dom_id(record, :context)` secara konsisten:
  ```erb
  <!-- BURUK -->
  <tr id="order_<%= order.id %>">...</tr>
  <div id="order_<%= order.id %>">...</div>

  <!-- BENAR -->
  <tr id="<%= dom_id(order, :table_row) %>">...</tr>
  <div id="<%= dom_id(order, :modal_card) %>">...</div>
  ```

### 10.2 N+1 Query Tersembunyi di Dalam ViewComponent Slots
* **Penyebab**: Memanggil relasi asosiasi ActiveRecord di dalam `RowComponent#initialize` atau template ViewComponent saat diulang di dalam loop.
* **Troubleshooting**: Aktifkan gem `bullet` pada mode *development* dan *test*. Pastikan eager loading dilakukan di *query root*:
  ```ruby
  # BURUK: Mengakibatkan N+1 query ke tabel User
  @orders = Order.all
  
  # BENAR: Preload relasi yang dibutuhkan komponen
  @orders = Order.includes(:user, :line_items).all
  ```

### 10.3 Kebocoran Memori (Memory Leak) pada Stimulus Controller
* **Penyebab**: Menginisialisasi event listener global (`window.addEventListener` atau third-party plugin seperti Flatpickr/Select2) di dalam metode `connect()` tanpa membersihkannya di `disconnect()`.
* **Solusi**: Daftarkan teardown logic pada `disconnect()`:
  ```javascript
  // app/javascript/controllers/chart_controller.js
  export default class extends Controller {
    connect() {
      this.resizeHandler = () => this.resizeChart()
      window.addEventListener("resize", this.resizeHandler)
      this.chart = new ChartLibrary(this.element)
    }

    disconnect() {
      window.removeEventListener("resize", this.resizeHandler)
      this.chart.destroy() // Hancurkan instance third-party plugin
    }
  }
  ```

---

## 11. Best Practices (Production Checklist)

- [ ] **Strict Slot Validation**: Validasi tipe komponen yang dilewatkan ke dalam ViewComponent slot menggunakan assertion:
  ```ruby
  renders_many :items, ->(component) {
    raise ArgumentError, "Must be an ItemComponent" unless component.is_a?(Orders::ItemComponent)
    component
  }
  ```
- [ ] **Broadcast via ActiveJob Only**: Jangan pernah memanggil `Turbo::StreamsChannel.broadcast_*` secara sinkron di dalam siklus *request-response* atau blok transaksi ActiveRecord. Selalu delegasikan ke antrean latar belakang (Sidekiq/SolidQueue).
- [ ] **Data Turbo Permanent Protection**: Tandai elemen *stateful client* (video player, rich text editors, dynamic file dropzones) dengan atribut `data-turbo-permanent` dan pastikan memiliki atribut `id` yang unik dan stabil.
- [ ] **Redis Connection Pooling**: Pastikan ukuran pool Redis pada `config/cable.yml` setara atau lebih besar dari jumlah thread Puma server (`RAILS_MAX_THREADS`):
  ```yaml
  production:
    adapter: redis
    url: <%= ENV.fetch("REDIS_URL") %>
    channel_prefix: enterprise_app_production
    pool_size: <%= ENV.fetch("RAILS_MAX_THREADS", 5).to_i * 2 %>
  ```
- [ ] **Component View Caching**: Gunakan Russian Doll Caching pada level ViewComponent:
  ```ruby
  def cache_key
    "order_component/#{order.id}-#{order.updated_at.to_fs(:usec)}"
  end
  ```

---

## 12. Hands-on Practice

Buat dan implementasikan file-file berikut pada folder `hands-on/m02/` di repositori lokal Anda.

### Direktori File Struktur
```
hands-on/m02/
├── app/
│   ├── components/
│   │   ├── metrics/
│   │   │   ├── card_component.rb
│   │   │   └── card_component.html.erb
│   ├── controllers/
│   │   └── telemetry_controller.rb
│   └── javascript/
│       └── controllers/
│           ├── telemetry_card_controller.js
│           └── telemetry_hub_controller.js
└── test/
    └── components/
        └── card_component_test.rb
```

### Langkah 1: Implementasi ViewComponent dengan Komputasi Aman
Tulis berkas `hands-on/m02/app/components/metrics/card_component.rb`:
```ruby
# frozen_string_literal: true

module Metrics
  class CardComponent < ViewComponent::Base
    attr_reader :title, :current_value, :previous_value, :unit

    def initialize(title:, current_value:, previous_value:, unit: "")
      @title = title
      @current_value = current_value.to_f
      @previous_value = previous_value.to_f
      @unit = unit
      super
    end

    def percentage_change
      return 0.0 if @previous_value.zero?
      (((@current_value - @previous_value) / @previous_value) * 100).round(2)
    end

    def trend_direction
      return :neutral if percentage_change.zero?
      percentage_change.positive? ? :up : :down
    end
  end
end
```

Tulis berkas template `hands-on/m02/app/components/metrics/card_component.html.erb`:
```erb
<div class="p-6 bg-white rounded-xl shadow-sm border border-slate-200"
     data-controller="telemetry-card"
     data-telemetry-card-value-value="<%= current_value %>"
     id="<%= "metric_#{title.parameterize.underscore}" %>">
  <dt class="text-sm font-medium text-slate-500 truncate"><%= title %></dt>
  <dd class="mt-2 text-3xl font-semibold tracking-tight text-slate-900">
    <%= current_value %> <span class="text-sm font-normal text-slate-500"><%= unit %></span>
  </dd>
  <div class="mt-2 flex items-center text-sm">
    <% if trend_direction == :up %>
      <span class="text-emerald-600 font-semibold flex items-center">▲ <%= percentage_change %>%</span>
    <% elsif trend_direction == :down %>
      <span class="text-rose-600 font-semibold flex items-center">▼ <%= percentage_change %>%</span>
    <% else %>
      <span class="text-slate-400 font-semibold">0.0%</span>
    <% end %>
    <span class="ml-2 text-slate-400">vs periode lalu</span>
  </div>
</div>
```

### Langkah 2: Unit Testing ViewComponent
Tulis berkas unit test `hands-on/m02/test/components/card_component_test.rb`:
```ruby
# frozen_string_literal: true

require "test_helper"

class MetricsCardComponentTest < ViewComponent::TestCase
  def test_renders_positive_trend_correctly
    render_inline(Metrics::CardComponent.new(
      title: "Throughput",
      current_value: 1200,
      previous_value: 1000,
      unit: "req/s"
    ))

    assert_selector("dt", text: "Throughput")
    assert_selector("dd", text: "1200.0 req/s")
    assert_selector(".text-emerald-600", text: "▲ 20.0%")
  end

  def test_handles_zero_previous_value_gracefully
    render_inline(Metrics::CardComponent.new(
      title: "Zero Division Check",
      current_value: 50,
      previous_value: 0
    ))

    assert_selector(".text-slate-400", text: "0.0%")
  end
end
```

### Langkah 3: Implementasi Stimulus Hub & Telemetry Controller
Tulis berkas `hands-on/m02/app/javascript/controllers/telemetry_card_controller.js`:
```javascript
import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  static values = { value: Number }

  flash() {
    this.element.animate([
      { transform: 'scale(1)', backgroundColor: 'rgba(238, 242, 255, 1)' },
      { transform: 'scale(1.02)', backgroundColor: 'rgba(199, 210, 254, 1)' },
      { transform: 'scale(1)', backgroundColor: 'rgba(255, 255, 255, 1)' }
    ], {
      duration: 400,
      easing: 'ease-in-out'
    })
  }

  valueChanged(current, previous) {
    if (previous !== undefined) {
      this.flash()
    }
  }
}
```

Tulis berkas `hands-on/m02/app/javascript/controllers/telemetry_hub_controller.js`:
```javascript
import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  static outlets = [ "telemetry-card" ]

  triggerMassFlash() {
    this.telemetryCardOutlets.forEach(card => card.flash())
  }
}
```

---

## 13. Exercise

### Level Easy
Modifikasi `Metrics::CardComponent` agar menerima slot opsional `renders_one :action_button`. Render slot tersebut di sudut kanan atas kartu metrik hanya jika slot diisi oleh view pemanggil.

### Level Medium
Buat sebuah Stimulus controller bernama `FilterPersistenceController` yang mendengarkan perubahan form filter (*search input* dan *select dropdown*). Simpan parameter query filter saat ini ke `sessionStorage`. Pasca-eksekusi Turbo 8 Morphing, controller harus memvalidasi dan mengembalikan isi kolom input sesuai data di `sessionStorage` tanpa memicu event `change` berulang.

### Level Hard
Implementasikan custom ActionCable Connection authenticator yang memvalidasi signed JWT token dari HTTP header Authorization atau fallback ke encrypted cookie session. Pasang interceptor yang memutuskan koneksi secara elegan (*graceful termination*) dan mengirimkan alert via Turbo Stream saat token mengalami *expiration* di tengah jalan tanpa mengharuskan pengguna memuat ulang seluruh halaman (*hard reload*).

---

## 14. Challenge

### Skenario: Resilient Offline-First Financial Ledger Ticket Terminal

#### Konteks:
Sebuah bank investasi internasional membutuhkan antarmuka web order book untuk obligasi berkecepatan tinggi yang dapat beroperasi pada koneksi satelit dengan latensi tinggi dan sering mengalami *packet drop*.

#### Spesifikasi Tantangan:
1. **Idempotent Optimistic Client Writes**:
   - Ketika trader mengeksekusi order, Stimulus Controller harus langsung memasukkan baris order baru ke dalam tabel secara optimis (*optimistic UI insertion*) dengan status visual "Submitting".
2. **Conflict Detection & Rollback Mechanism via Idiomorph**:
   - Jika order ditolak oleh server backend (misal: *balance insufficiency* atau *market closed*), server mengembalikan Turbo Stream morph signal.
   - Antarmuka harus mengembalikan status baris optimis tersebut ke posisi semula (*rollback*) dengan efek animasi getar (*shake animation*) dan menampilkan *toast notification* yang merinci pesan error validasi, tanpa merusak fokus kursor pada kolom harga.
3. **Bandwidth Preservation Throttling Engine**:
   - Arsitekturi background workers agar mem-broadcast pembaruan buku kasir (*ledger updates*) menggunakan sliding window rate-limiter: maksimal 2 transmisi broadcast per detik per desk. Seluruh mutasi selama jendela interval 500 ms tersebut harus di-*batch* secara rapi di memori (Redis) menjadi 1 representasi morph akhir.

*Evaluasi Keberhasilan*: Tidak boleh ada *layout jump*, state audio cue tidak boleh terinterupsi saat stream mendarat, dan memory profile pada browser DevTools harus datar (tidak ada akumulasi garbage collector akibat detached DOM nodes).

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Pertanyaan Basic
1. Apa fungsi utama algoritma Idiomorph pada Turbo 8 dibanding metode penggantian elemen DOM konvensional?
2. Mengapa method `initialize` pada sebuah ViewComponent dilarang mengakses variabel sesi HTTP Rails secara langsung?
3. Sebutkan atribut HTML yang harus disematkan pada elemen agar tidak terpengaruh oleh mutasi Turbo DOM Morphing!
4. Apa kelemahan konkurensi ActionCable standar yang berbasis Ruby thread pool saat menghadapi puluhan ribu koneksi WebSocket bersamaan?
5. Di manakah lokasi ideal melepaskan (*cleanup*) third-party library instance pada siklus hidup Stimulus Controller?

### 15.2 Pertanyaan Intermediate
6. Jelaskan bagaimana Stimulus Outlets API mengeliminasi kebutuhan komunikasi event melalui `window.dispatchEvent`!
7. Bagaimana cara mencegah terjadinya N+1 query ketika menggunakan arsitektur ViewComponent dengan banyak sub-slot (`renders_many`)?
8. Mengapa eksekusi `Turbo::StreamsChannel.broadcast_*` di dalam blok database transaction (`ActiveRecord::Base.transaction`) merupakan sebuah *anti-pattern* fatal?
9. Apa perbedaan teknis antara `broadcast_replace_to` dengan `broadcast_refresh_to` dalam Turbo 8?
10. Bagaimana AnyCable-Go dapat berkomunikasi kembali dengan business logic Rails ketika ada aksi masuk dari klien?

### 15.3 Skenario Kasus Produksi
11. **Kasus 1**: Sebuah halaman checkout yang di-morph oleh Turbo 8 menyebabkan pengguna kehilangan teks kartu kredit yang sedang diketik di dalam sebuah `iframe` pembayaran bank eksternal. Mengapa ini terjadi dan bagaimana arsitektur penanganannya secara presisi?
12. **Kasus 2**: Monitoring server menunjukkan lonjakan tajam pemakaian memori Redis saat flash sale berlangsung, hingga menyebabkan OOM (Out Of Memory) crash pada instance Redis. Aplikasi menggunakan ActiveJob broadcast stream untuk ribuan pengguna. Bagian mana dari konfigurasi broadcast pipeline yang harus dirombak?
13. **Kasus 3**: Pengguna melaporkan bahwa setelah membiarkan dashboard terbuka selama 4 jam, peramban mereka menjadi lambat (*lagging* parah) dan penggunaan CPU peramban menyentuh 100%. Komponen apa yang paling mungkin mengalami malafungsi pada implementasi Hotwire/Stimulus ini?

---

### Kunci Jawaban Singkat & Petunjuk Evaluasi

#### Pertanyaan Basic
1. **Fungsi Idiomorph**: Melakukan *DOM tree diffing in-place*, hanya mengubah node dan atribut yang berbeda, mempertahankan fokus input, posisi scroll, dan elemen status internal peramban tanpa penggantian total (`innerHTML`).
2. **Isolasi ViewComponent**: Komponen didesain sebagai objek terisolasi (*deterministic*). Mengakses session atau global state secara implisit melanggar prinsip *reusability* dan mempersulit pengujian unit.
3. **Atribut Pelindung**: `data-turbo-permanent`.
4. **Kelemahan Concurrency**: GVL (Global VM Lock) pada Ruby VM dan penggunaan memori yang tinggi per thread/koneksi (1-3 MB per soket di Ruby vs 10-20 KB di Go/Erlang).
5. **Pembersihan Stimulus**: Di dalam method `disconnect()`.

#### Pertanyaan Intermediate
6. **Stimulus Outlets**: Menyediakan referensi langsung berbasis selektor CSS antar-instance kelas Stimulus controller, menghasilkan pemanggilan metode dengan tipe yang lebih terprediksi dibanding *event bubbling* bebas.
7. **Mitigasi N+1 Slots**: Melakukan eager loading (`includes`, `preload`) di tingkat controller/query objek induk sebelum meneruskan koleksi rekod ke ViewComponent root.
8. **Anti-pattern Transaction Broadcast**: Jika job broadcast dieksekusi sebelum database transaksi melakukan *COMMIT*, worker background berpotensi membaca *stale data* atau rekod yang belum eksis (Race Condition).
9. **Morphing vs Granular Stream**: `broadcast_replace_to` menargetkan elemen spesifik dengan fragmen parsial pengganti; `broadcast_refresh_to` memicu sinyal Page Refresh yang memerintahkan browser mengunduh state halaman saat ini dan me-morphing seluruh DOM menggunakan Idiomorph.
10. **AnyCable RPC**: AnyCable-Go bertindak sebagai reverse proxy yang meneruskan RPC request melalui protokol gRPC ke AnyCable Ruby worker processes.

#### Skenario Kasus Produksi
11. **Analisis Kasus 1**: Elemen iframe tidak memiliki penanda identitas yang stabil atau tidak dilindungi oleh `data-turbo-permanent`. Mesin Idiomorph mencoba mencocokkan kembali iframe dan merender ulang SRC-nya sehingga mereset seluruh DOM internal iframe. Solusi: Berikan ID unik pada wrapper iframe dan tambahkan `data-turbo-permanent`.
12. **Analisis Kasus 2**: Terjadi penumpukan payload Turbo Stream berukuran besar di buffer pub/sub Redis akibat ukuran data HTML yang dikirimkan terlalu masif ke jutaan subscriber. Solusi: Ubah strategi broadcast dari pengiriman HTML lengkap ke pengiriman *lightweight notification signals* (Turbo Refresh signals), dan manfaatkan batching/throttling pada pipeline Redis.
13. **Analisis Kasus 3**: Adanya *detached DOM nodes* dan kegagalan dereferensi objek JavaScript di Stimulus controller. Kemungkinan besar Stimulus controller mendengarkan event via `addEventListener` pada `window`/`document` atau menginisialisasi pustaka visualisasi (*chart*/*tooltip*) tanpa memanggil method destruktor saat Turbo memutasi atau mengganti node tersebut berulang kali.

---

## 16. Summary

- **Modern Rails View Layer** telah berevolusi dari sekadar ERB monolitik menjadi ekosistem berkecepatan tinggi yang menggabungkan kecepatan *server-side rendering* dengan kelancaran antarmuka SPA.
- **Turbo 8 Morphing (Idiomorph)** secara radikal memangkas kebutuhan pembuatan file `.turbo_stream.erb` granular dengan cara memutasi DOM secara cerdas tanpa merusak fokus interaksi pengguna.
- **ViewComponent** membawa disiplin OOP sejati ke dalam rendering antarmuka Rails, memberikan performa render terkompilasi, pemisahan tanggung jawab yang modular via slots, serta kemampuan pengujian unit yang sangat cepat.
- Skalabilitas skala besar ( puluhan hingga ratusan ribu pengguna real-time) dicapai secara efisien dengan memisahkan koneksi WebSocket ke **AnyCable-Go**, menjaga Rails tetap fokus sebagai mesin logika bisnis murni.
- Disiplin penulisan JavaScript pada **Stimulus**—terutama dalam tata kelola siklus hidup `disconnect()` dan penggunaan Outlets API—merupakan kunci mutlak dalam menghindari *memory leak* dan mempertahankan reaktivitas sistem dalam jangka panjang.