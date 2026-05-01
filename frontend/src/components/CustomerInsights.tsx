import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Brain, TrendingUp, ShieldAlert, Zap } from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/Card';
import { getCustomer } from '@/lib/api';
import { cn } from '@/lib/utils';

function getAttr(customer: any, name: string): string | null {
  const a = customer?.attributes?.find((x: any) => String(x.attribute_name).toLowerCase() === name.toLowerCase());
  return a?.attribute_value ?? null;
}

function toNumber(v: any): number | null {
  if (v === null || v === undefined) return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

export default function CustomerInsights({ customerId }: { customerId: number }) {
  const { data: customer } = useQuery({
    queryKey: ['customer', customerId],
    queryFn: () => getCustomer(customerId),
    enabled: Number.isFinite(customerId),
  });

  const insights = useMemo(() => {
    if (!customer) return [];

    const ordersL52 = toNumber(getAttr(customer, 'orders_last_52_weeks') ?? customer.total_orders);
    const revenueL52 = toNumber(getAttr(customer, 'revenue_last_52_weeks') ?? customer.lifetime_value);
    const daysSinceLast = toNumber(getAttr(customer, 'days_since_last_order'));

    const churnRisk =
      daysSinceLast === null ? null : daysSinceLast >= 120 ? 'high' : daysSinceLast >= 60 ? 'medium' : 'low';

    const isHighValue = revenueL52 !== null && revenueL52 >= 2000;
    const isActive = daysSinceLast !== null && daysSinceLast <= 30;

    const result: { title: string; body: string; tone: 'good' | 'warn' | 'info'; icon: any }[] = [];

    if (isHighValue) {
      result.push({
        title: 'High value customer',
        body: `L52W revenue ${revenueL52 !== null ? `$${Math.round(revenueL52).toLocaleString()}` : '—'} across ${ordersL52 ?? '—'} orders.`,
        tone: 'good',
        icon: TrendingUp,
      });
    }

    if (churnRisk) {
      result.push({
        title: churnRisk === 'high' ? 'Churn risk: High' : churnRisk === 'medium' ? 'Churn risk: Medium' : 'Churn risk: Low',
        body: daysSinceLast !== null ? `Last order was ~${Math.round(daysSinceLast)} days ago.` : 'Insufficient data.',
        tone: churnRisk === 'high' ? 'warn' : churnRisk === 'medium' ? 'info' : 'good',
        icon: churnRisk === 'high' ? ShieldAlert : Zap,
      });
    }

    if (isActive && !isHighValue) {
      result.push({
        title: 'Recently active',
        body: 'Recent purchase activity detected. Consider cross-sell / upsell messaging.',
        tone: 'info',
        icon: Zap,
      });
    }

    if (result.length === 0) {
      result.push({
        title: 'AI insights',
        body: 'Not enough governed signals yet to generate insights for this profile.',
        tone: 'info',
        icon: Brain,
      });
    }

    return result.slice(0, 3);
  }, [customer]);

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2">
          <Brain className="w-4 h-4 text-primary-400" />
          AI Insights
        </CardTitle>
        <p className="text-xs text-surface-500">
          Deterministic insights based on governed marts (no external LLM calls).
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        {insights.map((ins) => {
          const Icon = ins.icon;
          const tone =
            ins.tone === 'good'
              ? 'bg-green-500/10 border-green-500/20'
              : ins.tone === 'warn'
                ? 'bg-amber-500/10 border-amber-500/20'
                : 'bg-surface-800/40 border-surface-800';
          return (
            <div key={ins.title} className={cn('rounded-lg border p-3', tone)}>
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg bg-surface-800 flex items-center justify-center">
                  <Icon className="w-4 h-4 text-surface-300" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold text-surface-200">{ins.title}</div>
                  <div className="text-sm text-surface-500 mt-0.5">{ins.body}</div>
                </div>
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

