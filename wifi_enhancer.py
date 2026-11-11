#!/usr/bin/env python3
"""
WiFi Speed Enhancer & Diagnostics — CLI Entry Point
Modular Architecture:
  - ui.py          : Terminal Front End (Sky Blue #82C8E5 logo, palette, menus, tables)
  - diagnostics.py : Read-only Wi-Fi audit, gateway ping, and raw UDP DNS benchmark
  - enhancer.py    : Active Wi-Fi optimizations (Power Save off, Fastest DNS, TCP BBR, Channel Scan)
"""

import argparse
import sys

from ui import (
    monitor_ping,
    run_audit,
    run_dns_benchmark_standalone,
    run_enhancer_menu,
    run_interactive_menu,
)


def main():
    parser = argparse.ArgumentParser(description="WiFi Speed Enhancer & Diagnostics")
    parser.add_argument("--audit", action="store_true", help="Run full Wi-Fi audit immediately")
    parser.add_argument("--dns", action="store_true", help="Run DNS resolver benchmark (1.1.1.1, 8.8.8.8, 9.9.9.9)")
    parser.add_argument("--optimize", action="store_true", help="Open the Wi-Fi Auto-Optimizer menu")
    parser.add_argument("--ping", action="store_true", help="Continuously monitor latency to detect jitter and drops")
    parser.add_argument("--menu", action="store_true", help="Launch interactive terminal menu (default in TTY)")
    parser.add_argument("--target", default="1.1.1.1", help="Target host for ping monitor (default: 1.1.1.1)")
    args = parser.parse_args()

    if args.ping:
        monitor_ping(args.target)
    elif args.dns:
        run_dns_benchmark_standalone()
    elif args.optimize:
        run_enhancer_menu(show_banner=True)
    elif args.audit:
        run_audit()
    elif args.menu or sys.stdout.isatty():
        run_interactive_menu()
    else:
        run_audit()


if __name__ == "__main__":
    main()
