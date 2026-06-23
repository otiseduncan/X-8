from x8.kernel.response_planner import ResponsePlanner as _ResponsePlanner


class ResponsePlanner(_ResponsePlanner):
    def classify(self, message: str, has_attachments: bool = False) -> str:
        if message.lower().strip() == "ready to pull":
            return "normal_chat"
        return super().classify(message, has_attachments=has_attachments)
