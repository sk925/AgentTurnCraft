import type { ReactNode } from 'react';

/** AI 晶体图标 */
export function AiCrystalIcon() {
  return (
    <span className="chat-ai-crystal" aria-hidden>
      <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="chat-crystal-g" x1="8" y1="4" x2="32" y2="36" gradientUnits="userSpaceOnUse">
            <stop stopColor="#38bdf8" />
            <stop offset="0.5" stopColor="#6366f1" />
            <stop offset="1" stopColor="#818cf8" />
          </linearGradient>
        </defs>
        <path
          d="M20 4L34 14V26L20 36L6 26V14L20 4Z"
          stroke="url(#chat-crystal-g)"
          strokeWidth="1.5"
          fill="rgba(99, 102, 241, 0.12)"
        />
        <path d="M20 10L27 15V25L20 30L13 25V15L20 10Z" fill="url(#chat-crystal-g)" fillOpacity="0.35" />
      </svg>
    </span>
  );
}

/** 思考中：三点波浪 */
export function ChatThinkingIndicator({ label = '正在思考' }: { label?: string }) {
  return (
    <div className="chat-msg chat-msg--ai chat-msg--thinking" role="status" aria-live="polite">
      <div className="chat-msg__ai-avatar">
        <AiCrystalIcon />
      </div>
      <div className="chat-msg__body">
        <div className="chat-msg__header">
          <span className="chat-msg__name">AI</span>
          <span className="chat-msg__status chat-msg__status--pulse" title="在线" />
        </div>
        <div className="chat-thinking-wave" aria-hidden>
          <span className="chat-thinking-wave__bar" />
          <span className="chat-thinking-wave__bar" />
          <span className="chat-thinking-wave__bar" />
          <span className="chat-thinking-wave__bar" />
          <span className="chat-thinking-wave__bar" />
        </div>
        <span className="chat-thinking-label">{label}</span>
      </div>
    </div>
  );
}

type ChatUserMessageProps = {
  content: string;
  attachments?: ReactNode;
  enterIndex?: number;
};

export function ChatUserMessage({ content, attachments, enterIndex = 0 }: ChatUserMessageProps) {
  return (
    <div
      className="chat-msg chat-msg--user chat-msg--enter"
      style={{ animationDelay: `${Math.min(enterIndex, 12) * 40}ms` }}
    >
      <div className="chat-user-message-stack">
        {attachments}
        {content ? (
          <div className="chat-msg__bubble-user">
            <p className="chat-msg__text">{content}</p>
          </div>
        ) : null}
      </div>
    </div>
  );
}

type ChatAiMessageProps = {
  title: string;
  content: string;
  streaming?: boolean;
  enterIndex?: number;
};

export function ChatAiMessage({ title, content, streaming, enterIndex = 0 }: ChatAiMessageProps) {
  const online = !streaming || content.length > 0;

  return (
    <div
      className={`chat-msg chat-msg--ai chat-msg--enter${streaming ? ' chat-msg--streaming' : ''}`}
      style={{ animationDelay: `${Math.min(enterIndex, 12) * 40}ms` }}
    >
      <div className="chat-msg__ai-avatar">
        <AiCrystalIcon />
      </div>
      <div className="chat-msg__body">
        <div className="chat-msg__header">
          <span className="chat-msg__name">{title}</span>
          <span
            className={`chat-msg__status${online ? ' chat-msg__status--pulse' : ''}`}
            title={streaming ? '生成中' : '在线'}
          />
        </div>
        <div className="chat-msg__content">
          {content ? <p className="chat-msg__text">{content}</p> : null}
          {streaming ? <span className="chat-stream-cursor" aria-hidden /> : null}
        </div>
      </div>
    </div>
  );
}
