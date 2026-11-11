"""
Terminal Front End (UI)
Sky Blue (#82C8E5) TrueColor palette, Wi-Fi ASCII logo, formatted tables,
and interactive menus for diagnostics and active Wi-Fi enhancement.
"""

import sys
import time
from typing import Dict, List, Optional

from diagnostics import (
    BENCHMARK_DOMAINS,
    benchmark_dns_resolvers,
    find_wifi_interface,
    get_default_gateway,
    get_tcp_congestion_control,
    get_wifi_details,
    measure_ping,
)
from enhancer import (
    apply_dns_resolver,
    disable_wifi_power_save,
    enable_tcp_bbr,
    find_fastest_public_dns,
    run_all_enhancements,
    scan_nearby_channels,
)


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


def colored(text: str, color: str) -> str:
    """Format text with ANSI escape codes if output is a terminal."""
    if sys.stdout.isatty():
        return f"{color}{text}{TerminalColors.ENDC}"
    return text


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
{c_deep}  │{rst}       {c_dim}Linux Wireless Audit • DNS Benchmark • Optimizer{rst}       {c_deep}│{rst}
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
                f"{float(fastest['avg_ms']):.1f} ms — use Option [4] or --optimize to apply it!",
                TerminalColors.ICE_BLUE,
            )
        )


def run_audit(show_banner: bool = True):
    """Display full diagnostic audit report."""
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
        print(f"  TCP Congestion:   {get_tcp_congestion_control()}")

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

    dns_results = benchmark_dns_resolvers()
    fastest_dns = print_dns_benchmark_section(dns_results)

    print("\n" + colored("─── Optimization Opportunities ───", TerminalColors.SKY_BLUE + TerminalColors.BOLD))
    recommendations = []

    if iface:
        details = get_wifi_details(iface)
        if details["power_management"].lower() == "on":
            recommendations.append(
                f"• Wi-Fi Power Management is ON for {iface} (causes ping spikes).\n"
                f"  Fix automatically via Menu [4] Auto-Optimizer or: sudo iw dev {iface} set power_save off"
            )

        if "2.4" in details["freq"]:
            recommendations.append(
                "• You are connected to a 2.4 GHz band.\n"
                "  Switch to 5 GHz or 6 GHz for higher speed and less interference."
            )

    if get_tcp_congestion_control().lower() != "bbr":
        recommendations.append(
            "• TCP BBR Congestion Control is not enabled.\n"
            "  Enable it via Menu [4] Auto-Optimizer for better Wi-Fi throughput."
        )

    sys_entry = next((r for r in dns_results if r["name"] == "System Default"), None)
    sys_ms = float(sys_entry["avg_ms"]) if (sys_entry and sys_entry["avg_ms"] is not None) else 0.0
    if fastest_dns and fastest_dns["name"] != "System Default":
        fast_ms = float(fastest_dns["avg_ms"])
        if sys_ms == 0.0 or (sys_ms - fast_ms) > 10.0 or sys_ms > 40.0:
            recommendations.append(
                f"• {fastest_dns['name']} DNS ({fastest_dns['ip']}) averaged {fast_ms:.1f} ms "
                f"(vs System DNS at {sys_ms:.1f} ms).\n"
                f"  Apply it via Menu [4] Auto-Optimizer."
            )

    if not recommendations:
        print(colored("  ✓ Wi-Fi connection is operating in optimal state!", TerminalColors.OKGREEN))
    else:
        for rec in recommendations:
            print(colored(rec, TerminalColors.WARNING))


def monitor_ping(target: str = "1.1.1.1"):
    """Continuously stream latency readings to the terminal."""
    print(colored(f"\n[+] Continuously monitoring latency to {target} (Ctrl+C to stop)...", TerminalColors.SKY_BLUE))
    try:
        while True:
            _, avg, _ = measure_ping(target, count=1)
            ts = time.strftime("%H:%M:%S")
            if avg is not None:
                color = (
                    TerminalColors.OKGREEN
                    if avg < 30
                    else (TerminalColors.WARNING if avg < 80 else TerminalColors.FAIL)
                )
                print(f"[{ts}] {target}: {colored(f'{avg:.1f} ms', color)}")
            else:
                print(f"[{ts}] {target}: {colored('TIMEOUT / LOSS', TerminalColors.FAIL)}")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopped.")


