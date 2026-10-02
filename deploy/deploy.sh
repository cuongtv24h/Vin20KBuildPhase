#!/usr/bin/env bash
# ==============================================================================
# [P-096] Deploy idempotent — cập nhật code + build + reload + kiểm tra sức khỏe
# ==============================================================================
#
# Vì sao viết lại: bản cũ dùng `git pull` + `npm install` nên **hay đứt giữa đường**
# (lần gần nhất chết ở `frontend/package-lock.json`: `npm install` trên server sửa lockfile,
# lần deploy sau `git pull` từ chối ghi đè thay đổi cục bộ) và luôn chạy lại mọi bước
# dù chỉ đổi một file backend (chậm vô ích).
#
# Bản này:
#   1. KHÔNG dùng `git pull` → `git fetch` + `checkout -B` về đúng commit của nhánh
#      (không bao giờ kẹt merge/conflict).
#   2. Thay đổi cục bộ trên server: sao lưu thành patch (logs/deploy-backups/) rồi mới
#      dọn — không mất dữ liệu, không chặn deploy.
#   3. `npm ci` thay `npm install` → không sửa lockfile, nhanh hơn, đúng như CI.
#   4. Bỏ qua bước không cần: chỉ `pip install` khi requirements.txt đổi, chỉ `npm ci`
#      khi lockfile đổi, chỉ build khi frontend đổi, chỉ reload pm2 khi backend đổi,
#      chỉ reload nginx khi config đổi.
#   5. Có khoá chống deploy chồng nhau (flock), health-check, và tự lùi về commit tốt
#      gần nhất nếu deploy hỏng.
#
# Dùng:
#   git up                                   # deploy nhánh develop (mặc định)
#   git up develop                           # chỉ rõ nhánh
#   bash deploy/deploy.sh --dry-run          # xem sẽ làm gì, không đổi gì
#   bash deploy/deploy.sh --force            # chạy đủ bước dù không có gì mới
#   bash deploy/deploy.sh --no-pm2 --no-nginx  # dev box: chỉ đồng bộ + build
#   bash deploy/deploy.sh --help             # toàn bộ cờ
#
# Xem deploy/README.md cho runbook + xử lý sự cố.
# ==============================================================================

set -Eeuo pipefail

# ── Tự chạy bằng bản sao trong /tmp ───────────────────────────────────────────
# `git checkout` ở bước 1 có thể ghi đè chính file deploy.sh; bash đọc script theo
# từng khối nên file bị thay giữa chừng sẽ làm script chạy sai/đứt. Vì vậy lần chạy
# đầu tự sao ra /tmp rồi exec bản sao (giữ nguyên PID, tham số, cờ dòng lệnh).
if [[ -z "${P096_SELF_DIR:-}" ]]; then
    P096_SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    export P096_SELF_DIR
    SELF_COPY="$(mktemp "${TMPDIR:-/tmp}/p096-deploy-XXXXXX.sh")"
    cp "${BASH_SOURCE[0]}" "$SELF_COPY"
    # dọn các bản sao cũ (chỉ giữ 4 bản gần nhất)
    find "${TMPDIR:-/tmp}" -maxdepth 1 -name 'p096-deploy-*.sh' -printf '%T@ %p\n' 2>/dev/null \
        | sort -rn | tail -n +5 | cut -d' ' -f2- | xargs -r rm -f -- 2>/dev/null || true
    exec bash "$SELF_COPY" "$@"
fi

SCRIPT_DIR="$P096_SELF_DIR"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# ── Mặc định ──────────────────────────────────────────────────────────────────
BRANCH="develop"
DRY_RUN=0
FORCE=0
KEEP_LOCAL=0
CLEAN_UNTRACKED=1
RUN_INSTALL=1
RUN_BUILD=1
RUN_PM2=1
RUN_NGINX=1
ALL_APPS=0
AUTO_ROLLBACK=1
HEALTH_TIMEOUT=45
HEALTH_URL="http://127.0.0.1:${APP_PORT:-8000}/health"
MIN_FREE_MB=1024

# ── Log có mốc thời gian, ghi cả ra logs/deploy.log ───────────────────────────
LOG_DIR="$REPO_DIR/logs"
LOG_FILE="$LOG_DIR/deploy.log"
BACKUP_DIR="$LOG_DIR/deploy-backups"
STAMP_DIR="$REPO_DIR/.deploy-stamps"
STATE_FILE="$LOG_DIR/deploy-state"
mkdir -p "$LOG_DIR" "$BACKUP_DIR" "$STAMP_DIR"

