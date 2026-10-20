import { useTranslation } from 'react-i18next';
import React, { useEffect, useRef, useState } from 'react';
import { briefingReportsApi } from '../../../services/api';

const MIN_MINUTES = 1;
const MAX_MINUTES = 300;

function formatWait(minutes) {
  if (minutes < 60) return `${minutes} 分钟`;
  const hours = minutes / 60;
  const text = Number.isInteger(hours) ? hours : hours.toFixed(1);
  return `${text} 小时`;
}

export default function BriefingTranscriptQueue() {
  const { t } = useTranslation();
  const [queue, setQueue] = useState(null);
  const [minutes, setMinutes] = useState(2);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const mounted = useRef(true);
  const saveTimer = useRef(null);

  useEffect(() => {
    mounted.current = true;
    briefingReportsApi.transcriptQueue()
      .then(response => {
        if (!mounted.current) return;
        const data = response.data || response;
        setQueue(data);
        setMinutes(Math.round(data.interval_minutes || 2));
      })
      .catch(err => { if (mounted.current) setError(err.message || t('ui.couldNotLoadBriefingSettings')); });
    return () => { mounted.current = false; clearTimeout(saveTimer.current); };
  }, []);

  // 拖动后停 400ms 再保存，避免连续请求
  const change = value => {
    setMinutes(value);
    clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(async () => {
      setSaving(true); setError('');
      try {
        const response = await briefingReportsApi.setTranscriptQueueInterval(value);
        if (mounted.current) setQueue(response.data || response);
      } catch (err) {
        if (mounted.current) setError(err.message || t('ui.couldNotSaveSettingsPleaseRetry'));
      } finally {
        if (mounted.current) setSaving(false);
      }
    }, 400);
  };

  const depth = queue?.queued_count ?? 0;
  const remaining = queue?.pending?.length ? queue.pending[queue.pending.length - 1]?.eta_seconds : null;
  const backlogText = remaining
    ? formatWait(Math.ceil(remaining / 60))
    : `${formatWait(Math.max(MIN_MINUTES, depth * minutes))}`;

  return <section className="br-settings-card" aria-labelledby="br-queue-title">
    <h2 id="br-queue-title">{t('ui.transcriptQueueTitle')}</h2>
    <p>{t('ui.transcriptQueueDescription')}</p>
    <label className="br-queue-slider">
      <span className="br-queue-slider-head">
        <span>{t('ui.transcriptQueueInterval')}</span>
        <strong>{saving ? t('ui.saving') : formatWait(minutes)}</strong>
      </span>
      <input type="range" min={MIN_MINUTES} max={MAX_MINUTES} step={1} value={minutes}
        disabled={saving} aria-label={t('ui.transcriptQueueInterval')}
        onChange={event => change(Number(event.target.value))} />
      <span className="br-queue-slider-scale"><span>{t('ui.transcriptQueueFastest')}</span><span>{t('ui.transcriptQueueSlowest')}</span></span>
    </label>
    <p className="br-settings-save-note">
      {t('ui.transcriptQueueBacklog', { count: depth, duration: backlogText })}
    </p>
    {error && <p className="br-queue-error" role="alert">{error}</p>}
  </section>;
}
