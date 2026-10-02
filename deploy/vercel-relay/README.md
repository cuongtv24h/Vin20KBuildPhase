# Relay trên Vercel cho nhà cung cấp LLM bị Cloudflare chặn theo IP

## Khi nào dùng

Máy chủ PricePolicy gọi nhà cung cấp thì bị Cloudflare trả trang `"Just a moment..."` (HTTP 403), trong khi
ứng dụng chạy trên Vercel gọi **cùng nhà cung cấp đó** lại bình thường. Nút **Test kết nối** đã tự kiểm tra
hai kiểu header (ứng dụng và trình duyệt) và báo: *đã thử cả hai đều bị chặn* — nghĩa là chặn ở tầng IP/hạ tầng,
không sửa được bằng header ở phía máy chủ.

Relay này dùng chính hạ tầng Vercel (nơi đã chứng minh là gọi được) làm đường đi cho máy chủ. Khoá API **không**
bị lưu ở relay; nó chỉ đi qua theo từng request.

> ⚠️ **Chỉ có tác dụng nếu Vercel của bạn gọi nhà cung cấp này từ phía server** (serverless/edge function) mà
> không bị chặn. Nếu ứng dụng Vercel của bạn đang gọi **từ trình duyệt** thì IP đó là IP của người dùng — relay
> serverless có thể vẫn bị chặn (xem phần "Kiểm tra trước khi làm" bên dưới). Khi đó chỉ còn cách nhờ nhà cung
> cấp allowlist IP máy chủ.

## Kiểm tra trước khi làm (1 phút, trên VM)

Chạy đúng lệnh này **trên máy chủ** để biết bị chặn ở tầng nào (không cần API key thật):

```bash
curl -sS -o /tmp/cf.txt -w 'HTTP %{http_code}\n' -X POST https://codecraftapi.com/v1/chat/completions \
  -H 'Authorization: Bearer test-key' -H 'Content-Type: application/json' \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"ping"}],"max_tokens":1}'
head -c 200 /tmp/cf.txt; echo
```

| Kết quả | Nghĩa là | Việc cần làm |
| :--- | :--- | :--- |
| `HTTP 401` + JSON | Cloudflare **cho qua**; khác biệt nằm ở "dấu vân tay" client (Python/httpx) chứ không phải IP | Báo lại để xử lý ở phía mã (dùng client mang vân tay khác) — **chưa cần relay** |
| `HTTP 403` + HTML "Just a moment" | Chặn theo IP/hạ tầng | Relay dưới đây (nếu Vercel server-side gọi được), hoặc nhờ nhà cung cấp allowlist IP |

Đối chiếu thêm: chạy cùng lệnh đó **từ laptop ở nhà** — nếu qua được, xác nhận IP dân dụng/khác dải thì qua,
còn IP datacenter (EC2 Singapore) thì bị chặn.

## Cách triển khai (khoảng 5 phút, trên Vercel bạn đã có)

1. **Copy file** `app/api/llm-relay/[...path]/route.ts` (trong thư mục này) vào đúng đường dẫn đó trong ứng
   dụng Next.js (App Router) đang chạy trên Vercel. Nếu app của bạn không phải Next.js, xem mục "Biến thể" bên dưới.
2. **Đặt 2 biến môi trường** trong Vercel → Project → Settings → Environment Variables:
   * `LLM_RELAY_UPSTREAM` = `https://codecraftapi.com/v1`
   * `LLM_RELAY_TOKEN` = một chuỗi ngẫu nhiên ≥ 24 ký tự (ví dụ `openssl rand -hex 24`)
3. **Deploy** (push lên Vercel như bình thường).
4. **Thử relay** từ máy chủ (thay `<app>` và `<TOKEN>`):
   ```bash
   curl -sS -o - -w '\nHTTP %{http_code}\n' https://<app>.vercel.app/api/llm-relay/<TOKEN>/v1/models \
     -H 'Authorization: Bearer test-key'
   ```
   * Thấy JSON của nhà cung cấp (ví dụ `missing_api_key`) ⇒ relay thông.
   * Thấy HTML "Just a moment" ⇒ hạ tầng Vercel cũng bị chặn; dừng lại, chuyển sang nhờ nhà cung cấp allowlist IP.
   * `HTTP 401` + `Sai token relay` ⇒ token trong URL khác `LLM_RELAY_TOKEN` (hoặc chưa deploy lại sau khi thêm biến).
5. **Khai báo trong PricePolicy** → Quản trị → Nhà cung cấp LLM → sửa nhà cung cấp đó:
   * **Base URL** = `https://<app>.vercel.app/api/llm-relay/<TOKEN>/v1`
   * **API key**: giữ nguyên khoá của nhà cung cấp (để trống nếu muốn giữ khoá cũ)
   * Bấm **Lưu thay đổi** → **Test kết nối** ⇒ kỳ vọng xanh, ghi rõ đã kết nối qua đường nào.

## Vì sao làm vậy là chấp nhận được

* Relay nằm trên **hạ tầng của chính bạn** (tài khoản Vercel của bạn) — không phải proxy công cộng của bên thứ ba.
* Khoá API vẫn đi qua HTTPS tới Vercel rồi tới nhà cung cấp; relay **không ghi log, không lưu** khoá.
* Token trong URL chỉ dùng để chặn người lạ lạm dụng relay (đổi bằng cách sửa `LLM_RELAY_TOKEN` + cập nhật Base URL).
* Host đích bị **ghim cứng** bằng `LLM_RELAY_UPSTREAM`, không nhận host tuỳ ý ⇒ không thành proxy mở.

## Giới hạn cần biết trước

1. **Thêm một chặng mạng**: độ trễ tăng ~50–200 ms mỗi lượt (Vercel → nhà cung cấp). Chỉ ảnh hưởng nhà cung
   cấp dùng relay.
2. **Giới hạn thời gian hàm**: Vercel Hobby cắt hàm sau ~10 giây. Câu trả lời dài có thể bị cắt — nâng
   `maxDuration` nếu gói cho phép, hoặc chỉ dùng relay cho tác vụ ngắn. Luồng Copilot hiện gọi không streaming.
3. **Vẫn là giải pháp tạm**: nếu nhà cung cấp bổ sung allowlist IP cho máy chủ, nên quay lại Base URL gốc
   (một dòng trong màn hình quản trị, không cần deploy).
4. **Kiểm tra định kỳ**: nếu một ngày relay trả 403 kèm HTML challenge, chính IP Vercel cũng đã bị chặn → cần
   phương án khác (allowlist, endpoint riêng của nhà cung cấp, hoặc proxy riêng có kiểm soát).

## Biến thể: không dùng Next.js

Nếu app Vercel của bạn không phải Next.js, có thể tạo project nhỏ chỉ để làm relay với Node serverless:

* `api/llm-relay.ts` export `export default async function handler(req, res)` — đọc `req.query.path`, ghép
  `LLM_RELAY_UPSTREAM`, gọi `fetch`, rồi `res.status(upstream.status).send(await upstream.text())`.
* Hoặc dùng `vercel.json` với `rewrites` chuyển `/api/llm-relay/:token/:path*` sang hàm đó.

Giữ nguyên ba nguyên tắc ở đầu file `route.ts`: kiểm tra token, ghim host đích, không lưu khoá.
