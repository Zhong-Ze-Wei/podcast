import { localizeUiMessage } from '../../utils/localization';
import { useTranslation } from 'react-i18next';
import React, { useState } from 'react';
import { Check, Loader2, Plus, X } from 'lucide-react';

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
  return <section className="br-settings-card br-interests-settings" aria-labelledby="br-interest-title">
    <div className="br-interests-heading"><h2 id="br-interest-title">{t("ui.topicsOfInterest")}</h2>{saving && <Loader2 size={14} className="br-spinning" aria-label={t("ui.savingInterests")} />}</div><div className="br-interest-tags">{interests.map(item => <div className={item.enabled ? 'is-enabled' : ''} key={item.label}><button className="br-interest-toggle" disabled={saving} aria-pressed={item.enabled} onClick={() => onChange(interests.map(current => current.label === item.label ? { ...current, enabled: !current.enabled } : current))}>{item.enabled && <Check size={13} />}{item.label}</button><button className="br-interest-remove" disabled={saving} aria-label={t("ui.removeInterest", { topic: item.label })} onClick={() => onChange(interests.filter(current => current.label !== item.label))}><X size={13} /></button></div>)}</div>
    <form className="br-interest-add" onSubmit={add}><input aria-label={t("ui.addATopicOrQuestion")} placeholder={t("ui.forExampleHowDoesAIChangeWork")} maxLength={200} value={label} onChange={event => setLabel(event.target.value)} /><button className="br-icon-button" type="submit" disabled={saving || !label.trim() || interests.length >= 12} aria-label={t("ui.addTopic")}><Plus size={18} /></button></form>
    <p>{t("ui.addTopicsOrQuestionsYouCareAbout")}</p>
    <p>{t("ui.interestInAIAlsoIncludesAICompanies")}</p>
    <label className="br-auto-period">{t("ui.automaticGeneration")}<select aria-label={t("ui.generateReportsAutomatically")} value={autoPeriod || ''} disabled={saving} onChange={event => onAutoPeriod(event.target.value || null)}><option value="">{t("ui.close")}</option><option value="week">{t("ui.weekly2")}</option><option value="month">{t("ui.monthly2")}</option></select></label><p className="br-auto-period-note">{autoPeriod === 'week' ? t("ui.generateLastWeekSReportAfterMonday") : autoPeriod === 'month' ? t("ui.generateLastMonthSReportAfter00") : t("ui.afterThePeriodEndsGenerateAllFive")}</p>
    {error && <p className="br-interest-error" role="alert">{localizeUiMessage(error, t)}</p>}
    <span className="br-settings-save-note">{saving ? t("ui.saving") : t("ui.changesSaveAutomaticallyAndApplyToThe")}</span>
  </section>;
}
