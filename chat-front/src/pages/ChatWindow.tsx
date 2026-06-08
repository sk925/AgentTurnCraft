import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type FocusEvent,
  type KeyboardEvent,
} from 'react';
import {
  Avatar,
  Badge,
  Button,
  Card,
  Checkbox,
  Col,
  Empty,
  Form,
  Input,
  Radio,
  Row,
  Select,
  Space,
  Switch,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd';
import {
  ArrowUpOutlined,
  FileExcelOutlined,
  FileImageOutlined,
  FileOutlined,
  FilePdfOutlined,
  FilePptOutlined,
  FileTextOutlined,
  FileWordOutlined,
  CloseOutlined,
  LeftOutlined,
  LoadingOutlined,
  PlusOutlined,
  RightOutlined,
  RobotOutlined,
  TeamOutlined,
  UserOutlined,
} from '@ant-design/icons';
import {
  agentsApi,
  chatPathForSessionType,
  chatWebSocket,
  chatWindowApi,
  getBackendErrorMessage,
  getCurrentUserIdFromToken,
  goLoginPage,
  groupsApi,
  isUserLoggedIn,
  requestOpenLoginModal,
  sessionsApi,
  uploadFileApi,
} from '../api';
import type {
  Agent,
  ChatWindowEvent,
  Group,
  SessionMessage,
  SessionToolCallItem,
  SessionType,
  SpeakerInterruptArgs,
  WSServerMessage,
  WorkspaceArtifactFile,
} from '../api';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { usePortalSessions } from '../PortalSessionsContext';
import {
  ChatAiMessage,
  ChatThinkingIndicator,
  ChatToolCallMessage,
  ChatUserMessage,
} from '../components/chat/ChatMessageView';
import './ChatWindow.css';

const { TextArea } = Input;

const SHOW_TOOL_CALLS_STORAGE_KEY = 'free-chat:show-tool-calls';
const WORKSPACE_COLLAPSED_STORAGE_KEY = 'free-chat:workspace-collapsed';

function readShowToolCallsPreference(): boolean {
  try {
    const raw = localStorage.getItem(SHOW_TOOL_CALLS_STORAGE_KEY);
    if (raw === '0' || raw === 'false') {
      return false;
    }
    return true;
  } catch {
    return true;
  }
}

function readWorkspaceCollapsedPreference(): boolean {
  try {
    const raw = localStorage.getItem(WORKSPACE_COLLAPSED_STORAGE_KEY);
    return raw === '1' || raw === 'true';
  } catch {
    return false;
  }
}

/** 上传完成后的附件元数据（用于气泡展示） */
type ChatAttachmentMeta = {
  id: string;
  file_name: string;
  file_type: string;
  type_label: string;
  preview_url?: string | null;
};

function friendlyFileTypeLabel(mime: string, fileName: string): string {
  const m = (mime || '').toLowerCase();
  const ext = (fileName.split('.').pop() || '').toLowerCase();
  if (m.includes('spreadsheetml') || m.includes('ms-excel') || ext === 'xlsx' || ext === 'xls') return 'Excel';
  if (m.includes('wordprocessingml') || m.includes('msword') || ext === 'docx' || ext === 'doc') return 'Word';
  if (m.includes('presentationml') || m.includes('powerpoint') || ext === 'pptx' || ext === 'ppt') return 'PPT';
  if (m === 'application/pdf' || ext === 'pdf') return 'PDF';
  if (m.startsWith('image/')) return '图片';
  if (m.startsWith('video/')) return '视频';
  if (m.startsWith('audio/')) return '音频';
  if (m.startsWith('text/') || ext === 'txt' || ext === 'csv' || ext === 'md' || ext === 'json') return '文本';
  if (ext === 'zip' || ext === 'rar' || ext === '7z') return '压缩包';
  if (ext) return ext.toUpperCase();
  return '文件';
}

function attachmentIconForFile(mime: string, fileName: string, size: number = 28) {
  const m = (mime || '').toLowerCase();
  const ext = (fileName.split('.').pop() || '').toLowerCase();
  const style = { fontSize: size };
  if (m.includes('spreadsheetml') || m.includes('ms-excel') || ext === 'xlsx' || ext === 'xls') {
    return <FileExcelOutlined style={{ ...style, color: '#107c41' }} />;
  }
  if (m.includes('wordprocessingml') || m.includes('msword') || ext === 'docx' || ext === 'doc') {
    return <FileWordOutlined style={{ ...style, color: '#185abd' }} />;
  }
  if (m.includes('presentationml') || ext === 'pptx' || ext === 'ppt') {
    return <FilePptOutlined style={{ ...style, color: '#d24726' }} />;
  }
  if (m === 'application/pdf' || ext === 'pdf') {
    return <FilePdfOutlined style={{ ...style, color: '#e53935' }} />;
  }
  if (m.startsWith('image/')) {
    return <FileImageOutlined style={{ ...style, color: '#0891b2' }} />;
  }
  if (m.startsWith('text/') || ext === 'txt' || ext === 'md' || ext === 'csv' || ext === 'json') {
    return <FileTextOutlined style={{ ...style, color: '#64748b' }} />;
  }
  return <FileOutlined style={{ ...style, color: '#64748b' }} />;
}

type UserAttachmentCardProps = {
  fileName: string;
  mime: string;
  typeLabel: string;
  uploading?: boolean;
  previewUrl?: string | null;
  onRemove?: () => void;
  /** 输入框内预览条略紧凑 */
  compact?: boolean;
};

function UserAttachmentCard({
  fileName,
  mime,
  typeLabel,
  uploading,
  previewUrl,
  onRemove,
  compact = false,
}: UserAttachmentCardProps) {
  const openPreview = () => {
    if (previewUrl && !uploading) {
      window.open(previewUrl, '_blank', 'noopener,noreferrer');
    }
  };

  const rootClass = [
    'chat-attachment-card',
    previewUrl && !uploading ? 'chat-attachment-card--clickable' : '',
    compact ? 'chat-attachment-card--compact chat-attachment-card--composer' : '',
    uploading ? 'chat-attachment-card--uploading' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div
      className={rootClass}
      onClick={previewUrl && !uploading ? () => openPreview() : undefined}
      onKeyDown={
        previewUrl && !uploading
          ? (ev) => {
              if (ev.key === 'Enter' || ev.key === ' ') {
                ev.preventDefault();
                openPreview();
              }
            }
          : undefined
      }
      role={previewUrl && !uploading ? 'button' : undefined}
      tabIndex={previewUrl && !uploading ? 0 : undefined}
    >
      <div className="chat-attachment-card__icon">
        {uploading ? (
          <LoadingOutlined className="chat-attachment-card__loading-icon" />
        ) : (
          attachmentIconForFile(mime, fileName, compact ? 22 : 28)
        )}
      </div>
      <div className="chat-attachment-card__meta">
        <div className="chat-attachment-card__name" title={fileName}>
          {fileName}
        </div>
        <div className="chat-attachment-card__type">{typeLabel}</div>
      </div>
      {onRemove != null && (
        <button
          type="button"
          className="chat-attachment-card__remove"
          onClick={(ev) => {
            ev.stopPropagation();
            onRemove();
          }}
          aria-label="移除附件"
        >
          <CloseOutlined />
        </button>
      )}
    </div>
  );
}

type ChatMessageKind = 'user' | 'speaker' | 'tool_call';

type ChatMessage = {
  id: string;
  kind: ChatMessageKind;
  role: 'user' | 'system' | 'speaker';
  title: string;
  content: string;
  speakerId?: number;
  /** 当前是否仍在接收 speaker_stream */
  streaming?: boolean;
  /** 为 false 时跳过入场动画（历史记录），减轻滚动重绘 */
  animate?: boolean;
  /** 用户消息附带的文件（仅前端展示；历史接口未返回时为空） */
  attachments?: ChatAttachmentMeta[];
  /** 历史 tool_call */
  toolCalls?: SessionToolCallItem[];
};

/** tool_out 合并到对应 tool_call 卡片（按 tool_id 匹配；可选限定 speaker） */
function attachToolResultToMessages(
  messages: ChatMessage[],
  toolCallId: string | null | undefined,
  result: string,
  speakerId?: number,
): ChatMessage[] {
  if (!toolCallId) {
    return messages;
  }
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i];
    if (m.kind !== 'tool_call' || !m.toolCalls?.length) {
      continue;
    }
    if (speakerId != null && m.speakerId !== speakerId) {
      continue;
    }
    const ti = m.toolCalls.findIndex((t) => t.tool_id === toolCallId);
    if (ti < 0) {
      continue;
    }
    const toolCalls = m.toolCalls.map((t, idx) => (idx === ti ? { ...t, result } : t));
    const next = [...messages];
    next[i] = { ...m, toolCalls };
    return next;
  }
  return messages;
}

