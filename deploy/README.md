# Triển khai (deploy) — P-096

Runbook cho việc deploy lên VM `ubuntu@ip-172-31-4-117:~/vland` (site `demoday.work.gd`).
Tất cả nằm trong 3 script ở thư mục này:

| File | Việc |
|---|---|
| `deploy.sh` | Deploy chính: cập nhật code → cài deps → build → reload pm2/nginx → health-check → tự lùi nếu hỏng |
| `rollback.sh` | Lùi về commit đã deploy thành công gần nhất |
| `install-git-up.sh` | Cài alias `git up` (một lần cho mỗi máy) |

---

## 1. TL;DR — deploy hằng ngày

```bash
ssh ubuntu@ip-172-31-4-117
cd ~/vland
git up                 # deploy nhánh đã deploy thành công lần trước; chưa có thì develop
git up main            # chỉ định nhánh — các lần sau `git up` sẽ NHỚ nhánh này
git up --dry-run       # xem script SẼ làm gì, không đổi gì
git up --force         # chạy đủ mọi bước dù không có commit mới
```

Không cần `git pull`, không cần tự `npm install`, không cần tự reload pm2.
Muốn lùi phiên bản: `bash deploy/rollback.sh`.

### Nhánh & remote mặc định

Nhánh được chọn theo thứ tự ưu tiên (cái trên thắng):

| # | Nguồn | Ví dụ |
| :-: | :--- | :--- |
| 1 | Chỉ định trong lệnh | `git up main`, `git up --branch=main` |
| 2 | Biến môi trường | `DEPLOY_BRANCH=main git up` |
| 3 | **Nhớ từ lần deploy thành công trước** (`logs/deploy-state: branch`) | `git up` sau khi đã `git up main` một lần |
| 4 | Mặc định | `develop` (khi chưa từng deploy bằng script này) |

Remote mặc định là `origin`; đổi bằng `git up --remote=upstream develop` hoặc `DEPLOY_REMOTE=upstream git up`.
Mỗi lần chạy, dòng đầu log in rõ: `Nguồn : origin/develop (… cho remote · … cho nhánh)` — nhìn là biết
đang lấy từ đâu và vì sao.

> Lưu ý nhỏ của git: `git up --help` (và `git up -h`) **không** chạy script — git in ra định nghĩa alias rồi thoát.
> Muốn xem trợ giúp: `bash deploy/deploy.sh --help` (hoặc `git up --dry-run` để xem trước kế hoạch).

---

## 2. Lần đầu trên một máy mới (VM hiện tại)

> Trạng thái hiện tại của VM: `git up develop` đang đứt ở
> `error: Your local changes to the following files would be overwritten by merge: frontend/package-lock.json`.

**Bước 1 — gỡ kẹt một lần (không mất gì, lockfile trên server chỉ là bản `npm install` tự sửa):**

```bash
cd ~/vland
git checkout -- frontend/package-lock.json     # bỏ phần npm install tự sửa
git pull origin develop                        # lấy bộ script deploy mới
```

**Bước 2 — cài alias `git up` (tự dọn drift còn sót, tự sao lưu `~/.gitconfig`, tự chạy thử `--dry-run`):**

```bash
bash deploy/install-git-up.sh
```

**Bước 3 — deploy thật:**

```bash
git up
```

Lần deploy này sẽ tạo `.venv` nếu chưa có, chạy `npm ci`, build app nội bộ, reload pm2 và
kiểm tra `http://127.0.0.1:8000/health`.

---

## 3. Vì sao lỗi cũ không còn xảy ra

| Nguyên nhân | Cách xử lý trong bản mới |
|---|---|
| Bản cũ chạy `git pull` → git **từ chối ghi đè** thay đổi cục bộ (chính `frontend/package-lock.json` do `npm install` sửa) → deploy dừng giữa đường | Không dùng `git pull`. Dùng `git fetch` + `git checkout -B <nhánh> <sha>`: luôn về đúng commit của origin, không bao giờ kẹt merge/conflict |
| `npm install` trên server sửa lockfile mỗi lần chạy | Dùng `npm ci` (đúng như CI): chỉ đọc lockfile, **không sửa**, và cài đúng phiên bản |
| Thay đổi cục bộ bị mất khi reset | Trước khi dọn, script lưu patch `logs/deploy-backups/dirty-<ts>.patch` + danh sách file `.files`. Muốn giữ lại: `git up --keep-local` (stash rồi trả lại) |
| Rác từ build/deploy cũ tích tụ, file lạ gây nhiễu | `git clean` có kiểm soát: **giữ** `.env*`, `.venv`, `data/`, `logs/`, `node_modules/`, `.deploy-stamps/`; chỉ xoá phần còn lại và ghi danh sách ra `logs/deploy-backups/cleaned-<ts>.files`. Muốn tắt: `--no-clean` |
| `git checkout` ghi đè chính `deploy.sh` giữa lúc bash đang chạy → script đứt tay | Lần chạy đầu tự copy ra `/tmp/p096-deploy-*.sh` rồi `exec` bản sao (giữ nguyên PID/tham số) |
| Deploy hỏng làm service chết | Có health-check + tự lùi về commit tốt gần nhất (`logs/deploy-state`), rồi kiểm tra lại sức khỏe |

