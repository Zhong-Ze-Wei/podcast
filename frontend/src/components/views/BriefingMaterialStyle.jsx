import React from 'react';
import { useTranslation } from 'react-i18next';
import { Check } from 'lucide-react';
import './briefing-materials.css';

export default function BriefingMaterialStyle({ layout = 'gallery', saving, onChange }) {
  const { t } = useTranslation();
  return <section className="br-settings-card bm-style-setting" aria-labelledby="bm-style-title">
    <h2 id="bm-style-title">{t('briefingMaterials.styleTitle')}</h2><p>{t('briefingMaterials.styleDescription')}</p>
    <div className="bm-style-options">{['gallery', 'stack'].map(style => <button key={style} disabled={saving} onClick={() => onChange(style)} aria-pressed={layout === style} className={layout === style ? 'is-active' : ''}>
      <span className={`bm-style-preview bm-preview-${style}`} aria-hidden="true"><i /><i /><i /></span>
      <span className="bm-style-name">{t(`briefingMaterials.${style}`)}{layout === style && <Check size={15} />}</span><span className="bm-style-description">{t(`briefingMaterials.${style}Description`)}</span>
    </button>)}</div><p className="br-settings-save-note">{t('briefingMaterials.savedToAccount')}</p>
  </section>;
}
