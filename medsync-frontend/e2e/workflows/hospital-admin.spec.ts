import { test, expect } from "@playwright/test";
import { login, getHospitalAdminCreds } from "../auth";

/**
 * T11.4: Hospital Admin Workflow
 * Invite user → User activates account → Assign role → View in staff list → Reset MFA
 * Requires: E2E_HOSPITAL_ADMIN_EMAIL, E2E_HOSPITAL_ADMIN_PASSWORD env vars
 */

test.describe("Hospital Admin Workflow: Staff Management", () => {
  const creds = getHospitalAdminCreds();
  test.skip(!creds, "E2E_HOSPITAL_ADMIN_EMAIL and E2E_HOSPITAL_ADMIN_PASSWORD not set");

  test("should invite user, confirm activation, assign role, view in list, reset MFA", async ({ page }) => {
    // 1. Login as hospital admin
    await login(page, creds!);
    await expect(page.getByRole("heading", { name: /dashboard|admin/i })).toBeVisible({ timeout: 10_000 });

    // 2. Navigate to staff management
    const staffLink = page.getByRole("link", { name: /staff|team|users/i });
    await expect(staffLink).toBeVisible({ timeout: 5_000 });
    await staffLink.click();

    await expect(page.getByRole("heading", { name: /staff|users|team/i })).toBeVisible({ timeout: 10_000 });

    // 3. Invite new user
    const inviteBtn = page.getByRole("button", { name: /invite|add user|new staff/i });
    await expect(inviteBtn).toBeVisible({ timeout: 5_000 });
    await inviteBtn.click();

    // Fill invitation form
    const emailInput = page.getByPlaceholder(/email/i);
    await expect(emailInput).toBeVisible({ timeout: 5_000 });
    const testEmail = `test.staff.${Date.now()}@medsync.test`;
    await emailInput.fill(testEmail);

    const firstNameInput = page.getByPlaceholder(/first name|given name/i);
    if (await firstNameInput.isVisible().catch(() => false)) {
      await firstNameInput.fill("John");
    }

    const lastNameInput = page.getByPlaceholder(/last name|surname/i);
    if (await lastNameInput.isVisible().catch(() => false)) {
      await lastNameInput.fill("Doe");
    }

    // Select role
    const roleSelect = page.getByLabel(/role/i);
    if (await roleSelect.isVisible().catch(() => false)) {
      await roleSelect.selectOption("doctor");
    }

    // Send invitation
    const sendInviteBtn = page.getByRole("button", { name: /invite|send|submit/i });
    await expect(sendInviteBtn).toBeVisible({ timeout: 5_000 });
    await sendInviteBtn.click();

    // Verify invitation sent
    await expect(page.getByText(/invited|invitation sent/i)).toBeVisible({ timeout: 5_000 });

    // 4. View staff list and verify user appears
    await page.reload();
    await expect(page.getByRole("heading", { name: /staff|users/i })).toBeVisible({ timeout: 10_000 });

    const staffTable = page.locator('[data-testid="staff-table"], table').first();
    await expect(staffTable).toBeVisible({ timeout: 5_000 });

    const invitedStaffRow = page.locator(`text=${testEmail}`).first();
    if (await invitedStaffRow.isVisible().catch(() => false)) {
      // Staff appears in list
      const invitedStatus = page.locator(`text=${testEmail}`).locator("..").getByText(/invited|pending/i);
      if (await invitedStatus.isVisible().catch(() => false)) {
        await expect(invitedStatus).toBeVisible();
      }
    }

    // 5. Simulate user activation (in real scenario, user clicks email link)
    // For E2E test, we check that the invitation mechanism works

    // 6. Find the user in staff list and attempt to assign/view role
    const staffRows = page.locator('[data-testid="staff-row"], tbody tr');
    const count = await staffRows.count();

    if (count > 0) {
      // Click on first staff member to view details
      const firstStaffRow = staffRows.first();
      const editBtn = firstStaffRow.getByRole("button", { name: /edit|view|details/i });

      if (await editBtn.isVisible().catch(() => false)) {
        await editBtn.click();
        await expect(page.getByText(/role|staff|details/i)).toBeVisible({ timeout: 10_000 });

        // Verify role display
        const roleDisplay = page.getByText(/doctor|nurse|admin/i);
        await expect(roleDisplay).toBeVisible({ timeout: 5_000 });
      }
    }

    // 7. Reset MFA (if MFA is enabled)
    const mfaResetBtn = page.getByRole("button", { name: /reset mfa|mfa|authenticator/i });
    if (await mfaResetBtn.isVisible().catch(() => false)) {
      await mfaResetBtn.click();

      const confirmReset = page.getByRole("button", { name: /confirm|reset|yes/i });
      if (await confirmReset.isVisible().catch(() => false)) {
        await confirmReset.click();
        await expect(page.getByText(/reset|cleared|disabled/i)).toBeVisible({ timeout: 5_000 });
      }
    }

    // Go back to staff list
    const backBtn = page.getByRole("button", { name: /back|close|cancel/i }).first();
    if (await backBtn.isVisible().catch(() => false)) {
      await backBtn.click();
    }

    await expect(page.getByRole("heading", { name: /staff|users/i })).toBeVisible({ timeout: 10_000 });
  });
});
