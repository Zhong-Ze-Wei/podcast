import React from 'react';
import { Activity, Menu } from 'lucide-react';
import { useTasks } from '../tasks/TasksContext';

export default function MobileHeader({ mode, onOpenMenu, onOpenTasks }) {
  const { activeTasks } = useTasks();
  return <header className="mobile-app-header md:hidden">
    <button aria-label="打开主菜单" onClick={onOpenMenu}><Menu size={22} /></button>
    <span>{mode === 'ai-briefing' ? 'AI 简报' : '传统播客'}</span>
    <button aria-label="打开任务" onClick={onOpenTasks}><Activity size={20} />{activeTasks.length > 0 && <small>{activeTasks.length}</small>}</button>
  </header>;
}
