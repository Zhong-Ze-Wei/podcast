// -*- coding: utf-8 -*-
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

import zh from './locales/zh.json';
import en from './locales/en.json';

// Language resources - add new languages here
const resources = {
  zh: { translation: zh },
  en: { translation: en }
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
    interpolation: {
      escapeValue: false
    },
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage']
    }
  });

export default i18n;
