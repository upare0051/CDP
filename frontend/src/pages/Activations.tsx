import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useSearchParams } from 'react-router-dom';
import { Plus } from 'lucide-react';
import { isAxiosError } from 'axios';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/Card';
import { PageLoader } from '@/components/LoadingSpinner';
import EmptyState from '@/components/EmptyState';
import Button from '@/components/Button';
import StatusBadge from '@/components/StatusBadge';
import Modal from '@/components/Modal';
import {
  getActivations,
  getDestinations,
  getSegments,
  createActivation,
} from '@/lib/api';
import { Zap } from 'lucide-react';

export default function Activations() {
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const rawSegment = searchParams.get('segment');
  const segmentId =
    rawSegment != null && rawSegment !== '' ? parseInt(rawSegment, 10) : undefined;
  const segmentFilter =
    segmentId !== undefined && Number.isFinite(segmentId) ? segmentId : undefined;

  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [modalSegmentId, setModalSegmentId] = useState<number | ''>('');
  const [modalDestinationId, setModalDestinationId] = useState<number | ''>('');
  const [inlineDestinationId, setInlineDestinationId] = useState<number | ''>('');

  const { data, isLoading, error } = useQuery({
    queryKey: ['activations', segmentFilter],
    queryFn: () =>
      getActivations(segmentFilter != null ? { segment_id: segmentFilter } : {}),
  });

  const { data: destinations = [] } = useQuery({
    queryKey: ['destinations'],
    queryFn: getDestinations,
  });

  const { data: segmentsList, isLoading: segmentsLoading, error: segmentsError } = useQuery({
    queryKey: ['segments', 'activations-modal'],
    queryFn: () => getSegments({ page_size: 100 }),
    enabled: createModalOpen,
  });
  const segments = segmentsList?.items ?? [];

  useEffect(() => {
    if (segmentFilter != null && destinations.length > 0 && inlineDestinationId === '') {
      setInlineDestinationId(destinations[0].id);
    }
  }, [segmentFilter, destinations, inlineDestinationId]);

  useEffect(() => {
    if (!createModalOpen) return;
    if (segments.length > 0 && modalSegmentId === '') {
      setModalSegmentId(segments[0].id);
    }
    if (destinations.length > 0 && modalDestinationId === '') {
      setModalDestinationId(destinations[0].id);
    }
  }, [createModalOpen, segments, destinations, modalSegmentId, modalDestinationId]);

  const createMutation = useMutation({
    mutationFn: (payload: { segment_id: number; destination_id: number }) =>
      createActivation(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['activations'] });
      setCreateModalOpen(false);
      setModalSegmentId('');
      setModalDestinationId('');
    },
  });

  const createErrorMessage = () => {
    const err = createMutation.error;
    if (!err) return '';
    if (isAxiosError(err)) {
      const d = err.response?.data as { detail?: string } | undefined;
      if (typeof d?.detail === 'string') return d.detail;
    }
    return (err as Error).message || 'Could not create activation.';
  };

  const segmentLoadErrorMessage = () => {
    if (!segmentsError) return '';
    if (isAxiosError(segmentsError)) {
      const d = segmentsError.response?.data as { detail?: string } | undefined;
      if (typeof d?.detail === 'string') return d.detail;
    }
    return (segmentsError as Error).message || 'Could not load segments.';
  };

  const handleInlineCreate = () => {
    if (segmentFilter == null || inlineDestinationId === '') return;
    createMutation.mutate({
      segment_id: segmentFilter,
      destination_id: Number(inlineDestinationId),
    });
  };

  const handleModalCreate = () => {
    if (modalSegmentId === '' || modalDestinationId === '') return;
    createMutation.mutate({
      segment_id: Number(modalSegmentId),
      destination_id: Number(modalDestinationId),
    });
  };

  if (isLoading) return <PageLoader />;

  const items = data?.items ?? [];
  const hasDestinations = destinations.length > 0;

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Activations</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">
            Sync segment members to downstream destinations.
            {segmentFilter != null && (
              <span className="block text-sm mt-1 text-gray-600 dark:text-gray-300">
                Showing activations for segment #{segmentFilter}.
              </span>
            )}
          </p>
        </div>
        <Button
          icon={<Plus className="w-4 h-4" />}
          variant="secondary"
          disabled={!hasDestinations}
          onClick={() => {
            setModalSegmentId(segmentFilter ?? '');
            setModalDestinationId(destinations[0]?.id ?? '');
            setCreateModalOpen(true);
          }}
        >
          New activation
        </Button>
      </div>

      {segmentFilter != null && hasDestinations && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Link segment to a destination</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col sm:flex-row sm:items-end gap-4">
            <div className="flex-1 min-w-[200px]">
              <label className="block text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-1.5">
                Destination
              </label>
              <select
                className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 text-sm"
                value={inlineDestinationId === '' ? '' : String(inlineDestinationId)}
                onChange={(e) => setInlineDestinationId(e.target.value ? parseInt(e.target.value, 10) : '')}
              >
                {destinations.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} ({d.destination_type})
                  </option>
                ))}
              </select>
            </div>
            <Button
              variant="primary"
              loading={createMutation.isPending}
              disabled={inlineDestinationId === ''}
              onClick={handleInlineCreate}
            >
              Create activation
            </Button>
          </CardContent>
          {createMutation.isError && (
            <CardContent className="pt-0">
              <p className="text-sm text-red-600 dark:text-red-400">{createErrorMessage()}</p>
            </CardContent>
          )}
        </Card>
      )}

      {segmentFilter != null && !hasDestinations && (
        <Card>
          <CardContent className="py-4 text-sm text-gray-600 dark:text-gray-300">
            Add a{' '}
            <Link to="/destinations" className="text-primary-600 dark:text-primary-400 underline">
              destination
            </Link>{' '}
            before you can create an activation for this segment.
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">All activations</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          {error ? (
            <div className="text-sm text-red-600 dark:text-red-400">Failed to load activations.</div>
          ) : items.length === 0 ? (
            <EmptyState
              icon={<Zap className="w-6 h-6" />}
              title={segmentFilter != null ? 'No activations for this segment yet' : 'No activations yet'}
              description={
                segmentFilter != null
                  ? hasDestinations
                    ? 'Use the form above to link this segment to a destination.'
                    : 'Add a destination, then create an activation using the form above.'
                  : 'Use New activation to pick a segment and destination, or open a segment in Segments and choose Activate.'
              }
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-800">
                    <th className="py-3 pr-4">Name</th>
                    <th className="py-3 pr-4">Segment</th>
                    <th className="py-3 pr-4">Destination</th>
                    <th className="py-3 pr-4">Status</th>
                    <th className="py-3 pr-4">Last synced</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((a) => (
                    <tr key={a.id} className="border-b border-gray-100 dark:border-gray-900 hover:bg-gray-50 dark:hover:bg-gray-900/30">
                      <td className="py-3 pr-4 font-medium text-gray-900 dark:text-white">
                        {a.name || `Activation ${a.id}`}
                      </td>
                      <td className="py-3 pr-4 text-gray-700 dark:text-gray-300">{a.segment_name || a.segment_id}</td>
                      <td className="py-3 pr-4 text-gray-700 dark:text-gray-300">{a.destination_name || a.destination_id}</td>
                      <td className="py-3 pr-4">
                        <StatusBadge status={a.status} />
                      </td>
                      <td className="py-3 pr-4 text-gray-700 dark:text-gray-300">
                        {a.last_sync_at ? new Date(a.last_sync_at).toLocaleString() : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Modal
        isOpen={createModalOpen}
        onClose={() => {
          setCreateModalOpen(false);
          createMutation.reset();
        }}
        title="New activation"
        size="md"
      >
        <div className="space-y-4">
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Link a segment to a destination. You can run a sync from the activation detail once this exists.
          </p>
          {!hasDestinations ? (
            <p className="text-sm text-amber-700 dark:text-amber-300">
              No destinations configured.{' '}
              <Link to="/destinations" className="underline" onClick={() => setCreateModalOpen(false)}>
                Add one first
              </Link>
              .
            </p>
          ) : (
            <>
              <div>
                <label className="block text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-1.5">
                  Segment
                </label>
                <select
                  className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 text-sm"
                  value={modalSegmentId === '' ? '' : String(modalSegmentId)}
                  onChange={(e) => setModalSegmentId(e.target.value ? parseInt(e.target.value, 10) : '')}
                  disabled={segmentsLoading || Boolean(segmentsError)}
                >
                  {segmentsLoading ? (
                    <option value="">Loading segments…</option>
                  ) : segmentsError ? (
                    <option value="">Failed to load segments</option>
                  ) : segments.length === 0 ? (
                    <option value="">No segments yet</option>
                  ) : (
                    segments.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name} ({s.status})
                      </option>
                    ))
                  )}
                </select>
                {segmentsError && (
                  <p className="text-sm text-red-600 dark:text-red-400 mt-2">
                    {segmentLoadErrorMessage()}
                  </p>
                )}
                {!segmentsLoading && !segmentsError && segments.length === 0 && (
                  <p className="text-sm text-gray-600 dark:text-gray-400 mt-2">
                    <Link
                      to="/segments/new"
                      className="text-primary-600 dark:text-primary-400 underline"
                      onClick={() => setCreateModalOpen(false)}
                    >
                      Create a segment
                    </Link>{' '}
                    first.
                  </p>
                )}
              </div>
              <div>
                <label className="block text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-1.5">
                  Destination
                </label>
                <select
                  className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 text-sm"
                  value={modalDestinationId === '' ? '' : String(modalDestinationId)}
                  onChange={(e) =>
                    setModalDestinationId(e.target.value ? parseInt(e.target.value, 10) : '')
                  }
                >
                  {destinations.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name} ({d.destination_type})
                    </option>
                  ))}
                </select>
              </div>
              {createMutation.isError && (
                <p className="text-sm text-red-600 dark:text-red-400">{createErrorMessage()}</p>
              )}
              <div className="flex justify-end gap-2 pt-2">
                <Button variant="ghost" onClick={() => setCreateModalOpen(false)}>
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  loading={createMutation.isPending}
                  disabled={
                    modalSegmentId === '' ||
                    modalDestinationId === '' ||
                    createMutation.isPending
                  }
                  onClick={handleModalCreate}
                >
                  Create
                </Button>
              </div>
            </>
          )}
        </div>
      </Modal>
    </div>
  );
}
