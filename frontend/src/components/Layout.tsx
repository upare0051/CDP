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
  ChevronRight,
  Bell,
  Search,
  Table2,
  BookOpen,
  MessageSquareText,
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
  { path: '/activations', icon: Zap, label: 'Activations' },
  { path: '/sources', icon: Database, label: 'Sources' },
  { path: '/destinations', icon: Send, label: 'Destinations' },
  { path: '/syncs', icon: RefreshCw, label: 'Syncs' },
  { path: '/runs', icon: History, label: 'Run History' },
];

export default function Layout({ children }: LayoutProps) {
  const location = useLocation();

  return (
    <div className="min-h-screen flex bg-white dark:bg-gray-950">
      {/* Sidebar */}
      <aside className="w-64 bg-gray-50 dark:bg-gray-900 border-r border-gray-200 dark:border-gray-800 flex flex-col">
        {/* Logo */}
        <div className="h-16 px-6 flex items-center border-b border-gray-200 dark:border-gray-800">
          <Link to="/dashboard" className="flex items-center gap-3 group">
            <span className="font-semibold text-gray-900 dark:text-white text-[14px] tracking-tight">
              ActivationOS
            </span>
          </Link>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-3 space-y-1">
          {navItems.map((item) => {
            const isActive = location.pathname === item.path || 
              (item.path !== '/' && location.pathname.startsWith(item.path));
            
            return (
              <Link
                key={item.path}
                to={item.path}
                className={cn(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-150 text-sm font-medium',
                  isActive
                    ? 'bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-400'
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-white'
                )}
              >
                <item.icon className="w-5 h-5" />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* AI Feature Banner */}
        <div className="p-3">
          <div className="p-3 bg-gradient-to-r from-primary-50 to-accent-50 dark:from-primary-900/20 dark:to-accent-900/20 rounded-lg border border-primary-100 dark:border-primary-800/50">
            <div className="flex items-center gap-2 mb-1">
              <Sparkles className="w-4 h-4 text-primary-600 dark:text-primary-400" />
              <span className="text-sm font-medium text-gray-900 dark:text-white">Ask C360</span>
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Governed NL→SQL on allowlisted marts
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="p-3 border-t border-gray-200 dark:border-gray-800">
          <div className="flex items-center justify-between px-3 py-2 text-gray-500 dark:text-gray-400 text-xs">
            <div className="flex items-center gap-2">
              <Settings className="w-4 h-4" />
              <span>v1.0.0</span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Top Header */}
        <header className="h-16 px-6 flex items-center justify-between border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950">
          {/* Search */}
          <div className="flex items-center gap-2 px-3 py-2 bg-gray-100 dark:bg-gray-800 rounded-lg text-gray-500 dark:text-gray-400 w-64">
            <Search className="w-4 h-4" />
            <span className="text-sm">Search...</span>
            <kbd className="ml-auto text-xs bg-white dark:bg-gray-700 px-1.5 py-0.5 rounded border border-gray-200 dark:border-gray-600">/</kbd>
          </div>

          {/* Right side */}
          <div className="flex items-center gap-2">
            <ThemeToggleButton />
            <button className="p-2 rounded-lg text-gray-500 hover:text-gray-700 hover:bg-gray-100 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:bg-gray-800 transition-colors">
              <Bell className="w-5 h-5" />
            </button>
            <div className="w-8 h-8 rounded-full bg-primary-100 dark:bg-primary-900/50 flex items-center justify-center text-primary-700 dark:text-primary-400 font-medium text-sm ml-2">
              U
            </div>
          </div>
        </header>

        {/* Main Content Area */}
        <main className="flex-1 overflow-auto bg-gray-50 dark:bg-gray-900">
          <div className="p-6 max-w-7xl mx-auto">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
