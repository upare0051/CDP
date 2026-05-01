import { useEffect, useMemo, useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import type { AxiosError } from 'axios';
import { Database, Play, GitBranch, LayoutGrid, Braces, Sparkles } from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/Card';
import Input from '@/components/Input';
import Button from '@/components/Button';
import Select from '@/components/Select';
import { PageLoader } from '@/components/LoadingSpinner';
import {
  getExplorerSchema,
  getExplorerErd,
  runExplorerQuery,
} from '@/lib/api';
import { cn } from '@/lib/utils';
import LineageDiagram, { type LineageModel } from '@/components/LineageDiagram';
import { LINEAGE_EDGES, UPSTREAM_TABLES } from '@/data/c360_lineage';
import '@/styles/reference.css';

const starterQuery = `SELECT *
FROM gold.customer_rfm_fact
LIMIT 50`;

type ExplorerTab = 'query' | 'catalog' | 'relationships';
type TeamKey = 'all' | 'cs' | 'sales' | 'da' | 'ds';

const TEAM_TEMPLATES = [
  {
    id: 'profiles-latest',
    team: 'cs',
    name: 'CS: Latest RFM rows',
    description: 'Quick look at recent customers in the governed RFM mart.',
    sql: `SELECT *
FROM gold.customer_rfm_fact
LIMIT 200`,
  },
  {
    id: 'sales-high-ltv',
    team: 'sales',
    name: 'Sales: Top customers by monetary score',
    description: 'Use the RFM mart to find top customers by monetary bucket/score.',
    sql: `SELECT *
FROM gold.customer_rfm_fact
LIMIT 200`,
  },
  {
    id: 'da-attribute-coverage',
    team: 'da',
    name: 'DA: Unified attributes sample',
    description: 'Inspect the unified attribute mart structure.',
    sql: `SELECT *
FROM gold.customer_unified_attr
LIMIT 200`,
  },
  {
    id: 'ds-event-distribution',
    team: 'ds',
    name: 'DS: Order line fact sample',
    description: 'Inspect order line distributions in the governed fact table.',
    sql: `SELECT *
FROM gold.order_line_fact
LIMIT 200`,
  },
] as const;

export default function DataExplorer() {
  const [activeTab, setActiveTab] = useState<ExplorerTab>('query');
  const [selectedTeam, setSelectedTeam] = useState<TeamKey>('all');
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [sql, setSql] = useState(starterQuery);
  const [queryLimit, setQueryLimit] = useState(500);

  const { data: schemaData, isLoading: schemaLoading } = useQuery({
    queryKey: ['explorerSchema'],
    queryFn: getExplorerSchema,
  });

  const { data: erdData } = useQuery({
    queryKey: ['explorerErd'],
    queryFn: getExplorerErd,
  });
  const queryMutation = useMutation({
    mutationFn: ({ query, limit }: { query: string; limit: number }) => runExplorerQuery(query, limit),
  });

  const tables = schemaData?.tables || [];
  const selectedTableObj = tables.find((t) => t.table_reference === selectedTable) || null;

  const relationshipCount = useMemo(() => erdData?.edges?.length || 0, [erdData]);
  const totalRows = useMemo(
    () => tables.reduce((acc, t) => acc + (typeof t.row_count === 'number' ? t.row_count : 0), 0),
    [tables]
  );
  const filteredTemplates = useMemo(
    () => TEAM_TEMPLATES.filter((tpl) => selectedTeam === 'all' || tpl.team === selectedTeam),
    [selectedTeam]
  );

  const lineageModels: LineageModel[] = useMemo(() => {
    const byId = new Map<string, LineageModel>();

    for (const t of tables) {
      // `table_reference` is schema-qualified (e.g., `gold.customer_rfm_fact`)
      const id = t.table_reference.split('.').pop() || t.table_reference;
      byId.set(id, {
        id,
        name: id,
        columns: (t.columns || []).map((c) => ({ name: c.name, type: c.type })),
      });
    }

    const upstreamIds = new Set<string>([
      ...UPSTREAM_TABLES.bronze.map((t) => t.id),
      ...UPSTREAM_TABLES.silver.map((t) => t.id),
    ]);

    // Ensure all lineage endpoints exist (some models may not be in the allowlisted schema response)
    for (const e of LINEAGE_EDGES) {
      for (const id of [e.from, e.to]) {
        if (upstreamIds.has(id)) continue;
        if (!byId.has(id)) {
          byId.set(id, { id, name: id, columns: [] });
        }
      }
    }

    return Array.from(byId.values());
  }, [tables]);

  useEffect(() => {
    if (!selectedTable && tables.length > 0) {
      setSelectedTable(tables[0].table_reference);
    }
  }, [selectedTable, tables]);

  if (schemaLoading) return <PageLoader />;

  const runQuery = () => {
    queryMutation.mutate({ query: sql, limit: queryLimit });
  };

  const queryError = queryMutation.error as AxiosError<{ detail?: string }> | null;
  const queryErrorMessage =
    queryError?.response?.data?.detail || queryError?.message || null;

  const tabs: { key: ExplorerTab; label: string; icon: JSX.Element }[] = [
    { key: 'query', label: 'Query Studio', icon: <Braces className="w-4 h-4" /> },
    { key: 'catalog', label: 'Table Catalog', icon: <LayoutGrid className="w-4 h-4" /> },
    { key: 'relationships', label: 'Relationships', icon: <GitBranch className="w-4 h-4" /> },
  ];

  const insertTableQuery = (tableReference: string) => {
    setSql(`SELECT *\nFROM ${tableReference}\nLIMIT 100`);
    setActiveTab('query');
  };
  const applyTemplate = (templateSql: string) => {
    setSql(templateSql);
    setActiveTab('query');
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="space-y-1">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Data Explorer</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">
            Explore allowlisted marts and run governed, read-only SQL.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <Database className="w-5 h-5 text-primary-600" />
              <div>
                <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Tables</p>
                <p className="text-xl font-semibold text-gray-900 dark:text-white">{tables.length}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <GitBranch className="w-5 h-5 text-primary-600" />
              <div>
                <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">ERD Links</p>
                <p className="text-xl font-semibold text-gray-900 dark:text-white">{relationshipCount}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <Sparkles className="w-5 h-5 text-primary-600" />
              <div>
                <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Known Rows</p>
                <p className="text-xl font-semibold text-gray-900 dark:text-white">{totalRows.toLocaleString()}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="pb-0">
          <div className="border-b border-gray-200 dark:border-gray-800">
            <nav className="flex items-center gap-2 overflow-x-auto pb-3">
              {tabs.map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={cn(
                    'inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                    activeTab === tab.key
                      ? 'bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300'
                      : 'text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800'
                  )}
                >
                  {tab.icon}
                  {tab.label}
                </button>
              ))}
            </nav>
          </div>
        </CardHeader>

        <CardContent className="pt-6">
          {activeTab === 'query' && (
            <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
              <div className="xl:col-span-8 space-y-6">
                <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
                  <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex flex-wrap items-end gap-3">
                    <Input
                      type="number"
                      value={queryLimit}
                      onChange={(e) => setQueryLimit(parseInt(e.target.value || '500', 10))}
                      className="w-28"
                      min={1}
                      max={5000}
                      label="Row limit"
                    />
                    <div className="pb-0.5">
                      <Button onClick={runQuery} loading={queryMutation.isPending} icon={<Play className="w-4 h-4" />}>
                        Run Query
                      </Button>
                    </div>
                  </div>

                  <div className="p-4">
                    <textarea
                      value={sql}
                      onChange={(e) => setSql(e.target.value)}
                      className="w-full min-h-[260px] p-4 font-mono text-sm leading-6 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-gray-900 dark:text-gray-100"
                    />

                    {queryErrorMessage && (
                      <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-900/20 dark:text-red-300">
                        {queryErrorMessage}
                      </div>
                    )}
                  </div>
                </div>

                <div className="rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden bg-white dark:bg-gray-900">
                  <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
                    <p className="text-sm font-semibold text-gray-900 dark:text-white">Results</p>
                    {queryMutation.data ? (
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                        {queryMutation.data.row_count}
                        {queryMutation.data.truncated ? '+' : ''} rows returned . {queryMutation.data.columns.length} columns
                      </p>
                    ) : (
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                        Run query to view result table.
                      </p>
                    )}
                  </div>

                  {queryMutation.data ? (
                    <div className="overflow-x-auto">
                      <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                        <thead className="bg-gray-50 dark:bg-gray-800">
                          <tr>
                            {queryMutation.data.columns.map((c) => (
                              <th
                                key={c}
                                className="px-4 py-2 text-left text-xs font-semibold text-gray-600 dark:text-gray-300 uppercase"
                              >
                                {c}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody className="bg-white dark:bg-gray-900 divide-y divide-gray-200 dark:divide-gray-700">
                          {queryMutation.data.rows.map((row, idx) => (
                            <tr key={idx}>
                              {row.map((cell, cellIdx) => (
                                <td key={cellIdx} className="px-4 py-2 text-sm text-gray-700 dark:text-gray-300">
                                  {cell === null ? 'NULL' : String(cell)}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="p-6 text-sm text-gray-500 dark:text-gray-400">No results yet.</div>
                  )}
                </div>
              </div>

              <div className="xl:col-span-4 space-y-4">
                <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                  <p className="text-sm font-semibold text-gray-900 dark:text-white">Team Templates</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 mb-3">
                    Prebuilt SQL for CS/Sales/DA/DS workflows.
                  </p>
                  <Select
                    options={[
                      { value: 'all', label: 'All teams' },
                      { value: 'cs', label: 'CS' },
                      { value: 'sales', label: 'Sales' },
                      { value: 'da', label: 'DA' },
                      { value: 'ds', label: 'DS' },
                    ]}
                    value={selectedTeam}
                    onChange={(e) => setSelectedTeam(e.target.value as TeamKey)}
                  />
                  <div className="space-y-2 max-h-[220px] overflow-y-auto mt-3">
                    {filteredTemplates.map((template) => (
                      <div
                        key={template.id}
                        className="rounded-md border border-gray-200 dark:border-gray-700 px-3 py-2"
                      >
                        <p className="text-sm font-medium text-gray-900 dark:text-white">{template.name}</p>
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{template.description}</p>
                        <Button
                          size="sm"
                          variant="secondary"
                          className="mt-2"
                          onClick={() => applyTemplate(template.sql)}
                        >
                          Apply
                        </Button>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                  <p className="text-sm font-semibold text-gray-900 dark:text-white">Quick Inserts</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 mb-3">
                    Click a table to start a query quickly.
                  </p>
                  <div className="space-y-2 max-h-[260px] overflow-y-auto">
                    {tables.slice(0, 20).map((table) => (
                      <button
                        key={table.table_reference}
                        onClick={() => insertTableQuery(table.table_reference)}
                        className="w-full text-left rounded-md border border-gray-200 dark:border-gray-700 px-3 py-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-800"
                      >
                        <span className="font-medium">{table.table}</span>
                        <span className="text-xs text-gray-500 dark:text-gray-400 ml-2">{table.catalog}</span>
                      </button>
                    ))}
                  </div>
                </div>

              </div>
            </div>
          )}

          {activeTab === 'catalog' && (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              <div className="lg:col-span-5">
                <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                  <p className="text-sm font-semibold text-gray-900 dark:text-white mb-3">Tables</p>
                  <div className="space-y-2 max-h-[500px] overflow-y-auto">
                    {tables.map((table) => (
                      <button
                        key={table.table_reference}
                        onClick={() => setSelectedTable(table.table_reference)}
                        className={cn(
                          'w-full text-left p-3 rounded-lg border transition-colors',
                          selectedTable === table.table_reference
                            ? 'border-primary-400 bg-primary-50 dark:bg-primary-900/20'
                            : 'border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800'
                        )}
                      >
                        <div className="flex items-center justify-between">
                          <p className="font-medium text-gray-900 dark:text-white">{table.table}</p>
                          <span className="text-xs text-gray-500 dark:text-gray-400">
                            {table.row_count ?? '-'} rows
                          </span>
                        </div>
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                          {table.columns.length} columns . {table.catalog}
                        </p>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
              <div className="lg:col-span-7">
                <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4 min-h-[500px]">
                  <div className="flex items-center justify-between gap-3 mb-4">
                    <p className="text-sm font-semibold text-gray-900 dark:text-white">
                      {selectedTableObj?.table_reference || 'Select a table'}
                    </p>
                    {selectedTableObj && (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => insertTableQuery(selectedTableObj.table_reference)}
                      >
                        Query This Table
                      </Button>
                    )}
                  </div>
                  {selectedTableObj ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2 max-h-[430px] overflow-y-auto">
                      {selectedTableObj.columns.map((col) => (
                        <div key={col.name} className="text-sm p-2 rounded bg-gray-50 dark:bg-gray-800">
                          <span className="font-medium text-gray-900 dark:text-white">{col.name}</span>
                          <span className="text-gray-500 dark:text-gray-400 ml-2">{col.type}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-gray-500 dark:text-gray-400">Pick a table to inspect its columns.</p>
                  )}
                </div>
              </div>
            </div>
          )}

          {activeTab === 'relationships' && (
            <div className="space-y-4">
              <LineageDiagram models={lineageModels} />
              <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                <p className="text-sm font-semibold text-gray-900 dark:text-white mb-1">ERD Hints</p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Inferred using *_id naming conventions. These are guidance hints, not strict FK constraints.
                </p>
              </div>
              <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                <div className="max-h-[460px] overflow-y-auto space-y-2">
                  {(erdData?.edges || []).map((edge, idx) => (
                    <div
                      key={idx}
                      className="text-sm text-gray-700 dark:text-gray-300 p-3 bg-gray-50 dark:bg-gray-800 rounded border border-gray-100 dark:border-gray-700"
                    >
                      <span className="font-medium">{edge.from_table}.{edge.from_column}</span>
                      {' -> '}
                      <span className="font-medium">{edge.to_table}.{edge.to_column}</span>
                    </div>
                  ))}
                  {relationshipCount === 0 && (
                    <p className="text-sm text-gray-500 dark:text-gray-400">No inferred relationships found.</p>
                  )}
                </div>
              </div>
            </div>
          )}

        </CardContent>
      </Card>
    </div>
  );
}
