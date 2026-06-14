"""向后兼容：WindowChatRequest 位于 shared，此处 re-export 供 orchestration 内部引用。"""

from app.chat.shared.window_models import WindowChatRequest, normalize_window_file_ids

__all__ = ["WindowChatRequest", "normalize_window_file_ids"]
