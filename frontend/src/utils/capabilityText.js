export function capabilityDescription(capability, t) {
  const fallback = t(`settings.transcription.fallbacks.${capability.state}`, {
    defaultValue: t('settings.transcription.fallbacks.unsupported'),
  });
  return t(`settings.transcription.reasons.${capability.reason_code}`, { defaultValue: fallback });
}
