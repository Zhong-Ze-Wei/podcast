import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createInstance } from 'i18next';
import { formatPeriodLabel, formatUiDate, localizedLabel, localizeUiMessage, templateDisplayName, uiLocale } from './localization.js';

const locale = language => ({ ...JSON.parse(readFileSync(new URL(`../locales/${language}.json`, import.meta.url))), ui: JSON.parse(readFileSync(new URL(`../locales/ui.${language}.json`, import.meta.url))) });
const flatten = (value, prefix = '') => Object.fromEntries(Object.entries(value).flatMap(([key, item]) => typeof item === 'string' ? [[prefix + key, item]] : Object.entries(flatten(item, `${prefix}${key}.`))));
const zh = flatten(locale('zh'));
const en = flatten(locale('en'));

test('both languages cover every UI key and interpolation variable', () => {
  assert.deepEqual(Object.keys(zh).sort(), Object.keys(en).sort());
  for (const key of Object.keys(zh)) {
    const variables = text => (text.match(/\{\{[^}]+\}\}/g) || []).sort();
    assert.deepEqual(variables(zh[key]), variables(en[key]), key);
  }
});

test('active UI translation references resolve in both languages', () => {
  function inspect(directory) {
    for (const item of readdirSync(directory, { withFileTypes: true })) {
      const file = join(directory, item.name);
      if (item.isDirectory()) inspect(file);
      else if (/\.(jsx|js)$/.test(file) && !file.endsWith('.test.js') && item.name !== 'AIBriefingView.jsx') {
        for (const [, key] of readFileSync(file, 'utf8').matchAll(/\bt\(['"]([^'"]+)['"]/g)) {
          const resolve = language => key.split('.').reduce((value, part) => value?.[part], locale(language));
          assert.ok(resolve('zh') && resolve('en'), `${file}: ${key}`);
        }
      }
    }
  }
  inspect(fileURLToPath(new URL('../', import.meta.url)));
});

test('regional languages choose the UI locale and bilingual parameter labels', () => {
  assert.equal(uiLocale('en-GB'), 'en-US');
  assert.equal(uiLocale('zh-CN'), 'zh-CN');
  const item = { label: 'Long', label_zh: '详细' };
  assert.equal(localizedLabel(item, 'en-GB'), 'Long');
  assert.equal(localizedLabel(item, 'zh-CN'), '详细');
  assert.equal(localizedLabel({ label: 'Custom value' }, 'zh'), 'Custom value');
});

test('display dates share the reporting timezone and periods handle a year boundary', () => {
  const date = '2026-09-30T18:00:00Z';
  assert.equal(formatUiDate(date, 'en'), '10/1/2026');
  assert.equal(formatUiDate(date, 'zh'), '2026/10/1');
  assert.match(formatPeriodLabel({ type: 'month', start: '2026-09-01' }, 'en'), /September 2026/);
  assert.match(formatPeriodLabel({ type: 'week', start: '2026-12-28' }, 'zh'), /2027\.01\.03/);
});

test('saved task messages change language while retaining counts, titles and provider details', async () => {
  const i18n = createInstance();
  await i18n.init({ resources: { zh: { translation: locale('zh') }, en: { translation: locale('en') } }, lng: 'en', interpolation: { escapeValue: false } });
  const t = i18n.t.bind(i18n);
  assert.equal(templateDisplayName({ is_system: true, name: 'learning', display_name: '学习笔记' }, t), 'Learning notes');
  assert.equal(templateDisplayName({ is_system: false, name: 'learning', display_name: '我的自定义摘要' }, t), '我的自定义摘要');
  const message = '逐篇分析 2/50 · 复用1期 · 正在分析《OpenAI 的经营》';
  assert.equal(localizeUiMessage(message, t), 'Analyzed 2/50 · 1 reused · Reading “OpenAI 的经营”');
  assert.equal(localizeUiMessage('已整理共性与分歧', t), 'Saved Common ground & differences');
  assert.equal(localizeUiMessage('Invalid email or password', t), 'Invalid email or password');
  const englishNotice = t('ui.loadingEpisodeAnalysis');
  await i18n.changeLanguage('zh');
  assert.equal(localizeUiMessage(message, t), message);
  assert.equal(localizeUiMessage(englishNotice, t), t('ui.loadingEpisodeAnalysis'));
  assert.equal(localizeUiMessage('Invalid email or password', t), '邮箱或密码不正确');
  assert.equal(localizeUiMessage('Provider error 429: quota exceeded', t), 'Provider error 429: quota exceeded');
});
