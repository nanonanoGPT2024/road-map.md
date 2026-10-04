/**
 * SIMULATOR: tRPC & Zod Contract-First End-to-End Type Safety Engine
 * -----------------------------------------------------------------------------
 * File: trpc_zod_end_to_end_safety_sim.js
 * Deskripsi: Implementasi mandiri (zero external dependencies) dari mekanisme
 * validasi runtime ala Zod, inferensi skema, middleware context, dan
 * Remote Procedure Call (tRPC) dispatcher dengan proteksi tipe penuh.
 */

// =============================================================================
// 1. MINI-ZOD RUNTIME SCHEMA ENGINE
// =============================================================================

class ZodError {
  constructor(issues) {
    this.name = "ZodError";
    this.issues = issues;
  }

  format() {
    return this.issues.map((i) => `  - [${i.path.join(".")}] ${i.message}`).join("\n");
  }
}

class ZodType {
  constructor() {
    this.transforms = [];
    this.refinements = [];
  }

  transform(fn) {
    this.transforms.push(fn);
    return this;
  }

  refine(validator, message) {
    this.refinements.push({ validator, message });
    return this;
  }

  safeParse(val) {
    const issues = [];
    const parsed = this._parse(val, issues, []);
    if (issues.length > 0) {
      return { success: false, error: new ZodError(issues) };
    }

    let result = parsed;
    for (const tf of this.transforms) {
      result = tf(result);
    }

    for (const ref of this.refinements) {
      if (!ref.validator(result)) {
        issues.push({ path: ["_root"], message: ref.message });
        return { success: false, error: new ZodError(issues) };
      }
    }

    return { success: true, data: result };
  }
}

class ZodString extends ZodType {
  constructor() {
    super();
    this.minLen = null;
    this.isEmailFormat = false;
    this.isUuidFormat = false;
  }

  min(len, msg) {
    this.minLen = { len, msg: msg || `String harus minimal ${len} karakter` };
    return this;
  }

  email(msg) {
    this.isEmailFormat = msg || "Format email tidak valid";
    return this;
  }

  uuid(msg) {
    this.isUuidFormat = msg || "Format UUID tidak valid";
    return this;
  }

  toLowerCase() {
    return this.transform((val) => (typeof val === "string" ? val.toLowerCase() : val));
  }

  _parse(val, issues, path) {
    if (typeof val !== "string") {
      issues.push({ path, message: `Expected string, received ${typeof val}` });
      return val;
    }
    if (this.minLen && val.length < this.minLen.len) {
      issues.push({ path, message: this.minLen.msg });
    }
    if (this.isEmailFormat && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val)) {
      issues.push({ path, message: this.isEmailFormat });
    }
    if (this.isUuidFormat && !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(val)) {
      issues.push({ path, message: this.isUuidFormat });
    }
    return val;
  }
}

class ZodNumber extends ZodType {
  constructor() {
    super();
    this.mustBeInt = false;
    this.minVal = null;
  }

  int(msg) {
    this.mustBeInt = msg || "Nilai harus berupa bilangan bulat (integer)";
    return this;
  }

  positive(msg) {
    this.minVal = { val: 0.000001, msg: msg || "Nilai harus positif (> 0)" };
    return this;
  }

  min(min, msg) {
    this.minVal = { val: min, msg: msg || `Nilai minimal ${min}` };
    return this;
  }

  _parse(val, issues, path) {
    if (typeof val !== "number" || isNaN(val)) {
      issues.push({ path, message: `Expected number, received ${typeof val}` });
      return val;
    }
    if (this.mustBeInt && !Number.isInteger(val)) {
      issues.push({ path, message: this.mustBeInt });
    }
    if (this.minVal && val < this.minVal.val) {
      issues.push({ path, message: this.minVal.msg });
    }
    return val;
  }
}

class ZodObject extends ZodType {
  constructor(shape) {
    super();
    this.shape = shape;
  }

  _parse(val, issues, path) {
    if (typeof val !== "object" || val === null) {
      issues.push({ path, message: `Expected object, received ${typeof val}` });
      return val;
    }

    const result = {};
    for (const key of Object.keys(this.shape)) {
      const childSchema = this.shape[key];
      const childVal = val[key];
      const childPath = [...path, key];
      result[key] = childSchema._parse(childVal, issues, childPath);
    }
    return result;
  }
}

class ZodArray extends ZodType {
  constructor(itemSchema) {
    super();
    this.itemSchema = itemSchema;
    this.minLen = null;
  }

  min(len, msg) {
    this.minLen = { len, msg: msg || `Array minimal memiliki ${len} item` };
    return this;
  }

  _parse(val, issues, path) {
    if (!Array.isArray(val)) {
      issues.push({ path, message: `Expected array, received ${typeof val}` });
      return val;
    }
    if (this.minLen && val.length < this.minLen.len) {
      issues.push({ path, message: this.minLen.msg });
    }
    return val.map((item, idx) => this.itemSchema._parse(item, issues, [...path, `[${idx}]`]));
  }
}

