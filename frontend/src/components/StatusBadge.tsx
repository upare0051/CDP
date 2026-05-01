import { cn } from '@/lib/utils';
import type { SyncStatus } from '@/types';

interface StatusBadgeProps {
  status: (SyncStatus | 'active' | 'inactive' | 'paused' | string) | undefined;
  size?: 'sm' | 'md';
}

const statusConfig = {
  pending: { 
    bg: 'bg-amber-50 dark:bg-amber-900/30', 
    text: 'text-amber-700 dark:text-amber-400', 
    dot: 'bg-amber-500' 
  },
  running: { 
    bg: 'bg-blue-50 dark:bg-blue-900/30', 
    text: 'text-blue-700 dark:text-blue-400', 
    dot: 'bg-blue-500 animate-pulse' 
  },
  completed: { 
    bg: 'bg-green-50 dark:bg-green-900/30', 
    text: 'text-green-700 dark:text-green-400', 
    dot: 'bg-green-500' 
  },
  failed: { 
    bg: 'bg-red-50 dark:bg-red-900/30', 
    text: 'text-red-700 dark:text-red-400', 
    dot: 'bg-red-500' 
  },
  cancelled: { 
    bg: 'bg-gray-100 dark:bg-gray-800', 
    text: 'text-gray-600 dark:text-gray-400', 
    dot: 'bg-gray-400' 
  },
  active: { 
    bg: 'bg-green-50 dark:bg-green-900/30', 
    text: 'text-green-700 dark:text-green-400', 
    dot: 'bg-green-500' 
  },
  inactive: { 
    bg: 'bg-gray-100 dark:bg-gray-800', 
    text: 'text-gray-600 dark:text-gray-400', 
    dot: 'bg-gray-400' 
  },
  paused: { 
    bg: 'bg-amber-50 dark:bg-amber-900/30', 
    text: 'text-amber-700 dark:text-amber-400', 
    dot: 'bg-amber-500' 
  },
};

export default function StatusBadge({ status, size = 'md' }: StatusBadgeProps) {
  if (!status) return null;
  
  const config = statusConfig[status] || statusConfig.inactive;
  
  return (
    <span
      className={cn(
        'inline-flex items-center gap-2 rounded-full font-medium capitalize',
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
