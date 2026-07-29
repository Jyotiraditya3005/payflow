import React, { useState } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, CreditCard, ShieldAlert, LogOut,
  Menu, X, Bell, Zap, ChevronRight
} from 'lucide-react';
import { useAuthStore } from '../../store/index.js';
import clsx from 'clsx';

const NAV = [
  { to: '/dashboard',    icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/transactions', icon: CreditCard,       label: 'Transactions' },
  { to: '/fraud',        icon: ShieldAlert,       label: 'Fraud Center' },
];

export default function Layout() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [notifications] = useState(3);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="flex h-screen overflow-hidden">
      {/* ── Sidebar ─────────────────────────────────────────────────────── */}
      <aside className={clsx(
        'fixed inset-y-0 left-0 z-50 flex flex-col w-64 bg-slate-900 border-r border-slate-800 transition-transform duration-200 lg:translate-x-0 lg:static lg:z-auto',
        open ? 'translate-x-0' : '-translate-x-full'
      )}>
        {/* Logo */}
        <div className="flex items-center gap-3 px-6 py-5 border-b border-slate-800">
          <div className="flex items-center justify-center w-9 h-9 bg-brand-600 rounded-lg">
            <Zap size={18} className="text-white" />
          </div>
          <div>
            <p className="font-bold text-white tracking-tight">PayFlow</p>
            <p className="text-xs text-slate-500">Merchant Portal</p>
          </div>
          <button className="ml-auto lg:hidden text-slate-400" onClick={() => setOpen(false)}>
            <X size={18} />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
          {NAV.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              onClick={() => setOpen(false)}
              className={({ isActive }) => clsx(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all group',
                isActive
                  ? 'bg-brand-600 text-white'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800'
              )}
            >
              <Icon size={18} />
              <span className="flex-1">{label}</span>
              <ChevronRight size={14} className="opacity-0 group-hover:opacity-100 transition-opacity" />
            </NavLink>
          ))}
        </nav>

        {/* User */}
        <div className="px-3 py-4 border-t border-slate-800">
          <div className="flex items-center gap-3 px-3 py-2 rounded-lg bg-slate-800">
            <div className="w-8 h-8 rounded-full bg-brand-600 flex items-center justify-center text-white text-sm font-bold">
              {(user?.full_name || user?.email || 'U')[0].toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white truncate">{user?.full_name || 'Merchant'}</p>
              <p className="text-xs text-slate-500 truncate">{user?.role || 'MERCHANT'}</p>
            </div>
            <button
              onClick={handleLogout}
              className="text-slate-500 hover:text-red-400 transition-colors"
              title="Logout"
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      {/* ── Mobile overlay ──────────────────────────────────────────────── */}
      {open && (
        <div className="fixed inset-0 z-40 bg-black/60 lg:hidden" onClick={() => setOpen(false)} />
      )}

      {/* ── Main content ────────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Topbar */}
        <header className="flex items-center gap-4 px-6 py-4 bg-slate-900 border-b border-slate-800 shrink-0">
          <button className="lg:hidden text-slate-400 hover:text-white" onClick={() => setOpen(true)}>
            <Menu size={20} />
          </button>
          <div className="flex-1" />
          {/* Live indicator */}
          <div className="flex items-center gap-2 text-xs text-success-500">
            <span className="w-2 h-2 rounded-full bg-success-500 animate-pulse" />
            Live
          </div>
          {/* Notifications */}
          <button className="relative text-slate-400 hover:text-white transition-colors">
            <Bell size={20} />
            {notifications > 0 && (
              <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 text-white text-[10px] rounded-full flex items-center justify-center">
                {notifications}
              </span>
            )}
          </button>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
