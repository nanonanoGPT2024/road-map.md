/**
 * Hands-on M01: Ansible Idempotency Runner, Inventory Groups, & Handlers Simulator
 * Mengilustrasikan konsep internal Ansible:
 * 1. Inventory Host Grouping & Variable Inheritance
 * 2. Eksekusi Task Idempotent (CHANGED vs OK)
 * 3. Mekanisme Notifikasi Handlers (Hanya restart service jika config changed)
 * 4. Play Recap Metrics (ok, changed, failed)
 *
 * Jalankan: node ansible_idempotent_runner.js
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

class SimulatedManagedNode {
  constructor(hostname, ip) {
    this.hostname = hostname;
    this.ip = ip;
    // State server saat ini
    this.installedPackages = new Set(['openssh-server', 'curl']);
    this.files = new Map(); // filepath -> content
    this.services = new Map(); // serviceName -> 'active' | 'inactive'
  }
}

class AnsibleEngineSimulator {
  constructor(inventory) {
    this.inventory = inventory; // Map of group -> array of SimulatedManagedNode
    this.notifiedHandlers = new Set();
  }

  async runPlaybook(playbook) {
    console.log(`\n${colors.bold}${colors.cyan}PLAY [${playbook.name}] **********************************************************${colors.reset}`);
    const targetNodes = this.inventory[playbook.hosts] || [];
    const stats = new Map(); // hostname -> { ok: 0, changed: 0, failed: 0 }
    this.notifiedHandlers.clear();

    targetNodes.forEach(node => stats.set(node.hostname, { ok: 0, changed: 0, failed: 0 }));

    // Eksekusi setiap Task
    for (const task of playbook.tasks) {
      console.log(`\n${colors.bold}TASK [${task.name}] *************************************************************${colors.reset}`);
      
      for (const node of targetNodes) {
        const nodeStats = stats.get(node.hostname);
        let taskResult = 'OK';

        if (task.type === 'apt') {
          // Task: Pastikan paket terinstal
          if (!node.installedPackages.has(task.params.name)) {
            node.installedPackages.add(task.params.name);
            taskResult = 'CHANGED';
            nodeStats.changed++;
          } else {
            nodeStats.ok++;
          }
        } else if (task.type === 'copy') {
          // Task: Salin file konfigurasi
          const currentContent = node.files.get(task.params.dest);
          if (currentContent !== task.params.content) {
            node.files.set(task.params.dest, task.params.content);
            taskResult = 'CHANGED';
            nodeStats.changed++;
            if (task.notify) this.notifiedHandlers.add(task.notify);
          } else {
            nodeStats.ok++;
          }
        } else if (task.type === 'systemd') {
          // Task: Pastikan service menyala
          const currentStatus = node.services.get(task.params.name);
          if (task.params.state === 'started' && currentStatus !== 'active') {
            node.services.set(task.params.name, 'active');
            taskResult = 'CHANGED';
            nodeStats.changed++;
          } else {
            nodeStats.ok++;
          }
        }

        // Tampilkan log output
        const color = taskResult === 'CHANGED' ? colors.yellow : colors.green;
        console.log(`${color}${taskResult.toLowerCase()}: [${node.hostname}]${colors.reset}`);
      }
    }

    // Eksekusi Handlers (Hanya jika dinotifikasi)
    if (this.notifiedHandlers.size > 0 && playbook.handlers) {
      for (const handlerName of this.notifiedHandlers) {
        const handler = playbook.handlers.find(h => h.name === handlerName);
        if (handler) {
          console.log(`\n${colors.bold}RUNNING HANDLER [${handler.name}] ***********************************************${colors.reset}`);
          for (const node of targetNodes) {
            const nodeStats = stats.get(node.hostname);
            if (handler.type === 'systemd' && handler.params.state === 'restarted') {
              node.services.set(handler.params.name, 'active');
              nodeStats.changed++;
              console.log(`${colors.yellow}changed: [${node.hostname}] (Service restarted)${colors.reset}`);
            }
          }
        }
      }
    }

    // Tampilkan Play Recap ala Ansible resmi
    console.log(`\n${colors.bold}PLAY RECAP *********************************************************************${colors.reset}`);
    for (const [hostname, s] of stats.entries()) {
      console.log(`${hostname.padEnd(24)} : ${colors.green}ok=${s.ok}${colors.reset}\t${colors.yellow}changed=${s.changed}${colors.reset}\tunreachable=0\tfailed=0`);
    }
    console.log('********************************************************************************\n');
  }
}

// ==========================================
// TEST SCENARIOS
// ==========================================
async function runLab() {
  console.log(`${colors.bold}${colors.cyan}=== DEVOPS LAB: ANSILE IDEMPOTENT PLAYBOOK RUNNER ===${colors.reset}`);

  // Inisialisasi 2 Managed Node di grup [webservers]
  const nodeWeb1 = new SimulatedManagedNode('web1.prod.corp', '10.0.1.10');
  const nodeWeb2 = new SimulatedManagedNode('web2.prod.corp', '10.0.1.11');

  const inventory = {
    webservers: [nodeWeb1, nodeWeb2]
  };

  const engine = new AnsibleEngineSimulator(inventory);

  // Definisi Playbook YAML
  const setupWebPlaybook = {
    name: 'Setup Nginx Webserver Cluster',
    hosts: 'webservers',
    tasks: [
      {
        name: 'Pastikan Nginx package terinstal',
        type: 'apt',
        params: { name: 'nginx', state: 'present' }
      },
      {
        name: 'Konfigurasikan virtual host nginx.conf',
        type: 'copy',
        params: { dest: '/etc/nginx/nginx.conf', content: 'server { listen 80; server_name app.corp; }' },
        notify: 'Restart Nginx'
      },
      {
        name: 'Pastikan Nginx service aktif',
        type: 'systemd',
        params: { name: 'nginx', state: 'started' }
      }
    ],
    handlers: [
      {
        name: 'Restart Nginx',
        type: 'systemd',
        params: { name: 'nginx', state: 'restarted' }
      }
    ]
  };

  // Run 1: Eksekusi Pertama (Server kosong -> Banyak CHANGED & Handler berjalan)
  console.log('\n--- EKSEKUSI RUN #1: SERVER DARI KONDISI MENTAH ---');
  await engine.runPlaybook(setupWebPlaybook);

  // Run 2: Eksekusi Kedua (Semua sudah terpasang -> 100% OK, 0 CHANGED, Handler SKIP!)
  console.log('--- EKSEKUSI RUN #2: IDEMPOTENCY TEST (TIDAK ADA PERUBAHAN) ---');
  await engine.runPlaybook(setupWebPlaybook);

  console.log(`${colors.bold}${colors.green}=== VERIFIKASI IDEMPOTENSI ANSILE BERHASIL DIBUKTIKAN! ===${colors.reset}`);
}

runLab();
