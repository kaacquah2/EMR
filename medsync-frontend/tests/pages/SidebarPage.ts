import { expect, type Page } from "@playwright/test";
import { E2E_NAV_LABELS } from "../utils/constants";

/**
 * Sidebar nav assertions. Sidebar shows nav items from getNavigation(role).
 */
export class SidebarPage {
  constructor(private readonly page: Page) {}

  /** Get sidebar nav container. Sidebar is in an aside; links are inside it. */
  private get sidebar() {
    return this.page.getByRole("navigation").or(this.page.locator("aside")).first();
  }

  /** Assert a link with this text is visible in the sidebar. */
  async expectNavLinkVisible(label: string) {
    await this.sidebar.getByRole("link", { name: new RegExp(label, "i") }).waitFor({ state: "visible", timeout: 5_000 });
  }

  /** Assert no link with this text in the sidebar. */
  async expectNavLinkHidden(label: string) {
    const link = this.sidebar.getByRole("link", { name: new RegExp(label, "i") });
    await expect(link).toHaveCount(0);
  }

  /** Assert all given labels are visible and no forbidden labels appear. */
  async expectVisibleNavLabels(visible: string[], forbidden: string[]) {
    for (const label of visible) {
      await this.expectNavLinkVisible(label);
    }
    for (const label of forbidden) {
      const link = this.sidebar.getByRole("link", { name: new RegExp(label, "i") });
      await expect(link).toHaveCount(0);
    }
  }

  /** Click sidebar link by visible text. */
  async clickNavLink(label: string) {
    await this.sidebar.getByRole("link", { name: new RegExp(label, "i") }).click();
  }

  /** Log out via sidebar button. */
  async logout() {
    await this.page.getByRole("button", { name: /log out|out/i }).click();
  }

  /** Convenience: assert Dashboard link visible. */
  async expectDashboardVisible() {
    await this.expectNavLinkVisible(E2E_NAV_LABELS.Dashboard);
  }
}
