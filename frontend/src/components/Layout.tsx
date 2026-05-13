import { ReactNode, useState, useEffect } from 'react';
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
  Table2,
  BookOpen,
  MessageSquareText,
  Activity,
  Workflow,
  Mail,
  Megaphone,
  PieChart,
  Truck,
  ChevronRight,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import ThemeToggle from '@/components/ThemeToggle';
import { AloMark } from '@/components/AloMark';

interface LayoutProps {
  children: ReactNode;
}

type NavLeaf = {
  kind?: 'leaf';
  path: string;
  icon: typeof Filter;
  label: string;
};

type NavGroup = {
  kind: 'group';
  basePath: string;       // shared prefix used to mark group "active"
  icon: typeof Filter;
  label: string;
  children: NavLeaf[];
};

type NavEntry = NavLeaf | NavGroup;

// Journey Builder surfaces Dittofeed inside cdp-main. Each child maps to a
// /journey-builder/<sub> route that iframes /dashboard/<sub> via the proxy.
// See pages/JourneyBuilder.tsx.
const navItems: NavEntry[] = [
  { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { path: '/customers', icon: Users, label: 'Customers' },
  { path: '/segments', icon: Filter, label: 'Segments' },
  { path: '/explorer', icon: Table2, label: 'Explorer' },
  { path: '/reference', icon: BookOpen, label: 'Reference' },
  { path: '/ask', icon: MessageSquareText, label: 'Ask C360' },
  { path: '/c360/model-health', icon: Activity, label: 'C360 health' },
  { path: '/activations', icon: Zap, label: 'Activations' },
  {
    kind: 'group',
    basePath: '/journey-builder',
    icon: Workflow,
    label: 'Journey Builder',
    children: [
      { path: '/journey-builder/journeys',         icon: Workflow,  label: 'Journeys' },
      { path: '/journey-builder/templates',        icon: Mail,      label: 'Templates' },
      { path: '/journey-builder/broadcasts',       icon: Megaphone, label: 'Broadcasts' },
      { path: '/journey-builder/analysis/overview',icon: PieChart,  label: 'Analytics' },
      { path: '/journey-builder/deliveries',       icon: Truck,     label: 'Deliveries' },
    ],
  },
  { path: '/sources', icon: Database, label: 'Sources' },
  { path: '/destinations', icon: Send, label: 'Destinations' },
  { path: '/syncs', icon: RefreshCw, label: 'Syncs' },
  { path: '/runs', icon: History, label: 'Run History' },
];

// Shared row styling for both top-level leaves and group children.
function rowClassName(isActive: boolean, indented = false) {
  return cn(
    'flex items-center gap-3 border px-3 py-2.5 text-left transition-colors',
    'text-sm font-medium text-gray-700 no-underline hover:bg-alo-smoke hover:text-black dark:text-neutral-300 dark:hover:bg-neutral-900 dark:hover:text-white',
    indented ? 'pl-9 text-[13px]' : '',
    isActive
      ? 'border-black bg-black text-white hover:bg-black hover:text-white dark:border-white dark:bg-white dark:text-black dark:hover:bg-white dark:hover:text-black'
      : 'border-transparent',
  );
}

export default function Layout({ children }: LayoutProps) {
  const location = useLocation();

  // Track which groups are open. A group whose basePath matches the active
  // URL is forced open; others remember per-session via local state.
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({});
  useEffect(() => {
    // When the user navigates INTO a group, auto-open it. We don't auto-close
    // when navigating away — feels less twitchy.
    setOpenGroups((prev) => {
      const next = { ...prev };
      for (const it of navItems) {
        if (it.kind === 'group' && location.pathname.startsWith(it.basePath)) {
          next[it.basePath] = true;
        }
      }
      return next;
    });
  }, [location.pathname]);

  const toggleGroup = (basePath: string) =>
    setOpenGroups((prev) => ({ ...prev, [basePath]: !prev[basePath] }));

  return (
    <div className="min-h-screen bg-white text-black dark:bg-black dark:text-white lg:grid lg:grid-cols-[248px_minmax(0,1fr)]">
      <aside className="flex flex-col gap-8 border-b border-alo-mercury bg-white p-6 dark:border-neutral-800 dark:bg-black lg:sticky lg:top-0 lg:h-screen lg:border-b-0 lg:border-r">
        <Link to="/dashboard" className="flex items-center gap-3 no-underline">
          <AloMark height={20} />
          <span className="flex flex-col gap-0.5">
            <span className="font-tag text-[11px] font-medium uppercase tracking-[0.16em] text-gray-500 dark:text-neutral-400">
              Internal
            </span>
            <span className="text-base font-semibold text-black dark:text-white">
              ActivationOS
            </span>
          </span>
        </Link>

        <nav className="flex gap-2 overflow-x-auto pb-1 lg:flex-1 lg:flex-col lg:overflow-x-visible lg:overflow-y-auto lg:pb-0">
          {navItems.map((item) => {
            if (item.kind === 'group') {
              const isOpen =
                openGroups[item.basePath] ??
                location.pathname.startsWith(item.basePath);
              const isParentActive = location.pathname.startsWith(item.basePath);

              return (
                <div key={item.basePath}>
                  <button
                    type="button"
                    onClick={() => toggleGroup(item.basePath)}
                    className={cn(rowClassName(isParentActive), 'w-full text-left')}
                    aria-expanded={isOpen}
                    aria-controls={`group-${item.basePath}`}
                  >
                    <item.icon className="w-5 h-5 shrink-0 opacity-90" />
                    <span className="flex-1">{item.label}</span>
                    <ChevronRight
                      className={cn(
                        'w-4 h-4 shrink-0 opacity-60 transition-transform',
                        isOpen && 'rotate-90',
                      )}
                    />
                  </button>
                  {isOpen && (
                    <div id={`group-${item.basePath}`} className="mt-1 hidden space-y-1 lg:block">
                      {item.children.map((child) => {
                        const isChildActive = location.pathname.startsWith(child.path);
                        return (
                          <Link
                            key={child.path}
                            to={child.path}
                            className={rowClassName(isChildActive, true)}
                          >
                            <child.icon className="w-4 h-4 shrink-0 opacity-90" />
                            <span className="flex-1">{child.label}</span>
                          </Link>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            }

            const isActive =
              location.pathname === item.path ||
              (item.path !== '/' && location.pathname.startsWith(item.path));
            return (
              <Link key={item.path} to={item.path} className={rowClassName(isActive)}>
                <item.icon className="w-5 h-5 shrink-0 opacity-90" />
                <span className="flex-1">{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="hidden border border-alo-mercury p-4 dark:border-neutral-800 lg:block">
          <div className="mb-2 flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-black dark:text-white" />
            <span className="font-tag text-[11px] font-semibold uppercase tracking-[0.14em] text-black dark:text-white">
              Ask C360
            </span>
          </div>
          <p className="text-xs leading-relaxed text-gray-500 dark:text-neutral-400">
            Governed NL to SQL on allowlisted marts.
          </p>
        </div>

        <div className="hidden border-t border-alo-mercury pt-6 dark:border-neutral-800 lg:block">
          <div className="mb-5 flex items-center gap-3">
            <div className="grid h-7 w-7 place-items-center rounded-full bg-black text-[11px] font-semibold tracking-[0.04em] text-white dark:bg-white dark:text-black">
              U
            </div>
            <div>
              <div className="text-[13px] font-medium text-gray-700 dark:text-neutral-300">
                data.ops
              </div>
              <div className="text-xs text-gray-500 dark:text-neutral-500">
                CDP admin
              </div>
            </div>
          </div>
          <ThemeToggle showLabel />
          <div className="mt-5 flex items-center gap-2 text-[11px] uppercase tracking-[0.12em] text-gray-500 dark:text-neutral-500">
            <Settings className="h-4 w-4" />
            <span>v1.0.0</span>
          </div>
        </div>
      </aside>

      <main className="min-w-0 bg-white dark:bg-black">
        <div className="mx-auto max-w-[1440px] px-6 py-10 sm:px-8 lg:px-14 lg:py-16">
          {children}
        </div>
      </main>
    </div>
  );
}
