import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Users,
  Search,
  Grid3X3,
  List,
  Mail,
  Phone,
  MapPin,
  DollarSign,
  Calendar,
  ChevronRight,
  ChevronLeft,
  RefreshCw,
  TrendingUp,
  UserPlus,
} from 'lucide-react';
import { Card, CardContent } from '@/components/Card';
import Button from '@/components/Button';
import Input from '@/components/Input';
import EmptyState from '@/components/EmptyState';
import { PageLoader } from '@/components/LoadingSpinner';
import { getCustomers, getCustomerStats, CustomerListParams } from '@/lib/api';
import { formatRelativeTime, formatNumber, cn } from '@/lib/utils';
import type { CustomerProfile } from '@/types';

type ViewMode = 'table' | 'card';

export default function Customers() {
  const [viewMode, setViewMode] = useState<ViewMode>('table');
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 20;

  const params: CustomerListParams = {
    search: searchQuery || undefined,
    page: currentPage,
    page_size: pageSize,
  };

  const { data: customerData, isLoading } = useQuery({
    queryKey: ['customers', params],
    queryFn: () => getCustomers(params),
  });

  const { data: stats } = useQuery({
    queryKey: ['customerStats'],
    queryFn: getCustomerStats,
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setCurrentPage(1);
  };

  if (isLoading) return <PageLoader />;

  const customers = customerData?.customers || [];
  const totalPages = customerData?.total_pages || 1;
  const total = customerData?.total || 0;

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-surface-50 mb-2">Customers</h1>
          <p className="text-surface-400">
            Customer 360 profiles aggregated from all synced sources
          </p>
        </div>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-4 gap-4">
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-primary-500/10 flex items-center justify-center">
                  <Users className="w-5 h-5 text-primary-400" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-surface-50">
                    {formatNumber(stats.total_customers)}
                  </p>
                  <p className="text-sm text-surface-500">Total Customers</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-green-500/10 flex items-center justify-center">
                  <UserPlus className="w-5 h-5 text-green-400" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-surface-50">
                    {formatNumber(stats.customers_added_today)}
                  </p>
                  <p className="text-sm text-surface-500">Added Today</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
                  <RefreshCw className="w-5 h-5 text-blue-400" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-surface-50">
                    {formatNumber(stats.customers_synced_today)}
                  </p>
                  <p className="text-sm text-surface-500">Synced Today</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-purple-500/10 flex items-center justify-center">
                  <TrendingUp className="w-5 h-5 text-purple-400" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-surface-50">
                    {stats.avg_attributes_per_customer.toFixed(1)}
                  </p>
                  <p className="text-sm text-surface-500">Avg Attributes</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Search & View Toggle */}
      <div className="flex items-center justify-between gap-4">
        <form onSubmit={handleSearch} className="flex-1 max-w-md">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-500" />
            <input
              type="text"
              placeholder="Search by name, email, or external ID..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-surface-800 border border-surface-700 rounded-lg text-surface-100 placeholder:text-surface-500 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>
        </form>

        <div className="flex items-center gap-2 bg-surface-800 rounded-lg p-1">
          <button
            onClick={() => setViewMode('table')}
            className={cn(
              'p-2 rounded-md transition-colors',
              viewMode === 'table'
                ? 'bg-surface-700 text-surface-100'
                : 'text-surface-500 hover:text-surface-300'
            )}
          >
            <List className="w-4 h-4" />
          </button>
          <button
            onClick={() => setViewMode('card')}
            className={cn(
              'p-2 rounded-md transition-colors',
              viewMode === 'card'
                ? 'bg-surface-700 text-surface-100'
                : 'text-surface-500 hover:text-surface-300'
            )}
          >
            <Grid3X3 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Customer List */}
      {customers.length > 0 ? (
        <>
          {viewMode === 'table' ? (
            <CustomerTable customers={customers} />
          ) : (
            <CustomerGrid customers={customers} />
          )}

          {/* Pagination */}
          <div className="flex items-center justify-between">
            <p className="text-sm text-surface-500">
              Showing {((currentPage - 1) * pageSize) + 1} to {Math.min(currentPage * pageSize, total)} of {formatNumber(total)} customers
            </p>
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                icon={<ChevronLeft className="w-4 h-4" />}
                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                disabled={currentPage === 1}
              >
                Previous
              </Button>
              <span className="px-3 py-1 text-sm text-surface-400">
                Page {currentPage} of {totalPages}
              </span>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
              >
                Next
                <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            </div>
          </div>
        </>
      ) : (
        <Card>
          <EmptyState
            icon={<Users className="w-8 h-8" />}
            title="No customers found"
            description={
              searchQuery
                ? "No customers match your search. Try a different query."
                : "Customer profiles will appear here after the first sync run."
            }
          />
        </Card>
      )}
    </div>
  );
}

