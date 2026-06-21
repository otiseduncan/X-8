export type RequestIntent =
  | 'self_build'
  | 'github'
  | 'file'
  | 'repo'
  | 'diff'
  | 'artifact'
  | 'research'
  | 'image'
  | 'test'
  | 'chat';

const FILE_EXTENSIONS = [
  'py',
  'ts',
  'tsx',
  'js',
  'jsx',
  'json',
  'md',
  'txt',
  'css',
  'html',
  'yaml',
  'yml',
  'toml',
  'env',
  'ini',
  'ps1',
  'sh',
  'dockerfile'
];

export function classifyRequest(text: string): RequestIntent {
  const lower = text.toLowerCase();
  if (isSelfBuildRequest(lower)) return 'self_build';
  if (isGitHubRequest(lower)) return 'github';
  if (isRepoInspectionRequest(lower)) return 'repo';
  if (parseRequestedPath(text, '')) return 'file';
  if (lower.includes('open') && lower.includes('readme')) return 'file';
  if (lower.includes('propose') && (lower.includes('edit') || lower.includes('diff'))) return 'diff';
  if (isArtifactRequest(lower)) return 'artifact';
  if (lower.includes('search') || lower.includes('searxng')) return 'research';
  if (lower.includes('image') || lower.includes('generate picture') || lower.includes('generate image')) return 'image';
  if (lower.includes('test') || lower.includes('testing')) return 'test';
  return 'chat';
}

export function parseRequestedPath(text: string, fallback = 'README.md') {
  const clean = text.trim();
  const quoted = clean.match(/["'`]([^"'`]+\.[A-Za-z0-9]+)["'`]/);
  if (quoted?.[1]) return normalizePathCandidate(quoted[1], fallback);

  const afterVerb = clean.match(/\b(?:open|read|show|inspect|view|load|display|edit)\s+(?:the\s+)?(?:file\s+)?([A-Za-z0-9_./\\:@ -]+\.[A-Za-z0-9]+)\b/i);
  if (afterVerb?.[1]) return normalizePathCandidate(afterVerb[1], fallback);

  const anyPath = clean.match(/\b([A-Za-z0-9_.-]+(?:[\\/][A-Za-z0-9_. -]+)*\.(?:py|ts|tsx|js|jsx|json|md|txt|css|html|yaml|yml|toml|ini|ps1|sh))\b/i);
  if (anyPath?.[1]) return normalizePathCandidate(anyPath[1], fallback);

  if (/\breadme\b/i.test(clean)) return 'README.md';
  return fallback;
}

function normalizePathCandidate(value: string, fallback: string) {
  const trimmed = value
    .trim()
    .replace(/[.,;:!?]+$/g, '')
    .replace(/^\.?[\\/]+/, '')
    .replace(/\\/g, '/');

  if (!trimmed) return fallback;
  if (trimmed.includes('..')) return fallback;

  const ext = trimmed.split('.').pop()?.toLowerCase() || '';
  if (!FILE_EXTENSIONS.includes(ext) && !trimmed.toLowerCase().endsWith('dockerfile')) return fallback;

  return trimmed;
}

export function isRepoInspectionRequest(lower: string) {
  return lower.includes('check the repo')
    || lower.includes('inspect the repo')
    || lower.includes('inspect repo')
    || lower.includes('repo inspection')
    || lower.includes('repo status')
    || lower.includes('scan the repo')
    || lower.includes('scan repo')
    || lower.includes('what is broken in the repo')
    || lower.includes('what broke in the repo');
}

export function isSelfBuildRequest(lower: string) {
  const markers = [
    'create a self-build proposal',
    'self-build proposal',
    'generate a self-build patch',
    'propose a patch',
    'fix chat routing',
    'do not apply the patch until i approve'
  ];
  return markers.some((marker) => lower.includes(marker))
    || lower.includes('self-build')
    || (lower.includes('patch') && lower.includes('do not commit'))
    || (lower.includes('completion rule') && lower.includes('tests'));
}

export function isArtifactRequest(lower: string) {
  return lower.includes('website')
    || lower.includes('preview')
    || lower.includes('html')
    || lower.includes('artifact');
}

export function isGitHubCreateRepoRequest(lower: string) {
  const markers = [
    'create github repo',
    'create a github repo',
    'create repo',
    'create-repo',
    'prepare a github create-repo proposal',
    'prepare repo creation',
    'make a private repo named',
    'new github repository',
    'create a private disposable repo named'
  ];
  return markers.some((marker) => lower.includes(marker));
}

export function isGitHubRequest(lower: string) {
  return lower.includes('check github')
    || lower.includes('github status')
    || lower.includes('github ops')
    || lower.includes('push this repo')
    || lower.includes('push to github')
    || lower.includes('pull latest')
    || lower.includes('pull from github')
    || lower.includes('prepare to push')
    || lower.includes('publish to github')
    || lower.includes('publish this repo')
    || lower.includes('publish this website to github')
    || lower.includes('initialize this as a repo')
    || lower.includes('connect this repo')
    || isGitHubCreateRepoRequest(lower);
}

function firstQuotedValue(text: string) {
  for (const quote of ['"', "'", '`']) {
    const start = text.indexOf(quote);
    if (start < 0) continue;
    const end = text.indexOf(quote, start + 1);
    if (end > start + 1) return text.slice(start + 1, end);
  }
  return '';
}

export function parseGitHubCreateRepo(text: string, configuredOwner: string) {
  const quoted = firstQuotedValue(text);
  const named = text.match(/\bnamed\s+([A-Za-z0-9_.-]+)/i);
  const ownerMatch = text.match(/\bowner\s+([A-Za-z0-9_.-]+)/i) || text.match(/\bunder\s+([A-Za-z0-9_.-]+)/i);
  return {
    repo_name: (quoted || named?.[1] || 'xv8-lab-repo').trim(),
    owner: ownerMatch?.[1] || configuredOwner,
    visibility: /\bpublic\b/i.test(text) ? 'public' : 'private'
  };
}
