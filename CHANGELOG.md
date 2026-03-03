# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-01-01

### Added

- Initial release
- 8 automated setup scripts for Jetson Orin Nano Super
  - System optimization (disable GUI, tune kernel)
  - Network setup (hostname, mDNS, optional Tailscale)
  - SSH hardening (key-only auth, fail2ban)
  - NVMe setup (partition, mount, swap, directories)
  - Docker setup (NVIDIA Runtime, data on NVMe)
  - Dev tools (Node.js, Python, Git, Claude Code, jtop)
  - Quality of life (tmux, aliases, MOTD)
  - Browser setup (Playwright + headless Chromium)
- Arasul interactive TUI with slash commands
  - Project management (create, clone, open, delete)
  - AI tool integration (Claude Code, Codex)
  - GitHub CLI setup wizard
  - Claude OAuth setup wizard
  - Headless browser management
  - System status dashboard
- Configuration via `.env` file
- SSH config template for Mac
- Shell aliases for common operations
- tmux configuration optimized for Jetson development
- Claude Code agent patterns and documentation
