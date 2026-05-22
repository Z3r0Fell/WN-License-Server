import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { ListChecks, ShieldCheck, KeyRound, Webhook, ArrowLeft } from 'lucide-react';
import { adminApi, adminAuth } from '../lib/api';
import { toast } from 'sonner';

export default function AdminLogin() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('admin@watchnexus.app');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  // 2FA challenge state
  const [mfaToken, setMfaToken] = useState(null);
  const [code, setCode] = useState('');
  const [useRecovery, setUseRecovery] = useState(false);
  const [recoveryCode, setRecoveryCode] = useState('');

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const r = await adminApi.post('/admin/login', { email, password });
      if (r.data?.require_2fa && r.data?.mfa_token) {
        setMfaToken(r.data.mfa_token);
        setCode('');
        setRecoveryCode('');
        setUseRecovery(false);
        toast.message('Enter your 6-digit authenticator code');
        return;
      }
      adminAuth.setSession(r.data.token, r.data.user);
      toast.success('Welcome back');
      navigate('/admin', { replace: true });
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const submit2FA = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const body = { mfa_token: mfaToken };
      if (useRecovery) body.recovery_code = recoveryCode;
      else body.code = code;
      const r = await adminApi.post('/admin/login/2fa', body);
      adminAuth.setSession(r.data.token, r.data.user);
      if (r.data?.used_recovery_code) {
        toast.warning(`Recovery code used. ${r.data.recovery_codes_remaining} left.`);
      } else {
        toast.success('Welcome back');
      }
      navigate('/admin', { replace: true });
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Invalid code');
    } finally {
      setLoading(false);
    }
  };

  const back = () => {
    setMfaToken(null);
    setCode('');
    setRecoveryCode('');
    setUseRecovery(false);
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
        {!mfaToken ? (
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
        ) : (
          <form onSubmit={submit2FA} className="w-full max-w-sm bg-card border border-border rounded-2xl p-7" data-testid="admin-login-2fa-form">
            <button type="button" onClick={back} className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 mb-3" data-testid="admin-login-2fa-back">
              <ArrowLeft className="h-3 w-3" /> Back
            </button>
            <h1 className="text-xl font-semibold tracking-tight">Two-factor authentication</h1>
            <p className="text-sm text-muted-foreground mt-1">
              {useRecovery
                ? 'Enter one of your one-time recovery codes.'
                : 'Open your authenticator app and enter the 6-digit code.'}
            </p>
            <div className="mt-6 space-y-4">
              {useRecovery ? (
                <div>
                  <Label htmlFor="rcode">Recovery code</Label>
                  <Input id="rcode" type="text" value={recoveryCode}
                    onChange={(e) => setRecoveryCode(e.target.value)}
                    placeholder="XXXXX-XXXXX"
                    required autoFocus autoComplete="off"
                    data-testid="admin-login-recovery-input" className="mt-1.5 font-mono tracking-wider" />
                </div>
              ) : (
                <div>
                  <Label htmlFor="tcode">6-digit code</Label>
                  <Input id="tcode" type="text" inputMode="numeric" pattern="[0-9]*"
                    value={code} onChange={(e) => setCode(e.target.value.replace(/[^0-9]/g, ''))}
                    maxLength={6} required autoFocus autoComplete="one-time-code"
                    data-testid="admin-login-totp-input"
                    className="mt-1.5 font-mono text-center text-2xl tracking-[0.4em]" />
                </div>
              )}
              <Button type="submit" disabled={loading} className="w-full bg-emerald-600 hover:bg-emerald-500 text-white" data-testid="admin-login-2fa-submit">
                {loading ? 'Verifying…' : 'Verify and sign in'}
              </Button>
              <button type="button" onClick={() => { setUseRecovery(!useRecovery); setCode(''); setRecoveryCode(''); }} className="text-xs text-muted-foreground hover:text-foreground w-full text-center" data-testid="admin-login-toggle-recovery">
                {useRecovery ? 'Use authenticator code instead' : "Lost your device? Use a recovery code"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
