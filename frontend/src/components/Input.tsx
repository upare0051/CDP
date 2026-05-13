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
          <label className="block font-tag text-[11px] font-semibold uppercase tracking-[0.14em] text-black dark:text-white">
            {label}
          </label>
        )}
        <input
          ref={ref}
          className={cn(
            'w-full border bg-white px-3.5 py-3 text-sm text-black dark:bg-black dark:text-white',
            'placeholder:text-neutral-400 dark:placeholder:text-neutral-500',
            'focus:border-black focus:outline-none focus:ring-2 focus:ring-black/15 dark:focus:border-white dark:focus:ring-white/25',
            'transition-colors duration-150',
            error
              ? 'border-black dark:border-white ring-1 ring-black dark:ring-white'
              : 'border-alo-mercury dark:border-neutral-700',
            className
          )}
          {...props}
        />
        {error && <p className="text-sm font-medium text-red-600 dark:text-red-200">{error}</p>}
        {hint && !error && <p className="text-sm text-gray-500 dark:text-neutral-400">{hint}</p>}
      </div>
    );
  }
);

Input.displayName = 'Input';

export default Input;
