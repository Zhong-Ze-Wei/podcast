// -*- coding: utf-8 -*-
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { RefreshCw, Activity, Check, Clock3, PanelRightOpen } from 'lucide-react';

export const AUTO_REFRESH_KEY = 'podcast_auto_refresh_minutes';
export const TASK_POLL_KEY = 'podcast_task_poll_seconds';
export const TASK_HISTORY_WINDOW_KEY = 'podcast_task_history_window_minutes';
export const TASK_PANEL_DEFAULT_OPEN_KEY = 'podcast_task_panel_default_open';

const REFRESH_OPTIONS = [0, 1, 5, 10, 30, 60];
const POLL_OPTIONS = [2, 3, 5, 10];
const HISTORY_OPTIONS = [5, 60, 1440, 10080];

function readInt(key, fallback) {
  const value = localStorage.getItem(key);
  const parsed = value !== null ? parseInt(value, 10) : fallback;
  return Number.isFinite(parsed) ? parsed : fallback;
}

function readBool(key, fallback) {
  const value = localStorage.getItem(key);
  if (value === null) return fallback;
  return value === 'true';
}

const SettingRow = ({ icon: Icon, title, description, children }) => (
  <section className="border-b border-zinc-800 pb-7 last:border-b-0 last:pb-0">
    <div className="flex items-start gap-3">
      <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-zinc-800 bg-zinc-950 text-sky-400">
        <Icon size={16} />
      </div>
      <div className="min-w-0 flex-1">
        <h3 className="text-base font-semibold text-white">{title}</h3>
        <p className="mt-1 text-sm leading-relaxed text-zinc-500">{description}</p>
        <div className="mt-4">{children}</div>
      </div>
    </div>
  </section>
);

const AppSettingsPanel = () => {
  const { t } = useTranslation();
  const [refreshMinutes, setRefreshMinutes] = useState(() => readInt(AUTO_REFRESH_KEY, 5));
  const [pollSeconds, setPollSeconds] = useState(() => readInt(TASK_POLL_KEY, 3));
  const [historyWindowMinutes, setHistoryWindowMinutes] = useState(() => readInt(TASK_HISTORY_WINDOW_KEY, 60));
  const [taskPanelDefaultOpen, setTaskPanelDefaultOpen] = useState(() => readBool(TASK_PANEL_DEFAULT_OPEN_KEY, false));
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    localStorage.setItem(AUTO_REFRESH_KEY, String(refreshMinutes));
    localStorage.setItem(TASK_POLL_KEY, String(pollSeconds));
    localStorage.setItem(TASK_HISTORY_WINDOW_KEY, String(historyWindowMinutes));
    localStorage.setItem(TASK_PANEL_DEFAULT_OPEN_KEY, String(taskPanelDefaultOpen));

    [
      AUTO_REFRESH_KEY,
      TASK_POLL_KEY,
      TASK_HISTORY_WINDOW_KEY,
      TASK_PANEL_DEFAULT_OPEN_KEY,
    ].forEach(key => {
      window.dispatchEvent(new StorageEvent('storage', {
        key,
        newValue: localStorage.getItem(key),
      }));
    });

    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b border-zinc-800 px-8 py-4">
        <p className="text-sm text-zinc-500">{t('settings.app.description')}</p>
        <button
          onClick={handleSave}
          className="flex items-center gap-2 rounded-lg bg-sky-600 px-4 py-2 font-medium text-white transition-colors hover:bg-sky-500"
        >
          <Check size={16} />
          {saved ? t('settings.saved') : t('settings.save')}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-8">
        <div className="max-w-2xl space-y-7">
          <SettingRow
            icon={RefreshCw}
            title={t('settings.app.autoRefreshTitle')}
            description={t('settings.app.autoRefreshDescription')}
          >
            <select
              value={refreshMinutes}
              onChange={event => setRefreshMinutes(parseInt(event.target.value, 10))}
              className="w-48 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-200 outline-none focus:border-sky-500"
            >
              {REFRESH_OPTIONS.map(value => (
                <option key={value} value={value}>{t(`settings.app.refreshOptions.${value}`)}</option>
              ))}
            </select>
          </SettingRow>

          <SettingRow
            icon={Activity}
            title={t('settings.app.taskPollTitle')}
            description={t('settings.app.taskPollDescription')}
          >
            <select
              value={pollSeconds}
              onChange={event => setPollSeconds(parseInt(event.target.value, 10))}
              className="w-48 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-200 outline-none focus:border-sky-500"
            >
              {POLL_OPTIONS.map(value => (
                <option key={value} value={value}>{t(`settings.app.pollOptions.${value}`)}</option>
              ))}
            </select>
          </SettingRow>

          <SettingRow
            icon={Clock3}
            title={t('settings.app.taskHistoryTitle')}
            description={t('settings.app.taskHistoryDescription')}
          >
            <select
              value={historyWindowMinutes}
              onChange={event => setHistoryWindowMinutes(parseInt(event.target.value, 10))}
              className="w-48 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-200 outline-none focus:border-sky-500"
            >
              {HISTORY_OPTIONS.map(value => (
                <option key={value} value={value}>{t(`settings.app.historyOptions.${value}`)}</option>
              ))}
            </select>
          </SettingRow>

          <SettingRow
            icon={PanelRightOpen}
            title={t('settings.app.taskPanelDefaultOpenTitle')}
            description={t('settings.app.taskPanelDefaultOpenDescription')}
          >
            <label className="inline-flex cursor-pointer items-center gap-3">
              <input
                type="checkbox"
                checked={taskPanelDefaultOpen}
                onChange={event => setTaskPanelDefaultOpen(event.target.checked)}
                className="h-4 w-4 rounded border-zinc-700 bg-zinc-900 text-sky-600 focus:ring-sky-500"
              />
              <span className="text-sm text-zinc-300">{t('settings.app.taskPanelDefaultOpenLabel')}</span>
            </label>
          </SettingRow>
        </div>
      </div>
    </div>
  );
};

export default AppSettingsPanel;
