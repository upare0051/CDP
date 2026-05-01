import React from 'react';

function isNullish(val: any) {
  return val === null || val === undefined || val === '';
}

export function BooleanBadge(props: any) {
  const value = props?.value ?? props;
  if (isNullish(value)) return <span className="ag-null-cell">—</span>;
  const bool = value === true || value === 'true' || value === 1 || value === '1';
  return <span className={`ag-badge ${bool ? 'ag-badge-green' : 'ag-badge-red'}`}>{bool ? 'Yes' : 'No'}</span>;
}

export function CurrencyCell(props: any) {
  const value = props?.value ?? props;
  if (isNullish(value)) return <span className="ag-null-cell">—</span>;
  const num = Number(value);
  if (Number.isNaN(num)) return <span>{String(value)}</span>;
  const formatted = num.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });
  return <span className={num < 0 ? 'ag-num-neg' : 'ag-num-pos'}>{formatted}</span>;
}

export function PercentCell(props: any) {
  const value = props?.value ?? props;
  if (isNullish(value)) return <span className="ag-null-cell">—</span>;
  const num = Number(value);
  if (Number.isNaN(num)) return <span>{String(value)}</span>;
  const pct = Math.abs(num) < 1 ? (num * 100).toFixed(1) : num.toFixed(1);
  return <span className="ag-num">{pct}%</span>;
}

export function NumberCell(props: any) {
  const value = props?.value ?? props;
  if (isNullish(value)) return <span className="ag-null-cell">—</span>;
  const num = Number(value);
  if (Number.isNaN(num)) return <span>{String(value)}</span>;
  return <span className="ag-num">{num.toLocaleString('en-US', { maximumFractionDigits: 2 })}</span>;
}

export function DateCell(props: any) {
  const value = props?.value ?? props;
  if (isNullish(value)) return <span className="ag-null-cell">—</span>;
  try {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return <span>{String(value)}</span>;
    const hasTime = String(value).includes(':') || String(value).includes('T');
    if (hasTime) {
      return (
        <span className="ag-date">
          {d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}{' '}
          {d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}
        </span>
      );
    }
    return <span className="ag-date">{d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</span>;
  } catch {
    return <span>{String(value)}</span>;
  }
}

export function IdCell(props: any) {
  const value = props?.value ?? props;
  if (isNullish(value)) return <span className="ag-null-cell">—</span>;
  const handleCopy = (e: any) => {
    e.stopPropagation();
    navigator.clipboard.writeText(String(value));
  };
  return (
    <span className="ag-id-cell">
      <code>{String(value)}</code>
      <button className="ag-copy-btn" onClick={handleCopy} title="Copy">
        📋
      </button>
    </span>
  );
}

const TIER_COLORS: Record<string, string> = { enthusiast: '#3b82f6', devotee: '#8b5cf6', icon: '#f59e0b', mover: '#10b981' };
export function TierBadge(props: any) {
  const value = props?.value ?? props;
  if (isNullish(value)) return <span className="ag-null-cell">—</span>;
  const tier = String(value).toLowerCase();
  const color = TIER_COLORS[tier] || '#6b7280';
  return (
    <span className="ag-badge" style={{ background: color, color: '#fff' }}>
      {String(value)}
    </span>
  );
}

const CHANNEL_ICONS: Record<string, string> = { email: '📧', sms: '💬', push: '🔔', digital: '🌐', retail: '🏬', none: '⊘' };
export function ChannelBadge(props: any) {
  const value = props?.value ?? props;
  if (isNullish(value)) return <span className="ag-null-cell">—</span>;
  const v = String(value).toLowerCase().trim();
  const icon = CHANNEL_ICONS[v] || '';
  return <span className="ag-channel-badge">{icon} {String(value)}</span>;
}

export function TextCell(props: any) {
  const value = props?.value ?? props;
  if (isNullish(value)) return <span className="ag-null-cell">—</span>;
  return <span>{String(value)}</span>;
}

export const cellRendererRegistry = {
  booleanBadge: BooleanBadge,
  currencyCell: CurrencyCell,
  percentCell: PercentCell,
  numberCell: NumberCell,
  dateCell: DateCell,
  idCell: IdCell,
  tierBadge: TierBadge,
  channelBadge: ChannelBadge,
  textCell: TextCell,
};

