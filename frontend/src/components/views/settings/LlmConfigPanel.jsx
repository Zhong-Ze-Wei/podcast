// -*- coding: utf-8 -*-
import React, { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  AlertCircle,
  Check,
  ChevronDown,
  Cpu,
  Eye,
  EyeOff,
  Key,
  Loader2,
  Plus,
  Route,
  Server,
  SlidersHorizontal,
  Trash2,
  Zap,
} from 'lucide-react';
import { settingsApi } from '../../../services/api';

const PROVIDER_PRESETS = [
  {
    id: 'modelscope',
    label: 'ModelScope',
    region: 'CN',
    api_format: 'openai_compatible',
    base_url: 'https://api-inference.modelscope.cn/v1',
    model: 'deepseek-ai/DeepSeek-V4-Flash',
    supports_streaming: true,
  },
  {
    id: 'deepseek',
    label: 'DeepSeek',
    region: 'CN',
    api_format: 'openai_compatible',
    base_url: 'https://api.deepseek.com/v1',
    model: 'deepseek-chat',
    supports_streaming: true,
  },
  {
    id: 'siliconflow',
    label: 'SiliconFlow',
    region: 'CN',
    api_format: 'openai_compatible',
    base_url: 'https://api.siliconflow.cn/v1',
    model: 'deepseek-ai/DeepSeek-V3',
    supports_streaming: true,
  },
  {
    id: 'dashscope',
    label: 'Qwen',
    region: 'CN',
    api_format: 'openai_compatible',
    base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    model: 'qwen-max',
    supports_streaming: true,
  },
  {
    id: 'moonshot',
    label: 'Kimi',
    region: 'CN',
    api_format: 'openai_compatible',
    base_url: 'https://api.moonshot.cn/v1',
    model: 'moonshot-v1-8k',
    supports_streaming: true,
  },
  {
    id: 'openai',
    label: 'OpenAI',
    region: 'Global',
    api_format: 'openai_compatible',
    base_url: 'https://api.openai.com/v1',
    model: 'gpt-4o-mini',
    supports_streaming: true,
  },
  {
    id: 'anthropic',
    label: 'Anthropic',
    region: 'Global',
    api_format: 'anthropic_messages',
    base_url: 'https://api.anthropic.com/v1',
    model: 'claude-3-5-sonnet-latest',
    supports_streaming: true,
  },
  {
    id: 'custom',
    label: 'Custom',
    region: 'Any',
    api_format: 'openai_compatible',
    base_url: '',
    model: '',
    supports_streaming: false,
  },
];

const TASKS = ['summary', 'transcript_normalize', 'briefing'];

const slug = (value, fallback = 'config') => (
  String(value || fallback)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '') || fallback
);

const createConfigFromPreset = (preset, index) => ({
  id: preset.id === 'custom' ? `custom-${index + 1}` : preset.id,
  name: preset.label,
  provider: preset.id,
  api_format: preset.api_format,
  base_url: preset.base_url,
  api_key: '',
  model: preset.model,
  max_tokens: 4096,
  temperature: 0.2,
  supports_streaming: preset.supports_streaming,
  enabled: true,
});

