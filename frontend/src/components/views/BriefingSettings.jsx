import { localizeUiMessage } from '../../utils/localization';
import { useTranslation } from 'react-i18next';
import React from 'react';
import BriefingInterests from './BriefingInterests';
import BriefingMaterialStyle from './BriefingMaterialStyle';
import { SettingGroup, SettingRow } from './settings/SettingsLayout';

export default function BriefingSettings({ interests, autoPeriod, saving, error, onChange, onAutoPeriod, layout, layouts, onLayout, materialsLayout, onMaterialsLayout, onBack }) {
  const { t } = useTranslation();
  return (
    <>
      {onBack && (
        <div className="flex justify-end">
          <button type="button" onClick={onBack} className="text-sm text-zinc-400 hover:text-white">{t('ui.backToBriefing')}</button>
        </div>
      )}

      <BriefingInterests
        interests={interests}
        autoPeriod={autoPeriod}
        saving={saving}
        error={error}
        onChange={onChange}
        onAutoPeriod={onAutoPeriod}
      />

      <SettingGroup
        title={t('ui.readingStyle')}
        description={t('ui.chooseHowTheSameContentIsPresented')}
        hint={t('settings.pendingHint')}
      >
        <SettingRow stacked>
          <div className="br-style-library">
            {layouts.map(item => (
              <button
                key={item.id}
                type="button"
                disabled={saving}
                aria-pressed={layout === item.id}
                className={layout === item.id ? 'is-active' : ''}
                onClick={() => onLayout(item.id)}
              >
                <strong>{item.name}</strong>
                <span>{item.description}</span>
              </button>
            ))}
          </div>
        </SettingRow>
        {error && <p role="alert" className="py-3 text-sm text-red-400">{localizeUiMessage(error, t)}</p>}
      </SettingGroup>

      <BriefingMaterialStyle layout={materialsLayout} saving={saving} onChange={onMaterialsLayout} />
    </>
  );
}
