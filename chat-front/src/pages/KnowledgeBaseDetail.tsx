import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Button,
  Empty,
  Form,
  Modal,
  Popconfirm,
  Select,
  Spin,
  Table,
  Tag,
  Tooltip,
  Typography,
  Upload,
  message,
} from 'antd';
import type { UploadFile } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  ArrowLeftOutlined,
  ClockCircleOutlined,
  DatabaseOutlined,
  DeleteOutlined,
  DownloadOutlined,
  ReloadOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import {
  getBackendErrorMessage,
  isUserLoggedIn,
  knowledgeBasesApi,
  modelManageApi,
} from '../api';
import type { ChatModelOption, KnowledgeBase, KnowledgeDocument, KnowledgeDocumentStatus } from '../api';

const { Title, Paragraph } = Typography;
const BUILTIN_TYPE = 1;
const POLL_INTERVAL_MS = 4000;

const STATUS_META: Record<
  KnowledgeDocumentStatus,
  { label: string; color: 'default' | 'processing' | 'success' | 'error' }
> = {
  pending: { label: '待处理', color: 'default' },
  processing: { label: '索引中', color: 'processing' },
  ready: { label: '就绪', color: 'success' },
  failed: { label: '失败', color: 'error' },
};

function formatFileSize(bytes: number) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDocDate(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function KnowledgeBaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const knowledgeBaseId = Number(id);
  const navigate = useNavigate();

  const [kb, setKb] = useState<KnowledgeBase | null>(null);
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [embeddingModels, setEmbeddingModels] = useState<ChatModelOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [docsLoading, setDocsLoading] = useState(false);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [uploadSubmitting, setUploadSubmitting] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadFileList, setUploadFileList] = useState<UploadFile[]>([]);
  const [uploadForm] = Form.useForm<{ embedding_model_id?: string }>();
  const [reindexingDocId, setReindexingDocId] = useState<number | null>(null);
  const [downloadingDocId, setDownloadingDocId] = useState<number | null>(null);

  const embeddingLabelById = useMemo(() => {
    const map = new Map<string, string>();
    for (const m of embeddingModels) {
      map.set(m.id, m.provider_name ? `${m.name}（${m.provider_name}）` : m.name);
    }
    return map;
  }, [embeddingModels]);

  const fetchKb = useCallback(async () => {
    if (!Number.isFinite(knowledgeBaseId)) {
      setKb(null);
      return;
    }
    try {
      const data = await knowledgeBasesApi.getById(knowledgeBaseId);
      setKb(data);
    } catch (error) {
      message.error(getBackendErrorMessage(error, '获取知识库信息失败'));
      setKb(null);
    }
  }, [knowledgeBaseId]);

  const fetchDocuments = useCallback(async (silent = false) => {
    if (!Number.isFinite(knowledgeBaseId)) {
      setDocuments([]);
      return;
    }
    if (!silent) {
      setDocsLoading(true);
    }
    try {
      const data = await knowledgeBasesApi.listDocuments(knowledgeBaseId);
      setDocuments(data);
    } catch (error) {
      message.error(getBackendErrorMessage(error, '获取文档列表失败'));
    } finally {
      if (!silent) {
        setDocsLoading(false);
      }
    }
  }, [knowledgeBaseId]);

  const fetchEmbeddingModels = async () => {
    try {
      const data = await modelManageApi.listEmbeddingModels();
      setEmbeddingModels(data);
    } catch {
      /* 上传时再提示 */
    }
  };

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      await Promise.all([fetchKb(), fetchDocuments(), fetchEmbeddingModels()]);
      setLoading(false);
    };
    void load();
  }, [fetchKb, fetchDocuments]);

  const needsPolling = useMemo(
    () => documents.some((doc) => doc.status === 'pending' || doc.status === 'processing'),
    [documents],
  );

  useEffect(() => {
    if (!needsPolling) {
      return;
    }
    const timer = window.setInterval(() => {
      void fetchDocuments(true);
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [needsPolling, fetchDocuments]);

  const isBuiltin = kb?.type === BUILTIN_TYPE;
  const canManage = isUserLoggedIn() && kb != null && !isBuiltin;
  const kbHasEmbedding = Boolean(kb?.embedding_model_id);
  const embeddingLabel = kb?.embedding_model_id
    ? embeddingLabelById.get(kb.embedding_model_id) ?? `ID ${kb.embedding_model_id}`
    : '未配置（首次上传时选定）';

  const resetUploadModal = () => {
    uploadForm.resetFields();
    setUploadFile(null);
    setUploadFileList([]);
  };

  const openUploadModal = () => {
    resetUploadModal();
    if (kbHasEmbedding) {
      uploadForm.setFieldsValue({ embedding_model_id: kb?.embedding_model_id ?? undefined });
    }
    setUploadModalOpen(true);
  };

  const handleUpload = async () => {
    if (!kb || !uploadFile) {
      message.error('请选择要上传的文件');
      return;
    }
    try {
      let embeddingModelId: string | undefined;
      if (!kbHasEmbedding) {
        const values = await uploadForm.validateFields();
        embeddingModelId = values.embedding_model_id;
        if (!embeddingModelId) {
          message.error('请选择 Embedding 模型');
          return;
        }
      }
      setUploadSubmitting(true);
      await knowledgeBasesApi.uploadDocument(kb.id, uploadFile, embeddingModelId);
      message.success('上传成功，正在索引');
      setUploadModalOpen(false);
      resetUploadModal();
      await Promise.all([fetchKb(), fetchDocuments()]);
    } catch (error: unknown) {
      if ((error as { errorFields?: unknown })?.errorFields) {
        return;
      }
      message.error(getBackendErrorMessage(error, '上传失败'));
    } finally {
      setUploadSubmitting(false);
    }
  };

  const handleDeleteDocument = async (documentId: number) => {
    if (!kb) {
      return;
    }
    try {
      await knowledgeBasesApi.deleteDocument(kb.id, documentId);
      message.success('已删除文档');
      void fetchDocuments();
    } catch (error) {
      message.error(getBackendErrorMessage(error, '删除失败'));
    }
  };

  const canReindexDocument = (status: KnowledgeDocumentStatus) =>
    status === 'failed' || status === 'ready';

  const handleReindexDocument = async (documentId: number) => {
    if (!kb) {
      return;
    }
    setReindexingDocId(documentId);
    try {
      await knowledgeBasesApi.reindexDocument(kb.id, documentId);
      message.success('已开始重新索引');
      void fetchDocuments();
    } catch (error) {
      message.error(getBackendErrorMessage(error, '重新索引失败'));
    } finally {
      setReindexingDocId(null);
    }
  };

  const canDownloadDocument = (status: KnowledgeDocumentStatus) => status !== 'pending';

  const handleDownloadDocument = async (document: KnowledgeDocument) => {
    if (!kb) {
      return;
    }
    setDownloadingDocId(document.id);
    try {
      await knowledgeBasesApi.downloadDocument(kb.id, document.id, document.file_name);
    } catch (error) {
      message.error(getBackendErrorMessage(error, '下载失败'));
    } finally {
      setDownloadingDocId(null);
    }
  };

  const columns: ColumnsType<KnowledgeDocument> = [
    {
      title: '文件名',
      dataIndex: 'file_name',
      align: 'center',
      ellipsis: { showTitle: false },
      render: (name: string) => (
        <Tooltip title={name}>
          <span className="portal-kb-detail__file-name">{name}</span>
        </Tooltip>
      ),
    },
    {
      title: '大小',
      dataIndex: 'file_size',
      width: 96,
      align: 'center',
      render: (size: number) => formatFileSize(size),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 96,
      align: 'center',
      render: (status: KnowledgeDocumentStatus, record) => {
        const meta = STATUS_META[status] ?? STATUS_META.pending;
        const tag = <Tag color={meta.color}>{meta.label}</Tag>;
        if (status === 'failed' && record.error_message) {
          return (
            <Tooltip title={record.error_message} styles={{ root: { maxWidth: 360 } }}>
              <span className="portal-kb-detail__status-cell">{tag}</span>
            </Tooltip>
          );
        }
        return tag;
      },
    },
    {
      title: '分块数',
      dataIndex: 'chunk_count',
      width: 88,
      align: 'center',
    },
    {
      title: '上传时间',
      dataIndex: 'create_time',
      width: 168,
      align: 'center',
      render: (value: string) => (
        <span className="portal-kb-detail__time-cell">{formatDocDate(value)}</span>
      ),
    },
    {
      title: '操作',
      width: 132,
      align: 'center',
      render: (_, record) => {
        const showReindex = canManage && canReindexDocument(record.status);
        const showDownload = canDownloadDocument(record.status);
        const isReindexing = reindexingDocId === record.id;
        const isDownloading = downloadingDocId === record.id;

        if (!showDownload && !canManage) {
          return <span className="portal-kb-detail__row-actions portal-kb-detail__row-actions--empty">—</span>;
        }

        return (
          <span className="portal-kb-detail__row-actions">
            {showDownload && (
              <Tooltip title="下载">
                <Button
                  type="link"
                  size="small"
                  icon={<DownloadOutlined />}
                  loading={isDownloading}
                  disabled={downloadingDocId !== null && !isDownloading}
                  aria-label={`下载 ${record.file_name}`}
                  onClick={() => void handleDownloadDocument(record)}
                />
              </Tooltip>
            )}
            {showReindex && (
              <Tooltip title="重新索引">
                <Button
                  type="link"
                  size="small"
                  icon={<ReloadOutlined />}
                  loading={isReindexing}
                  disabled={reindexingDocId !== null && !isReindexing}
                  aria-label={`重新索引 ${record.file_name}`}
                  onClick={() => void handleReindexDocument(record.id)}
                />
              </Tooltip>
            )}
            {canManage && (
              <Popconfirm
                title="确定删除该文档吗？"
                onConfirm={() => void handleDeleteDocument(record.id)}
                okText="确定"
                cancelText="取消"
              >
                <Tooltip title="删除">
                  <Button
                    type="link"
                    danger
                    size="small"
                    icon={<DeleteOutlined />}
                    aria-label={`删除 ${record.file_name}`}
                  />
                </Tooltip>
              </Popconfirm>
            )}
          </span>
        );
      },
    },
  ];

  return (
    <div className="portal-kb-detail">
      <div className="portal-agent-detail__topbar portal-kb-detail__topbar">
        <button type="button" className="portal-agent-detail__back" onClick={() => navigate('/knowledge-bases')}>
          <ArrowLeftOutlined />
          返回知识库列表
        </button>
      </div>

      <Spin spinning={loading}>
        {!kb ? (
          <Empty description={Number.isFinite(knowledgeBaseId) ? '知识库不存在或无权访问' : '无效的知识库 ID'} />
        ) : (
          <>
            <div className="portal-kb-detail__hero">
              <div className="portal-kb-detail__hero-icon" aria-hidden>
                <DatabaseOutlined />
              </div>
              <div className="portal-kb-detail__hero-body">
                <Title level={3} style={{ marginBottom: 4 }}>
                  {kb.name}
                </Title>
                <Paragraph type="secondary" style={{ marginBottom: 8 }}>
                  {kb.description?.trim() || '暂无描述'}
                </Paragraph>
                <div className="portal-kb-detail__meta">
                  <span>
                    <ClockCircleOutlined /> {formatDocDate(kb.create_time)}
                  </span>
                  <span>Embedding：{embeddingLabel}</span>
                  <span>{documents.length} 个文档</span>
                </div>
              </div>
              {canManage && (
                <div className="portal-kb-detail__hero-actions">
                  <Button
                    type="primary"
                    size="large"
                    icon={<UploadOutlined />}
                    className="portal-kb-detail__upload-btn"
                    onClick={openUploadModal}
                  >
                    上传文档
                  </Button>
                  <span className="portal-kb-detail__upload-hint">支持 PDF、Word、Excel 等</span>
                </div>
              )}
            </div>

            <div className="portal-kb-detail__panel">
              <div className="portal-kb-detail__panel-head">
                <Title level={5} className="portal-kb-detail__panel-title">
                  文档列表
                </Title>
              </div>
              <Table
                className="portal-kb-detail__doc-table"
                rowKey="id"
                columns={columns}
                dataSource={documents}
                loading={docsLoading}
                size="middle"
                pagination={{ pageSize: 10, hideOnSinglePage: true, showTotal: (t) => `共 ${t} 个文档` }}
                locale={{
                  emptyText: (
                    <div className="portal-kb-detail__empty">
                      <p>暂无文档</p>
                      <Paragraph type="secondary" style={{ marginBottom: 0 }}>
                        {canManage
                          ? '点击右上方「上传文档」，添加 PDF、Word、Excel、Markdown 等文件'
                          : '暂无可展示的文档'}
                      </Paragraph>
                    </div>
                  ),
                }}
              />
            </div>
          </>
        )}
      </Spin>

      <Modal
        title="上传文档"
        open={uploadModalOpen}
        onCancel={() => {
          setUploadModalOpen(false);
          resetUploadModal();
        }}
        destroyOnClose
        width={520}
        okText="上传"
        cancelText="取消"
        confirmLoading={uploadSubmitting}
        onOk={() => void handleUpload()}
      >
        {!kbHasEmbedding && (
          <Form form={uploadForm} layout="vertical" style={{ marginTop: 8 }}>
            <Form.Item
              name="embedding_model_id"
              label="Embedding 模型"
              rules={[{ required: true, message: '请选择 Embedding 模型' }]}
            >
              <Select
                placeholder={embeddingModels.length ? '选择向量化模型' : '请先在模型管理中配置 embedding 模型'}
                options={embeddingModels.map((m) => ({
                  value: m.id,
                  label: m.provider_name ? `${m.name}（${m.provider_name}）` : m.name,
                }))}
                disabled={embeddingModels.length === 0}
              />
            </Form.Item>
            <Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 16 }}>
              同一知识库内所有文档须使用相同 Embedding 模型，首次上传后将锁定。
            </Paragraph>
          </Form>
        )}
        <Form.Item label="文件" required style={{ marginBottom: 0 }}>
          <Upload
            accept=".pdf,.docx,.xlsx,.pptx,.txt,.csv,.json,.xml,.html,.md"
            maxCount={1}
            fileList={uploadFileList}
            beforeUpload={(file) => {
              setUploadFile(file);
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
              setUploadFile(null);
              setUploadFileList([]);
              return true;
            }}
          >
            <Button icon={<UploadOutlined />}>选择文件</Button>
          </Upload>
          <Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 0, fontSize: 12 }}>
            支持 PDF、Word、Excel、PPT、文本、Markdown 等常见格式。
          </Paragraph>
        </Form.Item>
      </Modal>
    </div>
  );
}
