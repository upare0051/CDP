import { cn } from '@/lib/utils';
import type { SyncStatus } from '@/types';

interface StatusBadgeProps {
  status: (SyncStatus | 'active' | 'inactive' | 'paused' | string) | undefined;
  size?: 'sm' | 'md';
}

const statusConfig = {
  pending: {
    bg: 'bg-neutral-100 dark:bg-neutral-900',
    text: 'text-black dark:text-white',
    dot: 'bg-neutral-500 dark:bg-neutral-400',
  },
  running: {
    bg: 'bg-neutral-200 dark:bg-neutral-800',
    text: 'text-black dark:text-white',
    dot: 'bg-black dark:bg-white animate-pulse',
  },
  completed: {
    bg: 'bg-black dark:bg-white',
    text: 'text-white dark:text-black',
    dot: 'bg-white dark:bg-black',
  },
  failed: {
    bg: 'bg-white dark:bg-black',
    text: 'text-black dark:text-white',
    dot: 'bg-black dark:bg-white',
  },
  cancelled: {
    bg: 'bg-neutral-100 dark:bg-neutral-900',
    text: 'text-neutral-600 dark:text-neutral-400',
    dot: 'bg-neutral-400 dark:bg-neutral-500',
  },
  active: {
    bg: 'bg-black dark:bg-white',
    text: 'text-white dark:text-black',
    dot: 'bg-white dark:bg-black',
  },
  inactive: {
    bg: 'bg-neutral-100 dark:bg-neutral-900',
    text: 'text-neutral-600 dark:text-neutral-400',
    dot: 'bg-neutral-400 dark:bg-neutral-500',
  },
  paused: {
    bg: 'bg-neutral-200 dark:bg-neutral-800',
    text: 'text-black dark:text-white',
    dot: 'bg-neutral-600 dark:bg-neutral-300',
  },
};

export default function StatusBadge({ status, size = 'md' }: StatusBadgeProps) {
  if (!status) return null;

  const config = statusConfig[status as keyof typeof statusConfig] || statusConfig.inactive;

  return (
    <span
      className={cn(
        'inline-flex items-center gap-2 rounded-full font-medium capitalize border border-neutral-300 dark:border-neutral-600',
        config.bg,
        config.text,
        size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs'
      )}
    >
      <span className={cn('w-1.5 h-1.5 rounded-full', config.dot)} />
      {status.replace('_', ' ')}
    </span>
  );
}
