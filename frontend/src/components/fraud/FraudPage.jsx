import React, { useState } from 'react';
import { ShieldAlert, AlertTriangle, XCircle, CheckCircle, Ban, RefreshCw } from 'lucide-react';
import clsx from 'clsx';

const MOCK_CASES = Array.from({ length: 20 }, (_, i) => ({
  id: `case_${i.toString().padStart(4, '0')}`,
  payment_id: `pay_${crypto.randomUUID().replace(/-/g,'').slice(0,16)}`,
  customer_id: `cust_${(i % 8).toString().padStart(4, '0')}`,
  amount: (Math.random() * 15000 + 500).toFixed(2),
  risk_score: (0.5 + Math.random() * 0.5).toFixed(4),
  risk_level: i % 3 === 0 ? 'CRITICAL' : 'HIGH',
  flags: [
    ...(Math.random() > 0.4 ? ['VELOCITY_EXCEEDED'] : []),
    ...(Math.random() > 0.5 ? ['GEO_ANOMALY'] : []),
    ...(Math.random() > 0.6 ? ['AMOUNT_SPIKE'] : []),
    ...(Math.random() > 0.7 ? ['NEW_DEVICE'] : []),
  ],
  status: i < 5 ? 'REVIEWED' : 'OPEN',
  created_at: new Date(Date.now() - i * 3600000).toISOString(),
}));

const FLAG_COLORS = {
  VELOCITY_EXCEEDED: 'bg-orange-900/30 text-orange-400 border-orange-800',
  GEO_ANOMALY:       'bg-blue-900/30 text-blue-400 border-blue-800',
  AMOUNT_SPIKE:      'bg-yellow-900/30 text-yellow-400 border-yellow-800',
  NEW_DEVICE:        'bg-purple-900/30 text-purple-400 border-purple-800',
  ODD_HOURS:         'bg-slate-800 text-slate-400 border-slate-700',
  BLACKLISTED:       'bg-red-900/30 text-red-400 border-red-800',
};

