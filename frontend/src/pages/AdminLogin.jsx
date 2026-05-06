import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { ListChecks, ShieldCheck, KeyRound, Webhook } from 'lucide-react';
import { adminApi, adminAuth } from '../lib/api';
import { toast } from 'sonner';

export default function AdminLogin() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('admin@watchnexus.app');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const r = await adminApi.post('/admin/login', { email, password });
      adminAuth.setSession(r.data.token, r.data.user);
      toast.success('Welcome back');
      navigate('/admin', { replace: true });
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="dark min-h-screen bg-background text-foreground grid lg:grid-cols-2">
      <div className="hidden lg:flex relative items-center justify-center bg-emerald-wash bg-grain p-10">
        <div className="max-w-md">
          <Link to="/" className="flex items-center gap-2 mb-6" data-testid="admin-login-brand">
            <div className="h-8 w-8 rounded-lg bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center">
              <ListChecks className="h-4 w-4 text-emerald-400" />
            </div>
            <span className="font-semibold">WatchNexus Admin</span>
          </Link>
          <h2 className="text-3xl font-semibold tracking-tight">Sign in to manage licenses.</h2>
          <p className="mt-2 text-muted-foreground">Issue keys, revoke installs, audit trails.</p>
          <ul className="mt-8 space-y-3 text-sm">
            <li className="flex items-start gap-3"><ShieldCheck className="h-4 w-4 text-emerald-400 mt-0.5" /> HMAC + RSA signing per product</li>
            <li className="flex items-start gap-3"><KeyRound className="h-4 w-4 text-emerald-400 mt-0.5" /> Bulk import licenses from CSV</li>
            <li className="flex items-start gap-3"><Webhook className="h-4 w-4 text-emerald-400 mt-0.5" /> Webhook events for Lemon Squeezy, Paddle, Gumroad</li>
          </ul>
        </div>
      </div>
      <div className="flex items-center justify-center p-6">
        <form onSubmit={submit} className="w-full max-w-sm bg-card border border-border rounded-2xl p-7" data-testid="admin-login-form">
          <h1 className="text-xl font-semibold tracking-tight">Admin sign in</h1>
          <p className="text-sm text-muted-foreground mt-1">Use the seeded admin account or your own.</p>
          <div className="mt-6 space-y-4">
            <div>
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                required autoComplete="email" data-testid="admin-login-email-input" className="mt-1.5" />
            </div>
            <div>
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                required autoComplete="current-password" data-testid="admin-login-password-input" className="mt-1.5" />
            </div>
            <Button type="submit" disabled={loading} className="w-full bg-emerald-600 hover:bg-emerald-500 text-white" data-testid="admin-login-submit-button">
              {loading ? 'Signing in…' : 'Sign in'}
            </Button>
            <p className="text-[11px] text-muted-foreground text-center">
              Default seed: admin@watchnexus.app / admin12345 — change in production.
            </p>
          </div>
        </form>
      </div>
    </div>
  );
}
