# Bab 08 Module 01: HTTP Protocol & REST API Fundamentals

## Kurikulum: Backend Beginner | Kategori: 01-Core-Foundations

---

## SECTION 01 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik mampu:

1. **Menjelaskan** cara kerja protokol HTTP sebagai fondasi komunikasi web modern
2. **Membedakan** HTTP methods (GET, POST, PUT, PATCH, DELETE) dan penggunaan yang tepat
3. **Menginterpretasikan** HTTP status codes dan maknanya dalam konteks API response
4. **Memahami** anatomi HTTP Request dan HTTP Response secara menyeluruh
5. **Mendeskripsikan** prinsip-prinsip arsitektur REST (RESTful constraints)
6. **Merancang** endpoint URL yang mengikuti konvensi REST yang benar
7. **Mengimplementasikan** REST API sederhana menggunakan Node.js dan Express
8. **Mengevaluasi** kualitas desain API berdasarkan prinsip REST dan best practices industri

**Tingkat Kompetensi Target:** Bloom's Taxonomy Level 3 (Apply) → Level 4 (Analyze)

**Prasyarat Modul:**
- Bab 01-07: Dasar pemrograman, JavaScript fundamentals, Node.js basics
- Pemahaman dasar tentang client-server architecture
- Familiar dengan terminal dan npm

---

## SECTION 02 — CONCEPT OVERVIEW

### Apa itu HTTP?

**HTTP (HyperText Transfer Protocol)** adalah protokol komunikasi berbasis teks yang mendefinisikan bagaimana pesan dikirim dan diterima antara **client** (browser, aplikasi mobile, service lain) dan **server** (komputer yang menyimpan dan memproses data).

HTTP bersifat:
- **Stateless** — Setiap request berdiri sendiri, server tidak mengingat request sebelumnya
- **Text-based** — Pesan dapat dibaca manusia (human-readable)
- **Request-Response** — Selalu ada pasangan: client meminta, server merespons
- **Application Layer Protocol** — Berjalan di atas TCP/IP

### Apa itu REST?

**REST (Representational State Transfer)** adalah **gaya arsitektur** (bukan protokol) yang mendefinisikan seperangkat constraint untuk membangun web services. REST diperkenalkan oleh Roy Fielding dalam disertasinya tahun 2000.

API yang mengikuti prinsip REST disebut **RESTful API**.

### Hubungan HTTP dan REST

```
REST  →  Gaya arsitektur / seperangkat aturan desain
HTTP  →  Protokol transport yang digunakan REST
```

REST menggunakan HTTP sebagai medium komunikasi, memanfaatkan HTTP methods, status codes, dan headers sebagai bahasa standar antara client dan server.

---

## SECTION 03 — WHY THIS MATTERS

### Mengapa HTTP & REST Sangat Penting untuk Backend Developer?

#### 1. Bahasa Universal Web
Hampir semua komunikasi di internet menggunakan HTTP. Sebagai backend developer, Anda akan **selalu** berurusan dengan HTTP — tidak ada pengecualian.

#### 2. REST adalah Standar Industri De Facto
Lebih dari **83% API publik** menggunakan arsitektur REST (RapidAPI Survey 2023). Memahami REST berarti Anda dapat:
- Bekerja dengan API manapun (Google, Stripe, GitHub, Twitter)
- Membangun API yang dapat dikonsumsi oleh siapapun
- Berkomunikasi dengan tim frontend menggunakan bahasa yang sama

#### 3. Fondasi untuk Teknologi Lanjutan
Pemahaman HTTP/REST adalah prasyarat untuk:
- GraphQL (alternatif REST)
- WebSockets (real-time communication)
- gRPC (high-performance RPC)
- Microservices architecture
- API Gateway patterns

#### 4. Debugging dan Problem Solving
Ketika aplikasi bermasalah, kemampuan membaca HTTP request/response adalah skill debugging paling fundamental yang dimiliki backend developer.

#### 5. Relevansi Karir
```
Job posting "Backend Developer" yang mensyaratkan REST API knowledge: ~97%
(LinkedIn Job Analysis, 2024)
```

---

## SECTION 04 — WHAT YOU NEED TO KNOW

### Komponen Utama yang Akan Dipelajari

#### A. HTTP Protocol Fundamentals
- Anatomi HTTP Request (Method, URL, Headers, Body)
- Anatomi HTTP Response (Status Line, Headers, Body)
- HTTP Methods dan semantiknya
- HTTP Status Codes (1xx, 2xx, 3xx, 4xx, 5xx)
- HTTP Headers yang umum digunakan

