import { useEffect, useMemo, useState } from 'react';
import {
  Avatar,
  Badge,
  Button,
  Card,
  Col,
  Input,
  List,
  Row,
  Space,
  Tag,
  Typography,
  message,
} from 'antd';
import { TeamOutlined, UserOutlined } from '@ant-design/icons';
import { chatWindowApi, sessionsApi } from '../api';
import type { ChatWindowEvent, SessionMessage, WorkspaceArtifactFile } from '../api';
import { useSearchParams } from 'react-router-dom';
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

export default function ChatWindowPage() {
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
    if (!selectedSessionId || selectedSessionId === sessionId) {
      return;
    }
    setSessionId(selectedSessionId);
    setGroupMembers([]);
    setCurrentSpeaker(null);
    void refreshWorkspaceFiles(selectedSessionId);
    void sessionsApi
      .getMessages(selectedSessionId, memberId)
      .then((records) => {
        setMessages(records.map(toChatMessage));
      })
      .catch((error) => {
        console.error('加载会话消息失败', error);
        message.error('加载会话消息失败');
      });
  }, [searchParams, memberId, sessionId]);

  return (
    <Row gutter={16} style={{ minHeight: 'calc(100vh - 120px)' }}>
      <Col span={5}>
        <Card title={<><TeamOutlined /> 群聊成员</>} style={{ height: '100%' }}>
          <List
            dataSource={groupMembers}
            locale={{ emptyText: '尚未创建群聊成员' }}
            renderItem={(item) => (
              <List.Item>
                <List.Item.Meta
                  avatar={
                    <Badge dot={currentSpeakerId === item.id} color="green">
                      <Avatar icon={<UserOutlined />} />
                    </Badge>
                  }
                  title={
                    <Space>
                      <span>{item.name}</span>
                      <Tag color={currentSpeakerId === item.id ? 'green' : 'default'}>
                        {currentSpeakerId === item.id ? '发言中' : `ID: ${item.id}`}
                      </Tag>
                    </Space>
                  }
                  description={currentSpeakerId === item.id ? '正在回复你的问题' : '待发言'}
                />
              </List.Item>
            )}
          />
        </Card>
      </Col>

      <Col span={13}>
        <Card title="群聊对话" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
          <div className="chat-scroll-panel">
            <List
              dataSource={chatMessages}
              locale={{ emptyText: '发一条消息，开始群聊' }}
              renderItem={(item) => (
                <List.Item>
                  <div className={`chat-row ${item.role === 'user' ? 'chat-row-self' : 'chat-row-speaker'}`}>
                    <div className={`chat-bubble ${item.role === 'user' ? 'chat-bubble-self' : 'chat-bubble-speaker'}`}>
                      <Typography.Text strong>
                        {item.role === 'user' ? '我' : item.title}
                      </Typography.Text>
                      <Typography.Paragraph className="chat-paragraph">
                        {item.content}
                      </Typography.Paragraph>
                    </div>
                  </div>
                </List.Item>
              )}
            />
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
          <List
            size="small"
            dataSource={workspaceFiles}
            locale={{ emptyText: '暂无产物文件' }}
            renderItem={(item) => (
              <List.Item>
                <div style={{ width: '100%' }}>
                  <Typography.Text strong>{item.name}</Typography.Text>
                  <div>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      {item.relative_path}
                    </Typography.Text>
                  </div>
                </div>
              </List.Item>
            )}
          />
        </Card>
      </Col>
    </Row>
  );
}
