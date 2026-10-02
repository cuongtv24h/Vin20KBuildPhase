/**
 * Relay cho nhà cung cấp LLM bị Cloudflare chặn theo IP máy chủ.
 *
 * Vì sao cần: máy chủ PricePolicy (EC2 `18.140.199.175`) bị Cloudflare Bot Fight Mode "challenge" —
 * trả trang "Just a moment..." cho MỌI request không phải trình duyệt thật, kể cả khi đã đổi User-Agent.
 * Trong khi đó ứng dụng chạy trên Vercel gọi cùng nhà cung cấp lại không bị chặn. Relay này biến Vercel
 * (hạ tầng bạn đã có và đã chứng minh là gọi được) thành đường đi hợp lệ cho máy chủ — thay vì phải chờ
 * nhà cung cấp allowlist IP.
 *
 * Cách dùng (xem README.md cùng thư mục):
 *   Base URL trong màn hình Nhà cung cấp LLM =
 *     https://<app>.vercel.app/api/llm-relay/<LLM_RELAY_TOKEN>/v1
 *
 * Nguyên tắc an toàn:
 *  1. KHÔNG mở relay công khai: mọi request phải kèm token trong đường dẫn (backend hiện chưa hỗ trợ
 *     header riêng cho từng nhà cung cấp nên token phải nằm trong Base URL).
 *  2. CHỈ chuyển tiếp tới đúng `LLM_RELAY_UPSTREAM` đã cấu hình — không nhận host/path tuỳ ý, tránh
 *     biến relay thành proxy mở cho toàn Internet.
 *  3. Relay KHÔNG lưu API key: khoá đi thẳng từ máy chủ PricePolicy tới nhà cung cấp qua Vercel.
 */

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
// Vercel Hobby mặc định 10 giây/hàm; đặt cao hơn nếu gói của bạn cho phép (Pro: tới 60s+).
export const maxDuration = 60;

const UPSTREAM = (process.env.LLM_RELAY_UPSTREAM ?? "").replace(/\/+$/, "");
const TOKEN = process.env.LLM_RELAY_TOKEN ?? "";
/** Chỉ chuyển tiếp những header cần thiết — không forward cookie/header lạ của client. */
const FORWARD_HEADERS = ["authorization", "accept", "content-type"];

type Ctx = { params: Promise<{ path: string[] }> | { path: string[] } };

function json(status: number, payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

async function forward(req: Request, ctx: Ctx): Promise<Response> {
  const { path } = await Promise.resolve(ctx.params);
  if (!UPSTREAM) return json(500, { error: "Relay chưa cấu hình LLM_RELAY_UPSTREAM." });
  if (!TOKEN) return json(500, { error: "Relay chưa cấu hình LLM_RELAY_TOKEN." });

  const [token, ...rest] = path;
  if (token !== TOKEN) return json(401, { error: "Sai token relay." });
  if (rest.length === 0) return json(404, { error: "Thiếu đường dẫn upstream." });

  const headers = new Headers();
  for (const name of FORWARD_HEADERS) {
    const value = req.headers.get(name);
    if (value) headers.set(name, value);
  }

  const method = req.method.toUpperCase();
  const body = method === "GET" || method === "HEAD" ? undefined : await req.text();

  let upstream: Response;
  try {
    upstream = await fetch(`${UPSTREAM}/${rest.join("/")}`, {
      method,
      headers,
      body,
      cache: "no-store",
      redirect: "follow",
    });
  } catch (error) {
    return json(502, { error: `Relay không gọi được nhà cung cấp: ${String(error)}` });
  }

  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "content-type": upstream.headers.get("content-type") ?? "application/json",
      "x-relay-upstream-status": String(upstream.status),
    },
  });
}

export async function GET(req: Request, ctx: Ctx): Promise<Response> {
  return forward(req, ctx);
}

export async function POST(req: Request, ctx: Ctx): Promise<Response> {
  return forward(req, ctx);
}

export async function OPTIONS(): Promise<Response> {
  return new Response(null, { status: 204 });
}
