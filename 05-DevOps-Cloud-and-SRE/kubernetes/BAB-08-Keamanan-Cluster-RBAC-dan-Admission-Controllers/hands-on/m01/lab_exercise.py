#!/usr/bin/env python3
"""
Lab Simulasi Keamanan Kubernetes: RBAC & Admission Controllers
Modul 01 - BAB 08 Keamanan Cluster Kubernetes
"""

import sys
import json
import base64
import copy
from typing import Dict, List, Optional, Tuple, Any

# ANSI Color Codes untuk visualisasi terminal
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
BG_BLUE = "\033[44m"
BG_RED = "\033[41m"
BG_GREEN = "\033[42m"


class PolicyRule:
    def __init__(self, api_groups: List[str], resources: List[str], verbs: List[str]):
        self.api_groups = api_groups
        self.resources = resources
        self.verbs = verbs

    def matches(self, api_group: str, resource: str, verb: str) -> bool:
        group_match = "*" in self.api_groups or api_group in self.api_groups
        resource_match = "*" in self.resources or resource in self.resources
        verb_match = "*" in self.verbs or verb in self.verbs
        return group_match and resource_match and verb_match


class Role:
    def __init__(self, name: str, namespace: str, rules: List[PolicyRule]):
        self.name = name
        self.namespace = namespace
        self.rules = rules


class ClusterRole:
    def __init__(self, name: str, rules: List[PolicyRule]):
        self.name = name
        self.rules = rules


class RoleBinding:
    def __init__(self, name: str, namespace: str, role_name: str, subjects: List[Dict[str, str]], is_cluster_role: bool = False):
        self.name = name
        self.namespace = namespace
        self.role_name = role_name
        self.subjects = subjects
        self.is_cluster_role = is_cluster_role


class ClusterRoleBinding:
    def __init__(self, name: str, cluster_role_name: str, subjects: List[Dict[str, str]]):
        self.name = name
        self.cluster_role_name = cluster_role_name
        self.subjects = subjects


class RBACAuthorizer:
    def __init__(self):
        self.roles: Dict[str, Role] = {}
        self.cluster_roles: Dict[str, ClusterRole] = {}
        self.role_bindings: List[RoleBinding] = []
        self.cluster_role_bindings: List[ClusterRoleBinding] = []

    def add_role(self, role: Role):
        self.roles[f"{role.namespace}/{role.name}"] = role

    def add_cluster_role(self, cluster_role: ClusterRole):
        self.cluster_roles[cluster_role.name] = cluster_role

    def add_role_binding(self, rb: RoleBinding):
        self.role_bindings.append(rb)

    def add_cluster_role_binding(self, crb: ClusterRoleBinding):
        self.cluster_role_bindings.append(crb)

    def can_i(self, user: str, groups: List[str], verb: str, resource: str, namespace: Optional[str] = None, api_group: str = "") -> Tuple[bool, str]:
        # 1. Evaluasi ClusterRoleBindings (Cluster-wide permission)
        for crb in self.cluster_role_bindings:
            if self._subject_matches(crb.subjects, user, groups):
                crole = self.cluster_roles.get(crb.cluster_role_name)
                if crole:
                    for rule in crole.rules:
                        if rule.matches(api_group, resource, verb):
                            return True, f"Diizinkan oleh ClusterRoleBinding '{crb.name}' -> ClusterRole '{crole.name}'"

        # 2. Evaluasi RoleBindings dalam Namespace tertentu
        if namespace:
            for rb in self.role_bindings:
                if rb.namespace == namespace and self._subject_matches(rb.subjects, user, groups):
                    if rb.is_cluster_role:
                        crole = self.cluster_roles.get(rb.role_name)
                        if crole:
                            for rule in crole.rules:
                                if rule.matches(api_group, resource, verb):
                                    return True, f"Diizinkan oleh RoleBinding '{rb.name}' di ns '{namespace}' (ClusterRole ref '{crole.name}')"
                    else:
                        role = self.roles.get(f"{namespace}/{rb.role_name}")
                        if role:
                            for rule in role.rules:
                                if rule.matches(api_group, resource, verb):
                                    return True, f"Diizinkan oleh RoleBinding '{rb.name}' -> Role '{role.name}'"

        return False, f"Ditolak (Implicit Deny) - Tidak ada Role/ClusterRole yang mengizinkan tindakan '{verb}' pada '{resource}'"

    @staticmethod
    def _subject_matches(subjects: List[Dict[str, str]], user: str, groups: List[str]) -> bool:
        for sub in subjects:
            kind = sub.get("kind")
            name = sub.get("name")
            if kind == "User" and name == user:
                return True
            if kind == "Group" and name in groups:
                return True
            if kind == "ServiceAccount" and name == user:
                return True
        return False


