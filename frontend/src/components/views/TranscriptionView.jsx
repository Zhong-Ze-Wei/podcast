import React from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronLeft, Mic2 } from 'lucide-react';
import TranscriptionPanel from './transcription/TranscriptionPanel';

export default function TranscriptionView({ onBack, capabilities, loading, error, onRefresh }) {
  const { t } = useTranslation();
  return (
    <div className="flex h-full flex-col overflow-hidden bg-zinc-950 text-zinc-100">
      <header className="flex shrink-0 items-center gap-4 border-b border-zinc-800 bg-zinc-900/20 px-8 py-6">
        <button onClick={onBack} aria-label={t('settings.transcription.back')} className="rounded-full p-2 text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-white">
          <ChevronLeft size={24} />
        </button>
        <h1 className="flex items-center gap-3 text-2xl font-bold text-white">
          <Mic2 size={24} className="text-indigo-400" />
          {t('settings.transcription.title')}
        </h1>
      </header>
      <div className="min-h-0 flex-1">
        <TranscriptionPanel capabilities={capabilities} loading={loading} error={error} onRefresh={onRefresh} />
      </div>
    </div>
  );
}
