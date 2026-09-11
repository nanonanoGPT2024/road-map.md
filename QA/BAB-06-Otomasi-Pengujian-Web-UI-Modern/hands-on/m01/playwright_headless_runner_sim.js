/**
 * Hands-on M01: Playwright Headless Engine & Auto-Waiting Actionability Simulator
 * 
 * Demonstrasi:
 * 1. 5 Actionability Checks (Attached, Visible, Stable, Receives Events, Enabled) sebelum klik.
 * 2. Auto-Retrying Polling Mechanism saat elemen terhalang spinner overlay.
 * 3. Resilient Locators (getByRole, getByLabel, getByTestId).
 * 4. Visual Regression Snapshot & Pixel Diff Calculator Simulator.
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
// 1. PLAYWRIGHT SIMULATED DOM & LOCATOR ENGINE
// ==========================================
class SimulatedDOMNode {
  constructor(config) {
    this.tag = config.tag || "div";
    this.role = config.role || null;
    this.name = config.name || null;
    this.label = config.label || null;
    this.testId = config.testId || null;
    this.text = config.text || "";
    this.value = config.value || "";

    // 5 Actionability States
    this.isAttached = config.isAttached !== undefined ? config.isAttached : true;
    this.isVisible = config.isVisible !== undefined ? config.isVisible : true;
    this.isStable = config.isStable !== undefined ? config.isStable : true;
    this.isObscured = config.isObscured !== undefined ? config.isObscured : false;
    this.isEnabled = config.isEnabled !== undefined ? config.isEnabled : true;
  }
}

class PlaywrightPageSimulator {
  constructor() {
    this.elements = [];
    this.overlayActive = false;
  }

  addElement(node) {
    this.elements.push(node);
  }

  // Resilient Locators
  getByRole(role, options = {}) {
    return {
      type: "ROLE",
      execute: () => {
        return this.elements.find(el => {
          const matchRole = el.role === role;
          const matchName = options.name ? (el.name === options.name || el.text === options.name) : true;
          return matchRole && matchName;
        });
      }
    };
  }

  getByLabel(labelText) {
    return {
      type: "LABEL",
      execute: () => this.elements.find(el => el.label === labelText)
    };
  }

  getByTestId(testId) {
    return {
      type: "TESTID",
      execute: () => this.elements.find(el => el.testId === testId)
    };
  }

  // Actionability Checks & Auto-waiting click
  async click(locator, timeoutMs = 2000) {
    const startTime = Date.now();
    let pollCount = 0;

    console.log(`  ${ANSI.dim}[Playwright Action] Initiating auto-waiting for element click...${ANSI.reset}`);

    while (Date.now() - startTime < timeoutMs) {
      pollCount++;
      const el = locator.execute();

      if (!el) {
        await new Promise(r => setTimeout(r, 50));
        continue;
      }

      // Check 1: Attached
      if (!el.isAttached) {
        await new Promise(r => setTimeout(r, 50));
        continue;
      }

      // Check 2: Visible
      if (!el.isVisible) {
        await new Promise(r => setTimeout(r, 50));
        continue;
      }

      // Check 3: Stable
      if (!el.isStable) {
        await new Promise(r => setTimeout(r, 50));
        continue;
      }

      // Check 4: Receives Events (Obscurity Check)
      if (this.overlayActive || el.isObscured) {
        // Obscured by modal backdrop or loading spinner!
        await new Promise(r => setTimeout(r, 50));
        continue;
      }

      // Check 5: Enabled
      if (!el.isEnabled) {
        throw new Error(`Actionability Check Failed: Element is disabled`);
      }

      // Passed all 5 checks!
      console.log(`    ${ANSI.green}✓ Actionability Passed:${ANSI.reset} Attached, Visible, Stable, Free of Overlays, Enabled (Polls: ${pollCount})`);
      return true;
    }

    throw new Error(`Playwright TimeoutError: Element failed actionability checks within ${timeoutMs}ms`);
  }
}

// ==========================================
// 2. VISUAL REGRESSION COMPARATOR SIMULATOR
// ==========================================
class VisualRegressionEngine {
  static compareSnapshots(actualLayoutHash, goldenBaselineHash) {
    // Simulasi perbandingan piksel matriks
    let mismatchedPixels = 0;
    const len = Math.max(actualLayoutHash.length, goldenBaselineHash.length);

    for (let i = 0; i < len; i++) {
      if (actualLayoutHash[i] !== goldenBaselineHash[i]) {
        mismatchedPixels++;
      }
    }

    const diffRatio = Number((mismatchedPixels / len).toFixed(4));
    return {
      diffRatio,
      isMatch: diffRatio <= 0.02, // 2% tolerance threshold
      mismatchedPixels
    };
  }
}

// ==========================================
// 3. MAIN SIMULATION EXECUTION
// ==========================================
async function main() {
  console.log(`${ANSI.bold}╔═══════════════════════════════════════════════════════════════╗`);
  console.log(`║      PLAYWRIGHT AUTO-WAITING & RESILIENT LOCATORS LAB         ║`);
  console.log(`╚═══════════════════════════════════════════════════════════════╝${ANSI.reset}`);

  const page = new PlaywrightPageSimulator();

  // Setup DOM Elements
  const emailInput = new SimulatedDOMNode({
    tag: "input",
    label: "Alamat Email",
    name: "email",
    testId: "input-email"
  });

  const payButton = new SimulatedDOMNode({
    tag: "button",
    role: "button",
    name: "Bayar Sekarang",
    testId: "btn-pay"
  });

  page.addElement(emailInput);
  page.addElement(payButton);

  console.log(`\n${ANSI.bold}${ANSI.cyan}=== 1. UJI RESILIENT LOCATORS (ACCESSIBILITY FIRST) ===${ANSI.reset}`);
  const locByRole = page.getByRole("button", { name: "Bayar Sekarang" });
  const locByLabel = page.getByLabel("Alamat Email");
  const locByTestId = page.getByTestId("btn-pay");

  console.log(`  getByRole("button", { name: "Bayar Sekarang" }) ➔ Target: <${locByRole.execute().tag} role="${locByRole.execute().role}"> (${ANSI.green}FOUND${ANSI.reset})`);
  console.log(`  getByLabel("Alamat Email")                     ➔ Target: <${locByLabel.execute().tag} label="${locByLabel.execute().label}"> (${ANSI.green}FOUND${ANSI.reset})`);
  console.log(`  getByTestId("btn-pay")                         ➔ Target: <${locByTestId.execute().tag} data-testid="${locByTestId.execute().testId}"> (${ANSI.green}FOUND${ANSI.reset})`);

  console.log(`\n${ANSI.bold}${ANSI.cyan}=== 2. UJI AUTO-WAITING DENGAN SPINNER OVERLAY SEMENTARA ===${ANSI.reset}`);
  console.log(`  Simulasi: Halaman memunculkan spinner loading modal selama 150ms...`);
  page.overlayActive = true;

  // Jadwalkan spinner hilang setelah 150ms (Auto-waiting Playwright harus menunggu)
  setTimeout(() => {
    console.log(`  ${ANSI.yellow}→ [DOM Event] Spinner loading selesai dan menghilang dari layar.${ANSI.reset}`);
    page.overlayActive = false;
  }, 150);

  const clickStart = Date.now();
  await page.click(locByRole);
  const clickDuration = Date.now() - clickStart;
  console.log(`  ${ANSI.green}✓ KLIK BERHASIL${ANSI.reset} tanpa hardcoded sleep, durasi penantian adaptif: ${clickDuration}ms`);

  console.log(`\n${ANSI.bold}${ANSI.cyan}=== 3. VISUAL REGRESSION TESTING (SNAPSHOT PIXEL DIFF) ===${ANSI.reset}`);
  const goldenBaseline = "LAYOUT_HEADER_LOGO_BLUE_BUTTON_NAV_SEARCH_FOOTER";
  const actualNormalBuild = "LAYOUT_HEADER_LOGO_BLUE_BUTTON_NAV_SEARCH_FOOTER";
  const actualBrokenCssBuild = "LAYOUT_HEADER_LOGO_RED_BUTTON_NAV_SEARCH_FOOTER"; // Button color changed to red!

  const resultClean = VisualRegressionEngine.compareSnapshots(actualNormalBuild, goldenBaseline);
  console.log(`  Build Normal: Diff Ratio: ${resultClean.diffRatio}% ➔ ${resultClean.isMatch ? ANSI.green + "✓ VISUAL PASS" : ANSI.red + "✗ FAIL"}${ANSI.reset}`);

  const resultBroken = VisualRegressionEngine.compareSnapshots(actualBrokenCssBuild, goldenBaseline);
  console.log(
    `  Build Rusak : Diff Ratio: ${(resultBroken.diffRatio * 100).toFixed(1)}% ` +
    `(${resultBroken.mismatchedPixels} pixels) ➔ ${resultBroken.isMatch ? ANSI.green + "✓ PASS" : ANSI.red + "🚨 VISUAL REGRESSION DETECTED"}${ANSI.reset}`
  );

  console.log(`\n${ANSI.green}✓ Playwright Auto-Waiting & Visual Engine Lab executed successfully!${ANSI.reset}\n`);
}

main().catch(console.error);
