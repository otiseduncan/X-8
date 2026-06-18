from x8.operator.contracts import JobState, OperatorJob, OperatorJobStatus


class OperatorJobEngine:
    def create(self, task_id: str, waiting_for_approval: bool) -> OperatorJob:
        state = JobState.WAITING_FOR_APPROVAL if waiting_for_approval else JobState.COMPLETED
        return OperatorJob(task_id=task_id, state=state, status=state.value, summary=f"Operator job {state.value}.")

    def status(self, job: OperatorJob, approvals=None, observations=None, results=None) -> OperatorJobStatus:
        return OperatorJobStatus(
            id=f"status_{job.id}",
            job_id=job.id,
            task_id=job.task_id,
            state=job.state,
            status=job.state.value,
            summary=job.summary,
            approvals=approvals or [],
            observations=observations or [],
            results=results or [],
        )

    def cancel(self, job: OperatorJob) -> OperatorJob:
        job.state = JobState.CANCELLED
        job.status = JobState.CANCELLED.value
        job.summary = "Operator job cancelled before execution."
        return job
