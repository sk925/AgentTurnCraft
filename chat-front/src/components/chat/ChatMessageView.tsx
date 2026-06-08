import { useState, type ReactNode } from 'react';

/** AI 晶体图标 */
export function AiCrystalIcon() {
  return (
    <span className="chat-ai-crystal" aria-hidden>
      <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="chat-crystal-g" x1="8" y1="4" x2="32" y2="36" gradientUnits="userSpaceOnUse">
            <stop stopColor="#60a5fa" />
            <stop offset="0.5" stopColor="#2563eb" />
            <stop offset="1" stopColor="#3b82f6" />
          </linearGradient>
        </defs>
        <path
          d="M20 4L34 14V26L20 36L6 26V14L20 4Z"
          stroke="url(#chat-crystal-g)"
          strokeWidth="1.5"
          fill="rgba(37, 99, 235, 0.12)"
        />
        <path d="M20 10L27 15V25L20 30L13 25V15L20 10Z" fill="url(#chat-crystal-g)" fillOpacity="0.35" />
      </svg>
    </span>
  );
}

function ChatAiAvatarSlot({ show }: { show: boolean }) {
  if (show) {
    return (
      <div className="chat-msg__ai-avatar">
        <AiCrystalIcon />
      </div>
    );
  }
  return <div className="chat-msg__ai-avatar chat-msg__ai-avatar--spacer" aria-hidden />;
}

/** 思考中：三点波浪 */
export function ChatThinkingIndicator({
  label = '正在思考',
  showAvatar = true,
}: {
  label?: string;
  showAvatar?: boolean;
}) {
  return (
    <div
      className={`chat-msg chat-msg--ai chat-msg--thinking${showAvatar ? '' : ' chat-msg--continued'}`}
      role="status"
      aria-live="polite"
    >
      <ChatAiAvatarSlot show={showAvatar} />
      <div className="chat-msg__body">
        {showAvatar ? (
          <div className="chat-msg__header">
            <span className="chat-msg__name">AI</span>
            <span className="chat-msg__status chat-msg__status--pulse" title="在线" />
          </div>
        ) : null}
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
  animate?: boolean;
  enterIndex?: number;
};

export function ChatUserMessage({ content, attachments, animate = true, enterIndex = 0 }: ChatUserMessageProps) {
  return (
    <div
      className={`chat-msg chat-msg--user${animate ? ' chat-msg--enter' : ' chat-msg--settled'}`}
      style={animate ? { animationDelay: `${Math.min(enterIndex, 12) * 40}ms` } : undefined}
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
  showAvatar?: boolean;
  animate?: boolean;
  enterIndex?: number;
};

function formatToolArgs(args: Record<string, unknown> | string | null | undefined): string {
  if (args == null) {
    return '';
  }
  if (typeof args === 'string') {
    return args;
  }
  try {
    return JSON.stringify(args, null, 2);
  } catch {
    return String(args);
  }
}

export type ChatToolCallItem = {
  tool_name: string;
  tool_args?: Record<string, unknown> | string | null;
  tool_id: string;
  result?: string | null;
};

type ChatToolCallMessageProps = {
  title: string;
  toolCalls: ChatToolCallItem[];
  showAvatar?: boolean;
  animate?: boolean;
  enterIndex?: number;
};

function ChatToolCard({ tc }: { tc: ChatToolCallItem }) {
  const done = tc.result != null && tc.result !== '';
  const argsText = formatToolArgs(tc.tool_args);
  /** 默认收起，减少实时插入时撑高滚动区导致的抖动 */
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className={`chat-tool-card chat-tool-card--call${done ? ' chat-tool-card--done' : ''}${expanded ? ' chat-tool-card--expanded' : ' chat-tool-card--collapsed'}`}
    >
      <button
        type="button"
        className="chat-tool-card__head"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        aria-label={expanded ? `收起 ${tc.tool_name}` : `展开 ${tc.tool_name}`}
      >
        <span className="chat-tool-card__chevron" aria-hidden />
        <span className="chat-tool-card__badge">工具调用</span>
        <span className="chat-tool-card__name">{tc.tool_name}</span>
        {done ? (
          <span className="chat-tool-card__badge chat-tool-card__badge--out">已完成</span>
        ) : (
          <span className="chat-tool-card__badge chat-tool-card__badge--pending">执行中</span>
        )}
        {!expanded && !done ? (
          <span className="chat-tool-card__head-hint">等待执行结果…</span>
        ) : null}
      </button>
      <div className="chat-tool-card__panel" aria-hidden={!expanded}>
        <div className="chat-tool-card__panel-inner">
          <div className="chat-tool-card__body">
            {argsText ? <pre className="chat-tool-card__args">{argsText}</pre> : null}
            {done ? (
              <div className="chat-tool-card__result-block">
                <span className="chat-tool-card__result-label">执行结果</span>
                <pre className="chat-tool-card__result">{tc.result}</pre>
              </div>
            ) : (
              <div className="chat-tool-card__pending">等待执行结果…</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/** 历史记录：工具调用 + 合并后的工具结果（同一张卡片） */
export function ChatToolCallMessage({
  title,
  toolCalls,
  showAvatar = true,
  animate = true,
  enterIndex = 0,
}: ChatToolCallMessageProps) {
  if (toolCalls.length === 0) {
    return null;
  }

  return (
    <div
      className={`chat-msg chat-msg--ai chat-msg--tool${showAvatar ? '' : ' chat-msg--continued'}${animate ? ' chat-msg--enter' : ' chat-msg--settled'}`}
      style={animate ? { animationDelay: `${Math.min(enterIndex, 12) * 40}ms` } : undefined}
    >
      <ChatAiAvatarSlot show={showAvatar} />
      <div className="chat-msg__body">
        {showAvatar ? (
          <div className="chat-msg__header">
            <span className="chat-msg__name">{title}</span>
          </div>
        ) : null}
        <div className="chat-tool-stack">
          {toolCalls.map((tc) => (
            <ChatToolCard key={tc.tool_id} tc={tc} />
          ))}
        </div>
      </div>
    </div>
  );
}

export function ChatAiMessage({
  title,
  content,
  streaming,
  showAvatar = true,
  animate = true,
  enterIndex = 0,
}: ChatAiMessageProps) {
  const online = !streaming || content.length > 0;

  return (
    <div
      className={`chat-msg chat-msg--ai${showAvatar ? '' : ' chat-msg--continued'}${animate ? ' chat-msg--enter' : ' chat-msg--settled'}${streaming ? ' chat-msg--streaming' : ''}`}
      style={animate ? { animationDelay: `${Math.min(enterIndex, 12) * 40}ms` } : undefined}
    >
      <ChatAiAvatarSlot show={showAvatar} />
      <div className="chat-msg__body">
        {showAvatar ? (
          <div className="chat-msg__header">
            <span className="chat-msg__name">{title}</span>
            <span
              className={`chat-msg__status${online ? ' chat-msg__status--pulse' : ''}`}
              title={streaming ? '生成中' : '在线'}
            />
          </div>
        ) : null}
        <div className="chat-msg__content">
          {content ? <p className="chat-msg__text">{content}</p> : null}
          {streaming ? <span className="chat-stream-cursor" aria-hidden /> : null}
        </div>
      </div>
    </div>
  );
}
