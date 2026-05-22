import { useEffect, useMemo, useState } from 'react';
import { adminApi } from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Skeleton } from '../components/ui/skeleton';
import {
  Tabs, TabsContent, TabsList, TabsTrigger,
} from '../components/ui/tabs';
import { toast } from 'sonner';
import {
  Save, Mail, Webhook, Globe2, Eye, EyeOff, AlertTriangle, MailCheck, Database, Cog,
} from 'lucide-react';

const CATEGORY_META = {
  webhooks: { icon: Webhook, label: 'Webhooks',
              description: 'Signing secrets for each payment processor. Paste the values from each provider\u2019s dashboard.' },
  email:    { icon: Mail,    label: 'Email',
              description: 'Set SendGrid (HTTP API) OR an SMTP block. SendGrid takes priority when both are filled.' },
  branding: { icon: Globe2,  label: 'Branding & URLs',
              description: 'Public URLs and brand name used in customer-facing emails and links.' },
};

function SourceTag({ source }) {
  if (source === 'db') return <span className="text-[10px] uppercase tracking-wider text-emerald-300 bg-emerald-500/10 border border-emerald-500/20 rounded px-1.5 py-0.5">Saved</span>;
  if (source === 'env') return <span className="text-[10px] uppercase tracking-wider text-sky-300 bg-sky-500/10 border border-sky-500/20 rounded px-1.5 py-0.5">From .env</span>;
  return <span className="text-[10px] uppercase tracking-wider text-muted-foreground bg-muted/30 border border-border rounded px-1.5 py-0.5">Unset</span>;
}

