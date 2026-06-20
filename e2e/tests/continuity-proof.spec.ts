import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

async function ask(page: Page, message: string) {
  await page.getByTestId('composer-input').fill(message);
  await page.getByTestId('send-button').click();
}

test('Brain continuity proof saves validation and handoff without fragile transcript wait', async ({ page, request }) => {
  test.setTimeout(120000);
  const stamp = Date.now().toString();

  await page.goto('/');
  await ask(page, `we are working on Brain V1 Phase 5 ${stamp}`);
  await expect(page.getByText(`Saved current project state: Brain V1 Phase 5 ${stamp}.`).first()).toBeVisible({ timeout: 30000 });

  await ask(page, `the next step is Phase 5 validation ${stamp}`);
  await expect(page.getByText(`Saved next step: Phase 5 validation ${stamp}.`).first()).toBeVisible({ timeout: 30000 });

  await ask(page, `the blocker is no live browser connector ${stamp}`);
  await expect(page.getByText(`Saved blocker: no live browser connector ${stamp}.`).first()).toBeVisible({ timeout: 30000 });

  const validation = await (await request.post('/api/brain/continuity/checkpoints', {
    data: { summary: `Phase 4 with 139 API tests passing ${stamp}`, global_scope: true }
  })).json();
  expect(validation.status).toBe('passed');
  expect(validation.message).toBe(`Saved validation checkpoint: Phase 4 with 139 API tests passing ${stamp}.`);

  await ask(page, 'what is the next step?');
  await expect(page.getByText(`Next step: Phase 5 validation ${stamp}.`).first()).toBeVisible({ timeout: 30000 });

  await ask(page, 'what is blocked?');
  await expect(page.getByText(`Current blocker: no live browser connector ${stamp}.`).first()).toBeVisible({ timeout: 30000 });

  const handoff = await (await request.post('/api/brain/continuity/handoff', { data: {} })).json();
  expect(handoff.data.handoff).toContain('Handoff note:');
  expect(handoff.data.handoff).toContain(`Phase 4 with 139 API tests passing ${stamp}`);

  await page.getByRole('button', { name: /^Info/ }).click();
  await page.getByRole('button', { name: /settings/i }).click();
  await expect(page.getByLabel('Continuity panel')).toContainText(`Brain V1 Phase 5 ${stamp}`);
});
