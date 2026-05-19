// -*- coding: utf-8 -*-
import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Plus, Trash2, Check, AlertCircle,
  Loader2, Server, Key, Cpu, Thermometer, ChevronDown
} from 'lucide-react';
import { settingsApi } from '../../../services/api';

const PROVIDER_PRESETS = [
  { label: 'OpenAI', base_url: 'https://api.openai.com/v1', model: 'gpt-4o-mini' },
  { label: 'DeepSeek', base_url: 'https://api.deepseek.com/v1', model: 'deepseek-chat' },
  { label: 'SiliconFlow（硅基流动）', base_url: 'https://api.siliconflow.cn/v1', model: 'deepseek-ai/DeepSeek-V3' },
  { label: 'Qwen（阿里云百炼）', base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', model: 'qwen-max' },
  { label: 'Kimi（月之暗面）', base_url: 'https://api.moonshot.cn/v1', model: 'moonshot-v1-8k' },
  { label: 'Groq（高速推理）', base_url: 'https://api.groq.com/openai/v1', model: 'llama-3.3-70b-versatile' },
  { label: 'OpenRouter（聚合路由）', base_url: 'https://openrouter.ai/api/v1', model: 'anthropic/claude-3.5-sonnet' },
  { label: 'Together AI', base_url: 'https://api.together.xyz/v1', model: 'meta-llama/Llama-3-70b-chat-hf' },
  { label: 'Ollama（本地）', base_url: 'http://localhost:11434/v1', model: 'llama3' },
];

const LlmConfigPanel = () => {
  const { t } = useTranslation();
  const [configs, setConfigs] = useState([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(null);
  const [testResult, setTestResult] = useState(null); // { success, message, hint, base_url, model }

  useEffect(() => { loadConfigs(); }, []);

  const loadConfigs = async () => {
    setLoading(true);
    try {
      const response = await settingsApi.getLlmConfigs();
      setConfigs(response.configs || []);
      setActiveIndex(response.active_index || 0);
    } catch (err) {
      console.error('Failed to load LLM configs:', err);
    } finally {
      setLoading(false);
    }
  };

  const saveConfigs = async () => {
    setSaving(true);
    setTestResult(null);
    try {
      await settingsApi.saveLlmConfigs({ configs, active_index: activeIndex });
      setTestResult({ success: true, message: '已保存' });
    } catch (err) {
      setTestResult({ success: false, message: '保存失败: ' + (err.message || err) });
    } finally {
      setSaving(false);
    }
  };

  const addConfig = () => {
    if (configs.length >= 5) return;
    setConfigs([...configs, {
      name: `Config ${configs.length + 1}`,
      base_url: '', api_key: '', model: '',
      max_tokens: 4096, temperature: 0.2
    }]);
  };

  const deleteConfig = (index) => {
    if (configs.length <= 1) return;
    const newConfigs = configs.filter((_, i) => i !== index);
    setConfigs(newConfigs);
    if (activeIndex >= newConfigs.length) setActiveIndex(Math.max(0, newConfigs.length - 1));
    else if (activeIndex > index) setActiveIndex(activeIndex - 1);
  };

  const updateConfig = (index, field, value) => {
    const newConfigs = [...configs];
    newConfigs[index] = { ...newConfigs[index], [field]: value };
    setConfigs(newConfigs);
  };

  const testConnection = async (index) => {
    const config = configs[index];
    if (!config.base_url || !config.model) {
      setTestResult({ success: false, message: '请先填写 Base URL 和 Model', hint: '这两个是必填项。' });
      return;
    }

    setTesting(index);
    setTestResult(null);
    try {
      const result = await settingsApi.testLlmConnection(config);
      if (result.success) {
        setTestResult({
          success: true,
          message: `连接成功! 模型回复: "${result.response}"`,
          base_url: result.base_url,
          model: result.model,
        });
      } else {
        setTestResult({
          success: false,
          message: result.error || '连接失败',
          hint: result.hint || '',
          base_url: result.base_url,
          model: result.model,
        });
      }
    } catch (err) {
      setTestResult({ success: false, message: '网络请求失败: ' + (err.message || err) });
    } finally {
      setTesting(null);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col h-full items-center justify-center">
        <Loader2 className="animate-spin w-8 h-8 text-indigo-500 mb-4" />
        <p className="text-zinc-400">{t('common.loading')}</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Toolbar */}
      <div className="px-8 py-4 border-b border-zinc-800 flex items-center justify-between">
        <p className="text-zinc-500 text-sm">配置 LLM API 端点（OpenAI 兼容格式）</p>
        <button
          onClick={saveConfigs}
          disabled={saving}
          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-zinc-700 text-white rounded-lg font-medium transition-colors flex items-center gap-2"
        >
          {saving ? <Loader2 className="animate-spin" size={16} /> : <Check size={16} />}
          保存
        </button>
      </div>

      {/* Test Result Banner */}
      {testResult && (
        <div className={`mx-8 mt-4 px-4 py-3 rounded-lg border ${
          testResult.success
            ? 'bg-green-900/20 border-green-800/50 text-green-400'
            : 'bg-red-900/20 border-red-800/50 text-red-400'
        }`}>
          <div className="flex items-start gap-2">
            {testResult.success ? <Check size={16} className="mt-0.5 shrink-0" /> : <AlertCircle size={16} className="mt-0.5 shrink-0" />}
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium">{testResult.message}</p>
              {testResult.hint && (
                <p className="text-xs mt-1 opacity-80">{testResult.hint}</p>
              )}
              {testResult.base_url && (
                <p className="text-xs mt-1 opacity-60 font-mono">
                  URL: {testResult.base_url} · Model: {testResult.model}
                </p>
              )}
            </div>
            <button onClick={() => setTestResult(null)} className="text-xs opacity-60 hover:opacity-100 shrink-0">关闭</button>
          </div>
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-8">
        <div className="max-w-4xl mx-auto space-y-4">
          {configs.map((config, index) => (
            <div
              key={index}
              className={`border rounded-xl p-6 transition-colors ${
                activeIndex === index
                  ? 'border-indigo-500 bg-indigo-900/10'
                  : 'border-zinc-800 bg-zinc-900/30 hover:border-zinc-700'
              }`}
            >
              {/* Config Header */}
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => setActiveIndex(index)}
                    className={`w-5 h-5 rounded-full border-2 flex items-center justify-center transition-colors ${
                      activeIndex === index
                        ? 'border-indigo-500 bg-indigo-500'
                        : 'border-zinc-600 hover:border-zinc-400'
                    }`}
                  >
                    {activeIndex === index && <Check size={12} className="text-white" />}
                  </button>
                  <input
                    type="text"
                    value={config.name || ''}
                    onChange={(e) => updateConfig(index, 'name', e.target.value)}
                    className="bg-transparent text-lg font-semibold text-white border-none outline-none focus:ring-0"
                    placeholder="配置名称"
                  />
                  {activeIndex === index && (
                    <span className="text-xs px-2 py-0.5 bg-indigo-500/20 text-indigo-400 rounded-full">
                      当前激活
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => testConnection(index)}
                    disabled={testing === index}
                    className="px-3 py-1.5 text-sm bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg transition-colors flex items-center gap-2"
                  >
                    {testing === index ? <Loader2 className="animate-spin" size={14} /> : <Server size={14} />}
                    测试连接
                  </button>
                  <button
                    onClick={() => deleteConfig(index)}
                    className="p-1.5 text-zinc-500 hover:text-red-400 transition-colors"
                    title="删除"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>

              {/* Provider Preset */}
              <div className="mb-4">
                <label className="text-xs text-zinc-500 mb-1 block">
                  Provider 预设（点选自动填写 Base URL + Model）
                </label>
                <div className="relative inline-block w-full max-w-xs">
                  <select
                    onChange={(e) => {
                      const preset = PROVIDER_PRESETS.find(p => p.base_url === e.target.value);
                      if (preset) {
                        updateConfig(index, 'base_url', preset.base_url);
                        updateConfig(index, 'model', preset.model);
                        if (!config.name || config.name.startsWith('Config ')) updateConfig(index, 'name', preset.label);
                      }
                    }}
                    value=""
                    className="w-full pl-3 pr-8 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-zinc-300 text-sm focus:outline-none focus:border-indigo-500 appearance-none cursor-pointer"
                  >
                    <option value="" disabled>选择 Provider...</option>
                    {PROVIDER_PRESETS.map(p => (
                      <option key={p.base_url} value={p.base_url}>{p.label}</option>
                    ))}
                  </select>
                  <ChevronDown size={14} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-500 pointer-events-none" />
                </div>
              </div>

              {/* Fields */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs text-zinc-500 flex items-center gap-1 mb-1">
                    <Server size={12} /> Base URL
                  </label>
                  <input
                    type="text"
                    value={config.base_url || ''}
                    onChange={(e) => updateConfig(index, 'base_url', e.target.value)}
                    placeholder="https://api.example.com/v1"
                    className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white text-sm font-mono placeholder-zinc-500 focus:outline-none focus:border-indigo-500"
                  />
                  <p className="text-xs text-zinc-600 mt-1">通常以 /v1 结尾，如 https://api.openai.com/v1</p>
                </div>
                <div>
                  <label className="text-xs text-zinc-500 flex items-center gap-1 mb-1">
                    <Cpu size={12} /> Model
                  </label>
                  <input
                    type="text"
                    value={config.model || ''}
                    onChange={(e) => updateConfig(index, 'model', e.target.value)}
                    placeholder="gpt-4o-mini, deepseek-chat, etc."
                    className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white text-sm font-mono placeholder-zinc-500 focus:outline-none focus:border-indigo-500"
                  />
                </div>
                <div>
                  <label className="text-xs text-zinc-500 flex items-center gap-1 mb-1">
                    <Key size={12} /> API Key
                    {config.has_api_key && !config.api_key && (
                      <span className="text-green-400 ml-2">(已保存)</span>
                    )}
                  </label>
                  <input
                    type="password"
                    value={config.api_key || ''}
                    onChange={(e) => updateConfig(index, 'api_key', e.target.value)}
                    placeholder={config.has_api_key ? "(留空保持当前值)" : "sk-... (Ollama 本地可留空)"}
                    className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white text-sm font-mono placeholder-zinc-500 focus:outline-none focus:border-indigo-500"
                  />
                  <p className="text-xs text-zinc-600 mt-1">
                    {config.has_api_key
                      ? '已保存密钥，留空则保持不变'
                      : '从 Provider 控制台获取，Ollama 本地部署可留空'}
                  </p>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs text-zinc-500 mb-1 block">Max Tokens（输出上限）</label>
                    <input
                      type="number"
                      value={config.max_tokens || 4096}
                      onChange={(e) => updateConfig(index, 'max_tokens', parseInt(e.target.value) || 4096)}
                      className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white text-sm focus:outline-none focus:border-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-zinc-500 flex items-center gap-1 mb-1">
                      <Thermometer size={12} /> Temperature
                    </label>
                    <input
                      type="number"
                      step="0.1"
                      min="0"
                      max="2"
                      value={config.temperature ?? 0.2}
                      onChange={(e) => updateConfig(index, 'temperature', parseFloat(e.target.value) || 0.2)}
                      className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white text-sm focus:outline-none focus:border-indigo-500"
                    />
                  </div>
                </div>
              </div>
            </div>
          ))}

          {configs.length < 5 && (
            <button
              onClick={addConfig}
              className="w-full py-4 border-2 border-dashed border-zinc-700 hover:border-zinc-600 rounded-xl text-zinc-500 hover:text-zinc-300 transition-colors flex items-center justify-center gap-2"
            >
              <Plus size={20} /> 添加配置
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default LlmConfigPanel;
