# qe-money-transfer-training-agent

A GreenNode AgentBase agent — QE training assistant for Money Transfer domain.

## Prerequisites

- Python 3.10+
- A GreenNode IAM Service Account

## Setup

1. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv && source venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure credentials:
   ```bash
   cp .env.example .env
   # Edit .env with your LLM_API_KEY
   ```

## Configure LLM

Set the following in `.env`:

```
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1
LLM_MODEL=claude-sonnet-4-5
```

## Run Locally

```bash
python3 main.py
```

Test it:
```bash
curl -X POST http://127.0.0.1:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"message": "Quy trình chuyển tiền nội địa là gì?", "mode": "nghiep_vu"}'
```

## Deploy to AgentBase Runtime

Use `/agentbase-deploy` skill or see the AgentBase Console.

## Payload Format

```json
{
  "message": "user question",
  "mode": "all | nghiep_vu | test_case | bug | tools | scenario",
  "history": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
}
```
