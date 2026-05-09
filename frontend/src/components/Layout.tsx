import { ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  Database,
  Send,
  RefreshCw,
  History,
  LayoutDashboard,
  Settings,
  Zap,
  Users,
  Filter,
  Sparkles,
  Bell,
  Search,
  Table2,
  BookOpen,
  MessageSquareText,
  Activity,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { ThemeToggleButton } from '@/components/ThemeToggle';

interface LayoutProps {
  children: ReactNode;
}

const navItems = [
  { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { path: '/customers', icon: Users, label: 'Customers' },
  { path: '/segments', icon: Filter, label: 'Segments' },
  { path: '/explorer', icon: Table2, label: 'Explorer' },
  { path: '/reference', icon: BookOpen, label: 'Reference' },
  { path: '/ask', icon: MessageSquareText, label: 'Ask C360' },
  { path: '/c360/model-health', icon: Activity, label: 'C360 health' },
  { path: '/activations', icon: Zap, label: 'Activations' },
  { path: '/sources', icon: Database, label: 'Sources' },
  { path: '/destinations', icon: Send, label: 'Destinations' },
  { path: '/syncs', icon: RefreshCw, label: 'Syncs' },
  { path: '/runs', icon: History, label: 'Run History' },
];

export default function Layout({ children }: LayoutProps) {
  const location = useLocation();

  return (
    <div className="min-h-screen flex bg-white dark:bg-black">
      {/* Sidebar — dark “nav tier” (Sanctuary-style contrast) */}
      <aside className="w-64 bg-black dark:bg-neutral-950 text-white border-r border-neutral-800 flex flex-col">
        {/* Logo */}
        <div className="h-16 px-6 flex items-center border-b border-neutral-800 bg-white dark:bg-black">
          <Link to="/dashboard" className="flex items-center group">
            <span className="font-semibold text-black dark:text-white text-xs tracking-[0.2em] uppercase">
              ActivationOS
            </span>
          </Link>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-2 space-y-0.5">
          {navItems.map((item) => {
            const isActive = location.pathname === item.path || 
              (item.path !== '/' && location.pathname.startsWith(item.path));
            
            return (
              <Link
                key={item.path}
                to={item.path}
                className={cn(
                  'flex items-center gap-3 px-3 py-3 transition-colors text-xs font-semibold uppercase tracking-[0.14em]',
                  isActive
                    ? 'text-white border-b-2 border-white'
                    : 'text-white/55 hover:text-white border-b-2 border-transparent'
                )}
              >
                <item.icon className="w-5 h-5 shrink-0 opacity-90" />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* AI Feature Banner */}
        <div className="p-3">
          <div className="p-3 bg-neutral-900 border border-neutral-700 rounded-md">
            <div className="flex items-center gap-2 mb-1">
              <Sparkles className="w-4 h-4 text-white" />
              <span className="text-xs font-semibold uppercase tracking-wider text-white">Ask C360</span>
            </div>
            <p className="text-[11px] text-white/60 leading-relaxed">
              Governed NL→SQL on allowlisted marts
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="p-3 border-t border-neutral-800">
          <div className="flex items-center justify-between px-3 py-2 text-white/45 text-[10px] uppercase tracking-wider">
            <div className="flex items-center gap-2">
              <Settings className="w-4 h-4" />
              <span>v1.0.0</span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Header — white tier */}
        <header className="h-16 px-6 flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 bg-white dark:bg-black">
          {/* Search */}
          <div className="flex items-center gap-2 px-3 py-2 border border-neutral-300 dark:border-neutral-700 rounded-md text-neutral-500 dark:text-neutral-400 w-64 bg-white dark:bg-black">
            <Search className="w-4 h-4 text-black dark:text-white" />
            <span className="text-sm text-neutral-600 dark:text-neutral-400">Search...</span>
            <kbd className="ml-auto text-[10px] uppercase tracking-wider bg-neutral-100 dark:bg-neutral-900 px-2 py-0.5 rounded border border-neutral-300 dark:border-neutral-600 text-black dark:text-white">
              /
            </kbd>
          </div>

          {/* Right side */}
          <div className="flex items-center gap-2">
            <ThemeToggleButton />
            <button
              type="button"
              className="p-2 rounded-md text-neutral-600 hover:text-black hover:bg-neutral-100 dark:text-neutral-400 dark:hover:text-white dark:hover:bg-neutral-900 transition-colors"
            >
              <Bell className="w-5 h-5" />
            </button>
            <div className="w-9 h-9 rounded-full bg-black dark:bg-white flex items-center justify-center text-white dark:text-black font-semibold text-xs ml-2 uppercase tracking-wider">
              U
            </div>
          </div>
        </header>

        {/* Main Content Area */}
        <main className="flex-1 overflow-auto bg-white dark:bg-black">
          <div className="p-6 max-w-7xl mx-auto">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
