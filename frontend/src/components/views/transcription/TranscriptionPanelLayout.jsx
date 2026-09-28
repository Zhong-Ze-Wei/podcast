import React from 'react';

export const transcriptionActionClass = 'flex shrink-0 items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-500 disabled:bg-zinc-700 disabled:cursor-not-allowed';

export default function TranscriptionPanelLayout({ description, action, children }) {
  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="shrink-0 border-b border-zinc-800 px-8 py-4" data-settings-toolbar>
        <div className="mx-auto flex max-w-4xl items-center justify-between gap-4">
          <p className="text-sm leading-relaxed text-zinc-500">{description}</p>
          {action}
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-8">
        <div className="mx-auto max-w-4xl space-y-6" data-settings-content>{children}</div>
      </div>
    </div>
  );
}

export function SettingRow({ icon: Icon, title, description, badge, children }) {
  return (
    <section className="border-b border-zinc-800 pb-7 last:border-b-0 last:pb-0">
      <div className="flex items-start gap-3">
        <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-zinc-800 bg-zinc-950 text-indigo-400">
          <Icon size={16} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-base font-semibold text-white">{title}</h3>
            {badge}
          </div>
          <p className="mt-1 text-sm leading-relaxed text-zinc-500">{description}</p>
          {children && <div className="mt-4">{children}</div>}
        </div>
      </div>
    </section>
  );
}
