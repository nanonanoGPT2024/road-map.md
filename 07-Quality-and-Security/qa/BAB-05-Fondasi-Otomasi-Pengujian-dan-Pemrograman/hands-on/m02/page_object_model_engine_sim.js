/**
 * Hands-on M02: Page Object Model (POM) Architecture & Test Data Factory Simulator
 * 
 * Demonstrasi:
 * 1. Virtual Browser DOM Driver (Simulasi engine peramban Playwright/Cypress).
 * 2. Arsitektur Page Object Model (BasePage, LoginPage, DashboardPage).
 * 3. Fluent API & Method Chaining Pattern.
 * 4. Test Data Factory (Generasi data dinamis unik).
 * 5. Pemisahan Tegas (Separation of Concerns: Assertions di file test, DOM di Page Object).
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
// 1. VIRTUAL BROWSER DRIVER (Browser Engine)
// ==========================================
class VirtualBrowserDriver {
  constructor() {
    this.currentUrl = "about:blank";
    this.dom = new Map();
    this.history = [];
  }

  async goto(url) {
    this.currentUrl = url;
    this.history.push(`GOTO: ${url}`);
  }

  async fill(selector, value) {
    this.dom.set(selector, { value, type: "input" });
    this.history.push(`FILL [${selector}] with "${value}"`);
  }

  async click(selector) {
    this.history.push(`CLICK [${selector}]`);
    // Simulasi interaksi backend halaman
    if (selector === "[data-testid='login-submit']") {
      const email = this.dom.get("[data-testid='input-email']")?.value;
      const pass = this.dom.get("[data-testid='input-password']")?.value;

      if (email === "valid_qa@testing.id" && pass === "ValidPassword123!") {
        this.currentUrl = "/dashboard";
        this.dom.set(".welcome-heading", { text: "Selamat Datang, Budi QA" });
      } else {
        this.dom.set(".alert-box", { text: "Kredensial email atau password salah" });
      }
    }
  }

  async getText(selector) {
    const el = this.dom.get(selector);
    return el?.text || el?.value || "";
  }

  async getUrl() {
    return this.currentUrl;
  }
}

// ==========================================
// 2. TEST DATA FACTORY (Factory Pattern)
// ==========================================
class UserDataFactory {
  static createValidUser(overrides = {}) {
    const randomId = Math.floor(1000 + Math.random() * 9000);
    return {
      fullName: `Tester Otomasi ${randomId}`,
      email: "valid_qa@testing.id",
      password: "ValidPassword123!",
      role: "SDET",
      ...overrides
    };
  }

  static createInvalidUser() {
    return {
      email: `fake_${Date.now()}@invalid.com`,
      password: "WrongPassword999!"
    };
  }
}

// ==========================================
// 3. PAGE OBJECT MODEL (POM ARCHITECTURE)
// ==========================================

// Base Page
class BasePage {
  constructor(driver) {
    this.driver = driver;
  }
  async getPageUrl() {
    return await this.driver.getUrl();
  }
}

// Login Page Object
class LoginPage extends BasePage {
  constructor(driver) {
    super(driver);
    // Locators terpusat di constructor
    this.locators = {
      emailInput: "[data-testid='input-email']",
      passwordInput: "[data-testid='input-password']",
      submitButton: "[data-testid='login-submit']",
      errorMessage: ".alert-box"
    };
  }

  async navigate() {
    await this.driver.goto("/login");
    return this; // Fluent interface
  }

  async enterEmail(email) {
    await this.driver.fill(this.locators.emailInput, email);
    return this;
  }

  async enterPassword(password) {
    await this.driver.fill(this.locators.passwordInput, password);
    return this;
  }

  async clickSubmit() {
    await this.driver.click(this.locators.submitButton);
    return this;
  }

  // Action Composite
  async loginWith(email, password) {
    await this.enterEmail(email);
    await this.enterPassword(password);
    await this.clickSubmit();
  }

  // State Inquiries untuk Assertion (Tanpa expect di dalam page!)
  async getErrorMessage() {
    return await this.driver.getText(this.locators.errorMessage);
  }
}

// Dashboard Page Object
class DashboardPage extends BasePage {
  constructor(driver) {
    super(driver);
    this.locators = {
      welcomeHeading: ".welcome-heading"
    };
  }

  async getWelcomeText() {
    return await this.driver.getText(this.locators.welcomeHeading);
  }
}

// ==========================================
// 4. TEST CASE EXECUTION (TIER 1)
// ==========================================
async function main() {
  console.log(`${ANSI.bold}╔═══════════════════════════════════════════════════════════════╗`);
  console.log(`║      PAGE OBJECT MODEL & TEST DATA FACTORY ARCHITECTURE       ║`);
  console.log(`╚═══════════════════════════════════════════════════════════════╝${ANSI.reset}`);

  const driver = new VirtualBrowserDriver();

  // Test Case 1: Positive Login Flow
  console.log(`\n${ANSI.bold}${ANSI.cyan}=== TEST 1: POSITIVE LOGIN FLOW (MENGGUNAKAN POM & DATA FACTORY) ===${ANSI.reset}`);
  const validUser = UserDataFactory.createValidUser();
  const loginPage = new LoginPage(driver);
  const dashboardPage = new DashboardPage(driver);

  console.log(`  [Data Factory] Menggunakan user dinamis: ${validUser.email} (${validUser.role})`);

  // Eksekusi aksi halaman lewat POM
  await loginPage.navigate();
  await loginPage.loginWith(validUser.email, validUser.password);

  // Assertion murni di layer test
  const currentUrl = await dashboardPage.getPageUrl();
  const welcomeText = await dashboardPage.getWelcomeText();

  if (currentUrl === "/dashboard" && welcomeText.includes("Selamat Datang")) {
    console.log(`  ${ANSI.green}✓ PASS${ANSI.reset} Pengguna berhasil login dan mendarat di ${currentUrl}`);
    console.log(`  ${ANSI.green}✓ PASS${ANSI.reset} Pesan sambutan terverifikasi: "${welcomeText}"`);
  } else {
    console.log(`  ${ANSI.red}✗ FAIL${ANSI.reset} Login gagal dialihkan.`);
  }

  // Test Case 2: Negative Login Flow
  console.log(`\n${ANSI.bold}${ANSI.cyan}=== TEST 2: NEGATIVE LOGIN FLOW (WRONG CREDENTIALS) ===${ANSI.reset}`);
  const invalidUser = UserDataFactory.createInvalidUser();
  const driverNeg = new VirtualBrowserDriver();
  const loginPageNeg = new LoginPage(driverNeg);

  await loginPageNeg.navigate();
  // Fluent chaining demo
  await (await (await loginPageNeg.enterEmail(invalidUser.email))
    .enterPassword(invalidUser.password))
    .clickSubmit();

  const errorAlert = await loginPageNeg.getErrorMessage();
  const expectedError = "Kredensial email atau password salah";

  if (errorAlert === expectedError) {
    console.log(`  ${ANSI.green}✓ PASS${ANSI.reset} Sistem menolak kredensial palsu dengan pesan: "${errorAlert}"`);
  } else {
    console.log(`  ${ANSI.red}✗ FAIL${ANSI.reset} Pesan error tidak sesuai: Expected "${expectedError}", got "${errorAlert}"`);
  }

  console.log(`\n${ANSI.bold}${ANSI.cyan}=== ANALISIS DESAIN ARSITEKTUR POM ===${ANSI.reset}`);
  console.log(`1. Single Point of Maintenance: Jika selector input-email berubah, hanya perbaiki di LoginPage.`);
  console.log(`2. High Readability: File test tidak memiliki baris selector DOM rumit.`);
  console.log(`3. Clean Isolation: Page Object tidak memiliki method expect() sehingga fleksibel digunakan ulang.`);
  console.log(`\n${ANSI.green}✓ Page Object Model & Data Factory Lab completed successfully!${ANSI.reset}\n`);
}

main().catch(console.error);