#### B. REST Architecture Principles
- 6 Constraints REST (Fielding's Dissertation)
- Resource-based thinking
- Uniform Interface
- Statelessness
- Client-Server separation

#### C. RESTful API Design
- URL/Endpoint naming conventions
- Resource vs Action dalam URL
- Versioning strategy
- Request/Response body format (JSON)
- CRUD mapping ke HTTP Methods

#### D. Implementasi Praktis
- Membuat REST API dengan Express.js
- Middleware untuk parsing JSON
- Error handling dalam REST API
- Testing API dengan tools (curl, Postman, Thunder Client)

### Terminologi Kunci

| Term | Definisi |
|------|----------|
| **Endpoint** | URL spesifik yang menerima request (e.g., `/api/users`) |
| **Resource** | Entitas data yang direpresentasikan dalam API (e.g., User, Product) |
| **Payload** | Data yang dikirim dalam body request/response |
| **Header** | Metadata yang menyertai request/response |
| **Status Code** | Kode numerik 3 digit yang menunjukkan hasil request |
| **CRUD** | Create, Read, Update, Delete — operasi dasar data |
| **JSON** | JavaScript Object Notation — format data standar REST API |
| **Idempotent** | Request yang diulang menghasilkan efek yang sama |

---

## SECTION 05 — HOW IT WORKS (DEEP DIVE)

### 5.1 Siklus HTTP Request-Response

Ketika Anda mengetik URL di browser atau aplikasi memanggil API, inilah yang terjadi:

```
1. DNS Resolution    → "api.example.com" → 192.168.1.100
2. TCP Handshake     → Koneksi 3-way handshake (SYN, SYN-ACK, ACK)
3. TLS Handshake     → Negosiasi enkripsi (jika HTTPS)
4. HTTP Request      → Client mengirim pesan request
5. Server Processing → Server memproses dan menyiapkan response
6. HTTP Response     → Server mengirim pesan response
7. Connection Close  → Koneksi ditutup (atau keep-alive)
```

### 5.2 Anatomi HTTP Request

```
POST /api/users HTTP/1.1
Host: api.example.com
Content-Type: application/json
Authorization: Bearer eyJhbGciOiJIUzI1NiJ9...
Accept: application/json
Content-Length: 67

{
  "name": "Budi Santoso",
  "email": "budi@example.com",
  "age": 28
}
```

**Breakdown:**
```
[Request Line]  → POST /api/users HTTP/1.1
                   │     │          └── Versi HTTP
                   │     └── Path/Endpoint
                   └── HTTP Method

[Headers]       → Key: Value pairs (metadata)
                  Host          → Domain tujuan
                  Content-Type  → Format body yang dikirim
                  Authorization → Kredensial autentikasi
                  Accept        → Format response yang diinginkan

[Empty Line]    → Pemisah wajib antara headers dan body

[Body]          → Data aktual (opsional, tergantung method)
```

### 5.3 Anatomi HTTP Response

```
HTTP/1.1 201 Created
Content-Type: application/json
Location: /api/users/123
X-Request-ID: req_abc123xyz
Date: Mon, 15 Jan 2024 10:30:00 GMT

{
  "success": true,
  "data": {
    "id": 123,
    "name": "Budi Santoso",
    "email": "budi@example.com",
    "createdAt": "2024-01-15T10:30:00Z"
  },
  "message": "User created successfully"
}
```

**Breakdown:**
```
[Status Line]   → HTTP/1.1 201 Created
                   │        │   └── Status text (human-readable)
                   │        └── Status code (machine-readable)
                   └── Versi HTTP

[Headers]       → Metadata response
                  Content-Type  → Format body response
                  Location      → URL resource yang baru dibuat
                  X-Request-ID  → Custom header untuk tracing

[Empty Line]    → Pemisah wajib

[Body]          → Data response (JSON, HTML, XML, dll)
```

### 5.4 HTTP Methods dan Semantiknya

| Method | Semantik | Body? | Idempotent? | Safe? |
|--------|----------|-------|-------------|-------|
| **GET** | Ambil data | ❌ | ✅ | ✅ |
| **POST** | Buat data baru | ✅ | ❌ | ❌ |
| **PUT** | Ganti seluruh data | ✅ | ✅ | ❌ |
| **PATCH** | Update sebagian data | ✅ | ❌* | ❌ |
| **DELETE** | Hapus data | ❌* | ✅ | ❌ |
| **HEAD** | Seperti GET, tanpa body | ❌ | ✅ | ✅ |
| **OPTIONS** | Cek method yang tersedia | ❌ | ✅ | ✅ |

> **Safe** = Tidak mengubah state server
> **Idempotent** = Dieksekusi 1x atau 100x, hasilnya sama

### 5.5 HTTP Status Codes

```
1xx → Informational  (Request diterima, sedang diproses)
2xx → Success        (Request berhasil)
3xx → Redirection    (Client perlu tindakan lanjut)
4xx → Client Error   (Kesalahan dari sisi client)
5xx → Server Error   (Kesalahan dari sisi server)
```

**Status Codes Paling Penting:**

| Code | Name | Kapan Digunakan |
|------|------|-----------------|
| 200 | OK | Request berhasil (GET, PUT, PATCH) |
| 201 | Created | Resource berhasil dibuat (POST) |
| 204 | No Content | Berhasil, tidak ada body (DELETE) |
| 301 | Moved Permanently | URL permanen berubah |
| 304 | Not Modified | Cache masih valid |
| 400 | Bad Request | Request malformed/invalid |
| 401 | Unauthorized | Belum autentikasi |
| 403 | Forbidden | Sudah autentikasi, tapi tidak punya izin |
| 404 | Not Found | Resource tidak ditemukan |
| 409 | Conflict | Konflik data (e.g., email sudah ada) |
| 422 | Unprocessable Entity | Validasi gagal |
| 429 | Too Many Requests | Rate limit terlampaui |
| 500 | Internal Server Error | Error tak terduga di server |
| 503 | Service Unavailable | Server sedang down/overload |

### 5.6 REST Constraints (6 Prinsip Fielding)

**1. Client-Server Separation**
```
Client bertanggung jawab atas UI/UX
Server bertanggung jawab atas data & business logic
Keduanya dapat berkembang secara independen
```

**2. Statelessness**
```
Setiap request harus mengandung SEMUA informasi yang dibutuhkan
Server tidak menyimpan session state client
State disimpan di client (token, cookies)
```

**3. Cacheability**
```
Response harus menandai apakah bisa di-cache atau tidak
Cache mengurangi beban server dan mempercepat response
Headers: Cache-Control, ETag, Last-Modified
```

**4. Uniform Interface**
```
Antarmuka yang konsisten dan standar
- Identifikasi resource via URI
- Manipulasi via representasi
- Self-descriptive messages
- HATEOAS (Hypermedia as the Engine of Application State)
```

**5. Layered System**
```
Client tidak perlu tahu apakah terhubung langsung ke server
Boleh ada load balancer, cache, gateway di antara keduanya
```

**6. Code on Demand (Opsional)**
```
Server dapat mengirim executable code ke client
Contoh: JavaScript yang dieksekusi browser
Satu-satunya constraint yang opsional
```

---

## SECTION 06 — ASCII DIAGRAM

### Diagram 1: HTTP Request-Response Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    HTTP REQUEST-RESPONSE CYCLE                   │
└─────────────────────────────────────────────────────────────────┘

  CLIENT                                              SERVER
  (Browser/App)                                    (Node.js/Express)
  
  ┌──────────┐                                      ┌──────────────┐
  │          │  1. DNS Lookup                        │              │
  │          │ ─────────────────────────────────►   │   DNS Server │
  │          │ ◄─────────────────────────────────   │  192.168.1.1 │
  │          │  "api.example.com" = 192.168.1.1     └──────────────┘
  │          │
  │          │  2. TCP Connection (3-way handshake)
  │          │ ──── SYN ──────────────────────────► ┌──────────────┐
  │          │ ◄─── SYN-ACK ──────────────────────  │              │
  │          │ ──── ACK ──────────────────────────► │   API SERVER │
  │          │                                       │              │
  │          │  3. HTTP Request                      │  ┌─────────┐ │
  │          │ ─────────────────────────────────►   │  │ Router  │ │
  │          │  GET /api/users/123 HTTP/1.1          │  └────┬────┘ │
  │          │  Host: api.example.com                │       │      │
  │          │  Authorization: Bearer token123       │  ┌────▼────┐ │
  │          │                                       │  │Handler  │ │
  │          │                                       │  └────┬────┘ │
  │          │                                       │       │      │
  │          │                                       │  ┌────▼────┐ │
  │          │                                       │  │Database │ │
  │          │                                       │  └────┬────┘ │
  │          │  4. HTTP Response                     │       │      │
  │          │ ◄─────────────────────────────────   │  ┌────▼────┐ │
  │          │  HTTP/1.1 200 OK                      │  │Response │ │
  │          │  Content-Type: application/json       │  │Builder  │ │
  │          │  {"id":123,"name":"Budi"}             │  └─────────┘ │
  └──────────┘                                       └──────────────┘
```

### Diagram 2: REST Resource Hierarchy

```
┌─────────────────────────────────────────────────────────────────┐
│                    REST RESOURCE HIERARCHY                       │
└─────────────────────────────────────────────────────────────────┘

  BASE URL: https://api.toko.com

  /api
  │
  ├── /v1                          ← API Version
  │   │
  │   ├── /products                ← Collection Resource
  │   │   │   GET    → List all products
  │   │   │   POST   → Create new product
  │   │   │
  │   │   └── /{id}               ← Single Resource
  │   │       │   GET    → Get product by ID
  │   │       │   PUT    → Replace product
  │   │       │   PATCH  → Update product partially
  │   │       │   DELETE → Delete product
  │   │       │
  │   │       └── /reviews        ← Sub-collection (nested)
  │   │               GET    → List reviews for product
  │   │               POST   → Add review to product
  │   │
  │   ├── /users
  │   │   ├── GET    → List users
  │   │   ├── POST   → Register user
  │   │   └── /{id}
  │   │       ├── GET    → Get user profile
  │   │       ├── PATCH  → Update profile
  │   │       └── /orders        ← User's orders
  │   │               GET    → List user's orders
  │   │
  │   └── /orders
  │       ├── GET    → List all orders
  │       └── /{id}
  │           ├── GET    → Get order detail
  │           └── PATCH  → Update order status
  │
  └── /health                     ← Non-resource endpoint (ok)
          GET → Server health check
```

### Diagram 3: HTTP Methods CRUD Mapping

```
┌─────────────────────────────────────────────────────────────────┐
│              HTTP METHODS ↔ CRUD ↔ SQL MAPPING                  │
└─────────────────────────────────────────────────────────────────┘

  HTTP Method    CRUD Operation    SQL Equivalent    Endpoint Example
  ───────────    ──────────────    ──────────────    ────────────────
  
  GET       ──► READ          ──► SELECT        ──► GET /users
                                                    GET /users/123
  
  POST      ──► CREATE        ──► INSERT        ──► POST /users
  
  PUT       ──► UPDATE (Full) ──► UPDATE (all   ──► PUT /users/123
                                  columns)
  
  PATCH     ──► UPDATE (Part) ──► UPDATE (some  ──► PATCH /users/123
                                  columns)
  
  DELETE    ──► DELETE        ──► DELETE        ──► DELETE /users/123

  ┌─────────────────────────────────────────────────────────────┐
  │  PUT vs PATCH:                                              │
  │                                                             │
  │  User: { name: "Budi", email: "budi@x.com", age: 28 }     │
  │                                                             │
  │  PUT /users/123  { name: "Budi Baru" }                     │
  │  Result: { name: "Budi Baru", email: null, age: null }     │
  │  → Seluruh resource diganti!                               │
  │                                                             │
  │  PATCH /users/123  { name: "Budi Baru" }                   │
  │  Result: { name: "Budi Baru", email: "budi@x.com", age:28} │
  │  → Hanya field yang dikirim yang berubah                   │
  └─────────────────────────────────────────────────────────────┘
```

### Diagram 4: Status Code Decision Tree

```
┌─────────────────────────────────────────────────────────────────┐
│                  STATUS CODE DECISION TREE                       │
└─────────────────────────────────────────────────────────────────┘

  Request masuk
       │
       ▼
  ┌─────────────┐   NO    ┌──────────────────────────────────────┐
  │ Request     ├────────►│ 400 Bad Request                      │
  │ valid?      │         │ (malformed JSON, missing required     │
  └──────┬──────┘         │  fields, invalid format)             │
         │ YES            └──────────────────────────────────────┘
         ▼
  ┌─────────────┐   NO    ┌──────────────────────────────────────┐
  │ Sudah       ├────────►│ 401 Unauthorized                     │
  │ autentikasi?│         │ (missing/invalid token)              │
  └──────┬──────┘         └──────────────────────────────────────┘
         │ YES
         ▼
  ┌─────────────┐   NO    ┌──────────────────────────────────────┐
  │ Punya       ├────────►│ 403 Forbidden                        │
  │ izin?       │         │ (token valid, tapi role tidak cukup) │
  └──────┬──────┘         └──────────────────────────────────────┘
         │ YES
         ▼
  ┌─────────────┐   NO    ┌──────────────────────────────────────┐
  │ Resource    ├────────►│ 404 Not Found                        │
  │ ada?        │         │ (ID tidak ditemukan di database)     │
  └──────┬──────┘         └──────────────────────────────────────┘
         │ YES
         ▼
  ┌─────────────┐   NO    ┌──────────────────────────────────────┐
  │ Validasi    ├────────►│ 422 Unprocessable Entity             │
  │ bisnis OK?  │         │ (email sudah terdaftar, stok habis)  │
  └──────┬──────┘         └──────────────────────────────────────┘
         │ YES
         ▼
  ┌─────────────┐   FAIL  ┌──────────────────────────────────────┐
  │ Proses      ├────────►│ 500 Internal Server Error            │
  │ berhasil?   │         │ (database error, unhandled exception) │
  └──────┬──────┘         └──────────────────────────────────────┘
         │ SUCCESS
         ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  GET/PUT/PATCH → 200 OK                                     │
  │  POST (create) → 201 Created                                │
  │  DELETE        → 204 No Content                             │
  └─────────────────────────────────────────────────────────────┘
```

---

## SECTION 07 — SIMPLE EXAMPLE

### Contoh Sederhana: REST API untuk Daftar Tugas (Todo List)

Mari kita mulai dengan contoh paling sederhana — REST API tanpa database, menggunakan array in-memory.

```javascript
// file: simple-todo-api.js
const express = require('express');
const app = express();

// Middleware: parse JSON body
app.use(express.json());

// "Database" sementara di memory
let todos = [
  { id: 1, task: 'Belajar HTTP', done: false },
  { id: 2, task: 'Belajar REST', done: false },
];
let nextId = 3;

// ─────────────────────────────────────────
// GET /todos → Ambil semua todo
// ─────────────────────────────────────────
app.get('/todos', (req, res) => {
  res.status(200).json({
    success: true,
    data: todos,
    total: todos.length
  });
});

// ─────────────────────────────────────────
// GET /todos/:id → Ambil satu todo
// ─────────────────────────────────────────
app.get('/todos/:id', (req, res) => {
  const id = parseInt(req.params.id);
  const todo = todos.find(t => t.id === id);

  if (!todo) {
    return res.status(404).json({
      success: false,
      message: `Todo dengan ID ${id} tidak ditemukan`
    });
  }

  res.status(200).json({
    success: true,
    data: todo
  });
});

// ─────────────────────────────────────────
// POST /todos → Buat todo baru
// ─────────────────────────────────────────
app.post('/todos', (req, res) => {
  const { task } = req.body;

  // Validasi sederhana
  if (!task || task.trim() === '') {
    return res.status(400).json({
      success: false,
      message: 'Field "task" wajib diisi'
    });
  }

  const newTodo = {
    id: nextId++,
    task: task.trim(),
    done: false
  };

  todos.push(newTodo);

  res.status(201).json({
    success: true,
    data: newTodo,
    message: 'Todo berhasil dibuat'
  });
});

// ─────────────────────────────────────────
// PATCH /todos/:id → Update status todo
// ─────────────────────────────────────────
app.patch('/todos/:id', (req, res) => {
  const id = parseInt(req.params.id);
  const todoIndex = todos.findIndex(t => t.id === id);

  if (todoIndex === -1) {
    return res.status(404).json({
      success: false,
      message: `Todo dengan ID ${id} tidak ditemukan`
    });
  }

  // Update hanya field yang dikirim
  const { task, done } = req.body;
  if (task !== undefined) todos[todoIndex].task = task;
  if (done !== undefined) todos[todoIndex].done = done;

  res.status(200).json({
    success: true,
    data: todos[todoIndex],
    message: 'Todo berhasil diupdate'
  });
});

// ─────────────────────────────────────────
// DELETE /todos/:id → Hapus todo
// ─────────────────────────────────────────
app.delete('/todos/:id', (req, res) => {
  const id = parseInt(req.params.id);
  const todoIndex = todos.findIndex(t => t.id === id);

  if (todoIndex === -1) {
    return res.status(404).json({
      success: false,
      message: `Todo dengan ID ${id} tidak ditemukan`
    });
  }

  todos.splice(todoIndex, 1);

  // 204 No Content: berhasil, tidak ada body
  res.status(204).send();
});

// Start server
app.listen(3000, () => {
  console.log('Server berjalan di http://localhost:3000');
});
```

### Cara Menjalankan dan Testing

```bash
# Install dependencies
npm init -y
npm install express

# Jalankan server
node simple-todo-api.js

# Test dengan curl (terminal baru)

# GET semua todos
curl http://localhost:3000/todos

# GET satu todo
curl http://localhost:3000/todos/1

# POST buat todo baru
curl -X POST http://localhost:3000/todos \
  -H "Content-Type: application/json" \
  -d '{"task": "Belajar Express"}'

# PATCH update todo
curl -X PATCH http://localhost:3000/todos/1 \
  -H "Content-Type: application/json" \
  -d '{"done": true}'

# DELETE hapus todo
curl -X DELETE http://localhost:3000/todos/2
```

### Output yang Diharapkan

```json
// GET /todos
{
  "success": true,
  "data": [
    { "id": 1, "task": "Belajar HTTP", "done": false },
    { "id": 2, "task": "Belajar REST", "done": false }
  ],
  "total": 2
}

// POST /todos dengan body {"task": "Belajar Express"}
// Status: 201 Created
{
  "success": true,
  "data": { "id": 3, "task": "Belajar Express", "done": false },
  "message": "Todo berhasil dibuat"
}

// GET /todos/999 (tidak ada)
// Status: 404 Not Found
{
  "success": false,
  "message": "Todo dengan ID 999 tidak ditemukan"
}
```

---

## SECTION 08 — PRACTICAL EXAMPLE

### Studi Kasus: REST API untuk Sistem Manajemen Produk Toko Online

Ini adalah contoh yang lebih realistis dengan struktur yang proper, validasi lengkap, dan error handling yang baik.

```javascript
// file: src/app.js
const express = require('express');
const app = express();

app.use(express.json());

// ─────────────────────────────────────────────────────────
// UTILITY FUNCTIONS
// ─────────────────────────────────────────────────────────

/**
 * Standar response format untuk seluruh API
 */
const createResponse = (success, data = null, message = '', meta = {}) => ({
  success,
  ...(data !== null && { data }),
  ...(message && { message }),
  ...(Object.keys(meta).length > 0 && { meta }),
  timestamp: new Date().toISOString()
});

/**
 * Validasi data produk
 */
const validateProduct = (data, isPartial = false) => {
  const errors = [];

  if (!isPartial || data.name !== undefined) {
    if (!data.name || typeof data.name !== 'string' || data.name.trim().length < 3) {
      errors.push('name: Minimal 3 karakter');
    }
  }

  if (!isPartial || data.price !== undefined) {
    if (data.price === undefined || typeof data.price !== 'number' || data.price < 0) {
      errors.push('price: Harus berupa angka positif');
    }
  }

  if (!isPartial || data.stock !== undefined) {
    if (data.stock === undefined || !Number.isInteger(data.stock) || data.stock < 0) {
      errors.push('stock: Harus berupa bilangan bulat non-negatif');
    }
  }

  if (!isPartial || data.category !== undefined) {
    const validCategories = ['electronics', 'clothing', 'food', 'books', 'other'];
    if (!data.category || !validCategories.includes(data.category)) {
      errors.push(`category: Harus salah satu dari: ${validCategories.join(', ')}`);
    }
  }

  return errors;
};

// ─────────────────────────────────────────────────────────
// IN-MEMORY DATABASE (simulasi)
// ─────────────────────────────────────────────────────────

let products = [
  {
    id: 1,
    name: 'Laptop Gaming ASUS ROG',
    price: 15000000,
    stock: 10,
    category: 'electronics',
    description: 'Laptop gaming high-performance',
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-01T00:00:00Z'
  },
  {
    id: 2,
    name: 'Kemeja Batik Premium',
    price: 350000,
    stock: 50,
    category: 'clothing',
    description: 'Kemeja batik motif parang',
    createdAt: '2024-01-02T00:00:00Z',
    updatedAt: '2024-01-02T00:00:00Z'
  },
  {
    id: 3,
    name: 'Clean Code - Robert Martin',
    price: 180000,
    stock: 25,
    category: 'books',
    description: 'Buku panduan menulis kode yang bersih',
    createdAt: '2024-01-03T00:00:00Z',
    updatedAt: '2024-01-03T00:00:00Z'
  }
];

let nextId = 4;

// ─────────────────────────────────────────────────────────
// ROUTES
// ─────────────────────────────────────────────────────────

/**
 * GET /api/v1/products
 * Ambil semua produk dengan filtering dan pagination
 *
 * Query params:
 * - category: filter by category
 * - minPrice: filter harga minimum
 * - maxPrice: filter harga maksimum
 * - search: cari berdasarkan nama
 * - page: halaman (default: 1)
 * - limit: jumlah per halaman (default: 10)
 * - sortBy: field untuk sorting (default: id)
 * - sortOrder: asc/desc (default: asc)
 */
app.get('/api/v1/products', (req, res) => {
  try {
    let result = [...products];

    // ── Filtering ──
    const { category, minPrice, maxPrice, search } = req.query;

    if (category) {
      result = result.filter(p => p.category === category);
    }

    if (minPrice) {
      const min = parseFloat(minPrice);
      if (!isNaN(min)) result = result.filter(p => p.price >= min);
    }

    if (maxPrice) {
      const max = parseFloat(maxPrice);
      if (!isNaN(max)) result = result.filter(p => p.price <= max);
    }

    if (search) {
      const keyword = search.toLowerCase();
      result = result.filter(p =>
        p.name.toLowerCase().includes(keyword) ||
        p.description.toLowerCase().includes(keyword)
      );
    }

    // ── Sorting ──
    const sortBy = req.query.sortBy || 'id';
    const sortOrder = req.query.sortOrder === 'desc' ? -1 : 1;
    const validSortFields = ['id', 'name', 'price', 'stock', 'createdAt'];

    if (validSortFields.includes(sortBy)) {
      result.sort((a, b) => {
        if (a[sortBy] < b[sortBy]) return -1 * sortOrder;
        if (a[sortBy] > b[sortBy]) return 1 * sortOrder;
        return 0;
      });
    }

    // ── Pagination ──
    const page = Math.max(1, parseInt(req.query.page) || 1);
    const limit = Math.min(100, Math.max(1, parseInt(req.query.limit) || 10));
    const totalItems = result.length;
    const totalPages = Math.ceil(totalItems / limit);
    const startIndex = (page - 1) * limit;
    const paginatedResult = result.slice(startIndex, startIndex + limit);

    res.status(200).json(createResponse(
      true,
      paginatedResult,
      '',
      {
        pagination: {
          currentPage: page,
          totalPages,
          totalItems,
          itemsPerPage: limit,
          hasNextPage: page < totalPages,
          hasPrevPage: page > 1
        }
      }
    ));
  } catch (error) {
    res.status(500).json(createResponse(false, null, 'Internal server error'));
  }
});

/**
 * GET /api/v1/products/:id
 * Ambil detail satu produk
 */
app.get('/api/v1/products/:id', (req, res) => {
  const id = parseInt(req.params.id);

  // Validasi ID
  if (isNaN(id) || id <= 0) {
    return res.status(400).json(
      createResponse(false, null, 'ID produk harus berupa angka positif')
    );
  }

  const product = products.find(p => p.id === id);

  if (!product) {
    return res.status(404).json(
      createResponse(false, null, `Produk dengan ID ${id} tidak ditemukan`)
    );
  }

  res.status(200).json(createResponse(true, product));
});

/**
 * POST /api/v1/products
 * Buat produk baru
 */
app.post('/api/v1/products', (req, res) => {
  const { name, price, stock, category, description } = req.body;

  // Validasi
  const errors = validateProduct({ name, price, stock, category });
  if (errors.length > 0) {
    return res.status(422).json(
      createResponse(false, null, 'Validasi gagal', { errors })
    );
  }

  // Cek duplikasi nama
  const isDuplicate = products.some(
    p => p.name.toLowerCase() === name.trim().toLowerCase()
  );
  if (isDuplicate) {
    return res.status(409).json(
      createResponse(false, null, `Produk dengan nama "${name}" sudah ada`)
    );
  }

  const now = new Date().toISOString();
  const newProduct = {
    id: nextId++,
    name: name.trim(),
    price,
    stock,
    category,
    description: description?.trim() || '',
    createdAt: now,
    updatedAt: now
  };

  products.push(newProduct);

  // 201 Created + Location header
  res
    .status(201)
    .set('Location', `/api/v1/products/${newProduct.id}`)
    .json(createResponse(true, newProduct, 'Produk berhasil dibuat'));
});

/**
 * PUT /api/v1/products/:id
 * Ganti seluruh data produk
 */
app.put('/api/v1/products/:id', (req, res) => {
  const id = parseInt(req.params.id);
  const productIndex = products.findIndex(p => p.id === id);

  if (productIndex === -1) {
    return res.status(404).json(
      createResponse(false, null, `Produk dengan ID ${id} tidak ditemukan`)
    );
  }

  const { name, price, stock, category, description } = req.body;

  // PUT memerlukan semua field (full replacement)
  const errors = validateProduct({ name, price, stock, category });
  if (errors.length > 0) {
    return res.status(422).json(
      createResponse(false, null, 'Validasi gagal', { errors })
    );
  }

  // Simpan data lama untuk audit (opsional)
  const oldProduct = { ...products[productIndex] };

  products[productIndex] = {
    id,
    name: name.trim(),
    price,
    stock,
    category,
    description: description?.trim() || '',
    createdAt: oldProduct.createdAt,  // Pertahankan createdAt
    updatedAt: new Date().toISOString()
  };

  res.status(200).json(
    createResponse(true, products[productIndex], 'Produk berhasil diperbarui')
  );
});

/**
 * PATCH /api/v1/products/:id
 * Update sebagian data produk
 */
app.patch('/api/v1/products/:id', (req, res) => {
  const id = parseInt(req.params.id);
  const productIndex = products.findIndex(p => p.id === id);

  if (productIndex === -1) {
    return res.status(404).json(
      createResponse(false, null, `Produk dengan ID ${id} tidak ditemukan`)
    );
  }

  // Validasi hanya field yang dikirim (isPartial = true)
  const errors = validateProduct(req.body, true);
  if (errors.length > 0) {
    return res.status(422).json(
      createResponse(false, null, 'Validasi gagal', { errors })
    );
  }

  // Merge: hanya update field yang ada di body
  const allowedFields = ['name', 'price', 'stock', 'category', 'description'];
  const updates = {};

  allowedFields.forEach(field => {
    if (req.body[field] !== undefined) {
      updates[field] = typeof req.body[field] === 'string'
        ? req.body[field].trim()
        : req.body[field];
    }
  });

  products[productIndex] = {
    ...products[productIndex],
    ...updates,
    updatedAt: new Date().toISOString()
  };

  res.status(200).json(
    createResponse(true, products[productIndex], 'Produk berhasil diperbarui')
  );
});

/**
 * DELETE /api/v1/products/:id
 * Hapus produk
 */
app.delete('/api/v1/products/:id', (req, res) => {
  const id = parseInt(req.params.id);
  const productIndex = products.findIndex(p => p.id === id);

  if (productIndex === -1) {
    return res.status(404).json(
      createResponse(false, null, `Produk dengan ID ${id} tidak ditemukan`)
    );
  }

  products.splice(productIndex, 1);

  // 204 No Content: sukses tanpa body
  res.status(204).send();
});

// ─────────────────────────────────────────────────────────
// GLOBAL ERROR HANDLER
// ─────────────────────────────────────────────────────────

// Handle route tidak ditemukan
app.use((req, res) => {
  res.status(404).json(
    createResponse(false, null, `Route ${req.method} ${req.path} tidak ditemukan`)
  );
});

// Handle error tak terduga
app.use((err, req, res, next) => {
  console.error('Unhandled error:', err);
  res.status(500).json(
    createResponse(false, null, 'Terjadi kesalahan internal server')
  );
});

// ─────────────────────────────────────────────────────────
// START SERVER
// ─────────────────────────────────────────────────────────

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`
  ┌─────────────────────────────────────────┐
  │   Product API Server Running            │
  │   URL: http://localhost:${PORT}           │
  │                                         │
  │   Endpoints:                            │
  │   GET    /api/v1/products               │
  │   GET    /api/v1/products/:id           │
  │   POST   /api/v1/products               │
  │   PUT    /api/v1/products/:id           │
  │   PATCH  /api/v1/products/:id           │
  │   DELETE /api/v1/products/:id           │
  └─────────────────────────────────────────┘
  `);
});

