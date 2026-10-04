#!/usr/bin/env python3
"""
AWS IAM Policy Evaluation Engine & STS AssumeRole Simulation
=============================================================
Simulasi komprehensif alur evaluasi kebijakan AWS IAM:
1. Default Deny
2. Explicit Deny Check (Prioritas Utama)
3. Explicit Allow Check
4. STS AssumeRole & Trust Policy Evaluation
"""

import fnmatch
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

# ANSI Color Codes for terminal visualization
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


@dataclass
class PolicyStatement:
    sid: str
    effect: str  # "Allow" or "Deny"
    actions: List[str]
    resources: List[str]
    principal: Optional[Any] = None
    conditions: Dict[str, Any] = field(default_factory=dict)

    def matches_action(self, action: str) -> bool:
        return any(fnmatch.fnmatch(action.lower(), pattern.lower()) for pattern in self.actions)

    def matches_resource(self, resource_arn: str) -> bool:
        return any(fnmatch.fnmatch(resource_arn, pattern) for pattern in self.resources)

    def matches_principal(self, principal_arn: str) -> bool:
        if self.principal is None:
            return True
        if isinstance(self.principal, str):
            return fnmatch.fnmatch(principal_arn, self.principal)
        if isinstance(self.principal, dict) and "AWS" in self.principal:
            allowed = self.principal["AWS"]
            if isinstance(allowed, list):
                return any(fnmatch.fnmatch(principal_arn, p) for p in allowed)
            return fnmatch.fnmatch(principal_arn, allowed)
        return False


@dataclass
class IAMPolicy:
    name: str
    statements: List[PolicyStatement]


@dataclass
class IAMRole:
    arn: str
    name: str
    assume_role_policy: IAMPolicy  # Trust Policy
    attached_policies: List[IAMPolicy] = field(default_factory=list)


@dataclass
class TemporaryCredentials:
    access_key_id: str
    secret_access_key: str
    session_token: str
    expiration: datetime
    assumed_role_arn: str


class IAMEvaluationEngine:
    """
    Evaluator inti mengikuti standar resmi AWS Policy Evaluation:
    1. Mulai dengan Default Deny.
    2. Evaluasi seluruh statement: jika ada satu pun matching statement ber-efek 'Deny',
       maka hasil final adalah EXPLICIT DENY (mengabaikan Allow apa pun).
    3. Jika tidak ada Deny dan terdapat matching statement ber-efek 'Allow',
       hasil final adalah ALLOW.
    4. Jika tidak ada matching statement yang Allow, hasil final adalah DEFAULT DENY.
    """

    @staticmethod
    def evaluate(
        principal_arn: str,
        action: str,
        resource_arn: str,
        policies: List[IAMPolicy],
    ) -> (str, str):
        matched_denies = []
        matched_allows = []

        for policy in policies:
            for stmt in policy.statements:
                if (
                    stmt.matches_principal(principal_arn)
                    and stmt.matches_action(action)
                    and stmt.matches_resource(resource_arn)
                ):
                    if stmt.effect.lower() == "deny":
                        matched_denies.append(f"{policy.name} -> {stmt.sid}")
                    elif stmt.effect.lower() == "allow":
                        matched_allows.append(f"{policy.name} -> {stmt.sid}")

        if matched_denies:
            return (
                "DENY",
                f"Explicit Deny ditemukan pada statement: {', '.join(matched_denies)}",
            )
        elif matched_allows:
            return (
                "ALLOW",
                f"Explicit Allow ditemukan pada statement: {', '.join(matched_allows)}",
            )
        else:
            return (
                "DENY",
                "Default Deny (tidak ada matching statement yang memberikan Allow).",
            )


class STSClient:
    """Simulasi AWS Security Token Service (STS)"""

    def __init__(self, evaluation_engine: IAMEvaluationEngine):
        self.engine = evaluation_engine

    def assume_role(
        self,
        caller_arn: str,
        role: IAMRole,
        session_name: str,
        duration_seconds: int = 3600,
    ) -> Optional[TemporaryCredentials]:
        decision, reason = self.engine.evaluate(
            principal_arn=caller_arn,
            action="sts:AssumeRole",
            resource_arn=role.arn,
            policies=[role.assume_role_policy],
        )

        print(f"\n{Colors.CYAN}[STS:AssumeRole Request]{Colors.RESET}")
        print(f"  Caller       : {Colors.BOLD}{caller_arn}{Colors.RESET}")
        print(f"  Target Role  : {role.arn}")
        print(f"  Session Name : {session_name}")
        print(f"  Trust Policy : {role.assume_role_policy.name}")

        if decision == "ALLOW":
            print(f"  Status       : {Colors.GREEN}{Colors.BOLD}SUKSES (ALLOW){Colors.RESET}")
            print(f"  Detail       : {reason}")
            now = datetime.now(timezone.utc)
            creds = TemporaryCredentials(
                access_key_id=f"ASIA{uuid.uuid4().hex[:16].upper()}",
                secret_access_key=uuid.uuid4().hex + uuid.uuid4().hex[:8],
                session_token="AQoDYXdzEJr1///" + uuid.uuid4().hex,
                expiration=now + timedelta(seconds=duration_seconds),
                assumed_role_arn=f"{role.arn}/{session_name}",
            )
            return creds
        else:
            print(f"  Status       : {Colors.RED}{Colors.BOLD}GAGAL (ACCESS DENIED){Colors.RESET}")
            print(f"  Detail       : {reason}")
            return None


