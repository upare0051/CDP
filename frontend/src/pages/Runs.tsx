import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  History,
  CheckCircle,
  XCircle,
  Clock,
  Loader2,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { Card, CardContent, CardHeader } from '@/components/Card';
import Select from '@/components/Select';
import StatusBadge from '@/components/StatusBadge';
import EmptyState from '@/components/EmptyState';
import { PageLoader } from '@/components/LoadingSpinner';
import { getRuns, getSyncs } from '@/lib/api';
import { formatDate, formatDuration, formatNumber, cn } from '@/lib/utils';

export default function Runs() {
  const [selectedJob, setSelectedJob] = useState<string>('');
  const [expandedRun, setExpandedRun] = useState<string | null>(null);

  const { data: syncs } = useQuery({ queryKey: ['syncs'], queryFn: getSyncs });
  const { data: runs, isLoading } = useQuery({
    queryKey: ['runs', selectedJob],
    queryFn: () => getRuns(selectedJob ? parseInt(selectedJob) : undefined, 100),
  });

  if (isLoading) return <PageLoader />;

  const statusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-5 h-5 text-green-400" />;
      case 'failed':
        return <XCircle className="w-5 h-5 text-red-400" />;
      case 'running':
        return <Loader2 className="w-5 h-5 text-blue-400 animate-spin" />;
      default:
        return <Clock className="w-5 h-5 text-yellow-400" />;
    }
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-surface-50 mb-2">Run History</h1>
          <p className="text-surface-400">View sync execution history and logs</p>
        </div>
        <div className="w-64">
          <Select
            options={[
              { value: '', label: 'All Sync Jobs' },
              ...(syncs?.map(s => ({ value: String(s.id), label: s.name })) || []),
            ]}
            value={selectedJob}
            onChange={(e) => setSelectedJob(e.target.value)}
          />
        </div>
      </div>

      {runs && runs.length > 0 ? (
        <div className="space-y-3">
          {runs.map((run) => (
            <Card key={run.id} className="overflow-hidden">
              <div
                className="flex items-center justify-between px-6 py-4 cursor-pointer hover:bg-surface-800/30 transition-colors"
                onClick={() => setExpandedRun(expandedRun === run.run_id ? null : run.run_id)}
              >
                <div className="flex items-center gap-4">
                  {statusIcon(run.status)}
                  <div>
                    <p className="font-medium text-surface-100">{run.sync_job_name}</p>
                    <p className="text-sm text-surface-500">
                      Run ID: <span className="font-mono">{run.run_id.slice(0, 8)}</span>
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-6">
                  <div className="text-right">
                    <p className="text-sm text-surface-200">{formatDate(run.started_at)}</p>
                    <p className="text-xs text-surface-500">
                      Duration: {formatDuration(run.duration_seconds)}
                    </p>
                  </div>

                  <div className="grid grid-cols-3 gap-4 text-center">
                    <div>
                      <p className="text-lg font-semibold text-surface-100">{formatNumber(run.rows_read)}</p>
                      <p className="text-xs text-surface-500">Read</p>
                    </div>
                    <div>
                      <p className="text-lg font-semibold text-green-400">{formatNumber(run.rows_synced)}</p>
                      <p className="text-xs text-surface-500">Synced</p>
                    </div>
                    <div>
                      <p className="text-lg font-semibold text-red-400">{formatNumber(run.rows_failed)}</p>
                      <p className="text-xs text-surface-500">Failed</p>
                    </div>
                  </div>

                  <StatusBadge status={run.status} size="sm" />

                  {expandedRun === run.run_id ? (
                    <ChevronUp className="w-5 h-5 text-surface-500" />
                  ) : (
                    <ChevronDown className="w-5 h-5 text-surface-500" />
                  )}
                </div>
              </div>

              {/* Expanded Details */}
              {expandedRun === run.run_id && (
                <div className="px-6 py-4 border-t border-surface-800 bg-surface-900/50">
                  <div className="grid grid-cols-2 gap-6">
                    <div className="space-y-3">
                      <h4 className="text-sm font-medium text-surface-400">Run Details</h4>
                      <div className="space-y-2 text-sm">
                        <div className="flex justify-between">
                          <span className="text-surface-500">Run ID</span>
                          <span className="text-surface-200 font-mono">{run.run_id}</span>
                        </div>
                        {run.airflow_run_id && (
                          <div className="flex justify-between">
                            <span className="text-surface-500">Airflow Run ID</span>
                            <span className="text-surface-200 font-mono">{run.airflow_run_id}</span>
                          </div>
                        )}
                        <div className="flex justify-between">
                          <span className="text-surface-500">Started</span>
                          <span className="text-surface-200">{formatDate(run.started_at)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-surface-500">Completed</span>
                          <span className="text-surface-200">{formatDate(run.completed_at)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-surface-500">Retries</span>
                          <span className="text-surface-200">{run.retry_count}</span>
                        </div>
                        {run.checkpoint_value && (
                          <div className="flex justify-between">
                            <span className="text-surface-500">Checkpoint</span>
                            <span className="text-surface-200 font-mono">{run.checkpoint_value}</span>
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="space-y-3">
                      {run.error_message && (
                        <div>
                          <h4 className="text-sm font-medium text-red-400 mb-2">Error</h4>
                          <p className="text-sm text-surface-300 bg-red-950/30 border border-red-500/20 rounded-lg p-3">
                            {run.error_message}
                          </p>
                        </div>
                      )}

                      {run.logs && (
                        <div>
                          <h4 className="text-sm font-medium text-surface-400 mb-2">Logs</h4>
                          <pre className="text-xs text-surface-300 bg-surface-950 rounded-lg p-3 overflow-x-auto max-h-40 font-mono">
                            {run.logs}
                          </pre>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <EmptyState
            icon={<History className="w-8 h-8" />}
            title="No run history"
            description="Run the first sync to see execution history here."
          />
        </Card>
      )}
    </div>
  );
}
