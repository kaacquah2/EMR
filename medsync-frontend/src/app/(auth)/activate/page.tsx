"use client";

import React, { useState, useEffect, Suspense, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Image from "next/image";
import { QRCodeSVG } from "qrcode.react";
import { 
  ShieldCheck, 
  Smartphone, 
  QrCode, 
  Key, 
  ChevronRight, 
  ChevronLeft, 
  AlertCircle,
  Clock,
  ExternalLink,
  Copy
} from "lucide-react";
import { useTotp, TotpSetupResponse } from "@/hooks/use-totp";
import { useToast } from "@/lib/toast-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AuthLayout } from "@/components/auth/AuthLayout";
import { TotpCountdownRing } from "@/components/ui/TotpCountdownRing";

const ActivationContent = () => {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  
  const { loading, getActivateSetup, activateAccount } = useTotp();
  const toast = useToast();
  
  const [step, setStep] = useState(1);
  const [setupData, setSetupData] = useState<TotpSetupResponse | null>(null);
  const [password, setPassword] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [isGracePeriodModalOpen, setIsGracePeriodModalOpen] = useState(false);

  const loadSetup = useCallback(async (t: string) => {
    const data = await getActivateSetup(t);
    if (data) {
      setSetupData(data);
    } else {
      router.push("/login");
    }
  }, [getActivateSetup, router]);
  
  useEffect(() => {
    if (token) {
      void (async () => {
        await loadSetup(token);
      })();
    } else {
      router.push("/login");
    }
  }, [token, loadSetup, router]);

  const handleNext = () => setStep(prev => prev + 1);
  const handleBack = () => setStep(prev => prev - 1);

  const handleActivate = async (skipTotp = false) => {
    if (!password) {
      toast.error("Please set a password first");
      setStep(1); // Go back to start if password missing (though it should be collected in a real form)
      return;
    }

    if (!skipTotp && mfaCode.length !== 6) {
      toast.error("Please enter the 6-digit verification code");
      return;
    }

    const result = await activateAccount(token!, password, skipTotp ? undefined : mfaCode);
    
    if (result) {
      toast.success(skipTotp ? "Account activated with 24-hour grace period" : "Account activated successfully!");
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
        <p className="mt-4 text-gray-500 font-medium">Preparing your secure workspace...</p>
      </div>
    );
  }

  const isStaff = !["super_admin", "hospital_admin"].includes(setupData.role);

  return (
    <div className="w-full max-w-md mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      {/* Progress Indicator */}
      <div className="flex items-center justify-center gap-3 mb-8">
        {[1, 2, 3].map((s) => (
          <div 
            key={s}
            className={`h-2 rounded-full transition-all duration-300 ${
              step === s ? "w-8 bg-teal-600" : s < step ? "w-4 bg-teal-200" : "w-2 bg-gray-200"
            }`}
          />
        ))}
      </div>

      {/* Step 1: Install App */}
      {step === 1 && (
        <div className="space-y-6">
          <div className="text-center space-y-2">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-teal-50 text-teal-600 rounded-2xl mb-2">
              <Smartphone className="w-8 h-8" />
            </div>
            <h1 className="text-2xl font-bold text-navy-900">Set up two-factor authentication</h1>
            <p className="text-gray-500 text-sm">
              MedSync requires an authenticator app to protect patient records and your identity.
            </p>
          </div>

          <div className="space-y-4">
            <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Recommended Apps</div>
            
            <a 
              href="https://play.google.com/store/apps/details?id=com.google.android.apps.authenticator2"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-4 p-4 border border-gray-100 rounded-xl hover:border-teal-200 hover:bg-teal-50/30 transition-all group"
            >
              <div className="w-10 h-10 bg-white rounded-lg border border-gray-100 flex items-center justify-center p-2 shadow-sm">
                <Image src="https://www.gstatic.com/images/branding/product/2x/authenticator_32dp.png" alt="Google" width={32} height={32} />
              </div>
              <div className="flex-1">
                <div className="text-sm font-bold text-gray-900">Google Authenticator</div>
                <div className="text-xs text-gray-400">Trusted and simple setup</div>
              </div>
              <ExternalLink className="w-4 h-4 text-gray-300 group-hover:text-teal-500" />
            </a>

            <a 
              href="https://www.microsoft.com/en-us/security/mobile-authenticator-app"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-4 p-4 border border-gray-100 rounded-xl hover:border-teal-200 hover:bg-teal-50/30 transition-all group"
            >
              <div className="w-10 h-10 bg-white rounded-lg border border-gray-100 flex items-center justify-center p-2 shadow-sm">
                <Image src="https://upload.wikimedia.org/wikipedia/commons/f/f7/Microsoft_Authenticator_logo.svg" alt="Microsoft" width={32} height={32} />
              </div>
              <div className="flex-1">
                <div className="text-sm font-bold text-gray-900">Microsoft Authenticator</div>
                <div className="text-xs text-gray-400">Great for enterprise accounts</div>
              </div>
              <ExternalLink className="w-4 h-4 text-gray-300 group-hover:text-teal-500" />
            </a>
          </div>

          <div className="space-y-4 pt-4">
            <div className="space-y-3">
              <label className="block text-sm font-medium text-gray-700">Set your login password</label>
              <Input 
                type="password" 
                placeholder="Minimum 12 characters" 
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="bg-white text-gray-900 border-gray-200 focus:border-teal-500 focus:ring-teal-500"
              />
            </div>

            <div className="flex flex-col gap-3">
              <Button 
                onClick={handleNext}
                className="w-full bg-teal-600 hover:bg-teal-700 text-white py-6 text-base font-bold shadow-lg shadow-teal-600/20"
              >
                Next <ChevronRight className="ml-2 w-5 h-5" />
              </Button>
              <button 
                onClick={handleNext}
                className="text-sm text-gray-500 hover:text-teal-600 font-medium transition-colors"
              >
                I already have an authenticator app →
              </button>
            </div>
          </div>

          {isStaff && (
            <div className="text-center pt-4 border-t border-gray-50">
              <button 
                onClick={() => setIsGracePeriodModalOpen(true)}
                className="text-xs text-gray-400 hover:text-teal-600 transition-colors underline underline-offset-4 decoration-gray-200"
              >
                Set up later (you have 24 hours)
              </button>
            </div>
          )}
        </div>
      )}

      {/* Step 2: Scan QR */}
      {step === 2 && (
        <div className="space-y-6 animate-in fade-in slide-in-from-right-4 duration-300">
          <div className="text-center space-y-2">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-teal-50 text-teal-600 rounded-2xl mb-2">
              <QrCode className="w-8 h-8" />
            </div>
            <h1 className="text-2xl font-bold text-navy-900">Scan this code</h1>
            <p className="text-gray-500 text-sm">
              Open your authenticator app and scan the code below.
            </p>
          </div>

          <div className="flex flex-col items-center gap-6">
            <div className="p-6 bg-white rounded-3xl shadow-xl shadow-gray-200 border border-gray-50 relative group">
              <QRCodeSVG 
                value={setupData.provisioning_url} 
                size={200} 
                includeMargin={false}
                className="transition-opacity group-hover:opacity-10"
              />
              <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                <span className="text-teal-600 font-bold bg-white px-3 py-1 rounded-full shadow-sm text-xs border border-teal-100">
                  Ready to scan
                </span>
              </div>
            </div>

            <div className="text-center">
              <div className="text-sm font-bold text-navy-900">MedSync Account</div>
              <div className="text-xs text-gray-400">{setupData.totp_secret.substring(0, 4)}... (Secret ID)</div>
            </div>

            <details className="w-full group">
              <summary className="text-sm font-medium text-teal-600 hover:text-teal-700 cursor-pointer text-center list-none flex items-center justify-center gap-1 select-none">
                <Key className="w-4 h-4" />
                Can&apos;t scan? Enter manually
              </summary>
              <div className="mt-4 p-4 bg-gray-50 rounded-xl border border-dashed border-gray-200 space-y-3">
                <p className="text-xs text-gray-500 leading-relaxed">
                  In your app: tap <strong>+</strong> → <strong>Enter a setup key</strong> → paste the code below
                </p>
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

          <div className="flex gap-4 pt-4">
            <Button 
              variant="outline"
              onClick={handleBack}
              className="flex-1 py-6 border-gray-200 text-gray-600 hover:bg-gray-50"
            >
              <ChevronLeft className="mr-2 w-5 h-5" /> Back
            </Button>
            <Button 
              onClick={handleNext}
              className="flex-[2] bg-teal-600 hover:bg-teal-700 text-white py-6 text-base font-bold shadow-lg shadow-teal-600/20"
            >
              I&apos;ve scanned it → Next
            </Button>
          </div>
        </div>
      )}

      {/* Step 3: Verify */}
      {step === 3 && (
        <div className="space-y-8 animate-in fade-in slide-in-from-right-4 duration-300">
          <div className="text-center space-y-2">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-teal-50 text-teal-600 rounded-2xl mb-2">
              <ShieldCheck className="w-8 h-8" />
            </div>
            <h1 className="text-2xl font-bold text-navy-900">Verify it works</h1>
            <p className="text-gray-500 text-sm">
              Enter the 6-digit code from your app to confirm setup.
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
                onChange={(e) => {
                  const val = e.target.value.replace(/\D/g, "");
                  setMfaCode(val);
                  if (val.length === 6) {
                    // Logic to auto-submit could be here, but let's wait a split second for UX
                  }
                }}
                className="bg-white text-gray-900 text-3xl font-bold tracking-[0.5em] text-center py-8 h-20 border-gray-200 focus:border-teal-500 focus:ring-teal-500 placeholder:text-gray-100"
              />
              <p className="mt-3 text-center text-xs text-gray-400">
                Type the 6 numbers currently shown in your app
              </p>
            </div>

            <TotpCountdownRing />

            <div className="w-full space-y-4">
              <Button 
                onClick={() => handleActivate()}
                disabled={loading || mfaCode.length !== 6}
                className="w-full bg-teal-600 hover:bg-teal-700 text-white py-6 text-lg font-bold shadow-lg shadow-teal-600/20 disabled:bg-gray-100 disabled:text-gray-400"
              >
                {loading ? "Verifying..." : "Verify & Activate"}
              </Button>
              <Button 
                variant="ghost"
                onClick={handleBack}
                className="w-full text-gray-400 hover:text-teal-600"
              >
                <ChevronLeft className="mr-1 w-4 h-4" /> Change setup
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Grace Period Modal */}
      {isGracePeriodModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-navy-900/40 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-white rounded-3xl p-8 max-w-sm w-full shadow-2xl space-y-6 animate-in zoom-in-95 duration-200">
            <div className="flex flex-col items-center text-center space-y-4">
              <div className="w-16 h-16 bg-amber-50 text-amber-500 rounded-2xl flex items-center justify-center">
                <Clock className="w-10 h-10" />
              </div>
              <div className="space-y-2">
                <h3 className="text-xl font-bold text-gray-900">Activate now, set up later?</h3>
                <p className="text-sm text-gray-500 leading-relaxed">
                  You can start using MedSync immediately, but you <strong>must</strong> complete the authenticator setup within <strong>24 hours</strong>.
                </p>
              </div>
              <div className="bg-amber-50 p-4 rounded-xl border border-amber-100 text-xs text-amber-800 text-left flex gap-3">
                <AlertCircle className="w-5 h-5 shrink-0" />
                <p>After 24 hours, your account will be locked until the setup is completed.</p>
              </div>
            </div>
            
            <div className="flex flex-col gap-3">
              <Button 
                onClick={() => handleActivate(true)}
                disabled={loading || !password}
                className="w-full bg-amber-500 hover:bg-amber-600 text-white font-bold py-4"
              >
                {loading ? "Activating..." : "Yes, Activate for 24h"}
              </Button>
              <Button 
                variant="ghost"
                onClick={() => setIsGracePeriodModalOpen(false)}
                className="w-full text-gray-400 font-medium"
              >
                Go back to setup
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default function ActivatePage() {
  return (
    <AuthLayout>
      <Suspense fallback={<div>Loading...</div>}>
        <ActivationContent />
      </Suspense>
    </AuthLayout>
  );
}
