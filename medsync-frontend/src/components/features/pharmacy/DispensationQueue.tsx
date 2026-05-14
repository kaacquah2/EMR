import React from "react";
import { Dispensation } from "@/hooks/use-pharmacy";
import {
  Clock,
  User,
  Package,
} from "lucide-react";

interface DispensationQueueProps {
  dispensations: Dispensation[];
  loading: boolean;
  onDispense?: (dispensationId: string) => void;
}

export function DispensationQueue({
  dispensations,
  loading,
  onDispense,
}: DispensationQueueProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading dispensations...</p>
        </div>
      </div>
    );
  }

  if (dispensations.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 bg-gray-50 rounded-lg">
        <Package className="h-12 w-12 text-gray-400 mb-4" />
        <p className="text-gray-600 font-medium">No dispensations</p>
        <p className="text-gray-500 text-sm mt-1">
          All prescriptions have been dispensed
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">
          Dispensation History
        </h3>
        <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800">
          {dispensations.length} items
        </span>
      </div>

      <div className="grid gap-4 max-h-96 overflow-y-auto">
        {dispensations.map((item) => (
          <div
            key={item.id}
            className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow"
          >
            <div className="flex items-start justify-between mb-3">
              <div className="flex-1">
                <h4 className="font-semibold text-gray-900 text-sm">
                  {item.drug_stock_name}
                </h4>
                <p className="text-xs text-gray-500 mt-1">
                  Batch: <span className="font-mono text-gray-600">{item.id.substring(0, 8)}</span>
                </p>
              </div>
              <div className="text-right">
                <div className="text-lg font-bold text-blue-600">
                  {item.quantity_dispensed}
                </div>
                <p className="text-xs text-gray-500">units</p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs mb-4">
              <div className="flex items-center gap-2 text-gray-600">
                <User className="h-3.5 w-3.5 text-gray-400" />
                <span>{item.dispensed_by_name || "Unknown"}</span>
              </div>
              <div className="flex items-center gap-2 text-gray-600">
                <Clock className="h-3.5 w-3.5 text-gray-400" />
                <span>
                  {new Date(item.dispensed_at).toLocaleDateString()} 
                  {" "}
                  {new Date(item.dispensed_at).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
              </div>
            </div>

            {item.batch_notes && (
              <div className="bg-gray-50 rounded p-2 mb-3">
                <p className="text-xs text-gray-700">
                  <strong>Notes:</strong> {item.batch_notes}
                </p>
              </div>
            )}

            <button
              onClick={() => onDispense?.(item.id)}
              className="w-full text-xs bg-green-600 hover:bg-green-700 text-white py-2 px-3 rounded transition-colors font-medium"
            >
              Mark Complete
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
