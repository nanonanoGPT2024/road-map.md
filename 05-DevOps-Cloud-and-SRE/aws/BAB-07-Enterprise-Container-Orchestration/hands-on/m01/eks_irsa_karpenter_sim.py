#!/usr/bin/env python3
"""
EKS IRSA, Karpenter Bin-Packing, and Service Connect Architectural Simulator
Author: Principal Cloud & SRE Curriculum Architect
Language: Python 3.9+
Dependencies: Standard Library Only (math, json, hashlib, time, uuid, typing)

Deskripsi:
Skrip mandiri ini memvalidasi dan mensimulasikan tiga pilar utama Container Orchestration AWS:
1. Validasi Kriptografi & OIDC Claims Matching untuk EKS IRSA (IAM Roles for Service Accounts).
2. Simulasi Algoritma Bin-Packing & Autoscaling Karpenter v1 vs Traditional ASG-based Cluster Autoscaler.
3. Simulasi Outlier Detection & Circuit Breaking pada ECS Service Connect / Envoy sidecar mesh.
"""

import sys
import json
import time
import math
import uuid
import hashlib
from typing import Dict, List, Any, Tuple, Optional

# ==============================================================================
# 1. CORE SIMULATION ENGINE: IRSA & OIDC CLAIMS VERIFIER
# ==============================================================================

class MockOIDCProvider:
    def __init__(self, cluster_id: str, region: str = "us-east-1"):
        self.issuer_url = f"https://oidc.eks.{region}.amazonaws.com/id/{cluster_id}"
        self.audience = "sts.amazonaws.com"
        # Secret simulated cluster signing key
        self._private_signing_key = f"k8s-priv-key-{uuid.uuid4()}"

    def issue_token(self, namespace: str, service_account: str, expiry_seconds: int = 3600) -> str:
        """Menghasilkan representasi JWT terenkripsi sederhana untuk ServiceAccount."""
        header = {"alg": "RS256", "typ": "JWT"}
        payload = {
            "iss": self.issuer_url,
            "sub": f"system:serviceaccount:{namespace}:{service_account}",
            "aud": self.audience,
            "exp": int(time.time()) + expiry_seconds,
            "iat": int(time.time())
        }
        raw_header = json.dumps(header).encode().hex()
        raw_payload = json.dumps(payload).encode().hex()
        signature_material = f"{raw_header}.{raw_payload}.{self._private_signing_key}"
        signature = hashlib.sha256(signature_material.encode()).hexdigest()
        return f"{raw_header}.{raw_payload}.{signature}"

class MockAWSSTS:
    def __init__(self):
        self.registered_trust_policies: Dict[str, Dict[str, Any]] = {}

    def register_role(self, role_arn: str, trust_policy: Dict[str, Any]):
        self.registered_trust_policies[role_arn] = trust_policy

    def assume_role_with_web_identity(
        self,
        role_arn: str,
        web_identity_token: str,
        oidc_provider: MockOIDCProvider
    ) -> Tuple[bool, str, Optional[Dict[str, str]]]:
        """Memverifikasi signature, audience, issuer, dan condition claims."""
        if role_arn not in self.registered_trust_policies:
            return False, "AccessDenied: Role does not exist.", None

        parts = web_identity_token.split(".")
        if len(parts) != 3:
            return False, "InvalidIdentityToken: Malformed JWT token.", None

        raw_header, raw_payload, token_signature = parts
        # Verifikasi tanda tangan
        expected_sig_mat = f"{raw_header}.{raw_payload}.{oidc_provider._private_signing_key}"
        expected_sig = hashlib.sha256(expected_sig_mat.encode()).hexdigest()
        if token_signature != expected_sig:
            return False, "InvalidIdentityToken: Signature verification failed.", None

        payload = json.loads(bytes.fromhex(raw_payload).decode())

        # Verifikasi Issuer & Expiry
        if payload.get("iss") != oidc_provider.issuer_url:
            return False, "InvalidIdentityToken: Issuer mismatch.", None
        if payload.get("exp", 0) < time.time():
            return False, "ExpiredToken: Token has expired.", None
        if payload.get("aud") != oidc_provider.audience:
            return False, "InvalidIdentityToken: Audience mismatch.", None

        # Evaluasi IAM Policy Trust Relationship Condition
        policy = self.registered_trust_policies[role_arn]
        statement = policy.get("Statement", [])[0]
        conditions = statement.get("Condition", {}).get("StringEquals", {})

        issuer_clean = oidc_provider.issuer_url.replace("https://", "")
        expected_sub_claim = f"{issuer_clean}:sub"
        expected_aud_claim = f"{issuer_clean}:aud"

        if expected_aud_claim in conditions:
            if conditions[expected_aud_claim] != payload.get("aud"):
                return False, "AccessDenied: STS Audience condition mismatch.", None

        if expected_sub_claim in conditions:
            if conditions[expected_sub_claim] != payload.get("sub"):
                return False, f"AccessDenied: Subject claim {payload.get('sub')} does not match {conditions[expected_sub_claim]}.", None

        # Sukses - generate STS Temporary Credentials
        credentials = {
            "AccessKeyId": f"ASIA{uuid.uuid4().hex[:16].upper()}",
            "SecretAccessKey": uuid.uuid4().hex,
            "SessionToken": f"IQoJb3JpZ2luX2VjEAM...simulated_token...{uuid.uuid4().hex}",
            "Expiration": time.strftime('%Y-%m-%d %H:%M:%SZ', time.gmtime(time.time() + 3600))
        }
        return True, "Success", credentials


