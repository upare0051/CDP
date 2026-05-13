import { ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface EmptyStateProps {
  icon: ReactNode;
  title: string;
  description: string;
  action?: ReactNode;
  className?: string;
}

export default function EmptyState({ icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cn('flex flex-col items-center justify-center py-16 px-4 text-center', className)}>
      <div className="mb-4 flex h-14 w-14 items-center justify-center border border-alo-mercury bg-alo-smoke text-gray-500 dark:border-neutral-800 dark:bg-neutral-900 dark:text-neutral-400">
        {icon}
      </div>
      <h3 className="mb-1 text-base font-semibold text-black dark:text-white">{title}</h3>
      <p className="text-sm text-gray-500 dark:text-gray-400 max-w-sm mb-6">{description}</p>
      {action}
    </div>
  );
}
