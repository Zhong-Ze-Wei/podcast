// -*- coding: utf-8 -*-
import React, { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Settings, Search, RefreshCw, LayoutGrid, List } from 'lucide-react';
import { feedsApi, episodesApi, transcriptsApi, summariesApi, tasksApi } from './services/api';
// Layout components
import Sidebar from './components/layout/Sidebar';
// View components
import EpisodeDetailView from './components/views/EpisodeDetailView';
import FeedDetailView from './components/views/FeedDetailView';
import FavoritesView from './components/views/FavoritesView';
import WorkspaceView from './components/views/WorkspaceView';
// Card components
import FeedCard from './components/cards/FeedCard';
import EpisodeCard from './components/cards/EpisodeCard';
// Common components
import StatusBadge from './components/common/StatusBadge';
import LanguageSwitcher from './components/common/LanguageSwitcher';
// Player components
import PlayerBar from './components/player/PlayerBar';
// Task components
import TaskPanel from './components/tasks/TaskPanel';
// Utils
import { decodeHtmlEntities } from './utils/helpers';

export default function App() {
  const { t } = useTranslation();
  const [view, setView] = useState('list'); // list | feedDetail | detail
  const [activeFeed, setActiveFeed] = useState(null);
  const [selectedFeed, setSelectedFeed] = useState(null); // 用于FeedDetailView
  const [selectedEpisode, setSelectedEpisode] = useState(null);
  const [currentPlaying, setCurrentPlaying] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [feeds, setFeeds] = useState([]);
  const [episodes, setEpisodes] = useState([]);
  const [workspaceEpisodes, setWorkspaceEpisodes] = useState([]); // 已转录/已摘要的episodes
  const [feedEpisodes, setFeedEpisodes] = useState([]); // 当前选中feed的全部episodes
  const [feedEpisodesLoading, setFeedEpisodesLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [episodeViewMode, setEpisodeViewMode] = useState('grid'); // grid | list
  const audioRef = useRef(null);
  const lastSavedPositionRef = useRef(0); // 上次保存的位置，避免频繁保存
  const feedRequestIdRef = useRef(0); // 用于取消过期的feed episodes请求

  // 保存播放位置到后端
  const savePlayPosition = async (episodeId, position) => {
    if (!episodeId || position === undefined) return;
    // 只在位置变化超过5秒时保存
    if (Math.abs(position - lastSavedPositionRef.current) < 5) return;
    try {
      await episodesApi.update(episodeId, { play_position: Math.floor(position) });
      lastSavedPositionRef.current = position;
    } catch (err) {
      console.error('Failed to save play position:', err);
    }
  };

  // 定期保存播放位置 (每30秒)
  useEffect(() => {
    if (!currentPlaying || !isPlaying) return;
    const interval = setInterval(() => {
      if (audioRef.current && currentPlaying) {
        savePlayPosition(currentPlaying.id, audioRef.current.currentTime);
      }
    }, 30000);
    return () => clearInterval(interval);
  }, [currentPlaying, isPlaying]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [feedsData, episodesData, transcribedData] = await Promise.all([
        feedsApi.list(),
        episodesApi.list({ per_page: 500 }),
        episodesApi.listTranscribed()
      ]);
      setFeeds(feedsData.data || feedsData);
      setEpisodes(episodesData.data || episodesData);
      setWorkspaceEpisodes(transcribedData.data || transcribedData);
    } catch (err) {
      console.error('Failed to load data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleAddFeed = () => {
    loadData();
  };

  const handleRefreshFeed = () => {
    loadData();
  };

  const handleDeleteFeed = () => {
    setActiveFeed(null);
    setSelectedFeed(null);
    loadData();
  };

  // 点击订阅源卡片，进入详情页
  const handleFeedClick = async (feed) => {
    setSelectedFeed(feed);
    setActiveFeed(feed.id);
    setView('feedDetail');
    // 清空旧数据，开始加载新数据
    setFeedEpisodes([]);
    setFeedEpisodesLoading(true);

    // 使用请求ID来处理竞态条件
    const requestId = ++feedRequestIdRef.current;

    try {
      const response = await feedsApi.getEpisodes(feed.id, { per_page: 500 });
      // 只有当这是最新的请求时才更新状态
      if (requestId === feedRequestIdRef.current) {
        const episodeData = response.data || response;
        setFeedEpisodes(Array.isArray(episodeData) ? episodeData : []);
        setFeedEpisodesLoading(false);
      }
    } catch (err) {
      if (requestId === feedRequestIdRef.current) {
        console.error('Failed to load feed episodes:', err);
        setFeedEpisodes([]);
        setFeedEpisodesLoading(false);
      }
    }
  };

  const handleEpisodeClick = async (episode) => {
    setSelectedEpisode(episode);
    setView('detail');
  };

  const handleStar = async (episode) => {
    const newStarred = !episode.is_starred;

    // 乐观更新：立即更新所有状态
    const updateEpisodeList = (list) =>
      list.map(ep => ep.id === episode.id ? {...ep, is_starred: newStarred} : ep);

    setEpisodes(prev => updateEpisodeList(prev));
    setFeedEpisodes(prev => updateEpisodeList(prev));
    setWorkspaceEpisodes(prev => updateEpisodeList(prev));

    try {
      await episodesApi.star(episode.id, newStarred);
    } catch (err) {
      console.error('Star failed:', err);
      // 失败时回滚
      const rollback = (list) =>
        list.map(ep => ep.id === episode.id ? {...ep, is_starred: !newStarred} : ep);
      setEpisodes(prev => rollback(prev));
      setFeedEpisodes(prev => rollback(prev));
      setWorkspaceEpisodes(prev => rollback(prev));
    }
  };

  // 播放控制函数
  const handlePlay = (episode) => {
    if (currentPlaying?.id === episode.id) {
      // 如果是同一个episode，切换播放/暂停
      handlePlayPause(!isPlaying);
    } else {
      // 切换episode前保存当前播放位置
      if (currentPlaying && audioRef.current) {
        savePlayPosition(currentPlaying.id, audioRef.current.currentTime);
      }
      // 重置位置记录
      lastSavedPositionRef.current = episode.play_position || 0;
      // 播放新的episode
      setCurrentPlaying(episode);
      setIsPlaying(true);
      // 等待下一个渲染周期，audio元素更新后再播放
      setTimeout(() => {
        if (audioRef.current) {
          // 恢复播放位置
          if (episode.play_position && episode.play_position > 0) {
            audioRef.current.currentTime = episode.play_position;
          }
          audioRef.current.play().catch(err => console.error('Play failed:', err));
        }
      }, 100);
    }
  };

  const handlePlayPause = (playing) => {
    setIsPlaying(playing);
    if (audioRef.current) {
      if (playing) {
        audioRef.current.play().catch(err => console.error('Play failed:', err));
      } else {
        // 暂停时保存播放位置
        if (currentPlaying) {
          savePlayPosition(currentPlaying.id, audioRef.current.currentTime);
        }
        audioRef.current.pause();
      }
    }
  };

  const handleSeek = (time) => {
    if (audioRef.current) {
      audioRef.current.currentTime = time;
    }
  };

  const filteredEpisodes = episodes.filter(ep => {
    const matchesFeed = !activeFeed || ep.feed_id === activeFeed;
    const matchesSearch = !searchQuery ||
      ep.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      ep.description?.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesFeed && matchesSearch;
  });

  if (loading && feeds.length === 0) {
    return (
      <div className="flex h-screen items-center justify-center bg-black text-zinc-100">
        <div className="text-center">
          <RefreshCw className="animate-spin mx-auto mb-4 text-indigo-500" size={32} />
          <p className="text-zinc-400">{t('common.loading')}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-black text-zinc-100 font-sans selection:bg-indigo-500/30 overflow-hidden">
      <Sidebar
        feeds={feeds}
        activeFeed={activeFeed}
        setActiveFeed={setActiveFeed}
        setSelectedFeed={setSelectedFeed}
        setView={setView}
        onAddFeed={handleAddFeed}
        onRefreshFeed={handleRefreshFeed}
        onDeleteFeed={handleDeleteFeed}
        onStarFeed={loadData}
        onNoteFeed={loadData}
        onFeedClick={handleFeedClick}
        hasPlayer={!!currentPlaying}
        currentView={view}
      />

      <div className="flex-1 flex flex-col min-w-0 bg-black relative">
        <div className="absolute top-0 left-0 w-full h-96 bg-indigo-900/10 pointer-events-none blur-3xl rounded-full translate-y-[-50%]"></div>

        <div className="absolute top-4 right-8 z-20">
          <LanguageSwitcher />
        </div>

        {view === 'list' ? (
          <div className="flex-1 overflow-y-auto custom-scrollbar z-10">
            {/* 置顶工具栏 */}
            <div className="sticky top-0 z-10 bg-black/95 backdrop-blur-sm px-8 py-4 border-b border-zinc-800/50">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-2xl font-bold text-white">
                    {activeFeed ? feeds.find(f => f.id === activeFeed)?.title : t('sidebar.subscriptions')}
                  </h2>
                  <p className="text-zinc-500 text-sm mt-1">
                    {activeFeed
                      ? `${filteredEpisodes.length} ${t('episode.episodes')}`
                      : `${feeds.length} ${t('feed.subscriptions')}`
                    }
                  </p>
                </div>
                <div className="flex gap-3">
                  {activeFeed && (
                    <div className="relative group">
                      <Search className="absolute left-3 top-2.5 text-zinc-500 group-focus-within:text-indigo-400 transition-colors" size={18} />
                      <input
                        type="text"
                        placeholder={t('episode.searchPlaceholder')}
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="bg-zinc-900 border border-zinc-800 rounded-xl pl-10 pr-4 py-2 text-sm text-zinc-200 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/50 w-64 transition-all"
                      />
                    </div>
                  )}
                  {/* 视图切换按钮 */}
                  <div className="flex bg-zinc-800 rounded-xl p-1">
                    <button
                      onClick={() => setEpisodeViewMode('grid')}
                      className={`p-2 rounded-lg transition-colors ${episodeViewMode === 'grid' ? 'bg-zinc-700 text-white' : 'text-zinc-400 hover:text-white'}`}
                      title={t('view.grid')}
                    >
                      <LayoutGrid size={16} />
                    </button>
                    <button
                      onClick={() => setEpisodeViewMode('list')}
                      className={`p-2 rounded-lg transition-colors ${episodeViewMode === 'list' ? 'bg-zinc-700 text-white' : 'text-zinc-400 hover:text-white'}`}
                      title={t('view.list')}
                    >
                      <List size={16} />
                    </button>
                  </div>
                  <button
                    onClick={() => loadData()}
                    className="flex items-center gap-2 px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded-xl text-sm font-medium transition-colors"
                  >
                    <RefreshCw size={16} />
                  </button>
                </div>
              </div>
            </div>

            <div className={`p-8 grid ${episodeViewMode === 'list' ? 'grid-cols-1 gap-3' : 'grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-4'} ${currentPlaying ? 'pb-24' : ''}`}>
              {activeFeed ? (
                // 显示选中Feed的Episodes
                filteredEpisodes.map(ep => (
                  <EpisodeCard
                    key={ep.id}
                    episode={ep}
                    onClick={handleEpisodeClick}
                    onStar={handleStar}
                    onPlay={handlePlay}
                    viewMode={episodeViewMode}
                    feedImage={activeFeed?.image}
                  />
                ))
              ) : (
                // 显示所有订阅源卡片
                feeds.map(feed => (
                  <FeedCard
                    key={feed.id}
                    feed={feed}
                    onClick={handleFeedClick}
                    onRefresh={handleRefreshFeed}
                    viewMode={episodeViewMode}
                  />
                ))
              )}
            </div>
          </div>
        ) : view === 'feedDetail' ? (
          <FeedDetailView
            feed={selectedFeed}
            episodes={feedEpisodes}
            loading={feedEpisodesLoading}
            onBack={() => { setView('list'); setActiveFeed(null); setSelectedFeed(null); setFeedEpisodes([]); }}
            onRefresh={handleRefreshFeed}
            onEpisodeClick={handleEpisodeClick}
            onPlay={handlePlay}
            onStar={handleStar}
            viewMode={episodeViewMode}
            onViewModeChange={setEpisodeViewMode}
          />
        ) : view === 'favorites' ? (
          <FavoritesView
            episodes={episodes}
            feeds={feeds}
            onEpisodeClick={handleEpisodeClick}
            onPlay={handlePlay}
            onStar={handleStar}
            viewMode={episodeViewMode}
            onViewModeChange={setEpisodeViewMode}
          />
        ) : view === 'workspace' ? (
          <WorkspaceView
            episodes={workspaceEpisodes}
            feeds={feeds}
            onEpisodeClick={handleEpisodeClick}
            onPlay={handlePlay}
            onStar={handleStar}
            viewMode={episodeViewMode}
            onViewModeChange={setEpisodeViewMode}
          />
        ) : (
          <EpisodeDetailView
            episode={selectedEpisode}
            onBack={() => { setView(selectedFeed ? 'feedDetail' : 'list'); setSelectedEpisode(null); }}
            onRefresh={loadData}
            onPlay={handlePlay}
          />
        )}
      </div>

      {/* 隐藏的audio元素 */}
      <audio
        ref={audioRef}
        src={currentPlaying?.audio_url}
        preload="metadata"
      />

      <PlayerBar
        episode={currentPlaying}
        isPlaying={isPlaying}
        onPlayPause={handlePlayPause}
        onSeek={handleSeek}
        audioRef={audioRef}
      />

      {/* 任务进度面板 */}
      <TaskPanel onTaskComplete={loadData} />
    </div>
  );
}