const z = {
  string: () => new ZodString(),
  number: () => new ZodNumber(),
  object: (shape) => new ZodObject(shape),
  array: (item) => new ZodArray(item),
};

// =============================================================================
// 2. MINI-tRPC DISPATCHER ENGINE
// =============================================================================

class TRPCError extends Error {
  constructor({ code, message }) {
    super(message);
    this.code = code;
    this.name = "TRPCError";
  }
}

class Procedure {
  constructor() {
    this._inputSchema = null;
    this._middlewares = [];
    this._resolver = null;
    this.type = "query"; // 'query' | 'mutation'
  }

  input(schema) {
    this._inputSchema = schema;
    return this;
  }

  use(middleware) {
    this._middlewares.push(middleware);
    return this;
  }

  query(resolver) {
    this.type = "query";
    this._resolver = resolver;
    return this;
  }

  mutation(resolver) {
    this.type = "mutation";
    this._resolver = resolver;
    return this;
  }

  async execute(rawInput, context) {
    // 1. Eksekusi Middleware Pipeline Terlebih Dahulu (Auth Guard / Context Enrichener)
    let currentCtx = { ...context };
    const runMiddleware = async (index) => {
      if (index < this._middlewares.length) {
        const mw = this._middlewares[index];
        return await mw({
          ctx: currentCtx,
          next: async (opts) => {
            if (opts && opts.ctx) currentCtx = { ...currentCtx, ...opts.ctx };
            return await runMiddleware(index + 1);
          },
        });
      } else {
        // 2. Validasi Input Skema via Zod setelah lolos Middleware
        let validatedInput = rawInput;
        if (this._inputSchema) {
          const parseResult = this._inputSchema.safeParse(rawInput);
          if (!parseResult.success) {
            throw new TRPCError({
              code: "BAD_REQUEST",
              message: `Validasi Input Gagal:\n${parseResult.error.format()}`,
            });
          }
          validatedInput = parseResult.data;
        }

        // 3. Eksekusi Resolver Utama
        return await this._resolver({ input: validatedInput, ctx: currentCtx });
      }
    };

    return await runMiddleware(0);
  }
}

class TRPCRouter {
  constructor(routes) {
    this.routes = routes;
  }

  async caller(procedurePath, input, context = {}) {
    const procedure = this.routes[procedurePath];
    if (!procedure) {
      throw new TRPCError({
        code: "NOT_FOUND",
        message: `Procedure '${procedurePath}' tidak ditemukan di router!`,
      });
    }
    return await procedure.execute(input, context);
  }
}

// =============================================================================
// 3. SKENARIO IMPLEMENTASI NYATA: E-COMMERCE CHECKOUT SERVICE
// =============================================================================

// Skema Validasi Payload Checkout
const OrderItemSchema = z.object({
  sku: z.string().min(3, "Kode SKU minimal 3 karakter"),
  quantity: z.number().int("Kuantitas harus bilangan bulat").positive("Kuantitas minimal 1 unit"),
  unitPrice: z.number().positive("Harga satuan harus lebih dari 0"),
});

const CheckoutInputSchema = z.object({
  customerId: z.string().uuid("Customer ID harus berupa UUID v4 yang valid"),
  customerEmail: z.string().email("Format email customer tidak valid").toLowerCase(),
  items: z.array(OrderItemSchema).min(1, "Daftar belanja minimal memiliki 1 barang"),
}).refine(
  (data) => {
    // Total belanja tidak boleh melebihi limit Rp 100.000.000 dalam satu transaksi
    const total = data.items.reduce((acc, item) => acc + (item.quantity * item.unitPrice), 0);
    return total <= 100000000;
  },
  "Total nilai transaksi melebihi batas limit harian Rp 100.000.000"
);

// Middleware Proteksi Autentikasi
const authMiddleware = async ({ ctx, next }) => {
  if (!ctx.session || !ctx.session.userId) {
    throw new TRPCError({
      code: "UNAUTHORIZED",
      message: "Akses ditolak: Anda harus login untuk melakukan transaksi ini.",
    });
  }
  return await next({
    ctx: {
      user: { id: ctx.session.userId, role: ctx.session.role || "CUSTOMER" },
    },
  });
};

// Middleware Admin Role Check
const adminOnlyMiddleware = async ({ ctx, next }) => {
  if (ctx.user.role !== "ADMIN") {
    throw new TRPCError({
      code: "FORBIDDEN",
      message: "Akses terlarang: Prosedur ini membutuhkan wewenang ADMINISTRATOR.",
    });
  }
  return await next();
};

// Database Mock
const mockDatabase = {
  orders: [],
};

