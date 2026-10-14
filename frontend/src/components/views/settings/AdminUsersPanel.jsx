import { localizeUiMessage, formatUiDate } from '../../../utils/localization';
import { useTranslation } from 'react-i18next';
// -*- coding: utf-8 -*-
import React, { useEffect, useState } from 'react';
import { adminApi } from '../../../services/api';


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
    <div className="px-4 md:px-8 py-6 space-y-3">
      <h2 className="text-lg font-semibold text-white">{t("ui.userManagement")}</h2>
      <p className="text-xs text-zinc-500">{t("ui.newAccountsAwaitApprovalBeforeSigningIn")}</p>
      {notice && <div className="rounded-lg border border-green-700/40 bg-green-900/20 px-3 py-2 text-sm text-green-300">{localizeUiMessage(notice, t)}</div>}
      {error && <div className="rounded-lg border border-red-800/50 bg-red-900/20 px-3 py-2 text-sm text-red-300">{localizeUiMessage(error, t)}</div>}

      {users.map(u => (
        <div key={u.id} className="flex flex-wrap items-center gap-3 rounded-lg border border-zinc-800 bg-zinc-900/40 px-4 py-3">
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm text-white">{u.email}</p>
            <p className="text-xs text-zinc-500">
              <span className={`mr-2 ${u.status === 'pending' ? 'text-amber-400' : u.status === 'disabled' ? 'text-zinc-600' : 'text-green-400'}`}>
                {STATUS_LABELS[u.status] || u.status}
              </span> {t("ui.registered")} {u.created_at ? formatUiDate(u.created_at, i18n.resolvedLanguage) : '-'}
            </p>
          </div>
          <select
            value={u.role}
            onChange={(e) => patch(u.id, { role: e.target.value }, t("ui.valueRoleChangedToValue", { value1: u.email, value2: ROLE_LABELS[e.target.value] }))}
            className="rounded-md border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-xs text-zinc-200"
          >
            <option value="admin">{t("ui.administrator")}</option>
            <option value="user">{t("ui.member")}</option>
            <option value="viewer">{t("ui.viewer")}</option>
          </select>
          {u.status === 'pending' ? (
            <button
              onClick={() => patch(u.id, { status: 'active' }, t("ui.valueApproved", { value1: u.email }))}
              className="rounded-md bg-green-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-green-500"
            > {t("ui.approve")} </button>
          ) : (
            <button
              onClick={() => patch(u.id, { status: u.status === 'disabled' ? 'active' : 'disabled' }, t("ui.valueValue", { value1: u.email, value2: u.status === 'disabled' ? t("ui.restore") : t("ui.disable") }))}
              className="rounded-md border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300 hover:bg-zinc-800"
            >
              {u.status === 'disabled' ? t("ui.restore") : t("ui.disable")}
            </button>
          )}
        </div>
      ))}
    </div>
  );
};

export default AdminUsersPanel;
