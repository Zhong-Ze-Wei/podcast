// -*- coding: utf-8 -*-
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Briefcase } from 'lucide-react';
import EpisodeCard from '../cards/EpisodeCard';
import ViewToolbar from '../common/ViewToolbar';

/**
 * WorkspaceView - 工作台页面
 * 显示所有处理过的节目（转录中、已转录、摘要中、已摘要）
 * 支持Tab筛选
 */
const WorkspaceView = ({ episodes, feeds, onEpisodeClick, onPlay, onStar, viewMode = 'grid', onViewModeChange }) => {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState('all');

  // 创建feed图片映射
  const feedImageMap = {};
  (feeds || []).forEach(f => { feedImageMap[f.id] = f.image; });

  // 所有处理过的节目
  const allProcessed = episodes.filter(ep =>
    ['downloaded', 'transcribing', 'transcribed', 'summarizing', 'summarized'].includes(ep.status) ||
    ep.local_audio_url ||
    ep.has_transcript ||
    ep.has_summary
  );

  // 根据Tab筛选
  const getFilteredEpisodes = () => {
    switch (activeTab) {
      case 'downloaded':
        return allProcessed.filter(ep => ep.status === 'downloaded' || ep.local_audio_url);
      case 'transcript':
        return allProcessed.filter(ep =>
          ep.has_transcript || ep.status === 'transcribing' || ep.status === 'transcribed'
        );
      case 'summary':
        return allProcessed.filter(ep =>
          ep.has_summary || ep.status === 'summarizing' || ep.status === 'summarized'
        );
      default:
        return allProcessed;
    }
  };

  const filteredEpisodes = getFilteredEpisodes();

  // Tab配置
  const tabs = [
    { key: 'all', label: t('workspace.tabAll') },
    { key: 'downloaded', label: t('status.downloaded') },
    { key: 'transcript', label: t('workspace.tabTranscript') },
    { key: 'summary', label: t('workspace.tabSummary') },
  ];

  return (
    <div className="flex flex-col h-full bg-zinc-950 text-zinc-100 overflow-hidden">
      {/* 头部 */}
      <div className="px-8 py-6 border-b border-zinc-800 bg-zinc-900/20">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center shadow-xl">
              <Briefcase size={32} className="text-white" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-white">{t('workspace.title')}</h1>
              <p className="text-zinc-400 text-sm mt-1">
                {filteredEpisodes.length} {t('workspace.episodes')}
              </p>
            </div>
          </div>
        </div>

        {/* Tab筛选 */}
        <div className="flex gap-2 mt-4">
          {tabs.map(tab => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                activeTab === tab.key
                  ? 'bg-emerald-600 text-white'
                  : 'bg-zinc-800 text-zinc-400 hover:text-white hover:bg-zinc-700'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* 列表 */}
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        <ViewToolbar
          count={`${filteredEpisodes.length} ${t('workspace.episodes')}`}
          description={t('viewToolbar.workspaceDescription')}
          viewMode={viewMode}
          onViewModeChange={onViewModeChange}
        />
        {filteredEpisodes.length > 0 ? (
          <div className={`p-4 md:p-8 grid ${viewMode === 'list' ? 'grid-cols-1 gap-3' : 'grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-4'}`}>
            {filteredEpisodes.map(ep => (
              <EpisodeCard
                key={ep.id}
                episode={ep}
                onClick={onEpisodeClick}
                onStar={onStar}
                onPlay={onPlay}
                viewMode={viewMode}
                feedImage={feedImageMap[ep.feed_id]}
              />
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-20 text-zinc-500">
            <Briefcase size={48} className="mb-4 text-zinc-700" />
            <p className="text-lg font-medium mb-2">{t('workspace.empty')}</p>
            <p className="text-sm text-zinc-600">{t('workspace.emptyHint')}</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default WorkspaceView;
