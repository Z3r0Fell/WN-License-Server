import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate, Outlet } from 'react-router-dom';
import { KeyRound, Download, LogOut, ListChecks, LifeBuoy } from 'lucide-react';
import { Button } from './ui/button';
import { customerAuth } from '../lib/api';
import { cn } from '../lib/utils';

const NAV = [
  { to: '/portal', label: 'Licenses', icon: KeyRound, testid: 'nav-portal-licenses' },
  { to: '/portal/downloads', label: 'Downloads', icon: Download, testid: 'nav-portal-downloads' },
  { to: '/docs', label: 'Docs', icon: LifeBuoy, testid: 'nav-portal-docs' },
];

export default function PortalLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [authed, setAuthed] = useState(null); // null=checking, false=redirect, true=ok
  const user = customerAuth.getUser();

  useEffect(() => {
    if (!customerAuth.getToken()) {
      setAuthed(false);
      navigate('/portal/login', { replace: true });
    } else {
      setAuthed(true);
    }
  }, [navigate]);

  if (!authed) {
    // Render nothing while we redirect, so children don't fire auth-required fetches.
    return null;
  }

  const onLogout = () => {
    customerAuth.clear();
    navigate('/portal/login', { replace: true });
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b border-border bg-card/40 backdrop-blur sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
          <Link to="/portal" className="flex items-center gap-2" data-testid="portal-brand">
            <div className="h-7 w-7 rounded-lg bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center">
              <ListChecks className="h-3.5 w-3.5 text-emerald-400" />
            </div>
            <span className="text-sm font-semibold tracking-tight">WatchNexus</span>
            <span className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground hidden sm:inline">Customer Portal</span>
          </Link>
          <nav className="flex items-center gap-1">
            {NAV.map((n) => {
              const Icon = n.icon;
              const active = location.pathname === n.to;
              return (
                <Link
                  key={n.to}
                  to={n.to}
                  data-testid={n.testid}
                  className={cn(
                    'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-colors',
                    active ? 'bg-emerald-500/10 text-emerald-400'
                      : 'text-muted-foreground hover:text-foreground hover:bg-muted/40',
                  )}
                >
                  <Icon className="h-3.5 w-3.5" />
                  <span className="hidden sm:inline">{n.label}</span>
                </Link>
              );
            })}
            <div className="ml-3 pl-3 border-l border-border flex items-center gap-2">
              <span className="text-xs text-muted-foreground hidden sm:inline">{user?.email}</span>
              <Button size="sm" variant="ghost" onClick={onLogout} data-testid="portal-logout-button">
                <LogOut className="h-3.5 w-3.5 mr-1" /> Logout
              </Button>
            </div>
          </nav>
        </div>
      </header>
      <main className="max-w-5xl mx-auto px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}
