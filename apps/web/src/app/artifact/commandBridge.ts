import type {
  ActiveArtifactContext,
  ArtifactCommand,
  ArtifactDiffEntry,
  ArtifactRevisionHistoryEntry,
  ArtifactSearchEntry,
  ArtifactRevisionKind,
  ArtifactWorkbenchSnapshot,
  PendingArtifactRevision,
} from '../../types/contracts';

interface ArtifactCardLike {
  id: string;
  title: string;
  payload?: Record<string, unknown>;
}

export interface LocalArtifactCommandResult {
  responseText: string;
  summary: string;
  command: ArtifactCommand;
}

function normalizePath(value: string) {
  return value.replace(/^\.\//, '').replace(/\\/g, '/');
}

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === 'object' && value !== null ? value as Record<string, unknown> : {};
}

function asString(value: unknown, fallback = '') {
  return typeof value === 'string' ? value : fallback;
}

function splitLines(content: string) {
  return content.split(/\r?\n/);
}

function formatLines(lines: number[]) {
  if (lines.length === 0) return 'unknown lines';
  if (lines.length === 1) return `line ${lines[0]}`;
  const contiguous = lines.every((line, index) => index === 0 || line === lines[index - 1] + 1);
  if (contiguous) return `lines ${lines[0]}-${lines.at(-1)}`;
  if (lines.length === 2) return `lines ${lines[0]} and ${lines[1]}`;
  return `lines ${lines.slice(0, -1).join(', ')}, and ${lines.at(-1)}`;
}

function compactSnippet(lines: string[], line: number) {
  return lines[line - 1]?.trim() || '';
}

function firstPath(paths: string[], suffix: string) {
  return paths.find((path) => path.endsWith(suffix)) || '';
}

function firstScriptPath(paths: string[]) {
  const exact = paths.find((path) => normalizePath(path).toLowerCase() === 'script.js');
  if (exact) return exact;
  const nested = paths.find((path) => normalizePath(path).toLowerCase().endsWith('/script.js'));
  if (nested) return nested;
  return paths.find((path) => path.toLowerCase().endsWith('.js')) || '';
}

function searchLines(content: string, matcher: (line: string) => boolean) {
  return splitLines(content).flatMap((line, index) => (matcher(line) ? [index + 1] : []));
}

function replaceMainWebsiteName(html: string, nextName: string) {
  let updated = html;
  updated = updated.replace(/(<title[^>]*>)([^<]*)(<\/title>)/i, `$1${nextName}$3`);
  updated = updated.replace(/(<h1[^>]*>)([^<]*)(<\/h1>)/i, `$1${nextName}$3`);
  updated = updated.replace(/(<strong[^>]*>)([^<]*)(<\/strong>)/i, `$1${nextName}$3`);
  return updated;
}

