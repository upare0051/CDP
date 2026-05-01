import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  Users,
  Users2,
  Zap,
  TrendingUp,
  TrendingDown,
  ArrowRight,
  CheckCircle,
  XCircle,
  Clock,
  Play,
  Sparkles,
  RefreshCw,
  Database,
  Send,
} from 'lucide-react';
import { Card, CardContent, CardHeader } from '@/components/Card';
import StatusBadge from '@/components/StatusBadge';
import { PageLoader } from '@/components/LoadingSpinner';
import Button from '@/components/Button';
import { 
  getDashboardStats, 
  getCustomerStats,
  getSources, 
  getDestinations,
  getSyncs,
  getRuns,
  getRunStats,
} from '@/lib/api';
import { formatNumber, formatRelativeTime, cn } from '@/lib/utils';

export default function Dashboard() {
  // Fetch all dashboard data
  const { data: stats, isLoading: statsLoading } = useQuery({ 
    queryKey: ['dashboardStats'], 
    queryFn: getDashboardStats 
  });
  const { data: customerStats } = useQuery({
    queryKey: ['customerStats'],
    queryFn: getCustomerStats,
  });
  const { data: sources } = useQuery({ queryKey: ['sources'], queryFn: getSources });
  const { data: destinations } = useQuery({ queryKey: ['destinations'], queryFn: getDestinations });
  const { data: syncs } = useQuery({ queryKey: ['syncs'], queryFn: getSyncs });
  const { data: runs } = useQuery({ queryKey: ['runs'], queryFn: () => getRuns(undefined, 5) });
  const { data: runStats } = useQuery({ queryKey: ['runStats'], queryFn: getRunStats });

  if (statsLoading) return <PageLoader />;

  const activeSyncs = syncs?.filter(s => s.is_active && !s.is_paused).length || 0;

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">Dashboard</h1>
          <p className="text-gray-500 dark:text-gray-400">
            Welcome back! Here's what's happening with your customer data.
          </p>
        </div>
        <Link to="/segments/new">
          <Button icon={<Sparkles className="w-4 h-4" />}>
            Create Segment
          </Button>
        </Link>
      </div>

      {/* Customer & Segment Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="stagger-1 animate-slide-in card-hover">
          <CardContent>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-500 dark:text-gray-400 text-sm font-medium">Total Customers</p>
                <p className="text-3xl font-bold text-gray-900 dark:text-white mt-1">
                  {formatNumber(customerStats?.total_customers || stats?.total_customers || 0)}
                </p>
                <div className="flex items-center gap-1 mt-2">
                  <TrendingUp className="w-4 h-4 text-green-500" />
                  <span className="text-sm text-green-500">
                    +{formatNumber(customerStats?.customers_added_this_week || stats?.customers_added_week || 0)} this week
                  </span>
                </div>
              </div>
              <div className="w-14 h-14 rounded-xl bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center">
                <Users className="w-7 h-7 text-primary-600 dark:text-primary-400" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="stagger-2 animate-slide-in card-hover">
          <CardContent>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-500 dark:text-gray-400 text-sm font-medium">Active Segments</p>
                <p className="text-3xl font-bold text-gray-900 dark:text-white mt-1">
                  {stats?.active_segments || 0}
                  <span className="text-lg text-gray-400 dark:text-gray-500 font-normal"> / {stats?.total_segments || 0}</span>
                </p>
                <div className="flex items-center gap-1 mt-2">
                  <span className="text-sm text-gray-500 dark:text-gray-400">
                    {stats?.segments_created_week || 0} created this week
                  </span>
                </div>
              </div>
              <div className="w-14 h-14 rounded-xl bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center">
                <Users2 className="w-7 h-7 text-purple-600 dark:text-purple-400" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="stagger-3 animate-slide-in card-hover">
          <CardContent>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-500 dark:text-gray-400 text-sm font-medium">Active Activations</p>
                <p className="text-3xl font-bold text-gray-900 dark:text-white mt-1">
                  {stats?.active_activations || 0}
                  <span className="text-lg text-gray-400 dark:text-gray-500 font-normal"> / {stats?.total_activations || 0}</span>
                </p>
                <div className="flex items-center gap-1 mt-2">
                  <span className="text-sm text-gray-500 dark:text-gray-400">
                    {stats?.syncs_today || 0} syncs today
                  </span>
                </div>
              </div>
              <div className="w-14 h-14 rounded-xl bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
                <Zap className="w-7 h-7 text-green-600 dark:text-green-400" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="stagger-4 animate-slide-in card-hover">
          <CardContent>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-500 dark:text-gray-400 text-sm font-medium">Total Rows Synced</p>
                <p className="text-3xl font-bold text-gray-900 dark:text-white mt-1">
                  {formatNumber(runStats?.total_rows_synced || 0)}
                </p>
                <div className="flex items-center gap-1 mt-2">
                  <span className="text-sm text-green-500">
                    {runStats?.success_rate?.toFixed(0) || 0}% success rate
                  </span>
                </div>
              </div>
              <div className="w-14 h-14 rounded-xl bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
                <TrendingUp className="w-7 h-7 text-blue-600 dark:text-blue-400" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Top Segments */}
        <Card className="lg:col-span-2">
          <CardHeader className="flex-row items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Top Segments by Size</h2>
            <Link
              to="/segments"
              className="text-sm text-primary-600 dark:text-primary-400 hover:text-primary-700 dark:hover:text-primary-300 flex items-center gap-1"
            >
              View all <ArrowRight className="w-4 h-4" />
            </Link>
          </CardHeader>
          <CardContent className="p-0">
            {stats?.top_segments && stats.top_segments.length > 0 ? (
              <div className="divide-y divide-gray-200 dark:divide-gray-700">
                {stats.top_segments.map((segment, index) => (
                  <Link
                    key={segment.id}
                    to={`/segments/${segment.id}`}
                    className="flex items-center justify-between px-6 py-4 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
                  >
                    <div className="flex items-center gap-4">
                      <div className="w-8 h-8 rounded-full bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center text-primary-600 dark:text-primary-400 font-semibold text-sm">
                        {index + 1}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <p className="font-medium text-gray-900 dark:text-white">{segment.name}</p>
                          {segment.ai_generated && (
                            <Sparkles className="w-4 h-4 text-purple-500" />
                          )}
                        </div>
                        <StatusBadge status={segment.status} size="sm" />
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="font-semibold text-gray-900 dark:text-white">
                        {formatNumber(segment.count || 0)}
                      </p>
                      <p className="text-sm text-gray-500 dark:text-gray-400">customers</p>
                    </div>
                  </Link>
                ))}
              </div>
            ) : (
              <div className="px-6 py-8 text-center text-gray-500 dark:text-gray-400">
                <Users2 className="w-8 h-8 mx-auto mb-3 opacity-50" />
                <p>No segments created yet</p>
                <Link to="/segments/new" className="text-primary-600 dark:text-primary-400 hover:underline text-sm mt-2 inline-block">
                  Create your first segment
                </Link>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Quick Actions */}
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Quick Actions</h2>
          </CardHeader>
          <CardContent className="space-y-3">
            <Link to="/segments/new">
              <div className="p-4 rounded-lg border border-gray-200 dark:border-gray-700 hover:border-primary-400 dark:hover:border-primary-500 hover:bg-primary-50 dark:hover:bg-primary-900/10 transition-colors group cursor-pointer">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center group-hover:bg-primary-200 dark:group-hover:bg-primary-800/30 transition-colors">
                    <Sparkles className="w-5 h-5 text-primary-600 dark:text-primary-400" />
                  </div>
                  <div>
                    <p className="font-medium text-gray-900 dark:text-white">Build AI Segment</p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">Use natural language</p>
                  </div>
                </div>
              </div>
            </Link>

            <Link to="/customers">
              <div className="p-4 rounded-lg border border-gray-200 dark:border-gray-700 hover:border-purple-400 dark:hover:border-purple-500 hover:bg-purple-50 dark:hover:bg-purple-900/10 transition-colors group cursor-pointer">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center group-hover:bg-purple-200 dark:group-hover:bg-purple-800/30 transition-colors">
                    <Users className="w-5 h-5 text-purple-600 dark:text-purple-400" />
                  </div>
                  <div>
                    <p className="font-medium text-gray-900 dark:text-white">View Customers</p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">Customer 360 profiles</p>
                  </div>
                </div>
              </div>
            </Link>

            <Link to="/syncs/new">
              <div className="p-4 rounded-lg border border-gray-200 dark:border-gray-700 hover:border-green-400 dark:hover:border-green-500 hover:bg-green-50 dark:hover:bg-green-900/10 transition-colors group cursor-pointer">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-green-100 dark:bg-green-900/30 flex items-center justify-center group-hover:bg-green-200 dark:group-hover:bg-green-800/30 transition-colors">
                    <RefreshCw className="w-5 h-5 text-green-600 dark:text-green-400" />
                  </div>
                  <div>
                    <p className="font-medium text-gray-900 dark:text-white">Create Sync Job</p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">Activate data to tools</p>
                  </div>
                </div>
              </div>
            </Link>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Activations */}
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Recent Activations</h2>
            <Link
              to="/syncs"
              className="text-sm text-primary-600 dark:text-primary-400 hover:text-primary-700 dark:hover:text-primary-300 flex items-center gap-1"
            >
              View all <ArrowRight className="w-4 h-4" />
            </Link>
          </CardHeader>
          <CardContent className="p-0">
            {stats?.recent_activations && stats.recent_activations.length > 0 ? (
              <div className="divide-y divide-gray-200 dark:divide-gray-700">
                {stats.recent_activations.map((activation) => (
                  <div
                    key={activation.id}
                    className="flex items-center justify-between px-6 py-4"
                  >
                    <div className="flex items-center gap-3">
                      {activation.status === 'active' ? (
                        <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                      ) : (
                        <div className="w-2 h-2 rounded-full bg-gray-400" />
                      )}
                      <div>
                        <p className="font-medium text-gray-900 dark:text-white">{activation.name || 'Unnamed'}</p>
                        <p className="text-sm text-gray-500 dark:text-gray-400">
                          {activation.segment_name} → {activation.destination_name}
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      {activation.last_sync_count !== null && (
                        <p className="text-sm font-medium text-gray-900 dark:text-white">
                          {formatNumber(activation.last_sync_count)} synced
                        </p>
                      )}
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        {activation.last_sync_at ? formatRelativeTime(activation.last_sync_at) : 'Never'}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="px-6 py-8 text-center text-gray-500 dark:text-gray-400">
                <Zap className="w-8 h-8 mx-auto mb-3 opacity-50" />
                <p>No activations yet</p>
                <p className="text-sm mt-1">Activate a segment to sync it to your tools</p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Recent Runs */}
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Recent Sync Runs</h2>
            <Link
              to="/runs"
              className="text-sm text-primary-600 dark:text-primary-400 hover:text-primary-700 dark:hover:text-primary-300 flex items-center gap-1"
            >
              View all <ArrowRight className="w-4 h-4" />
            </Link>
          </CardHeader>
          <CardContent className="p-0">
            {runs && runs.length > 0 ? (
              <div className="divide-y divide-gray-200 dark:divide-gray-700">
                {runs.map((run) => (
                  <div
                    key={run.id}
                    className="flex items-center justify-between px-6 py-4"
                  >
                    <div className="flex items-center gap-3">
                      {run.status === 'completed' ? (
                        <CheckCircle className="w-5 h-5 text-green-500" />
                      ) : run.status === 'failed' ? (
                        <XCircle className="w-5 h-5 text-red-500" />
                      ) : run.status === 'running' ? (
                        <RefreshCw className="w-5 h-5 text-blue-500 animate-spin" />
                      ) : (
                        <Clock className="w-5 h-5 text-yellow-500" />
                      )}
                      <div>
                        <p className="font-medium text-gray-900 dark:text-white">{run.sync_job_name}</p>
                        <p className="text-sm text-gray-500 dark:text-gray-400">
                          {formatNumber(run.rows_synced)} rows • {formatRelativeTime(run.started_at)}
                        </p>
                      </div>
                    </div>
                    <StatusBadge status={run.status} size="sm" />
                  </div>
                ))}
              </div>
            ) : (
              <div className="px-6 py-8 text-center text-gray-500 dark:text-gray-400">
                <RefreshCw className="w-8 h-8 mx-auto mb-3 opacity-50" />
                <p>No runs yet</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Infrastructure Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
              <Database className="w-5 h-5 text-blue-600 dark:text-blue-400" />
            </div>
            <div>
              <p className="text-2xl font-semibold text-gray-900 dark:text-white">{sources?.length || 0}</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">Sources</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center">
              <Send className="w-5 h-5 text-purple-600 dark:text-purple-400" />
            </div>
            <div>
              <p className="text-2xl font-semibold text-gray-900 dark:text-white">{destinations?.length || 0}</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">Destinations</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
              <RefreshCw className="w-5 h-5 text-green-600 dark:text-green-400" />
            </div>
            <div>
              <p className="text-2xl font-semibold text-gray-900 dark:text-white">{activeSyncs}</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">Active Syncs</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-yellow-100 dark:bg-yellow-900/30 flex items-center justify-center">
              <Clock className="w-5 h-5 text-yellow-600 dark:text-yellow-400" />
            </div>
            <div>
              <p className="text-2xl font-semibold text-gray-900 dark:text-white">
                {runStats?.runs_last_24h || 0}
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-400">Runs Today</p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
