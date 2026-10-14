import { useTranslation } from 'react-i18next';
import React from 'react';
import BriefingInterests from './BriefingInterests';
import BriefingMaterialStyle from './BriefingMaterialStyle';

export default function BriefingSettings({ interests, autoPeriod, saving, error, onChange, onAutoPeriod, layout, layouts, onLayout, materialsLayout, onMaterialsLayout, onBack }) {
  const { t } = useTranslation();
  return <div className="br-settings">
    <div className="br-settings-intro"><div><h2>{t("ui.interestsBriefing")}</h2><p>{t("ui.setYourReadingInterestsEpisodeWeeklyAnd")}</p></div>{onBack && <button className="br-text-button" onClick={onBack}>{t("ui.backToBriefing")}</button>}</div>
    <div className="br-settings-grid">
      <BriefingInterests interests={interests} autoPeriod={autoPeriod} saving={saving} error={error} onChange={onChange} onAutoPeriod={onAutoPeriod} />
      <section className="br-settings-card" aria-labelledby="br-style-title"><h2 id="br-style-title">{t("ui.readingStyle")}</h2><p>{t("ui.chooseHowTheSameContentIsPresented")}</p><div className="br-style-library">{layouts.map(item => <button key={item.id} disabled={saving} aria-pressed={layout === item.id} className={layout === item.id ? 'is-active' : ''} onClick={() => onLayout(item.id)}><strong>{item.name}</strong><span>{item.description}</span></button>)}</div><p className="br-settings-save-note">{t("ui.readingStyleIsSavedToYourAccount")}</p></section>

      <BriefingMaterialStyle layout={materialsLayout} saving={saving} onChange={onMaterialsLayout} />
    </div>
  </div>;
}
