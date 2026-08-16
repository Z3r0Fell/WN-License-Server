import '@/App.css';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from './components/ui/sonner';

import Landing from './pages/Landing';
import Docs from './pages/Docs';
import Checkout from './pages/Checkout';
import AdminLogin from './pages/AdminLogin';
import AdminLayout from './components/AdminLayout';
import AdminDashboard from './pages/AdminDashboard';
import AdminQuickstart from './pages/AdminQuickstart';
import AdminProducts from './pages/AdminProducts';
import AdminLicenses from './pages/AdminLicenses';
import AdminSubscriptions from './pages/AdminSubscriptions';
import AdminSubscriptionPlans from './pages/AdminSubscriptionPlans';
import AdminOrders from './pages/AdminOrders';
import AdminCustomers from './pages/AdminCustomers';
import AdminApiKeys from './pages/AdminApiKeys';
import AdminBuilds from './pages/AdminBuilds';
import AdminWebhooks from './pages/AdminWebhooks';
import AdminAudit from './pages/AdminAudit';
import AdminSettings from './pages/AdminSettings';
import AdminUsers from './pages/AdminUsers';
import AdminProfile from './pages/AdminProfile';
import AdminAcceptInvite from './pages/AdminAcceptInvite';
import PortalLogin from './pages/PortalLogin';
import PortalRegister from './pages/PortalRegister';
import PortalVerifyEmail from './pages/PortalVerifyEmail';
import PortalLayout from './components/PortalLayout';
import PortalDashboard from './pages/PortalDashboard';
import PortalDownloads from './pages/PortalDownloads';

/**
 * Customer-portal hostnames. When the page is served from one of these
 * (set via REACT_APP_CUSTOMER_PORTAL_HOST or `techhub.*`) the SPA boots
 * straight into /portal/login instead of the marketing landing page.
 */
const CUSTOMER_PORTAL_HOST = (process.env.REACT_APP_CUSTOMER_PORTAL_HOST || '').trim();

function isCustomerPortalHostname() {
  if (typeof window === 'undefined') return false;
  const host = (window.location.hostname || '').toLowerCase();
  if (!host) return false;
  if (CUSTOMER_PORTAL_HOST && host === CUSTOMER_PORTAL_HOST.toLowerCase()) return true;
  return host.startsWith('techhub.');
}

function RootRedirect() {
  if (isCustomerPortalHostname()) {
    return <Navigate to="/portal/login" replace />;
  }
  return <Landing />;
}

function App() {
  return (
    <div className="App dark min-h-screen bg-background text-foreground">
      <BrowserRouter>
        <Toaster richColors theme="dark" position="top-right" />
        <Routes>
          <Route path="/" element={<RootRedirect />} />
          <Route path="/docs" element={<Docs />} />
          <Route path="/checkout" element={<Checkout />} />

          {/* Admin */}
          <Route path="/admin/login" element={<AdminLogin />} />
          <Route path="/admin/accept-invite" element={<AdminAcceptInvite />} />
          <Route path="/admin" element={<AdminLayout />}>
            <Route index element={<AdminDashboard />} />
            <Route path="quickstart" element={<AdminQuickstart />} />
            <Route path="products" element={<AdminProducts />} />
            <Route path="licenses" element={<AdminLicenses />} />
            <Route path="subscriptions" element={<AdminSubscriptions />} />
            <Route path="subscription-plans" element={<AdminSubscriptionPlans />} />
            <Route path="orders" element={<AdminOrders />} />
            <Route path="customers" element={<AdminCustomers />} />
            <Route path="api-keys" element={<AdminApiKeys />} />
            <Route path="builds" element={<AdminBuilds />} />
            <Route path="webhooks" element={<AdminWebhooks />} />
            <Route path="audit" element={<AdminAudit />} />
            <Route path="users" element={<AdminUsers />} />
            <Route path="profile" element={<AdminProfile />} />
            <Route path="settings" element={<AdminSettings />} />
          </Route>

          {/* Customer portal */}
          <Route path="/portal/login" element={<PortalLogin />} />
          <Route path="/portal/register" element={<PortalRegister />} />
          <Route path="/portal/verify-email" element={<PortalVerifyEmail />} />
          <Route path="/portal" element={<PortalLayout />}>
            <Route index element={<PortalDashboard />} />
            <Route path="downloads" element={<PortalDownloads />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;
