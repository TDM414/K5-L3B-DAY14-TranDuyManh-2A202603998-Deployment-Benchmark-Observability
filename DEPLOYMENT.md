# Deployment Information

## Public URL
https://<YOUR_PUBLIC_URL>

## Platform
Railway / Render *(chọn nền tảng bạn đã deploy)*

## Test Commands

### 1. Health & Readiness Check
```bash
BASE="https://<YOUR_PUBLIC_URL>"
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"   # Expected: 200
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"    # Expected: 200
```

### 2. API Test (Auth & Ask)
```bash
# Không có API key → 401
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' \
  -d '{"question":"Hello"}'

# Có API key hợp lệ → 200
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"Hello"}'
```

## Environment Variables Set
- `PORT` (do platform tự inject hoặc `8000`)
- `ENVIRONMENT=production`
- `REDIS_URL` (trỏ tới managed Redis của Railway/Render)
- `AGENT_API_KEY` (đặt trên platform dashboard, không ghi vào code)
- `RATE_LIMIT_PER_MINUTE=10`
- `DAILY_BUDGET_USD=1.0`

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
