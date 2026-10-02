# Tối ưu câu trả lời của Agent — phân tích sâu & kế hoạch

**Trạng thái: P0 · P1 · P2 · P3 đã triển khai xong (2026-10-02 theo chốt thiết kế của người dùng).**
Bản ghi chuẩn của đợt này: `docs/team_report/upgrade_new.md` §16. Danh sách câu hỏi ở §8 đã được trả lời
và chuyển thành quyết định thiết kế — xem §16.3–§16.5 để biết từng điểm đã làm gì.

Người dùng chốt phạm vi: *"tôi muốn nói về độ rõ ràng và văn phong hợp lý khi trả lời, làm P0 đi"*.
P0 = dọn các cảnh báo xếp chồng và sửa văn phong trả lời — **không** đổi nội dung nghiệp vụ (phần đó là P1/P2/P3).

## 0. P0 đã làm gì — trước/sau trên đúng ví dụ của người dùng

Chạy thật `_finalize` với câu trả lời y nguyên trong ví dụ:

| | Trước P0 | Sau P0 |
|---|---|---|
| Số dòng cảnh báo cuối câu | **3** (`Lưu ý` verifier + `Lưu ý` grounded + `Kiểm duyệt nội bộ` critic) | **0** |
| `grounded` | `False` (báo động giả) | `True` |
| `verified` | `False` (vì "2 tỷ", "2,5 tỷ", "6,1 tỷ") | `True` — "2 tỷ" là số Sale nêu, "2,5/6,1 tỷ" là dải giá canonical |
| `critique.ok` | `False` (đòi mỏ neo [n] dù không có chứng cứ nào) | `True` |
| Nội dung gửi khách | có chen câu quy trình nội bộ | sạch, chỉ còn nội dung tư vấn |

**4 thay đổi mã nguồn:**

| # | File | Thay đổi |
|---|---|---|
| P0.1 | `src/agents/copilot/graph.py` | `grounded` = có citation **hoặc** tool tra cứu chính sách/giỏ hàng (`tra_cuu_chinh_sach`, `tra_cuu_gio_hang`, `tinh_phuong_an_thanh_toan`) chạy thành công — kết luận "0 căn khớp" cũng là dữ liệu, không phải "chưa đối chiếu" |
| P0.2 | `src/agents/copilot/verifier.py` | Tha số **do Sale nêu trong câu hỏi** (`echoed_claims`) và số/mã **có trong bối cảnh canonical** (`context_claims`); số không ai nói vẫn bị bắt |
| P0.3 | `src/agents/copilot/critic.py` | Chỉ nhắc "gắn mỏ neo [n]" khi lượt đó **có** citation để trỏ tới; gọi trực tiếp không truyền observation thì giữ luật chặt (tương thích ngược) |
| P0.4 | `src/agents/copilot/graph.py` | Mọi cảnh báo gộp vào **tối đa MỘT** khối `Ghi chú nội bộ:`; ghi chú kiểm duyệt **không** chèn vào nội dung trả lời (đã có banner riêng trên UI từ dữ liệu `critique`) |
| P0.5 | `src/agents/copilot/prompts.py` | Luật văn phong: mở đầu bằng kết luận; nêu rõ **phạm vi** của mọi số liệu phân khúc (cấm ghép "N căn toàn giỏ" với nhãn "3 ngủ"); hỏi lại tối đa 2 câu có đánh số; không viết câu quy trình nội bộ. Tách `canonical_facts()` để verifier biết đâu là số liệu hệ thống — **cố ý không** gồm `avoid_examples` (do LLM tổng hợp từ phản hồi) |

**Bằng chứng chạy thật:** `.venv/bin/python -m pytest -q` → **572 passed** (thêm 16 ca mới trong
`tests/test_agents/copilot/test_copilot_answer_clarity.py`); `ruff check src/ tests/` sạch;
`scripts/run_copilot_eval.py` → tool 100% · citation 100% · **bịa 0.0%** (không hồi quy bộ 32 câu vàng).

**Khoảng trống đã biết (nói thẳng):** ghi chú kiểm duyệt chỉ hiện khi lượt trả lời đang mở; mở lại lịch sử
thì mất vì hội thoại chỉ lưu `reply` + `citations`. Muốn giữ lâu cần thêm trường vào bản ghi lượt (backend).
Đây là việc nhỏ nhưng **chưa làm** — nằm trong danh sách câu hỏi (§8, câu P2.4).

