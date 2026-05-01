import React, { useCallback, useMemo, useState } from 'react';

import { LINEAGE_EDGES, UPSTREAM_TABLES } from '@/data/c360_lineage';

export type LineageModelColumn = { name: string; type: string; pk?: boolean };
export type LineageModel = { id: string; name: string; columns: LineageModelColumn[] };

const LAYER_COLORS: Record<string, any> = {
  bronze: { bg: '#fef3c7', border: '#f59e0b', text: '#92400e', headerBg: '#f59e0b', headerText: '#fff' },
  silver: { bg: '#f0f9ff', border: '#38bdf8', text: '#0c4a6e', headerBg: '#38bdf8', headerText: '#fff' },
  gold: { bg: '#ecfdf5', border: '#34d399', text: '#065f46', headerBg: '#10b981', headerText: '#fff' },
  platinum: { bg: '#f5f3ff', border: '#8b5cf6', text: '#4c1d95', headerBg: '#7c3aed', headerText: '#fff' },
};

export default function LineageDiagram({ models }: { models: LineageModel[] }) {
  const [expandedNodes, setExpandedNodes] = useState<Record<string, boolean>>({});
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [upstreamHighlight, setUpstreamHighlight] = useState<Set<string>>(new Set());

  const getUpstreamChain = useCallback((nodeId: string) => {
    const chain = new Set<string>();
    const queue: string[] = [nodeId];
    while (queue.length > 0) {
      const current = queue.shift() as string;
      LINEAGE_EDGES.forEach((edge) => {
        if (edge.to === current && !chain.has(edge.from)) {
          chain.add(edge.from);
          queue.push(edge.from);
        }
      });
    }
    return chain;
  }, []);

  const handleNodeHover = useCallback(
    (nodeId: string) => {
      setHoveredNode(nodeId);
      setUpstreamHighlight(getUpstreamChain(nodeId));
    },
    [getUpstreamChain]
  );

  const handleNodeLeave = useCallback(() => {
    setHoveredNode(null);
    setUpstreamHighlight(new Set());
  }, []);

  const toggleExpand = useCallback((nodeId: string) => {
    setExpandedNodes((prev) => ({ ...prev, [nodeId]: !prev[nodeId] }));
  }, []);

  // Layout constants
  const COL_WIDTH = 240;
  const NODE_H = 36;
  const NODE_GAP = 8;
  const COL_GAP = 80;
  const PAD_X = 24;
  const PAD_Y = 50;
  const EXPANDED_EXTRA = 18; // per column row

  const bronzeNodes = UPSTREAM_TABLES.bronze;
  const silverNodes = UPSTREAM_TABLES.silver;

  const platinumId = 'customer_unified_attr';
  const goldModels = models.filter((m) => m.id !== platinumId);
  const platinumModels = models.filter((m) => m.id === platinumId);

  const computePositions = (nodes: any[], x: number) => {
    let y = PAD_Y;
    const positions: Record<string, any> = {};
    nodes.forEach((n) => {
      const id = n.id || n;
      const isExpanded = expandedNodes[id];
      const model = models.find((m) => m.id === id);
      const colCount = model ? model.columns.length : 0;
      const h = NODE_H + (isExpanded ? Math.min(colCount, 8) * EXPANDED_EXTRA + 12 : 0);
      positions[id] = { x, y, w: COL_WIDTH, h };
      y += h + NODE_GAP;
    });
    return positions;
  };

  const bronzePos = computePositions(bronzeNodes, PAD_X);
  const silverPos = computePositions(silverNodes, PAD_X + COL_WIDTH + COL_GAP);
  const goldPos = computePositions(goldModels, PAD_X + 2 * (COL_WIDTH + COL_GAP));

  const goldMaxY = Math.max(...Object.values(goldPos).map((p: any) => p.y + p.h), 200);
  const platinumX = PAD_X + 3 * (COL_WIDTH + COL_GAP);
  const platinumModel = models.find((m) => m.id === platinumId);
  const platinumExpanded = expandedNodes[platinumId];
  const platinumColCount = platinumModel ? platinumModel.columns.length : 0;
  const platinumH = NODE_H + (platinumExpanded ? Math.min(platinumColCount, 8) * EXPANDED_EXTRA + 12 : 0);
  const platinumY = Math.max(PAD_Y, goldMaxY / 2 - platinumH / 2);
  const platinumPos = { [platinumId]: { x: platinumX, y: platinumY, w: COL_WIDTH, h: platinumH } };

  const allPos = { ...bronzePos, ...silverPos, ...goldPos, ...platinumPos };

  const maxY = Math.max(...Object.values(allPos).map((p: any) => p.y + p.h), 400);
  const svgW = PAD_X * 2 + 4 * COL_WIDTH + 3 * COL_GAP;
  const svgH = maxY + PAD_Y;

  const edgePaths = LINEAGE_EDGES.map((edge, i) => {
    const from = (allPos as any)[edge.from];
    const to = (allPos as any)[edge.to];
    if (!from || !to) return null;
    const x1 = from.x + from.w;
    const y1 = from.y + NODE_H / 2;
    const x2 = to.x;
    const y2 = to.y + NODE_H / 2;
    const cx = (x1 + x2) / 2;
    const isActive =
      !!hoveredNode &&
      upstreamHighlight.has(edge.from) &&
      (upstreamHighlight.has(edge.to) || edge.to === hoveredNode);
    return (
      <path
        key={i}
        d={`M${x1},${y1} C${cx},${y1} ${cx},${y2} ${x2},${y2}`}
        fill="none"
        stroke={isActive ? '#3b82f6' : '#d1d5db'}
        strokeWidth={isActive ? 2 : 1}
        opacity={hoveredNode ? (isActive ? 1 : 0.2) : 0.6}
        style={{ transition: 'all 0.2s' }}
      />
    );
  });

  const renderNode = (id: string, label: string, layer: string, pos: any, isGold = false) => {
    const colors = LAYER_COLORS[layer];
    const isHovered = hoveredNode === id;
    const isUpstream = upstreamHighlight.has(id);
    const dimmed = hoveredNode && !isHovered && !isUpstream;
    const model = models.find((m) => m.id === id);
    const isExpanded = !!expandedNodes[id];
    const colCount = model ? model.columns.length : 0;

    let desc = '';
    if (!isGold) {
      const upstream = [...UPSTREAM_TABLES.bronze, ...UPSTREAM_TABLES.silver].find((t) => t.id === id);
      desc = upstream ? upstream.desc : '';
    }

    return (
      <g
        key={id}
        transform={`translate(${pos.x},${pos.y})`}
        onMouseEnter={() => handleNodeHover(id)}
        onMouseLeave={handleNodeLeave}
        style={{ cursor: isGold ? 'pointer' : 'default', transition: 'opacity 0.2s' }}
        opacity={dimmed ? 0.25 : 1}
        onClick={isGold ? () => toggleExpand(id) : undefined}
      >
        <rect
          width={pos.w}
          height={pos.h}
          rx={8}
          fill={isHovered || isUpstream ? colors.bg : '#fff'}
          stroke={isHovered ? colors.border : isUpstream ? colors.border : '#e2e8f0'}
          strokeWidth={isHovered ? 2 : 1}
        />
        <rect x={0} y={0} width={6} height={pos.h} rx={4} fill={colors.border} />
        <text x={16} y={22} fontSize={11} fontFamily="'SF Mono','Fira Code',monospace" fill={colors.text} fontWeight={600}>
          {label.length > 30 ? label.slice(0, 28) + '…' : label}
        </text>
        {isGold && colCount > 0 && (
          <g>
            <rect x={pos.w - 44} y={8} width={36} height={18} rx={9} fill={isExpanded ? colors.border : '#e2e8f0'} />
            <text x={pos.w - 26} y={21} fontSize={10} fill={isExpanded ? '#fff' : '#64748b'} textAnchor="middle" fontWeight={600}>
              {isExpanded ? '▾' : ''}
              {colCount}
            </text>
          </g>
        )}
        {isGold && isExpanded && model && (
          <g>
            <line x1={10} y1={NODE_H + 2} x2={pos.w - 10} y2={NODE_H + 2} stroke="#e2e8f0" strokeWidth={1} />
            {model.columns.slice(0, 8).map((col, ci) => (
              <g key={col.name}>
                <text x={16} y={NODE_H + 16 + ci * EXPANDED_EXTRA} fontSize={10} fontFamily="'SF Mono','Fira Code',monospace" fill="#475569">
                  {col.pk ? '🔑 ' : '   '}
                  {col.name}
                </text>
                <text x={pos.w - 12} y={NODE_H + 16 + ci * EXPANDED_EXTRA} fontSize={9} fill="#94a3b8" textAnchor="end">
                  {col.type}
                </text>
              </g>
            ))}
            {colCount > 8 && (
              <text x={16} y={NODE_H + 16 + 8 * EXPANDED_EXTRA} fontSize={10} fill="#94a3b8" fontStyle="italic">
                +{colCount - 8} more…
              </text>
            )}
          </g>
        )}
        {!isGold && isHovered && desc && (
          <g>
            <rect x={0} y={pos.h + 4} width={pos.w} height={40} rx={6} fill="#1e293b" opacity={0.95} />
            <text x={8} y={pos.h + 20} fontSize={10} fill="#e2e8f0">
              {desc.length > 80 ? desc.slice(0, 78) + '…' : desc}
            </text>
            {desc.length > 80 && (
              <text x={8} y={pos.h + 34} fontSize={10} fill="#94a3b8">
                {desc.slice(78, 156)}
              </text>
            )}
          </g>
        )}
      </g>
    );
  };

  const colHeaders = [
    { label: 'BRONZE', x: PAD_X, color: LAYER_COLORS.bronze },
    { label: 'SILVER', x: PAD_X + COL_WIDTH + COL_GAP, color: LAYER_COLORS.silver },
    { label: 'GOLD', x: PAD_X + 2 * (COL_WIDTH + COL_GAP), color: LAYER_COLORS.gold },
    { label: 'PLATINUM', x: PAD_X + 3 * (COL_WIDTH + COL_GAP), color: LAYER_COLORS.platinum },
  ];

  return (
    <div className="ref-lineage" id="lineage">
      <h3>Model Lineage</h3>
      <p className="ref-lineage-subtitle">
        Hover over a model to highlight its upstream dependencies. Click gold models to expand columns.
      </p>
      <div className="ref-lineage-scroll">
        <svg width={svgW} height={svgH} className="ref-lineage-svg">
          {colHeaders.map((h) => (
            <g key={h.label}>
              <rect x={h.x} y={8} width={COL_WIDTH} height={24} rx={4} fill={h.color.headerBg} />
              <text
                x={h.x + COL_WIDTH / 2}
                y={24}
                textAnchor="middle"
                fontSize={11}
                fontWeight={700}
                fill={h.color.headerText}
                letterSpacing="0.08em"
              >
                {h.label}
              </text>
            </g>
          ))}
          {edgePaths}
          {bronzeNodes.map((n) => renderNode(n.id, n.label, 'bronze', (bronzePos as any)[n.id]))}
          {silverNodes.map((n) => renderNode(n.id, n.label, 'silver', (silverPos as any)[n.id]))}
          {goldModels.map((m) => renderNode(m.id, m.name, 'gold', (goldPos as any)[m.id], true))}
          {platinumModels.map((m) => renderNode(m.id, m.name, 'platinum', (platinumPos as any)[m.id], true))}
        </svg>
      </div>
      <p className="ref-lineage-caption">
        Bronze tables (amber) are raw/lightly transformed loads. Silver tables (blue) are cleaned enriched models. Gold models (green) are the C360 consumption layer.
        <code>customer_unified_attr</code> is the Platinum terminal table (purple) — the single DA-facing wide table joining all Gold dimensions and facts.
      </p>
    </div>
  );
}

