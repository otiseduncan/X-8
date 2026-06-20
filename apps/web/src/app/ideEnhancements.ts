const CODE_SELECTOR = 'pre.codeBlock:not([data-x8-enhanced="true"]), pre.diff:not([data-x8-enhanced="true"])';
const APPROVAL_SELECTOR = '.inlineCard.approval:not([data-x8-approval-enhanced="true"])';
const ARTIFACT_SELECTOR = '.inlineCard.artifact:not([data-x8-artifact-enhanced="true"])';

function appendToken(parent: HTMLElement, text: string, className = '') {
  if (!text) return;
  const span = document.createElement('span');
  span.textContent = text;
  if (className) span.className = className;
  parent.appendChild(span);
}

function tokenClass(token: string) {
  if (/^<!--/.test(token) || /^\/\//.test(token) || /^#(?![0-9a-fA-F]{3,8}\b)/.test(token)) return 'x8TokComment';
  if (/^<\/?[A-Za-z]/.test(token)) return 'x8TokTag';
  if (/^['"]/.test(token)) return 'x8TokString';
  if (/^#[0-9a-fA-F]{3,8}$/.test(token)) return 'x8TokColor';
  if (/^\b(?:const|let|var|function|return|class|import|export|from|if|else|async|await|type|interface|def|try|catch|for|while|True|False|None)\b/.test(token)) return 'x8TokKeyword';
  if (/^[a-zA-Z-]+(?=\s*:)/.test(token)) return 'x8TokProperty';
  if (/^\d/.test(token)) return 'x8TokNumber';
  return '';
}

function renderTokens(parent: HTMLElement, line: string) {
  const tokenPattern = /(<!--.*?-->|<\/?[A-Za-z][^>]*>|"[^"\n]*"|'[^'\n]*'|\b(?:const|let|var|function|return|class|import|export|from|if|else|async|await|type|interface|def|try|catch|for|while|True|False|None)\b|#[0-9a-fA-F]{3,8}\b|\b\d+(?:\.\d+)?(?:px|rem|em|%)?\b|[a-zA-Z-]+(?=\s*:))/g;
  let index = 0;
  for (const match of line.matchAll(tokenPattern)) {
    const token = match[0];
    const start = match.index || 0;
    appendToken(parent, line.slice(index, start));
    appendToken(parent, token, tokenClass(token));
    index = start + token.length;
  }
  appendToken(parent, line.slice(index));
}

function renderCodeLines(pre: HTMLPreElement, source: string) {
  const isDiff = pre.classList.contains('diff');
  pre.dataset.x8Enhanced = 'true';
  pre.dataset.x8Source = source;
  pre.textContent = '';
  const lines = source.split(/\r?\n/);
  lines.forEach((line, lineIndex) => {
    const row = document.createElement('div');
    row.className = 'x8CodeLine';
    if (isDiff && line.startsWith('+')) row.classList.add('added');
    if (isDiff && line.startsWith('-')) row.classList.add('removed');
    if (isDiff && line.startsWith('@@')) row.classList.add('hunk');

    const gutter = document.createElement('span');
    gutter.className = 'x8LineNumber';
    gutter.textContent = String(lineIndex + 1);

    const content = document.createElement('span');
    content.className = 'x8LineContent';
    if (isDiff && line.length > 0) {
      appendToken(content, line.slice(0, 1), line.startsWith('+') ? 'x8TokAdded' : line.startsWith('-') ? 'x8TokRemoved' : '');
      renderTokens(content, line.slice(1));
    } else {
      renderTokens(content, line);
    }

    row.append(gutter, content);
    pre.appendChild(row);
  });
}

function enhanceCodeBlock(pre: HTMLPreElement) {
  const source = pre.dataset.x8Source || pre.textContent || '';
  renderCodeLines(pre, source);
}

function downloadText(filename: string, content: string, type = 'text/html') {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function artifactSource(card: HTMLElement) {
  const iframe = card.querySelector<HTMLIFrameElement>('iframe');
  const code = card.querySelector<HTMLPreElement>('pre.codeBlock');
  const source = code?.dataset.x8Source || iframe?.getAttribute('srcdoc') || code?.textContent || '';
  return source.trim();
}

function setArtifactSource(card: HTMLElement, source: string) {
  card.dataset.x8ArtifactSource = source;
  const iframe = card.querySelector<HTMLIFrameElement>('iframe');
  if (iframe) iframe.srcdoc = source;
  const code = card.querySelector<HTMLPreElement>('pre.codeBlock');
  if (code) renderCodeLines(code, source);
}

function enhanceArtifactCard(card: HTMLElement) {
  card.dataset.x8ArtifactEnhanced = 'true';
  card.classList.add('x8ArtifactPackage');

  const header = card.querySelector<HTMLElement>('.inlineCardHeader');
  if (header && !card.querySelector('.x8PackageBadge')) {
    const badge = document.createElement('span');
    badge.className = 'x8PackageBadge';
    badge.textContent = 'Package viewer';
    header.appendChild(badge);
  }

  const actions = card.querySelector<HTMLElement>(':scope > .cardBody .inlineActions');
  if (!actions) return;

  const sourceForExport = () => card.dataset.x8ArtifactSource || artifactSource(card);
  const existingButtons = Array.from(actions.querySelectorAll<HTMLButtonElement>('button'));
  existingButtons.forEach((button) => {
    const label = button.textContent?.trim().toLowerCase() || '';
    if (label === 'apply') {
      button.remove();
      return;
    }
    if (label === 'export') {
      button.addEventListener('click', () => {
        const source = sourceForExport();
        if (!source) return;
        downloadText('xv8-artifact-preview.html', source, 'text/html');
      });
    }
  });

  if (!actions.querySelector('.x8EditArtifactButton')) {
    const edit = document.createElement('button');
    edit.type = 'button';
    edit.className = 'chipButton x8EditArtifactButton';
    edit.textContent = 'Edit';
    edit.addEventListener('click', () => {
      let editor = card.querySelector<HTMLTextAreaElement>('textarea.x8ArtifactEditor');
      if (!editor) {
        editor = document.createElement('textarea');
        editor.className = 'x8ArtifactEditor';
        editor.spellcheck = false;
        editor.value = sourceForExport();
        actions.parentElement?.insertBefore(editor, actions);
      }
      editor.hidden = !editor.hidden;
      if (!editor.hidden) editor.focus();
    });
    actions.prepend(edit);
  }

  if (!actions.querySelector('.x8RefreshPreviewButton')) {
    const refresh = document.createElement('button');
    refresh.type = 'button';
    refresh.className = 'chipButton x8RefreshPreviewButton';
    refresh.textContent = 'Refresh preview';
    refresh.addEventListener('click', () => {
      const editor = card.querySelector<HTMLTextAreaElement>('textarea.x8ArtifactEditor');
      if (!editor) return;
      setArtifactSource(card, editor.value);
    });
    actions.insertBefore(refresh, actions.children[1] || null);
  }

  if (!actions.querySelector('.x8ProposeArtifactButton')) {
    const propose = document.createElement('button');
    propose.type = 'button';
    propose.className = 'chipButton x8ProposeArtifactButton';
    propose.textContent = 'Propose apply';
    propose.addEventListener('click', () => {
      card.classList.add('x8ProposalRequested');
      let note = card.querySelector<HTMLElement>('.x8PackageNote');
      if (!note) {
        note = document.createElement('span');
        note.className = 'x8PackageNote';
        actions.appendChild(note);
      }
      note.textContent = 'Proposal requested. Apply still requires an approval card.';
    });
    actions.appendChild(propose);
  }
}

function enhanceApprovalCard(card: HTMLElement) {
  card.dataset.x8ApprovalEnhanced = 'true';
  const actions = card.querySelector<HTMLElement>(':scope > .inlineActions');
  if (!actions) return;

  const buttons = Array.from(actions.querySelectorAll<HTMLButtonElement>('button'));
  const realApply = buttons.find((button) => button.textContent?.trim() === 'Apply');
  if (realApply) {
    realApply.dataset.x8RealApply = 'true';
    realApply.classList.add('x8RealApplyButton');
    realApply.style.display = 'none';
  }

  const approve = document.createElement('button');
  approve.type = 'button';
  approve.className = 'chipButton x8ApproveButton';
  approve.textContent = 'Approve';
  approve.addEventListener('click', () => {
    card.dataset.x8Approved = 'true';
    card.classList.remove('x8Denied');
    card.classList.add('x8Approved');
    if (realApply) {
      realApply.style.display = '';
      realApply.textContent = realApply.textContent?.trim() === 'Applying' ? 'Applying' : 'Apply approved patch';
      realApply.focus();
    }
  });

  const deny = document.createElement('button');
  deny.type = 'button';
  deny.className = 'chipButton x8DenyButton';
  deny.textContent = 'Deny';
  deny.addEventListener('click', () => {
    card.dataset.x8Approved = 'false';
    card.classList.remove('x8Approved');
    card.classList.add('x8Denied');
    if (realApply) realApply.style.display = 'none';
  });

  actions.append(approve, deny);
  if (!realApply) {
    const note = document.createElement('span');
    note.className = 'x8ApprovalNote';
    note.textContent = 'No applyable patch is available yet.';
    actions.append(note);
  }
}

function enhanceDom() {
  document.querySelectorAll<HTMLPreElement>(CODE_SELECTOR).forEach(enhanceCodeBlock);
  document.querySelectorAll<HTMLElement>(ARTIFACT_SELECTOR).forEach(enhanceArtifactCard);
  document.querySelectorAll<HTMLElement>(APPROVAL_SELECTOR).forEach(enhanceApprovalCard);
}

if (typeof window !== 'undefined') {
  window.addEventListener('DOMContentLoaded', enhanceDom);
  const observer = new MutationObserver(() => enhanceDom());
  observer.observe(document.documentElement, { childList: true, subtree: true });
}