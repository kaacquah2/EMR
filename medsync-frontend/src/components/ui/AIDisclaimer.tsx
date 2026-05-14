import React from "react";
import { AlertCircle } from "lucide-react";

export function AIDisclaimer() {
  return (
    <div className="mb-6 flex items-center gap-3 rounded-lg border border-amber-200 bg-amber-50 p-4 text-amber-800 shadow-sm dark:border-amber-900/30 dark:bg-amber-950/20 dark:text-amber-400">
      <AlertCircle className="h-5 w-5 flex-shrink-0" />
      <p className="text-sm font-medium leading-relaxed">
        AI predictions are for demonstration only and have not been validated on clinical data. 
        Always verify insights with professional medical judgment before making clinical decisions.
      </p>
    </div>
  );
}
