'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Activity, TrendingUp, Users, CheckCircle, AlertCircle, Clock } from 'lucide-react';
import { useBatchOperations } from '@/hooks/use-batch-operations';

interface BatchSummary {
  total_jobs: number;
  active_jobs: number;
  completed_jobs: number;
  failed_jobs: number;
  total_users_imported: number;
  import_success_rate: number;
}

interface CampaignSummary {
  total_campaigns: number;
  active_campaigns: number;
  sent_invitations: number;
  accepted_invitations: number;
  expiring_soon_count: number;
}

export function BatchOperationsDashboardWidget() {
  const { getBatchOperationsSummary, loading, error } = useBatchOperations();
  const [batchSummary, setBatchSummary] = useState<BatchSummary>({
    total_jobs: 0,
    active_jobs: 0,
    completed_jobs: 0,
    failed_jobs: 0,
    total_users_imported: 0,
    import_success_rate: 0,
  });

  const [campaignSummary, setCampaignSummary] = useState<CampaignSummary>({
    total_campaigns: 0,
    active_campaigns: 0,
    sent_invitations: 0,
    accepted_invitations: 0,
    expiring_soon_count: 0,
  });

  useEffect(() => {
    const fetchSummary = async () => {
      try {
        const data = await getBatchOperationsSummary();
        if (data) {
          setBatchSummary({
            total_jobs: data.import_jobs.total,
            active_jobs: data.import_jobs.active,
            completed_jobs: data.import_jobs.completed,
            failed_jobs: data.import_jobs.failed,
            total_users_imported: data.import_jobs.total_users_imported,
            import_success_rate: data.import_jobs.success_rate,
          });

          setCampaignSummary({
            total_campaigns: data.invitation_campaigns.total,
            active_campaigns: data.invitation_campaigns.active,
            sent_invitations: data.invitation_campaigns.total_sent,
            accepted_invitations: data.invitation_campaigns.total_accepted,
            expiring_soon_count: data.invitation_campaigns.expiring_soon,
          });
        }
      } catch (err) {
        console.error('Error fetching batch operations summary:', err);
      }
    };

    fetchSummary();

    // Auto-refresh every 30 seconds
    const interval = setInterval(fetchSummary, 30000);
    return () => clearInterval(interval);
  }, [getBatchOperationsSummary]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold">Batch Operations Overview</h2>
        <p className="text-gray-600">Real-time metrics for user imports and invitation campaigns</p>
        {error && <p className="text-red-600 text-sm mt-2">{error}</p>}
        {loading && <p className="text-gray-500 text-sm mt-2">Loading...</p>}
      </div>

      {/* Import Jobs Summary */}
      <div className="space-y-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <Users className="h-5 w-5" />
          User Import Jobs
        </h3>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-gray-600">Total Jobs</p>
              <p className="text-3xl font-bold text-blue-600">{batchSummary.total_jobs}</p>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-gray-600 flex items-center gap-1">
                <Activity className="h-4 w-4" /> Active
              </p>
              <p className="text-3xl font-bold text-amber-600">{batchSummary.active_jobs}</p>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-gray-600 flex items-center gap-1">
                <CheckCircle className="h-4 w-4" /> Completed
              </p>
              <p className="text-3xl font-bold text-green-600">{batchSummary.completed_jobs}</p>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-gray-600 flex items-center gap-1">
                <AlertCircle className="h-4 w-4" /> Failed
              </p>
              <p className="text-3xl font-bold text-red-600">{batchSummary.failed_jobs}</p>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-gray-600">Success Rate</p>
              <p className="text-3xl font-bold text-green-600">
                {batchSummary.import_success_rate}%
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Import Stats */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Import Statistics</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-gray-600 mb-2">Users Imported (Total)</p>
                <p className="text-4xl font-bold text-blue-600">
                  {batchSummary.total_users_imported}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-600 mb-2">Average Success Rate</p>
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-3 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-green-500 to-green-600"
                      style={{ width: `${batchSummary.import_success_rate}%` }}
                    />
                  </div>
                  <span className="text-lg font-bold text-green-600">
                    {batchSummary.import_success_rate}%
                  </span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Invitation Campaigns Summary */}
      <div className="space-y-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <TrendingUp className="h-5 w-5" />
          Invitation Campaigns
        </h3>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-gray-600">Total Campaigns</p>
              <p className="text-3xl font-bold text-blue-600">{campaignSummary.total_campaigns}</p>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-gray-600 flex items-center gap-1">
                <Activity className="h-4 w-4" /> Active
              </p>
              <p className="text-3xl font-bold text-amber-600">
                {campaignSummary.active_campaigns}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-gray-600">Sent Invitations</p>
              <p className="text-3xl font-bold text-blue-600">
                {campaignSummary.sent_invitations}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-gray-600 flex items-center gap-1">
                <CheckCircle className="h-4 w-4" /> Accepted
              </p>
              <p className="text-3xl font-bold text-green-600">
                {campaignSummary.accepted_invitations}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-gray-600 flex items-center gap-1">
                <Clock className="h-4 w-4" /> Expiring
              </p>
              <p className="text-3xl font-bold text-orange-600">
                {campaignSummary.expiring_soon_count}
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Campaign Stats */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Campaign Statistics</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-gray-600 mb-2">Acceptance Rate</p>
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-3 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-green-500 to-green-600"
                      style={{
                        width:
                          campaignSummary.sent_invitations > 0
                            ? `${Math.round((campaignSummary.accepted_invitations / campaignSummary.sent_invitations) * 100)}%`
                            : '0%',
                      }}
                    />
                  </div>
                  <span className="text-lg font-bold text-green-600">
                    {campaignSummary.sent_invitations > 0
                      ? Math.round((campaignSummary.accepted_invitations / campaignSummary.sent_invitations) * 100)
                      : 0}
                    %
                  </span>
                </div>
              </div>
              <div>
                <p className="text-sm text-gray-600 mb-2">Pending Acceptance</p>
                <p className="text-3xl font-bold text-blue-600">
                  {campaignSummary.sent_invitations - campaignSummary.accepted_invitations}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Quick Actions */}
      <Card className="bg-blue-50 border-blue-200">
        <CardHeader>
          <CardTitle className="text-base">Quick Tips</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2 text-sm text-blue-900 list-disc list-inside">
            <li>
              Monitor import jobs in real-time and track validation/processing errors
            </li>
            <li>
              Check expiring invitations and resend them before they expire
            </li>
            <li>
              Analyze acceptance rates to identify onboarding bottlenecks
            </li>
            <li>
              Export import results as CSV for external analysis or record-keeping
            </li>
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}

// Export both the dashboard widget and a standalone page component
export function BatchOperationsDashboard() {
  return <BatchOperationsDashboardWidget />;
}
