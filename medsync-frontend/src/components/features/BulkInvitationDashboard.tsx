'use client';

import { useEffect, useState, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useBatchOperations } from '@/hooks/use-batch-operations';
import { Mail, CheckCircle, XCircle, Clock, AlertCircle, Plus } from 'lucide-react';

interface InvitationData {
  email: string;
  full_name: string;
  role: 'doctor' | 'nurse' | 'lab_technician' | 'receptionist' | 'hospital_admin' | 'super_admin';
}

interface CampaignInfo {
  id: string;
  campaign_id?: string;
  campaign_name: string;
  status: string;
  total_invitations: number;
  sent_count: number;
  failed_count: number;
  accepted_count: number;
  pending_count: number;
  progress_percent: number;
  expiry_days: number;
  created_at: string;
  sent_at?: string;
}

interface ExpiringInvitationInfo {
  id: string;
  email: string;
  expires_at: string;
  campaign_name: string;
  hours_remaining?: number;
}

export function BulkInvitationDashboard() {
  const { createBulkInvitationCampaign, checkExpiringInvitations, loading, error } =
    useBatchOperations();
  const [campaigns, setCampaigns] = useState<CampaignInfo[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    campaign_name: '',
    invitations: [] as InvitationData[],
    expiry_days: 7,
  });
  const [csvContent, setCsvContent] = useState('');
  const [parseError, setParseError] = useState('');
  const [preview, setPreview] = useState<InvitationData[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [expiringInvitations, setExpiringInvitations] = useState<ExpiringInvitationInfo[]>([]);

  // Check for expiring invitations
  useEffect(() => {
    const checkExpiring = async () => {
      try {
        const result = await checkExpiringInvitations();
        if (result?.expiring_soon) {
          setExpiringInvitations(result.expiring_soon);
        }
      } catch (err) {
        console.error('Failed to check expiring invitations:', err);
      }
    };

    checkExpiring();
    const interval = setInterval(checkExpiring, 60000); // Check every minute
    return () => clearInterval(interval);
  }, [checkExpiringInvitations]);

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
      const roleIdx = headers.indexOf('role');

      if (emailIdx === -1 || nameIdx === -1 || roleIdx === -1) {
        setParseError('CSV must have columns: email, full_name, role');
        return;
      }

      const parsedInvitations: InvitationData[] = [];
      for (let i = 1; i < lines.length; i++) {
        const cols = lines[i].split(',').map((c) => c.trim());
        if (!cols[emailIdx]) continue;

        parsedInvitations.push({
          email: cols[emailIdx],
          full_name: cols[nameIdx],
          role: cols[roleIdx] as InvitationData['role'],
        });
      }

      if (parsedInvitations.length === 0) {
        setParseError('No valid rows found');
        return;
      }

      setFormData((prev) => ({ ...prev, invitations: parsedInvitations }));
      setPreview(parsedInvitations.slice(0, 5));
    } catch (e) {
      setParseError('Failed to parse CSV: ' + (e instanceof Error ? e.message : 'Unknown error'));
    }
  }, []);

  const handleFileUpload = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;

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

  const handleSubmitCampaign = useCallback(async () => {
    if (!formData.campaign_name) {
      setParseError('Campaign name required');
      return;
    }

    if (formData.invitations.length === 0) {
      setParseError('No invitations to send');
      return;
    }

    try {
      setSubmitting(true);
      const result = await createBulkInvitationCampaign(
        formData.campaign_name,
        formData.invitations,
        formData.expiry_days
      );

      if (result) {
        // Add to campaigns list - convert API response to CampaignInfo format
        const newCampaign: CampaignInfo = {
          id: result.campaign_id,
          campaign_id: result.campaign_id,
          campaign_name: result.campaign_name,
          status: result.status,
          total_invitations: result.total_invitations,
          sent_count: 0,
          failed_count: 0,
          accepted_count: 0,
          pending_count: result.total_invitations,
          progress_percent: 0,
          expiry_days: formData.expiry_days,
          created_at: new Date().toISOString(),
        };
        setCampaigns((prev) => [newCampaign, ...prev]);

        // Reset form
        setShowForm(false);
        setFormData({
          campaign_name: '',
          invitations: [],
          expiry_days: 7,
        });
        setCsvContent('');
        setPreview([]);
        setParseError('');
      }
    } catch (err) {
      console.error('Failed to create campaign:', err);
    } finally {
      setSubmitting(false);
    }
  }, [formData, createBulkInvitationCampaign]);

  const statusColor = {
    draft: 'bg-gray-100 text-gray-800',
    sending: 'bg-blue-100 text-blue-800',
    sent: 'bg-green-100 text-green-800',
    partial: 'bg-amber-100 text-amber-800',
    completed: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
  } as Record<string, string>;

  if (showForm) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold">Create Invitation Campaign</h1>
          <Button
            variant="outline"
            onClick={() => {
              setShowForm(false);
              setFormData({ campaign_name: '', invitations: [], expiry_days: 7 });
              setCsvContent('');
              setPreview([]);
              setParseError('');
            }}
          >
            Back
          </Button>
        </div>

        {(error || parseError) && (
          <div className="flex gap-2 rounded-lg border border-red-200 bg-red-50 p-4 text-red-800">
            <AlertCircle className="h-5 w-5 flex-shrink-0 mt-0.5" />
            <p>{error || parseError}</p>
          </div>
        )}

        <Card>
          <CardHeader>
            <CardTitle>Campaign Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">Campaign Name</label>
              <input
                type="text"
                value={formData.campaign_name}
                onChange={(e) => setFormData({ ...formData, campaign_name: e.target.value })}
                placeholder="e.g., Q1 2024 Onboarding"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                disabled={submitting}
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Invitation Expiry (days)</label>
              <input
                type="number"
                value={formData.expiry_days}
                onChange={(e) =>
                  setFormData({ ...formData, expiry_days: parseInt(e.target.value) || 7 })
                }
                min={1}
                max={30}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                disabled={submitting}
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Upload Invitations</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="block text-sm font-medium">CSV File</label>
              <input
                type="file"
                accept=".csv"
                onChange={handleFileUpload}
                className="block w-full text-sm border border-gray-300 rounded-lg p-2 cursor-pointer"
                disabled={submitting}
              />
            </div>

            <div className="space-y-2">
              <label className="block text-sm font-medium">Or paste CSV content</label>
              <textarea
                value={csvContent}
                onChange={(e) => {
                  setCsvContent(e.target.value);
                  parseCSV(e.target.value);
                }}
                placeholder="email,full_name,role&#10;john@hospital.org,John Doe,doctor"
                className="w-full h-32 p-3 border border-gray-300 rounded-lg font-mono text-sm"
                disabled={submitting}
              />
            </div>

            {preview.length > 0 && (
              <div className="space-y-2">
                <h3 className="text-sm font-semibold">
                  Preview ({formData.invitations.length} invitations)
                </h3>
                <div className="overflow-x-auto rounded-lg border border-gray-200">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b">
                      <tr className="text-left">
                        <th className="px-4 py-2 font-semibold">Email</th>
                        <th className="px-4 py-2 font-semibold">Name</th>
                        <th className="px-4 py-2 font-semibold">Role</th>
                      </tr>
                    </thead>
                    <tbody>
                      {preview.map((inv, idx) => (
                        <tr key={idx} className="border-b hover:bg-gray-50">
                          <td className="px-4 py-2 text-blue-600">{inv.email}</td>
                          <td className="px-4 py-2">{inv.full_name}</td>
                          <td className="px-4 py-2">
                            <span className="inline-block px-2 py-1 text-xs rounded bg-blue-100 text-blue-700 font-medium">
                              {inv.role}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <div className="flex gap-2">
          <Button
            onClick={handleSubmitCampaign}
            disabled={
              !formData.campaign_name || formData.invitations.length === 0 || submitting || loading
            }
            className="flex-1"
          >
            {submitting ? 'Creating Campaign...' : 'Create Campaign'}
          </Button>
          <Button
            variant="outline"
            onClick={() => {
              setShowForm(false);
              setFormData({ campaign_name: '', invitations: [], expiry_days: 7 });
              setCsvContent('');
              setPreview([]);
              setParseError('');
            }}
            disabled={submitting}
          >
            Cancel
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Invitation Campaigns</h1>
          <p className="text-gray-600">Manage bulk user invitations and track acceptance</p>
        </div>
        <Button onClick={() => setShowForm(true)} className="gap-2">
          <Plus className="h-4 w-4" />
          New Campaign
        </Button>
      </div>

      {error && (
        <div className="flex gap-2 rounded-lg border border-red-200 bg-red-50 p-4 text-red-800">
          <AlertCircle className="h-5 w-5 flex-shrink-0 mt-0.5" />
          <p>{error}</p>
        </div>
      )}

      {/* Expiring Invitations Alert */}
      {expiringInvitations.length > 0 && (
        <Card accent="amber">
          <CardContent className="pt-6">
            <div className="flex items-start gap-3">
              <AlertCircle className="h-5 w-5 flex-shrink-0 text-amber-600 mt-0.5" />
              <div>
                <p className="font-semibold text-amber-900 mb-2">Invitations Expiring Soon</p>
                <p className="text-sm text-amber-800 mb-3">
                  {expiringInvitations.length} invitation(s) will expire in the next 24 hours
                </p>
                <div className="space-y-1">
                  {expiringInvitations.slice(0, 3).map((inv, idx) => (
                    <p key={idx} className="text-sm text-amber-800">
                      • {inv.email} ({inv.hours_remaining}h remaining)
                    </p>
                  ))}
                  {expiringInvitations.length > 3 && (
                    <p className="text-sm text-amber-800">
                      + {expiringInvitations.length - 3} more
                    </p>
                  )}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Campaigns List */}
      {campaigns.length === 0 ? (
        <Card>
          <CardContent className="pt-12 pb-12 text-center">
            <Mail className="h-12 w-12 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-600 mb-4">No campaigns created yet</p>
            <Button onClick={() => setShowForm(true)}>Create First Campaign</Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4">
          {campaigns.map((campaign) => (
            <Card key={campaign.id}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>{campaign.campaign_name}</CardTitle>
                    <p className="text-sm text-gray-600 mt-1">
                      Created {new Date(campaign.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <span className={`inline-block px-3 py-1 rounded-full text-sm font-semibold ${statusColor[campaign.status] || ''}`}>
                    {campaign.status.toUpperCase()}
                  </span>
                </div>
              </CardHeader>

              <CardContent className="space-y-4">
                {/* Progress Bar */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-sm font-medium">Progress</p>
                    <p className="text-sm font-semibold">{campaign.progress_percent}%</p>
                  </div>
                  <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-blue-500 to-blue-600 transition-all"
                      style={{ width: `${campaign.progress_percent}%` }}
                    />
                  </div>
                </div>

                {/* Stats Grid */}
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
                  <div>
                    <p className="text-sm text-gray-600">Total</p>
                    <p className="text-2xl font-bold">{campaign.total_invitations}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600 flex items-center gap-1">
                      <Mail className="h-4 w-4" /> Sent
                    </p>
                    <p className="text-2xl font-bold text-blue-600">{campaign.sent_count}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600 flex items-center gap-1">
                      <CheckCircle className="h-4 w-4" /> Accepted
                    </p>
                    <p className="text-2xl font-bold text-green-600">{campaign.accepted_count}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600 flex items-center gap-1">
                      <Clock className="h-4 w-4" /> Pending
                    </p>
                    <p className="text-2xl font-bold text-amber-600">{campaign.pending_count}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600 flex items-center gap-1">
                      <XCircle className="h-4 w-4" /> Failed
                    </p>
                    <p className="text-2xl font-bold text-red-600">{campaign.failed_count}</p>
                  </div>
                </div>

                {/* Info */}
                <div className="rounded-lg bg-gray-50 p-3 text-sm text-gray-700">
                  <p>
                    <strong>Expiry:</strong> {campaign.expiry_days} days
                  </p>
                  {campaign.sent_at && (
                    <p>
                      <strong>Sent:</strong> {new Date(campaign.sent_at).toLocaleDateString()}
                    </p>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Instructions */}
      <Card className="bg-blue-50 border-blue-200">
        <CardContent className="pt-6">
          <p className="font-semibold text-blue-900 mb-2">📋 How Bulk Invitations Work</p>
          <ul className="space-y-1 text-sm text-blue-900 list-disc list-inside">
            <li>Create a campaign and upload CSV with email, full_name, and role</li>
            <li>Invitations are created in draft status</li>
            <li>Send them to initiate email delivery</li>
            <li>Track acceptance status and expiration dates</li>
            <li>Expired invitations must be resent</li>
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
