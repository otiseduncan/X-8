import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import { DeveloperCockpit } from '../app/DeveloperCockpit';

vi.mock('../components/cockpit/CodeEditor', () => ({
  CodeEditor: ({ value }: { value: string }) => <pre aria-label="Code editor">{value}</pre>
}));

vi.mock('../services/apiClient', () => ({
  previewProjectBuild: vi.fn(() => Promise.resolve({
    status: 'preview',
    data: {
      status: 'preview',
      plan: {
        output_path: '/workspace/runtime/generated-projects/v8-release-proof-project',
        manifest_hash: 'manifest_hash_1',
        files: [{ path: 'manifest.json' }, { path: 'README.md' }, { path: 'index.html' }]
      }
    }
  })),
  writeProjectBuild: vi.fn(() => Promise.resolve({
    status: 'written',
    data: {
      status: 'written',
      plan: {
        output_path: '/workspace/runtime/generated-projects/v8-release-proof-project',
        manifest_hash: 'manifest_hash_1',
        files: [{ path: 'manifest.json' }, { path: 'README.md' }, { path: 'index.html' }]
      }
    }
  })),
  approveBrainMemory: vi.fn(),
  createContinuityHandoff: vi.fn(() => Promise.resolve({ data: { handoff: 'Handoff note' }, message: 'ok' })),
  createContinuityTask: vi.fn(),
  deleteBrainMemory: vi.fn(),
  loadBrainCandidates: vi.fn(() => Promise.resolve({ data: [] })),
  loadBrainEmbeddingStatus: vi.fn(() => Promise.resolve({ data: {} })),
  loadBrainEvents: vi.fn(() => Promise.resolve({ data: [] })),
  loadBrainIdentityRecords: vi.fn(() => Promise.resolve({ data: [] })),
  loadBrainMemories: vi.fn(() => Promise.resolve({ data: [] })),
  loadContinuityRecords: vi.fn(() => Promise.resolve({ data: [] })),
  loadContinuityStatus: vi.fn(() => Promise.resolve({ data: {} })),
  reactivateBrainMemory: vi.fn(),
  rejectBrainMemory: vi.fn(),
  reindexBrainMemories: vi.fn(),
  retrieveBrainMemory: vi.fn(() => Promise.resolve({ status: 'passed', message: 'ok', data: { memories: [], retrieval_proof: {} } })),
  seedBrainIdentityRecords: vi.fn(() => Promise.resolve({ data: { count: 0, created: 0, updated: 0, skipped: 0, records: [] } })),
  toggleBrainAutoCapture: vi.fn(() => Promise.resolve({ data: { auto_capture_enabled: true } })),
  updateBrainFocus: vi.fn(),
  updateBrainMemory: vi.fn(),
  updateContinuityRecord: vi.fn()
}));

afterEach(() => cleanup());

test('Project Builder panel previews and writes approved sandbox projects', async () => {
  render(<DeveloperCockpit {...props()} />);
  expect(screen.getByText('Project Builder')).toBeInTheDocument();
  expect(screen.getByText('no_preview')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /preview manifest/i }));
  expect(await screen.findByText('manifest_hash_1')).toBeInTheDocument();
  expect(screen.getByText(/manifest\.json, README\.md, index\.html/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /write approved sandbox/i }));
  await waitFor(() => expect(screen.getByText('written')).toBeInTheDocument());
});

function props() {
  return {
    files: [{ path: 'README.md' }],
    selectedPath: 'README.md',
    setSelectedPath: vi.fn(),
    proposal: null,
    code: '# XV8',
    setCode: vi.fn(),
    proposeDiffCard: vi.fn(),
    requestApply: vi.fn(),
    searchStatus: 'unavailable',
    imageStatus: 'unavailable',
    selfBuildTrustSummary: 'ready',
    selfBuildTrustStatus: {},
    modelDetails: {},
    memoryStatus: 'ready',
    memoryDetails: {},
    brainDetails: {},
    team: [],
    capabilities: [],
    integrations: [],
    githubStatus: 'not_configured',
    dockerPresets: [],
    githubAuth: {},
    githubOps: {},
    githubOpsResult: 'No GitHub op run yet.',
    refreshGitHubOps: vi.fn(),
    previewGitHubOp: vi.fn(),
    appendMessage: vi.fn(),
    githubApprovalCard: vi.fn(),
    nowId: () => 'id',
    bridgeStatus: 'unreachable',
    localSystemStatus: {},
    x7ImportStatus: 'unknown',
    x6ImportStatus: 'unknown',
    legacySignals: 'none',
    importStatus: 'unknown',
    submitConfigScan: vi.fn(),
    muted: false,
    micStatus: 'permission_required',
    voiceStatus: 'ready',
    voiceName: 'Test voice',
    volume: 80,
    changeVolume: vi.fn(),
    toggleMute: vi.fn(),
    readAloud: vi.fn(),
    startMicrophone: vi.fn(),
    audioReceipts: []
  };
}