**Chưa đo được trong sandbox:** thay đổi prompt (P0.5) chỉ đo được ở chế độ `llm` (cần API key + egress).
Bộ eval hiện chạy offline. Cần một vòng bấm tay trên VM để xác nhận văn phong.

Ví dụ người dùng đưa (đối tượng phân tích):

> **Câu hỏi:** "Khách hàng có 2 tỷ, cần mua căn 3 ngủ"
>
> **Trả lời hiện tại:** (kết luận "chưa có căn nào phù hợp" + 3 dòng *Lưu ý* xếp chồng)
>
> **Trả lời mong muốn:** (giữ nguyên thông tin, nhưng gắn mỏ neo `[1]…[5]`, câu hỏi làm rõ đánh số 1–2,
> khối "Ghi chú kiểm duyệt nội bộ" gọn lại)

---

## 1. Câu trả lời được sinh ra thế nào (đường đi thật, kèm số dòng)

Từ `src/agents/copilot/graph.py` — một câu trả lời đi qua **6 tầng**, và tầng 4–6 là các tầng **tự động
thêm chữ vào câu trả lời**, không phải LLM viết:

| Tầng | Ở đâu | Việc nó làm với câu trả lời |
|---|---|---|
| 1. Planner tất định | `planner.py` | Tách mệnh đề → chọn tool (`smart_units_browse` → `tra_cuu_gio_hang`) |
| 2. ReAct loop (LLM + tool) | `graph.py` L500–560 | Gọi tool, nhận Observation, viết câu trả lời |
| 3. Bối cảnh nhét vào prompt | `prompts.py` L90 | "Giỏ hàng canonical: **4 căn** đang mở bán, giá niêm yết trước thuế từ **2.500.000.000 ₫** đến **6.100.000.000 ₫**" |
| 4. Verifier | `graph.py` L250–258 | Nếu câu trả lời có số không nằm trong Observation → **append** dòng "Lưu ý: có số liệu chưa đối chiếu được…" |
| 5. Cờ `grounded` | `graph.py` L242, L260–261 | `grounded = bool(citations)` → nếu không có citation → **append** dòng "Lưu ý: câu trả lời này chưa đối chiếu được với dữ liệu chính sách/giỏ hàng…" |
| 6. Critic vòng 2 | `graph.py` L264–270, `critic.py` L82 | Nếu có số tiền mà không có mỏ neo `[n]` → **append** dòng "Kiểm duyệt nội bộ: Gắn mỏ neo [n] cho từng con số…" |

⇒ **Cả 3 dòng "Lưu ý" người dùng thấy đều do tầng tất định sinh ra, không phải LLM "nói linh tinh".**
Đây là tin tốt: sửa được, rẻ, và viết test được — không cần đổi model.

## 2. Truy vết từng dòng "Lưu ý" — dòng nào đúng, dòng nào là báo động giả

Chạy thật trong sandbox (`.venv/bin/python`, dữ liệu canonical hiện có 4 căn đang mở bán):

**(a) Dòng "có số liệu chưa đối chiếu được với dữ liệu hệ thống (2 tỷ, 2,5 tỷ, 6,1 tỷ)"** — verifier.

Đúng về mặt cơ chế, nhưng **vô nghĩa về mặt nghiệp vụ**, vì observation của lần lọc `3PN + ≤2 tỷ`
là **rỗng** (`summary = "Không còn căn nào phù hợp tiêu chí…"`, `citations = []`). Đã đo:

```
Observation khi lọc 3PN ≤ 2 tỷ : summary rỗng, 0 citation
Verifier đối chiếu CHỈ observation đã lọc : verified=False  unsupported=['2 tỷ', '2,5 tỷ', '6,1 tỷ']
```

Câu trả lời **buộc phải** nhắc tới giỏ hàng để giải thích vì sao không có căn nào — nhưng vì tool lọc
chặt đã trả về rỗng nên **không còn nguồn nào** cho chính những con số dùng để giải thích. Verifier
không sai; **dữ liệu đầu vào cho verifier bị thiếu**.

**(b) Dòng "câu trả lời này chưa đối chiếu được với dữ liệu chính sách/giỏ hàng"** — **LỖI THẬT (báo động giả).**

