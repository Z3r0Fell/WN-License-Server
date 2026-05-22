import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { adminApi, adminAuth } from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogDescription } from '../components/ui/dialog';
import { CopyChip } from '../components/CopyChip';
import { KeyRound, Save, ShieldCheck, ShieldOff, RefreshCw, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';

export default function AdminProfile() {
  const me = adminAuth.getUser();
  const navigate = useNavigate();

  // Live "me" status (needs totp_enabled, recovery_codes_remaining).
  const [meStatus, setMeStatus] = useState(null);

  const loadMe = async () => {
    try {
      const r = await adminApi.get('/admin/me');
      setMeStatus(r.data);
    } catch { /* ignore */ }
  };
  useEffect(() => { loadMe(); }, []);

  // Change-password state
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);

  // 2FA enroll state
  const [enrollOpen, setEnrollOpen] = useState(false);
  const [enrollData, setEnrollData] = useState(null); // {secret, otpauth_uri, qr_png_data_uri}
  const [enrollCode, setEnrollCode] = useState('');
  const [enrollPw, setEnrollPw] = useState('');
  const [recoveryCodes, setRecoveryCodes] = useState(null);

  // 2FA disable state
  const [disableOpen, setDisableOpen] = useState(false);
  const [disablePw, setDisablePw] = useState('');
  const [disableCode, setDisableCode] = useState('');

  // Regenerate recovery
  const [regenOpen, setRegenOpen] = useState(false);
  const [regenPw, setRegenPw] = useState('');
  const [regenCode, setRegenCode] = useState('');

  const submitPassword = async (e) => {
    e.preventDefault();
    if (next !== confirm) { toast.error("Passwords don't match"); return; }
    if (next.length < 8) { toast.error('New password must be at least 8 characters'); return; }
    setBusy(true);
    try {
      await adminApi.post('/admin/me/change-password', {
        current_password: current, new_password: next,
      });
      toast.success('Password updated. Please sign in again.');
      adminAuth.clear();
      navigate('/admin/login', { replace: true });
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to change password');
    } finally { setBusy(false); }
  };

  const startEnroll = async () => {
    try {
      const r = await adminApi.post('/admin/me/2fa/enroll');
      setEnrollData(r.data);
      setEnrollCode('');
      setEnrollPw('');
      setRecoveryCodes(null);
      setEnrollOpen(true);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to start 2FA enrollment');
    }
  };

  const verifyEnroll = async (e) => {
    e?.preventDefault?.();
    try {
      const r = await adminApi.post('/admin/me/2fa/verify', {
        secret: enrollData.secret, code: enrollCode, current_password: enrollPw,
      });
      setRecoveryCodes(r.data.recovery_codes);
      toast.success('Two-factor authentication enabled');
      loadMe();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Invalid code');
    }
  };

  const closeEnroll = () => {
    if (recoveryCodes && !window.confirm('Have you saved your recovery codes? You will not see them again.')) {
      return;
    }
    setEnrollOpen(false); setEnrollData(null); setRecoveryCodes(null);
    setEnrollCode(''); setEnrollPw('');
  };

  const submitDisable = async (e) => {
    e.preventDefault();
    try {
      await adminApi.post('/admin/me/2fa/disable', {
        current_password: disablePw, code: disableCode,
      });
      toast.success('Two-factor authentication disabled');
      setDisableOpen(false); setDisablePw(''); setDisableCode('');
      loadMe();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to disable');
    }
  };

  const submitRegen = async (e) => {
    e.preventDefault();
    try {
      const r = await adminApi.post('/admin/me/2fa/regenerate-recovery', {
        current_password: regenPw, code: regenCode,
      });
      setRecoveryCodes(r.data.recovery_codes);
      toast.success('New recovery codes generated. Save them now.');
      setRegenPw(''); setRegenCode('');
      loadMe();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to regenerate');
    }
  };

  const totpEnabled = !!meStatus?.totp_enabled;

  return (
    <div className="space-y-6 max-w-2xl" data-testid="admin-profile-page">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Profile</h1>
        <p className="text-sm text-muted-foreground mt-1">Manage your own account.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Signed in as</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Email</span>
            <span className="font-medium">{me?.email}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Name</span>
            <span>{me?.name || '—'}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-muted-foreground">Role</span>
            <Badge variant="outline" className={
              (me?.admin_role || 'admin') === 'admin'
                ? 'border-emerald-500/30 text-emerald-400 bg-emerald-500/10'
                : 'border-sky-500/30 text-sky-400 bg-sky-500/10'
            } data-testid="profile-role-badge">
              {me?.admin_role || 'admin'}
            </Badge>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-muted-foreground">Two-factor auth</span>
            <Badge variant="outline" className={
              totpEnabled
                ? 'border-emerald-500/30 text-emerald-400 bg-emerald-500/10'
                : 'border-zinc-500/30 text-zinc-400'
            } data-testid="profile-2fa-badge">
              {totpEnabled ? 'Enabled' : 'Off'}
            </Badge>
          </div>
        </CardContent>
      </Card>

      {/* 2FA card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4" /> Two-factor authentication
          </CardTitle>
          <CardDescription>
            Protect your account with a time-based code from an authenticator app (Google Authenticator, 1Password, Authy, etc).
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {!totpEnabled ? (
            <Button onClick={startEnroll} data-testid="profile-2fa-enroll">
              <ShieldCheck className="h-4 w-4 mr-2" /> Enable two-factor auth
            </Button>
          ) : (
            <div className="flex items-center gap-2 flex-wrap">
              <Button variant="secondary" onClick={() => setRegenOpen(true)} data-testid="profile-2fa-regen">
                <RefreshCw className="h-4 w-4 mr-2" /> Regenerate recovery codes
              </Button>
              <Button variant="ghost" onClick={() => setDisableOpen(true)} data-testid="profile-2fa-disable">
                <ShieldOff className="h-4 w-4 mr-2" /> Disable 2FA
              </Button>
              <span className="text-xs text-muted-foreground ml-1">
                {meStatus?.recovery_codes_remaining ?? 0} recovery code{(meStatus?.recovery_codes_remaining ?? 0) === 1 ? '' : 's'} remaining
              </span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Change password card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <KeyRound className="h-4 w-4" /> Change password
          </CardTitle>
          <CardDescription>You'll be signed out after saving.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={submitPassword} className="space-y-3">
            <div>
              <Label htmlFor="cur">Current password</Label>
              <Input id="cur" type="password" required value={current} onChange={(e) => setCurrent(e.target.value)} data-testid="profile-current-pw" />
            </div>
            <div>
              <Label htmlFor="new">New password (min 8 characters)</Label>
              <Input id="new" type="password" minLength={8} required value={next} onChange={(e) => setNext(e.target.value)} data-testid="profile-new-pw" />
            </div>
            <div>
              <Label htmlFor="con">Confirm new password</Label>
              <Input id="con" type="password" minLength={8} required value={confirm} onChange={(e) => setConfirm(e.target.value)} data-testid="profile-confirm-pw" />
            </div>
            <Button type="submit" disabled={busy} data-testid="profile-save">
              <Save className="h-4 w-4 mr-2" />
              {busy ? 'Saving…' : 'Update password'}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Enroll dialog */}
      <Dialog open={enrollOpen} onOpenChange={(o) => { if (!o) closeEnroll(); }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Enable two-factor authentication</DialogTitle>
            <DialogDescription>
              {recoveryCodes
                ? 'Save these recovery codes. They are shown only once and let you sign in if you lose access to your authenticator.'
                : 'Scan the QR code with your authenticator app, then enter the 6-digit code it shows.'}
            </DialogDescription>
          </DialogHeader>

          {!recoveryCodes && enrollData && (
            <div className="space-y-3">
              <div className="flex flex-col items-center bg-white p-3 rounded-lg">
                <img src={enrollData.qr_png_data_uri} alt="2FA QR" className="w-44 h-44" data-testid="enroll-qr" />
              </div>
              <div className="text-xs">
                <Label className="text-xs">Can't scan? Enter this secret manually:</Label>
                <CopyChip text={enrollData.secret} />
              </div>
              <form onSubmit={verifyEnroll} className="space-y-3">
                <div>
                  <Label htmlFor="ec">6-digit code</Label>
                  <Input id="ec" inputMode="numeric" maxLength={6} required
                    value={enrollCode} onChange={(e) => setEnrollCode(e.target.value.replace(/[^0-9]/g, ''))}
                    className="font-mono text-center text-xl tracking-[0.4em]"
                    data-testid="enroll-code" />
                </div>
                <div>
                  <Label htmlFor="epw">Confirm with current password</Label>
                  <Input id="epw" type="password" required value={enrollPw}
                    onChange={(e) => setEnrollPw(e.target.value)} data-testid="enroll-password" />
                </div>
                <DialogFooter>
                  <Button type="button" variant="ghost" onClick={closeEnroll}>Cancel</Button>
                  <Button type="submit" data-testid="enroll-submit">Enable 2FA</Button>
                </DialogFooter>
              </form>
            </div>
          )}

          {recoveryCodes && (
            <div className="space-y-3">
              <div className="flex items-start gap-2 text-xs text-amber-200 border border-amber-500/30 bg-amber-500/10 rounded-lg p-2">
                <AlertCircle className="h-4 w-4 mt-0.5" />
                <span>Save these now. Each code can be used exactly once if you lose your authenticator device.</span>
              </div>
              <div className="grid grid-cols-2 gap-1.5 font-mono text-sm" data-testid="enroll-recovery-codes">
                {recoveryCodes.map((c) => (
                  <div key={c} className="px-2 py-1 rounded border border-border bg-muted/30 text-center">{c}</div>
                ))}
              </div>
              <CopyChip text={recoveryCodes.join('\n')} />
              <DialogFooter>
                <Button onClick={closeEnroll} data-testid="enroll-done">I've saved them</Button>
              </DialogFooter>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Disable 2FA dialog */}
      <Dialog open={disableOpen} onOpenChange={setDisableOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Disable two-factor authentication</DialogTitle>
            <DialogDescription>Confirm with your password and a current 2FA code.</DialogDescription>
          </DialogHeader>
          <form onSubmit={submitDisable} className="space-y-3">
            <div>
              <Label htmlFor="dpw">Current password</Label>
              <Input id="dpw" type="password" required value={disablePw}
                onChange={(e) => setDisablePw(e.target.value)} data-testid="disable-password" />
            </div>
            <div>
              <Label htmlFor="dcode">6-digit code (or paste a recovery code)</Label>
              <Input id="dcode" required value={disableCode}
                onChange={(e) => setDisableCode(e.target.value)} data-testid="disable-code" />
            </div>
            <DialogFooter>
              <Button type="button" variant="ghost" onClick={() => setDisableOpen(false)}>Cancel</Button>
              <Button type="submit" variant="destructive" data-testid="disable-submit">Disable 2FA</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Regenerate recovery dialog */}
      <Dialog open={regenOpen} onOpenChange={(o) => { setRegenOpen(o); if (!o) setRecoveryCodes(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Regenerate recovery codes</DialogTitle>
            <DialogDescription>This invalidates your previous recovery codes.</DialogDescription>
          </DialogHeader>
          {!recoveryCodes ? (
            <form onSubmit={submitRegen} className="space-y-3">
              <div>
                <Label htmlFor="rpw">Current password</Label>
                <Input id="rpw" type="password" required value={regenPw}
                  onChange={(e) => setRegenPw(e.target.value)} data-testid="regen-password" />
              </div>
              <div>
                <Label htmlFor="rcode">6-digit code from your authenticator</Label>
                <Input id="rcode" inputMode="numeric" maxLength={6} required value={regenCode}
                  onChange={(e) => setRegenCode(e.target.value.replace(/[^0-9]/g, ''))}
                  className="font-mono text-center text-xl tracking-[0.4em]"
                  data-testid="regen-code" />
              </div>
              <DialogFooter>
                <Button type="button" variant="ghost" onClick={() => setRegenOpen(false)}>Cancel</Button>
                <Button type="submit" data-testid="regen-submit">Generate new codes</Button>
              </DialogFooter>
            </form>
          ) : (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-1.5 font-mono text-sm" data-testid="regen-recovery-codes">
                {recoveryCodes.map((c) => (
                  <div key={c} className="px-2 py-1 rounded border border-border bg-muted/30 text-center">{c}</div>
                ))}
              </div>
              <CopyChip text={recoveryCodes.join('\n')} />
              <DialogFooter>
                <Button onClick={() => { setRegenOpen(false); setRecoveryCodes(null); }}>Done</Button>
              </DialogFooter>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