# Commit đã deploy THÀNH CÔNG gần nhất (ghi ở bước 8, chỉ khi mọi bước đều qua).
last_deployed_sha() {
    [[ -f "$STATE_FILE" ]] || return 0
    grep '^current=' "$STATE_FILE" 2>/dev/null | cut -d= -f2 || true
}

if [[ -t 1 ]]; then
    C_RESET=$'\033[0m'; C_BOLD=$'\033[1m'; C_DIM=$'\033[2m'
    C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_RED=$'\033[31m'; C_CYAN=$'\033[36m'
else
    C_RESET=""; C_BOLD=""; C_DIM=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_CYAN=""
fi

log()  { printf '%s[%s]%s %s\n' "$C_DIM" "$(date '+%Y-%m-%d %H:%M:%S')" "$C_RESET" "$*" | tee -a "$LOG_FILE" >&2; }
info() { log "${C_CYAN}$*${C_RESET}"; }
ok()   { log "${C_GREEN}✓ $*${C_RESET}"; }
warn() { log "${C_YELLOW}! $*${C_RESET}"; }
fail() { log "${C_RED}✗ $*${C_RESET}"; }
step() { log ""; log "${C_BOLD}▶ $*${C_RESET}"; }

usage() {
    sed -n '3,28p' "${BASH_SOURCE[0]}" 2>/dev/null | sed 's/^# \{0,1\}//' || echo "(xem phần đầu deploy/deploy.sh)"
    cat <<'EOF'

Cờ:
  <branch>              nhánh cần deploy (mặc định: develop)
  --branch=<branch>     tương đương
  --dry-run, --check    chỉ in ra sẽ làm gì, không thay đổi gì
  --force               bỏ qua kiểm tra thay đổi: cập nhật code + build + reload dù commit không đổi
                        (pip/npm ci vẫn dựa trên dấu vết requirements/lockfile — đúng thì thôi)
  --keep-local          giữ thay đổi cục bộ (stash rồi trả lại sau khi cập nhật)
  --no-clean            không xoá file untracked (mặc định có xoá; file bị gitignore vẫn được giữ)
  --no-install          bỏ qua pip/npm
  --no-build            bỏ qua build frontend
  --all-apps            build cả app khách hàng (mặc định chỉ build app nội bộ mà nginx phục vụ)
  --no-pm2              không reload pm2 (đồng thời bỏ qua health-check — dùng cho dev box)
  --no-nginx            không reload nginx
  --no-auto-rollback    không tự lùi khi deploy hỏng
  --timeout=<giây>      thời gian chờ health-check (mặc định 45)
  -h, --help            in trợ giúp này
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --branch=*)          BRANCH="${1#*=}" ;;
        --dry-run|--check)   DRY_RUN=1 ;;
        --force)             FORCE=1 ;;
        --keep-local)        KEEP_LOCAL=1 ;;
        --no-clean)          CLEAN_UNTRACKED=0 ;;
        --no-install)        RUN_INSTALL=0 ;;
        --no-build)          RUN_BUILD=0 ;;
        --all-apps)          ALL_APPS=1 ;;
        --no-pm2)            RUN_PM2=0 ;;
        --no-nginx)          RUN_NGINX=0 ;;
        --no-auto-rollback)  AUTO_ROLLBACK=0 ;;
        --timeout=*)         HEALTH_TIMEOUT="${1#*=}" ;;
        -h|--help)           usage; exit 0 ;;
        -*)                  fail "Cờ không hợp lệ: $1"; usage; exit 2 ;;
        *)                   BRANCH="$1" ;;
    esac
    shift
done

cd "$REPO_DIR"

# ── Trạng thái dùng cho rollback khi có lỗi ───────────────────────────────────
CODE_SWITCHED=0
#: Chỉ lùi khi dịch vụ đã được reload (lúc đó code mới mới thực sự ảnh hưởng người dùng).
#: Lỗi ở bước cài dependencies/build thì dừng lại là đủ — service cũ vẫn đang chạy.
CAN_ROLLBACK=0
OLD_SHA=""
TARGET_SHA=""
DEPLOY_TS="$(date '+%Y%m%d-%H%M%S')"
IN_SUBSHELL=0

