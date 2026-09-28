import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createInstance } from 'i18next';
import { capabilityDescription } from './capabilityText.js';

const i18n = createInstance();
await i18n.init({
  lng: 'en', fallbackLng: false,
  resources: Object.fromEntries(['en', 'zh'].map(lang => [lang, {
    translation: JSON.parse(readFileSync(new URL(`../locales/${lang}.json`, import.meta.url))),
  }])),
});

test('capability messages follow the selected language, not the backend language', () => {
  const capability = { state: 'not_installed', reason_code: 'engine_missing', reason: '未安装本地转录引擎。' };
  const english = capabilityDescription(capability, i18n.getFixedT('en'));
  const chinese = capabilityDescription(capability, i18n.getFixedT('zh'));
  assert.match(english, /not installed/i);
  assert.doesNotMatch(english, /[\u3400-\u9fff]/);
  assert.match(chinese, /未安装/);
});

test('unknown capability reasons use a localized fallback', () => {
  const text = capabilityDescription({ state: 'runtime_error', reason_code: 'future_reason', reason: '未知错误' }, i18n.getFixedT('en'));
  assert.doesNotMatch(text, /[\u3400-\u9fff]|settings\./);
  assert.match(text, /check/i);
});
