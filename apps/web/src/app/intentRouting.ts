export function classifyRequest(text: string) {
  const lower = text.toLowerCase();
  if (isProjectBuilderRequest(lower)) return 'project_builder';
  if (isSelfBuildRequest(lower)) return 'self_build';
  if (lower.includes('open') && lower.includes('readme')) return 'file';
  if (lower.includes('propose') && (lower.includes('edit') || lower.includes('diff'))) return 'diff';
  if (lower.includes('website') || lower.includes('preview') || lower.includes('html')) return 'artifact';
  if (lower.includes('search') || lower.includes('searxng')) return 'research';
  if (lower.includes('image') || lower.includes('generate')) return 'image';
  if (isGitHubRequest(lower)) return 'github';
  if (/\btests?\b|\btesting\b/.test(lower)) return 'test';
  return 'chat';
}

export function isProjectBuilderRequest(lower: string) {
  if (lower.includes('self-build') || lower.includes('self build')) return false;
  const buildMarkers = ['build', 'create', 'generate', 'scaffold', 'write'];
  const projectMarkers = ['v8 project builder', 'project builder', 'real project', 'generated project', 'project output path', 'project folder name'];
  return buildMarkers.some((marker) => lower.includes(marker)) && projectMarkers.some((marker) => lower.includes(marker));
}

export function parseProjectBuilderName(text: string) {
  const folder = text.match(/project folder name:\s*([A-Za-z0-9_.-]+)/i);
  if (folder?.[1]) return folder[1].trim();
  const name = text.match(/project name:\s*([^\n\r]+)/i);
  return (name?.[1] || 'x8-generated-project').trim();
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
    || lower.includes('pull latest')
    || lower.includes('prepare to push')
    || lower.includes('initialize this as a repo')
    || lower.includes('connect this repo')
    || isGitHubCreateRepoRequest(lower);
}

export function parseGitHubCreateRepo(text: string, configuredOwner: string) {
  const quoted = text.match(/[`'"]([^`'"]+)[`'"]/);
  const named = text.match(/\bnamed\s+([A-Za-z0-9_.-]+)/i);
  const ownerMatch = text.match(/\bowner\s+([A-Za-z0-9_.-]+)/i) || text.match(/\bunder\s+([A-Za-z0-9_.-]+)/i);
  return {
    repo_name: (quoted?.[1] || named?.[1] || 'xv8-lab-repo').trim(),
    owner: ownerMatch?.[1] || configuredOwner,
    visibility: /\bpublic\b/i.test(text) ? 'public' : 'private'
  };
}
