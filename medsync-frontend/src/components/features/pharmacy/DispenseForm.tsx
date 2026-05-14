import React, { useState } from "react";
import { Plus, Loader2 } from "lucide-react";

interface DispenseFormProps {
  onSubmit: (data: {
    quantity_change: number;
    reason: string;
    movement_type: string;
  }) => Promise<void>;
  loading?: boolean;
  error?: string | null;
}

export function DispenseForm({
  onSubmit,
  loading = false,
  error = null,
}: DispenseFormProps) {
  const [quantity, setQuantity] = useState<string>("");
  const [reason, setReason] = useState<string>("");
  const [movementType, setMovementType] = useState<string>("adjustment");
  const [formError, setFormError] = useState<string | null>(null);
  const [success, setSuccess] = useState<boolean>(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setSuccess(false);

    // Validation
    if (!quantity || isNaN(Number(quantity))) {
      setFormError("Please enter a valid quantity");
      return;
    }

    if (!reason.trim()) {
      setFormError("Please provide a reason");
      return;
    }

    try {
      await onSubmit({
        quantity_change: -Math.abs(Number(quantity)), // Negative for removal
        reason,
        movement_type: movementType,
      });
      setSuccess(true);
      setQuantity("");
      setReason("");
      setMovementType("adjustment");
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Failed to adjust stock");
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-white rounded-lg shadow-md p-6 space-y-4"
    >
      <h3 className="text-lg font-semibold text-gray-900">Adjust Stock</h3>

      {(error || formError) && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <p className="text-red-700 text-sm">{error || formError}</p>
        </div>
      )}

      {success && (
        <div className="bg-green-50 border border-green-200 rounded-md p-4">
          <p className="text-green-700 text-sm font-medium">Stock adjusted successfully!</p>
        </div>
      )}

      <div>
        <label htmlFor="quantity" className="block text-sm font-medium text-gray-700 mb-1">
          Quantity <span className="text-red-500">*</span>
        </label>
        <input
          type="number"
          id="quantity"
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
          placeholder="Enter quantity to deduct"
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          min="0"
          required
        />
      </div>

      <div>
        <label htmlFor="movementType" className="block text-sm font-medium text-gray-700 mb-1">
          Adjustment Type <span className="text-red-500">*</span>
        </label>
        <select
          id="movementType"
          value={movementType}
          onChange={(e) => setMovementType(e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="adjustment">General Adjustment</option>
          <option value="damaged">Damaged Units</option>
          <option value="expired">Expired Stock</option>
          <option value="dispensed">Dispensed</option>
        </select>
      </div>

      <div>
        <label htmlFor="reason" className="block text-sm font-medium text-gray-700 mb-1">
          Reason <span className="text-red-500">*</span>
        </label>
        <textarea
          id="reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Enter reason for adjustment (e.g., 'Damaged in storage', 'Inventory count correction')"
          rows={3}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          required
        />
      </div>

      <button
        type="submit"
        disabled={loading}
        className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-medium py-2.5 px-4 rounded-md transition-colors flex items-center justify-center gap-2"
      >
        {loading ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            Processing...
          </>
        ) : (
          <>
            <Plus className="h-4 w-4" />
            Adjust Stock
          </>
        )}
      </button>
    </form>
  );
}
