import React, { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  AlertCircle, Check, ChevronDown, Copy, Eye, EyeOff,
  Loader2, Plus, Route, Search, Server, Star, Trash2, Zap,
} from 'lucide-react';
import { settingsApi } from '../../../services/api';

const PROVIDER_PRESETS = [
  { id: 'modelscope', label: 'ModelScope', api_format: 'openai_compatible', base_url: 'https://api-inference.modelscope.cn/v1' },
  { id: 'deepseek', label: 'DeepSeek', api_format: 'openai_compatible', base_url: 'https://api.deepseek.com/v1' },
  { id: 'siliconflow', label: 'SiliconFlow', api_format: 'openai_compatible', base_url: 'https://api.siliconflow.cn/v1' },
  { id: 'dashscope', label: 'Qwen', api_format: 'openai_compatible', base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
  { id: 'moonshot', label: 'Kimi', api_format: 'openai_compatible', base_url: 'https://api.moonshot.cn/v1' },
  { id: 'openai', label: 'OpenAI', api_format: 'openai_compatible', base_url: 'https://api.openai.com/v1' },
  { id: 'anthropic', label: 'Anthropic', api_format: 'anthropic_messages', base_url: 'https://api.anthropic.com/v1' },
  { id: 'custom', label: 'Custom', api_format: 'openai_compatible', base_url: '' },
];

const TASKS = ['summary', 'transcript_normalize', 'briefing'];

const slug = (v, fb = 'item') => String(v || fb).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || fb;

const createProvider = (preset, index) => ({
  id: preset.id === 'custom' ? `custom-${index + 1}` : preset.id,
  name: preset.label,
  provider: preset.id,
  api_format: preset.api_format,
  base_url: preset.base_url,
  api_key: '',
  enabled: true,
});

const createModel = (providerId, modelName, displayName) => ({
  id: `${providerId}-${slug(modelName, 'model')}`,
  provider_id: providerId,
  name: displayName || modelName,
  model: modelName,
  enabled: true,
  supports_streaming: true,
});

const LlmConfigPanel = () => {
  const { t } = useTranslation();
  const [providers, setProviders] = useState([]);
  const [models, setModels] = useState([]);
  const [defaultModelId, setDefaultModelId] = useState('default');
  const [taskRoutes, setTaskRoutes] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(null);
  const [notice, setNotice] = useState(null);
  const [revealKey, setRevealKey] = useState(null);
  const [fetchingModels, setFetchingModels] = useState(null);
  const [fetchedModels, setFetchedModels] = useState({});
  const [showFetched, setShowFetched] = useState(null);
  const [selectedFetched, setSelectedFetched] = useState([]);
  const [manualModelInputs, setManualModelInputs] = useState({});
  const [collapsedProviders, setCollapsedProviders] = useState(() => new Set());
  const [aiEnabled, setAiEnabled] = useState(true);

  useEffect(() => { loadConfigs(); }, []);

  const providerById = useMemo(() => Object.fromEntries(providers.map(p => [p.id, p])), [providers]);
  const enabledModels = useMemo(
    () => models.filter(m => m.enabled !== false && providerById[m.provider_id]?.enabled !== false),
    [models, providerById],
  );

  const modelsOf = (providerId) => models.filter(m => m.provider_id === providerId);

  // ── Data operations ──

  const toggleAiEnabled = async () => {
    const next = !aiEnabled;
    setAiEnabled(next);
    try {
      const r = await settingsApi.setAiAnalysis(next);
      setAiEnabled(r?.enabled ?? next);
    } catch (err) {
      setAiEnabled(!next);
      setNotice({ success: false, message: `${t('settings.saveError')}: ${err.message || err}` });
    }
  };

  const loadConfigs = async () => {
    setLoading(true);
    try {
      const res = await settingsApi.getLlmConfigs();
      setProviders(res.providers || []);
      setModels(res.models || []);
      setDefaultModelId(res.default_model_id || res.models?.[0]?.id || 'default');
      setTaskRoutes(res.task_routes || {});
      settingsApi.getAiAnalysis().then(r => setAiEnabled(!!r.enabled)).catch(() => {});
      // 已配置 Key 的服务商默认折叠为摘要卡片
      setCollapsedProviders(new Set((res.providers || []).filter(p => p.api_key).map(p => p.id)));
    } catch (err) {
      setNotice({ success: false, message: `${t('settings.loadError')}: ${err.message || err}` });
    } finally {
      setLoading(false);
    }
  };

  const saveConfigs = async () => {
    setSaving(true);
    setNotice(null);
    try {
      await settingsApi.saveLlmConfigs({
        providers,
        models,
        default_model_id: defaultModelId,
        task_routes: Object.fromEntries(TASKS.map(task => [task, taskRoutes[task] || 'default'])),
      });
      setNotice({ success: true, message: t('settings.saved') });
      await loadConfigs();
    } catch (err) {
      setNotice({ success: false, message: `${t('settings.saveError')}: ${err.message || err}` });
    } finally {
      setSaving(false);
    }
  };

  const updateProvider = (id, field, value) => {
    setProviders(prev => prev.map(p => p.id === id ? { ...p, [field]: value } : p));
  };

  const updateModel = (id, field, value) => {
    setModels(prev => prev.map(m => m.id === id ? { ...m, [field]: value } : m));
  };

  const addProvider = (preset) => {
    if (providers.some(p => p.id === preset.id) && preset.id !== 'custom') return;
    const provider = createProvider(preset, providers.length);
    setProviders(prev => [...prev, provider]);
  };

  const deleteProvider = (providerId) => {
    const nextProviders = providers.filter(p => p.id !== providerId);
    const deletedModelIds = new Set(models.filter(m => m.provider_id === providerId).map(m => m.id));
    const nextModels = models.filter(m => m.provider_id !== providerId);
    setProviders(nextProviders);
    setModels(nextModels);
    setTaskRoutes(Object.fromEntries(TASKS.map(task => [
      task, deletedModelIds.has(taskRoutes[task]) ? 'default' : (taskRoutes[task] || 'default'),
    ])));
    if (deletedModelIds.has(defaultModelId)) setDefaultModelId(nextModels[0]?.id || 'default');
  };

  const addModelToProvider = (providerId, modelName) => {
    const model = createModel(providerId, modelName, modelName);
    if (models.some(m => m.id === model.id)) return;
    setModels(prev => [...prev, model]);
    if (!defaultModelId || defaultModelId === 'default') setDefaultModelId(model.id);
  };

  const deleteModel = (modelId) => {
    const nextModels = models.filter(m => m.id !== modelId);
    setModels(nextModels);
    setTaskRoutes(Object.fromEntries(TASKS.map(task => [
      task, taskRoutes[task] === modelId ? 'default' : (taskRoutes[task] || 'default'),
    ])));
    if (defaultModelId === modelId) setDefaultModelId(nextModels[0]?.id || 'default');
  };

  const testModel = async (modelId) => {
    const model = models.find(m => m.id === modelId);
    const provider = providerById[model?.provider_id];
    if (!model || !provider?.base_url || !model.model) {
      setNotice({ success: false, message: t('settings.testRequiredFields') });
      return;
    }
    setTesting(modelId);
    setNotice(null);
    try {
      const result = await settingsApi.testLlmConnection({
        model_id: model.id,
        provider_id: provider.id,
        base_url: provider.base_url,
        api_key: provider.api_key,
        api_format: provider.api_format,
        model: model.model,
      });
      setNotice(result.success
        ? { success: true, message: `${t('settings.testSuccess')}: ${result.response || result.model}`, detail: `${provider.name} · ${model.model}` }
        : { success: false, message: result.error || t('settings.testFailed'), detail: result.hint });
    } catch (err) {
      setNotice({ success: false, message: `${t('settings.testFailed')}: ${err.message || err}` });
    } finally {
      setTesting(null);
    }
  };

  const handleFetchModels = async (providerId) => {
    if (showFetched === providerId) { setShowFetched(null); return; }
    if (fetchedModels[providerId]) { setShowFetched(providerId); setSelectedFetched([]); return; }
    setFetchingModels(providerId);
    try {
      const res = await settingsApi.fetchProviderModels(providerId);
      if (res.error) {
        setNotice({ success: false, message: res.error });
      } else {
        setFetchedModels(prev => ({ ...prev, [providerId]: res.models || [] }));
        setShowFetched(providerId);
        setSelectedFetched([]);
      }
    } catch (err) {
      setNotice({ success: false, message: `${t('settings.ai.fetchError')}: ${err.message || err}` });
    } finally {
      setFetchingModels(null);
    }
  };

  const addSelectedFetched = (providerId) => {
    const existingIds = new Set(models.map(m => m.id));
    const additions = selectedFetched
      .filter(id => !existingIds.has(`${providerId}-${slug(id)}`))
      .map(id => createModel(providerId, id, id));
    if (additions.length === 0) { setShowFetched(null); return; }
    setModels(prev => [...prev, ...additions]);
    if (!defaultModelId || defaultModelId === 'default') setDefaultModelId(additions[0].id);
    setShowFetched(null);
    setSelectedFetched([]);
  };

  const addManualModel = (providerId) => {
    const text = (manualModelInputs[providerId] || '').trim();
    if (!text) return;
    text.split('\n').map(s => s.trim()).filter(Boolean).forEach(name => addModelToProvider(providerId, name));
    setManualModelInputs(prev => ({ ...prev, [providerId]: '' }));
  };

  const copyToClipboard = (text) => {
    navigator.clipboard?.writeText(text).catch(() => {});
  };

  // ── Render helpers ──

  if (loading) {
    return (
      <div className="flex h-full flex-col items-center justify-center">
        <Loader2 className="mb-4 h-8 w-8 animate-spin text-blue-400" />
        <p className="text-zinc-400">{t('common.loading')}</p>
      </div>
    );
  }

  const NoticeBanner = () => notice ? (
    <div className={`mx-8 mt-4 rounded-md border px-4 py-3 ${
      notice.success ? 'border-emerald-800/60 bg-emerald-950/30 text-emerald-300'
        : 'border-red-900/70 bg-red-950/30 text-red-300'
    }`}>
      <div className="flex gap-2">
        {notice.success ? <Check size={16} className="mt-0.5 shrink-0" /> : <AlertCircle size={16} className="mt-0.5 shrink-0" />}
        <div className="min-w-0">
          <p className="text-sm font-medium">{notice.message}</p>
          {notice.detail && <p className="mt-1 truncate text-xs opacity-75">{notice.detail}</p>}
        </div>
      </div>
    </div>
  ) : null;

  // ── Main render ──

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Header */}
      <div className="border-b border-zinc-800 px-8 py-4">
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-sm font-medium text-white">
              <Server size={16} className="text-blue-300" />
              {t('settings.ai.cardTitle')}
            </div>
            <p className="mt-1 text-sm text-zinc-500">{t('settings.ai.cardDesc')}</p>
          </div>
          <button
            onClick={saveConfigs}
            disabled={saving}
            className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-60"
          >
            {saving ? <Loader2 className="animate-spin" size={16} /> : <Check size={16} />}
            {t('settings.save')}
          </button>
        </div>
      </div>

      <NoticeBanner />

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto px-8 py-6 space-y-6">

        {/* Provider Cards */}
        {providers.map((provider) => {
          const providerModels = modelsOf(provider.id);
          const isRevealed = revealKey === provider.id;
          const isFetching = fetchingModels === provider.id;
          const isShowingFetched = showFetched === provider.id;
          const fetched = fetchedModels[provider.id] || [];
          const isCollapsed = collapsedProviders.has(provider.id);
          const defaultModel = providerModels.find(m => m.id === defaultModelId);

          const toggleCollapsed = () => setCollapsedProviders(prev => {
            const next = new Set(prev);
            if (next.has(provider.id)) next.delete(provider.id);
            else next.add(provider.id);
            return next;
          });

          return (
            <div key={provider.id} className="mx-auto max-w-4xl rounded-lg border border-zinc-800 bg-zinc-900/35 overflow-hidden">
              {/* Card header (点击折叠/展开，左色条=启用状态) */}
              <div className="flex items-center justify-between gap-3 border-b border-zinc-800/60 py-3 pr-5">
                <button onClick={toggleCollapsed} className="flex min-w-0 flex-1 items-center gap-3 pl-4 text-left">
                  <span className={`w-[3px] self-stretch shrink-0 ${provider.enabled !== false ? 'bg-green-500' : 'bg-zinc-600'}`} />
                  <span className="shrink-0 text-base font-semibold text-white">{provider.name || provider.id}</span>
                  {!isCollapsed && defaultModelId && providerModels.some(m => m.id === defaultModelId) && (
                    <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-blue-500/15 px-2 py-0.5 text-[11px] font-medium text-blue-300">
                      <Star size={11} /> {t('settings.ai.defaultModel')}
                    </span>
                  )}
                  {isCollapsed && (
                    <>
                      <span className={`inline-flex shrink-0 items-center gap-1.5 text-[11px] ${provider.enabled !== false ? 'text-green-500' : 'text-zinc-500'}`}>
                        {provider.enabled !== false ? '●' : '○'} {provider.enabled !== false ? t('settings.ai.statusEnabled') : t('settings.ai.statusDisabled')}
                      </span>
                      <span className="ml-auto flex min-w-0 items-center gap-2 truncate text-xs text-zinc-500">
                        <span className="shrink-0">{t('settings.ai.modelCount', { count: providerModels.length })}</span>
                        {defaultModel && (
                          <>
                            <span className="shrink-0">·</span>
                            <span className="truncate text-zinc-400">{defaultModel.name || defaultModel.model}</span>
                          </>
                        )}
                      </span>
                    </>
                  )}
                  <ChevronDown
                    size={15}
                    className={`${isCollapsed ? '' : 'ml-auto '}shrink-0 text-zinc-500 transition-transform ${isCollapsed ? '' : 'rotate-180'}`}
                  />
                </button>
                <div className="flex items-center gap-2">
                  <label className="inline-flex items-center gap-1.5 text-xs text-zinc-400 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={provider.enabled !== false}
                      onChange={(e) => updateProvider(provider.id, 'enabled', e.target.checked)}
                      className="h-3.5 w-3.5 rounded border-zinc-700 bg-zinc-950"
                    />
                    {t('settings.ai.enabledProvider')}
                  </label>
                  <button
                    onClick={() => deleteProvider(provider.id)}
                    className="rounded-md p-1.5 text-zinc-500 hover:bg-zinc-800 hover:text-red-300"
                    title={t('settings.delete')}
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>

              {!isCollapsed && (<>

              {/* Card body: connection info */}
              <div className="px-5 py-4 grid gap-3 lg:grid-cols-2">
                <div>
                  <label className="mb-1 block text-xs text-zinc-500">{t('settings.ai.apiFormat')}</label>
                  <div className="relative">
                    <select
                      value={provider.api_format || 'openai_compatible'}
                      onChange={(e) => updateProvider(provider.id, 'api_format', e.target.value)}
                      className="w-full appearance-none rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-white outline-none focus:border-blue-500"
                    >
                      <option value="openai_compatible">OpenAI Compatible</option>
                      <option value="anthropic_messages">Anthropic Messages</option>
                    </select>
                    <ChevronDown className="pointer-events-none absolute right-3 top-2.5 text-zinc-500" size={15} />
                  </div>
                </div>
                <div>
                  <label className="mb-1 block text-xs text-zinc-500">{t('settings.ai.configName')}</label>
                  <input
                    value={provider.name || ''}
                    onChange={(e) => updateProvider(provider.id, 'name', e.target.value)}
                    className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-white outline-none focus:border-blue-500"
                  />
                </div>
                <div className="lg:col-span-2">
                  <label className="mb-1 block text-xs text-zinc-500">Base URL</label>
                  <input
                    value={provider.base_url || ''}
                    onChange={(e) => updateProvider(provider.id, 'base_url', e.target.value)}
                    placeholder="https://api-inference.modelscope.cn/v1"
                    className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 font-mono text-sm text-white outline-none focus:border-blue-500"
                  />
                </div>
                <div className="lg:col-span-2">
                  <label className="mb-1 block text-xs text-zinc-500">API Key</label>
                  <div className="flex gap-2">
                    <div className="relative flex-1">
                      <input
                        type={isRevealed ? 'text' : 'text'}
                        value={provider.api_key || ''}
                        onChange={(e) => updateProvider(provider.id, 'api_key', e.target.value)}
                        placeholder="sk-..."
                        className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 pr-10 font-mono text-sm text-white outline-none focus:border-blue-500"
                        style={!isRevealed && provider.api_key ? { WebkitTextSecurity: 'disc' } : {}}
                      />
                      <button
                        type="button"
                        onClick={() => setRevealKey(isRevealed ? null : provider.id)}
                        className="absolute right-2 top-2 rounded p-1 text-zinc-500 hover:text-white"
                      >
                        {isRevealed ? <EyeOff size={15} /> : <Eye size={15} />}
                      </button>
                    </div>
                    {provider.api_key && (
                      <button
                        onClick={() => copyToClipboard(provider.api_key)}
                        className="rounded-md border border-zinc-700 px-3 text-zinc-400 hover:bg-zinc-800 hover:text-white"
                        title={t('settings.ai.copyKey')}
                      >
                        <Copy size={15} />
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {/* Models section */}
              <div className="border-t border-zinc-800/60 px-5 py-4">
                <div className="flex items-center justify-between gap-2 mb-3">
                  <span className="text-sm font-medium text-zinc-300">{t('settings.ai.modelsLabel')}</span>
                  <button
                    onClick={() => handleFetchModels(provider.id)}
                    disabled={isFetching}
                    className="inline-flex items-center gap-1.5 rounded-md border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300 hover:bg-zinc-800 disabled:opacity-50"
                  >
                    {isFetching ? <Loader2 className="animate-spin" size={13} /> : <Search size={13} />}
                    {isFetching ? t('settings.ai.fetching') : t('settings.ai.fetchModels')}
                  </button>
                </div>

                {/* Fetched models picker */}
                {isShowingFetched && (
                  <div className="mb-3 rounded-md border border-zinc-800 bg-zinc-950/60 p-3 max-h-60 overflow-y-auto">
                    {fetched.length === 0 ? (
                      <p className="text-xs text-zinc-500 py-2">{t('settings.ai.noModelsFound')}</p>
                    ) : (
                      <>
                        <div className="space-y-1">
                          {fetched.map((fm) => {
                            const alreadyAdded = models.some(m => m.provider_id === provider.id && m.model === fm.id);
                            const isSelected = selectedFetched.includes(fm.id);
                            return (
                              <label key={fm.id} className={`flex items-center gap-2 rounded px-2 py-1 text-xs ${
                                alreadyAdded ? 'text-zinc-600' : isSelected ? 'text-blue-300 bg-blue-500/10' : 'text-zinc-300 hover:bg-zinc-800'
                              } ${alreadyAdded ? 'cursor-not-allowed' : 'cursor-pointer'}`}>
                                <input
                                  type="checkbox"
                                  checked={isSelected || alreadyAdded}
                                  disabled={alreadyAdded}
                                  onChange={(e) => {
                                    if (alreadyAdded) return;
                                    setSelectedFetched(prev =>
                                      e.target.checked ? [...prev, fm.id] : prev.filter(id => id !== fm.id)
                                    );
                                  }}
                                  className="h-3.5 w-3.5 rounded"
                                />
                                <span className="font-mono truncate">{fm.id}</span>
                                {alreadyAdded && <span className="text-zinc-600 ml-auto">{t('settings.ai.added')}</span>}
                              </label>
                            );
                          })}
                        </div>
                        <div className="mt-2 flex justify-end gap-2 border-t border-zinc-800 pt-2">
                          <button onClick={() => setShowFetched(null)} className="rounded-md px-3 py-1.5 text-xs text-zinc-400 hover:bg-zinc-800">
                            {t('settings.ai.close')}
                          </button>
                          <button
                            onClick={() => addSelectedFetched(provider.id)}
                            disabled={selectedFetched.length === 0}
                            className="rounded-md bg-blue-600 px-3 py-1.5 text-xs text-white hover:bg-blue-500 disabled:opacity-50"
                          >
                            {t('settings.ai.addSelected')} ({selectedFetched.length})
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                )}

                {/* Model list */}
                {providerModels.length === 0 ? (
                  <p className="text-xs text-zinc-600 py-2">{t('settings.ai.noModels')}</p>
                ) : (
                  <div className="space-y-2">
                    {providerModels.map((model) => (
                      <div
                        key={model.id}
                        className="flex items-center gap-3 rounded-md border border-zinc-800 bg-zinc-950/50 px-3 py-2"
                      >
                        <button
                          onClick={() => setDefaultModelId(model.id)}
                          className={`shrink-0 rounded p-1 ${
                            defaultModelId === model.id ? 'text-blue-400' : 'text-zinc-600 hover:text-zinc-400'
                          }`}
                          title={defaultModelId === model.id ? t('settings.ai.defaultModel') : t('settings.ai.setDefault')}
                        >
                          <Star size={14} fill={defaultModelId === model.id ? 'currentColor' : 'none'} />
                        </button>
                        <div className="min-w-0 flex-1">
                          <input
                            value={model.name || ''}
                            onChange={(e) => updateModel(model.id, 'name', e.target.value)}
                            className="w-full bg-transparent text-sm text-white outline-none border-b border-transparent focus:border-zinc-700"
                          />
                          <p className="truncate font-mono text-[11px] text-zinc-500">{model.model}</p>
                        </div>
                        <button
                          onClick={() => testModel(model.id)}
                          disabled={testing === model.id}
                          className="shrink-0 rounded-md p-1.5 text-zinc-500 hover:bg-zinc-800 hover:text-white"
                          title={t('settings.test')}
                        >
                          {testing === model.id ? <Loader2 className="animate-spin" size={14} /> : <Zap size={14} />}
                        </button>
                        <button
                          onClick={() => deleteModel(model.id)}
                          className="shrink-0 rounded-md p-1.5 text-zinc-600 hover:bg-zinc-800 hover:text-red-300"
                          title={t('settings.delete')}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                {/* Manual add */}
                <div className="mt-3 flex gap-2">
                  <input
                    value={manualModelInputs[provider.id] || ''}
                    onChange={(e) => setManualModelInputs(prev => ({ ...prev, [provider.id]: e.target.value }))}
                    onKeyDown={(e) => { if (e.key === 'Enter') addManualModel(provider.id); }}
                    placeholder={t('settings.ai.addModelPlaceholder')}
                    className="flex-1 rounded-md border border-zinc-700 bg-zinc-950 px-3 py-1.5 font-mono text-xs text-white outline-none focus:border-blue-500"
                  />
                  <button
                    onClick={() => addManualModel(provider.id)}
                    className="rounded-md bg-zinc-800 px-3 py-1.5 text-xs text-zinc-300 hover:bg-zinc-700"
                  >
                    <Plus size={14} />
                  </button>
                </div>
              </div>

              </>)}
            </div>
          );
        })}

        {/* Add provider bar */}
        <div className="mx-auto max-w-4xl">
          <div className="mb-2 text-xs font-medium uppercase text-zinc-500">{t('settings.ai.addProvider')}</div>
          <div className="flex flex-wrap gap-2">
            {PROVIDER_PRESETS.map((preset) => (
              <button
                key={preset.id}
                onClick={() => addProvider(preset)}
                disabled={preset.id !== 'custom' && providers.some(p => p.id === preset.id)}
                className="rounded-md border border-zinc-800 bg-zinc-900/40 px-3 py-2 text-sm text-zinc-300 hover:border-zinc-700 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {preset.label}
              </button>
            ))}
          </div>
        </div>

        {/* AI analysis master switch */}
        <div className="mx-auto max-w-4xl flex items-center justify-between rounded-lg border border-zinc-800 bg-zinc-900/35 px-5 py-4">
          <div className="min-w-0 pr-4">
            <div className="text-sm font-semibold text-white">{t('settings.ai.aiSwitchTitle')}</div>
            <p className="mt-0.5 text-xs text-zinc-500">{t('settings.ai.aiSwitchDesc')}</p>
          </div>
          <button
            onClick={toggleAiEnabled}
            className={`relative h-6 w-11 shrink-0 rounded-full transition-colors ${aiEnabled ? 'bg-green-600' : 'bg-zinc-700'}`}
            title={aiEnabled ? t('settings.ai.statusEnabled') : t('settings.ai.statusDisabled')}
          >
            <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-all ${aiEnabled ? 'left-[22px]' : 'left-0.5'}`} />
          </button>
        </div>

        {/* Task routing */}
        <div className="mx-auto max-w-4xl border-t border-zinc-800/60 pt-6">
          <div className="mb-4 flex items-center gap-2">
            <Route size={16} className="text-blue-300" />
            <div>
              <h3 className="text-sm font-semibold text-white">{t('settings.ai.taskRouting')}</h3>
              <p className="text-xs text-zinc-500">{t('settings.ai.taskRoutingDesc')}</p>
            </div>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            {TASKS.map((task) => (
              <div key={task} className="rounded-md border border-zinc-800 bg-zinc-950/60 p-4">
                <div className="text-sm font-medium text-white">{t(`settings.ai.tasks.${task}.title`)}</div>
                <p className="mt-1 text-xs text-zinc-500">{t(`settings.ai.tasks.${task}.description`)}</p>
                <select
                  value={taskRoutes[task] || 'default'}
                  onChange={(e) => setTaskRoutes(prev => ({ ...prev, [task]: e.target.value }))}
                  className="mt-3 w-full rounded-md border border-zinc-700 bg-zinc-900 px-2 py-2 text-sm text-white outline-none focus:border-blue-500"
                >
                  <option value="default">{t('settings.ai.defaultModel')}</option>
                  {enabledModels.map((model) => (
                    <option key={model.id} value={model.id}>
                      {providerById[model.provider_id]?.name || model.provider_id} / {model.name || model.model}
                    </option>
                  ))}
                </select>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default LlmConfigPanel;
