// -*- coding: utf-8 -*-
import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { User, Power } from 'lucide-react';
import { adminApi } from '../../../services/api';
import { formatUiDate, localizeUiMessage } from '../../../utils/localization';
import { SettingsButton, SettingsPage, SettingGroup } from './SettingsLayout';

/**
 * AccountPanel - 当前身份 + 系统概况 + 成员管理（仅 admin）。
 * 此前「账号」页有一份只读用户列表，「用户管理」页又有一份可操作的同批用户；
 * 现在合并到这里，成员管理只有一处。
 */
const AccountPanel = ({ currentUser, onLogout }) => {
  const { t, i18n } = useTranslation();
  const roles = { admin: t('ui.administrator'), user: t('ui.member'), viewer: t('ui.viewer') };
  const statuses = { active: t('ui.active'), pending: t('ui.awaitingApproval'), disabled: t('ui.disabled') };
  const [health, setHealth] = useState(null);
  const [users, setUsers] = useState([]);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const isAdmin = currentUser?.role === 'admin';

  const loadUsers = async () => {
    const response = await adminApi.users();
    setUsers(response.data || response || []);
  };

  useEffect(() => {
    if (!isAdmin) return;
    let mounted = true;
    Promise.all([adminApi.health(), adminApi.users()])
      .then(([healthResponse, usersResponse]) => {
        if (!mounted) return;
        setHealth(healthResponse.data || healthResponse);
        setUsers(usersResponse.data || usersResponse || []);
      })
      .catch((err) => { if (mounted) setError(err.message || t('settings.account.adminLoadError')); });
    return () => { mounted = false; };
  }, [isAdmin, t]);

  const patch = async (id, data, message) => {
    setNotice('');
    setError('');
    try {
      await adminApi.updateUser(id, data);
      setNotice(message);
      await loadUsers();
    } catch (err) {
      setError(err.message || t('ui.actionFailed'));
    }
  };

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
          <SettingGroup title={t('settings.account.adminTitle')} description={t('settings.account.adminDescription')}>
            {health && ['users', 'feeds', 'episodes', 'tasks'].map(key => (
              <div key={key} className="flex items-center justify-between py-3">
                <span className="text-sm text-zinc-400">{t(`ui.accountCounts.${key}`)}</span>
                <span className="text-lg font-semibold tabular-nums text-white">{health[key]}</span>
              </div>
            ))}
          </SettingGroup>

          <SettingGroup
            title={t('settings.account.userList')}
            description={t('ui.newAccountsAwaitApprovalBeforeSigningIn')}
            hint={localizeUiMessage(error || notice, t) || undefined}
          >
            {users.map(user => (
              <div key={user.id} className="flex flex-wrap items-center gap-3 py-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm text-white">{user.email}</p>
                  <p className="text-xs text-zinc-500">
                    <span className={`mr-2 ${user.status === 'pending' ? 'text-amber-400' : user.status === 'disabled' ? 'text-zinc-600' : 'text-emerald-400'}`}>
                      {statuses[user.status] || user.status}
                    </span>
                    {user.created_at ? formatUiDate(user.created_at, i18n.resolvedLanguage) : '-'}
                  </p>
                </div>
                <select
                  value={user.role}
                  onChange={event => patch(user.id, { role: event.target.value }, t('ui.valueRoleChangedToValue', { value1: user.email, value2: roles[event.target.value] }))}
                  className="rounded-lg border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-xs text-zinc-200 outline-none focus:border-indigo-500"
                >
                  <option value="admin">{t('ui.administrator')}</option>
                  <option value="user">{t('ui.member')}</option>
                  <option value="viewer">{t('ui.viewer')}</option>
                </select>
                {user.status === 'pending' ? (
                  <SettingsButton
                    onClick={() => patch(user.id, { status: 'active' }, t('ui.valueApproved', { value1: user.email }))}
                    className="!px-3 !py-1.5 !text-xs"
                  >
                    {t('ui.approve')}
                  </SettingsButton>
                ) : (
                  <SettingsButton
                    variant="secondary"
                    onClick={() => patch(user.id, { status: user.status === 'disabled' ? 'active' : 'disabled' }, t('ui.valueValue', { value1: user.email, value2: user.status === 'disabled' ? t('ui.restore') : t('ui.disable') }))}
                    className="!px-3 !py-1.5 !text-xs"
                  >
                    {user.status === 'disabled' ? t('ui.restore') : t('ui.disable')}
                  </SettingsButton>
                )}
              </div>
            ))}
          </SettingGroup>
        </>
      )}
      {!isAdmin && <p className="px-1 text-xs text-zinc-600">{t('settings.account.memberHint')}</p>}
    </SettingsPage>
  );
};

export default AccountPanel;
