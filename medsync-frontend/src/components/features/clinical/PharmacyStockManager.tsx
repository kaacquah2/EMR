"use client";

import React, { useState } from "react";
import { 
  AlertTriangle, 
  Plus, 
  History, 
  Search, 
  Filter, 
  MoreVertical,
  ArrowUpRight,
  Calendar,
  Box
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { 
  DropdownMenu, 
  DropdownMenuContent, 
  DropdownMenuItem, 
  DropdownMenuTrigger 
} from "@/components/ui/dropdown-menu";

interface StockItem {
  id: string;
  name: string;
  category: string;
  quantity: number;
  unit: string;
  reorderLevel: number;
  expiryDate: string;
  status: "in_stock" | "low_stock" | "out_of_stock" | "near_expiry";
}

const MOCK_STOCK: StockItem[] = [
  { id: "1", name: "Paracetamol 500mg", category: "Analgesics", quantity: 2500, unit: "Tablets", reorderLevel: 500, expiryDate: "2025-12-01", status: "in_stock" },
  { id: "2", name: "Amoxicillin 250mg", category: "Antibiotics", quantity: 120, unit: "Capsules", reorderLevel: 200, expiryDate: "2024-08-15", status: "low_stock" },
  { id: "3", name: "Artemether-Lumefantrine", category: "Antimalarials", quantity: 450, unit: "Doses", reorderLevel: 100, expiryDate: "2024-06-10", status: "near_expiry" },
  { id: "4", name: "Insulin Glargine", category: "Antidiabetics", quantity: 0, unit: "Vials", reorderLevel: 10, expiryDate: "2025-01-20", status: "out_of_stock" },
  { id: "5", name: "Salbutamol Inhaler", category: "Respiratory", quantity: 85, unit: "Units", reorderLevel: 25, expiryDate: "2026-03-12", status: "in_stock" },
];

/**
 * Pharmacy Stock Manager
 * 
 * Advanced inventory management with expiry tracking and reorder logic.
 */
export function PharmacyStockManager() {
  const [searchQuery, setSearchQuery] = useState("");

  const filteredStock = MOCK_STOCK.filter(item => 
    item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    item.category.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const getStatusBadge = (status: StockItem["status"]) => {
    switch (status) {
      case "in_stock": return <Badge variant="success">In Stock</Badge>;
      case "low_stock": return <Badge variant="pending">Low Stock</Badge>;
      case "out_of_stock": return <Badge variant="critical">Stock Out</Badge>;
      case "near_expiry": return <Badge variant="pending" className="bg-orange-500 text-white">Near Expiry</Badge>;
    }
  };

  const getStockProgress = (item: StockItem) => {
    if (item.quantity === 0) return 0;
    const percentage = (item.quantity / (item.reorderLevel * 4)) * 100;
    return Math.min(percentage, 100);
  };

  return (
    <div className="space-y-6">
      {/* Inventory Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="border-slate-200 dark:border-slate-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-bold text-slate-500 uppercase tracking-widest flex items-center gap-2">
              <Box className="h-4 w-4 text-[#0EAFBE]" /> Total Line Items
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-end justify-between">
              <p className="text-3xl font-black">1,284</p>
              <Badge variant="default" className="text-emerald-500 bg-emerald-50 dark:bg-emerald-500/10 border-emerald-200 dark:border-emerald-500/20 font-bold">
                <ArrowUpRight className="h-3 w-3 mr-1" /> 12%
              </Badge>
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-200 dark:border-slate-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-bold text-slate-500 uppercase tracking-widest flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-500" /> Low/Out of Stock
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-end justify-between">
              <p className="text-3xl font-black">18</p>
              <span className="text-xs text-slate-400 font-medium">12 reorders pending</span>
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-200 dark:border-slate-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-bold text-slate-500 uppercase tracking-widest flex items-center gap-2">
              <Calendar className="h-4 w-4 text-rose-500" /> Expiry (30 Days)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-end justify-between">
              <p className="text-3xl font-black">5</p>
              <Badge variant="default" className="text-rose-500 bg-rose-50 dark:bg-rose-500/10 border-rose-200 dark:border-rose-500/20 font-bold underline cursor-pointer">
                Process Waste
              </Badge>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Stock Table */}
      <Card className="border-slate-200 dark:border-slate-800 shadow-xl overflow-hidden">
        <CardHeader className="border-b border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-900 z-10 sticky top-0">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <CardTitle className="text-xl">Pharmacy Inventory</CardTitle>
              <CardDescription>Real-time stock monitoring and replenishment control.</CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <Input 
                  placeholder="Search medication..." 
                  className="pl-10 w-[250px] bg-slate-50 dark:bg-slate-800 border-none focus-visible:ring-1 focus-visible:ring-[#0EAFBE]"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
              <Button size="sm" variant="outline" className="hidden md:flex gap-2">
                <Filter className="h-4 w-4" /> Filter
              </Button>
              <Button size="sm" className="bg-[#0EAFBE] hover:bg-[#0E8F9B] text-white gap-2">
                <Plus className="h-4 w-4" /> Add Stock
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-xs font-semibold text-slate-500 uppercase tracking-wider border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
                  <th className="px-6 py-4 text-left">Medication</th>
                  <th className="px-6 py-4 text-left">Category</th>
                  <th className="px-6 py-4 text-left">Stock Level</th>
                  <th className="px-6 py-4 text-left">Expiry</th>
                  <th className="px-6 py-4 text-left">Status</th>
                  <th className="px-6 py-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {filteredStock.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-900/50 transition-colors group">
                    <td className="px-6 py-4">
                      <div className="flex flex-col">
                        <span className="text-sm font-bold text-slate-900 dark:text-white group-hover:text-[#0EAFBE] transition-colors">{item.name}</span>
                        <span className="text-xs text-slate-500 font-mono">ID: SKU-{item.id.padStart(4, '0')}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <Badge variant="default" className="font-normal">{item.category}</Badge>
                    </td>
                    <td className="px-6 py-4">
                      <div className="space-y-2 w-32">
                        <div className="flex justify-between text-xs font-medium">
                          <span>{item.quantity} {item.unit}</span>
                          <span className={item.quantity <= item.reorderLevel ? "text-rose-500" : "text-slate-400"}>
                            min: {item.reorderLevel}
                          </span>
                        </div>
                        <Progress 
                          value={getStockProgress(item)} 
                          className={`h-1.5 ${
                            item.status === 'out_of_stock' ? 'bg-slate-200' :
                            item.status === 'low_stock' ? 'bg-amber-100' :
                            ''
                          }`} 
                        />
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex flex-col">
                        <span className={`text-sm ${item.status === 'near_expiry' ? 'text-orange-500 font-bold' : 'text-slate-600 dark:text-slate-400'}`}>
                          {item.expiryDate}
                        </span>
                        {item.status === 'near_expiry' && (
                          <span className="text-[10px] uppercase font-bold text-orange-500">Action Required</span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4">{getStatusBadge(item.status)}</td>
                    <td className="px-6 py-4 text-right">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="sm">
                            <MoreVertical className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-[180px]">
                          <DropdownMenuItem className="gap-2">
                            <ArrowUpRight className="h-4 w-4" /> Update Stock
                          </DropdownMenuItem>
                          <DropdownMenuItem className="gap-2">
                            <History className="h-4 w-4" /> Stock History
                          </DropdownMenuItem>
                          <DropdownMenuItem className="gap-2 text-rose-500">
                            <AlertTriangle className="h-4 w-4" /> Mark as Damaged
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
