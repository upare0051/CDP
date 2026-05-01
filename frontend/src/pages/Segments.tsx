import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Plus,
  Search,
  Sparkles,
  Copy,
  Archive,
  Trash2,
  Play,
  Filter,
  MoreVertical,
  ChevronRight,
} from 'lucide-react';
import { cn, formatRelativeTime, formatNumber } from '@/lib/utils';
import {
  getSegments,
  deleteSegment,
  duplicateSegment,
  activateSegment,
  archiveSegment,
  Segment,
} from '@/lib/api';
import { Card, CardContent } from '@/components/Card';
import Button from '@/components/Button';
import Input from '@/components/Input';
import StatusBadge from '@/components/StatusBadge';
import EmptyState from '@/components/EmptyState';
import { PageLoader } from '@/components/LoadingSpinner';
import Modal from '@/components/Modal';
import { FilterPreview } from '@/components/FilterBuilder';

type StatusFilter = 'all' | 'draft' | 'active' | 'archived';

export default function Segments() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [segmentToDelete, setSegmentToDelete] = useState<Segment | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['segments', statusFilter, search],
    queryFn: () =>
      getSegments({
        status: statusFilter === 'all' ? undefined : statusFilter,
        search: search || undefined,
      }),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteSegment,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['segments'] });
      setDeleteModalOpen(false);
      setSegmentToDelete(null);
    },
  });

  const duplicateMutation = useMutation({
    mutationFn: (id: number) => duplicateSegment(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['segments'] });
    },
  });

  const activateMutation = useMutation({
    mutationFn: activateSegment,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['segments'] });
    },
  });

  const archiveMutation = useMutation({
    mutationFn: archiveSegment,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['segments'] });
    },
  });

  const handleDelete = (segment: Segment) => {
    setSegmentToDelete(segment);
    setDeleteModalOpen(true);
  };

  const confirmDelete = () => {
    if (segmentToDelete) {
      deleteMutation.mutate(segmentToDelete.id);
    }
  };

  const statusTabs: { key: StatusFilter; label: string }[] = [
    { key: 'all', label: 'All' },
    { key: 'active', label: 'Active' },
    { key: 'draft', label: 'Draft' },
    { key: 'archived', label: 'Archived' },
  ];

  if (isLoading) return <PageLoader />;

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">Segments</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">
            Create and manage audience segments for targeting
          </p>
        </div>
        <Button onClick={() => navigate('/segments/new')}>
          <Plus className="w-4 h-4" />
          Create Segment
        </Button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        {/* Status Tabs */}
        <div className="flex items-center gap-1 p-1 bg-gray-100 dark:bg-gray-800 rounded-lg">
          {statusTabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setStatusFilter(tab.key)}
              className={cn(
                'px-3 py-1.5 text-sm font-medium rounded-md transition-colors',
                statusFilter === tab.key
                  ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm'
                  : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="flex-1 relative max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search segments..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className={cn(
              'w-full pl-9 pr-4 py-2 text-sm rounded-lg',
              'bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700',
              'text-gray-900 dark:text-gray-100 placeholder:text-gray-400',
              'focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500'
            )}
          />
        </div>
      </div>

      {/* Segments List */}
      {data?.items.length === 0 ? (
        <EmptyState
          icon={<Filter className="w-8 h-8" />}
          title="No segments found"
          description={
            search ? 'Try adjusting the search or filters' : 'Create the first segment to start targeting audiences'
          }
          action={
            !search && (
              <Button onClick={() => navigate('/segments/new')}>
                <Plus className="w-4 h-4" />
                Create Segment
              </Button>
            )
          }
        />
      ) : (
        <div className="space-y-3">
          {data?.items.map((segment) => (
            <SegmentCard
              key={segment.id}
              segment={segment}
              onDuplicate={() => duplicateMutation.mutate(segment.id)}
              onActivate={() => activateMutation.mutate(segment.id)}
              onArchive={() => archiveMutation.mutate(segment.id)}
              onDelete={() => handleDelete(segment)}
            />
          ))}
        </div>
      )}

      {/* Delete Confirmation Modal */}
      <Modal isOpen={deleteModalOpen} onClose={() => setDeleteModalOpen(false)} title="Delete Segment">
        <div className="space-y-4">
          <p className="text-gray-600 dark:text-gray-400">
            Are you sure you want to delete{' '}
            <span className="font-medium text-gray-900 dark:text-white">{segmentToDelete?.name}</span>? This action
            cannot be undone.
          </p>
          <div className="flex justify-end gap-3">
            <Button variant="secondary" onClick={() => setDeleteModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={confirmDelete} loading={deleteMutation.isPending}>
              Delete
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

interface SegmentCardProps {
  segment: Segment;
  onDuplicate: () => void;
  onActivate: () => void;
  onArchive: () => void;
  onDelete: () => void;
}

function SegmentCard({ segment, onDuplicate, onActivate, onArchive, onDelete }: SegmentCardProps) {
  const [menuOpen, setMenuOpen] = useState(false);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'text-green-700 dark:text-green-400 bg-green-50 dark:bg-green-900/30';
      case 'draft':
        return 'text-gray-600 dark:text-gray-400 bg-gray-100 dark:bg-gray-800';
      case 'archived':
        return 'text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/30';
      default:
        return 'text-gray-600 dark:text-gray-400 bg-gray-100 dark:bg-gray-800';
    }
  };

  return (
    <Card hover className="group">
      <CardContent className="p-0">
        <div className="flex items-center">
          {/* Main Content - Clickable */}
          <Link to={`/segments/${segment.id}`} className="flex-1 flex items-center gap-4 p-4">
            {/* Icon */}
            <div
              className={cn(
                'w-10 h-10 rounded-lg flex items-center justify-center shrink-0',
                segment.ai_generated
                  ? 'bg-gradient-to-br from-primary-100 to-accent-100 dark:from-primary-900/30 dark:to-accent-900/30'
                  : 'bg-gray-100 dark:bg-gray-800'
              )}
            >
              {segment.ai_generated ? (
                <Sparkles className="w-5 h-5 text-primary-600 dark:text-primary-400" />
              ) : (
                <Filter className="w-5 h-5 text-gray-500 dark:text-gray-400" />
              )}
            </div>

            {/* Details */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <h3 className="font-medium text-gray-900 dark:text-white truncate">{segment.name}</h3>
                <span className={cn('px-2 py-0.5 text-xs font-medium rounded-full', getStatusColor(segment.status))}>
                  {segment.status}
                </span>
              </div>
              {segment.description && (
                <p className="text-sm text-gray-500 dark:text-gray-400 truncate">{segment.description}</p>
              )}
              <div className="flex items-center gap-3 mt-2">
                {segment.estimated_count !== null && segment.estimated_count !== undefined ? (
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    {formatNumber(segment.estimated_count)} customers
                  </span>
                ) : (
                  <span className="text-xs text-gray-500 dark:text-gray-400">—</span>
                )}
                <span className="text-xs text-gray-400 dark:text-gray-500">
                  {segment.updated_at ? `${formatRelativeTime(segment.updated_at)} updated` : ''}
                </span>
              </div>
              <div className="mt-2">
                <FilterPreview config={segment.filter_config} />
              </div>
            </div>

            <ChevronRight className="w-5 h-5 text-gray-300 dark:text-gray-600 group-hover:text-gray-400 dark:group-hover:text-gray-500 transition-colors" />
          </Link>

          {/* Actions Menu */}
          <div className="relative pr-4">
            <button
              onClick={(e) => {
                e.preventDefault();
                setMenuOpen((v) => !v);
              }}
              className="p-2 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
            >
              <MoreVertical className="w-4 h-4" />
            </button>

            {menuOpen && (
              <div
                className="absolute right-4 top-10 w-48 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-lg shadow-lg p-1 z-20"
                onMouseLeave={() => setMenuOpen(false)}
              >
                <button
                  onClick={(e) => {
                    e.preventDefault();
                    onDuplicate();
                    setMenuOpen(false);
                  }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
                >
                  <Copy className="w-4 h-4" /> Duplicate
                </button>
                {segment.status === 'draft' && (
                  <button
                    onClick={(e) => {
                      e.preventDefault();
                      onActivate();
                      setMenuOpen(false);
                    }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
                  >
                    <Play className="w-4 h-4" /> Set Active
                  </button>
                )}
                {segment.status === 'active' && (
                  <button
                    onClick={(e) => {
                      e.preventDefault();
                      onArchive();
                      setMenuOpen(false);
                    }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
                  >
                    <Archive className="w-4 h-4" /> Archive
                  </button>
                )}
                <button
                  onClick={(e) => {
                    e.preventDefault();
                    onDelete();
                    setMenuOpen(false);
                  }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-md"
                >
                  <Trash2 className="w-4 h-4" /> Delete
                </button>
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

