// -*- coding: utf-8 -*-
import React, { useEffect, useState } from 'react';
import { Shield, User, Activity, Power } from 'lucide-react';
import { adminApi } from '../../../services/api';

const AccountPanel = ({ currentUser, onLogout }) => {
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
      .catch((err) => setError(err.message || '管理员信息加载失败'));
    return () => { mounted = false; };
  }, [isAdmin]);

  return (
    <div className="h-full overflow-y-auto p-8 space-y-6">
      <section className="max-w-4xl">
        <h2 className="text-lg font-semibold text-white mb-4">账号</h2>
        <div className="border border-zinc-800 bg-zinc-900/40 rounded-lg p-5 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-11 h-11 rounded-lg bg-zinc-800 flex items-center justify-center">
              <User size={20} className="text-zinc-300" />
            </div>
            <div>
              <div className="text-white font-medium">{currentUser?.email || '本地默认用户'}</div>
              <div className="text-xs text-zinc-500">角色：{currentUser?.role || 'user'}</div>
            </div>
          </div>
          <button
            onClick={onLogout}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md text-sm text-zinc-300 hover:text-white hover:bg-zinc-800"
          >
            <Power size={16} />
            退出
          </button>
        </div>
      </section>

      {isAdmin && (
        <section className="max-w-4xl space-y-4">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Shield size={18} className="text-indigo-300" />
            管理员
          </h2>
          {error && <div className="text-sm text-red-300">{error}</div>}
          {health && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {['users', 'feeds', 'episodes', 'tasks'].map(key => (
                <div key={key} className="border border-zinc-800 bg-zinc-900/40 rounded-lg p-4">
                  <div className="text-xs text-zinc-500 uppercase">{key}</div>
                  <div className="text-2xl text-white mt-1">{health[key]}</div>
                </div>
              ))}
            </div>
          )}
          <div className="border border-zinc-800 bg-zinc-900/40 rounded-lg overflow-hidden">
            <div className="px-4 py-3 border-b border-zinc-800 text-sm text-zinc-400 flex items-center gap-2">
              <Activity size={16} />
              用户列表
            </div>
            {users.map(user => (
              <div key={user.id} className="px-4 py-3 border-b border-zinc-800/70 last:border-0 flex items-center justify-between">
                <div>
                  <div className="text-sm text-white">{user.email}</div>
                  <div className="text-xs text-zinc-500">{user.role}</div>
                </div>
                <span className={`text-xs px-2 py-1 rounded ${user.status === 'active' ? 'bg-emerald-500/10 text-emerald-300' : 'bg-red-500/10 text-red-300'}`}>
                  {user.status}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
};

export default AccountPanel;
