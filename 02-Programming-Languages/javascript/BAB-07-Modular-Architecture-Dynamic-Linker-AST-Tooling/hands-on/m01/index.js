// dynamic-plugin-engine.js
import * as parser from '@babel/parser';
import traverseModule from '@babel/traverse';
import generateModule from '@babel/generator';
import vm from 'node:vm';

// Workaround interop untuk paket Babel ESM/CJS dual builds
const traverse = traverseModule.default || traverseModule;
const generate = generateModule.default || generateModule;

/**
 * Enterprise Plugin Compiler & Virtual Security Sandbox
 */
class PluginEngine {
  constructor(allowedDependenciesMap) {
    this.allowedDependencies = allowedDependenciesMap; // Specifier -> Internal In-Memory Module
    this.forbiddenGlobals = new Set(['process', 'eval', 'Function', 'WebAssembly']);
    this.isolatedContext = vm.createContext({
      Object, Array, String, Number, Boolean, Math, Date,
      console: { log: (...args) => console.log('[Plugin Runtime]:', ...args) }
    });
  }

  /**
   * Langkah 1: AST Tooling Pipeline
   * Parse -> Validasi Keamanan (AST Inspection) -> Rewriting Path
   */
  transformAndSecure(sourceCode, pluginId) {
    // 1. Parsing Source Code menjadi Abstract Syntax Tree (ESTree compliant)
    const ast = parser.parse(sourceCode, {
      sourceType: 'module',
      plugins: ['topLevelAwait']
    });

    const forbiddenGlobals = this.forbiddenGlobals;
    const allowedDeps = this.allowedDependencies;

    // 2. Traversal AST dengan Visitor Pattern
    traverse(ast, {
      // Deteksi akses ke Identifier terlarang (Global Scope Protection)
      Identifier(path) {
        if (
          forbiddenGlobals.has(path.node.name) &&
          !path.scope.hasBinding(path.node.name) // Hanya tangkap jika BUKAN variabel lokal
        ) {
          throw new SecurityError(
            `[Security Violation] Akses ke global token '${path.node.name}' dilarang pada plugin '${pluginId}'. Baris: ${path.node.loc?.start.line}`
          );
        }
      },

      // Deteksi evaluasi kode tak aman via AST call expression
      CallExpression(path) {
        const callee = path.node.callee;
        if (callee.type === 'Identifier' && callee.name === 'eval') {
          throw new SecurityError(`[Security Violation] Penggunaan eval() dilarang pada plugin '${pluginId}'.`);
        }
      },

      // Rewriting Import Declaration Specifier
      ImportDeclaration(path) {
        const importSource = path.node.source.value;
        if (!allowedDeps.has(importSource)) {
          throw new SecurityError(
            `[Import Violation] Modul '${importSource}' tidak diizinkan dalam daftar dependensi plugin.`
          );
        }
        // Rewrite import specifier ke domain virtual host
        path.node.source.value = `virtual://host-registry/${importSource}`;
      }
    });

    // 3. Code Generation: Mengembalikan source code bersih hasil transformasi
    const output = generate(ast, { retainLines: true });
    return output.code;
  }

  /**
   * Langkah 2: Dynamic Linker & Instantiation
   */
  async executePlugin(pluginId, rawCode) {
    console.log(`\n=== MEMPROSES PLUGIN: ${pluginId} ===`);
    
    // Transformasi dan Amankan AST
    const securedCode = this.transformAndSecure(rawCode, pluginId);
    console.log('[AST Engine] Validasi Aman & Specifier Berhasil Diformat:');
    console.log(securedCode.trim());

    // Inisialisasi Root SourceTextModule
    const pluginModule = new vm.SourceTextModule(securedCode, {
      identifier: `plugin-${pluginId}.js`,
      context: this.isolatedContext
    });

    // Linker dinamis: memetakan 'virtual://host-registry/X' ke Host Module Record
    const dynamicLinker = async (specifier, referencingModule) => {
      const prefix = 'virtual://host-registry/';
      if (specifier.startsWith(prefix)) {
        const originalSpecifier = specifier.replace(prefix, '');
        const hostSource = this.allowedDependencies.get(originalSpecifier);
        
        return new vm.SourceTextModule(hostSource, {
          identifier: specifier,
          context: this.isolatedContext
        });
      }
      throw new Error(`Resolusi modul gagal: ${specifier}`);
    };

    // Linking graf modul & Evaluasi bytecode
    await pluginModule.link(dynamicLinker);
    await pluginModule.evaluate();

    // Jalankan entry point default jika ada
    if (pluginModule.namespace.default) {
      await pluginModule.namespace.default();
    }
    
    return pluginModule.namespace;
  }
}

class SecurityError extends Error {
  constructor(message) {
    super(message);
    this.name = 'SecurityError';
  }
}

// ==========================================
// TEST IMPLEMENTASI PRODUKSI
// ==========================================
(async () => {
  // Mock Host Internal Modules
  const hostDependencies = new Map();
  hostDependencies.set(
    'metrics-reporter',
    `export function send(metric) { console.log('Metric Sent to Host Server:', metric); }`
  );

  const engine = new PluginEngine(hostDependencies);

  // Kasus 1: Plugin Sah (Valid)
  const validPluginCode = `
    import { send } from 'metrics-reporter';

    export default async function run() {
      send({ event: 'latency', value: 42 });
    }
  `;

  try {
    await engine.executePlugin('valid-analytics', validPluginCode);
  } catch (err) {
    console.error('Eksekusi Plugin Sah Gagal:', err);
  }

  // Kasus 2: Plugin Berbahaya (Mencoba Bypass via Global Scope Process)
  const maliciousPluginCode = `
    import { send } from 'metrics-reporter';

    export default function exploit() {
      // Upaya eksfiltrasi environment host
      const env = process.env; 
      send({ leak: env });
    }
  `;

  try {
    await engine.executePlugin('malicious-plugin', maliciousPluginCode);
  } catch (err) {
    console.error(`DITOLAK OLEH AST SECURITY GUARD: -> ${err.message}`);
  }
})();
