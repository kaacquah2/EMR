"use client";

import React, { useEffect, useState } from "react";
import {
  useDrugStock,
  useDispensations,
  usePharmacyReports,
} from "@/hooks/use-pharmacy";
import { StockTable } from "./StockTable";
import { DispenseForm } from "./DispenseForm";
import { DispensationQueue } from "./DispensationQueue";
import {
  AlertTriangle,
  TrendingDown,
  Calendar,
  RefreshCw,
  Plus,
  Eye,
} from "lucide-react";

export function PharmacyDashboard() {
  const drugStock = useDrugStock();
  const dispensations = useDispensations();
  const reports = usePharmacyReports();

  const [selectedStockId, setSelectedStockId] = useState<string | null>(null);
  const [showAdjustForm, setShowAdjustForm] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState<"stock" | "reports" | "history">(
    "stock"
  );

  const { getStock } = drugStock;
  const { getDispensations } = dispensations;
  const { getLowStockReport, getExpiringReport } = reports;

  // Load initial data
  useEffect(() => {
    const loadData = async () => {
      try {
        await Promise.all([
          getStock(),
          getDispensations(),
          getLowStockReport(),
          getExpiringReport(),
        ]);
      } catch (err) {
        console.error("Error loading pharmacy data:", err);
      }
    };

    loadData();
  }, [getStock, getDispensations, getLowStockReport, getExpiringReport]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await Promise.all([
        drugStock.getStock(),
        dispensations.getDispensations(),
        reports.getLowStockReport(),
        reports.getExpiringReport(),
      ]);
    } catch (err) {
      console.error("Error refreshing data:", err);
    } finally {
      setRefreshing(false);
    }
  };

  const handleAdjustStock = (stockId: string) => {
    setSelectedStockId(stockId);
    setShowAdjustForm(true);
  };

  const handleAdjustSubmit = async (data: {
    quantity_change: number;
    reason: string;
    movement_type: string;
  }) => {
    if (!selectedStockId) return;

    try {
      await drugStock.adjustStock(selectedStockId, data);
      setShowAdjustForm(false);
      setSelectedStockId(null);
      // Refresh all data after adjustment
      await handleRefresh();
    } catch (err) {
      console.error("Error adjusting stock:", err);
    }
  };

  const lowStockCount = drugStock.stock.filter((s) => s.is_low_stock).length;
  const expiringCount = reports.expiringItems.filter(
    (s) => s.days_to_expiry <= 30
  ).length;
  const criticalCount = reports.expiringItems.filter(
    (s) => s.is_critical
  ).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">
            Pharmacy Inventory
          </h1>
          <p className="text-gray-600 mt-1">
            Manage drug stock, monitor inventory levels, and process dispensations
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white px-4 py-2 rounded-lg transition-colors"
        >
          <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow p-6 border-l-4 border-blue-500">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm font-medium">Total Items</p>
              <p className="text-3xl font-bold text-gray-900 mt-2">
                {drugStock.stock.length}
              </p>
            </div>
            <div className="bg-blue-100 rounded-full p-3">
              <Plus className="h-6 w-6 text-blue-600" />
            </div>
          </div>
        </div>

        <div className={`bg-white rounded-lg shadow p-6 border-l-4 ${lowStockCount > 0 ? "border-yellow-500" : "border-green-500"}`}>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm font-medium">Low Stock</p>
              <p className={`text-3xl font-bold mt-2 ${lowStockCount > 0 ? "text-yellow-600" : "text-green-600"}`}>
                {lowStockCount}
              </p>
            </div>
            <div className={`rounded-full p-3 ${lowStockCount > 0 ? "bg-yellow-100" : "bg-green-100"}`}>
              <TrendingDown className={`h-6 w-6 ${lowStockCount > 0 ? "text-yellow-600" : "text-green-600"}`} />
            </div>
          </div>
        </div>

        <div className={`bg-white rounded-lg shadow p-6 border-l-4 ${expiringCount > 0 ? "border-orange-500" : "border-green-500"}`}>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm font-medium">Expiring (30d)</p>
              <p className={`text-3xl font-bold mt-2 ${expiringCount > 0 ? "text-orange-600" : "text-green-600"}`}>
                {expiringCount}
              </p>
            </div>
            <div className={`rounded-full p-3 ${expiringCount > 0 ? "bg-orange-100" : "bg-green-100"}`}>
              <Calendar className={`h-6 w-6 ${expiringCount > 0 ? "text-orange-600" : "text-green-600"}`} />
            </div>
          </div>
        </div>

        <div className={`bg-white rounded-lg shadow p-6 border-l-4 ${criticalCount > 0 ? "border-red-500" : "border-green-500"}`}>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm font-medium">Critical (7d)</p>
              <p className={`text-3xl font-bold mt-2 ${criticalCount > 0 ? "text-red-600" : "text-green-600"}`}>
                {criticalCount}
              </p>
            </div>
            <div className={`rounded-full p-3 ${criticalCount > 0 ? "bg-red-100" : "bg-green-100"}`}>
              <AlertTriangle className={`h-6 w-6 ${criticalCount > 0 ? "text-red-600" : "text-green-600"}`} />
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white rounded-lg shadow">
        <div className="flex border-b border-gray-200">
          <button
            onClick={() => setActiveTab("stock")}
            className={`px-6 py-4 font-medium transition-colors ${
              activeTab === "stock"
                ? "text-blue-600 border-b-2 border-blue-600"
                : "text-gray-600 hover:text-gray-900"
            }`}
          >
            <div className="flex items-center gap-2">
              <Eye className="h-4 w-4" />
              Stock Inventory
            </div>
          </button>
          <button
            onClick={() => setActiveTab("reports")}
            className={`px-6 py-4 font-medium transition-colors ${
              activeTab === "reports"
                ? "text-blue-600 border-b-2 border-blue-600"
                : "text-gray-600 hover:text-gray-900"
            }`}
          >
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" />
              Reports
            </div>
          </button>
          <button
            onClick={() => setActiveTab("history")}
            className={`px-6 py-4 font-medium transition-colors ${
              activeTab === "history"
                ? "text-blue-600 border-b-2 border-blue-600"
                : "text-gray-600 hover:text-gray-900"
            }`}
          >
            <div className="flex items-center gap-2">
              <Calendar className="h-4 w-4" />
              History
            </div>
          </button>
        </div>

        <div className="p-6">
          {activeTab === "stock" && (
            <div className="space-y-6">
              <StockTable
                stock={drugStock.stock}
                loading={drugStock.loading}
                onAdjust={handleAdjustStock}
              />
              {showAdjustForm && selectedStockId && (
                <div className="mt-6">
                  <DispenseForm
                    onSubmit={handleAdjustSubmit}
                    loading={drugStock.loading}
                    error={drugStock.error}
                  />
                </div>
              )}
            </div>
          )}

          {activeTab === "reports" && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Low Stock Report */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold text-gray-900">
                    Low Stock Items
                  </h3>
                  <span className="text-sm text-gray-600">
                    {reports.lowStockItems.length} items
                  </span>
                </div>
                <div className="space-y-3 max-h-96 overflow-y-auto">
                  {reports.lowStockItems.length === 0 ? (
                    <p className="text-gray-600 text-sm py-8 text-center">
                      No low stock items
                    </p>
                  ) : (
                    reports.lowStockItems.map((item) => (
                      <div
                        key={item.id}
                        className="bg-yellow-50 border border-yellow-200 rounded-lg p-4"
                      >
                        <div className="flex items-start justify-between">
                          <div>
                            <h4 className="font-semibold text-gray-900 text-sm">
                              {item.drug_name}
                            </h4>
                            <p className="text-xs text-gray-600 mt-1">
                              Batch: {item.batch_number}
                            </p>
                          </div>
                          <div className="text-right">
                            <p className="text-sm font-semibold text-yellow-600">
                              {item.shortage} short
                            </p>
                            <p className="text-xs text-gray-600 mt-1">
                              Have: {item.current_quantity}, Need:{" "}
                              {item.reorder_level}
                            </p>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Expiring Report */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold text-gray-900">
                    Expiring Soon
                  </h3>
                  <span className="text-sm text-gray-600">
                    {reports.expiringItems.length} items
                  </span>
                </div>
                <div className="space-y-3 max-h-96 overflow-y-auto">
                  {reports.expiringItems.length === 0 ? (
                    <p className="text-gray-600 text-sm py-8 text-center">
                      No expiring items
                    </p>
                  ) : (
                    reports.expiringItems.map((item) => (
                      <div
                        key={item.id}
                        className={`rounded-lg p-4 border ${
                          item.is_critical
                            ? "bg-red-50 border-red-200"
                            : "bg-orange-50 border-orange-200"
                        }`}
                      >
                        <div className="flex items-start justify-between">
                          <div>
                            <h4 className="font-semibold text-gray-900 text-sm">
                              {item.drug_name}
                            </h4>
                            <p className="text-xs text-gray-600 mt-1">
                              Batch: {item.batch_number}
                            </p>
                          </div>
                          <div className="text-right">
                            <p
                              className={`text-sm font-semibold ${
                                item.is_critical
                                  ? "text-red-600"
                                  : "text-orange-600"
                              }`}
                            >
                              {item.days_to_expiry}d left
                            </p>
                            <p className="text-xs text-gray-600 mt-1">
                              {new Date(item.expiry_date).toLocaleDateString()}
                            </p>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          )}

          {activeTab === "history" && (
            <DispensationQueue
              dispensations={dispensations.dispensations}
              loading={dispensations.loading}
            />
          )}
        </div>
      </div>
    </div>
  );
}
