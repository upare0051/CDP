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
        <span className="mr-3 text-xs font-semibold uppercase tracking-wider text-neutral-600 dark:text-neutral-400">Theme</span>
      )}
      <div className="flex items-center gap-1 p-1 bg-neutral-100 dark:bg-neutral-900 border border-neutral-300 dark:border-neutral-700 rounded-full">
        {themes.map(({ value, icon: Icon, label }) => (
          <button
            key={value}
            onClick={() => setTheme(value)}
            className={cn(
              "p-2 rounded-full transition-all duration-200",
              theme === value
                ? "bg-black dark:bg-white text-white dark:text-black"
                : "text-neutral-500 dark:text-neutral-400 hover:text-black dark:hover:text-white"
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
        "p-2 rounded-full transition-colors border border-transparent",
        "text-neutral-600 hover:text-black hover:bg-neutral-100 hover:border-neutral-300",
        "dark:text-neutral-400 dark:hover:text-white dark:hover:bg-neutral-900 dark:hover:border-neutral-700",
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