on_error() {
    local exit_code="${1:-1}"
    if [[ "$IN_SUBSHELL" == 1 ]]; then
        exit "$exit_code"   # subshell con (cài deps song song): thoát để tiến trình cha biết
    fi
    fail "Deploy dừng ở bước trên (exit=$exit_code)."
    if [[ "$AUTO_ROLLBACK" == 1 && "$CAN_ROLLBACK" == 1 && "$CODE_SWITCHED" == 1 && "$DRY_RUN" == 0 ]]; then
        # Lùi về commit đang phục vụ tốt gần nhất: state 'current' (chỉ ghi sau lần deploy thành công trước).
        ROLLBACK_TARGET="$OLD_SHA"
        if [[ -f "$STATE_FILE" ]]; then
            LAST_GOOD="$(grep '^current=' "$STATE_FILE" | cut -d= -f2 || true)"
            [[ -n "$LAST_GOOD" ]] && ROLLBACK_TARGET="$LAST_GOOD"
        fi
        warn "Tự động lùi về commit tốt gần nhất (${ROLLBACK_TARGET:0:8})..."
        if ! bash "$SCRIPT_DIR/rollback.sh" --auto --to "$ROLLBACK_TARGET"; then
            fail "Lùi tự động cũng lỗi — chạy tay: bash deploy/rollback.sh --to $ROLLBACK_TARGET"
        fi
    else
        warn "Xem log: $LOG_FILE"
    fi
    exit "$exit_code"
}
# `die 1` KHÔNG kích hoạt trap ERR của bash — mọi lỗi phải đi qua die() để còn cơ hội lùi phiên bản.
die() { on_error "${1:-1}"; }

trap 'on_error $?' ERR

step "[P-096] Bắt đầu deploy — nhánh '$BRANCH' — $(date '+%Y-%m-%d %H:%M:%S')"
log "Repo: $REPO_DIR"

# ── 0. Kiểm tra sơ bộ ─────────────────────────────────────────────────────────
step "0/8 Kiểm tra sơ bộ"
command -v git >/dev/null || { fail "Thiếu 'git'."; die 1; }
command -v node >/dev/null || { fail "Thiếu 'node' (cần Node 20+)."; die 1; }
command -v npm >/dev/null || { fail "Thiếu 'npm'."; die 1; }
if [[ "$RUN_PM2" == 1 ]]; then
    command -v curl >/dev/null || { fail "Thiếu 'curl' (cần cho health-check; hoặc dùng --no-pm2)."; die 1; }
fi

NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]')"
if (( NODE_MAJOR < 20 )); then
    fail "Node $NODE_MAJOR quá cũ — cần ≥ 20 (Vite 8 yêu cầu)."
    die 1
fi
ok "Node $(node -v) · npm $(npm -v)"

FREE_MB="$(df -Pk "$REPO_DIR" | awk 'NR==2 {print int($4/1024)}')"
if (( FREE_MB < MIN_FREE_MB )); then
    fail "Ổ đĩa còn ${FREE_MB}MB (< ${MIN_FREE_MB}MB) — dọn bớt trước khi deploy (npm cache, dist cũ, log)."
    die 1
fi
ok "Ổ đĩa còn ${FREE_MB}MB"

if ! git ls-remote --exit-code --heads origin "$BRANCH" >/dev/null 2>&1; then
    fail "Không thấy nhánh '$BRANCH' trên origin. Kiểm tra: git ls-remote --heads origin"
    die 1
fi
ok "Nhánh '$BRANCH' tồn tại trên origin"

SUDO_OK=0
if [[ "$RUN_NGINX" == 1 ]] && command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
    SUDO_OK=1
    ok "sudo không cần mật khẩu (dùng để cập nhật nginx)"
fi

if command -v flock >/dev/null; then
    exec 9>"$LOG_DIR/.deploy.lock"
    if ! flock -n 9; then
        fail "Đang có tiến trình deploy khác chạy (khoá $LOG_DIR/.deploy.lock)."
        fail "Đợi lần kia xong rồi chạy lại — tránh 2 lần build ghi đè nhau."
        exit 3
    fi
    ok "Đã giữ khoá deploy"
else
    warn "Không có 'flock' — bỏ qua bước chống deploy chồng nhau."
fi

# ── 1. Lấy code mới (fetch + reset, KHÔNG dùng git pull) ──────────────────────
step "1/8 Lấy code mới từ origin/$BRANCH"
OLD_SHA="$(git rev-parse HEAD 2>/dev/null || true)"
git fetch --prune --quiet origin "$BRANCH"
TARGET_SHA="$(git rev-parse "origin/$BRANCH")"
LAST_DEPLOYED="$(last_deployed_sha)"
log "Commit hiện tại : ${OLD_SHA:-<chưa có>}"
log "Commit đích    : $TARGET_SHA ($(git log -1 --format=%s "$TARGET_SHA" | cut -c1-80))"
log "Đã deploy lần cuối: ${LAST_DEPLOYED:-<chưa từng deploy bằng script này>}"

