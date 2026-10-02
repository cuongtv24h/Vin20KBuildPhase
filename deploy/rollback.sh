#!/usr/bin/env bash
# ==============================================================================
# [P-096] Lùi phiên bản — đưa code về commit đã deploy thành công gần nhất
# ==============================================================================
#
# Vì sao có: deploy.sh tự lùi khi hỏng, nhưng vẫn cần đường lùi bằng tay khi phát
# hiện lỗi **sau** khi deploy xong (ví dụ 15 phút sau mới thấy API sai).
#
# Dùng:
#   bash deploy/rollback.sh                    # lùi về commit trong logs/deploy-state (prev=)
#   bash deploy/rollback.sh --to <sha>         # lùi về commit chỉ định
#   bash deploy/rollback.sh --auto             # dùng cho deploy.sh gọi tự động (im hơn)
#   bash deploy/rollback.sh --no-build         # chỉ đổi code, không build lại
#
# Cần state: logs/deploy-state do deploy.sh ghi sau mỗi lần deploy thành công.
# ==============================================================================

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_DIR"

STATE_FILE="$REPO_DIR/logs/deploy-state"
LOG_FILE="$REPO_DIR/logs/deploy.log"
TARGET=""
AUTO=0
DO_BUILD=1
RUN_PM2=1
HEALTH_TIMEOUT=45
HEALTH_URL="http://127.0.0.1:${APP_PORT:-8000}/health"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --to)         TARGET="${2:-}"; shift ;;
        --to=*)       TARGET="${1#*=}" ;;
        --auto)       AUTO=1 ;;
        --no-build)   DO_BUILD=0 ;;
        --no-pm2)     RUN_PM2=0 ;;
        --timeout=*)  HEALTH_TIMEOUT="${1#*=}" ;;
        -h|--help)    sed -n '3,18p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Cờ không hợp lệ: $1" >&2; exit 2 ;;
    esac
    shift
done

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG_FILE" >&2; }

if [[ -z "$TARGET" ]]; then
    [[ -f "$STATE_FILE" ]] || { log "✗ Không có $STATE_FILE — chưa deploy lần nào? Dùng --to <sha>."; exit 1; }
    # shellcheck disable=SC1090
    TARGET="$(grep '^prev=' "$STATE_FILE" | cut -d= -f2)"
    [[ -n "$TARGET" ]] || { log "✗ Không có commit trước đó trong $STATE_FILE."; exit 1; }
fi

CURRENT_SHA="$(git rev-parse HEAD)"
if ! git cat-file -e "$TARGET^{commit}" 2>/dev/null; then
    log "✗ Không tìm thấy commit '$TARGET' trong repo."
    exit 1
fi

log "▶ Lùi phiên bản: ${CURRENT_SHA:0:8} → ${TARGET:0:8} ($(git log -1 --format=%s "$TARGET" | cut -c1-70))"

git checkout -q --detach "$TARGET"
log "✓ Đã chuyển code về ${TARGET:0:8} (detached HEAD — deploy.sh lần sau sẽ đưa về nhánh)"

if [[ "$DO_BUILD" == 1 ]]; then
    if [[ -d frontend/node_modules ]]; then
        log "• Build lại frontend từ commit cũ..."
        ( cd frontend && npm run build -w @pricepolicy/internal )
        log "✓ Build lại xong"
    else
        log "! Không có frontend/node_modules — bỏ qua build (chạy npm ci rồi build lại nếu cần)."
    fi
fi

if [[ "$RUN_PM2" == 1 ]] && command -v pm2 >/dev/null 2>&1; then
    pm2 reload deploy/ecosystem.config.cjs --update-env >/dev/null 2>&1 && pm2 save >/dev/null 2>&1 || true
    log "• Đã reload pm2"
    for i in $(seq 1 "$HEALTH_TIMEOUT"); do
        if curl -fsS --max-time 3 "$HEALTH_URL" 2>/dev/null | grep -q '"status"'; then
            log "✓ Backend OK sau ${i}s"
            break
        fi
        if [[ "$i" == "$HEALTH_TIMEOUT" ]]; then
            log "✗ Backend vẫn không trả lời sau ${HEALTH_TIMEOUT}s — kiểm tra: pm2 logs p096-backend --lines 80"
            exit 1
        fi
        sleep 1
    done
fi

# Ghi lại state: "current" = commit vừa lùi về, "prev" = commit NGAY TRƯỚC nó
# (để lần lùi sau vẫn đi lùi tiếp, không quay ngược lại commit vừa bỏ).
OLD_BRANCH="$(grep '^branch=' "$STATE_FILE" 2>/dev/null | cut -d= -f2 || true)"
[[ -n "$OLD_BRANCH" ]] || OLD_BRANCH="develop"
NEW_PREV="$(git rev-parse --quiet --verify "${TARGET}^" 2>/dev/null || true)"
[[ -n "$NEW_PREV" ]] || NEW_PREV="$TARGET"
if [[ -f "$STATE_FILE" ]]; then
    cp "$STATE_FILE" "$STATE_FILE.bak"
fi
cat > "$STATE_FILE" <<EOF
branch=$OLD_BRANCH
prev=$NEW_PREV
current=$TARGET
at=$(date '+%Y-%m-%d %H:%M:%S')
rolled_back=1
EOF
log "Trạng thái mới: current=${TARGET:0:8} · prev=${NEW_PREV:0:8} (lùi tiếp vẫn đi về quá khứ)"

log "✓ === Lùi phiên bản xong: $(git rev-parse --short "$TARGET") ==="
if [[ "$AUTO" == 0 ]]; then
    log "Nhớ kiểm tra lại chức năng chính, và ghi chú nguyên nhân trước khi deploy lại."
fi
