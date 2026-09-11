/**
 * Hands-on M02: Shadow DOM, Storage State Injector, & Network Interceptor Simulator
 * 
 * Fitur:
 * 1. Storage State Injection Engine (Bypass login instan via Cookies & LocalStorage).
 * 2. Nested Iframe & Shadow DOM Piercing Navigator.
 * 3. Network Route Interceptor (page.route: mock 200, mock 500, network abort).
 */

const ANSI = {
  reset: "\x1b[0m",
  green: "\x1b[32m",
  red: "\x1b[31m",
  yellow: "\x1b[33m",
  cyan: "\x1b[36m",
  bold: "\x1b[1m",
  dim: "\x1b[2m"
};

// ==========================================
// 1. STORAGE STATE INJECTION SIMULATOR
// ==========================================
class BrowserContextSimulator {
  constructor() {
    this.cookies = new Map();
    this.localStorage = new Map();
  }

  // Pre-seed auth storage
  injectStorageState({ cookies, origins }) {
    if (cookies) {
      for (const c of cookies) {
        this.cookies.set(c.name, c.value);
      }
    }
    if (origins) {
      for (const origin of origins) {
        for (const item of origin.localStorage) {
          this.localStorage.set(`${origin.origin}::${item.name}`, item.value);
        }
      }
    }
  }

  isAuthenticated() {
    const hasSessionCookie = this.cookies.has("session_token");
    const hasJwtStorage = this.localStorage.has("https://app.id::auth_jwt");
    return hasSessionCookie && hasJwtStorage;
  }
}

// ==========================================
// 2. NESTED IFRAME & SHADOW DOM SIMULATOR
// ==========================================
class ComplexDomEnvironment {
  constructor() {
    // Hierarki: Parent Page -> Iframe -> Shadow Root -> Target Input
    this.tree = {
      tag: "HTML_PARENT",
      children: [
        {
          tag: "IFRAME",
          id: "stripe-payment-frame",
          src: "https://secure.stripe.com/v3",
          contentDocument: {
            tag: "HTML_IFRAME_DOC",
            children: [
              {
                tag: "PAYMENT-CARD-ELEMENT", // Custom Web Component
                shadowRoot: {
                  mode: "open",
                  children: [
                    { tag: "INPUT", id: "card-number-input", placeholder: "4111 2222 3333 4444" },
                    { tag: "INPUT", id: "cvv-input", placeholder: "123" }
                  ]
                }
              }
            ]
          }
        }
      ]
    };
  }

  // Menavigasi Iframe + Shadow DOM Piercing
  findInFrameAndShadow(iframeId, shadowSelectorId) {
    const iframe = this.tree.children.find(el => el.tag === "IFRAME" && el.id === iframeId);
    if (!iframe) throw new Error(`Iframe #${iframeId} tidak ditemukan`);

    const customElement = iframe.contentDocument.children.find(el => el.shadowRoot);
    if (!customElement) throw new Error("Shadow root tidak ditemukan di dalam iframe");

    const targetElement = customElement.shadowRoot.children.find(el => el.id === shadowSelectorId);
    if (!targetElement) throw new Error(`Elemen #${shadowSelectorId} tidak ditemukan di dalam Shadow DOM`);

    return targetElement;
  }
}

// ==========================================
// 3. NETWORK ROUTE INTERCEPTOR SIMULATOR
// ==========================================
class NetworkRouterSimulator {
  constructor() {
    this.routes = [];
  }

  route(urlPattern, handler) {
    this.routes.push({ pattern: new RegExp(urlPattern.replace(/\*/g, ".*")), handler });
  }

  async dispatch(url, requestOptions = {}) {
    for (const r of this.routes) {
      if (r.pattern.test(url)) {
        let routeResult = null;
        const routeControl = {
          fulfill: async (response) => {
            routeResult = { type: "MOCK_FULFILL", ...response };
          },
          abort: async () => {
            routeResult = { type: "NETWORK_ABORT", error: "net::ERR_INTERNET_DISCONNECTED" };
          }
        };
        await r.handler(routeControl);
        return routeResult;
      }
    }
    // Default: Fallback ke jaringan asli
    return { type: "PASSTHROUGH", status: 200, body: "Live API Response" };
  }
}