`graph.py` L242: `grounded = bool(citations) or intent == small_talk`. Lần lọc này tool chạy **thành công**
(`ok=true`, không lỗi), chỉ là kết quả rỗng nên `citations=[]` ⇒ hệ thống tự buộc tội mình "chưa đối chiếu
dữ liệu" **trong khi dữ liệu đã được đối chiếu và kết quả chính là "0 căn"**. Chạy offline cũng ra y hệt:

```
[final] reply: "Không còn căn nào phù hợp tiêu chí…\n\n_Lưu ý: câu trả lời này chưa đối chiếu được
với dữ liệu chính sách/giỏ hàng — anh/chị kiểm tra lại giúp em._"      grounded=false
```

Sửa đúng: `grounded` phải là *"đã gọi tool tra cứu và tool trả ok"*, không phải *"có citation"*.

**(c) Dòng "Kiểm duyệt nội bộ: Gắn mỏ neo [n] cho từng con số…"** — critic, **đúng luật nhưng không hành động được**.

`critic.py` L80–85 chỉ kiểm `_MONEY_RE` có số tiền mà không thấy `_ANCHOR_RE` ⇒ cảnh báo. Nhưng vì lượt
này **không có citation nào** thì Sale **không có gì để gắn mỏ neo** — nhắc vậy chỉ làm người đọc mất niềm tin.

⇒ Kết luận mục 2: 1 cảnh báo **sai** (grounded), 1 cảnh báo **không thể hành động** (critic), 1 cảnh báo
**hệ quả** (verifier). Ba dòng xếp chồng = câu trả lời trông "hỏng" dù logic nghiệp vụ không sai.

## 3. Đối chiếu bản hiện tại vs bản mong muốn — và hai lỗi dữ liệu cần nói thẳng

| Tiêu chí | Bản hiện tại | Bản mong muốn |
|---|---|---|
| Kết luận | "chưa có căn nào phù hợp" | như cũ |
| Số liệu thị trường | "giỏ đang mở bán có **4 căn**, giá **2,5 → 6,1 tỷ**" | "các căn **3 ngủ** đang mở bán (**4 căn**) có tầm giá **2,5 → 6,1 tỷ**" |
| Mỏ neo `[n]` | không có → bị critic nhắc | có `[1]…[5]` |
| Câu hỏi làm rõ | 1 đoạn văn | danh sách 1–2 |
| Ghi chú cuối | 3 dòng *Lưu ý* + banner cam | 1 khối "Ghi chú kiểm duyệt nội bộ" gọn |

**Lỗi dữ liệu #1 — "4 căn 3 ngủ" là SAI.** Giỏ canonical hiện có **4 căn tổng cộng**, trong đó
**chỉ 1 căn 3PN**:

```
ZEN-A-0803   1PN   2.500.000.000 ₫
ZEN-A-1205   2PN   4.200.000.000 ₫
SAP-01-2204  2PN   5.800.000.000 ₫
ZEN-B-1502   3PN   6.100.000.000 ₫   ← 3PN duy nhất
lọc 3PN: 1 căn   |   lọc 3PN ≤ 2 tỷ: 0 căn
```

Con số "4 căn" là **tổng giỏ**; LLM ghép "4 căn" với ngữ cảnh "3 phòng ngủ" thành "4 căn 3 ngủ".
Bản mong muốn **gán hẳn nhãn đó cho phân khúc 3PN** ⇒ nặng hơn bản hiện tại: bản hiện tại nói "giỏ có
4 căn" (đúng), bản mong muốn nói "căn 3 ngủ có 4 căn" (sai). Tương tự, dải giá **2,5 → 6,1 tỷ là dải của
cả giỏ**, không phải của 3PN (3PN chỉ có 6,1 tỷ).

⇒ **Nếu chỉ sửa hình thức (đánh số mỏ neo + bỏ cảnh báo) mà không sửa nguồn số, thì lỗi vẫn còn, chỉ là
lỗi trông chuyên nghiệp hơn.** Đây là điều tôi phải nói rõ trước khi bắt tay vào phần trình bày.

