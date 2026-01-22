// -*- coding: utf-8 -*-
import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Plus, Copy, Trash2, Check, AlertCircle, Loader2,
  FileText, Lock, ChevronRight, ToggleLeft, ToggleRight,
  RefreshCw
} from 'lucide-react';
import { promptTemplatesApi } from '../../../services/api';

/**
 * PromptTemplatesPanel - Prompt Templates Management Panel
 *
 * Manage summary templates:
 * - View system templates (read-only)
 * - Duplicate templates
 * - Edit user templates
 * - Configure blocks and parameters
 */
const PromptTemplatesPanel = () => {
  const { t } = useTranslation();
  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [templateDetail, setTemplateDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [showDuplicateModal, setShowDuplicateModal] = useState(false);
  const [duplicateName, setDuplicateName] = useState('');
  const [duplicateDisplayName, setDuplicateDisplayName] = useState('');

  useEffect(() => {
    loadTemplates();
  }, []);

  const loadTemplates = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await promptTemplatesApi.list();
      const templateList = response.data?.templates || response.templates || [];
      setTemplates(templateList);
      // Auto-select first template
      if (templateList.length > 0 && !selectedTemplate) {
        handleSelectTemplate(templateList[0]);
      }
    } catch (err) {
      // Try to initialize templates if empty
      if (err.code === 'TEMPLATE_NOT_FOUND' || templates.length === 0) {
        try {
          await promptTemplatesApi.init();
          const response = await promptTemplatesApi.list();
          const templateList = response.data?.templates || response.templates || [];
          setTemplates(templateList);
          if (templateList.length > 0) {
            handleSelectTemplate(templateList[0]);
          }
        } catch (initErr) {
          setError('Failed to initialize templates');
        }
      } else {
        setError('Failed to load templates');
      }
      console.error('Failed to load templates:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectTemplate = async (template) => {
    setSelectedTemplate(template);
    setDetailLoading(true);
    try {
      const response = await promptTemplatesApi.get(template.id);
      const detail = response.data || response;
      setTemplateDetail(detail);
    } catch (err) {
      console.error('Failed to load template detail:', err);
      setError('Failed to load template details');
    } finally {
      setDetailLoading(false);
    }
  };

  const handleDuplicate = async () => {
    if (!duplicateName.trim()) {
      setError('Template name is required');
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const result = await promptTemplatesApi.duplicate(
        selectedTemplate.id,
        duplicateName.trim(),
        duplicateDisplayName.trim() || duplicateName.trim()
      );
      setSuccess('Template duplicated successfully');
      setTimeout(() => setSuccess(null), 3000);
      setShowDuplicateModal(false);
      setDuplicateName('');
      setDuplicateDisplayName('');
      await loadTemplates();
      // Select the new template
      if (result.id) {
        handleSelectTemplate(result);
      }
    } catch (err) {
      setError(err.message || 'Failed to duplicate template');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (templateId) => {
    if (!confirm('Are you sure you want to delete this template?')) {
      return;
    }

    try {
      await promptTemplatesApi.delete(templateId);
      setSuccess('Template deleted');
      setTimeout(() => setSuccess(null), 3000);
      await loadTemplates();
      setSelectedTemplate(null);
      setTemplateDetail(null);
    } catch (err) {
      setError(err.message || 'Failed to delete template');
    }
  };

  const handleToggleBlock = async (blockId) => {
    if (!templateDetail || templateDetail.is_system) return;

    const updatedBlocks = templateDetail.optional_blocks.map(block => {
      if (block.id === blockId) {
        return { ...block, enabled_by_default: !block.enabled_by_default };
      }
      return block;
    });

    try {
      await promptTemplatesApi.update(templateDetail.id, {
        optional_blocks: updatedBlocks
      });
      setTemplateDetail({ ...templateDetail, optional_blocks: updatedBlocks });
      setSuccess('Block updated');
      setTimeout(() => setSuccess(null), 2000);
    } catch (err) {
      setError('Failed to update block');
    }
  };

  const handleUpdateParameter = async (paramName, field, value) => {
    if (!templateDetail || templateDetail.is_system) return;

    const updatedParams = {
      ...templateDetail.parameters,
      [paramName]: {
        ...templateDetail.parameters[paramName],
        [field]: value
      }
    };

    try {
      await promptTemplatesApi.update(templateDetail.id, {
        parameters: updatedParams
      });
      setTemplateDetail({ ...templateDetail, parameters: updatedParams });
      setSuccess('Parameter updated');
      setTimeout(() => setSuccess(null), 2000);
    } catch (err) {
      setError('Failed to update parameter');
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
    <div className="flex h-full overflow-hidden">
      {/* Left: Template List */}
      <div className="w-72 border-r border-zinc-800 flex flex-col">
        <div className="p-4 border-b border-zinc-800">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-medium text-zinc-400">
              {t('settings.templates') || 'Templates'}
            </h3>
            <button
              onClick={loadTemplates}
              className="p-1 text-zinc-500 hover:text-white transition-colors"
              title="Refresh"
            >
              <RefreshCw size={14} />
            </button>
          </div>
          <p className="text-xs text-zinc-600">
            {templates.length} {t('settings.templatesCount') || 'templates'}
          </p>
        </div>

        <div className="flex-1 overflow-y-auto">
          {templates.map(template => (
            <button
              key={template.id}
              onClick={() => handleSelectTemplate(template)}
              className={`w-full px-4 py-3 text-left border-b border-zinc-800/50 transition-colors flex items-center gap-3 ${
                selectedTemplate?.id === template.id
                  ? 'bg-indigo-900/20 border-l-2 border-l-indigo-500'
                  : 'hover:bg-zinc-800/50'
              }`}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  {template.is_system ? (
                    <Lock size={12} className="text-zinc-500 flex-shrink-0" />
                  ) : (
                    <FileText size={12} className="text-indigo-400 flex-shrink-0" />
                  )}
                  <span className="text-sm font-medium text-white truncate">
                    {template.display_name}
                  </span>
                </div>
                <p className="text-xs text-zinc-500 truncate mt-0.5">
                  {template.name}
                </p>
              </div>
              <ChevronRight size={16} className="text-zinc-600 flex-shrink-0" />
            </button>
          ))}
        </div>
      </div>

      {/* Right: Template Detail */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Messages */}
        {error && (
          <div className="mx-6 mt-4 flex items-center gap-2 text-red-400 px-4 py-2 bg-red-900/20 rounded-lg border border-red-800/50">
            <AlertCircle size={16} />
            <span className="text-sm">{error}</span>
            <button onClick={() => setError(null)} className="ml-auto text-red-400 hover:text-red-300">x</button>
          </div>
        )}
        {success && (
          <div className="mx-6 mt-4 flex items-center gap-2 text-green-400 px-4 py-2 bg-green-900/20 rounded-lg border border-green-800/50">
            <Check size={16} />
            <span className="text-sm">{success}</span>
          </div>
        )}

        {detailLoading ? (
          <div className="flex-1 flex items-center justify-center">
            <Loader2 className="animate-spin w-6 h-6 text-indigo-500" />
          </div>
        ) : templateDetail ? (
          <div className="flex-1 overflow-y-auto p-6">
            {/* Header */}
            <div className="mb-6">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  <h2 className="text-xl font-bold text-white">
                    {templateDetail.display_name}
                  </h2>
                  {templateDetail.is_system && (
                    <span className="text-xs px-2 py-0.5 bg-zinc-700 text-zinc-400 rounded">
                      System Template
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => {
                      setDuplicateName(`${templateDetail.name}_copy`);
                      setDuplicateDisplayName(`${templateDetail.display_name} (Copy)`);
                      setShowDuplicateModal(true);
                    }}
                    className="px-3 py-1.5 text-sm bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg transition-colors flex items-center gap-2"
                  >
                    <Copy size={14} />
                    Duplicate
                  </button>
                  {!templateDetail.is_system && (
                    <button
                      onClick={() => handleDelete(templateDetail.id)}
                      className="px-3 py-1.5 text-sm bg-red-900/30 hover:bg-red-900/50 text-red-400 rounded-lg transition-colors flex items-center gap-2"
                    >
                      <Trash2 size={14} />
                      Delete
                    </button>
                  )}
                </div>
              </div>
              <p className="text-sm text-zinc-500">{templateDetail.description}</p>
            </div>

            {/* Blocks Section */}
            <div className="mb-8">
              <h3 className="text-sm font-medium text-zinc-400 mb-3 flex items-center gap-2">
                <FileText size={14} />
                Optional Blocks
                {templateDetail.is_system && (
                  <span className="text-xs text-zinc-600">(duplicate to edit)</span>
                )}
              </h3>
              <div className="grid gap-2">
                {templateDetail.optional_blocks?.map(block => (
                  <div
                    key={block.id}
                    className={`flex items-center justify-between p-3 rounded-lg border ${
                      block.enabled_by_default
                        ? 'bg-indigo-900/10 border-indigo-800/50'
                        : 'bg-zinc-900/30 border-zinc-800'
                    }`}
                  >
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-white">{block.name}</span>
                        <span className="text-xs text-zinc-500">({block.name_zh})</span>
                      </div>
                      <p className="text-xs text-zinc-500 mt-0.5 line-clamp-1">
                        {block.prompt_fragment}
                      </p>
                    </div>
                    <button
                      onClick={() => handleToggleBlock(block.id)}
                      disabled={templateDetail.is_system}
                      className={`ml-4 ${templateDetail.is_system ? 'opacity-50 cursor-not-allowed' : ''}`}
                    >
                      {block.enabled_by_default ? (
                        <ToggleRight size={24} className="text-indigo-400" />
                      ) : (
                        <ToggleLeft size={24} className="text-zinc-600" />
                      )}
                    </button>
                  </div>
                ))}
              </div>
            </div>

            {/* Parameters Section */}
            <div>
              <h3 className="text-sm font-medium text-zinc-400 mb-3">
                Default Parameters
              </h3>
              <div className="grid gap-4">
                {templateDetail.parameters && Object.entries(templateDetail.parameters).map(([key, param]) => (
                  <div key={key} className="bg-zinc-900/30 border border-zinc-800 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-white">
                        {param.label || key}
                      </span>
                      <span className="text-xs text-zinc-500">{param.label_zh}</span>
                    </div>
                    {param.type === 'enum' && (
                      <div className="flex gap-2 flex-wrap">
                        {param.options?.map(opt => (
                          <button
                            key={opt.value}
                            onClick={() => handleUpdateParameter(key, 'default', opt.value)}
                            disabled={templateDetail.is_system}
                            className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                              param.default === opt.value
                                ? 'bg-indigo-600 text-white'
                                : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700'
                            } ${templateDetail.is_system ? 'opacity-50 cursor-not-allowed' : ''}`}
                          >
                            {opt.label}
                            {opt.token_hint && (
                              <span className="text-xs ml-1 opacity-60">
                                (~{opt.token_hint})
                              </span>
                            )}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center text-zinc-500">
            Select a template to view details
          </div>
        )}
      </div>

      {/* Duplicate Modal */}
      {showDuplicateModal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 w-full max-w-md">
            <h3 className="text-lg font-bold text-white mb-4">Duplicate Template</h3>
            <div className="space-y-4">
              <div>
                <label className="text-sm text-zinc-400 mb-1 block">Template ID (unique)</label>
                <input
                  type="text"
                  value={duplicateName}
                  onChange={(e) => setDuplicateName(e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, ''))}
                  placeholder="my_template"
                  className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="text-sm text-zinc-400 mb-1 block">Display Name</label>
                <input
                  type="text"
                  value={duplicateDisplayName}
                  onChange={(e) => setDuplicateDisplayName(e.target.value)}
                  placeholder="My Custom Template"
                  className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:border-indigo-500"
                />
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => setShowDuplicateModal(false)}
                className="px-4 py-2 text-zinc-400 hover:text-white transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleDuplicate}
                disabled={saving || !duplicateName.trim()}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-zinc-700 text-white rounded-lg font-medium transition-colors flex items-center gap-2"
              >
                {saving && <Loader2 className="animate-spin" size={16} />}
                Duplicate
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PromptTemplatesPanel;
