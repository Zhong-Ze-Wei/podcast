// -*- coding: utf-8 -*-
import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Play, Mic2, AlertCircle, ChevronLeft,
  Sparkles, CheckCircle2, Clock, DollarSign,
  Languages, TrendingUp, AlertTriangle, Quote
} from 'lucide-react';
import { transcriptsApi, summariesApi, episodesApi } from '../../services/api';
import { decodeHtmlEntities } from '../../utils/helpers';

/**
 * 转录进度条组件 - 基于预计时间显示进度，最高99%
 */
const TranscribeProgressBar = ({ startTime, estimatedMinutes }) => {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    if (!startTime || !estimatedMinutes) {
      setProgress(0);
      return;
    }

    const estimatedMs = estimatedMinutes * 60 * 1000;

    const updateProgress = () => {
      const elapsed = Date.now() - startTime;
      const calculatedProgress = Math.min((elapsed / estimatedMs) * 100, 99);
      setProgress(calculatedProgress);
    };

    updateProgress();
    const interval = setInterval(updateProgress, 1000);

    return () => clearInterval(interval);
  }, [startTime, estimatedMinutes]);

  return (
    <div className="w-full bg-zinc-800 rounded-full h-2 overflow-hidden">
      <div
        className="h-full bg-gradient-to-r from-purple-600 to-indigo-500 transition-all duration-1000 ease-linear"
        style={{ width: `${progress}%` }}
      />
    </div>
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
const EpisodeDetailView = ({ episode, onBack, onRefresh, onPlay }) => {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState('transcript');
  const [transcript, setTranscript] = useState(null);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [hasExternalTranscript, setHasExternalTranscript] = useState(false);
  const [transcriptLoading, setTranscriptLoading] = useState(true);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // Transcribe states - 本地追踪转录状态
  const [localTranscribing, setLocalTranscribing] = useState(false);
  const [transcribeStartTime, setTranscribeStartTime] = useState(null);

  // Summary states
  const [summaryType, setSummaryType] = useState('investment');
  const [translating, setTranslating] = useState(false);
  const [showChinese, setShowChinese] = useState(false);
  const [localSummarizing, setLocalSummarizing] = useState(false);
  const [summarizeStartTime, setSummarizeStartTime] = useState(null);

  // 检查是否正在转录
  const isTranscribing = episode?.status === 'transcribing';
  // 综合判断：后端状态或本地刚触发的状态
  const isCurrentlyTranscribing = isTranscribing || localTranscribing;

  // 检查是否正在生成摘要
  const isSummarizing = episode?.status === 'summarizing';
  const isCurrentlySummarizing = isSummarizing || localSummarizing;

  // 计算预估费用和时间 (AssemblyAI: $0.37/小时)
  const estimateCost = episode?.duration ? (episode.duration * 0.37 / 3600).toFixed(2) : null;
  const estimateTime = episode?.duration ? Math.ceil(episode.duration / 60 / 5) : null; // 约为音频时长的1/5
  // 摘要预估时间：约1-2分钟
  const summaryEstimateTime = 2;

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

  const loadSummary = async (type = null) => {
    try {
      const response = await summariesApi.get(episode.id, type || summaryType);
      setSummary(response.data);
      setShowChinese(false);
    } catch (err) {
      setSummary(null);
    }
  };

  const generateTranscript = async () => {
    setLoading(true);
    setLocalTranscribing(true);  // 立即锁定按钮
    setTranscribeStartTime(Date.now());  // 记录开始时间用于进度条
    setError(null);
    try {
      await transcriptsApi.create(episode.id);
      await loadTranscript();
      if (onRefresh) onRefresh();
      // 成功获取到转录后，清除本地状态
      setLocalTranscribing(false);
      setTranscribeStartTime(null);
    } catch (err) {
      console.error('Failed to generate transcript:', err);
      const errorCode = err?.code || '';
      const errorMsg = err?.message || 'Failed to generate transcript';
      if (errorCode === 'ALREADY_TRANSCRIBING') {
        setError(t('detail.alreadyTranscribing') || 'Transcription is already in progress');
        // 保持本地状态，因为确实在转录中
      } else if (errorCode === 'ALREADY_TRANSCRIBED') {
        setError(t('detail.alreadyTranscribed') || 'Episode already has a transcript');
        await loadTranscript();
        setLocalTranscribing(false);
        setTranscribeStartTime(null);
      } else {
        setError(errorMsg);
        setLocalTranscribing(false);
        setTranscribeStartTime(null);
      }
    } finally {
      setLoading(false);
    }
  };

  const generateSummary = async (type = null) => {
    setLoading(true);
    setLocalSummarizing(true);  // 立即锁定按钮
    setSummarizeStartTime(Date.now());  // 记录开始时间用于进度条
    setError(null);
    try {
      const targetType = type || summaryType;
      await summariesApi.create(episode.id, targetType, false);
      setSuccessMsg(t('detail.summaryStarted') || 'Summary generation started');
      setTimeout(() => setSuccessMsg(null), 3000);
      if (onRefresh) onRefresh();
      // 成功后清除本地状态
      setLocalSummarizing(false);
      setSummarizeStartTime(null);
      // 重新加载摘要（已自动包含翻译）
      await loadSummary(targetType);
    } catch (err) {
      console.error('Failed to generate summary:', err);
      const errorCode = err?.code || '';
      if (errorCode === 'SUMMARY_EXISTS') {
        await loadSummary(type);
        setLocalSummarizing(false);
        setSummarizeStartTime(null);
      } else if (errorCode === 'TASK_IN_PROGRESS') {
        setError(t('detail.summaryInProgress') || 'Summary generation in progress');
        // 保持本地状态，因为确实在进行中
      } else {
        setError(err?.message || 'Failed to generate summary');
        setLocalSummarizing(false);
        setSummarizeStartTime(null);
      }
    } finally {
      setLoading(false);
    }
  };

  const translateSummary = async () => {
    setTranslating(true);
    setError(null);
    try {
      await summariesApi.translate(episode.id, summaryType);
      setSuccessMsg(t('detail.translateStarted') || 'Translation started');
      setTimeout(() => setSuccessMsg(null), 3000);
      if (onRefresh) onRefresh();
    } catch (err) {
      console.error('Failed to translate summary:', err);
      if (err?.message?.includes('already exists')) {
        await loadSummary();
        setShowChinese(true);
      } else {
        setError(err?.message || 'Failed to translate');
      }
    } finally {
      setTranslating(false);
    }
  };

  const handleSummaryTypeChange = async (type) => {
    setSummaryType(type);
    setSummary(null);
    setShowChinese(false);
    await loadSummary(type);
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
                      <div className="flex flex-col items-center gap-3 w-full max-w-xs">
                        <div className="flex items-center gap-2">
                          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-purple-500" />
                          <span className="text-purple-400 font-medium">{t('detail.transcribingStatus')}</span>
                        </div>
                        {/* 进度条 */}
                        <TranscribeProgressBar
                          startTime={transcribeStartTime}
                          estimatedMinutes={estimateTime}
                        />
                        {estimateTime && (
                          <p className="text-xs text-zinc-500">
                            {t('detail.estimateTime')}: ~{estimateTime} min
                          </p>
                        )}
                      </div>
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
              {/* Summary Type Selector & Actions */}
              <div className="flex items-center justify-between">
                <div className="flex gap-2">
                  {['investment', 'general'].map(type => (
                    <button
                      key={type}
                      onClick={() => handleSummaryTypeChange(type)}
                      className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                        summaryType === type
                          ? 'bg-indigo-600 text-white'
                          : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-200'
                      }`}
                    >
                      {type === 'investment' ? (
                        <span className="flex items-center gap-2">
                          <TrendingUp size={14} />
                          {t('detail.investmentAnalysis') || 'Investment'}
                        </span>
                      ) : (
                        <span className="flex items-center gap-2">
                          <Sparkles size={14} />
                          {t('detail.generalSummary') || 'General'}
                        </span>
                      )}
                    </button>
                  ))}
                </div>
                <div className="flex gap-2">
                  {/* 没有翻译时显示翻译按钮，有翻译时显示语言切换 */}
                  {summary && !summary.has_translation ? (
                    <button
                      onClick={translateSummary}
                      disabled={translating || isCurrentlySummarizing}
                      className="flex items-center gap-2 px-3 py-1.5 text-sm bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg transition-colors"
                    >
                      <Languages size={14} />
                      {translating ? t('detail.translating') || 'Translating...' : t('detail.translate') || 'Translate'}
                    </button>
                  ) : summary?.has_translation ? (
                    <button
                      onClick={() => setShowChinese(!showChinese)}
                      className={`flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg transition-colors ${
                        showChinese ? 'bg-green-600 text-white' : 'bg-zinc-800 hover:bg-zinc-700 text-zinc-300'
                      }`}
                    >
                      <Languages size={14} />
                      {showChinese ? 'EN' : 'CN'}
                    </button>
                  ) : null}
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

                  {/* Investment Signals (for investment type) */}
                  {summary.summary_type === 'investment' && summary.investment_signals?.length > 0 && (
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
                    {summaryType === 'investment'
                      ? t('detail.investmentDesc') || 'Extract investment signals, tickers, and market insights'
                      : t('detail.generalDesc') || 'Generate a general summary with key points'
                    }
                  </p>
                  {isCurrentlySummarizing ? (
                    <div className="flex flex-col items-center gap-3 w-full max-w-xs">
                      <div className="flex items-center gap-2">
                        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-indigo-500" />
                        <span className="text-indigo-400 font-medium">{t('detail.summarizingStatus')}</span>
                      </div>
                      <TranscribeProgressBar
                        startTime={summarizeStartTime}
                        estimatedMinutes={summaryEstimateTime}
                      />
                      <p className="text-xs text-zinc-500">
                        {t('detail.estimateTime')}: ~{summaryEstimateTime} min
                      </p>
                    </div>
                  ) : (
                    <button
                      onClick={() => generateSummary()}
                      disabled={loading || isCurrentlySummarizing}
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
