/**
 * AI Insights Page
 * 
 * Comprehensive AI analysis dashboard for a patient.
 * Shows risk predictions, triage, diagnosis suggestions, and referrals.
 */

'use client';

import React, { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import { useAIAnalysis, type ComprehensiveAnalysis } from '@/hooks/use-ai-analysis';
import { RiskScoresWidget } from '@/components/features/ai/RiskScoresWidget';
import { AIAlertsPanel } from '@/components/features/ai/AIAlertsPanel';
import { TriageCard } from '@/components/features/ai/TriageCard';
import { SimilarPatients } from '@/components/features/ai/SimilarPatients';
import { ReferralSuggestions } from '@/components/features/ai/ReferralSuggestions';
import { AnalysisHistory } from '@/components/features/ai/AnalysisHistory';
import { Loader, RefreshCw, AlertCircle } from 'lucide-react';
import type { AnalysisHistoryItem } from '@/hooks/use-ai-analysis';
import { isBenignApiNetworkFailure } from '@/lib/api-client';
import { AIDisclaimer } from '@/components/ui/AIDisclaimer';

export default function AIInsightsPage() {
  const params = useParams();
  const patientId = params.id as string;
  const { user } = useAuth();

  // Role guard: AI Insights only for doctors
  if (user && user.role !== 'doctor') {
    return (
      <div className="space-y-6 p-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6">
          <AlertCircle className="w-5 h-5 text-red-600 mb-2" />
          <h3 className="font-semibold text-red-900">Access Denied</h3>
          <p className="text-sm text-red-800 mt-1">
            AI Clinical Insights are only available to doctors.
          </p>
        </div>
      </div>
    );
  }

  return <AIInsightsContentAuthorized patientId={patientId} />;
}

function AIInsightsContentAuthorized({ patientId }: { patientId: string }) {
  const { analyzePatient, getAnalysisHistory, error } = useAIAnalysis();

  const [analysis, setAnalysis] = useState<ComprehensiveAnalysis | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(true);
  const [history, setHistory] = useState<{
    analyses: AnalysisHistoryItem[];
    total: number;
    limit: number;
    offset: number;
  } | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);

  useEffect(() => {
    if (!patientId) return;

    const runAnalysis = async () => {
      try {
        setIsAnalyzing(true);
        const result = await analyzePatient(patientId, {
          include_similarity: true,
          include_referral: true,
        });
        setAnalysis(result);
        setHistoryLoading(true);
        try {
          const res = await getAnalysisHistory(patientId, 10, 0);
          setHistory({
            analyses: res.analyses,
            total: res.total,
            limit: res.limit,
            offset: res.offset,
          });
        } catch (err) {
          if (!isBenignApiNetworkFailure(err) && process.env.NODE_ENV === 'development') {
            console.error('History load failed:', err);
          }
        } finally {
          setHistoryLoading(false);
        }
      } catch (err) {
        if (!isBenignApiNetworkFailure(err) && process.env.NODE_ENV === 'development') {
          console.error('Analysis failed:', err);
        }
      } finally {
        setIsAnalyzing(false);
      }
    };

    runAnalysis();
  }, [patientId, analyzePatient, getAnalysisHistory]);

  const handleRefresh = async () => {
    try {
      setIsAnalyzing(true);
      const result = await analyzePatient(patientId, {
        include_similarity: true,
        include_referral: true,
      });
      setAnalysis(result);
    } catch (err) {
      if (!isBenignApiNetworkFailure(err) && process.env.NODE_ENV === 'development') console.error('Analysis refresh failed:', err);
    } finally {
      setIsAnalyzing(false);
    }
  };

  return (
    <div className="space-y-6 p-6">
      <AIDisclaimer />
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">AI Clinical Insights</h1>
          <p className="text-gray-600 mt-1">Comprehensive AI-powered clinical analysis</p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={isAnalyzing}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${isAnalyzing ? 'animate-spin' : ''}`} />
          Refresh Analysis
        </button>
      </div>

      {/* Loading State */}
      {isAnalyzing && !analysis && (
        <div className="flex flex-col items-center justify-center py-12 bg-white rounded-lg border border-gray-200">
          <Loader className="w-8 h-8 text-blue-600 animate-spin mb-3" />
          <p className="text-gray-600">Running comprehensive AI analysis...</p>
          <p className="text-sm text-gray-500 mt-1">This may take a few moments</p>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex gap-3">
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <div>
            <h3 className="font-semibold text-red-900">Analysis Error</h3>
            <p className="text-sm text-red-800">{error}</p>
          </div>
        </div>
      )}

      {/* Analysis Results */}
      {analysis && (
        <>
          {/* Top Alert - If Critical */}
          {analysis.alerts && analysis.alerts.length > 0 && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <h3 className="font-semibold text-red-900 mb-2">🚨 Critical Alerts</h3>
              <ul className="space-y-1">
                {analysis.alerts.map((alert, idx) => (
                  <li key={idx} className="text-sm text-red-800">
                    {alert}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Main Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Triage Assessment */}
            {analysis.triage_assessment && (
              <TriageCard
                triageLevel={analysis.triage_assessment.triage_level}
                triageScore={
                  (analysis.triage_assessment as { triage_score?: number; score?: number }).triage_score ??
                  (analysis.triage_assessment as { score?: number }).score ??
                  0
                }
                esiLevel={analysis.triage_assessment.esi_level}
                recommendedAction={analysis.triage_assessment.recommended_action}
                indicators={analysis.triage_assessment.indicators || []}
                isLoading={isAnalyzing}
              />
            )}

            {/* Alerts & Recommendations */}
            <AIAlertsPanel
              alerts={analysis.alerts || []}
              recommendedActions={analysis.recommended_actions || []}
              isLoading={isAnalyzing}
            />
          </div>

          {/* Risk Predictions */}
          {analysis.risk_analysis && (
            <RiskScoresWidget
              predictions={analysis.risk_analysis.predictions}
              topRiskDisease={analysis.risk_analysis.top_risk_disease}
              topRiskScore={analysis.risk_analysis.top_risk_score}
              isLoading={isAnalyzing}
            />
          )}

          {/* Clinical Summary */}
          {analysis.clinical_summary && (
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-3">Clinical Summary</h3>
              <p className="text-gray-700 leading-relaxed">{analysis.clinical_summary}</p>
            </div>
          )}

          {/* Diagnosis Suggestions */}
          {analysis.diagnosis_suggestions && analysis.diagnosis_suggestions.suggestions && (
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">
                Differential Diagnosis Suggestions
              </h3>
              <div className="space-y-4">
                {analysis.diagnosis_suggestions.suggestions.slice(0, 5).map((sugg, idx) => (
                  <div key={idx} className="border border-gray-200 rounded p-4">
                    <div className="flex justify-between items-start mb-2">
                      <div>
                        <p className="font-semibold text-gray-900">#{sugg.rank} {sugg.diagnosis}</p>
                        <p className="text-sm text-gray-600">ICD-10: {sugg.icd10_code}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-lg font-bold text-blue-600">
                          {(sugg.probability * 100).toFixed(0)}%
                        </p>
                        <p className="text-xs text-gray-600">
                          Confidence: {(sugg.confidence * 100).toFixed(0)}%
                        </p>
                      </div>
                    </div>
                    {sugg.recommended_tests && sugg.recommended_tests.length > 0 && (
                      <div className="text-sm text-gray-700 mt-3">
                        <p className="font-medium mb-1">Recommended Tests:</p>
                        <ul className="list-disc list-inside space-y-1">
                          {sugg.recommended_tests.map((test, tidx) => (
                            <li key={tidx}>{test}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Similar Patients & Referral Suggestions */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <SimilarPatients
              similarPatients={
                analysis.similar_patients?.similar_patients ?? []
              }
              isLoading={isAnalyzing}
            />
            <ReferralSuggestions
              recommendedHospitals={
                analysis.referral_recommendations?.recommended_hospitals ?? []
              }
              isLoading={isAnalyzing}
            />
          </div>

          {/* Analysis History */}
          <AnalysisHistory
            analyses={history?.analyses ?? []}
            total={history?.total ?? 0}
            isLoading={historyLoading}
            hasMore={history ? history.analyses.length < history.total : false}
            onLoadMore={
              history && history.analyses.length < history.total
                ? async () => {
                    setHistoryLoading(true);
                    try {
                      const res = await getAnalysisHistory(
                        patientId,
                        history.limit,
                        history.offset + history.limit
                      );
                      setHistory({
                        analyses: [...history.analyses, ...res.analyses],
                        total: res.total,
                        limit: res.limit,
                        offset: res.offset,
                      });
                    } finally {
                      setHistoryLoading(false);
                    }
                  }
                : undefined
            }
          />

          {/* Confidence Score */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <p className="text-sm text-gray-600">Overall Analysis Confidence</p>
            <div className="flex items-center gap-3 mt-2">
              <div className="flex-1 bg-blue-200 rounded-full h-3">
                <div
                  className="bg-blue-600 h-3 rounded-full transition-all"
                  style={{ width: `${(analysis.confidence_score || 0) * 100}%` }}
                ></div>
              </div>
              <p className="text-lg font-bold text-blue-600">
                {((analysis.confidence_score || 0) * 100).toFixed(0)}%
              </p>
            </div>
          </div>

          {/* Analysis Metadata */}
          <div className="text-xs text-gray-500 text-center">
            Analysis completed at {new Date(analysis.analysis_timestamp).toLocaleString()}
            {' • '}
            Agents executed: {analysis.agents_executed.join(', ')}
          </div>
        </>
      )}
    </div>
  );
}
