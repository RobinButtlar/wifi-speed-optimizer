#!/usr/bin/env python3
"""
WiFi Speed Enhancer & Diagnostics
A lightweight utility to diagnose, benchmark, and optimize Linux Wi-Fi performance.
"""

import argparse
import re
import shutil
import socket
import subprocess
import sys
import time
from typing import Dict, Optional, Tuple


class TerminalColors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"


def colored(text: str, color: str) -> str:
    """Format text with ANSI escape codes if output is a terminal."""
    if sys.stdout.isatty():
        return f"{color}{text}{TerminalColors.ENDC}"
    return text


def run_cmd(cmd: str) -> Tuple[int, str]:
    """Execute a system shell command and return status code and trimmed output."""
    try:
        res = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return res.returncode, res.stdout.strip()
    except Exception as e:
        return 1, str(e)


def find_wifi_interface() -> Optional[str]:
    """Detect active wireless interface name."""
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


def get_wifi_details(interface: str) -> Dict[str, str]:
    """Extract Wi-Fi metrics from iwconfig."""
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


def benchmark_dns(domain: str = "google.com", trials: int = 3) -> float:
    """Benchmark local DNS resolution time in milliseconds."""
    durations = []
    for _ in range(trials):
        start = time.perf_counter()
        try:
            socket.getaddrinfo(domain, 80)
            elapsed = (time.perf_counter() - start) * 1000.0
            durations.append(elapsed)
        except Exception:
            pass
        time.sleep(0.05)
    return sum(durations) / len(durations) if durations else 0.0


def print_banner():
    banner = """
==================================================
        ⚡ WiFi Speed Enhancer & Diagnostics ⚡
==================================================
    """
    print(colored(banner, TerminalColors.HEADER))


def run_audit():
    print_banner()
    iface = find_wifi_interface()
    if not iface:
        print(colored("[-] No active Wi-Fi interface detected.", TerminalColors.FAIL))
        print("    Ensure you are connected to a Wi-Fi network.")
        return

    print(colored(f"[+] Active Wi-Fi Interface: {iface}", TerminalColors.OKGREEN))
    details = get_wifi_details(iface)

    print("\n" + colored("--- Link Status ---", TerminalColors.BOLD))
    print(f"  SSID (Network):   {details['essid']}")
    print(f"  Frequency:        {details['freq']}")
    print(f"  Current Bit Rate: {details['bitrate']}")
    print(f"  Signal Level:     {details['signal_level']}")
    print(f"  Link Quality:     {details['link_quality']}")
    print(f"  Power Management: {details['power_management']}")

    print("\n" + colored("--- Latency & Stability Check ---", TerminalColors.BOLD))
    gw = get_default_gateway()
    if gw:
        gw_min, gw_avg, gw_max = measure_ping(gw, count=4)
        if gw_avg is not None:
            gw_jitter = gw_max - gw_min if (gw_max and gw_min) else 0.0
            print(f"  Router Gateway ({gw}): avg={gw_avg:.1f}ms, jitter={gw_jitter:.1f}ms")
        else:
            print(f"  Router Gateway ({gw}): ping failed or blocked")

    ext_min, ext_avg, ext_max = measure_ping("1.1.1.1", count=4)
    if ext_avg is not None:
        print(f"  Internet (1.1.1.1):    avg={ext_avg:.1f}ms (min={ext_min:.1f}ms, max={ext_max:.1f}ms)")
    else:
        print("  Internet (1.1.1.1):    ping failed")

    print("\n" + colored("--- DNS Resolution Speed ---", TerminalColors.BOLD))
    dns_time = benchmark_dns("github.com")
    print(f"  Lookup time (github.com): {dns_time:.1f} ms")

    # Optimization Suggestions
    print("\n" + colored("--- Optimization Opportunities ---", TerminalColors.OKCYAN))
    recommendations = []

    if details["power_management"].lower() == "on":
        recommendations.append(
            f"• Wi-Fi Power Management is ON for {iface}.\n"
            f"  On Linux, Wi-Fi power saving often causes latency spikes and packet delays.\n"
            f"  To disable it: sudo iwconfig {iface} power off"
        )

    if "2.4" in details["freq"]:
        recommendations.append(
            "• You are connected to a 2.4 GHz band.\n"
            "  If your router supports 5 GHz or 6 GHz, switching will significantly improve speed and reduce interference."
        )

    if dns_time > 40.0:
        recommendations.append(
            f"• DNS lookup took {dns_time:.1f} ms. Using fast DNS like 1.1.1.1 or 8.8.8.8 can speed up browsing."
        )

    if not recommendations:
        print(colored("  ✓ Wi-Fi connection is operating in optimal state!", TerminalColors.OKGREEN))
    else:
        for rec in recommendations:
            print(colored(rec, TerminalColors.WARNING))
    print("\n" + colored("Run with --help to see more options.", TerminalColors.OKBLUE))


def monitor_ping(target: str = "1.1.1.1"):
    print(colored(f"[+] Continuously monitoring latency to {target} (Ctrl+C to stop)...", TerminalColors.OKCYAN))
    try:
        while True:
            _, avg, _ = measure_ping(target, count=1)
            ts = time.strftime("%H:%M:%S")
            if avg is not None:
                color = TerminalColors.OKGREEN if avg < 30 else (TerminalColors.WARNING if avg < 80 else TerminalColors.FAIL)
                print(f"[{ts}] {target}: {colored(f'{avg:.1f} ms', color)}")
            else:
                print(f"[{ts}] {target}: {colored('TIMEOUT / LOSS', TerminalColors.FAIL)}")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopped.")


def main():
    parser = argparse.ArgumentParser(description="WiFi Speed Enhancer & Diagnostics")
    parser.add_argument("--audit", action="store_true", help="Run full Wi-Fi audit (default)")
    parser.add_argument("--ping", action="store_true", help="Continuously monitor latency to detect jitter and drops")
    parser.add_argument("--target", default="1.1.1.1", help="Target host for ping monitor (default: 1.1.1.1)")
    args = parser.parse_args()

    if args.ping:
        monitor_ping(args.target)
    else:
        run_audit()


if __name__ == "__main__":
    main()
