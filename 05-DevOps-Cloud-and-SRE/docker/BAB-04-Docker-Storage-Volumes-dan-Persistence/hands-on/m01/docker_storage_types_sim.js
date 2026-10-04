/**
 * Docker Storage Simulator: Named Volumes, Bind Mounts, & tmpfs
 * Hands-on Lab: BAB 04 - Module 01
 * 
 * Demonstrates:
 * 1. Named Volume: Cross-container destruction persistence (Postgres upgrade).
 * 2. Bind Mount: Host-to-container synchronization & Read-Only enforcement.
 * 3. tmpfs: Ultra-fast volatile in-memory storage (RAM).
 */

class MockNamedVolume {
  constructor(name) {
    this.name = name;
    this.hostPath = `/var/lib/docker/volumes/${name}/_data`;
    this.storage = new Map();
  }

  write(key, value) {
    this.storage.set(key, value);
    console.log(`💾 [Named Volume: ${this.name}] Saved key='${key}' at ${this.hostPath}`);
  }

  read(key) {
    return this.storage.get(key) || null;
  }
}

class MockHostFilesystem {
  constructor() {
    this.files = new Map();
  }

  setFile(path, content) {
    this.files.set(path, content);
  }

  getFile(path) {
    return this.files.get(path) || null;
  }
}

class MockContainerInstance {
  constructor(name, mounts = []) {
    this.name = name;
    this.mounts = mounts; // Array of { type: 'volume'|'bind'|'tmpfs', source, target, readonly }
    this.tmpfsStorage = new Map();
    this.status = 'RUNNING';
  }

  writeFile(targetPath, content) {
    const mount = this.mounts.find(m => targetPath.startsWith(m.target));

    if (!mount) {
      console.log(`[Container: ${this.name}] Wrote '${targetPath}' to ephemeral UpperDir layer.`);
      return;
    }

    if (mount.readonly) {
      throw new Error(`EROFS: Read-only file system. Cannot write to mounted path '${targetPath}'!`);
    }

    if (mount.type === 'volume') {
      mount.source.write(targetPath, content);
    } else if (mount.type === 'bind') {
      mount.hostFs.setFile(mount.hostPath, content);
      console.log(`📁 [Bind Mount] Synced file to host filesystem path: ${mount.hostPath}`);
    } else if (mount.type === 'tmpfs') {
      this.tmpfsStorage.set(targetPath, content);
      console.log(`⚡ [tmpfs] Stored '${targetPath}' in Host RAM. (Not written to disk!)`);
    }
  }

  readFile(targetPath) {
    const mount = this.mounts.find(m => targetPath.startsWith(m.target));
    if (!mount) return null;

    if (mount.type === 'volume') {
      return mount.source.read(targetPath);
    } else if (mount.type === 'bind') {
      return mount.hostFs.getFile(mount.hostPath);
    } else if (mount.type === 'tmpfs') {
      return this.tmpfsStorage.get(targetPath);
    }
  }

  destroy() {
    this.status = 'DESTROYED';
    this.tmpfsStorage.clear(); // RAM is cleared
    console.log(`💥 [docker rm -f] Container '${this.name}' destroyed! (UpperDir & tmpfs purged).`);
  }
}

// -----------------------------------------------------------------
// LAB SIMULATION
// -----------------------------------------------------------------
async function runLab() {
  console.log(`======================================================`);
  console.log(`💾 DOCKER STORAGE ARCHITECTURE SIMULATOR`);
  console.log(`======================================================\n`);

  // PART 1: Named Volume Persistence Across Database Rebuilds
  console.log(`--- PART 1: NAMED VOLUME DATABASE UPGRADE SIMULATION ---`);
  const pgDataVolume = new MockNamedVolume('prod_postgres_data');

  // Container 1 (Postgres 14) boots and writes critical bank balances
  const c1 = new MockContainerInstance('db-pg14', [
    { type: 'volume', source: pgDataVolume, target: '/var/lib/postgresql/data', readonly: false }
  ]);
  c1.writeFile('/var/lib/postgresql/data/accounts.db', 'ACCOUNT_101: Rp 50.000.000 | ACCOUNT_102: Rp 25.000.000');

  // Destroy Postgres 14 container
  c1.destroy();

  // Container 2 (Postgres 16) boots and mounts the EXACT same Named Volume
  console.log(`\nStarting new Postgres 16 container mounting existing volume 'prod_postgres_data'...`);
  const c2 = new MockContainerInstance('db-pg16', [
    { type: 'volume', source: pgDataVolume, target: '/var/lib/postgresql/data', readonly: false }
  ]);
  const restoredData = c2.readFile('/var/lib/postgresql/data/accounts.db');
  console.log(`✅ [Data Verification] Postgres 16 read preserved data: "${restoredData}"`);

  // PART 2: Bind Mount Live Reload & Read-Only Enforcement
  console.log(`\n--- PART 2: BIND MOUNT & READ-ONLY ENFORCEMENT ---`);
  const hostFs = new MockHostFilesystem();
  hostFs.setFile('/home/user/project/nginx.conf', 'server { listen 80; server_name api.local; }');

  const webContainer = new MockContainerInstance('nginx-edge', [
    { type: 'bind', hostFs, hostPath: '/home/user/project/nginx.conf', target: '/etc/nginx/nginx.conf', readonly: true }
  ]);

  console.log(`Reading host config from inside container:`, webContainer.readFile('/etc/nginx/nginx.conf'));

  // Attempting to overwrite read-only config
  try {
    console.log(`Attempting unauthorized modification of read-only mount...`);
    webContainer.writeFile('/etc/nginx/nginx.conf', 'HACKED CONFIG');
  } catch (err) {
    console.error(`🛡️  Security Blocked: ${err.message}`);
  }

  // PART 3: tmpfs Volatile RAM Storage
  console.log(`\n--- PART 3: TMPFS IN-MEMORY VOLATILE STORAGE ---`);
  const tokenContainer = new MockContainerInstance('auth-service', [
    { type: 'tmpfs', target: '/app/tokens', readonly: false }
  ]);
  tokenContainer.writeFile('/app/tokens/jwt_session.key', 'secret_token_session_9921');
  console.log(`Token read from RAM:`, tokenContainer.readFile('/app/tokens/jwt_session.key'));

  // Destroy container and verify RAM is cleared
  tokenContainer.destroy();
  console.log(`Attempting to read token after container destruction:`, tokenContainer.readFile('/app/tokens/jwt_session.key'));

  console.log(`\n🎉 Docker Storage Simulation Completed Successfully!`);
}

runLab();
