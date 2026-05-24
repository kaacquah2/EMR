"use client";

import React, { useState } from "react";
import { 
  Users, 
  ArrowRightCircle,
  FileText,
  AlertCircle,
  CheckCircle2,
  Lock,
  History
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardFooter, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";

interface SbarHandoverProps {
  patient: {
    id: string;
    name: string;
    mrn: string;
    ward: string;
    bed: string;
  };
  fromUser: {
    name: string;
    role: string;
  };
}

/**
 * SBAR Handover Report
 * 
 * Situation, Background, Assessment, Recommendation.
 * Compliant with WHO Patient Safety Standards.
 */
export function SbarHandoverReport({ patient, fromUser }: SbarHandoverProps) {
  const [formData, setFormData] = useState({
    situation: "",
    background: "",
    assessment: "",
    recommendation: "",
    isUrgent: false,
    nextReviewAt: "",
  });

  const [step, setStep] = useState(0); // 0: S, 1: B, 2: A, 3: R, 4: Review

  const steps = [
    { label: "Situation", color: "bg-rose-500", icon: <AlertCircle className="h-4 w-4" /> },
    { label: "Background", color: "bg-amber-500", icon: <History className="h-4 w-4" /> },
    { label: "Assessment", color: "bg-blue-500", icon: <FileText className="h-4 w-4" /> },
    { label: "Recommendation", color: "bg-emerald-500", icon: <ArrowRightCircle className="h-4 w-4" /> }
  ];

  const handleNext = () => setStep(prev => Math.min(prev + 1, 4));
  const handleBack = () => setStep(prev => Math.max(prev - 1, 0));

  const progress = (step / 4) * 100;

  return (
    <Card className="max-w-2xl mx-auto border-slate-200 dark:border-slate-800 shadow-2xl overflow-hidden">
      <CardHeader className="bg-slate-50/50 dark:bg-slate-900/50 border-b border-slate-100 dark:border-slate-800 p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <div className="p-2 bg-[#0EAFBE]/10 rounded-lg">
              <Users className="h-5 w-5 text-[#0EAFBE]" />
            </div>
            <div>
              <CardTitle className="text-xl">Clinical Handover (SBAR)</CardTitle>
              <CardDescription>Shift transition for {patient.name}</CardDescription>
            </div>
          </div>
          <Badge variant={formData.isUrgent ? "critical" : "default"} className="animate-pulse">
            {formData.isUrgent ? "URGENT" : "ROUTINE"}
          </Badge>
        </div>
        
        <div className="space-y-4">
          <div className="flex justify-between items-center text-xs font-bold text-slate-400 uppercase tracking-widest">
            <span>{step < 4 ? `Step ${step + 1}: ${steps[step].label}` : "Review & Submit"}</span>
            <span>{Math.round(progress)}% Complete</span>
          </div>
          <Progress value={progress} className="h-1.5 bg-slate-100 dark:bg-slate-800" />
        </div>
      </CardHeader>

      <CardContent className="p-8 min-h-[350px] flex flex-col">
        {step === 0 && (
          <div className="space-y-4 animate-in fade-in slide-in-from-right-4 duration-300">
            <div className="flex items-center gap-2 text-rose-500">
              <AlertCircle className="h-5 w-5" />
              <h3 className="font-black text-lg uppercase tracking-tight">Situation</h3>
            </div>
            <p className="text-sm text-slate-500">Briefly state the patient name, age, and current status/primary problem.</p>
            <Textarea 
              className="flex-1 min-h-[180px] text-lg leading-relaxed focus-visible:ring-rose-500 border-rose-100 bg-rose-50/10"
              placeholder="e.g. Pt is Kojo Mensah, post-op day 1 from appendectomy. Currently reporting increasing abdominal pain and spiking fever of 39.2C..."
              value={formData.situation}
              onChange={(e) => setFormData({...formData, situation: e.target.value})}
            />
          </div>
        )}

        {step === 1 && (
          <div className="space-y-4 animate-in fade-in slide-in-from-right-4 duration-300">
            <div className="flex items-center gap-2 text-amber-500">
              <History className="h-5 w-5" />
              <h3 className="font-black text-lg uppercase tracking-tight">Background</h3>
            </div>
            <p className="text-sm text-slate-500">Admission diagnosis, significant history, relevant meds, and allergies.</p>
            <Textarea 
              className="flex-1 min-h-[180px] text-lg leading-relaxed focus-visible:ring-amber-500 border-amber-100 bg-amber-50/10"
              placeholder="e.g. Admitted 2 days ago for acute appendicitis. History of HTN and asthma. Allergic to Penicillin. Surgery was uncomplicated..."
              value={formData.background}
              onChange={(e) => setFormData({...formData, background: e.target.value})}
            />
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4 animate-in fade-in slide-in-from-right-4 duration-300">
            <div className="flex items-center gap-2 text-blue-500">
              <FileText className="h-5 w-5" />
              <h3 className="font-black text-lg uppercase tracking-tight">Assessment</h3>
            </div>
            <p className="text-sm text-slate-500">Most recent vitals, current physical findings, and your clinical impression.</p>
            <Textarea 
              className="flex-1 min-h-[180px] text-lg leading-relaxed focus-visible:ring-blue-500 border-blue-100 bg-blue-50/10"
              placeholder="e.g. BP 110/70, P 110, R 24. Abdomen is board-like and tender. Lab results show rising WBC count. Concerned for post-op infection or leak..."
              value={formData.assessment}
              onChange={(e) => setFormData({...formData, assessment: e.target.value})}
            />
          </div>
        )}

        {step === 3 && (
          <div className="space-y-4 animate-in fade-in slide-in-from-right-4 duration-300">
            <div className="flex items-center gap-2 text-emerald-500">
              <ArrowRightCircle className="h-5 w-5" />
              <h3 className="font-black text-lg uppercase tracking-tight">Recommendation</h3>
            </div>
            <p className="text-sm text-slate-500">What do you think should happen next? Tests, meds, or immediate review.</p>
            <Textarea 
              className="flex-1 min-h-[180px] text-lg leading-relaxed focus-visible:ring-emerald-500 border-emerald-100 bg-emerald-50/10"
              placeholder="e.g. Needs immediate Surgical Review. Stat Abdominal Ultrasound ordered. Start IV hydration and monitor vitals q1h..."
              value={formData.recommendation}
              onChange={(e) => setFormData({...formData, recommendation: e.target.value})}
            />
          </div>
        )}

        {step === 4 && (
          <div className="space-y-6 animate-in zoom-in-95 duration-300">
            <div className="text-center pb-4 border-b border-slate-100">
              <CheckCircle2 className="h-12 w-12 text-[#0EAFBE] mx-auto mb-2" />
              <h3 className="text-xl font-black">Verify Handover Report</h3>
              <p className="text-sm text-slate-500">Confirm all details before final shift submission.</p>
            </div>
            
            <div className="grid grid-cols-4 gap-2">
              {steps.map((s, i) => (
                <div key={i} className="flex flex-col items-center gap-1">
                  <div className={`h-1.5 w-full rounded-full ${s.color}`} />
                  <span className="text-[10px] font-bold uppercase text-slate-400">{s.label[0]}</span>
                </div>
              ))}
            </div>

            <div className="space-y-3 p-4 bg-slate-50 dark:bg-slate-900 rounded-xl border border-slate-100 dark:border-slate-800">
              <div className="flex justify-between items-center">
                <span className="text-xs font-bold text-slate-400 uppercase tracking-tighter">Reporting Clinician</span>
                <span className="text-sm font-bold">{fromUser.name} ({fromUser.role})</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-xs font-bold text-slate-400 uppercase tracking-tighter">Patient Context</span>
                <span className="text-sm font-mono">{patient.ward} / Bed {patient.bed}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-xs font-bold text-slate-400 uppercase tracking-tighter">Report Type</span>
                <Badge variant={formData.isUrgent ? "critical" : "default"}>
                  {formData.isUrgent ? "High Priority" : "Standard Shift"}
                </Badge>
              </div>
            </div>
          </div>
        )}
      </CardContent>

      <CardFooter className="bg-slate-50/50 dark:bg-slate-900/50 border-t border-slate-100 dark:border-slate-800 p-6 flex justify-between">
        <Button 
          variant="ghost" 
          onClick={handleBack}
          disabled={step === 0}
        >
          Back
        </Button>
        
        <div className="flex gap-2">
          {step === 0 && (
            <Button 
              variant="outline" 
              onClick={() => setFormData({...formData, isUrgent: !formData.isUrgent})}
              className={formData.isUrgent ? "border-rose-500 text-rose-500 bg-rose-50" : ""}
            >
              Mark Urgent
            </Button>
          )}
          
          {step < 4 ? (
            <Button 
              className="bg-[#0EAFBE] hover:bg-[#0E8F9B] text-white min-w-[120px]"
              onClick={handleNext}
            >
              Continue <ArrowRightCircle className="ml-2 h-4 w-4" />
            </Button>
          ) : (
            <Button 
              className="bg-[#0EAFBE] hover:bg-[#0E8F9B] text-white min-w-[150px]"
            >
              <Lock className="mr-2 h-4 w-4" /> Submit & Lock
            </Button>
          )}
        </div>
      </CardFooter>
    </Card>
  );
}
