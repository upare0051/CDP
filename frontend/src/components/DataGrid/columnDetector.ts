const DATE_PATTERNS =
  /^(date|_at$|_date$|_ts$|timestamp|created|updated|effective|processed|loaded|started|expires)/i;
const CURRENCY_PATTERNS =
  /^(revenue|price|amount|cost|discount|refund|aov|spend|sales|line_revenue|total_revenue|avg_revenue)/i;
const BOOL_PATTERNS =
  /^(is_|has_|enabled|subscribed|enrolled|suppressed|bounce|push_enabled|email_subscribed|sms_subscribed|loyalty_enrolled)/i;
const ID_PATTERNS =
  /^(customer_id|anon_id|order_id|order_line_id|product_id|variant_id|loyalty_id|contact_sk|address_sk|loyalty_sk)/i;
const TIER_PATTERNS = /^(loyalty_tier_name|tier)/i;
const CHANNEL_PATTERNS = /^(digital_vs_retail|preferred_comm_channel|channel)/i;
const PCT_PATTERNS = /(_pct$|_rate$|percent)/i;

function looksLikeDate(val: any) {
  if (typeof val !== 'string') return false;
  return /^\d{4}-\d{2}-\d{2}/.test(val) || /^\d{2}\/\d{2}\/\d{4}/.test(val);
}

function looksLikeNumber(val: any) {
  if (val === null || val === undefined || val === '') return false;
  if (typeof val === 'number') return true;
  if (typeof val === 'boolean') return false;
  return !Number.isNaN(Number(val));
}

function looksLikeBool(val: any) {
  if (typeof val === 'boolean') return true;
  if (typeof val === 'string') {
    const v = val.toLowerCase().trim();
    return v === 'true' || v === 'false' || v === '0' || v === '1';
  }
  return false;
}

export function detectColumnType(colName: string, sampleValues: any[]) {
  const name = colName.toLowerCase();
  if (TIER_PATTERNS.test(name)) return 'tier';
  if (CHANNEL_PATTERNS.test(name)) return 'channel';
  if (BOOL_PATTERNS.test(name)) return 'boolean';
  if (ID_PATTERNS.test(name)) return 'id';
  if (CURRENCY_PATTERNS.test(name)) return 'currency';
  if (PCT_PATTERNS.test(name)) return 'percent';
  if (DATE_PATTERNS.test(name)) return 'date';

  const nonNull = sampleValues.filter((v) => v !== null && v !== undefined && v !== '');
  if (nonNull.length === 0) return 'string';
  if (nonNull.every((v) => looksLikeBool(v))) return 'boolean';
  if (nonNull.every((v) => looksLikeDate(v))) return 'date';
  if (nonNull.every((v) => looksLikeNumber(v))) return 'number';
  return 'string';
}

export function buildColumnDefs(rows: any[], options: { maxSampleRows?: number } = {}) {
  if (!rows || rows.length === 0) return [];
  const { maxSampleRows = 20 } = options;
  const cols = Object.keys(rows[0]);
  const sampleRows = rows.slice(0, maxSampleRows);

  return cols.map((col) => {
    const samples = sampleRows.map((r) => r[col]);
    const colType = detectColumnType(col, samples);
    const baseDef: any = {
      field: col,
      headerName: col.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
      sortable: true,
      resizable: true,
      filter: true,
      _detectedType: colType,
    };

    switch (colType) {
      case 'boolean':
        return { ...baseDef, cellRenderer: 'booleanBadge', width: 110, filter: 'agSetColumnFilter' };
      case 'currency':
        return { ...baseDef, cellRenderer: 'currencyCell', type: 'numericColumn', width: 140 };
      case 'percent':
        return { ...baseDef, cellRenderer: 'percentCell', type: 'numericColumn', width: 110 };
      case 'date':
        return { ...baseDef, cellRenderer: 'dateCell', width: 140 };
      case 'number':
        return { ...baseDef, cellRenderer: 'numberCell', type: 'numericColumn', width: 120 };
      case 'id':
        return {
          ...baseDef,
          cellRenderer: 'idCell',
          width: 160,
          pinned: col === 'customer_id' ? 'left' : undefined,
        };
      case 'tier':
        return { ...baseDef, cellRenderer: 'tierBadge', width: 130 };
      case 'channel':
        return { ...baseDef, cellRenderer: 'channelBadge', width: 140 };
      default:
        return { ...baseDef, width: 160, cellRenderer: 'textCell' };
    }
  });
}