const LlmConfigPanel = () => {
  const { t } = useTranslation();
  const [configs, setConfigs] = useState([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const [taskRoutes, setTaskRoutes] = useState({});
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [visibleKeys, setVisibleKeys] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(null);
  const [notice, setNotice] = useState(null);

  useEffect(() => { loadConfigs(); }, []);

  const selectedConfig = configs[selectedIndex] || configs[0];
  const availableConfigs = useMemo(
    () => configs.filter(config => config.enabled !== false && config.id && config.base_url && config.model),
    [configs],
  );

  const loadConfigs = async () => {
    setLoading(true);
    try {
      const response = await settingsApi.getLlmConfigs();
      const loadedConfigs = response.configs || [];
      setConfigs(loadedConfigs);
      setActiveIndex(response.active_index || 0);
      setSelectedIndex(Math.min(response.active_index || 0, Math.max(loadedConfigs.length - 1, 0)));
      setTaskRoutes(response.task_routes || {});
    } catch (err) {
      setNotice({ success: false, message: `${t('settings.loadError')}: ${err.message || err}` });
    } finally {
      setLoading(false);
    }
  };

  const updateConfig = (index, field, value) => {
    const next = [...configs];
    next[index] = { ...next[index], [field]: value };
    if (field === 'provider' && !next[index].id) {
      next[index].id = slug(value, `config-${index + 1}`);
    }
    setConfigs(next);
  };

  const applyPreset = (preset) => {
    if (configs.length === 0) {
      setConfigs([createConfigFromPreset(preset, 0)]);
      setSelectedIndex(0);
      setActiveIndex(0);
      return;
    }

    const index = selectedIndex;
    const next = [...configs];
    const current = next[index] || {};
    next[index] = {
      ...current,
      id: current.id || (preset.id === 'custom' ? `custom-${index + 1}` : preset.id),
      name: current.name && !current.name.startsWith('Config ') ? current.name : preset.label,
      provider: preset.id,
      api_format: preset.api_format,
      base_url: preset.base_url,
      model: preset.model,
      supports_streaming: preset.supports_streaming,
      enabled: current.enabled !== false,
    };
    setConfigs(next);
  };

  const addConfig = (preset = PROVIDER_PRESETS[0]) => {
    if (configs.length >= 5) return;
    const next = [...configs, createConfigFromPreset(preset, configs.length)];
    setConfigs(next);
    setSelectedIndex(next.length - 1);
  };

  const deleteConfig = (index) => {
    if (configs.length <= 1) return;
    const deletedId = configs[index]?.id;
    const next = configs.filter((_, i) => i !== index);
    const nextRoutes = Object.fromEntries(
      TASKS.map(task => [task, taskRoutes[task] === deletedId ? 'default' : (taskRoutes[task] || 'default')]),
    );
    setConfigs(next);
    setTaskRoutes(nextRoutes);
    setSelectedIndex(Math.max(0, Math.min(index, next.length - 1)));
    if (activeIndex >= next.length) setActiveIndex(Math.max(0, next.length - 1));
  };

  const saveConfigs = async () => {
    setSaving(true);
    setNotice(null);
    try {
      await settingsApi.saveLlmConfigs({
        configs,
        active_index: activeIndex,
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

  const testConnection = async (index) => {
    const config = configs[index];
    if (!config?.base_url || !config?.model) {
      setNotice({ success: false, message: t('settings.testRequiredFields') });
      return;
    }

    setTesting(index);
    setNotice(null);
    try {
      const result = await settingsApi.testLlmConnection(config);
      if (result.success) {
        setNotice({
          success: true,
          message: `${t('settings.testSuccess')}: ${result.response || result.model}`,
          detail: `${result.base_url} · ${result.model}`,
        });
      } else {
        setNotice({
          success: false,
          message: result.error || t('settings.testFailed'),
          detail: result.hint,
        });
      }
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
        <div className="mx-auto grid max-w-6xl gap-6 xl:grid-cols-[280px_minmax(0,1fr)]">
          <aside className="space-y-4">
            <section>
              <div className="mb-2 text-xs font-medium uppercase text-zinc-500">{t('settings.ai.presets')}</div>
              <div className="grid gap-2">
                {PROVIDER_PRESETS.map((preset) => (
                  <button
                    key={preset.id}
                    onClick={() => applyPreset(preset)}
                    className={`rounded-md border px-3 py-3 text-left transition-colors ${
                      selectedConfig?.provider === preset.id
                        ? 'border-blue-500/70 bg-blue-500/10'
                        : 'border-zinc-800 bg-zinc-900/40 hover:border-zinc-700'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-medium text-white">{preset.label}</span>
                      <span className="text-[11px] text-zinc-500">{preset.region}</span>
                    </div>
                    <div className="mt-1 truncate font-mono text-[11px] text-zinc-500">{preset.model || t('settings.ai.customModel')}</div>
                  </button>
                ))}
              </div>
            </section>

            <section>
              <div className="mb-2 flex items-center justify-between">
                <span className="text-xs font-medium uppercase text-zinc-500">{t('settings.ai.configuredProviders')}</span>
                <button
                  onClick={() => addConfig()}
                  disabled={configs.length >= 5}
                  className="rounded-md p-1 text-zinc-400 hover:bg-zinc-800 hover:text-white disabled:opacity-40"
                  title={t('settings.addConfig')}
                >
                  <Plus size={16} />
                </button>
              </div>
              <div className="space-y-2">
                {configs.map((config, index) => (
                  <button
                    key={`${config.id || index}-${index}`}
                    onClick={() => setSelectedIndex(index)}
                    className={`w-full rounded-md border px-3 py-3 text-left ${
                      selectedIndex === index
                        ? 'border-zinc-500 bg-zinc-800/80'
                        : 'border-zinc-800 bg-zinc-900/30 hover:border-zinc-700'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-sm font-medium text-white">{config.name || config.id}</span>
                      {activeIndex === index && <span className="rounded bg-blue-500/15 px-1.5 py-0.5 text-[11px] text-blue-300">{t('settings.active')}</span>}
                    </div>
                    <div className="mt-1 truncate font-mono text-[11px] text-zinc-500">{config.model}</div>
                  </button>
                ))}
              </div>
            </section>
          </aside>

          <main className="space-y-5">
            {selectedConfig && (
              <section className="rounded-lg border border-zinc-800 bg-zinc-900/35 p-5">
                <div className="mb-5 flex items-start justify-between gap-4">
                  <div>
                    <h2 className="text-lg font-semibold text-white">{t('settings.ai.endpointTitle')}</h2>
                    <p className="mt-1 text-sm text-zinc-500">{t('settings.ai.endpointDesc')}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setActiveIndex(selectedIndex)}
                      className={`rounded-md px-3 py-2 text-sm ${
                        activeIndex === selectedIndex
                          ? 'bg-blue-500/15 text-blue-300'
                          : 'bg-zinc-800 text-zinc-300 hover:text-white'
                      }`}
                    >
                      {activeIndex === selectedIndex ? t('settings.active') : t('settings.ai.setDefault')}
                    </button>
                    <button
                      onClick={() => testConnection(selectedIndex)}
                      disabled={testing === selectedIndex}
                      className="inline-flex items-center gap-2 rounded-md bg-zinc-800 px-3 py-2 text-sm text-zinc-300 hover:text-white disabled:opacity-60"
                    >
                      {testing === selectedIndex ? <Loader2 className="animate-spin" size={15} /> : <Zap size={15} />}
                      {t('settings.test')}
                    </button>
                    <button
                      onClick={() => deleteConfig(selectedIndex)}
                      disabled={configs.length <= 1}
                      className="rounded-md p-2 text-zinc-500 hover:bg-zinc-800 hover:text-red-300 disabled:opacity-40"
                      title={t('settings.delete')}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>

                <div className="grid gap-4 lg:grid-cols-2">
                  <div>
                    <label className="mb-1 block text-xs text-zinc-500">{t('settings.ai.configName')}</label>
                    <input
                      value={selectedConfig.name || ''}
                      onChange={(e) => updateConfig(selectedIndex, 'name', e.target.value)}
                      className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-white outline-none focus:border-blue-500"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs text-zinc-500">{t('settings.ai.apiFormat')}</label>
                    <div className="relative">
                      <select
                        value={selectedConfig.api_format || 'openai_compatible'}
                        onChange={(e) => updateConfig(selectedIndex, 'api_format', e.target.value)}
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
                      value={selectedConfig.base_url || ''}
                      onChange={(e) => updateConfig(selectedIndex, 'base_url', e.target.value)}
                      placeholder="https://api-inference.modelscope.cn/v1"
                      className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 font-mono text-sm text-white outline-none focus:border-blue-500"
                    />
                  </div>
                  <div>
                    <label className="mb-1 flex items-center gap-1 text-xs text-zinc-500">
                      <Cpu size={12} /> Model
                    </label>
                    <input
                      value={selectedConfig.model || ''}
                      onChange={(e) => updateConfig(selectedIndex, 'model', e.target.value)}
                      placeholder="deepseek-ai/DeepSeek-V4-Flash"
                      className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 font-mono text-sm text-white outline-none focus:border-blue-500"
                    />
                  </div>
                  <div>
                    <label className="mb-1 flex items-center gap-1 text-xs text-zinc-500">
                      <Key size={12} /> API Key
                      {selectedConfig.has_api_key && !selectedConfig.api_key && (
                        <span className="ml-1 text-emerald-300">{t('settings.ai.savedKey')}</span>
                      )}
                    </label>
                    <div className="relative">
                      <input
                        type={visibleKeys[selectedIndex] ? 'text' : 'password'}
                        value={selectedConfig.api_key || ''}
                        onChange={(e) => updateConfig(selectedIndex, 'api_key', e.target.value)}
                        placeholder={selectedConfig.has_api_key ? t('settings.ai.keepExistingKey') : 'sk-...'}
                        className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 pr-10 font-mono text-sm text-white outline-none focus:border-blue-500"
                      />
                      <button
                        type="button"
                        onClick={() => setVisibleKeys({ ...visibleKeys, [selectedIndex]: !visibleKeys[selectedIndex] })}
                        className="absolute right-2 top-2 rounded p-1 text-zinc-500 hover:text-white"
                      >
                        {visibleKeys[selectedIndex] ? <EyeOff size={15} /> : <Eye size={15} />}
                      </button>
                    </div>
                  </div>
                </div>

                <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-zinc-800 pt-4">
                  <label className="inline-flex items-center gap-2 text-sm text-zinc-300">
                    <input
                      type="checkbox"
                      checked={selectedConfig.enabled !== false}
                      onChange={(e) => updateConfig(selectedIndex, 'enabled', e.target.checked)}
                      className="h-4 w-4 rounded border-zinc-700 bg-zinc-950"
                    />
                    {t('settings.ai.enabled')}
                  </label>
                  <label className="inline-flex items-center gap-2 text-sm text-zinc-300">
                    <input
                      type="checkbox"
                      checked={!!selectedConfig.supports_streaming}
                      onChange={(e) => updateConfig(selectedIndex, 'supports_streaming', e.target.checked)}
                      className="h-4 w-4 rounded border-zinc-700 bg-zinc-950"
                    />
                    {t('settings.ai.streaming')}
                  </label>
                  <button
                    type="button"
                    onClick={() => setShowAdvanced(!showAdvanced)}
                    className="inline-flex items-center gap-2 rounded-md bg-zinc-800 px-3 py-1.5 text-sm text-zinc-300 hover:text-white"
                  >
                    <SlidersHorizontal size={14} />
                    {t('settings.ai.advanced')}
                  </button>
                </div>

                {showAdvanced && (
                  <div className="mt-4 grid gap-4 border-t border-zinc-800 pt-4 sm:grid-cols-2">
                    <div>
                      <label className="mb-1 block text-xs text-zinc-500">{t('settings.ai.maxTokens')}</label>
                      <input
                        type="number"
                        value={selectedConfig.max_tokens || 4096}
                        onChange={(e) => updateConfig(selectedIndex, 'max_tokens', parseInt(e.target.value, 10) || 4096)}
                        className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-white outline-none focus:border-blue-500"
                      />
                      <p className="mt-1 text-xs text-zinc-600">{t('settings.ai.maxTokensHint')}</p>
                    </div>
                    <div>
                      <label className="mb-1 block text-xs text-zinc-500">Temperature</label>
                      <input
                        type="number"
                        min="0"
                        max="2"
                        step="0.1"
                        value={selectedConfig.temperature ?? 0.2}
                        onChange={(e) => updateConfig(selectedIndex, 'temperature', parseFloat(e.target.value) || 0.2)}
                        className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-white outline-none focus:border-blue-500"
                      />
                    </div>
                  </div>
                )}
              </section>
            )}

            <section className="rounded-lg border border-zinc-800 bg-zinc-900/35 p-5">
              <div className="mb-4 flex items-center gap-2">
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
                      {availableConfigs.map((config) => (
                        <option key={config.id} value={config.id}>
                          {config.name || config.id} / {config.model}
                        </option>
                      ))}
                    </select>
                  </div>
                ))}
              </div>
            </section>
          </main>
        </div>
      </div>
    </div>
  );
};

export default LlmConfigPanel;
