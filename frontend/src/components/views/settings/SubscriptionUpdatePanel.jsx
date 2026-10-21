import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { settingsApi } from '../../../services/api';
import { useStagedSettings } from './SettingsDraft';
import { SettingGroup, SettingRow } from './SettingsLayout';

// 统一管理订阅更新节奏：所有间隔都在这里调，点弹窗底部“保存”才提交
const NUMBER_FIELDS = [
  { key: 'feed_interval_hours', label: 'feedInterval', min: 1, max: 168, step: 1, unit: 'hours' },
  { key: 'check_interval_minutes', label: 'checkInterval', min: 1, max: 60, step: 1, unit: 'minutes' },
  { key: 'feeds_per_tick', label: 'feedsPerTick', min: 1, max: 20, step: 1, unit: 'feeds' },
  { key: 'transcript_interval_minutes', label: 'transcriptInterval', min: 1, max: 300, step: 1, unit: 'minutes' },
  { key: 'transcript_sweep_minutes', label: 'sweepInterval', min: 5, max: 1440, step: 5, unit: 'minutes' },
  { key: 'transcript_sweep_batch', label: 'sweepBatch', min: 1, max: 50, step: 1, unit: 'feeds' },
];

const inputClass = 'w-24 rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm tabular-nums text-zinc-200 outline-none focus:border-indigo-500';

function BilibiliSession() {
  const { t } = useTranslation();
  const [status, setStatus] = useState(null);
  const [input, setInput] = useState('');
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState(null);

  useEffect(() => {
    settingsApi.getBilibiliStatus().then(setStatus).catch(() => {});
  }, []);

  // 登录态需要实时校验，所以保存即生效，不参与弹窗的批量提交
  const save = async () => {
    const value = input.trim();
    if (!value) return;
    setSaving(true);
    setNotice(null);
    try {
      const res = await settingsApi.updateBilibiliSessdata(value);
      if (res.valid) {
        setNotice({ success: true, message: t('settings.biliSessdataSaved', { value1: res.nickname || res.mid }) });
        setInput('');
      } else {
        setNotice({ success: false, message: res.message || t('settings.biliSessdataInvalid') });
      }
      setStatus({ configured: true, valid: !!res.valid, nickname: res.nickname, mid: res.mid });
    } catch (err) {
      setNotice({ success: false, message: err?.response?.data?.message || String(err) });
    } finally {
      setSaving(false);
    }
  };

  const state = !status?.configured
    ? t('ui.sESSDATAIsNotConfiguredBilibiliRefreshAnd')
    : status.valid
      ? t('ui.connectedValueValidSESSDATA', { value1: status.nickname || status.mid })
      : t('ui.configuredButValidationFailedSESSDATAMayHave');
  const tone = !status?.configured ? 'bg-zinc-600' : status.valid ? 'bg-emerald-500' : 'bg-amber-500';

  return (
    <SettingGroup
      title={t('settings.refresh.biliTitle')}
      description={state}
      hint={notice ? notice.message : (status?.valid === false ? t('settings.biliSessdataHowTo') : undefined)}
    >
      <SettingRow label={t('settings.refresh.biliSessdata')} description={t('settings.biliSessdataHowToShort')}>
        <span className="flex items-center gap-2">
          <span className={`h-2 w-2 shrink-0 rounded-full ${tone}`} />
          <input
            type="text"
            value={input}
            onChange={event => setInput(event.target.value)}
            placeholder={t('settings.biliSessdataPlaceholder')}
            className="w-64 rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-200 outline-none placeholder:text-zinc-600 focus:border-indigo-500"
          />
          <button
            type="button"
            onClick={save}
            disabled={!input.trim() || saving}
            className="shrink-0 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:cursor-not-allowed disabled:bg-zinc-700 disabled:text-zinc-400"
          >
            {saving ? t('settings.biliSessdataVerifying') : t('settings.biliSessdataSave')}
          </button>
        </span>
      </SettingRow>
    </SettingGroup>
  );
}

export default function SubscriptionUpdatePanel() {
  const { t } = useTranslation();
  const [server, setServer] = useState(null);
  const [limits, setLimits] = useState({});
  const [daily, setDaily] = useState(null);
  const [queue, setQueue] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    settingsApi.getRefreshSettings()
      .then(response => {
        const data = response.data || response;
        setServer(data.settings);
        setLimits(data.limits || {});
        setDaily(data.daily);
        setQueue(data.transcript_queue);
      })
      .catch(err => setError(err.message || t('settings.refresh.loadError')));
  }, []);

  const { values, change, hasStaged } = useStagedSettings('subscriptions', server, async changes => {
    await settingsApi.saveRefreshSettings(changes);
  });

  if (!server) {
    return <p role={error ? 'alert' : 'status'} className="text-sm text-zinc-500">{error || t('settings.refresh.loading')}</p>;
  }

  const bound = key => limits[key] || [1, 999];
  const queueDepth = queue?.queued_count ?? 0;
  const status = daily
    ? t('settings.refresh.todayDone', { done: daily.done, total: daily.feeds, failed: daily.failed })
    : '';

  return (
    <>
      <SettingGroup
        title={t('settings.refresh.title')}
        description={t('settings.refresh.description')}
        hint={[status, t('settings.refresh.queueDepth', { count: queueDepth })].filter(Boolean).join(' · ')}
      >
        <SettingRow
          label={t('settings.refresh.enabled')}
          description={t('settings.refresh.enabledHint')}
        >
          <label className="inline-flex cursor-pointer items-center gap-2">
            <input
              type="checkbox"
              checked={Boolean(values.enabled)}
              onChange={event => change({ enabled: event.target.checked })}
              className="h-4 w-4 rounded border-zinc-700 bg-zinc-950 text-indigo-600 focus:ring-indigo-500"
            />
            {hasStaged && <span className="text-xs text-amber-400">{t('settings.pendingSave')}</span>}
          </label>
        </SettingRow>

        {NUMBER_FIELDS.map(field => {
          const [min, max] = bound(field.key);
          return (
            <SettingRow
              key={field.key}
              label={t(`settings.refresh.${field.label}`)}
              description={t(`settings.refresh.${field.label}Hint`, { min, max })}
            >
              <span className="flex items-center gap-2">
                <input
                  type="number"
                  min={min}
                  max={max}
                  step={field.step}
                  value={values[field.key]}
                  onChange={event => change({ [field.key]: Number(event.target.value) })}
                  className={inputClass}
                />
                <span className="w-16 text-xs text-zinc-500">{t(`settings.refresh.units.${field.unit}`)}</span>
              </span>
            </SettingRow>
          );
        })}
      </SettingGroup>

      <BilibiliSession />
    </>
  );
}
