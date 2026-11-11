"""
Wi-Fi Enhancing Features Engine
Active optimizations for Linux wireless interfaces:
  1. Disable Wi-Fi Power Save (eliminates wake-up latency spikes)
  2. Apply Fastest DNS Resolver via NetworkManager + flush DNS cache
  3. Enable TCP BBR Congestion Control (improves throughput over Wi-Fi)
  4. Scan & Recommend 5 GHz / Less-Congested Channels
"""

from typing import Dict, List, Optional, Tuple
from diagnostics import (
    benchmark_dns_resolvers,
    find_wifi_interface,
    get_active_connection_name,
    get_tcp_congestion_control,
    get_wifi_details,
    run_cmd,
)


def disable_wifi_power_save(interface: str) -> Tuple[bool, str]:
    """
    Disable Wi-Fi power management on the given interface using iw or iwconfig.
    Requires sudo privileges if not already root.
    """
    code, out = run_cmd(f"sudo -n iw dev {interface} set power_save off 2>/dev/null")
    if code == 0:
        return True, f"Disabled Wi-Fi power saving on {interface} via 'iw'."

    # Try interactive sudo or iwconfig fallback
    code, out = run_cmd(f"sudo iw dev {interface} set power_save off", timeout=30)
    if code == 0:
        return True, f"Disabled Wi-Fi power saving on {interface} via 'iw'."

    code, out = run_cmd(f"sudo iwconfig {interface} power off", timeout=30)
    if code == 0:
        return True, f"Disabled Wi-Fi power saving on {interface} via 'iwconfig'."

    return False, f"Failed to disable power save on {interface}: {out}"


def apply_dns_resolver(interface: str, dns_ip: str, provider_name: str = "") -> Tuple[bool, str]:
    """
    Configure the active NetworkManager connection to use the specified DNS IP
    and flush the local systemd-resolved cache.
    """
    conn_name = get_active_connection_name(interface)
    if not conn_name:
        return False, f"Could not find an active NetworkManager profile for {interface}."

    cmd = (
        f'nmcli connection modify "{conn_name}" '
        f'ipv4.dns "{dns_ip}" ipv4.ignore-auto-dns yes && '
        f'nmcli device reapply "{interface}"'
    )
    code, out = run_cmd(cmd, timeout=20)
    if code != 0:
        # Try with sudo if unprivileged policy blocked it
        code, out = run_cmd(f"sudo sh -c '{cmd}'", timeout=30)
        if code != 0:
            return False, f"Failed to update DNS for '{conn_name}': {out}"

    # Flush local DNS cache if resolvectl is present
    run_cmd("resolvectl flush-caches 2>/dev/null")
    label = f"{provider_name} ({dns_ip})" if provider_name else dns_ip
    return True, f"Applied {label} to '{conn_name}' and flushed DNS cache."


def enable_tcp_bbr() -> Tuple[bool, str]:
    """
    Enable Google's TCP BBR congestion control algorithm for faster throughput
    and lower queuing delay over wireless links.
    """
    current = get_tcp_congestion_control()
    if current.lower() == "bbr":
        return True, "TCP BBR congestion control is already active."

    cmd = (
        "sudo modprobe tcp_bbr 2>/dev/null; "
        "sudo sysctl -w net.core.default_qdisc=fq >/dev/null && "
        "sudo sysctl -w net.ipv4.tcp_congestion_control=bbr >/dev/null"
    )
    code, out = run_cmd(cmd, timeout=30)
    if code == 0 and get_tcp_congestion_control().lower() == "bbr":
        return True, f"Switched TCP congestion control from '{current}' to 'bbr'."
    return False, f"Could not enable TCP BBR (current: {current}). {out}"


def scan_nearby_channels(ssid_filter: Optional[str] = None) -> List[Dict[str, str]]:
    """
    Scan visible Wi-Fi access points via nmcli to identify 5 GHz bands
    or less congested channels.
    """
    code, out = run_cmd("nmcli -t -f IN-USE,SSID,CHAN,FREQ,RATE,SIGNAL dev wifi list --rescan auto", timeout=15)
    access_points: List[Dict[str, str]] = []
    if code != 0:
        return access_points

    for line in out.splitlines():
        parts = line.split(":")
        if len(parts) >= 6:
            in_use, ssid, chan, freq, rate, signal = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]
            if ssid_filter and ssid != ssid_filter:
                continue
            access_points.append({
                "in_use": "*" in in_use,
                "ssid": ssid or "<Hidden>",
                "channel": chan,
                "freq": freq,
                "rate": rate,
                "signal": signal,
            })

    return access_points


def find_fastest_public_dns() -> Optional[Dict[str, object]]:
    """Run DNS benchmark and return the fastest public resolver entry."""
    results = benchmark_dns_resolvers()
    public_valid = [
        r for r in results
        if r["name"] != "System Default" and r["avg_ms"] is not None
    ]
    if not public_valid:
        return None
    return min(public_valid, key=lambda x: float(x["avg_ms"]))


def run_all_enhancements() -> List[Tuple[str, bool, str]]:
    """
    Execute all safe automated Wi-Fi enhancements and return a list of
    (step_name, success, message) tuples.
    """
    summary: List[Tuple[str, bool, str]] = []
    iface = find_wifi_interface()

    # 1. Power Save Optimization
    if iface:
        details = get_wifi_details(iface)
        if details["power_management"].lower() == "off":
            summary.append(("Wi-Fi Power Save", True, f"Already OFF on {iface} (optimal)."))
        else:
            ok, msg = disable_wifi_power_save(iface)
            summary.append(("Wi-Fi Power Save", ok, msg))
    else:
        summary.append(("Wi-Fi Power Save", False, "No active Wi-Fi interface detected."))

    # 2. Fastest DNS Resolver
    fastest = find_fastest_public_dns()
    if iface and fastest:
        ok, msg = apply_dns_resolver(
            iface,
            str(fastest["ip"]),
            f"{fastest['name']} [{float(fastest['avg_ms']):.1f} ms]",
        )
        summary.append(("Fastest DNS Resolver", ok, msg))
    elif not iface:
        summary.append(("Fastest DNS Resolver", False, "Skipped (no active Wi-Fi interface)."))
    else:
        summary.append(("Fastest DNS Resolver", False, "Could not benchmark public DNS resolvers."))

    # 3. TCP BBR Congestion Control
    ok, msg = enable_tcp_bbr()
    summary.append(("TCP BBR Acceleration", ok, msg))

    return summary
