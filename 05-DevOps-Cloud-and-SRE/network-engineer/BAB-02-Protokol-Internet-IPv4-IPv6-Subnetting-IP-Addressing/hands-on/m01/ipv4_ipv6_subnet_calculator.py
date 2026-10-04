#!/usr/bin/env python3
"""
IPv4/IPv6 Advanced Subnet & VLSM Engine with NAT Conntrack Simulation
Kurikulum Standar GEMINI.md - Network Engineering (DevOps/Cloud/SRE)
"""

import ipaddress
import sys
from typing import List, Dict, Tuple


class SubnetEngine:
    @staticmethod
    def calculate_ipv4_details(cidr_str: str) -> Dict[str, str]:
        """Menghitung detail matematis subnetting IPv4."""
        try:
            net = ipaddress.IPv4Network(cidr_str, strict=False)
        except ValueError as err:
            return {"error": str(err)}

        net_mask_int = int(net.netmask)
        wildcard_int = net_mask_int ^ 0xFFFFFFFF
        wildcard_ip = str(ipaddress.IPv4Address(wildcard_int))

        total_hosts = net.num_addresses
        usable_hosts = total_hosts - 2 if net.prefixlen < 31 else (2 if net.prefixlen == 31 else 1)

        first_usable = str(net.network_address + 1) if net.prefixlen < 31 else str(net.network_address)
        last_usable = str(net.broadcast_address - 1) if net.prefixlen < 31 else str(net.broadcast_address)

        return {
            "Input CIDR": str(cidr_str),
            "Network Address": str(net.network_address),
            "Subnet Mask": str(net.netmask),
            "Wildcard Mask": wildcard_ip,
            "Binary Subnet Mask": bin(net_mask_int)[2:].zfill(32),
            "Prefix Length": f"/{net.prefixlen}",
            "Total IP Addresses": str(total_hosts),
            "Usable Host Count": str(usable_hosts),
            "Usable Host Range": f"{first_usable} - {last_usable}",
            "Broadcast Address": str(net.broadcast_address) if net.prefixlen < 31 else "N/A (Point-to-Point)",
            "Scope": "Private (RFC 1918)" if net.is_private else ("CGNAT (RFC 6598)" if net.is_shared else "Public Global")
        }

    @staticmethod
    def calculate_vlsm(base_cidr: str, host_requirements: List[Tuple[str, int]]) -> List[Dict[str, str]]:
        """
        Menghitung segmentasi Variable Length Subnet Masking (VLSM).
        host_requirements: list of tuple ('Nama Segmen', jumlah_host)
        """
        try:
            base_net = ipaddress.IPv4Network(base_cidr, strict=True)
        except ValueError as err:
            raise ValueError(f"Base CIDR Invalid: {err}")

        # Urutkan kebutuhan dari yang terbesar ke terkecil
        sorted_reqs = sorted(host_requirements, key=lambda x: x[1], reverse=True)
        current_ip = int(base_net.network_address)
        max_ip = int(base_net.broadcast_address)

        allocations = []

        for name, req_hosts in sorted_reqs:
            # Butuh IP + 2 (Network & Broadcast), kecuali kebutuhan 1 atau 2 (RFC 3021 /31)
            needed_ips = req_hosts + 2
            prefix = 32 - (needed_ips - 1).bit_length()
            if prefix > 30 and req_hosts <= 2:
                prefix = 31 if req_hosts == 2 else 32

            sub_size = 2 ** (32 - prefix)

            # Validasi alignment alamat jaringan
            if current_ip % sub_size != 0:
                current_ip += sub_size - (current_ip % sub_size)

            if current_ip + sub_size - 1 > max_ip:
                allocations.append({
                    "Segment": name,
                    "Requested Hosts": str(req_hosts),
                    "Status": "FAILED: Insufficient address space in base network"
                })
                continue

            subnet = ipaddress.IPv4Network((current_ip, prefix))
            usable_count = subnet.num_addresses - 2 if subnet.prefixlen < 31 else subnet.num_addresses
            first_host = subnet.network_address + 1 if subnet.prefixlen < 31 else subnet.network_address
            last_host = subnet.broadcast_address - 1 if subnet.prefixlen < 31 else subnet.broadcast_address

            allocations.append({
                "Segment": name,
                "Requested Hosts": str(req_hosts),
                "Allocated CIDR": str(subnet),
                "Subnet Mask": str(subnet.netmask),
                "Usable Range": f"{first_host} - {last_host}",
                "Usable Hosts": str(usable_count),
                "Wasted IP": str(usable_count - req_hosts)
            })

            current_ip += sub_size

        return allocations

    @staticmethod
    def calculate_ipv6_details(ipv6_addr_str: str) -> Dict[str, str]:
        """Menganalisis alamat dan ekspansi heksadesimal IPv6."""
        try:
            v6 = ipaddress.IPv6Network(ipv6_addr_str, strict=False)
            addr = ipaddress.IPv6Address(v6.network_address)
        except ValueError as err:
            return {"error": str(err)}

        return {
            "Original Format": ipv6_addr_str,
            "Compressed Address": addr.compressed,
            "Expanded Address": addr.exploded,
            "Prefix Length": f"/{v6.prefixlen}",
            "Total /64 Subnets Possible": str(2 ** (64 - v6.prefixlen)) if v6.prefixlen <= 64 else "Sub-/64 slice",
            "Address Type": (
                "Link-Local (fe80::/10)" if addr.is_link_local else
                ("Unique Local / ULA (fc00::/7)" if addr.is_private else
                 ("Global Unicast (2000::/3)" if addr.is_global else
                  ("Multicast (ff00::/8)" if addr.is_multicast