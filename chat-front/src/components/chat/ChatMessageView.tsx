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

export function formatToolResult(result: unknown): string {
  if (result == null) {
    return '';
  }
  if (typeof result === 'string') {
    return result;
  }
  if (Array.isArray(result)) {
    return result
      .map((block) => {
        if (typeof block === 'string') {
          return block;
        }
        if (
          block &&
          typeof block === 'object' &&
          (block as { type?: string }).type === 'text' &&
          'text' in block
        ) {
          return String((block as { text: unknown }).text);
        }
        try {
          return JSON.stringify(block, null, 2);
        } catch {
          return String(block);
        }
      })
      .filter(Boolean)
      .join('\n');
  }
  if (
    typeof result === 'object' &&
    (result as { type?: string }).type === 'text' &&
    'text' in result
  ) {
    return String((result as { text: unknown }).text);
  }
  try {
    return JSON.stringify(result, null, 2);
  } catch {
    return String(result);
  }
}

export type ChatToolCallItem = {
  tool_name: string;
  tool_args?: Record<string, unknown> | string | null;
  tool_id: string;
  result?: string | null;
};

export type ChatTodoStatus = 'pending' | 'in_progress' | 'completed';

export type ChatTodoItem = {
  content: string;
  status: ChatTodoStatus;
};

type ChatToolCallMessageProps = {
  title: string;
  toolCalls: ChatToolCallItem[];
  showAvatar?: boolean;
  animate?: boolean;
  enterIndex?: number;
};

const TODO_STATUS_LABEL: Record<ChatTodoStatus, string> = {
  pending: '待办',
  in_progress: '进行中',
  completed: '已完成',
};

function normalizeTodoStatus(raw: unknown): ChatTodoStatus {
  if (raw === 'completed' || raw === 'in_progress' || raw === 'pending') {
    return raw;
  }
  return 'pending';
}

/** 从 write_todos 的 tool_args 解析任务列表 */
export function parseWriteTodosArgs(
  args: Record<string, unknown> | string | null | undefined,
): ChatTodoItem[] {
  let payload: unknown = args;
  if (typeof payload === 'string') {
    try {
      payload = JSON.parse(payload);
    } catch {
      return [];
    }
  }
  if (!payload || typeof payload !== 'object') {
    return [];
  }
  const todosRaw = (payload as { todos?: unknown }).todos;
  if (!Array.isArray(todosRaw)) {
    return [];
  }
  return todosRaw
    .map((item) => {
      if (!item || typeof item !== 'object') {
        return null;
      }
      const content = String((item as { content?: unknown }).content ?? '').trim();
      if (!content) {
        return null;
      }
      return {
        content,
        status: normalizeTodoStatus((item as { status?: unknown }).status),
      };
    })
    .filter((item): item is ChatTodoItem => item != null);
}

