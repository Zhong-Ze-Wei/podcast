// -*- coding: utf-8 -*-
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

import zh from './locales/zh.json';
import en from './locales/en.json';
import uiZh from './locales/ui.zh.json';
import uiEn from './locales/ui.en.json';

// Language resources - add new languages here
const resources = {
  zh: { translation: { ...zh, ui: uiZh } },
  en: { translation: { ...en, ui: uiEn } }
};

// Supported languages list - extend when adding new languages
export const supportedLanguages = [
  { code: 'zh', label: 'CN' },
  { code: 'en', label: 'EN' }
];

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: 'zh',
    supportedLngs: supportedLanguages.map(l => l.code),
    load: 'languageOnly',
    interpolation: {
      escapeValue: false
    },
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage']
    }
  });

const updateDocumentLanguage = language => { document.documentElement.lang = language?.startsWith('en') ? 'en' : 'zh-CN'; };
i18n.on('languageChanged', updateDocumentLanguage);
updateDocumentLanguage(i18n.resolvedLanguage || i18n.language);

export default i18n;
