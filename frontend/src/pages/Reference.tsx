import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import { DataGrid } from '@/components/DataGrid';
import { PageLoader } from '@/components/LoadingSpinner';
import { getC360Schema } from '@/lib/api';
import { MODEL_CATEGORIES, GLOSSARY, MODELS as DBT_MODELS, type ReferenceModel } from '@/data/c360_reference';

import '@/styles/reference.css';

type C360Column = { name: string; type: string };
type C360Table = { table_reference: string; columns: C360Column[] };

function ScdBadge({ type }: { type: string }) {
  const colors: Record<string, string> = { SCD1: '#3b82f6', SCD2: '#8b5cf6', Table: '#10b981' };
  return (
    <span className="ref-scd-badge" style={{ background: colors[type] || '#6b7280' }}>
      {type}
    </span>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      className="ref-copy-btn"
      onClick={() => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
    >
      {copied ? '✓ Copied' : '📋 Copy'}
    </button>
  );
}

function DerivationTooltip({ col, position, onClose }: any) {
  const ref = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const handler = (e: any) => {
      if (ref.current && !ref.current.contains(e.target)) onClose();
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [onClose]);

  if (!col?.source && !col?.logic) return null;
  return (
    <div className="derivation-tooltip" ref={ref} style={position}>
      <div className="dt-header">
        <code className="dt-col-name">{col.name}</code>
        <span className="dt-col-type">{col.type}</span>
      </div>
      {col.source && (
        <div className="dt-section">
          <span className="dt-label">Source</span>
          <span className="dt-value">{col.source}</span>
        </div>
      )}
      {col.logic && (
        <div className="dt-section">
          <span className="dt-label">Logic</span>
          <span className="dt-value dt-logic">{col.logic}</span>
        </div>
      )}
      {col.pk && (
        <div className="dt-badge-row">
          <span className="ref-pk-badge">Primary Key</span>
        </div>
      )}
    </div>
  );
}

function ColumnTable({ columns, filter }: { columns: any[]; filter: string }) {
  const [activeTooltip, setActiveTooltip] = useState<any>(null);
  const [tooltipPos, setTooltipPos] = useState<any>({});

  const filtered = filter
    ? columns.filter(
        (c) => c.name.toLowerCase().includes(filter) || (c.description || '').toLowerCase().includes(filter)
      )
    : columns;

  const rowData = useMemo(
    () =>
      filtered.map((c) => ({
        name: c.name,
        type: c.type,
        description: c.description || '',
        pk: !!c.pk,
        source: c.source || '',
        logic: c.logic || '',
        _raw: c,
      })),
    [filtered]
  );

  const columnDefs = useMemo(
    () => [
      {
        field: 'name',
        headerName: 'Column',
        width: 220,
        sortable: true,
        filter: true,
        cellRenderer: (params: any) => {
          const c = params.data._raw;
          return (
            <span className="ref-col-name" style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              <code>{c.name}</code>
              {c.pk && <span className="ref-pk-badge">PK</span>}
              {(c.source || c.logic) && <span className="ref-derivation-icon" title="Hover for derivation logic">ⓘ</span>}
            </span>
          );
        },
      },
      { field: 'type', headerName: 'Type', width: 120, sortable: true, filter: true },
      { field: 'description', headerName: 'Description', flex: 1, sortable: true, filter: true },
    ],
    []
  );

  const handleCellMouseOver = useCallback((params: any) => {
    const c = params.data?._raw;
    if (!c?.source && !c?.logic) {
      setActiveTooltip(null);
      return;
    }
    const cellEl = params.event?.target;
    if (cellEl) {
      const rect = cellEl.getBoundingClientRect();
      setTooltipPos({ top: rect.bottom + 4, left: Math.min(rect.left, window.innerWidth - 360) });
    }
    setActiveTooltip(c);
  }, []);

  const handleCellMouseOut = useCallback(() => setActiveTooltip(null), []);

  if (filtered.length === 0) return <div className="ref-empty">No columns match filter</div>;

  return (
    <div className="ref-table-wrap">
      <DataGrid
        rows={rowData}
        columnDefs={columnDefs}
        showToolbar={false}
        compact
        className="ref-datagrid"
        onCellMouseOver={handleCellMouseOver}
        onCellMouseOut={handleCellMouseOut}
      />
      {activeTooltip && <DerivationTooltip col={activeTooltip} position={tooltipPos} onClose={() => setActiveTooltip(null)} />}
    </div>
  );
}

function ModelDetail({ model }: any) {
  const [colFilter, setColFilter] = useState('');
  return (
    <section className="ref-model-card" id={`model-${model.id}`}>
      <div className="ref-model-header">
        <h3 className="ref-model-name"><code>{model.name}</code></h3>
        <ScdBadge type={model.scdType} />
      </div>
      <p className="ref-model-overview">{model.overview}</p>
      <div className="ref-model-meta">
        <div className="ref-meta-item">
          <span className="ref-meta-label">Grain</span>
          <span>{model.grain}</span>
        </div>
        <div className="ref-meta-item">
          <span className="ref-meta-label">Sources</span>
          <span>{(model.sources || []).join(' · ')}</span>
        </div>
      </div>
      <div className="ref-columns-section">
        <div className="ref-columns-header">
          <h4>Columns ({model.columns.length})</h4>
          <input
            className="ref-col-filter"
            type="text"
            placeholder="Filter columns…"
            value={colFilter}
            onChange={(e) => setColFilter(e.target.value.toLowerCase())}
          />
        </div>
        <ColumnTable columns={model.columns} filter={colFilter} />
      </div>
      <div className="ref-sql-section">
        <div className="ref-sql-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
          <h4 style={{ margin: 0, fontSize: 14, color: '#1e293b' }}>Sample Query</h4>
          <CopyButton text={model.sampleSql} />
        </div>
        <pre className="ref-sql-block"><code>{model.sampleSql}</code></pre>
      </div>
    </section>
  );
}

export default function Reference() {
  const { data, isLoading } = useQuery({ queryKey: ['c360Schema'], queryFn: getC360Schema });
  const tables: C360Table[] = data?.schema?.tables || [];

  // Build "models" from live Redshift schema, grouped into the same categories as leadership.
  const models = useMemo(() => {
    const docsById = new Map<string, ReferenceModel>(
      (DBT_MODELS as ReferenceModel[]).map((m) => [m.id, m])
    );
    const byName: Record<string, any> = {};
    for (const t of tables) {
      const short = t.table_reference.split('.').slice(-1)[0];
      const docs = docsById.get(short);
      const category =
        docs?.category ||
        (short.includes('order')
          ? 'transactions'
          : short.includes('rfm')
            ? 'rfm-behavior'
            : short.includes('loyalty')
              ? 'loyalty'
              : short.includes('geo')
                ? 'customer-attributes'
                : short.includes('identifier') || short.includes('address') || short.includes('dim')
                  ? 'customer-profile'
                  : 'customer-attributes');

      const docCols = new Map((docs?.columns || []).map((c) => [c.name.toLowerCase(), c]));
      byName[short] = {
        id: short,
        name: short,
        category,
        scdType: docs?.scdType || 'Table',
        grain: docs?.grain || `One row per key in ${t.table_reference}.`,
        overview: docs?.overview || `Live schema for ${t.table_reference} (allowlisted).`,
        sources: docs?.sources || ['gold marts'],
        columns: t.columns.map((c) => {
          const dc = docCols.get(c.name.toLowerCase());
          return {
            name: c.name,
            type: (c.type || '').toUpperCase(),
            description: dc?.description || '',
            pk: !!dc?.pk,
          };
        }),
        sampleSql: docs?.sampleSql || `SELECT *\nFROM ${t.table_reference}\nLIMIT 10;`,
      };
    }
    return Object.values(byName);
  }, [tables]);

  const [search, setSearch] = useState('');
  const [activeCategory, setActiveCategory] = useState<string>('all');

  const modelCount = models.length;
  const columnCount = models.reduce((acc: number, m: any) => acc + (m.columns?.length || 0), 0);

  const filteredModels = useMemo(() => {
    const s = search.trim().toLowerCase();
    return models.filter((m: any) => {
      if (activeCategory !== 'all' && m.category !== activeCategory) return false;
      if (!s) return true;
      return (
        m.name.toLowerCase().includes(s) ||
        (m.overview || '').toLowerCase().includes(s) ||
        (m.columns || []).some((c: any) => c.name.toLowerCase().includes(s))
      );
    });
  }, [models, activeCategory, search]);

  const categories = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const m of models) counts[m.category] = (counts[m.category] || 0) + 1;
    return MODEL_CATEGORIES.map((c: any) => ({ ...c, count: counts[c.id] || 0 }));
  }, [models]);

  if (isLoading) return <PageLoader />;

  return (
    <div className="ref-page">
      <div className="ref-hero">
        <h1>Reference</h1>
        <p className="ref-hero-sub">
          C360 data model reference — live schema from Redshift allowlist, in the same layout as the leadership app.
        </p>
        <div className="ref-stats-row">
          <div className="ref-stat">
            <span className="ref-stat-num">{modelCount}</span>
            <span className="ref-stat-label">Models</span>
          </div>
          <div className="ref-stat">
            <span className="ref-stat-num">{columnCount}</span>
            <span className="ref-stat-label">Columns</span>
          </div>
        </div>
      </div>

      <div className="ref-controls">
        <input className="ref-search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search models, columns, or terms…" />
        <div className="ref-cat-pills">
          <button className={`ref-cat-pill ${activeCategory === 'all' ? 'active' : ''}`} onClick={() => setActiveCategory('all')}>
            <span className="ref-cat-icon">📚</span> All
          </button>
          {categories.map((c: any) => (
            <button
              key={c.id}
              className={`ref-cat-pill ${activeCategory === c.id ? 'active' : ''}`}
              onClick={() => setActiveCategory(c.id)}
            >
              <span className="ref-cat-icon">{c.icon}</span> {c.label}
            </button>
          ))}
        </div>
      </div>

      <div className="ref-layout">
        <aside className="ref-sidebar-nav">
          <div className="ref-sidebar-section">
            <div className="ref-sidebar-title">Models</div>
            {categories.map((c: any) => {
              const group = filteredModels.filter((m: any) => m.category === c.id);
              if (activeCategory !== 'all' && c.id !== activeCategory) return null;
              if (group.length === 0) return null;
              return (
                <div className="ref-sidebar-group" key={c.id}>
                  <div className="ref-sidebar-cat">{c.label}</div>
                  {group.map((m: any) => (
                    <a key={m.id} className="ref-sidebar-model-link" href={`#model-${m.id}`}>
                      {m.name}
                    </a>
                  ))}
                </div>
              );
            })}
          </div>
        </aside>

        <main>
          {categories
            .filter((c: any) => activeCategory === 'all' || c.id === activeCategory)
            .map((c: any) => {
              const group = filteredModels.filter((m: any) => m.category === c.id);
              if (group.length === 0) return null;
              return (
                <div key={c.id}>
                  <h2 className="ref-category-heading">
                    <span>{c.icon}</span> {c.label}
                  </h2>
                  {group.map((m: any) => (
                    <ModelDetail key={m.id} model={m} />
                  ))}
                </div>
              );
            })}

          <section className="ref-model-card" style={{ marginTop: 32 }}>
            <div className="ref-model-header">
              <h3 className="ref-model-name">Glossary</h3>
              <ScdBadge type="Table" />
            </div>
            <div className="ref-model-overview">Common terms used across marts and segmentation logic.</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 12 }}>
              {GLOSSARY.map((g: any) => (
                <div key={g.term} style={{ padding: '10px 14px', background: '#f8fafc', borderRadius: 8 }}>
                  <div style={{ fontWeight: 600, marginBottom: 3 }}>
                    <code style={{ background: '#e2e8f0', padding: '1px 6px', borderRadius: 3 }}>{g.term}</code>
                  </div>
                  <div style={{ fontSize: 13, color: '#475569', lineHeight: 1.45 }}>{g.definition}</div>
                </div>
              ))}
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}

