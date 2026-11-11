# WiFi Speed Enhancer & Diagnostics

A lightweight Linux utility to diagnose, benchmark, and optimize Wi-Fi connection performance, latency, and stability.

## Features

- **Link & Signal Inspection**: Real-time signal strength (RSSI), channel, frequency band (2.4GHz / 5GHz), and maximum bitrate.
- **DNS Latency Benchmarking**: Compare your current DNS resolver latency against high-performance resolvers (Cloudflare `1.1.1.1`, Google `8.8.8.8`, Quad9 `9.9.9.9`).
- **Power Save Audit**: Check whether Wi-Fi power-saving mode is enabled (which can cause packet drops and ping spikes on Linux).
- **Optimization Suggestions**: Practical steps to reduce latency and maximize throughput.

## Quick Start

### Prerequisites
Make sure Python 3 and NetworkManager CLI (`nmcli`) are installed:
```bash
python3 --version
nmcli --version
```

### Running the Tool
Run the diagnostic script:
```bash
python3 wifi_enhancer.py
```

## Git Basics for this Project

Since you're getting started with Git, here are the essential commands:

- `git status` - See which files have changed or are untracked.
- `git add <file>` (or `git add .`) - Stage changes to be committed.
- `git commit -m "Your description"` - Save a snapshot of staged changes.
- `git push origin main` - Upload your local commits to GitHub.
- `git pull origin main` - Download and integrate changes from GitHub.

## License
MIT
