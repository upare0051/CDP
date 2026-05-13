/**
 * Cube-powered segment builder.
 *
 * Pulls the model graph from /api/v1/cube/meta and lets the marketer:
 *   1. Pick a view (e.g. customer_marketing, customer_unified, customer_360).
 *   2. Choose which dimensions to return (customer_id + identifying fields).
 *   3. Add filters (member + operator + values).
 *   4. Set a row limit.
 *
 * The resulting payload is the Cube /load body shape, which the backend
 * stores verbatim as `segment.cube_query` and the preview/sync paths use
 * as-is.
 */
import { useEffect, useMemo, useState } from 'react';
import { useQueries, useQuery } from '@tanstack/react-query';
import { BarChart3, Layers, Plus, X, Database } from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  getCubeMeta,
  previewSegmentCube,
  type CubeMetaCube,
  type CubeQuery,
  type CubeQueryFilter,
} from '@/lib/api';

type Props = {
  value: CubeQuery;
  onChange: (q: CubeQuery) => void;
};

// Operators Cube's REST API understands. Subset that covers the demo audiences.
const CUBE_OPERATORS: Record<string, { value: string; label: string; multi?: boolean }[]> = {
  string: [
    { value: 'equals', label: 'equals', multi: true },
    { value: 'notEquals', label: 'does not equal', multi: true },
    { value: 'contains', label: 'contains', multi: true },
    { value: 'notContains', label: 'does not contain', multi: true },
    { value: 'startsWith', label: 'starts with', multi: true },
    { value: 'endsWith', label: 'ends with', multi: true },
    { value: 'set', label: 'is set' },
    { value: 'notSet', label: 'is not set' },
  ],
  number: [
    { value: 'equals', label: '=', multi: true },
    { value: 'notEquals', label: '!=', multi: true },
    { value: 'gt', label: '>' },
    { value: 'gte', label: '>=' },
    { value: 'lt', label: '<' },
    { value: 'lte', label: '<=' },
    { value: 'set', label: 'is set' },
    { value: 'notSet', label: 'is not set' },
  ],
  boolean: [
    { value: 'equals', label: 'equals', multi: true },
    { value: 'set', label: 'is set' },
    { value: 'notSet', label: 'is not set' },
  ],
  time: [
    { value: 'beforeDate', label: 'is before' },
    { value: 'afterDate', label: 'is after' },
    { value: 'inDateRange', label: 'in range', multi: true },
    { value: 'set', label: 'is set' },
    { value: 'notSet', label: 'is not set' },
  ],
};

// Views the audience UI prefers (recommended order). Other cubes still
// selectable from the dropdown but the views are surfaced first.
const PREFERRED_VIEWS = ['customer_unified', 'customer_marketing', 'customer_360'];

function operatorsFor(type: string) {
  return CUBE_OPERATORS[type] ?? CUBE_OPERATORS.string;
}

function memberType(cube: CubeMetaCube | null, memberName: string): string {
  if (!cube) return 'string';
  const all = [...(cube.dimensions ?? []), ...(cube.measures ?? [])];
  return all.find((m) => m.name === memberName)?.type ?? 'string';
}

function formatCompact(n: number | null | undefined) {
  if (n === null || n === undefined || !Number.isFinite(n)) return '—';
  return Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 }).format(n);
}

function filterNeedsValue(filter: CubeQueryFilter) {
  return !['set', 'notSet'].includes(filter.operator);
}

function filterHasValue(filter: CubeQueryFilter) {
  return !filterNeedsValue(filter) || (filter.values?.length ?? 0) > 0;
}

