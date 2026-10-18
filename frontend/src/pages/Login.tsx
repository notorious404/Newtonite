import React, { useState } from 'react';
import { useAuth, DEMO_USERS, type DemoUser } from '../context/AuthContext';
import { ApiError } from '../api/client';
import { Lock, Mail, AlertCircle, Loader2, ArrowRight, ShieldCheck } from 'lucide-react';

export const Login: React.FC = () => {
  const { login, isLoading } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleLogin = async (e?: React.FormEvent, customEmail?: string, customPass?: string) => {
    if (e) e.preventDefault();
    const loginEmail = customEmail || email;
    const loginPass = customPass || password;

    if (!loginEmail || !loginPass) {
      setError('Please provide email and password.');
      return;
    }

    setError(null);
    setSubmitting(true);
    try {
      await login(loginEmail, loginPass);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError('Login failed. Please verify credentials.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleQuickDemoLogin = (demo: DemoUser) => {
    setEmail(demo.email);
    setPassword(demo.password);
    handleLogin(undefined, demo.email, demo.password);
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        <div className="inline-flex w-12 h-12 rounded-xl bg-slate-900 items-center justify-center text-white shadow-md text-xl font-bold tracking-wider mb-3">
          N
        </div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Newtonite Dashboard</h1>
        <p className="mt-1 text-sm text-slate-500">
          Operations Under Pressure — High-Concurrency Control Console
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-4 shadow-sm border border-slate-200 sm:rounded-lg sm:px-10">
          {error && (
            <div className="mb-4 p-3 bg-rose-50 border border-rose-200 rounded-md text-rose-700 text-sm flex items-start space-x-2">
              <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <div>{error}</div>
            </div>
          )}

          {/* Quick Demo Switcher */}
          <div className="mb-6">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 block mb-2">
              Quick Login as Seeded Demo User
            </span>
            <div className="grid grid-cols-1 gap-1.5">
              {DEMO_USERS.map((demo) => (
                <button
                  key={demo.email}
                  type="button"
                  onClick={() => handleQuickDemoLogin(demo)}
                  disabled={submitting || isLoading}
                  className="w-full text-left px-3 py-2 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded text-xs flex justify-between items-center transition-colors group"
                >
                  <div>
                    <span className="font-semibold text-slate-800">{demo.name}</span>
                    <span className="text-slate-500 block text-[11px]">{demo.roleDescription}</span>
                  </div>
                  <ArrowRight className="w-3.5 h-3.5 text-slate-400 group-hover:text-slate-700 transition-colors" />
                </button>
              ))}
            </div>
          </div>

          <div className="relative mb-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-slate-200" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-white px-2 text-slate-400 font-mono">Or manual credentials</span>
            </div>
          </div>

          <form className="space-y-4" onSubmit={handleLogin}>
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                Email Address
              </label>
              <div className="relative">
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  placeholder="engineer@newtonite.io"
                  className="w-full bg-white border border-slate-300 rounded-md py-2 pl-9 pr-3 text-sm text-slate-900 focus:ring-slate-500 focus:border-slate-500"
                />
                <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                Password
              </label>
              <div className="relative">
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  placeholder="••••••••"
                  className="w-full bg-white border border-slate-300 rounded-md py-2 pl-9 pr-3 text-sm text-slate-900 focus:ring-slate-500 focus:border-slate-500"
                />
                <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
              </div>
            </div>

            <button
              type="submit"
              disabled={submitting || isLoading}
              className="w-full flex justify-center items-center py-2 px-4 border border-transparent rounded-md shadow-xs text-sm font-medium text-white bg-slate-900 hover:bg-slate-800 focus:outline-none disabled:opacity-50 transition-colors"
            >
              {submitting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Authenticating...
                </>
              ) : (
                'Sign In'
              )}
            </button>
          </form>

          <div className="mt-6 pt-4 border-t border-slate-100 flex items-center justify-center text-xs text-slate-400 space-x-1">
            <ShieldCheck className="w-3.5 h-3.5 text-slate-400" />
            <span>Secure JWT Bearer Session</span>
          </div>
        </div>
      </div>
    </div>
  );
};
