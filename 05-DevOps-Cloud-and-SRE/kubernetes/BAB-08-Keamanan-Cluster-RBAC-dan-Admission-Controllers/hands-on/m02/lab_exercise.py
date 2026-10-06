#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Arsitektur Keamanan Kubernetes Tingkat Lanjut
Fokus: RBAC (Role-Based Access Control) & Admission Controllers (Mutating/Validating Webhook)
BAB-08: Keamanan Cluster, RBAC, dan Admission Controllers
"""

import sys
import time
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Tuple, Any

# ANSI Color Codes untuk visualisasi terminal interaktif
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[1;31m"
    GREEN = "\033[1;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[1;34m"
    MAGENTA = "\033[1;35m"
    CYAN = "\033[1;36m"
    WHITE = "\033[1;37m"
    BG_DARK = "\033[40m"


class SubjectKind(Enum):
    USER = "User"
    SERVICE_ACCOUNT = "ServiceAccount"
    GROUP = "Group"


@dataclass
class PolicyRule:
    api_groups: List[str]
    resources: List[str]
    verbs: List[str]

    def matches(self, api_group: str, resource: str, verb: str) -> bool:
        group_match = ("*" in self.api_groups) or (api_group in self.api_groups)
        resource_match = ("*" in self.resources) or (resource in self.resources)
        verb_match = ("*" in self.verbs) or (verb in self.verbs)
        return group_match and resource_match and verb_match


@dataclass
class Role:
    name: str
    namespace: str
    rules: List[PolicyRule]


@dataclass
class ClusterRole:
    name: str
    rules: List[PolicyRule]


@dataclass
class RoleBinding:
    name: str
    namespace: str
    role_name: str
    subjects: List[Tuple[SubjectKind, str, Optional[str]]]  # (Kind, Name, Namespace)


@dataclass
class ClusterRoleBinding:
    name: str
    cluster_role_name: str
    subjects: List[Tuple[SubjectKind, str, Optional[str]]]


@dataclass
class AdmissionReviewRequest:
    uid: str
    namespace: str
    resource: str
    operation: str  # CREATE, UPDATE, DELETE
    user_info: str
    object_spec: Dict[str, Any]


@dataclass
class AdmissionResponse:
    allowed: bool
    status_code: int
    message: str
    patches: List[Dict[str, Any]] = field(default_factory=list)


class RBACAuthorizationEngine:
    def __init__(self):
        self.roles: Dict[str, Role] = {}
        self.cluster_roles: Dict[str, ClusterRole] = {}
        self.role_bindings: List[RoleBinding] = []
        self.cluster_role_bindings: List[ClusterRoleBinding] = []

    def add_role(self, role: Role):
        self.roles[f"{role.namespace}/{role.name}"] = role

    def add_cluster_role(self, cluster_role: ClusterRole):
        self.cluster_roles[cluster_role.name] = cluster_role

    def add_role_binding(self, binding: RoleBinding):
        self.role_bindings.append(binding)

    def add_cluster_role_binding(self, binding: ClusterRoleBinding):
        self.cluster_role_bindings.append(binding)

    def authorize(
        self,
        subject_kind: SubjectKind,
        subject_name: str,
        subject_ns: Optional[str],
        verb: str,
        api_group: str,
        resource: str,
        target_namespace: Optional[str] = None,
    ) -> Tuple[bool, str]:
        # 1. Evaluasi ClusterRoleBindings
        for crb in self.cluster_role_bindings:
            for s_kind, s_name, s_ns in crb.subjects:
                if s_kind == subject_kind and s_name == subject_name:
                    if s_kind == SubjectKind.SERVICE_ACCOUNT and s_ns != subject_ns:
                        continue
                    crole = self.cluster_roles.get(crb.cluster_role_name)
                    if crole:
                        for rule in crole.rules:
                            if rule.matches(api_group, resource, verb):
                                return True, f"Allowed by ClusterRoleBinding '{crb.name}' -> ClusterRole '{crole.name}'"

        # 2. Evaluasi RoleBindings spesifik namespace
        if target_namespace:
            for rb in self.role_bindings:
                if rb.namespace == target_namespace:
                    for s_kind, s_name, s_ns in rb.subjects:
                        if s_kind == subject_kind and s_name == subject_name:
                            if s_kind == SubjectKind.SERVICE_ACCOUNT and s_ns != subject_ns:
                                continue
                            role_key = f"{rb.namespace}/{rb.role_name}"
                            role = self.roles.get(role_key)
                            if role:
                                for rule in role.rules:
                                    if rule.matches(api_group, resource, verb):
                                        return True, f"Allowed by RoleBinding '{rb.name}' -> Role '{role.name}' in ns '{target_namespace}'"

        return False, "Access Denied: Tidak ada rule RBAC eksplisit yang mengizinkan aksi ini (Default Deny)"


class MutatingAdmissionWebhook:
    """Simulasi Mutating Webhook: Menginjeksi securityContext dan sidecar logger"""
    def __init__(self, name: str):
        self.name = name

    def mutate(self, req: AdmissionReviewRequest) -> AdmissionResponse:
        spec = req.object_spec
        patches = []

        pod_spec = spec.get("spec", {})
        sec_ctx = pod_spec.get("securityContext", {})

        # Mutasi 1: Enforce runAsNonRoot
        if not sec_ctx.get("runAsNonRoot", False):
            patches.append({
                "op": "add",
                "path": "/spec/securityContext/runAsNonRoot",
                "value": True
            })

        # Mutasi 2: Inject readOnlyRootFilesystem pada container jika belum diset
        containers = pod_spec.get("containers", [])
        for idx, container in enumerate(containers):
            c_sec = container.get("securityContext", {})
            if not c_sec.get("readOnlyRootFilesystem", False):
                patches.append({
                    "op": "add",
                    "path": f"/spec/containers/{idx}/securityContext/readOnlyRootFilesystem",
                    "value": True
                })

        # Mutasi 3: Inject Istio/Audit Sidecar jika ada label inject-audit
        metadata = spec.get("metadata", {})
        labels = metadata.get("labels", {})
        if labels.get("security.zone/audit", "") == "enabled":
            patches.append({
                "op": "add",
                "path": "/spec/containers/-",
                "value": {
                    "name": "audit-proxy-sidecar",
                    "image": "internal-registry.corp/sec/audit-agent:v2.4.1",
                    "resources": {"limits": {"cpu": "100m", "memory": "64Mi"}}
                }
            })

        return AdmissionResponse(
            allowed=True,
            status_code=200,
            message="Mutating webhook executed successfully. Patches generated.",
            patches=patches
        )


class ValidatingAdmissionWebhook:
    """Simulasi Validating Webhook: Validasi Pod Security Standards (Restricted) & Registry Whitelist"""
    ALLOWED_REGISTRIES = ["harbor.corp.internal/", "ecr.aws.com/prod/"]

    def __init__(self, name: str):
        self.name = name

    def validate(self, req: AdmissionReviewRequest) -> AdmissionResponse:
        spec = req.object_spec
        pod_spec = spec.get("spec", {})

        # Aturan 1: Tolak Privileged Container
        for container in pod_spec.get("containers", []):
            c_sec = container.get("securityContext", {})
            if c_sec.get("privileged", False) is True:
                return AdmissionResponse(
                    allowed=False,
                    status_code=403,
                    message=f"REJECTED: Container '{container.get('name')}' meminta mode privileged=true (Melanggar PSS Restricted)."
                )

        # Aturan 2: Tolak HostPath Volumes
        for volume in pod_spec.get("volumes", []):
            if "hostPath" in volume:
                return AdmissionResponse(
                    allowed=False,
                    status_code=403,
                    message=f"REJECTED: Volume '{volume.get('name')}' menggunakan hostPath mount (Risiko container breakout)."
                )

        # Aturan 3: Image Registry Whitelist Enforcement
        for container in pod_spec.get("containers", []):
            image = container.get("image", "")
            is_allowed = any(image.startswith(prefix) for prefix in self.ALLOWED_REGISTRIES)
            if not is_allowed:
                return AdmissionResponse(
                    allowed=False,
                    status_code=403,
                    message=f"REJECTED: Image '{image}' berasal dari registry tidak terotorisasi. Hanya diperbolehkan: {self.ALLOWED_REGISTRIES}"
                )

        return AdmissionResponse(
            allowed=True,
            status_code=200,
            message="VALIDATED: Pod mematuhi Pod Security Standards (Restricted) dan supply chain policy."
        )


class KubernetesSecurityPipeline:
    def __init__(self):
        self.rbac = RBACAuthorizationEngine()
        self.mutating_webhooks: List[MutatingAdmissionWebhook] = []
        self.validating_webhooks: List[ValidatingAdmissionWebhook] = []

    def register_mutating_webhook(self, webhook: MutatingAdmissionWebhook):
        self.mutating_webhooks.append(webhook)

    def register_validating_webhook(self, webhook: ValidatingAdmissionWebhook):
        self.validating_webhooks.append(webhook)

    def apply_admission_phase(
        self,
        subject_kind: SubjectKind,
        subject_name: str,
        subject_ns: Optional[str],
        verb: str,
        api_group: str,
        resource: str,
        target_namespace: str,
        object_payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        print(f"\n{Color.BOLD}{Color.CYAN}--- Memulai Kubernetes API Request Pipeline ---{Color.RESET}")
        print(f"Request: {Color.YELLOW}{verb.upper()} {api_group}/{resource}{Color.RESET} in ns '{target_namespace}'")
        print(f"Subject: {Color.WHITE}{subject_kind.value}:{subject_name}{Color.RESET} (Origin NS: {subject_ns})")

        # Tahap 1: Authentication & RBAC Authorization
        print(f"\n{Color.BOLD}[Phase 1: RBAC Authorization]{Color.RESET}")
        time.sleep(0.3)
        auth_ok, auth_reason = self.rbac.authorize(
            subject_kind=subject_kind,
            subject_name=subject_name,
            subject_ns=subject_ns,
            verb=verb,
            api_group=api_group,
            resource=resource,
            target_namespace=target_namespace
        )

        if not auth_ok:
            print(f"  {Color.RED}✖ 403 Forbidden: {auth_reason}{Color.RESET}")
            return {"status": "FORBIDDEN", "phase": "RBAC", "reason": auth_reason}
        print(f"  {Color.GREEN}✔ Authorized: {auth_reason}{Color.RESET}")

        # Tahap 2: Mutating Admission Controller
        print(f"\n{Color.BOLD}[Phase 2: Mutating Admission Webhook]{Color.RESET}")
        time.sleep(0.3)
        review_req = AdmissionReviewRequest(
            uid="req-uuid-992384-xaa",
            namespace=target_namespace,
            resource=resource,
            operation="CREATE",
            user_info=subject_name,
            object_spec=object_payload
        )

        accumulated_patches = []
        for mwh in self.mutating_webhooks:
            res = mwh.mutate(review_req)
            if not res.allowed:
                print(f"  {Color.RED}✖ Mutation Failed by {mwh.name}: {res.message}{Color.RESET}")
                return {"status": "REJECTED", "phase": "MutatingWebhook", "reason": res.message}
            if res.patches:
                print(f"  {Color.MAGENTA}⚡ [{mwh.name}] Mutasi diterapkan ({len(res.patches)} patch):{Color.RESET}")
                for patch in res.patches:
                    print(f"    - {patch['op']} {patch['path']} => {json.dumps(patch.get('value', ''))}")
                accumulated_patches.extend(res.patches)
            else:
                print(f"  {Color.DIM}• [{mwh.name}] Tidak ada perubahan yang diperlukan.{Color.RESET}")

        # Tahap 3: Validating Admission Controller
        print(f"\n{Color.BOLD}[Phase 3: Validating Admission Webhook]{Color.RESET}")
        time.sleep(0.3)
        for vwh in self.validating_webhooks:
            vres = vwh.validate(review_req)
            if not vres.allowed:
                print(f"  {Color.RED}✖ Admission Denied by [{vwh.name}]: {vres.message}{Color.RESET}")
                return {"status": "DENIED", "phase": "ValidatingWebhook", "reason": vres.message}
            print(f"  {Color.GREEN}✔ Validated by [{vwh.name}]: {vres.message}{Color.RESET}")

        # Tahap 4: Persistence ke etcd
        print(f"\n{Color.BOLD}[Phase 4: Persistence / etcd Commit]{Color.RESET}")
        time.sleep(0.2)
        print(f"  {Color.GREEN}{Color.BOLD}✔ Object sukses disimpan ke etcd cluster.{Color.RESET}")
        return {
            "status": "SUCCESS",
            "phase": "Completed",
            "patches_applied": len(accumulated_patches),
            "reason": "Resource created with enforced security governance."
        }


def setup_sample_cluster_security(pipeline: KubernetesSecurityPipeline):
    # 1. Definisi ClusterRole dan Role
    cluster_admin_role = ClusterRole(
        name="platform-secops-admin",
        rules=[
            PolicyRule(api_groups=["*"], resources=["*"], verbs=["*"])
        ]
    )
    dev_role = Role(
        name="workload-developer",
        namespace="apps-production",
        rules=[
            PolicyRule(api_groups=[""], resources=["pods", "services", "configmaps"], verbs=["get", "list", "watch", "create", "update"])
        ]
    )

    pipeline.rbac.add_cluster_role(cluster_admin_role)
    pipeline.rbac.add_role(dev_role)

    # 2. Binding
    pipeline.rbac.add_cluster_role_binding(
        ClusterRoleBinding(
            name="secops-global-binding",
            cluster_role_name="platform-secops-admin",
            subjects=[(SubjectKind.USER, "secops-lead@corp.internal", None)]
        )
    )
    pipeline.rbac.add_role_binding(
        RoleBinding(
            name="dev-team-binding",
            namespace="apps-production",
            role_name="workload-developer",
            subjects=[(SubjectKind.SERVICE_ACCOUNT, "app-deployer-sa", "apps-production")]
        )
    )

    # 3. Webhooks
    pipeline.register_mutating_webhook(MutatingAdmissionWebhook("security-hardening-injector"))
    pipeline.register_validating_webhook(ValidatingAdmissionWebhook("pss-restricted-enforcer"))


def run_interactive_lab():
    pipeline = KubernetesSecurityPipeline()
    setup_sample_cluster_security(pipeline)

    print("=" * 80)
    print(f"{Color.BOLD}{Color.WHITE}KUBERNETES ADVANCED SECURITY LAB: RBAC & ADMISSION CONTROLLER SIMULATOR{Color.RESET}")
    print(f"{Color.CYAN}Modul 02: Hands-on Enterprise Zero-Trust Workload Hardening{Color.RESET}")
    print("=" * 80)

    scenarios = [
        {
            "title": "Scenario 1: Hacker / Anonim mencoba membuat Pod di production tanpa RBAC",
            "subject_kind": SubjectKind.USER,
            "subject_name": "unknown-attacker",
            "subject_ns": None,
            "verb": "create",
            "api_group": "",
            "resource": "pods",
            "namespace": "apps-production",
            "payload": {
                "apiVersion": "v1",
                "kind": "Pod",
                "metadata": {"name": "crypto-miner"},
                "spec": {
                    "containers": [{"name": "miner", "image": "docker.io/malicious/xmrig:latest"}]
                }
            }
        },
        {
            "title": "Scenario 2: Developer Deployer SA membuat Pod Non-Compliant (Privileged & Public Registry)",
            "subject_kind": SubjectKind.SERVICE_ACCOUNT,
            "subject_name": "app-deployer-sa",
            "subject_ns": "apps-production",
            "verb": "create",
            "api_group": "",
            "resource": "pods",
            "namespace": "apps-production",
            "payload": {
                "apiVersion": "v1",
                "kind": "Pod",
                "metadata": {"name": "rogue-debug-pod"},
                "spec": {
                    "containers": [{
                        "name": "debugger",
                        "image": "docker.io/ubuntu:latest",
                        "securityContext": {"privileged": True}
                    }]
                }
            }
        },
        {
            "title": "Scenario 3: Developer Deployer SA membuat Pod Valid (Akan di-mutate & di-validate)",
            "subject_kind": SubjectKind.SERVICE_ACCOUNT,
            "subject_name": "app-deployer-sa",
            "subject_ns": "apps-production",
            "verb": "create",
            "api_group": "",
            "resource": "pods",
            "namespace": "apps-production",
            "payload": {
                "apiVersion": "v1",
                "kind": "Pod",
                "metadata": {
                    "name": "payment-api-service",
                    "labels": {"security.zone/audit": "enabled"}
                },
                "spec": {
                    "containers": [{
                        "name": "web-api",
                        "image": "harbor.corp.internal/fintech/payment-gateway:v1.12.0",
                        "securityContext": {"privileged": False}
                    }]
                }
            }
        },
        {
            "title": "Scenario 4: SecOps Lead memeriksa cluster-wide Secret (Valid RBAC)",
            "subject_kind": SubjectKind.USER,
            "subject_name": "secops-lead@corp.internal",
            "subject_ns": None,
            "verb": "get",
            "api_group": "",
            "resource": "secrets",
            "namespace": "kube-system",
            "payload": {
                "apiVersion": "v1",
                "kind": "Secret",
                "metadata": {"name": "etcd-certs"}
            }
        }
    ]

    for idx, sc in enumerate(scenarios, start=1):
        print(f"\n{Color.BG_DARK}{Color.BOLD}>>> {sc['title']} <<<{Color.RESET}")
        result = pipeline.apply_admission_phase(
            subject_kind=sc["subject_kind"],
            subject_name=sc["subject_name"],
            subject_ns=sc["subject_ns"],
            verb=sc["verb"],
            api_group=sc["api_group"],
            resource=sc["resource"],
            target_namespace=sc["namespace"],
            object_payload=sc["payload"]
        )
        print(f"{Color.BOLD}Hasil Akhir: [{result['status']}] (Phase: {result['phase']}){Color.RESET}")
        print("-" * 80)
        time.sleep(0.5)

    print(f"\n{Color.GREEN}{Color.BOLD}✔ Seluruh skenario simulasi keamanan cluster berhasil dieksekusi.{Color.RESET}")
    print(f"{Color.CYAN}Ringkasan: Zero-Trust arsitektur Kubernetes mengintegrasikan otentikasi identitas, otorisasi RBAC least-privilege, mutasi keamanan otomatis, serta validasi integritas kontainer sebelum persistensi etcd.{Color.RESET}\n")


if __name__ == "__main__":
    run_interactive_lab()