SKIP_CODE=0
CURRENT_BRANCH="$(git symbolic-ref --quiet --short HEAD || true)"   # rỗng = đang detached (sau rollback)
if [[ -n "$OLD_SHA" && "$OLD_SHA" == "$TARGET_SHA" && "$FORCE" == 0 && "$CURRENT_BRANCH" == "$BRANCH" ]]; then
    SKIP_CODE=1
    if [[ "$LAST_DEPLOYED" == "$TARGET_SHA" ]]; then
        ok "Không có commit mới và commit này đã deploy thành công — chỉ kiểm tra dịch vụ."
    else
        ok "Code trên server đã là ${TARGET_SHA:0:8} nhưng CHƯA deploy bằng script này (kéo code tay / lần chạy đầu)."
        info "→ Sẽ chạy các bước cần thiết để máy thực sự chạy đúng commit này."
    fi
    if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
        warn "Vẫn còn thay đổi cục bộ trên server — sẽ sao lưu & dọn ở lần có commit mới (hoặc chạy --force để xử lý ngay)."
    fi
elif [[ "$DRY_RUN" == 0 && "$CURRENT_BRANCH" != "$BRANCH" && -n "$OLD_SHA" && "$OLD_SHA" == "$TARGET_SHA" ]]; then
    info "Đang ở '${CURRENT_BRANCH:-detached HEAD}' — đưa về nhánh '$BRANCH' cho lần sau."
fi

if [[ "$SKIP_CODE" == 0 && "$DRY_RUN" == 0 ]]; then
    # 1a. Thay đổi cục bộ: sao lưu rồi dọn (không để chặn deploy như `git pull` bản cũ).
    DIRTY="$(git status --porcelain --untracked-files=no)"
    if [[ -n "$DIRTY" ]]; then
        PATCH="$BACKUP_DIR/dirty-$DEPLOY_TS.patch"
        git diff HEAD > "$PATCH" || true
        printf '%s\n' "$DIRTY" > "$BACKUP_DIR/dirty-$DEPLOY_TS.files"
        warn "Server có thay đổi cục bộ ở $(printf '%s\n' "$DIRTY" | wc -l | tr -d ' ') file — đã sao lưu:"
        printf '%s\n' "$DIRTY" | sed 's/^/    /' | tee -a "$LOG_FILE" >&2
        log "    patch: $PATCH"
        if [[ "$KEEP_LOCAL" == 1 ]]; then
            git stash push --quiet -m "p096-deploy-$DEPLOY_TS" || true
            warn "Đã stash thay đổi cục bộ (--keep-local) — sẽ trả lại sau khi cập nhật."
        else
            git checkout -- . 2>/dev/null || true
            warn "Đã bỏ thay đổi cục bộ trên các file được git theo dõi (bản sao ở patch trên)."
        fi
    fi

    if [[ "$CLEAN_UNTRACKED" == 1 ]]; then
        # File bị gitignore (.env, .venv, data/, logs/, node_modules, dist) không bao giờ nằm trong danh sách này.
        UNTRACKED="$(LC_ALL=C git clean -fdn | sed 's/^Would remove //')"
        if [[ -n "$UNTRACKED" ]]; then
            PROTECTED_RE='^(\.env.*|\.venv|data|logs|\.deploy-stamps|node_modules|frontend/node_modules)(/|$)'
            TO_KEEP="$(grep -E "$PROTECTED_RE" <<<"$UNTRACKED" || true)"
            TO_CLEAN="$(grep -vE "$PROTECTED_RE" <<<"$UNTRACKED" || true)"
            if [[ -n "$TO_KEEP" ]]; then
                warn "Giữ lại (không xoá) các đường dẫn nhạy cảm:"
                printf '%s\n' "$TO_KEEP" | sed 's/^/    /' | tee -a "$LOG_FILE" >&2
            fi
            if [[ -n "$TO_CLEAN" ]]; then
                info "Dọn file untracked còn sót (rác từ lần deploy/build trước):"
                printf '%s\n' "$TO_CLEAN" | sed 's/^/    /' | tee -a "$LOG_FILE" >&2
                printf '%s\n' "$TO_CLEAN" > "$BACKUP_DIR/cleaned-$DEPLOY_TS.files"
                while IFS= read -r rel; do
                    [[ -n "$rel" ]] && rm -rf -- "$rel"
                done <<<"$TO_CLEAN"
            fi
        fi
    fi

    # 1b. Đưa nhánh local về đúng commit của origin — không bao giờ kẹt merge/conflict.
    git checkout -q -B "$BRANCH" "$TARGET_SHA"
    CODE_SWITCHED=1
    ok "Đã cập nhật code: $(git rev-parse --short "${OLD_SHA:-$TARGET_SHA}") → $(git rev-parse --short "$TARGET_SHA")"
