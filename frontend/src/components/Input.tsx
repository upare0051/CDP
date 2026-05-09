import { InputHTMLAttributes, forwardRef } from 'react';
import { cn } from '@/lib/utils';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
}

const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, hint, className, ...props }, ref) => {
    return (
      <div className="space-y-1.5">
        {label && (
          <label className="block text-xs font-semibold uppercase tracking-wider text-black dark:text-white">
            {label}
          </label>
        )}
        <input
          ref={ref}
          className={cn(
            'w-full px-3.5 py-2.5 bg-white dark:bg-black border rounded-md text-black dark:text-white',
            'placeholder:text-neutral-400 dark:placeholder:text-neutral-500',
            'focus:outline-none focus:ring-2 focus:ring-black/15 dark:focus:ring-white/25 focus:border-black dark:focus:border-white',
            'transition-all duration-150',
            error
              ? 'border-black dark:border-white ring-1 ring-black dark:ring-white'
              : 'border-neutral-300 dark:border-neutral-600',
            className
          )}
          {...props}
        />
        {error && <p className="text-sm text-black dark:text-white font-medium">{error}</p>}
        {hint && !error && <p className="text-sm text-neutral-500 dark:text-neutral-400">{hint}</p>}
      </div>
    );
  }
);

Input.displayName = 'Input';

export default Input;
