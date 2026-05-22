import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { publicApi, adminAuth } from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Loader2, ShieldCheck, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';

export default function AdminAcceptInvite() {
  const [params] = useSearchParams();
  const token = params.get('token') || '';
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [invite, setInvite] = useState(null);
  const [error, setError] = useState(null);

  const [pw, setPw] = useState('');
  const [pw2, setPw2] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!token) {
      setError('Missing invite token in URL');
      setLoading(false);
      return;
    }
    (async () => {
      try {
        const r = await publicApi.get(`/public/invites/${token}`);
        setInvite(r.data);
      } catch (e) {
        setError(e?.response?.data?.detail || 'Invite not found or already used');
      } finally { setLoading(false); }
    })();
  }, [token]);

  const submit = async (e) => {
    e.preventDefault();
    if (pw !== pw2) { toast.error("Passwords don't match"); return; }
    if (pw.length < 8) { toast.error('Password must be at least 8 characters'); return; }
    setBusy(true);
    try {
      const r = await publicApi.post('/public/invites/accept', { token, password: pw });
      adminAuth.setSession(r.data.token, r.data.user);
      toast.success('Welcome to WatchNexus');
      navigate('/admin', { replace: true });
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to accept invite');
    } finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-background" data-testid="accept-invite-page">
      <div className="w-full max-w-md">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-emerald-400" />
              Accept admin invite
            </CardTitle>
            <CardDescription>Set a password to activate your account.</CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" /> Verifying invite…
              </div>
            ) : error ? (
              <div className="flex items-start gap-2 text-sm text-rose-400">
                <AlertCircle className="h-4 w-4 mt-0.5" />
                <div>
                  <div>{error}</div>
                  <Button variant="link" className="px-0" onClick={() => navigate('/admin/login')}>Go to admin login</Button>
                </div>
              </div>
            ) : (
              <form onSubmit={submit} className="space-y-3">
                <div className="rounded-lg border border-border bg-card/40 px-3 py-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Email</span>
                    <span className="font-medium">{invite.email}</span>
                  </div>
                  <div className="flex justify-between mt-1">
                    <span className="text-muted-foreground">Role</span>
                    <Badge variant="outline" className={
                      invite.admin_role === 'admin'
                        ? 'border-emerald-500/30 text-emerald-400 bg-emerald-500/10'
                        : 'border-sky-500/30 text-sky-400 bg-sky-500/10'
                    }>{invite.admin_role}</Badge>
                  </div>
                </div>
                <div>
                  <Label htmlFor="ap1">Password (min 8 chars)</Label>
                  <Input id="ap1" type="password" minLength={8} required value={pw} onChange={(e) => setPw(e.target.value)} data-testid="accept-invite-pw" />
                </div>
                <div>
                  <Label htmlFor="ap2">Confirm password</Label>
                  <Input id="ap2" type="password" minLength={8} required value={pw2} onChange={(e) => setPw2(e.target.value)} data-testid="accept-invite-pw2" />
                </div>
                <Button type="submit" disabled={busy} className="w-full" data-testid="accept-invite-submit">
                  {busy ? 'Activating…' : 'Activate account'}
                </Button>
              </form>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
