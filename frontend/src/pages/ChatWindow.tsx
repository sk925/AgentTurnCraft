import { useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState, type ChangeEvent, type KeyboardEvent } from 'react';
import {
  Avatar,
  Badge,
  Card,
  Col,
  Empty,
  Input,
  Row,
  Select,
  Space,
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
  LoadingOutlined,
  PlusOutlined,
  TeamOutlined,
  UserOutlined,
} from '@ant-design/icons';
import {
  chatWebSocket,
  chatWindowApi,
  getBackendErrorMessage,
  getCurrentUserIdFromToken,
  goLoginPage,
  groupsApi,
  isUserLoggedIn,
  sessionsApi,
  uploadFileApi,
} from '../api';
import type { ChatWindowEvent, Group, SessionMessage, SessionType, WSServerMessage, WorkspaceArtifactFile } from '../api';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import './ChatWindow.css';

const { TextArea } = Input;

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
    compact ? 'chat-attachment-card--compact' : '',
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
          ×
        </button>
      )}
    </div>
  );
}

type ChatMessage = {
  id: string;
  role: 'user' | 'system' | 'speaker';
  title: string;
  content: string;
  speakerId?: number;
  /** 当前是否仍在接收 speaker_stream */
  streaming?: boolean;
  /** 用户消息附带的文件（仅前端展示；历史接口未返回时为空） */
  attachments?: ChatAttachmentMeta[];
};

type PendingAttachment = {
  id: string;
  name: string;
  uploading?: boolean;
  file_type?: string;
  type_label?: string;
  preview_url?: string | null;
};

type ChatWindowPageProps = {
  sessionType?: SessionType;
};

