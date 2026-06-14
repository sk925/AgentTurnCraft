"""已迁移至 app.chat.shared.window_models，此处保留兼容 re-export。"""

from app.chat.shared.window_models import WindowChatRequest, normalize_window_file_ids

__all__ = ["WindowChatRequest", "normalize_window_file_ids"]
