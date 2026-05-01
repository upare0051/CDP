import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { debounce } from 'lodash-es';
import type { AxiosError } from 'axios';
import {
  ArrowLeft,
  Save,
  Sparkles,
  Users,
  Play,
  Archive,
  Loader2,
  RefreshCw,
  Eye,
  Download,
  Zap,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  getSegment,
  createSegment,
  updateSegment,
  previewSegment,
  activateSegment,
  archiveSegment,
  createSegmentFromAI,
  exportSegment,
  FilterConfig,
  SegmentCreate,
  SegmentUpdate,
} from '@/lib/api';
import { toast } from 'react-hot-toast';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/Card';
import Button from '@/components/Button';
import Input from '@/components/Input';
import FilterBuilder from '@/components/FilterBuilder';
import { PageLoader } from '@/components/LoadingSpinner';

export default function SegmentEditor() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const isNew = id === 'new';

  // Form state
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [filterConfig, setFilterConfig] = useState<FilterConfig>({ filters: [], logic: 'AND' });
  const [aiPrompt, setAiPrompt] = useState('');
  const [showAiInput, setShowAiInput] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);

  // Preview state
  const [previewCount, setPreviewCount] = useState<number | null>(null);
  const [previewSamples, setPreviewSamples] = useState<any[]>([]);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewTime, setPreviewTime] = useState<number | null>(null);

  // Fetch existing segment
  const { data: segment, isLoading } = useQuery({
    queryKey: ['segment', id],
    queryFn: () => getSegment(parseInt(id!)),
    enabled: !isNew && !!id,
  });

  // Initialize form from segment data
  useEffect(() => {
    if (segment) {
      setName(segment.name);
      setDescription(segment.description || '');
      setFilterConfig(segment.filter_config);
      setPreviewCount(segment.estimated_count);
    }
  }, [segment]);

  // Create mutation
  const createMutation = useMutation({
    mutationFn: createSegment,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['segments'] });
      navigate(`/segments/${data.id}`);
    },
  });

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: SegmentUpdate }) => updateSegment(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['segments'] });
      queryClient.invalidateQueries({ queryKey: ['segment', id] });
      setHasChanges(false);
    },
  });

  // Activate mutation
  const activateMutation = useMutation({
    mutationFn: activateSegment,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['segment', id] });
    },
  });

  // Archive mutation
  const archiveMutation = useMutation({
    mutationFn: archiveSegment,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['segment', id] });
    },
  });

  // AI generation mutation
  const aiMutation = useMutation({
    mutationFn: (query: string) => createSegmentFromAI(query, false),
    onSuccess: (data) => {
      setName(data.name);
      setDescription(data.description);
      setFilterConfig(data.filter_config);
      setPreviewCount(data.estimated_count);
      setShowAiInput(false);
      setHasChanges(true);
      toast.success('AI segment generated');
    },
    onError: (err: AxiosError<{ detail?: string }>) => {
      const detail = err.response?.data?.detail || err.message || 'Failed to generate segment from AI';
      toast.error(detail);
    },
  });

  // Export mutation
  const [exporting, setExporting] = useState(false);
  const handleExport = async () => {
    if (!id || isNew) return;
    setExporting(true);
    try {
      const blob = await exportSegment(parseInt(id));
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${name.toLowerCase().replace(/\s+/g, '_')}_${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      toast.success('Segment exported successfully!');
    } catch (error) {
      toast.error('Failed to export segment');
    } finally {
      setExporting(false);
    }
  };

  // Preview function
  const fetchPreview = useCallback(
    debounce(async (config: FilterConfig) => {
      if (config.filters.length === 0) {
        setPreviewCount(null);
        setPreviewSamples([]);
        return;
      }

      setPreviewLoading(true);
      try {
        const result = await previewSegment(config);
        setPreviewCount(result.count);
        setPreviewSamples(result.sample_customers);
        setPreviewTime(result.query_time_ms);
      } catch (error) {
        console.error('Preview failed:', error);
      } finally {
        setPreviewLoading(false);
      }
    }, 500),
    []
  );

  // Trigger preview when filters change
  useEffect(() => {
    fetchPreview(filterConfig);
  }, [filterConfig, fetchPreview]);

  // Handle filter changes
  const handleFilterChange = (config: FilterConfig) => {
    setFilterConfig(config);
    setHasChanges(true);
  };

  // Save handler
  const handleSave = () => {
    if (!name.trim()) return;

    if (isNew) {
      const data: SegmentCreate = {
        name: name.trim(),
        description: description.trim() || undefined,
        filter_config: filterConfig,
      };
      createMutation.mutate(data);
    } else {
      const data: SegmentUpdate = {
        name: name.trim(),
        description: description.trim() || undefined,
        filter_config: filterConfig,
      };
      updateMutation.mutate({ id: parseInt(id!), data });
    }
  };

  if (isLoading && !isNew) return <PageLoader />;

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/segments')}
            className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">
              {isNew ? 'Create Segment' : 'Edit Segment'}
            </h1>
            {segment && (
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                Status: <span className="capitalize">{segment.status}</span>
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Export Button */}
          {!isNew && segment && (
            <Button
              variant="secondary"
              onClick={handleExport}
              loading={exporting}
              disabled={!previewCount}
            >
              <Download className="w-4 h-4" />
              Export CSV
            </Button>
          )}

          {/* Activate to Destination */}
          {!isNew && segment && (
            <Button
              variant="secondary"
              onClick={() => navigate(`/activations?segment=${id}`)}
            >
              <Zap className="w-4 h-4" />
              Activate
            </Button>
          )}

          {/* Status Actions */}
          {segment?.status === 'draft' && (
            <Button
              variant="secondary"
              onClick={() => activateMutation.mutate(parseInt(id!))}
              loading={activateMutation.isPending}
            >
              <Play className="w-4 h-4" />
              Set Active
            </Button>
          )}
          {segment?.status === 'active' && (
            <Button
              variant="secondary"
              onClick={() => archiveMutation.mutate(parseInt(id!))}
              loading={archiveMutation.isPending}
            >
              <Archive className="w-4 h-4" />
              Archive
            </Button>
          )}

          {/* Save Button */}
          <Button
            onClick={handleSave}
            disabled={!name.trim() || (!isNew && !hasChanges)}
            loading={createMutation.isPending || updateMutation.isPending}
          >
            <Save className="w-4 h-4" />
            {isNew ? 'Create Segment' : 'Save Changes'}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="col-span-2 space-y-6">
          {/* Basic Info */}
          <Card>
            <CardHeader>
              <CardTitle>Segment Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Input
                label="Name"
                value={name}
                onChange={(e) => { setName(e.target.value); setHasChanges(true); }}
                placeholder="e.g., High Value Customers"
              />
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Description
                </label>
                <textarea
                  value={description}
                  onChange={(e) => { setDescription(e.target.value); setHasChanges(true); }}
                  placeholder="Describe this segment..."
                  rows={2}
                  className={cn(
                    "w-full px-3.5 py-2.5 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg",
                    "text-gray-900 dark:text-gray-100 placeholder:text-gray-400",
                    "focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500",
                    "transition-all duration-150 resize-none"
                  )}
                />
              </div>
            </CardContent>
          </Card>

          {/* AI Input */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-primary-500" />
                  AI Segment Builder
                </CardTitle>
                <button
                  onClick={() => setShowAiInput(!showAiInput)}
                  className="text-sm text-primary-600 dark:text-primary-400 hover:text-primary-700 dark:hover:text-primary-300"
                >
                  {showAiInput ? 'Hide' : 'Use AI'}
                </button>
              </div>
            </CardHeader>
            {showAiInput && (
              <CardContent>
                <div className="flex gap-3">
                  <input
                    type="text"
                    value={aiPrompt}
                    onChange={(e) => setAiPrompt(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && aiPrompt.trim() && aiMutation.mutate(aiPrompt)}
                    placeholder="Describe your audience in plain English..."
                    className={cn(
                      "flex-1 px-4 py-2.5 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg",
                      "text-gray-900 dark:text-gray-100 placeholder:text-gray-400",
                      "focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500"
                    )}
                    disabled={aiMutation.isPending}
                  />
                  <Button
                    onClick={() => aiMutation.mutate(aiPrompt)}
                    disabled={!aiPrompt.trim()}
                    loading={aiMutation.isPending}
                  >
                    <Sparkles className="w-4 h-4" />
                    Generate
                  </Button>
                </div>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
                  Example: "Customers in California who spent over $1000 and ordered in the last 30 days"
                </p>
              </CardContent>
            )}
          </Card>

          {/* Filter Builder */}
          <Card>
            <CardHeader>
              <CardTitle>Filter Conditions</CardTitle>
            </CardHeader>
            <CardContent>
              <FilterBuilder
                value={filterConfig}
                onChange={handleFilterChange}
              />
            </CardContent>
          </Card>
        </div>

        {/* Sidebar - Preview */}
        <div className="space-y-6">
          {/* Live Preview */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <Eye className="w-5 h-5 text-gray-400" />
                  Live Preview
                </CardTitle>
                {previewLoading && (
                  <Loader2 className="w-4 h-4 animate-spin text-gray-400" />
                )}
              </div>
            </CardHeader>
            <CardContent>
              {/* Count */}
              <div className="text-center py-4 border-b border-gray-100 dark:border-gray-800">
                <div className="flex items-center justify-center gap-2">
                  <Users className="w-6 h-6 text-primary-500" />
                  <span className="text-4xl font-bold text-gray-900 dark:text-white">
                    {previewCount !== null ? previewCount.toLocaleString() : '—'}
                  </span>
                </div>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  {filterConfig.filters.length === 0 
                    ? 'Add filters to see count'
                    : 'matching customers'
                  }
                </p>
                {previewTime !== null && (
                  <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                    Query time: {previewTime}ms
                  </p>
                )}
              </div>

              {/* Sample Customers */}
              {previewSamples.length > 0 && (
                <div className="pt-4">
                  <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-3">
                    Sample Customers
                  </h4>
                  <div className="space-y-2">
                    {previewSamples.map((customer, idx) => (
                      <div
                        key={idx}
                        className="flex items-center gap-3 p-2 bg-gray-50 dark:bg-gray-800/50 rounded-lg"
                      >
                        <div className="w-8 h-8 rounded-full bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center text-primary-700 dark:text-primary-400 font-medium text-sm">
                          {customer.first_name?.[0] || customer.email?.[0] || '?'}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                            {customer.full_name || customer.email || 'Unknown'}
                          </p>
                          <p className="text-xs text-gray-500 dark:text-gray-400 truncate">
                            {customer.email}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Refresh Button */}
              <Button
                variant="ghost"
                size="sm"
                className="w-full mt-4"
                onClick={() => fetchPreview(filterConfig)}
                disabled={previewLoading || filterConfig.filters.length === 0}
              >
                <RefreshCw className={cn("w-4 h-4", previewLoading && "animate-spin")} />
                Refresh Preview
              </Button>
            </CardContent>
          </Card>

          {/* Segment Stats (if editing) */}
          {segment && (
            <Card>
              <CardHeader>
                <CardTitle>Segment Info</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-500 dark:text-gray-400">Created</span>
                  <span className="text-gray-900 dark:text-white">
                    {new Date(segment.created_at).toLocaleDateString()}
                  </span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-500 dark:text-gray-400">Last Updated</span>
                  <span className="text-gray-900 dark:text-white">
                    {new Date(segment.updated_at).toLocaleDateString()}
                  </span>
                </div>
                {segment.last_count_at && (
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-500 dark:text-gray-400">Count Refreshed</span>
                    <span className="text-gray-900 dark:text-white">
                      {new Date(segment.last_count_at).toLocaleDateString()}
                    </span>
                  </div>
                )}
                {segment.ai_generated && (
                  <div className="flex items-center gap-2 pt-2 border-t border-gray-100 dark:border-gray-800">
                    <Sparkles className="w-4 h-4 text-primary-500" />
                    <span className="text-sm text-gray-500 dark:text-gray-400">
                      AI Generated
                    </span>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

