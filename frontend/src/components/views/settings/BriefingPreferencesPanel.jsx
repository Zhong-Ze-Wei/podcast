import { localizeUiMessage } from '../../../utils/localization';
import { useTranslation } from 'react-i18next';
import React, { useEffect, useRef, useState } from 'react';
import { briefingReportsApi } from '../../../services/api';
import { getBriefingLayouts } from '../../../utils/briefingLayouts';
import BriefingSettings from '../BriefingSettings';
import '../briefing-reports.css';
import '../briefing-modes.css';

export default function BriefingPreferencesPanel() {
  const { t } = useTranslation();
  const [preferences, setPreferences] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    briefingReportsApi.preferences().then(response => { if (mounted.current) setPreferences(response.data); }).catch(err => { if (mounted.current) setError(err.message || t("ui.couldNotLoadBriefingSettings")); });
    return () => { mounted.current = false; };
  }, []);
  const save = async changes => {
    setSaving(true); setError('');
    try { const response = await briefingReportsApi.savePreferences(changes); if (mounted.current) setPreferences(response.data); }
    catch (err) { if (mounted.current) setError(err.message || t("ui.couldNotSaveSettingsPleaseRetry")); }
    finally { if (mounted.current) setSaving(false); }
  };
  return <div className="briefing-preferences-panel h-full overflow-y-auto custom-scrollbar p-4 md:p-8">
    {!preferences ? <p role={error ? 'alert' : 'status'}>{error || t("ui.loadingBriefingSettings")}</p> : <BriefingSettings interests={preferences.interests} autoPeriod={preferences.auto_period} saving={saving} error={localizeUiMessage(error, t)} onChange={interests => save({ interests })} onAutoPeriod={auto_period => save({ auto_period })} layout={preferences.layout} layouts={getBriefingLayouts(t)} onLayout={layout => save({ layout })} materialsLayout={preferences.materials_layout} onMaterialsLayout={materials_layout => save({ materials_layout })} />}
  </div>;
}
