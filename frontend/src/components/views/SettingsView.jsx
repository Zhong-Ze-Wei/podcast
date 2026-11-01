// -*- coding: utf-8 -*-
import React, { useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import { Check, Loader2, RefreshCw, Server, Settings, Sliders, Sparkles, UserCircle, X } from 'lucide-react';
import AiSettingsPanel from './settings/AiSettingsPanel';
import AppSettingsPanel from './settings/AppSettingsPanel';
import SubscriptionUpdatePanel from './settings/SubscriptionUpdatePanel';
import AccountPanel from './settings/AccountPanel';
import BriefingPreferencesPanel from './settings/BriefingPreferencesPanel';
import { SettingsDraftProvider, useSettingsDraft } from './settings/SettingsDraft';
import { SettingsPage } from './settings/SettingsLayout';
import useDialogFocus from '../../hooks/useDialogFocus';

/** 订阅更新标签：订阅刷新节奏 + 数据源登录态。 */
const SubscriptionPanel = () => (
  <SettingsPage>
    <SubscriptionUpdatePanel />
  </SettingsPage>
);

function SettingsDialogBody({ currentUser, onLogout, initialTab, onClose }) {
  const { t } = useTranslation();
  const { dirty, commitAll, reset } = useSettingsDraft();
  const [activeTab, setActiveTab] = useState(initialTab);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);

  const tabs = [
    { id: 'general', label: t('settings.tabs.general'), icon: Sliders },
    { id: 'subscriptions', label: t('settings.tabs.subscriptions'), icon: RefreshCw },
    { id: 'briefing', label: t('settings.tabs.briefing'), icon: Sparkles },
    ...(currentUser?.role === 'admin' ? [
      { id: 'ai', label: t('settings.tabs.ai'), icon: Server },
    ] : []),
    { id: 'account', label: t('settings.tabs.account'), icon: UserCircle },
  ];

  // AI 配置与提示词模板自带保存按钮、账号页是即时操作，这两类标签不参与底部批量保存
  const stagedTab = ['general', 'subscriptions', 'briefing'].includes(activeTab);

  const cancel = () => {
    reset();
    onClose();
  };

  const save = async () => {
    setSaving(true);
    setError('');
    try {
      await commitAll();
      setSaved(true);
      setTimeout(() => onClose(), 420);
    } catch (err) {
      setError(err?.message || t('settings.saveError'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col bg-zinc-950">
      <header className="flex shrink-0 items-center justify-between gap-4 border-b border-zinc-800 px-5 py-4">
        <div className="flex min-w-0 items-center gap-2">
          <Settings size={18} className="shrink-0 text-indigo-400" />
          <h2 className="text-base font-semibold text-white">{t('settings.title')}</h2>
        </div>
        <button
          type="button"
          onClick={cancel}
          aria-label={t('ui.close')}
          className="rounded-lg p-1.5 text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-200"
        >
          <X size={18} />
        </button>
      </header>

      <nav className="settings-tabs flex shrink-0 gap-1 overflow-x-auto border-b border-zinc-800 px-3 py-2">
        {tabs.map(tab => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            aria-current={activeTab === tab.id ? 'page' : undefined}
            className={`flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
              activeTab === tab.id ? 'bg-indigo-600 text-white' : 'text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100'
            }`}
          >
            <tab.icon size={14} />
            {tab.label}
          </button>
        ))}
      </nav>

      <div className="min-h-0 flex-1 overflow-hidden">
        {activeTab === 'general' && <AppSettingsPanel />}
        {activeTab === 'subscriptions' && <SubscriptionPanel />}
        {activeTab === 'briefing' && <BriefingPreferencesPanel key={currentUser?.id} />}
        {activeTab === 'ai' && currentUser?.role === 'admin' && <AiSettingsPanel />}
        {activeTab === 'account' && <AccountPanel currentUser={currentUser} onLogout={onLogout} />}
      </div>

      <footer className="flex shrink-0 items-center justify-between gap-4 border-t border-zinc-800 bg-zinc-900/40 px-5 py-3">
        <span className="min-w-0 truncate text-xs text-zinc-500">
          {!stagedTab ? t('settings.tabSavesOwn')
            : error ? <span role="alert" className="text-red-400">{error}</span>
              : dirty ? t('settings.unsavedChanges') : t('settings.noChanges')}
        </span>
        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            onClick={cancel}
            className="rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-300 transition-colors hover:bg-zinc-800 hover:text-white"
          >
            {stagedTab ? t('settings.cancel') : t('settings.close')}
          </button>
          {stagedTab && (
            <button
              type="button"
              onClick={save}
              disabled={saving || !dirty}
              className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-500 disabled:cursor-not-allowed disabled:bg-zinc-700 disabled:text-zinc-400"
            >
              {saving ? <Loader2 size={15} className="animate-spin" /> : <Check size={15} />}
              {saved ? t('settings.saved') : t('settings.save')}
            </button>
          )}
        </div>
      </footer>
    </div>
  );
}

/**
 * 设置弹窗：覆盖在当前页面上，不跳转路由。
 * 改动先暂存，底部「保存」提交、「取消」丢弃。
 */
const SettingsView = ({ onBack, currentUser, onLogout, initialTab = 'general' }) => {
  const { t } = useTranslation();
  const dialogRef = useRef(null);

  useDialogFocus(dialogRef, true, onBack);

  // 挂到 body：设置是应用级弹窗，不应受主布局 flex 影响
  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-0 sm:p-6">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={t('settings.title')}
        className="flex h-full w-full max-w-4xl flex-col overflow-hidden border border-zinc-800 bg-zinc-950 shadow-2xl shadow-black/60 sm:h-[min(88vh,860px)] sm:rounded-xl"
      >
        <SettingsDraftProvider>
          <SettingsDialogBody currentUser={currentUser} onLogout={onLogout} initialTab={initialTab} onClose={onBack} />
        </SettingsDraftProvider>
      </div>
    </div>,
    document.body
  );
};

export default SettingsView;
