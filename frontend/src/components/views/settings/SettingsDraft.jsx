import React, { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react';

const SettingsDraftContext = createContext(null);

/**
 * 设置弹窗的暂存区：面板改动先写在这里，点「保存」才落库，点「取消」直接丢弃。
 *
 * committers 按 panelId 注册且不随面板卸载移除，所以切到别的标签再保存时，
 * 之前改过的标签也能一起提交。
 */
export function SettingsDraftProvider({ children }) {
  const [drafts, setDrafts] = useState({});
  const committers = useRef({});

  const stage = useCallback((panelId, changes) => {
    setDrafts(current => ({ ...current, [panelId]: { ...current[panelId], ...changes } }));
  }, []);

  const registerCommitter = useCallback((panelId, commit) => {
    committers.current[panelId] = commit;
  }, []);

  const reset = useCallback(() => setDrafts({}), []);

  const commitAll = useCallback(async () => {
    for (const [panelId, values] of Object.entries(drafts)) {
      const commit = committers.current[panelId];
      if (commit) await commit(values);
    }
    setDrafts({});
  }, [drafts]);

  const value = useMemo(() => ({
    drafts, stage, reset, commitAll, registerCommitter,
    dirtyPanelIds: Object.keys(drafts).filter(id => Object.keys(drafts[id]).length > 0),
    dirty: Object.values(drafts).some(panel => Object.keys(panel).length > 0),
  }), [drafts, stage, reset, commitAll, registerCommitter]);

  return <SettingsDraftContext.Provider value={value}>{children}</SettingsDraftContext.Provider>;
}

export function useSettingsDraft() {
  const context = useContext(SettingsDraftContext);
  if (!context) throw new Error('useSettingsDraft must be used inside SettingsDraftProvider');
  return context;
}

/** 面板用：暂存值覆盖服务端值，并注册提交函数。 */
export function useStagedSettings(panelId, serverValues, commit) {
  const { drafts, stage, registerCommitter } = useSettingsDraft();
  const staged = drafts[panelId] || {};
  const registered = useRef(null);
  if (registered.current !== commit) {
    registered.current = commit;
    registerCommitter(panelId, commit);
  }
  return {
    staged,
    values: serverValues ? { ...serverValues, ...staged } : staged,
    change: changes => stage(panelId, changes),
    hasStaged: Object.keys(staged).length > 0,
  };
}
