#!/usr/bin/env bash
#
# sonpipe installer for Linux and macOS.
#
# Installs the sonpipe command-line tool (and CED's sonpy) into an isolated
# Python virtual environment, and puts the `sonpipe` command in your
# ~/.local/bin so it is on your PATH. Then verifies the install and prints the
# line you need to wire sonpipe into MATLAB.
#
# Re-run it any time to UPDATE: if the environment already exists it is reused
# and the sonpipe package is upgraded in place (fast; no venv rebuild). Use
# --recreate to force a clean rebuild.
#
#   venv:     ~/.local/share/sonpipe/venv   (isolated; holds sonpy + numpy)
#   command:  ~/.local/bin/sonpipe          (onto your PATH)
#
# Usage:
#   ./install.sh [options]        # install, or update if already installed
#
# Options:
#   --prefix DIR    Base install prefix (default: ~/.local); the venv goes in
#                   DIR/share/sonpipe/venv and the command in DIR/bin.
#   --venv DIR      Override the virtual environment location.
#   --bin-dir DIR   Override where the `sonpipe` command is placed.
#   --python PY     Python interpreter to build the venv with (default: auto,
#                   prefers python3.14 for sonpy wheel availability).
#   --pypi          Install from PyPI (default when not run inside the repo).
#   --source PATH   Install from this path or pip spec (default: the repo).
#   --update        Update the existing environment in place (the default when
#                   one exists).
#   --recreate      Delete and rebuild the environment from scratch.
#   --no-symlink    Do not create the ~/.local/bin command.
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
RECREATE=0

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
		--recreate)   RECREATE=1; shift ;;
		--update)     RECREATE=0; shift ;;
		-h|--help)    sed -n '2,37p' "$0" | sed 's/^#\{0,1\} \{0,1\}//'; exit 0 ;;
		*) err "unknown option: $1 (use --help)" ;;
	esac
done

VENV_DIR="${VENV_DIR:-$PREFIX/share/sonpipe/venv}"
BIN_DIR="${BIN_DIR:-$PREFIX/bin}"

OS="$(uname -s)"
ARCH="$(uname -m)"
# On Apple Silicon, CED's sonpy is x86_64-only AND is linked against the
# python.org framework build, so we build and run the environment as x86_64
# (Rosetta) using that framework Python.
MAC_ARM=0
if [ "$OS" = "Darwin" ] && [ "$ARCH" = "arm64" ]; then MAC_ARM=1; fi
PYRUN=""
[ "$MAC_ARM" -eq 1 ] && PYRUN="arch -x86_64"

