import React from 'react';
import { useTranslation } from 'react-i18next';
import { FileText, Cloud, Cpu, RefreshCw } from 'lucide-react';
import TranscriptionPanelLayout, { SettingRow, transcriptionActionClass } from './TranscriptionPanelLayout';
import { capabilityDescription } from '../../../utils/capabilityText';

const providerIcons = { official: FileText, local_whisper: Cpu, local_whisperx: Cpu, assemblyai: Cloud };

export default function TranscriptionPanel({ capabilities, loading, error, onRefresh }) {
  const { t } = useTranslation();
  const providers = Object.keys(providerIcons).map(id => capabilities?.transcription?.[id]).filter(Boolean);
  return (
    <TranscriptionPanelLayout
      description={t('settings.transcription.description')}
      action={
        <button onClick={onRefresh} disabled={loading} className={transcriptionActionClass}>
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          {t(loading ? 'settings.transcription.checking' : 'settings.transcription.refresh')}
        </button>
      }
    >
      <p className="text-sm leading-relaxed text-zinc-500">{t('settings.transcription.note')}</p>
      {error && <p role="alert" className="text-sm text-amber-400">{error}</p>}
      {!capabilities && !error && <p role="status" className="text-sm text-zinc-400">{t('settings.transcription.loading')}</p>}
      {providers.map(provider => (
        <SettingRow
          key={provider.id}
          icon={providerIcons[provider.id]}
          title={t(`settings.transcription.providers.${provider.id}`)}
          description={capabilityDescription(provider, t)}
          badge={
            <span className={`shrink-0 rounded-full px-2 py-1 text-xs ${provider.available ? 'bg-emerald-900/30 text-emerald-300' : 'bg-zinc-800 text-zinc-400'}`}>
              {t(`settings.transcription.states.${provider.state}`, { defaultValue: t('settings.transcription.states.unsupported') })}
            </span>
          }
        >
          {provider.install_command && <details className="text-sm leading-relaxed text-zinc-400">
            <summary className="cursor-pointer text-indigo-400 hover:text-indigo-300">{t('settings.transcription.setup')}</summary>
            <p className="mt-3">{t('settings.transcription.installHelp')}</p>
            <code className="mt-2 block break-all rounded-lg border border-zinc-800 bg-zinc-900 p-3 text-xs">{provider.install_command}</code>
            {provider.prepare_command && <>
              <p className="mt-3">{t('settings.transcription.prepareHelp')}</p>
              <code className="mt-2 block break-all rounded-lg border border-zinc-800 bg-zinc-900 p-3 text-xs">{provider.prepare_command}</code>
              <p className="mt-3">{t('settings.transcription.enableHelp')}</p>
            </>}
            {provider.id === 'assemblyai' && <p className="mt-3">{t('settings.transcription.cloudHelp')}</p>}
          </details>}
        </SettingRow>
      ))}
    </TranscriptionPanelLayout>
  );
}
