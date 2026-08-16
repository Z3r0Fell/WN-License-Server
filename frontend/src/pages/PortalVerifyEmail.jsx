import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { ListChecks } from 'lucide-react';
import { customerApi } from '../lib/api';
import { toast } from 'sonner';

export default function PortalVerifyEmail() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';
  const [status, setStatus] = useState('verifying'); // verifying | done | error

  useEffect(() => {
    if (!token) { setStatus('error'); return; }
    customerApi.post('/customer/verify-email', { token })
      .then(() => { setStatus('done'); toast.success('Email verified'); })
      .catch((e) => { setStatus('error'); toast.error(e?.response?.data?.detail || 'Verification failed'); });
  }, [token]);

  return (
    <div className="dark min-h-screen bg-background text-foreground flex items-center justify-center p-6 bg-emerald-wash">
      <div className="w-full max-w-sm bg-card border border-border rounded-2xl p-7 text-center">
        <Link to="/" className="inline-flex items-center gap-2 mb-4">
          <div className="h-8 w-8 rounded-lg bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center">
            <ListChecks className="h-4 w-4 text-emerald-400" />
          </div>
          <span className="font-semibold">WatchNexus Portal</span>
        </Link>
        {status === 'verifying' && <p className="text-sm text-muted-foreground">Verifying your email…</p>}
        {status === 'done' && (
          <>
            <h1 className="text-xl font-semibold tracking-tight">Email verified</h1>
            <p className="text-sm text-muted-foreground mt-1">You can now sign in to your portal.</p>
            <Link to="/portal/login"><Button className="w-full mt-6 bg-emerald-600 hover:bg-emerald-500 text-white">Sign in</Button></Link>
          </>
        )}
        {status === 'error' && (
          <>
            <h1 className="text-xl font-semibold tracking-tight">Verification failed</h1>
            <p className="text-sm text-muted-foreground mt-1">The link is invalid or expired.</p>
            <Link to="/portal/login"><Button className="w-full mt-6 bg-emerald-600 hover:bg-emerald-500 text-white">Go to sign in</Button></Link>
          </>
        )}
      </div>
    </div>
  );
}
