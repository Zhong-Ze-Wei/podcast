import { test } from 'node:test';
import assert from 'node:assert/strict';
import { transcriptionOptions as getOptions, defaultTranscriptionProvider } from './transcription.js';
import { readFileSync } from 'node:fs';
import { createInstance } from 'i18next';

const i18n = createInstance();
await i18n.init({ lng: 'en', resources: { en: { translation: JSON.parse(readFileSync(new URL('../locales/en.json', import.meta.url))) } } });
const transcriptionOptions = (caps, episode) => getOptions(caps, episode, i18n.t);

test('missing capabilities fail closed even when audio exists', () => {
  const options = transcriptionOptions(null, { audio_url: 'audio' });
  assert.ok(options.every(option => option.disabled));
  assert.equal(defaultTranscriptionProvider(options), '');
});

test('official subtitles remain available when local engine is missing', () => {
  const options = transcriptionOptions({ transcription: {
    official: { available: true }, local_whisper: { available: false, state: 'not_installed', reason_code: 'engine_missing', reason: '未安装' },
  } }, { transcript_url: 'captions', audio_url: 'audio' });
  assert.equal(options[0].disabled, false);
  assert.equal(options[1].disabled, true);
  assert.match(options[1].description, /not installed/);
  assert.equal(defaultTranscriptionProvider(options), 'official');
});

test('cloud is never automatically selected', () => {
  const options = transcriptionOptions({ transcription: { assemblyai: { available: true } } }, { audio_url: 'audio' });
  assert.equal(options.find(option => option.value === 'assemblyai').disabled, false);
  assert.equal(defaultTranscriptionProvider(options), '');
});

test('ready engine still needs episode audio', () => {
  const caps = { transcription: { local_whisper: { available: true } } };
  assert.equal(transcriptionOptions(caps, {})[1].disabled, true);
  assert.equal(transcriptionOptions(caps, { audio_url: 'audio' })[1].disabled, false);
});
