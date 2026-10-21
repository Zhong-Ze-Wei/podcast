import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import LlmConfigPanel from './LlmConfigPanel';
import PromptTemplatesPanel from './PromptTemplatesPanel';

/**
 * AI 与提示词标签：模型连接是低频配置，提示词是重型编辑器，
 * 两者都保留各自的保存按钮，用页内分段切换而不是并列成两个一级标签。
 */
export default function AiSettingsPanel() {
  const { t } = useTranslation();
  const [section, setSection] = useState('providers');
  const segments = [
    { id: 'providers', label: t('settings.ai.segmentProviders') },
    { id: 'templates', label: t('settings.ai.segmentTemplates') },
  ];

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="border-b border-zinc-800 px-4 py-3 md:px-8">
        <div className="flex w-fit gap-1 rounded-lg bg-zinc-900 p-1">
          {segments.map(segment => (
            <button
              key={segment.id}
              type="button"
              onClick={() => setSection(segment.id)}
              aria-pressed={section === segment.id}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                section === segment.id ? 'bg-indigo-600 text-white' : 'text-zinc-400 hover:text-zinc-100'
              }`}
            >
              {segment.label}
            </button>
          ))}
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-hidden">
        {section === 'providers' ? <LlmConfigPanel /> : <PromptTemplatesPanel />}
      </div>
    </div>
  );
}
