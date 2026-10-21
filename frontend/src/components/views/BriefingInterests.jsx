import { localizeUiMessage } from '../../utils/localization';
import { useTranslation } from 'react-i18next';
import React, { useState } from 'react';
import { Check, Plus, X } from 'lucide-react';
import { SaveStatus, SettingGroup, SettingRow } from './settings/SettingsLayout';

export default function BriefingInterests({ interests, autoPeriod, saving, error, onChange, onAutoPeriod }) {
  const { t } = useTranslation();
  const [label, setLabel] = useState('');
  const add = event => {
    event.preventDefault();
    const nextLabel = label.trim();
    if (!nextLabel) return;
    const existing = interests.find(item => item.label.toLowerCase() === nextLabel.toLowerCase());
    if (saving || (!existing && interests.length >= 12)) return;
    onChange(existing ? interests.map(item => item === existing ? { ...item, enabled: true } : item) : [...interests, { label: nextLabel, enabled: true }]);
    setLabel('');
  };
  const periodNote = autoPeriod === 'week'
    ? t('ui.generateLastWeekSReportAfterMonday')
    : autoPeriod === 'month' ? t('ui.generateLastMonthSReportAfter00') : t('ui.afterThePeriodEndsGenerateAllFive');

  return (
    <SettingGroup
      title={t('ui.topicsOfInterest')}
      description={t('ui.interestInAIAlsoIncludesAICompanies')}
      hint={t('ui.changesSaveAutomaticallyAndApplyToThe')}
    >
      <SettingRow stacked>
        <div className="flex flex-wrap gap-2">
          {interests.map(item => (
            <span
              key={item.label}
              className={`inline-flex items-center gap-1 rounded-lg border px-2 py-1 text-xs ${item.enabled ? 'border-indigo-500/50 bg-indigo-500/10 text-indigo-200' : 'border-zinc-700 text-zinc-400'}`}
            >
              <button
                type="button"
                disabled={saving}
                aria-pressed={item.enabled}
                onClick={() => onChange(interests.map(current => current.label === item.label ? { ...current, enabled: !current.enabled } : current))}
                className="inline-flex items-center gap-1 disabled:opacity-50"
              >
                {item.enabled && <Check size={12} />}{item.label}
              </button>
              <button
                type="button"
                disabled={saving}
                aria-label={t('ui.removeInterest', { topic: item.label })}
                onClick={() => onChange(interests.filter(current => current.label !== item.label))}
                className="text-zinc-500 hover:text-zinc-200 disabled:opacity-50"
              >
                <X size={12} />
              </button>
            </span>
          ))}
        </div>
        <form className="mt-3 flex gap-2" onSubmit={add}>
          <input
            aria-label={t('ui.addATopicOrQuestion')}
            placeholder={t('ui.forExampleHowDoesAIChangeWork')}
            maxLength={200}
            value={label}
            onChange={event => setLabel(event.target.value)}
            className="min-w-0 flex-1 rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-200 outline-none placeholder:text-zinc-600 focus:border-indigo-500"
          />
          <button
            type="submit"
            disabled={saving || !label.trim() || interests.length >= 12}
            aria-label={t('ui.addTopic')}
            className="rounded-lg border border-zinc-700 px-3 text-zinc-300 hover:bg-zinc-800 disabled:opacity-40"
          >
            <Plus size={16} />
          </button>
        </form>
      </SettingRow>

      <SettingRow label={t('ui.automaticGeneration')} description={periodNote}>
        <select
          aria-label={t('ui.generateReportsAutomatically')}
          value={autoPeriod || ''}
          disabled={saving}
          onChange={event => onAutoPeriod(event.target.value || null)}
          className="w-40 rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-200 outline-none focus:border-indigo-500"
        >
          <option value="">{t('ui.close')}</option>
          <option value="week">{t('ui.weekly2')}</option>
          <option value="month">{t('ui.monthly2')}</option>
        </select>
      </SettingRow>

      <div className="flex justify-end py-3">
        <SaveStatus saving={saving} error={localizeUiMessage(error, t)} t={t} />
      </div>
    </SettingGroup>
  );
}
