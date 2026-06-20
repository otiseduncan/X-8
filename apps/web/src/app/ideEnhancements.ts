const CODE_SELECTOR = 'pre.codeBlock:not([data-x8-enhanced="true"]), pre.diff:not([data-x8-enhanced="true"])';
const APPROVAL_SELECTOR = '.inlineCard.approval:not([data-x8-approval-enhanced="true"])';

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

function enhanceCodeBlock(pre: HTMLPreElement) {
  const source = pre.textContent || '';
  const isDiff = pre.classList.contains('diff');
  pre.dataset.x8Enhanced = 'true';
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
  document.querySelectorAll<HTMLElement>(APPROVAL_SELECTOR).forEach(enhanceApprovalCard);
}

if (typeof window !== 'undefined') {
  window.addEventListener('DOMContentLoaded', enhanceDom);
  const observer = new MutationObserver(() => enhanceDom());
  observer.observe(document.documentElement, { childList: true, subtree: true });
}
