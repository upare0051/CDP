import { cn } from '@/lib/utils';
import type { SyncStatus } from '@/types';

interface StatusBadgeProps {
  status: (SyncStatus | 'active' | 'inactive' | 'paused' | string) | undefined;
  size?: 'sm' | 'md';
}

const statusConfig = {
  pending: {
    bg: 'bg-amber-50',
    text: 'text-amber-700',
    border: 'border-transparent',
    dot: 'bg-current',
  },
  running: {
    bg: 'bg-blue-50',
    text: 'text-blue-700',
    border: 'border-transparent',
    dot: 'bg-current animate-pulse',
  },
  completed: {
    bg: 'bg-success-50',
    text: 'text-success-700',
    border: 'border-transparent',
    dot: 'bg-current',
  },
  failed: {
    bg: 'bg-red-50',
    text: 'text-red-700',
    border: 'border-transparent',
    dot: 'bg-current',
  },
  cancelled: {
    bg: 'bg-alo-smoke dark:bg-neutral-900',
    text: 'text-gray-500 dark:text-neutral-300',
    border: 'border-transparent',
    dot: 'bg-current',
  },
  active: {
    bg: 'bg-success-50',
    text: 'text-success-700',
    border: 'border-transparent',
    dot: 'bg-current',
  },
  inactive: {
    bg: 'bg-alo-smoke dark:bg-neutral-900',
    text: 'text-gray-500 dark:text-neutral-300',
    border: 'border-transparent',
    dot: 'bg-current',
  },
  paused: {
    bg: 'bg-alo-smoke dark:bg-neutral-900',
    text: 'text-gray-700 dark:text-neutral-200',
    border: 'border-alo-mercury dark:border-neutral-700',
    dot: 'bg-current',
  },
};

export default function StatusBadge({ status, size = 'md' }: StatusBadgeProps) {
  if (!status) return null;

  const config = statusConfig[status as keyof typeof statusConfig] || statusConfig.inactive;

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 border font-tag font-semibold uppercase tracking-[0.1em]',
        config.bg,
        config.text,
        config.border,
        size === 'sm' ? 'px-2 py-0.5 text-[10px]' : 'px-2 py-1 text-[11px]'
      )}
    >
      <span className={cn('h-1.5 w-1.5 rounded-full', config.dot)} />
      {status.replace('_', ' ')}
    </span>
  );
}
