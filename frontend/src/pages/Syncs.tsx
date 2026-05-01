import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  RefreshCw,
  Plus,
  Play,
  Pause,
  Trash2,
  ChevronRight,
  Clock,
  ArrowRight,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { Card, CardContent } from '@/components/Card';
import Button from '@/components/Button';
import Input from '@/components/Input';
import Select from '@/components/Select';
import Modal from '@/components/Modal';
import StatusBadge from '@/components/StatusBadge';
import EmptyState from '@/components/EmptyState';
import { PageLoader } from '@/components/LoadingSpinner';
import {
  getSyncs,
  getSources,
  getDestinations,
  createSync,
  deleteSync,
  triggerSync,
  pauseSync,
  resumeSync,
  getSourceSchemas,
  getSourceTables,
  getSourceTableSchema,
} from '@/lib/api';
import { formatRelativeTime, formatNumber } from '@/lib/utils';
import type { SyncJobCreate, SyncMode, ScheduleType, FieldMapping } from '@/types';

export default function Syncs() {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState<SyncJobCreate>({
    name: '',
    source_connection_id: 0,
    destination_connection_id: 0,
    source_schema: '',
    source_table: '',
    sync_mode: 'full_refresh',
    sync_key: 'external_id',
    schedule_type: 'manual',
    field_mappings: [],
  });
  const [schemas, setSchemas] = useState<string[]>([]);
  const [tables, setTables] = useState<{ table_name: string }[]>([]);
  const [columns, setColumns] = useState<{ column_name: string; data_type: string }[]>([]);

  const queryClient = useQueryClient();
  const { data: syncs, isLoading } = useQuery({ queryKey: ['syncs'], queryFn: getSyncs });
  const { data: sources } = useQuery({ queryKey: ['sources'], queryFn: getSources });
  const { data: destinations } = useQuery({ queryKey: ['destinations'], queryFn: getDestinations });

  const createMutation = useMutation({
    mutationFn: createSync,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['syncs'] });
      setIsModalOpen(false);
      resetForm();
      toast.success('Sync job created');
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteSync,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['syncs'] });
      toast.success('Sync job deleted');
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const triggerMutation = useMutation({
    mutationFn: (id: number) => triggerSync(id),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['syncs'] });
      queryClient.invalidateQueries({ queryKey: ['runs'] });
      toast.success(result.message);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const pauseMutation = useMutation({
    mutationFn: pauseSync,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['syncs'] });
      toast.success('Sync job paused');
    },
  });

  const resumeMutation = useMutation({
    mutationFn: resumeSync,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['syncs'] });
      toast.success('Sync job resumed');
    },
  });

  const resetForm = () => {
    setStep(1);
    setFormData({
      name: '',
      source_connection_id: 0,
      destination_connection_id: 0,
      source_schema: '',
      source_table: '',
      sync_mode: 'full_refresh',
      sync_key: 'external_id',
      schedule_type: 'manual',
      field_mappings: [],
    });
    setSchemas([]);
    setTables([]);
    setColumns([]);
  };

  const handleSourceChange = async (sourceId: number) => {
    setFormData((prev) => ({
      ...prev,
      source_connection_id: sourceId,
      source_schema: '',
      source_table: '',
      field_mappings: [],
    }));
    setSchemas([]);
    setTables([]);
    setColumns([]);

    if (!sourceId) return;

    try {
      const schemaList = await getSourceSchemas(sourceId);
      setSchemas(schemaList || []);
    } catch {
      setSchemas([]);
    }
  };

  const handleSchemaChange = async (schema: string) => {
    const sourceId = formData.source_connection_id;
    setFormData((prev) => ({
      ...prev,
      source_schema: schema,
      source_table: '',
      field_mappings: [],
    }));
    setTables([]);
    setColumns([]);

    if (!sourceId || !schema) return;

    try {
      const tableList = await getSourceTables(sourceId, schema);
      setTables(tableList || []);
    } catch {
      setTables([]);
    }
  };

  const handleTableChange = async (table: string) => {
    const sourceId = formData.source_connection_id;
    const schema = formData.source_schema;
    setFormData((prev) => ({ ...prev, source_table: table }));

    if (!sourceId || !schema || !table) return;

    try {
      const tableSchema = await getSourceTableSchema(sourceId, schema, table);
      setColumns(tableSchema.columns || []);

      // Auto-generate field mappings
      const mappings: Omit<FieldMapping, 'id' | 'sync_job_id' | 'created_at'>[] = (tableSchema.columns || []).map(col => ({
        source_field: col.column_name,
        source_field_type: col.data_type,
        destination_field: col.column_name,
        is_sync_key: col.column_name === 'external_id',
        is_required: col.column_name === 'external_id',
      }));
      setFormData(prev => ({ ...prev, field_mappings: mappings }));
    } catch {
      setColumns([]);
      setFormData((prev) => ({ ...prev, field_mappings: [] }));
    }
  };

  useEffect(() => {
    if (!isModalOpen) return;

    if ((sources?.length || 0) === 1 && !formData.source_connection_id) {
      handleSourceChange(sources![0].id);
    }

    if ((destinations?.length || 0) === 1 && !formData.destination_connection_id) {
      setFormData((prev) => ({ ...prev, destination_connection_id: destinations![0].id }));
    }
  }, [
    isModalOpen,
    sources,
    destinations,
    formData.source_connection_id,
    formData.destination_connection_id,
  ]);

  const handleSubmit = () => {
    createMutation.mutate(formData);
  };

  if (isLoading) return <PageLoader />;

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-surface-50 mb-2">Syncs</h1>
          <p className="text-surface-400">Manage your data sync jobs</p>
        </div>
        <Button icon={<Plus className="w-4 h-4" />} onClick={() => setIsModalOpen(true)}>
          Create Sync
        </Button>
      </div>

      {syncs && syncs.length > 0 ? (
        <div className="space-y-4">
          {syncs.map((sync) => (
            <Card key={sync.id} className="card-hover">
              <CardContent>
                <div className="flex items-center justify-between">
                  <Link to={`/syncs/${sync.id}`} className="flex-1 flex items-center gap-4">
                    <div className="w-12 h-12 rounded-xl bg-primary-500/10 flex items-center justify-center">
                      <RefreshCw className="w-6 h-6 text-primary-400" />
                    </div>
                    <div className="flex-1">
                      <h3 className="font-semibold text-surface-100">{sync.name}</h3>
                      <p className="text-sm text-surface-500">
                        {sync.source_connection_name}
                        <ArrowRight className="w-4 h-4 inline mx-2" />
                        {sync.destination_connection_name}
                      </p>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="text-right">
                        <p className="text-sm text-surface-500">
                          {sync.last_run_at ? formatRelativeTime(sync.last_run_at) : 'Never run'}
                        </p>
                        <p className="text-xs text-surface-500">
                          {formatNumber(sync.total_rows_synced)} rows synced
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <StatusBadge status={sync.last_run_status} size="sm" />
                        {sync.is_paused && <StatusBadge status="paused" size="sm" />}
                      </div>
                      <ChevronRight className="w-5 h-5 text-surface-500" />
                    </div>
                  </Link>

                  <div className="flex items-center gap-2 ml-4 pl-4 border-l border-surface-800">
                    <Button
                      variant="secondary"
                      size="sm"
                      icon={<Play className="w-4 h-4" />}
                      loading={triggerMutation.isPending}
                      onClick={(e) => {
                        e.preventDefault();
                        triggerMutation.mutate(sync.id);
                      }}
                      disabled={sync.is_paused}
                    >
                      Run
                    </Button>
                    {sync.is_paused ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        icon={<Play className="w-4 h-4" />}
                        onClick={(e) => {
                          e.preventDefault();
                          resumeMutation.mutate(sync.id);
                        }}
                      >
                        Resume
                      </Button>
                    ) : (
                      <Button
                        variant="ghost"
                        size="sm"
                        icon={<Pause className="w-4 h-4" />}
                        onClick={(e) => {
                          e.preventDefault();
                          pauseMutation.mutate(sync.id);
                        }}
                      >
                        Pause
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="sm"
                      icon={<Trash2 className="w-4 h-4" />}
                      onClick={(e) => {
                        e.preventDefault();
                        if (confirm('Delete this sync job?')) {
                          deleteMutation.mutate(sync.id);
                        }
                      }}
                    >
                      Delete
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <EmptyState
            icon={<RefreshCw className="w-8 h-8" />}
            title="No sync jobs configured"
            description="Create your first sync to start moving data from your warehouse to destinations."
            action={
              <Button icon={<Plus className="w-4 h-4" />} onClick={() => setIsModalOpen(true)}>
                Create Sync
              </Button>
            }
          />
        </Card>
      )}

      {/* Create Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false);
          resetForm();
        }}
        title={`Create Sync - Step ${step} of 3`}
        size="xl"
      >
        {step === 1 && (
          <div className="space-y-4">
            <Input
              label="Sync Name"
              placeholder="Customer to Braze Sync"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              required
            />

            <div className="grid grid-cols-2 gap-4">
              <Select
                label="Source"
                options={sources?.map(s => ({ value: String(s.id), label: s.name })) || []}
                value={formData.source_connection_id ? String(formData.source_connection_id) : ''}
                onChange={(e) => handleSourceChange(Number(e.target.value) || 0)}
                placeholder="Select source..."
              />
              <Select
                label="Destination"
                options={destinations?.map(d => ({ value: String(d.id), label: d.name })) || []}
                value={formData.destination_connection_id ? String(formData.destination_connection_id) : ''}
                onChange={(e) => setFormData((prev) => ({ ...prev, destination_connection_id: Number(e.target.value) || 0 }))}
                placeholder="Select destination..."
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <Select
                label="Schema"
                options={schemas.map(s => ({ value: s, label: s }))}
                value={formData.source_schema}
                onChange={(e) => handleSchemaChange(e.target.value)}
                placeholder="Select schema..."
                disabled={!formData.source_connection_id}
              />
              <Select
                label="Table"
                options={tables.map(t => ({ value: t.table_name, label: t.table_name }))}
                value={formData.source_table}
                onChange={(e) => handleTableChange(e.target.value)}
                placeholder="Select table..."
                disabled={!formData.source_schema}
              />
            </div>

            <div className="flex justify-end gap-3 pt-4">
              <Button variant="secondary" onClick={() => setIsModalOpen(false)}>
                Cancel
              </Button>
              <Button
                onClick={() => setStep(2)}
                disabled={
                  !formData.name.trim() ||
                  !formData.source_connection_id ||
                  !formData.destination_connection_id ||
                  !formData.source_schema ||
                  !formData.source_table
                }
              >
                Next: Field Mapping
              </Button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <p className="text-surface-400 text-sm">
              Map source fields to destination fields. The sync key field will be used to identify records.
            </p>

            <Select
              label="Sync Key"
              options={[
                { value: 'external_id', label: 'external_id (External ID)' },
                { value: 'email', label: 'email (Email Address)' },
                { value: 'phone', label: 'phone (Phone Number)' },
              ]}
              value={formData.sync_key}
              onChange={(e) => setFormData({ ...formData, sync_key: e.target.value })}
            />

            <div className="border border-surface-700 rounded-lg overflow-hidden">
              <div className="grid grid-cols-3 gap-4 px-4 py-2 bg-surface-800 text-sm font-medium text-surface-400">
                <span>Source Field</span>
                <span>Destination Field</span>
                <span>Type</span>
              </div>
              <div className="max-h-60 overflow-y-auto">
                {formData.field_mappings.map((mapping, index) => (
                  <div key={index} className="grid grid-cols-3 gap-4 px-4 py-2 border-t border-surface-800 text-sm">
                    <span className="text-surface-200 font-mono">{mapping.source_field}</span>
                    <input
                      className="bg-surface-800 px-2 py-1 rounded border border-surface-700 text-surface-200"
                      value={mapping.destination_field}
                      onChange={(e) => {
                        const newMappings = [...formData.field_mappings];
                        newMappings[index] = { ...mapping, destination_field: e.target.value };
                        setFormData({ ...formData, field_mappings: newMappings });
                      }}
                    />
                    <span className="text-surface-500 font-mono">{mapping.source_field_type}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="flex justify-between gap-3 pt-4">
              <Button variant="secondary" onClick={() => setStep(1)}>
                Back
              </Button>
              <Button onClick={() => setStep(3)}>
                Next: Schedule
              </Button>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-4">
            <Select
              label="Sync Mode"
              options={[
                { value: 'full_refresh', label: 'Full Refresh - Replace all records each run' },
                { value: 'incremental', label: 'Incremental - Only sync new/updated records' },
              ]}
              value={formData.sync_mode}
              onChange={(e) => setFormData({ ...formData, sync_mode: e.target.value as SyncMode })}
            />

            {formData.sync_mode === 'incremental' && (
              <Select
                label="Incremental Column"
                options={columns.map(c => ({ value: c.column_name, label: c.column_name }))}
                value={formData.incremental_column || ''}
                onChange={(e) => setFormData({ ...formData, incremental_column: e.target.value })}
                placeholder="Select column (e.g., updated_at)..."
              />
            )}

            <Select
              label="Schedule"
              options={[
                { value: 'manual', label: 'Manual - Run on demand' },
                { value: 'cron', label: 'Scheduled - Use cron expression' },
              ]}
              value={formData.schedule_type}
              onChange={(e) => setFormData({ ...formData, schedule_type: e.target.value as ScheduleType })}
            />

            {formData.schedule_type === 'cron' && (
              <Input
                label="Cron Expression"
                placeholder="0 */6 * * *"
                value={formData.cron_expression || ''}
                onChange={(e) => setFormData({ ...formData, cron_expression: e.target.value })}
                hint="Example: 0 */6 * * * (every 6 hours)"
              />
            )}

            <div className="flex justify-between gap-3 pt-4">
              <Button variant="secondary" onClick={() => setStep(2)}>
                Back
              </Button>
              <Button onClick={handleSubmit} loading={createMutation.isPending}>
                Create Sync
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