export default function CubeSegmentBuilder({ value, onChange }: Props) {
  const { data: meta, isLoading, error } = useQuery({
    queryKey: ['cube-meta'],
    queryFn: getCubeMeta,
    staleTime: 60_000,
  });

  // Sort: preferred views first, then other views, then cubes (alphabetical).
  const orderedCubes = useMemo(() => {
    const list = meta?.cubes ?? [];
    return [...list].sort((a, b) => {
      const ap = PREFERRED_VIEWS.indexOf(a.name);
      const bp = PREFERRED_VIEWS.indexOf(b.name);
      if (ap !== -1 || bp !== -1) {
        return (ap === -1 ? 99 : ap) - (bp === -1 ? 99 : bp);
      }
      const aV = a.type === 'view' ? 0 : 1;
      const bV = b.type === 'view' ? 0 : 1;
      if (aV !== bV) return aV - bV;
      return a.name.localeCompare(b.name);
    });
  }, [meta]);

  // The selected source cube/view is inferred from the first dimension/filter.
  const initialCube = useMemo(() => {
    const fromDim = value.dimensions?.[0]?.split('.')[0];
    const fromFilter = value.filters?.[0]?.member?.split('.')[0];
    return fromDim || fromFilter || PREFERRED_VIEWS[0];
  }, [value]);

  const [selectedCube, setSelectedCube] = useState<string>(initialCube);
  useEffect(() => {
    setSelectedCube(initialCube);
  }, [initialCube]);

  const cube = useMemo(
    () => orderedCubes.find((c) => c.name === selectedCube) ?? null,
    [orderedCubes, selectedCube],
  );

  const availableDimensions = cube?.dimensions ?? [];
  const availableMeasures = cube?.measures ?? [];

  const selectedDims = value.dimensions ?? [];
  const filters = value.filters ?? [];

  const funnelQueries = useQueries({
    queries: filters.map((_, index) => {
      const prefix = filters.slice(0, index + 1);
      const complete = prefix.every(filterHasValue);
      const query: CubeQuery = {
        ...value,
        filters: prefix,
        // The backend computes count independently; keep payload row extraction tiny.
        limit: 1,
      };
      return {
        queryKey: ['cube-filter-funnel', selectedCube, JSON.stringify(query)],
        queryFn: () => previewSegmentCube(query),
        enabled: Boolean(meta) && complete && prefix.length > 0,
        retry: 0,
        staleTime: 30_000,
      };
    }),
  });

  const funnelCounts = funnelQueries.map((q) => q.data?.count ?? null);
  const maxFunnelCount = Math.max(1, ...funnelCounts.filter((n): n is number => typeof n === 'number'));

  // -------------------------------------------------------------------------
  // Mutators
  // -------------------------------------------------------------------------
  const setCube = (cubeName: string) => {
    setSelectedCube(cubeName);
    // Reset selections when switching to a different cube/view to avoid
    // stale member references.
    onChange({
      dimensions: [],
      filters: [],
      limit: value.limit ?? 1000,
    });
  };

  const toggleDimension = (name: string) => {
    const isSelected = selectedDims.includes(name);
    const next = isSelected ? selectedDims.filter((d) => d !== name) : [...selectedDims, name];
    onChange({ ...value, dimensions: next });
  };

  const addFilter = () => {
    if (!availableDimensions[0]) return;
    const first = availableDimensions[0];
    const ops = operatorsFor(first.type);
    onChange({
      ...value,
      filters: [
        ...filters,
        { member: first.name, operator: ops[0].value, values: [] },
      ],
    });
  };

  const updateFilter = (index: number, patch: Partial<CubeQueryFilter>) => {
    const next = filters.map((f, i) => (i === index ? { ...f, ...patch } : f));
    onChange({ ...value, filters: next });
  };

  const removeFilter = (index: number) => {
    onChange({ ...value, filters: filters.filter((_, i) => i !== index) });
  };

  const setLimit = (n: number) => onChange({ ...value, limit: n });

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------
  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400 py-6">
        <Database className="w-4 h-4 animate-pulse" />
        Loading Cube model…
      </div>
    );
  }

  if (error || !meta) {
    return (
      <div className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3">
        Failed to load Cube model. Check that the Cube container is running
        and /api/v1/cube/meta is reachable.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Source picker */}
      <div>
        <label className="block text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-2">
          Source view
        </label>
        <select
          value={selectedCube}
          onChange={(e) => setCube(e.target.value)}
          className={cn(
            'w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg',
            'text-sm text-gray-900 dark:text-gray-100',
            'focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500',
          )}
        >
          {orderedCubes.map((c) => (
            <option key={c.name} value={c.name}>
              {c.type === 'view' ? '◆ ' : ''}
              {c.title || c.name}
            </option>
          ))}
        </select>
        {cube?.description && (
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1.5">{cube.description}</p>
        )}
      </div>

      {/* Filters */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <div>
            <label className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
              Filters
            </label>
            {filters.length > 0 && (
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                Funnel counts show remaining records after each condition.
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={addFilter}
            className="inline-flex items-center gap-1 text-sm text-primary-600 dark:text-primary-400 hover:text-primary-700 dark:hover:text-primary-300"
          >
            <Plus className="w-4 h-4" />
            Add filter
          </button>
        </div>
        {filters.length === 0 && (
          <p className="text-sm text-gray-500 dark:text-gray-400 italic">
            No filters — all rows in the view will match.
          </p>
        )}
        <div className="space-y-3">
          {filters.map((f, i) => {
            const t = memberType(cube, f.member);
            const ops = operatorsFor(t);
            const op = ops.find((o) => o.value === f.operator) ?? ops[0];
            const valuesStr = (f.values ?? []).join(',');
            const noValueOps = ['set', 'notSet'];
            const count = funnelCounts[i];
            const queryState = funnelQueries[i];
            const isComplete = filterHasValue(f);
            const widthPct = count === null ? 100 : Math.max(12, Math.round((count / maxFunnelCount) * 100));
            const clause = i === 0 ? 'WHERE' : 'AND';
            return (
              <div
                key={i}
                className="grid grid-cols-[72px_minmax(0,1fr)_220px] items-stretch gap-3 animate-fade-in"
              >
                <div className="flex items-center justify-center rounded-lg border border-gray-200 dark:border-gray-800 bg-white dark:bg-black">
                  <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-gray-700 dark:text-gray-300">
                    {clause}
                  </span>
                </div>

                <div className="flex items-center gap-2 p-2 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700 min-w-0">
                  <select
                    value={f.member}
                    onChange={(e) => updateFilter(i, { member: e.target.value })}
                    className="flex-1 min-w-[180px] px-2 py-1.5 text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded"
                  >
                    {availableDimensions.map((d) => (
                      <option key={d.name} value={d.name}>
                        {d.shortTitle || d.name.split('.').slice(-1)[0]}
                      </option>
                    ))}
                  </select>
                  <select
                    value={f.operator}
                    onChange={(e) => updateFilter(i, { operator: e.target.value })}
                    className="px-2 py-1.5 text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded"
                  >
                    {ops.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                  {!noValueOps.includes(f.operator) && (
                    <input
                      type="text"
                      value={valuesStr}
                      onChange={(e) => {
                        const vals = e.target.value
                          .split(',')
                          .map((v) => v.trim())
                          .filter(Boolean);
                        updateFilter(i, { values: vals });
                      }}
                      placeholder={op?.multi ? 'value1, value2 …' : 'value'}
                      className="flex-1 min-w-[160px] px-2 py-1.5 text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded"
                    />
                  )}
                  <button
                    type="button"
                    onClick={() => removeFilter(i)}
                    className="p-1.5 text-gray-400 hover:text-red-500 dark:hover:text-red-400"
                    aria-label="Remove filter"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>

                <div className="rounded-lg border border-gray-200 dark:border-gray-800 bg-white dark:bg-black p-3">
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                      <BarChart3 className="w-3.5 h-3.5" />
                      Remaining
                    </div>
                    <span className="text-sm font-semibold text-gray-900 dark:text-white">
                      {!isComplete
                        ? '—'
                        : queryState?.isLoading
                          ? '...'
                          : formatCompact(count)}
                    </span>
                  </div>
                  <div className="h-8 border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 flex items-center px-1.5">
                    <div
                      className={cn(
                        'h-4 bg-black dark:bg-white transition-all duration-300',
                        queryState?.isError && 'bg-red-500 dark:bg-red-400',
                        !isComplete && 'bg-gray-300 dark:bg-gray-700',
                      )}
                      style={{ width: `${!isComplete ? 100 : widthPct}%` }}
                    />
                  </div>
                  <p className="mt-1.5 text-[11px] text-gray-500 dark:text-gray-400">
                    {queryState?.isError
                      ? 'Count unavailable'
                      : i === 0
                        ? 'After first condition'
                        : `After ${i + 1} conditions`}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Dimensions */}
      <div>
        <label className="block text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-2">
          Return columns ({selectedDims.length} selected)
        </label>
        <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">
          Choose the fields this audience should expose to downstream syncs.
        </p>
        <div className="flex flex-wrap gap-1.5 max-h-48 overflow-y-auto p-2 border border-gray-200 dark:border-gray-700 rounded-lg">
          {availableDimensions.map((d) => {
            const isOn = selectedDims.includes(d.name);
            return (
              <button
                key={d.name}
                type="button"
                onClick={() => toggleDimension(d.name)}
                className={cn(
                  'inline-flex items-center gap-1 px-2 py-1 text-xs rounded transition-colors',
                  isOn
                    ? 'bg-primary-100 dark:bg-primary-900/40 text-primary-700 dark:text-primary-300 border border-primary-300 dark:border-primary-700'
                    : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 border border-transparent hover:bg-gray-200 dark:hover:bg-gray-700',
                )}
                title={d.name}
              >
                <Layers className="w-3 h-3" />
                {d.shortTitle || d.name.split('.').slice(-1)[0]}
              </button>
            );
          })}
        </div>
      </div>

      {/* Limit + measures (optional) */}
      <div className="flex items-end gap-3">
        <div className="flex-1">
          <label className="block text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-2">
            Row limit
          </label>
          <input
            type="number"
            min={1}
            value={value.limit ?? 1000}
            onChange={(e) => setLimit(Math.max(1, parseInt(e.target.value || '0', 10)))}
            className="w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-sm"
          />
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Cap on rows returned. Audience count is computed independently of this.
          </p>
        </div>
        <div className="text-xs text-gray-500 dark:text-gray-400 pb-2">
          {availableMeasures.length} measures available (use for analytics, not row-level audiences)
        </div>
      </div>
    </div>
  );
}