module.exports = app;
```

### Testing Lengkap dengan curl

```bash
# ── 1. GET semua produk ──
curl -s http://localhost:3000/api/v1/products | json_pp

# ── 2. GET dengan filter dan pagination ──
curl -s "http://localhost:3000/api/v1/products?category=electronics&page=1&limit=5" | json_pp

# ── 3. GET dengan search ──
curl -s "http://localhost:3000/api/v1/products?search=laptop" | json_pp

# ── 4. GET satu produk ──
curl -s http://localhost:3000/api/v1/products/1 | json_pp

# ── 5. POST buat produk baru ──
curl -s -X POST http://localhost:3000/api/v1/products \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Headphone Sony WH-1000XM5",
    "price": 4500000,
    "stock": 15,
    "category": "electronics",
    "description": "Headphone noise-cancelling premium"
  }' | json_pp

# ── 6. PATCH update stok saja ──
curl -s -X PATCH http://localhost:3000/api/v1/products/1 \
  -H "Content-Type: application/json" \
  -d '{"stock": 8}' | json_pp

# ── 7. DELETE produk ──
curl -s -X DELETE http://localhost:3000/api/v1/products/2 -v

# ── 8. Test error: POST tanpa field wajib ──
curl -s -X POST http://localhost:3000/api/v1/products \
  -H "Content-Type: application/json" \
  -d '{"name": "X"}' | json_pp
