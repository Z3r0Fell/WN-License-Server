import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  ArrowLeft, ArrowRight, BadgeCheck, ListChecks, Lock, Mail, Copy, ExternalLink,
  CreditCard, Loader2, RefreshCw, Search, ShieldCheck,
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { publicApi } from '../lib/api';

const PLAN_META = {
  pro: {
    name: 'WatchNexus Pro',
    tagline: 'Everything in Standard, plus Pro modules',
    features: ['49 modules total', 'Indexer search & movie automation', 'Live TV / IPTV with DVR', 'Watch analytics & AI recommendations'],
  },
  ultra: {
    name: 'WatchNexus Ultra',
    tagline: 'Everything unlocked',
    features: ['73 modules total', 'GPU hardware transcoding', 'Disc ripping & media sync', 'Security suite & Matrix'],
  },
};

function fmtPrice(n) {
  return `$${Number(n || 0).toFixed(2)}`;
}

function CheckoutPlanCard({ plan, selected, onClick, price }) {
  const meta = PLAN_META[plan] || { name: plan, features: [] };
  return (
    <button
      type="button"
      onClick={onClick}
      data-testid={`checkout-plan-${plan}`}
      className={[
        'w-full text-left rounded-xl border p-5 transition-colors',
        selected
          ? 'border-emerald-500/60 bg-emerald-500/10 ring-1 ring-emerald-500/30'
          : 'border-border bg-card/50 hover:border-emerald-500/30',
      ].join(' ')}
    >
      <div className="flex items-center justify-between">
        <div>
          <div className="font-semibold">{meta.name}</div>
          <div className="text-xs text-muted-foreground mt-0.5">{meta.tagline}</div>
        </div>
        {selected && <BadgeCheck className="h-5 w-5 text-emerald-400" />}
      </div>
      <ul className="mt-3 space-y-1">
        {meta.features.map((f) => (
          <li key={f} className="text-xs text-muted-foreground flex items-center gap-1.5">
            <span className="h-1 w-1 rounded-full bg-emerald-400 shrink-0" /> {f}
          </li>
        ))}
      </ul>
      <div className="mt-3 text-xs text-muted-foreground">
        {price
          ? (<><span className="text-lg font-semibold text-foreground">CAD {price}</span><span className="mx-1">/</span> one-time</>)
          : 'Loading price…'}
      </div>
    </button>
  );
}

