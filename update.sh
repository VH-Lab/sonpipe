#!/usr/bin/env bash
#
# sonpipe updater for Linux and macOS.
#
# Convenience wrapper around install.sh: updates the sonpipe package in your
# existing environment in place (no venv rebuild, no re-download of sonpy).
# All arguments are forwarded to install.sh, so e.g. `./update.sh --recreate`
# forces a clean rebuild instead.
#
# Typical use after a `git pull`:
#   ./update.sh

set -euo pipefail

DIR="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
exec "$DIR/install.sh" --update "$@"