elif [[ "$DRY_RUN" == 1 ]]; then
    info "[dry-run] Sẽ cập nhật ${OLD_SHA:0:8} → ${TARGET_SHA:0:8} (không thực hiện)."
fi

# ── 2. Phát hiện file thay đổi để chỉ chạy bước cần thiết ─────────────────────
# Mốc so sánh là commit ĐÃ DEPLOY THÀNH CÔNG (logs/deploy-state: current), KHÔNG phải HEAD:
# code có thể đã về máy bằng `git pull` tay (hoặc lần chạy script cũ) mà chưa hề được
# build & reload — so với HEAD sẽ tưởng "không có gì đổi" rồi bỏ qua, để lại service chạy code cũ.
step "2/8 Xác định bước cần chạy"
CHANGED=""
ALL_CHANGED=0
if [[ "$FORCE" == 1 ]]; then
    ALL_CHANGED=1
elif [[ -z "$LAST_DEPLOYED" ]]; then
    ALL_CHANGED=1                     # chưa từng deploy thành công bằng script này → chạy đủ bước
    info "Chưa có mốc deploy thành công trước đó — chạy đủ bước cho chắc."
elif ! git cat-file -e "${LAST_DEPLOYED}^{commit}" 2>/dev/null; then
    ALL_CHANGED=1                     # mốc cũ không còn trong repo (force-push) → chạy đủ bước
    info "Mốc deploy cũ (${LAST_DEPLOYED:0:8}) không còn trong repo — chạy đủ bước."
elif [[ "$LAST_DEPLOYED" != "$TARGET_SHA" ]]; then
    if git merge-base --is-ancestor "$LAST_DEPLOYED" "$TARGET_SHA" 2>/dev/null; then
        CHANGED="$(git diff --name-only "$LAST_DEPLOYED" "$TARGET_SHA")"
        info "Thay đổi kể từ lần deploy thành công ${LAST_DEPLOYED:0:8}: $(printf '%s\n' "$CHANGED" | grep -c . ) file."
    else
        ALL_CHANGED=1                 # lịch sử rẽ nhánh (rollback/force-push) → chạy đủ bước
        info "Mốc deploy cũ không phải tổ tiên của commit đích — chạy đủ bước."
    fi
fi

has() { [[ "$ALL_CHANGED" == 1 ]] && return 0; grep -qE "$1" <<<"$CHANGED"; }

REQ_CHANGED=0;      if has '^requirements\.txt$'; then REQ_CHANGED=1; fi
LOCK_CHANGED=0;     if has '^frontend/package(-lock)?\.json$'; then LOCK_CHANGED=1; fi
FRONTEND_CHANGED=0; if has '^frontend/(apps|packages)/'; then FRONTEND_CHANGED=1; fi
BACKEND_CHANGED=0;  if has '^(src/|requirements\.txt$|run\.py$)'; then BACKEND_CHANGED=1; fi
NGINX_CHANGED=0;    if has '^deploy/p096\.nginx\.conf$'; then NGINX_CHANGED=1; fi

frontend_hash() { sha256sum frontend/package-lock.json | awk '{print $1}'; }
req_hash() { sha256sum requirements.txt | awk '{print $1}'; }

need_pip=0; need_npm=0; need_build=0
if [[ "$RUN_INSTALL" == 1 ]]; then
    if [[ ! -x .venv/bin/python ]]; then
        need_pip=1; warn "Chưa có .venv — sẽ tạo mới."
    elif [[ ! -f "$STAMP_DIR/requirements.sha256" || "$(cat "$STAMP_DIR/requirements.sha256")" != "$(req_hash)" || "$REQ_CHANGED" == 1 ]]; then
        need_pip=1
    fi
    if [[ ! -d frontend/node_modules ]]; then
        need_npm=1
    elif [[ ! -f "$STAMP_DIR/package-lock.sha256" || "$(cat "$STAMP_DIR/package-lock.sha256")" != "$(frontend_hash)" || "$LOCK_CHANGED" == 1 ]]; then
        need_npm=1
    fi
fi
DIST_INDEX="frontend/apps/internal/dist/index.html"
if [[ "$RUN_BUILD" == 1 ]]; then
    if [[ "$FRONTEND_CHANGED" == 1 || ! -f "$DIST_INDEX" ]]; then
        need_build=1
    else
        # Lưới an toàn: code về máy bằng đường khác (git pull tay) thì bản build hiện có đã cũ,
        # dù commit không đổi so với lần chạy trước. So mtime nguồn với dist.
        NEWER_SRC="$(find frontend/apps frontend/packages -type f \( -path '*/src/*' -o -name '*.css' \) \
            -not -path '*/node_modules/*' -not -path '*/dist/*' -newer "$DIST_INDEX" -print -quit 2>/dev/null || true)"
        if [[ -n "$NEWER_SRC" ]]; then
            need_build=1
            info "Mã nguồn frontend mới hơn bản build hiện có (vd: $NEWER_SRC) — build lại."
        fi
    fi
