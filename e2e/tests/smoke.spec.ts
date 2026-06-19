import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

async function ask(page: Page, message: string) {
  await page.getByTestId('composer-input').fill(message);
  await page.getByTestId('send-button').click();
}

async function openAudioControls(page: Page) {
  const panel = page.getByTestId('avatar-audio-controls-panel');
  if ((await panel.getAttribute('open')) === null) {
    await page.getByTestId('audio-controls-toggle').click();
  }
  return page.getByTestId('avatar-audio-controls');
}

test('assistant mode renders without permanent tool panels', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('[data-theme="neon-blue"]')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Assistant conversation' })).toBeVisible();
  await expect(page.locator('[data-testid="avatar-video"], [data-testid="avatar-fallback"]')).toBeVisible();
  await expect(page.getByTestId('avatar-stage')).toHaveAttribute('data-avatar-state', 'idle');
  await expect(page.getByLabel('Avatar presence')).toBeVisible();
  await expect(page.getByText('State: idle')).toBeVisible();
  await expect(page.getByLabel('Chat timeline')).toBeVisible();
  await expect(page.getByLabel('Message XV8')).toBeVisible();
  await expect(page.getByPlaceholder('Ask XV8 anything...')).toBeVisible();
  await expect(page.getByLabel('Attach file', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Push to talk' })).toBeVisible();
  const controls = await openAudioControls(page);
  await expect(controls.getByTestId('mute-button')).toBeVisible();
  await expect(controls.getByTestId('volume-slider')).toBeVisible();
  await expect(page.getByRole('button', { name: /^Mute$/ })).toHaveCount(0);
  await expect(page.getByRole('button', { name: /^Read aloud$/ })).toHaveCount(0);
  await expect(page.getByRole('button', { name: /^Info/ })).toHaveCount(1);
  await expect(page.getByText('Runtime ready')).toHaveCount(0);
  await expect(page.getByText('Project File Tree')).toHaveCount(0);
  await expect(page.getByText('Full Editor')).toHaveCount(0);
  await expect(page.getByText('SearXNG Panel')).toHaveCount(0);
  await expect(page.getByText('Image Studio')).toHaveCount(0);
});

test('message and transcript copy controls work', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  await page.addInitScript(() => {
    let clipboardText = '';
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: {
        writeText: async (value: string) => {
          clipboardText = value;
        },
        readText: async () => clipboardText
      }
    });
  });
  await page.goto('/');
  await ask(page, 'hello copy check');
  await page.getByTestId('copy-message-button').last().click();
  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toContain('You:\nhello copy check');
  await page.getByTestId('copy-message-button').first().click();
  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toContain('XV8:');
  await page.getByRole('button', { name: /^Info/ }).click();
  await page.getByTestId('copy-transcript-button').last().click();
  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toContain('# XV8 Conversation Transcript');
});

test('avatar audio controls toggle mute and volume', async ({ page }) => {
  await page.goto('/');
  const controls = await openAudioControls(page);
  await controls.getByTestId('mute-button').click();
  await expect(page.getByTestId('avatar-stage')).toHaveAttribute('data-avatar-state', 'muted');
  await controls.getByTestId('volume-slider').fill('35');
  await expect(controls.getByTestId('volume-slider')).toHaveValue('35');
});

test('attachment chip appears before sending', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Attach file input').setInputFiles({
    name: 'notes.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('hello')
  });
  await expect(page.getByLabel('Attached files')).toContainText('notes.txt');
  await expect(page.getByLabel('Attached files')).toContainText(/uploaded|attached/);
});

test('chat loop returns honest model status and restores after refresh', async ({ page }) => {
  await page.goto('/');
  await ask(page, 'hello XV8');
  await expect(page.locator('.message.assistant')).toHaveCount(2, { timeout: 30000 });
  await expect(page.getByText('The assistant model is unavailable right now.')).toHaveCount(0);
  await page.reload();
  await expect(page.getByText('hello XV8')).toBeVisible({ timeout: 90000 });
});

test('chat loop sends uploaded text attachment', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Attach file input').setInputFiles({
    name: 'notes.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('hello from e2e')
  });
  await expect(page.getByLabel('Attached files')).toContainText(/uploaded|attached/);
  await ask(page, 'use this attachment');
  await expect(page.getByText('notes.txt')).toBeVisible();
});

