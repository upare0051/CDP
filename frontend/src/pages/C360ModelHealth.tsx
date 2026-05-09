import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Activity, RefreshCw, Search } from 'lucide-react';
import { getC360ModelHealth, type C360ModelHealthRow } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/Card';

function statusLabel(status: string) {
  if (status === 'ok') return 'OK';
  if (status === 'stale') return 'Stale';
  return 'Unknown';
}

function statusClass(status: string) {
  if (status === 'ok') return 'text-emerald-700 dark:text-emerald-400 font-semibold';
  if (status === 'stale') return 'text-red-600 dark:text-red-400 font-semibold';
  return 'text-amber-700 dark:text-amber-400 font-semibold';
}

function RowTable({ rows, title }: { rows: C360ModelHealthRow[]; title: string }) {
  return (
    <div className="overflow-x-auto border border-neutral-200 dark:border-neutral-800 rounded-md">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="table-header border-b border-neutral-200 dark:border-neutral-800">
            <th className="table-cell">Status</th>
            <th className="table-cell">Schema</th>
            <th className="table-cell">Table</th>
            <th className="table-cell">Type</th>
            <th className="table-cell">Watermark</th>
            <th className="table-cell">View SQL</th>
            <th className="table-cell">Last refresh (PST)</th>
            <th className="table-cell">Error</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.unique_id} className="table-row">
              <td className={`table-cell ${statusClass(r.status)}`}>{statusLabel(r.status)}</td>
              <td className="table-cell font-mono text-xs">{r.schema}</td>
              <td className="table-cell font-mono text-xs">{r.table || r.alias || r.name}</td>
              <td className="table-cell text-xs uppercase tracking-wide">{r.resource_type}</td>
              <td className="table-cell font-mono text-xs">{r.watermark_column ?? '—'}</td>
              <td className="table-cell align-top max-w-[14rem]">
                {r.watermark_sql ? (
                  <details className="text-xs">
                    <summary className="cursor-pointer font-semibold uppercase tracking-wide text-black dark:text-white underline decoration-1 underline-offset-2">
                      View SQL
                    </summary>
                    <pre className="mt-2 p-2 rounded-md bg-neutral-100 dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-700 whitespace-pre-wrap break-all font-mono text-[11px] leading-snug max-h-48 overflow-y-auto">
                      {r.watermark_sql}
                    </pre>
                  </details>
                ) : (
                  '—'
                )}
              </td>
              <td className="table-cell text-xs whitespace-nowrap">
                {r.last_refreshed_at_pst ?? '—'}
              </td>
              <td className="table-cell text-xs text-red-600 dark:text-red-300 max-w-xs truncate" title={r.error ?? ''}>
                {r.error ?? '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="px-4 py-2 text-xs text-neutral-500 border-t border-neutral-200 dark:border-neutral-800">
        {title}
      </div>
    </div>
  );
}

export default function C360ModelHealth() {
  const [q, setQ] = useState('');
  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ['c360ModelHealth'],
    queryFn: getC360ModelHealth,
    staleTime: 60_000,
  });

  const filtered = useMemo(() => {
    const rows = data?.upstream ?? [];
    const s = q.trim().toLowerCase();
    if (!s) return rows;
    return rows.filter((r) => {
      const blob = `${r.schema} ${r.alias ?? ''} ${r.name ?? ''} ${r.unique_id}`.toLowerCase();
      return blob.includes(s);
    });
  }, [data, q]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold uppercase tracking-wider text-black dark:text-white">
            C360 model health
          </h1>
          <p className="text-sm text-neutral-600 dark:text-neutral-400 max-w-3xl mt-1">
            Upstream dbt models and snapshots for{' '}
            <code className="font-mono text-xs bg-neutral-100 dark:bg-neutral-900 px-1 py-0.5 rounded">
              gold.customer_unified_attr
            </code>{' '}
            (ThoughtSpot / DA consumption). Stale = watermark before start of today in{' '}
            <strong>America/Los_Angeles</strong>.
          </p>
        </div>
        <button
          type="button"
          onClick={() => refetch()}
          disabled={isFetching}
          className="inline-flex items-center gap-2 rounded-full border border-black dark:border-white px-4 py-2 text-xs font-semibold uppercase tracking-wider hover:bg-neutral-100 dark:hover:bg-neutral-900 disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${isFetching ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {isLoading && (
        <div className="text-sm text-neutral-500 flex items-center gap-2">
          <Activity className="w-4 h-4 animate-pulse" />
          Loading model health (many Redshift probes; can take up to a few minutes)…
        </div>
      )}

      {isError && (
        <div className="rounded-md border border-red-300 bg-red-50 dark:bg-red-950/30 px-4 py-3 text-sm text-red-800 dark:text-red-200">
          {(error as Error)?.message || 'Failed to load model health'}
        </div>
      )}

      {data && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Card>
              <CardHeader className="py-3">
                <CardTitle className="text-xs uppercase tracking-wider">As of (PST)</CardTitle>
              </CardHeader>
              <CardContent className="pt-0 text-sm font-mono">{data.as_of_pst}</CardContent>
            </Card>
            <Card>
              <CardHeader className="py-3">
                <CardTitle className="text-xs uppercase tracking-wider">OK today</CardTitle>
              </CardHeader>
              <CardContent className="pt-0 text-2xl font-semibold">{data.summary.ok}</CardContent>
            </Card>
            <Card>
              <CardHeader className="py-3">
                <CardTitle className="text-xs uppercase tracking-wider text-red-600">Stale</CardTitle>
              </CardHeader>
              <CardContent className="pt-0 text-2xl font-semibold text-red-600">{data.summary.stale}</CardContent>
            </Card>
            <Card>
              <CardHeader className="py-3">
                <CardTitle className="text-xs uppercase tracking-wider text-amber-700">Unknown</CardTitle>
              </CardHeader>
              <CardContent className="pt-0 text-2xl font-semibold text-amber-700">{data.summary.unknown}</CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm uppercase tracking-wider">ThoughtSpot terminal</CardTitle>
            </CardHeader>
            <CardContent>
              <RowTable rows={[data.terminal_thoughtspot_table]} title="DA-facing wide table" />
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between space-y-0">
              <CardTitle className="text-sm uppercase tracking-wider">
                Upstream models ({data.summary.upstream_total})
              </CardTitle>
              <div className="flex items-center gap-2 px-3 py-2 border border-neutral-300 dark:border-neutral-700 rounded-md bg-white dark:bg-black w-full sm:w-72">
                <Search className="w-4 h-4 text-neutral-500" />
                <input
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  placeholder="Filter by name…"
                  className="flex-1 bg-transparent text-sm outline-none placeholder:text-neutral-400"
                />
              </div>
            </CardHeader>
            <CardContent>
              <RowTable
                rows={filtered}
                title="From dbt manifest parent closure (models + snapshots only; br_rs_* excluded). Regenerate JSON after graph changes."
              />
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
