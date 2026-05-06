import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { ListChecks } from 'lucide-react';
import { customerApi, customerAuth } from '../lib/api';
import { toast } from 'sonner';

export default function PortalRegister() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: '', email: '', password: '' });
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (form.password.length < 8) { toast.error('Password must be 8+ characters'); return; }
    setLoading(true);
    try {
      const r = await customerApi.post('/customer/register', form);
      customerAuth.setSession(r.data.token, r.data.user);
      toast.success('Account created');
      navigate('/portal', { replace: true });
    } catch (e) { toast.error(e?.response?.data?.detail || 'Registration failed'); }
    finally { setLoading(false); }
  };

  return (
    <div className="dark min-h-screen bg-background text-foreground flex items-center justify-center p-6 bg-emerald-wash">
      <form onSubmit={submit} className="w-full max-w-sm bg-card border border-border rounded-2xl p-7" data-testid="portal-register-form">
        <Link to="/" className="flex items-center gap-2 mb-4">
          <div className="h-8 w-8 rounded-lg bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center">
            <ListChecks className="h-4 w-4 text-emerald-400" />
          </div>
          <span className="font-semibold">WatchNexus Portal</span>
        </Link>
        <h1 className="text-xl font-semibold tracking-tight">Create your account</h1>
        <p className="text-sm text-muted-foreground mt-1">Use the email associated with your purchase to see your existing licenses automatically.</p>
        <div className="mt-6 space-y-4">
          <div><Label>Name</Label><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="mt-1.5" data-testid="portal-register-name-input" /></div>
          <div><Label>Email</Label><Input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="mt-1.5" data-testid="portal-register-email-input" /></div>
          <div>
            <Label>Password</Label>
            <Input type="password" required value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className="mt-1.5" data-testid="portal-register-password-input" />
            <div className="text-xs text-muted-foreground mt-1">Min 8 characters.</div>
          </div>
          <Button type="submit" disabled={loading} className="w-full bg-emerald-600 hover:bg-emerald-500 text-white" data-testid="portal-register-submit-button">
            {loading ? 'Creating…' : 'Create account'}
          </Button>
          <p className="text-xs text-muted-foreground text-center">Have an account? <Link to="/portal/login" className="text-emerald-400 hover:underline" data-testid="portal-register-to-login">Sign in</Link></p>
        </div>
      </form>
    </div>
  );
}
