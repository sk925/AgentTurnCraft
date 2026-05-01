import { useEffect, useMemo, useState } from 'react';
import {
  Avatar,
  Badge,
  Button,
  Card,
  Col,
  Empty,
  Input,
  Row,
  Space,
  Tag,
  Typography,
  message,
} from 'antd';
import { TeamOutlined, UserOutlined } from '@ant-design/icons';
import { chatWindowApi, sessionsApi } from '../api';
import type { ChatWindowEvent, SessionMessage, SessionType, WorkspaceArtifactFile } from '../api';
import { useNavigate, useSearchParams } from 'react-router-dom';
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
  const isGroupChat = sessionType === 'group';
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [orgId] = useState<number>(1);
  const [memberId] = useState<number>(1);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [input, setInput] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [groupMembers, setGroupMembers] = useState<Array<{ id: number; name: string }>>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [workspaceFiles, setWorkspaceFiles] = useState<WorkspaceArtifactFile[]>([]);
  const [currentSpeaker, setCurrentSpeaker] = useState<{ id: number; name: string } | null>(null);

  const currentSpeakerId = useMemo(() => {
    return currentSpeaker?.id ?? null;
  }, [currentSpeaker]);

  const chatMessages = useMemo(() => messages.filter((item) => item.role !== 'system'), [messages]);

  const emptyChatDescription = useMemo(() => {
    if (sessionId) return '历史对话';
    return isGroupChat ? '新建群聊' : '新建对话';
  }, [isGroupChat, sessionId]);

  // 切换“对话/群聊”模式时，若 URL 中没有显式 session_id，需要清空旧状态
  // 否则可能保留旧 sessionId/messages，导致默认文案“看起来没生效”
  useEffect(() => {
    setSessionId(null);
    setGroupMembers([]);
    setCurrentSpeaker(null);
    setMessages([]);
    setWorkspaceFiles([]);
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
    const sid = targetSessionId ?? sessionId;
    if (!sid) {
      return;
    }
    try {
      const files = await chatWindowApi.getWorkspaceFiles(memberId, sid);
      setWorkspaceFiles(files);
    } catch (error) {
      console.error(error);
    }
  };

  const handleEvent = (event: ChatWindowEvent) => {
    switch (event.event) {
      case 'start':
        setSessionId(event.session_id);
        void refreshWorkspaceFiles(event.session_id);
        break;
      case 'create_group':
        setGroupMembers(event.group_members ?? []);
        break;
      case 'select_speaker':
        // 新一轮选人：结束上一轮可能未收到收尾 speaker 的流式气泡
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
        // 发言轮结束：仅做收尾状态标记，不新增“超级助手”气泡
        setMessages((prev) =>
          prev.map((m) => (m.streaming ? { ...m, streaming: false } : m)),
        );
        setCurrentSpeaker(null);
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
        void refreshWorkspaceFiles();
        break;
      default:
        break;
    }
  };

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || submitting) {
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
    try {
      await chatWindowApi.streamChat(
        {
          user_message: text,
          org_id: orgId,
          member_id: memberId,
          session_id: sessionId,
          round_id: null,
          session_type: sessionType,
        },
        handleEvent,
      );
    } catch (error) {
      console.error(error);
      message.error('对话请求失败，请检查后端服务');
    } finally {
      setSubmitting(false);
    }
  };

  useEffect(() => {
    const selectedSessionId = searchParams.get('session_id');
    if (!selectedSessionId) {
      // 未指定 session_id：视为“新建”，需要保证窗口干净
      setSessionId(null);
      setCurrentSpeaker(null);
      setMessages([]);
      setWorkspaceFiles([]);
      if (isGroupChat) {
        setGroupMembers([]);
      }
      return;
    }
    if (selectedSessionId === sessionId) {
      return;
    }
    void (async () => {
      try {
        const allSessions = await sessionsApi.list(memberId, sessionType);
        const exists = allSessions.some((item) => item.id === selectedSessionId);
        if (!exists) {
          // 当前账号下无此会话：不再请求 messages，并清理 URL
          navigate(isGroupChat ? '/group-chat' : '/chat', { replace: true });
          setSessionId(null);
          setMessages([]);
          setWorkspaceFiles([]);
          if (isGroupChat) {
            setGroupMembers([]);
          }
          setCurrentSpeaker(null);
          return;
        }

        setSessionId(selectedSessionId);
        if (isGroupChat) {
          setGroupMembers([]);
        }
        setCurrentSpeaker(null);
        await refreshWorkspaceFiles(selectedSessionId);
        const records = await sessionsApi.getMessages(selectedSessionId, memberId);
        setMessages((Array.isArray(records) ? records : []).map(toChatMessage));
      } catch (error) {
        console.error('加载会话消息失败', error);
        message.error('加载会话消息失败');
      }
    })();
  }, [searchParams, memberId, sessionId, sessionType, isGroupChat, navigate]);

  return (
    <Row gutter={16} style={{ minHeight: 'calc(100vh - 120px)' }}>
      {isGroupChat && (
        <Col span={5}>
          <Card title={<><TeamOutlined /> 群聊成员</>} style={{ height: '100%' }}>
            {groupMembers.length === 0 ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="尚未创建群聊成员" />
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {groupMembers.map((item) => (
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

      <Col span={isGroupChat ? 13 : 18}>
        <Card title="群聊对话" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
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
              placeholder="输入你的问题..."
              onChange={(e) => setInput(e.target.value)}
              onPressEnter={sendMessage}
              disabled={submitting}
            />
            <Button type="primary" loading={submitting} onClick={sendMessage}>
              发送
            </Button>
          </Space.Compact>
        </Card>
      </Col>

      <Col span={6}>
        <Card title="工作空间" style={{ height: '100%' }}>
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