```

---

## SECTION 09 — TRADE-OFFS & CONSIDERATIONS

### 9.1 REST vs Alternatif Lain

#### REST vs GraphQL

| Aspek | REST | GraphQL |
|-------|------|---------|
| **Over-fetching** | Sering terjadi (data berlebih) | Tidak ada (client pilih field) |
| **Under-fetching** | Butuh multiple request | Satu request cukup |
| **Learning curve** | Rendah | Sedang-Tinggi |
| **Caching** | Mudah (HTTP native) | Kompleks |
| **File upload** | Native | Butuh workaround |
| **Real-time** | Butuh WebSocket terpisah | Subscription built-in |
| **Tooling** | Sangat mature | Berkembang pesat |
| **Best for** | Simple CRUD, public API | Complex queries, mobile |

#### REST vs gRPC

| Aspek | REST | gRPC |
|-------|------|------|
| **Format** | JSON (text) | Protocol Buffers (binary) |
| **Performance** | Baik | Sangat baik (3-10x lebih cepat) |
| **Browser support** | Native | Butuh grpc-web |
| **Human readable** | Ya | Tidak |
| **Streaming** | Terbatas | Built-in |
| **Best for** | Public API, web | Internal microservices |

### 9.2 Trade-offs dalam Desain REST API

#### Statelessness: Pro vs Con

```
✅ PRO:
- Scalability horizontal mudah (any server bisa handle request)
- Reliability: server crash tidak kehilangan session
- Simplicity: tidak ada state management di server

