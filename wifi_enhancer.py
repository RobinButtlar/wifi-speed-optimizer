#!/usr/bin/env python3
"""
WiFi Speed Enhancer & Diagnostics
A lightweight utility to diagnose, benchmark, and optimize Linux Wi-Fi performance.
"""

import argparse
import random
import re
import socket
import struct
import subprocess
import sys
import time
from typing import Dict, List, Optional, Tuple


class TerminalColors:
    # Sky Blue (#82C8E5) theme & TrueColor ANSI palette
    SKY_BLUE = "\033[38;2;130;200;229m"      # #82C8E5 - Primary Sky Blue
    DEEP_SKY = "\033[38;2;75;163;199m"       # #4BA3C7 - Deep Sky Accent
    ICE_BLUE = "\033[38;2;197;232;247m"      # #C5E8F7 - Soft Ice Highlight
    SLATE_DIM = "\033[38;2;100;116;139m"     # #64748B - Muted Slate

    # Background swatches for displaying the color palette
    BG_SKY_BLUE = "\033[48;2;130;200;229m"
    BG_DEEP_SKY = "\033[48;2;75;163;199m"
    BG_ICE_BLUE = "\033[48;2;197;232;247m"
    BG_MINT = "\033[48;2;110;231;183m"
    BG_AMBER = "\033[48;2;252;211;77m"
    BG_CORAL = "\033[48;2;248;113;113m"

    # Status colors
    HEADER = SKY_BLUE
    OKBLUE = DEEP_SKY
    OKCYAN = ICE_BLUE
    OKGREEN = "\033[38;2;110;231;183m"       # #6EE7B7 - Mint Green
    WARNING = "\033[38;2;252;211;77m"        # #FCD34D - Amber Warning
    FAIL = "\033[38;2;248;113;113m"          # #F87171 - Coral Red
    ENDC = "\033[0m"
    BOLD = "\033[1m"


DNS_RESOLVERS: List[Tuple[str, str]] = [
    ("Cloudflare", "1.1.1.1"),
    ("Google", "8.8.8.8"),
    ("Quad9", "9.9.9.9"),
]

BENCHMARK_DOMAINS: List[str] = [
    "github.com",
    "cloudflare.com",
    "wikipedia.org",
]


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


def build_dns_query(domain: str) -> Tuple[int, bytes]:
    """Construct a raw UDP DNS A-record query packet (RFC 1035)."""
    tx_id = random.randint(0, 65535)
    # Flags: 0x0100 (Standard query, recursion desired), QDCOUNT=1
    header = struct.pack(">HHHHHH", tx_id, 0x0100, 1, 0, 0, 0)
    qname = b"".join(
        struct.pack("B", len(label)) + label.encode("ascii")
        for label in domain.strip(".").split(".")
    ) + b"\x00"
    # QTYPE=1 (A record), QCLASS=1 (IN)
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
        # Prefix a random label view or query distinct domains to reduce single-domain cache skew
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

    # 1. System Resolver
    sys_avg = benchmark_system_dns(target_domains)
    results.append({
        "name": "System Default",
        "ip": "OS Resolver",
        "avg_ms": sys_avg if sys_avg > 0 else None,
    })

    # 2. Direct UDP queries to public DNS resolvers
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


