import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
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
  Form,
  Input,
  Select,
  Tooltip,
} from 'antd';
import type { UploadFile } from 'antd';
import {
  UploadOutlined,
  DeleteOutlined,
  EditOutlined,
  ThunderboltOutlined,
  ClockCircleOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import { useLocation, useNavigate } from 'react-router-dom';
import { getBackendErrorMessage, goLoginPage, isUserLoggedIn, skillsApi } from '../api';
import type { Skill } from '../api';

const { Title, Paragraph } = Typography;

const HOVER_DELAY_SEC = 0.5;
const BUILTIN_TYPE = 1;

type SkillTypeFilter = 'all' | 'custom' | 'builtin';

const SKILL_TYPE_FILTER_OPTIONS: { label: string; value: SkillTypeFilter }[] = [
  { label: '全部', value: 'all' },
  { label: '自定义', value: 'custom' },
  { label: '系统内建', value: 'builtin' },
];

function formatSkillDate(iso: string) {
  const d = new Date(iso);
  const date = d.toLocaleDateString('zh-CN', { year: 'numeric', month: 'numeric', day: 'numeric' });
  const time = d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  return `${date} ${time}`;
}

function resolveSkillDisplayDesc(skill: Skill) {
  const custom = skill.description?.trim();
  if (custom) {
    return custom;
  }
  const pkg = skill.skill_desc?.trim();
  if (pkg) {
    return pkg;
  }
  return '暂无描述';
}

function SkillCardDesc({ text }: { text: string }) {
  const ref = useRef<HTMLParagraphElement>(null);
  const [overflow, setOverflow] = useState(false);
  const isEmpty = text === '暂无描述';

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) {
      return;
    }
    setOverflow(el.scrollHeight > el.clientHeight + 1);
  }, [text]);

  const body = (
    <p
      ref={ref}
      className={`portal-skill-card__desc${isEmpty ? ' is-empty' : ''}${overflow ? ' is-help' : ''}`}
    >
      {text}
    </p>
  );

  if (!overflow || isEmpty) {
    return body;
  }

  return (
    <Tooltip
      title={<span className="portal-skill-card__desc-tooltip">{text}</span>}
      mouseEnterDelay={HOVER_DELAY_SEC}
      styles={{ root: { maxWidth: 360 } }}
    >
      {body}
    </Tooltip>
  );
}

function SkillCardTitle({ name }: { name: string }) {
  const ref = useRef<HTMLHeadingElement>(null);
  const [overflow, setOverflow] = useState(false);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) {
      return;
    }
    setOverflow(el.scrollWidth > el.clientWidth + 1);
  }, [name]);

  const title = (
    <h3 ref={ref} className={`portal-skill-card__title${overflow ? ' is-truncated' : ''}`}>
      {name}
    </h3>
  );

  if (!overflow) {
    return title;
  }

  return (
    <Tooltip
      title={name}
      mouseEnterDelay={HOVER_DELAY_SEC}
      color="rgba(15, 23, 42, 0.92)"
      styles={{ root: { maxWidth: 360 } }}
    >
      <div className="portal-skill-card__title-wrap">{title}</div>
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
  const displayDesc = resolveSkillDisplayDesc(skill);

  return (
    <article className="portal-skill-card-wrap">
      <span
        className={`portal-skill-card__badge portal-skill-card__badge--corner ${
          isBuiltin ? 'portal-skill-card__badge--builtin' : 'portal-skill-card__badge--custom'
        }`}
      >
        {isBuiltin ? '内置' : '自定义'}
      </span>

      {loggedIn && (
        <div className="portal-skill-card__hover-actions" onClick={(e) => e.stopPropagation()}>
          <Tooltip title={isBuiltin ? '内置技能不可编辑' : '编辑描述'}>
            <button
              type="button"
              className="portal-skill-card__icon-btn"
              disabled={!canManage}
              aria-label="编辑描述"
              onClick={() => onEdit(skill)}
            >
              <EditOutlined />
            </button>
          </Tooltip>
          <Popconfirm
            title="确定删除该技能吗？"
            onConfirm={() => void onDelete(skill.id)}
            okText="确定"
            cancelText="取消"
            disabled={!canManage}
          >
            <Tooltip title={isBuiltin ? '内置技能不可删除' : '删除'}>
              <button
                type="button"
                className="portal-skill-card__icon-btn portal-skill-card__icon-btn--delete"
                disabled={!canManage}
                aria-label="删除技能"
              >
                <DeleteOutlined />
              </button>
            </Tooltip>
          </Popconfirm>
        </div>
      )}

      <div className="portal-skill-card__badge-row" aria-hidden />

      <div className="portal-skill-card__head">
        <div className="portal-skill-card__avatar" aria-hidden>
          <ThunderboltOutlined />
        </div>
        <div className="portal-skill-card__head-main">
          <SkillCardTitle name={skill.name} />
        </div>
      </div>

      <div className="portal-skill-card__middle">
        <SkillCardDesc text={displayDesc} />
      </div>

      <div className="portal-skill-card__bottom">
        <span className="portal-skill-card__meta">
          <ClockCircleOutlined />
          {formatSkillDate(skill.create_time)}
        </span>
      </div>
    </article>
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
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState<SkillTypeFilter>('all');

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

  const displaySkills = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return skills.filter((skill) => {
      if (typeFilter === 'builtin' && skill.type !== BUILTIN_TYPE) {
        return false;
      }
      if (typeFilter === 'custom' && skill.type === BUILTIN_TYPE) {
        return false;
      }
      if (!q) {
        return true;
      }
      const desc = resolveSkillDisplayDesc(skill).toLowerCase();
      return skill.name.toLowerCase().includes(q) || desc.includes(q);
    });
  }, [skills, searchQuery, typeFilter]);

  const isFiltering = searchQuery.trim().length > 0 || typeFilter !== 'all';

  return (
    <div>
      <div className="portal-page-hero">
        <Title level={2}>技能</Title>
        <Paragraph type="secondary" style={{ maxWidth: 560, marginBottom: 0 }}>
          技能以压缩包形式扩展智能体能力。上传后可在「智能体」详情中为角色关联技能。
        </Paragraph>
        <div className="portal-toolbar portal-skills-toolbar">
          <div className="portal-toolbar-left portal-skills-toolbar__left">
            <Input
              allowClear
              prefix={<SearchOutlined style={{ color: 'var(--portal-muted)' }} />}
              placeholder="搜索技能名称/描述..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="portal-skills-toolbar__search"
            />
            <Select
              value={typeFilter}
              onChange={setTypeFilter}
              options={SKILL_TYPE_FILTER_OPTIONS}
              className="portal-skills-toolbar__filter"
            />
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
        {!loading && skills.length === 0 ? (
          <Empty description="暂无技能，上传符合规范的 .zip 技能包" />
        ) : !loading && displaySkills.length === 0 ? (
          <Empty description={isFiltering ? '未找到匹配的技能' : '暂无技能'} />
        ) : (
          <Row gutter={[14, 14]} className="portal-skills-grid">
            {displaySkills.map((skill) => (
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
