import { useState } from "react";
import { useApi } from "./use-api";
import { useToast } from "@/lib/toast-context";

export interface TotpSetupResponse {
  totp_secret: string;
  provisioning_url: string;
  role: string;
  mfa_method: string;
  totp_grace_period_expires: string | null;
}

export interface ActivateResponse {
  access_token: string;
  refresh_token: string;
  role: string;
  requires_totp_setup?: boolean;
  grace_expires_at?: string;
  user_profile: unknown;
  backup_codes?: string[];
}

export const useTotp = () => {
  const api = useApi();
  const toast = useToast();
  const [loading, setLoading] = useState(false);

  const getActivateSetup = async (token: string): Promise<TotpSetupResponse | null> => {
    setLoading(true);
    try {
      const data = await api.post<TotpSetupResponse>("/auth/activate-setup", { token });
      return data;
    } catch (error: unknown) {
      const err = error as { detail?: { message?: string }; message?: string };
      toast.error(err.detail?.message || err.message || "Failed to fetch activation details");
      return null;
    } finally {
      setLoading(false);
    }
  };

  const activateAccount = async (
    token: string, 
    password: string, 
    totpConfirmation?: string
  ): Promise<ActivateResponse | null> => {
    setLoading(true);
    try {
      const data = await api.post<ActivateResponse>("/auth/activate", {
        token,
        password,
        totp_confirmation: totpConfirmation,
      });
      return data;
    } catch (error: unknown) {
      const err = error as { detail?: { message?: string }; message?: string };
      toast.error(err.detail?.message || err.message || "Activation failed");
      return null;
    } finally {
      setLoading(false);
    }
  };

  const setupTotp = async (totpConfirmation: string): Promise<boolean> => {
    setLoading(true);
    try {
      await api.post("/auth/setup-totp", {
        totp_confirmation: totpConfirmation,
      });
      toast.success("TOTP setup completed successfully");
      return true;
    } catch (error: unknown) {
      const err = error as { detail?: { message?: string }; message?: string };
      toast.error(err.detail?.message || err.message || "TOTP setup failed");
      return false;
    } finally {
      setLoading(false);
    }
  };

  return {
    loading,
    getActivateSetup,
    activateAccount,
    setupTotp,
  };
};
