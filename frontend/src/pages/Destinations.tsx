import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Send, Plus, Trash2, TestTube, Check, X, Flame, MessageSquare } from 'lucide-react';
import toast from 'react-hot-toast';
import { Card, CardContent } from '@/components/Card';
import Button from '@/components/Button';
import Input from '@/components/Input';
import Select from '@/components/Select';
import Modal from '@/components/Modal';
import EmptyState from '@/components/EmptyState';
import { PageLoader } from '@/components/LoadingSpinner';
import { getDestinations, createDestination, deleteDestination, testDestination } from '@/lib/api';
import { formatRelativeTime } from '@/lib/utils';
import type { DestinationConnectionCreate, DestinationType } from '@/types';

const destinationTypeOptions = [
  { value: 'braze', label: 'Braze' },
  { value: 'attentive', label: 'Attentive' },
];

const brazeEndpoints = [
  { value: 'https://rest.iad-01.braze.com', label: 'US-01' },
  { value: 'https://rest.iad-02.braze.com', label: 'US-02' },
  { value: 'https://rest.iad-03.braze.com', label: 'US-03' },
  { value: 'https://rest.fra-01.braze.eu', label: 'EU-01' },
];

export default function Destinations() {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [formData, setFormData] = useState<DestinationConnectionCreate>({
    name: '',
    destination_type: 'braze',
    api_key: '',
    api_endpoint: 'https://rest.iad-01.braze.com',
    braze_app_id: '',
    batch_size: 75,
  });

  const queryClient = useQueryClient();
  const { data: destinations, isLoading } = useQuery({ queryKey: ['destinations'], queryFn: getDestinations });

  const createMutation = useMutation({
    mutationFn: createDestination,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['destinations'] });
      setIsModalOpen(false);
      resetForm();
      toast.success('Destination connection created');
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteDestination,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['destinations'] });
      toast.success('Destination connection deleted');
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const testMutation = useMutation({
    mutationFn: testDestination,
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['destinations'] });
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
      destination_type: 'braze',
      api_key: '',
      api_endpoint: 'https://rest.iad-01.braze.com',
      braze_app_id: '',
      batch_size: 75,
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
          <h1 className="text-3xl font-bold text-surface-50 mb-2">Destinations</h1>
          <p className="text-surface-400">Connect marketing platforms</p>
        </div>
        <Button icon={<Plus className="w-4 h-4" />} onClick={() => setIsModalOpen(true)}>
          Add Destination
        </Button>
      </div>

      {destinations && destinations.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {destinations.map((dest) => (
            <Card key={dest.id} className="card-hover">
              <CardContent>
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-4">
                    <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                      dest.destination_type === 'braze' ? 'bg-orange-500/10' : 'bg-purple-500/10'
                    }`}>
                      {dest.destination_type === 'braze' ? (
                        <Flame className="w-6 h-6 text-orange-400" />
                      ) : (
                        <MessageSquare className="w-6 h-6 text-purple-400" />
                      )}
                    </div>
                    <div>
                      <h3 className="font-semibold text-surface-100">{dest.name}</h3>
                      <p className="text-sm text-surface-500 capitalize">{dest.destination_type}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {dest.last_test_success !== null && (
                      dest.last_test_success ? (
                        <Check className="w-5 h-5 text-green-400" />
                      ) : (
                        <X className="w-5 h-5 text-red-400" />
                      )
                    )}
                  </div>
                </div>

                <div className="mt-4 pt-4 border-t border-surface-800 space-y-2">
                  <p className="text-sm text-surface-500">
                    API Key: <span className="text-surface-300 font-mono">{dest.api_key_masked || '****'}</span>
                  </p>
                  <p className="text-sm text-surface-500">
                    Batch Size: <span className="text-surface-300">{dest.batch_size}</span>
                  </p>
                  {dest.last_tested_at && (
                    <p className="text-sm text-surface-500">
                      Last tested: <span className="text-surface-300">{formatRelativeTime(dest.last_tested_at)}</span>
                    </p>
                  )}
                </div>

                <div className="mt-4 flex gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    icon={<TestTube className="w-4 h-4" />}
                    loading={testMutation.isPending}
                    onClick={() => testMutation.mutate(dest.id)}
                  >
                    Test
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={<Trash2 className="w-4 h-4" />}
                    onClick={() => {
                      if (confirm('Delete this destination connection?')) {
                        deleteMutation.mutate(dest.id);
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
            icon={<Send className="w-8 h-8" />}
            title="No destinations configured"
            description="Add the first destination to start syncing data to marketing platforms."
            action={
              <Button icon={<Plus className="w-4 h-4" />} onClick={() => setIsModalOpen(true)}>
                Add Destination
              </Button>
            }
          />
        </Card>
      )}

      {/* Create Modal */}
      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title="Add Destination Connection" size="lg">
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Connection Name"
            placeholder="Production Braze"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            required
          />

          <Select
            label="Destination Type"
            options={destinationTypeOptions}
            value={formData.destination_type}
            onChange={(e) => setFormData({ ...formData, destination_type: e.target.value as DestinationType })}
          />

          <Input
            label="API Key"
            type="password"
            placeholder="Your API key"
            value={formData.api_key}
            onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
            required
          />

          {formData.destination_type === 'braze' && (
            <>
              <Select
                label="API Endpoint"
                options={brazeEndpoints}
                value={formData.api_endpoint || ''}
                onChange={(e) => setFormData({ ...formData, api_endpoint: e.target.value })}
              />
              <Input
                label="App ID (Optional)"
                placeholder="Braze App ID"
                value={formData.braze_app_id || ''}
                onChange={(e) => setFormData({ ...formData, braze_app_id: e.target.value })}
              />
            </>
          )}

          {formData.destination_type === 'attentive' && (
            <Input
              label="API URL (Optional)"
              placeholder="https://api.attentivemobile.com"
              value={formData.attentive_api_url || ''}
              onChange={(e) => setFormData({ ...formData, attentive_api_url: e.target.value })}
            />
          )}

          <Input
            label="Batch Size"
            type="number"
            placeholder="75"
            value={formData.batch_size || ''}
            onChange={(e) => setFormData({ ...formData, batch_size: parseInt(e.target.value) })}
            hint="Records per API request (max 75 for Braze, 100 for Attentive)"
          />

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
