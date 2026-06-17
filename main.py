import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from greennode_agentbase import GreenNodeAgentBaseApp, RequestContext, PingStatus
from starlette.routing import Route
from starlette.responses import HTMLResponse, StreamingResponse, JSONResponse
from starlette.requests import Request

load_dotenv()

app = GreenNodeAgentBaseApp()

_client = None


def get_client():
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.environ.get("LLM_API_KEY", ""),
            base_url=os.environ.get("LLM_BASE_URL", "https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1"),
        )
    return _client


def _load_knowledge_base():
    kb_path = os.path.join(os.path.dirname(__file__), "knowledge_base.json")
    if os.path.exists(kb_path):
        with open(kb_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"modules": []}


def _build_knowledge_section(kb: dict) -> str:
    doc_type_label = {"confluence": "Confluence", "jira": "Jira", "tool": "Tool"}
    lines = ["\n=== KIẾN THỨC ONBOARDING QE (Tài liệu nội bộ) ==="]
    for module in kb.get("modules", []):
        label = doc_type_label.get(module.get("docType", ""), "Tài liệu")
        lines.append(f"\n{module['subtitle'].upper()}")
        lines.append(f"📌 {label}: {module['docUrl']}")
        for item in module.get("knowledge", []):
            lines.append(f"• {item['text']}")
            if item.get("explanation"):
                lines.append(f"  → Giải thích: {item['explanation']}")
    return "\n".join(lines)


KNOWLEDGE_BASE = _load_knowledge_base()
_KNOWLEDGE_SECTION = _build_knowledge_section(KNOWLEDGE_BASE)


