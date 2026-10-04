#!/usr/bin/env python3
"""
AWS Transit Gateway & Centralized Inspection Routing Engine Simulator.
Simulates L3 packet routing, TGW route table evaluation (associations/propagations),
stateless NACLs, and Appliance Mode inspection symmetry.

Standard Python library only (No external dependencies required).
"""

import ipaddress
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class Action(Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"


class TrafficDirection(Enum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


@dataclass
class Packet:
    src_ip: str
    dst_ip: str
    protocol: str  # TCP, UDP, ICMP
    src_port: int
    dst_port: int
    origin_az: str
    current_az: str
    flags: List[str] = field(default_factory=list)  # SYN, ACK, etc.
    payload: str = "payload-data"


@dataclass
class NACLRule:
    rule_number: int
    protocol: str
    action: Action
    cidr: str
    port_range: Tuple[int, int]
    direction: TrafficDirection

    def matches(self, packet: Packet, direction: TrafficDirection) -> bool:
        if self.direction != direction:
            return False
        if self.protocol.upper() != "ALL" and self.protocol.upper() != packet.protocol.upper():
            return False

        pkt_network = ipaddress.ip_network(self.cidr)
        target_ip = ipaddress.ip_address(packet.dst_ip if direction == TrafficDirection.OUTBOUND else packet.src_ip)
        if target_ip not in pkt_network:
            return False

        check_port = packet.dst_port if direction == TrafficDirection.OUTBOUND else packet.dst_port
        if not (self.port_range[0] <= check_port <= self.port_range[1]):
            return False

        return True


class NetworkACL:
    def __init__(self, name: str):
        self.name = name
        self.rules: List[NACLRule] = []

    def add_rule(self, rule: NACLRule):
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.rule_number)

    def evaluate(self, packet: Packet, direction: TrafficDirection) -> Tuple[Action, Optional[int]]:
        for rule in self.rules:
            if rule.matches(packet, direction):
                return rule.action, rule.rule_number
        # Default deny if no rules matched
        return Action.DENY, 9999


@dataclass
class Route:
    destination_cidr: str
    target_attachment_id: str


class RouteTable:
    def __init__(self, name: str):
        self.name = name
        self.routes: List[Route] = []

    def add_route(self, cidr: str, target_attachment_id: str):
        self.routes.append(Route(cidr, target_attachment_id))
        # Sort routes by most specific prefix length first (Longest Prefix Match)
        self.routes.sort(key=lambda r: ipaddress.ip_network(r.destination_cidr).prefixlen, reverse=True)

    def lookup(self, dst_ip: str) -> Optional[str]:
        dest_addr = ipaddress.ip_address(dst_ip)
        for route in self.routes:
            if dest_addr in ipaddress.ip_network(route.destination_cidr):
                return route.target_attachment_id
        return None


class TransitGatewayAttachment:
    def __init__(self, attachment_id: str, vpc_name: str, app_mode: bool = False):
        self.attachment_id = attachment_id
        self.vpc_name = vpc_name
        self.appliance_mode = app_mode
        self.associated_route_table: Optional[str] = None
        self.propagated_route_tables: List[str] = []


class TransitGatewaySimulator:
    def __init__(self):
        self.attachments: Dict[str, TransitGatewayAttachment] = {}
        self.route_tables: Dict[str, RouteTable] = {}
        self.sessions: Dict[str, str] = {}  # Flow affinity tracking for appliance mode

    def register_attachment(self, attachment: TransitGatewayAttachment):
        self.attachments[attachment.attachment_id] = attachment
        logging.info(f"Registered TGW Attachment: {attachment.attachment_id} ({attachment.vpc_name})")

    def create_route_table(self, name: str) -> RouteTable:
        rt = RouteTable(name)
        self.route_tables[name] = rt
        logging.info(f"Created TGW Route Table: {name}")
        return rt

    def associate(self, attachment_id: str, rt_name: str):
        if attachment_id in self.attachments and rt_name in self.route_tables:
            self.attachments[attachment_id].associated_route_table = rt_name
            logging.info(f"Associated Attachment {attachment_id} -> TGW RT: {rt_name}")

    def propagate(self, attachment_id: str, rt_name: str, cidr: str):
        if rt_name in self.route_tables and attachment_id in self.attachments:
            self.attachments[attachment_id].propagated_route_tables.append(rt_name)
            self.route_tables[rt_name].add_route(cidr, attachment_id)
            logging.info(f"Propagated CIDR {cidr} from {attachment_id} into TGW RT: {rt_name}")

    def route_packet(self, ingress_attachment_id: str, packet: Packet) -> Tuple[bool, str]:
        att = self.attachments.get(ingress_attachment_id)
        if not att:
            return False, f"Attachment {ingress_attachment_id} not found."

        rt_name = att.associated_route_table
        if not rt_name or rt_name not in self.route_tables:
            return False, f"Attachment {ingress_attachment_id} has no valid Route Table association."

        rt = self.route_tables[rt_name]
        target_att_id = rt.lookup(packet.dst_ip)
        if not target_att_id:
            return False, f"Blackhole: No route in {rt.name} matching destination {packet.dst_ip}."

        target_att = self.attachments[target_att_id]

        # Handling Appliance Mode AZ Affinity
        flow_key = f"{packet.src_ip}:{packet.src_port}->{packet.dst_ip}:{packet.dst_port}"
        reverse_flow_key = f"{packet.dst_ip}:{packet.dst_port}->{packet.src_ip}:{packet.src_port}"

        if target_att.appliance_mode:
            if reverse_flow_key in self.sessions:
                # Return flow: enforce same AZ as initial flow
                chosen_az = self.sessions[reverse_flow_key]
                logging.info(f"[Appliance Mode] Enforcing session sticky AZ {chosen_az} for return flow {flow_key}")
                packet.current_az = chosen_az
            else:
                # Initial flow: stick to packet origin AZ
                self.sessions[flow_key] = packet.origin_az
                packet.current_az = packet.origin_az
                logging.info(f"[Appliance Mode] Session created for {flow_key} bound to AZ {packet.origin_az}")
        else:
            # Without appliance mode, random or ingress-AZ drift can occur across AZs
            packet.current_az = packet.origin_az

        return True, f"Routed successfully from {att.vpc_name} -> {target_att.vpc_name} via TGW RT [{rt.name}] on AZ [{packet.current_az}]"


def run_enterprise_simulation():
    print("=" * 80)
    print(" AWS ENTERPRISE TRANSIT GATEWAY & CENTRALIZED ROUTING SIMULATOR")
    print("=" * 80)

    sim = TransitGatewaySimulator()

    # 1. Attachments
    att_prod = TransitGatewayAttachment("tgw-att-prod", "VPC-Production-Workload", app_mode=False)
    att_dev = TransitGatewayAttachment("tgw-att-dev", "VPC-Development-Workload", app_mode=False)
    att_sec = TransitGatewayAttachment("tgw-att-sec", "VPC-Central-Inspection", app_mode=True)

    sim.register_attachment(att_prod)
    sim.register_attachment(att_dev)
    sim.register_attachment(att_sec)

    # 2. TGW Route Tables
    rt_spoke = sim.create_route_table("TGW-Spoke-Workloads-RT")
    rt_sec = sim.create_route_table("TGW-Inspection-RT")

    # 3. Associations
    sim.associate("tgw-att-prod", "TGW-Spoke-Workloads-RT")
    sim.associate("tgw-att-dev", "TGW-Spoke-Workloads-RT")
    sim.associate("tgw-att-sec", "TGW-Inspection-RT")

    # 4. Routing Setup
    # All spoke traffic sends 0.0.0.0/0 to Central Inspection VPC
    rt_spoke.add_route("0.0.0.0/0", "tgw-att-sec")

    # Inspection RT learns Spoke networks via propagations
    sim.propagate("tgw-att-prod", "TGW-Inspection-RT", "10.10.0.0/16")
    sim.propagate("tgw-att-dev", "TGW-Inspection-RT", "10.20.0.0/16")

    # 5. Stateless NACL Setup on Production Subnet