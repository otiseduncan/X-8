from datetime import datetime, timezone

from x8.kernel.contracts import KernelReceipt


class KernelReceiptBuilder:
    def build(
        self,
        lane: str,
        status: str,
        started_at: datetime,
        model: str,
        context_sources: list[str],
        attachments: list[str],
        tools: list[str],
        limitations: list[str],
        fallback_used: bool = False,
        timed_out: bool = False,
        timeout_seconds: float = 0.0,
        failure_reason: str = "",
    ) -> KernelReceipt:
        return KernelReceipt(
            kernel_lane=lane,
            model_selected=model,
            fallback_used=fallback_used,
            timed_out=timed_out,
            timeout_seconds=timeout_seconds,
            failure_reason=failure_reason,
            context_sources_used=context_sources,
            attachments_used=attachments,
            tools_called=tools,
            status=status,
            limitations=limitations,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
        )