export default function Checkout() {
  const [params, setParams] = useSearchParams();
  const planParam = (params.get('plan') || '').toLowerCase();
  const [catalog, setCatalog] = useState({ plans: [], payment_email: '', payment_methods: '' });
  const [selected, setSelected] = useState(planParam === 'pro' || planParam === 'ultra' ? planParam : null);
  const [email, setEmail] = useState('');
  const [buyerName, setBuyerName] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [order, setOrder] = useState(null);
  const [lookupRef, setLookupRef] = useState('');
  const [lookup, setLookup] = useState(null);
  const [lookupLoading, setLookupLoading] = useState(false);

  useEffect(() => {
    publicApi.get('/orders/plans')
      .then((r) => setCatalog(r.data))
      .catch(() => setCatalog({ plans: [], payment_email: '', payment_methods: '' }));
  }, []);

  useEffect(() => {
    if (planParam === 'pro' || planParam === 'ultra') setSelected(planParam);
  }, [planParam]);

  const priceFor = useMemo(() => {
    const p = (catalog.plans || []).find((x) => x.plan === selected);
    return p ? fmtPrice(p.price_cad) : '';
  }, [catalog, selected]);

  const priceByPlan = useMemo(() => {
    const map = {};
    (catalog.plans || []).forEach((p) => { map[p.plan] = fmtPrice(p.price_cad); });
    return map;
  }, [catalog]);

  const selectPlan = (plan) => {
    setSelected(plan);
    setError('');
    setParams({ plan }, { replace: true });
  };

  const placeOrder = async () => {
    if (!selected) { setError('Pick a plan first.'); return; }
    if (!email.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setError('Enter a valid email address — your serial will be sent there.');
      return;
    }
    setError('');
    setSubmitting(true);
    try {
      const r = await publicApi.post('/orders', { plan: selected, email: email.trim(), buyer_name: buyerName.trim() || null });
      setOrder(r.data);
      setLookup(null);
    } catch (e) {
      setError(e?.response?.data?.detail || 'Could not place your order. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const doLookup = async () => {
    const ref = lookupRef.trim();
    if (!ref) return;
    setLookupLoading(true);
    setLookup(null);
    try {
      const r = await publicApi.get(`/orders/${encodeURIComponent(ref)}`);
      setLookup(r.data);
    } catch {
      setLookup({ status: 'not_found', reference: ref });
    } finally {
      setLookupLoading(false);
    }
  };

  const statusLabel = (s) => {
    const map = {
      pending_payment: ['Pending payment', 'bg-amber-500/10 text-amber-400 border-amber-500/30'],
      paid: ['Paid — serial issued', 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'],
      canceled: ['Canceled', 'bg-slate-500/10 text-slate-400 border-slate-500/30'],
      not_found: ['Not found', 'bg-red-500/10 text-red-400 border-red-500/30'],
    };
    return map[s] || [s, 'bg-muted/30 text-muted-foreground border-border'];
  };

  return (
    <div className="dark min-h-screen bg-background text-foreground">
      <header className="border-b border-border/60 bg-background/60 backdrop-blur sticky top-0 z-30">
        <div className="max-w-3xl mx-auto px-6 h-14 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2">
            <div className="h-7 w-7 rounded-lg bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center">
              <ListChecks className="h-3.5 w-3.5 text-emerald-400" />
            </div>
            <span className="text-sm font-semibold tracking-tight">WatchNexus</span>
          </Link>
          <nav className="flex items-center gap-1">
            <Link to="/admin/login" className="text-sm text-muted-foreground hover:text-foreground px-3 py-1.5 rounded-lg hover:bg-muted/40 transition-colors">Admin</Link>
          </nav>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-12">
        {!order ? (
          <>
            <div className="mb-8">
              <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight">Purchase a WatchNexus license</h1>
              <p className="mt-2 text-muted-foreground text-sm">
                One-time payment, lifetime access. Your serial is emailed to you once payment is confirmed.
              </p>
            </div>

            <div className="grid sm:grid-cols-2 gap-4">
              <CheckoutPlanCard plan="pro" selected={selected === 'pro'} onClick={() => selectPlan('pro')} price={priceByPlan.pro} />
              <CheckoutPlanCard plan="ultra" selected={selected === 'ultra'} onClick={() => selectPlan('ultra')} price={priceByPlan.ultra} />
            </div>

            <Card className="mt-8" data-testid="checkout-details-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-2"><Mail className="h-4 w-4" /> Where should we send your serial?</CardTitle>
                <CardDescription>Your license key will be emailed to this address after payment is confirmed.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label htmlFor="checkout-email" className="text-xs">Email address</Label>
                  <Input id="checkout-email" type="email" placeholder="you@example.com"
                    value={email} onChange={(e) => setEmail(e.target.value)}
                    className="mt-1" data-testid="checkout-email" />
                </div>
                <div>
                  <Label htmlFor="checkout-name" className="text-xs">Name <span className="text-muted-foreground font-normal">(optional)</span></Label>
                  <Input id="checkout-name" placeholder="Jane Doe"
                    value={buyerName} onChange={(e) => setBuyerName(e.target.value)}
                    className="mt-1" data-testid="checkout-name" />
                </div>

                <div className="rounded-lg border border-border bg-muted/20 p-4 flex items-center justify-between">
                  <div>
                    <div className="text-xs text-muted-foreground">Order total</div>
                    <div className="text-lg font-semibold">{selected ? `${PLAN_META[selected].name}` : 'Select a plan'}</div>
                  </div>
                  <div className="text-2xl font-semibold tracking-tight">{priceFor ? `CAD ${priceFor}` : '—'}</div>
                </div>

                {error && (
                  <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300" data-testid="checkout-error">
                    {error}
                  </div>
                )}

                <Button className="w-full bg-emerald-600 hover:bg-emerald-500 text-white"
                  onClick={placeOrder} disabled={submitting || !selected}
                  data-testid="checkout-place-order">
                  {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <CreditCard className="h-4 w-4" />}
                  Place order
                </Button>
                <p className="text-[11px] text-muted-foreground flex items-center justify-center gap-1">
                  <Lock className="h-3 w-3" /> No payment card required — you'll pay directly by e-transfer or PayPal.
                </p>
              </CardContent>
            </Card>
          </>
        ) : (
          <Card className="border-emerald-500/30" data-testid="checkout-confirmation">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-emerald-400">
                <BadgeCheck className="h-5 w-5" /> Order received
              </CardTitle>
              <CardDescription>
                Keep your order reference handy — include it with your payment so we can match it up.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-lg border border-border bg-muted/20 p-3">
                  <div className="text-[11px] text-muted-foreground uppercase tracking-wider">Plan</div>
                  <div className="font-semibold mt-0.5">{order.plan_name}</div>
                </div>
                <div className="rounded-lg border border-border bg-muted/20 p-3">
                  <div className="text-[11px] text-muted-foreground uppercase tracking-wider">Amount</div>
                  <div className="font-semibold mt-0.5">CAD {fmtPrice(order.price_cad)}</div>
                </div>
                <div className="rounded-lg border border-border bg-muted/20 p-3">
                  <div className="text-[11px] text-muted-foreground uppercase tracking-wider">Order reference</div>
                  <button
                    type="button"
                    className="font-mono text-emerald-300 mt-0.5 flex items-center gap-1.5 hover:underline"
                    onClick={() => navigator.clipboard?.writeText(order.reference)}
                    data-testid="checkout-reference-copy"
                  >
                    {order.reference} <Copy className="h-3 w-3" />
                  </button>
                </div>
                <div className="rounded-lg border border-border bg-muted/20 p-3">
                  <div className="text-[11px] text-muted-foreground uppercase tracking-wider">Serial sent to</div>
                  <div className="font-semibold mt-0.5 truncate">{order.email}</div>
                </div>
              </div>

              <div className="rounded-xl border border-amber-500/25 bg-amber-500/5 p-4">
                <div className="flex items-center gap-2 text-sm font-semibold">
                  <CreditCard className="h-4 w-4 text-amber-400" /> How to pay
                </div>
                <p className="mt-2 text-sm">
                  Send <b>CAD {fmtPrice(order.price_cad)}</b> to{' '}
                  <a href={`mailto:${order.payment_email}`} className="text-emerald-300 hover:underline font-medium">{order.payment_email}</a>{' '}
                  via {order.payment_methods || 'e-transfer or PayPal'}.
                </p>
                {order.payment_instructions && (
                  <p className="mt-2 text-xs text-muted-foreground">{order.payment_instructions}</p>
                )}
                <div className="mt-3 rounded-lg bg-background/60 border border-border px-3 py-2 text-xs text-muted-foreground flex items-center gap-2">
                  <span className="text-amber-400 shrink-0"><ShieldCheck className="h-3.5 w-3.5" /></span>
                  Include your reference <span className="font-mono text-foreground">{order.reference}</span> in the payment message.
                </div>
              </div>

              <div className="rounded-lg border border-border bg-muted/10 p-3 flex flex-col sm:flex-row sm:items-center gap-2">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                  <Input placeholder="Check order status — enter your reference" className="pl-8 font-mono text-xs"
                    value={lookupRef} onChange={(e) => setLookupRef(e.target.value)} />
                </div>
                <Button variant="secondary" size="sm" onClick={doLookup} disabled={lookupLoading}>
                  {lookupLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                  Check
                </Button>
              </div>

              {lookup && (
                <div className="rounded-lg border border-border bg-muted/20 p-3 text-xs" data-testid="checkout-lookup-result">
                  <div className="flex items-center gap-2">
                    <span className="font-mono">{lookup.reference}</span>
                    <span className={`rounded-full border px-2 py-0.5 text-[10px] ${statusLabel(lookup.status)[1]}`}>
                      {statusLabel(lookup.status)[0]}
                    </span>
                  </div>
                  {lookup.status === 'paid' && lookup.license_key && (
                    <div className="mt-2 flex items-center gap-2">
                      <span className="text-muted-foreground">Your serial:</span>
                      <code className="font-mono text-emerald-300 text-xs">{lookup.license_key}</code>
                    </div>
                  )}
                  {lookup.status === 'pending_payment' && (
                    <p className="mt-2 text-muted-foreground">We're waiting for payment confirmation. It usually arrives within a few hours of your transfer.</p>
                  )}
                </div>
              )}

              <div className="flex items-center justify-between">
                <Button variant="secondary" size="sm" onClick={() => { setOrder(null); setLookup(null); setLookupRef(''); }}>
                  <ArrowLeft className="h-3.5 w-3.5 mr-1" /> Place another order
                </Button>
                <a href="https://watchnexus.ca" className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1">
                  Back to watchnexus.ca <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}
