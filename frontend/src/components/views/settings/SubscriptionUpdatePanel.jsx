import React, { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Activity, Check, RefreshCw, Timer, Layers } from 'lucide-react';
import { settingsApi } from '../../../services/api';

// 统一管理订阅更新节奏：所有间隔都在这里调，保存后后端即时生效
const NUMBER_FIELDS = [
  { key: 'feed_interval_hours', label: 'feedInterval', icon: RefreshCw, min: 1, max: 168, step: 1, unit: 'hours' },
  { key: 'check_interval_minutes', label: 'checkInterval', icon: Activity, min: 1, max: 60, step: 1, unit: 'minutes' },
  { key: 'feeds_per_tick', label: 'feedsPerTick', icon: Activity, min: 1, max: 20, step: 1, unit: 'feeds' },
  { key: 'transcript_interval_minutes', label: 'transcriptInterval', icon: Timer, min: 1, max: 300, step: 1, unit: 'minutes' },
  { key: 'transcript_sweep_minutes', label: 'sweepInterval', icon: Layers, min: 5, max: 1440, step: 5, unit: 'minutes' },
  { key: 'transcript_sweep_batch', label: 'sweepBatch', icon: Layers, min: 1, max: 50, step: 1, unit: 'feeds' },
];

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

  const load = () => settingsApi.getRefreshSettings().then(response => {
    const data = response.data || response;
    if (!mounted.current) return;
    setSettings(data.settings);
    setLimits(data.limits || {});
    setDaily(data.daily);
    setQueue(data.transcript_queue);
  });

  useEffect(() => {
    mounted.current = true;
    load().catch(err => { if (mounted.current) setError(err.message || t('settings.refresh.loadError')); });
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

  return (
    <section className="border-b border-zinc-800 pb-7">
      <div className="flex items-start gap-3">
        <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-zinc-800 bg-zinc-950 text-sky-400">
          <RefreshCw size={16} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <h3 className="text-base font-semibold text-white">{t('settings.refresh.title')}</h3>
            {saving && <span className="text-xs text-sky-400">{t('common.saving')}</span>}
            {!saving && saved && <span className="flex items-center gap-1 text-xs text-emerald-400"><Check size={12} />{t('settings.saved')}</span>}
          </div>
          <p className="mt-1 text-sm leading-relaxed text-zinc-500">{t('settings.refresh.description')}</p>

          <label className="mt-4 inline-flex cursor-pointer items-center gap-3">
            <input
              type="checkbox"
              checked={Boolean(settings.enabled)}
              onChange={event => persist({ enabled: event.target.checked })}
              className="h-4 w-4 rounded border-zinc-700 bg-zinc-900 text-sky-600 focus:ring-sky-500"
            />
            <span className="text-sm text-zinc-300">{t('settings.refresh.enabled')}</span>
          </label>

          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            {NUMBER_FIELDS.map(field => {
              const [min, max] = bound(field.key);
              return (
                <label key={field.key} className="block">
                  <span className="flex items-center gap-1.5 text-sm text-zinc-300">
                    <field.icon size={14} className="text-zinc-500" />
                    {t(`settings.refresh.${field.label}`)}
                  </span>
                  <span className="mt-2 flex items-center gap-2">
                    <input
                      type="number"
                      min={min}
                      max={max}
                      step={field.step}
                      value={settings[field.key]}
                      onChange={event => persist({ [field.key]: Number(event.target.value) })}
                      className="w-28 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-200 outline-none focus:border-sky-500"
                    />
                    <span className="text-xs text-zinc-500">{t(`settings.refresh.units.${field.unit}`)}</span>
                  </span>
                  <span className="mt-1 block text-xs text-zinc-600">
                    {t(`settings.refresh.${field.label}Hint`, { min, max })}
                  </span>
                </label>
              );
            })}
          </div>

          <div className="mt-4 flex flex-wrap gap-x-6 gap-y-1 text-xs text-zinc-500">
            <span>{t('settings.refresh.queueDepth', { count: queueDepth })}</span>
            {daily && <span>{t('settings.refresh.todayDone', { done: daily.done, total: daily.feeds, failed: daily.failed })}</span>}
          </div>
          {error && <p role="alert" className="mt-3 text-sm text-red-400">{error}</p>}
        </div>
      </div>
    </section>
  );
}
