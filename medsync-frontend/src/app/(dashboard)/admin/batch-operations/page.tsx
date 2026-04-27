'use client';

import { useState } from 'react';
import { useAuth } from '@/lib/auth-context';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import { UserImportForm } from '@/components/features/UserImportForm';
import { BulkInvitationDashboard } from '@/components/features/BulkInvitationDashboard';
import { BatchOperationsDashboard } from '@/components/features/BatchOperationsDashboard';
import { hasRole, ALL_ADMIN_ROLES } from '@/lib/permissions';

export default function BatchOperationsPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<'overview' | 'import' | 'invitations'>('overview');

  // RBAC-17: use centralised admin role check
  useEffect(() => {
    if (user && !hasRole(user.role, ALL_ADMIN_ROLES)) {
      router.push('/unauthorized');
    }
  }, [user, router]);

  if (!user || !hasRole(user.role, ALL_ADMIN_ROLES)) {
    return null;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold">Batch Operations</h1>
        <p className="text-gray-600">Manage user imports, invitation campaigns, and batch operations</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-4 border-b border-gray-200 overflow-x-auto">
        <button
          onClick={() => setActiveTab('overview')}
          className={`px-4 py-2 font-medium text-sm transition-colors whitespace-nowrap ${
            activeTab === 'overview'
              ? 'border-b-2 border-blue-600 text-blue-600'
              : 'text-gray-600 hover:text-gray-900'
          }`}
        >
          Overview
        </button>
        <button
          onClick={() => setActiveTab('import')}
          className={`px-4 py-2 font-medium text-sm transition-colors whitespace-nowrap ${
            activeTab === 'import'
              ? 'border-b-2 border-blue-600 text-blue-600'
              : 'text-gray-600 hover:text-gray-900'
          }`}
        >
          User Import
        </button>
        <button
          onClick={() => setActiveTab('invitations')}
          className={`px-4 py-2 font-medium text-sm transition-colors whitespace-nowrap ${
            activeTab === 'invitations'
              ? 'border-b-2 border-blue-600 text-blue-600'
              : 'text-gray-600 hover:text-gray-900'
          }`}
        >
          Invitation Campaigns
        </button>
      </div>

      {/* Tab Content */}
      <div>
        {activeTab === 'overview' && <BatchOperationsDashboard />}
        {activeTab === 'import' && <UserImportForm />}
        {activeTab === 'invitations' && <BulkInvitationDashboard />}
      </div>
    </div>
  );
}
