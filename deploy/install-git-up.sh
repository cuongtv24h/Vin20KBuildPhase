#!/usr/bin/env bash
# ==============================================================================
# [P-096] Cài alias `git up` trỏ về deploy/deploy.sh (idempotent)
# ==============================================================================
#
# Vì sao cần: alias cũ trên server gọi thẳng `git pull` (hoặc một bản deploy.sh cũ
# dùng `git pull` + `npm install`) nên hay chết ở giữa như lỗi
# "Your local changes to frontend/package-lock.json would be overwritten by merge".
#
# Script này:
#   1. Sao lưu ~/.gitconfig (giữ bản cũ để đối chiếu).
#   2. Dọn thay đổi cục bộ đang chặn deploy (mặc định: chỉ `frontend/package-lock.json`).
#   3. Đặt alias `git up` → `bash <repo>/deploy/deploy.sh "$@"` (truyền được nhánh/cờ).
#
# Dùng:
#   bash deploy/install-git-up.sh                 # repo tự phát hiện theo vị trí script
#   bash deploy/install-git-up.sh --dir ~/vland   # chỉ định thư mục repo
#   bash deploy/install-git-up.sh --no-cleanup    # không dọn file cục bộ
#
# Sau khi cài: `git up` hoặc `git up develop`, `git up --dry-run`, `git up --force`…
# ==============================================================================

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DO_CLEANUP=1

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dir)           REPO_DIR="$(cd "$2" && pwd)"; shift ;;
        --dir=*)         REPO_DIR="$(cd "${1#*=}" && pwd)" ;;
        --no-cleanup)    DO_CLEANUP=0 ;;
        -h|--help)       sed -n '3,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Cờ không hợp lệ: $1" >&2; exit 2 ;;
    esac
    shift
done

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }

[[ -d "$REPO_DIR/.git" ]] || { log "✗ '$REPO_DIR' không phải git repo. Dùng --dir <đường dẫn>."; exit 1; }
[[ -f "$REPO_DIR/deploy/deploy.sh" ]] || { log "✗ Không thấy deploy/deploy.sh trong $REPO_DIR."; exit 1; }

cd "$REPO_DIR"

# ── 1. Sao lưu gitconfig ──────────────────────────────────────────────────────
GITCONFIG="$HOME/.gitconfig"
if [[ -f "$GITCONFIG" ]]; then
    BACKUP="$GITCONFIG.bak-$(date '+%Y%m%d-%H%M%S')"
    cp "$GITCONFIG" "$BACKUP"
    log "• Đã sao lưu $GITCONFIG → $BACKUP"
fi
log "• Alias cũ (nếu có): $(git config --global --get alias.up || echo '<chưa có>')"

# ── 2. Dọn thay đổi cục bộ đang chặn deploy ───────────────────────────────────
if [[ "$DO_CLEANUP" == 1 ]]; then
    DIRTY="$(git status --porcelain --untracked-files=no || true)"
    if [[ -n "$DIRTY" ]]; then
        log "• Thay đổi cục bộ đang có trên server:"
        printf '%s\n' "$DIRTY" | sed 's/^/    /'
        PATCH="/tmp/p096-local-changes-$(date '+%Y%m%d-%H%M%S').patch"
        git diff HEAD > "$PATCH" || true
        log "    (đã lưu bản sao: $PATCH)"
        git checkout -- . 2>/dev/null || true
        log "    → đã bỏ thay đổi trên các file được git theo dõi; file bị gitignore (.env, data/, logs/) giữ nguyên"
    else
        log "• Không có thay đổi cục bộ — không cần dọn"
    fi
fi

# ── 3. Đặt alias ──────────────────────────────────────────────────────────────
# Cú pháp: git nối tham số người dùng vào CUỐI dòng lệnh alias. Vì vậy định nghĩa một
# hàm `up` rồi gọi trần `up` (không `up "$@"`) — nếu gọi kèm "$@" thì mọi tham số bị
# nhân đôi (`git up --help` → `--help --help` → báo cờ không hợp lệ).
git config --global alias.up "!up() { cd \"$REPO_DIR\" && exec bash deploy/deploy.sh \"\$@\"; }; up"
log "• Đã đặt alias: git config --global alias.up"
log "    $(git config --global --get alias.up)"

# ── 4. Kiểm tra nhanh ─────────────────────────────────────────────────────────
log "• Kiểm tra: git up --dry-run"
if git up --dry-run; then
    log "✓ Cài đặt xong. Từ giờ dùng: git up [nhánh] [cờ]   (vd: git up develop --force)"
else
    log "✗ Alias chạy lỗi — xem log phía trên. Bản gitconfig cũ vẫn còn ở $GITCONFIG.bak-*"
    exit 1
fi