test('inline artifact card renders preview and code tabs', async ({ page }) => {
  await page.goto('/');
  await ask(page, 'simple HTML website preview');
  await expect(page.getByTestId('inline-artifact-card')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Preview', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Code', exact: true })).toBeVisible();
  await expect(page.getByText('Artifact + Website Preview')).toHaveCount(0);
});

test('inline file viewer card renders without file tree on main screen', async ({ page }) => {
  await page.goto('/');
  await ask(page, 'open README.md');
  await expect(page.getByTestId('inline-file-card')).toBeVisible();
  await expect(page.getByLabel('Developer Cockpit Mode')).toHaveCount(0);
});

test('inline diff proposal requires approval before mutation', async ({ page }) => {
  await page.goto('/');
  await ask(page, 'propose a README edit');
  await expect(page.getByTestId('inline-diff-card')).toBeVisible({ timeout: 15000 });
  await expect(page.getByTestId('inline-approval-card')).toBeVisible({ timeout: 15000 });
  await expect(page.getByText(/No mutation has happened/i)).toBeVisible();
});

test('self-build prompt creates plan proposal and approval card without applying', async ({ page }) => {
  await page.goto('/');
  await ask(page, 'create a self-build proposal to add a timestamped validation note to the self-build apply proof file');
  await expect(page.getByText('Self-build prompt detected')).toBeVisible({ timeout: 15000 });
  await expect(page.getByTestId('self-build-patch-plan-text')).toBeVisible();
  await expect(page.getByTestId('self-build-proposal-card')).toHaveCount(1);
  await expect(page.getByTestId('inline-diff-card')).toBeVisible();
  await expect(page.getByTestId('inline-approval-card')).toBeVisible();
});

test('self-build smoke proof applies once and blocks duplicate and stale apply', async ({ page, request }) => {
  const proofPath = 'runtime/self_build_smoke/approved_apply_proof.md';
  await page.goto('/');
  await ask(page, 'create a self-build proposal to add a timestamped validation note to the self-build apply proof file');
  await expect(page.getByText('Self-build prompt detected')).toBeVisible({ timeout: 15000 });
  await expect(page.getByTestId('inline-approval-card')).toBeVisible();
  await expect(page.getByTestId('inline-approval-card')).toContainText(proofPath);
  await page.getByRole('button', { name: /expand self-build patch proposal/i }).click();
  await expect(page.getByTestId('inline-diff-card')).toContainText('self-build approved apply proof');
  await expect(page.getByText(/git push|auto-push|auto push/i)).toHaveCount(0);

  const latest = await (await request.get('/api/self-build/tasks/latest/proposal')).json();
  const detail = latest.data;
  expect(detail.changed_file_paths).toEqual([proofPath]);
  expect(detail.changes[0].unified_diff).toContain('self-build approved apply proof');
  const before = await (await request.post('/api/workspace/read', { data: { path: proofPath } })).json();

  const denied = await (await request.post(`/api/self-build/tasks/${detail.task_id}/apply`, {
    data: { patch_id: detail.patch_id, approval_id: detail.approval_id, patch_hash: detail.patch_hash, approved: false }
  })).json();
  expect(denied.data.applied).toBe(false);
  const afterDenied = await (await request.post('/api/workspace/read', { data: { path: proofPath } })).json();
  expect(afterDenied.data.content).toBe(before.data.content);

  await page.getByTestId('inline-approval-card').getByRole('button', { name: /^Apply$/ }).click();
  await expect(page.getByTestId('inline-approval-card')).toContainText('Patch applied after exact approval hash match.', { timeout: 15000 });
  await expect(page.getByTestId('inline-approval-card')).toContainText(proofPath);
  const afterApproved = await (await request.post('/api/workspace/read', { data: { path: proofPath } })).json();
  expect(afterApproved.data.content).not.toBe(before.data.content);
  expect(afterApproved.data.content).toContain('self-build approved apply proof');

  const duplicate = await (await request.post(`/api/self-build/tasks/${detail.task_id}/apply`, {
    data: { patch_id: detail.patch_id, approval_id: detail.approval_id, patch_hash: detail.patch_hash, approved: true }
  })).json();
  expect(duplicate.status).toBe('blocked');
  expect(duplicate.message).toContain('already applied');

  const staleProposal = await (await request.post('/api/self-build/prompt', {
    data: { prompt: 'create a self-build proposal to add a timestamped validation note to the self-build apply proof file' }
  })).json();
  const staleDetail = staleProposal.data.proposal_detail;
  await request.post('/api/repo/apply-update', { data: { path: proofPath, proposed_content: `${afterApproved.data.content}\nManual stale e2e edit.\n`, approved: true } });
  const stale = await (await request.post(`/api/self-build/tasks/${staleDetail.task_id}/apply`, {
    data: { patch_id: staleDetail.patch_id, approval_id: staleDetail.approval_id, patch_hash: staleDetail.patch_hash, approved: true }
  })).json();
  expect(stale.status).toBe('blocked');
  expect(stale.message).toContain('changed since proposal');

  const trust = await (await request.get('/api/self-build/trust-status')).json();
  expect(trust.data.readiness.approved_apply_proven).toBe(true);
});