export default function FraudPage() {
  const [cases, setCases] = useState(MOCK_CASES);
  const [selected, setSelected] = useState(null);
  const [tab, setTab] = useState('cases'); // cases | blacklist
  const [ipInput, setIpInput] = useState('');
  const [custInput, setCustInput] = useState('');
  const [blacklisted, setBlacklisted] = useState({ ips: ['192.168.1.100', '10.0.0.55'], customers: [] });

  const openCases   = cases.filter((c) => c.status === 'OPEN');
  const reviewedCases = cases.filter((c) => c.status === 'REVIEWED');
  const criticalCount = cases.filter((c) => c.risk_level === 'CRITICAL' && c.status === 'OPEN').length;

  const markReviewed = (id) => {
    setCases((prev) => prev.map((c) => c.id === id ? { ...c, status: 'REVIEWED' } : c));
    if (selected?.id === id) setSelected(null);
  };

  const addBlacklistIP = () => {
    if (!ipInput.trim()) return;
    setBlacklisted((b) => ({ ...b, ips: [...b.ips, ipInput.trim()] }));
    setIpInput('');
  };
  const addBlacklistCustomer = () => {
    if (!custInput.trim()) return;
    setBlacklisted((b) => ({ ...b, customers: [...b.customers, custInput.trim()] }));
    setCustInput('');
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Fraud Center</h1>
          <p className="text-sm text-slate-500">
            {openCases.length} open cases · {criticalCount} critical
          </p>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Open Cases',    value: openCases.length,   icon: AlertTriangle, color: 'bg-warning-700' },
          { label: 'Critical',      value: criticalCount,       icon: XCircle,       color: 'bg-red-700' },
          { label: 'Reviewed',      value: reviewedCases.length,icon: CheckCircle,   color: 'bg-success-700' },
          { label: 'Blacklisted IPs',value: blacklisted.ips.length, icon: Ban,       color: 'bg-slate-700' },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="card flex items-center gap-4">
            <div className={clsx('p-2.5 rounded-lg', color)}>
              <Icon size={18} className="text-white" />
            </div>
            <div>
              <p className="text-2xl font-bold text-white">{value}</p>
              <p className="text-xs text-slate-500">{label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-slate-900 border border-slate-800 rounded-lg p-1 w-fit">
        {[['cases','Fraud Cases'], ['blacklist','Blacklists']].map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={clsx('px-4 py-1.5 rounded text-sm font-medium transition-all', tab === key ? 'bg-slate-700 text-white' : 'text-slate-500 hover:text-slate-300')}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'cases' && (
        <div className="grid grid-cols-1 xl:grid-cols-5 gap-6">
          {/* Cases list */}
          <div className="xl:col-span-3 space-y-2">
            {openCases.length === 0 && (
              <div className="card text-center py-12 text-slate-500">
                <CheckCircle size={32} className="mx-auto mb-3 text-success-500" />
                <p>No open fraud cases. All clear!</p>
              </div>
            )}
            {openCases.map((c) => (
              <button
                key={c.id}
                onClick={() => setSelected(c)}
                className={clsx(
                  'w-full text-left card p-4 transition-all cursor-pointer hover:border-slate-600',
                  selected?.id === c.id && 'border-brand-600 bg-brand-600/5'
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={clsx('text-xs font-bold px-2 py-0.5 rounded',
                        c.risk_level === 'CRITICAL' ? 'bg-red-900/50 text-red-400' : 'bg-orange-900/50 text-orange-400'
                      )}>
                        {c.risk_level}
                      </span>
                      <span className="text-xs text-slate-500 font-mono">{c.id}</span>
                    </div>
                    <p className="text-white font-semibold">
                      ${ Number(c.amount).toLocaleString(undefined, { minimumFractionDigits: 2 }) }
                    </p>
                    <p className="text-xs text-slate-500 mt-0.5 font-mono">{c.customer_id}</p>
                    <div className="flex flex-wrap gap-1 mt-2">
                      {c.flags.map((f) => (
                        <span key={f} className={clsx('text-[10px] px-1.5 py-0.5 rounded border', FLAG_COLORS[f] || 'bg-slate-800 text-slate-400 border-slate-700')}>
                          {f.replace(/_/g, ' ')}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-lg font-bold text-red-400">{(Number(c.risk_score) * 100).toFixed(1)}%</p>
                    <p className="text-[10px] text-slate-600">{new Date(c.created_at).toLocaleDateString()}</p>
                  </div>
                </div>
              </button>
            ))}
          </div>

          {/* Case detail panel */}
          <div className="xl:col-span-2">
            {selected ? (
              <div className="card sticky top-0 space-y-4">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <h2 className="font-semibold text-white">Case Detail</h2>
                  <button onClick={() => setSelected(null)} className="text-slate-500 hover:text-white text-lg leading-none">×</button>
                </div>

                <div className="space-y-3">
                  <div>
                    <p className="text-xs text-slate-500">Risk Score</p>
                    <div className="flex items-center gap-3 mt-1">
                      <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
                        <div className="h-full bg-red-500 rounded-full" style={{ width: `${Number(selected.risk_score) * 100}%` }} />
                      </div>
                      <span className="text-sm font-bold text-red-400">{(Number(selected.risk_score) * 100).toFixed(1)}%</span>
                    </div>
                  </div>

                  {[
                    ['Payment ID', selected.payment_id.slice(0, 20) + '…'],
                    ['Customer ID', selected.customer_id],
                    ['Amount', `$${Number(selected.amount).toLocaleString()}`],
                    ['Risk Level', selected.risk_level],
                    ['Detected', new Date(selected.created_at).toLocaleString()],
                  ].map(([k, v]) => (
                    <div key={k}>
                      <p className="text-xs text-slate-500">{k}</p>
                      <p className="text-sm text-white font-mono">{v}</p>
                    </div>
                  ))}

                  <div>
                    <p className="text-xs text-slate-500 mb-2">Triggered Flags</p>
                    {selected.flags.map((f) => (
                      <div key={f} className={clsx('flex items-center gap-2 text-xs px-2 py-1.5 rounded border mb-1', FLAG_COLORS[f])}>
                        <AlertTriangle size={12} />
                        {f.replace(/_/g, ' ')}
                      </div>
                    ))}
                  </div>
                </div>

                <div className="flex gap-2 pt-2 border-t border-slate-800">
                  <button
                    onClick={() => markReviewed(selected.id)}
                    className="btn-primary flex-1 text-sm flex items-center justify-center gap-2"
                  >
                    <CheckCircle size={14} /> Mark Reviewed
                  </button>
                  <button className="btn-secondary text-sm flex items-center gap-2">
                    <Ban size={14} /> Blacklist
                  </button>
                </div>
              </div>
            ) : (
              <div className="card h-64 flex items-center justify-center text-slate-600">
                <div className="text-center">
                  <ShieldAlert size={32} className="mx-auto mb-2 opacity-30" />
                  <p className="text-sm">Select a case to review</p>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {tab === 'blacklist' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* IP Blacklist */}
          <div className="card space-y-4">
            <h2 className="font-semibold text-white">IP Blacklist</h2>
            <div className="flex gap-2">
              <input className="input text-sm" placeholder="192.168.1.100" value={ipInput} onChange={(e) => setIpInput(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && addBlacklistIP()} />
              <button className="btn-primary text-sm px-4 shrink-0" onClick={addBlacklistIP}>Add</button>
            </div>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {blacklisted.ips.map((ip) => (
                <div key={ip} className="flex items-center justify-between p-2.5 bg-slate-800 rounded-lg">
                  <span className="font-mono text-sm text-red-400">{ip}</span>
                  <button onClick={() => setBlacklisted((b) => ({ ...b, ips: b.ips.filter((x) => x !== ip) }))} className="text-slate-600 hover:text-red-400 text-sm">Remove</button>
                </div>
              ))}
              {blacklisted.ips.length === 0 && <p className="text-sm text-slate-600 text-center py-4">No IPs blacklisted</p>}
            </div>
          </div>

          {/* Customer Blacklist */}
          <div className="card space-y-4">
            <h2 className="font-semibold text-white">Customer Blacklist</h2>
            <div className="flex gap-2">
              <input className="input text-sm" placeholder="customer-uuid" value={custInput} onChange={(e) => setCustInput(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && addBlacklistCustomer()} />
              <button className="btn-primary text-sm px-4 shrink-0" onClick={addBlacklistCustomer}>Add</button>
            </div>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {blacklisted.customers.map((c) => (
                <div key={c} className="flex items-center justify-between p-2.5 bg-slate-800 rounded-lg">
                  <span className="font-mono text-sm text-red-400">{c}</span>
                  <button onClick={() => setBlacklisted((b) => ({ ...b, customers: b.customers.filter((x) => x !== c) }))} className="text-slate-600 hover:text-red-400 text-sm">Remove</button>
                </div>
              ))}
              {blacklisted.customers.length === 0 && <p className="text-sm text-slate-600 text-center py-4">No customers blacklisted</p>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
