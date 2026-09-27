// -*- coding: utf-8 -*-
import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Sparkles, TrendingUp, Lightbulb, BookOpen, Play, ChevronRight, Target, Zap, RefreshCw, Download, AlertCircle } from 'lucide-react';
import { insightsApi } from '../../services/api';
import { settingsApi } from '../../services/api';

/**
 * AIBriefingView - AI每日简报视图
 *
 * 基于用户订阅的播客数据，由后端 LLM 生成每日简报。
 */
const AIBriefingView = ({ onEpisodeClick, onPlay }) => {
  const { t } = useTranslation();
  const [aiEnabled, setAiEnabled] = useState(true);
  useEffect(() => {
    settingsApi.getAiAnalysis().then(r => setAiEnabled(!!(r.enabled))).catch(() => {});
  }, []);
  const [briefing, setBriefing] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadBriefing = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await insightsApi.getBriefing();
      if (res.success && res.briefing) {
        setBriefing(res.briefing);
      } else {
        setBriefing(null);
        setError(res.message || '暂无简报数据');
      }
    } catch (err) {
      console.error('Failed to load briefing:', err);
      setError('加载简报失败，请检查后端服务');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadBriefing();
  }, [loadBriefing]);

  const handleRegenerate = async () => {
    if (!aiEnabled) {
      setError('AI 分析已冻结：已有缓存可查看，但暂时不再生成今日简报。');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await insightsApi.regenerateBriefing();
      if (res.success && res.briefing) {
        setBriefing(res.briefing);
      } else {
        setError(res.message || '生成简报失败');
      }
    } catch (err) {
      console.error('Failed to regenerate briefing:', err);
      setError('生成简报失败，请检查 LLM 配置');
    } finally {
      setLoading(false);
    }
  };

  const handleExportPdf = async () => {
    if (!briefing?.briefing?.markdownReport) {
      setError('简报内容为空，无法导出 PDF');
      return;
    }
    try {
      await insightsApi.exportPdf();
    } catch (err) {
      setError('PDF 导出失败，请重试');
    }
  };

  // Loading 状态
  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-black">
        <div className="text-center">
          <Sparkles className="w-12 h-12 text-indigo-500 animate-pulse mx-auto mb-4" />
          <p className="text-zinc-400">AI 正在分析你订阅的播客...</p>
        </div>
      </div>
    );
  }

  // 错误或无数据
  if (error || !briefing?.briefing) {
    return (
      <div className="flex-1 flex items-center justify-center bg-black">
        <div className="text-center max-w-md">
          <AlertCircle className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
          <p className="text-zinc-400 mb-4">{error || '暂无简报数据'}</p>
          <button
            onClick={handleRegenerate}
            disabled={!aiEnabled}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-zinc-800 disabled:text-zinc-500 text-white rounded-lg transition-colors"
          >
            {aiEnabled ? '生成今日简报' : 'AI 分析已冻结'}
          </button>
        </div>
      </div>
    );
  }

  const data = briefing.briefing;
  const summary = data.summary || {};
  const hotTopics = data.hotTopics || [];
  const newConcepts = data.newConcepts || [];
  const trends = data.trends || { topics: [] };
  const recommended = data.recommended || [];
  const meta = data._meta || {};

  return (
    <div className="flex-1 overflow-y-auto bg-black custom-scrollbar">
      <div className="max-w-4xl mx-auto px-8 py-12">
        {/* 头部 */}
        <div className="mb-10">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <Sparkles className="w-8 h-8 text-indigo-400" />
              <h1 className="text-3xl font-bold bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent">
                今日洞察
              </h1>
            </div>
            <div className="flex items-center gap-2">
              {meta.model && (
                <span className="text-xs text-zinc-600">{meta.model}</span>
              )}
              <button
                onClick={handleRegenerate}
                disabled={!aiEnabled}
                className="p-2 text-zinc-500 hover:text-indigo-400 disabled:text-zinc-700 disabled:cursor-not-allowed transition-colors"
                title={aiEnabled ? '重新生成' : 'AI 分析已冻结'}
              >
                <RefreshCw className="w-4 h-4" />
              </button>
              <button
                onClick={handleExportPdf}
                className="p-2 text-zinc-500 hover:text-indigo-400 transition-colors"
                title="导出 PDF"
              >
                <Download className="w-4 h-4" />
              </button>
            </div>
          </div>
          <p className="text-zinc-500 text-lg">
            {briefing.date} · 分析了 {summary.totalEpisodes || 0} 个单集 · 提取了 {summary.keyInsights || 0} 个核心洞察
            {meta.ai_summarized_count > 0 && (
              <span className="text-zinc-600"> · 其中 {meta.ai_summarized_count} 个含 AI 深度摘要</span>
            )}
          </p>
        </div>

        {/* 热点话题 */}
        {hotTopics.length > 0 && (
          <section className="mb-12">
            <div className="flex items-center gap-2 mb-6">
              <TrendingUp className="w-5 h-5 text-orange-400" />
              <h2 className="text-xl font-semibold text-zinc-200">今日热点</h2>
            </div>

            <div className="space-y-4">
              {hotTopics.map((topic) => (
                <div
                  key={topic.title}
                  className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-6 hover:border-zinc-700 transition-colors"
                >
                  <div className="flex items-start justify-between mb-3">
                    <h3 className="text-lg font-semibold text-zinc-100">{topic.title}</h3>
                    <div className="flex items-center gap-2">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        topic.sentiment === 'positive' ? 'bg-emerald-500/10 text-emerald-400' :
                        topic.sentiment === 'negative' ? 'bg-red-500/10 text-red-400' :
                        'bg-zinc-700 text-zinc-400'
                      }`}>
                        {topic.sentiment === 'positive' ? '正面' : topic.sentiment === 'negative' ? '负面' : '中性'}
                      </span>
                      <span className="text-xs text-zinc-500">{topic.mentions} 个播客提及</span>
                    </div>
                  </div>

                  <div className="text-zinc-400 text-sm mb-4" dangerouslySetInnerHTML={{
                    __html: formatMarkdownInline(topic.summary || '')
                  }} />

                  {topic.keyQuotes && topic.keyQuotes.length > 0 && (
                    <div className="space-y-2 mb-4">
                      {topic.keyQuotes.map((q, i) => (
                        <blockquote key={i} className="border-l-2 border-indigo-500/50 pl-3 text-zinc-500 text-sm italic">
                          "{q.quote}" — <span className="text-indigo-400">{q.speaker}</span>
                        </blockquote>
                      ))}
                    </div>
                  )}

                  <div className="flex items-center gap-2 text-xs text-zinc-600">
                    <BookOpen className="w-3 h-3" />
                    {topic.sources && topic.sources.join(', ')}
                  </div>

                  {topic.relatedEpisodes && topic.relatedEpisodes.length > 0 && (
                    <div className="mt-4 pt-3 border-t border-zinc-800">
                      <div className="space-y-2">
                        {topic.relatedEpisodes.map((ep) => (
                          <div
                            key={ep.id}
                            className="flex items-center gap-3 p-2 rounded-lg hover:bg-zinc-800/50 cursor-pointer transition-colors"
                            onClick={() => onEpisodeClick && onEpisodeClick(ep.id)}
                          >
                            <button
                              className="w-8 h-8 rounded-full bg-indigo-600/20 flex items-center justify-center text-indigo-400 hover:bg-indigo-600/30 transition-colors shrink-0"
                              onClick={(e) => {
                                e.stopPropagation();
                                onPlay && onPlay(ep);
                              }}
                            >
                              <Play className="w-4 h-4 ml-0.5" />
                            </button>
                            <div className="flex-1 min-w-0">
                              <p className="text-zinc-200 text-sm font-medium truncate">{ep.title}</p>
                              <p className="text-zinc-500 text-xs">{ep.feed} · {ep.duration}分钟</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* 新概念 */}
        {newConcepts.length > 0 && (
          <section className="mb-12">
            <div className="flex items-center gap-2 mb-6">
              <Lightbulb className="w-5 h-5 text-yellow-400" />
              <h2 className="text-xl font-semibold text-zinc-200">新概念</h2>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {newConcepts.map((concept, idx) => (
                <div
                  key={idx}
                  className="bg-zinc-900/30 border border-zinc-800 rounded-xl p-5 hover:bg-zinc-900/50 transition-colors"
                >
                  <div className="flex items-start justify-between mb-2">
                    <h3 className="text-zinc-200 font-semibold">{concept.concept}</h3>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      concept.complexity === 'high' ? 'bg-red-500/10 text-red-400' :
                      concept.complexity === 'medium' ? 'bg-yellow-500/10 text-yellow-400' :
                      'bg-green-500/10 text-green-400'
                    }`}>
                      {concept.complexity === 'high' ? '进阶' : concept.complexity === 'medium' ? '中等' : '入门'}
                    </span>
                  </div>
                  <p className="text-zinc-400 text-sm mb-3">{concept.explanation}</p>
                  <p className="text-zinc-500 text-xs">{concept.mentionedIn} 个播客提及</p>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* 趋势数据 */}
        {trends.topics && trends.topics.length > 0 && (
          <section className="mb-12">
            <div className="flex items-center gap-2 mb-6">
              <Zap className="w-5 h-5 text-purple-400" />
              <h2 className="text-xl font-semibold text-zinc-200">话题趋势</h2>
            </div>

            <div className="flex flex-wrap gap-3">
              {trends.topics.map((topic, idx) => (
                <div
                  key={idx}
                  className="flex items-center gap-2 px-4 py-2 bg-zinc-900/50 border border-zinc-800 rounded-full"
                >
                  <span className="text-zinc-200">{topic.name}</span>
                  {topic.change && (
                    <span className={`text-xs ${
                      topic.trend === 'up' ? 'text-emerald-400' :
                      topic.trend === 'down' ? 'text-red-400' :
                      'text-zinc-500'
                    }`}>
                      {topic.change}
                    </span>
                  )}
                  {topic.mentions && (
                    <span className="text-xs text-zinc-500">
                      {topic.mentions}次
                    </span>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* 推荐收听 */}
        {recommended.length > 0 && (
          <section>
            <div className="flex items-center gap-2 mb-6">
              <Target className="w-5 h-5 text-emerald-400" />
              <h2 className="text-xl font-semibold text-zinc-200">为你推荐</h2>
            </div>

            <div className="space-y-3">
              {recommended.map((rec) => (
                <div
                  key={rec.id}
                  className="flex items-center gap-4 p-4 bg-gradient-to-r from-indigo-900/20 to-purple-900/20 border border-indigo-500/20 rounded-xl hover:border-indigo-500/40 transition-colors cursor-pointer"
                  onClick={() => onEpisodeClick && onEpisodeClick(rec.id)}
                >
                  <button
                    className="w-10 h-10 rounded-full bg-indigo-600 flex items-center justify-center text-white hover:bg-indigo-500 transition-colors shrink-0"
                    onClick={(e) => {
                      e.stopPropagation();
                      onPlay && onPlay(rec);
                    }}
                  >
                    <Play className="w-5 h-5 ml-0.5" />
                  </button>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-zinc-100 font-semibold mb-1">{rec.title}</h3>
                    <p className="text-zinc-400 text-sm mb-1">{rec.feed}</p>
                    <p className="text-indigo-400 text-xs">{rec.reason}</p>
                  </div>
                  <ChevronRight className="w-5 h-5 text-zinc-600 shrink-0" />
                </div>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  );
};

/** 简单的 Markdown 内联格式化 */
function formatMarkdownInline(text) {
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`(.*?)`/g, '<code class="bg-zinc-800 px-1 rounded text-xs">$1</code>');
}

export default AIBriefingView;
