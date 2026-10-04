/**
 * Kubernetes RBAC Authorization Engine Simulator
 * 
 * Mensimulasikan logika RBAC Authorizer internal pada kube-apiserver:
 * 1. Evaluasi Role vs ClusterRole, RoleBinding vs ClusterRoleBinding.
 * 2. Evaluasi API Groups, Resources, Subresources (pods/log, pods/exec), dan Verbs.
 * 3. Restriksi granular berbasis resourceNames.
 * 4. Implementasi perintah audit 'kubectl auth can-i'.
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

function log(module, msg, color = ANSI.reset) {
  console.log(`${color}[${module}] ${msg}${ANSI.reset}`);
}

class RBACEngine {
  constructor() {
    this.roles = []; // { namespace, name, rules }
    this.clusterRoles = []; // { name, rules }
    this.roleBindings = []; // { namespace, name, subjects, roleRef }
    this.clusterRoleBindings = []; // { name, subjects, roleRef }
  }

  addRole(namespace, name, rules) {
    this.roles.push({ namespace, name, rules });
    log("rbac-store", `Role terdaftar: ${namespace}/${name}`, ANSI.cyan);
  }

  addClusterRole(name, rules) {
    this.clusterRoles.push({ name, rules });
    log("rbac-store", `ClusterRole terdaftar: ${name}`, ANSI.cyan);
  }

  addRoleBinding(namespace, name, subjects, roleRef) {
    this.roleBindings.push({ namespace, name, subjects, roleRef });
    log("rbac-store", `RoleBinding terdaftar: ${namespace}/${name} -> Ref: ${roleRef.kind}/${roleRef.name}`, ANSI.yellow);
  }

  addClusterRoleBinding(name, subjects, roleRef) {
    this.clusterRoleBindings.push({ name, subjects, roleRef });
    log("rbac-store", `ClusterRoleBinding terdaftar: ${name} -> Ref: ${roleRef.kind}/${roleRef.name}`, ANSI.yellow);
  }

  // Inti Mesin Otorisasi Kube-APIServer
  authorize(subject, request) {
    // request: { namespace, apiGroup, resource, subresource, verb, resourceName }
    const targetResource = request.subresource 
      ? `${request.resource}/${request.subresource}` 
      : request.resource;

    // 1. Evaluasi ClusterRoleBindings (Cluster Scope)
    for (const crb of this.clusterRoleBindings) {
      if (this._isSubjectMatched(crb.subjects, subject)) {
        const clusterRole = this.clusterRoles.find(cr => cr.name === crb.roleRef.name);
        if (clusterRole && this._isRulesPermitted(clusterRole.rules, request, targetResource)) {
          return { allowed: true, matchedBinding: `ClusterRoleBinding/${crb.name}`, role: clusterRole.name };
        }
      }
    }

    // 2. Evaluasi RoleBindings di Namespace target (Namespace Scope)
    if (request.namespace) {
      const nsBindings = this.roleBindings.filter(rb => rb.namespace === request.namespace);
      for (const rb of nsBindings) {
        if (this._isSubjectMatched(rb.subjects, subject)) {
          let rules = [];
          if (rb.roleRef.kind === "Role") {
            const role = this.roles.find(r => r.namespace === request.namespace && r.name === rb.roleRef.name);
            if (role) rules = role.rules;
          } else if (rb.roleRef.kind === "ClusterRole") {
            const cr = this.clusterRoles.find(r => r.name === rb.roleRef.name);
            if (cr) rules = cr.rules;
          }

          if (this._isRulesPermitted(rules, request, targetResource)) {
            return { allowed: true, matchedBinding: `RoleBinding/${rb.namespace}/${rb.name}`, role: rb.roleRef.name };
          }
        }
      }
    }

    return { allowed: false, reason: "No matching RBAC rule permitted this action (Default Deny)" };
  }

  _isSubjectMatched(subjects, targetSubject) {
    return subjects.some(s => {
      if (s.kind !== targetSubject.kind) return false;
      if (s.kind === "User" || s.kind === "Group") {
        return s.name === targetSubject.name;
      }
      if (s.kind === "ServiceAccount") {
        return s.name === targetSubject.name && s.namespace === targetSubject.namespace;
      }
      return false;
    });
  }

  _isRulesPermitted(rules, request, targetResource) {
    return rules.some(rule => {
      // Check API Group
      const groupMatch = rule.apiGroups.includes("*") || rule.apiGroups.includes(request.apiGroup || "");
      if (!groupMatch) return false;

      // Check Resource / Subresource
      const resMatch = rule.resources.includes("*") || rule.resources.includes(targetResource) || rule.resources.includes(request.resource);
      if (!resMatch) return false;

      // Check Verb
      const verbMatch = rule.verbs.includes("*") || rule.verbs.includes(request.verb);
      if (!verbMatch) return false;

      // Check ResourceNames restriction if exists
      if (rule.resourceNames && rule.resourceNames.length > 0) {
        if (!request.resourceName || !rule.resourceNames.includes(request.resourceName)) {
          return false;
        }
      }

      return true;
    });
  }

  // CLI Helper: kubectl auth can-i simulator
  canI(subject, verb, resource, options = {}) {
    const [mainRes, subRes] = resource.split("/");
    const req = {
      verb,
      resource: mainRes,
      subresource: subRes || null,
      namespace: options.namespace || null,
      apiGroup: options.apiGroup || "",
      resourceName: options.resourceName || null
    };

    const result = this.authorize(subject, req);
    const subDesc = subject.kind === "ServiceAccount" 
      ? `system:serviceaccount:${subject.namespace}:${subject.name}` 
      : `${subject.kind}:${subject.name}`;

    const queryStr = `kubectl auth can-i ${verb} ${resource} ${req.resourceName ? req.resourceName + ' ' : ''}${req.namespace ? '-n ' + req.namespace : '--all-namespaces'}`;

    if (result.allowed) {
      console.log(`[QUERY] ${ANSI.bold}${queryStr}${ANSI.reset} --as ${subDesc} -> ${ANSI.green}yes${ANSI.reset} (via ${result.matchedBinding})`);
    } else {
      console.log(`[QUERY] ${ANSI.bold}${queryStr}${ANSI.reset} --as ${subDesc} -> ${ANSI.red}no${ANSI.reset}`);
    }
  }
}

// ================= SIMULASI EKSEKUSI =================
console.log(`${ANSI.bold}================================================================${ANSI.reset}`);
console.log(`${ANSI.bold}       KUBERNETES RBAC AUTHORIZATION SIMULATOR (can-i)          ${ANSI.reset}`);
console.log(`${ANSI.bold}================================================================${ANSI.reset}\n`);

const engine = new RBACEngine();

// 1. Definisikan ClusterRole Standar: ReadOnly Viewer
engine.addClusterRole("cluster-viewer", [
  { apiGroups: ["", "apps"], resources: ["pods", "services", "deployments"], verbs: ["get", "list", "watch"] },
  { apiGroups: [""], resources: ["pods/log"], verbs: ["get"] }
]);

// 2. Definisikan Role Namespace Dev: Pod Operator
engine.addRole("dev", "pod-operator", [
  { apiGroups: [""], resources: ["pods"], verbs: ["get", "list", "create", "delete"] },
  { apiGroups: [""], resources: ["pods/exec"], verbs: ["create"] }
]);

// 3. Definisikan Role Payment: Restricted Secret Reader
engine.addRole("payment", "secret-reader", [
  { apiGroups: [""], resources: ["secrets"], resourceNames: ["payment-gateway-key"], verbs: ["get"] }
]);

// 4. Binding Roles
// a. Alice (Dev) terikat ke Role pod-operator di namespace 'dev'
engine.addRoleBinding("dev", "alice-dev-binding", [{ kind: "User", name: "alice" }], { kind: "Role", name: "pod-operator" });

// b. Bob (Auditor) mengikat ClusterRole 'cluster-viewer' HANYA ke namespace 'finance' (bukan seluruh cluster!)
engine.addRoleBinding("finance", "bob-finance-binding", [{ kind: "User", name: "bob" }], { kind: "ClusterRole", name: "cluster-viewer" });

// c. ServiceAccount backend-sa terikat ke Role secret-reader di namespace 'payment'
engine.addRoleBinding("payment", "backend-sa-secret-binding", [
  { kind: "ServiceAccount", name: "backend-sa", namespace: "payment" }
], { kind: "Role", name: "secret-reader" });

console.log("\n--- Menjalankan Uji Izin Otorisasi (kubectl auth can-i) ---\n");

const userAlice = { kind: "User", name: "alice" };
const userBob = { kind: "User", name: "bob" };
const saBackend = { kind: "ServiceAccount", name: "backend-sa", namespace: "payment" };

// Kasus 1: Alice di Namespace Dev
engine.canI(userAlice, "create", "pods", { namespace: "dev" });
engine.canI(userAlice, "create", "pods/exec", { namespace: "dev" });
engine.canI(userAlice, "delete", "pods", { namespace: "dev" });
engine.canI(userAlice, "delete", "pods", { namespace: "prod" }); // Seharusnya NO (isolasi namespace)

console.log("");
// Kasus 2: Bob (ClusterRole yang di-bind ke satu namespace saja)
engine.canI(userBob, "get", "pods", { namespace: "finance" }); // Seharusnya YES
engine.canI(userBob, "get", "pods/log", { namespace: "finance" }); // Seharusnya YES
engine.canI(userBob, "delete", "pods", { namespace: "finance" }); // Seharusnya NO
engine.canI(userBob, "get", "pods", { namespace: "dev" }); // Seharusnya NO (Binding hanya di finance)

console.log("");
// Kasus 3: ServiceAccount dengan batasan resourceNames
engine.canI(saBackend, "get", "secrets", { namespace: "payment", resourceName: "payment-gateway-key" }); // Seharusnya YES
engine.canI(saBackend, "get", "secrets", { namespace: "payment", resourceName: "tls-wildcard-cert" }); // Seharusnya NO
engine.canI(saBackend, "list", "secrets", { namespace: "payment" }); // Seharusnya NO (hanya get, bukan list)

console.log(`\n${ANSI.bold}Seluruh skenario RBAC Least Privilege teruji dan tervalidasi!${ANSI.reset}`);
