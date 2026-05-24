// -*- coding: utf-8 -*-
import React, { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  AlertCircle,
  Check,
  ChevronDown,
  Eye,
  EyeOff,
  Key,
  Layers,
  Loader2,
  Plus,
  Route,
  Server,
  Trash2,
  Zap,
} from 'lucide-react';
import { settingsApi } from '../../../services/api';

const PROVIDER_PRESETS = [
  {
    id: 'modelscope',
    label: 'ModelScope',
    api_format: 'openai_compatible',
    base_url: 'https://api-inference.modelscope.cn/v1',
  },
  {
    id: 'deepseek',
    label: 'DeepSeek',
    api_format: 'openai_compatible',
    base_url: 'https://api.deepseek.com/v1',
  },
  {
    id: 'siliconflow',
    label: 'SiliconFlow',
    api_format: 'openai_compatible',
    base_url: 'https://api.siliconflow.cn/v1',
  },
  {
    id: 'dashscope',
    label: 'Qwen',
    api_format: 'openai_compatible',
    base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
  },
  {
    id: 'moonshot',
    label: 'Kimi',
    api_format: 'openai_compatible',
    base_url: 'https://api.moonshot.cn/v1',
  },
  {
    id: 'openai',
    label: 'OpenAI',
    api_format: 'openai_compatible',
    base_url: 'https://api.openai.com/v1',
  },
  {
    id: 'anthropic',
    label: 'Anthropic',
    api_format: 'anthropic_messages',
    base_url: 'https://api.anthropic.com/v1',
  },
  {
    id: 'custom',
    label: 'Custom',
    api_format: 'openai_compatible',
    base_url: '',
  },
];

const QUICK_MODELS = [
  { provider_id: 'modelscope', name: 'DeepSeek V4 Flash', model: 'deepseek-ai/DeepSeek-V4-Flash' },
  { provider_id: 'modelscope', name: 'Qwen3 235B A22B', model: 'Qwen/Qwen3-235B-A22B' },
  { provider_id: 'modelscope', name: 'Qwen3 32B', model: 'Qwen/Qwen3-32B' },
  { provider_id: 'modelscope', name: 'GLM 4.5', model: 'ZhipuAI/GLM-4.5' },
  { provider_id: 'deepseek', name: 'DeepSeek Chat', model: 'deepseek-chat' },
  { provider_id: 'openai', name: 'GPT-4o mini', model: 'gpt-4o-mini' },
  { provider_id: 'anthropic', name: 'Claude Sonnet', model: 'claude-3-5-sonnet-latest' },
];

const TASKS = ['summary', 'transcript_normalize', 'briefing'];

