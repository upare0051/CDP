import { ButtonHTMLAttributes, ReactNode } from 'react';
import { cn } from '@/lib/utils';
import { Loader2 } from 'lucide-react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg' | 'icon';
  loading?: boolean;
  icon?: ReactNode;
  children: ReactNode;
}

export default function Button({
  variant = 'primary',
  size = 'md',
  loading,
  icon,
  children,
  className,
  disabled,
  ...props
}: ButtonProps) {
  const variants = {
    primary:
      'bg-black hover:bg-neutral-800 text-white dark:bg-white dark:text-black dark:hover:bg-neutral-200 border border-black dark:border-white uppercase tracking-wider text-xs font-semibold',
    secondary:
      'bg-white dark:bg-black border border-neutral-300 dark:border-neutral-600 text-black dark:text-white hover:bg-neutral-50 dark:hover:bg-neutral-900 uppercase tracking-wider text-xs font-semibold',
    ghost:
      'text-neutral-600 dark:text-neutral-400 hover:text-black dark:hover:text-white hover:bg-neutral-100 dark:hover:bg-neutral-900 uppercase tracking-wider text-xs font-semibold',
    danger:
      'bg-black hover:bg-neutral-800 text-white border border-black uppercase tracking-wider text-xs font-semibold dark:bg-white dark:text-black dark:border-white dark:hover:bg-neutral-200',
  };

  const sizes = {
    sm: 'px-4 py-2',
    md: 'px-5 py-2.5',
    lg: 'px-6 py-3',
    icon: 'p-2',
  };

  return (
    <button
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-full transition-all duration-150',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        variants[variant],
        sizes[size],
        className
      )}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : icon}
      {children}
    </button>
  );
}