// ==========================================
// 4. MAIN SIMULATION EXECUTION
// ==========================================
async function main() {
  console.log(`${ANSI.bold}╔═══════════════════════════════════════════════════════════════╗`);
  console.log(`║     ADVANCED WEB TESTING: IFRAMES, SHADOW DOM & STORAGE       ║`);
  console.log(`╚═══════════════════════════════════════════════════════════════╝${ANSI.reset}`);

  // 1. STORAGE STATE INJECTION BENCHMARK
  console.log(`\n${ANSI.bold}${ANSI.cyan}=== 1. STORAGE STATE INJECTION VS TRADITIONAL UI LOGIN ===${ANSI.reset}`);
  
  // Skenario A: Tradisional UI Login (Simulasi mengetik formulir)
  console.log(`  [Metode Tradisional] Mengetik email, password, klik tombol, menunggu 2FA...`);
  const t0 = Date.now();
  await new Promise(r => setTimeout(r, 200)); // Simulasi latency UI
  const uiLoginTime = Date.now() - t0;
  console.log(`    Waktu Eksekusi: ${ANSI.yellow}${uiLoginTime}ms${ANSI.reset} per test case`);

  // Skenario B: Storage State Injection (Injeksi instan)
  const context = new BrowserContextSimulator();
  const t1 = Date.now();
  context.injectStorageState({
    cookies: [{ name: "session_token", value: "sess_xyz_7712_active" }],
    origins: [{
      origin: "https://app.id",
      localStorage: [{ name: "auth_jwt", value: "eyJhbGciOiJIUzI1..." }]
    }]
  });
  const storageInjectTime = Date.now() - t1;
  console.log(`  [Playwright Storage Injection] Menyuntikkan auth cookies & localStorage secara instan...`);
  console.log(`    Waktu Eksekusi: ${ANSI.green}${storageInjectTime}ms${ANSI.reset} | Status Terotentikasi: ${context.isAuthenticated() ? ANSI.green + "YES" : ANSI.red + "NO"}${ANSI.reset}`);
  console.log(`    ${ANSI.bold}Efisiensi:${ANSI.reset} Menghemat > 95% waktu overhead login di setiap skenario test!`);

  // 2. IFRAME & SHADOW DOM PIERCING
  console.log(`\n${ANSI.bold}${ANSI.cyan}=== 2. IFRAME & SHADOW DOM PIERCING SIMULATION ===${ANSI.reset}`);
  const dom = new ComplexDomEnvironment();

  console.log("  Mencari elemen kartu kredit di dalam: Parent ➔ Iframe#stripe-payment-frame ➔ Shadow DOM...");
  const cardInput = dom.findInFrameAndShadow("stripe-payment-frame", "card-number-input");
  const cvvInput = dom.findInFrameAndShadow("stripe-payment-frame", "cvv-input");

  console.log(`    ${ANSI.green}✓ Ditemukan Elemen:${ANSI.reset} <${cardInput.tag} id="${cardInput.id}" placeholder="${cardInput.placeholder}">`);
  console.log(`    ${ANSI.green}✓ Ditemukan Elemen:${ANSI.reset} <${cvvInput.tag} id="${cvvInput.id}" placeholder="${cvvInput.placeholder}">`);
  console.log(`    ${ANSI.dim}Playwright frameLocator() berhasil menembus enkapsulasi dokumen terisolasi.${ANSI.reset}`);

  // 3. NETWORK ROUTE INTERCEPTION & MOCKING
  console.log(`\n${ANSI.bold}${ANSI.cyan}=== 3. NETWORK INTERCEPTION (page.route) MOCKING ===${ANSI.reset}`);
  const router = new NetworkRouterSimulator();

  // Route 1: Mock Respon Sukses Khusus
  router.route("**/api/v1/orders", async (route) => {
    await route.fulfill({
      status: 200,
      body: JSON.stringify({ orderId: "ORD-MOCK-99", status: "SETTLED", total: 125000 })
    });
  });

  // Route 2: Mock Error 500 untuk Uji Ketahanan Frontend
  router.route("**/api/v1/catalog/fail", async (route) => {
    await route.fulfill({
      status: 500,
      body: JSON.stringify({ error: "INTERNAL_SERVER_ERROR", message: "Database Down" })
    });
  });

  // Route 3: Mock Offline Network Abort
  router.route("**/api/v1/offline", async (route) => {
    await route.abort();
  });

  // Eksekusi Uji 1: Mocked Success
  const res1 = await router.dispatch("https://api.shop.id/api/v1/orders");
  console.log(`  1. Dispatch GET /orders: Status ${res1.status} | Data: ${res1.body}`);

  // Eksekusi Uji 2: Mocked Server Error 500
  const res2 = await router.dispatch("https://api.shop.id/api/v1/catalog/fail");
  console.log(`  2. Dispatch GET /catalog/fail: ${ANSI.yellow}Status ${res2.status} (Simulasi Crash Server Berhasil)${ANSI.reset}`);

  // Eksekusi Uji 3: Offline Disconnect
  const res3 = await router.dispatch("https://api.shop.id/api/v1/offline");
  console.log(`  3. Dispatch GET /offline: ${ANSI.red}${res3.error} (Simulasi Terputus Jaringan)${ANSI.reset}`);

  console.log(`\n${ANSI.green}✓ Advanced Web Automation Lab executed successfully!${ANSI.reset}\n`);
}

main();
