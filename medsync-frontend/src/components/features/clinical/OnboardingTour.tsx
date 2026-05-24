"use client";

import React, { useState, useEffect } from "react";
import { 
  X, 
  ChevronRight, 
  ChevronLeft, 
  Sparkles, 
  LayoutDashboard, 
  Users, 
  Activity, 
  ShieldCheck,
  CheckCircle2,
  Stethoscope
} from "lucide-react";
import { 
  Dialog, 
  DialogContent, 
  DialogTitle, 
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface TourStep {
  title: string;
  description: string;
  icon: React.ReactNode;
  color: string;
  image?: string;
}

const TOUR_STEPS: TourStep[] = [
  {
    title: "Welcome to MedSync",
    description: "The next-generation Health Intelligence platform designed for Ghana's clinical excellence. Let's take a quick look at your new workspace.",
    icon: <Sparkles />,
    color: "bg-[#0EAFBE]",
  },
  {
    title: "Intelligence Dashboard",
    description: "Your mission control. Track patient flow, triage status, and clinical alerts in real-time. Everything you need is just a glance away.",
    icon: <LayoutDashboard />,
    color: "bg-indigo-500",
  },
  {
    title: "Unified Patient Records",
    description: "A single, encrypted timeline for every patient. From lab results to nursing notes, access the full clinical context instantly.",
    icon: <Users />,
    color: "bg-emerald-500",
  },
  {
    title: "Clinical Decision Support",
    description: "Our AI-powered engine monitors vitals and drug interactions to keep patients safe. Look for the pulse icon for automated insights.",
    icon: <Activity />,
    color: "bg-rose-500",
  },
  {
    title: "Compliance & Reporting",
    description: "Automatic NHIS claim generation and GHS-compliant reporting tools help you focus on care, not paperwork.",
    icon: <ShieldCheck />,
    color: "bg-amber-500",
  },
  {
    title: "You're All Set!",
    description: "We're here to help you deliver the best care possible. You can always find help in the documentation or by contacting support.",
    icon: <Stethoscope />,
    color: "bg-[#0EAFBE]",
  }
];

/**
 * Onboarding Tour Component
 * 
 * Interactive guide for first-time users.
 */
export function OnboardingTour() {
  const [open, setOpen] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);

  useEffect(() => {
    const hasSeenTour = localStorage.getItem("medsync_tour_seen");
    if (!hasSeenTour) {
      const timer = setTimeout(() => setOpen(true), 1500);
      return () => clearTimeout(timer);
    }
  }, []);

  const handleNext = () => {
    if (currentStep < TOUR_STEPS.length - 1) {
      setCurrentStep(prev => prev + 1);
    } else {
      finishTour();
    }
  };

  const handleBack = () => {
    setCurrentStep(prev => Math.max(0, prev - 1));
  };

  const finishTour = () => {
    localStorage.setItem("medsync_tour_seen", "true");
    setOpen(false);
  };

  const step = TOUR_STEPS[currentStep];

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="sm:max-w-[500px] p-0 overflow-hidden border-none shadow-2xl">
        <div className={`h-32 ${step.color} flex items-center justify-center relative transition-colors duration-500`}>
          <div className="bg-white/20 p-4 rounded-2xl backdrop-blur-md border border-white/30 animate-in zoom-in-50 duration-500">
            {step.icon && React.isValidElement(step.icon) && React.cloneElement(step.icon as React.ReactElement<{ className?: string }>, { 
              className: "h-10 w-10 text-white" 
            })}
          </div>
          <Button 
            variant="ghost" 
            size="icon" 
            className="absolute top-2 right-2 text-white hover:bg-white/20"
            onClick={finishTour}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="p-8 space-y-6">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Badge variant="default" className="text-[10px] font-black uppercase tracking-widest border-slate-200">
                MEDSYNC TOUR
              </Badge>
              <div className="flex gap-1">
                {TOUR_STEPS.map((_, i) => (
                  <div 
                    key={i} 
                    className={`h-1 rounded-full transition-all duration-300 ${
                      i === currentStep ? `w-4 ${step.color}` : "w-1 bg-slate-200"
                    }`} 
                  />
                ))}
              </div>
            </div>
            <DialogTitle className="text-2xl font-black text-slate-900 dark:text-white">
              {step.title}
            </DialogTitle>
            <DialogDescription className="text-lg leading-relaxed text-slate-600 dark:text-slate-400">
              {step.description}
            </DialogDescription>
          </div>

          <div className="pt-4 flex items-center justify-between">
            <Button 
              variant="ghost" 
              onClick={handleBack}
              disabled={currentStep === 0}
              className="text-slate-500"
            >
              <ChevronLeft className="mr-2 h-4 w-4" /> Previous
            </Button>
            
            <Button 
              className={`${step.color} hover:brightness-90 text-white px-8 min-w-[140px] shadow-lg shadow-${step.color.split('-')[1]}-500/20`}
              onClick={handleNext}
            >
              {currentStep === TOUR_STEPS.length - 1 ? (
                <span className="flex items-center gap-2">Get Started <CheckCircle2 className="h-4 w-4" /></span>
              ) : (
                <span className="flex items-center gap-2">Next Step <ChevronRight className="h-4 w-4" /></span>
              )}
            </Button>
          </div>
        </div>

        <div className="bg-slate-50 dark:bg-slate-900 p-4 border-t border-slate-100 dark:border-slate-800 text-center">
          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
            Press ESC to skip or click X
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
}
