import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Search, Filter, ArrowUpRight, RefreshCw, Download } from 'lucide-react';
import clsx from 'clsx';

// ─── Mock payment data ────────────────────────────────────────────────────────
const MOCK_PAYMENTS = Array.from({ length: 50 }, (_, i) => {
  const statuses = ['COMPLETED','COMPLETED','COMPLETED','PENDING','FAILED','REFUNDED'];
  const methods  = ['CARD','CARD','BANK_TRANSFER','WALLET','UPI'];
  const currencies = ['USD','USD','USD','EUR','GBP','INR'];
  const risks = ['LOW','LOW','LOW','MEDIUM','HIGH'];
  const s = statuses[Math.floor(Math.random() * statuses.length)];
  const r = risks[Math.floor(Math.random() * risks.length)];
  const d = new Date(); d.setMinutes(d.getMinutes() - i * 17);
  return {
    id: `pay_${crypto.randomUUID().replace(/-/g, '').slice(0,16)}`,
    amount: (Math.random() * 9900 + 100).toFixed(2),
    currency: currencies[Math.floor(Math.random() * currencies.length)],
    status: s,
    payment_method: methods[Math.floor(Math.random() * methods.length)],
    fraud_risk: r,
    fraud_score: (Math.random() * 0.8).toFixed(3),
    merchant_id: 'merchant_demo_001',
    customer_id: `cust_${(i % 15).toString().padStart(4,'0')}`,
    created_at: d.toISOString(),
    idempotency_key: `idem_${i}_${Date.now()}`,
  };
});

// ─── Status badge ─────────────────────────────────────────────────────────────
const StatusBadge = ({ status }) => {
  const cfg = {
    COMPLETED: 'badge-success',
    PENDING: 'badge-warning',
    FAILED: 'badge-danger',
    REFUNDED: 'badge-neutral',
    CANCELLED: 'badge-neutral',
    PARTIALLY_REFUNDED: 'badge-warning',
  };
  return <span className={cfg[status] || 'badge-neutral'}>{status}</span>;
};

const RiskBadge = ({ risk }) => {
  const cfg = {
    LOW: 'text-success-500 bg-success-500/10',
    MEDIUM: 'text-warning-500 bg-warning-500/10',
    HIGH: 'text-red-400 bg-red-400/10',
    CRITICAL: 'text-red-600 bg-red-600/10 font-bold',
  };
  return (
    <span className={clsx('px-2 py-0.5 rounded text-xs font-medium', cfg[risk] || '')}>
      {risk}
    </span>
  );
};

// ─── Component ────────────────────────────────────────────────────────────────
export default function TransactionsPage() {
  const [payments, setPayments] = useState(MOCK_PAYMENTS);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [riskFilter, setRiskFilter] = useState('');
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 15;

  const filtered = payments.filter((p) => {
    const q = search.toLowerCase();
    const matchSearch = !q || p.id.includes(q) || p.customer_id.includes(q) || p.amount.includes(q);
    const matchStatus = !statusFilter || p.status === statusFilter;
    const matchRisk = !riskFilter || p.fraud_risk === riskFilter;
    return matchSearch && matchStatus && matchRisk;
  });

  const paginated = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);

  const refresh = () => {
    setLoading(true);
    setTimeout(() => setLoading(false), 600);
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Transactions</h1>
          <p className="text-sm text-slate-500">{filtered.length} payments found</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={refresh} className="btn-secondary flex items-center gap-2 text-sm" disabled={loading}>
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
          <button className="btn-secondary flex items-center gap-2 text-sm">
            <Download size={14} /> Export
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-48">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            className="input pl-9 text-sm"
            placeholder="Search by ID, customer..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          />
        </div>
        <select
          className="input w-auto text-sm cursor-pointer"
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
        >
          <option value="">All Statuses</option>
          {['COMPLETED','PENDING','FAILED','REFUNDED','CANCELLED'].map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <select
          className="input w-auto text-sm cursor-pointer"
          value={riskFilter}
          onChange={(e) => { setRiskFilter(e.target.value); setPage(1); }}
        >
          <option value="">All Risk Levels</option>
          {['LOW','MEDIUM','HIGH','CRITICAL'].map((r) => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="card p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-800">
                {['Payment ID','Amount','Method','Status','Fraud Risk','Score','Customer','Time',''].map((h) => (
                  <th key={h} className="text-left text-xs font-medium text-slate-500 uppercase tracking-wide px-4 py-3 whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {paginated.map((p) => (
                <tr key={p.id} className="hover:bg-slate-800/40 transition-colors group">
                  <td className="px-4 py-3 font-mono text-xs text-slate-400 whitespace-nowrap">
                    {p.id.slice(0, 20)}…
                  </td>
                  <td className="px-4 py-3 font-semibold text-white whitespace-nowrap">
                    {p.currency} {Number(p.amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </td>
                  <td className="px-4 py-3 text-slate-400 whitespace-nowrap">{p.payment_method}</td>
                  <td className="px-4 py-3 whitespace-nowrap"><StatusBadge status={p.status} /></td>
                  <td className="px-4 py-3 whitespace-nowrap"><RiskBadge risk={p.fraud_risk} /></td>
                  <td className="px-4 py-3 text-slate-500 whitespace-nowrap">{p.fraud_score}</td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-400 whitespace-nowrap">
                    {p.customer_id}
                  </td>
                  <td className="px-4 py-3 text-slate-500 whitespace-nowrap text-xs">
                    {new Date(p.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      to={`/transactions/${p.id}`}
                      className="opacity-0 group-hover:opacity-100 transition-opacity text-brand-500 hover:text-brand-400"
                    >
                      <ArrowUpRight size={16} />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-slate-800">
          <p className="text-xs text-slate-500">
            Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, filtered.length)} of {filtered.length}
          </p>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="btn-secondary text-xs py-1 px-3 disabled:opacity-40"
            >← Prev</button>
            <span className="text-xs text-slate-500">{page} / {totalPages}</span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="btn-secondary text-xs py-1 px-3 disabled:opacity-40"
            >Next →</button>
          </div>
        </div>
      </div>
    </div>
  );
}
