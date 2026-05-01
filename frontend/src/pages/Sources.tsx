import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Database, Plus, Trash2, TestTube, Check, X, Server } from 'lucide-react';
import toast from 'react-hot-toast';
import { Card, CardContent } from '@/components/Card';
import Button from '@/components/Button';
import Input from '@/components/Input';
import Select from '@/components/Select';
import Modal from '@/components/Modal';
import StatusBadge from '@/components/StatusBadge';
import EmptyState from '@/components/EmptyState';
import { PageLoader } from '@/components/LoadingSpinner';
import { getSources, createSource, deleteSource, testSource } from '@/lib/api';
import { formatRelativeTime } from '@/lib/utils';
import type { SourceConnectionCreate, SourceType } from '@/types';

const sourceTypeOptions = [
  { value: 'duckdb', label: 'DuckDB (Local)' },
  { value: 'redshift', label: 'Amazon Redshift' },
];

export default function Sources() {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [formData, setFormData] = useState<SourceConnectionCreate>({
    name: '',
    source_type: 'duckdb',
    host: '',
    port: 5439,
    database: '',
    username: '',
    password: '',
    duckdb_path: ':memory:',
  });

  const queryClient = useQueryClient();
  const { data: sources, isLoading } = useQuery({ queryKey: ['sources'], queryFn: getSources });

  const createMutation = useMutation({
    mutationFn: createSource,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sources'] });
      setIsModalOpen(false);
      resetForm();
      toast.success('Source connection created');
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteSource,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sources'] });
      toast.success('Source connection deleted');
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const testMutation = useMutation({
    mutationFn: testSource,
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['sources'] });
      if (result.success) {
        toast.success(result.message);
      } else {
        toast.error(result.message);
      }
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const resetForm = () => {
    setFormData({
      name: '',
      source_type: 'duckdb',
      host: '',
      port: 5439,
      database: '',
      username: '',
      password: '',
      duckdb_path: ':memory:',
    });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    createMutation.mutate(formData);
  };

  if (isLoading) return <PageLoader />;

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-surface-50 mb-2">Sources</h1>
          <p className="text-surface-400">Connect to your data warehouses</p>
        </div>
        <Button icon={<Plus className="w-4 h-4" />} onClick={() => setIsModalOpen(true)}>
          Add Source
        </Button>
      </div>

      {sources && sources.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {sources.map((source) => (
            <Card key={source.id} className="card-hover">
              <CardContent>
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-xl bg-blue-500/10 flex items-center justify-center">
                      {source.source_type === 'duckdb' ? (
                        <Database className="w-6 h-6 text-blue-400" />
                      ) : (
                        <Server className="w-6 h-6 text-orange-400" />
                      )}
                    </div>
                    <div>
                      <h3 className="font-semibold text-surface-100">{source.name}</h3>
                      <p className="text-sm text-surface-500 capitalize">{source.source_type}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {source.last_test_success !== null && (
                      source.last_test_success ? (
                        <Check className="w-5 h-5 text-green-400" />
                      ) : (
                        <X className="w-5 h-5 text-red-400" />
                      )
                    )}
                  </div>
                </div>

                <div className="mt-4 pt-4 border-t border-surface-800 space-y-2">
                  {source.source_type === 'duckdb' ? (
                    <p className="text-sm text-surface-500">
                      Path: <span className="text-surface-300">{source.duckdb_path || ':memory:'}</span>
                    </p>
                  ) : (
                    <p className="text-sm text-surface-500">
                      Host: <span className="text-surface-300">{source.host}:{source.port}</span>
                    </p>
                  )}
                  {source.last_tested_at && (
                    <p className="text-sm text-surface-500">
                      Last tested: <span className="text-surface-300">{formatRelativeTime(source.last_tested_at)}</span>
                    </p>
                  )}
                </div>

                <div className="mt-4 flex gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    icon={<TestTube className="w-4 h-4" />}
                    loading={testMutation.isPending}
                    onClick={() => testMutation.mutate(source.id)}
                  >
                    Test
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={<Trash2 className="w-4 h-4" />}
                    onClick={() => {
                      if (confirm('Delete this source connection?')) {
                        deleteMutation.mutate(source.id);
                      }
                    }}
                  >
                    Delete
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <EmptyState
            icon={<Database className="w-8 h-8" />}
            title="No sources configured"
            description="Add your first data warehouse connection to start syncing data."
            action={
              <Button icon={<Plus className="w-4 h-4" />} onClick={() => setIsModalOpen(true)}>
                Add Source
              </Button>
            }
          />
        </Card>
      )}

      {/* Create Modal */}
      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title="Add Source Connection" size="lg">
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Connection Name"
            placeholder="My Redshift Warehouse"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            required
          />

          <Select
            label="Source Type"
            options={sourceTypeOptions}
            value={formData.source_type}
            onChange={(e) => setFormData({ ...formData, source_type: e.target.value as SourceType })}
          />

          {formData.source_type === 'duckdb' ? (
            <Input
              label="Database Path"
              placeholder=":memory: or /path/to/database.db"
              value={formData.duckdb_path || ''}
              onChange={(e) => setFormData({ ...formData, duckdb_path: e.target.value })}
              hint="Use :memory: for in-memory database"
            />
          ) : (
            <>
              <div className="grid grid-cols-2 gap-4">
                <Input
                  label="Host"
                  placeholder="cluster.region.redshift.amazonaws.com"
                  value={formData.host || ''}
                  onChange={(e) => setFormData({ ...formData, host: e.target.value })}
                  required
                />
                <Input
                  label="Port"
                  type="number"
                  placeholder="5439"
                  value={formData.port || ''}
                  onChange={(e) => setFormData({ ...formData, port: parseInt(e.target.value) })}
                />
              </div>
              <Input
                label="Database"
                placeholder="my_database"
                value={formData.database || ''}
                onChange={(e) => setFormData({ ...formData, database: e.target.value })}
                required
              />
              <div className="grid grid-cols-2 gap-4">
                <Input
                  label="Username"
                  placeholder="admin"
                  value={formData.username || ''}
                  onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                  required
                />
                <Input
                  label="Password"
                  type="password"
                  placeholder="••••••••"
                  value={formData.password || ''}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  required
                />
              </div>
            </>
          )}

          <div className="flex justify-end gap-3 pt-4">
            <Button type="button" variant="secondary" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={createMutation.isPending}>
              Create Connection
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
