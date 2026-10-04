# Bab 04 Module 01: Modern View Layer, Hotwire & ViewComponents

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: `ROR-MOD-0401`
* **Kategori**: `02-Programming-Languages` / `ruby-on-rails`
* **Tingkat Kesulitan**: Advanced / Production-Grade
* **Prasyarat**: 
  * Pemahaman mendalam arsitektur MVC Rails (Routing, Controllers, Active Record).
  * Pemahaman dasar protokol HTTP, DOM API, dan WebSocket.
  * Pengalaman menggunakan Ruby 3.2+ dan Rails 7.1+.
* **Estimasi Waktu Penyelesaian**: 8 – 10 Jam Pembelajaran Mandiri / Praktikum Terpandu.
* **Stack Target**: Ruby 3.3+, Rails 7.2+/8.0, Hotwire (Turbo 8, Stimulus 3), ViewComponent 3+, TailwindCSS.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Mendekonstruksi** arsitektur Hotwire (*HTML-over-the-wire*) dan membedakan siklus hidup Turbo Drive, Turbo Frames, dan Turbo Streams.
2. **Mengimplementasikan** pola Turbo Drive Morphing dan Page Refresh untuk mitigasi *state loss* pada aplikasi berbasis *server-side rendering*.
3. **Merancang** komponen UI modular, teruji (*testable*), dan terisolasi menggunakan gem `view_component`, termasuk pemanfaatan *slots*, *collection rendering*, dan *sidecar assets*.
4. **Membangun** interaktivitas sisi klien (*client-side sprinkles*) menggunakan Stimulus Controllers yang terikat secara deklaratif ke ViewComponents.
5. **Mengorkestrasi** pembaruan UI asinkronus secara *real-time* via WebSocket (Turbo Streams over Action Cable) secara aman dan efisien pada skala produksi.
6. **Mendeteksi dan Memitigasi** *pitfalls* performa, kebocoran memori pada Turbo Drive caching, serta kerentanan keamanan (XSS via broadcasts dan Channel Authorization).

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: Client-Side SPA vs. HTML-Over-The-Wire

Selama satu dekade terakhir, industri web didominasi oleh arsitektur Single Page Application (SPA) yang memisahkan aplikasi menjadi dua entitas: Backend API (JSON) dan Frontend Client (React/Vue/Angular). Arsitektur ini memperkenalkan kompleksitas tinggi: duplikasi validasi, *state synchronization*, fragmentasi *tooling*, dan penurunan performa inisial (*bundle payload bloat*).

```
Paradigma SPA (State Duplication):
[Database] <-> [Active Record] <-> [JSON Serializer] === JSON API ===> [Client Store] <-> [Client Router] <-> [Virtual DOM] <-> [DOM]

Paradigma Hotwire (HTML-Over-The-Wire):
[Database] <-> [Active Record] <-> [ViewComponent / ERB] === HTML Snippets ===> [Turbo / Idiomorph] <-> [Real DOM]
                                                                        ^
                                                      [Stimulus: Micro-behaviors only]
```

Hotwire (HTML-over-the-wire) mengembalikan sumber kebenaran (*single source of truth*) ke server:
1. **Server Mengirim HTML, Bukan JSON**: Server memproses logika domain, hak akses, lokalisasi, dan langsung merender HTML representatif. Klien tidak perlu mengabstraksi ulang data tersebut ke dalam komponen klien.
2. **Progresif & Dekomposisi**: Halaman dimulai sebagai dokumen HTML utuh (Turbo Drive), dibagi menjadi fragmen independen (Turbo Frames), dimutasi secara langsung lintas konteks (Turbo Streams), dan diperkaya oleh perilaku lokal murni (Stimulus).
3. **ViewComponent sebagai Pengganti Helpers/Partials Monolitik**: ERB partial tradisional Rails sulit diuji secara terisolasi, mengotori *namespace* global melalui `ApplicationHelper`, dan memiliki *overhead* performa I/O. `ViewComponent` membawa paradigma OOP murni ke View layer: objek Ruby yang memiliki siklus hidup, tipe data parameter ketat, kapabilitas pengujian unit instan, dan kompilasi cepat.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Siklus Hidup Eksekusi Request: Turbo & ViewComponent

Alur berikut mengilustrasikan bagaimana sebuah interaksi pengguna dieksekusi melalui HTTP POST, diproses oleh Controller dan ViewComponent, lalu dikembalikan ke DOM klien melalui Turbo Stream dan Idiomorph Morphing:

```
[Browser / Klien]                                          [Server Rails]
       │                                                         │
  (1) Klik Submit Form                                           │
       │─── HTTP POST (Accept: text/vnd.turbo-stream.html) ──────>│
       │                                                    (2) Router & Controller
       │                                                         │── Instansiasi Model
       │                                                         │── Simpan Data (DB)
       │                                                         │
       │                                                    (3) View Layer Orchestration
       │                                                         │── Render ViewComponent
       │                                                         │   └── Eksekusi Template
       │                                                         │── Bungkus Turbo Stream
       │<── HTTP 200 (Content-Type: text/vnd.turbo-stream.html)──│
       │
  (4) Turbo Engine Menerima Stream
       │
       ├── Target ID Ditemukan di DOM?
       │     ├── YA ──> (5) Eksekusi Aksi:
       │     │               [append, prepend, replace, update, remove, morph]
       │     │               └── Jika Morph: Menggunakan Idiomorph untuk mutasi
       │     │                   hanya atribut/teks yang berubah (preserve focus/state)
       │     └── TIDAK ─> Abaikan secara aman (silent ignore)
       │
  (6) Stimulus Lifecycle Hooks Dipicu
       │── controller#connect()
       └── Target / Value binding disegarkan
```

### Taksonomi Komponen Hotwire

