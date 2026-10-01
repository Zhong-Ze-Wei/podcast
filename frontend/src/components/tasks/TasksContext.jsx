import React, { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { tasksApi } from '../../services/api';
import { createTaskMonitor } from '../../utils/taskMonitor';

const TasksContext = createContext(null);

export function TasksProvider({ children, pollIntervalMs = 3000, onTaskComplete, queuedTask }) {
  const [state, setState] = useState({ activeTasks: [], historyTasks: [], byId: {}, error: '' });
  const callbackRef = useRef(onTaskComplete);
  callbackRef.current = onTaskComplete;
  const monitor = useMemo(() => createTaskMonitor({ list: tasksApi.list, get: tasksApi.get, cancel: tasksApi.cancel, onChange: setState, onTerminal: tasks => callbackRef.current?.(tasks) }), []);
  useEffect(() => {
    if (!queuedTask) return;
    monitor.add(queuedTask);
    monitor.refresh();
  }, [monitor, queuedTask]);
  useEffect(() => {
    monitor.resume();
    let lastFetch = 0;
    const refresh = () => { lastFetch = Date.now(); return monitor.refresh(); };
    refresh();
    const timer = setInterval(() => {
      if (!document.hidden && (monitor.getState().activeTasks.length || Date.now() - lastFetch >= 30000)) refresh();
    }, pollIntervalMs);
    const visible = () => { if (!document.hidden) refresh(); };
    document.addEventListener('visibilitychange', visible);
    return () => { clearInterval(timer); document.removeEventListener('visibilitychange', visible); monitor.dispose(); };
  }, [monitor, pollIntervalMs]);
  return <TasksContext.Provider value={{ ...state, refresh: monitor.refresh, watch: monitor.watch, register: monitor.add, cancel: monitor.cancel }}>{children}</TasksContext.Provider>;
}

export const useTasks = () => useContext(TasksContext);

export function useTask(taskId) {
  const tasks = useTasks();
  useEffect(() => {
    if (!taskId) return;
    const unwatch = tasks.watch(taskId);
    tasks.refresh();
    return unwatch;
  }, [taskId, tasks.watch, tasks.refresh]);
  return { task: tasks.byId[taskId], error: tasks.error, cancel: tasks.cancel };
}
