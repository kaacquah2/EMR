import { test, expect } from "@playwright/test";
import { login, getDoctorCreds } from "../auth";

/**
 * T11.1: Doctor Workflow
 * Search patient → Create encounter → Add diagnosis → Prescribe medication → Close encounter
 * Requires: E2E_DOCTOR_EMAIL, E2E_DOCTOR_PASSWORD env vars
 */

test.describe("Doctor Workflow: Complete Encounter", () => {
  const creds = getDoctorCreds();
  test.skip(!creds, "E2E_DOCTOR_EMAIL and E2E_DOCTOR_PASSWORD not set");

  test("should search patient, create encounter, add diagnosis, prescribe, and close", async ({ page }) => {
    // 1. Login as doctor
    await login(page, creds!);
    await expect(page.getByRole("heading", { name: /dashboard/i })).toBeVisible({ timeout: 10_000 });

    // 2. Navigate to patient search
    await page.getByRole("link", { name: /patients/i }).click();
    await expect(page.getByRole("heading", { name: /patients/i })).toBeVisible({ timeout: 10_000 });

    // 3. Search for a patient
    const searchInput = page.getByPlaceholder(/search by name|ghana health id/i);
    await searchInput.fill("test");
    await page.waitForTimeout(500);

    // 4. Click first patient in results
    const firstPatient = page.locator('[data-testid="patient-list-item"]').first();
    await expect(firstPatient).toBeVisible({ timeout: 5_000 });
    const patientName = await firstPatient.textContent();
    await firstPatient.click();

    // Verify patient details loaded
    await expect(page.getByRole("heading", { name: new RegExp(patientName?.split("\n")[0] || "patient", "i") })).toBeVisible({ timeout: 10_000 });

    // 5. Create encounter
    const createEncounterBtn = page.getByRole("button", { name: /new encounter|start encounter/i });
    await expect(createEncounterBtn).toBeVisible({ timeout: 5_000 });
    await createEncounterBtn.click();

    // Verify encounter form appears
    await expect(page.getByText(/chief complaint|presenting complaint/i)).toBeVisible({ timeout: 10_000 });

    // 6. Fill encounter details
    const chiefComplaintInput = page.getByPlaceholder(/chief complaint|reason for visit/i);
    await chiefComplaintInput.fill("Patient presents with fever and cough");

    // 7. Add diagnosis
    const diagnosisBtn = page.getByRole("button", { name: /add diagnosis|diagnosis/i });
    await expect(diagnosisBtn).toBeVisible({ timeout: 5_000 });
    await diagnosisBtn.click();

    // Fill diagnosis
    const icdInput = page.getByPlaceholder(/icd|diagnosis code/i);
    await icdInput.fill("J18");
    await page.waitForTimeout(300);

    // Select from dropdown if available
    const icdOption = page.locator('li[role="option"]').first();
    if (await icdOption.isVisible().catch(() => false)) {
      await icdOption.click();
    }

    const diagnosisNameInput = page.getByPlaceholder(/diagnosis name|condition/i);
    await diagnosisNameInput.fill("Pneumonia");
    await page.getByRole("button", { name: /confirm|add|save/i }).first().click();

    // 8. Prescribe medication
    const prescribeBtn = page.getByRole("button", { name: /prescribe|add medication/i });
    await expect(prescribeBtn).toBeVisible({ timeout: 5_000 });
    await prescribeBtn.click();

    const medicationInput = page.getByPlaceholder(/medication|drug name/i);
    await medicationInput.fill("Amoxicillin");
    await page.waitForTimeout(300);

    const medOption = page.locator('li[role="option"]').first();
    if (await medOption.isVisible().catch(() => false)) {
      await medOption.click();
    }

    const dosageInput = page.getByPlaceholder(/dosage|dose/i);
    await dosageInput.fill("500mg");

    const frequencySelect = page.getByLabel(/frequency/i);
    if (await frequencySelect.isVisible().catch(() => false)) {
      await frequencySelect.selectOption("3");
    }

    const durationInput = page.getByPlaceholder(/duration|days/i);
    await durationInput.fill("7");

    await page.getByRole("button", { name: /confirm|save|add/i }).nth(1).click();

    // 9. Record vitals
    const vitalsBtn = page.getByRole("button", { name: /vitals|vital signs/i });
    if (await vitalsBtn.isVisible().catch(() => false)) {
      await vitalsBtn.click();

      const tempInput = page.getByPlaceholder(/temperature|temp/i);
      if (await tempInput.isVisible().catch(() => false)) {
        await tempInput.fill("38.5");
      }

      const bpInput = page.getByPlaceholder(/blood pressure|bp/i);
      if (await bpInput.isVisible().catch(() => false)) {
        await bpInput.fill("120/80");
      }

      const hrInput = page.getByPlaceholder(/heart rate|pulse/i);
      if (await hrInput.isVisible().catch(() => false)) {
        await hrInput.fill("85");
      }

      await page.getByRole("button", { name: /save|confirm/i }).last().click();
    }

    // 10. Close/Save encounter
    const saveEncounterBtn = page.getByRole("button", { name: /complete|finish|save encounter/i });
    await expect(saveEncounterBtn).toBeVisible({ timeout: 5_000 });
    await saveEncounterBtn.click();

    // Verify encounter saved
    await expect(page.getByText(/encounter|visit/i)).toBeVisible({ timeout: 10_000 });
  });
});
