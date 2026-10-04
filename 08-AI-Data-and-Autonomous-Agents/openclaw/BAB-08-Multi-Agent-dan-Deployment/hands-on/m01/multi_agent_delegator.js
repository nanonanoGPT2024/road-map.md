/**
 * Hands-on M01: OpenClaw Multi-Agent Collaboration & Subagent Delegation Simulator
 * Mengilustrasikan pola Orchestrator-Worker, pemisahan peran agen,
 * eksekusi paralel (Map-Reduce), dan sintesis hasil akhir tanpa context bloat.
 *
 * Jalankan: node multi_agent_delegator.js
 */

const colors = {
  reset: '\x1b[0m',
  cyan: '\x1b[36m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  magenta: '\x1b[35m',
  red: '\x1b[31m',
  bold: '\x1b[1m'
};

class SubagentWorker {
  constructor(name, role, model, specializedTools = []) {
    this.name = name;
    this.role = role;
    this.model = model;
    this.tools = specializedTools;
    this.contextHistory = []; // Konteks terisolasi per worker
  }

  async executeTask(taskDescription) {
    const startTime = Date.now();
    console.log(`  ${colors.magenta}[WORKER SPAWNED: ${this.name}]${colors.reset}`);
    console.log(`    Peran  : ${this.role}`);
    console.log(`    Model  : ${this.model} | Tools: [${this.tools.join(', ')}]`);
    console.log(`    Tugas  : "${taskDescription}"`);

    // Simulasi pemanggilan tool dan reasoning LLM independen (300 - 500 ms)
    const simulatedWorkTime = 300 + Math.floor(Math.random() * 200);
    await new Promise(r => setTimeout(r, simulatedWorkTime));

    let findings = '';
    if (this.name === 'TechAuditor') {
      findings = 'Target menggunakan arsitektur microservices Go + Kubernetes, Postgres 16, latency P99 45ms.';
    } else if (this.name === 'PricingAnalyst') {
      findings = 'Model subscription: $29/bulan (Starter) dan $99/bulan (Pro). Menawarkan free trial 14 hari.';
    } else if (this.name === 'SecurityResearcher') {
      findings = 'Sertifikasi SOC2 Type II aktif, TLS 1.3 enforced, tidak ditemukan celah CVE publik kritis.';
    } else {
      findings = `Hasil analisis domain untuk: ${taskDescription}`;
    }

    const elapsed = Date.now() - startTime;
    console.log(`  ${colors.green}[WORKER COMPLETED: ${this.name}]${colors.reset} Selesai dalam ${elapsed}ms`);

    return {
      worker: this.name,
      model: this.model,
      durationMs: elapsed,
      findings
    };
  }
}

class OrchestratorAgent {
  constructor(name, model) {
    this.name = name;
    this.model = model;
    this.registry = new Map();
    this.maxRecursionDepth = 2;
  }

  registerWorker(worker) {
    this.registry.set(worker.name, worker);
    console.log(`${colors.cyan}[ORCHESTRATOR] Registrasi Subagent: ${worker.name} (${worker.role})${colors.reset}`);
  }

  async handleUserComplexGoal(userGoal) {
    console.log(`\n${colors.bold}${colors.cyan}=== [ORCHESTRATOR] Menerima Goal Baru ===${colors.reset}`);
    console.log(`Instruksi Pengguna: "${userGoal}"`);
    console.log(`Model Utama: ${this.model}`);

    // Step 1: Decompose Task
    console.log(`\n${colors.yellow}[STEP 1: TASK DECOMPOSITION & PLANNING]${colors.reset}`);
    const subtasks = [
      { workerName: 'TechAuditor', task: 'Audit infrastruktur backend dan database kompetitor AcmeCorp' },
      { workerName: 'PricingAnalyst', task: 'Analisis strategi pricing dan paket langganan AcmeCorp' },
      { workerName: 'SecurityResearcher', task: 'Periksa kepatuhan keamanan dan sertifikasi publik AcmeCorp' }
    ];

    console.log(`Tugas berhasil dipecah menjadi ${subtasks.length} sub-tasks paralel.`);

    // Step 2: Concurrent Worker Dispatch (Map phase)
    console.log(`\n${colors.yellow}[STEP 2: PARALLEL SUBAGENT EXECUTION]${colors.reset}`);
    const workerPromises = subtasks.map(item => {
      const worker = this.registry.get(item.workerName);
      if (!worker) throw new Error(`Worker ${item.workerName} tidak ditemukan!`);
      return worker.executeTask(item.task);
    });

    const results = await Promise.all(workerPromises);

    // Step 3: Synthesis & Consolidation (Reduce phase)
    console.log(`\n${colors.yellow}[STEP 3: EXECUTIVE SYNTHESIS & REPORTING]${colors.reset}`);
    console.log(`Mengkonsolidasi temuan ${results.length} subagent ke dalam format Executive Report...`);

    const consolidatedReport = {
      target: 'AcmeCorp Intelligence Audit',
      generatedAt: new Date().toISOString(),
      orchestratedBy: this.name,
      subagentMetrics: results.map(r => ({ name: r.worker, model: r.model, latency: `${r.durationMs}ms` })),
      executiveSummary: results.map((r, idx) => `${idx + 1}. [${r.worker}] ${r.findings}`).join('\n')
    };

    return consolidatedReport;
  }
}

// ==========================================
// TEST SCENARIO
// ==========================================
async function runLab() {
  const orchestrator = new OrchestratorAgent('ExecutiveButler-Orchestrator', 'anthropic/claude-3-5-sonnet');

  // Daftarkan subagent pekerja
  orchestrator.registerWorker(new SubagentWorker(
    'TechAuditor',
    'Senior Infrastructure Architect',
    'openai/gpt-4o-mini',
    ['curl_analyzer', 'dns_lookup', 'wappalyzer']
  ));

  orchestrator.registerWorker(new SubagentWorker(
    'PricingAnalyst',
    'Financial Data Analyst',
    'anthropic/claude-3-5-haiku',
    ['page_scraper', 'currency_converter']
  ));

  orchestrator.registerWorker(new SubagentWorker(
    'SecurityResearcher',
    'Cybersecurity Auditor',
    'ollama/qwen2.5-coder-7b',
    ['shodan_search', 'ssl_cert_inspector']
  ));

  // Jalankan instruksi komprehensif
  const report = await orchestrator.handleUserComplexGoal(
    'Tolong buatkan intelijen komprehensif kompetitor AcmeCorp (teknologi, harga, dan keamanannya) untuk rapat dewan jam 10 pagi.'
  );

  console.log(`\n${colors.bold}${colors.green}================ HASIL LAPORAN PARIPURNA =================${colors.reset}`);
  console.log(`Judul        : ${report.target}`);
  console.log(`Orchestrator : ${report.orchestratedBy}`);
  console.log(`Daftar Worker:`);
  report.subagentMetrics.forEach(m => console.log(`  * ${m.name} (${m.model}) - Latensi: ${m.latency}`));
  console.log(`\nRingkasan Eksekutif:`);
  console.log(report.executiveSummary);
  console.log(`${colors.bold}${colors.green}==========================================================${colors.reset}\n`);

  console.log(`${colors.green}[VERIFIKASI SUKSES] Pola Multi-Agent Collaboration berhasil dijalankan tanpa context pollution!${colors.reset}`);
}

runLab();
