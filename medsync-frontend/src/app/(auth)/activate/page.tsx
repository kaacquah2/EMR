"use client";

import React, { useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/lib/auth-context";
import { AuthLayout } from "@/components/auth/AuthLayout";
import { validatePassword, PASSWORD_REQUIREMENTS } from "@/lib/password-policy";
import { API_BASE } from "@/lib/api-base";
import { QRCodeSVG } from "qrcode.react";
import { Copy, AlertCircle, CheckCircle2, Fingerprint } from "lucide-react";
import { isPlatformAuthenticatorAvailable, registerPasskey } from "@/lib/passkey";
import { createApiClient } from "@/lib/api-client";

function ActivateForm() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") || "";
  const { login } = useAuth();
  
  // Form states
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  
  // Two-step flow states
  const [step, setStep] = useState<"setup" | "complete" | "backup" | "passkey">("setup");
  const [totpSecret, setTotpSecret] = useState("");
  const [provisioningUrl, setProvisioningUrl] = useState("");
  const [showBackupCodes, setShowBackupCodes] = useState<string[] | null>(null);
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null);
  const [passkeySupported, setPasskeySupported] = useState(false);

  // Check for passkey support on mount
  React.useEffect(() => {
    isPlatformAuthenticatorAvailable().then((supported) => {
      console.debug('[Activate] Passkey support check result:', supported);
      setPasskeySupported(supported);
    });
  }, []);

  // Step 1: Get TOTP setup data
  const handleSetupMFA = async () => {
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/auth/activate-setup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
      const data = await res.json();
      if (!res.ok) {
        const errorMsg = data.message || "Failed to get MFA setup data";
        throw new Error(errorMsg);
      }
      setTotpSecret(data.totp_secret);
      setProvisioningUrl(data.provisioning_url);
      setStep("complete");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Setup failed";
      if (msg.includes("Invitation expired")) {
        setError("Your invitation has expired. Please request a new one from your administrator.");
      } else if (msg.includes("already activated")) {
        setError("This account has already been activated.");
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  };

  // Step 2: Complete activation with password and TOTP
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    
    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    
    const pwCheck = validatePassword(password);
    if (!pwCheck.valid) {
      setError(pwCheck.message || "Invalid password");
      return;
    }
    
    if (mfaCode.length !== 6) {
      setError("Please enter a valid 6-digit code from your authenticator");
      return;
    }
    
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/auth/activate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          token,
          password,
          totp_confirmation: mfaCode,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        const msg = data.message || "Activation failed";
        if (msg.includes("Invalid TOTP")) {
          throw new Error("Invalid authenticator code. Check your device's time settings and try again.");
        } else if (msg.includes("reuse")) {
          throw new Error("This password was previously used. Please choose a new one.");
        } else {
          throw new Error(msg);
        }
      }
      
      if (data.backup_codes?.length) {
        setShowBackupCodes(data.backup_codes);
        setStep("backup");
        login(data);
      } else {
        login(data);
        window.location.href = "/dashboard";
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Activation failed");
    } finally {
      setLoading(false);
    }
  };

  // Copy to clipboard helper
  const copyToClipboard = async (text: string, label: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopyFeedback(label);
      setTimeout(() => setCopyFeedback(null), 2000);
    } catch {
      setError("Failed to copy. Please try manual copy.");
    }
  };

  // Download backup codes
  const downloadBackupCodes = () => {
    if (!showBackupCodes) return;
    const text = `MedSync EMR Backup Codes\nGenerated: ${new Date().toISOString()}\n\nSave these codes in a safe place. Each can be used once if you lose your authenticator app.\n\n${showBackupCodes.join("\n")}`;
    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `medsync_backup_codes_${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Handle passkey registration during activation
  const handlePasskeyRegistration = async () => {
    setError("");
    setLoading(true);
    try {
      const apiClient = createApiClient(
        () => "",
        async () => false,
        () => {}
      );
      await registerPasskey(apiClient, "My Device");
      setStep("passkey");
      setTimeout(() => {
        window.location.href = "/dashboard";
      }, 2000);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Passkey registration failed";
      if (msg.includes("cancelled")) {
        // User cancelled, just move to dashboard
        setStep("passkey");
        setTimeout(() => {
          window.location.href = "/dashboard";
        }, 1000);
      } else {
        setError(msg);
        // Offer to continue without passkey
        setTimeout(() => {
          setError("");
          window.location.href = "/dashboard";
        }, 3000);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSkipPasskey = () => {
    window.location.href = "/dashboard";
  };

  if (!token) {
    return (
      <div className="rounded-xl border border-[#D97706]/30 bg-[#FEF3C7]/60 p-4 text-[#92400E]">
        <h2 className="font-sora text-lg font-semibold text-[#0F172A]">Invalid or missing invitation link</h2>
        <p className="mt-1 text-sm">Please use the link from your invitation email.</p>
      </div>
    );
  }

  // Step 3: Show backup codes
  if (step === "backup" && showBackupCodes) {
    return (
      <>
        <div className="rounded-xl border border-[#10b981]/30 bg-[#d1fae5]/60 p-4 text-[#065f46]">
          <div className="flex items-start gap-3">
            <CheckCircle2 className="mt-0.5 h-5 w-5 flex-shrink-0" />
            <div>
              <h2 className="font-sora font-bold">Account activated successfully!</h2>
              <p className="mt-1 text-sm">Your two-factor authentication is now enabled.</p>
            </div>
          </div>
        </div>

        <div className="mt-6">
          <h3 className="font-sora text-lg font-bold text-[#0C1F3D]">Save your backup codes</h3>
          <p className="mt-2 text-sm text-[#64748B]">
            Store these codes securely. Each can be used <strong>once</strong> to access your account if you lose your authenticator app.
          </p>

          <div className="mt-4 rounded-xl border border-[#fca5a5]/40 bg-[#fee2e2]/50 p-4">
            <div className="flex items-start gap-2">
              <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-[#dc2626]" />
              <p className="text-sm text-[#7f1d1d]">
                <strong>Important:</strong> These codes won&apos;t be shown again. Save them now in a password manager, write them down, or print them.
              </p>
            </div>
          </div>

          <div className="mt-6 space-y-3 rounded-xl border border-[#0B8A96]/20 bg-[#F0FDFA]/70 p-6">
            <div className="font-mono text-sm text-[#0F172A]">
              {showBackupCodes.map((code, i) => (
                <div key={i} className="flex items-center justify-between py-1">
                  <span>{code}</span>
                  <button
                    type="button"
                    onClick={() => copyToClipboard(code, `Code ${i + 1} copied`)}
                    className="ml-2 text-[#0B8A96] hover:text-[#0a7377]"
                  >
                    <Copy className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-6 flex gap-3">
            <Button
              type="button"
              onClick={() => copyToClipboard(showBackupCodes.join("\n"), "All codes copied")}
              variant="outline"
              fullWidth
            >
              Copy all codes
            </Button>
            <Button
              type="button"
              onClick={downloadBackupCodes}
              variant="outline"
              fullWidth
            >
              Download file
            </Button>
          </div>

          {copyFeedback && (
            <div className="mt-4 rounded-lg bg-[#d1fae5] p-3 text-sm text-[#065f46]">
              ✓ {copyFeedback}
            </div>
          )}

          {passkeySupported && (
            <div className="mt-6 rounded-xl border border-[#0B8A96]/20 bg-[#F0FDFA]/70 p-4">
              <div className="flex items-start gap-3">
                <Fingerprint className="mt-0.5 h-5 w-5 flex-shrink-0 text-[#0B8A96]" />
                <div className="flex-1">
                  <h3 className="font-sora font-semibold text-[#0C1F3D]">Set up faster sign-in?</h3>
                  <p className="mt-1 text-sm text-[#64748B]">
                    Use your fingerprint or face ID for quick, secure login instead of entering codes every time.
                  </p>
                </div>
              </div>
              <div className="mt-3 flex gap-2">
                <Button
                  type="button"
                  onClick={handlePasskeyRegistration}
                  fullWidth
                  disabled={loading}
                  data-testid="activate-passkey-setup"
                >
                  {loading ? "Setting up..." : "Set up passkey"}
                </Button>
                <Button
                  type="button"
                  onClick={handleSkipPasskey}
                  variant="outline"
                  fullWidth
                  disabled={loading}
                >
                  Skip
                </Button>
              </div>
            </div>
          )}

          {!passkeySupported && (
            <div className="mt-6 rounded-xl border border-[#FCD34D]/40 bg-[#FEF3C7]/50 p-4">
              <div className="flex items-start gap-3">
                <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-[#D97706]" />
                <div className="flex-1">
                  <h3 className="font-sora font-semibold text-[#92400E]">Passkey not available</h3>
                  <p className="mt-1 text-sm text-[#78350F]">
                    Windows Hello or biometric authentication isn&apos;t currently available on this device.
                    Check browser console (F12) for details. You can still use authenticator codes to sign in.
                  </p>
                </div>
              </div>
            </div>
          )}

          {!passkeySupported && (
            <Button
              className="mt-6 w-full"
              onClick={() => {
                window.location.href = "/dashboard";
              }}
            >
              Continue to dashboard
            </Button>
          )}

          {passkeySupported && (
            <Button
              className="mt-4 w-full"
              variant="outline"
              onClick={() => {
                window.location.href = "/dashboard";
              }}
            >
              Continue to dashboard
            </Button>
          )}
        </div>
      </>
    );
  }

  // Step: Passkey registration success
  if (step === "passkey") {
    return (
      <>
        <div className="rounded-xl border border-[#10b981]/30 bg-[#d1fae5]/60 p-4 text-[#065f46]">
          <div className="flex items-start gap-3">
            <CheckCircle2 className="mt-0.5 h-5 w-5 flex-shrink-0" />
            <div>
              <h2 className="font-sora font-bold">Passkey registered successfully!</h2>
              <p className="mt-1 text-sm">You can now use fingerprint or face ID to sign in.</p>
            </div>
          </div>
        </div>

        <div className="mt-6 text-center">
          <p className="text-sm text-[#64748B]">Redirecting to dashboard...</p>
        </div>
      </>
    );
  }

  // Step 2: Enter password and TOTP code
  if (step === "complete") {
    return (
      <>
        <div className="mb-4 rounded-lg border border-[#0B8A96]/20 bg-[#F0FDFA]/50 p-4">
          <h3 className="font-sora font-bold text-[#0C1F3D]">Step 2: Complete Your Setup</h3>
          <p className="mt-2 text-sm text-[#64748B]">
            Create your password and confirm your authenticator app is working by entering the code below.
          </p>
        </div>

        <div className="mb-6 rounded-lg border border-[#0B8A96]/25 bg-[#F0FDFA]/70 p-4">
          <div className="space-y-3">
            <div>
              <h4 className="font-mono text-xs font-semibold uppercase text-[#64748B]">Your TOTP Secret (if QR code didn&apos;t work):</h4>
              <div className="mt-2 flex items-center gap-2">
                <code className="flex-1 rounded bg-[#0F172A] p-2 font-mono text-xs text-white">{totpSecret}</code>
                <button
                  type="button"
                  onClick={() => copyToClipboard(totpSecret, "Secret copied")}
                  className="text-[#0B8A96] hover:text-[#0a7377]"
                >
                  <Copy className="h-4 w-4" />
                </button>
              </div>
            </div>
            {copyFeedback && (
              <div className="text-sm text-[#10b981]">✓ {copyFeedback}</div>
            )}
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Min 12 characters"
            required
            minLength={12}
          />
          <Input
            label="Confirm password"
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            placeholder="Repeat password"
            required
          />
          <Input
            label="Authenticator code"
            type="text"
            value={mfaCode}
            onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
            placeholder="6-digit code"
            required
            maxLength={6}
          />

          <div className="rounded-lg border border-[#0B8A96]/20 bg-[#F0FDFA]/50 p-3">
            <ul className="list-inside list-disc text-xs text-[#0F172A]">
              {PASSWORD_REQUIREMENTS.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          </div>

          {error && (
            <div className="rounded-lg border border-[#fca5a5]/40 bg-[#fee2e2]/50 p-3 text-sm text-[#7f1d1d]">
              {error}
            </div>
          )}

          <Button type="submit" fullWidth disabled={loading}>
            {loading ? "Activating..." : "Complete activation"}
          </Button>
        </form>
      </>
    );
  }

  // Step 1: Scan QR code
  return (
    <>
      <div className="mb-4 rounded-lg border border-[#0B8A96]/20 bg-[#F0FDFA]/50 p-4">
        <h3 className="font-sora font-bold text-[#0C1F3D]">Step 1: Set up two-factor authentication</h3>
        <p className="mt-2 text-sm text-[#64748B]">
          Scan this QR code with an authenticator app like Google Authenticator, Authy, or Microsoft Authenticator.
        </p>
      </div>

      <div className="flex flex-col items-center space-y-4">
        <div className="rounded-lg border-2 border-[#0B8A96]/30 bg-white p-4">
          {provisioningUrl ? (
            <QRCodeSVG
              value={provisioningUrl}
              size={256}
              level="H"
              includeMargin={true}
              className="h-auto w-64"
            />
          ) : (
            <div className="h-64 w-64 flex items-center justify-center rounded bg-[#F0FDFA]">
              <p className="text-sm text-[#64748B]">Loading QR code...</p>
            </div>
          )}
        </div>

        <p className="text-xs text-[#64748B]">Can&apos;t scan? You&apos;ll see your secret in the next step.</p>

        {error && (
          <div className="w-full rounded-lg border border-[#fca5a5]/40 bg-[#fee2e2]/50 p-3 text-sm text-[#7f1d1d]">
            {error}
          </div>
        )}

        <Button
          onClick={handleSetupMFA}
          fullWidth
          disabled={loading}
        >
          {loading ? "Loading..." : "Continue"}
        </Button>
      </div>
    </>
  );
}

export default function ActivatePage() {
  return (
    <AuthLayout title="Set up your account" subtitle="Complete your account activation and enable two-factor authentication.">
      <Suspense fallback={<p className="text-[#64748B]">Loading...</p>}>
        <ActivateForm />
      </Suspense>
    </AuthLayout>
  );
}
