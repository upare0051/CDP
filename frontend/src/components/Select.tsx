import { SelectHTMLAttributes, forwardRef } from 'react';
import { cn } from '@/lib/utils';
import { ChevronDown } from 'lucide-react';

interface Option {
  value: string;
  label: string;
}

interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'children'> {
  label?: string;
  error?: string;
  options: Option[];
  placeholder?: string;
}

const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, error, options, placeholder, className, ...props }, ref) => {
    return (
      <div className="space-y-1.5">
        {label && (
          <label className="block font-tag text-[11px] font-semibold uppercase tracking-[0.14em] text-black dark:text-white">
            {label}
          </label>
        )}
        <div className="relative">
          <select
            ref={ref}
            className={cn(
              'w-full border bg-white px-3.5 py-3 text-sm text-black dark:bg-black dark:text-white',
              'appearance-none cursor-pointer',
              'focus:border-black focus:outline-none focus:ring-2 focus:ring-black/15 dark:focus:border-white dark:focus:ring-white/25',
              'transition-colors duration-150',
              error
                ? 'border-black dark:border-white ring-1 ring-black dark:ring-white'
                : 'border-alo-mercury dark:border-neutral-700',
              className
            )}
            {...props}
          >
            {placeholder && (
              <option value="" disabled>
                {placeholder}
              </option>
            )}
            {options.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500 dark:text-neutral-400" />
        </div>
        {error && <p className="text-sm font-medium text-red-600 dark:text-red-200">{error}</p>}
      </div>
    );
  }
);

Select.displayName = 'Select';

export default Select;
