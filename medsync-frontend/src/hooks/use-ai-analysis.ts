/**
 * React custom hook for AI Analysis API integration.
 * Uses useApi() for authenticated requests.
 *
 * Usage:
 * const { analyzePatient, predictRisk, getCDS, triagePatient, getAnalysisHistory, loading, error } = useAIAnalysis();
 * const result = await analyzePatient(patientId);
 */

import { useState, useCallback } from 'react';
import { useApi } from '@/hooks/use-api';

export interface RiskPrediction {
  disease: string;
  risk_score: number;
  confidence: number;
  risk_category: 'low' | 'medium' | 'high' | 'critical';
}

export interface DiagnosisSuggestion {
  rank: number;
  diagnosis: string;
  icd10_code: string;
  probability: number;
  confidence: number;
  matching_symptoms: string[];
  recommended_tests: string[];
  clinical_notes: string;
}

export interface TriageResult {
  patient_id: string;
  triage_level: 'critical' | 'high' | 'medium' | 'low';
  triage_score: number;
  confidence: number;
  esi_level: number;
  recommended_action: string;
  indicators: Array<{ indicator: string; severity: string }>;
}

export interface ComprehensiveAnalysis {
  patient_id: string;
  analysis_timestamp: string;
  agents_executed: string[];
  risk_analysis: {
    predictions: Record<string, RiskPrediction>;
    top_risk_disease: string;
    top_risk_score: number;
  };
  triage_assessment: TriageResult;
  diagnosis_suggestions: {
    suggestions: DiagnosisSuggestion[];
  };
  similar_patients?: {
    similar_patients: Array<{
      patient_id: string;
      similarity_score: number;
      conditions: string[];
      treatment_outcome?: string;
      success_rate?: number;
    }>;
  };
  referral_recommendations?: {
    recommended_hospitals: Array<{
      hospital_name: string;
      hospital_id: string;
      specialty_match: number;
      bed_availability: number;
      distance_km?: number;
      reason: string;
    }>;
  };
  clinical_summary: string;
  recommended_actions: string[];
  alerts: string[];
  confidence_score: number;
}

export interface AnalysisHistoryItem {
  id: string;
  analysis_type: string;
  overall_confidence: number;
  agents_executed: string[];
  clinical_summary: string;
  recommended_actions: string[];
  alerts: string[];
  chief_complaint: string;
  created_at: string;
}

export function useAIAnalysis() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const api = useApi();

  const request = useCallback(
    async <T>(fn: () => Promise<T>): Promise<T> => {
      setLoading(true);
      setError(null);
      try {
        return await fn();
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Unknown error';
        setError(message);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const analyzePatient = useCallback(
    async (
      patientId: string,
      options?: { include_similarity?: boolean; include_referral?: boolean }
    ): Promise<ComprehensiveAnalysis> => {
      return request(async () => {
        const params = new URLSearchParams();
        if (options?.include_similarity !== undefined) {
          params.append('include_similarity', String(options.include_similarity));
        }
        if (options?.include_referral !== undefined) {
          params.append('include_referral', String(options.include_referral));
        }
        const path = `ai/analyze-patient/${patientId}${params.toString() ? `?${params}` : ''}`;
        return api.post<ComprehensiveAnalysis>(path);
      });
    },
    [api, request]
  );

  const predictRisk = useCallback(
    async (patientId: string): Promise<{
      risk_predictions: Record<string, RiskPrediction>;
      top_risk_disease: string;
      top_risk_score: number;
      contributing_factors: Array<{ factor: string; weight: string; value: string }>;
      recommendations: string[];
    }> => {
      return request(() => api.post(`ai/risk-prediction/${patientId}`));
    },
    [api, request]
  );

  const getCDS = useCallback(
    async (
      patientId: string,
      chiefComplaint?: string
    ): Promise<{ suggestions: DiagnosisSuggestion[]; chief_complaint: string }> => {
      return request(() =>
        api.post(`ai/clinical-decision-support/${patientId}`, {
          chief_complaint: chiefComplaint || '',
        })
      );
    },
    [api, request]
  );

  const triagePatient = useCallback(
    async (patientId: string, chiefComplaint?: string): Promise<TriageResult> => {
      return request(() =>
        api.post(`ai/triage/${patientId}`, { chief_complaint: chiefComplaint || '' })
      );
    },
    [api, request]
  );

  const findSimilarPatients = useCallback(
    async (
      patientId: string,
      k?: number
    ): Promise<{
      similar_patients: Array<{
        rank: number;
        patient_id: string;
        similarity_score: number;
        age?: number;
        conditions: string[];
        treatment_outcome?: string;
        success_rate?: number;
      }>;
    }> => {
      return request(() => {
        const path = k != null ? `ai/find-similar-patients/${patientId}?k=${k}` : `ai/find-similar-patients/${patientId}`;
        return api.post(path);
      });
    },
    [api, request]
  );

  const getReferralRecommendations = useCallback(
    async (
      patientId: string,
      specialty?: string
    ): Promise<{
      recommended_hospitals: Array<{
        rank: number;
        hospital_name: string;
        hospital_id: string;
        specialty_match: number;
        bed_availability: number;
        distance_km?: number;
        success_rate?: number;
        reason: string;
      }>;
    }> => {
      return request(() =>
        api.post(`ai/referral-recommendation/${patientId}`, {
          required_specialty: specialty || '',
        })
      );
    },
    [api, request]
  );

  const getAnalysisHistory = useCallback(
    async (
      patientId: string,
      limit?: number,
      offset?: number
    ): Promise<{
      patient_id: string;
      analyses: AnalysisHistoryItem[];
      total: number;
      limit: number;
      offset: number;
    }> => {
      return request(() => {
        const params = new URLSearchParams();
        if (limit != null) params.append('limit', String(limit));
        if (offset != null) params.append('offset', String(offset));
        const path = `ai/analysis-history/${patientId}${params.toString() ? `?${params}` : ''}`;
        return api.get(path);
      });
    },
    [api, request]
  );

  return {
    analyzePatient,
    predictRisk,
    getCDS,
    triagePatient,
    findSimilarPatients,
    getReferralRecommendations,
    getAnalysisHistory,
    loading,
    error,
  };
}