**Lỗi dữ liệu #2 — mỏ neo `[1]` và `[5]` cùng trỏ "2 tỷ".** Số 2 tỷ là **do Sale nêu trong câu hỏi**,
không phải dữ liệu hệ thống. Mỏ neo (theo đúng nghĩa đang dùng: `[CSBH-ZEN-2026-V3.1 · Điều 4]`, `[FSC v2.6]`)
là **con trỏ tới nguồn**. Gắn mỏ neo cho số do người dùng nhập là **sai ngữ nghĩa** và làm loãng khái niệm
mỏ neo. Đề xuất: phân biệt rõ hai loại số — *số hệ thống* (có mỏ neo, bấm mở được căn cứ) và *số do
người dùng nêu* (in đậm, **không** mỏ neo).

## 4. Giá trị lớn nhất đang bị bỏ mất: engine đã trả lời được câu hỏi thật, nhưng planner không gọi

Chạy thật `tinh_phuong_an_thanh_toan` cho căn 3PN duy nhất với **2 tỷ = vốn tự có**:

```
PA-VAY (Vay 70%, hỗ trợ lãi suất):  giá Net 6.100.000.000 ₫ · tổng HĐMB 6.832.000.000 ₫
                                    đợt đầu 1.006.500.000 ₫ · tổng tự chi đến nhận nhà 2.171.600.000 ₫
                                    ưu đãi 305.000.000 ₫ · khả thi: có      → đề xuất tối ưu: PA-VAY
```