❌ CON:
- Setiap request membawa lebih banyak data (token, dll)
- Tidak efisien untuk operasi yang butuh banyak konteks
- Bandwidth lebih besar
```

#### Versioning Strategy

```
Option 1: URL Versioning (Paling umum)
  /api/v1/products
  /api/v2/products
  ✅ Explicit, mudah di-cache
  ❌ URL "kotor", breaking change butuh URL baru

Option 2: Header Versioning
  Accept: application/vnd.api+json;version=1
  ✅ URL bersih
  ❌ Tidak terlihat di URL, sulit di-test dengan browser

Option 3: Query Parameter
  /api/products?version=1
  ✅ Mudah di-test
  ❌ Tidak standar, cache lebih sulit
```

#### Nested Resources: Kapan Digunakan?

```
✅ GUNAKAN nested jika:
  - Resource tidak bisa ada tanpa parent
  - Selalu diakses dalam konteks parent
  
  Contoh: /users/123/addresses (alamat milik user)

❌ HINDARI nested jika:
  - Resource bisa diakses secara independen
  - Nesting lebih dari 2 level (terlalu dalam)
  
  Contoh BURUK: /users/123/orders/456/items/789/reviews
  Lebih baik:   /reviews?itemId=789
```

### 9.3 Kapan REST Bukan Pilihan Terbaik?

```
❌ Real-time bidirectional communication → Gunakan WebSocket
❌ Streaming data besar → Gunakan gRPC atau SSE
❌ Complex queries dengan banyak relasi → Pertimbangkan GraphQL
❌ Internal microservices dengan performa kritis → Pertimbangkan gRPC
❌ Event-driven architecture → Pertimbangkan Message Queue (Kafka, RabbitMQ)
```

---

## SECTION 10 — BEST PRACTICES

### 10.1 URL Design Best Practices

```
✅ BENAR                          ❌ SALAH
─────────────────────────────────────────────────────
GET /products                     GET /getProducts
GET /products/123                 GET /product/123
POST /products                    POST /createProduct
DELETE /products/123              DELETE /deleteProduct/123
GET /users/123/orders             GET /getUserOrders/123
GET /products?status=active       GET /getActiveProducts
PATCH /products/123               POST /products/123/update
```

### 10.2 Naming Conventions

```javascript
// ✅ Gunakan noun (kata benda), bukan verb
GET /articles          // ✅
GET /getArticles       // ❌

// ✅ Gunakan plural untuk collections
GET /products          // ✅
GET /product           // ❌

// ✅ Gunakan lowercase dan hyphen untuk multi-kata
GET /product-categories    // ✅
GET /productCategories     // ❌ (camelCase di URL)
GET /product_categories    // ❌ (underscore)

// ✅ Gunakan query params untuk filtering, bukan path
GET /products?status=active&category=electronics   // ✅
GET /products/active/electronics                   // ❌

// ✅ Aksi non-CRUD: gunakan sub-resource atau query
POST /orders/123/cancel        // ✅ (sub-resource)
POST /users/123/activate       // ✅
GET  /reports?type=monthly     // ✅
```

### 10.3 Response Format Consistency

```javascript
// ✅ Standar response format yang konsisten
const successResponse = {
  success: true,
  data: { /* actual data */ },
  message: "Operasi berhasil",          // Opsional
  meta: {                                // Untuk pagination
    pagination: {
      currentPage: 1,
      totalPages: 10,
      totalItems: 100
    }
  },
  timestamp: "2024-01-15T10:30:00Z"
};

const errorResponse = {
  success: false,
  message: "Deskripsi error yang jelas",
  errors: [                              // Detail validasi (opsional)
    "name: Minimal 3 karakter",
    "price: Harus angka positif"
  ],
  code: "VALIDATION_ERROR",             // Error code (opsional)
  timestamp: "2024-01-15T10:30:00Z"
};
```

### 10.4 HTTP Headers Best Practices

```javascript
// ✅ Headers yang selalu disertakan
res.set({
  'Content-Type': 'application/json',
  'X-Request-ID': generateRequestId(),   // Untuk tracing
  'Cache-Control': 'no-cache',           // Untuk data dinamis
});

// ✅ Untuk resource yang baru dibuat (POST)
res.set('Location', `/api/v1/products/${newProduct.id}`);

// ✅ Untuk response yang bisa di-cache (data statis)
res.set({
  'Cache-Control': 'public, max-age=3600',
  'ETag': generateETag(data),
  'Last-Modified': lastModifiedDate.toUTCString()
});
```

### 10.5 Error Handling Best Practices

```javascript
// ✅ Selalu berikan pesan error yang informatif
// ❌ BURUK:
res.status(400).json({ error: "Bad request" });

// ✅ BAIK:
res.status(422).json({
  success: false,
  message: "Validasi input gagal",
  errors: [
    "email: Format email tidak valid",
    "password: Minimal 8 karakter, harus ada huruf besar dan angka"
  ]
});

// ✅ Jangan expose internal error ke client
// ❌ BURUK:
res.status(500).json({
  error: "SequelizeDatabaseError: column 'usr_id' does not exist"
});

// ✅ BAIK:
console.error('Database error:', err);  // Log untuk developer
res.status(500).json({
  success: false,
  message: "Terjadi kesalahan internal. Silakan coba lagi."
});
```

### 10.6 Security Best Practices (Preview)

```javascript
// ✅ Validasi dan sanitasi semua input
// ✅ Gunakan HTTPS di production
// ✅ Implementasi rate limiting
// ✅ Jangan expose sensitive data di response
// ✅ Gunakan proper authentication (JWT, OAuth)
// ✅ Set security headers (Helmet.js)

// Contoh: Jangan return password hash
const user = await User.findById(id);
const { password, ...safeUser } = user;  // Exclude password
res.json({ data: safeUser });
```

---

## SECTION 11 — COMMON MISTAKES & HOW TO AVOID THEM

### Mistake 1: Menggunakan HTTP Method yang Salah

```javascript
// ❌ SALAH: Menggunakan GET untuk operasi yang mengubah data
app.get('/users/delete/:id', ...);
app.get('/products/create', ...);

// ✅ BENAR: Gunakan method yang sesuai semantiknya
app.delete('/users/:id', ...);
app.post('/products', ...);
```

### Mistake 2: Status Code yang Tidak Tepat

```javascript
// ❌ SALAH: Selalu return 200 meski ada error
app.post('/users', (req, res) => {
  if (!req.body.email) {
    return res.status(200).json({ error: "Email required" }); // ❌
  }
});

