import React, { useEffect, useState } from 'react';
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend
} from 'recharts';
import {
  TrendingUp, TrendingDown, DollarSign, CreditCard,
  ShieldAlert, CheckCircle, Clock, AlertTriangle, RefreshCw
} from 'lucide-react';
import { paymentsAPI } from '../../services/api.js';
import clsx from 'clsx';

// ─── Mock data for demo (replace with real API calls) ─────────────────────────
const generateVolumeData = () => {
  const base = 85000;
  return Array.from({ length: 30 }, (_, i) => {
    const d = new Date(); d.setDate(d.getDate() - (29 - i));
    const val = base + Math.random() * 40000 - 20000;
    return {
      date: d.toLocaleDateString('en', { month: 'short', day: 'numeric' }),
      volume: Math.round(val),
      txns: Math.round(val / 150),
      fraud: Math.round(Math.random() * 8),
    };
  });
};

const METHOD_DATA = [
  { name: 'Card',          value: 58, color: '#0ea5e9' },
  { name: 'Bank Transfer', value: 22, color: '#6366f1' },
  { name: 'Wallet',        value: 13, color: '#22c55e' },
  { name: 'UPI',           value: 7,  color: '#f59e0b' },
];

const STATUS_DATA = [
  { status: 'Completed',  count: 4821, color: '#22c55e' },
  { status: 'Pending',    count: 143,  color: '#f59e0b' },
  { status: 'Failed',     count: 89,   color: '#ef4444' },
  { status: 'Refunded',   count: 47,   color: '#8b5cf6' },
];

const KPI = ({ icon: Icon, label, value, delta, deltaLabel, color }) => (
  <div className="card flex items-start gap-4">
    <div className={clsx('p-3 rounded-xl', color)}>
      <Icon size={20} className="text-white" />
    </div>
    <div className="flex-1 min-w-0">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="text-2xl font-bold text-white mt-0.5">{value}</p>
      {delta !== undefined && (
        <p className={clsx('text-xs mt-1 flex items-center gap-1', delta >= 0 ? 'text-success-500' : 'text-danger-500')}>
          {delta >= 0 ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
          {Math.abs(delta)}% {deltaLabel}
        </p>
      )}
    </div>
  </div>
);

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-3 text-sm shadow-xl">
      <p className="text-slate-400 mb-1">{label}</p>
      {payload.map((p) => (
        <p key={p.name} style={{ color: p.color }} className="font-medium">
          {p.name}: {typeof p.value === 'number' && p.name === 'volume'
            ? `$${p.value.toLocaleString()}`
            : p.value.toLocaleString()}
        </p>
      ))}
    </div>
  );
};

export default function DashboardPage() {
  const [volumeData] = useState(generateVolumeData);
  const [loading, setLoading] = useState(false);
  const [lastRefresh, setLastRefresh] = useState(new Date());

  const refresh = () => {
    setLoading(true);
    setTimeout(() => { setLoading(false); setLastRefresh(new Date()); }, 800);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Dashboard</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Last updated {lastRefresh.toLocaleTimeString()}
          </p>
        </div>
        <button onClick={refresh} disabled={loading} className="btn-secondary flex items-center gap-2 text-sm">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <KPI icon={DollarSign}  label="Total Volume (30d)"     value="$2.41M"  delta={12.4}   deltaLabel="vs last month" color="bg-brand-600" />
        <KPI icon={CreditCard}  label="Transactions (30d)"     value="5,100"   delta={8.2}    deltaLabel="vs last month" color="bg-indigo-600" />
        <KPI icon={CheckCircle} label="Success Rate"           value="94.6%"   delta={1.2}    deltaLabel="improvement"   color="bg-success-700" />
        <KPI icon={ShieldAlert} label="Fraud Rate"             value="0.31%"   delta={-0.08}  deltaLabel="improvement"   color="bg-warning-700" />
      </div>

      {/* Volume Chart */}
      <div className="card">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="font-semibold text-white">Transaction Volume</h2>
            <p className="text-sm text-slate-500">30-day payment volume and transaction count</p>
          </div>
          <div className="flex items-center gap-4 text-xs text-slate-500">
            <span className="flex items-center gap-1.5"><span className="w-3 h-0.5 bg-brand-500 inline-block rounded" /> Volume</span>
            <span className="flex items-center gap-1.5"><span className="w-3 h-0.5 bg-indigo-500 inline-block rounded" /> Transactions</span>
          </div>
        </div>
        <ResponsiveContainer width="100%" height={260}>
          <AreaChart data={volumeData} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="volGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#0ea5e9" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 11 }} tickLine={false} axisLine={false} interval={4} />
            <YAxis tick={{ fill: '#64748b', fontSize: 11 }} tickLine={false} axisLine={false} tickFormatter={(v) => `$${(v/1000).toFixed(0)}k`} />
            <Tooltip content={<CustomTooltip />} />
            <Area type="monotone" dataKey="volume" stroke="#0ea5e9" strokeWidth={2} fill="url(#volGrad)" name="volume" />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Bottom row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Payment Methods Pie */}
        <div className="card">
          <h2 className="font-semibold text-white mb-4">Payment Methods</h2>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={METHOD_DATA} cx="50%" cy="50%" innerRadius={55} outerRadius={80} paddingAngle={3} dataKey="value">
                {METHOD_DATA.map((m) => <Cell key={m.name} fill={m.color} />)}
              </Pie>
              <Tooltip formatter={(v) => `${v}%`} contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }} itemStyle={{ color: '#e2e8f0' }} />
            </PieChart>
          </ResponsiveContainer>
          <div className="space-y-2 mt-2">
            {METHOD_DATA.map((m) => (
              <div key={m.name} className="flex items-center justify-between text-sm">
                <span className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full" style={{ background: m.color }} />
                  <span className="text-slate-400">{m.name}</span>
                </span>
                <span className="text-white font-medium">{m.value}%</span>
              </div>
            ))}
          </div>
        </div>

        {/* Status breakdown */}
        <div className="card">
          <h2 className="font-semibold text-white mb-4">Transaction Status</h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={STATUS_DATA} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="status" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }} itemStyle={{ color: '#e2e8f0' }} />
              <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                {STATUS_DATA.map((s) => <Cell key={s.status} fill={s.color} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Fraud trend */}
        <div className="card">
          <h2 className="font-semibold text-white mb-1">Fraud Detections</h2>
          <p className="text-xs text-slate-500 mb-4">Daily flagged transactions (30d)</p>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={volumeData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="fraudGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} interval={6} />
              <YAxis tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }} itemStyle={{ color: '#e2e8f0' }} />
              <Area type="monotone" dataKey="fraud" stroke="#ef4444" strokeWidth={2} fill="url(#fraudGrad)" name="Fraud flags" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* System status */}
      <div className="card">
        <h2 className="font-semibold text-white mb-4">Service Health</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[
            { name: 'API Gateway',     status: 'healthy', latency: '4ms'  },
            { name: 'Payment Service', status: 'healthy', latency: '28ms' },
            { name: 'Fraud Engine',    status: 'healthy', latency: '18ms' },
            { name: 'Kafka Cluster',   status: 'healthy', latency: '2ms'  },
          ].map((svc) => (
            <div key={svc.name} className="flex items-center gap-3 p-3 bg-slate-800 rounded-lg">
              <span className="w-2 h-2 rounded-full bg-success-500 animate-pulse shrink-0" />
              <div>
                <p className="text-sm font-medium text-white">{svc.name}</p>
                <p className="text-xs text-slate-500">{svc.latency} avg</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
