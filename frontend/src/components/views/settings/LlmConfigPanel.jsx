// -*- coding: utf-8 -*-
import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Plus, Trash2, Check, AlertCircle,
  Loader2, Server, Key, Cpu, Thermometer
} from 'lucide-react';
import { settingsApi } from '../../../services/api';

/**
 * LlmConfigPanel - LLM Configuration Panel
 *
 * Manages LLM API endpoints (up to 5 configs)
 */
const LlmConfigPanel = () => {
  const { t } = useTranslation();
  const [configs, setConfigs] = useState([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(null);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  useEffect(() => {
    loadConfigs();
  }, []);

  const loadConfigs = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await settingsApi.getLlmConfigs();
      setConfigs(response.configs || []);
      setActiveIndex(response.active_index || 0);
    } catch (err) {
      setError(t('settings.loadError') || 'Failed to load settings');
      console.error('Failed to load LLM configs:', err);
    } finally {
      setLoading(false);
    }
  };

  const saveConfigs = async () => {
    setSaving(true);
    setError(null);
    try {
      await settingsApi.saveLlmConfigs({
        configs,
        active_index: activeIndex
      });
      setSuccess(t('settings.saved') || 'Settings saved');
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      setError(t('settings.saveError') || 'Failed to save settings');
      console.error('Failed to save LLM configs:', err);
    } finally {
      setSaving(false);
    }
  };

  const addConfig = () => {
    if (configs.length >= 5) {
      setError(t('settings.maxConfigs') || 'Maximum 5 configs allowed');
      return;
    }
    const newConfig = {
      name: `Config ${configs.length + 1}`,
      base_url: '',
      api_key: '',
      model: '',
      max_tokens: 4096,
      temperature: 0.2
    };
    setConfigs([...configs, newConfig]);
  };

  const deleteConfig = (index) => {
    if (configs.length <= 1) {
      setError(t('settings.minConfigs') || 'At least one config is required');
      return;
    }
    const newConfigs = configs.filter((_, i) => i !== index);
    setConfigs(newConfigs);
    if (activeIndex >= newConfigs.length) {
      setActiveIndex(Math.max(0, newConfigs.length - 1));
    } else if (activeIndex > index) {
      setActiveIndex(activeIndex - 1);
    }
  };

  const updateConfig = (index, field, value) => {
    const newConfigs = [...configs];
    newConfigs[index] = { ...newConfigs[index], [field]: value };
    setConfigs(newConfigs);
  };

  const testConnection = async (index) => {
    const config = configs[index];
    if (!config.base_url || !config.model) {
      setError(t('settings.testRequiredFields') || 'base_url and model are required');
      return;
    }

    setTesting(index);
    setError(null);
    try {
      const result = await settingsApi.testLlmConnection(config);
      if (result.success) {
        setSuccess(t('settings.testSuccess') || 'Connection successful');
        setTimeout(() => setSuccess(null), 3000);
      } else {
        setError(result.error || t('settings.testFailed') || 'Connection failed');
      }
    } catch (err) {
      setError(t('settings.testFailed') || 'Connection test failed');
    } finally {
      setTesting(null);
    }
  };

  const setActive = (index) => {
    setActiveIndex(index);
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
        <p className="text-zinc-500 text-sm">
          {t('settings.llmDesc') || 'Configure LLM API endpoints for AI features'}
        </p>
        <button
          onClick={saveConfigs}
          disabled={saving}
          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-zinc-700 text-white rounded-lg font-medium transition-colors flex items-center gap-2"
        >
          {saving ? <Loader2 className="animate-spin" size={16} /> : <Check size={16} />}
          {t('settings.save') || 'Save'}
        </button>
      </div>

      {/* Messages */}
      {error && (
        <div className="mx-8 mt-4 flex items-center gap-2 text-red-400 px-4 py-2 bg-red-900/20 rounded-lg border border-red-800/50">
          <AlertCircle size={16} />
          <span className="text-sm">{error}</span>
        </div>
      )}
      {success && (
        <div className="mx-8 mt-4 flex items-center gap-2 text-green-400 px-4 py-2 bg-green-900/20 rounded-lg border border-green-800/50">
          <Check size={16} />
          <span className="text-sm">{success}</span>
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
                    onClick={() => setActive(index)}
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
                    placeholder="Config Name"
                  />
                  {activeIndex === index && (
                    <span className="text-xs px-2 py-0.5 bg-indigo-500/20 text-indigo-400 rounded-full">
                      {t('settings.active') || 'Active'}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => testConnection(index)}
                    disabled={testing === index}
                    className="px-3 py-1.5 text-sm bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg transition-colors flex items-center gap-2"
                  >
                    {testing === index ? (
                      <Loader2 className="animate-spin" size={14} />
                    ) : (
                      <Server size={14} />
                    )}
                    {t('settings.test') || 'Test'}
                  </button>
                  <button
                    onClick={() => deleteConfig(index)}
                    className="p-1.5 text-zinc-500 hover:text-red-400 transition-colors"
                    title={t('settings.delete') || 'Delete'}
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>

              {/* Config Fields */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs text-zinc-500 flex items-center gap-1 mb-1">
                    <Server size={12} />
                    Base URL
                  </label>
                  <input
                    type="text"
                    value={config.base_url || ''}
                    onChange={(e) => updateConfig(index, 'base_url', e.target.value)}
                    placeholder="http://localhost:8000"
                    className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:border-indigo-500"
                  />
                </div>
                <div>
                  <label className="text-xs text-zinc-500 flex items-center gap-1 mb-1">
                    <Cpu size={12} />
                    Model
                  </label>
                  <input
                    type="text"
                    value={config.model || ''}
                    onChange={(e) => updateConfig(index, 'model', e.target.value)}
                    placeholder="gpt-4, claude-3-opus, etc."
                    className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:border-indigo-500"
                  />
                </div>
                <div>
                  <label className="text-xs text-zinc-500 flex items-center gap-1 mb-1">
                    <Key size={12} />
                    API Key
                    {config.has_api_key && !config.api_key && (
                      <span className="text-green-400 ml-2">(saved)</span>
                    )}
                  </label>
                  <input
                    type="password"
                    value={config.api_key || ''}
                    onChange={(e) => updateConfig(index, 'api_key', e.target.value)}
                    placeholder={config.has_api_key ? "(leave empty to keep current)" : "sk-..."}
                    className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:border-indigo-500"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs text-zinc-500 mb-1 block">Max Tokens</label>
                    <input
                      type="number"
                      value={config.max_tokens || 4096}
                      onChange={(e) => updateConfig(index, 'max_tokens', parseInt(e.target.value) || 4096)}
                      className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white focus:outline-none focus:border-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-zinc-500 flex items-center gap-1 mb-1">
                      <Thermometer size={12} />
                      Temperature
                    </label>
                    <input
                      type="number"
                      step="0.1"
                      min="0"
                      max="2"
                      value={config.temperature || 0.2}
                      onChange={(e) => updateConfig(index, 'temperature', parseFloat(e.target.value) || 0.2)}
                      className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white focus:outline-none focus:border-indigo-500"
                    />
                  </div>
                </div>
              </div>
            </div>
          ))}

          {/* Add Button */}
          {configs.length < 5 && (
            <button
              onClick={addConfig}
              className="w-full py-4 border-2 border-dashed border-zinc-700 hover:border-zinc-600 rounded-xl text-zinc-500 hover:text-zinc-300 transition-colors flex items-center justify-center gap-2"
            >
              <Plus size={20} />
              {t('settings.addConfig') || 'Add Configuration'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default LlmConfigPanel;