| Subsistem | Tanggung Jawab Utama | Mekanisme Komunikasi |
| :--- | :--- | :--- |
| **Turbo Drive** | Meniadakan *full page reload*. Mengintersepsi klik `<a>` dan submit `<form>`. | `fetch()` menggantikan navigasi browser standar; melakukan swap pada `<body>`. |
| **Turbo Frames** | Dekomposisi halaman menjadi segmen terisolasi dengan konteks independen. | Mengganti isi elemen `<turbo-frame id="...">` yang cocok antara request dan response. |
| **Turbo Streams** | Mengirim fragmen mutasi DOM secara deterministik ke elemen spesifik. | Protokol aksi HTML (`append`, `prepend`, `replace`, `update`, `remove`, `before`, `after`, `morph`). Mengalir via HTTP response atau WebSocket. |
| **Stimulus** | Menangani interaktivitas UI murni (*state* lokal sementara, animasi, manipulasi DOM kustom). | Mengikat siklus hidup elemen DOM via atribut HTML deklaratif (`data-controller`, `data-action`, `data-target`). |
| **ViewComponent** | Enkapsulasi logika presentasi Ruby ke dalam objek independen yang terstruktur. | Objek murni yang merender HTML ke buffer Rails, menggantikan *Rails Helpers* dan ERB partial monolitik. |

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Turbo Drive & Morphing (Idiomorph)
Pada Turbo 8, pembaruan halaman tidak lagi selalu menggantikan seluruh tag `<body>`. Rails 7.1/8 mengadopsi integrasi pustaka *Idiomorph* untuk Turbo Morphing.
* **Mekanisme**: Ketika Turbo Drive menerima navigasi baru (misal via Turbo Native HTTP redirect setelah mutasi), ia melakukan diff antara DOM pohon saat ini dengan DOM yang baru diterima dari server.
* **Keuntungan**: Elemen `<input>` yang sedang fokus tidak kehilangan status fokusnya, teks yang sedang diketik tidak hilang, posisi *scroll* dipertahankan, dan mutasi DOM hanya terjadi pada node yang mengalami perubahan diferensial.

### 2. Custom Elements Turbo: `<turbo-frame>`
Elemen `<turbo-frame>` adalah Web Component standar (`HTMLElement`).
* Ketika form atau link di dalam `<turbo-frame id="item_1">` diklik, Turbo menambahkan header `Turbo-Frame: item_1` pada request HTTP.
* Controller merespons dengan HTML utuh atau parsial. Turbo mengekstrak konten di dalam `<turbo-frame id="item_1">` pada payload response dan mengabaikan sisa HTML lainnya.
* Komponen ini mengisolasi navigasi: klik link pagination dalam frame hanya mengubah isi frame tersebut tanpa mengganggu bagian luar halaman.

### 3. Struktur Kompilasi ViewComponent
Berbeda dengan ERB partial biasa yang dievaluasi melalui `ActionView::Base#render` (yang membaca disk jika tidak di-cache dan memiliki *overhead* pencarian lookup path), `ViewComponent::Base`:
* Mengkompilasi template ERB sisi-samping (*sidecar*) ke dalam metode Ruby murni (`def call`) pada saat aplikasi melakukan *eager load* (pada mode produksi) atau pada render pertama (pada mode development).
* Semua *helper context* dibatasi secara eksplisit. Komponen tidak otomatis memuat seluruh helper global kecuali diizinkan, mengurangi polusi memori dan mempercepat resolusi variabel secara signifikan.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### A. Turbo Streams: Mutasi DOM Deklaratif
Turbo Streams mendefinisikan protokol berbasis markup untuk memanipulasi struktur DOM browser tanpa menuliskan satu baris JavaScript pun.

Struktur standar elemen Turbo Stream:
```html
<turbo-stream action="replace" target="task_123">
  <template>
    <div id="task_123" class="p-4 bg-green-50 border border-green-200">
      Task Selesai: Mengoptimalkan Database
    </div>
  </template>
</turbo-stream>
```

Aksi-aksi yang didukung:
1. `append`: Menambahkan konten ke akhir elemen target.
2. `prepend`: Menambahkan konten ke awal elemen target.
3. `replace`: Menggantikan seluruh node target dengan konten di dalam `<template>`.
4. `update`: Mengosongkan isi elemen target dan mengisinya dengan konten baru (node target dipertahankan).
5. `remove`: Menghapus node target dari DOM (tidak memerlukan `<template>`).
6. `before`: Menyisipkan konten persis sebelum node target.
7. `after`: Menyisipkan konten persis setelah node target.
8. `morph` (Turbo 8+): Mengubah target menggunakan algoritma diffing rekursif Idiomorph.

### B. Arsitektur ViewComponent: Encapsulation & Slots
Pemisahan tanggung jawab dalam ViewComponent membagi logika presentasi kompleks ke dalam arsitektur berbasis objek:

* **Inisialisasi**: Semua ketergantungan didefinisikan secara eksplisit melalui `initialize`. Parameter opsional, tipe data, dan nilai *default* diverifikasi di level Ruby.
* **Slots (Komposisi)**: Komponen dapat menerima fragmen UI lain melalui konsep `renders_one` dan `renders_many`. Ini memungkinkan pembuatan komponen komposit yang fleksibel (seperti Card dengan Header, Body, dan Footer terpisah) tanpa mengorbankan enkapsulasi.

### C. Stimulus: Life-cycle & Event Delegation
Stimulus beroperasi di atas pola *mutation-observer*. Komponen JS Stimulus memantau penambahan atau penghapusan elemen pada DOM secara dinamis.

* `connect()`: Dipanggil setiap kali controller diikat ke elemen di DOM (termasuk setelah disisipkan oleh Turbo Stream atau Turbo Frame).
* `disconnect()`: Dipanggil saat elemen target dilepaskan dari DOM (memungkinkan pembersihan event listeners eksternal untuk mencegah *memory leaks*).
* `Action Binding`: Stimulus menggunakan delegasi event modern pada `window` atau target level elemen menggunakan format:
  `data-action="event->controller-name#methodName"`.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi end-to-end fitur manajemen item daftar belanja interaktif dengan *inline edit* dan validasi instan menggunakan Turbo Frame, Turbo Stream, ViewComponent, dan Stimulus.

