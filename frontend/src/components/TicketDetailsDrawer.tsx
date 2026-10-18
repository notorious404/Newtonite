import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from '../api/client';
import type { WorkItemStatus, ActivityEvent } from '../types';
import { StatusBadge, PriorityBadge, TypeBadge } from './StatusBadge';
import { ConflictModal } from './ConflictModal';
import {
  X,
  UserCheck,
  ArrowRight,
  Clock,
  History,
  ShieldAlert,
  Loader2,
  AlertCircle,
} from 'lucide-react';

interface TicketDetailsDrawerProps {
  itemId: string | null;
  onClose: () => void;
}

export const TicketDetailsDrawer: React.FC<TicketDetailsDrawerProps> = ({ itemId, onClose }) => {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const [conflictMessage, setConflictMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // 1. Fetch live WorkItem details
  const {
    data: item,
    isLoading: isItemLoading,
    refetch: refetchItem,
  } = useQuery({
    queryKey: ['work-item', itemId],
    queryFn: () => (itemId ? api.getWorkItem(itemId) : Promise.reject('No ID')),
    enabled: !!itemId,
  });

  // 2. Fetch full chronological activity log
  const {
    data: activityData,
    isLoading: isActivityLoading,
    refetch: refetchActivity,
  } = useQuery({
    queryKey: ['work-item-activity', itemId],
    queryFn: () => (itemId ? api.getWorkItemActivity(itemId) : Promise.reject('No ID')),
    enabled: !!itemId,
  });

  const reloadAll = () => {
    refetchItem();
    refetchActivity();
    queryClient.invalidateQueries({ queryKey: ['work-items'] });
    setConflictMessage(null);
    setActionError(null);
  };

  // 3. Claim mutation
  const claimMutation = useMutation({
    mutationFn: () => api.claimWorkItem(item!.id),
    onSuccess: () => {
      reloadAll();
    },
    onError: (err: any) => {
      if (err instanceof ApiError && err.status === 409) {
        setConflictMessage(err.detail);
      } else if (err instanceof ApiError) {
        setActionError(err.detail);
      } else {
        setActionError('Failed to claim ticket');
      }
    },
  });

  // 4. Transition mutation (optimistic locking)
  const transitionMutation = useMutation({
    mutationFn: (targetStatus: WorkItemStatus) =>
      api.transitionWorkItem(item!.id, {
        to_status: targetStatus,
        version: item!.version, // client provides cached version
      }),
    onSuccess: () => {
      reloadAll();
    },
    onError: (err: any) => {
      if (err instanceof ApiError && err.status === 409) {
        setConflictMessage(err.detail);
      } else if (err instanceof ApiError) {
        setActionError(err.detail);
      } else {
        setActionError('Failed to transition ticket');
      }
    },
  });

  if (!itemId) return null;

  // Determine authorized role in this item's team
  const currentTeamMembership = user?.memberships.find((m) => m.team_id === item?.team_id);
  const userRole = currentTeamMembership?.role || 'Viewer';
  const isViewer = userRole === 'Viewer';
  const isLeadOrAdmin = userRole === 'Lead' || userRole === 'Admin';
  const isCreator = user?.id === item?.created_by;

  // Allowed transitions according to workflow_service.py:
  // OPEN -> IN_PROGRESS
  // IN_PROGRESS -> AWAITING_APPROVAL
  // AWAITING_APPROVAL -> RESOLVED (Approval: Lead/Admin, separation of duties: not creator)
  // AWAITING_APPROVAL -> IN_PROGRESS (Rejection)
  // RESOLVED -> CLOSED
  // RESOLVED -> IN_PROGRESS (Reopen)
  const getAvailableTransitions = (): { status: WorkItemStatus; label: string; disabled?: boolean; reason?: string }[] => {
    if (!item) return [];
    if (isViewer) return [];

    switch (item.status) {
      case 'OPEN':
        return [{ status: 'IN_PROGRESS', label: 'Start Progress' }];
      case 'IN_PROGRESS':
        return [{ status: 'AWAITING_APPROVAL', label: 'Submit for Approval' }];
      case 'AWAITING_APPROVAL': {
        const approvalDisabled = !isLeadOrAdmin || isCreator;
        let approvalReason = undefined;
        if (!isLeadOrAdmin) approvalReason = 'Only a Lead or Admin may approve work items';
        if (isCreator) approvalReason = 'Separation of duties: You cannot approve a ticket you created';

        return [
          {
            status: 'RESOLVED',
            label: 'Approve & Resolve',
            disabled: approvalDisabled,
            reason: approvalReason,
          },
          { status: 'IN_PROGRESS', label: 'Reject back to Progress' },
        ];
      }
      case 'RESOLVED':
        return [
          { status: 'CLOSED', label: 'Close Ticket' },
          { status: 'IN_PROGRESS', label: 'Reopen Ticket' },
        ];
      case 'CLOSED':
        return [];
      default:
        return [];
    }
  };

  const availableTransitions = getAvailableTransitions();
  const canClaim = !isViewer && item?.status === 'OPEN' && !item?.assignee_id;

  return (
    <>
      <div className="fixed inset-0 z-40 overflow-hidden bg-slate-900/40 backdrop-blur-xs flex justify-end">
        <div className="w-full max-w-2xl bg-white h-full shadow-2xl flex flex-col border-l border-slate-200">
          {/* Header */}
          <div className="p-5 border-b border-slate-200 flex items-start justify-between bg-slate-50">
            <div className="space-y-1">
              <div className="flex items-center space-x-2">
                <span className="font-mono text-xs text-slate-500 font-semibold">
                  TICKET-{item ? item.id.substring(0, 8).toUpperCase() : '...'}
                </span>
                {item && <TypeBadge type={item.type} />}
                {item && (
                  <span className="text-xs bg-slate-200 text-slate-700 px-1.5 py-0.5 rounded font-mono">
                    v{item.version}
                  </span>
                )}
              </div>
              <h2 className="text-lg font-bold text-slate-900 leading-snug">
                {item ? item.title : 'Loading...'}
              </h2>
            </div>
            <button
              onClick={onClose}
              className="text-slate-400 hover:text-slate-600 p-1.5 rounded-md hover:bg-slate-200"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Action Error Banner */}
          {actionError && (
            <div className="mx-6 mt-4 p-3 bg-rose-50 border border-rose-200 rounded-md text-rose-700 text-sm flex items-start space-x-2">
              <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <div>{actionError}</div>
            </div>
          )}

          {/* Body */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {isItemLoading ? (
              <div className="py-12 flex justify-center text-slate-400">
                <Loader2 className="w-6 h-6 animate-spin" />
              </div>
            ) : item ? (
              <>
                {/* Meta Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 p-4 bg-slate-50 rounded-lg border border-slate-200 text-xs">
                  <div>
                    <span className="text-slate-500 block uppercase font-semibold">Status</span>
                    <div className="mt-1">
                      <StatusBadge status={item.status} />
                    </div>
                  </div>
                  <div>
                    <span className="text-slate-500 block uppercase font-semibold">Priority</span>
                    <div className="mt-1">
                      <PriorityBadge priority={item.priority} />
                    </div>
                  </div>
                  <div>
                    <span className="text-slate-500 block uppercase font-semibold">Assignee</span>
                    <div className="mt-1 font-mono text-slate-800 truncate" title={item.assignee_id || 'Unassigned'}>
                      {item.assignee_id ? item.assignee_id.substring(0, 8) + '...' : 'Unassigned'}
                    </div>
                  </div>
                  <div>
                    <span className="text-slate-500 block uppercase font-semibold">Version</span>
                    <div className="mt-1 font-mono text-slate-800">
                      v{item.version}
                    </div>
                  </div>
                </div>

                {/* Description */}
                <div>
                  <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                    Description
                  </h3>
                  <div className="p-3 bg-slate-50 rounded-md border border-slate-200 text-sm text-slate-700 whitespace-pre-wrap">
                    {item.description || <span className="italic text-slate-400">No description provided.</span>}
                  </div>
                </div>

                {/* Action Bar */}
                <div className="p-4 bg-white rounded-lg border border-slate-200 shadow-xs space-y-3">
                  <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    Authorized Operations
                  </h3>

                  {isViewer && (
                    <div className="text-xs text-slate-500 bg-slate-50 p-2 rounded border border-slate-200 flex items-center">
                      <ShieldAlert className="w-4 h-4 mr-1.5 text-slate-400" />
                      Viewer role has read-only access for this team.
                    </div>
                  )}

                  <div className="flex flex-wrap gap-2">
                    {/* Atomic Claim button */}
                    {canClaim && (
                      <button
                        onClick={() => claimMutation.mutate()}
                        disabled={claimMutation.isPending}
                        className="inline-flex items-center px-3 py-1.5 bg-brand-600 hover:bg-brand-700 text-white text-xs font-medium rounded-md shadow-xs disabled:opacity-60"
                      >
                        {claimMutation.isPending ? (
                          <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                        ) : (
                          <UserCheck className="w-3.5 h-3.5 mr-1.5" />
                        )}
                        Claim Ticket (Atomic)
                      </button>
                    )}

                    {/* Workflow State Transitions */}
                    {availableTransitions.map((t) => (
                      <button
                        key={t.status}
                        onClick={() => transitionMutation.mutate(t.status)}
                        disabled={t.disabled || transitionMutation.isPending}
                        title={t.reason}
                        className={`inline-flex items-center px-3 py-1.5 text-xs font-medium rounded-md shadow-xs border transition-colors ${
                          t.disabled
                            ? 'bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed'
                            : 'bg-white hover:bg-slate-50 text-slate-800 border-slate-300'
                        }`}
                      >
                        {transitionMutation.isPending ? (
                          <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                        ) : (
                          <ArrowRight className="w-3.5 h-3.5 mr-1.5 text-slate-500" />
                        )}
                        {t.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Activity Audit Timeline */}
                <div>
                  <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 flex items-center">
                    <History className="w-4 h-4 mr-1.5 text-slate-400" />
                    Append-Only Activity Audit History
                  </h3>

                  {isActivityLoading ? (
                    <div className="py-6 flex justify-center text-slate-400">
                      <Loader2 className="w-5 h-5 animate-spin" />
                    </div>
                  ) : activityData && activityData.items.length > 0 ? (
                    <div className="space-y-3 relative pl-6 border-l-2 border-slate-200">
                      {activityData.items.map((ev: ActivityEvent) => (
                        <div key={ev.id} className="relative text-xs">
                          <span className="absolute -left-[31px] top-1 w-2.5 h-2.5 rounded-full bg-slate-400 border-2 border-white ring-1 ring-slate-300" />
                          <div className="font-semibold text-slate-800 flex items-center space-x-2">
                            <span className="uppercase text-[11px] font-mono px-1.5 py-0.2 bg-slate-100 border border-slate-200 rounded">
                              {ev.event_type}
                            </span>
                            <span className="text-slate-400 font-normal">
                              by {ev.actor_id.substring(0, 8)}...
                            </span>
                          </div>

                          {(ev.from_value || ev.to_value) && (
                            <div className="mt-1 text-slate-600 font-mono text-[11px]">
                              {ev.from_value || 'None'} → <span className="font-semibold">{ev.to_value}</span>
                            </div>
                          )}

                          <div className="mt-0.5 text-slate-400 text-[10px] flex items-center">
                            <Clock className="w-3 h-3 mr-1" />
                            {new Date(ev.created_at).toLocaleString()}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="p-4 bg-slate-50 rounded-md border border-slate-200 text-xs text-slate-400 italic text-center">
                      No activity events recorded.
                    </div>
                  )}
                </div>
              </>
            ) : null}
          </div>
        </div>
      </div>

      {/* Conflict Modal for 409 errors */}
      <ConflictModal
        isOpen={!!conflictMessage}
        message={conflictMessage || ''}
        onReload={reloadAll}
        onClose={() => setConflictMessage(null)}
      />
    </>
  );
};
