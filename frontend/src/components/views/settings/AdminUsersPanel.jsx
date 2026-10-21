import { localizeUiMessage, formatUiDate } from '../../../utils/localization';
import { useTranslation } from 'react-i18next';
// -*- coding: utf-8 -*-
import React, { useEffect, useState } from 'react';
import { adminApi } from '../../../services/api';
import { SettingsButton, SettingsPage, SettingGroup } from './SettingsLayout';

const selectClass = 'rounded-lg border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-xs text-zinc-200 outline-none focus:border-indigo-500';

/**
 * AdminUsersPanel - 用户管理与注册审批（仅 admin 可见）
 */
const AdminUsersPanel = () => {
  const { t, i18n } = useTranslation();
  const STATUS_LABELS = { active: t("ui.active"), pending: t("ui.awaitingApproval"), disabled: t("ui.disabled") };
  const ROLE_LABELS = { admin: t("ui.administrator"), user: t("ui.member"), viewer: t("ui.viewer") };
  const [users, setUsers] = useState([]);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  const load = async () => {
    try {
      const res = await adminApi.users();
      setUsers(res.data || res || []);
    } catch (err) {
      setError(err?.message || t("ui.couldNotLoadData"));
    }
  };
  useEffect(() => { load(); }, []);

  const patch = async (id, data, msg) => {
    setNotice(null);
    try {
      await adminApi.updateUser(id, data);
      setNotice(msg);
      await load();
    } catch (err) {
      setError(err?.message || t("ui.actionFailed"));
    }
  };

  return (
    <SettingsPage>
      {(notice || error) && (
        <p
          role={error ? 'alert' : 'status'}
          className={`rounded-lg border px-4 py-2.5 text-sm ${error ? 'border-red-900/50 bg-red-950/30 text-red-300' : 'border-emerald-900/50 bg-emerald-950/30 text-emerald-300'}`}
        >
          {localizeUiMessage(error || notice, t)}
        </p>
      )}

      <SettingGroup>
        {users.map(u => (
          <div key={u.id} className="flex flex-wrap items-center gap-3 py-3">
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm text-white">{u.email}</p>
              <p className="text-xs text-zinc-500">
                <span className={`mr-2 ${u.status === 'pending' ? 'text-amber-400' : u.status === 'disabled' ? 'text-zinc-600' : 'text-emerald-400'}`}>
                  {STATUS_LABELS[u.status] || u.status}
                </span>
                {u.created_at ? formatUiDate(u.created_at, i18n.resolvedLanguage) : '-'}
              </p>
            </div>
            <select
              value={u.role}
              onChange={(e) => patch(u.id, { role: e.target.value }, t("ui.valueRoleChangedToValue", { value1: u.email, value2: ROLE_LABELS[e.target.value] }))}
              className={selectClass}
            >
              <option value="admin">{t("ui.administrator")}</option>
              <option value="user">{t("ui.member")}</option>
              <option value="viewer">{t("ui.viewer")}</option>
            </select>
            {u.status === 'pending' ? (
              <SettingsButton
                onClick={() => patch(u.id, { status: 'active' }, t("ui.valueApproved", { value1: u.email }))}
                className="!px-3 !py-1.5 !text-xs"
              >
                {t("ui.approve")}
              </SettingsButton>
            ) : (
              <SettingsButton
                variant="secondary"
                onClick={() => patch(u.id, { status: u.status === 'disabled' ? 'active' : 'disabled' }, t("ui.valueValue", { value1: u.email, value2: u.status === 'disabled' ? t("ui.restore") : t("ui.disable") }))}
                className="!px-3 !py-1.5 !text-xs"
              >
                {u.status === 'disabled' ? t("ui.restore") : t("ui.disable")}
              </SettingsButton>
            )}
          </div>
        ))}
      </SettingGroup>
    </SettingsPage>
  );
};

export default AdminUsersPanel;