### 1. ViewComponent: Item Component
File: `app/components/shopping_item_component.rb`
```ruby
# frozen_string_literal: true

class ShoppingItemComponent < ViewComponent::Base
  with_collection_parameter :item

  attr_reader :item

  def initialize(item:)
    super
    @item = item
  end

  def item_status_class
    item.completed? ? "line-through text-slate-400" : "text-slate-800"
  end
end
```

File: `app/components/shopping_item_component.html.erb`
```erb
<%= turbo_frame_tag dom_id(item) do %>
  <div class="flex items-center justify-between p-3 border-b border-slate-100 hover:bg-slate-50 transition-colors">
    <div class="flex items-center space-x-3">
      <%= button_to toggle_item_path(item), 
                    method: :patch, 
                    class: "w-5 h-5 rounded border border-slate-300 flex items-center justify-center text-indigo-600 focus:ring-indigo-500" do %>
        <%= item.completed? ? "✓" : "" %>
      <% end %>
      <span class="<%= item_status_class %> font-medium text-sm">
        <%= item.name %> (<%= item.quantity %>)
      </span>
    </div>
    
    <div class="flex items-center space-x-2">
      <%= link_to "Edit", edit_item_path(item), class: "text-xs text-blue-600 hover:underline" %>
      <%= button_to "Hapus", item_path(item), method: :delete, class: "text-xs text-rose-600 hover:underline" %>
    </div>
  </div>
<% end %>
```

### 2. Form Edit Component (Turbo Frame Target)
File: `app/views/items/edit.html.erb`
```erb
<%= turbo_frame_tag dom_id(@item) do %>
  <%= form_with(model: @item, class: "p-3 bg-indigo-50 rounded flex items-center space-x-2") do |f| %>
    <%= f.text_field :name, class: "text-sm rounded border-slate-300 px-2 py-1 flex-grow" %>
    <%= f.number_field :quantity, class: "text-sm rounded border-slate-300 px-2 py-1 w-20" %>
    <%= f.submit "Simpan", class: "text-xs px-3 py-1 bg-indigo-600 text-white rounded cursor-pointer" %>
    <%= link_to "Batal", item_path(@item), class: "text-xs text-slate-500 hover:underline" %>
  <% end %>
<% end %>
```

### 3. Controller Actions dengan Turbo Stream
File: `app/controllers/items_controller.rb`
```ruby
# frozen_string_literal: true

class ItemsController < ApplicationController
  before_action :set_item, only: %i[show edit update destroy toggle]

  def index
    @items = Item.order(created_at: :desc)
    @new_item = Item.new
  end

  def create
    @item = Item.new(item_params)

    if @item.save
      respond_to do |format|
        format.turbo_stream
        format.html { redirect_to items_path, notice: "Item berhasil dibuat." }
      end
    else
      render :new, status: :unprocessable_entity
    end
  end

  def update
    if @item.update(item_params)
      respond_to do |format|
        format.turbo_stream
        format.html { redirect_to items_path }
      end
    else
      render :edit, status: :unprocessable_entity
    end
  end

  def toggle
    @item.update(completed: !@item.completed)
    respond_to do |format|
      format.turbo_stream { render turbo_stream: turbo_stream.replace(@item, ShoppingItemComponent.new(item: @item)) }
      format.html { redirect_to items_path }
    end
  end

  def destroy
    @item.destroy
    respond_to do |format|
      format.turbo_stream { render turbo_stream: turbo_stream.remove(@item) }
      format.html { redirect_to items_path }
    end
  end

  private

  def set_item
    @item = Item.find(params[:id])
  end

  def item_params
    params.require(:item).permit(:name, :quantity, :completed)
  end
end
```

File: `app/views/items/create.turbo_stream.erb`
```erb
<%= turbo_stream.prepend "items_list", ShoppingItemComponent.new(item: @item) %>
<%= turbo_stream.update "new_item_form", partial: "form", locals: { item: Item.new } %>
<%= turbo_stream.update "flash_messages" do %>
  <div class="p-2 text-sm text-green-700 bg-green-100 rounded">Item berhasil ditambahkan!</div>
<% end %>
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi teknis terhadap implementasi di Seksi 07:

1. **`with_collection_parameter :item`** (`shopping_item_component.rb:4`):
   * Menginstruksikan `ViewComponent` untuk mendukung rendering koleksi efisien melalui `render ShoppingItemComponent.with_collection(@items)`. Rails memotong overhead iterasi manual dan mengoptimalkan buffer render.
2. **`<%= turbo_frame_tag dom_id(item) do %>`** (`shopping_item_component.html.erb:1`):
   * Menggenerasikan `<turbo-frame id="item_42">`. Saat pengguna mengklik link "Edit", request HTTP secara otomatis membawa header `Turbo-Frame: item_42`. 
   * Server merender `items/edit.html.erb`, dan Turbo hanya mengekstrak konten di dalam `<turbo-frame id="item_42">`, menggantikan representasi tampilan komponen menjadi form edit tanpa me-reload sisa antarmuka.
3. **`format.turbo_stream { render turbo_stream: turbo_stream.replace(@item, ...) }`** (`items_controller.rb:39`):
   * Memanfaatkan helper `dom_id(@item)` secara implisit sebagai target.
   * Merender instance `ShoppingItemComponent` langsung ke dalam pipeline respons Turbo Stream tanpa memerlukan file template `.turbo_stream.erb` terpisah untuk aksi mutasi tunggal yang ringkas.
4. **`<%= turbo_stream.prepend "items_list", ShoppingItemComponent.new(item: @item) %>`** (`create.turbo_stream.erb:1`):
   * Menghasilkan payload `<turbo-stream action="prepend" target="items_list">`.
   * Turbo JavaScript Engine di browser menemukan elemen `<div id="items_list">` dan menyisipkan hasil kompilasi HTML dari `ShoppingItemComponent` pada indeks pertama DOM child target.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Real-time Multi-User Collaborative Kanban / Incident Command System

**Konteks**: Sistem Operasional Darurat (Incident Command System) di mana berbagai tim responder (Polisi, Medis, Pemadam) memperbarui status insiden, tingkat keparahan (*severity*), dan log penanganan secara simultan.

**Masalah Arsitektural**:
1. Pembaruan yang dilakukan Responder A harus muncul di layar Responder B secara seketika (*real-time*) tanpa mendistorsi form yang sedang diisi oleh Responder B.
2. Komponen kartu insiden memiliki logika visual yang rumit (penghitungan durasi SLA, level status, daftar penanggung jawab, badging dinamis). Menempatkannya di Rails Helpers menyebabkan polusi kode dan sulit diuji secara komprehensif.
3. Jika menggunakan SPA konvensional, latensi initial load tinggi dan sinkronisasi status model insiden yang rumit memerlukan state management kompleks (Redux/Zustand) yang berlebih.

**Solusi Terpilih**:
* Arsitektur **Hotwire Turbo Streams over Action Cable** untuk broadcast multi-user secara real-time.
* Penerapan **ViewComponents dengan sub-slots** untuk memecah UI insiden menjadi unit yang modular dan dapat diuji secara terisolasi.
* **Stimulus Controller** untuk mengelola interaksi drag-and-drop antar kolom kanban dan penanganan optimistik visual sebelum konfirmasi server.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

### 1. Model & Model Broadcasts
File: `app/models/incident.rb`
```ruby
# frozen_string_literal: true

