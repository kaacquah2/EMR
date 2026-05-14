import React from "react";
import { DrugStock } from "@/hooks/use-pharmacy";
import {
  AlertTriangle,
  Calendar,
  Package,
  TrendingDown,
} from "lucide-react";

interface StockTableProps {
  stock: DrugStock[];
  loading: boolean;
  onAdjust?: (stockId: string) => void;
}

export function StockTable({
  stock,
  loading,
  onAdjust,
}: StockTableProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading drug stock...</p>
        </div>
      </div>
    );
  }

  if (stock.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 bg-gray-50 rounded-lg">
        <Package className="h-12 w-12 text-gray-400 mb-4" />
        <p className="text-gray-600 font-medium">No drug stock found</p>
        <p className="text-gray-500 text-sm mt-1">
          Add drugs to inventory to get started
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse">
        <thead>
          <tr className="border-b-2 border-gray-300 bg-gray-100">
            <th className="px-4 py-3 text-left font-semibold text-gray-700">
              Drug Name
            </th>
            <th className="px-4 py-3 text-left font-semibold text-gray-700">
              Generic Name
            </th>
            <th className="px-4 py-3 text-left font-semibold text-gray-700">
              Batch #
            </th>
            <th className="px-4 py-3 text-center font-semibold text-gray-700">
              Quantity
            </th>
            <th className="px-4 py-3 text-center font-semibold text-gray-700">
              Reorder Level
            </th>
            <th className="px-4 py-3 text-left font-semibold text-gray-700">
              Expiry Date
            </th>
            <th className="px-4 py-3 text-center font-semibold text-gray-700">
              Status
            </th>
            <th className="px-4 py-3 text-center font-semibold text-gray-700">
              Actions
            </th>
          </tr>
        </thead>
        <tbody>
          {stock.map((item) => (
            <tr
              key={item.id}
              className={`border-b border-gray-200 ${
                item.is_low_stock
                  ? "bg-yellow-50 hover:bg-yellow-100"
                  : item.is_expired
                    ? "bg-red-50 hover:bg-red-100"
                    : "hover:bg-gray-50"
              } transition-colors`}
            >
              <td className="px-4 py-3 text-sm font-medium text-gray-900">
                {item.drug_name}
              </td>
              <td className="px-4 py-3 text-sm text-gray-600">
                {item.generic_name || "—"}
              </td>
              <td className="px-4 py-3 text-sm text-gray-600">
                {item.batch_number}
              </td>
              <td className="px-4 py-3 text-sm text-center font-semibold">
                <span
                  className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                    item.is_low_stock
                      ? "bg-yellow-100 text-yellow-800"
                      : "bg-green-100 text-green-800"
                  }`}
                >
                  {item.quantity} {item.unit}
                </span>
              </td>
              <td className="px-4 py-3 text-sm text-center text-gray-600">
                {item.reorder_level} {item.unit}
              </td>
              <td className="px-4 py-3 text-sm">
                <div className="flex items-center justify-start gap-2">
                  <Calendar className="h-4 w-4 text-gray-400" />
                  <span className={item.is_expired ? "text-red-600 font-semibold" : "text-gray-600"}>
                    {new Date(item.expiry_date).toLocaleDateString()}
                  </span>
                </div>
              </td>
              <td className="px-4 py-3 text-sm text-center">
                <div className="flex items-center justify-center gap-2">
                  {item.is_expired ? (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                      <AlertTriangle className="h-3 w-3 mr-1" />
                      Expired
                    </span>
                  ) : item.is_low_stock ? (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                      <TrendingDown className="h-3 w-3 mr-1" />
                      Low Stock
                    </span>
                  ) : item.days_until_expiry <= 7 ? (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-800">
                      Expiring Soon
                    </span>
                  ) : (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                      OK
                    </span>
                  )}
                </div>
              </td>
              <td className="px-4 py-3 text-sm text-center">
                <button
                  onClick={() => onAdjust?.(item.id)}
                  className="text-blue-600 hover:text-blue-900 font-medium text-xs px-3 py-1.5 rounded hover:bg-blue-50 transition-colors"
                >
                  Adjust
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