// Table View Component
function CustomerTable({ customers }: { customers: CustomerProfile[] }) {
  return (
    <Card className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-surface-800 text-left">
              <th className="px-4 py-3 text-sm font-medium text-surface-400">Customer</th>
              <th className="px-4 py-3 text-sm font-medium text-surface-400">Contact</th>
              <th className="px-4 py-3 text-sm font-medium text-surface-400">Location</th>
              <th className="px-4 py-3 text-sm font-medium text-surface-400">Value</th>
              <th className="px-4 py-3 text-sm font-medium text-surface-400">Sources</th>
              <th className="px-4 py-3 text-sm font-medium text-surface-400">Last Seen</th>
              <th className="px-4 py-3 text-sm font-medium text-surface-400"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-800">
            {customers.map((customer) => (
              <tr key={customer.id} className="hover:bg-surface-800/50 transition-colors">
                <td className="px-4 py-3">
                  <Link to={`/customers/${customer.id}`} className="block">
                    <p className="font-medium text-surface-100">{customer.full_name}</p>
                    <p className="text-sm text-surface-500 font-mono">{customer.external_id}</p>
                  </Link>
                </td>
                <td className="px-4 py-3">
                  <div className="space-y-1">
                    {customer.email && (
                      <div className="flex items-center gap-2 text-sm text-surface-400">
                        <Mail className="w-3 h-3" />
                        <span>{customer.email}</span>
                      </div>
                    )}
                    {customer.phone && (
                      <div className="flex items-center gap-2 text-sm text-surface-400">
                        <Phone className="w-3 h-3" />
                        <span>{customer.phone}</span>
                      </div>
                    )}
                  </div>
                </td>
                <td className="px-4 py-3">
                  {(customer.city || customer.country) && (
                    <div className="flex items-center gap-2 text-sm text-surface-400">
                      <MapPin className="w-3 h-3" />
                      <span>
                        {[customer.city, customer.country].filter(Boolean).join(', ')}
                      </span>
                    </div>
                  )}
                </td>
                <td className="px-4 py-3">
                  {customer.lifetime_value !== undefined && customer.lifetime_value !== null && (
                    <div className="flex items-center gap-2 text-sm">
                      <DollarSign className="w-3 h-3 text-green-400" />
                      <span className="text-green-400 font-medium">
                        {formatNumber(customer.lifetime_value)}
                      </span>
                    </div>
                  )}
                </td>
                <td className="px-4 py-3">
                  <span className="inline-flex items-center px-2 py-1 rounded-md bg-surface-700 text-xs text-surface-300">
                    {customer.source_count} {customer.source_count === 1 ? 'source' : 'sources'}
                  </span>
                </td>
                <td className="px-4 py-3 text-sm text-surface-500">
                  {customer.last_seen_at ? formatRelativeTime(customer.last_seen_at) : '-'}
                </td>
                <td className="px-4 py-3">
                  <Link to={`/customers/${customer.id}`}>
                    <ChevronRight className="w-4 h-4 text-surface-500 hover:text-surface-300" />
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

// Card/Grid View Component
function CustomerGrid({ customers }: { customers: CustomerProfile[] }) {
  return (
    <div className="grid grid-cols-3 gap-4">
      {customers.map((customer) => (
        <Link key={customer.id} to={`/customers/${customer.id}`}>
          <Card className="card-hover h-full">
            <CardContent className="p-4">
              {/* Header */}
              <div className="flex items-start gap-3 mb-4">
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center text-white font-bold text-lg">
                  {customer.first_name?.[0] || customer.email?.[0] || '?'}
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-surface-100 truncate">{customer.full_name}</h3>
                  <p className="text-sm text-surface-500 font-mono truncate">{customer.external_id}</p>
                </div>
              </div>

              {/* Contact Info */}
              <div className="space-y-2 mb-4">
                {customer.email && (
                  <div className="flex items-center gap-2 text-sm text-surface-400">
                    <Mail className="w-3.5 h-3.5 flex-shrink-0" />
                    <span className="truncate">{customer.email}</span>
                  </div>
                )}
                {customer.phone && (
                  <div className="flex items-center gap-2 text-sm text-surface-400">
                    <Phone className="w-3.5 h-3.5 flex-shrink-0" />
                    <span>{customer.phone}</span>
                  </div>
                )}
                {(customer.city || customer.country) && (
                  <div className="flex items-center gap-2 text-sm text-surface-400">
                    <MapPin className="w-3.5 h-3.5 flex-shrink-0" />
                    <span>{[customer.city, customer.country].filter(Boolean).join(', ')}</span>
                  </div>
                )}
              </div>

              {/* Footer Stats */}
              <div className="flex items-center justify-between pt-3 border-t border-surface-800">
                {customer.lifetime_value !== undefined && customer.lifetime_value !== null ? (
                  <div className="flex items-center gap-1 text-green-400">
                    <DollarSign className="w-4 h-4" />
                    <span className="font-semibold">{formatNumber(customer.lifetime_value)}</span>
                  </div>
                ) : (
                  <div />
                )}
                <div className="flex items-center gap-2 text-xs text-surface-500">
                  <Calendar className="w-3 h-3" />
                  <span>{customer.last_seen_at ? formatRelativeTime(customer.last_seen_at) : 'Never'}</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </Link>
      ))}
    </div>
  );
}

