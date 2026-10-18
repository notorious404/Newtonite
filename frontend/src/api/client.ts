import type {
  TokenResponse,
  UserProfile,
  TeamMembership,
  WorkItem,
  WorkItemListResponse,
  WorkItemCreatePayload,
  WorkItemTransitionPayload,
  ActivityEventListResponse,
} from '../types';

export const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
export const ROOT_URL = API_BASE.replace('/api/v1', '');

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = sessionStorage.getItem('access_token');
  const headers = new Headers(options.headers || {});

  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`;

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const errorJson = await response.json();
      if (typeof errorJson.detail === 'string') {
        detail = errorJson.detail;
      } else if (Array.isArray(errorJson.detail)) {
        // FastAPI validation errors (422)
        detail = errorJson.detail.map((err: any) => `${err.loc?.join('.') || 'field'}: ${err.msg}`).join(', ');
      }
    } catch {
      // response wasn't JSON
    }

    if (response.status === 401) {
      sessionStorage.removeItem('access_token');
    }

    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

export const api = {
  // Health
  checkHealth: async () => {
    return request<{ status: string; database: string }>(`${ROOT_URL}/health`);
  },

  // Auth
  login: async (email: string, password: string): Promise<TokenResponse> => {
    return request<TokenResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
  },

  getMe: async (): Promise<UserProfile> => {
    return request<UserProfile>('/auth/me');
  },

  listTeams: async (): Promise<TeamMembership[]> => {
    return request<TeamMembership[]>('/teams');
  },

  // Work Items
  listWorkItems: async (params: {
    team_id?: string;
    status?: string;
    priority?: string;
    q?: string;
    cursor?: string;
    limit?: number;
    offset?: number;
  }): Promise<WorkItemListResponse> => {
    const query = new URLSearchParams();
    if (params.team_id) query.set('team_id', params.team_id);
    if (params.status) query.set('status', params.status);
    if (params.priority) query.set('priority', params.priority);
    if (params.q) query.set('q', params.q);
    if (params.cursor) query.set('cursor', params.cursor);
    if (params.limit !== undefined) query.set('limit', String(params.limit));
    if (params.offset !== undefined) query.set('offset', String(params.offset));

    return request<WorkItemListResponse>(`/work-items?${query.toString()}`);
  },

  getWorkItem: async (id: string): Promise<WorkItem> => {
    return request<WorkItem>(`/work-items/${id}`);
  },

  createWorkItem: async (
    payload: WorkItemCreatePayload,
    idempotencyKey?: string
  ): Promise<WorkItem> => {
    const headers: Record<string, string> = {};
    if (idempotencyKey) {
      headers['Idempotency-Key'] = idempotencyKey;
    }
    return request<WorkItem>('/work-items', {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    });
  },

  claimWorkItem: async (id: string): Promise<WorkItem> => {
    return request<WorkItem>(`/work-items/${id}/claim`, {
      method: 'POST',
    });
  },

  transitionWorkItem: async (
    id: string,
    payload: WorkItemTransitionPayload
  ): Promise<WorkItem> => {
    return request<WorkItem>(`/work-items/${id}/transition`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  getWorkItemActivity: async (id: string): Promise<ActivityEventListResponse> => {
    return request<ActivityEventListResponse>(`/work-items/${id}/activity`);
  },
};