function ChatTodoListCard({ tc }: { tc: ChatToolCallItem }) {
  const todos = parseWriteTodosArgs(tc.tool_args);
  const completed = todos.filter((t) => t.status === 'completed').length;
  const inProgress = todos.filter((t) => t.status === 'in_progress').length;
  const allDone = todos.length > 0 && completed === todos.length;
  /** 任务列表本身就是内容，默认展开 */
  const [expanded, setExpanded] = useState(true);

  return (
    <div
      className={`chat-todo-card${allDone ? ' chat-todo-card--done' : ''}${inProgress > 0 ? ' chat-todo-card--running' : ''}${expanded ? ' chat-todo-card--expanded' : ' chat-todo-card--collapsed'}`}
    >
      <button
        type="button"
        className="chat-todo-card__head"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        aria-label={expanded ? '收起任务列表' : '展开任务列表'}
      >
        <span className="chat-todo-card__chevron" aria-hidden />
        <span className="chat-todo-card__badge">任务列表</span>
        <span className="chat-todo-card__progress">
          {todos.length === 0 ? '暂无任务' : `${completed}/${todos.length} 已完成`}
        </span>
        <span className="chat-todo-card__spacer" aria-hidden />
        {allDone ? (
          <span className="chat-todo-card__status chat-todo-card__status--done">全部完成</span>
        ) : inProgress > 0 ? (
          <span className="chat-todo-card__status chat-todo-card__status--running">进行中</span>
        ) : (
          <span className="chat-todo-card__status chat-todo-card__status--pending">待开始</span>
        )}
      </button>
      <div className="chat-todo-card__panel" aria-hidden={!expanded}>
        <div className="chat-todo-card__panel-inner">
          {todos.length === 0 ? (
            <div className="chat-todo-card__empty">未能解析任务内容</div>
          ) : (
            <ul className="chat-todo-card__list">
              {todos.map((todo, index) => (
                <li
                  key={`${tc.tool_id}-${index}`}
                  className={`chat-todo-card__item chat-todo-card__item--${todo.status}`}
                >
                  <span className="chat-todo-card__marker" aria-hidden>
                    {todo.status === 'completed' ? (
                      <svg viewBox="0 0 16 16" fill="none">
                        <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.4" />
                        <path
                          d="M5 8.2 7.1 10.2 11 5.8"
                          stroke="currentColor"
                          strokeWidth="1.5"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                    ) : todo.status === 'in_progress' ? (
                      <svg viewBox="0 0 16 16" fill="none">
                        <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.4" opacity="0.35" />
                        <path
                          d="M8 1.5a6.5 6.5 0 0 1 6.5 6.5"
                          stroke="currentColor"
                          strokeWidth="1.6"
                          strokeLinecap="round"
                        />
                      </svg>
                    ) : (
                      <svg viewBox="0 0 16 16" fill="none">
                        <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.4" />
                      </svg>
                    )}
                  </span>
                  <span className="chat-todo-card__content">{todo.content}</span>
                  <span className="chat-todo-card__item-status">{TODO_STATUS_LABEL[todo.status]}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

function ToolCallGlyph() {
  return (
    <svg className="chat-tool-card__glyph" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path
        d="M10.6 2.4a2.9 2.9 0 0 0-3.9 3.9L3.4 9.6a1.5 1.5 0 1 0 2.1 2.1l3.3-3.3a2.9 2.9 0 0 0 3.9-3.9L11 6.1 9.9 5l.7-2.6Z"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinejoin="round"
      />
      <path d="M9.9 5 11 6.1" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  );
}

function ChatToolCard({ tc }: { tc: ChatToolCallItem }) {
  const resultText = formatToolResult(tc.result);
  const done = resultText !== '';
  const argsText = formatToolArgs(tc.tool_args);
  /** 默认收起，减少实时插入时撑高滚动区导致的抖动 */
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className={`chat-tool-card chat-tool-card--call${done ? ' chat-tool-card--done' : ' chat-tool-card--running'}${expanded ? ' chat-tool-card--expanded' : ' chat-tool-card--collapsed'}`}
    >
      <button
        type="button"
        className="chat-tool-card__head"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        aria-label={expanded ? `收起 ${tc.tool_name}` : `展开 ${tc.tool_name}`}
      >
        <span className="chat-tool-card__chevron" aria-hidden />
        <span className="chat-tool-card__kind" title="工具调用">
          <ToolCallGlyph />
        </span>
        <span className="chat-tool-card__name" title={tc.tool_name}>
          {tc.tool_name}
        </span>
        <span className="chat-tool-card__spacer" aria-hidden />
        {done ? (
          <span className="chat-tool-card__status chat-tool-card__status--done">
            <span className="chat-tool-card__status-dot" aria-hidden />
            已完成
          </span>
        ) : (
          <span className="chat-tool-card__status chat-tool-card__status--pending">
            <span className="chat-tool-card__status-dot" aria-hidden />
            执行中
          </span>
        )}
      </button>
      <div className="chat-tool-card__panel" aria-hidden={!expanded}>
        <div className="chat-tool-card__panel-inner">
          <div className="chat-tool-card__body">
            {argsText ? (
              <div className="chat-tool-card__section">
                <span className="chat-tool-card__section-label">调用参数</span>
                <pre className="chat-tool-card__args">{argsText}</pre>
              </div>
            ) : null}
            {done ? (
              <div className="chat-tool-card__section">
                <span className="chat-tool-card__section-label chat-tool-card__section-label--out">
                  执行结果
                </span>
                <pre className="chat-tool-card__result">{resultText}</pre>
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
          {toolCalls.map((tc) =>
            tc.tool_name === 'write_todos' ? (
              <ChatTodoListCard key={tc.tool_id || `todos-${tc.tool_name}`} tc={tc} />
            ) : (
              <ChatToolCard key={tc.tool_id} tc={tc} />
            ),
          )}
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