fi

log "Thay đổi: requirements=$REQ_CHANGED lockfile=$LOCK_CHANGED frontend=$FRONTEND_CHANGED backend=$BACKEND_CHANGED nginx=$NGINX_CHANGED"
log "Cần chạy: pip=$need_pip npm-ci=$need_npm build=$need_build"

if [[ "$DRY_RUN" == 1 ]]; then
    step "Dry-run kết thúc"
    ok "Không thay đổi gì. Chạy lại không có --dry-run để deploy thật."
    exit 0
fi

# ── 3. Cài dependencies (pip + npm ci chạy song song) ─────────────────────────
step "3/8 Cài dependencies"

install_pip() {
    if [[ ! -x .venv/bin/python ]]; then
        info "Tạo virtualenv .venv..."
        python3 -m venv .venv
    fi
    info "pip install -r requirements.txt ..."
    .venv/bin/pip install --disable-pip-version-check --no-input -q -r requirements.txt
    req_hash > "$STAMP_DIR/requirements.sha256"
    ok "Python deps xong"
}

install_npm() {
    info "npm ci (không sửa lockfile, nhanh hơn npm install) ..."
    ( cd frontend && npm ci --no-audit --no-fund --prefer-offline )
    frontend_hash > "$STAMP_DIR/package-lock.sha256"
    ok "Node deps xong"
}

# Thời điểm pm2 khởi động tiến trình (ms) — để biết service có đang chạy code mới hay không.
pm2_uptime_ms() {
    command -v node >/dev/null 2>&1 || return 0
    pm2 jlist 2>/dev/null | node -e '
let s = "";
process.stdin.on("data", (d) => { s += d; })
  .on("end", () => {
    try {
      const app = JSON.parse(s).find((a) => a.name === "p096-backend");
      if (app && app.pm2_env && app.pm2_env.pm_uptime) process.stdout.write(String(app.pm2_env.pm_uptime));
    } catch (_) { /* pm2 trả về không phải JSON → bỏ qua kiểm tra */ }
  });' 2>/dev/null || true
}

PIDS=()
if [[ "$need_pip" == 1 ]]; then
    ( IN_SUBSHELL=1; install_pip ) & PIDS+=($!)
else
    info "Bỏ qua pip (requirements.txt không đổi)"
fi
if [[ "$need_npm" == 1 ]]; then
    ( IN_SUBSHELL=1; install_npm ) & PIDS+=($!)
else
    info "Bỏ qua npm ci (lockfile không đổi, node_modules còn nguyên)"
fi
for pid in "${PIDS[@]-}"; do
    if [[ -n "$pid" ]] && ! wait "$pid"; then
        fail "Cài dependencies lỗi (pid $pid)."
        die 1
    fi
done

# ── 4. Build frontend ─────────────────────────────────────────────────────────
step "4/8 Build frontend"
if [[ "$need_build" == 1 ]]; then
    if [[ "$ALL_APPS" == 1 ]]; then
        info "Build cả 2 app (customer + internal)..."
        ( cd frontend && npm run build )
    else
        # Nginx chỉ phục vụ app nội bộ (deploy/p096.nginx.conf) → build 1 app là đủ, nhanh gần một nửa.
        info "Build app nội bộ (thêm --all-apps nếu cần cả app khách hàng)..."
        ( cd frontend && npm run build -w @pricepolicy/internal )
    fi
    [[ -f frontend/apps/internal/dist/index.html ]] || { fail "Build xong nhưng thiếu frontend/apps/internal/dist/index.html!"; die 1; }
    ok "Frontend build xong ($(du -sh frontend/apps/internal/dist | cut -f1))"
else
    info "Bỏ qua build (frontend không đổi, dist còn nguyên)"
fi

# ── 5. Reload backend (pm2) ───────────────────────────────────────────────────
step "5/8 Backend (pm2)"
PM2_NEEDED=0
if [[ "$BACKEND_CHANGED" == 1 || "$need_pip" == 1 || "$FORCE" == 1 ]]; then PM2_NEEDED=1; fi

if [[ "$RUN_PM2" == 0 ]]; then
    info "Bỏ qua pm2 (--no-pm2)"
