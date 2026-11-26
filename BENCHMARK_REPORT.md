# Benchmark & Observability Report — Day 14

> Copy file này thành `BENCHMARK_REPORT.md` trong repo của bạn và điền đầy đủ.
> Mọi con số phải lấy từ report JSON / CSV / screenshot thật, không ước lượng.

**Họ tên:** Trần Duy Mạnh
**Ngày chạy:** 2026-11-26
**Môi trường:** Windows 11, Python 3.14.5, Docker Desktop (16 CPUs / 7.38 GiB RAM)

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | ≤ 500 ms | Latency cơ bản mock LLM ~120–180ms (+20ms retrieval), p95 ≤ 500ms đảm bảo trải nghiệm mượt và phát hiện sớm khi tail latency hoặc queueing tăng |
| Error rate `/ask` | ≤ 2.0 % | Cho phép sai số nhỏ từ lỗi upstream ngẫu nhiên (`MOCK_ERROR_RATE=0.01`), nhưng chặn sớm khi tỷ lệ lỗi tăng bất thường |
| Accuracy trên golden dataset | ≥ 85 % (chặn regression) | Đảm bảo chất lượng trả lời đúng theo bộ 23 câu hỏi chuẩn trước khi merge/deploy |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 3.65 | 202.6 | 235.0 | 1724.7 | 0.33% | PASS |
| 10 | 36.32 | 203.0 | 467.0 | 1707.7 | 1.00% | PASS |
| 50 | 99.42 | 209.3 | 531.1 | 1707.1 | 1.00% | FAIL |
| 100 | 46.65 | 721.7 | 4337.4 | 4693.3 | 0.67% | FAIL |

**Nhận xét:** RPS có tăng tuyến tính theo concurrency không? Vì sao?

Không. Từ `c=1` → `c=10` → `c=50`, RPS tăng từ 3.65 → 36.32 → 99.42 req/s, nhưng đến `c=100` thì **RPS tụt xuống 46.65 req/s** và p50/p95 nhảy vọt (p95 lên 4337.4 ms). Nguyên nhân là một process `uvicorn` đơn lẻ bị bão hòa event loop / kết nối đồng thời khi quá nhiều request xếp hàng chờ xử lý cùng lúc.

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 218.9 | 476.6 | 517.0 |
| 0.03 (mặc định) | 263.4 | 481.5 | 1708.8 |
| 0.1 | 358.0 | 1706.1 | 1726.8 |

**Nhận xét:** Chỉ số nào nhạy nhất với request chậm? Vì sao SLO không nên đặt theo average?

`p99` (và `p95` khi tỷ lệ slow đạt 10%) nhạy nhất với request chậm: ở `MOCK_SLOW_RATE=0.03`, `avg` chỉ tăng nhẹ từ 218.9 ms lên 263.4 ms, nhưng `p99` nhảy vọt từ 517.0 ms lên **1708.8 ms** (>3.3 lần). Nếu đặt SLO theo average, hệ thống vẫn trông "khỏe" dù thực tế 1%–10% người dùng đang phải chờ gần 2 giây; vì vậy SLO cần đặt theo **p95/p99**.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100.0% (23/23) |
| Avg tokens / câu | 58.2 | 109.0 | 113.7 |
| Tổng cost (USD) | $0.000419 | $0.000760 | $0.000790 |
| Cost / câu đúng (USD) | $0.00041895 | $0.00003619 | $0.00003436 |
| Quality gate | FAIL | PASS (≥ 80%) | PASS (≥ 100%) |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Thêm entry kiến thức về JWT (`["jwt"]`) vào `KNOWLEDGE_BASE` trong `develop/utils/mock_llm.py` |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Thêm entry kiến thức về Kubernetes HPA (`["hpa", "kubernetes", "autoscal"]`) vào `KNOWLEDGE_BASE` trong `develop/utils/mock_llm.py` |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**

