# Day 14 Lab - Mission Answers

> **Học viên:** Trần Duy Mạnh  
> **MSSV:** 2A202603998  
> **Lớp:** K5-L3B

---

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found (`01-localhost-vs-production/develop/app.py`)

1. **Hardcoded Secrets (dòng 17–18):**
   - `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"`
   - `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"`
   - *Rủi ro:* Khi push lên GitHub public, secret bị lộ ngay lập tức (bot quét secret tự động khai thác trong vài giây), và không thể đổi key theo từng môi trường mà không sửa code.
   - *Cách `production` đã sửa (`production/config.py`, dòng 27, 32):* Đọc từ biến môi trường `os.getenv("OPENAI_API_KEY", "")`, `os.getenv("AGENT_API_KEY", "")` và kiểm tra fail-fast trong `Settings.validate()` khi `environment == "production"`.

2. **Không có Config Management / Bật cứng Debug (dòng 21–22, 53):**
   - `DEBUG = True`, `MAX_TOKENS = 500`, `reload=True`.
   - *Rủi ro:* `reload=True` tiêu tốn tài nguyên theo dõi file và có thể restart worker bất ngờ; `DEBUG = True` dễ làm lộ stack trace nội bộ ra ngoài.
   - *Cách `production` đã sửa (`production/config.py`, dòng 14–35):* Gom cấu hình vào dataclass `Settings` đọc từ env vars với giá trị mặc định an toàn (`DEBUG` mặc định `"false"`).

3. **Dùng `print()` và log thẳng secret ra stdout (dòng 33–34, 38):**
   - `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")`
   - *Rủi ro:* Lộ API key vào log hệ thống; log dạng text tự do khó parse/filter trên các hệ thống như Datadog, Loki.
   - *Cách `production` đã sửa (`production/app.py`, dòng 28–32, 111–122):* Dùng `logging` với format JSON có cấu trúc (`time`, `level`, `msg`) và chỉ log metadata (`question_length`, `client_ip`), tuyệt đối không log secret.

4. **Thiếu Health Check / Readiness Endpoint:**
   - Bản `develop` không có `/health` hay `/ready`.
   - *Rủi ro:* Platform (Railway/Render/Kubernetes) không biết container còn sống hay sẵn sàng nhận traffic để tự động restart hoặc điều phối tải.
   - *Cách `production` đã sửa (`production/app.py`, dòng 135–149):* Cung cấp `GET /health` trả về `status`, `uptime_seconds`, `version`, `environment`, `timestamp`.

5. **Bind `localhost` và cứng `port=8000` (dòng 51–52):**
   - `host="localhost"`, `port=8000`.
   - *Rủi ro:* Bind `localhost` (`127.0.0.1`) khiến bên ngoài container không truy cập được; cứng port `8000` sẽ lỗi khi cloud platform inject biến `PORT` động.
   - *Cách `production` đã sửa (`production/config.py`, dòng 17–18):* `host` mặc định `"0.0.0.0"`, `port` đọc từ `os.getenv("PORT", "8000")`.

6. **Không xử lý Graceful Shutdown (dòng 47–54):**
   - Khi nhận `SIGTERM`, server tắt đột ngột, có thể làm đứt ngang các request đang xử lý.
   - *Cách `production` đã sửa (`production/app.py`, dòng 39–67):* Dùng `@asynccontextmanager async def lifespan(app)` để khởi tạo khi startup, chuyển `is_ready = False` khi shutdown và chờ hoàn thành request đang chạy.

---

### Exercise 1.2: Kết quả chạy thử bản `develop` và `production`

- **Chạy `01-localhost-vs-production/develop/app.py`:**
  - `GET http://localhost:8000/` → `200 OK`:
    ```json
    {"message":"Hello! Agent is running on my machine :)"}
    ```
  - `POST http://localhost:8000/ask?question=Hello` → `200 OK`:
    ```json
    {"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
    ```
  - Log terminal lộ trực tiếp key: `[DEBUG] Using key: sk-hardcoded-fake-key-never-do-this`

- **Chạy `01-localhost-vs-production/production/app.py`:**
  - `GET http://localhost:8000/health` → `200 OK`:
    ```json
    {"status":"ok","uptime_seconds":4.5,"version":"1.0.0","environment":"development","timestamp":"2026-11-26T07:42:59.760944+00:00"}
    ```
  - `POST http://localhost:8000/ask` (JSON `{"question":"Hello"}`) → `200 OK`:
    ```json
    {"question":"Hello","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé.","model":"gpt-4o-mini"}
    ```

---

### Exercise 1.3: Bảng so sánh Develop vs Production

