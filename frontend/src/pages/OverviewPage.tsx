import {
  ArrowRight,
  BadgeCheck,
  FileSearch,
  FileStack,
  Gauge,
  Scale,
  ShieldCheck,
  Sparkles,
  Target,
  UserCog,
  UserCheck,
  Users,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'

const CHAIN_LINKS = [
  { title: 'Tiếp nhận Chính sách', desc: 'Nạp và giải mã văn bản chính sách bán hàng chính thức.' },
  { title: 'Tra cứu Ngày Giao dịch', desc: 'Time-Travel định vị đúng phiên bản chính sách hiệu lực.' },
  { title: 'Cửa kiểm soát Xung đột', desc: 'Chặn cộng dồn ưu đãi cấm hoặc mâu thuẫn điều khoản.' },
  { title: 'Tính Số học Tuyệt đối', desc: 'Chuyển giao toàn bộ phép tính cho công cụ tất định.' },
  { title: 'Khớp Mục tiêu Khách hàng', desc: 'So sánh phương án bám sát tiêu chí khách chọn.' },
  { title: 'Kiểm chứng Lý do Loại trừ', desc: 'Trích dẫn điều khoản giải trình vì sao không áp dụng.' },
  { title: 'Quản lý Phê duyệt', desc: 'Cờ cảnh báo rủi ro, quyền quyết định thuộc về con người.' },
  { title: 'Đóng gói Hồ sơ Bất biến', desc: 'Khoá chứng cứ bằng mã băm SHA-256 phục vụ kiểm toán.' },
]

const CORE_LOOP = [
  { key: 'UNDERSTAND', label: 'Hiểu ngữ cảnh', icon: FileSearch },
  { key: 'DECIDE', label: 'Đánh giá điều kiện', icon: Scale },
  { key: 'COMPARE', label: 'So sánh phương án', icon: Gauge },
  { key: 'EXPLAIN', label: 'Giải trình hai chiều', icon: FileStack },
  { key: 'APPROVE', label: 'Phê duyệt HITL', icon: ShieldCheck },
]

const PERSONAS = [
  {
    icon: Users,
    name: 'Hoàng Nam',
    role: 'Sales Executive',
    goal: 'Lập phương án tài chính chuẩn xác trong 10 giây, tự tin thuyết phục khách chốt cọc.',
    pain: 'Chính sách đổi liên tục, sợ tính nhẩm sai, không giải thích được vì sao ưu đãi bị loại trừ.',
  },
  {
    icon: UserCheck,
    name: 'Hà Nguyễn',
    role: 'Sales Manager',
    goal: 'Duyệt báo giá trong 45 giây nhờ cờ cảnh báo rủi ro rõ ràng, kiểm soát 100% hồ sơ phát hành.',
    pain: 'Duyệt giá qua tin nhắn lộn xộn, không có chứng từ lưu vết để giải trình khi bị kiểm toán.',
  },
  {
    icon: UserCog,
    name: 'Tuấn Minh',
    role: 'Policy Admin',
    goal: 'Ban hành chính sách mới đồng bộ toàn mạng lưới, đảm bảo công thức khớp 100% chuẩn kế toán.',
    pain: 'Chính sách vừa ban hành đã bị áp dụng sai, không có công cụ kiểm thử công thức tự động.',
  },
]

export function OverviewPage() {
  return (
    <div className="space-y-14">
      <section className="grid grid-cols-1 gap-8 lg:grid-cols-[1.2fr,1fr] lg:items-center">
        <div className="space-y-5">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-primary/25 bg-primary/5 px-3 py-1 text-xs font-medium text-primary">
            <Sparkles className="h-3.5 w-3.5" /> Frontend Demo — Dữ liệu mock
          </span>
          <h1 className="font-display text-4xl font-semibold leading-[1.08] tracking-tight text-foreground sm:text-5xl">
            Tầng bảo chứng niềm tin cho định giá bất động sản VLandFuture
          </h1>
          <p className="max-w-xl text-base leading-relaxed text-muted-foreground">
            PricePolicy AI Agent tách biệt tuyệt đối giữa suy luận chính sách và tính toán tài chính: AI đọc hiểu
            điều khoản, phát hiện xung đột và điều phối quy trình; mọi phép tính VNĐ được uỷ thác cho công cụ số học
            tất định, và quyền phát hành cuối cùng luôn thuộc về Quản lý bán hàng.
          </p>
          <div className="flex flex-wrap gap-3 pt-1">
            <Button asChild size="lg">
              <Link to="/sales">
                Vào Sales Copilot <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
            <Button asChild size="lg" variant="outline">
              <Link to="/demo">Xem 6 kịch bản diễn tập</Link>
            </Button>
          </div>
        </div>

        <Card className="border-l-4 border-l-gold bg-primary text-primary-foreground">
          <CardContent className="space-y-2.5 p-6">
            <p className="inline-flex items-center gap-1.5 text-xs font-medium text-primary-foreground/70">
              <Target className="h-3.5 w-3.5" /> North Star Metric
            </p>
            <p className="font-display text-xl italic leading-snug">
              "Tỷ lệ giao dịch báo giá hợp lệ, đầy đủ căn cứ trích dẫn và được phê duyệt thành công trong dưới 60
              giây."
            </p>
            <div className="grid grid-cols-3 gap-3 pt-3 text-primary-foreground/90">
              <div>
                <p className="font-display text-2xl font-semibold tabular-nums">100%</p>
                <p className="text-[11px] text-primary-foreground/60">Exact Match công thức</p>
              </div>
              <div>
                <p className="font-display text-2xl font-semibold tabular-nums">≤45s</p>
                <p className="text-[11px] text-primary-foreground/60">Thời gian duyệt giá</p>
              </div>
              <div>
                <p className="font-display text-2xl font-semibold tabular-nums">2–6%</p>
                <p className="text-[11px] text-primary-foreground/60">Biên lợi nhuận bảo toàn</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </section>

      <section>
        <div className="mb-5 flex items-baseline justify-between gap-3">
          <h2 className="font-display text-2xl font-semibold tracking-tight">Chuỗi 8 mắt xích rào chắn nghiệp vụ</h2>
          <p className="hidden text-sm text-muted-foreground sm:block">Policy → Eligibility → Conflict → … → Audit</p>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {CHAIN_LINKS.map((link, idx) => (
            <div key={link.title} className="relative rounded-lg border border-border bg-card p-4">
              <div className="mb-2 flex h-7 w-7 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
                {idx + 1}
              </div>
              <p className="text-sm font-semibold leading-tight">{link.title}</p>
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{link.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="mb-5 font-display text-2xl font-semibold tracking-tight">
          Core Product Loop
        </h2>
        <div className="flex flex-wrap items-center gap-2">
          {CORE_LOOP.map((step, idx) => (
            <div key={step.key} className="flex items-center gap-2">
              <div className="flex items-center gap-2 rounded-full border border-border bg-card px-4 py-2">
                <step.icon className="h-4 w-4 text-primary" />
                <span className="text-sm font-medium">{step.label}</span>
              </div>
              {idx < CORE_LOOP.length - 1 && <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground" />}
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="mb-5 font-display text-2xl font-semibold tracking-tight">Ba chân dung người dùng</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {PERSONAS.map((p) => (
            <Card key={p.role}>
              <CardContent className="space-y-3 p-5">
                <div className="flex items-center gap-2.5">
                  <span className="flex h-9 w-9 items-center justify-center rounded-full bg-secondary text-secondary-foreground">
                    <p.icon className="h-4 w-4" />
                  </span>
                  <div>
                    <p className="text-sm font-semibold leading-tight">{p.name}</p>
                    <p className="text-xs text-muted-foreground">{p.role}</p>
                  </div>
                </div>
                <div className="space-y-1.5 text-xs leading-relaxed">
                  <p>
                    <span className="inline-flex items-center gap-1 font-medium text-foreground">
                      <BadgeCheck className="h-3 w-3 text-success" /> Mục tiêu
                    </span>{' '}
                    <span className="text-muted-foreground">{p.goal}</span>
                  </p>
                  <p>
                    <span className="font-medium text-foreground">Nỗi đau:</span>{' '}
                    <span className="text-muted-foreground">{p.pain}</span>
                  </p>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>
    </div>
  )
}