def run_scenario(
    title: str,
    principal_arn: str,
    action: str,
    resource: str,
    policies: List[IAMPolicy],
):
    print(f"\n{Colors.HEADER}=== Scenario: {title} ==={Colors.RESET}")
    print(f"Principal : {Colors.DIM}{principal_arn}{Colors.RESET}")
    print(f"Action    : {Colors.BOLD}{action}{Colors.RESET}")
    print(f"Resource  : {Colors.BOLD}{resource}{Colors.RESET}")

    decision, reason = IAMEvaluationEngine.evaluate(
        principal_arn=principal_arn,
        action=action,
        resource_arn=resource,
        policies=policies,
    )

    if decision == "ALLOW":
        badge = f"{Colors.GREEN}[✓ ALLOW]{Colors.RESET}"
    else:
        badge = f"{Colors.RED}[✗ DENY]{Colors.RESET}"

    print(f"Result    : {badge} -> {reason}")


def main():
    print(f"{Colors.BOLD}{Colors.CYAN}============================================================{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}    AWS IAM Policy Evaluation Engine & STS AssumeRole Demo   {Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}============================================================{Colors.RESET}")

    # 1. Definisikan Kebijakan
    policy_s3_read = IAMPolicy(
        name="S3ReadOnlyPolicy",
        statements=[
            PolicyStatement(
                sid="AllowS3GetList",
                effect="Allow",
                actions=["s3:GetObject", "s3:ListBucket"],
                resources=["arn:aws:s3:::prod-data/*", "arn:aws:s3:::prod-data"],
            )
        ],
    )

    policy_deny_prod_delete = IAMPolicy(
        name="GuardrailDenyDelete",
        statements=[
            PolicyStatement(
                sid="DenySensitiveDelete",
                effect="Deny",
                actions=["s3:DeleteObject*"],
                resources=["arn:aws:s3:::prod-data/*"],
            )
        ],
    )

    policy_wildcard_admin = IAMPolicy(
        name="OverlyPermissiveAdmin",
        statements=[
            PolicyStatement(
                sid="AllowAllS3",
                effect="Allow",
                actions=["s3:*"],
                resources=["*"],
            )
        ],
    )

    # User ARN
    user_arn = "arn:aws:iam::123456789012:user/developer-alex"

    # --- Skenario 1: Default Deny (Tidak ada policy yang allow) ---
    run_scenario(
        title="1. Default Deny - Akses EC2 tanpa kebijakan terkait",
        principal_arn=user_arn,
        action="ec2:DescribeInstances",
        resource="arn:aws:ec2:ap-southeast-1:123456789012:instance/*",
        policies=[policy_s3_read],
    )

    # --- Skenario 2: Explicit Allow ---
    run_scenario(
        title="2. Explicit Allow - Membaca data S3 dari bucket prod-data",
        principal_arn=user_arn,
        action="s3:GetObject",
        resource="arn:aws:s3:::prod-data/reports/q3.csv",
        policies=[policy_s3_read],
    )

    # --- Skenario 3: Explicit Deny Mengalahkan Explicit Allow ---
    run_scenario(
        title="3. Explicit Deny Trumps Allow - Hapus file di prod-data",
        principal_arn=user_arn,
        action="s3:DeleteObject",
        resource="arn:aws:s3:::prod-data/critical.db",
        policies=[policy_wildcard_admin, policy_deny_prod_delete],
    )

    # --- Skenario 4 & 5: STS AssumeRole & Trust Policy ---
    trust_policy_allow_alex = IAMPolicy(
        name="CrossAccountDataOpsTrustPolicy",
        statements=[
            PolicyStatement(
                sid="TrustSpecificUser",
                effect="Allow",
                actions=["sts:AssumeRole"],
                resources=["*"],
                principal={"AWS": "arn:aws:iam::123456789012:user/developer-alex"},
            )
        ],
    )

    ops_role = IAMRole(
        arn="arn:aws:iam::999888777666:role/DataOpsProductionRole",
        name="DataOpsProductionRole",
        assume_role_policy=trust_policy_allow_alex,
        attached_policies=[policy_s3_read],
    )

    sts = STSClient(evaluation_engine=IAMEvaluationEngine())

    # 4. AssumeRole sukses untuk Alex
    creds = sts.assume_role(
        caller_arn=user_arn,
        role=ops_role,
        session_name="alex-ops-session-01",
    )

    if creds:
        print(f"\n{Colors.YELLOW}>> Kredensial Sementara Dihasilkan:{Colors.RESET}")
        print(f"   AccessKeyId     : {creds.access_key_id}")
        print(f"   SecretAccessKey : {creds.secret_access_key[:8]}...[MASKED]")
        print(f"   SessionToken    : {creds.session_token[:20]}...")
        print(f"   Expiration      : {creds.expiration.isoformat()}")

        # Gunakan Assumed Role untuk mengakses resource
        run_scenario(
            title="4b. Evaluasi Hak Akses Assumed Role Baru",
            principal_arn=creds.assumed_role_arn,
            action="s3:GetObject",
            resource="arn:aws:s3:::prod-data/financials.xlsx",
            policies=ops_role.attached_policies,
        )

    # 5. AssumeRole ditolak untuk User yang tidak terdaftar di Trust Policy
    unauthorized_user = "arn:aws:iam::123456789012:user/intern-bob"
    sts.assume_role(
        caller_arn=unauthorized_user,
        role=ops_role,
        session_name="bob-exploit-attempt",
    )

    print(f"\n{Colors.BOLD}{Colors.GREEN}============================================================{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.GREEN}       Simulasi IAM Evaluation & STS Berhasil Selesai       {Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.GREEN}============================================================{Colors.RESET}\n")


if __name__ == "__main__":
    main()
