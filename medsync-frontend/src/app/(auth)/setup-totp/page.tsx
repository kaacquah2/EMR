"use client";

import React, { useState, useEffect, Suspense, useCallback } from "react";
import { useRouter } from "next/navigation";
import { QRCodeSVG } from "qrcode.react";
import { 
  ShieldCheck, 
  QrCode, 
  Key, 
  ChevronLeft, 
  Copy,
  Lock
} from "lucide-react";
import { useTotp, TotpSetupResponse } from "@/hooks/use-totp";
import { useToast } from "@/lib/toast-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AuthLayout } from "@/components/auth/AuthLayout";
import { TotpCountdownRing } from "@/components/ui/TotpCountdownRing";
import { useAuth } from "@/lib/auth-context";

const SetupTotpContent = () => {
  const router = useRouter();
  const { user } = useAuth();
  const { loading, setupTotp, getActivateSetup } = useTotp();
  const toast = useToast();
  
  const [step, setStep] = useState(1); // Step 1 is QR, Step 2 is Verify
  const [setupData, setSetupData] = useState<TotpSetupResponse | null>(null);
  const [mfaCode, setMfaCode] = useState("");

  const loadSetup = useCallback(async () => {
    const data = await getActivateSetup("CURRENT_SESSION"); 
    if (data) {
      setSetupData(data);
    } else {
      toast.error("Could not initialize setup. Please contact support.");
    }
  }, [getActivateSetup, toast]);
  
  useEffect(() => {
    void (async () => {
      await loadSetup();
    })();
  }, [loadSetup]);

  const handleNext = () => setStep(prev => prev + 1);
  const handleBack = () => setStep(prev => prev - 1);

  const handleCompleteSetup = async () => {
    if (mfaCode.length !== 6) {
      toast.error("Please enter the 6-digit verification code");
      return;
    }

    const success = await setupTotp(mfaCode);
    if (success) {
      router.push("/dashboard");
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success("Secret copied to clipboard");
  };

  if (!setupData) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-teal-600"></div>
        <p className="mt-4 text-gray-500 font-medium">Initializing security protocol...</p>
      </div>
    );
  }

  return (
    <div className="w-full max-w-md mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      {/* Locked Account Warning if applicable */}
      {user?.totp_grace_period_expires && new Date(user.totp_grace_period_expires) <= new Date() && (
        <div className="bg-red-50 p-4 rounded-2xl border border-red-100 flex gap-3 text-red-800 animate-pulse">
          <Lock className="w-6 h-6 shrink-0" />
          <div className="space-y-1">
            <div className="font-bold text-sm">Access Suspended</div>
            <p className="text-xs">Your grace period has expired. Complete setup now to regain access.</p>
          </div>
        </div>
      )}

      {/* Progress Indicator */}
      <div className="flex items-center justify-center gap-3 mb-8">
        {[1, 2].map((s) => (
          <div 
            key={s}
            className={`h-2 rounded-full transition-all duration-300 ${
              step === s ? "w-8 bg-teal-600" : s < step ? "w-4 bg-teal-200" : "w-2 bg-gray-200"
            }`}
          />
        ))}
      </div>

      {/* Step 1: Scan QR (corresponds to Wizard Step 2) */}
      {step === 1 && (
        <div className="space-y-6">
          <div className="text-center space-y-2">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-teal-50 text-teal-600 rounded-2xl mb-2">
              <QrCode className="w-8 h-8" />
            </div>
            <h1 className="text-2xl font-bold text-navy-900">Secure your account</h1>
            <p className="text-gray-500 text-sm">
              Scan this code with your authenticator app to complete your security setup.
            </p>
          </div>

          <div className="flex flex-col items-center gap-6">
            <div className="p-6 bg-white rounded-3xl shadow-xl shadow-gray-200 border border-gray-50 relative group">
              <QRCodeSVG 
                value={setupData.provisioning_url} 
                size={200} 
                includeMargin={false}
              />
            </div>

            <div className="text-center">
              <div className="text-sm font-bold text-navy-900">MedSync Identity</div>
              <div className="text-xs text-gray-400">Authenticator Setup</div>
            </div>

            <details className="w-full group">
              <summary className="text-sm font-medium text-teal-600 hover:text-teal-700 cursor-pointer text-center list-none flex items-center justify-center gap-1 select-none">
                <Key className="w-4 h-4" />
                Manual setup code
              </summary>
              <div className="mt-4 p-4 bg-gray-50 rounded-xl border border-dashed border-gray-200 space-y-3">
                <div className="flex items-center gap-2 bg-white p-3 rounded-lg border border-gray-100 font-mono text-sm tracking-widest text-navy-900 break-all">
                  {setupData.totp_secret}
                  <button 
                    onClick={() => copyToClipboard(setupData.totp_secret)}
                    className="ml-auto p-1 hover:bg-gray-50 rounded transition-colors"
                  >
                    <Copy className="w-4 h-4 text-gray-400" />
                  </button>
                </div>
              </div>
            </details>
          </div>

          <div className="pt-4">
            <Button 
              onClick={handleNext}
              className="w-full bg-teal-600 hover:bg-teal-700 text-white py-6 text-base font-bold shadow-lg shadow-teal-600/20"
            >
              I&apos;ve scanned it → Next
            </Button>
          </div>
        </div>
      )}

      {/* Step 2: Verify (corresponds to Wizard Step 3) */}
      {step === 2 && (
        <div className="space-y-8 animate-in fade-in slide-in-from-right-4 duration-300">
          <div className="text-center space-y-2">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-teal-50 text-teal-600 rounded-2xl mb-2">
              <ShieldCheck className="w-8 h-8" />
            </div>
            <h1 className="text-2xl font-bold text-navy-900">Confirm verification</h1>
            <p className="text-gray-500 text-sm">
              Enter the 6-digit code to finalize your security settings.
            </p>
          </div>

          <div className="flex flex-col items-center gap-8">
            <div className="w-full">
              <Input 
                type="text"
                inputMode="numeric"
                maxLength={6}
                autoFocus
                placeholder="000 000"
                value={mfaCode}
                onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, ""))}
                className="bg-white text-gray-900 text-3xl font-bold tracking-[0.5em] text-center py-8 h-20 border-gray-200 focus:border-teal-500 focus:ring-teal-500"
              />
            </div>

            <TotpCountdownRing />

            <div className="w-full space-y-4">
              <Button 
                onClick={handleCompleteSetup}
                disabled={loading || mfaCode.length !== 6}
                className="w-full bg-teal-600 hover:bg-teal-700 text-white py-6 text-lg font-bold shadow-lg shadow-teal-600/20"
              >
                {loading ? "Confirming..." : "Finalize Setup"}
              </Button>
              <Button 
                variant="ghost"
                onClick={handleBack}
                className="w-full text-gray-400 hover:text-teal-600"
              >
                <ChevronLeft className="mr-1 w-4 h-4" /> View code again
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default function SetupTotpPage() {
  return (
    <AuthLayout>
      <Suspense fallback={<div>Loading...</div>}>
        <SetupTotpContent />
      </Suspense>
    </AuthLayout>
  );
}