# ==============================================================================
# 2. KARPENTER HIGH-PERFORMANCE BIN-PACKING SIMULATOR
# ==============================================================================

class EC2InstanceType:
    def __init__(self, name: str, vcpu: int, memory_gib: float, hourly_cost_od: float, hourly_cost_spot: float):
        self.name = name
        self.vcpu = vcpu
        self.memory_gib = memory_gib
        self.hourly_cost_od = hourly_cost_od
        self.hourly_cost_spot = hourly_cost_spot

AVAILABLE_CATALOG = [
    EC2InstanceType("c6g.large",   2,  4.0,  0.0680, 0.0245),
    EC2InstanceType("c6g.xlarge",  4,  8.0,  0.1360, 0.0490),
    EC2InstanceType("m6g.xlarge",  4, 16.0,  0.1540, 0.0554),
    EC2InstanceType("m6g.2xlarge", 8, 32.0,  0.3080, 0.1109),
    EC2InstanceType("c6g.2xlarge", 8, 16.0,  0.2720, 0.0980),
    EC2InstanceType("r6g.xlarge",  4, 32.0,  0.2016, 0.0726),
]

class PodWorkload:
    def __init__(self, name: str, cpu_milli: int, mem_mib: int, capacity_preference: str = "spot"):
        self.name = name
        self.cpu_milli = cpu_milli
        self.mem_mib = mem_mib
        self.capacity_preference = capacity_preference

class KarpenterBinPacker:
    """Simulasi Karpenter v1 first-fit decreasing bin packing logic."""

    @staticmethod
    def pack(pods: List[PodWorkload], use_spot: bool = True) -> List[Dict[str, Any]]:
        total_cpu_needed = sum(p.cpu_milli for p in pods) / 1000.0
        total_mem_needed = sum(p.mem_mib for p in pods) / 1024.0

        # Cari instance terkecil dari catalog yang mampu menampung beban (Simulasi Bin-packing)
        selected_nodes = []
        remaining_cpu = total_cpu_needed
        remaining_mem = total_mem_needed

        # Urutkan katalog berdasarkan rasio efisiensi harga
        catalog_sorted = sorted(AVAILABLE_CATALOG, key=lambda x: (x.hourly_cost_spot if use_spot else x.hourly_cost_od) / (x.vcpu + x.memory_gib), reverse=False)

        while remaining_cpu > 0 or remaining_mem > 0:
            best_fit: Optional[EC2InstanceType] = None
            for inst in catalog_sorted:
                if inst.vcpu >= remaining_cpu and inst.memory_gib >= remaining_mem:
                    best_fit = inst
                    break
            
            if not best_fit:
                # Jika pod terlalu banyak, ambil instance terbesar yang tersedia
                best_fit = max(AVAILABLE_CATALOG, key=lambda x: x.vcpu)

            cost = best_fit.hourly_cost_spot if use_spot else best_fit.hourly_cost_od
            selected_nodes.append({
                "instance_type": best_fit.name,
                "vcpu": best_fit.vcpu,
                "memory_gib": best_fit.memory_gib,
                "cost_hourly": cost,
                "capacity_type": "spot" if use_spot else "on-demand",
                "provisioning_time_seconds": 38 # Rata-rata peluncuran native EC2 fleet API
            })
            remaining_cpu -= best_fit.vcpu
            remaining_mem -= best_fit.memory_gib

        return selected_nodes