function SecretField({ name, meta, value, onChange, dirty }) {
  const [show, setShow] = useState(false);
  return (
    <div data-testid={`setting-field-${name}`}>
      <div className="flex items-center justify-between mb-1">
        <Label htmlFor={name} className="text-sm">{meta.label}</Label>
        <SourceTag source={meta.source} />
      </div>
      <div className="relative">
        <Input
          id={name}
          type={show ? 'text' : 'password'}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={meta.has_value && !dirty ? meta.masked : 'Leave blank to keep current value'}
          className="font-mono text-xs pr-9"
          data-testid={`setting-input-${name}`}
          autoComplete="off"
        />
        <button
          type="button"
          aria-label={show ? 'Hide' : 'Show'}
          onClick={() => setShow((s) => !s)}
          className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
          tabIndex={-1}
        >
          {show ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
        </button>
      </div>
      {meta.help && <p className="text-[11px] text-muted-foreground mt-1">{meta.help}</p>}
    </div>
  );
}

function TextField({ name, meta, value, onChange }) {
  return (
    <div data-testid={`setting-field-${name}`}>
      <div className="flex items-center justify-between mb-1">
        <Label htmlFor={name} className="text-sm">{meta.label}</Label>
        <SourceTag source={meta.source} />
      </div>
      <Input
        id={name}
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={meta.help.includes('e.g.') ? meta.help.split('e.g.')[1].trim() : ''}
        data-testid={`setting-input-${name}`}
        autoComplete="off"
      />
      {meta.help && <p className="text-[11px] text-muted-foreground mt-1">{meta.help}</p>}
    </div>
  );
}

export default function AdminSettings() {
  const [meta, setMeta] = useState(null);     // server side current state
  const [edits, setEdits] = useState({});     // user-modified values
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testEmailTo, setTestEmailTo] = useState('');

  const load = async () => {
    setLoading(true);
    try {
      const r = await adminApi.get('/admin/settings');
      setMeta(r.data);
      setEdits({});
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, []);

  const onChange = (name) => (val) => setEdits((e) => ({ ...e, [name]: val }));

  const dirty = useMemo(() => Object.keys(edits).length > 0, [edits]);

  const save = async () => {
    if (!dirty) return;
    setSaving(true);
    try {
      const r = await adminApi.put('/admin/settings', { values: edits });
      setMeta(r.data);
      setEdits({});
      toast.success(`Saved ${Object.keys(edits).length} setting(s)`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const sendTestEmail = async () => {
    if (!testEmailTo) { toast.error('Enter a recipient email'); return; }
    try {
      const r = await adminApi.post('/admin/settings/test-email', { to: testEmailTo });
      if (r.data.sent) toast.success(`Test email sent via ${r.data.provider}`);
      else toast.warning(r.data.provider === 'log'
        ? 'Email provider not configured (log-only mode). Add SendGrid or SMTP creds below first.'
        : `Email not sent: ${r.data.error || r.data.reason || 'unknown'}`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Test failed');
    }
  };

  if (loading) {
    return <div className="space-y-3">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-12 rounded-lg" />)}</div>;
  }
  if (!meta) return null;

  // Group by category preserving the order in the server response
  const grouped = {};
  for (const [k, v] of Object.entries(meta)) {
    (grouped[v.category] ||= []).push({ key: k, ...v });
  }

  const renderField = (name, m) => {
    const userValue = edits[name] !== undefined ? edits[name] : (m.secret ? '' : (m.value || ''));
    const dirty = edits[name] !== undefined;
    return m.secret
      ? <SecretField key={name} name={name} meta={m} value={userValue} onChange={onChange(name)} dirty={dirty} />
      : <TextField   key={name} name={name} meta={m} value={userValue} onChange={onChange(name)} />;
  };

  return (
    <div>
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Configure webhook secrets, email provider and public URLs.
            Saved values override <code className="font-mono">.env</code> immediately\u2014no restart needed.
          </p>
        </div>
        <Button
          onClick={save}
          disabled={!dirty || saving}
          className="bg-emerald-600 hover:bg-emerald-500 text-white"
          data-testid="settings-save-button"
        >
          <Save className="h-4 w-4 mr-1.5" />
          {saving ? 'Saving\u2026' : dirty ? `Save ${Object.keys(edits).length} change${Object.keys(edits).length === 1 ? '' : 's'}` : 'Saved'}
        </Button>
      </div>

      <div className="mt-4 flex items-start gap-2 rounded-lg border border-sky-500/20 bg-sky-500/5 p-3 text-xs text-sky-100" data-testid="settings-source-explainer">
        <Database className="h-4 w-4 shrink-0 mt-0.5 text-sky-300" />
        <div>
          Secrets are stored in MongoDB and take precedence over the matching <code className="font-mono">.env</code> variable on the server. Leave a secret field blank to keep the current value; type a new value (or a single space then clear) to overwrite.
        </div>
      </div>

      <Tabs defaultValue="webhooks" className="mt-6">
        <TabsList>
          {Object.entries(CATEGORY_META).map(([cat, m]) => {
            const Icon = m.icon;
            return (
              <TabsTrigger key={cat} value={cat} data-testid={`settings-tab-${cat}`}>
                <Icon className="h-3.5 w-3.5 mr-1.5" />
                {m.label}
              </TabsTrigger>
            );
          })}
        </TabsList>

        {Object.entries(CATEGORY_META).map(([cat, m]) => (
          <TabsContent key={cat} value={cat} className="mt-4">
            <p className="text-sm text-muted-foreground mb-4">{m.description}</p>
            <div className="rounded-xl border border-border bg-card p-5 space-y-5" data-testid={`settings-panel-${cat}`}>
              {(grouped[cat] || []).map((row) => renderField(row.key, row))}
              {cat === 'email' && (
                <div className="pt-3 mt-2 border-t border-border">
                  <div className="flex items-end gap-2 flex-wrap">
                    <div className="flex-1 min-w-[260px]">
                      <Label htmlFor="test-email-to">Send a test email to</Label>
                      <Input
                        id="test-email-to"
                        type="email"
                        value={testEmailTo}
                        onChange={(e) => setTestEmailTo(e.target.value)}
                        placeholder="you@example.com"
                        data-testid="settings-test-email-to-input"
                      />
                    </div>
                    <Button
                      variant="secondary"
                      onClick={sendTestEmail}
                      data-testid="settings-test-email-button"
                    >
                      <MailCheck className="h-4 w-4 mr-1.5" /> Send test email
                    </Button>
                  </div>
                  <p className="text-[11px] text-muted-foreground mt-2">
                    Uses the currently saved provider (SendGrid HTTP API if SENDGRID_API_KEY is set, otherwise SMTP). Save your changes first if you just edited them.
                  </p>
                </div>
              )}
              {cat === 'branding' && (
                <div className="pt-3 mt-2 border-t border-border flex items-start gap-2 rounded-lg bg-amber-500/5 border border-amber-500/20 p-3 text-xs text-amber-100">
                  <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5 text-amber-300" />
                  <div>
                    <div className="font-semibold mb-1">DNS reminder</div>
                    The hostnames you set here only work if their DNS A-records point at this server.
                    The customer portal URL is used in purchase emails and the landing-page \u201CCustomer portal\u201D link.
                  </div>
                </div>
              )}
            </div>
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
