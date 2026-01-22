// -*- coding: utf-8 -*-
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Settings, ChevronLeft, Server, FileText } from 'lucide-react';
import LlmConfigPanel from './settings/LlmConfigPanel';
import PromptTemplatesPanel from './settings/PromptTemplatesPanel';

/**
 * SettingsView - Settings page with tabs
 *
 * Tabs:
 * - LLM Configuration
 * - Summary Templates
 */
const SettingsView = ({ onBack }) => {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState('llm'); // llm | templates

  const tabs = [
    {
      id: 'llm',
      label: t('settings.llmTab') || 'LLM Configuration',
      icon: Server
    },
    {
      id: 'templates',
      label: t('settings.templatesTab') || 'Summary Templates',
      icon: FileText
    }
  ];

  return (
    <div className="flex flex-col h-full bg-zinc-950 text-zinc-100 overflow-hidden">
      {/* Header */}
      <div className="px-8 py-6 border-b border-zinc-800 bg-zinc-900/20">
        <div className="flex items-center gap-4 mb-6">
          <button
            onClick={onBack}
            className="p-2 hover:bg-zinc-800 rounded-full transition-colors text-zinc-400 hover:text-white"
          >
            <ChevronLeft size={24} />
          </button>
          <div className="flex-1">
            <h1 className="text-2xl font-bold text-white flex items-center gap-3">
              <Settings size={24} className="text-indigo-400" />
              {t('settings.title') || 'Settings'}
            </h1>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-zinc-800/50 p-1 rounded-xl w-fit">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? 'bg-indigo-600 text-white'
                  : 'text-zinc-400 hover:text-white hover:bg-zinc-700/50'
              }`}
            >
              <tab.icon size={16} />
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        {activeTab === 'llm' && <LlmConfigPanel />}
        {activeTab === 'templates' && <PromptTemplatesPanel />}
      </div>
    </div>
  );
};

export default SettingsView;
