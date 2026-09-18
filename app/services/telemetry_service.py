import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

class TurnSpan(BaseModel):
    name: str
    duration_ms: float
    started_at: float
    ended_at: float

class TurnTrace(BaseModel):
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tenant_id: Optional[str] = None
    customer_phone: Optional[str] = None
    turn_type: str = "text" # text, audio, image, document
    input_text: str = ""
    output_text: str = ""
    total_latency_ms: float = 0.0
    spans: Dict[str, float] = {}
    status: str = "success" # success, error
    error_type: Optional[str] = None
    error_detail: Optional[str] = None

class TelemetryService:
    def __init__(self, max_traces: int = 150):
        self.max_traces = max_traces
        self.traces: List[TurnTrace] = []

    def start_trace(
        self,
        tenant_id: Optional[str] = None,
        customer_phone: Optional[str] = None,
        turn_type: str = "text"
    ) -> "TraceContext":
        return TraceContext(self, tenant_id, customer_phone, turn_type)

    def record_trace(self, trace: TurnTrace):
        self.traces.append(trace)
        if len(self.traces) > self.max_traces:
            self.traces.pop(0)

    def get_recent_traces(self, limit: int = 50) -> List[dict]:
        return [t.model_dump() for t in reversed(self.traces[-limit:])]

    def get_summary_metrics(self) -> dict:
        total = len(self.traces)
        if total == 0:
            return {
                "total_turns": 0,
                "audio_turns_count": 0,
                "error_rate_pct": 0.0,
                "avg_latency_ms": 0.0,
                "p95_latency_ms": 0.0,
            }

        latencies = sorted([t.total_latency_ms for t in self.traces])
        avg_lat = sum(latencies) / total
        p95_idx = int(total * 0.95)
        p95_lat = latencies[min(p95_idx, total - 1)]

        errors = sum(1 for t in self.traces if t.status == "error")
        audio_count = sum(1 for t in self.traces if t.turn_type == "audio")

        return {
            "total_turns": total,
            "audio_turns_count": audio_count,
            "error_rate_pct": round((errors / total) * 100, 2),
            "avg_latency_ms": round(avg_lat, 1),
            "p95_latency_ms": round(p95_lat, 1),
        }

class TraceContext:
    def __init__(
        self,
        service: TelemetryService,
        tenant_id: Optional[str],
        customer_phone: Optional[str],
        turn_type: str
    ):
        self.service = service
        self.trace = TurnTrace(
            tenant_id=tenant_id,
            customer_phone=customer_phone,
            turn_type=turn_type
        )
        self.start_time = time.perf_counter()
        self._span_starts: Dict[str, float] = {}

    def start_span(self, name: str):
        self._span_starts[name] = time.perf_counter()

    def end_span(self, name: str):
        if name in self._span_starts:
            duration = (time.perf_counter() - self._span_starts[name]) * 1000
            self.trace.spans[name] = round(duration, 2)
            del self._span_starts[name]

    def set_inputs_outputs(self, input_text: str, output_text: str):
        self.trace.input_text = input_text
        self.trace.output_text = output_text

    def set_error(self, error_type: str, detail: str):
        self.trace.status = "error"
        self.trace.error_type = error_type
        self.trace.error_detail = detail

    def finish(self) -> TurnTrace:
        self.trace.total_latency_ms = round((time.perf_counter() - self.start_time) * 1000, 2)
        self.service.record_trace(self.trace)
        return self.trace

telemetry_service = TelemetryService()