# Resolve the directory this script lives in (following symlinks).
SOURCE_PATH="${BASH_SOURCE[0]}"
while [ -h "$SOURCE_PATH" ]; do
	DIR="$(cd -P "$(dirname "$SOURCE_PATH")" >/dev/null 2>&1 && pwd)"
	SOURCE_PATH="$(readlink "$SOURCE_PATH")"
	[[ "$SOURCE_PATH" != /* ]] && SOURCE_PATH="$DIR/$SOURCE_PATH"
done
SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE_PATH")" >/dev/null 2>&1 && pwd)"

# --recreate wipes any existing environment so we build fresh.
if [ "$RECREATE" -eq 1 ] && [ -d "$VENV_DIR" ]; then
	log "Removing existing environment (--recreate): $VENV_DIR"
	rm -rf "$VENV_DIR"
fi
# Re-running over an existing venv is a fast in-place update.
REUSE=0
[ -f "$VENV_DIR/pyvenv.cfg" ] && REUSE=1

# A base interpreter is only needed to *create* a venv. Updating an existing one
# reuses its interpreter, so skip Python discovery/validation entirely.
if [ "$REUSE" -eq 0 ]; then
	# Pick a Python interpreter (prefer 3.14 for sonpy wheel availability).
	if [ -z "$PYTHON" ]; then
		candidates="python3.14 python3 python"
		# On macOS, prefer the python.org framework build -- CED's sonpy is linked
		# against it and will not load under other distributions (uv, Homebrew, ...).
		if [ "$OS" = "Darwin" ]; then
			candidates="/Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14 $candidates"
		fi
		for c in $candidates; do
			if command -v "$c" >/dev/null 2>&1; then PYTHON="$c"; break; fi
		done
	fi
	[ -n "$PYTHON" ] || err "no Python interpreter found; install Python 3.14 and retry."
	command -v "$PYTHON" >/dev/null 2>&1 || err "python not found: $PYTHON"

	# On Apple Silicon the interpreter must be able to run as x86_64 (i.e. a
	# universal2 build such as the python.org installer). Homebrew/arm64-only
	# builds cannot, and uv's standalone build lacks the framework sonpy needs.
	if [ "$MAC_ARM" -eq 1 ] && ! $PYRUN "$PYTHON" -c 'pass' >/dev/null 2>&1; then
		warn "The chosen Python cannot run as x86_64 (it looks arm64-only)."
		warn "On Apple Silicon, install the python.org universal2 build of Python 3.14:"
		warn "    https://www.python.org/downloads/macos/"
		warn "then re-run (the installer will find it automatically), or pass it explicitly:"
		warn "    ./install.sh --python /Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14"
		exit 1
	fi

	PYVER="$($PYRUN "$PYTHON" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
	log "Using Python $PYVER ($($PYRUN "$PYTHON" -c 'import sys; print(sys.executable)'))"
	[ "$MAC_ARM" -eq 1 ] && log "Apple Silicon: building an x86_64 environment via Rosetta (arch -x86_64)."
	if [ "$PYVER" != "3.14" ]; then
		warn "CED sonpy ships Linux/macOS wheels only for Python 3.14; you are on $PYVER."
		warn "If sonpy fails to import below, re-run with: --python \"\$(command -v python3.14)\""
	fi
fi

# Decide what to install.
if [ -z "$SOURCE" ]; then
	if [ -f "$SCRIPT_DIR/pyproject.toml" ]; then SOURCE="$SCRIPT_DIR"; else SOURCE="sonpipe"; fi
fi
log "Installing from: $SOURCE"

if [ "$REUSE" -eq 1 ]; then
	log "Updating existing environment: $VENV_DIR (use --recreate for a clean rebuild)"
else
	log "Creating virtual environment: $VENV_DIR"
	mkdir -p "$(dirname "$VENV_DIR")"
	$PYRUN "$PYTHON" -m venv "$VENV_DIR"
fi
PY="$VENV_DIR/bin/python"
# Version of the (possibly pre-existing) environment; used in messages below and
# always defined, including on the reuse/update path.
PYVER="$($PYRUN "$PY" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"

log "Upgrading pip"
$PYRUN "$PY" -m pip install --upgrade pip >/dev/null

# --upgrade updates sonpipe in place; dependencies (sonpy, numpy) are only
# touched if a version constraint requires it, so re-running is a fast update.
log "Installing/updating sonpipe (fetches CED's sonpy from PyPI if needed)"
$PYRUN "$PY" -m pip install --upgrade "$SOURCE"

# Verify.
log "Verifying sonpipe CLI ..."
$PYRUN "$PY" -m sonpipe --version || err "sonpipe did not install correctly."

log "Verifying CED sonpy import ..."
SONPY_OK=1
if ! $PYRUN "$PY" -c "from sonpipe.sonfile import load_sonpy; load_sonpy()"; then
	SONPY_OK=0
	if [ "$OS" = "Darwin" ]; then
		warn "sonpy could not be imported. On macOS, CED's sonpy is x86_64-only and is"
		warn "linked against the python.org framework Python. Install Python 3.14 from"
		warn "    https://www.python.org/downloads/macos/"
		warn "and re-run (it will be found automatically), or pass it explicitly:"
		warn "    ./install.sh --python /Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14"
	else
		warn "sonpy could not be imported -- most likely no sonpy wheel exists for"
		warn "Python $PYVER on this platform. Install Python 3.14 and re-run:"
		warn "    ./install.sh --python \"\$(command -v python3.14)\""
	fi
fi

# Put the command on the PATH.
CMD="$VENV_DIR/bin/sonpipe"
if [ "$SYMLINK" -eq 1 ]; then
	mkdir -p "$BIN_DIR"
	if [ "$MAC_ARM" -eq 1 ]; then
		# A wrapper (not a symlink) so the command always runs as x86_64 under
		# Rosetta -- including when launched from a native-arm64 host like MATLAB,
		# where a symlink's shebang would run arm64 and fail to load sonpy.
		rm -f "$BIN_DIR/sonpipe"
		cat > "$BIN_DIR/sonpipe" <<WRAP
#!/bin/sh
exec arch -x86_64 "$VENV_DIR/bin/python" -m sonpipe "\$@"
WRAP
		chmod +x "$BIN_DIR/sonpipe"
	else
		ln -sf "$CMD" "$BIN_DIR/sonpipe"
	fi
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