elif ! command -v pm2 >/dev/null 2>&1; then
    warn "Máy không có pm2 — bỏ qua (dev box? dùng --no-pm2 cho gọn log)."
elif pm2 describe p096-backend >/dev/null 2>&1; then
    if [[ "$PM2_NEEDED" == 0 ]]; then
        # Lưới an toàn: tiến trình khởi động TRƯỚC mã nguồn đang nằm trên đĩa → chưa nạp code mới.
        # Dùng mtime file (thời điểm checkout/pull) chứ không dùng mốc thời gian commit, để tránh
        # trường hợp commit mang ngày tương lai (đồng hồ máy khác lệch) gây reload vô ích mỗi lần.
        NEWEST_SRC_TS="$(find src -type f -name '*.py' -not -path '*/__pycache__/*' -printf '%T@\n' 2>/dev/null \
            | sort -rn | head -1 | cut -d. -f1 || true)"
        for extra in requirements.txt run.py; do
            if [[ -f "$extra" ]]; then
                extra_ts="$(stat -c %Y "$extra" 2>/dev/null || echo 0)"
                if [[ -n "$NEWEST_SRC_TS" ]] && (( extra_ts > NEWEST_SRC_TS )); then NEWEST_SRC_TS="$extra_ts"; fi
            fi
        done
        PM2_START_MS="$(pm2_uptime_ms)"
        if [[ -n "$PM2_START_MS" && -n "$NEWEST_SRC_TS" ]] && (( PM2_START_MS / 1000 < NEWEST_SRC_TS )); then
            PM2_NEEDED=1
            info "Mã nguồn backend mới hơn tiến trình đang chạy — reload để nạp code mới."
        fi
    fi
    if [[ "$PM2_NEEDED" == 1 ]]; then
        [[ -x .venv/bin/python ]] || { fail "Thiếu .venv/bin/python — pm2 không chạy được. Chạy: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"; die 1; }
        CAN_ROLLBACK=1
        pm2 reload deploy/ecosystem.config.cjs --update-env
        ok "Đã reload p096-backend (zero-downtime)"
    else
        info "Bỏ qua reload (backend không đổi)"
    fi
    pm2 save >/dev/null 2>&1 || true
else
    warn "pm2 chưa có app 'p096-backend' — khởi động lần đầu."
    pm2 start deploy/ecosystem.config.cjs
    pm2 save >/dev/null 2>&1 || true
    ok "Đã start p096-backend"
fi

# ── 6. Health-check ───────────────────────────────────────────────────────────
step "6/8 Kiểm tra sức khỏe backend ($HEALTH_URL)"
health_ok=0
if [[ "$RUN_PM2" == 0 ]]; then
    info "Bỏ qua health-check (--no-pm2): script không quản lý dịch vụ trong chế độ này."
else
    for _ in $(seq 1 "$HEALTH_TIMEOUT"); do
        if curl -fsS --max-time 3 "$HEALTH_URL" 2>/dev/null | grep -q '"status"'; then
            health_ok=1; break
        fi
        sleep 1
    done
fi

# Chưa lên: thử restart một lần (hay gặp khi process cũ treo hoặc máy vừa reboot).
if [[ "$health_ok" == 0 && "$RUN_PM2" == 1 ]] && command -v pm2 >/dev/null 2>&1 && pm2 describe p096-backend >/dev/null 2>&1; then
    warn "Chưa thấy backend trả lời — thử restart p096-backend một lần..."
    pm2 restart p096-backend --update-env >/dev/null 2>&1 || true
    for _ in $(seq 1 "$HEALTH_TIMEOUT"); do
        if curl -fsS --max-time 3 "$HEALTH_URL" 2>/dev/null | grep -q '"status"'; then
            health_ok=1; break
        fi
        sleep 1
    done
fi

if [[ "$RUN_PM2" == 0 ]]; then
    info "Không kiểm tra backend (--no-pm2)."
elif [[ "$health_ok" == 1 ]]; then
    ok "Backend trả lời OK"
else
    fail "Backend KHÔNG trả lời sau ${HEALTH_TIMEOUT}s ($HEALTH_URL)."
    fail "Xem log: pm2 logs p096-backend --lines 80"
    die 1     # die() → on_error() → tự lùi phiên bản nếu đã reload dịch vụ
fi

# ── 7. Nginx ──────────────────────────────────────────────────────────────────
step "7/8 Nginx"
if [[ "$RUN_NGINX" == 0 ]]; then
    info "Bỏ qua nginx (--no-nginx)"
elif ! command -v nginx >/dev/null 2>&1; then
    warn "Máy không có nginx — bỏ qua."
