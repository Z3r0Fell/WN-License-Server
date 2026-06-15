import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate, Outlet } from 'react-router-dom';
import {
  Home, Package, KeyRound, Users, FileBarChart2, Webhook,
  Download, ShieldCheck, LogOut, ListChecks, Zap, Cog, UserCog, UserCircle2, CreditCard,
} from 'lucide-react';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { adminAuth } from '../lib/api';
import { cn } from '../lib/utils';

// requires_admin: if true, hidden when the current user has role 'support'.
const NAV = [
  { to: '/admin',           icon: Home,         label: 'Dashboard',    testid: 'nav-admin-dashboard',    requires_admin: false },
  { to: '/admin/quickstart',icon: Zap,          label: 'Quickstart',   testid: 'nav-admin-quickstart',   requires_admin: false },
  { to: '/admin/licenses',  icon: KeyRound,     label: 'Licenses',     testid: 'nav-admin-licenses',     requires_admin: false },
  { to: '/admin/subscriptions', icon: CreditCard, label: 'Subscriptions', testid: 'nav-admin-subscriptions', requires_admin: false },
  { to: '/admin/subscription-plans',icon: Package, label: 'Sub Plans', testid: 'nav-admin-sub-plans',   requires_admin: true  },
  { to: '/admin/products',  icon: Package,      label: 'Products',     testid: 'nav-admin-products',     requires_admin: false },
  { to: '/admin/customers', icon: Users,        label: 'Customers',    testid: 'nav-admin-customers',    requires_admin: false },
  { to: '/admin/api-keys',  icon: ShieldCheck,  label: 'API Keys',     testid: 'nav-admin-api-keys',     requires_admin: true  },
  { to: '/admin/builds',    icon: Download,     label: 'Builds',       testid: 'nav-admin-builds',       requires_admin: false },
  { to: '/admin/webhooks',  icon: Webhook,      label: 'Webhooks',     testid: 'nav-admin-webhooks',     requires_admin: false },
  { to: '/admin/audit',     icon: FileBarChart2,label: 'Audit',        testid: 'nav-admin-audit',        requires_admin: false },
  { to: '/admin/users',     icon: UserCog,      label: 'Admin Users',  testid: 'nav-admin-users',        requires_admin: false },
  { to: '/admin/settings',  icon: Cog,          label: 'Settings',     testid: 'nav-admin-settings',     requires_admin: true  },
];

export default function AdminLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const [authed, setAuthed] = useState(null);
  const user = adminAuth.getUser();
  const role = user?.admin_role || 'admin';
  const isAdmin = role === 'admin';

  useEffect(() => {
    if (!adminAuth.getToken()) {
      setAuthed(false);
      navigate('/admin/login', { replace: true });
    } else {
      setAuthed(true);
    }
  }, [navigate]);

  if (!authed) return null;

  const onLogout = () => {
    adminAuth.clear();
    navigate('/admin/login', { replace: true });
  };

  const visibleNav = NAV.filter((n) => isAdmin || !n.requires_admin);

  return (
    <div className="min-h-screen flex bg-background text-foreground">
      <aside className="w-64 shrink-0 border-r border-border bg-card/40 backdrop-blur sticky top-0 h-screen flex flex-col">
        <div className="px-5 py-5 border-b border-border">
          <Link to="/" className="flex items-center gap-2" data-testid="admin-brand">
            <div className="h-8 w-8 rounded-lg bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center">
              <ListChecks className="h-4 w-4 text-emerald-400" />
            </div>
            <div className="flex flex-col">
              <span className="text-sm font-semibold tracking-tight">WatchNexus</span>
              <span className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">License Admin</span>
            </div>
          </Link>
        </div>
        <nav className="flex-1 p-2 space-y-0.5 overflow-y-auto">
          {visibleNav.map((n) => {
            const Icon = n.icon;
            const active = location.pathname === n.to ||
              (n.to !== '/admin' && location.pathname.startsWith(n.to));
            return (
              <Link
                key={n.to}
                to={n.to}
                data-testid={n.testid}
                className={cn(
                  'flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors',
                  active
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                    : 'text-muted-foreground hover:text-foreground hover:bg-muted/40 border border-transparent',
                )}
              >
                <Icon className="h-4 w-4" />
                <span>{n.label}</span>
              </Link>
            );
          })}
        </nav>
        <div className="p-3 border-t border-border space-y-2">
          <Link
            to="/admin/profile"
            data-testid="nav-admin-profile"
            className={cn(
              'flex items-center gap-2.5 px-2 py-2 rounded-lg text-sm transition-colors',
              location.pathname === '/admin/profile'
                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                : 'text-muted-foreground hover:text-foreground hover:bg-muted/40 border border-transparent',
            )}
          >
            <UserCircle2 className="h-4 w-4" />
            <span>My profile</span>
          </Link>
          <div className="flex items-center justify-between gap-2">
            <div className="min-w-0">
              <div className="flex items-center gap-1.5">
                <div className="text-xs font-medium truncate">{user?.name || 'Admin'}</div>
                <Badge
                  variant="outline"
                  className={cn(
                    'h-4 px-1.5 text-[9px] uppercase tracking-wider',
                    isAdmin
                      ? 'border-emerald-500/30 text-emerald-400 bg-emerald-500/10'
                      : 'border-sky-500/30 text-sky-400 bg-sky-500/10',
                  )}
                  data-testid="sidebar-role-badge"
                >
                  {role}
                </Badge>
              </div>
              <div className="text-[11px] text-muted-foreground truncate">{user?.email}</div>
            </div>
            <Button
              size="icon"
              variant="ghost"
              onClick={onLogout}
              aria-label="Logout"
              data-testid="admin-logout-button"
            >
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </aside>
      <main className="flex-1 min-w-0">
        <div className="max-w-[1400px] mx-auto px-6 py-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