class AdmissionControllerPipeline:
    def __init__(self):
        pass

    def mutate(self, request_obj: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
        """Mutating Phase: Mengubah atau menambahkan default value secara deterministik."""
        mutations = []
        obj = copy.deepcopy(request_obj)
        kind = obj.get("kind")
        spec = obj.get("spec", {})

        if kind == "Pod":
            # Mutasi 1: Pasang automountServiceAccountToken = false jika tidak ditentukan
            if "automountServiceAccountToken" not in spec:
                spec["automountServiceAccountToken"] = False
                mutations.append("[MutatingWebhook] Injeksi: automountServiceAccountToken=false")

            # Mutasi 2: Injeksi securityContext runAsNonRoot jika belum diatur
            pod_sc = spec.setdefault("securityContext", {})
            if "runAsNonRoot" not in pod_sc:
                pod_sc["runAsNonRoot"] = True
                pod_sc["runAsUser"] = 10001
                mutations.append("[MutatingWebhook] Injeksi: PodSecurityContext runAsNonRoot=true, runAsUser=10001")

            # Mutasi 3: Injeksi drop ALL capabilities ke semua kontainer
            for container in spec.get("containers", []):
                c_sc = container.setdefault("securityContext", {})
                caps = c_sc.setdefault("capabilities", {})
                if "drop" not in caps:
                    caps["drop"] = ["ALL"]
                    mutations.append(f"[MutatingWebhook] Injeksi: Container '{container.get('name')}' capabilities.drop=['ALL']")

        obj["spec"] = spec
        return obj, mutations

    def validate(self, request_obj: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validating Phase: Mencegah konfigurasi berbahaya (Zero Trust Policy)."""
        violations = []
        kind = request_obj.get("kind")
        spec = request_obj.get("spec", {})

        if kind == "Pod":
            # Validasi 1: Cek privileged container
            for c in spec.get("containers", []):
                c_sc = c.get("securityContext", {})
                if c_sc.get("privileged", False):
                    violations.append(f"DENY: Kontainer '{c.get('name')}' meminta izin 'privileged: true' (Dilarang oleh PSP/PSS Baseline/Restricted).")

                # Validasi 2: Host namespace (hostNetwork, hostPID, hostIPC)
                if spec.get("hostNetwork", False):
                    violations.append("DENY: Pod meminta 'hostNetwork: true' yang berisiko menyadap interface host node.")
                if spec.get("hostPID", False):
                    violations.append("DENY: Pod meminta 'hostPID: true' yang dapat membaca proses root sistem host.")

                # Validasi 3: Image tag :latest dilarang di production
                image = c.get("image", "")
                if image.endswith(":latest") or ":" not in image:
                    violations.append(f"DENY: Kontainer '{c.get('name')}' memakai image mutable '{image}'. Wajib gunakan tag immutable / SHA256 digest.")

                # Validasi 4: Resource Limits wajib didefinisikan
                resources = c.get("resources", {})
                if "limits" not in resources or "cpu" not in resources["limits"] or "memory" not in resources["limits"]:
                    violations.append(f"DENY: Kontainer '{c.get('name')}' tidak mendefinisikan CPU/Memory limits (Beresiko DoS/OOM cluster).")

        is_allowed = len(violations) == 0
        return is_allowed, violations


def print_banner():
    print(f"{CYAN}{BOLD}{'=' * 75}{RESET}")
    print(f"{WHITE}{BG_BLUE}{BOLD}   LAB SIMULATOR: KUBERNETES RBAC & ADMISSION CONTROLLERS (BAB 08)   {RESET}")
    print(f"{CYAN}{BOLD}{'=' * 75}{RESET}")
    print(f"{DIM}Arsitektur Keamanan: API Server -> AuthN -> AuthZ (RBAC) -> Admission Webhooks{RESET}\n")


def build_default_rbac_env() -> RBACAuthorizer:
    authz = RBACAuthorizer()

    # 1. ClusterRole: cluster-admin (Wildcard)
    authz.add_cluster_role(ClusterRole(
        name="cluster-admin",
        rules=[PolicyRule(api_groups=["*"], resources=["*"], verbs=["*"])]
    ))

    # 2. ClusterRole: view-only
    authz.add_cluster_role(ClusterRole(
        name="view",
        rules=[PolicyRule(api_groups=[""], resources=["pods", "services", "configmaps"], verbs=["get", "list", "watch"])]
    ))

    # 3. Role: pod-manager di namespace 'production'
    authz.add_role(Role(
        name="pod-manager",
        namespace="production",
        rules=[PolicyRule(api_groups=[""], resources=["pods", "pods/log"], verbs=["get", "list", "create", "delete"])]
    ))

    # Binding: dev-alice -> pod-manager (namespace: production)
    authz.add_role_binding(RoleBinding(
        name="alice-prod-binding",
        namespace="production",
        role_name="pod-manager",
        subjects=[{"kind": "User", "name": "alice"}]
    ))

    # Binding: dev-alice -> view di namespace 'staging' menggunakan ClusterRole view
    authz.add_role_binding(RoleBinding(
        name="alice-staging-view",
        namespace="staging",
        role_name="view",
        subjects=[{"kind": "User", "name": "alice"}],
        is_cluster_role=True
    ))

    # ClusterRoleBinding: sec-bob -> cluster-admin
    authz.add_cluster_role_binding(ClusterRoleBinding(
        name="bob-cluster-admin-binding",
        cluster_role_name="cluster-admin",
        subjects=[{"kind": "User", "name": "bob"}]
    ))

    return authz


def demo_rbac_authz(authz: RBACAuthorizer):
    print(f"{YELLOW}{BOLD}[1] Simulasi Evaluasi RBAC ('kubectl auth can-i'){RESET}")
    test_cases = [
        ("alice", [], "get", "pods", "production", "Alice membaca Pod di production"),
        ("alice", [], "create", "pods", "production", "Alice membuat Pod di production"),
        ("alice", [], "delete", "secrets", "production", "Alice menghapus Secret di production"),
        ("alice", [], "get", "pods", "staging", "Alice melihat Pod di staging"),
        ("alice", [], "create", "pods", "staging", "Alice membuat Pod di staging"),
        ("bob", [], "delete", "nodes", "default", "Bob menghapus Node di cluster"),
        ("charlie", [], "get", "pods", "production", "Charlie (tanpa binding) akses Pod"),
    ]

    for user, groups, verb, resource, ns, desc in test_cases:
        allowed, reason = authz.can_i(user, groups, verb, resource, ns)
        status_badge = f"{GREEN}{BOLD}✓ ALLOWED{RESET}" if allowed else f"{RED}{BOLD}✗ DENIED {RESET}"
        print(f"  • {WHITE}{desc:<40}{RESET} -> {status_badge}")
        print(f"    {DIM}Command : kubectl auth can-i {verb} {resource} -n {ns} --as={user}{RESET}")
        print(f"    {CYAN}Status  : {reason}{RESET}\n")


def demo_admission_controller_pipeline():
    print(f"{YELLOW}{BOLD}[2] Simulasi Pipeline Admission Controller (Mutating + Validating){RESET}")
    pipeline = AdmissionControllerPipeline()

    sample_pods = [
        {
            "desc": "Pod Standar Aplikasi Web (Akan dimutasi & divalidasi)",
            "manifest": {
                "apiVersion": "v1",
                "kind": "Pod",
                "metadata": {"name": "frontend-web", "namespace": "production"},
                "spec": {
                    "containers": [{
                        "name": "nginx",
                        "image": "nginx:1.25.3-alpine",
                        "resources": {"limits": {"cpu": "200m", "memory": "256Mi"}}
                    }]
                }
            }
        },
        {
            "desc": "Pod Berbahaya (Privileged Container + HostNetwork + Tag :latest)",
            "manifest": {
                "apiVersion": "v1",
                "kind": "Pod",
                "metadata": {"name": "exploit-pod", "namespace": "production"},
                "spec": {
                    "hostNetwork": True,
                    "containers": [{
                        "name": "attacker-tool",
                        "image": "busybox:latest",
                        "securityContext": {"privileged": True}
                    }]
                }
            }
        }
    ]

    for item in sample_pods:
        desc = item["desc"]
        raw_pod = item["manifest"]
        pod_name = raw_pod["metadata"]["name"]

        print(f"\n{MAGENTA}--- Memproses Permintaan Pembuatan Pod: {pod_name} ---{RESET}")
        print(f"{BOLD}Deskripsi:{RESET} {desc}")

        # Tahap 1: Mutating Webhook
        mutated_pod, mutations = pipeline.mutate(raw_pod)
        print(f"\n  {CYAN}{BOLD}[Fase 1: Mutating Webhook]{RESET}")
        if mutations:
            for m in mutations:
                print(f"    {YELLOW}⚡ {m}{RESET}")
        else:
            print(f"    {DIM}Tidak ada mutasi diterapkan.{RESET}")

        # Tahap 2: Validating Webhook
        print(f"\n  {CYAN}{BOLD}[Fase 2: Validating Webhook & Policy Enforcement]{RESET}")
        is_allowed, violations = pipeline.validate(mutated_pod)
        if is_allowed:
            print(f"    {GREEN}{BOLD}✓ ADMITTED:{RESET} Objek Pod aman dan disimpan ke etcd!")
            print(f"    {DIM}Final Pod Security Context: {json.dumps(mutated_pod['spec']['securityContext'])}{RESET}")
        else:
            print(f"    {RED}{BOLD}✗ REJECTED by Admission Webhook:{RESET}")
            for v in violations:
                print(f"      {RED}• {v}{RESET}")


def interactive_menu():
    authz = build_default_rbac_env()
    pipeline = AdmissionControllerPipeline()

    while True:
        print(f"\n{BOLD}{WHITE}=== MENU PILIHAN SIMULASI INTERAKTIF ==={RESET}")
        print(f"{CYAN}1.{RESET} Jalankan Audit Skenario RBAC Lengkap")
        print(f"{CYAN}2.{RESET} Uji Admission Controller Pipeline (Mutating -> Validating)")
        print(f"{CYAN}3.{RESET} Custom 'kubectl auth can-i' Query")
        print(f"{CYAN}4.{RESET} Uji Pod Kustom ke Validating Webhook")
        print(f"{CYAN}5.{RESET} Keluar")
        
        try:
            choice = input(f"\n{YELLOW}Pilih opsi [1-5]: {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari simulasi.")
            break

        if choice == "1":
            demo_rbac_authz(authz)
        elif choice == "2":
            demo_admission_controller_pipeline()
        elif choice == "3":
            user = input(f"{BOLD}Username (cth: alice, bob, charlie): {RESET}").strip() or "alice"
            verb = input(f"{BOLD}Verb (cth: get, list, create, delete): {RESET}").strip() or "get"
            resource = input(f"{BOLD}Resource (cth: pods, secrets, nodes): {RESET}").strip() or "pods"
            ns = input(f"{BOLD}Namespace (cth: production, staging, default): {RESET}").strip() or "production"
            allowed, reason = authz.can_i(user, [], verb, resource, ns)
            badge = f"{GREEN}[ALLOWED]{RESET}" if allowed else f"{RED}[DENIED]{RESET}"
            print(f"\nHasil: {badge}\nDetail: {reason}")
        elif choice == "4":
            print(f"\nMenguji Pod Berbahaya: priv=True, img='malicious:latest'...")
            test_pod = {
                "kind": "Pod",
                "spec": {
                    "containers": [{
                        "name": "test-c",
                        "image": "my-tool:latest",
                        "securityContext": {"privileged": True}
                    }]
                }
            }
            allowed, reasons = pipeline.validate(test_pod)
            if allowed:
                print(f"{GREEN}Pod lolos validasi.{RESET}")
            else:
                print(f"{RED}Pod ditolak dengan pelanggaran:{RESET}")
                for r in reasons:
                    print(f"  • {r}")
        elif choice == "5":
            print(f"{GREEN}Selesai. Terima kasih!{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid.{RESET}")


def main():
    print_banner()
    # Jika dijalankan secara non-interaktif atau dengan parameter --demo, jalankan skenario otomatis
    if len(sys.argv) > 1 and sys.argv[1] in ("--demo", "-d") or not sys.stdin.isatty():
        authz = build_default_rbac_env()
        demo_rbac_authz(authz)
        demo_admission_controller_pipeline()
        print(f"{GREEN}{BOLD}✓ Demonstrasi non-interaktif selesai dengan sukses.{RESET}")
    else:
        interactive_menu()


if __name__ == "__main__":
    main()
