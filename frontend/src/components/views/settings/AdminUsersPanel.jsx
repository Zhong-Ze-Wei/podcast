// -*- coding: utf-8 -*-
import React, { useEffect, useState } from 'react';
import { adminApi } from '../../../services/api';

const ROLE_LABELS = { admin: '管理员', user: '成员', viewer: '访客' };
const STATUS_LABELS = { active: '正常', pending: '待审批', disabled: '已禁用' };

/**
 * AdminUsersPanel - 用户管理与注册审批（仅 admin 可见）
 */
const AdminUsersPanel = () => {
  const [users, setUsers] = useState([]);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  const load = async () => {
    try {
      const res = await adminApi.users();
      setUsers(res.data || res || []);
    } catch (err) {
      setError(err?.message || '加载失败');
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
      setError(err?.message || '操作失败');
    }
  };

  return (
    <div className="px-4 md:px-8 py-6 space-y-3">
      <h2 className="text-lg font-semibold text-white">用户管理</h2>
      <p className="text-xs text-zinc-500">新注册账号默认"待审批"，批准后才能登录。角色：管理员（全部）/ 成员（可管理订阅）/ 访客（只读+AI）。</p>
      {notice && <div className="rounded-lg border border-green-700/40 bg-green-900/20 px-3 py-2 text-sm text-green-300">{notice}</div>}
      {error && <div className="rounded-lg border border-red-800/50 bg-red-900/20 px-3 py-2 text-sm text-red-300">{error}</div>}

      {users.map(u => (
        <div key={u.id} className="flex flex-wrap items-center gap-3 rounded-lg border border-zinc-800 bg-zinc-900/40 px-4 py-3">
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm text-white">{u.email}</p>
            <p className="text-xs text-zinc-500">
              <span className={`mr-2 ${u.status === 'pending' ? 'text-amber-400' : u.status === 'disabled' ? 'text-zinc-600' : 'text-green-400'}`}>
                {STATUS_LABELS[u.status] || u.status}
              </span>
              注册于 {u.created_at ? new Date(u.created_at).toLocaleDateString() : '-'}
            </p>
          </div>
          <select
            value={u.role}
            onChange={(e) => patch(u.id, { role: e.target.value }, `${u.email} 角色已改为 ${ROLE_LABELS[e.target.value]}`)}
            className="rounded-md border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-xs text-zinc-200"
          >
            <option value="admin">管理员</option>
            <option value="user">成员</option>
            <option value="viewer">访客</option>
          </select>
          {u.status === 'pending' ? (
            <button
              onClick={() => patch(u.id, { status: 'active' }, `${u.email} 已批准`)}
              className="rounded-md bg-green-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-green-500"
            >
              批准
            </button>
          ) : (
            <button
              onClick={() => patch(u.id, { status: u.status === 'disabled' ? 'active' : 'disabled' }, `${u.email} 已${u.status === 'disabled' ? '恢复' : '禁用'}`)}
              className="rounded-md border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300 hover:bg-zinc-800"
            >
              {u.status === 'disabled' ? '恢复' : '禁用'}
            </button>
          )}
        </div>
      ))}
    </div>
  );
};

export default AdminUsersPanel;