elif [[ "$SUDO_OK" == 1 && ( "$NGINX_CHANGED" == 1 || "$FORCE" == 1 ) ]]; then
    CONF_DEST="/etc/nginx/sites-available/p096.conf"
    if [[ -f "$CONF_DEST" ]]; then
        CONF_BAK="$CONF_DEST.bak-$(date '+%Y%m%d-%H%M%S')"
        CONF_BAK_MADE=0
        if sudo -n cp "$CONF_DEST" "$CONF_BAK" 2>/dev/null; then CONF_BAK_MADE=1; fi
        sudo -n cp deploy/p096.nginx.conf "$CONF_DEST"
        if sudo -n nginx -t; then
            sudo -n systemctl reload nginx && ok "Đã cập nhật $CONF_DEST + reload nginx"
        else
            if [[ "$CONF_BAK_MADE" == 1 ]]; then
                sudo -n cp "$CONF_BAK" "$CONF_DEST"
                warn "Config nginx mới KHÔNG hợp lệ — đã khôi phục bản cũ ($CONF_BAK), không reload."
            else
                warn "Config nginx mới KHÔNG hợp lệ — KHÔNG reload. Bản cũ ở $CONF_DEST cũng không sao lưu được, kiểm tra tay!"
            fi
            warn "Sửa deploy/p096.nginx.conf rồi deploy lại."
        fi
    else
        sudo -n nginx -t && sudo -n systemctl reload nginx && ok "Đã reload nginx"
        warn "Chưa thấy $CONF_DEST — cài lần đầu: sudo cp deploy/p096.nginx.conf $CONF_DEST && sudo ln -sf $CONF_DEST /etc/nginx/sites-enabled/ && sudo nginx -t && sudo systemctl reload nginx"
    fi
elif [[ "$NGINX_CHANGED" == 1 || "$FORCE" == 1 ]]; then
    warn "Sudo cần mật khẩu — bỏ qua nginx. Chạy tay: sudo cp deploy/p096.nginx.conf /etc/nginx/sites-available/p096.conf && sudo nginx -t && sudo systemctl reload nginx"
else
    info "Bỏ qua reload nginx (config không đổi)"
fi

# ── 8. Ghi trạng thái (cho rollback) + trả lại thay đổi cục bộ nếu có stash ───
step "8/8 Ghi trạng thái"
PREV_TO_KEEP="$OLD_SHA"
if [[ "$SKIP_CODE" == 1 && -f "$STATE_FILE" ]]; then
    PREV_FROM_FILE="$(grep '^prev=' "$STATE_FILE" | cut -d= -f2 || true)"
    [[ -n "$PREV_FROM_FILE" ]] && PREV_TO_KEEP="$PREV_FROM_FILE"
fi
if [[ "$PREV_TO_KEEP" == "$TARGET_SHA" ]]; then
    # Tránh prev == current (thường gặp khi lần trước kết thúc ở detached HEAD đúng commit này):
    # prev phải CŨ HƠN current để `git up`/rollback lần sau còn lùi được.
    PREV_TO_KEEP="$(git rev-parse --quiet --verify "${TARGET_SHA}^" 2>/dev/null || true)"
fi
cat > "$STATE_FILE" <<EOF
branch=$BRANCH
prev=$PREV_TO_KEEP
current=$TARGET_SHA
at=$(date '+%Y-%m-%d %H:%M:%S')
EOF
ok "Trạng thái: $STATE_FILE"

if [[ "$KEEP_LOCAL" == 1 ]] && git stash list | grep -q "p096-deploy-$DEPLOY_TS"; then
    if git stash pop --quiet; then
        warn "Đã trả lại thay đổi cục bộ (--keep-local). Lưu ý: lần deploy sau chúng vẫn bị sao lưu/dọn."
    else
        warn "Stash pop bị xung đột — thay đổi vẫn nằm trong: git stash list (p096-deploy-$DEPLOY_TS)"
    fi
fi

if [[ "$SKIP_CODE" == 1 && "$need_pip" == 0 && "$need_npm" == 0 && "$need_build" == 0 && "$PM2_NEEDED" == 0 ]]; then
    info "Không có bước nào cần chạy (code, deps, build, pm2 đều đã đúng commit này)."
    info "Nếu bạn vừa tự kéo code bằng tay và nghi build/reload chưa chạy: git up --force"
fi

log ""
ok "=== [P-096] Deploy thành công: $BRANCH @ $(git rev-parse --short "$TARGET_SHA") ($(date '+%H:%M:%S')) ==="
log "Log đầy đủ: $LOG_FILE · Lùi phiên bản: bash deploy/rollback.sh"
