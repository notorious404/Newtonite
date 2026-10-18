import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import type { WorkItem } from '../types';
import { StatusBadge, PriorityBadge, TypeBadge } from '../components/StatusBadge';
import { CreateTicketModal } from '../components/CreateTicketModal';
import { TicketDetailsDrawer } from '../components/TicketDetailsDrawer';
import {
  Search,
  Plus,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  Inbox,
  AlertCircle,
  Loader2,
  Layers,
  Clock,
  CheckCircle,
} from 'lucide-react';

export const Dashboard: React.FC = () => {
  const { selectedTeam } = useAuth();

  // Filters & Pagination State
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [priorityFilter, setPriorityFilter] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [limit, setLimit] = useState<number>(20);
  const [cursor, setCursor] = useState<string | undefined>(undefined);
  const [cursorHistory, setCursorHistory] = useState<string[]>([]);

  // Modals state
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);

  const teamId = selectedTeam?.team_id;
  const isViewer = selectedTeam?.role === 'Viewer';

  // 1. Fetch Work Items with filters and keyset cursor
  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ['work-items', teamId, statusFilter, priorityFilter, searchQuery, cursor, limit],
    queryFn: () =>
      api.listWorkItems({
        team_id: teamId,
        status: statusFilter || undefined,
        priority: priorityFilter || undefined,
        q: searchQuery.trim() || undefined,
        cursor: cursor,
        limit: limit,
      }),
    enabled: !!teamId,
  });

  // Calculate Metrics from fetched items / total
  const items = data?.items || [];
  const totalCount = data?.total || 0;

  const openCount = items.filter((i) => i.status === 'OPEN').length;
  const inProgressCount = items.filter((i) => i.status === 'IN_PROGRESS').length;
  const awaitingCount = items.filter((i) => i.status === 'AWAITING_APPROVAL').length;
  const resolvedCount = items.filter((i) => i.status === 'RESOLVED').length;

  const handleNextPage = () => {
    if (data?.next_cursor) {
      setCursorHistory((prev) => [...prev, cursor || '']);
      setCursor(data.next_cursor);
    }
  };

  const handlePrevPage = () => {
    if (cursorHistory.length > 0) {
      const prev = [...cursorHistory];
      const lastCursor = prev.pop();
      setCursorHistory(prev);
      setCursor(lastCursor || undefined);
    }
  };

  const handleFilterChange = (setter: React.Dispatch<React.SetStateAction<string>>) => (e: React.ChangeEvent<HTMLSelectElement>) => {
    setter(e.target.value);
    setCursor(undefined);
    setCursorHistory([]);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Metrics Row */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
        <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-xs">
          <div className="flex items-center text-xs font-semibold text-slate-500 uppercase tracking-wider">
            <Layers className="w-4 h-4 mr-1.5 text-slate-400" /> Total Active
          </div>
          <div className="mt-2 text-2xl font-bold text-slate-900">{totalCount}</div>
        </div>

        <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-xs">
          <div className="flex items-center text-xs font-semibold text-blue-600 uppercase tracking-wider">
            <span className="w-2 h-2 rounded-full bg-blue-500 mr-1.5" /> Open
          </div>
          <div className="mt-2 text-2xl font-bold text-slate-900">{openCount}</div>
        </div>

        <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-xs">
          <div className="flex items-center text-xs font-semibold text-amber-600 uppercase tracking-wider">
            <Clock className="w-4 h-4 mr-1.5 text-amber-500" /> In Progress
          </div>
          <div className="mt-2 text-2xl font-bold text-slate-900">{inProgressCount}</div>
        </div>

        <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-xs">
          <div className="flex items-center text-xs font-semibold text-purple-600 uppercase tracking-wider">
            <span className="w-2 h-2 rounded-full bg-purple-500 mr-1.5" /> Approval
          </div>
          <div className="mt-2 text-2xl font-bold text-slate-900">{awaitingCount}</div>
        </div>

        <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-xs">
          <div className="flex items-center text-xs font-semibold text-emerald-600 uppercase tracking-wider">
            <CheckCircle className="w-4 h-4 mr-1.5 text-emerald-500" /> Resolved
          </div>
          <div className="mt-2 text-2xl font-bold text-slate-900">{resolvedCount}</div>
        </div>
      </div>

      {/* Action and Filter Control Bar */}
      <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-xs flex flex-col md:flex-row gap-3 items-center justify-between">
        {/* Left: Search & Filters */}
        <div className="flex flex-wrap items-center gap-2.5 w-full md:w-auto">
          {/* Search */}
          <div className="relative flex-1 sm:w-64">
            <label htmlFor="search-tickets" className="sr-only">Search tickets</label>
            <input
              id="search-tickets"
              type="text"
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setCursor(undefined);
                setCursorHistory([]);
              }}
              placeholder="Search title & description..."
              className="w-full bg-slate-50 border border-slate-300 rounded-md py-1.5 pl-8 pr-3 text-xs text-slate-900 focus:ring-slate-500 focus:border-slate-500"
            />
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
          </div>

          {/* Status Filter */}
          <div className="flex items-center">
            <label htmlFor="status-filter" className="sr-only">Filter by Status</label>
            <select
              id="status-filter"
              aria-label="Filter by Status"
              value={statusFilter}
              onChange={handleFilterChange(setStatusFilter)}
              className="bg-slate-50 border border-slate-300 rounded-md py-1.5 px-2 text-xs text-slate-800 font-medium"
            >
              <option value="">All Statuses</option>
              <option value="OPEN">OPEN</option>
              <option value="IN_PROGRESS">IN PROGRESS</option>
              <option value="AWAITING_APPROVAL">AWAITING APPROVAL</option>
              <option value="RESOLVED">RESOLVED</option>
              <option value="CLOSED">CLOSED</option>
            </select>
          </div>

          {/* Priority Filter */}
          <div className="flex items-center">
            <label htmlFor="priority-filter" className="sr-only">Filter by Priority</label>
            <select
              id="priority-filter"
              aria-label="Filter by Priority"
              value={priorityFilter}
              onChange={handleFilterChange(setPriorityFilter)}
              className="bg-slate-50 border border-slate-300 rounded-md py-1.5 px-2 text-xs text-slate-800 font-medium"
            >
              <option value="">All Priorities</option>
              <option value="CRITICAL">CRITICAL</option>
              <option value="HIGH">HIGH</option>
              <option value="MEDIUM">MEDIUM</option>
              <option value="LOW">LOW</option>
            </select>
          </div>

          {/* Refresh Button */}
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            title="Refresh items"
            className="p-1.5 border border-slate-300 rounded-md hover:bg-slate-50 text-slate-600 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {/* Right: Create Ticket Button */}
        <div className="w-full md:w-auto flex justify-end">
          <button
            onClick={() => setIsCreateOpen(true)}
            disabled={isViewer}
            title={isViewer ? 'Viewer role cannot create tickets' : 'Create new work item'}
            className="inline-flex items-center px-3.5 py-1.5 bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold rounded-md shadow-xs disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Plus className="w-3.5 h-3.5 mr-1.5" />
            Create Work Item
          </button>
        </div>
      </div>

      {/* Table Container */}
      <div className="bg-white rounded-lg border border-slate-200 shadow-xs overflow-hidden">
        {isLoading ? (
          <div className="py-20 flex flex-col items-center justify-center text-slate-400 space-y-2">
            <Loader2 className="w-8 h-8 animate-spin" />
            <span className="text-xs">Loading operational tickets...</span>
          </div>
        ) : isError ? (
          <div className="py-16 px-4 text-center">
            <AlertCircle className="w-8 h-8 text-rose-500 mx-auto mb-2" />
            <h3 className="text-sm font-semibold text-slate-900">Failed to load work items</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
              {(error as any)?.detail || 'Ensure your team membership is valid and the server is running.'}
            </p>
            <button
              onClick={() => refetch()}
              className="mt-4 px-3 py-1.5 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-md"
            >
              Retry Request
            </button>
          </div>
        ) : items.length === 0 ? (
          <div className="py-16 text-center text-slate-400">
            <Inbox className="w-10 h-10 mx-auto mb-2 stroke-1" />
            <div className="text-sm font-semibold text-slate-700">No work items found</div>
            <p className="text-xs text-slate-400 mt-1">
              {searchQuery || statusFilter || priorityFilter
                ? 'Try adjusting your search criteria or active filters.'
                : 'Click "+ Create Work Item" above to add the first operational ticket.'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 font-semibold uppercase tracking-wider">
                <tr>
                  <th scope="col" className="px-4 py-3">ID / Ref</th>
                  <th scope="col" className="px-4 py-3">Status</th>
                  <th scope="col" className="px-4 py-3">Priority</th>
                  <th scope="col" className="px-4 py-3">Title</th>
                  <th scope="col" className="px-4 py-3">Type</th>
                  <th scope="col" className="px-4 py-3">Assignee</th>
                  <th scope="col" className="px-4 py-3">Version</th>
                  <th scope="col" className="px-4 py-3">Created</th>
                  <th scope="col" className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {items.map((item: WorkItem) => (
                  <tr
                    key={item.id}
                    onClick={() => setSelectedItemId(item.id)}
                    className="hover:bg-slate-50 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-3 font-mono font-semibold text-slate-700 whitespace-nowrap">
                      {item.id.substring(0, 8).toUpperCase()}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <StatusBadge status={item.status} />
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <PriorityBadge priority={item.priority} />
                    </td>
                    <td className="px-4 py-3 font-medium text-slate-900 max-w-xs truncate">
                      {item.title}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <TypeBadge type={item.type} />
                    </td>
                    <td className="px-4 py-3 font-mono text-slate-600 whitespace-nowrap">
                      {item.assignee_id ? (
                        <span className="text-slate-800" title={item.assignee_id}>
                          {item.assignee_id.substring(0, 8)}...
                        </span>
                      ) : (
                        <span className="text-slate-400 italic">None</span>
                      )}
                    </td>
                    <td className="px-4 py-3 font-mono text-slate-600 whitespace-nowrap">
                      v{item.version}
                    </td>
                    <td className="px-4 py-3 text-slate-500 whitespace-nowrap">
                      {new Date(item.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3 text-right whitespace-nowrap">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedItemId(item.id);
                        }}
                        className="text-slate-600 hover:text-slate-900 font-medium text-xs bg-slate-100 hover:bg-slate-200 px-2 py-1 rounded transition-colors"
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Keyset Pagination Footer */}
        <div className="p-3 bg-slate-50 border-t border-slate-200 flex items-center justify-between text-xs text-slate-500">
          <div className="flex items-center space-x-2">
            <span>Page size:</span>
            <label htmlFor="page-size-select" className="sr-only">Page size</label>
            <select
              id="page-size-select"
              aria-label="Page size"
              value={limit}
              onChange={(e) => {
                setLimit(Number(e.target.value));
                setCursor(undefined);
                setCursorHistory([]);
              }}
              className="bg-white border border-slate-300 rounded px-1.5 py-0.5 text-xs text-slate-700"
            >
              <option value="10">10</option>
              <option value="20">20</option>
              <option value="50">50</option>
            </select>
            <span className="ml-2 font-mono text-slate-400">
              Deterministic Keyset (created_at DESC, id DESC)
            </span>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={handlePrevPage}
              disabled={cursorHistory.length === 0}
              className="inline-flex items-center px-2.5 py-1 bg-white border border-slate-300 rounded hover:bg-slate-100 text-slate-700 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="w-3.5 h-3.5 mr-1" />
              Previous
            </button>
            <button
              onClick={handleNextPage}
              disabled={!data?.has_more}
              className="inline-flex items-center px-2.5 py-1 bg-white border border-slate-300 rounded hover:bg-slate-100 text-slate-700 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next
              <ChevronRight className="w-3.5 h-3.5 ml-1" />
            </button>
          </div>
        </div>
      </div>

      {/* Modals and Drawers */}
      <CreateTicketModal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
      />

      <TicketDetailsDrawer
        itemId={selectedItemId}
        onClose={() => setSelectedItemId(null)}
      />
    </div>
  );
};