function clearSpeakerStreaming(messages: ChatMessage[], speakerId: number): ChatMessage[] {
  return messages.map((m) =>
    m.role === 'speaker' && m.streaming && m.speakerId === speakerId
      ? { ...m, streaming: false }
      : m,
  );
}

function normalizeSpeakerId(id: unknown): number | null {
  if (id == null || id === '') {
    return null;
  }
  const n = Number(id);
  return Number.isFinite(n) ? n : null;
}

/** 将接口记录转为时间线消息；tool_out 合并到对应 tool_call 卡片（按 tool_call_id 匹配 tool_id） */
function sessionRecordsToChatMessages(records: SessionMessage[]): ChatMessage[] {
  const messages: ChatMessage[] = [];

  const attachToolResult = (toolCallId: string | null | undefined, result: string) => {
    const next = attachToolResultToMessages(messages, toolCallId, result);
    if (next !== messages) {
      messages.length = 0;
      messages.push(...next);
    }
  };

  records.forEach((record, index) => {
    if (record.role_type === 'user' || record.message_type === 'user') {
      const attachments =
        record.file_info && record.file_info.length > 0
          ? record.file_info.map((f) => ({
              id: f.file_id,
              file_name: f.file_name,
              file_type: f.file_type || 'application/octet-stream',
              type_label: friendlyFileTypeLabel(f.file_type || '', f.file_name),
              preview_url: f.file_url,
            }))
          : undefined;
      messages.push({
        id: `history-user-${index}`,
        kind: 'user',
        role: 'user',
        title: record.speaker_name || '我',
        content: record.message_content,
        attachments,
        animate: false,
      });
      return;
    }

    const speakerTitle = record.speaker_name || '超级助手';
    const speakerId = record.speaker_id ?? undefined;
    const msgType = (record.message_type || '').toLowerCase();

    if (record.role_type === 'speaker' && msgType === 'tool_out') {
      attachToolResult(record.tool_call_id, record.message_content);
      return;
    }

    if (record.role_type === 'speaker' && msgType === 'tool_call') {
      const toolCalls = Array.isArray(record.tool_calls) ? [...record.tool_calls] : [];
      if (toolCalls.length === 0) {
        return;
      }
      messages.push({
        id: `history-tool-call-${index}`,
        kind: 'tool_call',
        role: 'speaker',
        title: speakerTitle,
        content: '',
        speakerId,
        toolCalls,
        animate: false,
      });
      return;
    }

    if (msgType === 'todo_list' || msgType === 'interactive') {
      return;
    }

    const text = (record.message_content || '').trim();
    if (!text) {
      return;
    }

    messages.push({
      id: `history-speaker-${index}`,
      kind: 'speaker',
      role: 'speaker',
      title: speakerTitle,
      content: record.message_content,
      speakerId,
      animate: false,
    });
  });

  return messages;
}

/** 发言人侧消息的唯一键（用户消息返回 null） */
function getMessageSpeakerKey(msg: ChatMessage): string | null {
  if (msg.kind === 'user' || msg.role === 'user') {
    return null;
  }
  if (msg.speakerId != null) {
    return `id:${msg.speakerId}`;
  }
  return `name:${msg.title}`;
}

/** 相对前序可见消息，该 speaker 是否应显示头像 */
function shouldShowSpeakerAvatarAfterPrevious(
  messages: ChatMessage[],
  speakerKey: string,
  showToolCalls: boolean,
  beforeIndex = messages.length,
): boolean {
  for (let i = beforeIndex - 1; i >= 0; i--) {
    const prev = messages[i];
    if (prev.kind === 'user' || prev.role === 'user') {
      return true;
    }
    if (prev.kind === 'tool_call' && !showToolCalls) {
      continue;
    }
    if (prev.kind === 'tool_call' || prev.kind === 'speaker') {
      return getMessageSpeakerKey(prev) !== speakerKey;
    }
  }
  return true;
}

/** 连续同一 speaker 时仅首条显示头像（跳过已隐藏的工具卡） */
function shouldShowSpeakerAvatar(
  messages: ChatMessage[],
  index: number,
  showToolCalls: boolean,
): boolean {
  const currentKey = getMessageSpeakerKey(messages[index]);
  if (!currentKey) {
    return true;
  }
  return shouldShowSpeakerAvatarAfterPrevious(messages, currentKey, showToolCalls, index);
}

type PendingAttachment = {
  id: string;
  name: string;
  uploading?: boolean;
  file_type?: string;
  type_label?: string;
  preview_url?: string | null;
};

type ActiveInterruptForm = SpeakerInterruptArgs & { tool_id?: string };

type SpeakerInterruptFormCardProps = {
  args: SpeakerInterruptArgs;
  submitting: boolean;
  onSubmit: (values: Record<string, string | string[]>) => void;
  onCancel: () => void;
};

