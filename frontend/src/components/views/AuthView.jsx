// -*- coding: utf-8 -*-
import React, { useState } from 'react';
import { LockKeyhole, Mail, Podcast, UserPlus } from 'lucide-react';
import { authApi, setAuthToken } from '../../services/api';

const AuthView = ({ onAuthenticated }) => {
  const [mode, setMode] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError('');
    try {
      const response = mode === 'login'
        ? await authApi.login({ email, password })
        : await authApi.register({ email, password });
      const payload = response.data || response;
      setAuthToken(payload.token);
      onAuthenticated(payload.user);
    } catch (err) {
      setError(err.message || err.error || '认证失败，请检查账号信息');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex items-center justify-center px-6">
      <div className="w-full max-w-md">
        <div className="mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/30 mb-5">
            <Podcast className="text-indigo-300" size={24} />
          </div>
          <h1 className="text-3xl font-semibold tracking-tight text-white">Podcast Manager</h1>
          <p className="mt-2 text-sm text-zinc-400">登录后管理自己的订阅、转录、摘要和任务。</p>
        </div>

        <form onSubmit={submit} className="border border-zinc-800 bg-zinc-900/60 rounded-lg p-6 shadow-2xl shadow-black/30">
          <div className="flex gap-2 mb-6 bg-zinc-950 p-1 rounded-lg">
            <button
              type="button"
              onClick={() => setMode('login')}
              className={`flex-1 px-3 py-2 rounded-md text-sm transition-colors ${mode === 'login' ? 'bg-zinc-800 text-white' : 'text-zinc-500 hover:text-zinc-300'}`}
            >
              登录
            </button>
            <button
              type="button"
              onClick={() => setMode('register')}
              className={`flex-1 px-3 py-2 rounded-md text-sm transition-colors ${mode === 'register' ? 'bg-zinc-800 text-white' : 'text-zinc-500 hover:text-zinc-300'}`}
            >
              注册
            </button>
          </div>

          <label className="block text-xs font-medium text-zinc-500 mb-2">邮箱</label>
          <div className="relative mb-4">
            <Mail size={16} className="absolute left-3 top-3 text-zinc-500" />
            <input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              type="email"
              autoComplete="email"
              required
              className="w-full bg-zinc-950 border border-zinc-800 rounded-md pl-10 pr-3 py-2.5 text-sm text-white outline-none focus:border-indigo-500"
              placeholder="you@example.com"
            />
          </div>

          <label className="block text-xs font-medium text-zinc-500 mb-2">密码</label>
          <div className="relative mb-4">
            <LockKeyhole size={16} className="absolute left-3 top-3 text-zinc-500" />
            <input
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              type="password"
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              minLength={8}
              required
              className="w-full bg-zinc-950 border border-zinc-800 rounded-md pl-10 pr-3 py-2.5 text-sm text-white outline-none focus:border-indigo-500"
              placeholder="至少 8 位"
            />
          </div>

          {error && (
            <div className="mb-4 text-sm text-red-300 bg-red-950/40 border border-red-900/60 rounded-md px-3 py-2">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full inline-flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 text-white rounded-md px-4 py-2.5 text-sm font-medium transition-colors"
          >
            {mode === 'register' ? <UserPlus size={16} /> : <LockKeyhole size={16} />}
            {loading ? '处理中...' : mode === 'register' ? '创建账号' : '登录'}
          </button>
        </form>
      </div>
    </div>
  );
};

export default AuthView;