def run_enhancer_menu(show_banner: bool = False):
    """Interactive submenu for active Wi-Fi enhancements."""
    if show_banner:
        print_banner()

    c_sky = TerminalColors.SKY_BLUE
    c_deep = TerminalColors.DEEP_SKY
    c_ice = TerminalColors.ICE_BLUE
    c_bold = TerminalColors.BOLD
    rst = TerminalColors.ENDC

    print(f"\n{c_deep}  ╭─────────────────── {c_bold}{c_sky}⚡ WI-FI AUTO-OPTIMIZER ⚡{rst}{c_deep} ───────────────╮{rst}")
    print(f"{c_deep}  │{rst}  {c_sky}[1]{rst} {c_ice}Run All Safe Enhancements (Power + Fastest DNS + BBR){rst}   {c_deep}│{rst}")
    print(f"{c_deep}  │{rst}  {c_sky}[2]{rst} {c_ice}Disable Wi-Fi Power Saving (Fix Latency Spikes){rst}         {c_deep}│{rst}")
    print(f"{c_deep}  │{rst}  {c_sky}[3]{rst} {c_ice}Benchmark & Apply Fastest DNS Resolver{rst}                  {c_deep}│{rst}")
    print(f"{c_deep}  │{rst}  {c_sky}[4]{rst} {c_ice}Enable TCP BBR Congestion Control{rst}                       {c_deep}│{rst}")
    print(f"{c_deep}  │{rst}  {c_sky}[5]{rst} {c_ice}Scan Nearby Channels & 5 GHz Access Points{rst}              {c_deep}│{rst}")
    print(f"{c_deep}  │{rst}  {c_sky}[0]{rst} Back to Main Menu                                       {c_deep}│{rst}")
    print(f"{c_deep}  ╰──────────────────────────────────────────────────────────────╯{rst}")

    try:
        sub = input(colored("  Choose enhancement [0-5]: ", c_sky + c_bold)).strip()
    except (EOFError, KeyboardInterrupt):
        return

    iface = find_wifi_interface()

    if sub == "1":
        print("\n" + colored("─── Running All Wi-Fi Enhancements ───", c_sky + c_bold))
        for step, ok, msg in run_all_enhancements():
            icon = colored("✓", TerminalColors.OKGREEN) if ok else colored("✗", TerminalColors.FAIL)
            print(f"  [{icon}] {colored(step, c_ice)}: {msg}")
    elif sub == "2":
        if not iface:
            print(colored("  [-] No active Wi-Fi interface found.", TerminalColors.FAIL))
        else:
            ok, msg = disable_wifi_power_save(iface)
            color = TerminalColors.OKGREEN if ok else TerminalColors.FAIL
            print("  " + colored(msg, color))
    elif sub == "3":
        if not iface:
            print(colored("  [-] No active Wi-Fi interface found.", TerminalColors.FAIL))
        else:
            fastest = find_fastest_public_dns()
            if not fastest:
                print(colored("  [-] Could not reach public DNS resolvers.", TerminalColors.FAIL))
            else:
                ok, msg = apply_dns_resolver(
                    iface,
                    str(fastest["ip"]),
                    f"{fastest['name']} ({float(fastest['avg_ms']):.1f} ms)",
                )
                color = TerminalColors.OKGREEN if ok else TerminalColors.FAIL
                print("  " + colored(msg, color))
    elif sub == "4":
        ok, msg = enable_tcp_bbr()
        color = TerminalColors.OKGREEN if ok else TerminalColors.FAIL
        print("  " + colored(msg, color))
    elif sub == "5":
        aps = scan_nearby_channels()
        print("\n" + colored("─── Nearby Wi-Fi Channels & Bands ───", c_sky + c_bold))
        if not aps:
            print(colored("  No access points returned by nmcli scan.", TerminalColors.WARNING))
        else:
            print(f"  {'USE':<4} {'SSID':<24} {'CHAN':<6} {'FREQ':<10} {'RATE':<12} {'SIGNAL'}")
            for ap in aps[:12]:
                mark = colored(" ★ ", TerminalColors.OKGREEN) if ap["in_use"] else "   "
                print(
                    f"  {mark:<4} {ap['ssid'][:22]:<24} {ap['channel']:<6} "
                    f"{ap['freq']:<10} {ap['rate']:<12} {ap['signal']}%"
                )


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
        print(f"{c_deep}  │{rst}  {c_sky}[4]{rst} {TerminalColors.OKGREEN}⚡ Wi-Fi Auto-Optimizer (Enhance Speed & Latency){rst}        {c_deep}│{rst}")
        print(f"{c_deep}  ├─────────────────── {c_dim}UPCOMING / ROADMAP{c_deep} ───────────────────────┤{rst}")
        print(f"{c_deep}  │{rst}  {c_dim}[5] Modern iw / nmcli Deep Link Inspector    [Coming Soon]{rst}  {c_deep}│{rst}")
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
        elif choice == "4":
            run_enhancer_menu(show_banner=False)
        elif choice in {"5", "6"}:
            feature_names = {
                "5": "Modern iw / nmcli Deep Link Inspector",
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
