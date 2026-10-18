import React, { createContext, useContext, useState, useEffect } from 'react';
import type { UserProfile, TeamMembership } from '../types';
import { api } from '../api/client';

export interface DemoUser {
  name: string;
  email: string;
  roleDescription: string;
  defaultTeam: string;
  password: string;
}

export const DEMO_USERS: DemoUser[] = [
  {
    name: 'Alice Admin',
    email: 'admin@newtonite.io',
    roleDescription: 'Admin (Team Alpha & Beta)',
    defaultTeam: 'Team Alpha',
    password: 'Password123!',
  },
  {
    name: 'Bob Lead',
    email: 'lead@newtonite.io',
    roleDescription: 'Lead (Team Alpha)',
    defaultTeam: 'Team Alpha',
    password: 'Password123!',
  },
  {
    name: 'Charlie Engineer',
    email: 'engineer@newtonite.io',
    roleDescription: 'Member (Team Alpha)',
    defaultTeam: 'Team Alpha',
    password: 'Password123!',
  },
  {
    name: 'Dana Viewer',
    email: 'viewer@newtonite.io',
    roleDescription: 'Viewer (Team Alpha)',
    defaultTeam: 'Team Alpha',
    password: 'Password123!',
  },
  {
    name: 'Oscar Outsider',
    email: 'outsider@newtonite.io',
    roleDescription: 'Member (Team Beta only)',
    defaultTeam: 'Team Beta',
    password: 'Password123!',
  },
];

interface AuthContextType {
  user: UserProfile | null;
  token: string | null;
  isLoading: boolean;
  selectedTeam: TeamMembership | null;
  setSelectedTeam: (team: TeamMembership | null) => void;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [token, setToken] = useState<string | null>(sessionStorage.getItem('access_token'));
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [selectedTeam, setSelectedTeam] = useState<TeamMembership | null>(null);

  const fetchProfile = async () => {
    try {
      const profile = await api.getMe();
      setUser(profile);
      if (profile.memberships.length > 0) {
        setSelectedTeam((prev) => {
          if (prev && profile.memberships.some((m) => m.team_id === prev.team_id)) {
            return prev;
          }
          return profile.memberships[0];
        });
      } else {
        setSelectedTeam(null);
      }
    } catch {
      sessionStorage.removeItem('access_token');
      setToken(null);
      setUser(null);
      setSelectedTeam(null);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (token) {
      fetchProfile();
    } else {
      setIsLoading(false);
    }
  }, [token]);

  const login = async (email: string, password: string) => {
    setIsLoading(true);
    try {
      const resp = await api.login(email, password);
      sessionStorage.setItem('access_token', resp.access_token);
      setToken(resp.access_token);
      const profile = await api.getMe();
      setUser(profile);
      if (profile.memberships.length > 0) {
        setSelectedTeam(profile.memberships[0]);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    sessionStorage.removeItem('access_token');
    setToken(null);
    setUser(null);
    setSelectedTeam(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        selectedTeam,
        setSelectedTeam,
        login,
        logout,
        refreshUser: fetchProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