// ✅ BENAR: Gunakan status code yang tepat
app.post('/users', (req, res) => {
  if (!req.body.email) {
    return res.status(400).json({          // ✅ 400 untuk bad request
      success: false,
      message: "Email wajib diisi"
    });
  }
  // ...
  res.status(201).json({ ... });           // ✅ 201 untuk created
});
```

### Mistake 3: Menyimpan State di Server (Melanggar Stateless)

```javascript
// ❌ SALAH: Menyimpan state user di server memory
const userSessions = {};  // Ini tidak scalable!

app.post('/login', (req, res) => {
  userSessions[userId] = { loggedIn: true, cart: [] };
});

// ✅ BENAR: State ada di client (JWT token)
app.post('/login', (req, res) => {
  const token = jwt.sign({ userId, role }, SECRET_KEY, { expiresIn: '1h' });
  res.json({ token });  // Client menyimpan token
});
```

### Mistake 4: URL yang Mengandung Verb

```javascript
// ❌ SALAH: Verb di URL
GET  /getAllProducts
POST /createUser
PUT  /updateProduct/123
GET  /deleteOrder/456

// ✅ BENAR: Noun di URL, verb dari HTTP method
GET    /products
POST   /users
PUT    /products/123
DELETE /orders/456
```

### Mistake 5: Tidak Konsisten dalam Response Format

```javascript
// ❌ SALAH: Format berbeda-beda di setiap endpoint
// Endpoint A: { users: [...] }
// Endpoint B: { data: [...], status: "ok" }
// Endpoint C: [...]  (langsung array)

// ✅ BENAR: Format konsisten di semua endpoint
// Semua endpoint: { success: true, data: [...], timestamp: "..." }
```

### Mistake 6: Nested Resource Terlalu Dalam

```javascript
// ❌ SALAH: Terlalu dalam, sulit dibaca dan di-maintain
GET /companies/1/departments/2/employees/3/projects/4/tasks/5

// ✅ BENAR: Maksimal 2 level nesting, gunakan query params
GET /tasks/5
GET /tasks?projectId=4&employeeId=3
```

---

## SECTION 12 — HANDS-ON EXERCISE

### Exercise 1: Identifikasi HTTP Method (Beginner)

Tentukan HTTP method yang tepat untuk setiap operasi berikut:

```
1. Mengambil daftar semua artikel blog
2. Membuat artikel baru
3. Mengubah judul artikel (tanpa mengubah konten)
4. Mengganti seluruh data artikel
5. Menghapus artikel
6. Mengecek apakah server berjalan
7. Mendapatkan detail artikel berdasarkan ID
8. Mencari artikel berdasarkan keyword
```

**Jawaban:**
```
1. GET    /articles
2. POST   /articles
3. PATCH  /articles/:id
4. PUT    /articles/:id
5. DELETE /articles/:id
6. GET    /health
7. GET    /articles/:id
8. GET    /articles?search=keyword
```

### Exercise 2: Rancang URL Endpoints (Intermediate)

Rancang RESTful endpoints untuk sistem perpustakaan dengan entitas:
- **Book** (buku)
- **Member** (anggota)
- **Loan** (peminjaman)

```
Solusi yang diharapkan:

BOOKS:
GET    /api/v1/books              → List semua buku
GET    /api/v1/books/:id          → Detail buku
POST   /api/v1/books              → Tambah buku baru
PUT    /api/v1/books/:id          → Update seluruh data buku
PATCH  /api/v1/books/:id          → Update sebagian (e.g., stok)
DELETE /api/v1/books/:id          → Hapus buku

MEMBERS:
GET    /api/v1/members            → List anggota
GET    /api/v1/members/:id        → Detail anggota
POST   /api/v1/members            → Daftar anggota baru
PATCH  /api/v1/members/:id        → Update profil
DELETE /api/v1/members/:id        → Nonaktifkan anggota

LOANS:
GET    /api/v1/loans              → List semua peminjaman
GET    /api/v1/loans/:id          → Detail peminjaman
POST   /api/v1/loans              → Buat peminjaman baru
PATCH  /api/v1/loans/:id          → Update status (return, extend)
GET    /api/v1/members/:id/loans  → Riwayat pinjam anggota
GET    /api/v1/books/:id/loans    → Riwayat pinjam buku
```

### Exercise 3: Implementasi CRUD Sederhana (Hands-on)

Implementasikan REST API untuk entitas **Student** dengan field:
- `id` (auto-generated)
- `name` (string, required, min 3 char)
- `email` (string, required, unique, valid email format)
- `grade` (number, 1-12)
- `createdAt` (auto-generated)

**Requirement:**
1. GET /students — list dengan filter by grade
2. GET /students/:id — detail
3. POST /students — create dengan validasi
4. PATCH /students/:id — partial update
5. DELETE /students/:id — delete

**Starter code tersedia di:** `/exercises/08-01/student-api/`

---

## SECTION 13 — QUIZ & KNOWLEDGE CHECK

### Quiz 1: Multiple Choice

**Q1.** Manakah HTTP method yang bersifat **idempotent** sekaligus **safe**?
```
A) POST
B) PUT
C) GET  ← BENAR
D) PATCH
```

**Q2.** Status code apa yang tepat ketika user mencoba mengakses resource yang ada, tetapi tidak memiliki izin?
```
A) 401 Unauthorized
B) 403 Forbidden  ← BENAR
C) 404 Not Found
D) 400 Bad Request
```

**Q3.** Manakah URL yang paling sesuai konvensi REST?
```
A) POST /api/createNewUser
B) POST /api/users  ← BENAR
C) GET  /api/users/create
D) POST /api/user/new
```

**Q4.** Apa perbedaan utama antara PUT dan PATCH?
```
A) PUT lebih cepat dari PATCH
B) PUT mengganti seluruh resource, PATCH hanya sebagian  ← BENAR
C) PATCH bisa digunakan untuk create, PUT tidak
D) Tidak ada perbedaan, keduanya sama
```

**Q5.** Constraint REST mana yang menyatakan bahwa server tidak boleh menyimpan state client?
```
A) Uniform Interface
B) Layered System
C) Statelessness  ← BENAR
D) Cacheability
```

### Quiz 2: True or False

```
1. REST adalah protokol komunikasi. 
   → FALSE (REST adalah gaya arsitektur)

2. HTTP 204 No Content berarti request gagal.
   → FALSE (204 berarti sukses tanpa body response)

3. GET request tidak boleh memiliki body.
   → TRUE (secara konvensi dan best practice)

4. Semua REST API harus menggunakan JSON.
   → FALSE (REST tidak mensyaratkan format tertentu)

5. DELETE request yang diulang harus menghasilkan efek yang sama.
   → TRUE (DELETE bersifat idempotent)
```

### Quiz 3: Analisis Kode

```javascript
// Apa yang salah dengan kode ini?
app.get('/api/users/delete/:id', async (req, res) => {
  const user = await User.findById(req.params.id);
  await user.delete();
  res.status(200).json({ message: "deleted" });
});
```

**Jawaban:**
```
Masalah 1: Menggunakan GET untuk operasi DELETE (melanggar HTTP semantics)
           → Seharusnya: app.delete('/api/users/:id', ...)

Masalah 2: Verb "delete" ada di URL
           → Seharusnya: /api/users/:id

Masalah 3: Status 200 untuk delete, seharusnya 204 No Content
           → res.status(204).send()

Masalah 4: Tidak ada error handling jika user tidak ditemukan
           → Perlu cek: if (!user) return res.status(404)...
```

---

## SECTION 14 — DEBUGGING GUIDE

### 14.1 Tools untuk Debugging HTTP

#### 1. curl (Command Line)
```bash
# Verbose mode: lihat semua headers
curl -v http://localhost:3000/api/products

# Lihat hanya response headers
curl -I http://localhost:3000/api/products

# POST dengan body
curl -X POST http://localhost:3000/api/products \
  -H "Content-Type: application/json" \
  -d '{"name":"Test"}' \
  -v

# Simpan response ke file
curl http://localhost:3000/api/products -o response.json
```

#### 2. Postman / Thunder Client (GUI)
```
1. Buat collection untuk setiap API
2. Gunakan environment variables untuk base URL
3. Simpan contoh request dan response
4. Gunakan Tests tab untuk auto-validasi response
```

#### 3. Browser DevTools
```
Network Tab → Lihat semua HTTP request
- Headers tab: request/response headers
- Preview tab: response body terformat
- Timing tab: breakdown waktu request
```

### 14.2 Common Debugging Scenarios

#### Scenario 1: "Cannot GET /api/products"
```
Kemungkinan penyebab:
1. Route belum didefinisikan
2. Typo di path (/api/product vs /api/products)
3. Server belum dijalankan
4. Port berbeda

Debug steps:
1. Cek console server untuk error
2. Verifikasi route definition
3. Cek apakah server running: curl http://localhost:3000/health
```

#### Scenario 2: "SyntaxError: Unexpected token in JSON"
```
Kemungkinan penyebab:
1. Body request bukan valid JSON
2. Lupa middleware express.json()
3. Content-Type header tidak di-set

