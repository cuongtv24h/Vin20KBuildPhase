#!/usr/bin/env bash
# Cross-platform Python launcher for AI log hooks.
# Tries python3 → python → py -3 on PATH; on Windows, falls back to common
# Python install locations because Git Bash launched by some hooks gets a
# stripped PATH that omits the Windows Python directory.
# Designed to be sourced or called as: bash scripts/_pyrun.sh <script> [args...]
#
# Exits 0 silently if no Python is found — hooks must never block the AI tool.
set -u

# `command -v` only checks PATH presence, but Windows registers no-op "App
# Execution Alias" stubs for python/python3 (Microsoft Store redirector) that
# exist on PATH yet fail to actually run Python. Verify each candidate really
# executes before trusting it.
_py_works() {
  # shellcheck disable=SC2086
  $1 --version >/dev/null 2>&1
}

PY=""
for cand in .venv/bin/python venv/bin/python .venv/Scripts/python.exe venv/Scripts/python.exe python3 python "py -3"; do
  if _py_works "$cand"; then PY="$cand"; break; fi
done

if [ -z "$PY" ]; then
  # PATH lookup failed — probe standard Windows install locations.
  shopt -s nullglob 2>/dev/null || true
  for cand in \
    /c/Users/*/AppData/Local/Programs/Python/Python*/python.exe \
    "/c/Program Files/Python"*/python.exe \
    "/c/Program Files (x86)/Python"*/python.exe \
    /c/Python*/python.exe; do
    if [ -x "$cand" ] && _py_works "$cand"; then PY="$cand"; break; fi
  done
  shopt -u nullglob 2>/dev/null || true
  [ -n "$PY" ] || exit 0
fi

# shellcheck disable=SC2086
exec $PY "$@"