class Incident < ApplicationRecord
  enum :status, { open: 0, investigating: 1, mitigated: 2, resolved: 3 }
  enum :severity, { low: 0, medium: 1, high: 2, critical: 3 }

  validates :title, presence: true, length: { minimum: 5 }
  validates :severity, presence: true

  # Turbo Stream Broadcasts secara otomatis via WebSocket setelah transaksi DB komit
  after_create_commit -> { broadcast_prepend_to "incidents_channel", target: "incident_cards_list", html: render_component }
  after_update_commit -> { broadcast_replace_to "incidents_channel", target: self, html: render_component }
  after_destroy_commit -> { broadcast_remove_to "incidents_channel", target: self }

  private

  def render_component
    ApplicationController.render(
      IncidentCardComponent.new(incident: self),
      layout: false
    )
  end
end
```

### 2. ViewComponent dengan Slots & Presentational Logic
File: `app/components/incident_card_component.rb`
```ruby
# frozen_string_literal: true

class IncidentCardComponent < ViewComponent::Base
  renders_one :action_menu
  renders_many :responders

  attr_reader :incident

  def initialize(incident:)
    super
    @incident = incident
  end

  def severity_badge_classes
    case incident.severity.to_sym
    when :critical
      "bg-rose-100 text-rose-800 border-rose-300 animate-pulse"
    when :high
      "bg-orange-100 text-orange-800 border-orange-300"
    when :medium
      "bg-yellow-100 text-yellow-800 border-yellow-300"
    else
      "bg-slate-100 text-slate-700 border-slate-300"
    end
  end

  def sla_time_remaining
    deadline = incident.created_at + 4.hours
    if Time.current > deadline
      "SLA Breached"
    else
      "#{((deadline - Time.current) / 60).to_i} menit tersisa"
    end
  end
end
```

File: `app/components/incident_card_component.html.erb`
```erb
<div id="<%= dom_id(incident) %>" 
     class="p-4 bg-white rounded-lg shadow-sm border border-slate-200 transition-all duration-200 hover:shadow-md mb-3"
     data-controller="incident-card"
     data-incident-card-status-value="<%= incident.status %>">
  
  <div class="flex items-start justify-between">
    <div>
      <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold border <%= severity_badge_classes %>">
        <%= incident.severity.upcase %>
      </span>
      <span class="text-xs text-slate-500 ml-2"><%= sla_time_remaining %></span>
    </div>
    
    <% if action_menu? %>
      <div class="relative">
        <%= action_menu %>
      </div>
    <% end %>
  </div>

  <h3 class="text-base font-bold text-slate-900 mt-2 mb-1">
    <%= incident.title %>
  </h3>

  <div class="flex items-center justify-between text-xs text-slate-500 mt-3 pt-3 border-t border-slate-100">
    <div class="flex items-center space-x-1">
      <% responders.each do |responder| %>
        <%= responder %>
      <% end %>
    </div>
    
    <span class="font-mono bg-slate-100 px-2 py-0.5 rounded text-[10px]">
      <%= incident.status.humanize %>
    </span>
  </div>
</div>
```

### 3. Stimulus Controller untuk Interaktivitas UI
File: `app/javascript/controllers/incident_card_controller.js`
```javascript
import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  static values = { 
    status: String 
  }

  connect() {
    this.applyStatusStyling()
  }

  statusValueChanged(newStatus, oldStatus) {
    if (oldStatus !== undefined) {
      this.flashHighlight()
    }
  }

  flashHighlight() {
    this.element.classList.add("ring-2", "ring-indigo-500", "transition-all")
    setTimeout(() => {
      this.element.classList.remove("ring-2", "ring-indigo-500")
    }, 1200)
  }

  applyStatusStyling() {
    if (this.statusValue === "resolved") {
      this.element.classList.add("opacity-60", "bg-slate-50")
    }
  }
}
```

### 4. Controller & Global Subscription View
File: `app/controllers/incidents_controller.rb`
```ruby
# frozen_string_literal: true

class IncidentsController < ApplicationController
  def index
    @incidents = Incident.order(created_at: :desc)
  end

  def update_status
    @incident = Incident.find(params[:id])
    if @incident.update(status: params[:status])
      head :ok
    else
      head :unprocessable_entity
    end
  end
