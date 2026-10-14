import { useTranslation } from 'react-i18next';
import React from 'react';
import { Activity, Menu } from 'lucide-react';
import { useTasks } from '../tasks/TasksContext';
import LanguageSwitcher from '../common/LanguageSwitcher';

export default function MobileHeader({ mode, onOpenMenu, onOpenTasks }) {
  const { t } = useTranslation();
  const { activeTasks } = useTasks();
  return <header className="mobile-app-header md:hidden">
    <button aria-label={t("ui.openMainMenu")} onClick={onOpenMenu}><Menu size={22} /></button>
    <span>{mode === 'ai-briefing' ? t("ui.aIBriefing") : t("ui.podcastLibrary")}</span>
    <LanguageSwitcher compact />
    <button aria-label={t("ui.openTasks")} onClick={onOpenTasks}><Activity size={20} />{activeTasks.length > 0 && <small>{activeTasks.length}</small>}</button>
  </header>;
}
