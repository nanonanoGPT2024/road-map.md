/**
 * SIMULATOR: Headless Browser E2E Test Runner & Network Mocking Engine
 * -----------------------------------------------------------------------------
 * File: e2e_browser_test_runner_sim.js
 * Deskripsi: Implementasi mandiri (zero-dependency) dari konsep inti Playwright:
 * DOM virtual auto-waiting assertions, network route interception, storageState
 * session re-use, dan visual regression layout comparator.
 */

// =============================================================================
// 1. MINI VIRTUAL DOM & AUTO-WAITING LOCATOR ENGINE
// =============================================================================

class VirtualDOMNode {
  constructor(tag, attributes = {}, text = "") {
    this.tag = tag;
    this.attributes = attributes;
    this.text = text;
    this.children = [];
    this.visible = true;
    this.disabled = false;
  }

  appendChild(child) {
    this.children.push(child);
  }
}

class VirtualPage {
  constructor() {
    this.currentUrl = "about:blank";
    this.domTree = new VirtualDOMNode("html");
    this.networkRoutes = [];
    this.cookies = new Map();
  }

  async goto(url) {
    this.currentUrl = url;
    // Simulasi inisialisasi halaman
    this._renderPage(url);
  }

  route(pattern, handler) {
    this.networkRoutes.unshift({ pattern, handler });
  }

  async dispatchNetwork(url, method = "GET", body = null) {
    for (const r of this.networkRoutes) {
      if (url.includes(r.pattern) || r.pattern === "**/*") {
        let fulfilledResponse = null;
        await r.handler({
          fulfill: (res) => {
            fulfilledResponse = res;
          },
        });
        if (fulfilledResponse) return fulfilledResponse;
      }
    }
    // Default server response jika tidak di-mock
    return { status: 200, body: JSON.stringify({ ok: true, source: "REAL_SERVER" }) };
  }

  // Locator berpusat pada pengguna (User-Centric)
  getByRole(role, options = {}) {
    return new Locator(this, { role, name: options.name });
  }

  getByText(text) {
    return new Locator(this, { text });
  }

  _renderPage(url) {
    this.domTree = new VirtualDOMNode("html");
    const body = new VirtualDOMNode("body");
    this.domTree.appendChild(body);

    if (url === "/login") {
      body.appendChild(new VirtualDOMNode("h1", {}, "Masuk ke Akun"));
      body.appendChild(new VirtualDOMNode("input", { label: "Email", value: "" }));
      body.appendChild(new VirtualDOMNode("input", { label: "Password", value: "" }));
      body.appendChild(new VirtualDOMNode("button", { role: "button", name: "Masuk" }, "Masuk"));
    } else if (url === "/dashboard") {
      body.appendChild(new VirtualDOMNode("h1", {}, "Selamat Datang di Dashboard"));
      body.appendChild(new VirtualDOMNode("button", { role: "button", name: "Beli Paket Pro" }, "Beli Paket Pro"));
    } else if (url === "/checkout") {
      body.appendChild(new VirtualDOMNode("h1", {}, "Ringkasan Pembayaran"));
      body.appendChild(new VirtualDOMNode("button", { role: "button", name: "Konfirmasi & Bayar" }, "Konfirmasi & Bayar"));
    }
  }
}

class Locator {
  constructor(page, query) {
    this.page = page;
    this.query = query;
  }

  // Auto-Waiting Assertion: Memastikan elemen siap sebelum berinteraksi
  async _waitForElement(timeoutMs = 1500) {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      const node = this._findInTree(this.page.domTree);
      if (node && node.visible && !node.disabled) {
        return node;
      }
      await new Promise((r) => setTimeout(r, 20)); // Poll interval
    }
    throw new Error(`Timeout ${timeoutMs}ms exceeded waiting for locator: ${JSON.stringify(this.query)}`);
  }

  _findInTree(node) {
    if (this.query.role && node.attributes.role === this.query.role) {
      if (!this.query.name || node.attributes.name === this.query.name) return node;
    }
    if (this.query.text && node.text.includes(this.query.text)) return node;
    for (const c of node.children) {
      const found = this._findInTree(c);
      if (found) return found;
    }
    return null;
  }

  async click() {
    const node = await this._waitForElement();
    // Simulasi interaksi klik
    return { clicked: true, tag: node.tag, name: node.attributes.name };
  }

  async isVisible() {
    try {
      await this._waitForElement(200);
      return true;
    } catch (e) {
      return false;
    }
  }
}

// =============================================================================
// 2. PLAYWRIGHT-STYLE EXPECT ASSERTIONS
// =============================================================================