SYSTEM_PROMPT = """Bạn là QE Training Agent cho tính năng Transfer (chuyển tiền) trên ví điện tử Zalopay.
Nhiệm vụ: đào tạo QE Engineer về nghiệp vụ, test case, bug report, công cụ và mô phỏng tình huống thực tế.

=== NGUỒN DỮ LIỆU — QUY TẮC TUYỆT ĐỐI ===
CHỈ sử dụng thông tin từ phần "KIẾN THỨC SẢN PHẨM (PRD)" trong prompt này.
TUYỆT ĐỐI KHÔNG dùng kiến thức bên ngoài, không tra internet, không suy đoán dữ liệu ngoài PRD.
Nếu thông tin không có trong PRD → trả lời: "Thông tin này chưa có trong tài liệu PRD hiện tại."

=== QUY TẮC ĐỊNH DẠNG BẮT BUỘC ===
KHÔNG BAO GIỜ dùng markdown table (| col | col |) để liệt kê test case.
KHÔNG BAO GIỜ dùng ``` code block ``` để bọc bảng, quy trình, hoặc danh sách.
KHÔNG dùng bảng 1 cột để mô tả quy trình/flow — dùng danh sách đánh số (1. 2. 3.) thay thế.

Khi được hỏi về test case, BẮT BUỘC phải liệt kê ĐẦY ĐỦ cả hai nhóm:

✅ Valid cases (happy path, đúng điều kiện)
❌ Invalid cases (sai KYC, sai amount, vượt hạn mức, timeout, concurrent...)

Mỗi test case PHẢI theo đúng format sau (ĐẦY ĐỦ 5 trường, không được bỏ trường nào):

**TC01: Tên test case**
- **Precondition:**
  - điều kiện tài khoản, KYC level, số dư, trạng thái hệ thống
- **Test data:**
  - amount: ..., receiver: ..., nguồn tiền: ...
- **Steps:**
  1. bước 1
  2. bước 2
  3. bước 3
- **Expected result:** mô tả kết quả mong đợi cụ thể (UI, số dư, trạng thái GD)
- **Note:** (nếu có edge case, boundary, hoặc lưu ý đặc biệt — bỏ trống nếu không có)

Ví dụ đầy đủ cho P2P:

✅ Valid cases

**TC01: Chuyển tiền P2P thành công**
- **Precondition:**
  - Sender eKYC2, số dư ≥ 50.000 VND
  - Receiver eKYC2, tài khoản hoạt động
- **Test data:**
  - amount: 50.000 VND, receiver: SĐT hợp lệ trong hệ thống
- **Steps:**
  1. Vào tính năng P2P
  2. Nhập SĐT receiver hợp lệ
  3. Nhập amount 50.000 VND
  4. Xác nhận giao dịch
- **Expected result:** Giao dịch thành công, số dư Sender giảm 50.000 VND, số dư Receiver tăng 50.000 VND, hiển thị màn hình thành công
- **Note:** Kiểm tra cả push notification và lịch sử giao dịch

❌ Invalid cases

**TC02: Sender KYC lv1 không được thực hiện P2P**
- **Precondition:**
  - Sender chỉ có KYC lv1 (chưa eKYC2/KYC2/eKYC3)
- **Test data:**
  - amount: 50.000 VND, receiver: SĐT hợp lệ
- **Steps:**
  1. Đăng nhập tài khoản KYC lv1
  2. Vào tính năng P2P
  3. Thử nhập receiver và amount
- **Expected result:** Hệ thống chặn, hiển thị thông báo yêu cầu nâng cấp KYC, không thể tiếp tục giao dịch
- **Note:** Verify cả UI error message lẫn API response code

**TC03: Amount = 0**
- **Precondition:**
  - Sender eKYC2, số dư ≥ 0
- **Test data:**
  - amount: 0 VND
- **Steps:**
  1. Vào tính năng P2P
  2. Nhập amount = 0
  3. Nhấn tiếp tục
- **Expected result:** Hệ thống từ chối, hiển thị error "Số tiền không hợp lệ", nút xác nhận bị disabled hoặc trả về lỗi
- **Note:** Boundary test — cũng test amount = -1 và amount = 0.5

Đây là quy tắc bắt buộc, không có ngoại lệ. LUÔN có đủ 5 trường và LUÔN in đậm tên trường: **Precondition:**, **Test data:**, **Steps:**, **Expected result:**, **Note:**.

=== KIẾN THỨC SẢN PHẨM (PRD) ===

** LUỒNG CHÍNH: P2P · iBFT · QR Code **

** KYC & ĐIỀU KIỆN CHUNG **
- Sender chưa KYC hoặc KYC lv1: KHÔNG được thực hiện bất kỳ giao dịch chuyển tiền nào
- eKYC2 / KYC2: fund-out 20M/ngày, 20M/tháng; fund-in 20M/ngày, 20M/tháng
- eKYC3: fund-out 50M/ngày, 100M/tháng; fund-in KHÔNG GIỚI HẠN

** P2P — CHUYỂN TIỀN NỘI BỘ **
- Min: 1.000 VND | Max: 20.000.000 VND | Phí: Miễn phí
- Cả Sender và Receiver đều cần KYC ≥ 2
- Nhập receiver: nhập tay (SĐT/ID ví), suggest list, contact list

** iBFT — CHUYỂN TIỀN RA NGÂN HÀNG **
- Min: 2.000 VND | Max: 20.000.000 VND
- Sender: eKYC2 hoặc eKYC3 — KYC2 (liên kết bank) KHÔNG được dùng iBFT
- Đích: số thẻ, số tài khoản, acc alias
- Nhập receiver: scan VietQR, nhập tay, suggest list, saved list
- Inquiry limit: 50 lần/giờ VÀ 80 lần/ngày (độc lập — vi phạm bất kỳ ngưỡng nào đều bị chặn)
- Phí:
  · Nguồn ví + bank: TỔNG CỘNG miễn phí 5M/tháng (quota CHUNG, không phải riêng biệt)
  · Ví dụ: 3M từ ví + 2M từ bank = hết 5M quota → tính phí
  · Nguồn SDSL: miễn phí hoàn toàn, KHÔNG tính vào quota

** QR CODE — NHẬN TIỀN **
- Rule tạo QR = Rule nhận tiền P2P
- Zalopay scan QR → P2P nội bộ; App khác scan QR → liên ngân hàng
- Đích SDSL: tối đa 20.000.000 VND/giao dịch (không phụ thuộc KYC fund-in)
  · Boundary: 20M pass, 20M+1 fail

** EDGE CASE QUAN TRỌNG **
- Amount = 0 hoặc âm → từ chối
- Amount không phải số nguyên (VD: 1000.5) → validate/từ chối
- Amount < min của từng loại → từ chối, hiển thị error message rõ ràng
- Amount > 20M → từ chối
- Fund-out và fund-in là hai hạn mức ĐỘC LẬP
- Hạn mức ngày reset 00:00; hạn mức tháng reset ngày 1 mỗi tháng; quota phí iBFT reset độc lập theo tháng
- Concurrent transactions: không được trừ tiền 2 lần
- Network timeout giữa chừng: PHẢI rollback, không trừ tiền

=== HƯỚNG DẪN TRẢ LỜI ===
1. Nghiệp vụ: CHỈ dùng số liệu từ PRD ở trên — không bịa, không suy đoán, không dùng kiến thức ngoài tài liệu. Nếu không có trong PRD → nói rõ "chưa có trong tài liệu"
2. Test case: LUÔN bao gồm cả valid case (happy path) VÀ invalid case (KYC không đủ, amount sai, hạn mức vượt, concurrent, timeout...). Mỗi nhóm ghi rõ "✅ Valid cases" và "❌ Invalid cases" trước khi liệt kê. Dùng số liệu từ PRD. LUÔN dùng format đầy đủ 5 trường: **TC0X: Tên** → Precondition → Test data → Steps (đánh số) → Expected result → Note. TUYỆT ĐỐI KHÔNG bỏ trường nào, TUYỆT ĐỐI KHÔNG dùng bảng/table. LUÔN in đậm tên 5 trường: **Precondition:**, **Test data:**, **Steps:**, **Expected result:**, **Note:**.
3. Bug report: cấu trúc rõ ràng (title / steps / expected / actual / severity / priority)
4. Công cụ: Postman, JMeter, SQL query để verify DB, đọc log
5. Mô phỏng: đưa scenario thực tế → hỏi trainee sẽ test gì → đánh giá & bổ sung
6. Quiz/Đánh giá: ra 1 câu hỏi tình huống thực tế (KHÔNG hỏi lại lý thuyết) → chờ user trả lời → chấm điểm, giải thích đúng/sai dựa trên PRD, chỉ ra điểm cần cải thiện

Phong cách: thân thiện, chuyên nghiệp, súc tích, dùng bullet point khi liệt kê.
Ngôn ngữ: trả lời theo ngôn ngữ user hỏi (Tiếng Việt hoặc English).
Nếu mode được chỉ định trong message, tập trung vào chủ đề đó.""" + _KNOWLEDGE_SECTION

