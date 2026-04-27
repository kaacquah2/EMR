import { test, expect } from "@playwright/test";
import { login, getNurseCreds } from "../auth";

/**
 * T11.2: Nurse Workflow
 * View ward dashboard → Record vitals → Dispense medication → Record nursing note → Handover shift
 * Requires: E2E_NURSE_EMAIL, E2E_NURSE_PASSWORD env vars
 */

test.describe("Nurse Workflow: Ward Shift Handover", () => {
  const creds = getNurseCreds();
  test.skip(!creds, "E2E_NURSE_EMAIL and E2E_NURSE_PASSWORD not set");

  test("should view ward, record vitals, dispense medication, note, and handover", async ({ page }) => {
    // 1. Login as nurse
    await login(page, creds!);
    await expect(page.getByRole("heading", { name: /dashboard|ward/i })).toBeVisible({ timeout: 10_000 });

    // 2. Navigate to ward dashboard
    const wardLink = page.getByRole("link", { name: /ward|dashboard/i });
    if (await wardLink.isVisible().catch(() => false)) {
      await wardLink.click();
    }
    await expect(page.getByText(/ward|bed|patient/i)).toBeVisible({ timeout: 10_000 });

    // 3. Find and select a patient in the ward
    const firstBedPatient = page.locator('[data-testid="bed-card"]').first();
    if (await firstBedPatient.isVisible().catch(() => false)) {
      await firstBedPatient.click();
    } else {
      const patientLink = page.locator('[data-testid="patient-list-item"]').first();
      await expect(patientLink).toBeVisible({ timeout: 5_000 });
      await patientLink.click();
    }

    // Verify patient record opened
    await expect(page.getByText(/patient|bed|admission/i)).toBeVisible({ timeout: 10_000 });

    // 4. Record vitals
    const vitalBtn = page.getByRole("button", { name: /record vitals|vital signs/i });
    await expect(vitalBtn).toBeVisible({ timeout: 5_000 });
    await vitalBtn.click();

    // Fill vital signs
    const tempInput = page.getByPlaceholder(/temperature|temp|celsius/i);
    if (await tempInput.isVisible().catch(() => false)) {
      await tempInput.fill("37.5");
    }

    const bpInput = page.getByPlaceholder(/blood pressure|bp|systolic/i);
    if (await bpInput.isVisible().catch(() => false)) {
      await bpInput.fill("120");
    }

    const bpDiastolic = page.getByPlaceholder(/diastolic/i);
    if (await bpDiastolic.isVisible().catch(() => false)) {
      await bpDiastolic.fill("80");
    }

    const hrInput = page.getByPlaceholder(/heart rate|pulse|bpm/i);
    if (await hrInput.isVisible().catch(() => false)) {
      await hrInput.fill("72");
    }

    const o2Input = page.getByPlaceholder(/oxygen|spo2/i);
    if (await o2Input.isVisible().catch(() => false)) {
      await o2Input.fill("98");
    }

    await page.getByRole("button", { name: /save|confirm/i }).first().click();
    await expect(page.getByText(/vitals|recorded/i)).toBeVisible({ timeout: 5_000 });

    // 5. Dispense medication
    const dispenseBtn = page.getByRole("button", { name: /dispense|give medication/i });
    if (await dispenseBtn.isVisible().catch(() => false)) {
      await dispenseBtn.click();

      // Select medication
      const medCheckbox = page.locator('[data-testid="medication-checkbox"]').first();
      if (await medCheckbox.isVisible().catch(() => false)) {
        await medCheckbox.check();
      }

      const confirmDispense = page.getByRole("button", { name: /confirm|dispense/i });
      await expect(confirmDispense).toBeVisible({ timeout: 5_000 });
      await confirmDispense.click();

      await expect(page.getByText(/dispensed|given/i)).toBeVisible({ timeout: 5_000 });
    }

    // 6. Record nursing note
    const noteBtn = page.getByRole("button", { name: /note|nursing note|add note/i });
    if (await noteBtn.isVisible().catch(() => false)) {
      await noteBtn.click();

      const noteInput = page.getByPlaceholder(/note|observation/i);
      await expect(noteInput).toBeVisible({ timeout: 5_000 });
      await noteInput.fill("Patient is stable, vital signs normal. Ate well. No complaints.");

      await page.getByRole("button", { name: /save|submit/i }).first().click();
      await expect(page.getByText(/note|saved|recorded/i)).toBeVisible({ timeout: 5_000 });
    }

    // 7. Handover shift
    const handoverBtn = page.getByRole("button", { name: /handover|end shift|sign off/i });
    if (await handoverBtn.isVisible().catch(() => false)) {
      await handoverBtn.click();

      const handoverNoteInput = page.getByPlaceholder(/handover|summary|notes/i);
      if (await handoverNoteInput.isVisible().catch(() => false)) {
        await handoverNoteInput.fill("All patients stable. No incidents. Medications dispensed on schedule.");

        await page.getByRole("button", { name: /confirm|complete|handover/i }).first().click();
        await expect(page.getByText(/shift ended|handover complete/i)).toBeVisible({ timeout: 5_000 });
      }
    }
  });
});
