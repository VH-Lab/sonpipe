#!/usr/bin/env bash
#
# sonpipe installer for Linux and macOS.
#
# Installs the sonpipe command-line tool (and CED's sonpy) into an isolated
# Python virtual environment, and symlinks the `sonpipe` command into your
# ~/.local/bin so it is on your PATH. Then verifies the install and prints the
# line you need to wire sonpipe into MATLAB.
#
#   venv:     ~/.local/share/sonpipe/venv   (isolated; holds sonpy + numpy)
#   command:  ~/.local/bin/sonpipe          (symlink onto your PATH)
#
# Usage:
#   ./install.sh [options]
#
# Options:
#   --prefix DIR    Base install prefix (default: ~/.local); the venv goes in
#                   DIR/share/sonpipe/venv and the command in DIR/bin.
#   --venv DIR      Override the virtual environment location.
#   --bin-dir DIR   Override where the `sonpipe` command is linked.
#   --python PY     Python interpreter to build the venv with (default: auto,
#                   prefers python3.14 for sonpy wheel availability).
#   --pypi          Install from PyPI (default when not run inside the repo).
#   --source PATH   Install from this path or pip spec (default: the repo).
#   --no-symlink    Do not create the ~/.local/bin symlink.
#   -h, --help      Show this help.
#
# Note: CED ships sonpy Linux/macOS wheels only for Python 3.14, so this script
# prefers python3.14. If sonpy fails to import afterwards, install Python 3.14
# and re-run with: --python "$(command -v python3.14)".

set -euo pipefail

PREFIX="$HOME/.local"
VENV_DIR=""
BIN_DIR=""
PYTHON=""
SOURCE=""
SYMLINK=1

log()  { printf '\033[1;34m[sonpipe]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[sonpipe] WARNING:\033[0m %s\n' "$*" >&2; }
err()  { printf '\033[1;31m[sonpipe] ERROR:\033[0m %s\n' "$*" >&2; exit 1; }

# Print a PATH-setup instruction appropriate to the user's login shell.
path_hint() {
	bindir="$1"
	case "$(basename "${SHELL:-}")" in
		zsh)
			warn "    echo 'export PATH=\"$bindir:\$PATH\"' >> ~/.zshrc && source ~/.zshrc" ;;
		bash)
			# macOS login shells read ~/.bash_profile; most Linux shells read ~/.bashrc.
			if [ "$(uname -s)" = "Darwin" ]; then rc="~/.bash_profile"; else rc="~/.bashrc"; fi
			warn "    echo 'export PATH=\"$bindir:\$PATH\"' >> $rc && source $rc" ;;
		fish)
			warn "    fish_add_path $bindir" ;;
		*)
			warn "    add to your shell profile:  export PATH=\"$bindir:\$PATH\"" ;;
	esac
}

while [ $# -gt 0 ]; do
	case "$1" in
		--prefix)     PREFIX="$2";   shift 2 ;;
		--venv)       VENV_DIR="$2"; shift 2 ;;
		--bin-dir)    BIN_DIR="$2";  shift 2 ;;
		--python)     PYTHON="$2";   shift 2 ;;
		--source)     SOURCE="$2";   shift 2 ;;
		--pypi)       SOURCE="sonpipe"; shift ;;
		--no-symlink) SYMLINK=0; shift ;;
		-h|--help)    sed -n '2,38p' "$0" | sed 's/^#\{0,1\} \{0,1\}//'; exit 0 ;;
		*) err "unknown option: $1 (use --help)" ;;
	esac
done

VENV_DIR="${VENV_DIR:-$PREFIX/share/sonpipe/venv}"
BIN_DIR="${BIN_DIR:-$PREFIX/bin}"

# Resolve the directory this script lives in (following symlinks).
SOURCE_PATH="${BASH_SOURCE[0]}"
while [ -h "$SOURCE_PATH" ]; do
	DIR="$(cd -P "$(dirname "$SOURCE_PATH")" >/dev/null 2>&1 && pwd)"
	SOURCE_PATH="$(readlink "$SOURCE_PATH")"
	[[ "$SOURCE_PATH" != /* ]] && SOURCE_PATH="$DIR/$SOURCE_PATH"
done
SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE_PATH")" >/dev/null 2>&1 && pwd)"

# Pick a Python interpreter (prefer 3.14 for sonpy wheel availability).
if [ -z "$PYTHON" ]; then
	for c in python3.14 python3 python; do
		if command -v "$c" >/dev/null 2>&1; then PYTHON="$c"; break; fi
	done
fi
[ -n "$PYTHON" ] || err "no Python interpreter found; install Python 3.14 and retry."
command -v "$PYTHON" >/dev/null 2>&1 || err "python not found: $PYTHON"

PYVER="$("$PYTHON" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
log "Using Python $PYVER ($("$PYTHON" -c 'import sys; print(sys.executable)'))"
if [ "$PYVER" != "3.14" ]; then
	warn "CED sonpy ships Linux/macOS wheels only for Python 3.14; you are on $PYVER."
	warn "If sonpy fails to import below, re-run with: --python \"\$(command -v python3.14)\""
fi

# Decide what to install.
if [ -z "$SOURCE" ]; then
	if [ -f "$SCRIPT_DIR/pyproject.toml" ]; then SOURCE="$SCRIPT_DIR"; else SOURCE="sonpipe"; fi
fi
log "Installing from: $SOURCE"

log "Creating virtual environment: $VENV_DIR"
mkdir -p "$(dirname "$VENV_DIR")"
"$PYTHON" -m venv "$VENV_DIR"
PY="$VENV_DIR/bin/python"

log "Upgrading pip"
"$PY" -m pip install --upgrade pip >/dev/null

log "Installing sonpipe (also fetches CED's sonpy from PyPI)"
"$PY" -m pip install "$SOURCE"

# Verify.
log "Verifying sonpipe CLI ..."
"$PY" -m sonpipe --version || err "sonpipe did not install correctly."

log "Verifying CED sonpy import ..."
SONPY_OK=1
if ! "$PY" -c "import sonpy; print('sonpy', sonpy.__version__)"; then
	SONPY_OK=0
	warn "sonpy could not be imported -- most likely no sonpy wheel exists for"
	warn "Python $PYVER on this platform. Install Python 3.14 and re-run:"
	warn "    ./install.sh --python \"\$(command -v python3.14)\""
fi

# Symlink the command onto the PATH.
CMD="$VENV_DIR/bin/sonpipe"
if [ "$SYMLINK" -eq 1 ]; then
	mkdir -p "$BIN_DIR"
	ln -sf "$CMD" "$BIN_DIR/sonpipe"
	CMD="$BIN_DIR/sonpipe"
	case ":$PATH:" in
		*":$BIN_DIR:"*) : ;;
		*) warn "$BIN_DIR is not on your PATH. Add it with:"
		   path_hint "$BIN_DIR" ;;
	esac
fi

echo
log "Done."
echo "  Command: $CMD --help"
echo "  MATLAB:  add the repo's 'matlab' folder to your path, then run:"
echo "             sonpipe.executable('$CMD')"
[ "$SONPY_OK" -eq 1 ] || exit 1