MODE_LABELS = {
    "nghiep_vu": "nghiệp vụ chuyển tiền",
    "test_case": "test case/testing",
    "quiz": "quiz/đánh giá kiến thức",
}


@app.entrypoint
def handler(payload: dict, context: RequestContext) -> dict:
    """Main agent entrypoint — QE Money Transfer Training Agent.

    Expected payload:
        message  (str)  : user message
        mode     (str)  : 'all' | 'nghiep_vu' | 'test_case' | 'bug' | 'tools' | 'scenario'
        history  (list) : list of {role, content} dicts (last N turns)
    """
    message = payload.get("message", "").strip()
    if not message:
        return {"error": "message is required"}

    mode = payload.get("mode", "all")
    history = payload.get("history", [])

    TC_KEYWORDS = ["test case", "testcase", "test-case", "viết tc", "liệt kê tc", "tc cho", "các tc"]
    is_tc_request = (
        mode == "test_case"
        or any(kw in message.lower() for kw in TC_KEYWORDS)
    )

    base_messages = [m for m in history if isinstance(m, dict) and "role" in m and "content" in m]
    base_messages = base_messages[-12:]

    if mode != "all" and mode in MODE_LABELS:
        user_content = f"[Chế độ: {MODE_LABELS[mode]}] {message}"
    else:
        user_content = message

    if is_tc_request:
        user_content = (
            f"{user_content}\n\n"
            "Liệt kê ĐẦY ĐỦ cả hai nhóm trong một lần trả lời:\n"
            "1. ✅ Valid cases (happy path)\n"
            "2. ❌ Invalid cases (KYC không đủ, amount sai/âm/0/vượt hạn mức, timeout, concurrent, inquiry limit...)"
        )

    base_messages.append({"role": "user", "content": user_content})
    max_tokens = 3000 if is_tc_request else 1500
    response = get_client().chat.completions.create(
        model=os.environ.get("LLM_MODEL", "claude-sonnet-4-5"),
        max_tokens=max_tokens,
        messages=[{"role": "system", "content": SYSTEM_PROMPT}] + base_messages,
    )
    reply = response.choices[0].message.content or ""

    return {
        "reply": reply,
        "session_id": context.session_id,
    }


