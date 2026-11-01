import { localizeUiMessage } from '../../../utils/localization';
import { useTranslation } from 'react-i18next';
import React, { useEffect, useState } from 'react';
import { briefingReportsApi } from '../../../services/api';
import { getBriefingLayouts } from '../../../utils/briefingLayouts';
import BriefingSettings from '../BriefingSettings';
import { SettingsPage } from './SettingsLayout';
import { useStagedSettings } from './SettingsDraft';
import '../briefing-reports.css';
import '../briefing-modes.css';

export default function BriefingPreferencesPanel() {
  const { t } = useTranslation();
  const [preferences, setPreferences] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    briefingReportsApi.preferences()
      .then(response => setPreferences(response.data))
      .catch(err => setError(err.message || t('ui.couldNotLoadBriefingSettings')));
  }, []);

  const { values, change } = useStagedSettings('briefing', {
    interests: preferences?.interests,
    auto_period: preferences?.auto_period,
    layout: preferences?.layout,
    materials_layout: preferences?.materials_layout,
  }, async changes => {
    await briefingReportsApi.savePreferences(changes);
  });

  if (!preferences) {
    return <p role={error ? 'alert' : 'status'} className="text-sm text-zinc-500">{error ? localizeUiMessage(error, t) : t('ui.loadingBriefingSettings')}</p>;
  }

  return (
    <SettingsPage>
      <BriefingSettings
        interests={values.interests || []}
        autoPeriod={values.auto_period}
        error={localizeUiMessage(error, t)}
        onChange={interests => change({ interests })}
        onAutoPeriod={auto_period => change({ auto_period })}
        layout={values.layout}
        layouts={getBriefingLayouts(t)}
        onLayout={layout => change({ layout })}
        materialsLayout={values.materials_layout}
        onMaterialsLayout={materials_layout => change({ materials_layout })}
      />
    </SettingsPage>
  );
}
