'use strict';

/**
 * Enterprise Change-Tracking Engine via Recursive Virtual Proxy
 */
class ChangeTracker {
  static #rawToProxy = new WeakMap();
  static #proxyToRaw = new WeakMap();
  
  #target;
  #dirtyState = new Map();
  #isSealed = false;

  constructor(initialData = {}) {
    this.#target = initialData;
    this.proxy = this.#createProxy(this.#target);
  }

  #createProxy(obj) {
    if (obj === null || typeof obj !== 'object') {
      return obj;
    }

    // Hindari alokasi ganda: kembalikan proxy yang telah dipetakan jika ada
    if (ChangeTracker.#rawToProxy.has(obj)) {
      return ChangeTracker.#rawToProxy.get(obj);
    }

    // Jika objek sudah berupa Proxy, kembalikan objek tersebut
    if (ChangeTracker.#proxyToRaw.has(obj)) {
      return obj;
    }

    const handler = {
      get: (target, prop, receiver) => {
        // Introspeksi internal engine: bypass unwrap
        if (prop === '__isProxy') return true;
        if (prop === '__rawTarget') return target;

        const value = Reflect.get(target, prop, receiver);

        // Rekursif membungkus properti bertipe objek (Lazy Evaluation)
        if (value !== null && typeof value === 'object') {
          return this.#createProxy(value);
        }

        return value;
      },

      set: (target, prop, value, receiver) => {
        if (this.#isSealed) {
          throw new Error('Transaction is sealed. Commits are final.');
        }

        const oldValue = Reflect.get(target, prop, receiver);

        // Normalisasi unwrap jika value yang dimasukkan adalah sebuah proxy
        const actualValue = ChangeTracker.#proxyToRaw.get(value) || value;

        if (oldValue !== actualValue) {
          // Rekam mutasi jika belum tercatat di dirtyState Map
          const targetDelta = this.#dirtyState.get(target) || new Map();
          if (!targetDelta.has(prop)) {
            targetDelta.set(prop, { original: oldValue, current: actualValue });
            this.#dirtyState.set(target, targetDelta);
          } else {
            // Update current value pada mutasi berikutnya
            targetDelta.get(prop).current = actualValue;
          }
        }

        return Reflect.set(target, prop, actualValue, receiver);
      },

      deleteProperty: (target, prop) => {
        if (this.#isSealed) {
          throw new Error('Transaction is sealed. Mutating schema is disallowed.');
        }

        if (Reflect.has(target, prop)) {
          const oldValue = Reflect.get(target, prop);
          const targetDelta = this.#dirtyState.get(target) || new Map();
          targetDelta.set(prop, { original: oldValue, current: undefined, deleted: true });
          this.#dirtyState.set(target, targetDelta);
        }

        return Reflect.deleteProperty(target, prop);
      }
    };

    const proxy = new Proxy(obj, handler);
    ChangeTracker.#rawToProxy.set(obj, proxy);
    ChangeTracker.#proxyToRaw.set(proxy, obj);
    return proxy;
  }

  isDirty() {
    return this.#dirtyState.size > 0;
  }

  getChanges() {
    const changes = [];
    for (const [target, deltaMap] of this.#dirtyState.entries()) {
      for (const [prop, delta] of deltaMap.entries()) {
        changes.push({
          target,
          property: prop,
          from: delta.original,
          to: delta.current,
          isDeleted: delta.deleted || false
        });
      }
    }
    return changes;
  }

  commit() {
    this.#isSealed = true;
    this.#dirtyState.clear();
    Object.freeze(this.#target);
  }
}

// -------------------------------------------------------------
// Verifikasi Pengujian Sistem
// -------------------------------------------------------------

const entityData = {
  id: 1001,
  metadata: {
    version: '1.0.0',
    tags: ['production', 'financial']
  },
  payload: {
    amount: 5000000
  }
};

const tracker = new ChangeTracker(entityData);
const tracked = tracker.proxy;

// Verifikasi Identity Caching
console.assert(tracked.metadata === tracked.metadata, 'Identity cache lookup validation');

// Mutasi Properti Bersarang
tracked.metadata.version = '1.0.1';
tracked.payload.amount = 7500000;
delete tracked.metadata.tags;

console.log('Is Dirty:', tracker.isDirty()); // true
console.log('Delta Changes Matrix:', JSON.stringify(tracker.getChanges(), null, 2));

tracker.commit();

try {
  // Upaya mutasi pasca commit harus diblokir oleh integritas transaksi
  tracked.payload.amount = 9999999;
} catch (error) {
  console.log('Security Constraint Enforced:', error.message);
}
