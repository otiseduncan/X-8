export function classifyRequest(text: string) {
  const lower = text.toLowerCase();
  if (isSelfBuildRequest(lower)) return 'self_build';
  if (isGitHubRequest(lower)) return 'github';
  if (lower.includes('open') && lower.includes('readme')) return 'file';
  if (lower.includes('propose') && (lower.includes('edit') || lower.includes('diff'))) return 'diff';
  if (isArtifactRequest(lower)) return 'artifact';
  if (lower.includes('search') || lower.includes('searxng')) return 'research';
  if (lower.includes('image') || lower.includes('generate')) return 'image';
  if (lower.includes('test') || lower.includes('testing')) return 'test';
  return 'chat';
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

export function parseGitHubCreateRepo(text: string, configuredOwner: string) {
  const named = text.match(/\bnamed\s+([A-Za-z0-9_.-]+)/i);
  const ownerMatch = text.match(/\bowner\s+([A-Za-z0-9_.-]+)/i) || text.match(/\bunder\s+([A-Za-z0-9_.-]+)/i);
  return {
    repo_name: (named?.[1] || 'xv8-lab-repo').trim(),
    owner: ownerMatch?.[1] || configuredOwner,
    visibility: /\bpublic\b/i.test(text) ? 'public' : 'private'
  };
}
