import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Button,
  Col,
  Empty,
  Form,
  Input,
  Modal,
  Popconfirm,
  Row,
  Spin,
  Tooltip,
  Typography,
  message,
  Pagination,
  Select,
} from 'antd';
import {
  ClockCircleOutlined,
  DatabaseOutlined,
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  getBackendErrorMessage,
  goLoginPage,
  isUserLoggedIn,
  knowledgeBasesApi,
  modelManageApi,
} from '../api';
import type { ChatModelOption, KnowledgeBase } from '../api';

const { Title, Paragraph } = Typography;
const BUILTIN_TYPE = 1;
const PAGE_SIZE = 12;
const SEARCH_DEBOUNCE_MS = 300;

type KbTypeFilter = 'all' | 'custom' | 'builtin';

const KB_TYPE_FILTER_OPTIONS: { label: string; value: KbTypeFilter }[] = [
  { label: '全部', value: 'all' },
  { label: '自定义', value: 'custom' },
  { label: '系统内建', value: 'builtin' },
];

function formatKbDate(iso: string) {
  const d = new Date(iso);
  const date = d.toLocaleDateString('zh-CN', { year: 'numeric', month: 'numeric', day: 'numeric' });
  const time = d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  return `${date} ${time}`;
}

function resolveKbDesc(kb: KnowledgeBase) {
  return kb.description?.trim() || '暂无描述';
}

function KnowledgeBaseCard({
  kb,
  embeddingLabel,
  onOpen,
  onEdit,
  onDelete,
}: {
  kb: KnowledgeBase;
  embeddingLabel: string;
  onOpen: (kb: KnowledgeBase) => void;
  onEdit: (kb: KnowledgeBase) => void;
  onDelete: (id: number) => void;
}) {
  const isBuiltin = kb.type === BUILTIN_TYPE;
  const loggedIn = isUserLoggedIn();
  const canManage = loggedIn && !isBuiltin;
  const displayDesc = resolveKbDesc(kb);

  return (
    <article
      className="portal-skill-card-wrap portal-kb-card-wrap"
      role="button"
      tabIndex={0}
      onClick={() => onOpen(kb)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onOpen(kb);
        }
      }}
    >
      <span
        className={`portal-skill-card__badge portal-skill-card__badge--corner ${
          isBuiltin ? 'portal-skill-card__badge--builtin' : 'portal-skill-card__badge--custom'
        }`}
      >
        {isBuiltin ? '内置' : '自定义'}
      </span>

      {loggedIn && (
        <div className="portal-skill-card__hover-actions" onClick={(e) => e.stopPropagation()}>
          <Tooltip title={isBuiltin ? '内置知识库不可编辑' : '编辑'}>
            <button
              type="button"
              className="portal-skill-card__icon-btn"
              disabled={!canManage}
              aria-label="编辑知识库"
              onClick={() => onEdit(kb)}
            >
              <EditOutlined />
            </button>
          </Tooltip>
          <Popconfirm
            title="确定删除该知识库吗？"
            description="将同时删除库内文档与向量索引，且会从已关联的智能体中移除。"
            onConfirm={() => void onDelete(kb.id)}
            okText="确定"
            cancelText="取消"
            disabled={!canManage}
          >
            <Tooltip title={isBuiltin ? '内置知识库不可删除' : '删除'}>
              <button
                type="button"
                className="portal-skill-card__icon-btn portal-skill-card__icon-btn--delete"
                disabled={!canManage}
                aria-label="删除知识库"
              >
                <DeleteOutlined />
              </button>
            </Tooltip>
          </Popconfirm>
        </div>
      )}

      <div className="portal-skill-card__badge-row" aria-hidden />

      <div className="portal-skill-card__head">
        <div className="portal-skill-card__avatar portal-kb-card__avatar" aria-hidden>
          <DatabaseOutlined />
        </div>
        <div className="portal-skill-card__head-main">
          <h3 className="portal-skill-card__title">{kb.name}</h3>
        </div>
      </div>

      <div className="portal-skill-card__middle">
        <p className={`portal-skill-card__desc${displayDesc === '暂无描述' ? ' is-empty' : ''}`}>{displayDesc}</p>
        <p className="portal-kb-card__embedding">{embeddingLabel}</p>
      </div>

      <div className="portal-skill-card__bottom">
        <span className="portal-skill-card__meta">
          <ClockCircleOutlined />
          {formatKbDate(kb.create_time)}
        </span>
      </div>
    </article>
  );
}

