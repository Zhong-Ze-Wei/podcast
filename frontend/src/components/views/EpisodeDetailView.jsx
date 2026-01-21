// -*- coding: utf-8 -*-
import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Play, Mic2, Download, AlertCircle, ChevronLeft,
  Sparkles, CheckCircle2
} from 'lucide-react';
import { transcriptsApi, summariesApi, episodesApi } from '../../services/api';
import { decodeHtmlEntities } from '../../utils/helpers';

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

  // 检查音频是否已下载
  const isAudioDownloaded = episode?.status === 'downloaded' ||
    episode?.status === 'transcribed' ||
    episode?.status === 'transcribing' ||
    episode?.status === 'summarized' ||
    episode?.status === 'summarizing' ||
    episode?.local_path;

  // 检查是否正在下载
  const isDownloading = episode?.status === 'downloading';

  // 检查是否正在转录
  const isTranscribing = episode?.status === 'transcribing';

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

  const loadSummary = async () => {
    try {
      const response = await summariesApi.get(episode.id);
      setSummary(response.data);
    } catch (err) {
      setSummary(null);
    }
  };

  const generateTranscript = async () => {
    setLoading(true);
    setError(null);
    try {
      await transcriptsApi.create(episode.id);
      await loadTranscript();
      if (onRefresh) onRefresh();
    } catch (err) {
      console.error('Failed to generate transcript:', err);
      // 显示用户友好的错误信息
      const errorCode = err?.code || '';
      const errorMsg = err?.message || 'Failed to generate transcript';
      if (errorCode === 'AUDIO_NOT_DOWNLOADED' ||
          errorMsg.includes('audio not downloaded') ||
          errorMsg.includes('Audio needs to be downloaded') ||
          errorMsg.includes('Audio file not found')) {
        setError(t('detail.needDownloadFirst'));
      } else if (errorCode === 'ALREADY_TRANSCRIBING') {
        setError(t('detail.alreadyTranscribing') || 'Transcription is already in progress');
      } else if (errorCode === 'ALREADY_TRANSCRIBED') {
        setError(t('detail.alreadyTranscribed') || 'Episode already has a transcript');
        // 重新加载转录
        await loadTranscript();
      } else {
        setError(errorMsg);
      }
    } finally {
      setLoading(false);
    }
  };

  const downloadAudio = async () => {
    setLoading(true);
    setError(null);
    setSuccessMsg(null);
    try {
      await episodesApi.download(episode.id);
      setSuccessMsg(t('detail.downloadStarted') || 'Download started! Please wait...');
      if (onRefresh) onRefresh();
      // 3秒后清除成功消息
      setTimeout(() => setSuccessMsg(null), 5000);
    } catch (err) {
      console.error('Failed to download audio:', err);
      const errorCode = err?.code || '';
      if (errorCode === 'ALREADY_DOWNLOADED') {
        setSuccessMsg(t('detail.alreadyDownloaded') || 'Audio already downloaded');
        setTimeout(() => setSuccessMsg(null), 3000);
      } else if (errorCode === 'ALREADY_DOWNLOADING') {
        setSuccessMsg(t('detail.downloadInProgress') || 'Download already in progress');
        setTimeout(() => setSuccessMsg(null), 3000);
      } else {
        setError(err?.message || 'Failed to download audio');
      }
    } finally {
      setLoading(false);
    }
  };

  const generateSummary = async () => {
    setLoading(true);
    try {
      await summariesApi.create(episode.id);
      await loadSummary();
      if (onRefresh) onRefresh();
    } catch (err) {
      console.error('Failed to generate summary:', err);
    } finally {
      setLoading(false);
    }
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
                disabled={loading}
                className="p-2.5 rounded-full border border-zinc-700 hover:bg-zinc-800 text-zinc-400 hover:text-white transition-colors"
                title={t('detail.generateTranscript')}
              >
                <Mic2 size={20} />
              </button>
              <button
                onClick={generateSummary}
                disabled={loading}
                className="p-2.5 rounded-full border border-zinc-700 hover:bg-zinc-800 text-zinc-400 hover:text-white transition-colors"
                title={t('detail.generateSummary')}
              >
                <Sparkles size={20} />
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
                transcript.segments.map((seg, idx) => (
                  <div key={idx} className="flex gap-6 group hover:bg-zinc-900/30 p-2 rounded-lg transition-colors -mx-2">
                    <span className="text-xs text-zinc-600 font-mono w-12 pt-1 flex-shrink-0 select-none group-hover:text-zinc-500">
                      {seg.time}
                    </span>
                    <p className="text-zinc-300 leading-relaxed text-lg selection:bg-indigo-500/30">{seg.text}</p>
                  </div>
                ))
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
                    {/* 如果正在下载，显示下载中状态 */}
                    {isDownloading ? (
                      <div className="flex flex-col items-center gap-2">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                        <p className="text-sm text-blue-400">{t('status.downloading')}</p>
                      </div>
                    ) : isTranscribing ? (
                      <div className="flex flex-col items-center gap-2">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-500"></div>
                        <p className="text-sm text-purple-400">{t('status.transcribing')}</p>
                      </div>
                    ) : !isAudioDownloaded ? (
                      /* 如果音频未下载，显示下载按钮 */
                      <div className="flex flex-col items-center gap-2">
                        <p className="text-sm text-zinc-400 mb-2">{t('detail.needDownloadFirst')}</p>
                        <button
                          onClick={downloadAudio}
                          disabled={loading}
                          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-medium transition-colors"
                        >
                          <Download size={16} />
                          {loading ? t('detail.downloading') : t('detail.downloadAudio')}
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={generateTranscript}
                        disabled={loading}
                        className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-medium transition-colors"
                      >
                        {loading ? t('detail.generating') : t('detail.generateTranscriptAI')}
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'summary' && (
            <div className="space-y-8 animate-in">
              {summary?.tldr || summary?.key_points ? (
                <>
                  <div className="bg-gradient-to-br from-indigo-900/20 to-purple-900/20 p-6 rounded-2xl border border-indigo-500/20">
                    <h3 className="text-indigo-300 font-semibold mb-3 flex items-center gap-2">
                      <Sparkles size={18} /> {t('detail.tldr')}
                    </h3>
                    <p className="text-lg text-zinc-200 leading-relaxed font-light">{summary.tldr}</p>
                  </div>

                  {summary.key_points && (
                    <div>
                      <h3 className="text-zinc-400 font-semibold uppercase tracking-wider text-xs mb-4">{t('detail.keyTakeaways')}</h3>
                      <ul className="space-y-3">
                        {summary.key_points.map((point, i) => (
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
                </>
              ) : (
                <div className="flex flex-col items-center justify-center py-20 text-zinc-500 border-2 border-dashed border-zinc-800 rounded-2xl">
                  <Sparkles size={48} className="mb-4 text-zinc-700" />
                  <p className="text-lg font-medium mb-2">{t('detail.noSummary')}</p>
                  <button
                    onClick={generateSummary}
                    disabled={loading}
                    className="text-indigo-400 hover:text-indigo-300 text-sm font-medium"
                  >
                    {loading ? t('detail.generating') : t('detail.generateSummaryAI')}
                  </button>
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
