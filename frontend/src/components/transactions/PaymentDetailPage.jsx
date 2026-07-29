import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, CheckCircle, XCircle, Clock, AlertTriangle, RefreshCw } from 'lucide-react';
import clsx from 'clsx';

const MOCK_DETAIL = {
  id: 'pay_demo_detail_001',
  idempotency_key: 'idem_demo_001_1717000000',
  merchant_id: 'merchant_demo_001',
  customer_id: 'cust_0007',
  amount: '2450.00',
  currency: 'USD',
  fee_amount: '61.25',
  net_amount: '2388.75',
  status: 'COMPLETED',
  payment_method: 'CARD',
  fraud_risk: 'LOW',
  fraud_score: '0.0421',
  fraud_flags: [],
  description: 'Enterprise SaaS subscription - Annual',
  created_at: new Date().toISOString(),
  processed_at: new Date().toISOString(),
  retry_count: 0,
  events: [
    { id: '1', event_type: 'payment.created',    to_status: 'PENDING',     actor: 'payment-service', created_at: new Date(Date.now() - 3000).toISOString() },
    { id: '2', event_type: 'payment.processing', to_status: 'PROCESSING',  actor: 'payment-service', created_at: new Date(Date.now() - 2500).toISOString() },
    { id: '3', event_type: 'fraud.checked',      to_status: 'PROCESSING',  actor: 'fraud-service',   created_at: new Date(Date.now() - 2000).toISOString() },
    { id: '4', event_type: 'payment.completed',  to_status: 'COMPLETED',   actor: 'payment-processor', created_at: new Date(Date.now() - 1500).toISOString() },
  ],
};

const Field = ({ label, value, mono = false }) => (
  <div>
    <p className="text-xs text-slate-500 mb-0.5">{label}</p>
    <p className={clsx('text-sm text-white', mono && 'font-mono')}>{value ?? '—'}</p>
  </div>
);

const StatusIcon = ({ status }) => {
  if (status === 'COMPLETED') return <CheckCircle size={16} className="text-success-500" />;
  if (status === 'FAILED')    return <XCircle size={16} className="text-danger-500" />;
  if (status === 'PENDING')   return <Clock size={16} className="text-warning-500" />;
  return <AlertTriangle size={16} className="text-slate-500" />;
};

export default function PaymentDetailPage() {
  const { id } = useParams();
  const p = MOCK_DETAIL; // In production: fetch from paymentsAPI.get(id)

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Back */}
      <Link to="/transactions" className="flex items-center gap-2 text-sm text-slate-400 hover:text-white transition-colors w-fit">
        <ArrowLeft size={16} /> Back to Transactions
      </Link>

      {/* Header */}
      <div className="card flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <StatusIcon status={p.status} />
            <span className={clsx('text-sm font-semibold',
              p.status === 'COMPLETED' ? 'text-success-500' :
              p.status === 'FAILED' ? 'text-danger-500' : 'text-warning-500'
            )}>{p.status}</span>
          </div>
          <p className="text-3xl font-bold text-white">${Number(p.amount).toLocaleString(undefined, { minimumFractionDigits: 2 })} {p.currency}</p>
          <p className="text-sm text-slate-500 mt-1 font-mono">{p.id}</p>
        </div>
        <div className="text-right">
          <p className="text-xs text-slate-500">Net to Merchant</p>
          <p className="text-xl font-bold text-success-500">${Number(p.net_amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}</p>
          <p className="text-xs text-slate-600">Fee: ${p.fee_amount}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Details */}
        <div className="card space-y-4">
          <h2 className="font-semibold text-white border-b border-slate-800 pb-3">Payment Details</h2>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Payment Method" value={p.payment_method} />
            <Field label="Currency" value={p.currency} />
            <Field label="Customer ID" value={p.customer_id} mono />
            <Field label="Merchant ID" value={p.merchant_id.slice(0,20) + '…'} mono />
            <Field label="Description" value={p.description} />
            <Field label="Retry Count" value={p.retry_count} />
            <Field label="Created" value={new Date(p.created_at).toLocaleString()} />
            <Field label="Processed" value={new Date(p.processed_at).toLocaleString()} />
          </div>
          <div className="pt-2">
            <Field label="Idempotency Key" value={p.idempotency_key} mono />
          </div>
        </div>

        {/* Fraud Analysis */}
        <div className="card space-y-4">
          <h2 className="font-semibold text-white border-b border-slate-800 pb-3">Fraud Analysis</h2>
          <div className="flex items-center gap-4">
            <div className="relative w-24 h-24">
              <svg className="w-full h-full -rotate-90" viewBox="0 0 36 36">
                <circle cx="18" cy="18" r="15.9155" fill="none" stroke="#1e293b" strokeWidth="3" />
                <circle cx="18" cy="18" r="15.9155" fill="none" stroke={
                  p.fraud_risk === 'LOW' ? '#22c55e' : p.fraud_risk === 'MEDIUM' ? '#f59e0b' : '#ef4444'
                } strokeWidth="3" strokeDasharray={`${Number(p.fraud_score)*100} 100`} strokeLinecap="round" />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-lg font-bold text-white">{(Number(p.fraud_score)*100).toFixed(1)}%</span>
                <span className="text-xs text-slate-500">risk</span>
              </div>
            </div>
            <div className="flex-1 space-y-3">
              <div>
                <p className="text-xs text-slate-500">Risk Level</p>
                <p className="font-semibold text-success-500 text-lg">{p.fraud_risk}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">ML Score</p>
                <div className="flex items-center gap-2 mt-1">
                  <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                    <div className="h-full bg-success-500 rounded-full" style={{ width: `${Number(p.fraud_score)*100}%` }} />
                  </div>
                  <span className="text-xs text-slate-400">{p.fraud_score}</span>
                </div>
              </div>
            </div>
          </div>
          <div>
            <p className="text-xs text-slate-500 mb-2">Fraud Flags</p>
            {p.fraud_flags.length === 0 ? (
              <p className="text-sm text-success-500 flex items-center gap-1.5">
                <CheckCircle size={14} /> No flags raised
              </p>
            ) : (
              <div className="space-y-1">
                {p.fraud_flags.map((f) => (
                  <div key={f} className="flex items-center gap-2 text-sm text-warning-500">
                    <AlertTriangle size={12} /> {f}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Event Timeline */}
      <div className="card">
        <h2 className="font-semibold text-white mb-5">Event Timeline</h2>
        <div className="relative pl-6">
          <div className="absolute left-2 top-0 bottom-0 w-px bg-slate-800" />
          <div className="space-y-4">
            {p.events.map((ev, i) => (
              <div key={ev.id} className="relative flex items-start gap-4">
                <span className="absolute -left-[17px] w-2.5 h-2.5 rounded-full bg-brand-600 border-2 border-slate-900 mt-0.5 shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 flex-wrap">
                    <p className="text-sm font-medium text-white font-mono">{ev.event_type}</p>
                    {ev.to_status && (
                      <span className="text-xs text-slate-500">→ <span className="text-slate-300">{ev.to_status}</span></span>
                    )}
                    <span className="text-xs text-slate-600 ml-auto">{ev.actor}</span>
                  </div>
                  <p className="text-xs text-slate-600 mt-0.5">{new Date(ev.created_at).toLocaleString()}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