Debug steps:
1. Validasi JSON di jsonlint.com
2. Pastikan: app.use(express.json())
3. Cek header: -H "Content-Type: application/json"
```

#### Scenario 3: Response 200 tapi data kosong
```
Kemungkinan penyebab:
1. Filter terlalu ketat, tidak ada data yang match
2. Query parameter salah nama
3. Database kosong

Debug steps:
1. Log req.query untuk cek parameter yang diterima
2. Test tanpa filter dulu
3. Cek data di "database"
```

### 14.3 Logging untuk Debugging

```javascript
// Middleware logging sederhana
app.use((req, res, next) => {
  const start = Date.now();
  
  // Log request
  console.log(`[${new Date().toISOString()}] ${req.method} ${req.path}`);
  console.log('Query:', req.query);
  console.log('Body:', req.body);
  
  // Intercept response untuk log status
  const originalSend = res.send;
  res.send = function(body) {
    console.log(`Response: ${res.statusCode} (${Date.now() - start}ms)`);
    return originalSend.call(this, body);
  };
  
  next();
});
```

---

## SECTION 15 — PERFORMANCE CONSIDERATIONS

### 15.1 HTTP Caching

```javascript
// ✅ Cache untuk data yang jarang berubah
app.get('/api/v1/categories', (req, res) => {
  res.set({
    'Cache-Control': 'public, max-age=3600',  // Cache 1 jam
    'ETag': '"categories-v1"'
  });
  res.json({ data: categories });
});

// ✅ No cache untuk data sensitif/dinamis
app.get('/api/v1/users/me', (req, res) => {
  res.set('Cache-Control', 'no-store');
  res.json({ data: currentUser });
});
```

### 15.2 Pagination untuk Large Datasets

```javascript
// ❌ BURUK: Return semua data sekaligus
app.get('/products', async (req, res) => {
  const allProducts = await Product.findAll();  // Bisa jutaan record!
  res.json(allProducts);
});

// ✅ BAIK: Pagination
app.get('/products', async (req, res) => {
  const page = parseInt(req.query.page) || 1;
  const limit = Math.min(parseInt(req.query.limit) || 20, 100);
  const offset = (page - 1) * limit;
  
  const { rows, count } = await Product.findAndCountAll({
    limit,
    offset
  });
  
  res.json({
    data: rows,
    meta: {
      totalItems: count,
      currentPage: page,
      totalPages: Math.ceil(count / limit)
    }
  });
});
```

### 15.3 Field Selection (Sparse Fieldsets)

```javascript
// ✅ Izinkan client memilih field yang dibutuhkan
app.get('/api/products', (req, res) => {
  const { fields } = req.query;
  // ?fields=id,name,price
  
  let result = products;
  
  if (fields) {
    const selectedFields = fields.split(',');
    result = products.map(p => {
      const filtered = {};
      selectedFields.forEach(f => {
        if (p[f] !== undefined) filtered[f] = p[f];
      });
      return filtered;
    });
  }
  
  res.json({ data: result });
});
```

### 15.4 Compression

```javascript
const compression = require('compression');

// ✅ Kompres response untuk mengurangi bandwidth
app.use(compression({
  level: 6,           // Compression level (1-9)
  threshold: 1024,    // Hanya kompres jika > 1KB
}));
```

---

## SECTION 16 — SECURITY FUNDAMENTALS

### 16.1 Input Validation & Sanitization

```javascript
// ✅ Selalu validasi dan sanitasi input
const sanitizeString = (str) => {
  if (typeof str !== 'string') return '';
  return str
    .trim()
    .replace(/[<>]/g, '')  // Basic XSS prevention
    .substring(0, 1000);   // Limit length
};

const validateEmail = (email) => {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
};

app.post('/api/users', (req, res) => {
  const name = sanitizeString(req.body.name);
  const email = sanitizeString(req.body.email);
  
  if (!validateEmail(email)) {
    return res.status(422).json({
      success: false,
      message: 'Format email tidak valid'
    });
  }
  // ...
});
```

### 16.2 Rate Limiting (Preview)

```javascript
// Mencegah abuse dan DDoS sederhana
const requestCounts = {};

const rateLimiter = (req, res, next) => {
  const ip = req.ip;
  const now = Date.now();
  const windowMs = 60 * 1000;  // 1 menit
  const maxRequests = 100;
  
  if (!requestCounts[ip]) {
    requestCounts[ip] = { count: 1, resetTime: now + windowMs };
  } else if (now > requestCounts[ip].resetTime) {
    requestCounts[ip] = { count: 1, resetTime: now + windowMs };
  } else {
    requestCounts[ip].count++;
  }
  
  if (requestCounts[ip].count > maxRequests) {
    return res.status(429).json({
      success: false,
      message: 'Terlalu banyak request. Coba lagi dalam 1 menit.'
    });
  }
  
  next();
};

app.use(rateLimiter);
```

### 16.3 CORS (Cross-Origin Resource Sharing)

```javascript
// ✅ Konfigurasi CORS yang proper
const cors = require('cors');

// Development: izinkan semua origin
app.use(cors());

// Production: batasi origin yang diizinkan
app.use(cors({
  origin: ['https://app.example.com', 'https://admin.example.com'],
  methods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
  allowedHeaders: ['Content-Type', 'Authorization'],
  credentials: true,
  maxAge: 86400  // Cache preflight 24 jam
}));
```

---

## SECTION 17 — INTEGRATION WITH ECOSYSTEM

### 17.1 Middleware Stack yang Umum

```javascript
const express = require('express');
const cors = require('cors');
const compression = require('compression');
const helmet = require('helmet');

const app = express();

// ── Security ──
app.use(helmet());          // Set security headers
app.use(cors(corsOptions)); // CORS policy

// ── Performance ──
app.use(compression());     // Gzip compression

// ── Parsing ──
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true }));

// ── Logging ──
app.use(requestLogger);     // Custom atau morgan

// ── Routes ──
app.use('/api/v1', routes);

// ── Error Handling ──
app.use(notFoundHandler);
app.use(errorHandler);
```

### 17.2 Struktur Folder yang Direkomendasikan

```
project/
├── src/
│   ├── routes/
│   │   ├── index.js          ← Route aggregator
│   │   ├── products.routes.js
│   │   └── users.routes.js
│   ├── controllers/
│   │   ├── products.controller.js
│   │   └── users.controller.js
│   ├── middleware/
│   │   ├── auth.middleware.js
│   │   ├── validation.middleware.js
│   │   └── error.middleware.js
│   ├── utils/
│   │   ├── response.helper.js
│   │   └── validation.helper.js
│   └── app.js               ← Express app setup
├── tests/
│   └── products.test.js
├── package.json
└── README.md
```

### 17.3 Dokumentasi API dengan OpenAPI/Swagger

```yaml
# openapi.yaml
openapi: 3.0.0
info:
  title: Product API
  version: 1.0.0
  description: REST API untuk manajemen produk

paths:
  /api/v1/products:
    get:
      summary: Ambil daftar produk
      parameters:
        - name: category
          in: query
          schema:
            type: string
        - name: page
          in: query
          schema:
            type: integer
            default: 1
      responses:
        '200':
          description: Berhasil
          content:
            application/json:
              schema:
                type: object
                properties:
                  success:
                    type: boolean
                  data:
                    type: array
                    items:
                      $ref: '#/components/schemas/Product'
```

---

## SECTION 18 — REAL-WORLD CASE STUDY

### Studi Kasus: Desain API untuk Aplikasi E-Commerce "TokoKita"

#### Konteks Bisnis
TokoKita adalah platform e-commerce yang menghubungkan penjual dan pembeli. Tim backend perlu merancang REST API yang akan dikonsumsi oleh:
- Mobile app (iOS & Android)
- Web frontend (React)
- Third-party integrations (payment gateway, shipping)

#### Tantangan yang Dihadapi

**Tantangan 1: Konsistensi Response Format**
```
Masalah: Tim frontend mengeluh setiap endpoint punya format berbeda
Solusi: Buat response helper yang digunakan di semua endpoint

// response.helper.js
const success = (res, data, message = '', statusCode = 200, meta = {}) => {
  return res.status(statusCode).json({
    success: true,
    data,
    ...(message && { message }),
    ...(Object.keys(meta).length > 0 && { meta }),
    timestamp: new Date().toISOString()
  });
};

const error = (res, message, statusCode = 500, errors = []) => {
  return res.status(statusCode).json({
    success: false,
    message,
    ...(errors.length > 0 && { errors }),
    timestamp: new Date().toISOString()
  });
};
```

**Tantangan 2: Versioning saat API Berubah**
```
Masalah: Mobile app tidak bisa update serentak saat API berubah
Solusi: URL versioning + backward compatibility

/api/v1/products  → Versi lama (tetap support)
/api/v2/products  → Versi baru dengan breaking changes

