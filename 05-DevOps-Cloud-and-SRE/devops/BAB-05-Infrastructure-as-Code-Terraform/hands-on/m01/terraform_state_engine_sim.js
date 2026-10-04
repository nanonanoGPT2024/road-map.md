/**
 * Hands-on M01: Terraform State Engine, Plan Calculation, & Lifecycle Protection Simulator
 * Mengilustrasikan konsep:
 * 1. Declarative Desired Config vs State File vs Live Cloud
 * 2. Perhitungan Plan Diff (+ Create, ~ Modify, - Destroy)
 * 3. Lifecycle Protection (prevent_destroy = true)
 *
 * Jalankan: node terraform_state_engine_sim.js
 */

const fs = require('fs');
const path = require('path');

const colors = {
  reset: '\x1b[0m',
  cyan: '\x1b[36m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  magenta: '\x1b[35m',
  red: '\x1b[31m',
  bold: '\x1b[1m'
};

class TerraformStateEngine {
  constructor() {
    this.liveCloud = new Map(); // cloud_id -> resource data
    this.tfState = {
      version: 4,
      terraform_version: "1.7.0",
      serial: 1,
      resources: []
    };
  }

  // Menghitung Plan Diff antara HCL Desired State dan State saat ini
  plan(desiredConfig) {
    console.log(`\n${colors.bold}${colors.cyan}=== TERRAFORM PLAN EXECUTION ===${colors.reset}`);
    const plannedActions = [];

    // 1. Periksa resource yang perlu di-Create atau di-Modify
    for (const res of desiredConfig) {
      const existingInState = this.tfState.resources.find(r => r.type === res.type && r.name === res.name);

      if (!existingInState) {
        // Belum ada di state -> CREATE (+)
        plannedActions.push({
          action: 'CREATE',
          symbol: '+',
          color: colors.green,
          resource: res,
          reason: 'Resource baru dideklarasikan di konfigurasi HCL'
        });
      } else {
        // Bandingkan atribut -> MODIFY (~)
        const hasChanges = JSON.stringify(existingInState.attributes) !== JSON.stringify(res.attributes);
        if (hasChanges) {
          plannedActions.push({
            action: 'MODIFY',
            symbol: '~',
            color: colors.yellow,
            resource: res,
            oldAttributes: existingInState.attributes,
            reason: 'Perubahan atribut terdeteksi'
          });
        }
      }
    }

    // 2. Periksa resource yang dihapus dari HCL -> DESTROY (-)
    for (const stateRes of this.tfState.resources) {
      const stillInConfig = desiredConfig.find(r => r.type === stateRes.type && r.name === stateRes.name);
      if (!stillInConfig) {
        // Cek proteksi prevent_destroy
        const isProtected = stateRes.lifecycle && stateRes.lifecycle.prevent_destroy;
        plannedActions.push({
          action: 'DESTROY',
          symbol: '-',
          color: colors.red,
          resource: stateRes,
          isBlocked: isProtected,
          reason: isProtected ? 'DIBLOKIR oleh lifecycle { prevent_destroy = true }' : 'Resource dihapus dari konfigurasi HCL'
        });
      }
    }

    // Tampilkan output plan ala Terraform CLI
    let createCount = 0, changeCount = 0, destroyCount = 0;
    plannedActions.forEach(p => {
      console.log(`  ${p.color}${p.symbol} ${p.resource.type}.${p.resource.name}${colors.reset} [${p.action}]`);
      console.log(`    Alasan: ${p.reason}`);
      if (p.action === 'CREATE') createCount++;
      if (p.action === 'MODIFY') changeCount++;
      if (p.action === 'DESTROY' && !p.isBlocked) destroyCount++;
    });

    console.log(`\nPlan: ${createCount} to add, ${changeCount} to change, ${destroyCount} to destroy.\n`);
    return plannedActions;
  }

  // Menerapkan Plan ke Live Cloud dan memperbarui State File
  async apply(plannedActions) {
    console.log(`${colors.bold}${colors.magenta}=== TERRAFORM APPLY EXECUTION ===${colors.reset}`);
    this.tfState.serial++;

    for (const plan of plannedActions) {
      if (plan.action === 'DESTROY' && plan.isBlocked) {
        throw new Error(`[CRITICAL SECURITY ERROR] Resource ${plan.resource.type}.${plan.resource.name} memiliki lifecycle prevent_destroy = true. Operasi apply dibatalkan demi keamanan!`);
      }

      if (plan.action === 'CREATE') {
        const cloudId = `${plan.resource.type.replace('aws_', '')}_${Math.random().toString(36).substring(2, 9)}`;
        console.log(`  ${colors.green}[CREATING]${colors.reset} ${plan.resource.type}.${plan.resource.name}...`);
        await new Promise(r => setTimeout(r, 200));

        // Simpan ke Live Cloud
        this.liveCloud.set(cloudId, { ...plan.resource.attributes, id: cloudId });

        // Simpan ke terraform.tfstate
        this.tfState.resources.push({
          type: plan.resource.type,
          name: plan.resource.name,
          cloud_id: cloudId,
          attributes: plan.resource.attributes,
          lifecycle: plan.resource.lifecycle || {}
        });
        console.log(`  ${colors.green}[CREATED]${colors.reset} ${plan.resource.type}.${plan.resource.name} (ID: ${cloudId})`);
      } else if (plan.action === 'MODIFY') {
        console.log(`  ${colors.yellow}[MODIFYING]${colors.reset} ${plan.resource.type}.${plan.resource.name}...`);
        const target = this.tfState.resources.find(r => r.type === plan.resource.type && r.name === plan.resource.name);
        target.attributes = plan.resource.attributes;
        this.liveCloud.set(target.cloud_id, { ...plan.resource.attributes, id: target.cloud_id });
        console.log(`  ${colors.yellow}[MODIFIED]${colors.reset} ${plan.resource.type}.${plan.resource.name} atribut diperbarui.`);
      }
    }

    console.log(`\n${colors.green}[APPLY COMPLETE] State file disinkronkan (Serial: ${this.tfState.serial})${colors.reset}\n`);
  }
}

// ==========================================
// TEST SCENARIOS
// ==========================================
async function runLab() {
  console.log(`${colors.bold}${colors.cyan}=== DEVOPS LAB: TERRAFORM STATE & LIFECYCLE ENGINE ===${colors.reset}\n`);

  const engine = new TerraformStateEngine();

  // Step 1: Initial Desired Configuration (VPC & Database)
  console.log('--- 1. INITIAL RUN (PROVISION VPC & RDS DATABASE) ---');
  const hclConfigV1 = [
    {
      type: 'aws_vpc',
      name: 'main',
      attributes: { cidr_block: '10.0.0.0/16', enable_dns: true }
    },
    {
      type: 'aws_db_instance',
      name: 'production_postgres',
      attributes: { instance_class: 'db.t3.medium', allocated_storage: 50 },
      lifecycle: { prevent_destroy: true } // Proteksi database
    }
  ];

  const plan1 = engine.plan(hclConfigV1);
  await engine.apply(plan1);

  // Step 2: Modifikasi Atribut (Scale Up Database Storage ke 100GB)
  console.log('--- 2. MODIFIKASI ATRIBUT (IN-PLACE UPDATE) ---');
  const hclConfigV2 = [
    {
      type: 'aws_vpc',
      name: 'main',
      attributes: { cidr_block: '10.0.0.0/16', enable_dns: true }
    },
    {
      type: 'aws_db_instance',
      name: 'production_postgres',
      attributes: { instance_class: 'db.t3.medium', allocated_storage: 100 }, // Berubah 50 -> 100
      lifecycle: { prevent_destroy: true }
    }
  ];

  const plan2 = engine.plan(hclConfigV2);
  await engine.apply(plan2);

  // Step 3: Simulasi Kesalahan Menghapus Database (Uji prevent_destroy)
  console.log('--- 3. PENGUJIAN PROTEKSI PREVENT_DESTROY ---');
  console.log('Developer tidak sengaja menghapus blok aws_db_instance dari file HCL...');
  const dangerousConfig = [
    {
      type: 'aws_vpc',
      name: 'main',
      attributes: { cidr_block: '10.0.0.0/16', enable_dns: true }
    }
    // aws_db_instance dihilangkan!
  ];

  const plan3 = engine.plan(dangerousConfig);
  try {
    await engine.apply(plan3);
  } catch (err) {
    console.log(`${colors.green}[PROTECTION VERIFIED] Terraform berhasil menggagalkan bencana:${colors.reset}\n${err.message}\n`);
  }

  console.log(`${colors.bold}${colors.green}=== SEMUA PENGUJIAN TERRAFORM STATE SELESAI DENGAN SUKSES ===${colors.reset}`);
}

runLab();