def print_banner():
    """Display the Sky Blue (#82C8E5) Wi-Fi ASCII logo and color palette."""
    c_sky = TerminalColors.SKY_BLUE
    c_deep = TerminalColors.DEEP_SKY
    c_ice = TerminalColors.ICE_BLUE
    c_dim = TerminalColors.SLATE_DIM
    c_bold = TerminalColors.BOLD
    rst = TerminalColors.ENDC

    logo = f"""
{c_deep}  ╭──────────────────────────────────────────────────────────────╮{rst}
{c_deep}  │{rst}                  {c_ice}       . · ´ ` · .       {rst}                   {c_deep}│{rst}
{c_deep}  │{rst}                  {c_sky}    .´  . · ´ ` · .  `.    {rst}                 {c_deep}│{rst}
{c_deep}  │{rst}                  {c_sky}   /  .´  . · · .  `.  \\   {rst}                 {c_deep}│{rst}
{c_deep}  │{rst}                  {c_deep}  '  /   /   _   \\   \\  '  {rst}                 {c_deep}│{rst}
{c_deep}  │{rst}                  {c_ice}        '   {c_sky}(●){c_ice}   '        {rst}                 {c_deep}│{rst}
{c_deep}  │{rst}                                                              {c_deep}│{rst}
{c_deep}  │{rst}           {c_bold}{c_sky}⚡ WiFi Speed Enhancer & Diagnostics ⚡{rst}            {c_deep}│{rst}
{c_deep}  │{rst}       {c_dim}Linux Wireless Audit • DNS Benchmark • Live Monitor{rst}    {c_deep}│{rst}
{c_deep}  ╰──────────────────────────────────────────────────────────────╯{rst}"""

    palette_line = (
        f"    {c_dim}Palette:{rst} "
        f"{TerminalColors.BG_SKY_BLUE}   {rst} {c_sky}#82C8E5{rst}  "
        f"{TerminalColors.BG_ICE_BLUE}   {rst} {c_ice}#C5E8F7{rst}  "
        f"{TerminalColors.BG_DEEP_SKY}   {rst} {c_deep}#4BA3C7{rst}  "
        f"{TerminalColors.BG_MINT}   {rst} {TerminalColors.OKGREEN}#6EE7B7{rst}  "
        f"{TerminalColors.BG_AMBER}   {rst} {TerminalColors.WARNING}#FCD34D{rst}  "
        f"{TerminalColors.BG_CORAL}   {rst} {TerminalColors.FAIL}#F87171{rst}"
    )

    if sys.stdout.isatty():
        print(logo)
        print(palette_line)
    else:
        print("==================================================")
        print("        WiFi Speed Enhancer & Diagnostics         ")
        print("==================================================")


def print_dns_benchmark_section(dns_results: List[Dict[str, object]]) -> Optional[Dict[str, object]]:
    """Render formatted DNS benchmark table with Sky Blue progress bars and return fastest resolver."""
    print("\n" + colored("─── DNS Resolver Benchmark ───", TerminalColors.SKY_BLUE + TerminalColors.BOLD))
    print(colored(f"  Tested domains: {', '.join(BENCHMARK_DOMAINS)}", TerminalColors.SLATE_DIM))

    valid = [r for r in dns_results if r["avg_ms"] is not None]
    fastest = min(valid, key=lambda x: float(x["avg_ms"])) if valid else None
    max_ms = max((float(r["avg_ms"]) for r in valid), default=100.0)

    for entry in dns_results:
        name = str(entry["name"])
        ip = str(entry["ip"])
        avg_ms = entry["avg_ms"]
        label = f"{name:<15} ({ip:<11})"

        if avg_ms is None:
            print(f"  {label} : {colored('UNREACHABLE / TIMEOUT', TerminalColors.FAIL)}")
            continue

        ms_val = float(avg_ms)
        bar_len = max(1, min(20, int((ms_val / max(max_ms, 1.0)) * 20)))
        bar = "█" * bar_len + "░" * (20 - bar_len)

        if fastest and entry is fastest:
            color = TerminalColors.OKGREEN
            badge = colored(" ★ FASTEST", TerminalColors.OKGREEN + TerminalColors.BOLD)
        elif ms_val < 35.0:
            color = TerminalColors.SKY_BLUE
            badge = ""
        elif ms_val < 75.0:
            color = TerminalColors.WARNING
            badge = ""
        else:
            color = TerminalColors.FAIL
            badge = ""

        print(f"  {label} : {colored(bar, color)} {colored(f'{ms_val:6.1f} ms', color)}{badge}")

    return fastest


