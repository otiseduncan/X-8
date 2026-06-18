from x8.operator.contracts import OperatorResourceBudget


class CancellationToken:
    def __init__(self) -> None:
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True


class TimeoutPolicy:
    def __init__(self, seconds: int) -> None:
        self.seconds = seconds


class ConcurrencyPolicy:
    def __init__(self, max_parallel_jobs: int) -> None:
        self.max_parallel_jobs = max_parallel_jobs


class ResourceGuard:
    def __init__(self, budget: OperatorResourceBudget) -> None:
        self.budget = budget

    def truncate(self, value: str) -> tuple[str, bool]:
        if len(value) <= self.budget.max_output_chars:
            return value, False
        return value[: self.budget.max_output_chars] + "\n[truncated]", True

    def allowed_file_size(self, size_bytes: int) -> bool:
        return size_bytes <= self.budget.max_file_bytes
