import { useEffect, useState } from 'react';
import { adminApi, adminAuth } from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../components/ui/alert-dialog';
import { Switch } from '../components/ui/switch';
import { Badge } from '../components/ui/badge';
import { Skeleton } from '../components/ui/skeleton';
import { EmptyState } from '../components/EmptyState';
import { CopyChip } from '../components/CopyChip';
import { UserPlus, Mail, Key as KeyIcon, Trash2, Pencil, Users as UsersIcon, ShieldAlert } from 'lucide-react';
import { toast } from 'sonner';

const ROLE_LABEL = {
  admin: 'Admin',
  support: 'Support',
};

function RoleBadge({ role }) {
  const r = role || 'admin';
  return (
    <Badge
      variant="outline"
      className={r === 'admin'
        ? 'border-emerald-500/30 text-emerald-400 bg-emerald-500/10'
        : 'border-sky-500/30 text-sky-400 bg-sky-500/10'}
      data-testid={`role-badge-${r}`}
    >
      {ROLE_LABEL[r] || r}
    </Badge>
  );
}

export default function AdminUsers() {
  const me = adminAuth.getUser();
  const myRole = me?.admin_role || 'admin';
  const isAdmin = myRole === 'admin';

  const [users, setUsers] = useState([]);
  const [invites, setInvites] = useState([]);
  const [loading, setLoading] = useState(true);

  // Create user modal
  const [createOpen, setCreateOpen] = useState(false);
  const [cEmail, setCEmail] = useState('');
  const [cName, setCName] = useState('');
  const [cRole, setCRole] = useState('support');
  const [cPassword, setCPassword] = useState('');

  // Invite modal
  const [inviteOpen, setInviteOpen] = useState(false);
  const [iEmail, setIEmail] = useState('');
  const [iName, setIName] = useState('');
  const [iRole, setIRole] = useState('support');
  const [lastInvite, setLastInvite] = useState(null);

  // Edit modal
  const [editing, setEditing] = useState(null);
  const [eName, setEName] = useState('');
  const [eRole, setERole] = useState('support');
  const [eActive, setEActive] = useState(true);

  // Reset-password modal
  const [resetUser, setResetUser] = useState(null);
  const [rPassword, setRPassword] = useState('');

  // Delete confirmation
  const [confirmDelete, setConfirmDelete] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const u = await adminApi.get('/admin/users');
      setUsers(u.data);
      if (isAdmin) {
        try {
          const inv = await adminApi.get('/admin/users/invites');
          setInvites(inv.data || []);
        } catch { /* ignore */ }
      }
    } catch (e) {
      toast.error('Failed to load users');
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const create = async (e) => {
    e.preventDefault();
    try {
      await adminApi.post('/admin/users', {
        email: cEmail, name: cName, admin_role: cRole, password: cPassword,
      });
      toast.success('User created');
      setCreateOpen(false);
      setCEmail(''); setCName(''); setCRole('support'); setCPassword('');
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to create user');
    }
  };

  const invite = async (e) => {
    e.preventDefault();
    try {
      const r = await adminApi.post('/admin/users/invite', {
        email: iEmail, name: iName, admin_role: iRole,
      });
      setLastInvite(r.data);
      if (r.data?.email_sent) toast.success('Invite sent by email');
      else toast.warning('Invite created. Email not configured — copy the link below.');
      setIEmail(''); setIName(''); setIRole('support');
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to create invite');
    }
  };

  const openEdit = (u) => {
    setEditing(u);
    setEName(u.name || '');
    setERole(u.admin_role || 'admin');
    setEActive(u.is_active !== false);
  };

  const saveEdit = async () => {
    try {
      await adminApi.patch(`/admin/users/${editing.id}`, {
        name: eName, admin_role: eRole, is_active: eActive,
      });
      toast.success('User updated');
      setEditing(null);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to update');
    }
  };

  const doReset = async () => {
    try {
      await adminApi.post(`/admin/users/${resetUser.id}/reset-password`, {
        new_password: rPassword,
      });
      toast.success('Password reset');
      setResetUser(null);
      setRPassword('');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to reset password');
    }
  };

  const doDelete = async () => {
    try {
      await adminApi.delete(`/admin/users/${confirmDelete.id}`);
      toast.success('User deleted');
      setConfirmDelete(null);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to delete');
    }
  };

  const revokeInvite = async (iid) => {
    try {
      await adminApi.delete(`/admin/users/invites/${iid}`);
      toast.success('Invite revoked');
      load();
    } catch { toast.error('Failed to revoke'); }
  };

  return (
    <div className="space-y-6" data-testid="admin-users-page">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Admin Users</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Manage who can sign in to the admin panel. <RoleBadge role="admin" /> has full access. <RoleBadge role="support" /> is read-only and can deactivate seats.
          </p>
        </div>
        {isAdmin && (
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => { setInviteOpen(true); setLastInvite(null); }}
              data-testid="users-invite-button"
            >
              <Mail className="h-4 w-4 mr-2" /> Invite by email
            </Button>
            <Button onClick={() => setCreateOpen(true)} data-testid="users-create-button">
              <UserPlus className="h-4 w-4 mr-2" /> Add user
            </Button>
          </div>
        )}
      </div>

      {!isAdmin && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground border border-border bg-card/40 rounded-lg px-3 py-2">
          <ShieldAlert className="h-4 w-4 text-amber-400" />
          You're signed in with the <b className="mx-1">Support</b> role — you can view this list but not modify it.
        </div>
      )}

      {loading ? (
        <div className="space-y-2">
          {[1,2,3].map((i) => <Skeleton key={i} className="h-14 w-full" />)}
        </div>
      ) : users.length === 0 ? (
        <EmptyState icon={UsersIcon} title="No users yet" />
      ) : (
        <div className="border border-border rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-card/60">
              <tr className="text-left text-xs uppercase tracking-wider text-muted-foreground">
                <th className="px-4 py-3">Email</th>
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Role</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Last login</th>
                {isAdmin && <th className="px-4 py-3 text-right">Actions</th>}
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const isMe = u.id === me?.id;
                return (
                  <tr key={u.id} className="border-t border-border" data-testid={`user-row-${u.email}`}>
                    <td className="px-4 py-3 font-medium">
                      {u.email}
                      {isMe && <span className="ml-2 text-xs text-muted-foreground">(you)</span>}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">{u.name || '—'}</td>
                    <td className="px-4 py-3"><RoleBadge role={u.admin_role} /></td>
                    <td className="px-4 py-3">
                      {u.is_active === false
                        ? <Badge variant="outline" className="border-zinc-500/30 text-zinc-400">Disabled</Badge>
                        : <Badge variant="outline" className="border-emerald-500/30 text-emerald-400">Active</Badge>}
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      {u.last_login_at ? new Date(u.last_login_at).toLocaleString() : '—'}
                    </td>
                    {isAdmin && (
                      <td className="px-4 py-3 text-right">
                        <div className="inline-flex gap-1">
                          <Button
                            size="sm" variant="ghost"
                            onClick={() => openEdit(u)}
                            data-testid={`user-edit-${u.email}`}
                          ><Pencil className="h-4 w-4" /></Button>
                          <Button
                            size="sm" variant="ghost"
                            onClick={() => { setResetUser(u); setRPassword(''); }}
                            data-testid={`user-reset-${u.email}`}
                          ><KeyIcon className="h-4 w-4" /></Button>
                          <Button
                            size="sm" variant="ghost"
                            disabled={isMe}
                            onClick={() => setConfirmDelete(u)}
                            data-testid={`user-delete-${u.email}`}
                          ><Trash2 className="h-4 w-4 text-rose-400" /></Button>
                        </div>
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {isAdmin && invites.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-sm font-semibold tracking-tight">Pending invites</h2>
          <div className="border border-border rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-card/60">
                <tr className="text-left text-xs uppercase tracking-wider text-muted-foreground">
                  <th className="px-4 py-3">Email</th>
                  <th className="px-4 py-3">Role</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Expires</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {invites.map((inv) => (
                  <tr key={inv.id} className="border-t border-border">
                    <td className="px-4 py-3">{inv.email}</td>
                    <td className="px-4 py-3"><RoleBadge role={inv.admin_role} /></td>
                    <td className="px-4 py-3">
                      <Badge variant="outline" className={
                        inv.status === 'pending' ? 'border-amber-500/30 text-amber-400' :
                        inv.status === 'accepted' ? 'border-emerald-500/30 text-emerald-400' :
                        'border-zinc-500/30 text-zinc-400'
                      }>{inv.status}</Badge>
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      {inv.expires_at ? new Date(inv.expires_at).toLocaleString() : '—'}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {inv.status === 'pending' && (
                        <Button size="sm" variant="ghost" onClick={() => revokeInvite(inv.id)}>
                          Revoke
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Create user dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add admin user</DialogTitle>
          </DialogHeader>
          <form onSubmit={create} className="space-y-3">
            <div>
              <Label htmlFor="c-email">Email</Label>
              <Input id="c-email" type="email" required value={cEmail} onChange={(e) => setCEmail(e.target.value)} data-testid="create-user-email" />
            </div>
            <div>
              <Label htmlFor="c-name">Name</Label>
              <Input id="c-name" required value={cName} onChange={(e) => setCName(e.target.value)} data-testid="create-user-name" />
            </div>
            <div>
              <Label>Role</Label>
              <Select value={cRole} onValueChange={setCRole}>
                <SelectTrigger data-testid="create-user-role"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="admin">Admin (full access)</SelectItem>
                  <SelectItem value="support">Support (read-only)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="c-pw">Initial password (min 8 chars)</Label>
              <Input id="c-pw" type="text" minLength={8} required value={cPassword} onChange={(e) => setCPassword(e.target.value)} data-testid="create-user-password" />
              <p className="text-xs text-muted-foreground mt-1">Share this with the user out of band. They can change it after signing in.</p>
            </div>
            <DialogFooter>
              <Button type="button" variant="ghost" onClick={() => setCreateOpen(false)}>Cancel</Button>
              <Button type="submit" data-testid="create-user-submit">Create user</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Invite dialog */}
      <Dialog open={inviteOpen} onOpenChange={(o) => { setInviteOpen(o); if (!o) setLastInvite(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Invite admin user by email</DialogTitle>
          </DialogHeader>
          {!lastInvite ? (
            <form onSubmit={invite} className="space-y-3">
              <div>
                <Label htmlFor="i-email">Email</Label>
                <Input id="i-email" type="email" required value={iEmail} onChange={(e) => setIEmail(e.target.value)} data-testid="invite-email" />
              </div>
              <div>
                <Label htmlFor="i-name">Name</Label>
                <Input id="i-name" required value={iName} onChange={(e) => setIName(e.target.value)} data-testid="invite-name" />
              </div>
              <div>
                <Label>Role</Label>
                <Select value={iRole} onValueChange={setIRole}>
                  <SelectTrigger data-testid="invite-role"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="admin">Admin (full access)</SelectItem>
                    <SelectItem value="support">Support (read-only)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <p className="text-xs text-muted-foreground">
                A one-time setup link (valid 72h) will be sent. Configure email under <b>Settings</b> first, or copy the link from the next screen.
              </p>
              <DialogFooter>
                <Button type="button" variant="ghost" onClick={() => setInviteOpen(false)}>Cancel</Button>
                <Button type="submit" data-testid="invite-submit">Send invite</Button>
              </DialogFooter>
            </form>
          ) : (
            <div className="space-y-3">
              <p className="text-sm">
                Invite created for <b>{lastInvite.email}</b>.{' '}
                {lastInvite.email_sent
                  ? <span className="text-emerald-400">Email sent via {lastInvite.email_provider}.</span>
                  : <span className="text-amber-400">Email delivery is not configured — copy this link to share manually:</span>}
              </p>
              <CopyChip text={lastInvite.invite_url || ''} />
              <p className="text-xs text-muted-foreground">
                Expires {new Date(lastInvite.expires_at).toLocaleString()}.
              </p>
              <DialogFooter>
                <Button onClick={() => { setInviteOpen(false); setLastInvite(null); }}>Done</Button>
              </DialogFooter>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Edit dialog */}
      <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit {editing?.email}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label htmlFor="e-name">Name</Label>
              <Input id="e-name" value={eName} onChange={(e) => setEName(e.target.value)} data-testid="edit-user-name" />
            </div>
            <div>
              <Label>Role</Label>
              <Select value={eRole} onValueChange={setERole} disabled={editing?.id === me?.id}>
                <SelectTrigger data-testid="edit-user-role"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="admin">Admin</SelectItem>
                  <SelectItem value="support">Support</SelectItem>
                </SelectContent>
              </Select>
              {editing?.id === me?.id && (
                <p className="text-xs text-muted-foreground mt-1">You cannot change your own role.</p>
              )}
            </div>
            <div className="flex items-center justify-between border border-border rounded-lg px-3 py-2">
              <div>
                <Label className="text-sm">Account enabled</Label>
                <p className="text-xs text-muted-foreground">Disabled users cannot sign in.</p>
              </div>
              <Switch
                checked={eActive}
                onCheckedChange={setEActive}
                disabled={editing?.id === me?.id}
                data-testid="edit-user-active"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setEditing(null)}>Cancel</Button>
            <Button onClick={saveEdit} data-testid="edit-user-save">Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reset password dialog */}
      <Dialog open={!!resetUser} onOpenChange={(o) => !o && setResetUser(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reset password for {resetUser?.email}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <Label htmlFor="r-pw">New password (min 8 chars)</Label>
            <Input id="r-pw" type="text" minLength={8} value={rPassword} onChange={(e) => setRPassword(e.target.value)} data-testid="reset-pw-input" />
            <p className="text-xs text-muted-foreground">Hand this to the user out of band. They should change it on next login.</p>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setResetUser(null)}>Cancel</Button>
            <Button onClick={doReset} disabled={rPassword.length < 8} data-testid="reset-pw-submit">Reset</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete confirm */}
      <AlertDialog open={!!confirmDelete} onOpenChange={(o) => !o && setConfirmDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {confirmDelete?.email}?</AlertDialogTitle>
            <AlertDialogDescription>
              This permanently removes the account. They will be logged out immediately. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={doDelete} data-testid="confirm-delete-user">Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
