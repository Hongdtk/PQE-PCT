# QE Money Transfer Training Agent

Agent đào tạo QE Engineer về nghiệp vụ chuyển tiền trên ví điện tử **Zalopay**, chạy trên nền tảng GreenNode AgentBase.

## Tính năng

- **Nghiệp vụ**: P2P · iBFT · QR Code — hạn mức, KYC, phí, edge case theo PRD
- **Test case**: Sinh tự động với đầy đủ Precondition, Test data, Steps, Expected result, Note
- **Quiz**: 10 câu trắc nghiệm + câu hỏi AI tình huống với chấm điểm tự động
- **Feature cards**: Tóm tắt nhanh P2P / iBFT / QR Code

> Dữ liệu chỉ lấy từ file PRD nội bộ, không tra internet.

## Cấu trúc

```
main.py                              # AgentBase entrypoint, system prompt, LLM call
qe_money_transfer_training_agent.html  # Chatbot UI (single-file, Tiếng Việt)
prd-transfer.txt                     # PRD nội bộ — nguồn dữ liệu duy nhất
requirements.txt
Dockerfile
```

## Yêu cầu

- Python 3.10+
- GreenNode IAM Service Account
- LLM API Key (GreenNode AI Platform hoặc tương thích OpenAI)

## Cài đặt local

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Điền LLM_API_KEY vào .env
python3 main.py
```

Mở trình duyệt tại `http://127.0.0.1:8080`

## Cấu hình `.env`

```
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1
LLM_MODEL=minimax/minimax-m2.5
```

## Test API

```bash
curl -X POST http://127.0.0.1:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"message": "Viết test case cho iBFT", "mode": "test_case"}'
```

## Payload format

```json
{
  "message": "câu hỏi của user",
  "mode": "all | nghiep_vu | test_case | bug | tools | scenario | quiz",
  "history": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
}
```

## Deploy lên AgentBase

```bash
docker build --platform linux/amd64 -t vcr.vngcloud.vn/<repo>/qe-money-transfer-training-agent:latest .
bash .claude/skills/agentbase/scripts/cr.sh credentials docker-login
docker push vcr.vngcloud.vn/<repo>/qe-money-transfer-training-agent:latest
bash .claude/skills/agentbase/scripts/runtime.sh update <runtime-id> \
  --image vcr.vngcloud.vn/<repo>/qe-money-transfer-training-agent:latest \
  --from-cr
```

## Chế độ hoạt động

| Mode | Nội dung |
|------|----------|
| Tất cả | Tổng hợp, hiển thị feature cards |
| Nghiệp vụ | Hạn mức, KYC, quy trình |
| Test case | Sinh TC valid + invalid đầy đủ 5 trường |
| Quiz | Trắc nghiệm + AI chấm điểm |
