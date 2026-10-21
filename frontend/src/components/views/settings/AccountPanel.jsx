// -*- coding: utf-8 -*-
import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Shield, User, Activity, Power } from 'lucide-react';
import { adminApi } from '../../../services/api';
import { localizeUiMessage } from '../../../utils/localization';
import { SettingsButton, SettingsPage, SettingGroup } from './SettingsLayout';

const AccountPanel = ({ currentUser, onLogout }) => {
  const { t } = useTranslation();
  const roles = { admin: t('ui.administrator'), user: t('ui.member'), viewer: t('ui.viewer') };
  const statuses = { active: t('ui.active'), pending: t('ui.awaitingApproval'), disabled: t('ui.disabled') };
  const [health, setHealth] = useState(null);
  const [users, setUsers] = useState([]);
  const [error, setError] = useState('');
  const isAdmin = currentUser?.role === 'admin';

  useEffect(() => {
    if (!isAdmin) return;
    let mounted = true;
    Promise.all([adminApi.health(), adminApi.users()])
      .then(([healthResponse, usersResponse]) => {
        if (!mounted) return;
        setHealth(healthResponse.data || healthResponse);
        setUsers(usersResponse.data || usersResponse);
      })
      .catch((err) => setError(err.message || t('settings.account.adminLoadError')));
    return () => { mounted = false; };
  }, [isAdmin, t]);

  return (
    <SettingsPage>
      <SettingGroup>
        <div className="flex items-center justify-between gap-4 py-4">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-zinc-800 bg-zinc-950 text-zinc-300">
              <User size={18} />
            </div>
            <div className="min-w-0">
              <div className="truncate text-sm font-medium text-white">{currentUser?.email || t('settings.account.localUser')}</div>
              <div className="text-xs text-zinc-500">{t('settings.account.role')}: {roles[currentUser?.role || 'user']}</div>
              {isAdmin && <div className="mt-0.5 text-xs text-emerald-300">{t('settings.account.firstAdminHint')}</div>}
            </div>
          </div>
          <SettingsButton variant="secondary" onClick={onLogout}>
            <Power size={15} />{t('settings.account.logout')}
          </SettingsButton>
        </div>
      </SettingGroup>

      {isAdmin && (
        <>
          <SettingGroup
            title={t('settings.account.adminTitle')}
            description={t('settings.account.adminDescription')}
            hint={error ? localizeUiMessage(error, t) : undefined}
          >
            {health && ['users', 'feeds', 'episodes', 'tasks'].map(key => (
              <div key={key} className="flex items-center justify-between py-3">
                <span className="text-sm text-zinc-400">{t(`ui.accountCounts.${key}`)}</span>
                <span className="text-lg font-semibold tabular-nums text-white">{health[key]}</span>
              </div>
            ))}
          </SettingGroup>

          <SettingGroup title={t('settings.account.userList')}>
            {users.map(user => (
              <div key={user.id} className="flex items-center justify-between gap-4 py-3">
                <div className="min-w-0">
                  <div className="truncate text-sm text-white">{user.email}</div>
                  <div className="text-xs text-zinc-500">{roles[user.role]}</div>
                </div>
                <span className={`shrink-0 rounded px-2 py-0.5 text-xs ${user.status === 'active' ? 'bg-emerald-500/10 text-emerald-300' : 'bg-red-500/10 text-red-300'}`}>
                  {statuses[user.status]}
                </span>
              </div>
            ))}
          </SettingGroup>
        </>
      )}
      {!isAdmin && <p className="flex items-center gap-2 px-1 text-xs text-zinc-600"><Shield size={13} /><Activity size={13} />{t('settings.account.memberHint')}</p>}
    </SettingsPage>
  );
};

export default AccountPanel;
