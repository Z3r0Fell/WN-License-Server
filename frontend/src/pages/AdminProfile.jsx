import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { adminApi, adminAuth } from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { KeyRound, Save } from 'lucide-react';
import { toast } from 'sonner';

export default function AdminProfile() {
  const me = adminAuth.getUser();
  const navigate = useNavigate();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (next !== confirm) {
      toast.error("Passwords don't match");
      return;
    }
    if (next.length < 8) {
      toast.error('New password must be at least 8 characters');
      return;
    }
    setBusy(true);
    try {
      await adminApi.post('/admin/me/change-password', {
        current_password: current,
        new_password: next,
      });
      toast.success('Password updated. Please sign in again.');
      adminAuth.clear();
      navigate('/admin/login', { replace: true });
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to change password');
    } finally { setBusy(false); }
  };

  return (
    <div className="space-y-6 max-w-2xl" data-testid="admin-profile-page">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Profile</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Manage your own account.
        </p>
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
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <KeyRound className="h-4 w-4" /> Change password
          </CardTitle>
          <CardDescription>You'll be signed out after saving.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-3">
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
    </div>
  );
}
