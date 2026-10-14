import { templateDisplayName, localizeUiMessage, formatUiDate, localizedLabel } from '../../utils/localization';
// -*- coding: utf-8 -*-
import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Play, Mic2, AlertCircle, ChevronLeft,
  Sparkles, CheckCircle2, Clock, DollarSign,
  Languages, TrendingUp, AlertTriangle, Quote, Download
} from 'lucide-react';
import { episodesApi, transcriptsApi, summariesApi, promptTemplatesApi } from '../../services/api';
import { decodeHtmlEntities } from '../../utils/helpers';
import TaskProgress from '../common/TaskProgress';
import { useTasks } from '../tasks/TasksContext';
import { getEpisodeTaskId, submitTranscription } from '../../utils/taskMonitor';
import { isActiveTask } from '../../utils/taskActions';
import EpisodeAnalysisPanel from '../briefing/EpisodeAnalysisPanel';

/**
 * EpisodeStatusBadge - 剧集处理状态徽标（标题区，一眼可见）
 */

const EpisodeStatusBadge = ({ status, transcriptSource }) => {
  const { t, i18n } = useTranslation();
  let transcriptLabel = t('status.transcribed');
  if (transcriptSource?.startsWith('official')) transcriptLabel = t('status.officialTranscript');
  else if (['youtube', 'bilibili'].includes(transcriptSource)) transcriptLabel = t('status.platformTranscript');
  else if (['local_whisper', 'local_whisperx', 'assemblyai'].includes(transcriptSource)) transcriptLabel = t('status.audioTranscribed');
  const STATUS_BADGES = {
    new: { label: t("ui.noTranscript"), cls: 'bg-zinc-700/60 text-zinc-300' },
    downloading: { label: t("ui.downloading"), cls: 'bg-blue-500/15 text-blue-300 animate-pulse' },
    downloaded: { label: t("ui.downloaded"), cls: 'bg-blue-500/15 text-blue-300' },
    transcribing: { label: t("ui.transcribing"), cls: 'bg-purple-500/15 text-purple-300 animate-pulse' },
    transcribed: { label: t("ui.transcribed"), cls: 'bg-green-500/15 text-green-300' },
    summarizing: { label: t("ui.summarizing"), cls: 'bg-indigo-500/15 text-indigo-300 animate-pulse' },
    summarized: { label: t("ui.summarized"), cls: 'bg-green-500/15 text-green-300' },
    error: { label: t("ui.error"), cls: 'bg-red-500/15 text-red-300' },
  };
  const badge = STATUS_BADGES[status];
  if (!badge) return null;
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${badge.cls}`}>
      {status === 'transcribed' ? transcriptLabel : badge.label}
    </span>
  );
};

/**
 * EpisodeDetailView - 节目详情页
 *
 * 显示单个节目的详细信息，包括：
 * - 转录内容（带时间戳）
 * - AI生成的摘要
 * - 节目元信息
 */
const EpisodeDetailView = ({ episode: episodeProp, activeTab = 'transcript', onTabChange: setActiveTab, onBack, onRefresh, onPlay }) => {
  const { t, i18n } = useTranslation();
  const [transcript, setTranscript] = useState(null);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [hasExternalTranscript, setHasExternalTranscript] = useState(false);
  const [transcriptLoading, setTranscriptLoading] = useState(true);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // 本地episode状态，用于实时更新
  const [episode, setEpisode] = useState(episodeProp);

  // 任务状态
  const [localTranscribing, setLocalTranscribing] = useState(false);
  const [localSummarizing, setLocalSummarizing] = useState(false);
  const [transcriptionProvider, setTranscriptionProvider] = useState('official');
  const [transcriptionLanguage, setTranscriptionLanguage] = useState('auto');
  const [submittedTaskIds, setSubmittedTaskIds] = useState({});
  const taskStore = useTasks();

  // Summary states
  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [templateBlocks, setTemplateBlocks] = useState([]);
  const [templateParams, setTemplateParams] = useState({ length: '', language: '' });
  const [paramOptions, setParamOptions] = useState({});
  const [enabledBlocks, setEnabledBlocks] = useState([]);
  const [showChinese, setShowChinese] = useState(false);

  // 当props中的episode变化时，更新本地状态
  useEffect(() => {
    setEpisode(episodeProp);
  }, [episodeProp]);

  // 加载模板列表
  useEffect(() => {
    const loadTemplates = async () => {
      try {
        const response = await promptTemplatesApi.list();
        const templateList = response.data?.templates || response.templates || [];
        setTemplates(templateList);
        // 默认选择 learning 模板（学习笔记），如果没有则选第一个；
        // 已有摘要时优先选中生成它的模板，打开即见内容（如"创业与商业分析"）
        if (templateList.length > 0 && !selectedTemplate) {
          let defaultTemplate = templateList.find(t => t.name === 'learning') || templateList[0];
          try {
            const summaryResp = await summariesApi.get(episodeProp.id);
            const existing = summaryResp.data || summaryResp;
            const used = existing?.template_name && templateList.find(t => t.name === existing.template_name);
            if (used) defaultTemplate = used;
          } catch (err) { /* 无已有摘要，走默认模板 */ }
          setSelectedTemplate(defaultTemplate);
          // 获取模板详情以获取 enabled blocks
          const detailResp = await promptTemplatesApi.get(defaultTemplate.id);
          const detail = detailResp.data || detailResp;
          const defaultEnabled = detail.optional_blocks
            ?.filter(b => b.enabled_by_default)
            .map(b => b.id) || [];
          setEnabledBlocks(defaultEnabled);
          setTemplateBlocks(detail.optional_blocks || []);
          setParamOptions(detail.parameters || {});
        }
      } catch (err) {
        console.error('Failed to load templates:', err);
      }
    };
    loadTemplates();
  }, []);

  const transcribeTaskId = getEpisodeTaskId(episode, 'transcribe', submittedTaskIds.transcribe);
  const downloadTaskId = getEpisodeTaskId(episode, 'download', submittedTaskIds.download);
  const summarizeTaskId = getEpisodeTaskId(episode, 'summarize', submittedTaskIds.summarize);
  const taskActive = id => id && (!taskStore.byId[id] || isActiveTask(taskStore.byId[id]));
  const isCurrentlyTranscribing = Boolean(localTranscribing || taskActive(transcribeTaskId));
  const isCurrentlyDownloading = Boolean(taskActive(downloadTaskId));
  const isCurrentlySummarizing = Boolean(localSummarizing || taskActive(summarizeTaskId));
  const aiEnabled = episode?.actions?.summarize?.reason_code !== 'AI_ANALYSIS_DISABLED';
  const canSummarize = Boolean(episode?.actions?.summarize?.allowed);
  const actionReasons = {
    NO_TRANSCRIPT_URL: t('status.noOfficialTranscript'), LOCAL_AI_NOT_INSTALLED: t("ui.localTranscriptionComponentsAreNotInstalled"),
    CLOUD_TRANSCRIPTION_DISABLED: t("ui.cloudTranscriptionIsDisabled"), NO_AUDIO_URL: t("ui.thisEpisodeHasNoAvailableAudio"),
    TASK_IN_PROGRESS: t("ui.aTaskIsAlreadyRunningForThis"), ALREADY_DOWNLOADED: t("ui.audioAlreadyDownloaded"),
    ALREADY_TRANSCRIBED: t("ui.thisEpisodeAlreadyHasATranscript"), NO_TRANSCRIPTION_PROVIDER: t("ui.noTranscriptionMethodIsAvailable"),
    TRANSCRIPT_NOT_FOUND: t("ui.getATranscriptBeforeGeneratingASummary"), AI_ANALYSIS_DISABLED: t("ui.aIAnalysisIsDisabled"),
    ROLE_DENIED: t("ui.yourAccountHasReadOnlyAccessAnd"),
  };
  // 无文稿时的真实原因优先于通用文案：字幕拉取失败原因 / 官网可拉提示
  const transcriptHints = [];
  if (!episode?.has_transcript) {
    if (episode?.transcript_fetch_error) transcriptHints.push(episode.transcript_fetch_error);
    else if (episode?.transcript_url) transcriptHints.push(t("ui.officialTranscriptAvailable"));
  }

  // 计算预估费用 (AssemblyAI: $0.37/小时)
  const estimateCost = episode?.duration ? (episode.duration * 0.37 / 3600).toFixed(2) : null;
  const estimateTime = episode?.duration ? Math.ceil(episode.duration / 60 / 5) : null;
  const hasLocalAudio = Boolean(episode?.artifacts?.local_audio);
  const transcriptionOptions = [
    { value: 'official', label: t('status.officialTranscript'), description: t('status.officialTranscriptHint') },
    { value: 'local_whisper', label: t("ui.localWhisper"), description: hasLocalAudio ? t("ui.transcribeDownloadedAudioOnThisComputer") : t("ui.downloadAudioInTheBackgroundThenTranscribe") },
    { value: 'local_whisperx', label: 'WhisperX', description: hasLocalAudio ? t("ui.useDownloadedAudioForAdvancedLocalTranscription") : t("ui.downloadAudioInTheBackgroundThenTranscribe2") },
    { value: 'assemblyai', label: t("ui.assemblyAICloud"), description: t("ui.transcribeWithTheEnabledPaidCloudService") },
  ].map(option => {
    const provider = episode?.transcription_providers?.find(provider => provider.id === option.value);
    return { ...option, disabled: !provider?.available, description: provider?.reason_code ? actionReasons[provider.reason_code] : option.description };
  });
  const selectedTranscriptionOption =
    transcriptionOptions.find(option => option.value === transcriptionProvider) || transcriptionOptions[0];
  const transcriptSourceLabels = {
    local_whisper: t("ui.localWhisper"),
    local_whisperx: 'WhisperX',
    assemblyai: t("ui.assemblyAICloud"),
    official: t('status.officialTranscript'),
    official_srt: t("ui.officialSRT"),
    official_vtt: t("ui.officialVTT"),
    official_json: t("ui.officialJSON"),
    external: t("ui.externalSubtitles"),
    manual: t("ui.manualImport")
  };
  const transcriptSourceLabel =
    transcriptSourceLabels[transcript?.source] || transcript?.source || episode?.transcript_source || t("ui.unknownSource");
  const transcriptionLanguageOptions = [
    { value: 'auto', label: t("ui.autoDetect"), description: t("ui.useWhenTheLanguageIsUnknownFor") },
    { value: 'zh', label: t("ui.chineseSimplifiedOutput"), description: t("ui.forMandarinChineseInterviewsAndMixedContent") },
    { value: 'en', label: 'English', description: t("ui.forMainlyEnglishEpisodes") },
    { value: 'ja', label: '日本語', description: t("ui.forJapaneseEpisodes") },
    { value: 'ko', label: '한국어', description: t("ui.forKoreanEpisodes") },
  ];
  const selectedLanguageOption =
    transcriptionLanguageOptions.find(option => option.value === transcriptionLanguage) || transcriptionLanguageOptions[0];

  useEffect(() => {
    setSubmittedTaskIds({});
    setLocalTranscribing(false); setLocalSummarizing(false);
    setTranscriptionProvider(episode?.transcription_providers?.find(provider => provider.available)?.id || 'official');
  }, [episode?.id]);

  const rememberTask = (type, data) => {
    setSubmittedTaskIds(current => ({ ...current, [type]: data.task_id }));
    taskStore.register({ id: data.task_id, type, episode_id: episode.id, status: 'pending', progress: 0 });
    taskStore.refresh();
  };

  // 任务完成回调
  const handleTranscribeComplete = async () => {
    setLocalTranscribing(false);
    await loadTranscript();
    await refreshEpisode();
    if (onRefresh) onRefresh();
  };

  const handleDownloadComplete = async () => {

    await refreshEpisode();
    onRefresh?.();
  };

  const handleSummarizeComplete = async () => {
    setLocalSummarizing(false);
    await loadSummary();
    await refreshEpisode();
    if (onRefresh) onRefresh();
  };

  const handleTaskError = async (errorMsg) => {
    setError(errorMsg);

    setLocalTranscribing(false);
    setLocalSummarizing(false);
    await refreshEpisode();
    if (onRefresh) onRefresh();
  };

  const handleTaskCancelled = async () => {

    setLocalTranscribing(false);
    setLocalSummarizing(false);
    setSuccessMsg(t('tasks.status.cancelled'));
    await refreshEpisode();
    onRefresh?.();
  };

  const refreshEpisode = async () => {
    if (!episode?.id) return null;
    try {
      const response = await episodesApi.get(episode.id);
      const refreshedEpisode = response.data || response;
      setEpisode(refreshedEpisode);
      return refreshedEpisode;
    } catch (err) {
      console.error('Failed to refresh episode:', err);
      return null;
    }
  };

  useEffect(() => {
    if (episode?.id) {
      setError(null);
      setSuccessMsg(null);
      loadTranscriptWithAutoFetch();
      loadSummary();
    }
  }, [episode?.id]);

  const loadTranscriptWithAutoFetch = async () => {
    setTranscriptLoading(true);
    try {
      // 1. 先尝试从数据库获取
      const response = await transcriptsApi.get(episode.id);
      setTranscript(response.data);
      setHasExternalTranscript(false);
      setTranscriptLoading(false);
    } catch (err) {
      // 2. 数据库没有时只检查是否有外部转录URL，不自动抓取/创建转录。
      setTranscript(null);
      try {
        const extResponse = await transcriptsApi.checkExternal(episode.id);
        const hasExternal = extResponse.data?.has_external_transcript || false;
        setHasExternalTranscript(hasExternal);
      } catch (extErr) {
        setHasExternalTranscript(false);
      }
      setTranscriptLoading(false);
    }
  };

  const loadTranscript = async () => {
    try {
      const response = await transcriptsApi.get(episode.id);
      setTranscript(response.data);
    } catch (err) {
      setTranscript(null);
    }
  };

  const loadSummary = async (templateName = null) => {
    try {
      const name = templateName || selectedTemplate?.name || 'learning';
      const response = await summariesApi.get(episode.id, { template_name: name });
      setSummary(response.data);
      setShowChinese(false);
    } catch (err) {
      setSummary(null);
    }
  };

  const startTranscriptionTask = async (provider) => {
    setLoading(true);
    setLocalTranscribing(true);
    setError(null);
    try {
      const task = await submitTranscription(episode.id, provider, transcriptionLanguage, transcriptsApi.create);
      rememberTask('transcribe', task);
      // 任务已提交，TaskProgress 组件会轮询状态
      if (onRefresh) onRefresh();
      return true;
    } catch (err) {
      console.error('Failed to generate transcript:', err);
      setLocalTranscribing(false);
      const errorCode = err?.error_code || err?.code || '';
      const errorMsg = err?.message || 'Failed to generate transcript';
      if (errorCode === 'ALREADY_TRANSCRIBING' || errorCode === 'TASK_IN_PROGRESS') {
        setError(t('detail.alreadyTranscribing') || 'Transcription is already in progress');
        await refreshEpisode();
      } else if (errorCode === 'ALREADY_TRANSCRIBED') {
        setError(t('detail.alreadyTranscribed') || 'Episode already has a transcript');
        await loadTranscript();
        setLocalTranscribing(false);
      } else {
        setError(errorMsg);
        setLocalTranscribing(false);
      }
      return false;
    } finally {
      setLoading(false);
    }
  };

  const generateTranscript = async () => {
    if (!episode.actions.transcribe.allowed) {
      setError(actionReasons[episode.actions.transcribe.reason_code]);
      return;
    }
    if (selectedTranscriptionOption?.disabled) {
      setError(selectedTranscriptionOption.description);
      return;
    }

    await startTranscriptionTask(transcriptionProvider);
  };

  const deleteTranscript = async () => {
    setError(null);
    try {
      await transcriptsApi.delete(episode.id);
      setTranscript(null);
      if (onRefresh) onRefresh();
    } catch (err) {
      setError(err?.message || 'Failed to delete transcript');
    }
  };

  const isVideoEpisode = episode?.guid?.startsWith('youtube:') || episode?.guid?.startsWith('bilibili:');

  const transcribeVideoNow = async () => {
    setError(null);
    setLocalTranscribing(true);
    try {
      const response = await transcriptsApi.transcribeVideo(episode.id);
      rememberTask('transcribe', response.data);
    } catch (err) {
      setError(err?.message || 'Failed to start transcription');
      setLocalTranscribing(false);
    }
  };

  const generateSummary = async (force = false) => {
    if (!canSummarize) {
      setError(actionReasons[episode.actions.summarize.reason_code]);
      return;
    }
    if (!selectedTemplate) {
      setError('Please select a template first');
      return;
    }
    setLoading(true);
    setLocalSummarizing(true);
    setError(null);
    try {
      const params = {};
      if (templateParams.length) params.length = templateParams.length;
      if (templateParams.language) params.language = templateParams.language;
      const summaryResponse = await summariesApi.create(episode.id, {
        template_name: selectedTemplate.name,
        enabled_blocks: enabledBlocks,
        params,
        force
      });
      rememberTask('summarize', summaryResponse.data);
      setSuccessMsg(t('detail.summaryStarted') || 'Summary generation started');
      setTimeout(() => setSuccessMsg(null), 3000);
      if (onRefresh) onRefresh();
      // 任务已提交，TaskProgress 组件会轮询状态
    } catch (err) {
      console.error('Failed to generate summary:', err);
      // 拦截器 reject 的是后端响应体，错误码在 error_code 字段
      const errorCode = err?.error_code || err?.code || '';
      if (errorCode === 'SUMMARY_EXISTS' && !force) {
        await loadSummary();
        setLocalSummarizing(false);
      } else if (errorCode === 'TASK_IN_PROGRESS') {
        setLocalSummarizing(false);
        await refreshEpisode();
        setError(t('detail.summaryInProgress') || 'Summary generation in progress');
      } else {
        setError(err?.message || 'Failed to generate summary');
        setLocalSummarizing(false);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleTemplateChange = async (template) => {
    setSelectedTemplate(template);
    setSummary(null);
    setShowChinese(false);
    setTemplateParams({ length: '', language: '' });
    // 获取模板详情并设置默认启用的块与参数选项
    try {
      const response = await promptTemplatesApi.get(template.id);
      const detail = response.data || response;
      const defaultEnabled = detail.optional_blocks
        ?.filter(b => b.enabled_by_default)
        .map(b => b.id) || [];
      setEnabledBlocks(defaultEnabled);
      setTemplateBlocks(detail.optional_blocks || [])
          setParamOptions(detail.parameters || {});
    } catch (err) {
      console.error('Failed to load template detail:', err);
    }
    await loadSummary(template.name);
  };

  const toggleBlock = (blockId) => {
    setEnabledBlocks(prev =>
      prev.includes(blockId)
        ? prev.filter(id => id !== blockId)
        : [...prev, blockId]
    );
  };

  const tabLabels = {
    transcript: t('detail.transcript'),
    analysis: t("ui.aIAnalysis"),
    summary: t("ui.templateSummary"),
    info: t('detail.info')
  };

  if (!episode) return null;

  return (
    <div className="flex flex-col h-full bg-zinc-950 text-zinc-100 overflow-hidden animate-in">
      <div className="px-4 md:px-8 py-6 border-b border-zinc-800 flex items-start gap-4 md:gap-6 bg-zinc-900/20">
        <button onClick={onBack} aria-label={t("ui.backToPreviousPage")} className="mt-1 p-2 hover:bg-zinc-800 rounded-full transition-colors text-zinc-400 hover:text-white">
          <ChevronLeft size={24} />
        </button>
        <div className="flex-1 min-w-0">
          <div className="episode-header-meta flex items-center gap-3 mb-2">
            <span className="text-indigo-400 text-sm font-semibold tracking-wide uppercase">
              {episode.feed_title || episode.feed?.title}
            </span>
            <span className="w-1 h-1 rounded-full bg-zinc-700"></span>
            <span className="text-zinc-500 text-sm">{formatUiDate(episode.published_at, i18n.resolvedLanguage)}</span>
            <EpisodeStatusBadge status={episode.status} transcriptSource={transcript?.source || episode.transcript_source} />
          </div>
          <h1 className="text-xl md:text-3xl font-bold text-white mb-4 leading-tight max-w-4xl">{episode.title}</h1>
          <div className="flex flex-wrap items-center gap-3 md:gap-4">
            <button
              onClick={() => onPlay && onPlay(episode)}
              className="flex items-center gap-2 bg-white text-black px-6 py-2.5 rounded-full font-semibold hover:scale-105 transition-transform shadow-lg shadow-white/10"
            >
              <Play size={18} fill="currentColor" stroke="none" /> {t('detail.playEpisode')}
            </button>
            <div className="flex gap-2">
              <button
                onClick={generateTranscript}
                aria-label={transcriptionProvider === 'official' ? t('status.fetchOfficialTranscript') : t('detail.generateTranscript')}
                disabled={!episode.actions?.transcribe?.allowed || loading || isCurrentlyTranscribing || isCurrentlyDownloading || selectedTranscriptionOption?.disabled}
                className={`p-2.5 rounded-full border transition-colors ${
                  isCurrentlyTranscribing
                    ? 'border-purple-500 bg-purple-900/30 text-purple-400 cursor-not-allowed'
                    : 'border-zinc-700 hover:bg-zinc-800 text-zinc-400 hover:text-white'
                }`}
                title={!episode.actions?.transcribe?.allowed ? actionReasons[episode.actions?.transcribe?.reason_code] : isCurrentlyDownloading ? t("ui.downloadingAudio") : (isCurrentlyTranscribing ? t('detail.transcribingStatus') : transcriptionProvider === 'official' ? t('status.fetchOfficialTranscript') : t('detail.generateTranscript'))}
              >
                {isCurrentlyDownloading ? (
                  <div className="animate-spin"><Download size={20} /></div>
                ) : isCurrentlyTranscribing ? (
                  <div className="animate-spin"><Mic2 size={20} /></div>
                ) : (
                  <Mic2 size={20} />
                )}
              </button>
              <button
                onClick={generateSummary}
                aria-label={t('detail.generateSummary')}
                disabled={!canSummarize || loading || isCurrentlySummarizing}
                className={`p-2.5 rounded-full border transition-colors ${
                  isCurrentlySummarizing
                    ? 'border-indigo-500 bg-indigo-900/30 text-indigo-400 cursor-not-allowed'
                    : !aiEnabled
                      ? 'border-zinc-800 text-zinc-600 cursor-not-allowed'
                      : 'border-zinc-700 hover:bg-zinc-800 text-zinc-400 hover:text-white'
                }`}
                title={!canSummarize ? actionReasons[episode.actions?.summarize?.reason_code] : (isCurrentlySummarizing ? t('detail.summarizingStatus') : t('detail.generateSummary'))}
              >
                {isCurrentlySummarizing ? (
                  <div className="animate-spin"><Sparkles size={20} /></div>
                ) : (
                  <Sparkles size={20} />
                )}
              </button>
            </div>
          </div>
          {[
            ...transcriptHints,
            ...Array.from(new Set([episode.actions?.transcribe?.reason_code, episode.actions?.summarize?.reason_code].filter(reason => reason && reason !== 'ALREADY_TRANSCRIBED').map(reason => actionReasons[reason])))
              .filter(message => !(transcriptHints.length > 0 && message === t("ui.getATranscriptBeforeGeneratingASummary"))),
          ].map(message => <p key={message} className="mt-2 text-xs text-zinc-500">{message}</p>)}
        </div>
      </div>

      <div className="px-4 md:px-8 border-b border-zinc-800 flex items-center gap-4 md:gap-8 bg-zinc-950/50 backdrop-blur sticky top-0 z-10 overflow-x-auto">
        {['transcript', 'analysis', 'summary', 'info'].map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`py-4 text-sm font-medium border-b-2 transition-colors capitalize ${
              activeTab === tab
                ? 'border-indigo-500 text-indigo-400'
                : 'border-transparent text-zinc-500 hover:text-zinc-300'
            }`}
          >
            {tabLabels[tab]}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto custom-scrollbar p-8 bg-zinc-950">
        <div className="max-w-4xl mx-auto">
          {activeTab === 'transcript' && (
            <div className="space-y-6">
              {/* 有转录时显示删除/重新转录按钮 */}
              {transcript && !transcriptLoading && !isCurrentlyTranscribing && (
                <div className="flex items-start justify-between gap-4 rounded-lg border border-zinc-800 bg-zinc-900/50 px-4 py-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2 text-sm">
                      <span className="font-medium text-zinc-200">{transcriptSourceLabel}</span>
                      {transcript.model && (
                        <span className="rounded-full border border-zinc-700 px-2 py-0.5 text-xs text-zinc-400">
                          {transcript.model}
                        </span>
                      )}
                      {transcript.language && (
                        <span className="rounded-full border border-zinc-700 px-2 py-0.5 text-xs text-zinc-400">
                          {transcript.language}
                        </span>
                      )}
                    </div>
                    <div className="mt-1 flex flex-wrap gap-3 text-xs text-zinc-500">
                      {typeof transcript.word_count === 'number' && <span>{transcript.word_count} {t("ui.words")}</span>}
                      {Array.isArray(transcript.segments) && <span>{transcript.segments.length} {t("ui.segments")}</span>}
                      {transcript.created_at && <span>{formatUiDate(transcript.created_at, i18n.resolvedLanguage, { dateStyle: 'medium', timeStyle: 'short' })}</span>}
                    </div>
                  </div>
                  <button
                    onClick={deleteTranscript}
                    className="flex-shrink-0 px-3 py-1.5 text-xs bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-red-400 rounded-lg transition-colors border border-zinc-700"
                    title={t("ui.deleteTranscriptAndRegenerate")}
                  > {t("ui.deleteTranscript")} </button>
                </div>
              )}
              {transcriptLoading || loading ? (
                <div className="flex flex-col items-center justify-center py-20 text-zinc-500">
                  <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-500 mb-4"></div>
                  <p className="text-lg font-medium">{loading ? t('detail.generating') : t('common.loading')}</p>
                </div>
              ) : transcript?.segments && transcript.segments.length > 0 ? (
                transcript.segments.map((seg, idx) => {
                  // 计算时间显示 (支持 time 或 start 字段)
                  const timeInSeconds = seg.time ?
                    (typeof seg.time === 'string' ? seg.time : Math.floor(seg.time)) :
                    (seg.start ? Math.floor(seg.start) : 0);
                  const timeDisplay = typeof timeInSeconds === 'string' ?
                    timeInSeconds :
                    `${Math.floor(timeInSeconds / 60)}:${String(timeInSeconds % 60).padStart(2, '0')}`;

                  // 说话人标签颜色
                  const speakerColors = {
                    'A': 'bg-blue-500/20 text-blue-400 border-blue-500/30',
                    'B': 'bg-green-500/20 text-green-400 border-green-500/30',
                    'C': 'bg-purple-500/20 text-purple-400 border-purple-500/30',
                    'D': 'bg-orange-500/20 text-orange-400 border-orange-500/30',
                  };
                  const speakerColor = speakerColors[seg.speaker] || 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30';

                  return (
                    <div key={idx} className="flex gap-4 group hover:bg-zinc-900/30 p-3 rounded-lg transition-colors -mx-2">
                      <div className="flex flex-col items-center gap-1 flex-shrink-0 w-20">
                        <span className="text-xs text-zinc-600 font-mono select-none group-hover:text-zinc-500">
                          {timeDisplay}
                        </span>
                        {seg.speaker && (
                          <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${speakerColor}`}>
                            {seg.speaker}
                          </span>
                        )}
                      </div>
                      <p className="text-zinc-300 leading-relaxed text-base selection:bg-indigo-500/30 flex-1">{seg.text}</p>
                    </div>
                  );
                })
              ) : transcript?.text ? (
                <div>
                  <div className="mb-3 flex items-center gap-2">
                    {transcript.source === 'bilibili' && (
                      <span className="rounded-full bg-pink-500/15 px-2.5 py-0.5 text-[11px] font-medium text-pink-300"> {t("ui.bilibiliAISubtitlesContentVerified")} </span>
                    )}
                    {transcript.source === 'youtube' && (
                      <span className="rounded-full bg-red-500/15 px-2.5 py-0.5 text-[11px] font-medium text-red-300"> {t("ui.youTubeSubtitles")} </span>
                    )}
                    {(transcript.source === 'local_whisperx' || transcript.source === 'whisper') && (
                      <span className="rounded-full bg-purple-500/15 px-2.5 py-0.5 text-[11px] font-medium text-purple-300"> {t("ui.localWhisperTranscription")}{transcript.segments?.some(s => s.speaker) ? t("ui.includesSpeakerDiarization") : ''}
                      </span>
                    )}
                  </div>
                  <div className="prose prose-invert max-w-none">
                    <p className="text-zinc-300 leading-relaxed text-lg whitespace-pre-wrap">{transcript.text}</p>
                  </div>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-20 text-zinc-500 border-2 border-dashed border-zinc-800 rounded-2xl">
                  <Mic2 size={48} className="mb-4 text-zinc-700" />
                  <p className="text-lg font-medium mb-4">{t('detail.noTranscript')}</p>

                  {isVideoEpisode && !localTranscribing && (
                    <div className="mb-6 flex flex-col items-center gap-3">
                      <p role="status" className="text-sm text-zinc-500">{t('common.fetchUnavailable')}</p>
                      <button
                        onClick={transcribeVideoNow}
                        className="rounded-md border border-zinc-700 px-3 py-1.5 text-xs font-medium text-zinc-300 hover:bg-zinc-800"
                      >
                        {t('detail.transcribeVideoNow')}
                      </button>
                    </div>
                  )}

                  {/* 显示错误信息 */}
                  {error && (
                    <div className="flex items-center gap-2 text-red-400 mb-4 px-4 py-2 bg-red-900/20 rounded-lg border border-red-800/50">
                      <AlertCircle size={16} />
                      <span className="text-sm">{localizeUiMessage(error, t)}</span>
                    </div>
                  )}

                  {/* 显示成功消息 */}
                  {successMsg && (
                    <div className="flex items-center gap-2 text-green-400 mb-4 px-4 py-2 bg-green-900/20 rounded-lg border border-green-800/50">
                      <CheckCircle2 size={16} />
                      <span className="text-sm">{localizeUiMessage(successMsg, t)}</span>
                    </div>
                  )}

                  <div className="flex flex-col gap-3 items-center">
                    {isCurrentlyDownloading ? (
                      <TaskProgress
                        taskType="download"
                        taskId={downloadTaskId}
                        onComplete={handleDownloadComplete}
                        onError={handleTaskError}
                        onCancelled={handleTaskCancelled}
                      />
                    ) : isCurrentlyTranscribing ? (
                      <TaskProgress
                        taskType="transcribe"
                        taskId={transcribeTaskId}
                        onComplete={handleTranscribeComplete}
                        onError={handleTaskError}
                        onCancelled={handleTaskCancelled}
                      />
                    ) : (
                      <div className="flex flex-col items-center gap-3">
                        <div className="w-full max-w-md rounded-lg border border-zinc-800 bg-zinc-900/60 p-3">
                          <div className="flex items-center justify-between gap-3 mb-2">
                            <label htmlFor="transcription-provider" className="text-xs font-medium text-zinc-300"> {t("ui.transcriptionMethod")} </label>
                            {transcriptionProvider === 'assemblyai' && (
                              <span className="text-[11px] text-amber-400">{t("ui.paidCloud")}</span>
                            )}
                          </div>
                          <select
                            id="transcription-provider"
                            value={transcriptionProvider}
                            onChange={(event) => {
                              setTranscriptionProvider(event.target.value);
                              setError(null);
                            }}
                            className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-indigo-500"
                          >
                            {transcriptionOptions.map(option => (
                              <option key={option.value} value={option.value} disabled={option.disabled}>
                                {option.label}
                              </option>
                            ))}
                          </select>
                          <p className="mt-2 text-xs leading-relaxed text-zinc-500">
                            {selectedTranscriptionOption?.description}
                          </p>
                        </div>
                        <div className="w-full max-w-md rounded-lg border border-zinc-800 bg-zinc-900/60 p-3">
                          <div className="flex items-center justify-between gap-3 mb-2">
                            <label htmlFor="transcription-language" className="text-xs font-medium text-zinc-300"> {t("ui.transcriptionLanguage")} </label>
                            {transcriptionLanguage === 'zh' && (
                              <span className="text-[11px] text-emerald-400">{t("ui.normalizeChineseSpacingAndScript")}</span>
                            )}
                          </div>
                          <select
                            id="transcription-language"
                            value={transcriptionLanguage}
                            onChange={(event) => {
                              setTranscriptionLanguage(event.target.value);
                              setError(null);
                            }}
                            className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-indigo-500"
                          >
                            {transcriptionLanguageOptions.map(option => (
                              <option key={option.value} value={option.value}>
                                {option.label}
                              </option>
                            ))}
                          </select>
                          <p className="mt-2 text-xs leading-relaxed text-zinc-500">
                            {selectedLanguageOption.description}
                          </p>
                        </div>
                        {/* 预估费用和时间 */}
                        {transcriptionProvider === 'assemblyai' && (estimateCost || estimateTime) && (
                          <div className="flex items-center gap-4 text-xs text-zinc-500 mb-2">
                            {estimateCost && (
                              <span className="flex items-center gap-1">
                                <DollarSign size={12} />
                                ~${estimateCost}
                              </span>
                            )}
                            {estimateTime && (
                              <span className="flex items-center gap-1">
                                <Clock size={12} />
                                ~{estimateTime} {t('ui.minutes')}
                              </span>
                            )}
                          </div>
                        )}
                        <button
                          onClick={generateTranscript}
                          disabled={!episode.actions?.transcribe?.allowed || loading || isCurrentlyTranscribing || isCurrentlyDownloading || selectedTranscriptionOption?.disabled}
                          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-zinc-700 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition-colors"
                        >
                          {isCurrentlyDownloading ? t("ui.downloadingAudio") :
                           isCurrentlyTranscribing ? t('detail.transcribingStatus') :
                           loading ? t('detail.generating') :
                           transcriptionProvider === 'official' ? t('status.fetchOfficialTranscript') :
                            (transcriptionProvider === 'local_whisper' || transcriptionProvider === 'local_whisperx') && !hasLocalAudio ? t("ui.downloadAndTranscribe") : t("ui.startValue", { value1: selectedTranscriptionOption?.label || t("ui.transcription") })}
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'analysis' && (
            <EpisodeAnalysisPanel key={episode.id} episode={episode} hasTranscript={Boolean(transcript || episode.has_transcript || episode.artifacts?.transcript)} onPlay={onPlay} onTranscript={() => setActiveTab('transcript')} />
          )}

          {activeTab === 'summary' && (
            <div className="space-y-6 animate-in">
              {/* Template Selector & Actions */}
              <div className="flex items-center justify-between flex-wrap gap-3">
                <div className="flex gap-2 flex-wrap">
                  {templates.map(template => (
                    <button
                      key={template.id}
                      onClick={() => handleTemplateChange(template)}
                      className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                        selectedTemplate?.id === template.id
                          ? 'bg-indigo-600 text-white'
                          : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-200'
                      }`}
                    >
                      <span className="flex items-center gap-2">
                        {template.name === 'investment' ? <TrendingUp size={14} /> : <Sparkles size={14} />}
                        {templateDisplayName(template, t)}
                      </span>
                    </button>
                  ))}
                </div>

                  {/* 参数快捷调节（覆盖模板默认） */}
                  {paramOptions.length && (
                    <div className="mt-3 flex flex-wrap items-center gap-4">
                      <label className="flex items-center gap-2 text-xs text-zinc-400">
                        {localizedLabel(paramOptions.length, i18n.resolvedLanguage) || t("ui.summaryLength")}
                        <select
                          value={templateParams.length}
                          onChange={(e) => setTemplateParams(prev => ({ ...prev, length: e.target.value }))}
                          className="rounded-md border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-xs text-zinc-200 outline-none focus:border-indigo-500"
                        >
                          <option value="">{t("ui.useTemplateDefault")}</option>
                          {(paramOptions.length.options || []).map(o => (
                            <option key={o.value} value={o.value}>{localizedLabel(o, i18n.resolvedLanguage)}</option>
                          ))}
                        </select>
                      </label>
                      {paramOptions.language && (
                        <label className="flex items-center gap-2 text-xs text-zinc-400">
                          {localizedLabel(paramOptions.language, i18n.resolvedLanguage) || t("ui.outputLanguage")}
                          <select
                            value={templateParams.language}
                            onChange={(e) => setTemplateParams(prev => ({ ...prev, language: e.target.value }))}
                            className="rounded-md border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-xs text-zinc-200 outline-none focus:border-indigo-500"
                          >
                            <option value="">{t("ui.useTemplateDefault")}</option>
                            {(paramOptions.language.options || []).map(o => (
                              <option key={o.value} value={o.value}>{localizedLabel(o, i18n.resolvedLanguage)}</option>
                            ))}
                          </select>
                        </label>
                      )}
                    </div>
                  )}
                <div className="flex gap-2">
                  {/* 有摘要时显示强制重新生成按钮 */}
                  {summary && !isCurrentlySummarizing && (
                    <button
                      onClick={() => generateSummary(true)}
                      disabled={!aiEnabled || loading}
                      className="flex items-center gap-1 px-3 py-1.5 text-sm bg-zinc-800 hover:bg-zinc-700 disabled:bg-zinc-900 disabled:text-zinc-600 text-zinc-400 hover:text-white rounded-lg transition-colors"
                      title={aiEnabled ? t("ui.regenerateIgnoreCache") : t("ui.aIAnalysisDisabled")}
                    >
                      <Sparkles size={13} />
                      {aiEnabled ? t("ui.regenerate") : t("ui.disabled2")}
                    </button>
                  )}
                  {/* 有翻译时显示语言切换 */}
                  {summary?.has_translation && (
                    <button
                      onClick={() => setShowChinese(!showChinese)}
                      className={`flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg transition-colors ${
                        showChinese ? 'bg-green-600 text-white' : 'bg-zinc-800 hover:bg-zinc-700 text-zinc-300'
                      }`}
                    >
                      <Languages size={14} />
                      {showChinese ? 'EN' : 'CN'}
                    </button>
                  )}
                </div>
              </div>

              {/* Block Toggles */}
              {templateBlocks.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {templateBlocks.map(block => (
                    <button
                      key={block.id}
                      onClick={() => toggleBlock(block.id)}
                      className={`px-3 py-1 rounded-full text-xs font-medium transition-colors border ${
                        enabledBlocks.includes(block.id)
                          ? 'bg-indigo-600/30 text-indigo-300 border-indigo-500/50'
                          : 'bg-zinc-900 text-zinc-500 border-zinc-700 hover:border-zinc-500 hover:text-zinc-300'
                      }`}
                    >
                      {block.name_zh || block.name}
                    </button>
                  ))}
                </div>
              )}

              {/* Error/Success Messages */}
              {error && (
                <div className="flex items-center gap-2 text-red-400 px-4 py-2 bg-red-900/20 rounded-lg border border-red-800/50">
                  <AlertCircle size={16} />
                  <span className="text-sm">{localizeUiMessage(error, t)}</span>
                </div>
              )}
              {successMsg && (
                <div className="flex items-center gap-2 text-green-400 px-4 py-2 bg-green-900/20 rounded-lg border border-green-800/50">
                  <CheckCircle2 size={16} />
                  <span className="text-sm">{localizeUiMessage(successMsg, t)}</span>
                </div>
              )}

              {summary?.tldr || summary?.investment_signals ? (
                <>
                  {/* TL;DR */}
                  <div className="bg-gradient-to-br from-indigo-900/20 to-purple-900/20 p-6 rounded-2xl border border-indigo-500/20">
                    <h3 className="text-indigo-300 font-semibold mb-3 flex items-center gap-2">
                      <Sparkles size={18} /> {t('detail.tldr')}
                    </h3>
                    <p className="text-lg text-zinc-200 leading-relaxed font-light">
                      {showChinese && summary.content_zh?.tldr_zh ? summary.content_zh.tldr_zh : summary.tldr}
                    </p>
                  </div>

                  {/* Investment Signals (for investment template) */}
                  {summary.template_name === 'investment' && summary.investment_signals?.length > 0 && (
                    <div>
                      <h3 className="text-zinc-400 font-semibold uppercase tracking-wider text-xs mb-4 flex items-center gap-2">
                        <TrendingUp size={14} /> {t('detail.investmentSignals') || 'Investment Signals'}
                      </h3>
                      <div className="space-y-3">
                        {(showChinese && summary.content_zh?.investment_signals_zh
                          ? summary.content_zh.investment_signals_zh
                          : summary.investment_signals
                        ).map((signal, i) => (
                          <div key={i} className="p-4 bg-zinc-900/50 rounded-xl border border-zinc-800/50">
                            <div className="flex items-center gap-3 mb-2">
                              <span className={`px-2 py-1 rounded text-xs font-bold ${
                                (signal.type || signal.type_zh) === 'bullish' || signal.type_zh === t("ui.bullish") ? 'bg-green-500/20 text-green-400' :
                                (signal.type || signal.type_zh) === 'bearish' || signal.type_zh === t("ui.bearish") ? 'bg-red-500/20 text-red-400' :
                                'bg-yellow-500/20 text-yellow-400'
                              }`}>
                                {(signal.type_zh || signal.type)?.toUpperCase()}
                              </span>
                              <span className="font-semibold text-white">{signal.target_zh || signal.target}</span>
                              {(signal.confidence_zh || signal.confidence) && (
                                <span className="text-xs text-zinc-500">{signal.confidence_zh || signal.confidence}</span>
                              )}
                            </div>
                            <p className="text-zinc-300 text-sm">{signal.reason_zh || signal.reason}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Mentioned Tickers */}
                  {summary.mentioned_tickers?.length > 0 && (
                    <div>
                      <h3 className="text-zinc-400 font-semibold uppercase tracking-wider text-xs mb-3">
                        {t('detail.mentionedTickers') || 'Mentioned Tickers'}
                      </h3>
                      <div className="flex flex-wrap gap-2">
                        {summary.mentioned_tickers.map((ticker, i) => (
                          <span key={i} className="px-3 py-1 bg-blue-500/20 text-blue-400 rounded-full text-sm font-mono">
                            ${ticker}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Key Quotes */}
                  {summary.key_quotes?.length > 0 && (
                    <div>
                      <h3 className="text-zinc-400 font-semibold uppercase tracking-wider text-xs mb-4 flex items-center gap-2">
                        <Quote size={14} /> {t('detail.keyQuotes') || 'Key Quotes'}
                      </h3>
                      <div className="space-y-3">
                        {(showChinese && summary.content_zh?.key_quotes_zh
                          ? summary.content_zh.key_quotes_zh
                          : summary.key_quotes
                        ).slice(0, 3).map((quote, i) => (
                          <blockquote key={i} className="border-l-2 border-indigo-500 pl-4 py-2 text-zinc-300 italic">
                            "{typeof quote === 'string' ? quote : (quote.quote_zh || quote.quote)}"
                          </blockquote>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Risk Alerts */}
                  {summary.risk_alerts?.length > 0 && (
                    <div>
                      <h3 className="text-zinc-400 font-semibold uppercase tracking-wider text-xs mb-4 flex items-center gap-2">
                        <AlertTriangle size={14} /> {t('detail.riskAlerts') || 'Risk Alerts'}
                      </h3>
                      <div className="space-y-2">
                        {(showChinese && summary.content_zh?.risk_alerts_zh
                          ? summary.content_zh.risk_alerts_zh
                          : summary.risk_alerts
                        ).map((risk, i) => (
                          <div key={i} className="flex items-start gap-2 p-3 bg-red-900/10 rounded-lg border border-red-800/30">
                            <AlertTriangle size={16} className="text-red-400 mt-0.5 flex-shrink-0" />
                            <span className="text-zinc-300 text-sm">{typeof risk === 'string' ? risk : (risk.alert_zh || risk.alert)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Key Points (for general type) */}
                  {summary.key_points?.length > 0 && (
                    <div>
                      <h3 className="text-zinc-400 font-semibold uppercase tracking-wider text-xs mb-4">{t('detail.keyTakeaways')}</h3>
                      <ul className="space-y-3">
                        {(showChinese && summary.content_zh?.key_points_zh
                          ? summary.content_zh.key_points_zh
                          : summary.key_points
                        ).map((point, i) => (
                          <li key={i} className="flex gap-3 items-start p-4 bg-zinc-900/50 rounded-xl border border-zinc-800/50">
                            <span className="w-6 h-6 rounded-full bg-indigo-500/20 text-indigo-400 flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">
                              {i + 1}
                            </span>
                            <span className="text-zinc-300">{point}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Debug Info - 临时调试用 */}
                  {/* Core Content */}
                  {summary?.core_content && (
                    <div>
                      <h3 className="text-zinc-400 font-semibold uppercase tracking-wider text-xs mb-3">
                        {t('detail.coreContent') || t("ui.coreContent")}
                      </h3>
                      <p className="text-zinc-300 leading-relaxed">{summary.core_content}</p>
                    </div>
                  )}

                  {/* Guest Background */}
                  {summary.guest_background && summary.guest_background !== "No specific guest is interviewed in this transcript." && (
                    <div>
                      <h3 className="text-zinc-400 font-semibold uppercase tracking-wider text-xs mb-3">
                        {t('detail.guestBackground') || t("ui.guestBackground")}
                      </h3>
                      <p className="text-zinc-300 leading-relaxed">{summary.guest_background}</p>
                    </div>
                  )}

                  {/* Unique Insights */}
                  {summary.unique_insights?.length > 0 && (
                    <div>
                      <h3 className="text-zinc-400 font-semibold uppercase tracking-wider text-xs mb-4">
                        {t('detail.uniqueInsights') || t("ui.distinctiveInsights")}
                      </h3>
                      <div className="space-y-3">
                        {summary.unique_insights.map((insight, i) => (
                          <div key={i} className="flex gap-3 items-start p-4 bg-zinc-900/50 rounded-xl border border-zinc-800/50">
                            <span className="w-6 h-6 rounded-full bg-purple-500/20 text-purple-400 flex items-center justify-center text-xs font-bold flex-shrink-0">
                              {i + 1}
                            </span>
                            <span className="text-zinc-300">{insight}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Action Items */}
                  {summary.action_items?.length > 0 && (
                    <div>
                      <h3 className="text-zinc-400 font-semibold uppercase tracking-wider text-xs mb-4">
                        {t('detail.actionItems') || t("ui.actionItems")}
                      </h3>
                      <ul className="space-y-2">
                        {summary.action_items.map((item, i) => (
                          <li key={i} className="flex gap-2 items-start text-zinc-300">
                            <span className="text-green-400 mt-1">→</span>
                            <span>{item}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Key Concepts */}
                  {summary.key_concepts?.length > 0 && (
                    <div>
                      <h3 className="text-zinc-400 font-semibold uppercase tracking-wider text-xs mb-4">
                        {t('detail.keyConcepts') || t("ui.keyConcepts")}
                      </h3>
                      <div className="space-y-3">
                        {summary.key_concepts.map((concept, i) => (
                          <div key={i} className="p-4 bg-zinc-900/50 rounded-xl border border-zinc-800/50">
                            <h4 className="text-indigo-400 font-medium mb-1">
                              {typeof concept === 'string' ? concept : concept.concept}
                            </h4>
                            {typeof concept !== 'string' && concept.explanation && (
                              <p className="text-zinc-400 text-sm">{concept.explanation}</p>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Examples */}
                  {summary.examples?.length > 0 && (
                    <div>
                      <h3 className="text-zinc-400 font-semibold uppercase tracking-wider text-xs mb-4">
                        {t('detail.examples') || t("ui.examples")}
                      </h3>
                      <div className="space-y-2">
                        {summary.examples.map((example, i) => (
                          <div key={i} className="p-3 bg-zinc-900/30 rounded-lg border-l-2 border-zinc-700">
                            <p className="text-zinc-300 text-sm">{example}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Resources */}
                  {summary.resources?.length > 0 && (
                    <div>
                      <h3 className="text-zinc-400 font-semibold uppercase tracking-wider text-xs mb-4">
                        {t('detail.resources') || t("ui.recommendedResources")}
                      </h3>
                      <div className="space-y-2">
                        {summary.resources.map((resource, i) => (
                          <div key={i} className="flex gap-2 items-start text-zinc-300">
                            <span className="text-blue-400 mt-0.5">•</span>
                            <span className="text-sm">{resource}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Tags */}
                  {summary.tags?.length > 0 && (
                    <div className="flex flex-wrap gap-2 pt-4">
                      {summary.tags.map((tag, i) => (
                        <span key={i} className="px-3 py-1 bg-zinc-800 text-zinc-400 rounded-full text-xs">
                          #{tag}
                        </span>
                      ))}
                    </div>
                  )}
                </>
              ) : (
                <div className="flex flex-col items-center justify-center py-20 text-zinc-500 border-2 border-dashed border-zinc-800 rounded-2xl">
                  <Sparkles size={48} className="mb-4 text-zinc-700" />
                  <p className="text-lg font-medium mb-2">{t('detail.noSummary')}</p>
                  <p className="text-sm text-zinc-600 mb-4">
                    {selectedTemplate?.description || t('detail.selectTemplate') || 'Select a template to generate summary'}
                  </p>
                  {isCurrentlySummarizing ? (
                    <TaskProgress
                      taskType="summarize"
                      taskId={summarizeTaskId}
                      onComplete={handleSummarizeComplete}
                      onError={handleTaskError}
                      onCancelled={handleTaskCancelled}
                    />
                  ) : (
                    <button
                      onClick={() => generateSummary()}
                      disabled={!canSummarize || loading || isCurrentlySummarizing || !selectedTemplate}
                      className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-zinc-700 text-white rounded-lg text-sm font-medium transition-colors"
                    >
                      {!canSummarize ? actionReasons[episode.actions?.summarize?.reason_code] : (loading ? t('detail.generating') : t('detail.generateSummaryAI'))}
                    </button>
                  )}
                </div>
              )}
            </div>
          )}

          {activeTab === 'info' && (
            <div className="space-y-6">
              {/* 摘要 */}
              {episode.summary && (
                <div>
                  <h3 className="text-zinc-400 font-semibold uppercase tracking-wider text-xs mb-3">{t('detail.summary')}</h3>
                  <p className="text-zinc-300 leading-relaxed">
                    {decodeHtmlEntities(episode.summary)}
                  </p>
                </div>
              )}

              {/* 详细内容 */}
              {episode.content && (
                <div>
                  <h3 className="text-zinc-400 font-semibold uppercase tracking-wider text-xs mb-3">{t('detail.content')}</h3>
                  <div className="text-zinc-300 leading-relaxed whitespace-pre-line">
                    {decodeHtmlEntities(episode.content)}
                  </div>
                </div>
              )}

              {/* 元信息 */}
              <div className="grid grid-cols-2 gap-4 p-4 bg-zinc-900/50 rounded-xl border border-zinc-800/50">
                <div>
                  <span className="text-zinc-500 text-xs">{t('detail.duration')}</span>
                  <p className="text-zinc-300">{episode.duration_formatted || t('episode.unknown')}</p>
                </div>
                <div>
                  <span className="text-zinc-500 text-xs">{t('detail.publishDate')}</span>
                  <p className="text-zinc-300">{episode.published_at ? formatUiDate(episode.published_at, i18n.resolvedLanguage) : t('episode.unknown')}</p>
                </div>
                {episode.link && (
                  <div className="col-span-2">
                    <span className="text-zinc-500 text-xs">{t('detail.originalLink')}</span>
                    <a href={episode.link} target="_blank" rel="noopener noreferrer" className="text-indigo-400 hover:text-indigo-300 block truncate">
                      {episode.link}
                    </a>
                  </div>
                )}
              </div>

              {/* 如果没有任何内容 */}
              {!episode.summary && !episode.content && (
                <p className="text-zinc-500">{t('episode.noDescription')}</p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default EpisodeDetailView;