| Feature | Develop | Production | Why Important? |
|---------|---------|------------|----------------|
| **Secrets & API Keys** | Hardcode trực tiếp trong `app.py` (`OPENAI_API_KEY`, `DATABASE_URL`) | Đọc từ biến môi trường (`os.getenv(...)`) qua `config.py`, có `validate()` | Tránh lộ secret lên Git/GitHub, dễ xoay vòng key và tách biệt giữa dev/staging/prod |
| **Host & Port** | Cứng `host="localhost"`, `port=8000` | `HOST` mặc định `0.0.0.0`, `PORT` đọc từ env var | `0.0.0.0` cần thiết để nhận traffic từ ngoài container; cloud platform tự cấp `PORT` qua env |
| **Debug / Reload** | `DEBUG = True`, `reload=True` | `DEBUG` mặc định `false`, không bật reload | Tránh rò rỉ thông tin nội bộ qua traceback và tránh tốn CPU/restart ngoài ý muốn |
| **Health Check** | Không có | `GET /health` trả về uptime, version, status | Giúp orchestrator/platform phát hiện app treo để tự restart và kiểm tra trạng thái |
| **Logging** | `print()` dạng text tự do, có in secret | `logging` định dạng JSON có cấu trúc, không log secret | Dễ thu thập, tìm kiếm và cảnh báo trên hệ thống log tập trung mà không lộ dữ liệu nhạy cảm |
| **Shutdown** | Tắt đột ngột | `lifespan` chuyển trạng thái shutdown và chờ request in-flight | Không làm rớt kết nối của người dùng đang chờ phản hồi khi deploy bản mới hoặc scale down |
| **CORS** | Không cấu hình | `CORSMiddleware` giới hạn theo `ALLOWED_ORIGINS` | Kiểm soát domain nào được phép gọi API từ trình duyệt |

---

## Part 2: Docker

### Exercise 2.1: Dockerfile questions (`02-docker/develop/Dockerfile`)

1. **Base image:** `python:3.11` (full Debian-based Python distribution, dung lượng lớn ~1 GB).
2. **Working directory:** `/app` (`WORKDIR /app`).
3. **Tại sao `COPY requirements.txt` trước `COPY ... app.py`?** Để tận dụng **Docker layer cache**: `requirements.txt` ít thay đổi hơn source code. Khi chỉ sửa code (`app.py`), Docker tái sử dụng cache của layer `pip install` thay vì cài lại toàn bộ dependencies từ đầu.
4. **Khác nhau giữa `CMD` và `ENTRYPOINT`:**
   - `ENTRYPOINT` định nghĩa **lệnh gốc cố định** luôn chạy khi container khởi động (ví dụ `["uvicorn"]`).
   - `CMD` định nghĩa **lệnh mặc định hoặc tham số mặc định** truyền cho `ENTRYPOINT`, và dễ dàng bị ghi đè khi truyền thêm đối số ở cuối lệnh `docker run`.

### Exercise 2.2: Build và run `my-agent:develop`

- Build từ gốc repo: `docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .`
- Chạy container: `docker run -d -p 8000:8000 my-agent:develop`
- Kết quả test:
  - `GET http://localhost:8000/health` → `{"status":"ok","uptime_seconds":2.6,"container":true}`
  - `POST http://localhost:8000/ask?question=What+is+Docker?` → `{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}`

### Exercise 2.3: Multi-stage build & Image size comparison

- **Stage 1 (`builder` — `python:3.11-slim`):** Cài `gcc`, `libpq-dev` và `pip install --user -r requirements.txt` vào `/root/.local` để biên dịch các package cần build tools.
- **Stage 2 (`runtime` — `python:3.11-slim`):** Tạo user non-root `appuser`, chỉ `COPY --from=builder /root/.local` và source code cần thiết sang, cấu hình `HEALTHCHECK` và chạy `uvicorn` bằng `appuser`.
- **Tại sao nhỏ hơn?** Stage `runtime` loại bỏ hoàn toàn `gcc`, `libpq-dev`, cache build và phần OS nặng của `python:3.11` full image.
- **Số đo thực tế (`docker images my-agent`):**
  - Develop (`my-agent:develop`): **1.67 GB** (1,710 MB; content size 426 MB)
  - Production (`my-agent:advanced`): **240 MB** (content size 57.4 MB)
  - Difference: giảm **~85.97%** (nhỏ hơn ~7.1 lần)

### Exercise 2.4: Docker Compose stack (`02-docker/production/docker-compose.yml`)

- **Các service trong stack:** `nginx` (reverse proxy, mở port 80/443), `agent` (FastAPI, nối mạng nội bộ `internal`, phụ thuộc healthcheck của `redis` và `qdrant`), `redis` (`redis:7-alpine`, cache/rate limit), `qdrant` (`qdrant/qdrant:v1.9.0`, vector DB).

