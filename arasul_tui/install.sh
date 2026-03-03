#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${HOME}/venvs/arasul-tui"

echo "[arasul-tui] Creating venv: ${VENV_DIR}"
python3 -m venv "${VENV_DIR}"
# shellcheck disable=SC1090
source "${VENV_DIR}/bin/activate"

echo "[arasul-tui] Installing dependencies..."
python -m pip install --upgrade pip
python -m pip install -e "${REPO_ROOT}"

NVME_BROWSER_CACHE="/mnt/nvme/playwright-browsers"
if [[ -d "/mnt/nvme" ]]; then
  BROWSER_CACHE="${NVME_BROWSER_CACHE}"
else
  BROWSER_CACHE="${HOME}/.cache/ms-playwright"
fi

echo "[arasul-tui] Installing Playwright Chromium to ${BROWSER_CACHE}..."
mkdir -p "${BROWSER_CACHE}"
PLAYWRIGHT_BROWSERS_PATH="${BROWSER_CACHE}" python -m playwright install chromium 2>/dev/null || \
  echo "[arasul-tui] WARN: Chromium download failed (run /browser install later)"

if ! grep -q "PLAYWRIGHT_BROWSERS_PATH" "${HOME}/.bashrc" 2>/dev/null; then
  echo "" >> "${HOME}/.bashrc"
  echo "export PLAYWRIGHT_BROWSERS_PATH=\"${BROWSER_CACHE}\"" >> "${HOME}/.bashrc"
fi

echo "[arasul-tui] Creating launcher: /usr/local/bin/arasul-shell"
sudo tee /usr/local/bin/arasul-shell >/dev/null <<'EOF'
#!/usr/bin/env bash
exec "$HOME/venvs/arasul-tui/bin/arasul-tui" "$@"
EOF
sudo chmod +x /usr/local/bin/arasul-shell

if ! grep -q "alias atui='arasul-shell'" "${HOME}/.bash_aliases" 2>/dev/null; then
  echo "alias atui='arasul-shell'" >> "${HOME}/.bash_aliases"
fi

echo "[arasul-tui] Done. Start with: arasul-shell (or alias: atui)"

