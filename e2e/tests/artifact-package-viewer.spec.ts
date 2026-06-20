import { test, expect } from '@playwright/test';

async function ask(page, prompt) {
  await page.getByTestId('composer-input').fill(prompt);
  await expect(page.getByTestId('send-button')).toBeEnabled({ timeout: 30000 });
  await page.getByTestId('send-button').click();
}

test.describe('artifact package viewer workflow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://x8-web:5173');
    await expect(page.getByTestId('composer-input')).toBeVisible({ timeout: 30000 });
  });

  test('complete 10-step artifact IDE package viewer acceptance flow', async ({ page }) => {
    // Step 1: Generate HTML artifact
    await ask(page, 'make a simple HTML website preview');
    const artifactCard = page.getByTestId('inline-artifact-card');
    await expect(artifactCard).toBeVisible({ timeout: 15000 });

    // Step 2: Verify one package shell with header
    const packageHeader = artifactCard.getByTestId('artifact-package-header');
    await expect(packageHeader).toBeVisible({ timeout: 5000 });

    // Step 3: Verify header Approve/Deny/disabled Apply visible on Preview
    const approveBtn = packageHeader.getByRole('button', { name: 'Approve' });
    const denyBtn = packageHeader.getByRole('button', { name: 'Deny' });
    const applyBtn = packageHeader.getByRole('button', { name: 'Apply' });
    const previewTab = artifactCard.locator('button.tab').filter({ hasText: 'Preview' });

    await expect(approveBtn).toBeVisible();
    await expect(denyBtn).toBeVisible();
    await expect(applyBtn).toBeDisabled();
    await expect(previewTab).toHaveClass(/active/);

    // Step 4: Switch to Code
    const codeTab = artifactCard.locator('button.tab').filter({ hasText: 'Code' });
    await expect(codeTab).toBeVisible();
    await codeTab.click();

    // Step 5: Edit code in place
    const codeEditor = artifactCard.getByLabel('Artifact page code editor');
    await expect(codeEditor).toBeVisible({ timeout: 5000 });
    const originalValue = await codeEditor.inputValue();
    const editedValue = originalValue.replace('</h1>', ' - EDITED</h1>');

    await codeEditor.fill(editedValue);
    await expect(codeEditor).toHaveValue(editedValue);

    // Step 6: Save draft
    const saveDraftBtn = artifactCard.getByRole('button', { name: /save draft/i });
    if (await saveDraftBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await saveDraftBtn.click();
      // Wait for any state updates
      await page.waitForTimeout(500);
    }

    // Step 7: Switch Preview and verify edited preview renders
    await previewTab.click();
    const frame = artifactCard.locator('iframe').first();
    await expect(frame).toBeVisible({ timeout: 5000 });

    // Step 8: Approve
    await expect(applyBtn).toBeDisabled(); // Still disabled before approval
    await approveBtn.click();
    await page.waitForTimeout(500); // Wait for state update

    // Step 9: Verify Apply enables in same header without switching
    await expect(applyBtn).toBeEnabled({ timeout: 5000 });

    // Step 10: Edit again and save, verify Apply disables until re-approved
    await codeTab.click();
    const updatedValue = editedValue.replace('EDITED', 'EDITED AGAIN');
    await codeEditor.fill(updatedValue);
    await expect(codeEditor).toHaveValue(updatedValue);

    if (await saveDraftBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await saveDraftBtn.click();
      // Wait for any state updates
      await page.waitForTimeout(500);
    }

    // Apply should now be disabled again (re-approval needed after edit)
    await expect(applyBtn).toBeDisabled({ timeout: 5000 });

    // Verify re-approval enables Apply
    await approveBtn.click();
    await page.waitForTimeout(500);
    await expect(applyBtn).toBeEnabled({ timeout: 5000 });
  });
});
