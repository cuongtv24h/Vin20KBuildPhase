#!/usr/bin/env bash
# Forwarding wrapper for setup_hooks.sh in scripts/ai_log/
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$SCRIPT_DIR/ai_log/setup_hooks.sh" "$@"
