import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from '../api/client';
import type { WorkItemPriority, WorkItemType } from '../types';
import { X, PlusCircle, AlertCircle, Loader2 } from 'lucide-react';

interface CreateTicketModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const CreateTicketModal: React.FC<CreateTicketModalProps> = ({ isOpen, onClose }) => {
  const { user, selectedTeam } = useAuth();
  const queryClient = useQueryClient();

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [type, setType] = useState<WorkItemType>('TASK');
  const [priority, setPriority] = useState<WorkItemPriority>('MEDIUM');
  const [teamId, setTeamId] = useState(selectedTeam?.team_id || '');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Sync teamId if selectedTeam changes
  React.useEffect(() => {
    if (selectedTeam?.team_id) {
      setTeamId(selectedTeam.team_id);
    }
  }, [selectedTeam]);

  const createMutation = useMutation({
    mutationFn: async () => {
      // Generate a fresh idempotency key per ticket creation attempt
      const idempotencyKey = crypto.randomUUID();
      return api.createWorkItem(
        {
          team_id: teamId,
          title: title.trim(),
          description: description.trim() || undefined,
          type,
          priority,
        },
        idempotencyKey
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['work-items'] });
      setTitle('');
      setDescription('');
      setErrorMessage(null);
      onClose();
    },
    onError: (err: any) => {
      if (err instanceof ApiError) {
        setErrorMessage(err.detail);
      } else {
        setErrorMessage('Failed to create ticket. Please check input parameters.');
      }
    },
  });

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setErrorMessage('Title is required');
      return;
    }
    setErrorMessage(null);
    createMutation.mutate();
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white rounded-lg max-w-lg w-full p-6 shadow-xl border border-slate-200">
        <div className="flex justify-between items-center pb-3 border-b border-slate-100">
          <h2 className="text-base font-semibold text-slate-900 flex items-center">
            <PlusCircle className="w-5 h-5 mr-2 text-slate-700" />
            Create Work Item
          </h2>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-1 rounded-md"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {errorMessage && (
          <div className="mt-4 p-3 bg-rose-50 border border-rose-200 rounded-md flex items-start space-x-2 text-rose-700 text-sm">
            <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <div>{errorMessage}</div>
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          {/* Target Team */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
              Authorized Team
            </label>
            <select
              value={teamId}
              onChange={(e) => setTeamId(e.target.value)}
              className="w-full bg-slate-50 border border-slate-300 rounded-md p-2 text-sm text-slate-900 focus:ring-slate-500 focus:border-slate-500"
              required
            >
              {user?.memberships.map((m) => (
                <option key={m.id} value={m.team_id}>
                  {m.team_name} ({m.role})
                </option>
              ))}
            </select>
          </div>

          {/* Title */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
              Title <span className="text-rose-500">*</span>
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g., Investigate high DB connection pool latency"
              className="w-full bg-white border border-slate-300 rounded-md p-2 text-sm text-slate-900 focus:ring-slate-500 focus:border-slate-500"
              required
              maxLength={255}
            />
          </div>

          {/* Type & Priority */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                Type
              </label>
              <select
                value={type}
                onChange={(e) => setType(e.target.value as WorkItemType)}
                className="w-full bg-white border border-slate-300 rounded-md p-2 text-sm text-slate-900 focus:ring-slate-500 focus:border-slate-500"
              >
                <option value="TASK">TASK</option>
                <option value="BUG">BUG</option>
                <option value="FEATURE">FEATURE</option>
                <option value="IMPROVEMENT">IMPROVEMENT</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                Priority
              </label>
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value as WorkItemPriority)}
                className="w-full bg-white border border-slate-300 rounded-md p-2 text-sm text-slate-900 focus:ring-slate-500 focus:border-slate-500"
              >
                <option value="LOW">LOW</option>
                <option value="MEDIUM">MEDIUM</option>
                <option value="HIGH">HIGH</option>
                <option value="CRITICAL">CRITICAL</option>
              </select>
            </div>
          </div>

          {/* Description */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
              Description (Optional)
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              placeholder="Provide context, reproducing steps, or technical notes..."
              className="w-full bg-white border border-slate-300 rounded-md p-2 text-sm text-slate-900 focus:ring-slate-500 focus:border-slate-500"
            />
          </div>

          <div className="pt-3 border-t border-slate-100 flex items-center justify-between">
            <span className="text-xs text-slate-400 font-mono">
              Idempotency: automatic UUID header
            </span>
            <div className="flex space-x-2">
              <button
                type="button"
                onClick={onClose}
                className="px-3 py-1.5 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-md hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={createMutation.isPending}
                className="inline-flex items-center px-4 py-1.5 text-sm font-medium text-white bg-slate-900 rounded-md hover:bg-slate-800 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {createMutation.isPending && (
                  <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />
                )}
                Create Ticket
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};