// Strategi deprecation:
// 1. Announce deprecation 3 bulan sebelumnya
// 2. Tambahkan header: Deprecation: true, Sunset: "2024-06-01"
// 3. Maintain v1 selama 6 bulan setelah v2 release
```

**Tantangan 3: Performance untuk Halaman Produk**
```
Masalah: Halaman produk butuh data dari 3 endpoint berbeda
  - GET /products/:id
  - GET /products/:id/reviews
  - GET /products/:id/related

Solusi A: Composite endpoint (pragmatic)
  GET /products/:id?include=reviews,related

Solusi B: Tetap 3 request tapi parallel (frontend)
  Promise.all([
    fetch('/products/123'),
    fetch('/products/123/reviews'),
    fetch('/products/123/related')
  ])

Solusi C: Pertimbangkan GraphQL untuk use case ini
```

#### Keputusan Arsitektur Final

```
✅ Gunakan URL versioning (/api/v1/)
✅ Standarisasi response format dengan helper
✅ Pagination wajib untuk semua list endpoint
✅ Field selection opsional (?fields=id,name,price)
✅ Composite endpoint untuk use case yang sangat umum
✅ Rate limiting: 1000 req/menit untuk authenticated, 100 untuk public
✅ Dokumentasi dengan Swagger/OpenAPI
✅ Semantic versioning untuk API changelog
```

---

## SECTION 19 — SUMMARY & KEY TAKEAWAYS

### Ringkasan Konsep Utama

```
┌─────────────────────────────────────────────────────────────────┐
│                    KEY TAKEAWAYS                                 │
└─────────────────────────────────────────────────────────────────┘

1. HTTP PROTOCOL
   ├── Stateless, text-based, request-response
   ├── Request: Method + URL + Headers + Body
   └── Response: Status Code + Headers + Body

2. HTTP METHODS
   ├── GET    → Read (safe + idempotent)
   ├── POST   → Create (tidak safe, tidak idempotent)
   ├── PUT    → Full Update (idempotent)
   ├── PATCH  → Partial Update
   └── DELETE → Delete (idempotent)

3. STATUS CODES
   ├── 2xx → Success (200 OK, 201 Created, 204 No Content)
   ├── 4xx → Client Error (400, 401, 403, 404, 422, 429)
   └── 5xx → Server Error (500, 503)

4. REST PRINCIPLES
   ├── Client-Server Separation
   ├── Statelessness ← PALING PENTING
   ├── Cacheability
   ├── Uniform Interface
   ├── Layered System
   └── Code on Demand (opsional)

5. REST API DESIGN
   ├── Gunakan noun, bukan verb di URL
   ├── Plural untuk collections (/products, bukan /product)
   ├── Nested max 2 level (/users/:id/orders)
   ├── Query params untuk filter/sort/paginate
   └── Konsisten dalam response format

6. BEST PRACTICES
   ├── Validasi semua input
   ├── Gunakan status code yang tepat
   ├── Berikan error message yang informatif
   ├── Implementasi pagination
   └── Dokumentasikan API Anda
```

### Checklist Kesiapan

```
□ Saya bisa menjelaskan perbedaan HTTP dan REST
□ Saya bisa memilih HTTP method yang tepat untuk setiap operasi
□ Saya bisa menginterpretasikan status code dengan benar
□ Saya bisa merancang URL endpoint yang mengikuti konvensi REST
□ Saya bisa mengimplementasikan CRUD API dengan Express.js
□ Saya bisa membedakan kapan menggunakan PUT vs PATCH
□ Saya memahami mengapa REST bersifat stateless
□ Saya bisa melakukan debugging HTTP request dengan curl
```

---

## SECTION 20 — FURTHER LEARNING & REFERENCES

### 20.1 Topik Lanjutan yang Perlu Dipelajari

```
IMMEDIATE NEXT (Bab 09-12):
├── Database Integration (PostgreSQL/MySQL dengan REST API)
├── Authentication & Authorization (JWT, OAuth 2.0)
├── Input Validation Libraries (Joi, Zod, express-validator)
└── API Testing (Jest, Supertest)

INTERMEDIATE (Bab 13-20):
├── API Documentation (Swagger/OpenAPI)
├── Rate Limiting & Throttling
├── Caching Strategies (Redis)
├── File Upload dalam REST API
└── Pagination Patterns (cursor-based vs offset)

ADVANCED (Beyond Beginner):
├── GraphQL sebagai alternatif REST
├── gRPC untuk internal services
├── API Gateway patterns
├── Microservices dengan REST
└── Event-driven architecture
```

### 20.2 Referensi Resmi & Terpercaya

```
SPESIFIKASI & STANDAR:
├── RFC 7230-7235: HTTP/1.1 Specification
│   https://tools.ietf.org/html/rfc7230
├── RFC 7807: Problem Details for HTTP APIs
│   https://tools.ietf.org/html/rfc7807
└── Roy Fielding's Dissertation (REST Origin)
    https://www.ics.uci.edu/~fielding/pubs/dissertation/rest_arch_style.htm

DOKUMENTASI RESMI:
├── MDN Web Docs - HTTP
│   https://developer.mozilla.org/en-US/docs/Web/HTTP
├── Express.js Official Docs
│   https://expressjs.com/
└── Node.js Official Docs
    https://nodejs.org/en/docs/

BUKU YANG DIREKOMENDASIKAN:
├── "RESTful Web APIs" - Leonard Richardson & Mike Amundsen
├── "REST API Design Rulebook" - Mark Masse
└── "HTTP: The Definitive Guide" - David Gourley

TOOLS:
├── Postman          → https://www.postman.com/
├── Insomnia         → https://insomnia.rest/
├── Thunder Client   → VS Code Extension
├── HTTPie           → https://httpie.io/ (curl alternatif)
└── JSON Formatter   → https://jsonformatter.curiousconcept.com/
```

### 20.3 Project Mini untuk Portofolio

```
LEVEL 1 (Selesaikan minggu ini):
└── Todo List API dengan full CRUD + filtering + pagination

LEVEL 2 (Selesaikan bulan ini):
└── Blog API:
    ├── Articles (CRUD + search + category filter)
    ├── Comments (nested under articles)
    └── Tags (many-to-many dengan articles)

LEVEL 3 (Selesaikan setelah bab authentication):
└── E-Commerce API:
    ├── Products, Categories, Users
    ├── Cart & Orders
    ├── Authentication (JWT)
    └── Role-based access (admin, seller, buyer)
```

### 20.4 Komunitas & Diskusi

```
FORUM & KOMUNITAS:
├── Stack Overflow → tag: rest, http, express, node.js
├── Reddit         → r/webdev, r/node, r/learnprogramming
├── Discord        → Programmer Zaman Now, Dicoding Community
└── GitHub         → Explore REST API examples dan best practices

NEWSLETTER & BLOG:
├── Node Weekly    → https://nodeweekly.com/
├── API Evangelist → https://apievangelist.com/
└── Smashing Magazine → REST API articles
```

---

## APPENDIX: QUICK REFERENCE CARD

```
┌─────────────────────────────────────────────────────────────────┐
│                    HTTP & REST QUICK REFERENCE                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  METHOD    ENDPOINT           STATUS    USE CASE                 │
│  ──────    ────────           ──────    ────────                 │
│  GET       /resources         200       List all                 │
│  GET       /resources/:id     200/404   Get one                  │
│  POST      /resources         201       Create new               │
│  PUT       /resources/:id     200/404   Replace all fields       │
│  PATCH     /resources/:id     200/404   Update some fields       │
│  DELETE    /resources/:id     204/404   Delete                   │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  STATUS CODE CHEAT SHEET:                                        │
│  200 OK              → Berhasil (GET, PUT, PATCH)               │
│  201 Created         → Resource baru dibuat (POST)              │
│  204 No Content      → Berhasil, tanpa body (DELETE)            │
│  400 Bad Request     → Request malformed                        │
│  401 Unauthorized    → Belum login                              │
│  403 Forbidden       → Login tapi tidak punya izin              │
│  404 Not Found       → Resource tidak ada                       │
│  409 Conflict        → Duplikasi data                           │
│  422 Unprocessable   → Validasi gagal                           │
│  429 Too Many Req    → Rate limit                               │
│  500 Server Error    → Bug di server                            │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  URL DESIGN RULES:                                               │
│  ✅ /products          ❌ /getProducts                           │
│  ✅ /products/123      ❌ /product/123                           │
│  ✅ /users/1/orders    ❌ /getUserOrders/1                       │
│  ✅ /products?sort=asc ❌ /products/sort/asc                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

**Modul ini adalah bagian dari kurikulum Backend Beginner**
**Kategori: 01-Core-Foundations | Bab 08 | Module 01**
**Estimasi waktu belajar: 6-8 jam (termasuk latihan)**
**Tingkat kesulitan: ⭐⭐⭐☆☆ (Beginner-Intermediate)**