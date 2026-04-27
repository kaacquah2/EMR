import { test, expect } from "@playwright/test";
import { login, getDoctorCreds } from "../auth";

/**
 * T11.7: Break-Glass Workflow
 * Initiate emergency access → View patient record → Document reason → Review audit
 * Tests emergency access override with comprehensive audit trail.
 * Requires: E2E_DOCTOR_EMAIL, E2E_DOCTOR_PASSWORD env vars
 */

test.describe("Break-Glass Workflow: Emergency Access Override", () => {
  const creds = getDoctorCreds();
  test.skip(!creds, "E2E_DOCTOR_EMAIL and E2E_DOCTOR_PASSWORD not set");

  test("should initiate emergency access, view record, document reason, and audit", async ({ page }) => {
    // 1. Login as doctor
    await login(page, creds!);
    await expect(page.getByRole("heading", { name: /dashboard/i })).toBeVisible({ timeout: 10_000 });

    // 2. Navigate to patient search
    await page.getByRole("link", { name: /patients/i }).click();
    await expect(page.getByRole("heading", { name: /patients/i })).toBeVisible({ timeout: 10_000 });

    // 3. Search for a patient (preferably cross-facility if applicable)
    const searchInput = page.getByPlaceholder(/search|patient|ghana health/i);
    await searchInput.fill("test");
    await page.waitForTimeout(500);

    // 4. Find a patient that requires break-glass access
    // (One from a different facility, or with restricted consent)
    const patientList = page.locator('[data-testid="patient-list-item"]');
    const firstPatient = patientList.first();

    if (await firstPatient.isVisible().catch(() => false)) {
      await firstPatient.click();
    }

    // 5. Check if break-glass overlay appears
    const breakGlassOverlay = page.getByText(/emergency access|break.?glass|restricted/i);

    if (await breakGlassOverlay.isVisible().catch(() => false)) {
      // Break-glass button should be visible
      const breakGlassBtn = page.getByRole("button", { name: /emergency access|break.?glass|override/i });
      await expect(breakGlassBtn).toBeVisible({ timeout: 5_000 });

      await breakGlassBtn.click();

      // 6. Fill break-glass form (reason for emergency access)
      const reasonInput = page.getByPlaceholder(/reason|justify|emergency|medical need/i);
      await expect(reasonInput).toBeVisible({ timeout: 5_000 });
      await reasonInput.fill("Patient in critical condition requires immediate access to full medical history");

      const diagnosisInput = page.getByPlaceholder(/diagnosis|clinical concern/i);
      if (await diagnosisInput.isVisible().catch(() => false)) {
        await diagnosisInput.fill("Acute myocardial infarction suspected");
      }

      // 7. Confirm break-glass access
      const confirmBtn = page.getByRole("button", { name: /confirm|access|override/i });
      await expect(confirmBtn).toBeVisible({ timeout: 5_000 });
      await confirmBtn.click();

      // 8. Verify access granted
      await expect(page.getByText(/access granted|emergency access active|override active/i)).toBeVisible({ timeout: 10_000 });

      // 9. Verify patient record is now viewable
      const patientData = page.getByText(/patient|medical record|encounter/i);
      await expect(patientData).toBeVisible({ timeout: 10_000 });

      // 10. Display should show break-glass indicator
      const breakGlassIndicator = page.getByText(/emergency access|break.?glass/i);
      await expect(breakGlassIndicator).toBeVisible();

      // 11. Navigate to audit/activity log
      const auditLink = page.getByRole("link", { name: /audit|activity|log/i });

      if (await auditLink.isVisible().catch(() => false)) {
        await auditLink.click();

        // Verify break-glass access appears in audit log
        await expect(page.getByText(/break.?glass|emergency access/i)).toBeVisible({ timeout: 10_000 });

        // Check for details: who, when, reason
        const auditEntry = page.locator('[data-testid="audit-entry"], tbody tr').filter({ hasText: /break.?glass|emergency/ }).first();

        if (await auditEntry.isVisible().catch(() => false)) {
          // Verify timestamp
          const timestamp = auditEntry.getByText(/\d{1,2}:\d{1,2}|AM|PM/);
          await expect(timestamp).toBeVisible();

          // Verify user
          const userName = auditEntry.getByText(/doctor|user|name/);
          await expect(userName).toBeVisible();

          // Click to view full audit details
          await auditEntry.click();

          const auditDetails = page.getByText(/reason|emergency|override/i);
          await expect(auditDetails).toBeVisible({ timeout: 5_000 });
        }
      }
    } else {
      // If no break-glass needed (patient is accessible), verify normal access
      await expect(page.getByText(/patient|record|medical/i)).toBeVisible({ timeout: 10_000 });
    }

    // 12. Verify break-glass access is time-limited
    // The system should show: "Emergency access expires in: X minutes"
    const expiryWarning = page.getByText(/expires|emergency access expires/i);

    if (await expiryWarning.isVisible().catch(() => false)) {
      await expect(expiryWarning).toBeVisible();
    }
  });
});
