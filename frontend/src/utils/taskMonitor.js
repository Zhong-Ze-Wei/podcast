import { isActiveTask, isTerminalTask } from './taskActions.js';

export async function submitTranscription(episodeId, provider, language, create) {
  return (await create(episodeId, { provider, language, download_if_needed: true })).data;
}

export function getEpisodeTaskId(episode, type, submitted) {
  return submitted || episode?.active_tasks?.find(task => task.task_type === type)?.task_id || null;
}

// 一个用户会话只维护一份任务快照；详情通过明确 ID 订阅同一份状态。
export function createTaskMonitor({ list, get, cancel, onChange = () => {}, onTerminal = () => {} }) {
  let state = { activeTasks: [], historyTasks: [], byId: {}, errorsById: {}, error: '' };
  let pending = null;
  let initialized = false;
  let disposed = false;
  const watched = new Map();
  const registered = new Map();
  const unavailable = new Set();
  const notified = new Set();
  const publish = next => { state = next; if (!disposed) onChange(state); };
  const run = async () => {
    if (disposed) return state;
    try {
      const [active, history] = await Promise.all([
        list({ status: 'pending,processing', per_page: 100 }),
        list({ status: 'completed,failed,cancelled', per_page: 50 }),
      ]);
      const activeTasks = [...active.data];
      let pagination = active.pagination;
      while (pagination?.has_next) {
        const next = await list({ status: 'pending,processing', per_page: 100, page: pagination.page + 1 });
        activeTasks.push(...next.data);
        pagination = next.pagination;
      }
      let tasks = [...activeTasks, ...history.data];
      const retainedTasks = [];
      const errorsById = { ...state.errorsById };
      const requested = [...new Set([...watched.keys(), ...registered.keys()])].filter(id => !tasks.some(task => task.id === id) && !unavailable.has(id));
      const lookups = await Promise.allSettled(requested.map(id => get(id)));
      lookups.forEach((result, index) => {
        const id = requested[index];
        if (result.status === 'fulfilled') { tasks.push(result.value.data); delete errorsById[id]; }
        else {
          const error = result.reason;
          const code = error.error_code || error.code;
          errorsById[id] = { code, message: error.message || '任务状态暂未读取，请重试。' };
          if (code === 'TASK_NOT_FOUND') { unavailable.add(id); registered.delete(id); }
          else if (state.byId[id]) retainedTasks.push(state.byId[id]);
        }
      });
      tasks.forEach(task => { registered.delete(task.id); unavailable.delete(task.id); delete errorsById[task.id]; });
      tasks.push(...retainedTasks);
      // GET 等待期间也可能提交新任务；它来自成功的提交响应，下一轮再由后端确认。
      tasks.push(...[...registered.values()].filter(task => !tasks.some(item => item.id === task.id)));
      if (disposed) return state;
      const byId = Object.fromEntries(tasks.map(task => [task.id, task]));
      const terminal = tasks.filter(task => {
        if (!isTerminalTask(task) || notified.has(task.id)) return false;
        notified.add(task.id);
        return initialized || (state.byId[task.id] && isActiveTask(state.byId[task.id]));
      });
      initialized = true;
      publish({ activeTasks: Object.values(byId).filter(isActiveTask), historyTasks: Object.values(byId).filter(isTerminalTask), byId, errorsById, error: '' });
      if (terminal.length) onTerminal(terminal);
    } catch (error) {
      if (!disposed) publish({ ...state, error: error.message });
    }
    return state;
  };
  const refresh = () => {
    if (pending) return pending;
    pending = run().finally(() => { pending = null; });
    return pending;
  };
  return {
    getState: () => state,
    refresh,
    add: task => { registered.set(task.id, task); unavailable.delete(task.id); publish({ ...state, byId: { ...state.byId, [task.id]: task }, activeTasks: [...state.activeTasks.filter(item => item.id !== task.id), task] }); },
    watch: id => { watched.set(id, (watched.get(id) || 0) + 1); return () => { const count = watched.get(id) - 1; if (count) watched.set(id, count); else watched.delete(id); }; },
    cancel: async id => { try { await cancel(id); await refresh(); } catch (error) { if (!disposed) publish({ ...state, error: error.message }); } },
    resume: () => { disposed = false; },
    dispose: () => { disposed = true; },
  };
}
