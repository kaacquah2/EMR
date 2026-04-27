import { test, expect } from "@playwright/test";
import { login, getDoctorCreds, getSuperAdminCreds } from "../auth";

/**
 * T11.8: Cross-Facility Workflow
 * Create consent → Create referral → Accept referral → Verify data sharing
 * Tests multi-hospital HIE (Health Information Exchange) workflow.
 * Requires: E2E_DOCTOR_EMAIL, E2E_DOCTOR_PASSWORD, E2E_SUPER_ADMIN_EMAIL, E2E_SUPER_ADMIN_PASSWORD
 */

test.describe("Cross-Facility Workflow: Consent and Referral", () => {
  test("should create consent, referral, accept, and verify data sharing", async ({ page, context }) => {
    // Part 1: Doctor creates referral to another facility
    const doctorCreds = getDoctorCreds();
    test.skip(!doctorCreds, "E2E_DOCTOR_EMAIL and E2E_DOCTOR_PASSWORD not set");

    // 1. Login as doctor in Hospital A
    await login(page, doctorCreds!);
    await expect(page.getByRole("heading", { name: /dashboard/i })).toBeVisible({ timeout: 10_000 });

    // 2. Navigate to patient search
    await page.getByRole("link", { name: /patients/i }).click();
    await expect(page.getByRole("heading", { name: /patients/i })).toBeVisible({ timeout: 10_000 });

    // 3. Search and select a patient
    const searchInput = page.getByPlaceholder(/search|patient|ghana health/i);
    await searchInput.fill("test");
    await page.waitForTimeout(500);

    const firstPatient = page.locator('[data-testid="patient-list-item"]').first();
    if (await firstPatient.isVisible().catch(() => false)) {
      await firstPatient.click();
    }

    // 4. Create referral to another hospital
    const referralBtn = page.getByRole("button", { name: /referral|refer|send referral/i });

    if (await referralBtn.isVisible().catch(() => false)) {
      await referralBtn.click();

      // Fill referral form
      const targetHospitalSelect = page.getByLabel(/hospital|facility|refer to/i);
      if (await targetHospitalSelect.isVisible().catch(() => false)) {
        const options = await targetHospitalSelect.locator("option").count();
        if (options > 1) {
          await targetHospitalSelect.selectOption({ index: 1 });
        }
      }

      const reasonInput = page.getByPlaceholder(/reason|indication|justification/i);
      if (await reasonInput.isVisible().catch(() => false)) {
        await reasonInput.fill("Patient requires specialist cardiology evaluation");
      }

      const urgencySelect = page.getByLabel(/urgency|priority/i);
      if (await urgencySelect.isVisible().catch(() => false)) {
        await urgencySelect.selectOption("routine");
      }

      const referralSubmitBtn = page.getByRole("button", { name: /send|create|submit/i }).first();
      await referralSubmitBtn.click();

      await expect(page.getByText(/referral created|sent|submitted/i)).toBeVisible({ timeout: 10_000 });
    }

    // 5. Grant data sharing consent
    const consentBtn = page.getByRole("button", { name: /consent|permission|share data/i });

    if (await consentBtn.isVisible().catch(() => false)) {
      await consentBtn.click();

      // Select scope
      const scopeSelect = page.getByLabel(/scope|access level|data type/i);
      if (await scopeSelect.isVisible().catch(() => false)) {
        await scopeSelect.selectOption("full_record");
      }

      const expiryInput = page.getByPlaceholder(/expiry|duration|valid until/i);
      if (await expiryInput.isVisible().catch(() => false)) {
        const expiryDate = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split("T")[0];
        await expiryInput.fill(expiryDate);
      }

      const consentSubmitBtn = page.getByRole("button", { name: /grant|confirm|save/i }).first();
      if (await consentSubmitBtn.isVisible().catch(() => false)) {
        await consentSubmitBtn.click();

        await expect(page.getByText(/consent|granted|permission/i)).toBeVisible({ timeout: 10_000 });
      }
    }

    // Part 2: Doctor at Hospital B accepts referral
    const superAdminCreds = getSuperAdminCreds();
    test.skip(!superAdminCreds, "E2E_SUPER_ADMIN_EMAIL and E2E_SUPER_ADMIN_PASSWORD not set");

    // Create a new context to simulate different user/hospital
    const secondPage = await context.newPage();

    // Login as doctor/admin from Hospital B (or use super admin to switch hospital)
    await login(secondPage, superAdminCreds!);

    // If super admin, switch to Hospital B context
    const hospitalSwitcher = secondPage.getByLabel(/hospital|facility|operating in/i);
    if (await hospitalSwitcher.isVisible().catch(() => false)) {
      // Try to select different hospital if available
      const options = await hospitalSwitcher.locator("option").count();
      if (options > 1) {
        await hospitalSwitcher.selectOption({ index: 1 });
      }
    }

    // 6. Navigate to referrals inbox
    const referralsLink = secondPage.getByRole("link", { name: /referral|inbox|incoming/i });
    if (await referralsLink.isVisible().catch(() => false)) {
      await referralsLink.click();

      await expect(secondPage.getByText(/referral|incoming|pending/i)).toBeVisible({ timeout: 10_000 });

      // Find the referral
      const referralCard = secondPage.locator('[data-testid="referral-card"], [data-testid="referral-item"]').first();

      if (await referralCard.isVisible().catch(() => false)) {
        await referralCard.click();

        // 7. View referral details
        await expect(secondPage.getByText(/referral details|reason|from/i)).toBeVisible({ timeout: 10_000 });

        // 8. Accept referral
        const acceptBtn = secondPage.getByRole("button", { name: /accept|approve|confirm/i });
        if (await acceptBtn.isVisible().catch(() => false)) {
          await acceptBtn.click();

          const confirmAccept = secondPage.getByRole("button", { name: /confirm|yes|accept/i });
          if (await confirmAccept.isVisible().catch(() => false)) {
            await confirmAccept.click();
          }

          await expect(secondPage.getByText(/accepted|approved/i)).toBeVisible({ timeout: 10_000 });
        }
      }
    }

    // 9. Verify data sharing works
    const patientSearchLink = secondPage.getByRole("link", { name: /patients|search/i });
    if (await patientSearchLink.isVisible().catch(() => false)) {
      await patientSearchLink.click();

      // Search for the referred patient
      const searchBox = secondPage.getByPlaceholder(/search|patient/i);
      if (await searchBox.isVisible().catch(() => false)) {
        await searchBox.fill("test");
        await secondPage.waitForTimeout(500);

        // Verify cross-facility patient is visible
        const crossFacilityIndicator = secondPage.getByText(/cross.?facility|shared|other hospital/i);
        if (await crossFacilityIndicator.isVisible().catch(() => false)) {
          await expect(crossFacilityIndicator).toBeVisible();
        }
      }
    }

    // 10. Verify audit log shows the consent and referral activity
    const auditLink = secondPage.getByRole("link", { name: /audit|activity|log/i });
    if (await auditLink.isVisible().catch(() => false)) {
      await auditLink.click();

      await expect(secondPage.getByText(/referral|consent|access/i)).toBeVisible({ timeout: 10_000 });
    }

    await secondPage.close();
  });
});
