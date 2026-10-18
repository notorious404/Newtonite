import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface ConflictModalProps {
  isOpen: boolean;
  message: string;
  onReload: () => void;
  onClose: () => void;
}

export const ConflictModal: React.FC<ConflictModalProps> = ({
  isOpen,
  message,
  onReload,
  onClose,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white rounded-lg max-w-md w-full p-6 shadow-xl border border-slate-200">
        <div className="flex items-start space-x-3">
          <div className="p-2 bg-amber-100 rounded-full text-amber-600 flex-shrink-0">
            <AlertTriangle className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-slate-900">Conflict Detected (HTTP 409)</h3>
            <p className="text-sm text-slate-600 mt-2">
              {message || 'The work item was modified by another user or operation, or your cached version is stale.'}
            </p>
            <p className="text-xs text-slate-500 mt-2">
              To prevent overwriting concurrent updates (optimistic concurrency control), your modification was safely rejected. Reload to inspect the latest state.
            </p>
          </div>
        </div>

        <div className="mt-6 flex justify-end space-x-3">
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-md hover:bg-slate-50"
          >
            Dismiss
          </button>
          <button
            type="button"
            onClick={onReload}
            className="inline-flex items-center px-4 py-1.5 text-sm font-medium text-white bg-slate-900 rounded-md hover:bg-slate-800 focus:outline-none"
          >
            <RefreshCw className="w-4 h-4 mr-1.5" />
            Reload Latest State
          </button>
        </div>
      </div>
    </div>
  );
};
