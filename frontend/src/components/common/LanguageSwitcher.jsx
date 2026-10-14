// -*- coding: utf-8 -*-
import React from 'react';
import { useTranslation } from 'react-i18next';
import { Globe } from 'lucide-react';

/**
 * LanguageSwitcher - 语言切换按钮
 */
const LanguageSwitcher = ({ compact = false }) => {
  const { t, i18n } = useTranslation();

  const toggleLanguage = () => {
    const newLang = (i18n.resolvedLanguage || i18n.language).startsWith('en') ? 'zh' : 'en';
    i18n.changeLanguage(newLang);
  };

  return (
    <button
      onClick={toggleLanguage}
      className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-zinc-400 hover:text-white border border-zinc-700 hover:border-zinc-600 rounded-lg transition-colors bg-zinc-900/50"
      aria-label={(i18n.resolvedLanguage || i18n.language).startsWith('en') ? '切换到中文' : 'Switch to English'}
      title={(i18n.resolvedLanguage || i18n.language).startsWith('en') ? '切换到中文' : 'Switch to English'}
    >
      {!compact && <Globe size={14} />}
      <span>{t('language.switch')}</span>
    </button>
  );
};

export default LanguageSwitcher;
