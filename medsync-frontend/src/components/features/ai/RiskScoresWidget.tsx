/**
 * Risk Scores Widget
 * 
 * Displays disease risk prediction scores with visual indicators.
 */

'use client';

import React from 'react';
import { AlertCircle, TrendingUp } from 'lucide-react';

interface RiskScore {
  disease: string;
  risk_score: number;
  risk_category: 'low' | 'medium' | 'high' | 'critical';
  confidence: number;
}

interface RiskScoresWidgetProps {
  predictions: Record<string, RiskScore>;
  topRiskDisease: string;
  topRiskScore: number;
  contributingFactors?: Array<{ factor: string; weight: string; value: string }>;
  isLoading?: boolean;
}

export function RiskScoresWidget({
  predictions,
  topRiskDisease,
  topRiskScore,
  contributingFactors = [],
  isLoading = false,
}: RiskScoresWidgetProps) {
  const getRiskColor = (score: number): string => {
    if (score >= 80) return 'bg-red-100 border-red-300';
    if (score >= 50) return 'bg-orange-100 border-orange-300';
    if (score >= 20) return 'bg-yellow-100 border-yellow-300';
    return 'bg-green-100 border-green-300';
  };

  const getRiskTextColor = (score: number): string => {
    if (score >= 80) return 'text-red-900';
    if (score >= 50) return 'text-orange-900';
    if (score >= 20) return 'text-yellow-900';
    return 'text-green-900';
  };

  const getScoreIcon = (score: number) => {
    if (score >= 80) return <AlertCircle className="w-5 h-5 text-red-600" />;
    if (score >= 50) return <TrendingUp className="w-5 h-5 text-orange-600" />;
    return <TrendingUp className="w-5 h-5 text-blue-600" />;
  };

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-200 rounded w-3/4"></div>
          <div className="h-4 bg-gray-200 rounded w-full"></div>
          <div className="h-4 bg-gray-200 rounded w-full"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-4">
      <h3 className="text-lg font-semibold text-gray-900">Disease Risk Predictions</h3>

      {/* Top Risk Alert */}
      {topRiskScore > 50 && (
        <div className={`rounded-lg border-2 p-4 ${getRiskColor(topRiskScore)}`}>
          <div className="flex items-start gap-3">
            {getScoreIcon(topRiskScore)}
            <div>
              <p className={`font-semibold ${getRiskTextColor(topRiskScore)}`}>
                {topRiskDisease.replace(/_/g, ' ').toUpperCase()}
              </p>
              <p className={`text-sm ${getRiskTextColor(topRiskScore)}`}>
                Risk Score: {topRiskScore.toFixed(0)}%
              </p>
            </div>
          </div>
        </div>
      )}

      {/* All Risk Scores */}
      <div className="space-y-3">
        {Object.entries(predictions).map(([disease, pred]) => (
          <div key={disease} className="space-y-1">
            <div className="flex justify-between items-center">
              <span className="text-sm font-medium text-gray-700">
                {disease.replace(/_/g, ' ').toUpperCase()}
              </span>
              <span className={`text-sm font-semibold ${getRiskTextColor(pred.risk_score)}`}>
                {pred.risk_score.toFixed(0)}%
              </span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className={`h-2 rounded-full transition-all ${
                  pred.risk_score >= 80
                    ? 'bg-red-600'
                    : pred.risk_score >= 50
                    ? 'bg-orange-600'
                    : pred.risk_score >= 20
                    ? 'bg-yellow-600'
                    : 'bg-green-600'
                }`}
                style={{ width: `${pred.risk_score}%` }}
              ></div>
            </div>
            <div className="flex justify-between text-xs text-gray-500">
              <span>Confidence: {(pred.confidence * 100).toFixed(0)}%</span>
              <span className="capitalize">{pred.risk_category}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Contributing Factors */}
      {contributingFactors.length > 0 && (
        <div className="border-t pt-4 mt-4">
          <h4 className="text-sm font-semibold text-gray-900 mb-2">Contributing Factors</h4>
          <ul className="space-y-2">
            {contributingFactors.map((factor, idx) => (
              <li key={idx} className="text-sm text-gray-700">
                <span className="font-medium">{factor.factor}</span>
                {factor.value && <span className="text-gray-600"> - {factor.value}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