function SpeakerInterruptFormCard({ args, submitting, onSubmit, onCancel }: SpeakerInterruptFormCardProps) {
  const [form] = Form.useForm<Record<string, string | string[]>>();

  return (
    <div className="chat-interrupt-card">
      <div className="chat-interrupt-card__head">
        <Typography.Text strong className="chat-interrupt-card__title">
          需要您补充信息
        </Typography.Text>
        {args.reason ? (
          <Typography.Paragraph type="secondary" className="chat-interrupt-card__reason">
            {args.reason}
          </Typography.Paragraph>
        ) : null}
      </div>
      <Form
        form={form}
        layout="vertical"
        className="chat-interrupt-card__form"
        onFinish={(values) => onSubmit(values)}
      >
        {args.questions.map((q) => {
          const fieldType = (q.field_type || 'input').toLowerCase();
          const choices = (q.choices ?? []).filter(Boolean);
          return (
            <Form.Item
              key={q.field_key}
              name={q.field_key}
              label={
                <span>
                  <span className="chat-interrupt-card__field-label">{q.field_label || q.field_key}</span>
                  {q.question ? (
                    <Typography.Text type="secondary" className="chat-interrupt-card__field-hint">
                      {q.question}
                    </Typography.Text>
                  ) : null}
                </span>
              }
              rules={[{ required: true, message: `请填写${q.field_label || q.field_key}` }]}
            >
              {fieldType === 'radio' && choices.length > 0 ? (
                <Radio.Group options={choices.map((c) => ({ label: c, value: c }))} />
              ) : fieldType === 'checkbox' && choices.length > 0 ? (
                <Checkbox.Group options={choices.map((c) => ({ label: c, value: c }))} />
              ) : (
                <Input placeholder={q.placeholder ?? undefined} allowClear />
              )}
            </Form.Item>
          );
        })}
        <div className="chat-interrupt-card__actions">
          <Button type="primary" htmlType="submit" loading={submitting}>
            提交并继续
          </Button>
          <Button htmlType="button" disabled={submitting} onClick={onCancel}>
            取消
          </Button>
        </div>
      </Form>
    </div>
  );
}

type ChatWindowPageProps = {
  sessionType?: SessionType;
};

