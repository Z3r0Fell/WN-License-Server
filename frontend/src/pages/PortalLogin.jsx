import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { ListChecks } from 'lucide-react';
import { customerApi, customerAuth } from '../lib/api';
import { toast } from 'sonner';

export default function PortalLogin() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const r = await customerApi.post('/customer/login', { email, password });
      customerAuth.setSession(r.data.token, r.data.user);
      toast.success('Welcome back');
      navigate('/portal', { replace: true });
    } catch (e) { toast.error(e?.response?.data?.detail || 'Login failed'); }
    finally { setLoading(false); }
  };

  return (
    <div className="dark min-h-screen bg-background text-foreground flex items-center justify-center p-6 bg-emerald-wash">
      <form onSubmit={submit} className="w-full max-w-sm bg-card border border-border rounded-2xl p-7" data-testid="portal-login-form">
        <Link to="/" className="flex items-center gap-2 mb-4" data-testid="portal-login-brand">
          <div className="h-8 w-8 rounded-lg bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center">
            <ListChecks className="h-4 w-4 text-emerald-400" />
          </div>
          <span className="font-semibold">WatchNexus Portal</span>
        </Link>
        <h1 className="text-xl font-semibold tracking-tight">Sign in to your portal</h1>
        <p className="text-sm text-muted-foreground mt-1">View licenses, deactivate machines, download builds.</p>
        <div className="mt-6 space-y-4">
          <div><Label htmlFor="e">Email</Label><Input id="e" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="mt-1.5" data-testid="portal-login-email-input" /></div>
          <div><Label htmlFor="p">Password</Label><Input id="p" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} className="mt-1.5" data-testid="portal-login-password-input" /></div>
          <Button type="submit" disabled={loading} className="w-full bg-emerald-600 hover:bg-emerald-500 text-white" data-testid="portal-login-submit-button">
            {loading ? 'Signing in…' : 'Sign in'}
          </Button>
          <p className="text-xs text-muted-foreground text-center">No account? <Link to="/portal/register" className="text-emerald-400 hover:underline" data-testid="portal-login-to-register">Register</Link></p>
        </div>
      </form>
    </div>
  );
}