end
```

File: `app/views/incidents/index.html.erb`
```erb
<div class="max-w-5xl mx-auto py-8 px-4">
  <div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-black text-slate-900">Incident Command Center</h1>
    <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800">
      ● WebSocket Connected
    </span>
  </div>

  <!-- Berlangganan ke stream Turbo melalui Action Cable -->
  <%= turbo_stream_from "incidents_channel" %>

  <div id="incident_cards_list" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
    <% @incidents.each do |incident| %>
      <%= render(IncidentCardComponent.new(incident: incident)) do |component| %>
        <% component.with_action_menu do %>
          <%= link_to "Tindak Lanjut", "#", class: "text-xs text-indigo-600 font-semibold" %>
        <% end %>
      <% end %>
    <% end %>
  </div>
</div>
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Kriteria / Skenario | Modern Rails View (Hotwire + ViewComponent) | Single Page Application (React / Next.js + API) | Classic Rails (ERB + Turbolinks + JQuery) |
| :--- | :--- | :--- | :--- |
| **Kecepatan Development (TMM - Time to Market)** | **Sangat Cepat**: Menggunakan model Rails langsung tanpa menulis lapisan serialisasi JSON. | **Lambat**: Memerlukan sinkronisasi schema, API contracts (OpenAPI), dan endpoint ganda. | **Cepat**: Namun arsitektur JS cenderung menjadi spaghetti (*unstructured*). |
| **Overhead Bundle JavaScript** | **Minimal (~30-50KB)**: Turbo dan Stimulus memiliki ukuran payload yang sangat ringan. | **Tinggi (300KB - 2MB+)**: Runtime React, state library, build system, dan dependensi npm. | **Sedang**: Bergantung pada ukuran pustaka script manual yang dipasang. |
| **Latensi Respons Interaksi (First Interaction)** | **Instan**: HTML dikirim langsung dari server dengan optimasi rendering cache. | **Tertunda**: Browser harus mengunduh runtime JS, mengeksekusi script, lalu memanggil API JSON. | **Instan**: Namun visual seringkali *flicker* karena full/partial reload kasar. |
| **Offline Mode & State Klien Kompleks** | **Terbatas**: Tidak dirancang untuk aplikasi offline murni (*offline-first*). | **Unggul**: Service Worker dan local storage terintegrasi secara modular pada level runtime JS. | **Sangat Buruk**: Sangat bergantung pada koneksi server aktif di tiap interaksi. |
| **Testing Overhead** | **Rendah & Sangat Cepat**: ViewComponent dapat diuji menggunakan *Ruby Unit Tests* biasa tanpa browser headless. | **Tinggi**: Memerlukan Jest/Vitest, Mock API Server, Cypress/Playwright untuk integrasi. | **Tinggi**: Mengandalkan System/Feature Tests yang lambat karena rendering berbasis browser. |
| **Konsumsi Memori Server** | **Moderat - Tinggi**: Merender HTML di server memerlukan siklus CPU Ruby dan alokasi string buffer. | **Rendah**: Server hanya mengembalikan JSON mentah yang sangat ringan diproses oleh CPU. | **Moderat**: Mirip Hotwire, namun kurang optimal tanpa ViewComponent caching. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. State Duplication pada Turbo Drive Navigation Cache
* **Perilaku Masalah**: Turbo Drive menyimpan snapshot dokumen HTML di memori klien sebelum navigasi untuk ditampilkan secara instan (*preview mode*) saat tombol "Back" ditekan. Jika halaman memiliki komponen interaktif yang mengubah DOM (misal form modal terbuka atau grafik canvas ter-render), snapshot tersebut menyimpan state sementara yang rusak (*stale*).
* **Solusi**: Bersihkan DOM sebelum Turbo melakukan caching:
  ```javascript
  document.addEventListener("turbo:before-cache", () => {
    // Reset state modal atau tutup dropdown
    document.querySelectorAll(".dropdown-menu").forEach(el => el.classList.add("hidden"))
  })
  ```
  Atau gunakan meta tag untuk menonaktifkan cache pada halaman tertentu:
  ```erb
  <% content_for :head do %>
    <meta name="turbo-cache-control" content="no-cache">
  <% end %>
  ```

### 2. WebSocket Broadcast Concurrency & Race Conditions
* **Perilaku Masalah**: Menggunakan `after_commit -> { broadcast_replace_to ... }` pada Active Record dapat menimbulkan race condition jika operasi broadcast lambat dan request HTTP klien berikutnya selesai lebih dulu sebelum frame broadcast sampai ke browser target.
* **Solusi**: Gunakan transaksi database yang terkapsulasi secara ketat dan pastikan rendering broadcast dialihkan ke background worker pool menggunakan:
  ```ruby
  after_commit -> { broadcast_replace_later_to "incidents_channel", ... }
  ```
  Metode `_later` mendelegasikan proses rendering komponen dan transmisi WebSocket ke *Solid Queue* atau *Sidekiq*, mencegah proses HTTP request worker Rails terblokir.

### 3. Nested `<turbo-frame>` Form Submission Trap
* **Perilaku Masalah**: Jika Anda menempatkan form di dalam frame yang bersarang (*nested frame*), Turbo secara *default* mencari respon dengan ID frame terdalam. Jika respon server bermaksud memperbarui frame terluar atau halaman secara menyeluruh, aplikasi akan tampak macet (*frame missing* error).
* **Solusi**: Nyatakan target frame secara eksplisit menggunakan atribut `data-turbo-frame`:
  ```erb
  <%= form_with model: @incident, data: { turbo_frame: "_top" } do |f| %>
    <!-- Memaksa pembaruan ke tingkat root document, bukan frame saat ini -->
  <% end %>
  ```

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Memperlakukan Stimulus Seperti Komponen React
* **Kesalahan**: Menyimpan *state* bisnis inti dan merender struktur HTML besar melalui string template JavaScript di dalam file Controller Stimulus.
* **Koreksi**: Stimulus dirancang sebagai *progressive enhancement*. Server tetap bertanggung jawab membangun markup HTML via Rails/ViewComponent. Stimulus hanya menambahkan perilaku (misal: toggle visibility kelas CSS, mendengarkan keyboard shortcut, menginisialisasi pustaka pihak ketiga seperti Pikaday).

