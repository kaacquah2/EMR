import React from 'react';
import { AlertTriangle, CheckCircle } from 'lucide-react';
import { Tooltip } from '@/components/ui/Tooltip';

interface DisclaimerBadgeProps {
  clinical_use_approved: boolean;
  version?: string;
  className?: string;
}

export const DisclaimerBadge: React.FC<DisclaimerBadgeProps> = ({
  clinical_use_approved,
  version,
  className = '',
}) => {
  const contentText = clinical_use_approved
    ? 'This model version has been validated against real patient data and approved for clinical decision support by a super-admin.'
    : 'This prediction is based on synthetic training data and must not be used for clinical decision-making. It is for demonstration purposes only.';

  return (
    <Tooltip content={contentText}>
      <div
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition-all ${
          clinical_use_approved
            ? 'bg-green-100 text-green-700 border border-green-200'
            : 'bg-red-100 text-red-700 border border-red-200 animate-pulse'
        } ${className}`}
      >
        {clinical_use_approved ? (
          <>
            <CheckCircle className="w-3.5 h-3.5" />
            <span>Clinically Validated {version && `(${version})`}</span>
          </>
        ) : (
          <>
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>Demo only — synthetic data</span>
          </>
        )}
      </div>
    </Tooltip>
  );
};
