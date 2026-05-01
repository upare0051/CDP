import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Plus } from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/Card';
import { PageLoader } from '@/components/LoadingSpinner';
import EmptyState from '@/components/EmptyState';
import Button from '@/components/Button';
import StatusBadge from '@/components/StatusBadge';
import { getActivations } from '@/lib/api';
import { Zap } from 'lucide-react';

export default function Activations() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['activations'],
    queryFn: () => getActivations(),
  });

  if (isLoading) return <PageLoader />;

  const items = data?.items ?? [];

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Activations</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">
            Sync segment members to downstream destinations.
          </p>
        </div>
        <Button icon={<Plus className="w-4 h-4" />} variant="secondary" disabled>
          New Activation
        </Button>
      </div>

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
              title="No activations yet"
              description="Create an activation once you have segments and destinations configured."
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
    </div>
  );
}