export default function ChatWindowPage({ sessionType = 'chat' }: ChatWindowPageProps) {
  const memberId = getCurrentUserIdFromToken();
  const isGroupChat = sessionType === 'group';
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();

  const [orgId] = useState<number>(1);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [input, setInput] = useState('');
  const [submitting, setSubmitting] = useState(false);
  /** 当前轮次后端「建群」结果（SSE create_group） */
  const [roundGroupMembers, setRoundGroupMembers] = useState<Array<{ id: number; name: string }>>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState<number | undefined>(undefined);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [workspaceFiles, setWorkspaceFiles] = useState<WorkspaceArtifactFile[]>([]);
  const [currentSpeaker, setCurrentSpeaker] = useState<{ id: number; name: string } | null>(null);
  const [pendingAttachments, setPendingAttachments] = useState<PendingAttachment[]>([]);
  const [uploadingAttachment, setUploadingAttachment] = useState(false);
  const scrollPanelRef = useRef<HTMLDivElement>(null);
  const attachmentInputId = `chat-attachment-${useId().replace(/:/g, '')}`;

  const scrollChatToBottom = useCallback(() => {
    const el = scrollPanelRef.current;
    if (!el) {
      return;
    }
    el.scrollTop = el.scrollHeight;
  }, []);

  useLayoutEffect(() => {
    scrollChatToBottom();
    const id = requestAnimationFrame(() => {
      scrollChatToBottom();
    });
    return () => cancelAnimationFrame(id);
  }, [messages, scrollChatToBottom]);

  const currentSpeakerId = useMemo(() => {
    return currentSpeaker?.id ?? null;
  }, [currentSpeaker]);

  const chatMessages = useMemo(() => messages.filter((item) => item.role !== 'system'), [messages]);

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
    setCurrentSpeaker(null);
    setMessages([]);
    setWorkspaceFiles([]);
    setPendingAttachments([]);
  }, [isGroupChat]);


  useEffect(() => {
    if (!isGroupChat) {
      return;
    }
    void groupsApi
      .getAll()
      .then(setGroups)
      .catch((error: unknown) => {
        message.error(getBackendErrorMessage(error, '加载群组列表失败'));
      });
  }, [isGroupChat]);

  const toChatMessage = (record: SessionMessage, index: number): ChatMessage => {
    if (record.role_type === 'user') {
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
      return {
        id: `history-user-${index}`,
        role: 'user',
        title: record.speaker_name || '我',
        content: record.message_content,
        attachments,
      };
    }
    return {
      id: `history-speaker-${index}`,
      role: 'speaker',
      title: record.speaker_name || '超级助手',
      content: record.message_content,
      speakerId: record.speaker_id ?? undefined,
    };
  };

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
        setSessionId(event.session_id);
        void refreshWorkspaceFiles(event.session_id);
        break;
      case 'create_group':
        setRoundGroupMembers(event.group_members ?? []);
        break;
      case 'select_speaker':
        setMessages((prev) =>
          prev.map((m) => (m.streaming ? { ...m, streaming: false } : m)),
        );
        setCurrentSpeaker(event.current_speaker);
        break;
      case 'speaker_stream':
      case 'speaker_model_stream': {
        const { speaker_id, speaker_name } = event;
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
              role: 'speaker',
              title: event.speaker_name,
              content: event.content,
              speakerId: event.speaker_id,
            },
          ];
        });
        break;
      case 'speaker_finished':
        setMessages((prev) =>
          prev.map((m) => (m.streaming ? { ...m, streaming: false } : m)),
        );
        setCurrentSpeaker(null);
        setSubmitting(false);
        void refreshWorkspaceFiles();
        break;
      case 'finished':
        setMessages((prev) =>
          prev.map((m) => (m.streaming ? { ...m, streaming: false } : m)),
        );
        if (event.answer) {
          appendMessage({
            id: `finish-${Date.now()}`,
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
    if (event.event === 'catchup_round') {
      // 断线重放：逐一处理缓冲事件
      if (event.events && event.events.length > 0) {
        event.events.forEach((e) => handleSSEEvent(e));
      }
      return;
    }
    if (event.event === 'error') {
      console.error('[ChatWindow] 服务端错误:', event.message);
      message.error(event.message || '服务端错误');
      setSubmitting(false);
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
    chatWebSocket.connect(sessionId);
    const unsub = chatWebSocket.onEvent((event) => handleEventRef.current(event));

    return () => {
      unsub();
      chatWebSocket.disconnect();
    };
  }, [isGroupChat, loggedIn]);

  const sendMessage = () => {
    const text = input.trim();
    const fileIds = pendingAttachments.filter((a) => !a.uploading).map((a) => a.id);
    if (pendingAttachments.some((a) => a.uploading)) {
      message.warning('请等待附件上传完成后再发送');
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

    appendMessage({
      id: `user-${Date.now()}`,
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

    const sent = chatWebSocket.sendChat({
      user_message: text,
      org_id: orgId,
      session_id: sessionId,
      session_type: sessionType,
      group_id: isGroupChat && selectedGroupId != null ? selectedGroupId : undefined,
      file_ids: fileIds.length > 0 ? fileIds : undefined,
    });
    if (!sent) {
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

  const sessionIdRef = useRef(sessionId);
  sessionIdRef.current = sessionId;

  useEffect(() => {
    const selectedSessionId = searchParams.get('session_id');
    if (!selectedSessionId) {
      // 未指定 session_id：视为”新建”，需要保证窗口干净
      setSessionId(null);
      setCurrentSpeaker(null);
      setMessages([]);
      setWorkspaceFiles([]);
      setPendingAttachments([]);
      if (isGroupChat) {
        setRoundGroupMembers([]);
      }
      chatWebSocket.setSessionId(null);
      return;
    }
    if (selectedSessionId === sessionIdRef.current) {
      return;
    }
    void (async () => {
      if (!isUserLoggedIn() || memberId == null) {
        if (selectedSessionId) {
          message.warning('查看历史对话请先登录');
          navigate(isGroupChat ? '/group-chat' : '/chat', { replace: true });
        }
        return;
      }
      try {
        const allSessions = await sessionsApi.list(sessionType);
        const exists = allSessions.some((item) => item.id === selectedSessionId);
        if (!exists) {
          // 当前账号下无此会话：不再请求 messages，并清理 URL
          navigate(isGroupChat ? '/group-chat' : '/chat', { replace: true });
          setSessionId(null);
          setMessages([]);
          setWorkspaceFiles([]);
          setPendingAttachments([]);
          if (isGroupChat) {
            setRoundGroupMembers([]);
          }
          setCurrentSpeaker(null);
          chatWebSocket.setSessionId(null);
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
        setMessages((Array.isArray(records) ? records : []).map(toChatMessage));
        // 请求断线重放：如果当前有活跃 round，拉取流式增量
        chatWebSocket.sendCatchup(selectedSessionId);
      } catch (error) {
        console.error('加载会话消息失败', error);
        message.error(getBackendErrorMessage(error, '加载会话消息失败'));
      }
    })();
  }, [searchParams, memberId, sessionType, isGroupChat, navigate]);

  return (
    <Row gutter={[16, 16]} style={{ minHeight: 'calc(100vh - 140px)' }}>
      {isGroupChat && (
        <Col xs={24} lg={5}>
          <Card
            className="portal-card"
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

      <Col xs={24} lg={isGroupChat ? 13 : 18}>
        <Card
          className="portal-card"
          variant="borderless"
          title={isGroupChat ? '群聊对话' : '对话'}
          style={{ height: '100%', display: 'flex', flexDirection: 'column', position: 'relative' }}
        >
          <div ref={scrollPanelRef} className="chat-scroll-panel">
            {chatMessages.length === 0 ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={emptyChatDescription} />
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {chatMessages.map((item) => (
                  <div key={item.id} className={`chat-row ${item.role === 'user' ? 'chat-row-self' : 'chat-row-speaker'}`}>
                    {item.role === 'user' ? (
                      <div className="chat-user-message-stack">
                        {(item.attachments?.length ?? 0) > 0 && (
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
                        )}
                        {item.content ? (
                          <div className="chat-bubble chat-bubble-self chat-bubble-self--neutral">
                            <Typography.Text strong>我</Typography.Text>
                            <Typography.Paragraph className="chat-paragraph">{item.content}</Typography.Paragraph>
                          </div>
                        ) : null}
                      </div>
                    ) : (
                      <div className="chat-bubble chat-bubble-speaker">
                        <Typography.Text strong>{item.title}</Typography.Text>
                        <Typography.Paragraph className="chat-paragraph">{item.content}</Typography.Paragraph>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="chat-composer">
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
            {pendingAttachments.length > 0 && (
              <div className="chat-composer__attachments">
                <div className="chat-composer__attachments-inner">
                  {pendingAttachments.map((f) => (
                    <UserAttachmentCard
                      key={f.id}
                      fileName={f.name}
                      mime={f.file_type || 'application/octet-stream'}
                      typeLabel={
                        f.uploading
                          ? '上传中'
                          : f.type_label || friendlyFileTypeLabel(f.file_type || '', f.name)
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
            <TextArea
              className="chat-composer__textarea"
              value={input}
              placeholder={
                isUserLoggedIn()
                  ? '发消息或输入「/」选择技能（Shift+Enter 换行）'
                  : '请先登录后再发送消息'
              }
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleComposerKeyDown}
              disabled={submitting || !isUserLoggedIn()}
              autoSize={{ minRows: 2, maxRows: 12 }}
              variant="borderless"
            />
            <div className="chat-composer__toolbar chat-composer__toolbar--minimal">
              <Tooltip title={!isUserLoggedIn() ? '请先登录' : '上传附件'}>
                <span className="chat-composer__tooltip-anchor">
                  {!isUserLoggedIn() || submitting ? (
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
              <Tooltip title="发送（Enter）">
                <span className="chat-composer__tooltip-anchor">
                  <button
                    type="button"
                    className={`chat-composer__send${submitting ? ' chat-composer__send--loading' : ''}`}
                    disabled={submitting || !isUserLoggedIn()}
                    onClick={() => void sendMessage()}
                    aria-label="发送"
                  >
                    {submitting ? <span className="chat-composer__spinner chat-composer__spinner--light" /> : <ArrowUpOutlined />}
                  </button>
                </span>
              </Tooltip>
            </div>
          </div>
        </Card>
      </Col>

      <Col xs={24} lg={6}>
        <Card className="portal-card" variant="borderless" title="工作空间" style={{ height: '100%' }}>
          {workspaceFiles.length === 0 ? (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无产物文件" />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {workspaceFiles.map((item) => (
                <div key={`${item.round_id}-${item.relative_path}`} style={{ paddingBottom: 10, borderBottom: '1px solid #f0f0f0' }}>
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
      </Col>
    </Row>
  );
}