---

## 4. Tối ưu: bỏ những bước không cần

Bản cũ chạy **mọi** bước mỗi lần: `pip install` + `npm install` + build cả 2 app + reload pm2 + reload nginx
(kể cả khi chỉ sửa 1 file backend).

| Bước | Khi nào chạy ở bản mới |
|---|---|
| `pip install` | chỉ khi `requirements.txt` đổi (so sha256 trong `.deploy-stamps/`) hoặc chưa có `.venv` |
| `npm ci` | chỉ khi `frontend/package-lock.json` đổi hoặc chưa có `node_modules` |
| Build frontend | chỉ khi có file trong `frontend/apps/` hoặc `frontend/packages/` đổi, hoặc chưa có `dist` |
| Build app khách hàng | chỉ khi thêm `--all-apps` (nginx chỉ phục vụ app nội bộ) |
| `pm2 reload` | chỉ khi backend đổi (`src/`, `requirements.txt`, `run.py`) hoặc vừa cài deps |
| `nginx` | chỉ khi `deploy/p096.nginx.conf` đổi (và chỉ chạy nếu sudo không cần mật khẩu) |
| Cập nhật code | chỉ khi có commit mới (`git up --force` để bỏ qua kiểm tra) |

### 4.1 Mốc so sánh là **lần deploy thành công gần nhất**, không phải `HEAD`

`.deploy-state` (cụ thể `logs/deploy-state: current`) ghi commit đã deploy **thành công**. Script so
`current` với commit đích để biết cần chạy bước gì — vì code có thể đã về máy bằng đường khác:

* kéo tay `git pull` (không build, không reload),
* lần chạy script cũ,
* deploy hỏng dở dang rồi chạy lại.

Ví dụ thật: bạn `git pull` tay để lấy code mới rồi chạy `git up` — nếu script so với `HEAD` thì thấy
"không có gì đổi" và **bỏ qua build/reload**, để lại web chạy bundle cũ và backend chạy code cũ.
Từ bản này, script so với mốc deploy thành công nên vẫn build & reload đúng.

Thêm hai **lưới an toàn** khi mốc đã trùng commit đích nhưng thực tế vẫn chưa chạy:

| Kiểm tra | Khi nào kích hoạt |
| :--- | :--- |
| Mã nguồn frontend mới hơn `frontend/apps/internal/dist/index.html` | build lại |
| Mã nguồn backend (`src/*.py`, `requirements.txt`, `run.py`) mới hơn thời điểm tiến trình pm2 khởi động | reload pm2 |

Vì vậy `git up` chỉ thật sự im lặng khi mọi thứ đã đúng; nếu vẫn nghi ngờ, chạy `git up --force`.

Ngoài ra: `pip` và `npm ci` chạy **song song**; `pm2 reload` là zero-downtime; có khoá
`flock logs/.deploy.lock` để hai lần deploy không giẫm lên nhau; health-check dừng ngay khi
API trả lời (không chờ đủ timeout).

Thời gian điển hình: sửa 1 file frontend ≈ **1–2 phút**; chỉ sửa backend ≈ **10–20 giây**
(không tính thời gian cài deps khi requirements/lockfile đổi).

---

## 5. Cờ của `deploy.sh`

| Cờ | Ý nghĩa |
|---|---|
| `<branch>` | nhánh cần deploy (bỏ trống: nhớ nhánh lần deploy thành công trước, chưa có thì `develop`) |
| `--branch=<branch>` | tương đương |
| `--remote=<name>` | remote để lấy code, mặc định `origin` (cũng đặt được bằng `DEPLOY_REMOTE`) |
| `--dry-run`, `--check` | chỉ in kế hoạch, không thay đổi gì |
| `--force` | bỏ qua kiểm tra thay đổi: cập nhật code + build + reload dù commit không đổi |
| `--keep-local` | stash thay đổi cục bộ rồi trả lại sau khi cập nhật |
| `--no-clean` | không xoá file untracked |
| `--no-install` | bỏ qua `pip`/`npm ci` |
| `--no-build` | bỏ qua build frontend |
| `--all-apps` | build cả app khách hàng |
| `--no-pm2` | không reload pm2 (đồng thời bỏ qua health-check) — dùng cho dev box |
| `--no-nginx` | không đụng tới nginx |
| `--no-auto-rollback` | tắt tự lùi khi deploy hỏng |
| `--timeout=<giây>` | thời gian chờ health-check (mặc định 45) |
| `-h`, `--help` | trợ giúp |

Biến môi trường: `APP_PORT` (mặc định `8000`) cho health-check · `DEPLOY_BRANCH` · `DEPLOY_REMOTE`.

---

## 6. Lùi phiên bản

```bash
bash deploy/rollback.sh                 # về commit trong logs/deploy-state (prev=)
bash deploy/rollback.sh --to <sha>      # về commit chỉ định
bash deploy/rollback.sh --no-build      # chỉ đổi code, không build lại
```