```mermaid
flowchart LR
    Client["Client (Browser / curl)"] -->|":80 / :443"| Nginx["nginx (nginx:alpine)"]
    subgraph internal["Docker Network: internal"]
        Nginx -->|":8000"| Agent["agent (FastAPI)"]
        Agent -->|"redis://redis:6379/0"| Redis["redis (redis:7-alpine)"]
        Agent -->|"http://qdrant:6333"| Qdrant["qdrant (v1.9.0)"]
    end
```

- **Kết quả test qua Nginx (`http://localhost`):**
  - `GET http://localhost/health` → `{"status":"ok","uptime_seconds":7.3,"version":"2.0.0","timestamp":"2026-11-26T08:04:49.074701"}`
  - `POST http://localhost/ask` (`{"question":"Explain microservices"}`) → `{"answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}`

## Part 3: Cloud Deployment

### Exercise 3.1 / 3.2: Deploy Agent Part 6 (`06-lab-complete/`)
- **URL:** `https://<YOUR_PUBLIC_URL>` *(điền URL thật sau khi deploy lên Railway/Render)*
- **Screenshots:** [dashboard.png](screenshots/dashboard.png), [running.png](screenshots/running.png), [test.png](screenshots/test.png)

### So sánh `railway.toml` vs `render.yaml`
| Tiêu chí | `railway.toml` | `render.yaml` (Blueprint) |
|---|---|---|
| **Định dạng & cấu hình** | TOML ngắn gọn (`[build]`, `[deploy]`) | YAML (Infrastructure as Code, khai báo danh sách `services`) |
| **Build & Healthcheck** | `builder = "DOCKERFILE"`, `healthcheckPath = "/health"` | `type: web`, `runtime: docker`, `healthCheckPath: /health` |
| **Quản lý biến môi trường & Secret** | Thiết lập riêng qua Railway Dashboard hoặc `railway variables set` | Khai báo trực tiếp `envVars` trong file; secret dùng `generateValue: true` hoặc `sync: false` để không lộ trong Git |
| **Multi-service (kèm Redis)** | Thêm Redis service trực tiếp trên project dashboard và link biến `REDIS_URL` | Có thể khai báo cả web service và Redis trong cùng file Blueprint |

### Exercise 3.3: Mô tả pipeline Cloud Run (`03-cloud-deployment/production-cloud-run/`)
Pipeline trong `cloudbuild.yaml` tự động chạy 4 bước khi push lên `main`: (1) chạy `pytest tests/` bằng `python:3.11-slim`, (2) build Docker image gắn tag `$COMMIT_SHA` và `latest` (tận dụng `--cache-from`), (3) push image lên Container Registry (`gcr.io/$PROJECT_ID/ai-agent`), và (4) deploy lên Cloud Run vùng `asia-southeast1` với `min-instances=1`, `max-instances=10`, lấy secret từ Secret Manager. File `service.yaml` định nghĩa cấu hình Knative cho service: giới hạn `1 CPU / 512Mi RAM`, `containerConcurrency=80`, `livenessProbe` (`/health`) và `startupProbe` (`/ready`).

## Part 4: API Security

### Exercise 4.1–4.3: Test results (`04-api-gateway/`)

- **Bản `develop` (API Key auth):**
  - Không có `X-API-Key` → `401 Unauthorized`: `{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}`
  - Có `X-API-Key` hợp lệ → `200 OK`: `{"question":"hello","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}`

- **Bản `production` (JWT + Rate Limiting 10 req/min + Cost Guard):**
  - Lấy JWT token qua `POST /auth/token` → `200 OK` (token được che `<JWT_TOKEN>`).
  - **Không có token (`401`):**
    ```http
    HTTP/1.1 401 Unauthorized
    www-authenticate: Bearer
    content-type: application/json

    {"detail":"Authentication required. Include: Authorization: Bearer <token>"}
    ```
  - **Có token hợp lệ (`200`, request 1/10):**
    ```http
    HTTP/1.1 200 OK
    content-type: application/json

    {"question":"hello","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.","usage":{"requests_remaining":9,"budget_remaining_usd":1.8e-05}}
    ```
  - **Vòng lặp 12 requests liên tiếp:** Request 1–10 trả `HTTP 200`, từ request 11 trở đi trả `HTTP 429`:
    ```http
    HTTP/1.1 429 Too Many Requests
    x-ratelimit-limit: 10
    x-ratelimit-remaining: 0
    retry-after: 59
    content-type: application/json

    {"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
    ```

### Exercise 4.4: Cost guard implementation (`04-api-gateway/production/cost_guard.py`)

