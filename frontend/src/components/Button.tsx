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
      'bg-black hover:bg-gray-700 text-white dark:bg-white dark:text-black dark:hover:bg-neutral-200 border border-black dark:border-white',
    secondary:
      'bg-white dark:bg-black border border-black dark:border-white text-black dark:text-white hover:bg-alo-smoke dark:hover:bg-neutral-900',
    ghost:
      'bg-transparent border border-alo-mercury dark:border-neutral-700 text-black dark:text-white hover:bg-alo-smoke dark:hover:bg-neutral-900',
    danger:
      'bg-white hover:bg-red-500 text-red-600 hover:text-white border border-red-500 dark:bg-black dark:text-red-100 dark:border-red-300 dark:hover:bg-red-600',
  };

  const sizes = {
    sm: 'px-4 py-2 text-[11px]',
    md: 'px-5 py-3 text-[13px]',
    lg: 'px-8 py-4 text-sm',
    icon: 'p-2 text-[13px]',
  };

  return (
    <button
      className={cn(
        'inline-flex min-h-10 items-center justify-center gap-2 font-sans font-semibold uppercase tracking-[0.06em] transition-colors duration-150',
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
