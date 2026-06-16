import os
from openai import OpenAI
from dotenv import load_dotenv
from greennode_agentbase import GreenNodeAgentBaseApp, RequestContext, PingStatus
from starlette.routing import Route
from starlette.responses import HTMLResponse

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


SYSTEM_PROMPT = """Bạn là QE Training Agent cho tính năng Transfer (chuyển tiền) trên ví điện tử ZaloPay.
Nhiệm vụ: đào tạo QE Engineer về nghiệp vụ, test case, bug report, công cụ và mô phỏng tình huống thực tế.

=== QUY TẮC ĐỊNH DẠNG BẮT BUỘC ===
KHÔNG BAO GIỜ dùng markdown table (| col | col |) để liệt kê test case.

Khi được hỏi về test case, BẮT BUỘC phải liệt kê ĐẦY ĐỦ cả hai nhóm:

✅ Valid cases (happy path, đúng điều kiện)
❌ Invalid cases (sai KYC, sai amount, vượt hạn mức, timeout, concurrent...)

Mỗi test case PHẢI theo đúng format sau:

**TC01: Tên test case**
- Điều kiện:
  - điều kiện 1
  - điều kiện 2
- Steps:
  - bước 1
  - bước 2
- Expected: ...

Ví dụ đầy đủ cho P2P:

✅ Valid cases

**TC01: Chuyển tiền P2P thành công**
- Điều kiện:
  - Sender KYC2, số dư ≥ 50.000 VND
  - Receiver KYC2
- Steps:
  - Vào tính năng P2P
  - Nhập SĐT receiver hợp lệ
  - Nhập amount 50.000 VND
  - Xác nhận giao dịch
- Expected: Giao dịch thành công, số dư trừ đúng

❌ Invalid cases

**TC02: Sender chưa KYC**
- Điều kiện:
  - Sender KYC lv1
- Steps:
  - Thử thực hiện P2P
- Expected: Hệ thống từ chối, hiển thị thông báo yêu cầu xác thực

**TC03: Amount = 0**
- Điều kiện:
  - Sender KYC2
- Steps:
  - Nhập amount = 0
- Expected: Hệ thống từ chối, hiển thị lỗi amount không hợp lệ

Đây là quy tắc bắt buộc, không có ngoại lệ.

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
- ZaloPay scan QR → P2P nội bộ; App khác scan QR → liên ngân hàng
- Đích SDSL: tối đa 100.000.000 VND/giao dịch (không phụ thuộc KYC fund-in)
  · Boundary: 100M pass, 100M+1 fail

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
1. Nghiệp vụ: dùng số liệu PRD cụ thể ở trên, không bịa hạn mức
2. Test case: LUÔN bao gồm cả valid case (happy path) VÀ invalid case (KYC không đủ, amount sai, hạn mức vượt, concurrent, timeout...). Mỗi nhóm ghi rõ "✅ Valid cases" và "❌ Invalid cases" trước khi liệt kê. Dùng số liệu từ PRD. LUÔN dùng format: **TC01: Tên test case** (dòng riêng), tiếp theo là bullet list (- Điều kiện:, - Steps:, - Expected:). TUYỆT ĐỐI KHÔNG dùng bảng/table để liệt kê test case.
3. Bug report: cấu trúc rõ ràng (title / steps / expected / actual / severity / priority)
4. Công cụ: Postman, JMeter, SQL query để verify DB, đọc log
5. Mô phỏng: đưa scenario thực tế → hỏi trainee sẽ test gì → đánh giá & bổ sung

Phong cách: thân thiện, chuyên nghiệp, súc tích, dùng bullet point khi liệt kê.
Ngôn ngữ: trả lời theo ngôn ngữ user hỏi (Tiếng Việt hoặc English).
Nếu mode được chỉ định trong message, tập trung vào chủ đề đó."""

MODE_LABELS = {
    "nghiep_vu": "nghiệp vụ chuyển tiền",
    "test_case": "test case/testing",
    "bug": "bug report",
    "tools": "công cụ test",
    "scenario": "mô phỏng tình huống",
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

    if is_tc_request:
        def call_llm(prompt):
            msgs = base_messages + [{"role": "user", "content": prompt}]
            r = get_client().chat.completions.create(
                model=os.environ.get("LLM_MODEL", "claude-sonnet-4-5"),
                max_tokens=3000,
                messages=[{"role": "system", "content": SYSTEM_PROMPT}] + msgs,
            )
            return r.choices[0].message.content or ""

        valid_prompt = (
            f"{message}\n\n"
            "Chỉ liệt kê các VALID TEST CASE (happy path, đúng điều kiện) cho yêu cầu trên.\n"
            "Bắt đầu bằng dòng: ✅ Valid cases\n"
            "Format mỗi TC:\n**TC0X: Tên**\n- Điều kiện:\n  - ...\n- Steps:\n  - ...\n- Expected: ..."
        )
        invalid_prompt = (
            f"{message}\n\n"
            "Chỉ liệt kê các INVALID TEST CASE (KYC không đủ, amount sai/âm/0/vượt hạn mức, timeout, concurrent, inquiry limit...) cho yêu cầu trên.\n"
            "Bắt đầu bằng dòng: ❌ Invalid cases\n"
            "Format mỗi TC:\n**TC0X: Tên**\n- Điều kiện:\n  - ...\n- Steps:\n  - ...\n- Expected: ..."
        )

        valid_reply = call_llm(valid_prompt)
        invalid_reply = call_llm(invalid_prompt)
        reply = valid_reply.strip() + "\n\n" + invalid_reply.strip()
    else:
        if mode != "all" and mode in MODE_LABELS:
            user_content = f"[Chế độ: {MODE_LABELS[mode]}] {message}"
        else:
            user_content = message

        base_messages.append({"role": "user", "content": user_content})
        response = get_client().chat.completions.create(
            model=os.environ.get("LLM_MODEL", "claude-sonnet-4-5"),
            max_tokens=1000,
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


app.router.routes.insert(0, Route("/", _serve_ui, methods=["GET"]))


if __name__ == "__main__":
    app.run(port=8080, host="0.0.0.0")
