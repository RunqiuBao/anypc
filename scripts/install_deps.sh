#!/usr/bin/env bash
#
# install_deps.sh — install system + Python dependencies for anypc.
#
# Sets up:
#   - TigerVNC server + a lightweight XFCE desktop (the remote "PC").
#   - A uv-managed Python virtual environment with websockets + msgpack + pyzmq.
#
# Target: Debian/Ubuntu (apt). Run as a normal user with sudo available.

set -euo pipefail

# --- locations -------------------------------------------------------------
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${VENV_DIR:-$REPO_ROOT/.venv}"

log() { printf '\033[1;32m[install]\033[0m %s\n' "$*"; }
err() { printf '\033[1;31m[install]\033[0m %s\n' "$*" >&2; }

# --- sanity checks ---------------------------------------------------------
if ! command -v apt-get >/dev/null 2>&1; then
  err "apt-get not found. This script targets Debian/Ubuntu."
  exit 1
fi

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  if command -v sudo >/dev/null 2>&1; then
    SUDO="sudo"
  else
    err "Run as root or install sudo."
    exit 1
  fi
fi

# The user who will actually run the services and own the VNC config. When
# invoked via `sudo`, that's the original user (SUDO_USER), not root.
TARGET_USER="${SUDO_USER:-$(id -un)}"
TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"

# --- system packages -------------------------------------------------------
log "Updating apt package index..."
$SUDO apt-get update -y

log "Installing VNC server and desktop environment..."
# Use `env` to set DEBIAN_FRONTEND: when running as root $SUDO is empty, and a
# bare `VAR=val cmd` after the (empty) $SUDO token is parsed as a command name,
# not an assignment. `env` is a real command in both the root and sudo cases.
$SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  tigervnc-standalone-server \
  tigervnc-common \
  xfce4 \
  xfce4-goodies \
  dbus-x11 \
  xfonts-base

# Some TigerVNC builds ship only `tigervncserver` and no `vncserver`. The unit
# files invoke `vncserver`, so symlink it when the plain name is missing.
if ! command -v vncserver >/dev/null 2>&1 && command -v tigervncserver >/dev/null 2>&1; then
  log "Creating /usr/bin/vncserver -> $(command -v tigervncserver) symlink..."
  $SUDO ln -sf "$(command -v tigervncserver)" /usr/bin/vncserver
fi

# --- vnc desktop startup ---------------------------------------------------
# The xstartup script tells VNC which desktop to launch; without it the
# session comes up to a blank/gray screen. Created in the target user's home
# (matches the systemd user service, which runs as that user).
VNC_DIR="$TARGET_HOME/.vnc"
log "Configuring VNC desktop startup at $VNC_DIR/xstartup ..."
mkdir -p "$VNC_DIR"
cat > "$VNC_DIR/xstartup" <<'EOF'
#!/bin/sh
unset SESSION_MANAGER DBUS_SESSION_BUS_ADDRESS
exec startxfce4
EOF
chmod +x "$VNC_DIR/xstartup"
# Ensure the target user owns it even when this script runs as root via sudo.
chown -R "$TARGET_USER" "$VNC_DIR"

log "Installing base Python (used by uv to build the venv)..."
$SUDO apt-get install -y --no-install-recommends python3

# --- uv --------------------------------------------------------------------
if ! command -v uv >/dev/null 2>&1; then
  log "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # uv installs to ~/.local/bin; make it available for the rest of this run.
  export PATH="$HOME/.local/bin:$PATH"
fi

if ! command -v uv >/dev/null 2>&1; then
  err "uv installation failed or not on PATH (expected in ~/.local/bin)."
  exit 1
fi
log "Using uv $(uv --version)"

# --- python environment ----------------------------------------------------
# Keep uv's managed Python interpreter *inside the app tree* ($REPO_ROOT/.python)
# instead of the default ~/.local/share/uv/python. This matters because under
# `sudo make install` this script runs as root: with the default location uv
# would download the interpreter into /root/.local/share/uv (mode 700), the
# venv's bin/python would symlink there, and after `make install` hands the app
# to the unprivileged run user that path stays root-owned and unreadable — so
# anypc-server.service fails to start. Placed under $REPO_ROOT it gets chowned
# to the run user along with the rest of /opt/anypc, keeping the venv usable.
# UV_LINK_MODE=copy avoids hardlink failures when the uv cache and $REPO_ROOT
# live on different filesystems.
export UV_PYTHON_INSTALL_DIR="$REPO_ROOT/.python"
export UV_LINK_MODE=copy

log "Creating virtual environment at $VENV_DIR ..."
uv venv "$VENV_DIR"

REQ_FILE="$REPO_ROOT/requirements.txt"
PYPROJECT="$REPO_ROOT/pyproject.toml"
if [ -f "$PYPROJECT" ]; then
  log "Syncing project + deps from pyproject.toml ..."
  # Installs the anypc package itself, so the entry-point executables
  # (anypc-server, anypc-example-worker) land on PATH inside the venv.
  (cd "$REPO_ROOT" && uv sync)
elif [ -f "$REQ_FILE" ]; then
  log "Installing Python deps from requirements.txt ..."
  VIRTUAL_ENV="$VENV_DIR" uv pip install -r "$REQ_FILE"
  VIRTUAL_ENV="$VENV_DIR" uv pip install -e "$REPO_ROOT"
else
  log "No requirements.txt/pyproject.toml found; installing the WebSocket stack directly..."
  VIRTUAL_ENV="$VENV_DIR" uv pip install \
    "websockets" "msgpack" "numpy" "pyzmq"
fi

# --- verify the anypc package installed correctly --------------------------
log "Verifying anypc package installation..."
if ! "$VENV_DIR/bin/python" -c "import anypc; print('anypc', anypc.__version__)"; then
  err "anypc package is not importable in $VENV_DIR — installation failed."
  exit 1
fi
if [ ! -x "$VENV_DIR/bin/anypc-server" ]; then
  err "anypc-server executable missing from $VENV_DIR/bin — installation failed."
  exit 1
fi
log "anypc package OK ($VENV_DIR/bin/anypc-server)"

# --- shell helper ----------------------------------------------------------
# Make the `anypc` command available in interactive shells by sourcing the
# version-controlled helper from ~/.bashrc. Written as a guarded block so
# re-running this script just refreshes it (no duplicate lines).
HELPER="$REPO_ROOT/scripts/anypc.sh"
BASHRC="$TARGET_HOME/.bashrc"
log "Enabling 'anypc' command in $BASHRC (sources $HELPER) ..."
if [ -f "$BASHRC" ]; then
  sed -i '/# >>> anypc service helper >>>/,/# <<< anypc service helper <<</d' "$BASHRC"
fi
cat >> "$BASHRC" <<EOF

# >>> anypc service helper >>>
[ -f "$HELPER" ] && . "$HELPER"
# <<< anypc service helper <<<
EOF
chown "$TARGET_USER" "$BASHRC"

# --- keep services running after logout ------------------------------------
# Enable lingering so the user's systemd instance (and our services) keeps
# running even when no interactive session is open. Needs root; $SUDO covers
# both the root (make install) and non-root (standalone) cases.
log "Enabling lingering for $TARGET_USER ..."
$SUDO loginctl enable-linger "$TARGET_USER"

log "Done."
log "Open a new shell (or: source ~/.bashrc), then:  anypc launch"
log "Or load it explicitly anywhere:  source $HELPER && anypc launch"
log "Other commands:  anypc {stop|restart|status|logs}"
