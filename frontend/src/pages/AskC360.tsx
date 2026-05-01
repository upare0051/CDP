import { useMemo, useRef, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import type { AxiosError } from 'axios';
import { Sparkles } from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/Card';
import Button from '@/components/Button';
import Input from '@/components/Input';
import { PageLoader } from '@/components/LoadingSpinner';
import { c360Chat } from '@/lib/api';

type ChatMsg = {
  role: 'user' | 'assistant';
  content: string;
  sql?: string | null;
  sql_results?: Record<string, any>[] | null;
  pii_redacted?: boolean;
  cache_hit?: boolean;
};

const SUGGESTED: string[] = [
  "What's the total revenue for last 52 weeks?",
  'How many customers are loyalty vs non-loyalty?',
  'Show me top 10 customers by revenue',
  "What's the digital vs retail revenue split?",
  'Which geo segments have the highest AOV?',
  'How many dormant customers do we have?',
  'Show monthly revenue trend for last 12 months',
  "What's the customer acquisition trend this year?",
];

function ResultTable({ rows }: { rows: Record<string, any>[] }) {
  const columns = useMemo(() => {
    const set = new Set<string>();
    rows.forEach((r) => Object.keys(r || {}).forEach((k) => set.add(k)));
    return Array.from(set);
  }, [rows]);

  if (rows.length === 0) return null;

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-800">
      <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-800">
        <thead className="bg-gray-50 dark:bg-gray-900">
          <tr>
            {columns.map((c) => (
              <th
                key={c}
                className="px-3 py-2 text-left text-xs font-semibold text-gray-600 dark:text-gray-300 uppercase"
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="bg-white dark:bg-gray-950 divide-y divide-gray-200 dark:divide-gray-800">
          {rows.map((row, idx) => (
            <tr key={idx}>
              {columns.map((c) => (
                <td key={c} className="px-3 py-2 text-sm text-gray-700 dark:text-gray-300">
                  {row?.[c] === null || row?.[c] === undefined ? 'NULL' : String(row[c])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function AskC360() {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState('');
  const endRef = useRef<HTMLDivElement | null>(null);

  const chatMutation = useMutation({
    mutationFn: ({ question, history }: { question: string; history: ChatMsg[] }) =>
      c360Chat(question, history),
    onSuccess: (data, variables) => {
      const next: ChatMsg[] = [
        ...variables.history,
        { role: 'user', content: variables.question },
        {
          role: 'assistant',
          content: data.answer,
          sql: data.sql,
          sql_results: data.sql_results,
          pii_redacted: data.pii_redacted,
          cache_hit: data.cache_hit,
        },
      ];
      setMessages(next);
      setTimeout(() => endRef.current?.scrollIntoView({ behavior: 'smooth' }), 50);
    },
  });

  const send = (q?: string) => {
    const question = (q ?? input).trim();
    if (!question || chatMutation.isPending) return;
    setInput('');
    chatMutation.mutate({ question, history: messages.slice(-6) });
  };

  const err = chatMutation.error as AxiosError<{ detail?: string }> | null;
  const errMsg = err?.response?.data?.detail || err?.message || null;

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-primary-600 dark:text-primary-400" />
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Ask C360</h1>
        </div>
        <p className="text-gray-500 dark:text-gray-400 mt-1">
          Ask business questions. We’ll generate governed SQL on allowlisted marts and return anonymized results.
        </p>
      </div>

      {messages.length === 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Suggested questions</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {SUGGESTED.map((q) => (
                <button
                  key={q}
                  onClick={() => send(q)}
                  className="px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-800 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-900"
                >
                  {q}
                </button>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <div className="space-y-4">
        {messages.map((m, idx) => (
          <Card key={idx}>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">{m.role === 'user' ? 'You' : 'Assistant'}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="text-sm text-gray-800 dark:text-gray-200 whitespace-pre-wrap">
                {m.content}
              </div>

              {m.sql_results && m.sql_results.length > 0 && (
                <ResultTable rows={m.sql_results} />
              )}

              {m.sql && (
                <details className="rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900">
                  <summary className="cursor-pointer px-3 py-2 text-sm font-medium text-gray-700 dark:text-gray-200">
                    View SQL
                  </summary>
                  <pre className="px-3 pb-3 text-xs overflow-x-auto text-gray-800 dark:text-gray-200">
{m.sql}
                  </pre>
                </details>
              )}

              <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
                {m.pii_redacted ? (
                  <span className="inline-flex items-center gap-1 rounded-full border border-purple-300 bg-purple-50 px-2 py-0.5 text-purple-700 dark:border-purple-900/50 dark:bg-purple-900/20 dark:text-purple-200">
                    PII redacted
                  </span>
                ) : null}
                {m.cache_hit ? <span>Cached</span> : null}
              </div>
            </CardContent>
          </Card>
        ))}
        <div ref={endRef} />
      </div>

      {errMsg && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-900/20 dark:text-red-300">
          {errMsg}
        </div>
      )}

      <Card>
        <CardContent className="p-4">
          <div className="flex gap-3 items-end">
            <div className="flex-1">
              <Input
                label="Question"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask a business question about C360 data…"
                onKeyDown={(e) => {
                  if (e.key === 'Enter') send();
                }}
              />
            </div>
            <Button
              onClick={() => send()}
              loading={chatMutation.isPending}
              disabled={!input.trim()}
            >
              Send
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

