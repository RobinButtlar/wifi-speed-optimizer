"""
Diagnostics & Benchmarking Engine
Read-only system checks for Wi-Fi link status, ping/jitter, and raw UDP DNS latency.
"""

import random
import re
import socket
import struct
import subprocess
import time
from typing import Dict, List, Optional, Tuple

DNS_RESOLVERS: List[Tuple[str, str]] = [
    ("Cloudflare", "1.1.1.1"),
    ("Google", "8.8.8.8"),
    ("Quad9", "9.9.9.9"),
    ("OpenDNS", "208.67.222.222")
]

BENCHMARK_DOMAINS: List[str] = [
    "github.com",
    "cloudflare.com",
    "wikipedia.org",
    "youtube.com",
    "amazon.de"
]


def run_cmd(cmd: str, timeout: int = 10) -> Tuple[int, str]:
    """Execute a system shell command and return (exit_code, trimmed_output)."""
    try:
        res = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = res.stdout.strip() or res.stderr.strip()
        return res.returncode, out
    except Exception as e:
        return 1, str(e)


def find_wifi_interface() -> Optional[str]:
    """Detect active wireless interface name (e.g., wlan0, wlp3s0)."""
    code, out = run_cmd("nmcli -t -f DEVICE,TYPE,STATE dev")
    if code == 0:
        for line in out.splitlines():
            parts = line.split(":")
            if len(parts) >= 3 and parts[1] == "wifi" and parts[2] == "connected":
                return parts[0]

    code, out = run_cmd("iwconfig 2>/dev/null")
    if code == 0:
        for line in out.splitlines():
            if "IEEE 802.11" in line:
                return line.split()[0]
    return None


def get_active_connection_name(interface: str) -> Optional[str]:
    """Return the active NetworkManager connection profile name for the interface."""
    code, out = run_cmd("nmcli -t -f NAME,DEVICE,STATE connection show --active")
    if code == 0:
        for line in out.splitlines():
            parts = line.split(":")
            if len(parts) >= 3 and parts[1] == interface and parts[2] == "activated":
                return parts[0]
    return None


def get_wifi_details(interface: str) -> Dict[str, str]:
    """Extract Wi-Fi metrics from iwconfig and iw."""
    details = {
        "interface": interface,
        "essid": "Unknown",
        "freq": "Unknown",
        "bitrate": "Unknown",
        "power_management": "Unknown",
        "link_quality": "Unknown",
        "signal_level": "Unknown",
    }
    code, out = run_cmd(f"iwconfig {interface} 2>/dev/null")
    if code == 0:
        essid_m = re.search(r'ESSID:"([^"]+)"', out)
        if essid_m:
            details["essid"] = essid_m.group(1)

        freq_m = re.search(r"Frequency:([0-9.]+\s*GHz)", out)
        if freq_m:
            details["freq"] = freq_m.group(1)

        rate_m = re.search(r"Bit Rate[=:]([0-9.]+\s*[MG]b/s)", out)
        if rate_m:
            details["bitrate"] = rate_m.group(1)

        pwr_m = re.search(r"Power Management:(\w+)", out)
        if pwr_m:
            details["power_management"] = pwr_m.group(1)

        qual_m = re.search(r"Link Quality=([0-9/]+)", out)
        if qual_m:
            details["link_quality"] = qual_m.group(1)

        sig_m = re.search(r"Signal level=([-\w\s]+dBm)", out)
        if sig_m:
            details["signal_level"] = sig_m.group(1)

    # Fallback to 'iw' for power save check if iwconfig didn't report it
    if details["power_management"] == "Unknown":
        code, pwr_out = run_cmd(f"iw dev {interface} get power_save 2>/dev/null")
        if code == 0 and "Power save:" in pwr_out:
            details["power_management"] = pwr_out.split("Power save:")[-1].strip()

    return details


def get_default_gateway() -> Optional[str]:
    """Retrieve default IP gateway."""
    code, out = run_cmd("ip route show default")
    if code == 0 and out:
        parts = out.split()
        if "via" in parts:
            idx = parts.index("via")
            if idx + 1 < len(parts):
                return parts[idx + 1]
    return None


def measure_ping(target: str, count: int = 4) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Measure min, avg, max latency (ms) to a target."""
    code, out = run_cmd(f"ping -c {count} -W 2 {target}")
    if code != 0:
        return None, None, None
    m = re.search(r"rtt min/avg/max/mdev = ([0-9.]+)/([0-9.]+)/([0-9.]+)/([0-9.]+)", out)
    if m:
        return float(m.group(1)), float(m.group(2)), float(m.group(3))
    return None, None, None


def get_tcp_congestion_control() -> str:
    """Check current Linux TCP congestion control algorithm (e.g. cubic or bbr)."""
    code, out = run_cmd("sysctl -n net.ipv4.tcp_congestion_control 2>/dev/null")
    return out if code == 0 and out else "unknown"


def build_dns_query(domain: str) -> Tuple[int, bytes]:
    """Construct a raw UDP DNS A-record query packet (RFC 1035)."""
    tx_id = random.randint(0, 65535)
    header = struct.pack(">HHHHHH", tx_id, 0x0100, 1, 0, 0, 0)
    qname = b"".join(
        struct.pack("B", len(label)) + label.encode("ascii")
        for label in domain.strip(".").split(".")
    ) + b"\x00"
    question = qname + struct.pack(">HH", 1, 1)
    return tx_id, header + question


def query_dns_server(server_ip: str, domain: str, timeout: float = 2.0) -> Optional[float]:
    """Send a UDP DNS query directly to a specific resolver and return latency in ms."""
    tx_id, packet = build_dns_query(domain)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        start = time.perf_counter()
        sock.sendto(packet, (server_ip, 53))
        data, _ = sock.recvfrom(512)
        elapsed = (time.perf_counter() - start) * 1000.0
        if len(data) >= 2:
            resp_id = struct.unpack(">H", data[:2])[0]
            if resp_id == tx_id:
                return elapsed
        return None
    except Exception:
        return None
    finally:
        sock.close()


def benchmark_system_dns(domains: Optional[List[str]] = None) -> float:
    """Benchmark system stub resolver across distinct domains in milliseconds."""
    target_domains = domains or BENCHMARK_DOMAINS
    durations: List[float] = []
    for domain in target_domains:
        start = time.perf_counter()
        try:
            socket.getaddrinfo(domain, 80)
            elapsed = (time.perf_counter() - start) * 1000.0
            durations.append(elapsed)
        except Exception:
            pass
        time.sleep(0.03)
    return sum(durations) / len(durations) if durations else 0.0


def benchmark_dns_resolvers(domains: Optional[List[str]] = None) -> List[Dict[str, object]]:
    """
    Compare current System DNS resolver against Cloudflare (1.1.1.1),
    Google (8.8.8.8), and Quad9 (9.9.9.9).
    """
    target_domains = domains or BENCHMARK_DOMAINS
    results: List[Dict[str, object]] = []

    sys_avg = benchmark_system_dns(target_domains)
    results.append({
        "name": "System Default",
        "ip": "OS Resolver",
        "avg_ms": sys_avg if sys_avg > 0 else None,
    })

    for name, ip in DNS_RESOLVERS:
        samples: List[float] = []
        for domain in target_domains:
            ms = query_dns_server(ip, domain)
            if ms is not None:
                samples.append(ms)
            time.sleep(0.03)
        avg_ms = (sum(samples) / len(samples)) if samples else None
        results.append({
            "name": name,
            "ip": ip,
            "avg_ms": avg_ms,
        })

    return results
