import { useState, useCallback } from 'react';
import { useApi } from './use-api';
import { useToast } from '@/lib/toast-context';

export interface ModelVersion {
  id: string;
  model_type: string;
  version_tag: string;
  trained_at: string;
  trained_by_name: string;
  training_data_source: 'synthetic' | 'anonymized_local' | 'anonymized_federated';
  training_sample_count: number;
  evaluation_metrics: Record<string, number>;
  comparison_vs_previous: Record<string, number> | null;
  is_production: boolean;
  clinical_use_approved: boolean;
  approved_by_name: string | null;
  approved_at: string | null;
  approval_notes: string | null;
}

export const useModelManagement = () => {
  const api = useApi();
  const toast = useToast();
  const [models, setModels] = useState<ModelVersion[]>([]);
  const [loading, setLoading] = useState(false);
  const [retrainingTask, setRetrainingTask] = useState<string | null>(null);

  const fetchModels = useCallback(async () => {
    setLoading(true);
    try {
      const response = await api.get<ModelVersion[]>('/superadmin/ai-models');
      setModels(response);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to fetch AI models';
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }, [api, toast]);

  const approveModel = async (id: string, notes: string) => {
    try {
      await api.post(`/superadmin/ai-models/${id}/approve`, { notes });
      toast.success('The model has been promoted to production.');
      fetchModels();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Could not approve model';
      toast.error(message);
    }
  };

  const startRetraining = async (modelType: string, dataSource: string) => {
    try {
      const response = await api.post<{ task_id: string }>('/superadmin/ai-models/retrain', {
        model_type: modelType,
        data_source: dataSource,
      });
      setRetrainingTask(response.task_id);
      toast.success('The model is being retrained in the background.');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Could not start retraining';
      toast.error(message);
    }
  };

  const checkRetrainStatus = async (taskId: string) => {
    try {
      const response = await api.get<{
        status: 'PENDING' | 'SUCCESS' | 'FAILURE';
        result: { version_tag?: string; message?: string };
      }>(`/superadmin/ai-models/retrain/${taskId}/status`);
      
      if (response.status === 'SUCCESS' && response.result.version_tag) {
        setRetrainingTask(null);
        fetchModels();
        toast.success(`Retraining complete. New version: ${response.result.version_tag}`);
      } else if (response.status === 'FAILURE') {
        setRetrainingTask(null);
        toast.error(response.result?.message || 'The retraining task failed.');
      }
      return response;
    } catch {
      return null;
    }
  };

  return {
    models,
    loading,
    retrainingTask,
    fetchModels,
    approveModel,
    startRetraining,
    checkRetrainStatus,
  };
};