- **Cách hoạt động:**
  1. `CostGuard` theo dõi mức chi tiêu hàng ngày theo từng `user_id` (`daily_budget_usd = 1.0`, `UsageRecord` lưu `input_tokens`, `output_tokens`, `request_count`, `day`) và tổng ngân sách toàn hệ thống (`global_daily_budget_usd = 10.0`).
  2. Trước khi gọi LLM, `check_budget(user_id)` kiểm tra: nếu vượt global budget trả `503`, nếu vượt budget của user trả `402 Payment Required`, và ghi log cảnh báo khi đạt `80%` (`warn_at_pct = 0.8`).
  3. Sau khi gọi LLM xong, `record_usage(user_id, input_tokens, output_tokens)` cộng dồn token và tính chi phí theo đơn giá `PRICE_PER_1K_INPUT_TOKENS` / `PRICE_PER_1K_OUTPUT_TOKENS`.
- **Vì sao cần cả Rate Limit và Cost Guard?** Rate limit bảo vệ **tốc độ** (chống spam/DoS theo số request/phút), còn Cost Guard bảo vệ **tiền** (một vài request hợp lệ nhưng prompt/output rất dài vẫn có thể đốt hết ngân sách nếu không giới hạn chi phí). Khi đưa lên production đa instance, trạng thái budget cần lưu trong **Redis** (key theo tháng/ngày có TTL) thay vì in-memory dict.

## Part 5: Scaling & Reliability

### Exercise 5.1–5.5: Implementation notes (`05-scaling-reliability/`)

1. **Phân biệt Liveness (`/health`) và Readiness (`/ready`):**
   - `GET /health` (**Liveness probe**): Kiểm tra process agent còn sống hay bị treo. Trả `200 OK` miễn là app còn phản hồi (ngay cả khi Redis/DB tạm thời mất kết nối), để tránh platform restart nhầm toàn bộ container khi chỉ có dependency gặp sự cố tạm thời.
   - `GET /ready` (**Readiness probe**): Kiểm tra agent đã sẵn sàng nhận traffic chưa (đã startup xong, chưa vào trạng thái shutdown, và kết nối Redis/DB thông suốt). Nếu chưa sẵn sàng hoặc Redis chết, trả `503 Service Unavailable` để Load Balancer tạm ngừng điều phối request mới tới instance đó.

2. **Graceful Shutdown (`SIGTERM`):**
   - Trong `05-scaling-reliability/develop/app.py`, `lifespan` chuyển `_is_ready = False` ngay khi nhận tín hiệu dừng, sau đó chờ `_in_flight_requests` về `0` (tối đa 30s) trước khi đóng process, tránh làm đứt ngang request đang xử lý của người dùng.

3. **Stateless Design & Load Balancing (`--scale agent=3`):**
   - **Vì sao state trong RAM hỏng khi scale?** Mỗi container instance có vùng nhớ RAM riêng biệt. Nếu lưu lịch sử hội thoại trong dict ở RAM, request 1 vào `instance-A` nhưng request 2 qua Nginx lại vào `instance-B` thì `instance-B` không có lịch sử trước đó.
   - **Giải pháp:** Lưu toàn bộ session history vào **Redis** dùng chung giữa các instance.

4. **Kết quả chạy thực tế (`docker compose -p k5-day14-scaling up -d --build --scale agent=3` + `python test_stateless.py`):**
   - `docker compose ps` xác nhận có 3 container `agent` (`healthy`), 1 `nginx` (`0.0.0.0:8080->80/tcp`) và 1 `redis` (`healthy`).
   - Kết quả `test_stateless.py`:
     - `Session ID: bc327c22-4b76-40eb-aefc-705c2ec0a354`
     - 5 requests liên tiếp được Nginx phân tải qua cả 3 instance:
       - Request 1: `instance-652f59`
       - Request 2: `instance-d7d16f`
       - Request 3: `instance-dc886a`
       - Request 4: `instance-652f59`
       - Request 5: `instance-d7d16f`
     - `Total requests: 5` | `Instances used: {'instance-652f59', 'instance-dc886a', 'instance-d7d16f'}`
     - Kiểm tra `/chat/{session_id}/history`: `Total messages: 10` (đủ 5 cặp user/assistant), chứng minh session state được bảo toàn xuyên suốt các instance nhờ Redis.

---

## Part 6: Final Project (`06-lab-complete/`)

Kết quả chạy `python check_production_ready.py` trong `06-lab-complete/` (trên Windows, `RT_GRACEFUL` bị skip tự động do `os.name == "nt"`, còn bài test `docker stop` trong container đã PASS `exit code 0, 0.6s`):

```text
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)        # 238 MB
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ⚠️  Graceful shutdown                         # Docker stop: exit code 0, 0.6s (host SIGTERM skip trên Windows)
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 11/12 tiêu chí đạt · 42/42 checks passed
```