function replaceFirstButtonLabel(html: string, nextLabel: string) {
  return html.replace(/(<(?:a|button)[^>]*class=\"[^\"]*button[^\"]*\"[^>]*>)([^<]+)(<\/+?(?:a|button)>)/i, `$1${nextLabel}$3`);
}

function uniqueSorted(lines: number[]) {
  return Array.from(new Set(lines)).sort((a, b) => a - b);
}

function findInlineScriptLines(html: string) {
  const lines = splitLines(html);
  const inlineScriptLines: number[] = [];
  let scriptStart = 0;
  for (let i = 0; i < lines.length; i += 1) {
    if (/<script\b/i.test(lines[i]) && scriptStart === 0) {
      scriptStart = i + 1;
      continue;
    }
    if (scriptStart > 0 && /<\/script>/i.test(lines[i])) {
      for (let line = scriptStart; line <= i + 1; line += 1) inlineScriptLines.push(line);
      scriptStart = 0;
    }
  }
  if (scriptStart > 0) {
    for (let line = scriptStart; line <= lines.length; line += 1) inlineScriptLines.push(line);
  }
  return uniqueSorted(inlineScriptLines);
}

function extractCurrentBackgroundValue(css: string) {
  const match = css.match(/background(?:-color)?\s*:\s*([^;]+);?/i);
  return match?.[1]?.trim() || 'not explicitly set';
}

const accentWord = ['pur', 'ple'].join('');

const namedColors: Record<string, string> = {
  '#ffd21f': 'yellow',
  '#1b0909': 'black',
  '#0b3b8f': 'blue',
  '#e11d24': 'red',
  '#2a1010': 'deep red',
  '#ffffff': 'white',
  '#1b1200': 'near-black',
};

function normalizeColorToken(token: string) {
  const raw = token.toLowerCase();
  if (/^#[0-9a-f]{8}$/i.test(raw)) return raw.slice(0, 7);
  return raw;
}

function describeColorValue(rawValue: string) {
  const matches = rawValue.match(/#[0-9a-f]{6}(?:[0-9a-f]{2})?/gi) || [];
  const described = uniqueSorted(matches.map((_, index) => index + 1)).map((index) => matches[index - 1]).filter(Boolean).map((token) => {
    const normalized = normalizeColorToken(token);
    const name = namedColors[normalized];
    return name ? `${name} (${normalized})` : normalized;
  });
  if (described.length === 0) return rawValue;
  if (described.length === 1) return `${described[0]} from ${rawValue}`;
  if (described.length === 2) return `${described[0]} and ${described[1]} from ${rawValue}`;
  return `${described.slice(0, -1).join(', ')}, and ${described.at(-1)} from ${rawValue}`;
}

function describeBackgroundValue(css: string, lines: number[]) {
  const allLines = splitLines(css);
  const source = lines.map((line) => compactSnippet(allLines, line)).join(' ');
  return describeColorValue(source || extractCurrentBackgroundValue(css));
}

function replaceBackgroundToBlue(css: string) {
  let next = css;
  next = next.replace(/background:#1b0909;/gi, 'background:#0b3b8f;');
  next = next.replace(/linear-gradient\(135deg,#1b0909,#2a1010\)/gi, 'linear-gradient(135deg,#0b3b8f,#1d4ed8)');
  next = next.replace(/radial-gradient\(circle at top left,#e11d2444,transparent 34%\)/gi, 'radial-gradient(circle at top left,#60a5fa66,transparent 34%)');
  if (next === css) {
    next = css.replace(/background(?:-color)?\s*:[^;]+;/i, 'background:#0b3b8f;');
  }
  return next;
}

function replaceBackgroundToAccent(css: string) {
  let next = css;
  next = next.replace(/background:#0b3b8f;/gi, 'background:#32105e;');
  next = next.replace(/background:#1b0909;/gi, 'background:#32105e;');
  next = next.replace(/linear-gradient\(135deg,#0b3b8f,#1d4ed8\)/gi, 'linear-gradient(135deg,#32105e,#6d28d9)');
  next = next.replace(/linear-gradient\(135deg,#1b0909,#2a1010\)/gi, 'linear-gradient(135deg,#32105e,#6d28d9)');
  next = next.replace(/radial-gradient\(circle at top left,#60a5fa66,transparent 34%\)/gi, 'radial-gradient(circle at top left,#6d28d966,transparent 34%)');
  next = next.replace(/radial-gradient\(circle at top left,#e11d2444,transparent 34%\)/gi, 'radial-gradient(circle at top left,#6d28d966,transparent 34%)');
  if (next === css) {
    next = css.replace(/background(?:-color)?\s*:[^;]+;/i, 'background:#32105e;');
  }
  return next;
}

function replaceButtonColor(css: string, lower: string) {
  const wantsAccent = lower.includes(accentWord);
  const wantsWhiteText = lower.includes('white text') || lower.includes('white');
  if (!wantsAccent) return css;
  let next = css.replace(/\.primary\{[^}]*\}/i, `.primary{background:#6d28d9;color:${wantsWhiteText ? '#ffffff' : '#f5ecff'};}`);
  if (next === css) {
    next = `${css}\n.primary{background:#6d28d9;color:${wantsWhiteText ? '#ffffff' : '#f5ecff'};}`;
  }
  return next;
}

function isLocateQuestion(lower: string) {
  return /\b(where is|show me where|show me the|what controls|what line controls|where do i edit|what is the color|what controls the background color)\b/.test(lower);
}

function isExplicitNewArtifactRequest(lower: string) {
  return /\bgenerate\s+a\s+new\s+artifact\b/.test(lower) || /\bstart\s+over\b/.test(lower);
}

function parseNameChange(message: string) {
  const match = message.match(/change\s+the\s+(?:main\s+)?(?:website\s+name|title|site\s+name|brand\s+name)\s+to\s+(.+)/i);
  if (!match?.[1]) return '';
  return match[1].trim().replace(/[.?!]+$/g, '').replace(/^['\"]|['\"]$/g, '').trim();
}

function parseButtonTextChange(message: string) {
  const labelMatch = message.match(/change the button text to\s+(.+)/i);
  return labelMatch?.[1]?.trim().replace(/["'.]+$/g, '') || '';
}

function isBackgroundDirectEdit(lower: string) {
  return /change\s+the\s+background\s+to|make\s+the\s+background/i.test(lower);
}

function isButtonColorDirectEdit(lower: string) {
  return /change\s+the\s+button\s+color/i.test(lower) || lower.includes(`button ${accentWord}`);
}

function isButtonColorLocate(lower: string) {
  return /show me where the button color is controlled|where is the button color|what controls the button color/i.test(lower);
}

function isBackgroundLocate(lower: string) {
  return /what controls the background color|what is the color for the background|where is the background color|show me.*background/i.test(lower);
}

function isWebsiteNameLocate(lower: string) {
  return /show me where.*main website name|where.*main website name|where do i edit.*website name/i.test(lower);
}

function isJavaScriptLocate(lower: string) {
  return /show me the javascript|show me the script|where is the click handler|where is the special of the day logic/.test(lower);
}

function isPreviewRefreshRequest(lower: string) {
  return lower.includes('refresh the preview') || lower.includes('reload the preview') || lower.includes('update the preview');
}

function diffEntries(beforeText: string, afterText: string, filePath: string): ArtifactDiffEntry[] {
  const beforeLines = splitLines(beforeText);
  const afterLines = splitLines(afterText);
  const length = Math.max(beforeLines.length, afterLines.length);
  const entries: ArtifactDiffEntry[] = [];
  for (let i = 0; i < length; i += 1) {
    const before = beforeLines[i] ?? '';
    const after = afterLines[i] ?? '';
    if (before === after) continue;
    if (before && !after) {
      entries.push({ file_path: filePath, line_number: i + 1, kind: 'deleted', content: before });
      continue;
    }
    if (!before && after) {
      entries.push({ file_path: filePath, line_number: i + 1, kind: 'added', content: after });
      continue;
    }
    entries.push({ file_path: filePath, line_number: i + 1, kind: 'modified_old', content: before });
    entries.push({ file_path: filePath, line_number: i + 1, kind: 'modified_new', content: after });
  }
  return entries;
}

function revisionHistoryFromDiff(summary: string, filePath: string, beforeText: string, afterText: string, invalidated: boolean): ArtifactRevisionHistoryEntry {
  const entries = diffEntries(beforeText, afterText, filePath);
  return {
    id: `revision-${Date.now()}`,
    timestamp: new Date().toISOString(),
    command_summary: summary,
    file_path: filePath,
    before_snippet: splitLines(beforeText).slice(0, 5).join('\n'),
    after_snippet: splitLines(afterText).slice(0, 5).join('\n'),
    added_lines: entries.filter((entry) => entry.kind === 'added' || entry.kind === 'modified_new').map((entry) => entry.line_number),
    deleted_lines: entries.filter((entry) => entry.kind === 'deleted' || entry.kind === 'modified_old').map((entry) => entry.line_number),
    modified_lines: entries.filter((entry) => entry.kind === 'modified_new' || entry.kind === 'modified_old').map((entry) => entry.line_number),
    approved_state_invalidated: invalidated,
  };
}

export function buildArtifactWorkbenchSnapshot(card: ArtifactCardLike): ArtifactWorkbenchSnapshot | null {
  const payload = card.payload || {};
  const bridge = asRecord(payload.artifactBridge);
  const snapshot = asRecord(bridge.snapshot);
  if (Object.keys(snapshot).length > 0) {
    return {
      package_id: asString(snapshot.package_id, card.id),
      title: asString(snapshot.title, card.title),
      package_type: asString(snapshot.package_type, asString(payload.package_type, 'website_package')),
      active_file_path: asString(snapshot.active_file_path, ''),
      active_tab: asString(snapshot.active_tab, 'Preview'),
      active_preview_path: asString(snapshot.active_preview_path, 'index.html'),
      available_files: Array.isArray(snapshot.available_files) ? snapshot.available_files.map((entry) => String(entry)) : [],
      files_by_path: asRecord(snapshot.files_by_path) as Record<string, string>,
      saved_files_by_path: asRecord(snapshot.saved_files_by_path) as Record<string, string>,
      dirty_by_path: asRecord(snapshot.dirty_by_path) as Record<string, boolean>,
      approval_state: asString(snapshot.approval_state, 'proposed'),
      highlighted_file_path: asString(snapshot.highlighted_file_path, ''),
      highlighted_line_start: Number(snapshot.highlighted_line_start || 0),
      highlighted_line_end: Number(snapshot.highlighted_line_end || 0),
      highlighted_token: asString(snapshot.highlighted_token, ''),
      workbench_state: asString(snapshot.workbench_state, 'idle') as ArtifactWorkbenchSnapshot['workbench_state'],
      pending_revision: (snapshot.pending_revision || null) as PendingArtifactRevision | null,
      last_artifact_command: asString(snapshot.last_artifact_command, ''),
      revision_history: Array.isArray(snapshot.revision_history) ? snapshot.revision_history as ArtifactRevisionHistoryEntry[] : [],
      diff_entries: Array.isArray(snapshot.diff_entries) ? snapshot.diff_entries as ArtifactDiffEntry[] : [],
    };
  }

  const files = Array.isArray(payload.files) ? payload.files : [];
  const filesByPath = files.reduce<Record<string, string>>((acc, item) => {
    const record = asRecord(item);
    const path = normalizePath(asString(record.path));
    if (path) acc[path] = asString(record.content);
    return acc;
  }, {});
  if (Object.keys(filesByPath).length === 0) {
    const html = asString(payload.html);
    const css = asString(payload.css);
    if (html) filesByPath['index.html'] = html;
    if (css) filesByPath['styles.css'] = css;
  }
  const availableFiles = Object.keys(filesByPath).sort();
  if (availableFiles.length === 0) return null;
  return {
    package_id: card.id,
    title: card.title,
    package_type: asString(payload.package_type, 'website_package'),
    active_file_path: availableFiles[0],
    active_tab: 'Preview',
    active_preview_path: availableFiles.find((path) => path.endsWith('.html')) || 'index.html',
    available_files: availableFiles,
    files_by_path: filesByPath,
    saved_files_by_path: { ...filesByPath },
    dirty_by_path: {},
    approval_state: 'proposed',
    highlighted_file_path: '',
    highlighted_line_start: 0,
    highlighted_line_end: 0,
    highlighted_token: '',
    workbench_state: 'idle',
    pending_revision: null,
    last_artifact_command: '',
    revision_history: [],
    diff_entries: [],
  };
}

export function buildArtifactChatContext(card: ArtifactCardLike): ActiveArtifactContext | null {
  const snapshot = buildArtifactWorkbenchSnapshot(card);
  if (!snapshot) return null;
  const searchableIndex: ArtifactSearchEntry[] = [];
  const snippetIndex: string[] = [];
  snapshot.available_files.forEach((path) => {
    const lines = splitLines(snapshot.files_by_path[path] || '');
    lines.forEach((line, index) => {
      const lowered = line.toLowerCase();
      const tokens = [
        lowered.includes('background') && 'background',
        lowered.includes('linear-gradient') && 'linear-gradient',
        lowered.includes('radial-gradient') && 'radial-gradient',
        lowered.includes('.button') && 'button',
        lowered.includes('.primary') && 'primary',
        lowered.includes('<h1') && 'h1',
        lowered.includes('<strong') && 'brand',
        lowered.includes('<title') && 'title',
        lowered.includes('request service') && 'button-text',
      ].filter(Boolean) as string[];
      if (tokens.length === 0) return;
      searchableIndex.push({ file_path: path, line_start: index + 1, line_end: index + 1, label: tokens.join(', '), snippet: line.trim(), tokens });
      snippetIndex.push(`${path}:${index + 1} ${line.trim()}`);
    });
  });
  return {
    package_id: snapshot.package_id,
    title: snapshot.title,
    package_type: snapshot.package_type,
    active_file_path: snapshot.active_file_path,
    active_tab: snapshot.active_tab,
    available_files: snapshot.available_files,
    searchable_index: searchableIndex,
    snippet_index: snippetIndex.slice(0, 80),
  };
}

function makeLocateWithFollowup(args: {
  snapshot: ArtifactWorkbenchSnapshot;
  filePath: string;
  lines: number[];
  token: string;
  currentValue: string;
  revisionKind: ArtifactRevisionKind;
  responsePrefix: string;
  followupPrompt: string;
}) {
  const { currentValue, filePath, followupPrompt, lines, responsePrefix, revisionKind, snapshot, token } = args;
  const pendingRevision: PendingArtifactRevision = {
    activeArtifactPackageId: snapshot.package_id,
    target_file_path: filePath,
    line_start: lines[0] || 1,
    line_end: lines.at(-1) || lines[0] || 1,
    token_or_selector: token,
    current_value: currentValue,
    revision_kind: revisionKind,
    followup_prompt: followupPrompt,
  };
  return {
    summary: `${responsePrefix} ${formatLines(lines)}. Awaiting revision instruction.`,
    responseText: `${responsePrefix} ${formatLines(lines)}. The current value is ${currentValue}. ${followupPrompt}`,
    command: {
      id: `artifact-command-${Date.now()}`,
      command_class: 'artifact_ask_followup',
      type: 'locate',
      package_id: snapshot.package_id,
      file_path: filePath,
      line_start: lines[0] || 1,
      line_end: lines.at(-1) || lines[0] || 1,
      token,
      workbench_state: 'awaiting_revision_instruction',
      pending_revision: pendingRevision,
      summary: followupPrompt,
      explanation: responsePrefix,
      tab: 'Code',
    },
  } satisfies LocalArtifactCommandResult;
}

function makeEditCommand(args: {
  snapshot: ArtifactWorkbenchSnapshot;
  filePath: string;
  before: string;
  after: string;
  token: string;
  summary: string;
  responseText: string;
}) {
  const { after, before, filePath, responseText, snapshot, summary, token } = args;
  const diff = diffEntries(before, after, filePath);
  const invalidated = snapshot.approval_state === 'approved' || snapshot.approval_state === 'applied';
  const historyEntry = revisionHistoryFromDiff(summary, filePath, before, after, invalidated);
  return {
    summary,
    responseText,
    command: {
      id: `artifact-command-${Date.now()}`,
      command_class: 'artifact_apply_pending_revision',
      type: 'apply_pending_revision',
      package_id: snapshot.package_id,
      file_path: filePath,
      replacement: after,
      token,
      explanation: summary,
      changed_files: [filePath],
      tab: 'Preview',
      workbench_state: 'preview_refreshed',
      pending_revision: null,
      diff_entries: diff,
      added_lines: historyEntry.added_lines,
      deleted_lines: historyEntry.deleted_lines,
      modified_lines: historyEntry.modified_lines,
      summary,
    },
  } satisfies LocalArtifactCommandResult;
}

export function resolveArtifactCommand(message: string, card: ArtifactCardLike): LocalArtifactCommandResult | null {
  const snapshot = buildArtifactWorkbenchSnapshot(card);
  if (!snapshot) return null;

  const lower = message.toLowerCase();
  if (isExplicitNewArtifactRequest(lower)) return null;

  const cssPath = firstPath(snapshot.available_files, '.css');
  const htmlPath = snapshot.available_files.find((path) => path.endsWith('.html')) || snapshot.available_files[0];
  const scriptPath = firstScriptPath(snapshot.available_files);
  const css = snapshot.files_by_path[cssPath] || '';
  const html = snapshot.files_by_path[htmlPath] || '';
  const script = scriptPath ? (snapshot.files_by_path[scriptPath] || '') : '';
  const pendingRevision = snapshot.pending_revision || null;

  if (pendingRevision && pendingRevision.activeArtifactPackageId === snapshot.package_id && !isLocateQuestion(lower)) {
    if (pendingRevision.revision_kind === 'background_color' && cssPath) {
      const colorName = lower.includes(accentWord) ? accentWord : 'blue';
      const replacement = lower.includes(accentWord)
        ? replaceBackgroundToAccent(css)
        : lower.includes('blue')
          ? replaceBackgroundToBlue(css)
          : css;
      if (replacement !== css) {
        return makeEditCommand({
          snapshot,
          filePath: cssPath,
          before: css,
          after: replacement,
          token: 'background',
          summary: `Changed the background to ${colorName} in ${cssPath} and refreshed the preview.`,
          responseText: `I changed the background to ${colorName} in ${cssPath} and refreshed the preview.`,
        });
      }
    }
    if (pendingRevision.revision_kind === 'button_color' && cssPath) {
      const replacement = replaceButtonColor(css, lower);
      if (replacement !== css) {
        return makeEditCommand({
          snapshot,
          filePath: cssPath,
          before: css,
          after: replacement,
          token: 'button-color',
          summary: `Updated button colors in ${cssPath} and refreshed the preview.`,
          responseText: `I updated the button color in ${cssPath} and refreshed the preview.`,
        });
      }
    }
    if (pendingRevision.revision_kind === 'website_name' && htmlPath) {
      const nextName = message.trim().replace(/[.?!]+$/g, '').replace(/^['\"]|['\"]$/g, '');
      if (nextName) {
        const replacement = replaceMainWebsiteName(html, nextName);
        if (replacement !== html) {
          return makeEditCommand({
            snapshot,
            filePath: htmlPath,
            before: html,
            after: replacement,
            token: nextName,
            summary: `Updated the main website name to ${nextName} in ${htmlPath} and refreshed the preview.`,
            responseText: `I changed the main website name to ${nextName} in ${htmlPath} and refreshed the preview.`,
          });
        }
      }
    }
  }

  if (isPreviewRefreshRequest(lower)) {
    return {
      summary: 'Refreshed the active package preview.',
      responseText: 'I refreshed the preview for the active package.',
      command: {
        id: `artifact-command-${Date.now()}`,
        command_class: 'artifact_preview_refresh',
        type: 'refresh_preview',
        package_id: snapshot.package_id,
        tab: 'Preview',
        workbench_state: 'preview_refreshed',
        explanation: 'Refreshed the workbench preview for the active package.',
      },
    };
  }

  if (isBackgroundDirectEdit(lower) && cssPath) {
    const replacement = lower.includes(accentWord)
      ? replaceBackgroundToAccent(css)
      : lower.includes('blue')
        ? replaceBackgroundToBlue(css)
        : css;
    if (replacement !== css) {
      const colorName = lower.includes(accentWord) ? accentWord : 'blue';
      return makeEditCommand({
        snapshot,
        filePath: cssPath,
        before: css,
        after: replacement,
        token: 'background',
        summary: `Changed the background to ${colorName} in ${cssPath} and refreshed the preview.`,
        responseText: `I changed the background to ${colorName} in ${cssPath} and refreshed the preview.`,
      });
    }
  }

  if (isButtonColorDirectEdit(lower) && cssPath) {
    const replacement = replaceButtonColor(css, lower);
    if (replacement !== css) {
      return makeEditCommand({
        snapshot,
        filePath: cssPath,
        before: css,
        after: replacement,
        token: 'button-color',
        summary: `Updated button colors in ${cssPath} and refreshed the preview.`,
        responseText: `I updated the button color in ${cssPath} and refreshed the preview.`,
      });
    }
  }

  const directName = parseNameChange(message);
  if (directName && htmlPath) {
    const replacement = replaceMainWebsiteName(html, directName);
    if (replacement !== html) {
      return makeEditCommand({
        snapshot,
        filePath: htmlPath,
        before: html,
        after: replacement,
        token: directName,
        summary: `Updated the main website name to ${directName} in ${htmlPath} and refreshed the preview.`,
        responseText: `I changed the main website name to ${directName} in ${htmlPath} and refreshed the preview.`,
      });
    }
  }

  const buttonText = parseButtonTextChange(message);
  if (buttonText && htmlPath) {
    const replacement = replaceFirstButtonLabel(html, buttonText);
    if (replacement !== html) {
      return makeEditCommand({
        snapshot,
        filePath: htmlPath,
        before: html,
        after: replacement,
        token: buttonText,
        summary: `Updated button text in ${htmlPath} to ${buttonText} and refreshed the preview.`,
        responseText: `I updated the button text to ${buttonText} in ${htmlPath} and refreshed the preview.`,
      });
    }
  }

  if (isBackgroundLocate(lower) && cssPath) {
    const lines = searchLines(css, (line) => /background(?:-color)?\s*:|linear-gradient|radial-gradient/i.test(line));
    if (lines.length > 0) {
      return makeLocateWithFollowup({
        snapshot,
        filePath: cssPath,
        lines,
        token: 'background',
        currentValue: describeBackgroundValue(css, lines),
        revisionKind: 'background_color',
        responsePrefix: `The background is controlled in ${cssPath}`,
        followupPrompt: 'What would you like to change it to?',
      });
    }
  }

  if (isButtonColorLocate(lower) && cssPath) {
    const lines = searchLines(css, (line) => /\.button|\.primary|\.secondary/i.test(line));
    if (lines.length > 0) {
      return makeLocateWithFollowup({
        snapshot,
        filePath: cssPath,
        lines,
        token: 'button-color',
        currentValue: describeColorValue(compactSnippet(splitLines(css), lines[0])),
        revisionKind: 'button_color',
        responsePrefix: `The button color is controlled in ${cssPath}`,
        followupPrompt: 'What would you like to change it to?',
      });
    }
  }

  if (isWebsiteNameLocate(lower) && htmlPath) {
    const lines = searchLines(html, (line) => /<strong>|<h1>|<title>/i.test(line));
    if (lines.length > 0) {
      return makeLocateWithFollowup({
        snapshot,
        filePath: htmlPath,
        lines,
        token: 'website-name',
        currentValue: compactSnippet(splitLines(html), lines[0]),
        revisionKind: 'website_name',
        responsePrefix: `The main website name is in ${htmlPath}`,
        followupPrompt: 'What would you like to change it to?',
      });
    }
  }

  if (isJavaScriptLocate(lower)) {
    if (scriptPath) {
      const scriptLines = searchLines(script, (line) => /special|click|onclick|addEventListener/i.test(line));
      const lines = scriptLines.length > 0 ? scriptLines : [1];
      return makeLocateWithFollowup({
        snapshot,
        filePath: scriptPath,
        lines,
        token: 'javascript',
        currentValue: compactSnippet(splitLines(script), lines[0]),
        revisionKind: 'javascript_behavior',
        responsePrefix: `The JavaScript logic is in ${scriptPath}`,
        followupPrompt: 'What would you like to change it to?',
      });
    }

    const inlineLines = findInlineScriptLines(html);
    if (inlineLines.length > 0) {
      return makeLocateWithFollowup({
        snapshot,
        filePath: htmlPath,
        lines: inlineLines,
        token: 'javascript-inline',
        currentValue: compactSnippet(splitLines(html), inlineLines[0]),
        revisionKind: 'javascript_behavior',
        responsePrefix: `The JavaScript logic is inline in ${htmlPath}`,
        followupPrompt: 'What would you like to change it to?',
      });
    }

    return {
      summary: 'No JavaScript file or click-handler code found in the current package.',
      responseText: 'This package currently has no separate JavaScript file or click-handler code.',
      command: {
        id: `artifact-command-${Date.now()}`,
        command_class: 'artifact_locate_code',
        type: 'select_tab',
        package_id: snapshot.package_id,
        tab: 'Code',
        token: 'javascript-missing',
        workbench_state: 'locating',
        explanation: 'No separate JavaScript file or click-handler code found.',
      },
    };
  }

  return null;
}
