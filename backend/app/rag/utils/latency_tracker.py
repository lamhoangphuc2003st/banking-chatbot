# app/rag/utils/latency_tracker.py
import time
from app.rag.utils.logger import get_logger

logger = get_logger(__name__)


class LatencyTracker:
    """
    Đo latency từng bước trong pipeline.

    Dùng:
        tracker = LatencyTracker(session_id)
        ...
        tracker.mark("rewrite_clarify")
        ...
        tracker.mark("intent_redis_embed")
        ...
        tracker.mark("retrieval")
        ...
        tracker.mark("generation")

        trace["latency_breakdown"] = tracker.to_dict()
    """

    # Thứ tự chuẩn của các checkpoint — dùng để tính delta đúng thứ tự
    STANDARD_ORDER = [
        "rewrite_clarify",
        "intent_redis_embed",
        "semantic_cache",
        "retrieval",
        "generation",
    ]

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.start = time.perf_counter()
        self.checkpoints: dict[str, int] = {}

    def mark(self, name: str):
        """Ghi lại thời điểm hiện tại (ms từ start)."""
        self.checkpoints[name] = round((time.perf_counter() - self.start) * 1000)

    def elapsed_ms(self) -> int:
        """Thời gian đã trôi qua từ khi khởi tạo."""
        return round((time.perf_counter() - self.start) * 1000)

    def to_dict(self) -> dict:
        """
        Trả về:
        - checkpoints_ms: thời điểm tuyệt đối từng bước
        - deltas_ms: thời gian từng bước chiếm (hiệu giữa 2 checkpoint liền nhau)
        - total_ms: tổng thời gian đến hiện tại
        """
        total = self.elapsed_ms()

        # Sắp xếp theo thứ tự chuẩn, unknown thì xếp cuối
        def sort_key(item):
            name, _ = item
            try:
                return self.STANDARD_ORDER.index(name)
            except ValueError:
                return len(self.STANDARD_ORDER)

        sorted_steps = sorted(self.checkpoints.items(), key=sort_key)

        deltas: dict[str, int] = {}
        prev = 0
        for name, ms in sorted_steps:
            deltas[f"{name}_ms"] = ms - prev
            prev = ms

        return {
            "total_ms": total,
            "checkpoints_ms": dict(sorted_steps),
            "deltas_ms": deltas,
        }

    def log_summary(self):
        """In breakdown ra log ở mức INFO."""
        d = self.to_dict()
        parts = [f"{k}={v}" for k, v in d["deltas_ms"].items()]
        logger.info(
            f"[{self.session_id[:8]}] Latency breakdown — "
            f"total={d['total_ms']}ms | " + " | ".join(parts)
        )