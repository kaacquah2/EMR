import { useState, useCallback } from 'react';
import { useApi } from './use-api';

interface BatchImportJob {
  id: string;
  filename: string;
  status: 'pending' | 'validating' | 'processing' | 'completed' | 'failed' | 'paused';
  total_records: number;
  processed_count: number;
  success_count: number;
  validation_error_count: number;
  processing_error_count: number;
  progress_percent: number;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  validation_summary: Record<string, string[]>;
}

interface BatchImportItem {
  id: string;
  row_number: number;
  email: string;
  full_name: string;
  role: string;
  status: string;
  validation_errors: string[];
  processing_error?: string;
  processed_at?: string;
}

interface BulkInvitationJob {
  id: string;
  campaign_name: string;
  status: 'draft' | 'sending' | 'sent' | 'partial' | 'completed' | 'failed';
  total_invitations: number;
  sent_count: number;
  failed_count: number;
  accepted_count: number;
  expired_count: number;
  pending_count: number;
  progress_percent: number;
  expiry_days: number;
  created_at: string;
  sent_at?: string;
}

/** Input for creating a batch import item */
interface BatchImportInput {
  email: string;
  full_name: string;
  role: string;
  hospital_id?: string;
  ward_id?: string;
}

/** Input for creating a bulk invitation */
interface BulkInvitationInput {
  email: string;
  role: string;
  hospital_id?: string;
  message?: string;
}

/** Expiring invitation info */
interface ExpiringInvitation {
  id: string;
  email: string;
  expires_at: string;
  campaign_name: string;
}

export function useBatchOperations() {
  const api = useApi();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const createBatchImport = useCallback(
    async (filename: string, items: BatchImportInput[]) => {
      try {
        setLoading(true);
        setError('');

        const response = await api.post<{
          job_id: string;
          filename: string;
          total_records: number;
          valid_records: number;
          validation_errors: number;
          status: string;
          validation_summary: Record<string, string[]>;
        }>('/batch-import', {
          filename,
          items,
        });

        return response;
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to create batch import';
        setError(message);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [api]
  );

  const getBatchImportJob = useCallback(
    async (jobId: string) => {
      try {
        setLoading(true);
        setError('');

        const response = await api.get<BatchImportJob>(`/batch-import/${jobId}`);
        return response;
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to fetch import job';
        setError(message);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [api]
  );

  const getBatchImportItems = useCallback(
    async (jobId: string, status?: string, page = 1, perPage = 50) => {
      try {
        setLoading(true);
        setError('');

        const response = await api.post<{
          items: BatchImportItem[];
          total: number;
          page: number;
          per_page: number;
          pages: number;
        }>(`/batch-import/${jobId}/items`, {
          status,
          page,
          per_page: perPage,
        });

        return response;
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to fetch import items';
        setError(message);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [api]
  );

  const exportBatchImportResults = useCallback(
    async (jobId: string) => {
      try {
        setLoading(true);
        setError('');

        const response = await api.get<{ csv: string; filename: string }>(
          `/batch-import/${jobId}/export`
        );

        if (response) {
          // Trigger download
          const blob = new Blob([response.csv], { type: 'text/csv' });
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = response.filename;
          document.body.appendChild(a);
          a.click();
          window.URL.revokeObjectURL(url);
          document.body.removeChild(a);
        }

        return response;
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to export results';
        setError(message);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [api]
  );

  const createBulkInvitationCampaign = useCallback(
    async (campaignName: string, invitations: BulkInvitationInput[], expiryDays = 7) => {
      try {
        setLoading(true);
        setError('');

        const response = await api.post<{
          campaign_id: string;
          campaign_name: string;
          total_invitations: number;
          status: string;
        }>('/bulk-invitations', {
          campaign_name: campaignName,
          invitations,
          expiry_days: expiryDays,
        });

        return response;
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to create invitation campaign';
        setError(message);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [api]
  );

  const getBulkInvitationCampaign = useCallback(
    async (campaignId: string) => {
      try {
        setLoading(true);
        setError('');

        const response = await api.get<BulkInvitationJob>(
          `/bulk-invitations/${campaignId}`
        );

        return response;
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to fetch campaign details';
        setError(message);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [api]
  );

  const checkExpiringInvitations = useCallback(
    async () => {
      try {
        setLoading(true);
        setError('');

        const response = await api.get<{
          expiring_soon: ExpiringInvitation[];
          expired_count: number;
        }>('/bulk-invitations/expiration-check');

        return response;
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to check expiring invitations';
        setError(message);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [api]
  );

  const getBatchOperationsSummary = useCallback(
    async () => {
      try {
        setLoading(true);
        setError('');

        const response = await api.get<{
          import_jobs: {
            total: number;
            active: number;
            completed: number;
            failed: number;
            total_users_imported: number;
            success_rate: number;
            recent_jobs: Array<{
              id: string;
              filename: string;
              status: string;
              progress: number;
              total_records: number;
              success_count: number;
              created_at: string;
              hospital: string;
            }>;
          };
          invitation_campaigns: {
            total: number;
            active: number;
            completed: number;
            total_sent: number;
            total_accepted: number;
            acceptance_rate: number;
            expiring_soon: number;
            recent_campaigns: Array<{
              id: string;
              campaign_name: string;
              status: string;
              progress: number;
              total_invitations: number;
              sent_count: number;
              accepted_count: number;
              created_at: string;
              hospital: string;
            }>;
          };
          timestamp: string;
        }>('/batch-operations/summary');

        return response;
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to fetch batch operations summary';
        setError(message);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [api]
  );

  return {
    loading,
    error,
    createBatchImport,
    getBatchImportJob,
    getBatchImportItems,
    exportBatchImportResults,
    createBulkInvitationCampaign,
    getBulkInvitationCampaign,
    checkExpiringInvitations,
    getBatchOperationsSummary,
  };
}
