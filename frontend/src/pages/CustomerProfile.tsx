import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ArrowLeft,
  Mail,
  Phone,
  MapPin,
  Calendar,
  DollarSign,
  Database,
  Activity,
  Tag,
  Link as LinkIcon,
  RefreshCw,
  Clock,
  User,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/Card';
import Button from '@/components/Button';
import { PageLoader } from '@/components/LoadingSpinner';
import CustomerInsights from '@/components/CustomerInsights';
import { getCustomer, getCustomerTimeline } from '@/lib/api';
import { formatRelativeTime, formatNumber, cn } from '@/lib/utils';

export default function CustomerProfile() {
  const { id } = useParams<{ id: string }>();
  const [activeTab, setActiveTab] = useState<TabType>('overview');

  const { data: customer, isLoading } = useQuery({
    queryKey: ['customer', id],
    queryFn: () => getCustomer(parseInt(id!)),
    enabled: !!id,
  });

  const { data: timeline } = useQuery({
    queryKey: ['customerTimeline', id],
    queryFn: () => getCustomerTimeline(parseInt(id!), 100),
    enabled: !!id && activeTab === 'timeline',
  });

  if (isLoading) return <PageLoader />;
  if (!customer) return <div>Customer not found</div>;

  const tabs: { key: TabType; label: string; icon: React.ReactNode }[] = [
    { key: 'overview', label: 'Overview', icon: <User className="w-4 h-4" /> },
    { key: 'attributes', label: 'Attributes', icon: <Tag className="w-4 h-4" /> },
    { key: 'timeline', label: 'Timeline', icon: <Activity className="w-4 h-4" /> },
    { key: 'identities', label: 'Identities', icon: <LinkIcon className="w-4 h-4" /> },
  ];

  return (
    <div className="space-y-6 animate-fade-in">
      <Link
        to="/customers"
        className="inline-flex items-center gap-2 text-surface-400 hover:text-surface-200 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Customers
      </Link>

      <Card className="overflow-hidden">
        <div className="bg-gradient-to-r from-primary-600/20 to-primary-800/20 p-6">
          <div className="flex items-start gap-6">
            <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center text-white font-bold text-3xl shadow-lg">
              {customer.first_name?.[0] || customer.email?.[0] || '?'}
            </div>

            <div className="flex-1">
              <h1 className="text-3xl font-bold text-surface-50 mb-1">{customer.full_name}</h1>
              <p className="text-surface-400 font-mono mb-3">{customer.external_id}</p>

              <div className="flex flex-wrap items-center gap-4">
                {customer.email && (
                  <div className="flex items-center gap-2 text-surface-300">
                    <Mail className="w-4 h-4 text-surface-500" />
                    <span>{customer.email}</span>
                  </div>
                )}
                {customer.phone && (
                  <div className="flex items-center gap-2 text-surface-300">
                    <Phone className="w-4 h-4 text-surface-500" />
                    <span>{customer.phone}</span>
                  </div>
                )}
                {(customer.city || customer.country) && (
                  <div className="flex items-center gap-2 text-surface-300">
                    <MapPin className="w-4 h-4 text-surface-500" />
                    <span>{[customer.city, customer.country].filter(Boolean).join(', ')}</span>
                  </div>
                )}
              </div>
            </div>

            <div className="flex gap-6">
              {customer.lifetime_value !== undefined && customer.lifetime_value !== null && (
                <div className="text-center">
                  <p className="text-3xl font-bold text-green-400">${formatNumber(customer.lifetime_value)}</p>
                  <p className="text-sm text-surface-500">Lifetime Value</p>
                </div>
              )}
              <div className="text-center">
                <p className="text-3xl font-bold text-surface-100">{customer.source_count}</p>
                <p className="text-sm text-surface-500">Sources</p>
              </div>
              <div className="text-center">
                <p className="text-3xl font-bold text-surface-100">{customer.attributes?.length || 0}</p>
                <p className="text-sm text-surface-500">Attributes</p>
              </div>
            </div>
          </div>
        </div>

        <div className="px-6 py-3 bg-surface-800/50 flex items-center gap-6 text-sm text-surface-500">
          <div className="flex items-center gap-2">
            <Calendar className="w-4 h-4" />
            <span>First seen: {customer.first_seen_at ? formatRelativeTime(customer.first_seen_at) : 'N/A'}</span>
          </div>
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4" />
            <span>Last seen: {customer.last_seen_at ? formatRelativeTime(customer.last_seen_at) : 'N/A'}</span>
          </div>
          <div className="flex items-center gap-2">
            <RefreshCw className="w-4 h-4" />
            <span>Last synced: {customer.last_synced_at ? formatRelativeTime(customer.last_synced_at) : 'Never'}</span>
          </div>
        </div>
      </Card>

      <div className="border-b border-surface-800">
        <nav className="flex gap-4">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={cn(
                'flex items-center gap-2 px-4 py-3 border-b-2 transition-colors',
                activeTab === tab.key
                  ? 'border-primary-500 text-primary-400'
                  : 'border-transparent text-surface-500 hover:text-surface-300'
              )}
            >
              {tab.icon}
              <span>{tab.label}</span>
              {tab.key === 'attributes' && (
                <span className="ml-1 px-1.5 py-0.5 text-xs bg-surface-700 rounded">
                  {customer.attributes?.length || 0}
                </span>
              )}
            </button>
          ))}
        </nav>
      </div>

      <div className="min-h-[400px]">
        {activeTab === 'overview' && <OverviewTab customer={customer} />}
        {activeTab === 'attributes' && <AttributesTab customer={customer} />}
        {activeTab === 'timeline' && <TimelineTab events={timeline || customer.recent_events || []} />}
        {activeTab === 'identities' && <IdentitiesTab customer={customer} />}
      </div>
    </div>
  );
}

