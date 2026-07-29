import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Zap, Eye, EyeOff, AlertCircle } from 'lucide-react';
import { authAPI } from '../../services/api.js';
import { useAuthStore } from '../../store/index.js';

export default function LoginPage() {
  const navigate = useNavigate();
  const { login } = useAuthStore();
  const [form, setForm] = useState({ email: 'demo@payflow.io', password: 'demo1234' });
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await authAPI.login(form.email, form.password);
      login(res.data.access_token, { email: form.email, role: res.data.role, full_name: 'Demo Merchant' });
      navigate('/dashboard');
    } catch (err) {
      setError(err.response?.data?.detail?.message || 'Invalid credentials. Use demo@payflow.io / demo1234');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 px-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 bg-brand-600 rounded-2xl mb-4">
            <Zap size={28} className="text-white" />
          </div>
          <h1 className="text-2xl font-bold text-white">PayFlow</h1>
          <p className="text-slate-500 mt-1 text-sm">Sign in to your merchant portal</p>
        </div>

        {/* Demo credentials banner */}
        <div className="mb-6 p-3 rounded-lg bg-brand-600/10 border border-brand-600/30 text-sm text-brand-400">
          <strong>Demo:</strong> demo@payflow.io / demo1234
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="flex items-center gap-2 p-3 rounded-lg bg-red-900/20 border border-red-800 text-red-400 text-sm">
              <AlertCircle size={16} className="shrink-0" />
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-slate-400 mb-1.5">Email</label>
            <input
              className="input"
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              placeholder="you@company.com"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-400 mb-1.5">Password</label>
            <div className="relative">
              <input
                className="input pr-10"
                type={showPw ? 'text' : 'password'}
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                placeholder="••••••••"
                required
              />
              <button
                type="button"
                onClick={() => setShowPw(!showPw)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
              >
                {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full py-2.5 mt-2"
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Signing in...
              </span>
            ) : 'Sign In'}
          </button>
        </form>

        <p className="text-center text-xs text-slate-600 mt-8">
          PayFlow v1.0 — Distributed Payment Infrastructure
        </p>
      </div>
    </div>
  );
}
