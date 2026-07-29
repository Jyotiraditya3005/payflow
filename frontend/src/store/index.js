import { create } from 'zustand';

export const useAuthStore = create((set) => ({
  user: null,
  token: localStorage.getItem('payflow_token'),
  isAuthenticated: !!localStorage.getItem('payflow_token'),

  login: (token, user) => {
    localStorage.setItem('payflow_token', token);
    set({ token, user, isAuthenticated: true });
  },

  logout: () => {
    localStorage.removeItem('payflow_token');
    set({ token: null, user: null, isAuthenticated: false });
  },

  setUser: (user) => set({ user }),
}));

export const usePaymentStore = create((set, get) => ({
  payments: [],
  summary: null,
  loading: false,
  error: null,
  filters: { status: '', currency: '', page: 1, page_size: 20 },
  selectedPayment: null,

  setPayments: (payments) => set({ payments }),
  setSummary: (summary) => set({ summary }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
  setFilters: (filters) => set({ filters: { ...get().filters, ...filters } }),
  setSelectedPayment: (p) => set({ selectedPayment: p }),
}));

export const useFraudStore = create((set) => ({
  cases: [],
  loading: false,
  setCases: (cases) => set({ cases }),
  setLoading: (loading) => set({ loading }),
}));