def run_dns_benchmark_standalone():
    """Run only the DNS resolver comparison benchmark."""
    print_banner()
    dns_results = benchmark_dns_resolvers()
    fastest = print_dns_benchmark_section(dns_results)
    if fastest and fastest["name"] != "System Default":
        print(
            "\n"
            + colored(
                f"  💡 Tip: {fastest['name']} ({fastest['ip']}) responded in "
                f"{float(fastest['avg_ms']):.1f} ms — switching your DNS can speed up browsing!",
                TerminalColors.ICE_BLUE,
            )
        )


def run_audit(show_banner: bool = True):
    if show_banner:
        print_banner()
    iface = find_wifi_interface()
    if not iface:
        print("\n" + colored("[-] No active Wi-Fi interface detected.", TerminalColors.FAIL))
        print("    Ensure you are connected to a Wi-Fi network.")
    else:
        print("\n" + colored(f"[+] Active Wi-Fi Interface: {iface}", TerminalColors.OKGREEN))
        details = get_wifi_details(iface)

        print("\n" + colored("─── Link Status ───", TerminalColors.SKY_BLUE + TerminalColors.BOLD))
        print(f"  SSID (Network):   {colored(details['essid'], TerminalColors.ICE_BLUE)}")
        print(f"  Frequency:        {details['freq']}")
        print(f"  Current Bit Rate: {details['bitrate']}")
        print(f"  Signal Level:     {details['signal_level']}")
        print(f"  Link Quality:     {details['link_quality']}")
        print(f"  Power Management: {details['power_management']}")

    print("\n" + colored("─── Latency & Stability Check ───", TerminalColors.SKY_BLUE + TerminalColors.BOLD))
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

    # DNS Resolver Benchmark
    dns_results = benchmark_dns_resolvers()
    fastest_dns = print_dns_benchmark_section(dns_results)

    # Optimization Suggestions
    print("\n" + colored("─── Optimization Opportunities ───", TerminalColors.SKY_BLUE + TerminalColors.BOLD))
    recommendations = []

    if iface:
        details = get_wifi_details(iface)
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

    sys_entry = next((r for r in dns_results if r["name"] == "System Default"), None)
    sys_ms = float(sys_entry["avg_ms"]) if (sys_entry and sys_entry["avg_ms"] is not None) else 0.0
    if fastest_dns and fastest_dns["name"] != "System Default":
        fast_ms = float(fastest_dns["avg_ms"])
        if sys_ms == 0.0 or (sys_ms - fast_ms) > 10.0 or sys_ms > 40.0:
            recommendations.append(
                f"• {fastest_dns['name']} DNS ({fastest_dns['ip']}) averaged {fast_ms:.1f} ms "
                f"(vs System DNS at {sys_ms:.1f} ms).\n"
                f"  Configure {fastest_dns['ip']} in NetworkManager to speed up domain lookups."
            )

    if not recommendations:
        print(colored("  ✓ Wi-Fi connection is operating in optimal state!", TerminalColors.OKGREEN))
    else:
        for rec in recommendations:
            print(colored(rec, TerminalColors.WARNING))
    print("\n" + colored("Run with --help to see CLI flags or launch without arguments for the menu.", TerminalColors.OKBLUE))


def monitor_ping(target: str = "1.1.1.1"):
    print(colored(f"\n[+] Continuously monitoring latency to {target} (Ctrl+C to stop)...", TerminalColors.SKY_BLUE))
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


