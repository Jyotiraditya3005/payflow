import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import './index.css';

import { useAuthStore } from './store/index.js';
import Layout from './components/shared/Layout.jsx';
import LoginPage from './components/auth/LoginPage.jsx';
import DashboardPage from './components/dashboard/DashboardPage.jsx';
import TransactionsPage from './components/transactions/TransactionsPage.jsx';
import FraudPage from './components/fraud/FraudPage.jsx';
import PaymentDetailPage from './components/transactions/PaymentDetailPage.jsx';

function ProtectedRoute({ children }) {
  const { isAuthenticated } = useAuthStore();
  return isAuthenticated ? children : <Navigate to="/login" replace />;
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="transactions" element={<TransactionsPage />} />
          <Route path="transactions/:id" element={<PaymentDetailPage />} />
          <Route path="fraud" element={<FraudPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);
