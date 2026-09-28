import { capabilityDescription } from './capabilityText.js';

export function transcriptionOptions(capabilities, episode, t, error = '') {
  const hasLocalAudio = Boolean(episode?.local_audio_url);
  const hasRemoteAudio = Boolean(episode?.audio_url);
  return ['official', 'local_whisper', 'local_whisperx', 'assemblyai', 'manual'].map(value => {
    const label = t(`settings.transcription.providers.${value}`);
    const capability = capabilities?.transcription?.[value];
    let description = capability ? capabilityDescription(capability, t) : error || t('settings.transcription.loading');
    let disabled = !capability?.available;
    if (!disabled && value === 'official') {
      disabled = !episode?.transcript_url;
      description = t(`settings.transcription.episode.${disabled ? 'noOfficial' : 'official'}`);
    } else if (!disabled && (value === 'local_whisper' || value === 'local_whisperx')) {
      disabled = !hasLocalAudio && !hasRemoteAudio;
      description = t(`settings.transcription.episode.${disabled ? 'noAudio' : hasLocalAudio ? 'localAudio' : 'downloadFirst'}`);
    } else if (!disabled && value === 'assemblyai' && !hasRemoteAudio) {
      disabled = true;
      description = t('settings.transcription.episode.noCloudAudio');
    }
    return { value, label, description, disabled };
  });
}

// Paid cloud transcription must always be explicitly selected by the user.
export function defaultTranscriptionProvider(options) {
  return options.find(option => !option.disabled && option.value !== 'assemblyai')?.value || '';
}
