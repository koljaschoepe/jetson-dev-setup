# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-03-03

### Added

- Automated 8-step setup for Jetson Orin Nano Super (headless dev server)
- Arasul TUI with slash commands (/status, /open, /create, /clone, /claude, /codex, /git, /browser, /delete)
- UFW firewall (SSH + mDNS only)
- fail2ban with sshd + recidive jails
- Network hardening (SYN cookies, reverse-path filter)
- OOM protection for SSH and Docker
- Journald size/retention limits
- NVMe I/O scheduler optimization + weekly TRIM + health monitoring
- Headless Chromium via Playwright for AI agent browser automation
- Shared shell library (lib/common.sh)
- CI pipeline (ruff, shellcheck, pytest)
- Comprehensive test suite

### Security

- SSH key-only authentication with sshd config validation
- Automatic security updates via unattended-upgrades (Docker/NVIDIA excluded)
- fail2ban repeat offender protection (recidive jail)

### Fixed

- Shell injection vulnerability in TUI subprocess calls
- Venv path mismatch between installer and browser setup
- Missing STATIC_IP/STATIC_GATEWAY export in setup.sh
- Broken arasul-shell references (renamed to arasul)
- Binary existence check with incorrect shell=True usage
