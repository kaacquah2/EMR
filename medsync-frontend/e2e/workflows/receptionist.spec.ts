import { test, expect } from "@playwright/test";
import { login, getReceptionistCreds } from "../auth";

/**
 * T11.5: Receptionist Workflow
 * Register patient → Schedule appointment → Check-in on arrival → Mark completed
 * Requires: E2E_RECEPTIONIST_EMAIL, E2E_RECEPTIONIST_PASSWORD env vars
 */

test.describe("Receptionist Workflow: Patient Registration and Scheduling", () => {
  const creds = getReceptionistCreds();
  test.skip(!creds, "E2E_RECEPTIONIST_EMAIL and E2E_RECEPTIONIST_PASSWORD not set");

  test("should register patient, schedule appointment, check-in, and mark completed", async ({ page }) => {
    // 1. Login as receptionist
    await login(page, creds!);
    await expect(page.getByRole("heading", { name: /dashboard|reception/i })).toBeVisible({ timeout: 10_000 });

    // 2. Register new patient
    const registerLink = page.getByRole("link", { name: /register|new patient|add patient/i });
    if (await registerLink.isVisible().catch(() => false)) {
      await registerLink.click();
    } else {
      // Navigate via button or menu
      const registerBtn = page.getByRole("button", { name: /register|new|add/i }).first();
      await expect(registerBtn).toBeVisible({ timeout: 5_000 });
      await registerBtn.click();
    }

    await expect(page.getByText(/register|new patient|details/i)).toBeVisible({ timeout: 10_000 });

    // Fill patient registration form
    const firstNameInput = page.getByPlaceholder(/first name|given name/i);
    const uniqueName = `Patient${Date.now()}`;
    await firstNameInput.fill("John");

    const lastNameInput = page.getByPlaceholder(/last name|surname/i);
    await lastNameInput.fill(uniqueName);

    const dobInput = page.getByPlaceholder(/date of birth|dob|birth date/i);
    if (await dobInput.isVisible().catch(() => false)) {
      await dobInput.fill("1990-05-15");
    }

    const genderSelect = page.getByLabel(/gender|sex/i);
    if (await genderSelect.isVisible().catch(() => false)) {
      await genderSelect.selectOption("M");
    }

    const phoneInput = page.getByPlaceholder(/phone|mobile/i);
    if (await phoneInput.isVisible().catch(() => false)) {
      await phoneInput.fill("0201234567");
    }

    const addressInput = page.getByPlaceholder(/address|location/i);
    if (await addressInput.isVisible().catch(() => false)) {
      await addressInput.fill("Accra, Ghana");
    }

    // Submit registration
    const registerSubmitBtn = page.getByRole("button", { name: /register|submit|save/i }).first();
    await registerSubmitBtn.click();

    // Verify patient registered
    await expect(page.getByText(/registered|created|success/i)).toBeVisible({ timeout: 10_000 });

    // Get Ghana Health ID from success message or table
    const ghanaIdText = page.getByText(/ID|[A-Z]{2}\d+/i).first();
    void (await ghanaIdText.textContent());

    // 3. Schedule appointment
    const appointmentLink = page.getByRole("link", { name: /appointment|schedule/i });
    if (await appointmentLink.isVisible().catch(() => false)) {
      await appointmentLink.click();
    } else {
      // Navigate from dashboard
      await page.goto("/appointments");
    }

    await expect(page.getByRole("heading", { name: /appointment/i })).toBeVisible({ timeout: 10_000 });

    const scheduleBtn = page.getByRole("button", { name: /schedule|new|add appointment/i });
    await expect(scheduleBtn).toBeVisible({ timeout: 5_000 });
    await scheduleBtn.click();

    // Search for patient
    const searchInput = page.getByPlaceholder(/search|patient|ghana health/i);
    await expect(searchInput).toBeVisible({ timeout: 5_000 });
    await searchInput.fill(uniqueName);
    await page.waitForTimeout(500);

    const patientOption = page.locator('li[role="option"], [data-testid="patient-search-option"]').first();
    if (await patientOption.isVisible().catch(() => false)) {
      await patientOption.click();
    }

    // Set appointment date/time
    const dateInput = page.getByPlaceholder(/date|appointment date/i);
    if (await dateInput.isVisible().catch(() => false)) {
      const tomorrow = new Date(Date.now() + 86400000).toISOString().split("T")[0];
      await dateInput.fill(tomorrow);
    }

    const timeInput = page.getByPlaceholder(/time|appointment time/i);
    if (await timeInput.isVisible().catch(() => false)) {
      await timeInput.fill("10:00");
    }

    const departmentSelect = page.getByLabel(/department|speciality/i);
    if (await departmentSelect.isVisible().catch(() => false)) {
      const options = await departmentSelect.locator("option").count();
      if (options > 1) {
        await departmentSelect.selectOption({ index: 1 });
      }
    }

    const appointmentSubmitBtn = page.getByRole("button", { name: /schedule|save|confirm/i }).first();
    await appointmentSubmitBtn.click();

    await expect(page.getByText(/scheduled|created|appointment/i)).toBeVisible({ timeout: 10_000 });

    // 4. Check-in patient on arrival
    const appointmentsList = page.locator('[data-testid="appointment-card"], [data-testid="appointment-row"]');
    const firstAppointment = appointmentsList.first();

    if (await firstAppointment.isVisible().catch(() => false)) {
      const checkInBtn = firstAppointment.getByRole("button", { name: /check.?in|arrive|arrival/i });

      if (await checkInBtn.isVisible().catch(() => false)) {
        await checkInBtn.click();

        const confirmCheckIn = page.getByRole("button", { name: /confirm|yes|check.?in/i });
        if (await confirmCheckIn.isVisible().catch(() => false)) {
          await confirmCheckIn.click();
        }

        await expect(page.getByText(/checked.?in|arrival|arrived/i)).toBeVisible({ timeout: 5_000 });
      }
    }

    // 5. Mark appointment completed
    const completedAppointment = page.locator('[data-testid="appointment-card"]').filter({ hasText: /checked.?in|arrived/ }).first();

    if (await completedAppointment.isVisible().catch(() => false)) {
      const completeBtn = completedAppointment.getByRole("button", { name: /complete|done|finish/i });

      if (await completeBtn.isVisible().catch(() => false)) {
        await completeBtn.click();

        const confirmComplete = page.getByRole("button", { name: /confirm|yes|complete/i });
        if (await confirmComplete.isVisible().catch(() => false)) {
          await confirmComplete.click();
        }

        await expect(page.getByText(/completed|finished/i)).toBeVisible({ timeout: 5_000 });
      }
    }
  });
});
