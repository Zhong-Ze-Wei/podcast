import React from 'react';
import { useTranslation } from 'react-i18next';
import { Check } from 'lucide-react';
import { SettingGroup, SettingRow } from './settings/SettingsLayout';
import './briefing-materials.css';

export default function BriefingMaterialStyle({ layout = 'gallery', saving, onChange }) {
  const { t } = useTranslation();
  return (
    <SettingGroup
      title={t('briefingMaterials.styleTitle')}
      description={t('briefingMaterials.styleDescription')}
      hint={t('briefingMaterials.savedToAccount')}
    >
      <SettingRow stacked>
        <div className="bm-style-options">
          {['gallery', 'stack'].map(style => (
            <button
              key={style}
              disabled={saving}
              onClick={() => onChange(style)}
              aria-pressed={layout === style}
              className={layout === style ? 'is-active' : ''}
            >
              <span className={`bm-style-preview bm-preview-${style}`} aria-hidden="true"><i /><i /><i /></span>
              <span className="bm-style-name">{t(`briefingMaterials.${style}`)}{layout === style && <Check size={15} />}</span>
              <span className="bm-style-description">{t(`briefingMaterials.${style}Description`)}</span>
            </button>
          ))}
        </div>
      </SettingRow>
    </SettingGroup>
  );
}