export default function KnowledgeBasesPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [items, setItems] = useState<KnowledgeBase[]>([]);
  const [embeddingModels, setEmbeddingModels] = useState<ChatModelOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [searchInput, setSearchInput] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState<KbTypeFilter>('all');
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createSubmitting, setCreateSubmitting] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editSubmitting, setEditSubmitting] = useState(false);
  const [editingKb, setEditingKb] = useState<KnowledgeBase | null>(null);
  const [createForm] = Form.useForm<{ name: string; description?: string; embedding_model_id?: string }>();
  const [editForm] = Form.useForm<{ name: string; description?: string }>();

  const embeddingLabelById = useMemo(() => {
    const map = new Map<string, string>();
    for (const m of embeddingModels) {
      map.set(m.id, m.provider_name ? `${m.name}（${m.provider_name}）` : m.name);
    }
    return map;
  }, [embeddingModels]);

  const fetchItems = useCallback(async (targetPage: number) => {
    setLoading(true);
    try {
      const data = await knowledgeBasesApi.list({
        page: targetPage,
        page_size: PAGE_SIZE,
        q: searchQuery || undefined,
        type: typeFilter,
      });
      setItems(data.items);
      setTotal(data.total);
      if (data.total > 0 && data.items.length === 0 && targetPage > 1) {
        setPage(targetPage - 1);
      }
    } catch (error) {
      message.error(getBackendErrorMessage(error, '获取知识库列表失败'));
    } finally {
      setLoading(false);
    }
  }, [searchQuery, typeFilter]);

  const fetchEmbeddingModels = async () => {
    try {
      const data = await modelManageApi.listEmbeddingModels();
      setEmbeddingModels(data);
    } catch (error) {
      message.error(getBackendErrorMessage(error, '获取 Embedding 模型列表失败'));
    }
  };

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setSearchQuery(searchInput.trim());
      setPage(1);
    }, SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    void fetchItems(page);
  }, [page, fetchItems]);

  useEffect(() => {
    void fetchEmbeddingModels();
  }, []);

  const requireLogin = () => {
    if (isUserLoggedIn()) {
      return true;
    }
    message.warning('请先登录');
    goLoginPage(navigate, { pathname: location.pathname, search: location.search });
    return false;
  };

  const openCreateModal = () => {
    if (!requireLogin()) {
      return;
    }
    createForm.resetFields();
    setCreateModalOpen(true);
  };

  const handleCreate = async () => {
    if (!requireLogin()) {
      return;
    }
    try {
      const values = await createForm.validateFields();
      setCreateSubmitting(true);
      await knowledgeBasesApi.create({
        name: values.name.trim(),
        description: values.description?.trim() || undefined,
        embedding_model_id: values.embedding_model_id || null,
      });
      message.success('创建成功');
      setCreateModalOpen(false);
      void fetchItems(page);
    } catch (error: unknown) {
      if ((error as { errorFields?: unknown })?.errorFields) {
        return;
      }
      message.error(getBackendErrorMessage(error, '创建失败'));
    } finally {
      setCreateSubmitting(false);
    }
  };

  const openEditModal = (kb: KnowledgeBase) => {
    if (!requireLogin() || kb.type === BUILTIN_TYPE) {
      return;
    }
    setEditingKb(kb);
    editForm.setFieldsValue({
      name: kb.name,
      description: kb.description ?? '',
    });
    setEditModalOpen(true);
  };

  const handleEdit = async () => {
    if (!editingKb || !requireLogin()) {
      return;
    }
    try {
      const values = await editForm.validateFields();
      setEditSubmitting(true);
      await knowledgeBasesApi.update(editingKb.id, {
        name: values.name.trim(),
        description: values.description?.trim() || null,
      });
      message.success('保存成功');
      setEditModalOpen(false);
      setEditingKb(null);
      void fetchItems(page);
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
    if (!requireLogin()) {
      return;
    }
    try {
      await knowledgeBasesApi.delete(id);
      message.success('删除成功');
      const nextPage = items.length === 1 && page > 1 ? page - 1 : page;
      if (nextPage !== page) {
        setPage(nextPage);
      } else {
        void fetchItems(page);
      }
    } catch (error) {
      message.error(getBackendErrorMessage(error, '删除失败'));
    }
  };

  const resolveEmbeddingLabel = (kb: KnowledgeBase) => {
    if (!kb.embedding_model_id) {
      return 'Embedding：首次上传文档时选定';
    }
    return `Embedding：${embeddingLabelById.get(kb.embedding_model_id) ?? `ID ${kb.embedding_model_id}`}`;
  };

  const isFiltering = searchQuery.length > 0 || typeFilter !== 'all';

  return (
    <div>
      <div className="portal-page-hero">
        <Title level={2}>知识库</Title>
        <Paragraph type="secondary" style={{ maxWidth: 560, marginBottom: 0 }}>
          上传企业文档并建立向量索引。在「智能体」详情中关联知识库后，对话时可检索相关片段。
        </Paragraph>
        <div className="portal-toolbar portal-skills-toolbar">
          <div className="portal-toolbar-left portal-skills-toolbar__left">
            <Input
              allowClear
              prefix={<SearchOutlined style={{ color: 'var(--portal-muted)' }} />}
              placeholder="搜索知识库名称/描述..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="portal-skills-toolbar__search"
            />
            <Select
              value={typeFilter}
              onChange={(value) => {
                setTypeFilter(value);
                setPage(1);
              }}
              options={KB_TYPE_FILTER_OPTIONS}
              className="portal-skills-toolbar__filter"
            />
          </div>
          <div className="portal-toolbar-actions">
            {isUserLoggedIn() && (
              <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>
                新建知识库
              </Button>
            )}
          </div>
        </div>
      </div>

      <Spin spinning={loading}>
        {!loading && total === 0 ? (
          <Empty
            description={
              isFiltering ? '未找到匹配的知识库' : '暂无知识库，点击「新建知识库」开始'
            }
          />
        ) : (
          <>
            <Row gutter={[14, 14]} className="portal-skills-grid">
              {items.map((kb) => (
                <Col xs={24} sm={12} md={8} lg={6} xl={4} key={kb.id}>
                  <KnowledgeBaseCard
                    kb={kb}
                    embeddingLabel={resolveEmbeddingLabel(kb)}
                    onOpen={(item) => navigate(`/knowledge-bases/${item.id}`)}
                    onEdit={openEditModal}
                    onDelete={handleDelete}
                  />
                </Col>
              ))}
            </Row>
            {total > PAGE_SIZE && (
              <div className="portal-skills-pagination">
                <Pagination
                  current={page}
                  pageSize={PAGE_SIZE}
                  total={total}
                  showSizeChanger={false}
                  onChange={(nextPage) => setPage(nextPage)}
                />
              </div>
            )}
          </>
        )}
      </Spin>

      <Modal
        title="新建知识库"
        open={createModalOpen}
        onCancel={() => setCreateModalOpen(false)}
        destroyOnClose
        width={520}
        okText="创建"
        cancelText="取消"
        confirmLoading={createSubmitting}
        onOk={() => void handleCreate()}
      >
        <Form form={createForm} layout="vertical" style={{ marginTop: 8 }}>
          <Form.Item
            name="name"
            label="名称"
            rules={[
              { required: true, message: '请填写知识库名称' },
              { max: 64, message: '名称过长' },
            ]}
          >
            <Input placeholder="例如：产品手册、人事制度" maxLength={64} />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} placeholder="简要说明库内文档类型与用途" maxLength={500} showCount />
          </Form.Item>
          <Form.Item name="embedding_model_id" label="Embedding 模型（可选）">
            <Select
              allowClear
              placeholder={embeddingModels.length ? '也可在首次上传文档时再选定' : '请先在模型管理中配置 embedding 模型'}
              options={embeddingModels.map((m) => ({
                value: m.id,
                label: m.provider_name ? `${m.name}（${m.provider_name}）` : m.name,
              }))}
              disabled={embeddingModels.length === 0}
            />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={editingKb ? `编辑知识库：${editingKb.name}` : '编辑知识库'}
        open={editModalOpen}
        onCancel={() => {
          setEditModalOpen(false);
          setEditingKb(null);
        }}
        destroyOnClose
        width={520}
        okText="保存"
        cancelText="取消"
        confirmLoading={editSubmitting}
        onOk={() => void handleEdit()}
      >
        <Form form={editForm} layout="vertical" style={{ marginTop: 8 }}>
          <Form.Item
            name="name"
            label="名称"
            rules={[
              { required: true, message: '请填写知识库名称' },
              { max: 64, message: '名称过长' },
            ]}
          >
            <Input maxLength={64} />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} maxLength={500} showCount />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