Agent `v2` (có RAG retrieval) tốn gần gấp đôi token mỗi câu (109–113.7 vs 58.2) và tổng cost cao hơn (~$0.00079 vs $0.000419), nhưng độ chính xác tăng từ **4.3% lên 100%**, kéo **cost / câu đúng giảm hơn 12 lần** (từ $0.00041895 xuống $0.00003436). Đánh đổi thêm ~20ms cho bước retrieval là hoàn toàn xứng đáng.

*(CI Quality Gate: đã tạo workflow `.github/workflows/eval.yml` chạy `run_eval.py --min-accuracy 0.85`; khi accuracy < 85% hoặc có regression, script trả exit code 1 để chặn merge PR.)*

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [x] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals) — [grafana-dashboard.png](screenshots/grafana-dashboard.png)
- [x] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian) — [jaeger-slow-trace.png](screenshots/jaeger-slow-trace.png)
- [x] Một trace lỗi trong Jaeger (có event `exception`) — [jaeger-error-trace.png](screenshots/jaeger-error-trace.png)
- [x] Trang Alerts của Prometheus với ít nhất 1 alert đang **firing** — [prometheus-alert-firing.png](screenshots/prometheus-alert-firing.png)

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| C | Tải cao Locust (100 users, `mock-llm-small`) | `LLMCostBurnRateHigh` | ~60s (sau khi rate 5m vượt $2/giờ, đạt $5.87–$6.78/giờ) | Cost / giờ & LLM Tokens/s |
| D | `docker pause` 1 instance `agent` (`agent-2`) | `AgentInstanceDown` | ~30s (`for: 30s`, `up{job="agent"} == 0`) | Active Instances / Requests/s theo instance |

**Thí nghiệm E (`AGENT_VERSION=v1`) không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

Chạy **Eval tự động (`eval/run_eval.py`) trên golden dataset trong CI/CD** trước khi deploy (quality gate chặn merge nếu accuracy giảm hoặc có regression), kết hợp theo dõi tỷ lệ retrieval hit (`retrieved=true`) trong JSON log và user feedback / thumbs-down rate ở production.

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất bạn tìm được:

- `trace_id`: `02886541471bf55f00e4ceac87753857`
- Tổng thời gian: `1723.6` ms
- Span chiếm nhiều thời gian nhất: `llm.generate` (`1695.9` ms, `98.4%`)
- Dòng log tương ứng (grep theo `trace_id`):

```json
{"ts": "2026-11-26T08:36:58.892368+00:00", "level": "INFO", "service": "observable-agent", "instance": "3e5997325e22", "event": "http_request", "trace_id": "02886541471bf55f00e4ceac87753857", "span_id": "2668174b628f9f25", "request_id": "4946d017b791", "method": "POST", "route": "/ask", "status": 200, "ms": 1723.6}
```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 66.85 (Aggregated) / 60.58 (`/ask`) | 180 | 310 | 1700 | 1105 (13.9%, gồm giai đoạn warmup đầu khi container mới khởi động) |
| 3 | 66.24 (Aggregated) / 60.09 (`/ask`) | 190 | 260 | 1700 | 66 (0.83%, chỉ lỗi `MOCK_ERROR_RATE` 1%) |

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?

Có: khi tăng từ 1 lên 3 instance, **p95 tổng hợp giảm từ 310 ms xuống 260 ms** (và p95 riêng của `/ask` giảm từ **340 ms xuống 280 ms**), đồng thời không còn lỗi quá tải/khởi động. Tuy nhiên **RPS không tăng gấp 3** (vẫn ~66 req/s) vì Locust giả lập 100 user có `wait_time` giữa các request — nút thắt nằm ở **tốc độ sinh tải cố định của 100 user** và **p99 (~1700 ms)** do bản thân mock LLM cố tình tạo 3% request chậm (`MOCK_SLOW_RATE=0.03`), không phải do thiếu CPU ở agent.

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. ...
  2. ...
  3. ...
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?

...
