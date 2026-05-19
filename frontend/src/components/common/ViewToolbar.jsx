// -*- coding: utf-8 -*-
import React from 'react';
import { useTranslation } from 'react-i18next';
import { LayoutGrid, List } from 'lucide-react';

const ViewToolbar = ({
  count,
  description,
  viewMode = 'grid',
  onViewModeChange,
  children
}) => {
  const { t } = useTranslation();

  return (
    <div className="sticky top-0 z-10 bg-zinc-950/95 backdrop-blur-sm px-8 py-4 border-b border-zinc-800/50">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="min-w-0">
          <p className="text-sm font-medium text-zinc-300 truncate">{count}</p>
          {description && (
            <p className="mt-1 text-xs text-zinc-500 truncate">{description}</p>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {children}
          <div className="flex bg-zinc-800 rounded-xl p-1">
            <button
              onClick={() => onViewModeChange && onViewModeChange('grid')}
              className={`p-2 rounded-lg transition-colors ${viewMode === 'grid' ? 'bg-zinc-700 text-white' : 'text-zinc-400 hover:text-white'}`}
              title={t('view.grid')}
            >
              <LayoutGrid size={16} />
            </button>
            <button
              onClick={() => onViewModeChange && onViewModeChange('list')}
              className={`p-2 rounded-lg transition-colors ${viewMode === 'list' ? 'bg-zinc-700 text-white' : 'text-zinc-400 hover:text-white'}`}
              title={t('view.list')}
            >
              <List size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ViewToolbar;
