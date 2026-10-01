import React, { useEffect, useRef, useState } from 'react';
import { briefingReportsApi } from '../../../services/api';
import { BRIEFING_LAYOUTS } from '../../../utils/briefingLayouts';
import BriefingSettings from '../BriefingSettings';
import '../briefing-reports.css';

export default function BriefingPreferencesPanel() {
  const [preferences, setPreferences] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    briefingReportsApi.preferences().then(response => { if (mounted.current) setPreferences(response.data); }).catch(err => { if (mounted.current) setError(err.message || '简报设置暂未加载。'); });
    return () => { mounted.current = false; };
  }, []);
  const save = async changes => {
    setSaving(true); setError('');
    try { const response = await briefingReportsApi.savePreferences(changes); if (mounted.current) setPreferences(response.data); }
    catch (err) { if (mounted.current) setError(err.message || '设置未能保存，请重试。'); }
    finally { if (mounted.current) setSaving(false); }
  };
  return <div className="briefing-reports-view briefing-preferences-panel h-full overflow-y-auto custom-scrollbar p-4 md:p-8">
    {!preferences ? <p role={error ? 'alert' : 'status'}>{error || '正在读取简报设置…'}</p> : <BriefingSettings interests={preferences.interests} autoPeriod={preferences.auto_period} saving={saving} error={error} onChange={interests => save({ interests })} onAutoPeriod={auto_period => save({ auto_period })} layout={preferences.layout} layouts={BRIEFING_LAYOUTS} onLayout={layout => save({ layout })} />}
  </div>;
}