### 2. Inkonsistensi Target ID pada Turbo Stream
* **Kesalahan**: Menggunakan string arbitrer yang tidak tersinkronisasi antara target DOM dan stream action:
  ```erb
  <!-- View Template -->
  <div id="incident-<%= incident.id %>">...</div>
  
  <!-- Turbo Broadcast Server -->
  turbo_stream.replace(dom_id(incident)) # Menghasilkan target: "incident_123" (Menggunakan underscore!)
  ```
* **Koreksi**: Wajib selalu menggunakan Rails helper `dom_id(record)` secara konsisten di seluruh ViewComponent, ERB partial, dan Turbo Stream invocation.

### 3. Lupa Mengompilasi Sidecar Asset pada ViewComponent
* **Kesalahan**: Membuat file `incident_card_component.js` tepat di samping komponen tanpa mendaftarkannya pada konfigurasi Asset Pipeline / Importmap / Esbuild.
* **Koreksi**: Konfigurasi path manifest agar memindai folder `app/components`:
  ```javascript
  // app/javascript/controllers/index.js
  import { application } from "./application"
  import { registerControllersFrom } from "@hotwired/stimulus-loading"
  registerControllersFrom("components", application)
  ```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

### 1. Desain Granularitas Komponen ViewComponent
* Terapkan prinsip *Single Responsibility*. Pecah komponen besar menjadi atomik:
  * `Incident::BadgeComponent`
  * `Incident::RowComponent`
  * `Incident::TimelineComponent`
* Simpan komponen domain di dalam namespace yang merefleksikan model: letakkan di `app/components/incident/card_component.rb` alih-alih `app/components/incident_card_component.rb` jika aplikasi memiliki ratusan entitas view.

### 2. Standarisasi Turbo Frame Targeting
* Selalu tetapkan fallback behavior: Jika sebuah request dari turbo frame mungkin merespons dengan pengalihan (*redirect*) ke luar alur kerja biasa (misal: sesi login habis), pastikan server merespons dengan header `Turbo-Location` alih-alih HTTP 302 standar untuk memaksa Turbo Drive menavigasi frame terluar.

### 3. Penggunaan Stimulus Values API secara Ketat
* Jangan membaca konfigurasi dari atribut HTML secara manual via `element.getAttribute("data-value")`. Gunakan sistem *Values API* Stimulus yang menyediakan *type casting* otomatis dan *change callbacks*:
  ```javascript
  export default class extends Controller {
    static values = { 
      threshold: { type: Number, default: 10 },
      active: { type: Boolean, default: false }
    }
  }
  ```

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. ViewComponent Collection Rendering vs ERB Loops
Jangan melakukan iterasi manual pada komponen jika Anda memiliki banyak baris data:

* **Pola Buruk (Lambat)**:
  ```erb
  <% @incidents.each do |incident| %>
    <%= render IncidentCardComponent.new(incident: incident) %>
  <% end %>
  ```
* **Pola Optimal (Sangat Cepat)**:
  ```erb
  <%= render IncidentCardComponent.with_collection(@incidents) %>
  ```
  *Mekanisme*: `with_collection` menggunakan metode kompilasi batch internal `ViewComponent`. Pengujian performa benchmark menunjukkan peningkatan *rendering throughput* hingga 300% dibanding loop ERB standar karena bypassing evaluasi method missing ActionView berulang-ulang.

### 2. Russian Doll Caching Terintegrasi dengan ViewComponent
Manfaatkan kapabilitas caching Rails langsung pada komponen:

```ruby
class IncidentCardComponent < ViewComponent::Base
  def initialize(incident:)
    super
    @incident = incident
  end

  def cache_key
    "incident_card/#{incident.id}-#{incident.updated_at.to_fs(:usec)}"
  end
end
```
Dalam template:
```erb
<% cache component.cache_key do %>
  <!-- HTML Markup di-cache langsung di Redis/Solid Cache -->
<% end %>
```

---

## SEKSI 16 — KEAMANAN & HARDENING

### 1. Mitigasi Turbo Stream XSS Injection via WebSockets
* Saat menyiarkan Turbo Streams ke saluran Action Cable publik, seluruh pengguna yang mendengarkan channel tersebut akan menerima markup yang dikirim.
* **Aturan**: Jangan pernah merender input pengguna yang belum disanitasi ke dalam template broadcast:
  ```ruby
  # SANGAT BERBAHAYA
  turbo_stream.append("messages", "<div>#{params[:unsafe_user_input]}</div>".html_safe)

  # AMAN: Gunakan ViewComponent / ERB yang melakukan auto-escaping
  turbo_stream.append("messages", MessageComponent.new(message: @message))
  ```

### 2. Otorisasi Akses Saluran Action Cable (Stream Scoping)
* Jangan membuat channel broadcast yang dapat disubscribe secara global tanpa pengecekan authorization:
  ```erb
  <!-- SALAH: Siapapun bisa mendengarkan channel insiden rahasia -->
  <%= turbo_stream_from "all_incidents" %>

  <!-- BENAR: Enkripsi dan scope channel berdasarkan ID organisasi/akses user -->
  <%= turbo_stream_from current_user.organization, "incidents" %>
  ```
* Di sisi model:
  ```ruby
  class Incident < ApplicationRecord
    belongs_to :organization
    after_create_commit -> {
      broadcast_prepend_to [organization, "incidents"], 
                           target: "incident_cards_list",
                           html: ApplicationController.render(IncidentCardComponent.new(incident: self), layout: false)
    }
  end
  ```

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### 1. Logging Event Turbo di Sisi Klien
Untuk menganalisis siklus request-response Turbo yang gagal atau tidak melakukan penggantian frame seperti yang diharapkan, pasang telemetry listener di console:

