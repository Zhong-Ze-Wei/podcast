import { localizeUiMessage, formatUiDate } from '../../utils/localization';
import { useTranslation } from 'react-i18next';
import React, { useEffect, useState } from 'react';
import { Loader2, Sparkles } from 'lucide-react';
import { briefingReportsApi } from '../../services/api';
import { useTasks } from '../tasks/TasksContext';
import TaskProgress from '../common/TaskProgress';
import EpisodeAnalysisContent from './EpisodeAnalysisContent';
import BriefingQuotePopover from '../views/BriefingQuotePopover';
import { SourceDrawer } from '../views/BriefingReportsView';

export default function EpisodeAnalysisPanel({ episode, hasTranscript, onPlay, onTranscript }) {
  const { t, i18n } = useTranslation();
  const sourceId = `ep${episode.id}`;
  const tasks = useTasks();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [taskId, setTaskId] = useState(null);
  const [evidence, setEvidence] = useState(null);
  const [sourceSelection, setSourceSelection] = useState(null);
  const activeTask = tasks.activeTasks.find(task => task.report_context?.kind === 'reading' && task.report_context.source_id === sourceId);
  const reading = data?.reading || data?.legacy_reading;
  const working = submitting || Boolean(taskId || activeTask);
  const permission = episode.actions?.summarize?.reason_code;
  const disabledReason = permission === 'ROLE_DENIED' ? t("ui.yourAccountHasReadOnlyAccess")
    : permission === 'AI_ANALYSIS_DISABLED' ? t("ui.aIAnalysisIsDisabledSavedAnalysesRemain")
      : !hasTranscript ? t("ui.getThisEpisodeSTranscriptBeforeAnalyzing") : '';

  const load = async () => {
    setLoading(true); setError('');
    try {
      const response = await briefingReportsApi.reading(sourceId);
      setData(response.data);
    } catch (err) {
      if (err.error_code !== 'SOURCE_NOT_FOUND') setError(err.message || t("ui.couldNotLoadTheAnalysisPleaseRetry"));
    } finally { setLoading(false); }
  };

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    briefingReportsApi.reading(sourceId).then(response => { if (mounted) setData(response.data); }).catch(err => {
      if (mounted && err.error_code !== 'SOURCE_NOT_FOUND') setError(err.message || t("ui.couldNotLoadTheAnalysisPleaseRetry"));
    }).finally(() => { if (mounted) setLoading(false); });
    return () => { mounted = false; };
  }, [sourceId, hasTranscript]);

  useEffect(() => { if (activeTask) setTaskId(activeTask.id); }, [activeTask?.id]);

  const generate = async () => {
    setSubmitting(true); setError('');
    try {
      const response = await briefingReportsApi.generateReading(sourceId, {});
      const id = response.data.task_id;
      setTaskId(id);
      tasks.register({ id, type: 'briefing-report', episode_id: episode.id, episode_title: episode.title, feed_title: episode.feed_title, target_type: 'episode', target_id: episode.id, status: 'pending', progress: 0, report_context: { kind: 'reading', source_id: sourceId } });
      tasks.refresh();
    } catch (err) { setError(err.message || t("ui.couldNotStartAnalysisPleaseRetry")); }
    finally { setSubmitting(false); }
  };

  const listen = quote => onPlay?.(episode, quote.start ?? 0);
  return <section aria-label={t("ui.episodeAIAnalysis")} className="space-y-6">
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div><h2 className="text-xl font-semibold text-zinc-100">{t("ui.whatToTakeAwayFromThisEpisode")}</h2><p className="mt-2 text-sm leading-6 text-zinc-400">{t("ui.readTheFullTranscriptToCaptureTopics")}</p></div>
      {!loading && (!reading || reading.legacy) && <button onClick={generate} disabled={working || Boolean(disabledReason)} className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:cursor-not-allowed disabled:bg-zinc-700">{working ? <Loader2 className="animate-spin" size={16} /> : <Sparkles size={16} />}{reading?.legacy ? t("ui.analyzeFullTranscript") : t("ui.analyzeEpisode")}</button>}
    </header>
    {error && <div role="alert" className="rounded-lg border border-red-900 bg-red-950/20 p-4 text-sm text-red-300">{localizeUiMessage(error, t)}<button onClick={load} className="ml-3 underline">{t("ui.reload")}</button></div>}
    {disabledReason && !reading && <p className="text-sm text-zinc-400">{disabledReason}{!hasTranscript && <button onClick={onTranscript} className="ml-3 text-indigo-300 underline">{t("ui.viewTranscript")}</button>}</p>}
    {(taskId || activeTask) && <TaskProgress taskType="analysis" taskId={taskId || activeTask.id} onComplete={() => { setTaskId(null); load(); }} onError={message => { setTaskId(null); setError(message || t("ui.analysisDidNotFinishYouCanTry")); }} onCancelled={() => setTaskId(null)} />}
    {loading ? <p className="flex items-center gap-2 text-sm text-zinc-400"><Loader2 size={16} className="animate-spin" />{t("ui.loadingSavedAnalysis")}</p> : reading ? <>
      {reading.legacy && <p className="rounded-lg border border-amber-800/40 p-3 text-sm text-amber-200">{t("ui.thisOlderAnalysisWasBasedOnExcerpts")}</p>}
      <EpisodeAnalysisContent reading={reading} onEvidence={setEvidence} onSource={setSourceSelection} />
      <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-zinc-800 pt-4 text-xs text-zinc-500"><span>{reading.legacy ? t("ui.earlierAnalysis") : t("ui.savedReusableInWeeklyAndMonthlyReports")}{reading.generated_at && ` · ${formatUiDate(reading.generated_at, i18n.resolvedLanguage, { dateStyle: 'medium', timeStyle: 'short' })}`}</span><button onClick={onTranscript} className="text-indigo-300">{t("ui.readFullTranscript")}</button></footer>
    </> : !error && <div className="rounded-xl border border-dashed border-zinc-700 p-8 text-center text-sm leading-7 text-zinc-400">{t("ui.thisEpisodeHasNoFullTranscriptAnalysis")}<br />{t("ui.analyzeItOnceThenReadTheSaved")}</div>}
    {evidence && <BriefingQuotePopover selection={evidence} sources={data?.source ? [data.source] : []} onClose={() => setEvidence(null)} onRead={() => setEvidence(null)} onListen={listen} onSource={setSourceSelection} />}
    {sourceSelection && <SourceDrawer selection={sourceSelection} onClose={() => setSourceSelection(null)} onOpenEpisode={onTranscript} onListen={listen} />}
  </section>;
}
