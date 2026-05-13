import { Sun, Moon, Monitor } from 'lucide-react';
import { useTheme } from '@/contexts/ThemeContext';
import { cn } from '@/lib/utils';

interface ThemeToggleProps {
  className?: string;
  showLabel?: boolean;
}

export default function ThemeToggle({ className, showLabel = false }: ThemeToggleProps) {
  const { theme, setTheme, resolvedTheme } = useTheme();

  const themes = [
    { value: 'light' as const, icon: Sun, label: 'Light' },
    { value: 'dark' as const, icon: Moon, label: 'Dark' },
    { value: 'system' as const, icon: Monitor, label: 'System' },
  ];

  return (
    <div className={cn("flex items-center", className)}>
      {showLabel && (
        <span className="mr-3 font-tag text-[11px] font-semibold uppercase tracking-[0.14em] text-gray-500 dark:text-neutral-400">Theme</span>
      )}
      <div className="flex items-center border border-alo-mercury bg-white dark:border-neutral-700 dark:bg-black">
        {themes.map(({ value, icon: Icon, label }) => (
          <button
            key={value}
            onClick={() => setTheme(value)}
            className={cn(
              "border-r border-alo-mercury p-2 transition-colors duration-150 last:border-r-0 dark:border-neutral-700",
              theme === value
                ? "bg-black text-white dark:bg-white dark:text-black"
                : "text-gray-500 hover:bg-alo-smoke hover:text-black dark:text-neutral-400 dark:hover:bg-neutral-900 dark:hover:text-white"
            )}
            title={label}
          >
            <Icon className="w-4 h-4" />
          </button>
        ))}
      </div>
    </div>
  );
}

// Simple toggle button version
export function ThemeToggleButton({ className }: { className?: string }) {
  const { resolvedTheme, setTheme } = useTheme();

  return (
    <button
      onClick={() => setTheme(resolvedTheme === 'dark' ? 'light' : 'dark')}
      className={cn(
        "border border-alo-mercury p-2 transition-colors",
        "text-gray-500 hover:bg-alo-smoke hover:text-black",
        "dark:border-neutral-700 dark:text-neutral-400 dark:hover:bg-neutral-900 dark:hover:text-white",
        className
      )}
      title={`Switch to ${resolvedTheme === 'dark' ? 'light' : 'dark'} mode`}
    >
      {resolvedTheme === 'dark' ? (
        <Sun className="w-5 h-5" />
      ) : (
        <Moon className="w-5 h-5" />
      )}
    </button>
  );
}
