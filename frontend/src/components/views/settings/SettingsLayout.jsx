import React from 'react';

const WIDTHS = {
  narrow: 'max-w-2xl',
  default: 'max-w-3xl',
  wide: 'max-w-5xl',
  full: 'max-w-none',
};

/**
 * 设置页统一骨架：可选的右侧操作条 + 可滚动内容区。
 * 页面标题与说明由外层 SettingsView 统一渲染，面板内不再重复。
 */
export function SettingsPage({ actions, width = 'default', toolbarNote, children }) {
  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="min-h-0 flex-1 overflow-y-auto custom-scrollbar px-4 py-6 md:px-8">
        <div className={`mx-auto w-full space-y-6 ${WIDTHS[width] || WIDTHS.default}`}>
          {actions && (
            <div className="flex items-center justify-end gap-3">
              {toolbarNote && <span className="text-xs text-zinc-500">{toolbarNote}</span>}
              {actions}
            </div>
          )}
          {children}
        </div>
      </div>
    </div>
  );
}

/**
 * 设置页统一分组卡片：标题 + 说明 + 内容。
 * 需要按行排布时用 SettingRow。
 */
export function SettingGroup({ title, description, hint, children }) {
  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900/30">
      {(title || description) && (
        <div className="border-b border-zinc-800/70 px-5 py-4">
          {title && <h3 className="text-sm font-semibold text-white">{title}</h3>}
          {description && <p className="mt-1 text-sm leading-relaxed text-zinc-500">{description}</p>}
        </div>
      )}
      <div className="divide-y divide-zinc-800/70 px-5">{children}</div>
      {hint && <p className="border-t border-zinc-800/70 px-5 py-3 text-xs text-zinc-600">{hint}</p>}
    </section>
  );
}

/**
 * 设置页统一行：左侧标题 + 灰色说明，控件右对齐。
 * 长控件（滑块、多选框组）用 stacked 变成上下排布。
 */
export function SettingRow({ label, description, stacked = false, children }) {
  return (
    <div className={`flex gap-3 py-4 ${stacked ? 'flex-col' : 'flex-col sm:flex-row sm:items-center sm:justify-between sm:gap-4'}`}>
      <div className="min-w-0 sm:max-w-[62%]">
        {label && <p className="text-sm font-medium text-zinc-200">{label}</p>}
        {description && <p className="mt-1 text-xs leading-relaxed text-zinc-500">{description}</p>}
      </div>
      <div className={`shrink-0 ${stacked ? 'w-full' : 'flex items-center justify-start sm:justify-end'}`}>{children}</div>
    </div>
  );
}

/** 设置页主按钮：全站统一 indigo，状态色只用于成功/失败提示。 */
export function SettingsButton({ variant = 'primary', className = '', ...props }) {
  const styles = {
    primary: 'bg-indigo-600 text-white hover:bg-indigo-500 disabled:bg-zinc-700 disabled:text-zinc-400',
    secondary: 'border border-zinc-700 text-zinc-300 hover:bg-zinc-800 hover:text-white',
    danger: 'border border-red-900/60 bg-red-950/30 text-red-300 hover:bg-red-900/40',
  };
  return (
    <button
      {...props}
      className={`inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed ${styles[variant] || styles.primary} ${className}`}
    />
  );
}

/** 设置页内联保存状态：与行内容同行，不占布局。 */
export function SaveStatus({ saving, saved, error, t, savingText, savedText }) {
  if (error) return <span role="alert" className="text-xs text-red-400">{error}</span>;
  if (saving) return <span className="text-xs text-zinc-500">{savingText || t('common.saving')}</span>;
  if (saved) return <span className="text-xs text-emerald-400">{savedText || t('settings.saved')}</span>;
  return null;
}
