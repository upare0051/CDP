/**
 * Deliveries — native cdp-main page replacing Dittofeed's deliveries surface.
 *
 * Phase 0 of the headless journey-builder rebuild. The page calls cdp-main's
 * backend (which proxies to Dittofeed) — no iframe, no Dittofeed UI, just
 * a native React table inside cdp-main's shell.
 */
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Loader2, Mail, MessageSquare, Webhook, ChevronLeft, ChevronRight } from 'lucide-react';
import { listDeliveries, type DeliveryItem } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/Card';
import Button from '@/components/Button';
import { cn } from '@/lib/utils';

const PAGE_SIZE = 25;

function channelIcon(channel: string | undefined) {
  switch ((channel || '').toLowerCase()) {
    case 'email': return Mail;
    case 'sms':   return MessageSquare;
    case 'webhook': return Webhook;
    default: return Mail;
  }
}

function statusTone(status: string) {
  const s = (status || '').toLowerCase();
  if (s.includes('deliver') || s.includes('sent')) {
    return 'text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-900/30';
  }
  if (s.includes('open') || s.includes('click')) {
    return 'text-blue-700 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30';
  }
  if (s.includes('bounce') || s.includes('fail') || s.includes('error')) {
    return 'text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-900/30';
  }
  return 'text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-800';
}

function pickTo(item: DeliveryItem): string {
  return (item.variant?.to as string) || item.to || item.userId || '—';
}

function pickChannel(item: DeliveryItem): string {
  return (item.variant?.type as string) || item.channel || 'email';
}

function pickSubject(item: DeliveryItem): string {
  return (item.variant?.subject as string) || '—';
}

export default function Deliveries() {
  // Cursor stack — we push the next cursor as we go forward, pop on Back.
  const [cursorStack, setCursorStack] = useState<(string | undefined)[]>([undefined]);
  const currentCursor = cursorStack[cursorStack.length - 1];

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['journey-builder', 'deliveries', currentCursor],
    queryFn: () => listDeliveries({ limit: PAGE_SIZE, cursor: currentCursor }),
    staleTime: 10_000,
  });

  const items: DeliveryItem[] = data?.items ?? [];
  const nextCursor = data?.cursor;

  const goNext = () => {
    if (nextCursor) setCursorStack((s) => [...s, nextCursor]);
  };
  const goPrev = () => {
    if (cursorStack.length > 1) setCursorStack((s) => s.slice(0, -1));
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">Deliveries</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
            Every message sent by a journey or broadcast.
          </p>
        </div>
        <Button variant="secondary" size="sm" onClick={() => refetch()}>
          Refresh
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent activity</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && (
            <div className="flex items-center gap-2 py-12 text-gray-500 dark:text-gray-400">
              <Loader2 className="w-4 h-4 animate-spin" /> Loading deliveries…
            </div>
          )}

          {isError && (
            <div className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3">
              Failed to load deliveries — {(error as Error)?.message || 'unknown error'}.
              Make sure the journeys stack is running.
            </div>
          )}

          {!isLoading && !isError && items.length === 0 && (
            <div className="py-12 text-center text-gray-500 dark:text-gray-400">
              <p className="text-sm">No deliveries yet.</p>
              <p className="text-xs mt-1">
                Trigger a sync to an audience that lands in a Dittofeed journey, then come back here.
              </p>
            </div>
          )}

          {!isLoading && !isError && items.length > 0 && (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs uppercase tracking-wider text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-800">
                      <th className="text-left px-3 py-2 font-medium">Sent</th>
                      <th className="text-left px-3 py-2 font-medium">Channel</th>
                      <th className="text-left px-3 py-2 font-medium">Recipient</th>
                      <th className="text-left px-3 py-2 font-medium">Subject / Body</th>
                      <th className="text-left px-3 py-2 font-medium">Journey / Broadcast</th>
                      <th className="text-left px-3 py-2 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((item, idx) => {
                      const channel = pickChannel(item);
                      const Icon = channelIcon(channel);
                      const to = pickTo(item);
                      const subject = pickSubject(item);
                      const source = item.journeyId
                        ? `Journey ${item.journeyId.slice(0, 8)}`
                        : item.broadcastId
                          ? `Broadcast ${item.broadcastId.slice(0, 8)}`
                          : '—';
                      return (
                        <tr
                          key={item.originMessageId || `${idx}-${item.sentAt}`}
                          className="border-b border-gray-100 dark:border-gray-800/60 hover:bg-gray-50 dark:hover:bg-gray-900/40"
                        >
                          <td className="px-3 py-2 text-gray-600 dark:text-gray-400 whitespace-nowrap">
                            {new Date(item.sentAt).toLocaleString()}
                          </td>
                          <td className="px-3 py-2">
                            <span className="inline-flex items-center gap-1.5 text-xs text-gray-700 dark:text-gray-300">
                              <Icon className="w-3.5 h-3.5 text-gray-400" />
                              {channel}
                            </span>
                          </td>
                          <td className="px-3 py-2 text-gray-900 dark:text-gray-100 truncate max-w-[18ch]" title={to}>
                            {to}
                          </td>
                          <td className="px-3 py-2 text-gray-700 dark:text-gray-300 truncate max-w-[36ch]" title={subject}>
                            {subject}
                          </td>
                          <td className="px-3 py-2 text-gray-500 dark:text-gray-400 text-xs whitespace-nowrap">
                            {source}
                          </td>
                          <td className="px-3 py-2">
                            <span
                              className={cn(
                                'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
                                statusTone(item.status),
                              )}
                            >
                              {item.status || 'unknown'}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              <div className="flex items-center justify-between mt-4">
                <div className="text-xs text-gray-500 dark:text-gray-400">
                  Page {cursorStack.length} · {items.length} rows
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={cursorStack.length <= 1}
                    onClick={goPrev}
                  >
                    <ChevronLeft className="w-4 h-4" /> Previous
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={!nextCursor}
                    onClick={goNext}
                  >
                    Next <ChevronRight className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
