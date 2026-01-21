// -*- coding: utf-8 -*-
import React, { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import {
  LayoutGrid, Plus, Mic2, Briefcase,
  Star, RefreshCw, X, Trash2, MoreVertical, Edit3, Heart
} from 'lucide-react';
import { feedsApi } from '../../services/api';

/**
 * Sidebar - 侧边栏组件
 *
 * 包含：
 * - 应用标题
 * - 导航菜单（所有节目、我的喜欢、已下载、已转录）
 * - 订阅源列表（带右键菜单）
 * - 添加订阅按钮和模态框
 * - 备注模态框
 */
const Sidebar = ({
  feeds,
  activeFeed,
  setActiveFeed,
  setSelectedFeed,
  setView,
  onAddFeed,
  onRefreshFeed,
  onDeleteFeed,
  onStarFeed,
  onNoteFeed,
  onFeedClick,
  hasPlayer,
  currentView
}) => {
  const { t } = useTranslation();
  const [showAddModal, setShowAddModal] = useState(false);
  const [newFeedUrl, setNewFeedUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [menuOpen, setMenuOpen] = useState(null);
  const [showNoteModal, setShowNoteModal] = useState(false);
  const [noteFeed, setNoteFeed] = useState(null);
  const [noteText, setNoteText] = useState('');
  const menuRef = useRef(null);

  // 点击外部关闭菜单
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(null);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleAddFeed = async (e) => {
    e.preventDefault();
    if (!newFeedUrl.trim()) return;

    setLoading(true);
    setError('');
    try {
      await feedsApi.create({ rss_url: newFeedUrl });
      setShowAddModal(false);
      setNewFeedUrl('');
      if (onAddFeed) onAddFeed();
    } catch (err) {
      setError(err.message || t('feed.addFailed'));
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async (feedId) => {
    setMenuOpen(null);
    try {
      await feedsApi.refresh(feedId);
      if (onRefreshFeed) onRefreshFeed();
    } catch (err) {
      console.error('Refresh failed:', err);
    }
  };

  const handleDelete = async (feedId) => {
    setMenuOpen(null);
    if (!window.confirm(t('feed.confirmDelete'))) return;
    try {
      await feedsApi.delete(feedId);
      if (onDeleteFeed) onDeleteFeed();
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  const handleStar = async (feed) => {
    setMenuOpen(null);
    if (onStarFeed) {
      // 传递 feed 对象给 App.jsx，由它处理 API 调用和乐观更新
      onStarFeed(feed);
    } else {
      // 兜底：直接调用 API（不推荐）
      try {
        await feedsApi.favorite(feed.id, { favorite: !feed.is_favorite });
      } catch (err) {
        console.error('Star failed:', err);
      }
    }
  };

  const openNoteModal = (feed) => {
    setMenuOpen(null);
    setNoteFeed(feed);
    setNoteText(feed.note || '');
    setShowNoteModal(true);
  };

  const handleSaveNote = async () => {
    if (!noteFeed) return;
    try {
      await feedsApi.update(noteFeed.id, { note: noteText });
      if (onNoteFeed) onNoteFeed();
      setShowNoteModal(false);
      setNoteFeed(null);
      setNoteText('');
    } catch (err) {
      console.error('Save note failed:', err);
    }
  };

  return (
    <div className="w-64 bg-zinc-950 border-r border-zinc-800 flex flex-col h-full flex-shrink-0">
      <div className="p-6">
        <h1 className="text-xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-purple-400 flex items-center gap-2">
          <Mic2 className="text-indigo-500" />
          {t('app.title')}
        </h1>
      </div>

      <div className="px-4 mb-4 space-y-1">
        <button
          onClick={() => { setActiveFeed(null); setSelectedFeed(null); setView('list'); }}
          className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all duration-200 ${currentView === 'list' && !activeFeed ? 'bg-zinc-900 text-white shadow-lg shadow-zinc-900/50' : 'text-zinc-400 hover:text-white hover:bg-zinc-900/50'}`}
        >
          <LayoutGrid size={18} />
          {t('sidebar.allEpisodes')}
        </button>
        <button
          onClick={() => { setActiveFeed(null); setSelectedFeed(null); setView('favorites'); }}
          className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all duration-200 ${currentView === 'favorites' ? 'bg-yellow-600/10 text-yellow-300 border border-yellow-500/20' : 'text-zinc-400 hover:text-white hover:bg-zinc-900/50'}`}
        >
          <Star size={18} />
          {t('sidebar.favorites')}
        </button>
        <button
          onClick={() => { setActiveFeed(null); setSelectedFeed(null); setView('workspace'); }}
          className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all duration-200 ${currentView === 'workspace' ? 'bg-emerald-600/10 text-emerald-300 border border-emerald-500/20' : 'text-zinc-400 hover:text-white hover:bg-zinc-900/50'}`}
        >
          <Briefcase size={18} />
          {t('sidebar.workspace')}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 space-y-1 custom-scrollbar">
        <div className="text-xs font-semibold text-zinc-500 px-3 py-2 uppercase tracking-wider">{t('sidebar.subscriptions')}</div>
        {feeds.map(feed => (
          <div
            key={feed.id}
            className={`relative w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all duration-200 group cursor-pointer ${activeFeed === feed.id ? 'bg-indigo-600/10 text-indigo-300 border border-indigo-500/20' : 'text-zinc-400 hover:text-white hover:bg-zinc-900/50'}`}
            onClick={() => onFeedClick ? onFeedClick(feed) : null}
          >
            <img
              src={feed.image || '/placeholder.png'}
              alt={feed.title}
              className="w-6 h-6 rounded-md object-cover opacity-80 group-hover:opacity-100"
              onError={(e) => {
                if (!e.target.dataset.fallback) {
                  e.target.dataset.fallback = 'true';
                  e.target.src = '/placeholder.png';
                }
              }}
            />
            <span className="truncate flex-1 text-left">{feed.title}</span>
            {feed.is_favorite && <Heart size={12} className="text-pink-400" fill="currentColor" />}
            {feed.unread_count > 0 && (
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-500"></span>
            )}
            {/* 三点菜单按钮 */}
            <button
              onClick={(e) => { e.stopPropagation(); setMenuOpen(menuOpen === feed.id ? null : feed.id); }}
              className="p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-zinc-700 transition-all"
            >
              <MoreVertical size={14} />
            </button>
            {/* 下拉菜单 */}
            {menuOpen === feed.id && (
              <div
                ref={menuRef}
                className="absolute right-0 top-full mt-1 w-36 bg-zinc-800 border border-zinc-700 rounded-lg shadow-xl z-50 overflow-hidden"
                onClick={(e) => e.stopPropagation()}
              >
                <button
                  onClick={() => handleRefresh(feed.id)}
                  className="w-full flex items-center gap-2 px-3 py-2 text-xs text-zinc-300 hover:bg-zinc-700 hover:text-white transition-colors"
                >
                  <RefreshCw size={12} />
                  {t('feed.menu.refresh')}
                </button>
                <button
                  onClick={() => handleStar(feed)}
                  className="w-full flex items-center gap-2 px-3 py-2 text-xs text-zinc-300 hover:bg-zinc-700 hover:text-white transition-colors"
                >
                  <Heart size={12} className={feed.is_favorite ? 'text-pink-400' : ''} fill={feed.is_favorite ? 'currentColor' : 'none'} />
                  {feed.is_favorite ? t('feed.menu.unfavorite') : t('feed.menu.favorite')}
                </button>
                <button
                  onClick={() => openNoteModal(feed)}
                  className="w-full flex items-center gap-2 px-3 py-2 text-xs text-zinc-300 hover:bg-zinc-700 hover:text-white transition-colors"
                >
                  <Edit3 size={12} />
                  {t('feed.menu.note')}
                </button>
                <div className="border-t border-zinc-700"></div>
                <button
                  onClick={() => handleDelete(feed.id)}
                  className="w-full flex items-center gap-2 px-3 py-2 text-xs text-red-400 hover:bg-red-900/30 hover:text-red-300 transition-colors"
                >
                  <Trash2 size={12} />
                  {t('feed.menu.delete')}
                </button>
              </div>
            )}
          </div>
        ))}
      </div>

      <div className={`p-4 border-t border-zinc-800 ${hasPlayer ? 'pb-24' : ''}`}>
        <button
          onClick={() => setShowAddModal(true)}
          className="flex items-center gap-2 text-zinc-400 hover:text-indigo-400 text-xs font-medium transition-colors w-full justify-center py-2 border border-zinc-800 rounded-lg hover:border-indigo-500/30 hover:bg-zinc-900"
        >
          <Plus size={14} /> {t('sidebar.addPodcast')}
        </button>
      </div>

      {showAddModal && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
          <div className="bg-zinc-900 rounded-2xl p-6 w-96 border border-zinc-800">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-white">{t('feed.addTitle')}</h3>
              <button onClick={() => setShowAddModal(false)} className="text-zinc-400 hover:text-white">
                <X size={20} />
              </button>
            </div>
            <form onSubmit={handleAddFeed}>
              <input
                type="url"
                value={newFeedUrl}
                onChange={(e) => setNewFeedUrl(e.target.value)}
                placeholder={t('feed.urlPlaceholder')}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500 mb-3"
                required
              />
              {error && <p className="text-red-400 text-xs mb-3">{error}</p>}
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="flex-1 py-2 text-zinc-400 hover:text-white text-sm font-medium"
                >
                  {t('feed.cancel')}
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="flex-1 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-medium disabled:opacity-50"
                >
                  {loading ? t('feed.adding') : t('feed.addFeed')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 备注模态框 */}
      {showNoteModal && noteFeed && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
          <div className="bg-zinc-900 rounded-2xl p-6 w-96 border border-zinc-800">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-white">{t('feed.noteTitle')}</h3>
              <button onClick={() => { setShowNoteModal(false); setNoteFeed(null); }} className="text-zinc-400 hover:text-white">
                <X size={20} />
              </button>
            </div>
            <div className="mb-3">
              <p className="text-sm text-zinc-400 mb-2">{noteFeed.title}</p>
              <textarea
                value={noteText}
                onChange={(e) => setNoteText(e.target.value)}
                placeholder={t('feed.notePlaceholder')}
                className="w-full h-32 bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500 resize-none"
              />
            </div>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => { setShowNoteModal(false); setNoteFeed(null); }}
                className="flex-1 py-2 text-zinc-400 hover:text-white text-sm font-medium"
              >
                {t('feed.cancel')}
              </button>
              <button
                onClick={handleSaveNote}
                className="flex-1 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-medium"
              >
                {t('feed.saveNote')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Sidebar;
