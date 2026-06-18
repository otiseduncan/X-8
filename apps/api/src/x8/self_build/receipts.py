from x8.self_build.contracts import SelfBuildReceipt


class SelfBuildReceiptManager:
    def create(self, action_type: str, status: str, request_id: str = "", task_id: str = "", patch_id: str = "", approval_id: str = "", files_read=None, files_changed=None, tests_run=None, limitations=None) -> SelfBuildReceipt:
        return SelfBuildReceipt(
            action_type=action_type,
            status=status,
            request_id=request_id,
            task_id=task_id,
            patch_id=patch_id,
            approval_id=approval_id,
            files_read=files_read or [],
            files_changed=files_changed or [],
            tests_run=tests_run or [],
            limitations=limitations or [],
        )
