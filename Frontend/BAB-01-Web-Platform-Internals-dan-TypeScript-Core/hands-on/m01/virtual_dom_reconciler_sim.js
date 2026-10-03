/**
 * Hands-on M01: Virtual DOM Tree & Reconciliation Diffing Engine
 * Track: Frontend & TypeScript Mastery - BAB 01
 * 
 * Demonstrasi mekanisme internal Web Platform:
 * 1. Representasi Pohon VNode (Virtual DOM)
 * 2. Diffing Algorithm antara Old VNode vs New VNode
 * 3. Batching & Patch Generation via Microtask Queue
 * 4. Zero external dependencies (Dijalankan langsung di Node.js)
 */

const ANSI = {
  reset: "\x1b[0m",
  bold: "\x1b[1m",
  green: "\x1b[32m",
  cyan: "\x1b[36m",
  yellow: "\x1b[33m",
  red: "\x1b[31m",
  magenta: "\x1b[35m"
};

// 1. VNode Factory
function h(tag, props = {}, children = []) {
  return {
    tag,
    props: props || {},
    children: (Array.isArray(children) ? children : [children]).map(child =>
      typeof child === "string" || typeof child === "number"
        ? { tag: "#text", text: String(child) }
        : child
    )
  };
}

// 2. Patch Types
const PATCH_TYPE = {
  NONE: "NONE",
  CREATE: "CREATE",
  REMOVE: "REMOVE",
  REPLACE: "REPLACE",
  UPDATE_PROPS: "UPDATE_PROPS",
  TEXT: "TEXT"
};

// 3. Diffing Engine
class Reconciler {
  diffProps(oldProps, newProps) {
    const patches = {};
    let hasChanges = false;

    // Check updated / added props
    for (const [k, v] of Object.entries(newProps)) {
      if (oldProps[k] !== v) {
        patches[k] = v;
        hasChanges = true;
      }
    }

    // Check removed props
    for (const k of Object.keys(oldProps)) {
      if (!(k in newProps)) {
        patches[k] = null;
        hasChanges = true;
      }
    }

    return hasChanges ? patches : null;
  }

  diff(oldVNode, newVNode) {
    if (!oldVNode) {
      return { type: PATCH_TYPE.CREATE, newVNode };
    }
    if (!newVNode) {
      return { type: PATCH_TYPE.REMOVE };
    }

    // Text node diff
    if (oldVNode.tag === "#text" && newVNode.tag === "#text") {
      if (oldVNode.text !== newVNode.text) {
        return { type: PATCH_TYPE.TEXT, text: newVNode.text };
      }
      return { type: PATCH_TYPE.NONE };
    }

    // Tag replacement
    if (oldVNode.tag !== newVNode.tag) {
      return { type: PATCH_TYPE.REPLACE, newVNode };
    }

    // Props diff
    const propPatches = this.diffProps(oldVNode.props, newVNode.props);

    // Children diff
    const childPatches = [];
    const maxLen = Math.max(oldVNode.children.length, newVNode.children.length);
    for (let i = 0; i < maxLen; i++) {
      childPatches.push(this.diff(oldVNode.children[i], newVNode.children[i]));
    }

    return {
      type: PATCH_TYPE.UPDATE_PROPS,
      props: propPatches,
      children: childPatches
    };
  }

  // Render to string DOM representation
  renderToString(vnode) {
    if (!vnode) return "";
    if (vnode.tag === "#text") return vnode.text;
    const props = Object.entries(vnode.props)
      .map(([k, v]) => ` ${k}="${v}"`)
      .join("");
    const children = vnode.children.map(c => this.renderToString(c)).join("");
    return `<${vnode.tag}${props}>${children}</${vnode.tag}>`;
  }
}

// 4. Batch Renderer Simulator
class BatchRenderer {
  constructor() {
    this.reconciler = new Reconciler();
    this.currentTree = null;
    this.pendingTree = null;
    this.isScheduled = false;
    this.renderCount = 0;
  }

  scheduleRender(newTree) {
    this.pendingTree = newTree;
    if (!this.isScheduled) {
      this.isScheduled = true;
      // Gunakan queueMicrotask untuk simulasi event loop microtask execution
      queueMicrotask(() => this.flush());
    }
  }

  flush() {
    this.renderCount++;
    console.log(`\n${ANSI.cyan}[BatchRenderer] Flushing render frame #${this.renderCount} (Microtask Tick)...${ANSI.reset}`);
    const patches = this.reconciler.diff(this.currentTree, this.pendingTree);
    console.log(`${ANSI.yellow}Calculated Patches:${ANSI.reset}`, JSON.stringify(patches, null, 2));
    this.currentTree = this.pendingTree;
    this.isScheduled = false;
    console.log(`${ANSI.green}DOM Updated to:${ANSI.reset} ${this.reconciler.renderToString(this.currentTree)}`);
  }
}

// ==========================================
// TEST SUITE & DEMO RUNNER
// ==========================================
async function runLab() {
  console.log(`${ANSI.bold}${ANSI.magenta}======================================================${ANSI.reset}`);
  console.log(`${ANSI.bold}${ANSI.magenta}  LAB HANDS-ON: VIRTUAL DOM RECONCILER SIMULATOR      ${ANSI.reset}`);
  console.log(`${ANSI.bold}${ANSI.magenta}======================================================${ANSI.reset}`);

  const reconciler = new Reconciler();

  // Test Case 1: Initial Tree Creation
  console.log(`\n${ANSI.bold}[Test 1] Initial VNode Tree Creation${ANSI.reset}`);
  const vtree1 = h("div", { id: "app", class: "container" }, [
    h("h1", {}, "Selamat Datang di Nusantara UI"),
    h("p", { class: "lead" }, "Rendering performa tinggi berbasis TypeScript.")
  ]);
  console.log("HTML Render 1:", reconciler.renderToString(vtree1));

  // Test Case 2: In-place Props Update & Text Change
  console.log(`\n${ANSI.bold}[Test 2] State Change & Reconciliation Diff${ANSI.reset}`);
  const vtree2 = h("div", { id: "app", class: "container active" }, [
    h("h1", {}, "Nusantara UI v2.0 Released!"),
    h("p", { class: "lead text-bold" }, "Rendering performa tinggi berbasis TypeScript."),
    h("span", { class: "badge" }, "NEW")
  ]);

  const patch = reconciler.diff(vtree1, vtree2);
  console.log(`${ANSI.green}✓ Diffing Berhasil Terhitung.${ANSI.reset}`);
  console.log("Patch Type:", patch.type);
  console.log("Prop Changes:", patch.props);

  // Test Case 3: Batching Simulation
  console.log(`\n${ANSI.bold}[Test 3] Microtask Queue Batching Test${ANSI.reset}`);
  const renderer = new BatchRenderer();
  renderer.scheduleRender(vtree1);
  renderer.scheduleRender(vtree2); // Harus di-batch menjadi 1 flush

  await new Promise(resolve => setTimeout(resolve, 50));

  if (renderer.renderCount === 1) {
    console.log(`\n${ANSI.green}${ANSI.bold}✓ SUCCESS: Multiple state updates were coalesced into 1 render tick!${ANSI.reset}`);
  } else {
    console.error(`\n${ANSI.red}✗ FAILED: Expected 1 batch flush, got ${renderer.renderCount}${ANSI.reset}`);
    process.exit(1);
  }
}

runLab();
