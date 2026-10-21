// -*- coding: utf-8 -*-
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import SubscriptionUpdatePanel from './SubscriptionUpdatePanel';
import { SaveStatus, SettingsPage, SettingGroup, SettingRow } from './SettingsLayout';

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

/**
 * 写入浏览器偏好并通知同窗口的其他订阅者。
 * App 用 storage 事件同步这些值，而同一窗口内的写入不会自动触发该事件。
 */
function writePref(key, value) {
  localStorage.setItem(key, String(value));
  window.dispatchEvent(new StorageEvent('storage', { key, newValue: localStorage.getItem(key) }));
}

const selectClass = 'w-44 rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-200 outline-none focus:border-indigo-500';

const AppSettingsPanel = () => {
  const { t } = useTranslation();
  const [refreshMinutes, setRefreshMinutes] = useState(() => readInt(AUTO_REFRESH_KEY, 5));
  const [pollSeconds, setPollSeconds] = useState(() => readInt(TASK_POLL_KEY, 3));
  const [historyWindowMinutes, setHistoryWindowMinutes] = useState(() => readInt(TASK_HISTORY_WINDOW_KEY, 60));
  const [taskPanelDefaultOpen, setTaskPanelDefaultOpen] = useState(() => readBool(TASK_PANEL_DEFAULT_OPEN_KEY, false));
  const [savedAt, setSavedAt] = useState(0);

  // 与订阅更新一致：改完立即生效，只在行尾提示“已保存”
  const change = (key, setter, value) => {
    setter(value);
    writePref(key, value);
    setSavedAt(Date.now());
  };
  const saved = Date.now() - savedAt < 1600;

  return (
    <SettingsPage>
      <SubscriptionUpdatePanel />

      <SettingGroup title={t('settings.app.displayGroup')} description={t('settings.app.displayGroupHint')}>
        <SettingRow
          label={t('settings.app.autoRefreshTitle')}
          description={t('settings.app.autoRefreshDescription')}
        >
          <span className="flex items-center gap-3">
            <SaveStatus saved={saved} t={t} />
            <select
              value={refreshMinutes}
              onChange={event => change(AUTO_REFRESH_KEY, setRefreshMinutes, parseInt(event.target.value, 10))}
              className={selectClass}
            >
              {REFRESH_OPTIONS.map(value => (
                <option key={value} value={value}>{t(`settings.app.refreshOptions.${value}`)}</option>
              ))}
            </select>
          </span>
        </SettingRow>

        <SettingRow
          label={t('settings.app.taskPollTitle')}
          description={t('settings.app.taskPollDescription')}
        >
          <select
            value={pollSeconds}
            onChange={event => change(TASK_POLL_KEY, setTaskPollSeconds, parseInt(event.target.value, 10))}
            className={selectClass}
          >
            {POLL_OPTIONS.map(value => (
              <option key={value} value={value}>{t(`settings.app.pollOptions.${value}`)}</option>
            ))}
          </select>
        </SettingRow>

        <SettingRow
          label={t('settings.app.taskHistoryTitle')}
          description={t('settings.app.taskHistoryDescription')}
        >
          <select
            value={historyWindowMinutes}
            onChange={event => change(TASK_HISTORY_WINDOW_KEY, setHistoryWindowMinutes, parseInt(event.target.value, 10))}
            className={selectClass}
          >
            {HISTORY_OPTIONS.map(value => (
              <option key={value} value={value}>{t(`settings.app.historyOptions.${value}`)}</option>
            ))}
          </select>
        </SettingRow>

        <SettingRow
          label={t('settings.app.taskPanelDefaultOpenTitle')}
          description={t('settings.app.taskPanelDefaultOpenDescription')}
        >
          <label className="inline-flex cursor-pointer items-center gap-3">
            <input
              type="checkbox"
              checked={taskPanelDefaultOpen}
              onChange={event => change(TASK_PANEL_DEFAULT_OPEN_KEY, setTaskPanelDefaultOpen, event.target.checked)}
              className="h-4 w-4 rounded border-zinc-700 bg-zinc-950 text-indigo-600 focus:ring-indigo-500"
            />
            <span className="text-sm text-zinc-300">{t('settings.app.taskPanelDefaultOpenLabel')}</span>
          </label>
        </SettingRow>
      </SettingGroup>
    </SettingsPage>
  );
};

export default AppSettingsPanel;
