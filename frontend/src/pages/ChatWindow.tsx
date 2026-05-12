import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Avatar,
  Badge,
  Button,
  Card,
  Col,
  Empty,
  Input,
  Row,
  Select,
  Space,
  Tag,
  Typography,
  message,
} from 'antd';
import { TeamOutlined, UserOutlined } from '@ant-design/icons';
import {
  chatWebSocket,
  chatWindowApi,
  getBackendErrorMessage,
  getCurrentUserIdFromToken,
  goLoginPage,
  groupsApi,
  isUserLoggedIn,
  sessionsApi,
} from '../api';
import type { ChatWindowEvent, Group, SessionMessage, SessionType, WSServerMessage, WorkspaceArtifactFile } from '../api';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import './ChatWindow.css';

type ChatMessage = {
  id: string;
  role: 'user' | 'system' | 'speaker';
  title: string;
  content: string;
  speakerId?: number;
  /** 当前是否仍在接收 speaker_stream */
  streaming?: boolean;
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
      return {
        id: `history-user-${index}`,
        role: 'user',
        title: record.speaker_name || '我',
        content: record.message_content,
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
    if (!text || submitting) {
      return;
    }
    if (!isUserLoggedIn() || memberId == null) {
      message.warning('请先登录后再发送消息');
      goLoginPage(navigate, { pathname: location.pathname, search: location.search });
      return;
    }

    appendMessage({
      id: `user-${Date.now()}`,
      role: 'user',
      title: '我',
      content: text,
    });

    setInput('');
    setSubmitting(true);

    const sent = chatWebSocket.sendChat({
      user_message: text,
      org_id: orgId,
      session_id: sessionId,
      session_type: sessionType,
      group_id: isGroupChat && selectedGroupId != null ? selectedGroupId : undefined,
    });
    if (!sent) {
      setSubmitting(false);
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
          style={{ height: '100%', display: 'flex', flexDirection: 'column' }}
        >
          <div className="chat-scroll-panel">
            {chatMessages.length === 0 ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={emptyChatDescription} />
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {chatMessages.map((item) => (
                  <div key={item.id} className={`chat-row ${item.role === 'user' ? 'chat-row-self' : 'chat-row-speaker'}`}>
                    <div className={`chat-bubble ${item.role === 'user' ? 'chat-bubble-self' : 'chat-bubble-speaker'}`}>
                      <Typography.Text strong>
                        {item.role === 'user' ? '我' : item.title}
                      </Typography.Text>
                      <Typography.Paragraph className="chat-paragraph">
                        {item.content}
                      </Typography.Paragraph>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <Space.Compact style={{ width: '100%' }}>
            <Input
              value={input}
              placeholder={isUserLoggedIn() ? '输入你的问题...' : '请先登录后再发送消息'}
              onChange={(e) => setInput(e.target.value)}
              onPressEnter={() => void sendMessage()}
              disabled={submitting}
            />
            <Button type="primary" loading={submitting} onClick={() => void sendMessage()}>
              发送
            </Button>
          </Space.Compact>
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
