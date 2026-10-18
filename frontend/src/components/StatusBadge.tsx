import React from 'react';
import type { WorkItemStatus, WorkItemPriority, WorkItemType } from '../types';

export const StatusBadge: React.FC<{ status: WorkItemStatus | string }> = ({ status }) => {
  const styles: Record<string, string> = {
    OPEN: 'bg-blue-50 text-blue-700 border-blue-200',
    IN_PROGRESS: 'bg-amber-50 text-amber-700 border-amber-200',
    AWAITING_APPROVAL: 'bg-purple-50 text-purple-700 border-purple-200',
    RESOLVED: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    CLOSED: 'bg-slate-100 text-slate-600 border-slate-200',
  };

  const currentStyle = styles[status] || 'bg-gray-50 text-gray-700 border-gray-200';

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${currentStyle}`}
    >
      <span className="w-1.5 h-1.5 rounded-full mr-1.5 bg-current opacity-70" />
      {status.replace('_', ' ')}
    </span>
  );
};

export const PriorityBadge: React.FC<{ priority: WorkItemPriority | string }> = ({ priority }) => {
  const styles: Record<string, string> = {
    CRITICAL: 'bg-rose-50 text-rose-700 border-rose-200',
    HIGH: 'bg-orange-50 text-orange-700 border-orange-200',
    MEDIUM: 'bg-amber-50 text-amber-700 border-amber-200',
    LOW: 'bg-slate-50 text-slate-600 border-slate-200',
  };

  const currentStyle = styles[priority] || 'bg-gray-50 text-gray-700 border-gray-200';

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold border ${currentStyle}`}>
      {priority}
    </span>
  );
};

export const TypeBadge: React.FC<{ type: WorkItemType | string }> = ({ type }) => {
  return (
    <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-mono uppercase tracking-wider bg-slate-100 text-slate-700 border border-slate-200">
      {type}
    </span>
  );
};