// Pembentukan Router Backend tRPC
const appRouter = new TRPCRouter({
  // Query: Mengambil ringkasan pesanan
  getOrders: new Procedure()
    .use(authMiddleware)
    .query(async ({ ctx }) => {
      return {
        callerUserId: ctx.user.id,
        totalOrders: mockDatabase.orders.length,
        orders: mockDatabase.orders,
      };
    }),

  // Mutation: Melakukan checkout aman
  checkout: new Procedure()
    .use(authMiddleware)
    .input(CheckoutInputSchema)
    .mutation(async ({ input, ctx }) => {
      const orderTotal = input.items.reduce((acc, item) => acc + (item.quantity * item.unitPrice), 0);
      const newOrder = {
        id: `ORD-${Date.now()}`,
        userId: ctx.user.id,
        customerId: input.customerId,
        customerEmail: input.customerEmail, // otomatis lowercase via transform
        items: input.items,
        totalAmount: orderTotal,
        createdAt: new Date(), // Serialization test
        status: "COMPLETED",
      };

      mockDatabase.orders.push(newOrder);
      return {
        success: true,
        orderId: newOrder.id,
        chargedAmount: orderTotal,
        timestamp: newOrder.createdAt.toISOString(),
      };
    }),

  // Admin Procedure: Reset database
  purgeAllOrders: new Procedure()
    .use(authMiddleware)
    .use(adminOnlyMiddleware)
    .mutation(async ({ ctx }) => {
      const count = mockDatabase.orders.length;
      mockDatabase.orders = [];
      return { purgedCount: count, message: "Seluruh pesanan berhasil dihapus oleh admin." };
    }),
});

// =============================================================================
// 4. EKSEKUSI SIMULASI CLIENT-SERVER END-TO-END
// =============================================================================

async function runSimulation() {
  console.log("===========================================================================");
  console.log("SIMULASI: tRPC + ZOD CONTRACT-FIRST END-TO-END TYPE SAFETY");
  console.log("===========================================================================\n");

  // TEST 1: Request tanpa autentikasi (Gagal di Middleware)
  console.log("--- TEST 1: Memanggil checkout tanpa login (Anonymous Caller) ---");
  try {
    await appRouter.caller("checkout", {}, {});
  } catch (err) {
    console.log(`❌ [DITOLAK MIDDLEWARE] Code: ${err.code} | Pesan: ${err.message}\n`);
  }

  // TEST 2: Request login tapi payload cacat (Gagal di Zod Runtime Validation)
  console.log("--- TEST 2: Payload Cacat (UUID salah, Email typo, Jumlah 0) ---");
  const authenticatedContext = {
    session: { userId: "usr_9981", role: "CUSTOMER" },
  };

  const invalidPayload = {
    customerId: "invalid-uuid-format-123",
    customerEmail: "budi-bukan-email",
    items: [
      { sku: "IP", quantity: 0, unitPrice: -5000 },
    ],
  };

  try {
    await appRouter.caller("checkout", invalidPayload, authenticatedContext);
  } catch (err) {
    console.log(`❌ [DITOLAK ZOD VALIDATOR] Code: ${err.code}`);
    console.log(err.message + "\n");
  }

  // TEST 3: Request dengan payload valid (Sukses)
  console.log("--- TEST 3: Payload Valid Sesuai Kontrak Penuh ---");
  const validPayload = {
    customerId: "c73a9482-6298-4e3a-9642-12628468b8e2",
    customerEmail: "BUDI.SANTOSO@Perusahaan.CO.ID", // Menguji transformasi toLowerCase
    items: [
      { sku: "MACBOOK-M3-PRO", quantity: 2, unitPrice: 32000000 },
      { sku: "LOGITECH-MX-MASTER", quantity: 1, unitPrice: 1500000 },
    ],
  };

  try {
    const response = await appRouter.caller("checkout", validPayload, authenticatedContext);
    console.log("✅ [TRANSAKSI BERHASIL]");
    console.log(`   Order ID: ${response.orderId}`);
    console.log(`   Total Bayar: Rp ${response.chargedAmount.toLocaleString("id-ID")}`);
    console.log(`   Waktu Transaksi: ${response.timestamp}`);
    console.log(`   Email Ternormalisasi: ${mockDatabase.orders[0].customerEmail}\n`);
  } catch (err) {
    console.error("Gagal:", err);
  }

  // TEST 4: Non-admin mencoba eksekusi prosedur terlarang (Admin Guard Test)
  console.log("--- TEST 4: Customer Biasa Mencoba Menghapus Data (Admin-Only Procedure) ---");
  try {
    await appRouter.caller("purgeAllOrders", {}, authenticatedContext);
  } catch (err) {
    console.log(`❌ [DITOLAK ROLE GUARD] Code: ${err.code} | Pesan: ${err.message}\n`);
  }

  // TEST 5: Admin memanggil Prosedur Pembersihan (Sukses)
  console.log("--- TEST 5: Administrator Resmi Memanggil Pembersihan ---");
  const adminContext = {
    session: { userId: "usr_admin_01", role: "ADMIN" },
  };
  try {
    const adminRes = await appRouter.caller("purgeAllOrders", {}, adminContext);
    console.log(`✅ [ADMIN SUKSES] ${adminRes.message} (Total dihapus: ${adminRes.purgedCount})\n`);
  } catch (err) {
    console.error("Gagal:", err);
  }

  console.log("===========================================================================");
  console.log("SIMULASI SELESAI: Validasi runtime dan proteksi tipe tRPC terbukti andal!");
  console.log("===========================================================================");
}

runSimulation();
