import { useEffect, useMemo, useState } from 'react';
import {
  Button,
  Input,
  Modal,
  message,
  Spin,
  Empty,
} from 'antd';
import {
  ArrowLeftOutlined,
  RobotOutlined,
  ClockCircleOutlined,
  ApiOutlined,
  ThunderboltOutlined,
  PlusOutlined,
  FileTextOutlined,
  CloseOutlined,
  SettingOutlined,
  DatabaseOutlined,
} from '@ant-design/icons';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import {
  agentsApi,
  getBackendErrorMessage,
  goLoginPage,
  isUserLoggedIn,
  modelManageApi,
  skillsApi,
  knowledgeBasesApi,
} from '../api';
import type { Agent, ChatModelOption, KnowledgeBase, Skill } from '../api';

const BUILTIN_TYPE = 1;
const MAX_AGENT_KNOWLEDGE_BASES = 3;

type DetailTab = 'settings' | 'prompt' | 'model' | 'skills' | 'knowledge';

function formatAgentDate(iso: string) {
  const d = new Date(iso);
  const date = d.toLocaleDateString('zh-CN', { year: 'numeric', month: 'numeric', day: 'numeric' });
  const time = d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  return `${date} ${time}`;
}

export default function AgentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const isCreateMode = id === 'new';
  const agentId = isCreateMode ? NaN : Number(id);
  const navigate = useNavigate();
  const location = useLocation();

  const [agent, setAgent] = useState<Agent | null>(null);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [chatModels, setChatModels] = useState<ChatModelOption[]>([]);
  const [loading, setLoading] = useState(!isCreateMode);
  const [creating, setCreating] = useState(false);
  const [savingPrompt, setSavingPrompt] = useState(false);
  const [savingModel, setSavingModel] = useState(false);
  const [savingBasic, setSavingBasic] = useState(false);
  const [activeTab, setActiveTab] = useState<DetailTab>('settings');
  const [nameDraft, setNameDraft] = useState('');
  const [descriptionDraft, setDescriptionDraft] = useState('');
  const [promptDraft, setPromptDraft] = useState('');
  const [modelDraft, setModelDraft] = useState<string | null>(null);
  const [addSkillModalOpen, setAddSkillModalOpen] = useState(false);
  const [addSkillSearch, setAddSkillSearch] = useState('');
  const [addingSkillId, setAddingSkillId] = useState<number | null>(null);
  const [addKbModalOpen, setAddKbModalOpen] = useState(false);
  const [addKbSearch, setAddKbSearch] = useState('');
  const [addingKbId, setAddingKbId] = useState<number | null>(null);

  const fetchAgent = async () => {
    if (!Number.isFinite(agentId)) {
      setAgent(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const data = await agentsApi.getWithSkills(agentId);
      setAgent(data);
    } catch (error) {
      message.error(getBackendErrorMessage(error, '获取智能体详情失败'));
      setAgent(null);
    } finally {
      setLoading(false);
    }
  };

  const fetchSkills = async () => {
    try {
      const data = await skillsApi.getAll();
      setSkills(data);
    } catch (error) {
      message.error(getBackendErrorMessage(error, '获取技能列表失败'));
    }
  };

  const fetchKnowledgeBases = async () => {
    try {
      const data = await knowledgeBasesApi.getAll();
      setKnowledgeBases(data);
    } catch (error) {
      message.error(getBackendErrorMessage(error, '获取知识库列表失败'));
    }
  };

  const fetchChatModels = async () => {
    try {
      const data = await modelManageApi.listChatModels();
      setChatModels(data);
    } catch (error) {
      message.error(getBackendErrorMessage(error, '获取聊天模型列表失败'));
    }
  };

  useEffect(() => {
    void fetchSkills();
    void fetchKnowledgeBases();
    void fetchChatModels();
  }, []);

  useEffect(() => {
    if (isCreateMode) {
      setLoading(false);
      setAgent(null);
      return;
    }
    void fetchAgent();
  }, [agentId, isCreateMode]);

  useEffect(() => {
    if (isCreateMode && !isUserLoggedIn()) {
      message.warning('请先登录');
      goLoginPage(navigate, { pathname: location.pathname, search: location.search });
    }
  }, [isCreateMode, navigate, location.pathname, location.search]);

  useEffect(() => {
    if (agent) {
      setNameDraft(agent.name);
      setDescriptionDraft(agent.description ?? '');
      setPromptDraft(agent.prompt ?? '');
      setModelDraft(agent.chat_model_id ?? null);
    }
  }, [agent?.id]);

  const chatModelLabelById = useMemo(() => {
    const map = new Map<string, string>();
    for (const m of chatModels) {
      map.set(m.id, m.provider_name ? `${m.name}（${m.provider_name}）` : m.name);
    }
    return map;
  }, [chatModels]);

  const agentSkills = agent?.skills ?? [];
  const linkedSkillIds = useMemo(() => new Set(agentSkills.map((s) => s.id)), [agentSkills]);
  const availableSkills = useMemo(
    () => skills.filter((s) => !linkedSkillIds.has(s.id)),
    [skills, linkedSkillIds],
  );
  const filteredAvailableSkills = useMemo(() => {
    const q = addSkillSearch.trim().toLowerCase();
    if (!q) {
      return availableSkills;
    }
    return availableSkills.filter((s) => {
      const desc = (s.description ?? s.skill_desc ?? '').toLowerCase();
      return s.name.toLowerCase().includes(q) || desc.includes(q);
    });
  }, [availableSkills, addSkillSearch]);

  const agentKnowledgeBases = agent?.knowledge_bases ?? [];
  const linkedKbIds = useMemo(() => new Set(agentKnowledgeBases.map((kb) => kb.id)), [agentKnowledgeBases]);
  const linkedEmbeddingModelId =
    agentKnowledgeBases.length > 0 ? agentKnowledgeBases[0].embedding_model_id ?? null : null;
  const kbAtLimit = agentKnowledgeBases.length >= MAX_AGENT_KNOWLEDGE_BASES;

  const availableKnowledgeBases = useMemo(
    () =>
      knowledgeBases.filter((kb) => {
        if (linkedKbIds.has(kb.id)) {
          return false;
        }
        if (kbAtLimit) {
          return false;
        }
        if (!kb.embedding_model_id) {
          return false;
        }
        if (linkedEmbeddingModelId && kb.embedding_model_id !== linkedEmbeddingModelId) {
          return false;
        }
        return true;
      }),
    [knowledgeBases, linkedKbIds, kbAtLimit, linkedEmbeddingModelId],
  );

  const filteredAvailableKnowledgeBases = useMemo(() => {
    const q = addKbSearch.trim().toLowerCase();
    if (!q) {
      return availableKnowledgeBases;
    }
    return availableKnowledgeBases.filter((kb) => {
      const desc = (kb.description ?? '').toLowerCase();
      return kb.name.toLowerCase().includes(q) || desc.includes(q);
    });
  }, [availableKnowledgeBases, addKbSearch]);

  const isBuiltin = !isCreateMode && agent?.type === BUILTIN_TYPE;
  const canManage = isUserLoggedIn() && (isCreateMode || !isBuiltin);
  const showPage = isCreateMode || !!agent;
  const savedName = agent?.name ?? '';
  const savedDescription = agent?.description ?? '';
  const savedPrompt = agent?.prompt ?? '';
  const savedModelId = agent?.chat_model_id ?? null;
  const basicDirty = nameDraft !== savedName || descriptionDraft !== savedDescription;
  const basicValid = nameDraft.trim().length > 0;
  const promptDirty = promptDraft !== savedPrompt;
  const modelDirty = modelDraft !== savedModelId;
  const promptCharCount = promptDraft.length;
  const promptLineCount = promptDraft ? promptDraft.split('\n').length : 0;

  const requireLogin = () => {
    if (isUserLoggedIn()) {
      return true;
    }
    message.warning('请先登录');
    goLoginPage(navigate, { pathname: location.pathname, search: location.search });
    return false;
  };

  const handleSaveBasic = async () => {
    if (!agent || !requireLogin() || !basicDirty || !basicValid) {
      return;
    }
    setSavingBasic(true);
    try {
      const name = nameDraft.trim();
      const description = descriptionDraft.trim() || null;
      await agentsApi.update(agent.id, { name, description: description ?? undefined });
      message.success('保存成功');
      setAgent({ ...agent, name, description });
      setNameDraft(name);
      setDescriptionDraft(description ?? '');
    } catch (error) {
      message.error(getBackendErrorMessage(error, '保存失败'));
    } finally {
      setSavingBasic(false);
    }
  };

  const handleCancelBasic = () => {
    setNameDraft(savedName);
    setDescriptionDraft(savedDescription);
  };

  const handleCreate = async () => {
    if (!requireLogin() || !basicValid) {
      return;
    }
    setCreating(true);
    try {
      const created = await agentsApi.create({
        name: nameDraft.trim(),
        description: descriptionDraft.trim() || undefined,
        prompt: promptDraft || undefined,
        chat_model_id: modelDraft,
      });
      message.success('创建成功');
      navigate(`/agents/${created.id}`, { replace: true });
    } catch (error) {
      message.error(getBackendErrorMessage(error, '创建失败'));
    } finally {
      setCreating(false);
    }
  };

  const handleSavePrompt = async () => {
    if (!agent || !requireLogin() || !promptDirty) {
      return;
    }
    setSavingPrompt(true);
    try {
      await agentsApi.update(agent.id, { prompt: promptDraft });
      message.success('保存成功');
      setAgent({ ...agent, prompt: promptDraft });
    } catch (error) {
      message.error(getBackendErrorMessage(error, '保存失败'));
    } finally {
      setSavingPrompt(false);
    }
  };

  const handleCancelPrompt = () => {
    setPromptDraft(savedPrompt);
  };

  const handleSaveModel = async () => {
    if (!agent || !requireLogin() || !modelDirty) {
      return;
    }
    setSavingModel(true);
    try {
      await agentsApi.update(agent.id, { chat_model_id: modelDraft });
      message.success('模型已保存');
      setAgent({ ...agent, chat_model_id: modelDraft });
    } catch (error) {
      message.error(getBackendErrorMessage(error, '保存失败'));
    } finally {
      setSavingModel(false);
    }
  };

  const handleCancelModel = () => {
    setModelDraft(savedModelId);
  };

  const handleAddSkill = async (skillId: number) => {
    if (!agent || !requireLogin()) {
      return;
    }
    setAddingSkillId(skillId);
    try {
      await agentsApi.addSkill(agent.id, skillId);
      message.success('关联成功');
      void fetchAgent();
    } catch (error) {
      message.error(getBackendErrorMessage(error, '关联失败'));
    } finally {
      setAddingSkillId(null);
    }
  };

  const openAddSkillModal = () => {
    setAddSkillSearch('');
    setAddSkillModalOpen(true);
  };

  const closeAddSkillModal = () => {
    setAddSkillModalOpen(false);
    setAddSkillSearch('');
    setAddingSkillId(null);
  };

  const handleRemoveSkill = async (skillId: number) => {
    if (!agent || !requireLogin()) {
      return;
    }
    try {
      await agentsApi.removeSkill(agent.id, skillId);
      message.success('已解除关联');
      void fetchAgent();
    } catch (error) {
      message.error(getBackendErrorMessage(error, '解除关联失败'));
    }
  };

  const handleAddKnowledgeBase = async (knowledgeBaseId: number) => {
    if (!agent || !requireLogin()) {
      return;
    }
    setAddingKbId(knowledgeBaseId);
    try {
      await agentsApi.addKnowledgeBase(agent.id, knowledgeBaseId);
      message.success('关联成功');
      void fetchAgent();
    } catch (error) {
      message.error(getBackendErrorMessage(error, '关联失败'));
    } finally {
      setAddingKbId(null);
    }
  };

  const openAddKbModal = () => {
    setAddKbSearch('');
    setAddKbModalOpen(true);
  };

  const closeAddKbModal = () => {
    setAddKbModalOpen(false);
    setAddKbSearch('');
    setAddingKbId(null);
  };

  const handleRemoveKnowledgeBase = async (knowledgeBaseId: number) => {
    if (!agent || !requireLogin()) {
      return;
    }
    try {
      await agentsApi.removeKnowledgeBase(agent.id, knowledgeBaseId);
      message.success('已解除关联');
      void fetchAgent();
    } catch (error) {
      message.error(getBackendErrorMessage(error, '解除关联失败'));
    }
  };

  const modelLabel = modelDraft
    ? chatModelLabelById.get(modelDraft) ?? `ID ${modelDraft}`
    : '未配置';

  const displayName = isCreateMode ? nameDraft.trim() || '新建智能体' : (agent?.name ?? '');
  const displayDescription = isCreateMode
    ? descriptionDraft.trim() || '暂无描述'
    : agent?.description?.trim()
      ? agent.description
      : '暂无描述';

  return (
    <div className="portal-agent-detail">
      <div className="portal-agent-detail__topbar">
        <button type="button" className="portal-agent-detail__back" onClick={() => navigate('/agents')}>
          <ArrowLeftOutlined />
          返回智能体列表
        </button>
        {isCreateMode && isUserLoggedIn() && (
          <div className="portal-agent-detail__actions">
            <Button
              type="primary"
              disabled={!basicValid}
              loading={creating}
              onClick={() => void handleCreate()}
            >
              创建智能体
            </Button>
          </div>
        )}
        {!isCreateMode && agent && canManage && (
          <div
            className={`portal-agent-detail__actions${
              activeTab !== 'settings' &&
              activeTab !== 'prompt' &&
              activeTab !== 'skills' &&
              activeTab !== 'knowledge' &&
              activeTab !== 'model'
                ? ' portal-agent-detail__actions--hidden'
                : ''
            }`}
            aria-hidden={
              activeTab !== 'settings' &&
              activeTab !== 'prompt' &&
              activeTab !== 'skills' &&
              activeTab !== 'knowledge' &&
              activeTab !== 'model'
            }
          >
            {activeTab === 'settings' && (
              <>
                <Button disabled={!basicDirty} onClick={handleCancelBasic}>
                  取消
                </Button>
                <Button
                  type="primary"
                  disabled={!basicDirty || !basicValid}
                  loading={savingBasic}
                  onClick={() => void handleSaveBasic()}
                >
                  保存
                </Button>
              </>
            )}
            {activeTab === 'prompt' && (
              <>
                <Button disabled={!promptDirty} onClick={handleCancelPrompt}>
                  取消
                </Button>
                <Button
                  type="primary"
                  disabled={!promptDirty}
                  loading={savingPrompt}
                  onClick={() => void handleSavePrompt()}
                >
                  保存
                </Button>
              </>
            )}
            {activeTab === 'model' && (
              <>
                <Button disabled={!modelDirty} onClick={handleCancelModel}>
                  取消
                </Button>
                <Button
                  type="primary"
                  disabled={!modelDirty}
                  loading={savingModel}
                  onClick={() => void handleSaveModel()}
                >
                  保存
                </Button>
              </>
            )}
            {activeTab === 'skills' && (
              <Button
                type="primary"
                icon={<PlusOutlined />}
                disabled={availableSkills.length === 0}
                onClick={openAddSkillModal}
              >
                关联新技能
              </Button>
            )}
            {activeTab === 'knowledge' && (
              <Button
                type="primary"
                icon={<PlusOutlined />}
                disabled={availableKnowledgeBases.length === 0 || kbAtLimit}
                onClick={openAddKbModal}
              >
                关联知识库
              </Button>
            )}
          </div>
        )}
      </div>

      <Spin spinning={loading}>
        {!showPage ? (
          <Empty
            description={
              !Number.isFinite(agentId) ? '无效的智能体 ID' : '智能体不存在或无权访问'
            }
          />
        ) : (
          <>
            <div className="portal-agent-detail__layout">
              <aside className="portal-agent-detail__sidebar">
                <div className="portal-agent-detail__sidebar-head">
                  <div className="portal-agent-detail__sidebar-icon" aria-hidden>
                    <RobotOutlined />
                  </div>
                  <h1 className="portal-agent-detail__sidebar-title">{displayName}</h1>
                  <span
                    className={`portal-agent-detail__badge ${
                      isBuiltin ? 'portal-agent-detail__badge--builtin' : 'portal-agent-detail__badge--custom'
                    }`}
                  >
                    {isBuiltin ? '内置' : '自定义'}
                  </span>
                </div>

                <p className="portal-agent-detail__sidebar-desc">{displayDescription}</p>

                <dl className="portal-agent-detail__meta-list">
                  <div className="portal-agent-detail__meta-row">
                    <dt className="portal-agent-detail__meta-label">
                      <ApiOutlined />
                      对话模型
                    </dt>
                    <dd className="portal-agent-detail__meta-value">{modelLabel}</dd>
                  </div>
                  <div className="portal-agent-detail__meta-row">
                    <dt className="portal-agent-detail__meta-label">
                      <ThunderboltOutlined />
                      关联技能
                    </dt>
                    <dd className="portal-agent-detail__meta-value">{agentSkills.length} 个</dd>
                  </div>
                  <div className="portal-agent-detail__meta-row">
                    <dt className="portal-agent-detail__meta-label">
                      <DatabaseOutlined />
                      关联知识库
                    </dt>
                    <dd className="portal-agent-detail__meta-value">
                      {agentKnowledgeBases.length} / {MAX_AGENT_KNOWLEDGE_BASES}
                    </dd>
                  </div>
                  <div className="portal-agent-detail__meta-row">
                    <dt className="portal-agent-detail__meta-label">
                      <ClockCircleOutlined />
                      创建时间
                    </dt>
                    <dd className="portal-agent-detail__meta-value">
                      {isCreateMode || !agent ? '创建后显示' : formatAgentDate(agent.create_time)}
                    </dd>
                  </div>
                </dl>
              </aside>

              <main className="portal-agent-detail__main">
                <nav className="portal-agent-detail__tabs" aria-label="智能体配置">
                <button
                  type="button"
                  className={`portal-agent-detail__tab${activeTab === 'settings' ? ' is-active' : ''}`}
                  aria-selected={activeTab === 'settings'}
                  onClick={() => setActiveTab('settings')}
                >
                    <SettingOutlined />
                    基础设置
                  </button>
                <button
                  type="button"
                  className={`portal-agent-detail__tab${activeTab === 'prompt' ? ' is-active' : ''}`}
                  aria-selected={activeTab === 'prompt'}
                  onClick={() => setActiveTab('prompt')}
                >
                    <FileTextOutlined />
                    系统提示词
                  </button>
                <button
                  type="button"
                  className={`portal-agent-detail__tab${activeTab === 'model' ? ' is-active' : ''}`}
                  aria-selected={activeTab === 'model'}
                  onClick={() => setActiveTab('model')}
                >
                    <ApiOutlined />
                    模型
                  </button>
                <button
                  type="button"
                  className={`portal-agent-detail__tab${activeTab === 'skills' ? ' is-active' : ''}`}
                  aria-selected={activeTab === 'skills'}
                  onClick={() => setActiveTab('skills')}
                >
                    <ThunderboltOutlined />
                    关联技能
                    {agentSkills.length > 0 && (
                      <span className="portal-agent-detail__tab-count">{agentSkills.length}</span>
                    )}
                  </button>
                <button
                  type="button"
                  className={`portal-agent-detail__tab${activeTab === 'knowledge' ? ' is-active' : ''}`}
                  aria-selected={activeTab === 'knowledge'}
                  onClick={() => setActiveTab('knowledge')}
                >
                    <DatabaseOutlined />
                    关联知识库
                    {agentKnowledgeBases.length > 0 && (
                      <span className="portal-agent-detail__tab-count">{agentKnowledgeBases.length}</span>
                    )}
                  </button>
                </nav>

                <div className="portal-agent-detail__panel">
                  {activeTab === 'settings' && (
                    <div className="portal-agent-detail__basic-viewport">
                      <div className="portal-agent-detail__basic-form">
                        <label className="portal-agent-detail__basic-field">
                          <span className="portal-agent-detail__basic-label">
                            名称
                            <span className="portal-agent-detail__basic-required" aria-hidden>
                              *
                            </span>
                          </span>
                          <Input
                            value={nameDraft}
                            onChange={(e) => setNameDraft(e.target.value)}
                            readOnly={!canManage}
                            placeholder="例如：职场顾问小王"
                            maxLength={64}
                            status={canManage && basicDirty && !basicValid ? 'error' : undefined}
                          />
                          {canManage && basicDirty && !basicValid && (
                            <span className="portal-agent-detail__basic-error">名称不能为空</span>
                          )}
                        </label>
                        <label className="portal-agent-detail__basic-field">
                          <span className="portal-agent-detail__basic-label">描述</span>
                          <Input.TextArea
                            value={descriptionDraft}
                            onChange={(e) => setDescriptionDraft(e.target.value)}
                            readOnly={!canManage}
                            placeholder="一句话介绍角色定位，访客会先看到这段"
                            rows={5}
                            maxLength={500}
                            showCount
                          />
                        </label>
                      </div>
                    </div>
                  )}
                  {activeTab === 'prompt' && (
                    <div className="portal-agent-detail__prompt-wrap">
                      <div className="portal-agent-detail__prompt-viewport">
                        <Input.TextArea
                          className="portal-agent-detail__prompt-editor"
                          value={promptDraft}
                          onChange={(e) => setPromptDraft(e.target.value)}
                          readOnly={!canManage}
                          placeholder="输入系统提示词，定义智能体的角色、语气与行为边界"
                          spellCheck={false}
                        />
                      </div>
                      <div className="portal-agent-detail__prompt-stats" aria-live="polite">
                        共 {promptLineCount} 行 · {promptCharCount} 字符
                      </div>
                    </div>
                  )}
                  {activeTab === 'model' && (
                    <div className="portal-agent-detail__models-viewport">
                      {chatModels.length === 0 ? (
                        <div className="portal-agent-detail__empty-state">
                          <ApiOutlined />
                          <span>暂无可用对话模型</span>
                          <p className="portal-agent-detail__empty-hint">请先在模型管理中配置聊天模型</p>
                        </div>
                      ) : (
                        <ul className="portal-agent-detail__models-grid">
                          {chatModels.map((model) => {
                            const isSelected = modelDraft === model.id;
                            const desc = model.description?.trim() || '暂无描述';
                            return (
                              <li key={model.id} className="portal-agent-detail__models-grid-item">
                                <button
                                  type="button"
                                  className={`portal-agent-detail__model-card${
                                    isSelected ? ' is-selected' : ''
                                  }${canManage ? '' : ' is-readonly'}`}
                                  disabled={!canManage}
                                  onClick={() => setModelDraft(model.id)}
                                >
                                  <span className="portal-agent-detail__model-card-icon" aria-hidden>
                                    <ApiOutlined />
                                  </span>
                                  <div className="portal-agent-detail__model-card-head">
                                    <h3 className="portal-agent-detail__model-card-name">{model.name}</h3>
                                    {model.provider_name ? (
                                      <span className="portal-agent-detail__model-card-provider">
                                        {model.provider_name}
                                      </span>
                                    ) : null}
                                  </div>
                                  {model.model_type ? (
                                    <span className="portal-agent-detail__model-card-type">{model.model_type}</span>
                                  ) : null}
                                  <p
                                    className={`portal-agent-detail__model-card-desc${
                                      model.description?.trim() ? '' : ' is-empty'
                                    }`}
                                  >
                                    {desc}
                                  </p>
                                </button>
                              </li>
                            );
                          })}
                        </ul>
                      )}
                    </div>
                  )}
                  {activeTab === 'skills' && (
                    <div className="portal-agent-detail__skills-viewport">
                      {isCreateMode ? (
                        <div className="portal-agent-detail__empty-state">
                          <ThunderboltOutlined />
                          <span>创建智能体后可关联技能</span>
                          <p className="portal-agent-detail__empty-hint">
                            请先填写基础信息并点击右上角「创建智能体」
                          </p>
                        </div>
                      ) : !canManage && agentSkills.length === 0 ? (
                        <div className="portal-agent-detail__empty-state">
                          <ThunderboltOutlined />
                          <span>尚未关联任何技能</span>
                        </div>
                      ) : (
                        <ul className="portal-agent-detail__skills-grid">
                          {agentSkills.map((skill) => {
                            const desc = skill.description?.trim() || skill.skill_desc?.trim() || '';
                            return (
                              <li key={skill.id} className="portal-agent-detail__skills-grid-item">
                                <article className="portal-agent-detail__skill-card">
                                  {canManage && (
                                    <button
                                      type="button"
                                      className="portal-agent-detail__skill-card-remove"
                                      aria-label={`解除关联 ${skill.name}`}
                                      onClick={() => void handleRemoveSkill(skill.id)}
                                    >
                                      <CloseOutlined />
                                    </button>
                                  )}
                                  <div className="portal-agent-detail__skill-card-icon" aria-hidden>
                                    <ThunderboltOutlined />
                                  </div>
                                  <h3 className="portal-agent-detail__skill-card-name">{skill.name}</h3>
                                  <p
                                    className={`portal-agent-detail__skill-card-desc${
                                      desc ? '' : ' is-empty'
                                    }`}
                                  >
                                    {desc || '暂无描述'}
                                  </p>
                                </article>
                              </li>
                            );
                          })}
                          {canManage && (
                            <li className="portal-agent-detail__skills-grid-item">
                              <button
                                type="button"
                                className="portal-agent-detail__skill-card portal-agent-detail__skill-card--add"
                                disabled={availableSkills.length === 0}
                                onClick={openAddSkillModal}
                              >
                                <span className="portal-agent-detail__skill-card-add-icon" aria-hidden>
                                  <PlusOutlined />
                                </span>
                                <span className="portal-agent-detail__skill-card-add-title">关联新技能</span>
                                <span className="portal-agent-detail__skill-card-add-hint">
                                  {availableSkills.length > 0
                                    ? `${availableSkills.length} 个可关联`
                                    : '暂无可关联'}
                                </span>
                              </button>
                            </li>
                          )}
                        </ul>
                      )}
                    </div>
                  )}
                  {activeTab === 'knowledge' && (
                    <div className="portal-agent-detail__skills-viewport">
                      {isCreateMode ? (
                        <div className="portal-agent-detail__empty-state">
                          <DatabaseOutlined />
                          <span>创建智能体后可关联知识库</span>
                          <p className="portal-agent-detail__empty-hint">
                            请先填写基础信息并点击右上角「创建智能体」
                          </p>
                        </div>
                      ) : !canManage && agentKnowledgeBases.length === 0 ? (
                        <div className="portal-agent-detail__empty-state">
                          <DatabaseOutlined />
                          <span>尚未关联任何知识库</span>
                        </div>
                      ) : (
                        <>
                          <p className="portal-agent-detail__kb-hint">
                            最多关联 {MAX_AGENT_KNOWLEDGE_BASES} 个知识库，且须使用相同 Embedding 模型。关联后对话时可调用
                            search_knowledge 检索文档片段。
                          </p>
                          <ul className="portal-agent-detail__skills-grid">
                            {agentKnowledgeBases.map((kb) => {
                              const desc = kb.description?.trim() || '';
                              return (
                                <li key={kb.id} className="portal-agent-detail__skills-grid-item">
                                  <article className="portal-agent-detail__skill-card portal-agent-detail__skill-card--kb">
                                    {canManage && (
                                      <button
                                        type="button"
                                        className="portal-agent-detail__skill-card-remove"
                                        aria-label={`解除关联 ${kb.name}`}
                                        onClick={() => void handleRemoveKnowledgeBase(kb.id)}
                                      >
                                        <CloseOutlined />
                                      </button>
                                    )}
                                    <div className="portal-agent-detail__skill-card-icon" aria-hidden>
                                      <DatabaseOutlined />
                                    </div>
                                    <h3 className="portal-agent-detail__skill-card-name">{kb.name}</h3>
                                    <p
                                      className={`portal-agent-detail__skill-card-desc${
                                        desc ? '' : ' is-empty'
                                      }`}
                                    >
                                      {desc || '暂无描述'}
                                    </p>
                                  </article>
                                </li>
                              );
                            })}
                            {canManage && !kbAtLimit && (
                              <li className="portal-agent-detail__skills-grid-item">
                                <button
                                  type="button"
                                  className="portal-agent-detail__skill-card portal-agent-detail__skill-card--add"
                                  disabled={availableKnowledgeBases.length === 0}
                                  onClick={openAddKbModal}
                                >
                                  <span className="portal-agent-detail__skill-card-add-icon" aria-hidden>
                                    <PlusOutlined />
                                  </span>
                                  <span className="portal-agent-detail__skill-card-add-title">关联知识库</span>
                                  <span className="portal-agent-detail__skill-card-add-hint">
                                    {availableKnowledgeBases.length > 0
                                      ? `${availableKnowledgeBases.length} 个可关联`
                                      : linkedEmbeddingModelId
                                        ? '无相同 Embedding 的可选库'
                                        : '请先创建并完成文档索引的知识库'}
                                  </span>
                                </button>
                              </li>
                            )}
                          </ul>
                        </>
                      )}
                    </div>
                  )}
                </div>
              </main>
            </div>
          </>
        )}
      </Spin>

      <Modal
        title="关联新技能"
        open={addSkillModalOpen}
        onCancel={closeAddSkillModal}
        footer={null}
        width={520}
        destroyOnClose
        className="portal-agent-detail__add-skill-modal"
      >
        <Input
          allowClear
          placeholder="搜索技能名称或描述"
          value={addSkillSearch}
          onChange={(e) => setAddSkillSearch(e.target.value)}
          className="portal-agent-detail__add-skill-search"
        />
        <div className="portal-agent-detail__add-skill-list" role="list">
          {filteredAvailableSkills.length === 0 ? (
            <div className="portal-agent-detail__add-skill-empty">
              {availableSkills.length === 0 ? '所有技能均已关联' : '未找到匹配的技能'}
            </div>
          ) : (
            filteredAvailableSkills.map((skill) => {
              const desc = skill.description?.trim() || skill.skill_desc?.trim() || '暂无描述';
              const isAdding = addingSkillId === skill.id;
              return (
                <button
                  key={skill.id}
                  type="button"
                  role="listitem"
                  className="portal-agent-detail__add-skill-item"
                  disabled={isAdding || addingSkillId !== null}
                  onClick={() => void handleAddSkill(skill.id)}
                >
                  <span className="portal-agent-detail__add-skill-item-icon" aria-hidden>
                    <ThunderboltOutlined />
                  </span>
                  <span className="portal-agent-detail__add-skill-item-body">
                    <span className="portal-agent-detail__add-skill-item-name">{skill.name}</span>
                    <span className="portal-agent-detail__add-skill-item-desc">{desc}</span>
                  </span>
                  <span className="portal-agent-detail__add-skill-item-action">
                    {isAdding ? <Spin size="small" /> : <PlusOutlined />}
                  </span>
                </button>
              );
            })
          )}
        </div>
      </Modal>

      <Modal
        title="关联知识库"
        open={addKbModalOpen}
        onCancel={closeAddKbModal}
        footer={null}
        width={520}
        destroyOnClose
        className="portal-agent-detail__add-skill-modal"
      >
        <Input
          allowClear
          placeholder="搜索知识库名称或描述"
          value={addKbSearch}
          onChange={(e) => setAddKbSearch(e.target.value)}
          className="portal-agent-detail__add-skill-search"
        />
        <div className="portal-agent-detail__add-skill-list" role="list">
          {filteredAvailableKnowledgeBases.length === 0 ? (
            <div className="portal-agent-detail__add-skill-empty">
              {availableKnowledgeBases.length === 0
                ? kbAtLimit
                  ? `已达上限（${MAX_AGENT_KNOWLEDGE_BASES} 个）`
                  : linkedEmbeddingModelId
                    ? '无相同 Embedding 模型的可选知识库'
                    : '暂无可关联的知识库（须已配置 Embedding 并完成文档索引）'
                : '未找到匹配的知识库'}
            </div>
          ) : (
            filteredAvailableKnowledgeBases.map((kb) => {
              const desc = kb.description?.trim() || '暂无描述';
              const isAdding = addingKbId === kb.id;
              return (
                <button
                  key={kb.id}
                  type="button"
                  role="listitem"
                  className="portal-agent-detail__add-skill-item"
                  disabled={isAdding || addingKbId !== null}
                  onClick={() => void handleAddKnowledgeBase(kb.id)}
                >
                  <span className="portal-agent-detail__add-skill-item-icon" aria-hidden>
                    <DatabaseOutlined />
                  </span>
                  <span className="portal-agent-detail__add-skill-item-body">
                    <span className="portal-agent-detail__add-skill-item-name">{kb.name}</span>
                    <span className="portal-agent-detail__add-skill-item-desc">{desc}</span>
                  </span>
                  <span className="portal-agent-detail__add-skill-item-action">
                    {isAdding ? <Spin size="small" /> : <PlusOutlined />}
                  </span>
                </button>
              );
            })
          )}
        </div>
      </Modal>
    </div>
  );
}
