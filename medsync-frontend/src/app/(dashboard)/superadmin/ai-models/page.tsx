'use client';

import React, { useEffect, useState } from 'react';
import { useModelManagement, type ModelVersion } from '@/hooks/use-model-management';
import { 
  Database, 
  Brain, 
  AlertCircle, 
  History, 
  Play, 
  Activity,
  ArrowUpRight,
  ArrowDownRight,
  ShieldCheck,
  Zap,
  ChevronRight
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from '@/components/ui/Table';
import { 
  Card, 
  CardContent, 
  CardHeader, 
  CardTitle 
} from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/Checkbox';

export default function AIModelManagementPage() {
  const { 
    models, 
    loading, 
    fetchModels, 
    approveModel, 
    startRetraining, 
    retrainingTask,
    checkRetrainStatus 
  } = useModelManagement();

  const [approvalModal, setApprovalModal] = useState<{ isOpen: boolean; modelId: string | null }>({
    isOpen: false,
    modelId: null,
  });
  const [approvalNotes, setApprovalNotes] = useState('');
  const [confirmIRB, setConfirmIRB] = useState(false);

  useEffect(() => {
    fetchModels();
  }, [fetchModels]);

  // Poll for retraining status if task exists
  useEffect(() => {
    if (retrainingTask) {
      const interval = setInterval(() => {
        checkRetrainStatus(retrainingTask);
      }, 3000);
      return () => clearInterval(interval);
    }
  }, [retrainingTask, checkRetrainStatus]);

  const handleApprove = async () => {
    if (approvalModal.modelId && approvalNotes && confirmIRB) {
      await approveModel(approvalModal.modelId, approvalNotes);
      setApprovalModal({ isOpen: false, modelId: null });
      setApprovalNotes('');
      setConfirmIRB(false);
    }
  };

  const getStatusBadge = (model: ModelVersion) => {
    if (model.is_production) {
      return <Badge className="bg-green-100 text-green-700 border-green-200">Production</Badge>;
    }
    if (model.training_data_source === 'synthetic') {
      return <Badge variant="critical">Synthetic Data</Badge>;
    }
    if (model.clinical_use_approved) {
      return <Badge variant="active">Validated</Badge>;
    }
    return <Badge variant="default" className="border border-gray-300">Pending Approval</Badge>;
  };

  const formatMetric = (val: number | undefined) => {
    if (val === undefined) return 'N/A';
    return (val * 100).toFixed(1) + '%';
  };

  const renderDelta = (val: number | undefined) => {
    if (val === undefined) return null;
    const isPos = val >= 0;
    return (
      <span className={`text-xs flex items-center ${isPos ? 'text-green-600' : 'text-red-600'}`}>
        {isPos ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
        {(val * 100).toFixed(1)}%
      </span>
    );
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8 animate-in fade-in duration-500">
      <header className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 tracking-tight flex items-center gap-3">
            <Brain className="w-8 h-8 text-blue-600" />
            AI Model Governance
          </h1>
          <p className="text-gray-500 mt-1">Manage, retrain, and validate clinical prediction models.</p>
        </div>
        <div className="flex gap-3">
          <Button 
            variant="outline" 
            onClick={() => fetchModels()} 
            disabled={loading}
            className="gap-2"
          >
            <History className="w-4 h-4" />
            Refresh
          </Button>
          <Button 
            onClick={() => startRetraining('risk_prediction', 'synthetic')} 
            className="bg-blue-600 hover:bg-blue-700 gap-2"
            disabled={!!retrainingTask}
          >
            {retrainingTask ? (
              <Activity className="w-4 h-4 animate-spin" />
            ) : (
              <Play className="w-4 h-4" />
            )}
            Retrain Models
          </Button>
        </div>
      </header>

      {/* Retraining Progress Banner */}
      {retrainingTask && (
        <Card className="bg-blue-50 border-blue-200 overflow-hidden">
          <CardContent className="p-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-2 h-2 bg-blue-600 rounded-full animate-ping" />
              <p className="text-blue-800 font-medium text-sm">
                Async retraining task in progress...
              </p>
            </div>
            <p className="text-blue-600 text-xs font-mono">{retrainingTask}</p>
          </CardContent>
          <div className="h-1 bg-blue-100">
            <div className="h-full bg-blue-600 w-1/2 animate-[progress_2s_infinite_linear]" />
          </div>
        </Card>
      )}

      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="hover:shadow-md transition-shadow">
          <CardHeader className="pb-2">
            <p className="flex items-center gap-1.5 uppercase tracking-wider text-[10px] font-semibold text-gray-400">
              <Zap className="w-3 h-3" />
              Active Risk Model
            </p>
            <CardTitle className="text-lg">
              {models.find(m => m.model_type === 'risk_prediction' && m.is_production)?.version_tag || 'None'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <ShieldCheck className="w-4 h-4 text-green-500" />
              <span>Validated against local data</span>
            </div>
          </CardContent>
        </Card>
        
        <Card className="hover:shadow-md transition-shadow">
          <CardHeader className="pb-2">
            <p className="flex items-center gap-1.5 uppercase tracking-wider text-[10px] font-semibold text-gray-400">
              <Activity className="w-3 h-3" />
              Active Triage Model
            </p>
            <CardTitle className="text-lg">
              {models.find(m => m.model_type === 'triage' && m.is_production)?.version_tag || 'None'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <AlertCircle className="w-4 h-4 text-amber-500" />
              <span>Pending production promotion</span>
            </div>
          </CardContent>
        </Card>

        <Card className="hover:shadow-md transition-shadow">
          <CardHeader className="pb-2">
            <p className="flex items-center gap-1.5 uppercase tracking-wider text-[10px] font-semibold text-gray-400">
              <Database className="w-3 h-3" />
              Training Samples
            </p>
            <CardTitle className="text-lg">
              {models.reduce((acc, m) => acc + m.training_sample_count, 0).toLocaleString()}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <ArrowUpRight className="w-4 h-4 text-blue-500" />
              <span>+12.4% vs last quarter</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Model Versions Table */}
      <Card>
        <CardHeader>
          <CardTitle>Model Version History</CardTitle>
          <p className="text-sm text-gray-500 mt-1">Full audit trail of all trained models and their performance metrics.</p>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow className="bg-gray-50/50">
                <TableHead className="w-[180px]">Model Type</TableHead>
                <TableHead>Version</TableHead>
                <TableHead>Trained</TableHead>
                <TableHead>Data Source</TableHead>
                <TableHead className="text-right">F1 Score</TableHead>
                <TableHead className="text-right">AUC-ROC</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading && models.length === 0 ? (
                <TableRow>
                  <td colSpan={8} className="px-4 py-12 text-center text-gray-500">
                    Loading model history...
                  </td>
                </TableRow>
              ) : models.length === 0 ? (
                <TableRow>
                  <td colSpan={8} className="px-4 py-12 text-center text-gray-500">
                    No model versions found. Start retraining to create one.
                  </td>
                </TableRow>
              ) : (
                models.map((model) => (
                  <TableRow key={model.id} className="group hover:bg-gray-50/50 transition-colors">
                    <TableCell className="font-medium capitalize text-gray-700">
                      {model.model_type.replace('_', ' ')}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-gray-500">{model.version_tag}</TableCell>
                    <TableCell className="text-xs text-gray-500">
                      {new Date(model.trained_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell>
                      <Badge variant="default" className="capitalize font-normal text-[10px] border border-gray-200">
                        {model.training_data_source.replace('_', ' ')}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex flex-col items-end">
                        <span className="font-medium">{formatMetric(model.evaluation_metrics.f1)}</span>
                        {renderDelta(model.comparison_vs_previous?.f1)}
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex flex-col items-end">
                        <span className="font-medium">{formatMetric(model.evaluation_metrics.auc_roc)}</span>
                        {renderDelta(model.comparison_vs_previous?.auc_roc)}
                      </div>
                    </TableCell>
                    <TableCell>{getStatusBadge(model)}</TableCell>
                    <TableCell className="text-right">
                      {!model.is_production && model.training_data_source !== 'synthetic' && (
                        <Button 
                          size="sm" 
                          variant="primary"
                          className="h-8 px-3 text-xs bg-gray-900 hover:bg-gray-800"
                          onClick={() => setApprovalModal({ isOpen: true, modelId: model.id })}
                        >
                          Approve
                        </Button>
                      )}
                      {model.is_production && (
                        <Button variant="ghost" size="sm" className="h-8 w-8 p-0 opacity-0 group-hover:opacity-100">
                          <ChevronRight className="w-4 h-4" />
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Approval Dialog */}
      <Dialog 
        open={approvalModal.isOpen} 
        onOpenChange={(open) => !open && setApprovalModal({ isOpen: false, modelId: null })}
      >
        <DialogContent size="md">
          <DialogHeader>
            <DialogTitle>Approve Model for Clinical Use</DialogTitle>
            <p className="text-sm text-gray-500 mt-1">
              This action will promote this model version to production. Clinicians will start seeing predictions from this model.
            </p>
          </DialogHeader>
          <div className="space-y-6 py-4">
            <div className="space-y-2">
              <label htmlFor="notes" className="text-sm font-medium text-gray-700">
                Clinical Validation Summary
              </label>
              <Textarea 
                id="notes" 
                placeholder="Briefly describe the validation performed (e.g., 'Tested against 500 records at KBTH with 92% accuracy')."
                value={approvalNotes}
                onChange={(e) => setApprovalNotes(e.target.value)}
                className="min-h-[100px]"
              />
            </div>
            <div className="flex items-start space-x-3 bg-amber-50 p-4 rounded-lg border border-amber-100">
              <Checkbox 
                id="confirm" 
                checked={confirmIRB} 
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setConfirmIRB(e.target.checked)}
                className="mt-1"
              />
              <div className="grid gap-1.5 leading-none">
                <label
                  htmlFor="confirm"
                  className="text-sm font-medium text-amber-900 leading-normal cursor-pointer"
                >
                  I confirm this model has been validated against real patient data with appropriate IRB approval.
                </label>
              </div>
            </div>
          </div>
          <div className="flex justify-end gap-3 mt-6">
            <Button variant="outline" onClick={() => setApprovalModal({ isOpen: false, modelId: null })}>
              Cancel
            </Button>
            <Button 
              onClick={handleApprove} 
              disabled={!approvalNotes || !confirmIRB}
              className="bg-blue-600 hover:bg-blue-700"
            >
              Confirm Approval & Deploy
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
