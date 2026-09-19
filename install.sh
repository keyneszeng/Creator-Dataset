#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${CREATOR_DATASET_REPO_URL:-https://github.com/keyneszeng/Creator-Dataset.git}"
INSTALL_DIR="${CREATOR_DATASET_INSTALL_DIR:-$HOME/.creator-dataset}"
BIN_DIR="${CREATOR_DATASET_BIN_DIR:-$HOME/.local/bin}"
PYTHON_BIN="${CREATOR_DATASET_PYTHON:-}"
MIN_PYTHON_MAJOR=3
MIN_PYTHON_MINOR=12

info() {
  printf '\n[Creator Dataset] %s\n' "$*"
}

fail() {
  printf '\n[Creator Dataset] ERROR: %s\n' "$*" >&2
  exit 1
}

version_ok() {
  "$1" - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 12) else 1)
PY
}

find_python() {
  if [ -n "$PYTHON_BIN" ]; then
    command -v "$PYTHON_BIN" >/dev/null 2>&1 || fail "Python not found: $PYTHON_BIN"
    version_ok "$PYTHON_BIN" || fail "$PYTHON_BIN must be Python 3.12+"
    printf '%s' "$PYTHON_BIN"
    return
  fi

  for candidate in python3.13 python3.12 python3; do
    if command -v "$candidate" >/dev/null 2>&1 && version_ok "$candidate"; then
      printf '%s' "$candidate"
      return
    fi
  done

  if [ "$(uname -s)" = "Darwin" ] && command -v brew >/dev/null 2>&1; then
    info "Python 3.12+ not found. Installing python@3.12 with Homebrew..."
    brew install python@3.12
    local brewed
    brewed="$(brew --prefix python@3.12)/bin/python3.12"
    [ -x "$brewed" ] || fail "Homebrew installed Python but executable was not found."
    printf '%s' "$brewed"
    return
  fi

  fail "Python 3.12+ is required. On macOS, install Homebrew + python@3.12, then rerun."
}

ensure_git() {
  command -v git >/dev/null 2>&1 || fail "git is required."
}

install_repo() {
  ensure_git
  if [ -d "$INSTALL_DIR/.git" ]; then
    info "Updating existing installation at $INSTALL_DIR"
    git -C "$INSTALL_DIR" fetch origin
    git -C "$INSTALL_DIR" checkout main
    git -C "$INSTALL_DIR" pull --ff-only origin main
  else
    if [ -e "$INSTALL_DIR" ]; then
      fail "$INSTALL_DIR exists but is not a Creator Dataset git checkout."
    fi
    info "Cloning Creator Dataset to $INSTALL_DIR"
    git clone "$REPO_URL" "$INSTALL_DIR"
  fi
}

install_python_env() {
  local python="$1"
  info "Using Python: $python"
  if [ ! -x "$INSTALL_DIR/.venv/bin/python" ]; then
    "$python" -m venv "$INSTALL_DIR/.venv"
  fi

  "$INSTALL_DIR/.venv/bin/python" -m pip install --upgrade pip
  "$INSTALL_DIR/.venv/bin/pip" install -e "$INSTALL_DIR[agent,xhs,ocr,stt]"
}

configure_env() {
  cd "$INSTALL_DIR"
  if [ ! -f .env ]; then
    cp .env.example .env
  fi

  "$INSTALL_DIR/.venv/bin/python" - <<'PY'
from pathlib import Path

path = Path(".env")
text = path.read_text(encoding="utf-8")
updates = {
    "CREATOR_DATASET_DEPLOYMENT_MODE": "local",
    "CREATOR_DATASET_DATABASE_BACKEND": "sqlite",
    "CREATOR_DATASET_STORAGE_BACKEND": "local",
    "CREATOR_DATASET_SAAS_AUTH_ENABLED": "false",
    "CREATOR_DATASET_AGENT_FREE_MODE": "true",
    "CREATOR_DATASET_MCP_HOST": "127.0.0.1",
    "CREATOR_DATASET_MCP_PORT": "8765",
}

lines = text.splitlines()
seen = set()
out = []
for line in lines:
    stripped = line.strip()
    replaced = False
    for key, value in updates.items():
        if stripped.startswith(f"{key}="):
            out.append(f"{key}={value}")
            seen.add(key)
            replaced = True
            break
    if not replaced:
        out.append(line)

for key, value in updates.items():
    if key not in seen:
        out.append(f"{key}={value}")

path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
PY
}

install_wrappers() {
  mkdir -p "$BIN_DIR"

  cat > "$BIN_DIR/creator-dataset" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd "$INSTALL_DIR"
exec "$INSTALL_DIR/.venv/bin/creator-dataset-agent" "\$@"
EOF
  chmod +x "$BIN_DIR/creator-dataset"

  cat > "$BIN_DIR/creator-dataset-plugin" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd "$INSTALL_DIR"
exec "$INSTALL_DIR/.venv/bin/creator-dataset-plugin-build" "\$@"
EOF
  chmod +x "$BIN_DIR/creator-dataset-plugin"
}

build_local_plugin() {
  cd "$INSTALL_DIR"
  "$INSTALL_DIR/.venv/bin/creator-dataset-plugin-build" --local >/dev/null
}

run_check() {
  cd "$INSTALL_DIR"
  set +e
  "$INSTALL_DIR/.venv/bin/creator-dataset-agent" --check
  local status=$?
  set -e
  return "$status"
}

main() {
  info "Starting one-click personal-use installation"
  local python
  python="$(find_python)"

  install_repo
  install_python_env "$python"
  configure_env
  install_wrappers
  build_local_plugin

  info "Installation complete"

  if run_check; then
    info "Configuration check passed."
  else
    info "Core installation is complete. The remaining expected step is usually adding your Xiaohongshu Cookie to:"
    printf '  %s/.env\n' "$INSTALL_DIR"
  fi

  printf '\n'
  printf 'Installed at: %s\n' "$INSTALL_DIR"
  printf 'Plugin bundle: %s/dist/plugins/creator-dataset\n' "$INSTALL_DIR"
  printf '\n'
  printf 'Start Creator Dataset:\n'
  printf '  %s/creator-dataset\n' "$BIN_DIR"
  printf '\n'
  printf 'Check configuration:\n'
  printf '  %s/creator-dataset --check\n' "$BIN_DIR"
  printf '\n'

  case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *)
      printf 'Tip: add this to your shell profile if the command is not found:\n'
      printf '  export PATH="%s:$PATH"\n' "$BIN_DIR"
      ;;
  esac
}

main "$@"