def run_interactive_menu():
    """Display an interactive Sky Blue terminal menu with active and upcoming features."""
    print_banner()
    c_sky = TerminalColors.SKY_BLUE
    c_deep = TerminalColors.DEEP_SKY
    c_ice = TerminalColors.ICE_BLUE
    c_dim = TerminalColors.SLATE_DIM
    c_warn = TerminalColors.WARNING
    c_bold = TerminalColors.BOLD
    rst = TerminalColors.ENDC

    while True:
        print(f"\n{c_deep}  ╭─────────────────── {c_bold}{c_sky}TERMINAL CONTROL MENU{rst}{c_deep} ────────────────────╮{rst}")
        print(f"{c_deep}  │{rst}  {c_sky}[1]{rst} {c_ice}Full Wi-Fi Audit & Diagnostics{rst}                          {c_deep}│{rst}")
        print(f"{c_deep}  │{rst}  {c_sky}[2]{rst} {c_ice}DNS Resolver Benchmark{rst} (1.1.1.1 / 8.8.8.8 / 9.9.9.9)    {c_deep}│{rst}")
        print(f"{c_deep}  │{rst}  {c_sky}[3]{rst} {c_ice}Live Ping & Jitter Monitor{rst}                              {c_deep}│{rst}")
        print(f"{c_deep}  ├─────────────────── {c_dim}UPCOMING / ROADMAP{c_deep} ───────────────────────┤{rst}")
        print(f"{c_deep}  │{rst}  {c_dim}[4] Modern iw / nmcli Deep Link Inspector    [Coming Soon]{rst}  {c_deep}│{rst}")
        print(f"{c_deep}  │{rst}  {c_dim}[5] Auto-Optimizer (Power Save & Channel)    [Coming Soon]{rst}  {c_deep}│{rst}")
        print(f"{c_deep}  │{rst}  {c_dim}[6] Live Signal Quality Bar & Dashboard      [Coming Soon]{rst}  {c_deep}│{rst}")
        print(f"{c_deep}  ├──────────────────────────────────────────────────────────────┤{rst}")
        print(f"{c_deep}  │{rst}  {c_sky}[0]{rst} Exit                                                    {c_deep}│{rst}")
        print(f"{c_deep}  ╰──────────────────────────────────────────────────────────────╯{rst}")

        try:
            choice = input(colored("  Select an option [0-6]: ", c_sky + c_bold)).strip()
        except (EOFError, KeyboardInterrupt):
            print("\n" + colored("  Goodbye! 👋", c_sky))
            break

        if choice == "1":
            run_audit(show_banner=False)
        elif choice == "2":
            dns_results = benchmark_dns_resolvers()
            print_dns_benchmark_section(dns_results)
        elif choice == "3":
            monitor_ping("1.1.1.1")
        elif choice in {"4", "5", "6"}:
            feature_names = {
                "4": "Modern iw / nmcli Deep Link Inspector",
                "5": "Auto-Optimizer (Power Save & Channel Tuner)",
                "6": "Live Signal Quality Bar & Dashboard",
            }
            print(
                "\n"
                + colored(
                    f"  🚧 '{feature_names[choice]}' is on the roadmap! We'll build this next.",
                    c_warn,
                )
            )
        elif choice in {"0", "q", "exit"}:
            print(colored("  Goodbye! 👋", c_sky))
            break
        else:
            print(colored("  [!] Invalid option. Please choose 0-6.", TerminalColors.FAIL))


def main():
    parser = argparse.ArgumentParser(description="WiFi Speed Enhancer & Diagnostics")
    parser.add_argument("--audit", action="store_true", help="Run full Wi-Fi audit immediately")
    parser.add_argument("--dns", action="store_true", help="Run DNS resolver benchmark (1.1.1.1, 8.8.8.8, 9.9.9.9)")
    parser.add_argument("--ping", action="store_true", help="Continuously monitor latency to detect jitter and drops")
    parser.add_argument("--menu", action="store_true", help="Launch interactive terminal menu (default in TTY)")
    parser.add_argument("--target", default="1.1.1.1", help="Target host for ping monitor (default: 1.1.1.1)")
    args = parser.parse_args()

    if args.ping:
        monitor_ping(args.target)
    elif args.dns:
        run_dns_benchmark_standalone()
    elif args.audit:
        run_audit()
    elif args.menu or sys.stdout.isatty():
        run_interactive_menu()
    else:
        run_audit()


if __name__ == "__main__":
    main()