```javascript
// app/javascript/application.js
if (process.env.NODE_ENV === "development") {
  const events = [
    "turbo:before-visit",
    "turbo:visit",
    "turbo:submit-start",
    "turbo:before-fetch-request",
    "turbo:before-fetch-response",
    "turbo:before-frame-render",
    "turbo:frame-render",
    "turbo:render"
  ]

  events.forEach(eventName => {
    document.addEventListener(eventName, (e) => {
      console.log(`[TURBO EVENT] ${eventName}:`, e.detail)
    })
  })
}
```

### 2. Unit Testing ViewComponent secara Terisolasi
Salah satu keunggulan terbesar `ViewComponent` adalah kemampuan pengujian unit tanpa menjalankan integration test / Capybara yang lambat.

File: `spec/components/incident_card_component_spec.rb`
```ruby
# frozen_string_literal: true

require "rails_helper"

RSpec.describe IncidentCardComponent, type: :component do
  it "merender badge critical dengan animasi pulse" do
    incident = build(:incident, title: "Database Kebakaran", severity: :critical)
    
    render_inline(described_class.new(incident: incident))

    expect(page).to have_text("Database Kebakaran")
    expect(page).to have_css(".animate-pulse")
    expect(page).to have_text("CRITICAL")
  end

  it "merender slot menu aksi jika disediakan" do
    incident = build(:incident)

    render_inline(described_class.new(incident: incident)) do |component|
      component.with_action_menu { "<button id='btn-test'>Aksi</button>".html_safe }
    end

    expect(page).to have_css("#btn-test", text: "Aksi")
  end
end
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

### Turbo HTML Attributes
* `data-turbo="false"`: Menonaktifkan Turbo Drive pada anchor tag `<a>` atau `<form>` tertentu.
* `data-turbo-frame="_top"`: Memaksa link/form di dalam `<turbo-frame>` menavigasi seluruh halaman.
* `data-turbo-action="advance|replace"`: Mengatur apakah navigasi frame harus memanipulasi *History API* browser.
* `data-turbo-permanent`: Menjaga elemen agar tidak dimutasi saat Turbo Drive melakukan page swap (berguna untuk audio player, sidebar scroll position).

### Stimulus Syntax Cheat Sheet
* `data-controller="nama-file"`: Mengikat file controller (`nama_file_controller.js`).
* `data-nama-file-target="namaTarget"`: Mengikat elemen ke properti `this.namaTargetTarget`.
* `data-action="click->nama-file#namaMetode"`: Menghubungkan event DOM ke method controller.
* `data-nama-file-param-id="123"`: Mengirim parameter ke method action (`event.params.id`).

### ViewComponent Command Matrix
* Generate Component: `bin/rails generate component ComponentName param1 param2`
* Render via Controller: `render(MyComponent.new(param: @val))`
* Render Collection: `render(MyComponent.with_collection(@items))`

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

Pilihlah satu jawaban yang paling tepat, lalu cocokkan dengan kunci interpretasi di bawah.

### Tingkat Dasar (Basic)

**Soal 1:** Apa perbedaan mendasar antara Turbo Drive dan Turbolinks generasi lama?
A. Turbo Drive hanya bekerja pada aplikasi mobile native.  
B. Turbo Drive mendukung form submissions via `fetch()`, integrasi Morphing (Idiomorph), dan custom elements `<turbo-frame>`.  
C. Turbo Drive membatasi aplikasi hanya boleh menggunakan JSON API.  
D. Turbo Drive tidak lagi mendukung intercept klik tautan `<a>`.  

**Soal 2:** Ketika sebuah request dikirim dari dalam `<turbo-frame id="user_profile">`, apa yang diharapkan Turbo dari response server?
A. Server wajib mengembalikan respons kosong berstatus 204 No Content.  
B. Server harus mengembalikan JSON array dengan struktur serializer tertentu.  
C. Server harus mengembalikan HTML yang setidaknya memiliki elemen `<turbo-frame id="user_profile">` yang cocok.  
D. Server wajib melakukan redirect 301 ke endpoint root.  

**Soal 3:** Manakah aksi Turbo Stream yang digunakan untuk menghapus elemen dari DOM tanpa membutuhkan tag `<template>`?
A. `clear`  
B. `remove`  
C. `destroy`  
D. `drop`  

**Soal 4:** Di mana lokasi siklus hidup Stimulus JavaScript yang paling tepat untuk menginisialisasi plugin pihak ketiga (seperti date picker) pada suatu elemen?
A. `initialize()`  
B. `connect()`  
C. `render()`  
D. `mounted()`  

**Soal 5:** Mengapa `ViewComponent` menawarkan performa render yang lebih tinggi dibanding Rails ERB Partials konvensional?
A. ViewComponent tidak menggunakan CPU server untuk rendering.  
B. ViewComponent secara otomatis mengonversi kode Ruby ke WebAssembly.  
C. ViewComponent dikompilasi menjadi metode Ruby murni yang terisolasi tanpa overhead lookup path ActionView berulang.  
D. ViewComponent berjalan di thread terpisah pada background worker.  

---

### Tingkat Menengah (Intermediate)

**Soal 6:** Anda memiliki halaman detail produk. Pengguna menekan tombol "Tambah Komentar" di dalam Turbo Frame. Respon berhasil disimpan, namun Anda ingin memperbarui indikator total keranjang belanja yang berada di luar Turbo Frame tersebut secara bersamaan. Apa pendekatan paling idiomatik dalam Hotwire?
A. Menggunakan Stimulus controller untuk melakukan window reload utuh.  
B. Mengembalikan respons dengan `Content-Type: text/vnd.turbo-stream.html` yang berisi aksi stream untuk memperbarui frame komentar DAN aksi stream terpisah yang menargetkan badge keranjang.  
C. Membungkus seluruh dokumen aplikasi dari `<body>` ke dalam satu Turbo Frame raksasa.  
D. Menembakkan alert JavaScript dari server.  

**Soal 7:** Apa implikasi penggunaan `after_commit -> { broadcast_replace_to ... }` pada Model Rails di lingkungan produksi bertrafik tinggi, dan bagaimana solusinya?
A. Model akan deadlock; solusinya adalah menghapus Active Record callbacks.  
B. Rendering HTML di dalam model callback dapat memblokir worker thread web server; solusinya adalah beralih ke `broadcast_replace_later_to` untuk pemrosesan asinkron via background job.  
C. WebSocket tidak mendukung format string HTML; solusinya adalah broadcast JSON.  
D. Turbo Stream Action Cable tidak mendukung enkripsi TLS; solusinya adalah polling HTTP.  

**Soal 8:** Perhatikan skenario ini: Input teks pencarian live filter kehilangan kursor fokus setiap kali hasil pencarian diperbarui oleh Turbo Drive. Mekanisme apa di Turbo 8 yang dirancang untuk mengatasi masalah ini?
A. Session Storage Caching.  
B. Turbo Page Morphing menggunakan Idiomorph diffing engine.  
C. Stimulus Debounce Controller manual.  
D. Full document swap.  

**Soal 9:** Kapan Anda harus menggunakan Stimulus `Values API` dengan change callbacks daripada mendengarkan event manual via `addEventListener`?
A. Ketika ingin memantau perubahan atribut data HTML secara reaktif dan otomatis menjalankan logic tertentu tanpa menulis MutationObserver manual.  
B. Hanya ketika memproses form submit.  
C. Hanya ketika berinteraksi dengan API eksternal REST.  
D. Values API sudah usang dan digantikan oleh Redux store.  

**Soal 10:** Di dalam sebuah objek `ViewComponent`, Anda ingin menggunakan helper Rails seperti `image_tag` atau `time_ago_in_words`. Bagaimana cara terbaik mengaksesnya jika helper tersebut tidak tersedia secara langsung?
A. Helpers tersebut tidak pernah bisa digunakan di dalam ViewComponent.  
B. Mengaksesnya secara eksplisit melalui method proxy `helpers.image_tag` atau menyertakan module helper terkait menggunakan `include ActionView::Helpers::DateHelper`.  
C. Memanggil `ApplicationController.new.image_tag`.  
D. Menulis ulang implementasi method tersebut secara manual di dalam komponen.  

---

### Kunci Jawaban & Evaluasi

1. **B** — Turbo Drive memperluas Turbolinks dengan kemampuan submit form via fetch, custom elements, dan integrasi Turbo Morphing.
2. **C** — Turbo mengisolasi rendering frame dan mencocokkan ID tag frame yang sama antara permintaan dan payload response.
3. **B** — Aksi `remove` hanya membutuhkan atribut `target`, tanpa pembungkus `<template>` karena tidak ada node baru yang disisipkan.
4. **B** — `connect()` dipanggil setiap kali elemen memasuki DOM, memastikan pustaka eksternal terpasang sempurna bahkan setelah swap Turbo.
5. **C** — Berbeda dengan dynamic path lookup ERB, ViewComponent dikompilasi langsung menjadi method Ruby biasa pada memori kelas.
6. **B** — Turbo Streams dirancang khusus untuk memutasi beberapa segmen DOM yang terpisah secara bebas dalam satu siklus response HTTP.
7. **B** — `broadcast_*_later_to` mengabstraksikan rendering ke sistem antrean (ActiveJob/Sidekiq), menjaga respon HTTP request tetap responsif.
8. **B** — Turbo Morphing melakukan patch diferensial pada node DOM sehingga elemen input aktif mempertahankan fokus kursornya.
9. **A** — Stimulus Values API mengotomatisasi parsing tipe data dan memicu hook callback (`[name]ValueChanged`) seketika atribut HTML termutasi.
10. **B** — ViewComponent mengisolasi namespace view, namun menyediakan helper context aman via accessor `helpers`.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Mini Project: Real-Time E-Commerce Dynamic Cart & Inventory Watcher

#### Deskripsi
Bangun antarmuka katalog produk mini di mana pengguna dapat mengelola keranjang secara asinkronus, melihat ketersediaan stok produk yang berkurang secara *real-time* saat dibeli pengguna lain via WebSocket, dan form pemesanan yang tervalidasi seketika tanpa reload halaman.

#### Spesifikasi Fungsional:
1. **Daftar Produk (ViewComponent + Slots)**:
   * Buat `ProductCardComponent` yang memiliki slot untuk:
     * `badge` status (misal: "Stok Menipis").
     * `actions` (tombol Add to Cart).
   * Gunakan `render ProductCardComponent.with_collection(@products)`.
2. **Live Counter & Optimistic UI (Stimulus)**:
   * Buat `cart_controller.js`. Saat tombol "Beli" diklik:
     * Tambahkan animasi indikator loading pada tombol secara lokal seketika.
     * Kirim POST request via Turbo Frame atau Stimulus Fetch API.
3. **Multi-Tab / Multi-User Inventory Broadcast (Turbo Streams over Action Cable)**:
   * Ketika seorang pengguna berhasil membeli produk, model `Product` menyiarkan Turbo Stream broadcast:
     * Mengurangi jumlah stok yang tampil pada katalog di layar pengguna lain yang sedang membuka halaman tersebut secara *real-time*.
     * Jika stok = 0, ubah tombol secara otomatis menjadi disabled ("Stok Habis") melalui Turbo Stream `replace`.
4. **Slide-over Cart Drawer (Turbo Frame)**:
   * Keranjang belanja berada di dalam layout utama, dibungkus `<turbo-frame id="cart_drawer">`.
   * Update quantity item di dalam cart drawer mengkalkulasi ulang *Subtotal* secara instan via Turbo Streams.

#### Acceptance Criteria:
* Pengujian unit `ProductCardComponent` menggunakan RSpec memiliki coverage 100% untuk kondisi *in-stock* vs *out-of-stock*.
* Tidak ada error `Turbo-Frame Missing` di browser console.
* Tidak terjadi *full page refresh* pada setiap interaksi pengguna (dibuktikan dengan status koneksi WebSocket yang tidak terputus).
* Kode mematuhi styling RuboCop Rails dan strict linting.