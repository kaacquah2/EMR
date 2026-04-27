'use client';

import { useEffect, useState, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { useBatchOperations } from '@/hooks/use-batch-operations';
import {
  Upload,
  AlertCircle,
  CheckCircle,
  XCircle,
  Download,
  RefreshCw,
  FileText,
} from 'lucide-react';

interface ImportUser {
  email: string;
  full_name: string;
  phone?: string;
  role: 'doctor' | 'nurse' | 'lab_technician' | 'receptionist' | 'hospital_admin' | 'super_admin';
  ward_id?: string;
}

interface ImportJobResult {
  job_id: string;
  filename: string;
  status: string;
  total_records: number;
  valid_records?: number;
  validation_errors?: number;
  processed_count: number;
  success_count: number;
  validation_error_count: number;
  processing_error_count: number;
  progress_percent: number;
  validation_summary?: Record<string, string[]>;
}

interface ImportItem {
  id: string;
  row_number: number;
  email: string;
  full_name: string;
  role?: string;
  status: string;
  validation_errors: string[];
  processing_error?: string;
}

interface PaginationInfo {
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
  pages?: number;
}

export function UserImportForm() {
  const { createBatchImport, loading, error } = useBatchOperations();
  const [csvContent, setCsvContent] = useState('');
  const [parseError, setParseError] = useState('');
  const [users, setUsers] = useState<ImportUser[]>([]);
  const [preview, setPreview] = useState<ImportUser[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<ImportJobResult | null>(null);

  const parseCSV = useCallback((content: string) => {
    try {
      setParseError('');
      const lines = content.trim().split('\n');

      if (lines.length < 2) {
        setParseError('CSV must have header row + at least 1 data row');
        return;
      }

      const headers = lines[0].split(',').map((h) => h.trim().toLowerCase());
      const emailIdx = headers.indexOf('email');
      const nameIdx = headers.indexOf('full_name');
      const phoneIdx = headers.indexOf('phone');
      const roleIdx = headers.indexOf('role');
      const wardIdx = headers.indexOf('ward_id');

      if (emailIdx === -1 || nameIdx === -1 || roleIdx === -1) {
        setParseError('CSV must have columns: email, full_name, role');
        return;
      }

      const parsedUsers: ImportUser[] = [];
      for (let i = 1; i < lines.length; i++) {
        const cols = lines[i].split(',').map((c) => c.trim());
        if (!cols[emailIdx]) continue;

        parsedUsers.push({
          email: cols[emailIdx],
          full_name: cols[nameIdx],
          phone: cols[phoneIdx] || undefined,
          role: cols[roleIdx] as ImportUser['role'],
          ward_id: cols[wardIdx] || undefined,
        });
      }

      if (parsedUsers.length === 0) {
        setParseError('No valid rows found');
        return;
      }

      setUsers(parsedUsers);
      setPreview(parsedUsers.slice(0, 5));
    } catch (e) {
      setParseError('Failed to parse CSV: ' + (e instanceof Error ? e.message : 'Unknown error'));
    }
  }, []);

  const handleFileUpload = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;

      // Audit: Add size limit check
      const MAX_SIZE = 5 * 1024 * 1024; // 5MB
      if (file.size > MAX_SIZE) {
        setParseError('File size exceeds 5MB limit.');
        return;
      }

      const reader = new FileReader();
      reader.onload = (event) => {
        const content = event.target?.result as string;
        setCsvContent(content);
        parseCSV(content);
      };
      reader.readAsText(file);
    },
    [parseCSV]
  );

  const handleSubmit = useCallback(async () => {
    if (users.length === 0) {
      setParseError('No users to import');
      return;
    }

    try {
      setSubmitting(true);
      const result = await createBatchImport('users.csv', users);

      if (result) {
        // Convert API response to ImportJobResult format
        const importJobResult: ImportJobResult = {
          job_id: result.job_id,
          filename: result.filename,
          status: result.status,
          total_records: result.total_records,
          valid_records: result.valid_records,
          validation_errors: result.validation_errors,
          processed_count: 0,
          success_count: 0,
          validation_error_count: result.validation_errors,
          processing_error_count: 0,
          progress_percent: 0,
          validation_summary: result.validation_summary,
        };
        setJobId(result.job_id);
        setImportResult(importJobResult);
        setCsvContent('');
        setUsers([]);
        setPreview([]);
      }
    } catch (err) {
      console.error('Import failed:', err);
    } finally {
      setSubmitting(false);
    }
  }, [users, createBatchImport]);

  if (jobId && importResult) {
    return <ImportProgressDisplay jobId={jobId} initialResult={importResult} />;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Upload className="h-5 w-5" />
          User Import
        </CardTitle>
      </CardHeader>

      <CardContent className="space-y-6">
        {(error || parseError) && (
          <div className="flex gap-2 rounded-lg border border-red-200 bg-red-50 p-4 text-red-800">
            <AlertCircle className="h-5 w-5 flex-shrink-0 mt-0.5" />
            <p>{error || parseError}</p>
          </div>
        )}

        {/* CSV Upload */}
        <div className="space-y-2">
          <label className="block text-sm font-medium">CSV File (Max 5MB)</label>
          <input
            type="file"
            accept=".csv"
            onChange={handleFileUpload}
            className="block w-full text-sm border border-gray-300 rounded-lg p-2 cursor-pointer focus:outline-none focus:ring-2 focus:ring-[var(--teal-500)]"
            disabled={loading}
          />
          <p className="text-xs text-gray-600">
            Required columns: email, full_name, role. Optional: phone, ward_id
          </p>
        </div>

        {/* Raw CSV Editor */}
        {!users.length && (
          <Textarea
            label="Or paste CSV content"
            value={csvContent}
            onChange={(e) => {
              setCsvContent(e.target.value);
              parseCSV(e.target.value);
            }}
            placeholder="email,full_name,phone,role,ward_id&#10;doctor@hospital.org,John Doe,+233234567890,doctor"
            className="font-mono"
            disabled={loading}
            rows={6}
          />
        )}

        {/* Preview */}
        {preview.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">Preview ({users.length} users)</h3>
              {users.length > preview.length && (
                <p className="text-xs text-gray-600">showing first 5 of {users.length}</p>
              )}
            </div>
            <div className="overflow-x-auto rounded-lg border border-gray-200">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b">
                  <tr className="text-left">
                    <th className="px-4 py-2 font-semibold">Email</th>
                    <th className="px-4 py-2 font-semibold">Name</th>
                    <th className="px-4 py-2 font-semibold">Role</th>
                    <th className="px-4 py-2 font-semibold">Ward</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.map((user, idx) => (
                    <tr key={idx} className="border-b hover:bg-gray-50">
                      <td className="px-4 py-2 text-blue-600">{user.email}</td>
                      <td className="px-4 py-2">{user.full_name}</td>
                      <td className="px-4 py-2">
                        <span className="inline-block px-2 py-1 text-xs rounded bg-blue-100 text-blue-700 font-medium">
                          {user.role}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-gray-600">{user.ward_id || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex gap-2 pt-4">
          <Button
            onClick={handleSubmit}
            loading={submitting || loading}
            disabled={users.length === 0}
            fullWidth
          >
            Import {users.length} Users
          </Button>
          <Button
            variant="outline"
            onClick={() => {
              setCsvContent('');
              setUsers([]);
              setPreview([]);
              setParseError('');
            }}
            disabled={submitting || loading}
          >
            Clear
          </Button>
        </div>

        {/* Instructions */}
        <div className="rounded-lg bg-blue-50 p-4 text-sm text-blue-800">
          <p className="font-semibold mb-2">📋 CSV Format Guide</p>
          <p className="mb-3">Example CSV header and row:</p>
          <code className="block bg-white p-2 rounded border border-blue-200 mb-3 text-xs whitespace-nowrap overflow-x-auto">
            email,full_name,phone,role,ward_id
          </code>
          <code className="block bg-white p-2 rounded border border-blue-200 text-xs whitespace-nowrap overflow-x-auto">
            john.doe@hospital.org,John Doe,+233234567890,doctor
          </code>
          <p className="mt-3">
            Valid roles: doctor, nurse, lab_technician, receptionist, hospital_admin, super_admin
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

function ImportProgressDisplay({
  jobId,
  initialResult,
}: {
  jobId: string;
  initialResult: ImportJobResult;
}) {
  const { getBatchImportJob, getBatchImportItems, exportBatchImportResults, error } =
    useBatchOperations();
  // Use ImportJobResult for state, convert from BatchImportJob when updating
  const [job, setJob] = useState<ImportJobResult>(initialResult);
  const [items, setItems] = useState<ImportItem[]>([]);
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);
  const [page, setPage] = useState(1);
  const [pagination, setPagination] = useState<PaginationInfo | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  // Auto-refresh job status
  useEffect(() => {
    if (!autoRefresh || job.status === 'completed' || job.status === 'failed') {
      return;
    }

    const interval = setInterval(async () => {
      try {
        const updated = await getBatchImportJob(jobId);
        if (updated) {
          // Convert BatchImportJob to ImportJobResult format
          setJob({
            job_id: updated.id,
            filename: updated.filename,
            status: updated.status,
            total_records: updated.total_records,
            processed_count: updated.processed_count,
            success_count: updated.success_count,
            validation_error_count: updated.validation_error_count,
            processing_error_count: updated.processing_error_count,
            progress_percent: updated.progress_percent,
            validation_summary: updated.validation_summary,
          });
        }
      } catch (err) {
        console.error('Failed to refresh job status:', err);
      }
    }, 5000); // Refresh every 5 seconds

    return () => clearInterval(interval);
  }, [jobId, getBatchImportJob, autoRefresh, job.status]);

  // Fetch items
  useEffect(() => {
    const fetchItems = async () => {
      try {
        const result = await getBatchImportItems(jobId, statusFilter, page);
        if (result) {
          // Convert BatchImportItem[] to ImportItem[]
          const convertedItems: ImportItem[] = result.items.map((item) => ({
            id: item.id,
            row_number: item.row_number,
            email: item.email,
            full_name: item.full_name,
            role: item.role,
            status: item.status,
            validation_errors: item.validation_errors,
            processing_error: item.processing_error,
          }));
          setItems(convertedItems);
          setPagination({
            total: result.total,
            page: result.page,
            per_page: result.per_page,
            total_pages: result.pages,
            pages: result.pages,
          });
        }
      } catch (err) {
        console.error('Failed to fetch items:', err);
      }
    };

    fetchItems();
  }, [jobId, statusFilter, page, getBatchImportItems]);

  const handleExport = useCallback(async () => {
    try {
      await exportBatchImportResults(jobId);
    } catch (err) {
      console.error('Export failed:', err);
    }
  }, [jobId, exportBatchImportResults]);

  const statusColor = {
    validating: 'bg-blue-100 text-blue-800',
    processing: 'bg-amber-100 text-amber-800',
    completed: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
    paused: 'bg-gray-100 text-gray-800',
  } as Record<string, string>;

  const itemStatusIcon = {
    validated: <CheckCircle className="h-4 w-4 text-green-600" />,
    created: <CheckCircle className="h-4 w-4 text-green-600" />,
    validation_error: <XCircle className="h-4 w-4 text-red-600" />,
    processing_error: <XCircle className="h-4 w-4 text-red-600" />,
  } as Record<string, React.ReactNode>;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Import Progress</h2>
          <p className="text-gray-600">{initialResult.filename}</p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => setAutoRefresh(!autoRefresh)}
            className="gap-2"
          >
            <RefreshCw className={`h-4 w-4 ${autoRefresh ? 'animate-spin' : ''}`} />
            {autoRefresh ? 'Auto-Refresh On' : 'Auto-Refresh Off'}
          </Button>
          <Button onClick={handleExport} variant="outline" className="gap-2">
            <Download className="h-4 w-4" />
            Export
          </Button>
        </div>
      </div>

      {error && (
        <div className="flex gap-2 rounded-lg border border-red-200 bg-red-50 p-4 text-red-800">
          <AlertCircle className="h-5 w-5 flex-shrink-0 mt-0.5" />
          <p>{error}</p>
        </div>
      )}

      {/* Status Card */}
      <Card>
        <CardContent className="pt-6">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div>
              <p className="text-sm text-gray-600">Status</p>
              <p className={`text-lg font-bold rounded px-3 py-1 inline-block ${statusColor[job.status] || 'bg-gray-100'}`}>
                {job.status.toUpperCase()}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Total Records</p>
              <p className="text-2xl font-bold">{job.total_records}</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Processed</p>
              <p className="text-2xl font-bold text-blue-600">{job.processed_count}</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Success</p>
              <p className="text-2xl font-bold text-green-600">{job.success_count}</p>
            </div>
          </div>

          {/* Progress Bar */}
          <div className="mt-6">
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-medium">Progress</p>
              <p className="text-sm font-semibold">{job.progress_percent}%</p>
            </div>
            <div className="h-3 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-blue-500 to-blue-600 transition-all duration-300"
                style={{ width: `${job.progress_percent}%` }}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-gray-600">Valid</p>
            <p className="text-2xl font-bold text-green-600">{job.total_records - job.validation_error_count}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-gray-600">Validation Errors</p>
            <p className="text-2xl font-bold text-red-600">{job.validation_error_count}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-gray-600">Processing Errors</p>
            <p className="text-2xl font-bold text-orange-600">{job.processing_error_count}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-gray-600">Success Rate</p>
            <p className="text-2xl font-bold text-blue-600">
              {job.total_records > 0
                ? Math.round((job.success_count / job.total_records) * 100)
                : 0}
              %
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Items Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Import Items
          </CardTitle>
        </CardHeader>
        <CardContent>
          {/* Status Filter */}
          <div className="mb-4 flex gap-2">
            {['all', 'validated', 'created', 'validation_error', 'processing_error'].map((status) => (
              <button
                key={status}
                onClick={() => {
                  setStatusFilter(status === 'all' ? undefined : status);
                  setPage(1);
                }}
                className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                  (status === 'all' && !statusFilter) || statusFilter === status
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                {status.replace('_', ' ')}
              </button>
            ))}
          </div>

          {/* Table */}
          <div className="overflow-x-auto rounded-lg border border-gray-200">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr className="text-left">
                  <th className="px-4 py-2 font-semibold">Row</th>
                  <th className="px-4 py-2 font-semibold">Email</th>
                  <th className="px-4 py-2 font-semibold">Name</th>
                  <th className="px-4 py-2 font-semibold">Role</th>
                  <th className="px-4 py-2 font-semibold">Status</th>
                  <th className="px-4 py-2 font-semibold">Errors</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id} className="border-b hover:bg-gray-50">
                    <td className="px-4 py-2 text-gray-600">{item.row_number}</td>
                    <td className="px-4 py-2 text-blue-600">{item.email}</td>
                    <td className="px-4 py-2">{item.full_name}</td>
                    <td className="px-4 py-2">
                      <span className="inline-block px-2 py-1 text-xs rounded bg-blue-100 text-blue-700 font-medium">
                        {item.role}
                      </span>
                    </td>
                    <td className="px-4 py-2">
                      <div className="flex items-center gap-2">
                        {itemStatusIcon[item.status]}
                        <span className="capitalize">{item.status}</span>
                      </div>
                    </td>
                    <td className="px-4 py-2 text-red-600 text-xs">
                      {item.validation_errors?.length > 0 && (
                        <div className="space-y-0.5">
                          {item.validation_errors.map((err: string, idx: number) => (
                            <div key={idx}>• {err}</div>
                          ))}
                        </div>
                      )}
                      {item.processing_error && <div>• {item.processing_error}</div>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {pagination && (pagination.pages ?? 0) > 1 && (
            <div className="mt-4 flex items-center justify-between">
              <p className="text-sm text-gray-600">
                Page {pagination.page} of {pagination.pages ?? pagination.total_pages} ({pagination.total} total)
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage(Math.max(1, page - 1))}
                  disabled={page === 1}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage(Math.min(pagination.pages ?? pagination.total_pages, page + 1))}
                  disabled={page === (pagination.pages ?? pagination.total_pages)}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

