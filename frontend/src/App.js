import '@/App.css';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from './components/ui/sonner';

import Landing from './pages/Landing';
import Docs from './pages/Docs';
import AdminLogin from './pages/AdminLogin';
import AdminLayout from './components/AdminLayout';
import AdminDashboard from './pages/AdminDashboard';
import AdminProducts from './pages/AdminProducts';
import AdminLicenses from './pages/AdminLicenses';
import AdminCustomers from './pages/AdminCustomers';
import AdminApiKeys from './pages/AdminApiKeys';
import AdminBuilds from './pages/AdminBuilds';
import AdminWebhooks from './pages/AdminWebhooks';
import AdminAudit from './pages/AdminAudit';
import PortalLogin from './pages/PortalLogin';
import PortalRegister from './pages/PortalRegister';
import PortalLayout from './components/PortalLayout';
import PortalDashboard from './pages/PortalDashboard';
import PortalDownloads from './pages/PortalDownloads';

function App() {
  return (
    <div className="App dark min-h-screen bg-background text-foreground">
      <BrowserRouter>
        <Toaster richColors theme="dark" position="top-right" />
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/docs" element={<Docs />} />

          {/* Admin */}
          <Route path="/admin/login" element={<AdminLogin />} />
          <Route path="/admin" element={<AdminLayout />}>
            <Route index element={<AdminDashboard />} />
            <Route path="products" element={<AdminProducts />} />
            <Route path="licenses" element={<AdminLicenses />} />
            <Route path="customers" element={<AdminCustomers />} />
            <Route path="api-keys" element={<AdminApiKeys />} />
            <Route path="builds" element={<AdminBuilds />} />
            <Route path="webhooks" element={<AdminWebhooks />} />
            <Route path="audit" element={<AdminAudit />} />
          </Route>

          {/* Customer portal */}
          <Route path="/portal/login" element={<PortalLogin />} />
          <Route path="/portal/register" element={<PortalRegister />} />
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
