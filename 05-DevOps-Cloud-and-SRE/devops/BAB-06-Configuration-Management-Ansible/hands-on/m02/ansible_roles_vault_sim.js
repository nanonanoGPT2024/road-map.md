/**
 * Hands-on M02: Ansible Roles, Jinja2 Template Engine, & AES-256 Vault Simulator
 * Mengilustrasikan konsep:
 * 1. Struktur Variabel Ansible Roles (defaults vs vars)
 * 2. Jinja2 Template Rendering (Variabel, Loop, dan Kondisional)
 * 3. Enkripsi & Dekripsi Rahasia Ansible Vault (AES-256-CBC)
 *
 * Jalankan: node ansible_roles_vault_sim.js
 */

const crypto = require('crypto');

const colors = {
  reset: '\x1b[0m',
  cyan: '\x1b[36m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  magenta: '\x1b[35m',
  red: '\x1b[31m',
  bold: '\x1b[1m'
};

// ==========================================
// 1. ANSIBLE VAULT ENCRYPTOR (AES-256)
// ==========================================
class AnsibleVaultEngine {
  static encrypt(plaintext, vaultPassword) {
    const salt = crypto.randomBytes(32);
    // Turunkan key 32-byte dan iv 16-byte menggunakan PBKDF2
    const key = crypto.pbkdf2Sync(vaultPassword, salt, 10000, 32, 'sha256');
    const iv = crypto.randomBytes(16);

    const cipher = crypto.createCipheriv('aes-256-cbc', key, iv);
    let ciphertext = cipher.update(plaintext, 'utf8', 'hex');
    ciphertext += cipher.final('hex');

    // Format output header persis standar Ansible Vault
    const payload = {
      salt: salt.toString('hex'),
      iv: iv.toString('hex'),
      data: ciphertext
    };

    const encoded = Buffer.from(JSON.stringify(payload)).toString('hex');
    return `$ANSIBLE_VAULT;1.1;AES256\n${encoded}`;
  }

  static decrypt(vaultContent, vaultPassword) {
    const lines = vaultContent.trim().split('\n');
    if (lines[0] !== '$ANSIBLE_VAULT;1.1;AES256') {
      throw new Error('Invalid Vault Header!');
    }

    try {
      const payload = JSON.parse(Buffer.from(lines[1], 'hex').toString('utf8'));
      const salt = Buffer.from(payload.salt, 'hex');
      const iv = Buffer.from(payload.iv, 'hex');
      const key = crypto.pbkdf2Sync(vaultPassword, salt, 10000, 32, 'sha256');

      const decipher = crypto.createDecipheriv('aes-256-cbc', key, iv);
      let decrypted = decipher.update(payload.data, 'hex', 'utf8');
      decrypted += decipher.final('utf8');
      return decrypted;
    } catch (e) {
      throw new Error(`Gagal mendekripsi Ansible Vault (Password salah?): ${e.message}`);
    }
  }
}

// ==========================================
// 2. JINJA2 TEMPLATE ENGINE SIMULATOR
// ==========================================
class Jinja2TemplateEngine {
  static render(templateString, context) {
    let output = templateString;

    // 1. Handle Loop: {% for item in list %} ... {% endfor %}
    const loopRegex = /\{%\s*for\s+(\w+)\s+in\s+(\w+)\s*%\}([\s\S]*?)\{%\s*endfor\s*%\}/g;
    output = output.replace(loopRegex, (_, itemVar, listVar, innerContent) => {
      const list = context[listVar] || [];
      return list.map(item => {
        let itemRender = innerContent;
        // Ganti properti item: {{ item.prop }}
        const itemPropRegex = new RegExp(`\\{\\{\\s*${itemVar}\\.(\\w+)\\s*\\}\\}`, 'g');
        itemRender = itemRender.replace(itemPropRegex, (__, prop) => item[prop] || '');
        // Ganti item itu sendiri: {{ item }}
        const simpleItemRegex = new RegExp(`\\{\\{\\s*${itemVar}\\s*\\}\\}`, 'g');
        return itemRender.replace(simpleItemRegex, item);
      }).join('');
    });

    // 2. Handle Variabel Sederhana: {{ varName }}
    const varRegex = /\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g;
    output = output.replace(varRegex, (_, varName) => {
      return context[varName] !== undefined ? context[varName] : '';
    });

    return output;
  }
}

// ==========================================
// TEST SCENARIOS
// ==========================================
async function runLab() {
  console.log(`${colors.bold}${colors.cyan}=== DEVOPS LAB: ANSILE ROLES, JINJA2 & VAULT ===${colors.reset}\n`);

  // 1. Uji Coba Ansible Vault Enkripsi & Dekripsi
  console.log('--- 1. UJI ANSIBLE VAULT (AES-256 ENCRYPTION) ---');
  const masterVaultPass = 'EnterpriseVaultPassword2026!';
  const secretDbPassword = 'db_prod_super_secret_p@ssw0rd!';

  console.log(`Plaintext Asli : ${secretDbPassword}`);
  const encryptedVault = AnsibleVaultEngine.encrypt(secretDbPassword, masterVaultPass);
  console.log(`\n${colors.yellow}[TERENKRIPSI] Format File Vault (Aman disimpan di Git):${colors.reset}`);
  console.log(encryptedVault);

  console.log('\nMendekripsi file vault menggunakan Master Password...');
  const decryptedSecret = AnsibleVaultEngine.decrypt(encryptedVault, masterVaultPass);
  console.log(`${colors.green}[DEKRIPSI SUKSES] Nilai Terbuka:${colors.reset} ${decryptedSecret}\n`);

  // 2. Uji Coba Jinja2 Template Rendering untuk Nginx Conf
  console.log('--- 2. UJI JINJA2 TEMPLATE RENDERING (ROLES PATTERN) ---');
  
  // Template Nginx Dinamis
  const nginxTemplate = `
# Generated automatically by Ansible Role: nginx_reverse_proxy
worker_processes {{ cpu_cores }};

upstream backend_pool {
{% for s in backend_servers %}
    server {{ s.ip }}:{{ s.port }};
{% endfor %}
}

server {
    listen {{ listen_port }};
    server_name {{ domain_name }};

    location / {
        proxy_pass http://backend_pool;
        proxy_set_header X-DB-Secret-Check "{{ db_pass }}";
    }
}
  `.trim();

  // Context gabungan dari defaults, vars, dan vault yang didekripsi
  const roleContext = {
    cpu_cores: 4,
    listen_port: 80,
    domain_name: 'api.production.corp',
    db_pass: decryptedSecret,
    backend_servers: [
      { ip: '10.0.1.21', port: 3000 },
      { ip: '10.0.1.22', port: 3000 },
      { ip: '10.0.1.23', port: 3000 }
    ]
  };

  const renderedConfig = Jinja2TemplateEngine.render(nginxTemplate, roleContext);
  console.log(`${colors.green}[HASIL RENDER JINJA2 /etc/nginx/sites-available/api.conf]${colors.reset}`);
  console.log(renderedConfig);

  console.log(`\n${colors.bold}${colors.green}=== SEMUA PENGUJIAN JINJA2 & ANSIBLE VAULT BERHASIL DILAKUKAN ===${colors.reset}`);
}

runLab();