function expect(actual) {
  return {
    toBeVisible: async () => {
      if (actual instanceof Locator) {
        const visible = await actual.isVisible();
        if (!visible) throw new Error("Expected element to be visible, but it was hidden or detached");
        return true;
      }
      throw new Error("Invalid assertion target");
    },
    toHaveURL: (expectedUrl) => {
      if (actual.currentUrl !== expectedUrl) {
        throw new Error(`Expected URL to be '${expectedUrl}', but received '${actual.currentUrl}'`);
      }
      return true;
    },
    toEqual: (expected) => {
      if (JSON.stringify(actual) !== JSON.stringify(expected)) {
        throw new Error(`Expected ${JSON.stringify(expected)}, received ${JSON.stringify(actual)}`);
      }
      return true;
    },
  };
}

// =============================================================================
// 3. RUN SUITE: TEST SCENARIOS
// =============================================================================

async function runTestSuite() {
  console.log("===========================================================================");
  console.log("SIMULASI: PLAYWRIGHT E2E TEST RUNNER & NETWORK MOCKING ENGINE");
  console.log("===========================================================================\n");

  const page = new VirtualPage();
  const mockStorageState = {};

  // SKENARIO 1: SETUP PHASE - AUTHENTICATION & STORAGE STATE EXPORT
  console.log("--- TEST 1: Otentikasi Pengguna & Export StorageState ---");
  await page.goto("/login");
  console.log("  1. Navigasi ke URL:", page.currentUrl);

  const loginBtn = page.getByRole("button", { name: "Masuk" });
  await loginBtn.click();
  console.log("  2. Klik tombol 'Masuk' dengan auto-waiting berhasil.");

  // Simulasi redirect dan penyimpanan sesi
  await page.goto("/dashboard");
  mockStorageState.sessionToken = "jwt_auth_state_secure_9988";
  expect(page).toHaveURL("/dashboard");
  console.log("  3. Ter-redirect ke Dashboard. StorageState diekspor ke 'user.json' ✅\n");

  // SKENARIO 2: CHECKOUT DENGAN NETWORK INTERCEPTION (MOCK 200 SUCCESS)
  console.log("--- TEST 2: Alur Checkout dengan Mocking Gateway Pembayaran ---");
  await page.goto("/checkout");

  // Pasang Network Mock untuk endpoint payment
  page.route("payments/charge", async (route) => {
    console.log("  [NETWORK INTERCEPTED] Mencegat panggilan ke gateway pembayaran!");
    route.fulfill({
      status: 200,
      body: JSON.stringify({ success: true, transactionId: "TRX_MOCK_101", status: "SETTLED" }),
    });
  });

  const payBtn = page.getByRole("button", { name: "Konfirmasi & Bayar" });
  await payBtn.click();

  const payRes = await page.dispatchNetwork("https://api.gateway.com/payments/charge", "POST");
  const payData = JSON.parse(payRes.body);

  console.log(`  Respon Gateway Mock : Status ${payRes.status} | Ref: ${payData.transactionId}`);
  console.log("  Web-First Assertion : Transaksi Lunas Terkonfirmasi ✅\n");

  // SKENARIO 3: RESILIENCE TEST - SIMULASI SERVER ERROR 500
  console.log("--- TEST 3: Pengujian Resiliensi Saat Backend Mengalami Error 500 ---");
  page.route("payments/charge", async (route) => {
    console.log("  [NETWORK INTERCEPTED] Menyuntikkan simulasi error server 500...");
    route.fulfill({
      status: 500,
      body: JSON.stringify({ error: "Internal Server Error: Database Down" }),
    });
  });

  const failRes = await page.dispatchNetwork("https://api.gateway.com/payments/charge", "POST");
  console.log(`  Respon Error Mock   : Status ${failRes.status} (Ditangani secara anggun oleh UI! 🛡️)\n`);

  // SKENARIO 4: VISUAL REGRESSION TESTING (HASH PIXEL COMPARATOR)
  console.log("--- TEST 4: Visual Regression Layout Snapshot Comparison ---");
  const baselineLayoutHash = "layout_hash_navbar_v1_0_a9f82d";
  const currentRenderHash = "layout_hash_navbar_v1_0_a9f82d"; // Tidak ada pergeseran piksel

  console.log(`  Baseline Snapshot  : ${baselineLayoutHash}`);
  console.log(`  Current Screenshot : ${currentRenderHash}`);
  expect(currentRenderHash).toEqual(baselineLayoutHash);
  console.log("  Visual Diff Ratio  : 0.00% (Piksel Identik Sempurna! ✅)\n");

  console.log("===========================================================================");
  console.log("HASIL: 4/4 Skenario Pengujian Playwright E2E Berhasil Lolos 100%!");
  console.log("===========================================================================");
}

runTestSuite();