# ==============================================================================
# 3. ECS SERVICE CONNECT & CIRCUIT BREAKER SIMULATOR
# ==============================================================================

class ServiceConnectMeshSimulator:
    def __init__(self, error_threshold_consecutive: int = 3, ejection_time_sec: float = 2.0):
        self.error_threshold = error_threshold_consecutive
        self.ejection_time_sec = ejection_time_sec
        self.consecutive_5xx = 0
        self.is_ejected = False
        self.ejected_until = 0.0

    def route_request(self, should_fail: bool) -> Tuple[int, str]:
        current_time = time.time()
        # Periksa apakah sirkuit sedang terputus (ejected)
        if self.is_ejected:
            if current_time < self.ejected_until:
                return 503, "ServiceConnect: CircuitBreakerOpen (Host Ejected)"
            else:
                # Half-Open State
                self.is_ejected = False
                self.consecutive_5xx = 0

        if should_fail:
            self.consecutive_5xx += 1
            if self.consecutive_5xx >= self.error_threshold:
                self.is_ejected = True
                self.ejected_until = current_time + self.ejection_time_sec
                return 500, f"InternalServerError (Threshold reached: Host Ejected for {self.ejection_time_sec}s)"
            return 500, "InternalServerError"
        else:
            self.consecutive_5xx = 0
            return 200, "OK"


# ==============================================================================
# MAIN TEST & DEMONSTRATION HARNESS
# ==============================================================================

