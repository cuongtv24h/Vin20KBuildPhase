# Forwarding wrapper for setup_hooks.ps1 in scripts/ai_log/
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
& "$scriptDir\ai_log\setup_hooks.ps1" $args