test('inline research and image status cards render honestly', async ({ page }) => {
  await page.goto('/');
  await ask(page, 'search with SearXNG for XV8');
  await expect(page.getByTestId('inline-research-card')).toBeVisible({ timeout: 15000 });
  await expect(page.getByText('SearXNG Panel')).toHaveCount(0);

  await ask(page, 'generate an image of a console');
  await expect(page.locator('[data-testid="inline-image-card"], [data-testid="inline-error-card"]')).toBeVisible({ timeout: 15000 });
  await expect(page.getByText('Image Studio')).toHaveCount(0);
});

test('Brain auto-capture saves deduplicates gates secrets and respects toggle', async ({ page, request }) => {
  test.setTimeout(90000);
  const stamp = Date.now().toString();
  await request.post('/api/brain/auto-capture/toggle', { data: { enabled: true } });

  await page.goto('/');
  await ask(page, `I prefer direct senior-engineer answers ${stamp}.`);
  await expect(page.getByText('Memory saved').last()).toBeVisible({ timeout: 30000 });
  let memories = await (await request.get(`/api/brain/memories?q=${stamp}&include_deleted=true`)).json();
  expect(memories.data.filter((item: Record<string, unknown>) => String(item.summary).includes(stamp) && item.active).length).toBe(1);

  await ask(page, `I prefer direct senior-engineer answers ${stamp}.`);
  await expect(page.getByText('Already remembered').last()).toBeVisible({ timeout: 30000 });
  memories = await (await request.get(`/api/brain/memories?q=${stamp}&include_deleted=true`)).json();
  expect(memories.data.filter((item: Record<string, unknown>) => String(item.summary).includes(stamp) && item.active).length).toBe(1);

  await ask(page, `Actually, I prefer short direct answers unless we are debugging ${stamp}.`);
  await expect(page.getByText('Memory updated').last()).toBeVisible({ timeout: 30000 });

  const sensitive = `my family history includes e2e pending ${stamp}`;
  await ask(page, sensitive);
  await expect(page.getByText('Memory pending approval').last()).toBeVisible({ timeout: 30000 });
  const pending = await (await request.get(`/api/brain/memories?status_filter=pending&q=${stamp}`)).json();
  const pendingMemory = pending.data.find((item: Record<string, unknown>) => String(item.summary).includes(sensitive));
  expect(pendingMemory).toBeTruthy();
  await request.post(`/api/brain/memories/${pendingMemory.id}/approve`, { data: {} });
  const retrieved = await (await request.post('/api/brain/retrieve', { data: { query: sensitive } })).json();
  expect(retrieved.message).toContain('family history');

  await ask(page, `my GitHub token is ghp_secret_${stamp}`);
  await expect(page.getByText('Memory blocked').last()).toBeVisible({ timeout: 30000 });
  await expect(page.getByText(`ghp_secret_${stamp}`)).toHaveCount(0);

  await request.post('/api/brain/auto-capture/toggle', { data: { enabled: false } });
  await ask(page, `I prefer disabled auto capture ${stamp}.`);
  const disabled = await (await request.get(`/api/brain/memories?q=disabled auto capture ${stamp}`)).json();
  expect(disabled.data).toHaveLength(0);
  await request.post('/api/brain/remember', { data: { content: `I prefer manual while disabled ${stamp}` } });
  const manual = await (await request.get(`/api/brain/memories?q=manual while disabled ${stamp}`)).json();
  expect(manual.data.length).toBeGreaterThan(0);
  await request.post('/api/brain/auto-capture/toggle', { data: { enabled: true } });
});
