export type UserRole = 'Viewer' | 'Member' | 'Lead' | 'Admin';

export interface TeamMembership {
  id: string;
  team_id: string;
  team_name: string;
  role: UserRole;
  created_at: string;
}

export interface UserProfile {
  id: string;
  name: string;
  email: string;
  is_active: boolean;
  created_at: string;
  memberships: TeamMembership[];
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export type WorkItemStatus =
  | 'OPEN'
  | 'IN_PROGRESS'
  | 'AWAITING_APPROVAL'
  | 'RESOLVED'
  | 'CLOSED';

export type WorkItemPriority = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export type WorkItemType = 'TASK' | 'BUG' | 'FEATURE' | 'IMPROVEMENT';

export interface WorkItem {
  id: string;
  team_id: string;
  title: string;
  description?: string | null;
  type: WorkItemType;
  priority: WorkItemPriority;
  status: WorkItemStatus;
  assignee_id?: string | null;
  created_by: string;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface WorkItemListResponse {
  items: WorkItem[];
  total: number;
  limit: number;
  offset: number;
  next_cursor?: string | null;
  has_more: boolean;
}

export interface WorkItemCreatePayload {
  team_id: string;
  title: string;
  description?: string;
  type?: WorkItemType;
  priority?: WorkItemPriority;
}

export interface WorkItemTransitionPayload {
  to_status: WorkItemStatus;
  version: number;
}

export interface ActivityEvent {
  id: string;
  work_item_id: string;
  actor_id: string;
  event_type: string;
  from_value?: string | null;
  to_value?: string | null;
  payload?: Record<string, any> | null;
  created_at: string;
}

export interface ActivityEventListResponse {
  items: ActivityEvent[];
  total: number;
}
