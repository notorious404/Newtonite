import React from 'react';
import { useAuth } from '../context/AuthContext';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { Shield, Users, LogOut, CheckCircle2, AlertCircle } from 'lucide-react';

export const Navbar: React.FC = () => {
  const { user, selectedTeam, setSelectedTeam, logout } = useAuth();

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: () => api.checkHealth(),
    refetchInterval: 15000,
  });

  const isHealthy = health?.status === 'ok' && health?.database === 'connected';

  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          {/* Brand */}
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-lg bg-slate-900 flex items-center justify-center text-white shadow-sm font-semibold tracking-wider">
              N
            </div>
            <div>
              <span className="font-bold text-slate-900 text-base tracking-tight">Newtonite</span>
              <span className="text-xs text-slate-500 block font-mono">Operations Under Pressure</span>
            </div>

            {/* Health Indicator */}
            <div className="ml-4 pl-4 border-l border-slate-200 flex items-center">
              <span
                className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                  isHealthy
                    ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                    : 'bg-rose-50 text-rose-700 border border-rose-200'
                }`}
                title={`Database: ${health?.database || 'disconnected'}`}
              >
                {isHealthy ? (
                  <CheckCircle2 className="w-3 h-3 mr-1 text-emerald-600" />
                ) : (
                  <AlertCircle className="w-3 h-3 mr-1 text-rose-600" />
                )}
                {isHealthy ? 'Live PG16' : 'Offline'}
              </span>
            </div>
          </div>

          {/* Center: Team Selector */}
          {user && user.memberships.length > 0 && (
            <div className="flex items-center space-x-2">
              <Users className="w-4 h-4 text-slate-400" />
              <label htmlFor="team-select" className="sr-only">Select Team</label>
              <select
                id="team-select"
                aria-label="Active Team"
                value={selectedTeam?.team_id || ''}
                onChange={(e) => {
                  const target = user.memberships.find((m) => m.team_id === e.target.value);
                  if (target) setSelectedTeam(target);
                }}
                className="bg-slate-50 border border-slate-300 text-slate-900 text-sm rounded-md focus:ring-slate-500 focus:border-slate-500 block p-1.5 font-medium"
              >
                {user.memberships.map((m) => (
                  <option key={m.id} value={m.team_id}>
                    {m.team_name} ({m.role})
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Right: User Profile & Logout */}
          <div className="flex items-center space-x-4">
            {user && (
              <div className="flex items-center space-x-3 text-right">
                <div>
                  <div className="text-sm font-semibold text-slate-800 leading-tight">{user.name}</div>
                  <div className="text-xs text-slate-500 flex items-center justify-end space-x-1">
                    <Shield className="w-3 h-3 text-slate-400" />
                    <span>{selectedTeam?.role || 'User'}</span>
                  </div>
                </div>
                <button
                  onClick={logout}
                  title="Sign out"
                  className="p-1.5 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-md transition-colors"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};
