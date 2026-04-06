"""
locustfile.py — Load testing cho RAG Banking Chatbot

Cài đặt:
    pip install locust

Chạy Web UI:
    locust -f locustfile.py --host=http://localhost:8000
    # Mở http://localhost:8089

Chạy headless (CI):
    locust -f locustfile.py --host=https://banking-chatbot-1-081l.onrender.com --users=100 --spawn-rate=10 --run-time=5m --headless --csv=results/stress

Các scenario theo thứ tự tăng dần:
    Baseline : 5 users   → latency bình thường
    Normal   : 20 users  → traffic thường ngày
    Peak     : 50 users  → giờ cao điểm
    Stress   : 100 users → tìm điểm gãy
"""

import random
import time
from locust import HttpUser, task, between, events


# -------------------------------------------------------
# Kịch bản test — gần với traffic thực tế nhất có thể
# Format: (weight, message, history)
# -------------------------------------------------------
SCENARIOS = [
    # --- Discovery / Listing (30%) ---
    (15, "VCB có cho vay tiêu dùng không?", []),
    (10, "Vietcombank có những loại thẻ tín dụng nào?", []),
    ( 5, "VCB có cho vay mua nhà không?", []),

    # --- Single product detail (40%) ---
    (15, "Điều kiện vay mua ô tô tại Vietcombank là gì?", []),
    (10, "Phí thường niên thẻ Visa Platinum Vietcombank bao nhiêu?", []),
    (15, "Hồ sơ vay tín chấp theo lương cần những gì?", []),

    # --- Multi-turn — context từ turn trước (20%) ---
    (10, "Điều kiện của các gói đó là gì?", [
        {"role": "user",      "content": "VCB có gói vay tiêu dùng nào?"},
        {"role": "assistant", "content": "Có 3 gói: Vay tín chấp theo lương, Vay cầm cố giấy tờ có giá, Vay tiêu dùng có tài sản bảo đảm"},
    ]),
    (10, "Hồ sơ cần gì?", [
        {"role": "user",      "content": "Điều kiện vay mua ô tô Vietcombank?"},
        {"role": "assistant", "content": "Điều kiện: 18-60 tuổi, tài sản bảo đảm là bất động sản hoặc ô tô..."},
    ]),

    # --- Decompose — nhiều sub_queries (10%) ---
    (10, "Lợi ích và phí thường niên thẻ Visa Platinum và Mastercard World là gì?", []),
]

# Build weighted pool
_pool = []
for weight, msg, hist in SCENARIOS:
    _pool.extend([(msg, hist)] * weight)


def pick_scenario():
    return random.choice(_pool)


# -------------------------------------------------------
# Locust User
# -------------------------------------------------------

class ChatbotUser(HttpUser):
    """Giả lập 1 user chat với chatbot — bao gồm thinking time."""

    wait_time = between(3, 10)  # nghĩ 3-10s giữa các tin nhắn

    def on_start(self):
        self.session_id = f"loadtest-{random.randint(100000, 999999)}"
        self.ttft_samples = []   # time-to-first-token samples

    # --- Main task: gửi tin nhắn ---
    @task(9)
    def send_message(self):
        message, history = pick_scenario()

        # api.py nhận messages: List[{role, content}]
        # history là các turn trước, message là turn hiện tại
        messages = history + [{"role": "user", "content": message}]

        payload = {
            "messages": messages,
            "session_id": self.session_id,
        }

        request_start = time.perf_counter()
        first_token_ms = None
        chunks = []

        with self.client.post(
            "/chat",
            json=payload,
            stream=True,
            catch_response=True,
            name="/chat [total]",   # tên metric — đo total time
            timeout=60,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"HTTP {resp.status_code}")
                return

            try:
                # Consume TOÀN BỘ stream trước khi đánh dấu xong
                for chunk in resp.iter_content(chunk_size=None):
                    if chunk:
                        if first_token_ms is None:
                            # Đo time-to-first-token riêng
                            first_token_ms = (time.perf_counter() - request_start) * 1000
                        chunks.append(chunk)

                if not chunks:
                    resp.failure("Empty response — no tokens received")
                    return

                total_ms = (time.perf_counter() - request_start) * 1000
                total_bytes = sum(len(c) for c in chunks)

                # Metric 1: TTFT (time to first token)
                if first_token_ms:
                    events.request.fire(
                        request_type="TTFT",
                        name="/chat [first_token]",
                        response_time=first_token_ms,
                        response_length=total_bytes,
                        exception=None,
                        context={},
                    )

                # Metric 2: Total response time (ghi đè Locust default)
                events.request.fire(
                    request_type="POST",
                    name="/chat [total]",
                    response_time=total_ms,
                    response_length=total_bytes,
                    exception=None,
                    context={},
                )
                resp.success()

            except Exception as e:
                resp.failure(f"Stream error: {e}")

    # --- Health check (thấp tần suất) ---
    @task(1)
    def health_check(self):
        with self.client.get(
            "/health",
            name="/health",
            catch_response=True,
            timeout=5,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Health check failed: {resp.status_code}")


# -------------------------------------------------------
# StressUser — wait_time ngắn để tạo tải cao
# Dùng khi muốn test peak/stress nhanh hơn
# locust -f locustfile.py --host=... --users=50 -u StressUser
# -------------------------------------------------------

class StressUser(ChatbotUser):
    """Giống ChatbotUser nhưng không có thinking time — tối đa RPS."""
    wait_time = between(0, 1)


# -------------------------------------------------------
# Report khi kết thúc
# -------------------------------------------------------

@events.quitting.add_listener
def on_quitting(environment, **kwargs):
    stats = environment.stats

    print("\n" + "=" * 60)
    print("  LOAD TEST SUMMARY")
    print("=" * 60)

    for name in ["/chat [total]", "/chat [first_token]", "/health"]:
        for method in ["POST", "GET", "TTFT"]:
            s = stats.get(name, method)
            if s and s.num_requests > 0:
                print(f"\n  {method} {name}")
                print(f"    Requests   : {s.num_requests}")
                print(f"    Failures   : {s.num_failures} ({s.fail_ratio*100:.1f}%)")
                print(f"    P50        : {s.get_response_time_percentile(0.5):.0f} ms")
                print(f"    P90        : {s.get_response_time_percentile(0.9):.0f} ms")
                print(f"    P95        : {s.get_response_time_percentile(0.95):.0f} ms")
                print(f"    P99        : {s.get_response_time_percentile(0.99):.0f} ms")
                print(f"    RPS        : {s.current_rps:.2f}")

    print("\n" + "=" * 60)

    # Đánh giá tự động
    chat = stats.get("/chat [total]", "POST")
    if chat and chat.num_requests > 0:
        p95 = chat.get_response_time_percentile(0.95)
        fail = chat.fail_ratio * 100
        print("\n  Assessment:")
        if fail > 5:
            print(f"  🔴 FAIL — Error rate {fail:.1f}% > 5%")
        elif p95 > 20000:
            print(f"  🔴 FAIL — P95 {p95:.0f}ms > 20s (system overloaded)")
        elif p95 > 12000:
            print(f"  🟡 DEGRADED — P95 {p95:.0f}ms > 12s")
        else:
            print(f"  ✅ OK — P95 {p95:.0f}ms, fail rate {fail:.1f}%")