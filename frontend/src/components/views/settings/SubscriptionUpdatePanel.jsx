import React, { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { settingsApi } from '../../../services/api';
import { SaveStatus, SettingGroup, SettingRow } from './SettingsLayout';

// 统一管理订阅更新节奏：所有间隔都在这里调，改完即生效
const NUMBER_FIELDS = [
  { key: 'feed_interval_hours', label: 'feedInterval', min: 1, max: 168, step: 1, unit: 'hours' },
  { key: 'check_interval_minutes', label: 'checkInterval', min: 1, max: 60, step: 1, unit: 'minutes' },
  { key: 'feeds_per_tick', label: 'feedsPerTick', min: 1, max: 20, step: 1, unit: 'feeds' },
  { key: 'transcript_interval_minutes', label: 'transcriptInterval', min: 1, max: 300, step: 1, unit: 'minutes' },
  { key: 'transcript_sweep_minutes', label: 'sweepInterval', min: 5, max: 1440, step: 5, unit: 'minutes' },
  { key: 'transcript_sweep_batch', label: 'sweepBatch', min: 1, max: 50, step: 1, unit: 'feeds' },
];

const inputClass = 'w-24 rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm tabular-nums text-zinc-200 outline-none focus:border-indigo-500';

export default function SubscriptionUpdatePanel() {
  const { t } = useTranslation();
  const [settings, setSettings] = useState(null);
  const [limits, setLimits] = useState({});
  const [daily, setDaily] = useState(null);
  const [queue, setQueue] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');
  const mounted = useRef(true);
  const saveTimer = useRef(null);

  useEffect(() => {
    mounted.current = true;
    settingsApi.getRefreshSettings()
      .then(response => {
        const data = response.data || response;
        if (!mounted.current) return;
        setSettings(data.settings);
        setLimits(data.limits || {});
        setDaily(data.daily);
        setQueue(data.transcript_queue);
      })
      .catch(err => { if (mounted.current) setError(err.message || t('settings.refresh.loadError')); });
    return () => { mounted.current = false; clearTimeout(saveTimer.current); };
  }, []);

  const persist = changes => {
    setSettings(current => ({ ...current, ...changes }));
    clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(async () => {
      setSaving(true); setError('');
      try {
        const response = await settingsApi.saveRefreshSettings(changes);
        if (!mounted.current) return;
        setSettings((response.data || response).settings);
        setSaved(true);
        setTimeout(() => { if (mounted.current) setSaved(false); }, 1600);
      } catch (err) {
        if (mounted.current) setError(err.message || t('settings.refresh.saveError'));
      } finally {
        if (mounted.current) setSaving(false);
      }
    }, 400);
  };

  if (!settings) {
    return <p role={error ? 'alert' : 'status'} className="text-sm text-zinc-500">{error || t('settings.refresh.loading')}</p>;
  }

  const bound = key => limits[key] || [1, 999];
  const queueDepth = queue?.queued_count ?? 0;
  const status = daily
    ? t('settings.refresh.todayDone', { done: daily.done, total: daily.feeds, failed: daily.failed })
    : '';

  return (
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
            checked={Boolean(settings.enabled)}
            onChange={event => persist({ enabled: event.target.checked })}
            className="h-4 w-4 rounded border-zinc-700 bg-zinc-950 text-indigo-600 focus:ring-indigo-500"
          />
          <SaveStatus saving={saving} saved={saved} error={error} t={t} />
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
                value={settings[field.key]}
                onChange={event => persist({ [field.key]: Number(event.target.value) })}
                className={inputClass}
              />
              <span className="w-16 text-xs text-zinc-500">{t(`settings.refresh.units.${field.unit}`)}</span>
            </span>
          </SettingRow>
        );
      })}
    </SettingGroup>
  );
}
