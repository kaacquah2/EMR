'use client';

import { useState } from 'react';
import { UserImportForm } from '@/components/features/UserImportForm';
import { BulkInvitationDashboard } from '@/components/features/BulkInvitationDashboard';
import { BatchOperationsDashboard } from '@/components/features/BatchOperationsDashboard';
import { ALL_ADMIN_ROLES } from '@/lib/permissions';
import { RequireRole } from '@/components/auth/RequireRole';

function BatchOperationsContent() {
  const [activeTab, setActiveTab] = useState<'overview' | 'import' | 'invitations'>('overview');

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

export default function BatchOperationsPage() {
  return (
    <RequireRole roles={ALL_ADMIN_ROLES}>
      <BatchOperationsContent />
    </RequireRole>
  );
}