export default function ChatWindowPage({ sessionType = 'chat' }: ChatWindowPageProps) {
  const memberId = getCurrentUserIdFromToken();
  const isGroupChat = sessionType === 'group';
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const selectedSessionIdFromUrl = searchParams.get('session_id');
  const hasSelectedSession = Boolean(selectedSessionIdFromUrl);
  const { sessions: portalSessions, ready: portalSessionsReady } = usePortalSessions();

  const [orgId] = useState<number>(1);
  const [sessionId, setSessionId] = useState<string | null>(null);
  /** 当前对话轮次（来自 start / catchup_round） */
  const [roundId, setRoundId] = useState<string | null>(null);
  const [input, setInput] = useState('');
  const [submitting, setSubmitting] = useState(false);
  /** 当前轮次后端「建群」结果（SSE create_group） */
  const [roundGroupMembers, setRoundGroupMembers] = useState<Array<{ id: number; name: string }>>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState<number | undefined>(undefined);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [agentsReady, setAgentsReady] = useState(false);
  /** 单聊指定智能体；undefined 表示使用服务端默认智能体 */
  const [selectedAgentId, setSelectedAgentId] = useState<number | undefined>(undefined);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [workspaceFiles, setWorkspaceFiles] = useState<WorkspaceArtifactFile[]>([]);
  const [currentSpeaker, setCurrentSpeaker] = useState<{ id: number; name: string } | null>(null);
  const [pendingAttachments, setPendingAttachments] = useState<PendingAttachment[]>([]);
  const [uploadingAttachment, setUploadingAttachment] = useState(false);
  /** speaker_interrupt：待用户填写的表单 */
  const [activeInterruptForm, setActiveInterruptForm] = useState<ActiveInterruptForm | null>(null);
  const [composerFocused, setComposerFocused] = useState(false);
  const [showToolCalls, setShowToolCalls] = useState(readShowToolCallsPreference);
  const [workspaceCollapsed, setWorkspaceCollapsed] = useState(readWorkspaceCollapsedPreference);

  const toggleWorkspaceCollapsed = useCallback(() => {
    setWorkspaceCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(WORKSPACE_COLLAPSED_STORAGE_KEY, next ? '1' : '0');
      } catch {
        /* ignore */
      }
      return next;
    });
  }, []);
  const scrollPanelRef = useRef<HTMLDivElement>(null);
  /** 用户未上滑时保持贴底，避免工具卡插入/结果回填时整页抖动 */
  const stickToBottomRef = useRef(true);
  /** 用视口像素高度约束整块聊天区，避免 Ant Layout/Row/Card 链上 min-height:auto 撑开导致内部无法滚动 */
  const chatViewportRootRef = useRef<HTMLDivElement>(null);
  const attachmentInputId = `chat-attachment-${useId().replace(/:/g, '')}`;
  const sessionIdRef = useRef(sessionId);
  sessionIdRef.current = sessionId;
  const roundIdRef = useRef(roundId);
  roundIdRef.current = roundId;
  /** 展示 interrupt 表单时对应的 round_id（提交 resume 须沿用该轮次） */
  const interruptRoundIdRef = useRef<string | null>(null);
  /** 当前连接上正在进行的 chat 轮次；避免 start 改 URL 后误触发 catchup / 重载历史 */
  const liveChatRoundRef = useRef(false);

  const syncChatViewportHeight = useCallback(() => {
    const el = chatViewportRootRef.current;
    if (!el) {
      return;
    }
    const vv = window.visualViewport;
    const vh = vv?.height ?? window.innerHeight;
    const top = el.getBoundingClientRect().top;
    const bottomGap = 10;
    const h = Math.max(200, Math.floor(vh - top - bottomGap));
    el.style.height = `${h}px`;
    el.style.maxHeight = `${h}px`;
  }, []);

  useLayoutEffect(() => {
    const el = chatViewportRootRef.current;
    if (!el) {
      return;
    }
    const run = () => {
      syncChatViewportHeight();
    };
    run();
    let innerRaf = 0;
    const outerRaf = requestAnimationFrame(() => {
      innerRaf = requestAnimationFrame(run);
    });
    window.addEventListener('resize', run);
    const vv = window.visualViewport;
    vv?.addEventListener('resize', run);
    vv?.addEventListener('scroll', run);
    const ro = new ResizeObserver(run);
    const pc = el.closest('.portal-content--chat');
    if (pc) {
      ro.observe(pc);
    }
    return () => {
      cancelAnimationFrame(outerRaf);
      cancelAnimationFrame(innerRaf);
      window.removeEventListener('resize', run);
      vv?.removeEventListener('resize', run);
      vv?.removeEventListener('scroll', run);
      ro.disconnect();
      el.style.height = '';
      el.style.maxHeight = '';
    };
  }, [syncChatViewportHeight, hasSelectedSession, isGroupChat, location.pathname]);

  const scrollChatToBottom = useCallback((opts?: { force?: boolean }) => {
    const el = scrollPanelRef.current;
    if (!el) {
      return;
    }
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    if (!opts?.force && distanceFromBottom > 96) {
      stickToBottomRef.current = false;
      return;
    }
    stickToBottomRef.current = true;
    el.scrollTop = el.scrollHeight;
  }, []);

  useEffect(() => {
    const el = scrollPanelRef.current;
    if (!el) {
      return;
    }
    const onScroll = () => {
      const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
      stickToBottomRef.current = distanceFromBottom <= 80;
    };
    el.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
    return () => el.removeEventListener('scroll', onScroll);
  }, [hasSelectedSession, messages.length]);

  useLayoutEffect(() => {
    if (!stickToBottomRef.current) {
      return;
    }
    scrollChatToBottom();
  }, [messages, scrollChatToBottom]);

  const currentSpeakerId = useMemo(() => {
    return currentSpeaker?.id ?? null;
  }, [currentSpeaker]);

  const chatMessages = useMemo(() => messages.filter((item) => item.role !== 'system'), [messages]);

  const showThinking = useMemo(() => {
    if (!submitting) {
      return false;
    }
    const streaming = chatMessages.find((m) => m.streaming);
    return !streaming || !streaming.content.trim();
  }, [submitting, chatMessages]);

  const visibleGroupMembers = useMemo(() => {
    if (!isGroupChat) {
      return [];
    }
    const selected = selectedGroupId != null ? groups.find((g) => g.id === selectedGroupId) : null;
    if (selected) {
      const ids = new Set((selected.agents ?? []).map((a) => a.id));
      if (roundGroupMembers.length > 0) {
        return roundGroupMembers.filter((m) => ids.has(m.id));
      }
      return (selected.agents ?? []).map((a) => ({ id: a.id, name: a.name }));
    }
    return roundGroupMembers;
  }, [isGroupChat, groups, selectedGroupId, roundGroupMembers]);

  const membersEmptyDescription = useMemo(() => {
    if (!isGroupChat) {
      return '尚未创建群聊成员';
    }
    if (selectedGroupId != null && roundGroupMembers.length > 0 && visibleGroupMembers.length === 0) {
      return '当前轮次发言成员不在所选群组中';
    }
    if (selectedGroupId != null) {
      const g = groups.find((x) => x.id === selectedGroupId);
      if (g && (!g.agents || g.agents.length === 0)) {
        return '该群组暂无智能体，请先在群组管理中添加';
      }
    }
    return '尚未创建群聊成员';
  }, [isGroupChat, selectedGroupId, groups, roundGroupMembers.length, visibleGroupMembers.length]);

  const emptyChatDescription = useMemo(() => {
    if (sessionId) return '历史对话';
    return isGroupChat ? '新建群聊' : '新建对话';
  }, [isGroupChat, sessionId]);

  // 切换”对话/群聊”模式时，若 URL 中没有显式 session_id，需要清空旧状态
  // 否则可能保留旧 sessionId/messages，导致默认文案”看起来没生效”
  useEffect(() => {
    setSessionId(null);
    setRoundGroupMembers([]);
    setSelectedGroupId(undefined);
    setSelectedAgentId(undefined);
    setCurrentSpeaker(null);
    setMessages([]);
    setWorkspaceFiles([]);
    setPendingAttachments([]);
  }, [isGroupChat]);


  useEffect(() => {
    if (!isGroupChat || !hasSelectedSession) {
      return;
    }
    void groupsApi
      .getAll()
      .then(setGroups)
      .catch((error: unknown) => {
        message.error(getBackendErrorMessage(error, '加载群组列表失败'));
      });
  }, [isGroupChat, hasSelectedSession]);

  useEffect(() => {
    if (isGroupChat || !isUserLoggedIn()) {
      setAgents([]);
      setAgentsReady(true);
      return;
    }
    setAgentsReady(false);
    void agentsApi
      .getAll()
      .then((list) => setAgents(list))
      .catch((error: unknown) => {
        message.error(getBackendErrorMessage(error, '加载智能体列表失败'));
        setAgents([]);
      })
      .finally(() => setAgentsReady(true));
  }, [isGroupChat]);

  const chatAgentOptions = useMemo(() => {
    return agents
      .filter((a) => a.chat_model_id != null && String(a.chat_model_id).trim() !== '')
      .map((a) => ({ label: a.name, value: a.id }));
  }, [agents]);

  const appendMessage = (msg: ChatMessage) => {
    setMessages((prev) => [...prev, msg]);
  };

  const refreshWorkspaceFiles = async (targetSessionId?: string | null) => {
    if (!isUserLoggedIn()) {
      setWorkspaceFiles([]);
      return;
    }
    const sid = targetSessionId ?? sessionId;
    if (!sid) {
      return;
    }
    try {
      const files = await chatWindowApi.getWorkspaceFiles(sid);
      setWorkspaceFiles(files);
    } catch (error) {
      console.error(error);
    }
  };

  const handleSSEEvent = (event: ChatWindowEvent) => {
    switch (event.event) {
      case 'start':
        sessionIdRef.current = event.session_id;
        roundIdRef.current = event.round_id;
        interruptRoundIdRef.current = null;
        liveChatRoundRef.current = true;
        setSessionId(event.session_id);
        setRoundId(event.round_id);
        chatWebSocket.setSessionId(event.session_id);
        void refreshWorkspaceFiles(event.session_id);
        if (searchParams.get('session_id') !== event.session_id) {
          navigate(
            {
              pathname: location.pathname,
              search: `?session_id=${encodeURIComponent(event.session_id)}`,
            },
            { replace: true },
          );
        }
        break;
      case 'create_group':
        setRoundGroupMembers(event.group_members ?? []);
        break;
      case 'select_speaker':
        setMessages((prev) =>
          prev.map((m) => (m.streaming ? { ...m, streaming: false } : m)),
        );
        {
          const id = normalizeSpeakerId(event.current_speaker?.id);
          if (id != null) {
            setCurrentSpeaker({ id, name: event.current_speaker.name ?? '' });
          }
        }
        break;
      case 'speaker_stream':
      case 'speaker_model_stream': {
        const { speaker_id, speaker_name } = event;
        const activeSpeakerId = normalizeSpeakerId(speaker_id);
        if (activeSpeakerId != null) {
          setCurrentSpeaker({ id: activeSpeakerId, name: speaker_name ?? '' });
        }
        let delta = event.delta ?? '';
        if (!delta && 'content' in event) {
          delta = event.content ?? '';
        }
        if (!delta && 'text' in event) {
          delta = event.text ?? '';
        }
        if (!delta) {
          break;
        }
        setMessages((prev) => {
          const idx = prev.findIndex(
            (m) => m.role === 'speaker' && m.streaming === true && m.speakerId === speaker_id,
          );
          if (idx === -1) {
            return [
              ...prev,
              {
                id: `speaker-stream-${speaker_id}-${Date.now()}`,
                kind: 'speaker',
                role: 'speaker',
                title: speaker_name,
                content: delta,
                speakerId: speaker_id,
                streaming: true,
              },
            ];
          }
          const next = [...prev];
          const row = next[idx];
          next[idx] = { ...row, content: row.content + delta, title: speaker_name };
          return next;
        });
        break;
      }
      case 'speaker':
        setMessages((prev) => {
          const idx = prev.findIndex(
            (m) => m.role === 'speaker' && m.streaming === true && m.speakerId === event.speaker_id,
          );
          if (idx !== -1) {
            const next = [...prev];
            next[idx] = {
              ...next[idx],
              title: event.speaker_name,
              content: event.content,
              streaming: false,
            };
            return next;
          }
          // 没找到 streaming 消息：可能是 catchup 重放或 streaming 标记已被清理
          // 查找该发言人最近一条消息，存在则原地更新，避免重复渲染
          let lastSpeakerIdx = -1;
          for (let i = prev.length - 1; i >= 0; i--) {
            if (prev[i].role === 'speaker' && prev[i].speakerId === event.speaker_id) {
              lastSpeakerIdx = i;
              break;
            }
          }
          if (lastSpeakerIdx !== -1) {
            const next = [...prev];
            next[lastSpeakerIdx] = {
              ...next[lastSpeakerIdx],
              title: event.speaker_name,
              content: event.content,
              streaming: false,
            };
            return next;
          }
          return [
            ...prev,
            {
              id: `speaker-${Date.now()}`,
              kind: 'speaker',
              role: 'speaker',
              title: event.speaker_name,
              content: event.content,
              speakerId: event.speaker_id,
            },
          ];
        });
        break;
      case 'speaker_tool_call': {
        const toolCalls = Array.isArray(event.tool_calls) ? event.tool_calls : [];
        if (toolCalls.length === 0) {
          break;
        }
        const activeSpeakerId = normalizeSpeakerId(event.speaker_id);
        if (activeSpeakerId != null) {
          setCurrentSpeaker({ id: activeSpeakerId, name: event.speaker_name ?? '' });
        }
        setMessages((prev) => [
          ...clearSpeakerStreaming(prev, event.speaker_id),
          {
            id: `live-tool-call-${event.speaker_id}-${Date.now()}`,
            kind: 'tool_call',
            role: 'speaker',
            title: event.speaker_name,
            content: '',
            speakerId: event.speaker_id,
            toolCalls: toolCalls.map((tc) => ({
              tool_name: tc.tool_name,
              tool_args: tc.tool_args,
              tool_id: tc.tool_id,
            })),
            animate: false,
          },
        ]);
        break;
      }
      case 'speaker_tool_out': {
        const result = event.content ?? '';
        setMessages((prev) =>
          attachToolResultToMessages(prev, event.tool_id, result, event.speaker_id),
        );
        break;
      }
      case 'speaker_interrupt':
        setMessages((prev) => prev.map((m) => (m.streaming ? { ...m, streaming: false } : m)));
        interruptRoundIdRef.current = roundIdRef.current;
        setActiveInterruptForm({
          reason: event.args?.reason ?? '',
          questions: Array.isArray(event.args?.questions) ? event.args.questions : [],
          tool_id: event.tool_id,
        });
        setSubmitting(false);
        break;
      case 'speaker_finished':
        liveChatRoundRef.current = false;
        setActiveInterruptForm(null);
        interruptRoundIdRef.current = null;
        setMessages((prev) =>
          prev.map((m) => (m.streaming ? { ...m, streaming: false } : m)),
        );
        setCurrentSpeaker(null);
        setSubmitting(false);
        void refreshWorkspaceFiles();
        break;
      case 'finished':
        liveChatRoundRef.current = false;
        setActiveInterruptForm(null);
        interruptRoundIdRef.current = null;
        setRoundId(null);
        setMessages((prev) =>
          prev.map((m) => (m.streaming ? { ...m, streaming: false } : m)),
        );
        if (event.answer) {
          appendMessage({
            id: `finish-${Date.now()}`,
            kind: 'speaker',
            role: 'speaker',
            title: '超级助手',
            content: event.answer,
          });
        }
        setCurrentSpeaker(null);
        setSubmitting(false);
        void refreshWorkspaceFiles();
        break;
      default:
        break;
    }
  };

  const handleEvent = (event: WSServerMessage) => {
    if (event.event === 'authenticated') {
      return;
    }
    if (event.event === 'catchup_round') {
      if (event.round_id) {
        roundIdRef.current = event.round_id;
        setRoundId(event.round_id);
      }
      // 断线重放：逐一处理缓冲事件
      if (event.events && event.events.length > 0) {
        event.events.forEach((e) => handleSSEEvent(e));
      }
      return;
    }
    if (event.event === 'error') {
      console.error('[ChatWindow] 服务端错误:', event.message);
      message.error(event.message || '服务端错误');
      liveChatRoundRef.current = false;
      setActiveInterruptForm(null);
      interruptRoundIdRef.current = null;
      setSubmitting(false);
      return;
    }
    if (event.event === 'auth_error') {
      message.error(event.message || '登录已失效，请重新登录', 6);
      setSubmitting(false);
      requestOpenLoginModal(800);
      return;
    }
    if (event.event === 'pong') {
      return;
    }
    handleSSEEvent(event as ChatWindowEvent);
  };

  // 用 ref 保持 handleEvent 引用最新，避免 WebSocket 回调中的闭包过期
  const handleEventRef = useRef(handleEvent);
  handleEventRef.current = handleEvent;

  // WebSocket 连接管理
  const loggedIn = isUserLoggedIn();

  useEffect(() => {
    if (!loggedIn) {
      return;
    }
    // 须先于 connect 注册：首包 auth 失败时服务端立即下发 auth_error 并关连接，否则 onmessage 时 callbacks 仍为空
    const unsub = chatWebSocket.onEvent((event) => handleEventRef.current(event));
    chatWebSocket.ensureConnected();

    return () => {
      unsub();
      chatWebSocket.disconnect();
    };
  }, [isGroupChat, loggedIn]);

  const submitInterruptForm = (values: Record<string, string | string[]>) => {
    const sid = sessionIdRef.current ?? sessionId;
    const rid = interruptRoundIdRef.current ?? roundIdRef.current ?? roundId;
    if (!sid) {
      message.warning('会话尚未就绪，请稍后再试');
      return;
    }
    if (!rid) {
      message.warning('缺少对话轮次信息，请刷新页面后重试');
      return;
    }
    if (!isUserLoggedIn()) {
      message.warning('请先登录');
      return;
    }
    setSubmitting(true);
    setActiveInterruptForm(null);
    interruptRoundIdRef.current = null;
    liveChatRoundRef.current = true;
    const sent = chatWebSocket.sendInterruptResume({
      org_id: orgId,
      session_id: sid,
      round_id: rid,
      session_type: sessionType,
      group_id: isGroupChat && selectedGroupId != null ? selectedGroupId : undefined,
      resume: { data: values },
    });
    if (!sent) {
      setSubmitting(false);
      liveChatRoundRef.current = false;
    }
  };

  const cancelInterruptForm = () => {
    const sid = sessionIdRef.current ?? sessionId;
    const rid = interruptRoundIdRef.current ?? roundIdRef.current ?? roundId;
    if (!sid) {
      setActiveInterruptForm(null);
      return;
    }
    if (!rid) {
      setActiveInterruptForm(null);
      message.warning('缺少对话轮次信息，请刷新页面后重试');
      return;
    }
    setSubmitting(true);
    setActiveInterruptForm(null);
    interruptRoundIdRef.current = null;
    liveChatRoundRef.current = true;
    const sent = chatWebSocket.sendInterruptResume({
      org_id: orgId,
      session_id: sid,
      round_id: rid,
      session_type: sessionType,
      group_id: isGroupChat && selectedGroupId != null ? selectedGroupId : undefined,
      resume: { cancel: true },
    });
    if (!sent) {
      setSubmitting(false);
      liveChatRoundRef.current = false;
    }
  };

  const renderInterruptForm = () => {
    if (!activeInterruptForm || activeInterruptForm.questions.length === 0) {
      return null;
    }
    return (
      <div className="chat-row chat-row-interrupt">
        <SpeakerInterruptFormCard
          args={activeInterruptForm}
          submitting={submitting}
          onSubmit={submitInterruptForm}
          onCancel={cancelInterruptForm}
        />
      </div>
    );
  };

  const sendMessage = () => {
    const text = input.trim();
    const fileIds = pendingAttachments.filter((a) => !a.uploading).map((a) => a.id);
    if (pendingAttachments.some((a) => a.uploading)) {
      message.warning('请等待附件上传完成后再发送');
      return;
    }
    if (activeInterruptForm) {
      message.info('请先完成上方表单或点击取消');
      return;
    }
    if ((!text && fileIds.length === 0) || submitting) {
      return;
    }
    if (!isUserLoggedIn() || memberId == null) {
      message.warning('请先登录后再发送消息');
      goLoginPage(navigate, { pathname: location.pathname, search: location.search });
      return;
    }

    const displayContent = text;

    stickToBottomRef.current = true;
    appendMessage({
      id: `user-${Date.now()}`,
      kind: 'user',
      role: 'user',
      title: '我',
      content: displayContent,
      attachments:
        pendingAttachments.length > 0
          ? pendingAttachments.map((a) => ({
              id: a.id,
              file_name: a.name,
              file_type: a.file_type || 'application/octet-stream',
              type_label: a.type_label || friendlyFileTypeLabel(a.file_type || '', a.name),
              preview_url: a.preview_url,
            }))
          : undefined,
    });

    setInput('');
    setSubmitting(true);
    liveChatRoundRef.current = true;
    requestAnimationFrame(() => scrollChatToBottom({ force: true }));

    const sent = chatWebSocket.sendChat({
      user_message: text,
      org_id: orgId,
      session_id: sessionId,
      session_type: sessionType,
      group_id: isGroupChat && selectedGroupId != null ? selectedGroupId : undefined,
      single_agent_id:
        !isGroupChat && selectedAgentId != null ? String(selectedAgentId) : undefined,
      file_ids: fileIds.length > 0 ? fileIds : undefined,
    });
    if (!sent) {
      liveChatRoundRef.current = false;
      setSubmitting(false);
      return;
    }
    setPendingAttachments([]);
  };

  const handleComposerKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void sendMessage();
    }
  };

  const onAttachmentFilesSelected = async (e: ChangeEvent<HTMLInputElement>) => {
    const inputEl = e.currentTarget;
    const list = inputEl.files;
    if (!list?.length) {
      return;
    }
    if (!isUserLoggedIn()) {
      message.warning('请先登录后再上传文件');
      inputEl.value = '';
      return;
    }
    const files = Array.from(list);
    const base = Date.now();
    const placeholders: PendingAttachment[] = files.map((file, i) => ({
      id: `local-upload-${base}-${i}`,
      name: file.name,
      uploading: true,
      file_type: file.type || 'application/octet-stream',
      type_label: '上传中',
    }));
    setPendingAttachments((prev) => [...prev, ...placeholders]);

    setUploadingAttachment(true);
    try {
      for (let i = 0; i < files.length; i++) {
        const tempId = placeholders[i].id;
        try {
          const row = await uploadFileApi.upload(files[i]);
          setPendingAttachments((prev) =>
            prev.map((p) =>
              p.id === tempId
                ? {
                    id: row.id,
                    name: row.file_name,
                    uploading: false,
                    file_type: row.file_type,
                    type_label: friendlyFileTypeLabel(row.file_type, row.file_name),
                    preview_url: row.preview_url ?? undefined,
                  }
                : p,
            ),
          );
        } catch (err: unknown) {
          setPendingAttachments((prev) => prev.filter((p) => p.id !== tempId));
          message.error(getBackendErrorMessage(err, '上传失败'));
        }
      }
    } finally {
      setUploadingAttachment(false);
      inputEl.value = '';
    }
  };

  useEffect(() => {
    const selectedSessionId = searchParams.get('session_id');
    const pathHere = location.pathname.startsWith('/group-chat') ? '/group-chat' : '/chat';

    if (!selectedSessionId) {
      // 未指定 session_id：视为”新建”，需要保证窗口干净
      setSessionId(null);
      setRoundId(null);
      interruptRoundIdRef.current = null;
      setCurrentSpeaker(null);
      setMessages([]);
      setWorkspaceFiles([]);
      setPendingAttachments([]);
      if (pathHere === '/group-chat') {
        setRoundGroupMembers([]);
      }
      chatWebSocket.setSessionId(null);
      liveChatRoundRef.current = false;
      setActiveInterruptForm(null);
      chatWebSocket.ensureConnected();
      return;
    }

    if (!portalSessionsReady) {
      return;
    }

    if (liveChatRoundRef.current) {
      if (selectedSessionId === sessionIdRef.current) {
        chatWebSocket.setSessionId(selectedSessionId);
        return;
      }
    }

    if (selectedSessionId === sessionIdRef.current) {
      return;
    }

    void (async () => {
      if (!isUserLoggedIn() || memberId == null) {
        if (selectedSessionId) {
          message.warning('查看历史对话请先登录');
          navigate(pathHere, { replace: true });
        }
        return;
      }
      try {
        const found = portalSessions.find((item) => item.id === selectedSessionId);
        if (!found) {
          // 当前账号下无此会话：不再请求 messages，并清理 URL
          navigate(pathHere, { replace: true });
          setSessionId(null);
          setMessages([]);
          setWorkspaceFiles([]);
          setPendingAttachments([]);
          if (pathHere === '/group-chat') {
            setRoundGroupMembers([]);
          }
          setCurrentSpeaker(null);
          chatWebSocket.setSessionId(null);
          return;
        }
        const pathForSession = chatPathForSessionType(found.session_type);
        if (pathForSession !== pathHere) {
          navigate(`${pathForSession}?session_id=${encodeURIComponent(selectedSessionId)}`, { replace: true });
          return;
        }

        setSessionId(selectedSessionId);
        chatWebSocket.setSessionId(selectedSessionId);
        if (isGroupChat) {
          setRoundGroupMembers([]);
        }
        setCurrentSpeaker(null);
        setPendingAttachments([]);
        await refreshWorkspaceFiles(selectedSessionId);
        const records = await sessionsApi.getMessages(selectedSessionId);
        setMessages(sessionRecordsToChatMessages(Array.isArray(records) ? records : []));
        // 请求断线重放：如果当前有活跃 round，拉取流式增量
        chatWebSocket.sendCatchup(selectedSessionId);
      } catch (error) {
        console.error('加载会话消息失败', error);
        message.error(getBackendErrorMessage(error, '加载会话消息失败'));
      }
    })();
  }, [searchParams, memberId, navigate, portalSessions, portalSessionsReady, location.pathname]);

  const handleComposerPodBlur = (e: FocusEvent<HTMLDivElement>) => {
    const next = e.relatedTarget as Node | null;
    if (next && e.currentTarget.contains(next)) {
      return;
    }
    setComposerFocused(false);
  };

  const renderComposer = () => {
    const showComposerDock = pendingAttachments.length > 0;

    return (
      <div className="chat-composer-pod" tabIndex={-1} onBlur={handleComposerPodBlur}>
        <input
          id={attachmentInputId}
          type="file"
          multiple
          className="chat-file-input-sr"
          tabIndex={-1}
          disabled={uploadingAttachment || submitting || !isUserLoggedIn()}
          aria-label="选择要上传的附件"
          onChange={(e) => void onAttachmentFilesSelected(e)}
        />
        <div className={`chat-composer__dock${showComposerDock ? ' chat-composer__dock--visible' : ''}`}>
          {pendingAttachments.length > 0 && (
            <div className="chat-composer__attachments">
              <div className="chat-composer__attachments-head">
                <span className="chat-composer__attachments-label">
                  已添加 {pendingAttachments.length} 个附件
                </span>
              </div>
              <div className="chat-composer__attachments-inner">
                {pendingAttachments.map((f) => (
                  <UserAttachmentCard
                    key={f.id}
                    fileName={f.name}
                    mime={f.file_type || 'application/octet-stream'}
                    typeLabel={
                      f.uploading ? '上传中' : f.type_label || friendlyFileTypeLabel(f.file_type || '', f.name)
                    }
                    uploading={f.uploading}
                    previewUrl={f.preview_url}
                    compact
                    onRemove={
                      !f.uploading
                        ? () => setPendingAttachments((prev) => prev.filter((x) => x.id !== f.id))
                        : undefined
                    }
                  />
                ))}
              </div>
            </div>
          )}
        </div>
        <div
          className={`chat-composer chat-composer--capsule${composerFocused ? ' chat-composer--focused' : ''}`}
        >
          <div className="chat-composer__input-row">
            <TextArea
              className="chat-composer__textarea"
              value={input}
              placeholder={
                !isUserLoggedIn()
                  ? '请先登录后再发送消息'
                  : hasSelectedSession
                    ? '发消息…'
                    : isGroupChat
                      ? '发送消息开始群聊'
                      : '发送消息开始对话'
              }
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleComposerKeyDown}
              onFocus={() => setComposerFocused(true)}
              disabled={submitting || !isUserLoggedIn() || Boolean(activeInterruptForm)}
              autoSize={{ minRows: 2, maxRows: 8 }}
              variant="borderless"
            />
          </div>
          <div className="chat-composer__footer">
            <div className="chat-composer__capsule-tools">
              <Tooltip title={!isUserLoggedIn() ? '请先登录' : '上传附件'}>
                <span className="chat-composer__tooltip-anchor">
                  {!isUserLoggedIn() || submitting || activeInterruptForm ? (
                    <span
                      className="chat-composer__icon-btn chat-composer__icon-btn--plus chat-composer__icon-btn--disabled"
                      aria-disabled
                    >
                      <PlusOutlined />
                    </span>
                  ) : (
                    <label
                      htmlFor={attachmentInputId}
                      className={`chat-composer__icon-btn chat-composer__icon-btn--plus${uploadingAttachment ? ' chat-composer__icon-btn--busy' : ''}`}
                    >
                      {uploadingAttachment ? <span className="chat-composer__spinner" /> : <PlusOutlined />}
                    </label>
                  )}
                </span>
              </Tooltip>
              {!isGroupChat && (
                <Select
                  className="chat-composer__agent-select"
                  allowClear
                  showSearch
                  optionFilterProp="label"
                  placeholder={agentsReady ? '默认智能体' : '加载智能体…'}
                  loading={!agentsReady}
                  disabled={
                    !isUserLoggedIn() ||
                    submitting ||
                    Boolean(activeInterruptForm) ||
                    chatAgentOptions.length === 0
                  }
                  value={selectedAgentId}
                  onChange={(v) => setSelectedAgentId(v ?? undefined)}
                  options={chatAgentOptions}
                  popupMatchSelectWidth={false}
                  suffixIcon={<RobotOutlined className="chat-composer__agent-select-icon" />}
                  notFoundContent={agentsReady ? '暂无已绑定模型的智能体' : null}
                />
              )}
            </div>
            <Tooltip title="发送（Enter）">
              <span className="chat-composer__tooltip-anchor">
                <button
                  type="button"
                  className={`chat-composer__send chat-composer__send--round${submitting ? ' chat-composer__send--loading' : ''}`}
                  disabled={submitting || !isUserLoggedIn() || Boolean(activeInterruptForm)}
                  onClick={() => void sendMessage()}
                  aria-label="发送"
                >
                  {submitting ? (
                    <span className="chat-composer__spinner chat-composer__spinner--light" />
                  ) : (
                    <ArrowUpOutlined />
                  )}
                </button>
              </span>
            </Tooltip>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div ref={chatViewportRootRef} className="chat-viewport-root">
      {!hasSelectedSession ? (
        <div className="chat-idle-shell">
          {activeInterruptForm ? (
            <div className="chat-idle-shell__interrupt">{renderInterruptForm()}</div>
          ) : null}
          <div className="chat-idle-shell__composer">{renderComposer()}</div>
        </div>
      ) : (
        <div
          className={`chat-session-root${workspaceCollapsed ? ' chat-session-root--workspace-collapsed' : ''}`}
        >
          <Row
            className={`chat-session-row chat-session-row--stretch${hasSelectedSession ? ' chat-session-row--has-workspace' : ''}`}
            gutter={[0, 0]}
            align="stretch"
            style={{ flex: 1, minHeight: 0, width: '100%' }}
          >
            {isGroupChat && hasSelectedSession && (
              <Col xs={24} lg={5} className="chat-session-col chat-session-col--members">
                <Card
                  className="portal-card chat-side-panel-card"
                  variant="borderless"
                  title={
                    <Space>
                      <TeamOutlined />
                      群聊成员
                    </Space>
                  }
                  extra={
                    <Select
                      allowClear
                      placeholder="选择群组"
                      style={{ minWidth: 140, maxWidth: 200 }}
                      value={selectedGroupId}
                      onChange={(v) => setSelectedGroupId(v ?? undefined)}
                      options={groups.map((g) => ({ label: g.name, value: g.id }))}
                    />
                  }
                  style={{ height: '100%' }}
                >
                  {visibleGroupMembers.length === 0 ? (
                    <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={membersEmptyDescription} />
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                      {visibleGroupMembers.map((item) => (
                        <div key={item.id} style={{ padding: '8px 0', borderBottom: '1px solid #f0f0f0' }}>
                          <Space align="start">
                            <Badge dot={currentSpeakerId === item.id} color="green">
                              <Avatar icon={<UserOutlined />} />
                            </Badge>
                            <div>
                              <Space>
                                <span>{item.name}</span>
                                <Tag color={currentSpeakerId === item.id ? 'green' : 'default'}>
                                  {currentSpeakerId === item.id ? '发言中' : `ID: ${item.id}`}
                                </Tag>
                              </Space>
                              <div style={{ color: 'rgba(0,0,0,0.45)', fontSize: 12 }}>
                                {currentSpeakerId === item.id ? '正在回复你的问题' : '待发言'}
                              </div>
                            </div>
                          </Space>
                        </div>
                      ))}
                    </div>
                  )}
                </Card>
              </Col>
            )}

            <Col xs={24} lg={isGroupChat ? 13 : 18} className="chat-session-col chat-session-col--dialog">
              <Card
                className="portal-card chat-main-dialog-card"
                variant="borderless"
                title={isGroupChat ? '群聊对话' : '对话'}
                extra={
                  <label className="chat-dialog-tool-toggle">
                    <span className="chat-dialog-tool-toggle__label">显示工具调用</span>
                    <Switch
                      size="small"
                      checked={showToolCalls}
                      onChange={(checked) => {
                        setShowToolCalls(checked);
                        try {
                          localStorage.setItem(SHOW_TOOL_CALLS_STORAGE_KEY, checked ? '1' : '0');
                        } catch {
                          /* ignore */
                        }
                      }}
                    />
                  </label>
                }
                style={{ height: '100%', display: 'flex', flexDirection: 'column', position: 'relative' }}
              >
                {chatMessages.length === 0 && !activeInterruptForm ? (
                  <div className="chat-empty-session">
                    <div className="chat-empty-session__inner">
                      <Empty className="chat-empty-session__hint" image={Empty.PRESENTED_IMAGE_SIMPLE} description={emptyChatDescription} />
                      {renderComposer()}
                    </div>
                  </div>
                ) : chatMessages.length === 0 && activeInterruptForm ? (
                  <div className="chat-dialog-body">
                    <div ref={scrollPanelRef} className="chat-scroll-panel chat-thread">
                      <div className="chat-thread__inner">{renderInterruptForm()}</div>
                    </div>
                    {renderComposer()}
                  </div>
                ) : (
                  <div className="chat-dialog-body">
                    <div ref={scrollPanelRef} className="chat-scroll-panel chat-thread">
                      <div className="chat-thread__inner">
                        {chatMessages.map((item, index) => {
                          const showSpeakerAvatar = shouldShowSpeakerAvatar(
                            chatMessages,
                            index,
                            showToolCalls,
                          );
                          if (item.kind === 'user' || item.role === 'user') {
                            return (
                              <ChatUserMessage
                                key={item.id}
                                content={item.content}
                                animate={item.animate !== false}
                                enterIndex={index}
                                attachments={
                                  (item.attachments?.length ?? 0) > 0 ? (
                                    <div className="chat-user-attachment-stack">
                                      {item.attachments!.map((a) => (
                                        <UserAttachmentCard
                                          key={a.id}
                                          fileName={a.file_name}
                                          mime={a.file_type}
                                          typeLabel={a.type_label}
                                          previewUrl={a.preview_url}
                                        />
                                      ))}
                                    </div>
                                  ) : undefined
                                }
                              />
                            );
                          }
                          if (item.kind === 'tool_call') {
                            if (!showToolCalls) {
                              return null;
                            }
                            return (
                              <ChatToolCallMessage
                                key={item.id}
                                title={item.title}
                                toolCalls={item.toolCalls ?? []}
                                showAvatar={showSpeakerAvatar}
                                animate={item.animate !== false}
                                enterIndex={index}
                              />
                            );
                          }
                          return (
                            <ChatAiMessage
                              key={item.id}
                              title={item.title}
                              content={item.content}
                              streaming={item.streaming}
                              showAvatar={showSpeakerAvatar}
                              animate={item.animate !== false}
                              enterIndex={index}
                            />
                          );
                        })}
                        {showThinking ? (
                          <ChatThinkingIndicator
                            showAvatar={shouldShowSpeakerAvatarAfterPrevious(
                              chatMessages,
                              currentSpeakerId != null
                                ? `id:${currentSpeakerId}`
                                : `name:${currentSpeaker?.name ?? 'AI'}`,
                              showToolCalls,
                            )}
                          />
                        ) : null}
                        {renderInterruptForm()}
                      </div>
                    </div>

                    {renderComposer()}
                  </div>
                )}
              </Card>
            </Col>

            {hasSelectedSession && (
              <aside
                className={`chat-workspace-aside${workspaceCollapsed ? ' chat-workspace-aside--collapsed' : ''}`}
                aria-label="工作空间"
              >
                <Tooltip
                  title={workspaceCollapsed ? '展开工作空间' : '收起工作空间'}
                  placement="left"
                >
                  <button
                    type="button"
                    className="chat-workspace-aside__toggle"
                    onClick={toggleWorkspaceCollapsed}
                    aria-expanded={!workspaceCollapsed}
                    aria-label={workspaceCollapsed ? '展开工作空间' : '收起工作空间'}
                  >
                    {workspaceCollapsed ? <LeftOutlined /> : <RightOutlined />}
                  </button>
                </Tooltip>
                {!workspaceCollapsed ? (
                  <div className="chat-workspace-aside__body">
                    <Card
                      className="portal-card chat-side-panel-card chat-workspace-card"
                      variant="borderless"
                      title="工作空间"
                      style={{ height: '100%' }}
                    >
                      {workspaceFiles.length === 0 ? (
                        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无产物文件" />
                      ) : (
                        <div className="chat-workspace-file-list">
                          {workspaceFiles.map((item) => (
                            <div
                              key={`${item.round_id}-${item.relative_path}`}
                              className="chat-workspace-file-item"
                            >
                              <Typography.Text strong>{item.name}</Typography.Text>
                              <div>
                                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                                  {item.relative_path}
                                </Typography.Text>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </Card>
                  </div>
                ) : null}
              </aside>
            )}
          </Row>
        </div>
      )}
    </div>
  );
}