⇒ Với 2 tỷ, khách **vào được** căn 3PN 6,1 tỷ qua PA-VAY: đợt đầu ~**1,0065 tỷ**, tổng tự chi tới nhận nhà
~**2,1716 tỷ** — tức **hụt ~172 triệu** so với 2 tỷ. Đây là câu trả lời Sale cần ("gần được, thiếu bao
nhiêu, đi đường nào"), có đủ số liệu, có sanity kế toán, và **hoàn toàn tất định**.

Nhưng planner dừng ở bước 1: `plan = [smart_units_browse → tra_cuu_gio_hang]`, tool trả rỗng ⇒ hết.
Nguyên nhân cấu trúc: **không có luật "kết quả rỗng thì nới tiêu chí và đi tiếp"**, và
`tra_cuu_gio_hang` (tools.py L208–209) khi rỗng chỉ trả đúng một câu "Không còn căn nào phù hợp tiêu chí"
⇒ **mất toàn bộ thông tin phễu** (khớp 0/1, căn gần nhất, thiếu bao nhiêu).

## 5. Kế hoạch tối ưu — 4 nhóm, xếp theo (giá trị ÷ rủi ro)

### P0 — Sửa sai & dọn cảnh báo (nhỏ, rẻ, có test ngay)

| # | Việc | File/dòng | Kết quả |
|---|---|---|---|
| P0.1 | `grounded` = "đã gọi tool tra cứu & tool ok", không phải `bool(citations)` | `graph.py` L242 | Hết báo động giả "chưa đối chiếu" khi tool chạy đúng mà rỗng |
| P0.2 | Truyền **câu hỏi của Sale** vào `_finalize`; verifier bỏ qua số **đã có trong câu hỏi** (echo), chỉ bắt số *tự nghĩ ra* | `graph.py` L194 (chữ ký `_finalize`), L510/L562/L611 (3 chỗ gọi), `verifier.py` | "2 tỷ" không còn bị coi là số bịa |
| P0.3 | Critic chỉ nhắc mỏ neo khi **có nguồn để gắn** (`citations > 0`) | `critic.py` L80–85 + `graph.py` L264 | Hết lời nhắc không hành động được |
| P0.4 | Gộp 3 dòng cảnh báo thành **tối đa 1 khối**, có mức độ (thông tin / cần kiểm) | `graph.py` L250–270 | Câu trả lời không còn "3 dòng Lưu ý" |

### P1 — Biến "không có gì" thành "có việc để làm" (giá trị cao nhất)

| # | Việc | Chi tiết |
|---|---|---|
| P1.1 | `tra_cuu_gio_hang` trả **phễu**: khớp đúng bao nhiêu, tổng giỏ bao nhiêu, **số căn theo từng số phòng ngủ**, dải giá **theo từng phân khúc** | Nguồn chính danh cho "1 căn 3PN · 6,1 tỷ" và "toàn giỏ 4 căn · 2,5–6,1 tỷ" — nhãn phân khúc do tool ghi, LLM chỉ diễn đạt |
| P1.2 | Khi lọc rỗng: trả **thang nới tiêu chí** (bỏ trần giá → cùng số PN; đổi 3PN→2PN; toàn giỏ) kèm **khoảng cách giá** | "Căn 3PN gần nhất 6,1 tỷ — thiếu 4,1 tỷ so với trần 2 tỷ" |
| P1.3 | Planner: **kết quả rỗng ⇒ tự nới 1 nấc rồi tính phương án tài chính** với ngân sách Sale nêu (coi là vốn tự có) | Trong hạn mức 4 tool/lượt đã có sẵn |
| P1.4 | Prompt: bắt buộc nêu **phạm vi** của mọi số phân khúc ("trong toàn giỏ" / "trong phân khúc 3PN"); **cấm** gộp "N căn + số PN" khi N là toàn giỏ | Chặn đúng lỗi "4 căn 3 ngủ" ở tầng gốc |
| P1.5 | Luật trình bày cho câu hỏi tra cứu: 1 đoạn kết luận → số liệu có mỏ neo → tối đa 2 câu hỏi làm rõ (đánh số) | Khớp đúng hình thức bản mong muốn |

### P2 — Hợp đồng mỏ neo `[n]` (phần bản mong muốn cần hệ thống làm, không phải LLM tự gõ)

| # | Việc | Chi tiết |
|---|---|---|
| P2.1 | Hậu xử lý **tự chèn mỏ neo**: quét số trong câu trả lời, khớp với citation, chèn `[n]` **và** trả thêm `anchors: [{index, value, citation}]` trong payload `final` | LLM gõ mỏ neo bằng tay thì không đảm bảo; máy làm mới nhất quán |
| P2.2 | UI: `[n]` **bấm được** → mở đúng modal căn cứ (đã có sẵn `citationToEvidence`); thêm bảng "Nguồn" dưới câu trả lời | Hiện `[n]` chỉ là chuỗi chết (`FormattedAiMessage` không xử lý), citation nằm rời ở dải chip bên dưới |
| P2.3 | "Ghi chú kiểm duyệt nội bộ": giữ trong khung chat (banner riêng, không nằm trong text copy) — đúng bản chất *ghi chú nội bộ, không gửi khách*. **Nội dung ghi chú phải đổi theo thực tế:** sau P1, số liệu đã lấy từ hệ thống nên câu "các con số cần đối chiếu lại" tự mâu thuẫn; ghi chú chỉ nên nói điều **còn** chưa chắc chắn (ví dụ: chính sách/giá có thể đổi theo *ngày giao dịch* — đối chiếu CSBH tại ngày gửi) | Tránh việc Sale copy nguyên văn rồi gửi khách kèm ghi chú nội bộ |

### P3 — Chống nhiễm từ prompt (nên cân nhắc, không bắt buộc)

`prompts.py` L90 nạp "4 căn · 2,5 → 6,1 tỷ" **không kèm nhãn phạm vi** ⇒ đây là **nguồn nhiễm** trực tiếp
của lỗi "4 căn 3 ngủ". Hai lựa chọn: (a) bỏ dải giá khỏi bối cảnh, ép gọi tool; (b) giữ nhưng ghi rõ
*"toàn giỏ, mọi số phòng ngủ"*. Tôi nghiêng về **(b) + luật P1.4**, vì giữ bối cảnh giúp LLM biết giỏ có gì
mà trả lời khi tool lỗi.

## 6. Đo lường — không hứa suông

Thêm vào `scripts/run_copilot_eval.py` bộ ca khó và **ngưỡng CI**:

1. Lọc rỗng (đúng ca này): `grounded=true`; **0** cảnh báo "chưa đối chiếu"; có **≥1** gợi ý nới tiêu chí.
2. Chống hồi quy lỗi "4 căn 3 ngủ": bất kỳ câu trả lời nào chứa `N căn + <số> ngủ` thì N **phải** bằng số
   căn của đúng phân khúc đó (đối chiếu máy, không đọc bằng mắt).
3. Mọi số tiền trong câu trả lời phải map được vào `anchors` (100%), hoặc được đánh dấu *số do người dùng nêu*.
4. Câu hỏi ≥2 tiêu chí mâu thuẫn (ngân sách thấp + PN cao): phải trả **khoảng cách giá** và **phương án tài chính**, không được dừng ở "không có".
5. Tra cứu số không tồn tại trong giỏ: phải nói rõ "không có trong giỏ hiện tại", không suy diễn.

## 7. Bốn điểm cần chốt trước khi code

1. **Thứ tự:** làm P0 ngay (3 lỗi rẻ, có test, không đổi hình thức) rồi chờ các ví dụ tiếp — hay chờ đủ
   ví dụ rồi làm một lượt P0+P1?
2. **P1.3 (tự động đi tiếp sang phương án vay)** có nằm trong phạm vi mong muốn không? Đây là thay đổi
   *hành vi* (Copilot chủ động tính tiền), không chỉ *hình thức*.
3. **Mỏ neo `[n]`** chỉ cần đánh số, hay cần **bấm mở được căn cứ** (P2.2)? (Ảnh hưởng khối lượng UI.)
4. **Một câu hỏi làm rõ hay hai?** Bản mong muốn đang là 2; quy tắc hiện tại trong prompt là "đúng 1 câu ngắn".

> Ghi chú kỹ thuật để không phải khảo sát lại: `FormattedAiMessage` **đã** render markdown (tiêu đề, bảng,
> danh sách, in đậm, blockquote) ⇒ hình thức bản mong muốn hiển thị được, **không cần** thêm thư viện markdown.
> Riêng gạch đầu dòng lồng trong mục số (mục 2 của bản mong muốn) sẽ bị làm phẳng — nếu cần giữ, phải sửa
> parser block của `FormattedAiMessage`.

---

## 8. Danh sách câu hỏi để tinh chỉnh P1 / P2 / P3

Cách dùng: mỗi câu có **đề xuất mặc định** — anh chỉ cần trả lời "theo đề xuất", hoặc sửa lại ý nào khác.
Không cần trả lời hết một lượt; câu nào chốt trước em làm trước.

### P1 — Nội dung & giá trị câu trả lời (quan trọng nhất)

**P1.1 — Khi lọc rỗng thì nới tiêu chí tới đâu?**
Đề xuất: nới **bỏ trần giá trước** (giữ số phòng ngủ) → nếu vẫn rỗng mới **hạ 1 phòng ngủ** → cuối cùng mới
liệt kê cả giỏ. Lý do: khách hỏi 3 ngủ thì hạ phòng ngủ là đổi nhu cầu, cần nói rõ "đây là gợi ý gần nhất".
→ *Anh muốn Copilot tự nới, hay chỉ nêu các phương án để Sale chọn?*

**P1.2 — Có được tự tính phương án tài chính khi Sale nêu ngân sách không?**
Đề xuất: **có**, nhưng chỉ khi Sale nêu số tiền, và ghi rõ giả định ("tạm coi 2 tỷ là **vốn tự có**").
Đây là thay đổi *hành vi*: Copilot chủ động đưa số tiền (đợt đầu 1,0065 tỷ · tổng tự chi 2,1716 tỷ · hụt ~172 triệu).
→ *Anh muốn Copilot chủ động đưa số, hay chỉ gợi ý và chờ Sale bấm?*

**P1.3 — Khi không có căn nào khớp, có luôn kèm "căn gần nhất và thiếu bao nhiêu" không?**
Đề xuất: **luôn kèm 1 dòng** ("căn 3 ngủ gần nhất là ZEN-B-1502 — 6,1 tỷ, cao hơn ngân sách 4,1 tỷ").
→ *Có sợ lộ thông tin giá khi Sale chưa hỏi không?*

**P1.4 — Ngân sách Sale nêu được hiểu là gì?**
Đề xuất: hiểu là **tổng giá trị căn** (khớp cách lọc giỏ hàng hiện nay), và **hỏi lại** nếu có dấu hiệu là
vốn tự có. Nếu Sale nói rõ "vốn tự có 2 tỷ" thì chuyển sang tính theo vốn tự có.
→ *Anh muốn mặc định là tổng giá, hay luôn hỏi lại?*

**P1.5 — Bao nhiêu căn thì chuyển sang bảng so sánh?**
Đề xuất: ≤5 căn → liệt kê có mỏ neo; >5 căn → bảng so sánh + nêu tiêu chí sắp xếp (giá tăng dần).
→ *Ngưỡng anh thấy phù hợp?*

**P1.6 — Có cần nêu "dữ liệu lấy tại ngày giao dịch nào" không?**
Đề xuất: chỉ nêu khi trả lời về **giá/chính sách** ("giá niêm yết theo chính sách đang hiệu lực ngày 02/10/2026").

**P1.7 — Ưu tiên khi phải chọn: rõ ràng, đầy đủ hay ngắn gọn?**
Đề xuất thứ tự: **rõ ràng → đầy đủ → ngắn gọn** (ngắn mà mơ hồ thì Sale vẫn phải hỏi lại, tốn hơn).
→ *Anh đổi thứ tự được không?*

### P2 — Mỏ neo `[n]` & cách hiển thị

**P2.1 — `[n]` cần bấm mở được căn cứ, hay chỉ đánh số?**
Đề xuất: **bấm mở được** (hạ tầng modal căn cứ đã có sẵn: `citationToEvidence`).
→ *Nếu ngại khối lượng UI thì chỉ đánh số.*

**P2.2 — Số do Sale tự nêu (2 tỷ) có gắn `[n]` không?**
Đề xuất: **không**. Số của Sale in đậm + ghi chú "(số anh/chị nêu)"; mỏ neo chỉ dành cho **số liệu hệ thống**.
Lý do: mỏ neo là con trỏ tới nguồn — gắn cho số người dùng nhập là sai nghĩa, làm loãng khái niệm.
→ *Anh có cần mọi con số đều có mỏ neo, kể cả số của Sale?*

**P2.3 — Mỏ neo do máy tự chèn hay để LLM tự viết?**
Đề xuất: **máy tự chèn** ở tầng hậu xử lý (khớp số → tìm citation → chèn `[n]`), LLM chỉ viết nội dung.
Lý do: LLM gõ tay không đảm bảo nhất quán, và không kiểm chứng được.
→ *Anh có muốn thấy `[n]` ngay trong bản nháp, hay chỉ khi gửi khách?*

**P2.4 — "Ghi chú kiểm duyệt nội bộ" có cần lưu theo hội thoại không?**
Đề xuất: **có** — hiện mở lại lịch sử là mất ghi chú (chỉ lưu `reply` + `citations`). Cần thêm 1 trường vào
bản ghi lượt (backend + mock + UI). Khối lượng nhỏ nhưng đụng hợp đồng API.
→ *Anh có cần ghi chú sống cùng hội thoại, hay chỉ cần thấy lúc đang chat là đủ?*

### P3 — Chống nhiễm & cổng chất lượng

**P3.1 — Giữ dải giá giỏ hàng trong prompt (kèm nhãn "TOÀN GIỎ") hay bỏ hẳn để buộc gọi tool?**
Đề xuất: **giữ + nhãn** (đã làm ở P0.5): giúp Copilot biết giỏ có gì khi tool lỗi, mà không còn bị hiểu nhầm
"N căn toàn giỏ" thành "N căn của phân khúc".

**P3.2 — Có thêm cổng CI "N căn X ngủ phải khớp phân khúc" không?**
Đề xuất: **có** (đối chiếu máy với dữ liệu canonical, không đọc bằng mắt). Đây là lỗi đã xảy ra thật.

**P3.3 — Ngưỡng chất lượng mới cho bộ eval?**
Đề xuất: câu hỏi tra cứu **0%** được phép còn "Ghi chú nội bộ"; tỷ lệ bịa tiếp tục **0%**; thêm ca
"lọc rỗng" và "ngân sách là vốn tự có" vào bộ 32 câu vàng.

**P3.4 — Chính sách/giá có được coi là cố định trong ngày không?**
Đề xuất: không — luôn tra theo ngày giao dịch, và ghi chú "đối chiếu CSBH tại ngày gửi" khi câu trả lời
có số tiền.

### Câu hỏi để hiểu kỳ vọng (giúp em khỏi đoán)

**K1 —** Anh có thêm **mẫu câu trả lời nào khác** ngoài ví dụ này không? (Em đưa vào bộ vàng để không
hồi quy.) Càng nhiều ví dụ, P1 càng chắc.
**K2 —** Người đọc chính của câu trả lời là **Sale** (tự dùng) hay **khách** (Sale copy gửi)? Quyết định văn phong.
**K3 —** Trong ví dụ, anh thích điểm nào nhất ở "câu trả lời mong muốn": **mỏ neo `[n]`**, **câu hỏi đánh số**,
hay **phần ghi chú tách riêng**? (Em ưu tiên làm đúng cái đó trước.)
**K4 —** Có chấp nhận câu trả lời **dài hơn** một chút để đủ căn cứ không, hay phải gọn trong ~6 câu như hiện tại?
