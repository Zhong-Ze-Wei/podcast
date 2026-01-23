// -*- coding: utf-8 -*-
import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Play, Mic2, AlertCircle, ChevronLeft,
  Sparkles, CheckCircle2, Clock, DollarSign,
  Languages, TrendingUp, AlertTriangle, Quote,
  Database, FileCheck, MessageCircle, HelpCircle, Users, Eye
} from 'lucide-react';
import { transcriptsApi, summariesApi, episodesApi, promptTemplatesApi } from '../../services/api';
import { decodeHtmlEntities } from '../../utils/helpers';
import TaskProgress from '../common/TaskProgress';

/**
 * EpisodeDetailView - 节目详情页
 *
 * 显示单个节目的详细信息，包括：
 * - 转录内容（带时间戳）
 * - AI生成的摘要
 * - 节目元信息
 */
const EpisodeDetailView = ({ episode: episodeProp, onBack, onRefresh, onPlay }) => {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState('transcript');
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

  // Summary states
  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [enabledBlocks, setEnabledBlocks] = useState([]);
  const [showChinese, setShowChinese] = useState(false);
  const [showTemplateOptions, setShowTemplateOptions] = useState(false);
  const [userFocus, setUserFocus] = useState('');
  const [selectedLength, setSelectedLength] = useState('medium');

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
        // 默认选择第一个模板
        if (templateList.length > 0 && !selectedTemplate) {
          const defaultTemplate = templateList.find(t => t.name === 'investment') || templateList[0];
          setSelectedTemplate(defaultTemplate);
          // 获取模板详情以获取 enabled blocks
          const detailResp = await promptTemplatesApi.get(defaultTemplate.id);
          const detail = detailResp.data || detailResp;
          const defaultEnabled = detail.optional_blocks
            ?.filter(b => b.enabled_by_default)
            .map(b => b.id) || [];
          setEnabledBlocks(defaultEnabled);
        }
      } catch (err) {
        console.error('Failed to load templates:', err);
      }
    };
    loadTemplates();
  }, []);

  // 检查是否正在转录
  const isTranscribing = episode?.status === 'transcribing';
  // 综合判断：后端状态或本地刚触发的状态
  const isCurrentlyTranscribing = isTranscribing || localTranscribing;

  // 检查是否正在生成摘要
  const isSummarizing = episode?.status === 'summarizing';
  const isCurrentlySummarizing = isSummarizing || localSummarizing;

  // 计算预估费用 (AssemblyAI: $0.37/小时)
  const estimateCost = episode?.duration ? (episode.duration * 0.37 / 3600).toFixed(2) : null;
  const estimateTime = episode?.duration ? Math.ceil(episode.duration / 60 / 5) : null;

  // 任务完成回调
  const handleTranscribeComplete = async () => {
    setLocalTranscribing(false);
    await loadTranscript();
    if (onRefresh) onRefresh();
  };

  const handleSummarizeComplete = async () => {
    setLocalSummarizing(false);
    await loadSummary();
    if (onRefresh) onRefresh();
  };

  const handleTaskError = (errorMsg) => {
    setError(errorMsg);
    setLocalTranscribing(false);
    setLocalSummarizing(false);
  };

  useEffect(() => {
    if (episode?.id) {
      setError(null);
      setSuccessMsg(null);
      loadTranscriptWithAutoFetch();
      loadSummary();
    }
  }, [episode]);

  const loadTranscriptWithAutoFetch = async () => {
    setTranscriptLoading(true);
    try {
      // 1. 先尝试从数据库获取
      const response = await transcriptsApi.get(episode.id);
      setTranscript(response.data);
      setHasExternalTranscript(false);
      setTranscriptLoading(false);
    } catch (err) {
      // 2. 数据库没有，检查是否有外部转录URL
      setTranscript(null);
      try {
        const extResponse = await transcriptsApi.checkExternal(episode.id);
        const hasExternal = extResponse.data?.has_external_transcript || false;
        setHasExternalTranscript(hasExternal);

        // 3. 如果有外部转录URL，自动获取
        if (hasExternal) {
          setLoading(true);
          try {
            await transcriptsApi.fetch(episode.id);
            const fetchedResponse = await transcriptsApi.get(episode.id);
            setTranscript(fetchedResponse.data);
            setHasExternalTranscript(false);
            if (onRefresh) onRefresh();
          } catch (fetchErr) {
            console.error('Auto-fetch external transcript failed:', fetchErr);
          } finally {
            setLoading(false);
          }
        }
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
      const name = templateName || selectedTemplate?.name || 'investment';
      const response = await summariesApi.get(episode.id, { template_name: name });
      setSummary(response.data);
      setShowChinese(false);
    } catch (err) {
      setSummary(null);
    }
  };

  const generateTranscript = async () => {
    setLoading(true);
    setLocalTranscribing(true);
    setError(null);
    try {
      await transcriptsApi.create(episode.id);
      // 任务已提交，TaskProgress 组件会轮询状态
      if (onRefresh) onRefresh();
    } catch (err) {
      console.error('Failed to generate transcript:', err);
      const errorCode = err?.code || '';
      const errorMsg = err?.message || 'Failed to generate transcript';
      if (errorCode === 'ALREADY_TRANSCRIBING') {
        setError(t('detail.alreadyTranscribing') || 'Transcription is already in progress');
      } else if (errorCode === 'ALREADY_TRANSCRIBED') {
        setError(t('detail.alreadyTranscribed') || 'Episode already has a transcript');
        await loadTranscript();
        setLocalTranscribing(false);
      } else {
        setError(errorMsg);
        setLocalTranscribing(false);
      }
    } finally {
      setLoading(false);
    }
  };

  const generateSummary = async () => {
    if (!selectedTemplate) {
      setError('Please select a template first');
      return;
    }
    setLoading(true);
    setLocalSummarizing(true);
    setError(null);
    try {
      await summariesApi.create(episode.id, {
        template_name: selectedTemplate.name,
        enabled_blocks: enabledBlocks,
        user_focus: userFocus.trim(),
        params: { length: selectedLength }
      });
      setSuccessMsg(t('detail.summaryStarted') || 'Summary generation started');
      setTimeout(() => setSuccessMsg(null), 3000);
      if (onRefresh) onRefresh();
      // 任务已提交，TaskProgress 组件会轮询状态
    } catch (err) {
      console.error('Failed to generate summary:', err);
      const errorCode = err?.code || '';
      if (errorCode === 'SUMMARY_EXISTS') {
        await loadSummary();
        setLocalSummarizing(false);
      } else if (errorCode === 'TASK_IN_PROGRESS') {
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
    setShowTemplateOptions(false);
    // 获取模板详情并设置默认启用的块
    try {
      const response = await promptTemplatesApi.get(template.id);
      const detail = response.data || response;
      const defaultEnabled = detail.optional_blocks
        ?.filter(b => b.enabled_by_default)
        .map(b => b.id) || [];
      setEnabledBlocks(defaultEnabled);
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
    summary: t('detail.summary'),
    info: t('detail.info')
  };

  if (!episode) return null;

  return (
    <div className="flex flex-col h-full bg-zinc-950 text-zinc-100 overflow-hidden animate-in">
      <div className="px-8 py-6 border-b border-zinc-800 flex items-start gap-6 bg-zinc-900/20">
        <button onClick={onBack} className="mt-1 p-2 hover:bg-zinc-800 rounded-full transition-colors text-zinc-400 hover:text-white">
          <ChevronLeft size={24} />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            <span className="text-indigo-400 text-sm font-semibold tracking-wide uppercase">
              {episode.feed_title || episode.feed?.title}
            </span>
            <span className="w-1 h-1 rounded-full bg-zinc-700"></span>
            <span className="text-zinc-500 text-sm">{new Date(episode.published_at).toLocaleDateString()}</span>
          </div>
          <h1 className="text-3xl font-bold text-white mb-4 leading-tight max-w-4xl">{episode.title}</h1>
          <div className="flex items-center gap-4">
            <button
              onClick={() => onPlay && onPlay(episode)}
              className="flex items-center gap-2 bg-white text-black px-6 py-2.5 rounded-full font-semibold hover:scale-105 transition-transform shadow-lg shadow-white/10"
            >
              <Play size={18} fill="currentColor" stroke="none" /> {t('detail.playEpisode')}
            </button>
            <div className="flex gap-2">
              <button
                onClick={generateTranscript}
                disabled={loading || isCurrentlyTranscribing}
                className={`p-2.5 rounded-full border transition-colors ${
                  isCurrentlyTranscribing
                    ? 'border-purple-500 bg-purple-900/30 text-purple-400 cursor-not-allowed'
                    : 'border-zinc-700 hover:bg-zinc-800 text-zinc-400 hover:text-white'
                }`}
                title={isCurrentlyTranscribing ? t('detail.transcribingStatus') : t('detail.generateTranscript')}
              >
                {isCurrentlyTranscribing ? (
                  <div className="animate-spin"><Mic2 size={20} /></div>
                ) : (
                  <Mic2 size={20} />
                )}
              </button>
              <button
                onClick={generateSummary}
                disabled={loading || isCurrentlySummarizing}
                className={`p-2.5 rounded-full border transition-colors ${
                  isCurrentlySummarizing
                    ? 'border-indigo-500 bg-indigo-900/30 text-indigo-400 cursor-not-allowed'
                    : 'border-zinc-700 hover:bg-zinc-800 text-zinc-400 hover:text-white'
                }`}
                title={isCurrentlySummarizing ? t('detail.summarizingStatus') : t('detail.generateSummary')}
              >
                {isCurrentlySummarizing ? (
                  <div className="animate-spin"><Sparkles size={20} /></div>
                ) : (
                  <Sparkles size={20} />
                )}
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="px-8 border-b border-zinc-800 flex items-center gap-8 bg-zinc-950/50 backdrop-blur sticky top-0 z-10">
        {['transcript', 'summary', 'info'].map(tab => (
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
                <div className="prose prose-invert max-w-none">
                  <p className="text-zinc-300 leading-relaxed text-lg whitespace-pre-wrap">{transcript.text}</p>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-20 text-zinc-500 border-2 border-dashed border-zinc-800 rounded-2xl">
                  <Mic2 size={48} className="mb-4 text-zinc-700" />
                  <p className="text-lg font-medium mb-4">{t('detail.noTranscript')}</p>

                  {/* 显示错误信息 */}
                  {error && (
                    <div className="flex items-center gap-2 text-red-400 mb-4 px-4 py-2 bg-red-900/20 rounded-lg border border-red-800/50">
                      <AlertCircle size={16} />
                      <span className="text-sm">{error}</span>
                    </div>
                  )}

                  {/* 显示成功消息 */}
                  {successMsg && (
                    <div className="flex items-center gap-2 text-green-400 mb-4 px-4 py-2 bg-green-900/20 rounded-lg border border-green-800/50">
                      <CheckCircle2 size={16} />
                      <span className="text-sm">{successMsg}</span>
                    </div>
                  )}

                  <div className="flex flex-col gap-3 items-center">
                    {isCurrentlyTranscribing ? (
                      <TaskProgress
                        taskType="transcribe"
                        episodeId={episode.id}
                        onComplete={handleTranscribeComplete}
                        onError={handleTaskError}
                      />
                    ) : (
                      <div className="flex flex-col items-center gap-3">
                        {/* 预估费用和时间 */}
                        {(estimateCost || estimateTime) && (
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
                                ~{estimateTime} min
                              </span>
                            )}
                          </div>
                        )}
                        <button
                          onClick={generateTranscript}
                          disabled={loading || isCurrentlyTranscribing}
                          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-zinc-700 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition-colors"
                        >
                          {isCurrentlyTranscribing ? t('detail.transcribingStatus') :
                           loading ? t('detail.generating') : t('detail.generateTranscriptAI')}
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
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
                        {template.display_name}
                      </span>
                    </button>
                  ))}
                </div>
                <div className="flex gap-2">
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

              {/* Error/Success Messages */}
              {error && (
                <div className="flex items-center gap-2 text-red-400 px-4 py-2 bg-red-900/20 rounded-lg border border-red-800/50">
                  <AlertCircle size={16} />
                  <span className="text-sm">{error}</span>
                </div>
              )}
              {successMsg && (
                <div className="flex items-center gap-2 text-green-400 px-4 py-2 bg-green-900/20 rounded-lg border border-green-800/50">
                  <CheckCircle2 size={16} />
                  <span className="text-sm">{successMsg}</span>
                </div>
              )}

              {/* User Focus & Length Config - 只在没有摘要或重新生成时显示 */}
              {(!summary?.tldr || showTemplateOptions) && !isCurrentlySummarizing && (
                <div className="p-4 bg-zinc-900/50 rounded-xl border border-zinc-800 space-y-4">
                  {/* User Focus Input */}
                  <div>
                    <label className="block text-sm text-zinc-400 mb-2">{t('detail.userFocusLabel') || 'Focus Area (optional)'}</label>
                    <div className="relative">
                      <input
                        type="text"
                        placeholder={t('detail.userFocusPlaceholder') || 'e.g., China market opportunities, risk factors...'}
                        maxLength={50}
                        value={userFocus}
                        onChange={e => setUserFocus(e.target.value)}
                        className="w-full px-4 py-2.5 bg-zinc-800 border border-zinc-700 rounded-lg text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-indigo-500 transition-colors"
                      />
                      <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-zinc-500">{userFocus.length}/50</span>
                    </div>
                  </div>

                  {/* Length Selection */}
                  <div>
                    <label className="block text-sm text-zinc-400 mb-2">{t('detail.lengthLabel') || 'Summary Length'}</label>
                    <div className="flex gap-2">
                      {[
                        { value: 'short', label: t('detail.lengthShort') || 'Short' },
                        { value: 'medium', label: t('detail.lengthMedium') || 'Medium' },
                        { value: 'long', label: t('detail.lengthLong') || 'Long' }
                      ].map(opt => (
                        <button
                          key={opt.value}
                          onClick={() => setSelectedLength(opt.value)}
                          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                            selectedLength === opt.value
                              ? 'bg-indigo-600 text-white'
                              : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700'
                          }`}
                        >
                          {opt.label}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* 摘要生成进度条 - 无论是否有摘要都显示 */}
              {isCurrentlySummarizing && (
                <div className="p-4 bg-indigo-900/20 rounded-xl border border-indigo-500/30">
                  <TaskProgress
                    taskType="summarize"
                    episodeId={episode.id}
                    onComplete={handleSummarizeComplete}
                    onError={handleTaskError}
                  />
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

                  {/* Investment Signals (显示任何包含投资信号的摘要) */}
                  {summary.investment_signals?.length > 0 && (
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
                                (signal.type || signal.type_zh) === 'bullish' || signal.type_zh === '看多' ? 'bg-green-500/20 text-green-400' :
                                (signal.type || signal.type_zh) === 'bearish' || signal.type_zh === '看空' ? 'bg-red-500/20 text-red-400' :
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

                  {/* Market Insights */}
                  {summary.market_insights?.length > 0 && (
                    <div>
                      <h3 className="text-zinc-400 font-semibold uppercase tracking-wider text-xs mb-4 flex items-center gap-2">
                        <TrendingUp size={14} /> {t('detail.marketInsights') || 'Market Insights'}
                      </h3>
                      <div className="space-y-2">
                        {(showChinese && summary.content_zh?.market_insights_zh
                          ? summary.content_zh.market_insights_zh
                          : summary.market_insights
                        ).map((insight, i) => (
                          <div key={i} className="flex items-start gap-2 p-3 bg-zinc-900/50 rounded-lg border border-zinc-800/50">
                            <span className="text-indigo-400 mt-0.5">*</span>
                            <span className="text-zinc-300 text-sm">{typeof insight === 'string' ? insight : (insight.insight_zh || insight.insight)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Unique Insights */}
                  {summary.unique_insights?.length > 0 && (
                    <div>
                      <h3 className="text-zinc-400 font-semibold uppercase tracking-wider text-xs mb-4 flex items-center gap-2">
                        <Sparkles size={14} /> {t('detail.uniqueInsights') || 'Unique Insights'}
                      </h3>
                      <div className="space-y-2">
                        {(showChinese && summary.content_zh?.unique_insights_zh
                          ? summary.content_zh.unique_insights_zh
                          : summary.unique_insights
                        ).map((insight, i) => (
                          <div key={i} className="flex items-start gap-2 p-3 bg-purple-900/20 rounded-lg border border-purple-800/30">
                            <span className="text-purple-400 mt-0.5">*</span>
                            <span className="text-zinc-300 text-sm">{typeof insight === 'string' ? insight : (insight.insight_zh || insight.insight)}</span>
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

                  {/* ===== Data & Evidence Template Fields ===== */}

                  {/* Core Content */}
                  {summary.core_content && (
                    <div>
                      <h3 className="text-zinc-400 font-semibold uppercase tracking-wider text-xs mb-4 flex items-center gap-2">
                        <FileCheck size={14} /> {t('detail.coreContent') || 'Core Content'}
                      </h3>
                      <div className="p-4 bg-zinc-900/50 rounded-xl border border-zinc-800/50">
                        <p className="text-zinc-300 leading-relaxed">
                          {showChinese && summary.content_zh?.core_content_zh
                            ? summary.content_zh.core_content_zh
                            : summary.core_content}
                        </p>
                      </div>
                    </div>
                  )}

                  {/* Cited Data */}
                  {summary.cited_data?.length > 0 && (
                    <div>
                      <h3 className="text-zinc-400 font-semibold uppercase tracking-wider text-xs mb-4 flex items-center gap-2">
                        <Database size={14} /> {t('detail.citedData') || 'Cited Data'}
                      </h3>
                      <div className="space-y-3">
                        {(showChinese && summary.content_zh?.cited_data_zh
                          ? summary.content_zh.cited_data_zh
                          : summary.cited_data
                        ).map((item, i) => (
                          <div key={i} className="p-4 bg-blue-900/10 rounded-xl border border-blue-800/30">
                            <div className="flex items-center gap-3 mb-2">
                              <span className="px-3 py-1 bg-blue-500/20 text-blue-400 rounded-lg text-lg font-bold">
                                {item.data_point || item.data_point_zh}
                              </span>
                            </div>
                            <p className="text-zinc-400 text-sm mb-1">{item.context_zh || item.context}</p>
                            <p className="text-zinc-300 text-sm font-medium">{item.claim_zh || item.claim}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Data Sources */}
                  {summary.data_sources?.length > 0 && (
                    <div>
                      <h3 className="text-zinc-400 font-semibold uppercase tracking-wider text-xs mb-4 flex items-center gap-2">
                        <FileCheck size={14} /> {t('detail.dataSources') || 'Data Sources'}
                      </h3>
                      <div className="space-y-2">
                        {(showChinese && summary.content_zh?.data_sources_zh
                          ? summary.content_zh.data_sources_zh
                          : summary.data_sources
                        ).map((src, i) => (
                          <div key={i} className="flex items-start gap-3 p-3 bg-zinc-900/50 rounded-lg border border-zinc-800/50">
                            <span className={`px-2 py-1 rounded text-xs font-medium ${
                              src.type === 'report' || src.type === 'institution' ? 'bg-green-500/20 text-green-400' :
                              src.type === 'personal' ? 'bg-yellow-500/20 text-yellow-400' :
                              'bg-zinc-500/20 text-zinc-400'
                            }`}>
                              {src.type_zh || src.type}
                            </span>
                            <div className="flex-1">
                              <p className="text-zinc-200 font-medium">{src.source_zh || src.source}</p>
                              <p className="text-zinc-500 text-xs">{src.credibility_note_zh || src.credibility_note}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Factual Claims */}
                  {summary.factual_claims?.length > 0 && (
                    <div>
                      <h3 className="text-zinc-400 font-semibold uppercase tracking-wider text-xs mb-4 flex items-center gap-2">
                        <CheckCircle2 size={14} /> {t('detail.factualClaims') || 'Factual Claims'}
                      </h3>
                      <div className="space-y-2">
                        {(showChinese && summary.content_zh?.factual_claims_zh
                          ? summary.content_zh.factual_claims_zh
                          : summary.factual_claims
                        ).map((item, i) => (
                          <div key={i} className="flex items-start gap-3 p-3 bg-green-900/10 rounded-lg border border-green-800/30">
                            <CheckCircle2 size={16} className="text-green-400 mt-0.5 flex-shrink-0" />
                            <div className="flex-1">
                              <p className="text-zinc-300">{item.claim_zh || item.claim}</p>
                              <div className="flex gap-2 mt-1">
                                <span className={`text-xs px-2 py-0.5 rounded ${
                                  item.verifiable === 'yes' ? 'bg-green-500/20 text-green-400' :
                                  item.verifiable === 'partial' ? 'bg-yellow-500/20 text-yellow-400' :
                                  'bg-zinc-500/20 text-zinc-400'
                                }`}>
                                  {item.verifiable_zh || item.verifiable}
                                </span>
                                {item.source_mentioned && (
                                  <span className="text-xs text-zinc-500">Source: {item.source_mentioned_zh || item.source_mentioned}</span>
                                )}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Opinion Claims */}
                  {summary.opinion_claims?.length > 0 && (
                    <div>
                      <h3 className="text-zinc-400 font-semibold uppercase tracking-wider text-xs mb-4 flex items-center gap-2">
                        <MessageCircle size={14} /> {t('detail.opinionClaims') || 'Opinion Claims'}
                      </h3>
                      <div className="space-y-2">
                        {(showChinese && summary.content_zh?.opinion_claims_zh
                          ? summary.content_zh.opinion_claims_zh
                          : summary.opinion_claims
                        ).map((item, i) => (
                          <div key={i} className="flex items-start gap-3 p-3 bg-orange-900/10 rounded-lg border border-orange-800/30">
                            <MessageCircle size={16} className="text-orange-400 mt-0.5 flex-shrink-0" />
                            <div className="flex-1">
                              <p className="text-zinc-300">{item.claim_zh || item.claim}</p>
                              <div className="flex gap-2 mt-1">
                                <span className="text-xs px-2 py-0.5 rounded bg-orange-500/20 text-orange-400">
                                  {item.type_zh || item.type}
                                </span>
                                {item.speaker && (
                                  <span className="text-xs text-zinc-500">- {item.speaker_zh || item.speaker}</span>
                                )}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Missing Data */}
                  {summary.missing_data?.length > 0 && (
                    <div>
                      <h3 className="text-zinc-400 font-semibold uppercase tracking-wider text-xs mb-4 flex items-center gap-2">
                        <HelpCircle size={14} /> {t('detail.missingData') || 'Missing Data'}
                      </h3>
                      <div className="space-y-2">
                        {(showChinese && summary.content_zh?.missing_data_zh
                          ? summary.content_zh.missing_data_zh
                          : summary.missing_data
                        ).map((item, i) => (
                          <div key={i} className="flex items-start gap-2 p-3 bg-zinc-900/50 rounded-lg border border-zinc-800/50">
                            <HelpCircle size={16} className="text-zinc-500 mt-0.5 flex-shrink-0" />
                            <span className="text-zinc-400 text-sm">{typeof item === 'string' ? item : (item.description_zh || item.description)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* ===== Stakeholder Analysis Template Fields ===== */}

                  {/* Speaker Profile */}
                  {summary.speaker_profile && (
                    <div>
                      <h3 className="text-zinc-400 font-semibold uppercase tracking-wider text-xs mb-4 flex items-center gap-2">
                        <Users size={14} /> {t('detail.speakerProfile') || 'Speaker Profile'}
                      </h3>
                      <div className="p-4 bg-purple-900/10 rounded-xl border border-purple-800/30">
                        <p className="text-zinc-300 leading-relaxed">
                          {showChinese && summary.content_zh?.speaker_profile_zh
                            ? summary.content_zh.speaker_profile_zh
                            : (typeof summary.speaker_profile === 'string' ? summary.speaker_profile : summary.speaker_profile.description)}
                        </p>
                      </div>
                    </div>
                  )}

                  {/* Stakeholders */}
                  {summary.stakeholders?.length > 0 && (
                    <div>
                      <h3 className="text-zinc-400 font-semibold uppercase tracking-wider text-xs mb-4 flex items-center gap-2">
                        <Users size={14} /> {t('detail.stakeholders') || 'Stakeholders'}
                      </h3>
                      <div className="space-y-3">
                        {(showChinese && summary.content_zh?.stakeholders_zh
                          ? summary.content_zh.stakeholders_zh
                          : summary.stakeholders
                        ).map((item, i) => (
                          <div key={i} className="p-4 bg-zinc-900/50 rounded-xl border border-zinc-800/50">
                            <div className="flex items-center gap-2 mb-2">
                              <span className="font-semibold text-zinc-200">{item.name_zh || item.name}</span>
                              <span className={`px-2 py-0.5 rounded text-xs ${
                                item.impact === 'benefits' || item.impact_zh === 'benefits' ? 'bg-green-500/20 text-green-400' :
                                item.impact === 'harmed' || item.impact_zh === 'harmed' ? 'bg-red-500/20 text-red-400' :
                                'bg-zinc-500/20 text-zinc-400'
                              }`}>
                                {item.impact_zh || item.impact}
                              </span>
                            </div>
                            <p className="text-zinc-400 text-sm">{item.description_zh || item.description}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Hidden Agendas */}
                  {summary.hidden_agendas?.length > 0 && (
                    <div>
                      <h3 className="text-zinc-400 font-semibold uppercase tracking-wider text-xs mb-4 flex items-center gap-2">
                        <Eye size={14} /> {t('detail.hiddenAgendas') || 'Hidden Agendas'}
                      </h3>
                      <div className="space-y-2">
                        {(showChinese && summary.content_zh?.hidden_agendas_zh
                          ? summary.content_zh.hidden_agendas_zh
                          : summary.hidden_agendas
                        ).map((item, i) => (
                          <div key={i} className="flex items-start gap-2 p-3 bg-yellow-900/10 rounded-lg border border-yellow-800/30">
                            <Eye size={16} className="text-yellow-400 mt-0.5 flex-shrink-0" />
                            <span className="text-zinc-300 text-sm">{typeof item === 'string' ? item : (item.agenda_zh || item.agenda)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Power Dynamics */}
                  {summary.power_dynamics && (
                    <div>
                      <h3 className="text-zinc-400 font-semibold uppercase tracking-wider text-xs mb-4 flex items-center gap-2">
                        <TrendingUp size={14} /> {t('detail.powerDynamics') || 'Power Dynamics'}
                      </h3>
                      <div className="p-4 bg-zinc-900/50 rounded-xl border border-zinc-800/50">
                        <p className="text-zinc-300 leading-relaxed">
                          {showChinese && summary.content_zh?.power_dynamics_zh
                            ? summary.content_zh.power_dynamics_zh
                            : (typeof summary.power_dynamics === 'string' ? summary.power_dynamics : summary.power_dynamics.description)}
                        </p>
                      </div>
                    </div>
                  )}

                  {/* Contrasting Views */}
                  {summary.contrasting_views?.length > 0 && (
                    <div>
                      <h3 className="text-zinc-400 font-semibold uppercase tracking-wider text-xs mb-4 flex items-center gap-2">
                        <MessageCircle size={14} /> {t('detail.contrastingViews') || 'Contrasting Views'}
                      </h3>
                      <div className="space-y-2">
                        {(showChinese && summary.content_zh?.contrasting_views_zh
                          ? summary.content_zh.contrasting_views_zh
                          : summary.contrasting_views
                        ).map((item, i) => (
                          <div key={i} className="flex items-start gap-2 p-3 bg-indigo-900/10 rounded-lg border border-indigo-800/30">
                            <MessageCircle size={16} className="text-indigo-400 mt-0.5 flex-shrink-0" />
                            <span className="text-zinc-300 text-sm">{typeof item === 'string' ? item : (item.view_zh || item.view)}</span>
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
                  {!isCurrentlySummarizing && (
                    <button
                      onClick={() => generateSummary()}
                      disabled={loading || !selectedTemplate}
                      className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-zinc-700 text-white rounded-lg text-sm font-medium transition-colors"
                    >
                      {loading ? t('detail.generating') : t('detail.generateSummaryAI')}
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
                  <p className="text-zinc-300">{episode.published_at ? new Date(episode.published_at).toLocaleDateString() : t('episode.unknown')}</p>
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
