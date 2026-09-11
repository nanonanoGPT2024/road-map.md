/**
 * Hands-on M02: Mobile Touch Gestures & axe-core Automated Accessibility Auditor Simulator
 * 
 * Demonstrasi:
 * 1. Kalkulator Gestur Sentuhan Mobile W3C Actions (Vertical Scroll, Carousel Swipe, Long Press).
 * 2. Validator Desired Capabilities Appium (Android UiAutomator2 / iOS XCUITest).
 * 3. Engine Audit Aksesibilitas Otomatis (axe-core Simulator):
 *    - Touch Target Size Audit (Minimum 48x48 dp untuk tombol mobile)
 *    - Color Contrast Audit (WCAG 2.1 AA)
 *    - Accessibility ID / Content-Description Audit
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
// 1. MOBILE TOUCH GESTURES ENGINE (W3C ACTIONS)
// ==========================================
class MobileGestureCalculator {
  constructor(screenWidth = 1080, screenHeight = 2400) {
    this.width = screenWidth;
    this.height = screenHeight;
  }

  calculateSwipeUp() {
    const startX = Math.floor(this.width * 0.5);
    const startY = Math.floor(this.height * 0.8);
    const endX = startX;
    const endY = Math.floor(this.height * 0.2);
    return {
      action: "SWIPE_UP_VERTICAL_SCROLL",
      start: { x: startX, y: startY },
      end: { x: endX, y: endY },
      durationMs: 600,
      w3cPayload: [
        { type: "pointerMove", duration: 0, x: startX, y: startY },
        { type: "pointerDown", button: 0 },
        { type: "pause", duration: 100 },
        { type: "pointerMove", duration: 600, x: endX, y: endY },
        { type: "pointerUp", button: 0 }
      ]
    };
  }

  calculateCarouselSwipeLeft() {
    const startX = Math.floor(this.width * 0.85);
    const endX = Math.floor(this.width * 0.15);
    const y = Math.floor(this.height * 0.3); // Posisi vertikal banner
    return {
      action: "SWIPE_LEFT_CAROUSEL",
      start: { x: startX, y },
      end: { x: endX, y },
      durationMs: 400
    };
  }
}

// ==========================================
// 2. APPIUM DESIRED CAPABILITIES VALIDATOR
// ==========================================
class AppiumCapabilitiesValidator {
  static validate(caps) {
    const errors = [];
    const validPlatforms = ["Android", "iOS"];

    if (!validPlatforms.includes(caps.platformName)) {
      errors.push(`Invalid platformName: "${caps.platformName}". Must be "Android" or "iOS"`);
    }

    if (caps.platformName === "Android" && caps["appium:automationName"] !== "UiAutomator2") {
      errors.push(`Android automationName must be "UiAutomator2"`);
    }

    if (caps.platformName === "iOS" && caps["appium:automationName"] !== "XCUITest") {
      errors.push(`iOS automationName must be "XCUITest"`);
    }

    if (!caps["appium:app"] && !caps["appium:appPackage"]) {
      errors.push("Missing application target: must specify app or appPackage");
    }

    return { isValid: errors.length === 0, errors };
  }
}

// ==========================================
// 3. AXE-CORE AUTOMATED A11Y AUDIT ENGINE
// ==========================================
class AxeCoreAuditor {
  constructor() {
    this.violations = [];
    this.passes = 0;
  }

  auditView(screenElements) {
    for (const el of screenElements) {
      // Rule 1: Touch Target Size (WCAG 2.5.5 - Min 48x48dp pada Mobile)
      if (el.isInteractive) {
        if (el.widthDp < 48 || el.heightDp < 48) {
          this.violations.push({
            id: "touch-target-size",
            impact: "serious",
            element: `<${el.type} id="${el.id}">`,
            detail: `Ukuran tombol ${el.widthDp}x${el.heightDp}dp terlalu kecil. Standar WCAG minimal 48x48dp agar mudah ditekan jari.`
          });
        } else {
          this.passes++;
        }
      }

      // Rule 2: Image Content Description / Accessibility ID
      if (el.type === "ImageView") {
        if (!el.contentDescription && !el.isDecorative) {
          this.violations.push({
            id: "image-alt-missing",
            impact: "critical",
            element: `<ImageView id="${el.id}">`,
            detail: "Gambar tidak memiliki 'contentDescription' atau 'accessibilityIdentifier' untuk pembaca layar (TalkBack/VoiceOver)."
          });
        } else {
          this.passes++;
        }
      }

      // Rule 3: Text Contrast (WCAG 1.4.3 - Min 4.5:1)
      if (el.textContrastRatio && el.textContrastRatio < 4.5) {
        this.violations.push({
          id: "color-contrast",
          impact: "serious",
          element: `<TextView text="${el.text}">`,
          detail: `Rasio kontras ${el.textContrastRatio}:1 di bawah standar minimum 4.5:1.`
        });
      } else if (el.textContrastRatio) {
        this.passes++;
      }
    }
  }
}

// ==========================================
// 4. MAIN SIMULATION EXECUTION
// ==========================================
function main() {
  console.log(`${ANSI.bold}╔═══════════════════════════════════════════════════════════════╗`);
  console.log(`║    MOBILE TESTING APPIUM GESTURES & axe-core AUDIT LAB        ║`);
  console.log(`╚═══════════════════════════════════════════════════════════════╝${ANSI.reset}`);

  // 1. DEMONSTRASI KALKULASI GESTUR MOBILE
  console.log(`\n${ANSI.bold}${ANSI.cyan}=== 1. W3C ACTIONS MOBILE GESTURE CALCULATIONS ===${ANSI.reset}`);
  const gestureCalc = new MobileGestureCalculator(1080, 2400); // Resolusi Layar FHD+
  const swipeUp = gestureCalc.calculateSwipeUp();
  const swipeLeft = gestureCalc.calculateCarouselSwipeLeft();

  console.log(`  Resolusi Layar Uji : 1080 x 2400 piksel`);
  console.log(`  [Swipe Up Scroll]  : Start (X: ${swipeUp.start.x}, Y: ${swipeUp.start.y}) ➔ End (X: ${swipeUp.end.x}, Y: ${swipeUp.end.y}) [Durasi: ${swipeUp.durationMs}ms]`);
  console.log(`  [Swipe Carousel]   : Start (X: ${swipeLeft.start.x}, Y: ${swipeLeft.start.y}) ➔ End (X: ${swipeLeft.end.x}, Y: ${swipeLeft.end.y})`);
  console.log(`  ${ANSI.green}✓ W3C Pointer Events payload generated successfully.${ANSI.reset}`);

  // 2. DEMONSTRASI VALIDASI CAPABILITIES APPIUM
  console.log(`\n${ANSI.bold}${ANSI.cyan}=== 2. VALIDASI APPIUM DESIRED CAPABILITIES ===${ANSI.reset}`);
  const validCaps = {
    platformName: "Android",
    "appium:automationName": "UiAutomator2",
    "appium:deviceName": "Google Pixel 8",
    "appium:appPackage": "com.tokomodern.app",
    "appium:appActivity": ".MainActivity"
  };
  const capResult = AppiumCapabilitiesValidator.validate(validCaps);
  console.log(`  Desired Capabilities Status: ${capResult.isValid ? ANSI.green + "✓ VALID CONFIGURATION" : ANSI.red + "INVALID"}${ANSI.reset}`);

  // 3. AUDIT AKSESIBILITAS OTOMATIS (axe-core SIMULATOR)
  console.log(`\n${ANSI.bold}${ANSI.cyan}=== 3. AXE-CORE AUTOMATED ACCESSIBILITY (A11Y) SCAN ===${ANSI.reset}`);
  
  // Simulasi elemen layar aplikasi mobile
  const screenElements = [
    { type: "Button", id: "btn-checkout", isInteractive: true, widthDp: 54, heightDp: 50 }, // Valid (>=48dp)
    { type: "Button", id: "btn-close-banner", isInteractive: true, widthDp: 24, heightDp: 24 }, // VIOLATION: Touch target too small!
    { type: "ImageView", id: "product-promo-banner", isDecorative: false }, // VIOLATION: Missing contentDescription!
    { type: "ImageView", id: "app-logo", isDecorative: true, contentDescription: "" }, // Valid decorative
    { type: "TextView", id: "lbl-disclaimer", text: "Syarat & Ketentuan", textContrastRatio: 2.3 } // VIOLATION: Low contrast!
  ];

  const auditor = new AxeCoreAuditor();
  auditor.auditView(screenElements);

  console.log(`  Total Evaluasi Aturan: ${auditor.passes + auditor.violations.length}`);
  console.log(`  Aturan Terpenuhi     : ${ANSI.green}${auditor.passes} Passed${ANSI.reset}`);
  console.log(`  Pelanggaran Ditemukan: ${ANSI.red}${auditor.violations.length} Violations${ANSI.reset}\n`);

  for (const v of auditor.violations) {
    console.log(`  ${ANSI.red}✗ [${v.impact.toUpperCase()}] Rule: ${v.id}${ANSI.reset}`);
    console.log(`    Target : ${ANSI.bold}${v.element}${ANSI.reset}`);
    console.log(`    Detail : ${ANSI.yellow}${v.detail}${ANSI.reset}`);
  }

  console.log(`\n${ANSI.green}✓ Mobile Gestures & axe-core Lab executed successfully!${ANSI.reset}\n`);
}

main();
