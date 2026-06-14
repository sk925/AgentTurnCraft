import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import {
  Button,
  Modal,
  Upload,
  message,
  Popconfirm,
  Row,
  Col,
  Typography,
  Empty,
  Spin,
  Card,
  Form,
  Input,
  Tooltip,
} from 'antd';
import type { UploadFile } from 'antd';
import {
  UploadOutlined,
  DeleteOutlined,
  EditOutlined,
  ThunderboltOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons';
import { useLocation, useNavigate } from 'react-router-dom';
import { getBackendErrorMessage, goLoginPage, isUserLoggedIn, skillsApi } from '../api';
import type { Skill } from '../api';

const { Title, Paragraph } = Typography;

const HOVER_DELAY_SEC = 0.5;
const CLAMP_LINES = 2;
const BUILTIN_TYPE = 1;

function formatSkillDate(iso: string) {
  const d = new Date(iso);
  const date = d.toLocaleDateString('zh-CN', { year: 'numeric', month: 'numeric', day: 'numeric' });
  const time = d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  return `${date} ${time}`;
}

function ClampHoverText({
  text,
  placeholder = '—',
  lines = CLAMP_LINES,
  variant = 'primary',
}: {
  text: string | null | undefined;
  placeholder?: string;
  lines?: number;
  variant?: 'primary' | 'secondary';
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [overflow, setOverflow] = useState(false);
  const isEmpty = !text?.trim();
  const display = isEmpty ? placeholder : text!.trim();

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) {
      return;
    }
    setOverflow(el.scrollHeight > el.clientHeight + 1);
  }, [display, lines]);

  const body = (
    <div
      className={`portal-skill-card__content portal-skill-card__content--${variant}`}
    >
      <p
        ref={ref}
        className={`portal-skill-card__clamp${isEmpty ? ' is-empty' : ''}${overflow ? ' is-help' : ''}`}
        style={{ WebkitLineClamp: lines }}
      >
        {display}
      </p>
    </div>
  );

  if (!overflow || isEmpty) {
    return body;
  }

  return (
    <Tooltip title={display} mouseEnterDelay={HOVER_DELAY_SEC} styles={{ root: { maxWidth: 360 } }}>
      {body}
    </Tooltip>
  );
}

function SkillCard({
  skill,
  onEdit,
  onDelete,
}: {
  skill: Skill;
  onEdit: (skill: Skill) => void;
  onDelete: (id: number) => void;
}) {
  const isBuiltin = skill.type === BUILTIN_TYPE;
  const loggedIn = isUserLoggedIn();
  const canManage = loggedIn && !isBuiltin;

  return (
    <Card className="portal-card portal-skill-card" hoverable variant="borderless" style={{ height: '100%' }}>
      <div className="portal-card__head">
        <div className="portal-card__avatar" aria-hidden>
          <ThunderboltOutlined />
        </div>
        <div className="portal-skill-card__head-main">
          <div className="portal-skill-card__title-row">
            <h3 className="portal-card__title">{skill.name}</h3>
            <span
              className={`portal-skill-card__badge ${
                isBuiltin ? 'portal-skill-card__badge--builtin' : 'portal-skill-card__badge--custom'
              }`}
            >
              {isBuiltin ? '内置' : '自定义'}
            </span>
          </div>
          <div className="portal-skill-card__meta">
            <ClockCircleOutlined style={{ fontSize: 10, opacity: 0.7 }} />
            <span>{formatSkillDate(skill.create_time)}</span>
          </div>
        </div>
      </div>

      <div className="portal-card__body">
        <div className="portal-skill-card__sections">
          <section>
            <div className="portal-skill-card__section-head">
              <span className="portal-skill-card__label">
                <span className="portal-skill-card__label-mark portal-skill-card__label-mark--primary" />
                自定义描述
              </span>
              {loggedIn && (
                <Tooltip title={isBuiltin ? '内置技能不可编辑' : '编辑描述'}>
                  <button
                    type="button"
                    className="portal-skill-card__inline-edit"
                    disabled={!canManage}
                    aria-label="编辑自定义描述"
                    onClick={() => onEdit(skill)}
                  >
                    <EditOutlined style={{ fontSize: 11 }} />
                  </button>
                </Tooltip>
              )}
            </div>
            <ClampHoverText text={skill.description} placeholder="暂无描述" variant="primary" />
          </section>

          <section>
            <div className="portal-skill-card__section-head">
              <span className="portal-skill-card__label">
                <span className="portal-skill-card__label-mark portal-skill-card__label-mark--secondary" />
                包内描述
              </span>
            </div>
            <ClampHoverText text={skill.skill_desc} lines={1} variant="secondary" />
          </section>
        </div>
      </div>

      {loggedIn && (
        <div className="portal-card__footer">
          <div className="portal-skill-card__actions">
            <Popconfirm
              title="确定删除该技能吗？"
              onConfirm={() => void onDelete(skill.id)}
              okText="确定"
              cancelText="取消"
              disabled={!canManage}
            >
              <Button
                className="portal-skill-card__action-btn portal-skill-card__action-btn--delete"
                icon={<DeleteOutlined />}
                disabled={!canManage}
              >
                删除
              </Button>
            </Popconfirm>
          </div>
        </div>
      )}
    </Card>
  );
}

