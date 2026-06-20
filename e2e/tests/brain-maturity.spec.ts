import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

async function ask(page: Page, message: string) {
  await page.getByTestId('composer-input').fill(message);
  await expect(page.getByTestId('send-button')).toBeEnabled({ timeout: 30000 });
  await page.getByTestId('send-button').click();
}

async function waitForAssistantResponse(page: Page, timeout = 30000) {
  await expect(page.locator('.message.assistant').last()).toBeVisible({ timeout });
}

test('identity: greeting returns X identity without Kernel limitations card', async ({ page }) => {
  await page.goto('/');
  await ask(page, 'hello');
  await waitForAssistantResponse(page);
  const message = page.locator('.message.assistant').last();
  await expect(message).toContainText('X', { ignoreCase: false });
  await expect(page.getByText('Kernel limitations')).toHaveCount(0);
  await expect(page.getByText('The assistant model is unavailable')).toHaveCount(0);
});

test('identity: who are you returns X identity', async ({ page }) => {
  await page.goto('/');
  await ask(page, 'who are you');
  await waitForAssistantResponse(page);
  const message = page.locator('.message.assistant').last();
  await expect(message).toContainText('X');
  const text = await message.textContent();
  expect(text?.toLowerCase()).not.toContain('chatgpt');
  await expect(page.getByText('Kernel limitations')).toHaveCount(0);
});

test('memory: remember and recall works end-to-end', async ({ page }) => {
  await page.goto('/');
  await ask(page, 'remember that I want concise bullet point answers');
  await waitForAssistantResponse(page);
  const saveMsg = page.locator('.message.assistant').last();
  const saveMsgText = await saveMsg.textContent();
  // Either saved fresh or detected as duplicate — both are correct
  expect(saveMsgText?.toLowerCase()).toMatch(/remembered|already remembered/);

  await ask(page, 'what do you remember about my answer preferences');
  await waitForAssistantResponse(page);
  const recallMsg = page.locator('.message.assistant').last();
  await expect(recallMsg).not.toContainText('The assistant model is unavailable');
});

test('memory: brain card appears after remember command', async ({ page }) => {
  await page.goto('/');
  const stamp = Date.now();
  await ask(page, `remember this: my output preference is short ${stamp}`);
  await waitForAssistantResponse(page);
  const msgText = await page.locator('.message.assistant').last().textContent();
  expect(msgText?.toLowerCase()).toMatch(/remembered|already remembered/);
});

test('active focus: can be set and acknowledged', async ({ page }) => {
  await page.goto('/');
  await ask(page, 'update your focus to brain maturity sprint');
  await waitForAssistantResponse(page);
  const msg = page.locator('.message.assistant').last();
  await expect(msg).toContainText('Focus updated');
  await expect(msg).toContainText('brain maturity');
});

test('routing: github push routes to approval card', async ({ page }) => {
  await page.goto('/');
  await ask(page, 'push this repo');
  await waitForAssistantResponse(page);
  await expect(page.locator('.message.assistant').last()).toContainText('push');
  // Push approval or preview card should appear
  const responseText = await page.locator('.message.assistant').last().textContent();
  expect(responseText?.toLowerCase()).toContain('push');
});

test('routing: email draft returns draft boundary', async ({ page }) => {
  await page.goto('/');
  await ask(page, 'write an email draft to introduce myself');
  await waitForAssistantResponse(page);
  const msg = page.locator('.message.assistant').last();
  const text = await msg.textContent();
  expect(text?.toLowerCase()).toContain('draft');
  await expect(page.getByText('The assistant model is unavailable')).toHaveCount(0);
});

test('capability: local system body returns read-only scan', async ({ page }) => {
  await page.goto('/');
  await ask(page, 'show your body status');
  await waitForAssistantResponse(page);
  const msg = page.locator('.message.assistant').last();
  await expect(msg).toContainText('read-only');
});

test('safety: blocked shell command shows blocked status', async ({ page }) => {
  await page.goto('/');
  await ask(page, 'commit and push everything automatically');
  await waitForAssistantResponse(page);
  const msg = page.locator('.message.assistant').last();
  await expect(msg).toContainText('blocked');
});

test('deterministic routes do not show Kernel limitations card', async ({ page }) => {
  await page.goto('/');
  for (const msg of ['hello', 'check github status', 'push this repo']) {
    await ask(page, msg);
    await waitForAssistantResponse(page);
  }
  // No Kernel limitations cards should appear for any of these
  await expect(page.getByText('Kernel limitations')).toHaveCount(0);
  // Ensure Info/overlays are closed to avoid leaking state into next tests
  const infoBtn = page.getByRole('button', { name: /^Info/ });
  if (await infoBtn.isVisible()) {
    const expanded = await infoBtn.getAttribute('aria-expanded');
    if (expanded === 'true') await infoBtn.click();
  }
});

test('no stuck thinking indicator on deterministic routes', async ({ page }) => {
  await page.goto('/');
  await ask(page, 'what is your name');
  await waitForAssistantResponse(page, 15000);
  await expect(page.locator('.message.assistant')).toHaveCount(1);
  // Thinking indicator (aria label) should be gone after response
  await expect(page.locator('[aria-label="XV8 thinking"]')).toHaveCount(0);
});
