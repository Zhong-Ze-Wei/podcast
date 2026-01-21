// -*- coding: utf-8 -*-
import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  ChevronDown, ChevronUp, X, Download, Mic2, Sparkles,
  RefreshCw, CheckCircle2, AlertCircle, Loader2
} from 'lucide-react';
import { tasksApi } from '../../services/api';

/**
 * TaskPanel - 任务进度浮动面板
 * 显示下载、转录、摘要等异步任务的进度
 */
const TaskPanel = ({ onTaskComplete }) => {
  const { t } = useTranslation();
  const [tasks, setTasks] = useState([]);
  const [isExpanded, setIsExpanded] = useState(true);
  const [isVisible, setIsVisible] = useState(false);

  // 获取任务列表
  const fetchTasks = useCallback(async () => {
    try {
      const response = await tasksApi.list({ status: 'pending,processing' });
      const activeTasks = response.data.data || [];

      // 也获取最近完成/失败的任务 (最近5分钟)
      const recentResponse = await tasksApi.list({ per_page: 10 });
      const recentTasks = (recentResponse.data.data || []).filter(task => {
        if (task.status === 'pending' || task.status === 'processing') return false;
        const completedAt = new Date(task.completed_at);
        const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000);
        return completedAt > fiveMinutesAgo;
      });

      const allTasks = [...activeTasks, ...recentTasks];
      setTasks(allTasks);
      setIsVisible(allTasks.length > 0);

      // 检查是否有新完成的任务
      const completedTasks = activeTasks.filter(t => t.status === 'completed');
      if (completedTasks.length > 0 && onTaskComplete) {
        onTaskComplete();
      }
    } catch (err) {
      console.error('Failed to fetch tasks:', err);
    }
  }, [onTaskComplete]);

  // 定期轮询任务状态
  useEffect(() => {
    fetchTasks();
    const interval = setInterval(fetchTasks, 3000);
    return () => clearInterval(interval);
  }, [fetchTasks]);

  // 取消任务
  const handleCancel = async (taskId) => {
    try {
      await tasksApi.cancel(taskId);
      fetchTasks();
    } catch (err) {
      console.error('Failed to cancel task:', err);
    }
  };

  // 移除已完成任务
  const handleDismiss = (taskId) => {
    setTasks(prev => prev.filter(t => t.id !== taskId));
  };

  // 清除所有已完成任务
  const handleClearCompleted = () => {
    setTasks(prev => prev.filter(t => t.status === 'pending' || t.status === 'processing'));
  };

  // 任务类型图标
  const getTaskIcon = (type) => {
    switch (type) {
      case 'download': return <Download size={16} />;
      case 'transcribe': return <Mic2 size={16} />;
      case 'summarize': return <Sparkles size={16} />;
      case 'refresh': return <RefreshCw size={16} />;
      default: return <Loader2 size={16} />;
    }
  };

  // 任务状态样式
  const getStatusStyle = (status) => {
    switch (status) {
      case 'pending': return 'text-zinc-400';
      case 'processing': return 'text-blue-400';
      case 'completed': return 'text-green-400';
      case 'failed': return 'text-red-400';
      default: return 'text-zinc-400';
    }
  };

  // 任务状态图标
  const getStatusIcon = (status) => {
    switch (status) {
      case 'pending': return <Loader2 size={14} className="animate-pulse" />;
      case 'processing': return <Loader2 size={14} className="animate-spin" />;
      case 'completed': return <CheckCircle2 size={14} />;
      case 'failed': return <AlertCircle size={14} />;
      default: return null;
    }
  };

  if (!isVisible || tasks.length === 0) return null;

  const activeTasks = tasks.filter(t => t.status === 'pending' || t.status === 'processing');
  const completedTasks = tasks.filter(t => t.status === 'completed' || t.status === 'failed');

  return (
    <div className="fixed bottom-20 right-4 z-50 w-80 bg-zinc-900 border border-zinc-700 rounded-xl shadow-2xl overflow-hidden">
      {/* 头部 */}
      <div
        className="flex items-center justify-between px-4 py-3 bg-zinc-800/50 cursor-pointer"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-2">
          <Loader2 size={16} className={activeTasks.length > 0 ? 'animate-spin text-blue-400' : 'text-zinc-500'} />
          <span className="text-sm font-medium text-zinc-200">
            {t('tasks.title')}
          </span>
          {activeTasks.length > 0 && (
            <span className="px-1.5 py-0.5 text-xs bg-blue-600 text-white rounded-full">
              {activeTasks.length}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {completedTasks.length > 0 && (
            <button
              onClick={(e) => { e.stopPropagation(); handleClearCompleted(); }}
              className="text-xs text-zinc-500 hover:text-zinc-300"
            >
              {t('tasks.clearCompleted')}
            </button>
          )}
          {isExpanded ? <ChevronDown size={16} className="text-zinc-400" /> : <ChevronUp size={16} className="text-zinc-400" />}
        </div>
      </div>

      {/* 任务列表 */}
      {isExpanded && (
        <div className="max-h-64 overflow-y-auto custom-scrollbar">
          {tasks.map(task => (
            <div
              key={task.id}
              className="flex items-center gap-3 px-4 py-3 border-b border-zinc-800 last:border-b-0 hover:bg-zinc-800/30"
            >
              {/* 图标 */}
              <div className={`flex-shrink-0 ${getStatusStyle(task.status)}`}>
                {getTaskIcon(task.type)}
              </div>

              {/* 信息 */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-zinc-300 truncate">
                    {t(`tasks.types.${task.type}`)}
                  </span>
                  <span className={`flex items-center gap-1 text-xs ${getStatusStyle(task.status)}`}>
                    {getStatusIcon(task.status)}
                    {t(`tasks.status.${task.status}`)}
                  </span>
                </div>

                {/* 进度条 */}
                {(task.status === 'processing' || task.status === 'pending') && (
                  <div className="mt-1.5 h-1 bg-zinc-700 rounded-full overflow-hidden">
                    <div
                      className={`h-full transition-all duration-300 ${
                        task.status === 'processing' ? 'bg-blue-500' : 'bg-zinc-600'
                      }`}
                      style={{ width: `${task.progress || 0}%` }}
                    />
                  </div>
                )}

                {/* 错误信息 */}
                {task.status === 'failed' && task.error_message && (
                  <p className="text-xs text-red-400 mt-1 truncate" title={task.error_message}>
                    {task.error_message}
                  </p>
                )}
              </div>

              {/* 操作按钮 */}
              <div className="flex-shrink-0">
                {(task.status === 'pending') && (
                  <button
                    onClick={() => handleCancel(task.id)}
                    className="p-1 text-zinc-500 hover:text-red-400 transition-colors"
                    title={t('tasks.cancel')}
                  >
                    <X size={14} />
                  </button>
                )}
                {(task.status === 'completed' || task.status === 'failed') && (
                  <button
                    onClick={() => handleDismiss(task.id)}
                    className="p-1 text-zinc-500 hover:text-zinc-300 transition-colors"
                    title={t('tasks.dismiss')}
                  >
                    <X size={14} />
                  </button>
                )}
              </div>
            </div>
          ))}

          {tasks.length === 0 && (
            <div className="py-8 text-center text-zinc-500 text-sm">
              {t('tasks.empty')}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default TaskPanel;
