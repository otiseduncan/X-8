import { fireEvent, render, screen } from '@testing-library/react';
import { expect, test, vi } from 'vitest';
import { AvatarStage, selectAvatarAsset } from '../app/AssistantComponents';

test('avatar manifest maps states to the expected video assets', () => {
  const manifest = {
    version: '1.0',
    defaultAvatar: 'xoduz',
    assets: [
      { id: 'idle', label: 'Idle', type: 'video', src: '/avatar/xoduz-idle.mp4', states: ['idle'], loop: true, muted: true },
      { id: 'thinking', label: 'Thinking', type: 'video', src: '/avatar/xoduz-thinking.mp4', states: ['thinking', 'listening'], loop: true, muted: true },
      { id: 'speaking', label: 'Speaking', type: 'video', src: '/avatar/xoduz-speaking.mp4', states: ['speaking'], loop: true, muted: true }
    ],
    fallback: { type: 'generated', label: 'Fallback X avatar', src: '/avatar/fallback.svg' }
  };
  expect(selectAvatarAsset(manifest, 'idle')?.src).toBe('/avatar/xoduz-idle.mp4');
  expect(selectAvatarAsset(manifest, 'listening')?.src).toBe('/avatar/xoduz-thinking.mp4');
  expect(selectAvatarAsset(manifest, 'thinking')?.src).toBe('/avatar/xoduz-thinking.mp4');
  expect(selectAvatarAsset(manifest, 'speaking')?.src).toBe('/avatar/xoduz-speaking.mp4');
  expect(selectAvatarAsset(manifest, 'error')?.src).toBe('/avatar/xoduz-idle.mp4');
});

test('avatar falls back if the active video fails to load', async () => {
  vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({
    ok: true,
    json: () => Promise.resolve({
      version: '1.0',
      defaultAvatar: 'xoduz',
      assets: [{ id: 'idle', label: 'Idle', type: 'video', src: '/avatar/xoduz-idle.mp4', states: ['idle'], loop: true, muted: true }],
      fallback: { type: 'generated', label: 'Fallback X avatar', src: '/avatar/fallback.svg' }
    })
  })));
  render(<AvatarStage state="idle" />);
  const video = await screen.findByTestId('avatar-video');
  fireEvent.error(video);
  expect(await screen.findByTestId('avatar-fallback')).toBeInTheDocument();
  vi.unstubAllGlobals();
});