Script chuyển code về commit cũ (detached HEAD), build lại frontend, reload pm2, kiểm tra
`/health`, rồi ghi lại `logs/deploy-state`: `current` = commit vừa lùi về, `prev` = commit **ngay trước nó**.
Nhờ vậy lùi liên tiếp luôn đi về quá khứ (`d92125a → 96e45b1 → 1ec9a76 → …`), không quay lại commit
vừa bỏ. Lần `git up` sau đó sẽ tự đưa repo về nhánh và lên commit mới nhất.

Khi deploy tự lùi (health-check fail sau lúc reload), log có dạng:

```
✗ Backend KHÔNG trả lời sau 45s (http://127.0.0.1:8000/health).
! Tự động lùi về commit tốt gần nhất (a1b2c3d4)...
✓ === Lùi phiên bản xong: a1b2c3d4 ===
```

---

## 7. File & log cần biết

| Đường dẫn | Nội dung |
|---|---|
| `logs/deploy.log` | toàn bộ log mọi lần deploy (kèm mốc thời gian) |
| `logs/deploy-state` | `branch/prev/current/at` — mốc để lùi phiên bản |
| `logs/deploy-backups/dirty-<ts>.patch` | bản sao thay đổi cục bộ trên server đã bị dọn |
| `logs/deploy-backups/cleaned-<ts>.files` | danh sách file untracked đã xoá |
| `.deploy-stamps/*.sha256` | dấu vết requirements/lockfile để bỏ qua bước cài deps |
| `deploy/ecosystem.config.cjs` | cấu hình pm2 cho `p096-backend` (uvicorn, port 8000, 2 workers) |
| `deploy/p096.nginx.conf` | cấu hình nginx (cài tại `/etc/nginx/sites-available/p096.conf`) |

---

## 8. Xử lý sự cố

| Hiện tượng | Việc cần làm |
|---|---|
| `error: Your local changes ... would be overwritten by merge` | Bản cũ còn sót: `git checkout -- .` rồi chạy lại — hoặc cài lại alias: `bash deploy/install-git-up.sh` |
| `Đang có tiến trình deploy khác chạy` | Đợi lần đang chạy xong (`tail -f logs/deploy.log`), tìm tiến trình: `ps aux \| grep deploy.sh` |
| `Backend KHÔNG trả lời` | `pm2 logs p096-backend --lines 80`, kiểm tra `curl -s localhost:8000/health`, `pm2 status` |
| Deploy hỏng, service vẫn phải chạy | Script tự lùi; nếu chưa: `bash deploy/rollback.sh --to <sha tốt>` |
| `Thiếu .venv/bin/python` | `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt` rồi `git up --force` |
| `Node ... quá cũ` | VM cần Node ≥ 20 (Vite 8). Kiểm tra `node -v`; cài lại Node 20/22 rồi deploy lại |
| `Ổ đĩa còn ...MB` | Dọn bớt: `npm cache clean --force`, `rm -rf frontend/apps/*/dist.bak`, xoá log cũ trong `logs/` |
| Nginx không được reload | Script chỉ đụng tới nginx khi config đổi **và** `sudo -n true` chạy được (không cần mật khẩu). Chạy tay lệnh in ra trong log |
| Muốn xem trước mọi thay đổi | `git up --dry-run` |
| `git up` deploy nhầm nhánh | Xem dòng `Nguồn :` đầu log. Đổi nhánh: `git up <nhánh>` (script nhớ luôn lần này) hoặc tạm thời `DEPLOY_BRANCH=<nhánh> git up` |
| `git up` báo "không có bước nào cần chạy" mà vừa đổi code | Kiểm tra code đã thật sự lên remote chưa: `git fetch origin develop && git log --oneline -3 HEAD origin/develop`. Nếu `HEAD` == `origin/develop` thì bản trên máy đã là mới nhất — có thể bạn đã push sang **repo/nhánh khác** với remote của VM. Nghi ngờ build/reload chưa chạy thì dùng `git up --force` |

---

## 9. Ghi chú

* Alias được lưu ở `~/.gitconfig` (`alias.up`); script cài đặt tự sao lưu `~/.gitconfig.bak-<ts>`.
  Đổi vị trí repo thì chạy lại `bash deploy/install-git-up.sh --dir <đường dẫn mới>`.
* `git up <nhánh>` tương đương `bash deploy/deploy.sh <nhánh>`; mọi cờ của script đều dùng được qua alias
  (`git up --force`, `git up develop --dry-run`, …).
* Deploy chỉ tác động trong thư mục repo + pm2/nginx; **không** chạm vào `data/`, `logs/` (trừ file log của chính nó),
  `.env` và `.venv`.
* Script deploy được CI kiểm tra cú pháp + `shellcheck` (job `deploy-scripts` trong `.github/workflows/ci.yml`).
* Chạy định kỳ (cron) cũng được, ví dụ 5 phút một lần:
  `*/5 * * * * cd /home/ubuntu/vland && bash deploy/deploy.sh >> logs/cron-deploy.log 2>&1`
  (khi không có commit mới, script chỉ kiểm tra dịch vụ rồi thoát).
