import axios from 'axios';

const BASE_URL = import.meta.env.VITE_API_GATEWAY_URL || 'http://localhost:8080';

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('payflow_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  config.headers['X-Request-ID'] = crypto.randomUUID();
  return config;
});

// Handle 401 globally — redirect to login
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('payflow_token');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  }
);

// ─── Auth ─────────────────────────────────────────────────────────────────────
export const authAPI = {
  login: (email, password) =>
    api.post('/api/v1/auth/login', { email, password }),
  register: (data) => api.post('/api/v1/auth/register', data),
  me: () => api.get('/api/v1/auth/me'),
};

// ─── Payments ─────────────────────────────────────────────────────────────────
export const paymentsAPI = {
  list: (params = {}) => api.get('/api/v1/payments/', { params }),
  get: (id) => api.get(`/api/v1/payments/${id}`),
  initiate: (data) => api.post('/api/v1/payments/', data),
  refund: (id, data) => api.post(`/api/v1/payments/${id}/refund`, data),
  cancel: (id) => api.post(`/api/v1/payments/${id}/cancel`),
  summary: (merchantId) =>
    api.get('/api/v1/payments/summary/stats', { params: { merchant_id: merchantId } }),
};

// ─── Fraud ────────────────────────────────────────────────────────────────────
export const fraudAPI = {
  cases: (params = {}) => api.get('/api/v1/fraud/cases', { params }),
  blacklistIP: (ip) => api.post('/api/v1/fraud/blacklist/ip', null, { params: { ip_address: ip } }),
  blacklistCustomer: (id) =>
    api.post('/api/v1/fraud/blacklist/customer', null, { params: { customer_id: id } }),
};

export default api;
