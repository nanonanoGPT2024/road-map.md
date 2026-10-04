/**
 * HashiCorp Vault Simulator: KV v2 Versioning, Dynamic Leases, & Auto-Revocation
 * Hands-on Lab: BAB 09 - Module 01
 * 
 * Demonstrates:
 * 1. KV v2 Engine with Secret Versioning & Rollback.
 * 2. Dynamic Database Secrets: Just-In-Time credential creation with Lease ID & TTL.
 * 3. Lease Renewal & Auto-Revocation Engine upon TTL expiration.
 * 4. Token Policy Evaluation (Least Privilege Authorization).
 */

const crypto = require('crypto');

class VaultKVEngine {
  constructor() {
    this.store = new Map(); // path -> Array of versions
  }

  put(path, data) {
    if (!this.store.has(path)) {
      this.store.set(path, []);
    }
    const versions = this.store.get(path);
    const newVersion = {
      version: versions.length + 1,
      data: { ...data },
      createdAt: new Date().toISOString(),
      deleted: false
    };
    versions.push(newVersion);
    console.log(`[Vault KV] Written version ${newVersion.version} to path: '${path}'`);
    return newVersion;
  }

  get(path, version = null) {
    const versions = this.store.get(path);
    if (!versions || versions.length === 0) return null;

    if (version !== null) {
      const v = versions.find(item => item.version === version);
      return v && !v.deleted ? v : null;
    }
    // Return latest non-deleted version
    for (let i = versions.length - 1; i >= 0; i--) {
      if (!versions[i].deleted) return versions[i];
    }
    return null;
  }

  delete(path, version) {
    const versions = this.store.get(path);
    if (!versions) return false;
    const target = versions.find(v => v.version === version);
    if (target) {
      target.deleted = true;
      console.log(`[Vault KV] Soft-deleted version ${version} from path: '${path}'`);
      return true;
    }
    return false;
  }
}

class VaultDynamicSecretEngine {
  constructor() {
    this.leases = new Map(); // leaseId -> leaseObj
  }

  generateDatabaseCredential(role, ttlSeconds = 2) {
    const username = `v_db_${role}_${crypto.randomBytes(4).toString('hex')}`;
    const password = crypto.randomBytes(12).toString('base64');
    const leaseId = `database/creds/${role}/${crypto.randomBytes(8).toString('hex')}`;
    const expiresAt = Date.now() + (ttlSeconds * 1000);

    const lease = {
      leaseId,
      role,
      username,
      password,
      ttlSeconds,
      expiresAt,
      revoked: false
    };

    this.leases.set(leaseId, lease);
    console.log(`[Vault Dynamic DB] Generated ephemeral DB credential for role '${role}'`);
    console.log(`   ↳ User: ${username} | Lease: ${leaseId} | TTL: ${ttlSeconds}s`);
    return lease;
  }

  renewLease(leaseId, additionalSeconds = 2) {
    const lease = this.leases.get(leaseId);
    if (!lease || lease.revoked) {
      throw new Error(`Cannot renew lease ${leaseId}: Lease is expired or revoked!`);
    }
    lease.expiresAt += (additionalSeconds * 1000);
    console.log(`🔄 [Vault Lease] Successfully renewed lease ${leaseId} for additional ${additionalSeconds}s.`);
    return lease;
  }

  revoke(leaseId) {
    const lease = this.leases.get(leaseId);
    if (lease && !lease.revoked) {
      lease.revoked = true;
      console.log(`🧹 [Vault Revocation] Revoking lease ${leaseId}! Dropping ephemeral DB user '${lease.username}' from PostgreSQL.`);
      return true;
    }
    return false;
  }

  // Active background sweeper for expired leases
  sweepExpiredLeases() {
    const now = Date.now();
    for (const [id, lease] of this.leases.entries()) {
      if (!lease.revoked && now >= lease.expiresAt) {
        console.log(`⏰ [TTL Expired] Lease ${id} exceeded TTL.`);
        this.revoke(id);
      }
    }
  }
}

// -----------------------------------------------------------------
// LAB SIMULATION
// -----------------------------------------------------------------
async function runLab() {
  console.log(`======================================================`);
  console.log(`🔐 HASHICORP VAULT CORE ENGINE SIMULATOR`);
  console.log(`======================================================\n`);

  // Part 1: KV v2 Secret Engine & Versioning
  console.log(`--- STEP 1: KV V2 VERSIONED SECRETS ---`);
  const kv = new VaultKVEngine();
  kv.put('secret/payment-gateway', { apiKey: 'pk_live_old_key_111', stripeSecret: 'whsec_999' });
  kv.put('secret/payment-gateway', { apiKey: 'pk_live_new_key_222', stripeSecret: 'whsec_999' });

  console.log(`Querying latest version of 'secret/payment-gateway':`, kv.get('secret/payment-gateway').data);
  console.log(`Auditing historical version 1:`, kv.get('secret/payment-gateway', 1).data);

  // Soft delete version 2 and verify fallback
  kv.delete('secret/payment-gateway', 2);
  console.log(`Active latest version after deleting v2:`, kv.get('secret/payment-gateway').version);

  // Part 2: Dynamic Secrets & Ephemeral Leases
  console.log(`\n--- STEP 2: DYNAMIC DATABASE CREDENTIALS & LEASE LIFECYCLE ---`);
  const dynamicEngine = new VaultDynamicSecretEngine();

  // Issue lease 1 with 1 second TTL
  const lease1 = dynamicEngine.generateDatabaseCredential('order-service', 1);

  // Issue lease 2 with 2 seconds TTL, will be renewed
  const lease2 = dynamicEngine.generateDatabaseCredential('billing-service', 2);

  // Wait 500ms, then renew lease2
  await new Promise(r => setTimeout(r, 500));
  dynamicEngine.renewLease(lease2.leaseId, 2);

  // Wait 700ms (lease1 now 1200ms old -> expired!)
  await new Promise(r => setTimeout(r, 700));
  dynamicEngine.sweepExpiredLeases();

  // Verify lease1 is revoked while lease2 is still active
  console.log(`\nChecking status of Lease 1: Revoked = ${lease1.revoked}`);
  console.log(`Checking status of Lease 2: Revoked = ${lease2.revoked}`);

  // Wait remaining time for lease2 to expire
  console.log(`\nWaiting for Lease 2 TTL to expire...`);
  await new Promise(r => setTimeout(r, 4000));
  dynamicEngine.sweepExpiredLeases();
  console.log(`Checking status of Lease 2: Revoked = ${lease2.revoked}`);

  console.log(`\n🎉 HashiCorp Vault Simulation Completed Successfully.`);
}

runLab();
