import { localizeUiMessage } from '../../utils/localization';
// -*- coding: utf-8 -*-
import React, { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import {
  X, Download, Mic2, Sparkles, RefreshCw, CheckCircle2,
  AlertCircle, Loader2, Activity, Clock3, Grip, ChevronRight, FileText
} from 'lucide-react';
import useMediaQuery from '../../hooks/useMediaQuery';
import useDialogFocus from '../../hooks/useDialogFocus';
import { shouldAutoOpenTaskPanel } from '../../utils/taskPanelPolicy';
import { useTasks } from './TasksContext';
import { briefingTaskLabel, getBriefingTaskPeriod } from '../../utils/briefingTask';
import { getTaskNavigation } from '../../utils/taskNavigation';
import { isActiveTask, isTerminalTask, canCancelTask } from '../../utils/taskActions';
import { subscriptionProgress } from '../../utils/subscriptionTask';

const TASK_PANEL_SIZE_KEY = 'podcast_task_panel_size';
const DEFAULT_PANEL_SIZE = { width: 352, height: 480 };
const MIN_PANEL_SIZE = { width: 320, height: 360 };

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function readPanelSize() {
  try {
    const saved = JSON.parse(localStorage.getItem(TASK_PANEL_SIZE_KEY) || 'null');
    if (!saved) return DEFAULT_PANEL_SIZE;
    return {
      width: clamp(Number(saved.width) || DEFAULT_PANEL_SIZE.width, MIN_PANEL_SIZE.width, 720),
      height: clamp(Number(saved.height) || DEFAULT_PANEL_SIZE.height, MIN_PANEL_SIZE.height, 760)
    };
  } catch {
    return DEFAULT_PANEL_SIZE;
  }
}

const TaskPanel = ({
  onRetrySubscription,
  onNavigate,
  historyWindowMinutes = 60,
  defaultOpen = false,
  openRequest = 0
}) => {
  const { t, i18n } = useTranslation();
  const { activeTasks, historyTasks: allHistoryTasks, error: requestError, cancel, refresh } = useTasks();
  const historyCutoff = Date.now() - historyWindowMinutes * 60 * 1000;
  const historyTasks = allHistoryTasks.filter(task => task.completed_at && new Date(task.completed_at).getTime() > historyCutoff);
  const mobile = useMediaQuery('(max-width: 767px)');
  const [isOpen, setIsOpen] = useState(defaultOpen && !mobile);
  const panelRef = useRef(null);
  const [activeTab, setActiveTab] = useState('active');
  const [dismissedTaskIds, setDismissedTaskIds] = useState(() => new Set());
  const [panelSize, setPanelSize] = useState(readPanelSize);
  const panelSizeRef = useRef(panelSize);
  const userClosedDuringActiveRef = useRef(false);
  const previousActiveCountRef = useRef(0);
  const resizeStateRef = useRef(null);

  const visibleHistoryTasks = historyTasks.filter(task => !dismissedTaskIds.has(task.id));

  useEffect(() => {
    if (!activeTasks.length) userClosedDuringActiveRef.current = false;
    if (shouldAutoOpenTaskPanel({ mobile, activeCount: activeTasks.length, previousActiveCount: previousActiveCountRef.current, userClosed: userClosedDuringActiveRef.current })) {
      setIsOpen(true);
      setActiveTab('active');
    }
    previousActiveCountRef.current = activeTasks.length;
  }, [activeTasks.length, mobile]);

  useEffect(() => {
    if (defaultOpen && !mobile) setIsOpen(true);
  }, [defaultOpen, mobile]);
  useEffect(() => { if (mobile) setIsOpen(false); }, [mobile]);
  useEffect(() => { if (openRequest) { refresh(); setIsOpen(true); } }, [openRequest, refresh]);

  const closePanel = () => {
    if (activeTasks.length > 0) {
      userClosedDuringActiveRef.current = true;
    }
    setIsOpen(false);
  };

  useDialogFocus(panelRef, mobile && isOpen, closePanel);

  useEffect(() => {
    const handlePointerMove = (event) => {
      const state = resizeStateRef.current;
      if (!state) return;

      const maxWidth = Math.max(MIN_PANEL_SIZE.width, window.innerWidth - 40);
      const maxHeight = Math.max(MIN_PANEL_SIZE.height, window.innerHeight - 180);
      const nextSize = {
        width: clamp(state.width + state.x - event.clientX, MIN_PANEL_SIZE.width, maxWidth),
        height: clamp(state.height + state.y - event.clientY, MIN_PANEL_SIZE.height, maxHeight)
      };
      panelSizeRef.current = nextSize;
      setPanelSize(nextSize);
    };

    const handlePointerUp = () => {
      if (!resizeStateRef.current) return;
      resizeStateRef.current = null;
      localStorage.setItem(TASK_PANEL_SIZE_KEY, JSON.stringify(panelSizeRef.current));
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };

    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerUp);
    return () => {
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, []);

  const handleResizeStart = (event) => {
    event.preventDefault();
    resizeStateRef.current = {
      x: event.clientX,
      y: event.clientY,
      width: panelSize.width,
      height: panelSize.height
    };
    document.body.style.cursor = 'nwse-resize';
    document.body.style.userSelect = 'none';
  };

  const handleCancel = cancel;

  const handleDismiss = (taskId) => {
    setDismissedTaskIds(prev => {
      const next = new Set(prev);
      next.add(taskId);
      return next;
    });
  };

  const handleClearHistory = () => {
    setDismissedTaskIds(prev => {
      const next = new Set(prev);
      historyTasks.forEach(task => {
        if (task.id) next.add(task.id);
      });
      return next;
    });
  };

  const getTaskTargetLabel = (task) => {
    const periodLabel = briefingTaskLabel(task, i18n.language);
    if (periodLabel) return periodLabel;
    if (task.episode_title || task.report_context?.source_title) return task.episode_title || task.report_context.source_title;
    if (task.feed_title || task.report_context?.feed_title) return task.feed_title || task.report_context.feed_title;
    if (task.target_exists === false) return t('tasks.targetDeleted');
    if (task.episode_id) return t('tasks.unknownEpisode');
    if (task.feed_id) return t('tasks.unknownFeed');
    return '';
  };

  const getTaskMetaLabel = (task) => {
    const parts = [];
    const feedTitle = task.feed_title || task.report_context?.feed_title;
    if (feedTitle && (task.episode_title || task.report_context?.source_title)) parts.push(feedTitle);
    if (task.target_exists === false) parts.push(t('tasks.targetDeleted'));
    return parts.join(' · ');
  };

  const canOpenTask = (task) => Boolean(onNavigate && getTaskNavigation(task));

  const handleOpenTask = (task) => {
    if (!canOpenTask(task)) return;
    onNavigate(getTaskNavigation(task));
    setIsOpen(false);
  };

  const getTaskTypeLabel = (task) => {
    if (task.type !== 'briefing-report') return t(`tasks.types.${task.type}`);
    if (task.report_context?.kind === 'reading') return t('tasks.singleReading');
    const period = getBriefingTaskPeriod(task);
    return t(period?.type === 'month' ? 'tasks.monthlyBriefing' : period?.type === 'week' ? 'tasks.weeklyBriefing' : 'tasks.types.briefing-report');
  };

  const getTaskOpenLabel = (task) => {
    if (task.report_context?.kind === 'reading') return t('tasks.openReading');
    const navigation = getTaskNavigation(task);
    if (navigation?.type === 'briefing') return t('tasks.openBriefing');
    return t(navigation?.type === 'feed' ? 'tasks.openFeed' : 'tasks.openEpisode');
  };

  const getTaskIcon = (type) => {
    switch (type) {
      case 'download': return <Download size={16} />;
      case 'transcribe': return <Mic2 size={16} />;
      case 'briefing-report': return <Sparkles size={16} />;
      case 'summarize': return <Sparkles size={16} />;
      case 'refresh': return <RefreshCw size={16} />;
      case 'subscribe': return <RefreshCw size={16} />;
      case 'fetch_transcripts': return <FileText size={16} />;
      default: return <Loader2 size={16} />;
    }
  };

  const getStatusStyle = (status) => {
    switch (status) {
      case 'pending': return 'text-zinc-400';
      case 'processing': return 'text-sky-400';
      case 'completed': return 'text-emerald-400';
      case 'failed': return 'text-red-400';
      case 'cancelled': return 'text-zinc-400';
      default: return 'text-zinc-400';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'pending': return <Loader2 size={14} className="animate-pulse" />;
      case 'processing': return <Loader2 size={14} className="animate-spin" />;
      case 'completed': return <CheckCircle2 size={14} />;
      case 'failed': return <AlertCircle size={14} />;
      case 'cancelled': return <X size={14} />;
      default: return null;
    }
  };

  const formatRelativeTime = (value) => {
    if (!value) return '';
    const diffSeconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
    if (diffSeconds < 5) return t('tasks.justNow');
    if (diffSeconds < 60) return t('tasks.time.secondsAgo', { count: diffSeconds });
    const diffMinutes = Math.floor(diffSeconds / 60);
    if (diffMinutes < 60) return t('tasks.time.minutesAgo', { count: diffMinutes });
    const diffHours = Math.floor(diffMinutes / 60);
    if (diffHours < 24) return t('tasks.time.hoursAgo', { count: diffHours });
    return t('tasks.time.daysAgo', { count: Math.floor(diffHours / 24) });
  };

  const renderTask = (task) => {
    const isActive = isActiveTask(task);
    const errorMessage = ['refresh', 'fetch_transcripts', 'subscribe'].includes(task.type)
      ? t('common.fetchUnavailable')
      : localizeUiMessage(task.error_message, t);
    const targetLabel = getTaskTargetLabel(task);
    const metaLabel = getTaskMetaLabel(task);
    const isOpenable = canOpenTask(task);
    const progress = clamp(task.progress || 0, 0, 100);
    const hasAction = canCancelTask(task) || isTerminalTask(task);
    const Content = isOpenable ? 'button' : 'div';
    return (
      <article
        key={task.id}
        data-task-id={task.id}
        className={`group relative mx-3 my-3 overflow-hidden rounded-xl border bg-zinc-950/40 transition-colors ${task.status === 'processing' ? 'border-sky-500/25' : 'border-zinc-800'} ${isOpenable ? 'hover:border-sky-500/50 hover:bg-zinc-950/70' : ''}`}
      >
        <Content
          {...(isOpenable ? { type: 'button', onClick: () => handleOpenTask(task), 'aria-label': `${getTaskOpenLabel(task)} · ${targetLabel || getTaskTypeLabel(task)}` } : {})}
          className="block w-full min-w-0 p-3.5 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-sky-400"
        >
          <div className={`flex items-center justify-between gap-2 ${hasAction ? 'pr-6' : ''}`}>
            <span className="flex min-w-0 items-center gap-2 text-[11px] font-medium text-zinc-400">
              <span className={getStatusStyle(task.status)}>{getTaskIcon(task.type)}</span>
              <span className="truncate">{getTaskTypeLabel(task)}</span>
            </span>
            <span className={`flex shrink-0 items-center gap-1 text-[11px] ${getStatusStyle(task.status)}`}>
              {getStatusIcon(task.status)}
              {task.cancel_requested ? t('tasks.cancelRequested') : t(`tasks.status.${task.status}`)}
            </span>
          </div>

          <p className="mt-3 line-clamp-2 break-words text-sm font-semibold leading-6 text-zinc-100">
            {targetLabel || getTaskTypeLabel(task)}
          </p>
          {metaLabel && <p className="mt-1 truncate text-[11px] text-zinc-500">{metaLabel}</p>}

          {isActive && (
            <div className="mt-3">
              {task.progress_message && (
                <p className="mb-2 line-clamp-2 text-[11px] leading-5 text-zinc-400">{localizeUiMessage(subscriptionProgress(task.progress_message, t), t)}</p>
              )}
              <div
                role="progressbar"
                aria-label={targetLabel || getTaskTypeLabel(task)}
                aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress}
                className="h-1 bg-zinc-800 rounded-full overflow-hidden"
              >
                <div
                  className={`h-full rounded-full transition-all duration-300 motion-reduce:transition-none ${task.status === 'processing' ? 'bg-sky-400' : 'bg-zinc-600'}`}
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
          )}

          {task.status === 'failed' && task.error_message && (
            <p className="mt-2 line-clamp-2 text-xs leading-5 text-red-400" title={errorMessage}>
              {errorMessage}
            </p>
          )}

          <div className="mt-3 flex items-center justify-between gap-2 border-t border-zinc-800/70 pt-2.5 text-[11px]">
            {isActive ? <span className="font-mono tabular-nums text-zinc-500">{progress}%</span> : <span className="flex items-center gap-1 text-zinc-500"><Clock3 size={12} />{formatRelativeTime(task.completed_at)}</span>}
            {isOpenable && <span className="flex items-center gap-1 font-medium text-sky-300">{getTaskOpenLabel(task)}<ChevronRight size={14} className="transition-transform motion-safe:group-hover:translate-x-0.5" /></span>}
          </div>
        </Content>
        {task.type === 'subscribe' && task.status === 'failed' && task.report_context?.url && <button type="button" onClick={() => { onRetrySubscription(task.report_context.url); setActiveTab('active'); }} className="mx-4 mb-3 rounded-md bg-sky-500/10 px-3 py-1.5 text-xs text-sky-300 hover:bg-sky-500/20">{t('tasks.retrySubscription')}</button>}
        {hasAction && <button
          type="button"
          onClick={() => isActive ? handleCancel(task.id) : handleDismiss(task.id)}
          aria-label={isActive ? t('tasks.cancel') : t('tasks.dismiss')}
          className="absolute right-2 top-2 rounded-md p-1.5 text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400"
        ><X size={14} /></button>}
      </article>
    );
  };

  const visibleTasks = activeTab === 'active' ? activeTasks : visibleHistoryTasks;
  const hasActiveTasks = activeTasks.length > 0;
  const hasFailures = visibleHistoryTasks.some(task => task.status === 'failed');

  return (
    <>
      {isOpen && (
        <div
          ref={panelRef} role={mobile ? 'dialog' : undefined} aria-modal={mobile ? true : undefined} aria-label={t('tasks.title')} className="task-panel fixed bottom-40 right-5 z-50 flex max-h-[calc(100vh-12rem)] max-w-[calc(100vw-2rem)] flex-col overflow-hidden rounded-xl border border-zinc-700 bg-zinc-900 shadow-2xl shadow-black/50"
          style={{ width: `${panelSize.width}px`, height: `${panelSize.height}px` }}
        >
          {!mobile && <button
            onPointerDown={handleResizeStart}
            className="absolute left-1 top-1 z-10 flex h-6 w-6 cursor-nwse-resize items-center justify-center rounded-md text-zinc-600 hover:bg-zinc-800 hover:text-zinc-300"
            title={t('tasks.resizePanel')}
          >
            <Grip size={13} />
          </button>}
          <div className="flex items-center justify-between px-4 py-3 bg-zinc-950/70 border-b border-zinc-800">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-zinc-700 bg-zinc-900 text-sky-400">
                <Activity size={16} className={hasActiveTasks ? 'animate-pulse' : ''} />
              </div>
              <div>
                <div className="text-sm font-semibold text-zinc-100">{t('tasks.title')}</div>
                <div className="text-xs text-zinc-500">
                  {hasActiveTasks
                    ? t('tasks.activeCount', { count: activeTasks.length })
                    : t('tasks.recentCount', { count: visibleHistoryTasks.length })}
                </div>
              </div>
            </div>
            <button
              onClick={closePanel}
              aria-label={t("ui.closeTasks")}
              className="p-1.5 rounded-md text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
              title={t('tasks.dismiss')}
            >
              <X size={16} />
            </button>
          </div>

          <div className="flex items-center justify-between gap-2 px-3 py-2 bg-zinc-900 border-b border-zinc-800">
            <div className="grid grid-cols-2 gap-1 rounded-lg bg-zinc-950 p-1">
              <button
                onClick={() => setActiveTab('active')}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${activeTab === 'active' ? 'bg-sky-600 text-white' : 'text-zinc-500 hover:text-zinc-200'}`}
              >
                {t('tasks.tabs.active')} {activeTasks.length > 0 ? activeTasks.length : ''}
              </button>
              <button
                onClick={() => setActiveTab('history')}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${activeTab === 'history' ? 'bg-sky-600 text-white' : 'text-zinc-500 hover:text-zinc-200'}`}
              >
                {t('tasks.tabs.history')} {visibleHistoryTasks.length > 0 ? visibleHistoryTasks.length : ''}
              </button>
            </div>

            {activeTab === 'history' && visibleHistoryTasks.length > 0 && (
              <button
                onClick={handleClearHistory}
                className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
              >
                {t('tasks.clearCompleted')}
              </button>
            )}
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto custom-scrollbar">
            {requestError && <div role="alert" className="mx-3 mt-3 rounded-lg bg-red-900/20 p-3 text-xs text-red-300">{localizeUiMessage(requestError, t)}</div>}
            {visibleTasks.length > 0 ? (
              visibleTasks.map(renderTask)
            ) : (
              <div className="flex flex-col items-center justify-center px-6 py-10 text-center">
                <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg border border-zinc-800 bg-zinc-950 text-zinc-600">
                  {activeTab === 'active' ? <Loader2 size={18} /> : <Clock3 size={18} />}
                </div>
                <p className="text-sm font-medium text-zinc-300">
                  {activeTab === 'active' ? t('tasks.emptyActive') : t('tasks.emptyHistory')}
                </p>
                <p className="mt-1 text-xs text-zinc-500">
                  {activeTab === 'active'
                    ? t('tasks.emptyActiveHint')
                    : t('tasks.emptyHistoryHint')}
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      <button
        onClick={() => { refresh(); setIsOpen(prev => !prev); }}
        aria-label={isOpen ? t('tasks.closePanel') : t('tasks.openPanel')} className="task-launcher fixed bottom-24 right-5 z-50 h-14 w-14 rounded-full border border-zinc-700 bg-zinc-900 text-zinc-100 shadow-2xl shadow-black/50 transition-transform hover:scale-105 hover:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/60"
        title={isOpen ? t('tasks.closePanel') : t('tasks.openPanel')}
      >
        <span
          className={`absolute inset-0 rounded-full opacity-80 ${hasActiveTasks ? 'animate-spin' : ''}`}
          style={{
            background: hasActiveTasks
              ? 'conic-gradient(from 120deg, rgba(14,165,233,0), rgba(14,165,233,0.95), rgba(16,185,129,0.85), rgba(14,165,233,0))'
              : hasFailures
                ? 'conic-gradient(from 120deg, rgba(239,68,68,0), rgba(239,68,68,0.9), rgba(239,68,68,0))'
                : 'conic-gradient(from 120deg, rgba(63,63,70,0), rgba(113,113,122,0.8), rgba(63,63,70,0))'
          }}
        />
        <span className="absolute inset-[3px] rounded-full bg-zinc-950" />
        <span className="relative flex h-full w-full items-center justify-center">
          {hasActiveTasks ? <Loader2 size={22} className="animate-spin text-sky-400" /> : <Activity size={22} className="text-zinc-300" />}
        </span>
        {hasActiveTasks && (
          <span className="absolute -right-1 -top-1 min-w-5 rounded-full bg-sky-500 px-1.5 py-0.5 text-[11px] font-bold text-white">
            {activeTasks.length}
          </span>
        )}
        {!hasActiveTasks && visibleHistoryTasks.length > 0 && (
          <span className="absolute -right-1 -top-1 h-3 w-3 rounded-full border-2 border-zinc-950 bg-emerald-400" />
        )}
      </button>
    </>
  );
};

export default TaskPanel;