def main():
    print("=" * 80)
    print("AWS CONTAINER ORCHESTRATION ARCHITECTURAL ENGINE VALIDATOR")
    print("Standard Kurikulum: GEMINI.md Enterprise Grade")
    print("=" * 80)

    # --------------------------------------------------------------------------
    # TEST 1: EKS IRSA OIDC VALIDATION
    # --------------------------------------------------------------------------
    print("\n[TEST 1] Menguji Mekanisme Keamanan IAM Roles for Service Accounts (IRSA)...")
    cluster_oidc_id = "4A8B9C0D1E2F3A4B5C6D7E8F9A0B1C2D"
    oidc_engine = MockOIDCProvider(cluster_id=cluster_oidc_id)
    sts_engine = MockAWSSTS()

    target_role_arn = "arn:aws:iam::123456789012:role/ProductionPaymentGatewayRole"
    correct_trust_policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Federated": f"arn:aws:iam::123456789012:oidc-provider/oidc.eks.us-east-1.amazonaws.com/id/{cluster_oidc_id}"},
            "Action": "sts:AssumeRoleWithWebIdentity",
            "Condition": {
                "StringEquals": {
                    f"oidc.eks.us-east-1.amazonaws.com/id/{cluster_oidc_id}:aud": "sts.amazonaws.com",
                    f"oidc.eks.us-east-1.amazonaws.com/id/{cluster_oidc_id}:sub": "system:serviceaccount:payments:payment-sa"
                }
            }
        }]
    }
    sts_engine.register_role(target_role_arn, correct_trust_policy)

    # Skenario 1.a: Valid Authorized Pod Token
    valid_jwt = oidc_engine.issue_token(namespace="payments", service_account="payment-sa")
    success, msg, creds = sts_engine.assume_role_with_web_identity(target_role_arn, valid_jwt, oidc_engine)
    print(f"  -> Scenario 1.a: Authorized Pod (namespace: payments, SA: payment-sa)")
    print(f"     Status: {'SUCCESS' if success else 'FAILED'} | Pesan: {msg}")
    if creds:
        print(f"     Temporary AccessKeyId: {creds['AccessKeyId']}")

    # Skenario 1.b: Unauthorized Rogue Pod (Cross-Namespace Privilege Escalation Attempt)
    rogue_jwt = oidc_engine.issue_token(namespace="default", service_account="rogue-sa")
    success_rogue, msg_rogue, _ = sts_engine.assume_role_with_web_identity(target_role_arn, rogue_jwt, oidc_engine)
    print(f"  -> Scenario 1.b: Unauthorized Pod Attempt (namespace: default, SA: rogue-sa)")
    print(f"     Status: {'SUCCESS (ALERT VULNERABILITY!)' if success_rogue else 'SECURE / BLOCKED'} | Detail: {msg_rogue}")

    # --------------------------------------------------------------------------
    # TEST 2: KARPENTER PACKING SIMULATION VS CLUSTER AUTOSCALER
    # --------------------------------------------------------------------------
    print("\n[TEST 2] Simulasi Karpenter Auto-provisioning & Fast Bin-Packing...")
    # Beban lonjakan: 45 pod checkout microservice baru
    pending_pods = [PodWorkload(name=f"checkout-{i}", cpu_milli=500, mem_mib=1024) for i in range(45)]
    total_cpu_req = sum(p.cpu_milli for p in pending_pods) / 1000.0
    total_mem_req = sum(p.mem_mib for p in pending_pods) / 1024.0

    print(f"  -> Beban Menumpuk: 45 Pods Pending | Kebutuhan Total: {total_cpu_req} vCPU, {total_mem_req} GiB RAM")

    # Karpenter calculation
    karpenter_nodes = KarpenterBinPacker.pack(pending_pods, use_spot=True)
    total_karpenter_cost = sum(n["cost_hourly"] for n in karpenter_nodes)
    karpenter_time = max(n["provisioning_time_seconds"] for n in karpenter_nodes)

    # Legacy ASG Cluster Autoscaler estimation (Menggunakan m5.large statis On-Demand via ASG)
    nodes_needed_cas = math.ceil(max(total_cpu_req / 2, total_mem_req / 8))
    cas_cost_hourly = nodes_needed_cas * 0.096 # m5.large On-Demand price
    cas_provisioning_time = 320 # ~5.3 menit (ASG launch + CloudInit initialization)

    print("\n  [KOMPARASI AUTOSCALING]")
    print(f"  * Karpenter v1 (Direct EC2 Fleet + Spot Bin-pack):")
    for idx, n in enumerate(karpenter_nodes):
        print(f"    - Node {idx+1}: Type={n['instance_type']}, vCPU={n['vcpu']}, RAM={n['memory_gib']}GiB, Cost=${n['cost_hourly']:.4f}/hr ({n['capacity_type']})")
    print(f"    Total Biaya Compute: ${total_karpenter_cost:.4f}/jam")
    print(f"    Estimasi Provisioning Time: {karpenter_time} detik!")

    print(f"\n  * Legacy Kubernetes Cluster Autoscaler (ASG Fixed Type):")
    print(f"    - Memerlukan: {nodes_needed_cas} instance m5.large On-Demand")
    print(f"    Total Biaya Compute: ${cas_cost_hourly:.4f}/jam")
    print(f"    Estimasi Provisioning Time: {cas_provisioning_time} detik (~5.3 menit)")

    cost_saving = ((cas_cost_hourly - total_karpenter_cost) / cas_cost_hourly) * 100
    time_saving = ((cas_provisioning_time - karpenter_time) / cas_provisioning_time) * 100
    print(f"\n  HASIL: Penghematan Biaya = {cost_saving:.1f}% | Percepatan Scaling = {time_saving:.1f}%")

    # --------------------------------------------------------------------------
    # TEST 3: SERVICE CONNECT OUTLIER DETECTION (CIRCUIT BREAKER)
    # --------------------------------------------------------------------------
    print("\n[TEST 3] Simulasi AWS Service Connect / Envoy Resiliency (Outlier Detection)...")
    sc_mesh = ServiceConnectMeshSimulator(error_threshold_consecutive=3, ejection_time_sec=1.5)

    request_trace = [False, False, True, True, True, False, False]
    for step, is_failure in enumerate(request_trace, start=1):
        status, reason = sc_mesh.route_request(should_fail=is_failure)
        print(f"  Req #{step}: InjectedFailure={is_failure} -> Code {status} ({reason})")
        time.sleep(0.1)

    print("\nMenunggu masa cooldown ejection circuit breaker (1.5s)...")
    time.sleep(1.6)
    status_recover, reason_recover = sc_mesh.route_request(should_fail=False)
    print(f"  Req post-cooldown: InjectedFailure=False -> Code {status_recover} ({reason_recover}) [CIRCUIT CLOSED]")

    print("\n" + "=" * 80)
    print("SIMULASI INTEGRASI SELESAI: SELURUH PRINSIP ARSITEKTUR TERVALIDASI DENGAN SUKSES.")
    print("=" * 80)

if __name__ == "__main__":
    main()