export default function SkillsPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [skills, setSkills] = useState<Skill[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploadModalVisible, setUploadModalVisible] = useState(false);
  const [uploadSubmitting, setUploadSubmitting] = useState(false);
  const [uploadForm] = Form.useForm<{ description: string }>();
  const [editForm] = Form.useForm<{ description: string }>();
  const [zipFile, setZipFile] = useState<File | null>(null);
  const [uploadFileList, setUploadFileList] = useState<UploadFile[]>([]);
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [editSubmitting, setEditSubmitting] = useState(false);
  const [editingSkill, setEditingSkill] = useState<Skill | null>(null);

  const fetchSkills = async () => {
    setLoading(true);
    try {
      const data = await skillsApi.getAll();
      setSkills(data);
    } catch (error) {
      message.error(getBackendErrorMessage(error, '获取技能列表失败'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchSkills();
  }, []);

  const resetUploadModal = () => {
    uploadForm.resetFields();
    setZipFile(null);
    setUploadFileList([]);
  };

  const openUploadModal = () => {
    if (!isUserLoggedIn()) {
      message.warning('请先登录后再上传技能');
      goLoginPage(navigate, { pathname: location.pathname, search: location.search });
      return;
    }
    resetUploadModal();
    setUploadModalVisible(true);
  };

  const closeUploadModal = () => {
    setUploadModalVisible(false);
    resetUploadModal();
  };

  const handleUploadSubmit = async () => {
    if (!isUserLoggedIn()) {
      message.warning('请先登录后再上传技能');
      goLoginPage(navigate, { pathname: location.pathname, search: location.search });
      return;
    }
    try {
      const { description } = await uploadForm.validateFields();
      if (!zipFile) {
        message.error('请选择 .zip 技能包');
        throw new Error('missing_file');
      }
      setUploadSubmitting(true);
      await skillsApi.upload(zipFile, description.trim());
      message.success('上传成功');
      closeUploadModal();
      void fetchSkills();
    } catch (error: unknown) {
      if ((error as { errorFields?: unknown })?.errorFields) {
        return;
      }
      message.error(getBackendErrorMessage(error, '上传失败'));
    } finally {
      setUploadSubmitting(false);
    }
  };

  const openEditModal = (skill: Skill) => {
    if (!isUserLoggedIn()) {
      message.warning('请先登录后再编辑技能');
      goLoginPage(navigate, { pathname: location.pathname, search: location.search });
      return;
    }
    if (skill.type === BUILTIN_TYPE) {
      return;
    }
    setEditingSkill(skill);
    editForm.setFieldsValue({ description: skill.description ?? '' });
    setEditModalVisible(true);
  };

  const closeEditModal = () => {
    setEditModalVisible(false);
    setEditingSkill(null);
    editForm.resetFields();
  };

  const handleEditSubmit = async () => {
    if (!editingSkill) {
      return;
    }
    if (!isUserLoggedIn()) {
      message.warning('请先登录后再编辑技能');
      goLoginPage(navigate, { pathname: location.pathname, search: location.search });
      return;
    }
    try {
      const { description } = await editForm.validateFields();
      setEditSubmitting(true);
      await skillsApi.update(editingSkill.id, { description: description.trim() });
      message.success('保存成功');
      closeEditModal();
      void fetchSkills();
    } catch (error: unknown) {
      if ((error as { errorFields?: unknown })?.errorFields) {
        return;
      }
      message.error(getBackendErrorMessage(error, '保存失败'));
    } finally {
      setEditSubmitting(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!isUserLoggedIn()) {
      message.warning('请先登录后再删除技能');
      goLoginPage(navigate, { pathname: location.pathname, search: location.search });
      return;
    }
    try {
      await skillsApi.delete(id);
      message.success('删除成功');
      void fetchSkills();
    } catch (error: unknown) {
      message.error(getBackendErrorMessage(error, '删除失败'));
    }
  };

  return (
    <div>
      <div className="portal-page-hero">
        <Title level={2}>技能</Title>
        <Paragraph type="secondary" style={{ maxWidth: 560, marginBottom: 0 }}>
          技能以压缩包形式扩展智能体能力。上传后可在「智能体」卡片中为角色关联技能。
        </Paragraph>
        <div className="portal-toolbar">
          <div className="portal-toolbar-left">
            <span style={{ color: 'var(--portal-muted)', fontSize: 13 }}>支持 .zip 技能包</span>
          </div>
          <div className="portal-toolbar-actions">
            {isUserLoggedIn() && (
              <Button type="primary" icon={<UploadOutlined />} onClick={openUploadModal}>
                上传技能
              </Button>
            )}
          </div>
        </div>
      </div>

      <Spin spinning={loading}>
        {skills.length === 0 ? (
          <Empty description="暂无技能，上传符合规范的 .zip 技能包" />
        ) : (
          <Row gutter={[14, 14]}>
            {skills.map((skill) => (
              <Col xs={24} sm={12} md={8} lg={6} xl={4} key={skill.id}>
                <SkillCard skill={skill} onEdit={openEditModal} onDelete={handleDelete} />
              </Col>
            ))}
          </Row>
        )}
      </Spin>

      <Modal
        title={editingSkill ? `编辑技能：${editingSkill.name}` : '编辑技能'}
        open={editModalVisible}
        onCancel={closeEditModal}
        destroyOnClose
        width={520}
        okText="保存"
        cancelText="取消"
        confirmLoading={editSubmitting}
        onOk={() => void handleEditSubmit()}
      >
        <Form form={editForm} layout="vertical" style={{ marginTop: 8 }}>
          <Form.Item
            name="description"
            label="自定义描述"
            rules={[
              { required: true, message: '请填写技能描述' },
              { min: 2, message: '至少输入 2 个字' },
              { max: 2000, message: '描述过长' },
            ]}
          >
            <Input.TextArea
              rows={4}
              placeholder="说明该技能的用途、适用场景等，将展示在技能卡片上"
              showCount
              maxLength={2000}
            />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="上传技能"
        open={uploadModalVisible}
        onCancel={closeUploadModal}
        destroyOnClose
        width={520}
        okText="上传"
        cancelText="取消"
        confirmLoading={uploadSubmitting}
        onOk={() => void handleUploadSubmit()}
      >
        <Form form={uploadForm} layout="vertical" style={{ marginTop: 8 }}>
          <Form.Item
            name="description"
            label="技能描述"
            rules={[
              { required: true, message: '请填写技能描述' },
              { min: 2, message: '至少输入 2 个字' },
              { max: 2000, message: '描述过长' },
            ]}
          >
            <Input.TextArea
              rows={4}
              placeholder="说明该技能的用途、适用场景等，将展示在技能卡片上"
              showCount
              maxLength={2000}
            />
          </Form.Item>
          <Form.Item label="技能包 (.zip)" required>
            <Upload
              accept=".zip"
              maxCount={1}
              fileList={uploadFileList}
              beforeUpload={(file) => {
                setZipFile(file);
                setUploadFileList([
                  {
                    uid: file.uid,
                    name: file.name,
                    status: 'done',
                    originFileObj: file,
                  },
                ]);
                return false;
              }}
              onRemove={() => {
                setZipFile(null);
                setUploadFileList([]);
                return true;
              }}
            >
              <Button icon={<UploadOutlined />}>选择文件</Button>
            </Upload>
            <Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 0, fontSize: 12 }}>
              上传符合 openclaw 规范的压缩包；名称可从包内 skill.md 的标题行读取。
            </Paragraph>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