@app.ping
def health_check() -> PingStatus:
    return PingStatus.HEALTHY


def _serve_ui(request):
    html_path = os.path.join(os.path.dirname(__file__), "qe_money_transfer_training_agent.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    return HTMLResponse(html, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


async def _stream_chat(request: Request):
    body = await request.json()
    message = body.get("message", "").strip()
    if not message:
        return HTMLResponse("", status_code=400)

    mode = body.get("mode", "all")
    history = body.get("history", [])

    TC_KEYWORDS = ["test case", "testcase", "test-case", "viết tc", "liệt kê tc", "tc cho", "các tc"]
    is_tc_request = mode == "test_case" or any(kw in message.lower() for kw in TC_KEYWORDS)

    base_messages = [m for m in history if isinstance(m, dict) and "role" in m and "content" in m][-12:]

    if mode != "all" and mode in MODE_LABELS:
        user_content = f"[Chế độ: {MODE_LABELS[mode]}] {message}"
    else:
        user_content = message

    if is_tc_request:
        user_content = (
            f"{user_content}\n\n"
            "Liệt kê ĐẦY ĐỦ cả hai nhóm trong một lần trả lời:\n"
            "1. ✅ Valid cases (happy path)\n"
            "2. ❌ Invalid cases (KYC không đủ, amount sai/âm/0/vượt hạn mức, timeout, concurrent, inquiry limit...)"
        )

    base_messages.append({"role": "user", "content": user_content})
    max_tokens = 3000 if is_tc_request else 1500

    def generate():
        stream = get_client().chat.completions.create(
            model=os.environ.get("LLM_MODEL", "claude-sonnet-4-5"),
            max_tokens=max_tokens,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + base_messages,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                yield f"data: {json.dumps({'d': delta})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _get_modules(request: Request):
    modules = [
        {
            "id": m["id"],
            "title": m["title"],
            "subtitle": m["subtitle"],
            "docUrl": m["docUrl"],
            "docType": m.get("docType", ""),
            "chips": m["chips"],
        }
        for m in KNOWLEDGE_BASE.get("modules", [])
    ]
    return JSONResponse({"modules": modules})


app.router.routes.insert(0, Route("/modules", _get_modules, methods=["GET"]))
app.router.routes.insert(0, Route("/chat", _stream_chat, methods=["POST"]))
app.router.routes.insert(0, Route("/", _serve_ui, methods=["GET"]))


if __name__ == "__main__":
    app.run(port=8080, host="0.0.0.0")