const slug = (value, fallback = 'item') => (
  String(value || fallback)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '') || fallback
);

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
  const [activeTab, setActiveTab] = useState('keys');
  const [providers, setProviders] = useState([]);
  const [models, setModels] = useState([]);
  const [defaultModelId, setDefaultModelId] = useState('default');
  const [taskRoutes, setTaskRoutes] = useState({});
  const [selectedProviderId, setSelectedProviderId] = useState('modelscope');
  const [selectedModelId, setSelectedModelId] = useState('');
  const [quickModelText, setQuickModelText] = useState('deepseek-ai/DeepSeek-V4-Flash\nQwen/Qwen3-235B-A22B\nQwen/Qwen3-32B');
  const [visibleKeys, setVisibleKeys] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(null);
  const [notice, setNotice] = useState(null);

  useEffect(() => { loadConfigs(); }, []);

  const providerById = useMemo(
    () => Object.fromEntries(providers.map(provider => [provider.id, provider])),
    [providers],
  );
  const enabledModels = useMemo(
    () => models.filter(model => model.enabled !== false && providerById[model.provider_id]?.enabled !== false),
    [models, providerById],
  );
  const selectedProvider = providers.find(provider => provider.id === selectedProviderId) || providers[0];

  const loadConfigs = async () => {
    setLoading(true);
    try {
      const response = await settingsApi.getLlmConfigs();
      const loadedProviders = response.providers || [];
      const loadedModels = response.models || [];
      setProviders(loadedProviders);
      setModels(loadedModels);
      setDefaultModelId(response.default_model_id || loadedModels[0]?.id || 'default');
      setTaskRoutes(response.task_routes || {});
      setSelectedProviderId(loadedProviders[0]?.id || 'modelscope');
      setSelectedModelId(loadedModels[0]?.id || '');
    } catch (err) {
      setNotice({ success: false, message: `${t('settings.loadError')}: ${err.message || err}` });
    } finally {
      setLoading(false);
    }
  };

  const updateProvider = (providerId, field, value) => {
    setProviders(providers.map(provider => (
      provider.id === providerId ? { ...provider, [field]: value } : provider
    )));
  };

  const updateModel = (modelId, field, value) => {
    setModels(models.map(model => (
      model.id === modelId ? { ...model, [field]: value } : model
    )));
  };

  const addProvider = (preset = PROVIDER_PRESETS[0]) => {
    if (providers.some(provider => provider.id === preset.id) && preset.id !== 'custom') {
      setSelectedProviderId(preset.id);
      return;
    }
    const provider = createProvider(preset, providers.length);
    setProviders([...providers, provider]);
    setSelectedProviderId(provider.id);
  };

  const deleteProvider = (providerId) => {
    if (providers.length <= 1) return;
    const nextProviders = providers.filter(provider => provider.id !== providerId);
    const deletedModelIds = new Set(models.filter(model => model.provider_id === providerId).map(model => model.id));
    const nextModels = models.filter(model => model.provider_id !== providerId);
    setProviders(nextProviders);
    setModels(nextModels);
    setTaskRoutes(Object.fromEntries(TASKS.map(task => [
      task,
      deletedModelIds.has(taskRoutes[task]) ? 'default' : (taskRoutes[task] || 'default'),
    ])));
    if (deletedModelIds.has(defaultModelId)) setDefaultModelId(nextModels[0]?.id || 'default');
    setSelectedProviderId(nextProviders[0]?.id || '');
  };

  const addQuickModel = (quickModel) => {
    if (!providerById[quickModel.provider_id]) {
      const preset = PROVIDER_PRESETS.find(item => item.id === quickModel.provider_id);
      if (preset) addProvider(preset);
    }
    const model = createModel(quickModel.provider_id, quickModel.model, quickModel.name);
    if (models.some(item => item.id === model.id)) {
      setSelectedModelId(model.id);
      return;
    }
    setModels([...models, model]);
    setSelectedModelId(model.id);
    if (!defaultModelId || defaultModelId === 'default') setDefaultModelId(model.id);
  };

  const addCustomModel = () => {
    const providerId = selectedProvider?.id || providers[0]?.id;
    if (!providerId) return;
    const model = createModel(providerId, `custom-model-${models.length + 1}`, `Custom Model ${models.length + 1}`);
    setModels([...models, model]);
    setSelectedModelId(model.id);
  };

  const addBatchModels = () => {
    const providerId = selectedProvider?.id || providers[0]?.id;
    if (!providerId) return;

    const existingIds = new Set(models.map(model => model.id));
    const seenIds = new Set(existingIds);
    const additions = quickModelText
      .split('\n')
      .map(item => item.trim())
      .filter(Boolean)
      .map(modelName => createModel(providerId, modelName, modelName))
      .filter((model) => {
        if (seenIds.has(model.id)) return false;
        seenIds.add(model.id);
        return true;
      });

    if (additions.length === 0) return;
    setModels([...models, ...additions]);
    setSelectedModelId(additions[0].id);
    if (!defaultModelId || defaultModelId === 'default') setDefaultModelId(additions[0].id);
  };

  const deleteModel = (modelId) => {
    if (models.length <= 1) return;
    const nextModels = models.filter(model => model.id !== modelId);
    setModels(nextModels);
    setTaskRoutes(Object.fromEntries(TASKS.map(task => [
      task,
      taskRoutes[task] === modelId ? 'default' : (taskRoutes[task] || 'default'),
    ])));
    if (defaultModelId === modelId) setDefaultModelId(nextModels[0]?.id || 'default');
    setSelectedModelId(nextModels[0]?.id || '');
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

  const testModel = async (modelId) => {
    const model = models.find(item => item.id === modelId);
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

  if (loading) {
    return (
      <div className="flex h-full flex-col items-center justify-center">
        <Loader2 className="mb-4 h-8 w-8 animate-spin text-blue-400" />
        <p className="text-zinc-400">{t('common.loading')}</p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="border-b border-zinc-800 px-8 py-4">
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-sm font-medium text-white">
              <Server size={16} className="text-blue-300" />
              {t('settings.ai.providerFirst')}
            </div>
            <p className="mt-1 text-sm text-zinc-500">{t('settings.ai.providerFirstDesc')}</p>
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
        <div className="mt-4 flex gap-1 rounded-lg bg-zinc-900 p-1 w-fit">
          {[
            ['keys', Key, t('settings.ai.tabs.keys')],
            ['models', Layers, t('settings.ai.tabs.models')],
            ['routes', Route, t('settings.ai.tabs.routes')],
          ].map(([id, Icon, label]) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm ${
                activeTab === id ? 'bg-zinc-800 text-white' : 'text-zinc-500 hover:text-zinc-300'
              }`}
            >
              <Icon size={15} />
              {label}
            </button>
          ))}
        </div>
      </div>

      {notice && (
        <div className={`mx-8 mt-4 rounded-md border px-4 py-3 ${
          notice.success
            ? 'border-emerald-800/60 bg-emerald-950/30 text-emerald-300'
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
      )}

      <div className="flex-1 overflow-y-auto px-8 py-6">
        {activeTab === 'keys' && (
          <div className="mx-auto grid max-w-6xl gap-6 xl:grid-cols-[280px_minmax(0,1fr)]">
            <aside className="space-y-4">
              <section>
                <div className="mb-2 text-xs font-medium uppercase text-zinc-500">{t('settings.ai.presets')}</div>
                <div className="grid gap-2">
                  {PROVIDER_PRESETS.map((preset) => (
                    <button
                      key={preset.id}
                      onClick={() => addProvider(preset)}
                      className={`rounded-md border px-3 py-3 text-left ${
                        selectedProvider?.provider === preset.id
                          ? 'border-blue-500/70 bg-blue-500/10'
                          : 'border-zinc-800 bg-zinc-900/40 hover:border-zinc-700'
                      }`}
                    >
                      <div className="text-sm font-medium text-white">{preset.label}</div>
                      <div className="mt-1 truncate font-mono text-[11px] text-zinc-500">{preset.base_url || t('settings.ai.customProvider')}</div>
                    </button>
                  ))}
                </div>
              </section>
              <section>
                <div className="mb-2 text-xs font-medium uppercase text-zinc-500">{t('settings.ai.configuredProviders')}</div>
                <div className="space-y-2">
                  {providers.map((provider) => (
                    <button
                      key={provider.id}
                      onClick={() => setSelectedProviderId(provider.id)}
                      className={`w-full rounded-md border px-3 py-3 text-left ${
                        selectedProviderId === provider.id
                          ? 'border-zinc-500 bg-zinc-800/80'
                          : 'border-zinc-800 bg-zinc-900/30 hover:border-zinc-700'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate text-sm font-medium text-white">{provider.name || provider.id}</span>
                        {provider.has_api_key && <span className="text-[11px] text-emerald-300">{t('settings.ai.savedKey')}</span>}
                      </div>
                      <div className="mt-1 truncate font-mono text-[11px] text-zinc-500">{provider.base_url}</div>
                    </button>
                  ))}
                </div>
              </section>
            </aside>

            {selectedProvider && (
              <section className="rounded-lg border border-zinc-800 bg-zinc-900/35 p-5">
                <div className="mb-5 flex items-start justify-between gap-4">
                  <div>
                    <h2 className="text-lg font-semibold text-white">{t('settings.ai.keyTitle')}</h2>
                    <p className="mt-1 text-sm text-zinc-500">{t('settings.ai.keyDesc')}</p>
                  </div>
                  <button
                    onClick={() => deleteProvider(selectedProvider.id)}
                    disabled={providers.length <= 1}
                    className="rounded-md p-2 text-zinc-500 hover:bg-zinc-800 hover:text-red-300 disabled:opacity-40"
                    title={t('settings.delete')}
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
                <div className="grid gap-4 lg:grid-cols-2">
                  <div>
                    <label className="mb-1 block text-xs text-zinc-500">{t('settings.ai.configName')}</label>
                    <input
                      value={selectedProvider.name || ''}
                      onChange={(e) => updateProvider(selectedProvider.id, 'name', e.target.value)}
                      className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-white outline-none focus:border-blue-500"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs text-zinc-500">{t('settings.ai.apiFormat')}</label>
                    <div className="relative">
                      <select
                        value={selectedProvider.api_format || 'openai_compatible'}
                        onChange={(e) => updateProvider(selectedProvider.id, 'api_format', e.target.value)}
                        className="w-full appearance-none rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-white outline-none focus:border-blue-500"
                      >
                        <option value="openai_compatible">OpenAI Compatible</option>
                        <option value="anthropic_messages">Anthropic Messages</option>
                      </select>
                      <ChevronDown className="pointer-events-none absolute right-3 top-2.5 text-zinc-500" size={15} />
                    </div>
                  </div>
                  <div className="lg:col-span-2">
                    <label className="mb-1 flex items-center gap-1 text-xs text-zinc-500">
                      <Server size={12} /> Base URL
                    </label>
                    <input
                      value={selectedProvider.base_url || ''}
                      onChange={(e) => updateProvider(selectedProvider.id, 'base_url', e.target.value)}
                      placeholder="https://api-inference.modelscope.cn/v1"
                      className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 font-mono text-sm text-white outline-none focus:border-blue-500"
                    />
                  </div>
                  <div className="lg:col-span-2">
                    <label className="mb-1 flex items-center gap-1 text-xs text-zinc-500">
                      <Key size={12} /> API Key
                      {selectedProvider.has_api_key && !selectedProvider.api_key && (
                        <span className="ml-1 text-emerald-300">{t('settings.ai.savedKey')}</span>
                      )}
                    </label>
                    <div className="relative">
                      <input
                        type={visibleKeys[selectedProvider.id] ? 'text' : 'password'}
                        value={selectedProvider.api_key || ''}
                        onChange={(e) => updateProvider(selectedProvider.id, 'api_key', e.target.value)}
                        placeholder={selectedProvider.has_api_key ? t('settings.ai.keepExistingKey') : 'sk-...'}
                        className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 pr-10 font-mono text-sm text-white outline-none focus:border-blue-500"
                      />
                      <button
                        type="button"
                        onClick={() => setVisibleKeys({ ...visibleKeys, [selectedProvider.id]: !visibleKeys[selectedProvider.id] })}
                        className="absolute right-2 top-2 rounded p-1 text-zinc-500 hover:text-white"
                      >
                        {visibleKeys[selectedProvider.id] ? <EyeOff size={15} /> : <Eye size={15} />}
                      </button>
                    </div>
                    <p className="mt-2 text-xs text-zinc-600">{t('settings.ai.keyStorageHint')}</p>
                  </div>
                  <label className="inline-flex items-center gap-2 text-sm text-zinc-300">
                    <input
                      type="checkbox"
                      checked={selectedProvider.enabled !== false}
                      onChange={(e) => updateProvider(selectedProvider.id, 'enabled', e.target.checked)}
                      className="h-4 w-4 rounded border-zinc-700 bg-zinc-950"
                    />
                    {t('settings.ai.enabledProvider')}
                  </label>
                </div>
              </section>
            )}
          </div>
        )}

        {activeTab === 'models' && (
          <div className="mx-auto grid max-w-6xl gap-6 xl:grid-cols-[320px_minmax(0,1fr)]">
            <aside className="space-y-4">
              <section>
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-xs font-medium uppercase text-zinc-500">{t('settings.ai.quickModels')}</span>
                  <button onClick={addCustomModel} className="rounded-md p-1 text-zinc-400 hover:bg-zinc-800 hover:text-white">
                    <Plus size={16} />
                  </button>
                </div>
                <div className="mb-3 rounded-md border border-zinc-800 bg-zinc-950/50 p-3">
                  <label className="mb-2 block text-xs text-zinc-500">{t('settings.ai.modelProvider')}</label>
                  <div className="relative mb-3">
                    <select
                      value={selectedProvider?.id || ''}
                      onChange={(e) => setSelectedProviderId(e.target.value)}
                      className="w-full appearance-none rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-xs text-white outline-none focus:border-blue-500"
                    >
                      {providers.map(provider => (
                        <option key={provider.id} value={provider.id}>{provider.name || provider.id}</option>
                      ))}
                    </select>
                    <ChevronDown className="pointer-events-none absolute right-3 top-2.5 text-zinc-500" size={14} />
                  </div>
                  <label className="mb-2 block text-xs text-zinc-500">{t('settings.ai.batchModels')}</label>
                  <textarea
                    value={quickModelText}
                    onChange={(e) => setQuickModelText(e.target.value)}
                    rows={4}
                    className="w-full resize-none rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 font-mono text-xs text-white outline-none focus:border-blue-500"
                    placeholder={t('settings.ai.batchModelsPlaceholder')}
                  />
                  <button
                    onClick={addBatchModels}
                    className="mt-2 inline-flex items-center gap-2 rounded-md bg-zinc-800 px-3 py-2 text-xs font-medium text-zinc-200 hover:bg-zinc-700"
                  >
                    <Plus size={14} />
                    {t('settings.ai.addBatchModels')}
                  </button>
                </div>
                <div className="grid gap-2">
                  {QUICK_MODELS.map((model) => (
                    <button
                      key={`${model.provider_id}-${model.model}`}
                      onClick={() => addQuickModel(model)}
                      className="rounded-md border border-zinc-800 bg-zinc-900/40 px-3 py-3 text-left hover:border-zinc-700"
                    >
                      <div className="text-sm font-medium text-white">{model.name}</div>
                      <div className="mt-1 truncate font-mono text-[11px] text-zinc-500">{model.provider_id} / {model.model}</div>
                    </button>
                  ))}
                </div>
              </section>
            </aside>

            <section className="rounded-lg border border-zinc-800 bg-zinc-900/35 p-5">
              <div className="mb-5">
                <h2 className="text-lg font-semibold text-white">{t('settings.ai.modelsTitle')}</h2>
                <p className="mt-1 text-sm text-zinc-500">{t('settings.ai.modelsDesc')}</p>
              </div>
              <div className="space-y-3">
                {models.map((model) => (
                  <div
                    key={model.id}
                    className={`rounded-md border p-4 ${
                      selectedModelId === model.id ? 'border-blue-500/60 bg-blue-500/10' : 'border-zinc-800 bg-zinc-950/50'
                    }`}
                    onClick={() => setSelectedModelId(model.id)}
                  >
                    <div className="grid gap-3 lg:grid-cols-[1fr_1.5fr_180px_auto]">
                      <input
                        value={model.name || ''}
                        onChange={(e) => updateModel(model.id, 'name', e.target.value)}
                        className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-white outline-none focus:border-blue-500"
                      />
                      <input
                        value={model.model || ''}
                        onChange={(e) => updateModel(model.id, 'model', e.target.value)}
                        className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 font-mono text-sm text-white outline-none focus:border-blue-500"
                      />
                      <select
                        value={model.provider_id}
                        onChange={(e) => updateModel(model.id, 'provider_id', e.target.value)}
                        className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-white outline-none focus:border-blue-500"
                      >
                        {providers.map(provider => (
                          <option key={provider.id} value={provider.id}>{provider.name || provider.id}</option>
                        ))}
                      </select>
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={(e) => { e.stopPropagation(); setDefaultModelId(model.id); }}
                          className={`rounded-md px-2 py-2 text-xs ${defaultModelId === model.id ? 'bg-blue-500/15 text-blue-300' : 'bg-zinc-800 text-zinc-400'}`}
                        >
                          {defaultModelId === model.id ? t('settings.ai.defaultModel') : t('settings.ai.setDefault')}
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); testModel(model.id); }}
                          disabled={testing === model.id}
                          className="rounded-md p-2 text-zinc-400 hover:bg-zinc-800 hover:text-white"
                        >
                          {testing === model.id ? <Loader2 className="animate-spin" size={15} /> : <Zap size={15} />}
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); deleteModel(model.id); }}
                          disabled={models.length <= 1}
                          className="rounded-md p-2 text-zinc-500 hover:bg-zinc-800 hover:text-red-300 disabled:opacity-40"
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-4">
                      <label className="inline-flex items-center gap-2 text-xs text-zinc-400">
                        <input type="checkbox" checked={model.enabled !== false} onChange={(e) => updateModel(model.id, 'enabled', e.target.checked)} />
                        {t('settings.ai.enabledModel')}
                      </label>
                      <label className="inline-flex items-center gap-2 text-xs text-zinc-400">
                        <input type="checkbox" checked={!!model.supports_streaming} onChange={(e) => updateModel(model.id, 'supports_streaming', e.target.checked)} />
                        {t('settings.ai.streaming')}
                      </label>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </div>
        )}

        {activeTab === 'routes' && (
          <section className="mx-auto max-w-6xl rounded-lg border border-zinc-800 bg-zinc-900/35 p-5">
            <div className="mb-5 flex items-center gap-2">
              <Route size={17} className="text-blue-300" />
              <div>
                <h2 className="text-lg font-semibold text-white">{t('settings.ai.taskRouting')}</h2>
                <p className="mt-1 text-sm text-zinc-500">{t('settings.ai.taskRoutingDesc')}</p>
              </div>
            </div>
            <div className="grid gap-3 md:grid-cols-3">
              {TASKS.map((task) => (
                <div key={task} className="rounded-md border border-zinc-800 bg-zinc-950/60 p-4">
                  <div className="text-sm font-medium text-white">{t(`settings.ai.tasks.${task}.title`)}</div>
                  <p className="mt-1 min-h-10 text-xs leading-5 text-zinc-500">{t(`settings.ai.tasks.${task}.description`)}</p>
                  <select
                    value={taskRoutes[task] || 'default'}
                    onChange={(e) => setTaskRoutes({ ...taskRoutes, [task]: e.target.value })}
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
          </section>
        )}
      </div>
    </div>
  );
};

export default LlmConfigPanel;
