// -*- coding: utf-8 -*-
import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Settings, ChevronLeft, RefreshCw, Server, Sliders, Sparkles, UserCircle } from 'lucide-react';
import AiSettingsPanel from './settings/AiSettingsPanel';
import AppSettingsPanel from './settings/AppSettingsPanel';
import SubscriptionUpdatePanel from './settings/SubscriptionUpdatePanel';
import AccountPanel from './settings/AccountPanel';
import BriefingPreferencesPanel from './settings/BriefingPreferencesPanel';
import { SettingsPage } from './settings/SettingsLayout';

/** 订阅更新标签：订阅刷新节奏 + 数据源登录态。 */
const SubscriptionPanel = () => (
  <SettingsPage>
    <SubscriptionUpdatePanel />
  </SettingsPage>
);

const SettingsView = ({ onBack, currentUser, onLogout, initialTab = 'general', onOpenMenu }) => {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState(initialTab);

  useEffect(() => { setActiveTab(initialTab); }, [initialTab]);

  // 按「用户此刻想做什么」分组：日常偏好 → 数据来源 → 内容偏好 → 一次性配置
  const tabs = [
    { id: 'general', label: t('settings.tabs.general'), description: t('settings.tabs.generalDesc'), icon: Sliders },
    { id: 'subscriptions', label: t('settings.tabs.subscriptions'), description: t('settings.tabs.subscriptionsDesc'), icon: RefreshCw },
    { id: 'briefing', label: t('settings.tabs.briefing'), description: t('settings.tabs.briefingDesc'), icon: Sparkles },
    ...(currentUser?.role === 'admin' ? [
      { id: 'ai', label: t('settings.tabs.ai'), description: t('settings.tabs.aiDesc'), icon: Server },
    ] : []),
    { id: 'account', label: t('settings.tabs.account'), description: t('settings.tabs.accountDesc'), icon: UserCircle },
  ];
  const activeTabMeta = tabs.find(tab => tab.id === activeTab) || tabs[0];

  return (
    <div className="flex h-full flex-col overflow-hidden bg-zinc-950 text-zinc-100">
      <div className="border-b border-zinc-800 bg-zinc-900/20 px-4 py-5 md:px-8">
        <div className="flex items-center gap-4">
          <button
            onClick={onBack}
            aria-label={t('ui.backToPreviousPage')}
            className="rounded-full p-2 text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-white"
          >
            <ChevronLeft size={24} />
          </button>
          <div className="min-w-0 flex-1">
            <h1 className="flex items-center gap-2 text-xl font-bold text-white">
              <Settings size={20} className="text-indigo-400" />
              {t('settings.title')}
            </h1>
            <p className="mt-1 text-sm text-zinc-500">{activeTabMeta.description}</p>
          </div>
        </div>

        <div className="settings-tabs mt-4 flex w-full gap-1 overflow-x-auto rounded-xl bg-zinc-800/50 p-1 sm:w-fit">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              aria-current={activeTab === tab.id ? 'page' : undefined}
              className={`flex shrink-0 items-center gap-2 whitespace-nowrap rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === tab.id ? 'bg-indigo-600 text-white' : 'text-zinc-400 hover:bg-zinc-700/50 hover:text-white'
              }`}
            >
              <tab.icon size={16} />
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-hidden">
        {activeTab === 'general' && <AppSettingsPanel />}
        {activeTab === 'subscriptions' && <SubscriptionPanel />}
        {activeTab === 'briefing' && <BriefingPreferencesPanel key={currentUser.id} />}
        {activeTab === 'ai' && currentUser?.role === 'admin' && <AiSettingsPanel />}
        {activeTab === 'account' && <AccountPanel currentUser={currentUser} onLogout={onLogout} />}
      </div>
    </div>
  );
};

export default SettingsView;