type TabType = 'overview' | 'attributes' | 'timeline' | 'identities';

function OverviewTab({ customer }: { customer: any }) {
  const getAttributeValue = (names: string[]) => {
    for (const name of names) {
      const attr = customer.attributes?.find((a: any) => a.attribute_name.toLowerCase() === name.toLowerCase());
      if (attr) return attr.attribute_value;
    }
    return null;
  };

  return (
    <div className="space-y-6">
      <CustomerInsights customerId={customer.id} />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <DollarSign className="w-4 h-4 text-green-400" />
              Key Metrics
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <MetricRow label="Lifetime Value" value={customer.lifetime_value ? `$${formatNumber(customer.lifetime_value)}` : '-'} />
            <MetricRow label="Total Orders" value={customer.total_orders || getAttributeValue(['total_orders', 'order_count']) || '-'} />
            <MetricRow label="Subscription" value={getAttributeValue(['is_subscribed', 'email_subscribe']) || '-'} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-blue-400" />
              Recent Activity
            </CardTitle>
          </CardHeader>
          <CardContent>
            {customer.recent_events?.length > 0 ? (
              <div className="space-y-3">
                {customer.recent_events.slice(0, 5).map((event: any) => (
                  <div key={event.id} className="flex items-start gap-3">
                    <div className="w-2 h-2 rounded-full bg-blue-400 mt-2" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-surface-200 truncate">{event.title}</p>
                      <p className="text-xs text-surface-500">{formatRelativeTime(event.occurred_at)}</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-surface-500 text-sm">No recent activity</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="w-4 h-4 text-purple-400" />
              Data Sources
            </CardTitle>
          </CardHeader>
          <CardContent>
            {customer.identities?.length > 0 ? (
              <div className="space-y-3">
                {customer.identities.map((identity: any) => (
                  <div key={identity.id} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Database className="w-4 h-4 text-surface-500" />
                      <span className="text-sm text-surface-200">{identity.source_name || 'Unknown Source'}</span>
                    </div>
                    {identity.is_primary && (
                      <span className="text-xs px-2 py-0.5 bg-primary-500/20 text-primary-400 rounded">Primary</span>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-surface-500 text-sm">No sources linked</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function MetricRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-surface-500">{label}</span>
      <span className="text-surface-200 font-medium">{value}</span>
    </div>
  );
}

function AttributesTab({ customer }: { customer: any }) {
  const attributes = customer.attributes || [];
  const groupedBySource: Record<string, any[]> = {};
  attributes.forEach((attr: any) => {
    const source = attr.source_name || 'Unknown Source';
    if (!groupedBySource[source]) groupedBySource[source] = [];
    groupedBySource[source].push(attr);
  });

  return (
    <div className="space-y-6">
      {Object.entries(groupedBySource).map(([source, attrs]) => (
        <Card key={source}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Database className="w-4 h-4 text-surface-500" />
              {source}
              <span className="text-sm text-surface-500 font-normal">({attrs.length} attributes)</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {attrs.map((attr: any) => (
                <div key={attr.id} className="flex justify-between py-2 border-b border-surface-800 last:border-0">
                  <span className="text-surface-500 font-mono text-sm">{attr.attribute_name}</span>
                  <span className="text-surface-200 text-sm truncate max-w-[220px]" title={attr.attribute_value}>
                    {attr.attribute_value || '-'}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ))}

      {attributes.length === 0 && (
        <Card>
          <CardContent className="py-12 text-center">
            <Tag className="w-12 h-12 text-surface-600 mx-auto mb-4" />
            <p className="text-surface-400">No attributes found</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function TimelineTab({ events }: { events: any[] }) {
  const getEventIcon = (eventType: string) => {
    switch (eventType) {
      case 'profile_created':
        return <User className="w-4 h-4" />;
      case 'synced_from_source':
        return <RefreshCw className="w-4 h-4" />;
      case 'attribute_updated':
        return <Tag className="w-4 h-4" />;
      default:
        return <Activity className="w-4 h-4" />;
    }
  };

  const getEventColor = (eventType: string) => {
    switch (eventType) {
      case 'profile_created':
        return 'bg-green-500';
      case 'synced_from_source':
        return 'bg-blue-500';
      case 'attribute_updated':
        return 'bg-yellow-500';
      default:
        return 'bg-surface-500';
    }
  };

  return (
    <Card>
      <CardContent className="p-6">
        {events.length > 0 ? (
          <div className="relative">
            <div className="absolute left-[19px] top-0 bottom-0 w-px bg-surface-700" />
            <div className="space-y-6">
              {events.map((event: any) => (
                <div key={event.id} className="relative flex gap-4">
                  <div className={cn('w-10 h-10 rounded-full flex items-center justify-center text-white z-10', getEventColor(event.event_type))}>
                    {getEventIcon(event.event_type)}
                  </div>
                  <div className="flex-1 pb-6">
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="font-medium text-surface-200">{event.title}</p>
                        {event.description && <p className="text-sm text-surface-500 mt-1">{event.description}</p>}
                        {event.source_name && <p className="text-xs text-surface-600 mt-1">Source: {event.source_name}</p>}
                      </div>
                      <span className="text-sm text-surface-500">{formatRelativeTime(event.occurred_at)}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="py-12 text-center">
            <Activity className="w-12 h-12 text-surface-600 mx-auto mb-4" />
            <p className="text-surface-400">No events recorded</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function IdentitiesTab({ customer }: { customer: any }) {
  const identities = customer.identities || [];
  return (
    <Card>
      <CardHeader>
        <CardTitle>Linked Identities</CardTitle>
      </CardHeader>
      <CardContent>
        {identities.length > 0 ? (
          <div className="space-y-4">
            {identities.map((identity: any) => (
              <div key={identity.id} className="flex items-center justify-between p-4 bg-surface-800 rounded-lg">
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 rounded-lg bg-surface-700 flex items-center justify-center">
                    <LinkIcon className="w-5 h-5 text-surface-400" />
                  </div>
                  <div>
                    <p className="font-medium text-surface-200">{identity.identity_type}</p>
                    <p className="text-sm text-surface-500 font-mono">{identity.identity_value}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {identity.source_name && <span className="text-sm text-surface-500">{identity.source_name}</span>}
                  {identity.is_primary && <span className="px-2 py-1 text-xs bg-primary-500/20 text-primary-400 rounded">Primary</span>}
                  {identity.verified && <span className="px-2 py-1 text-xs bg-green-500/20 text-green-400 rounded">Verified</span>}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="py-12 text-center">
            <LinkIcon className="w-12 h-12 text-surface-600 mx-auto mb-4" />
            <p className="text-surface-400">No identities linked</p>
            <p className="text-sm text-surface-600 mt-1">Identities are created when customer data is synced from sources</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

