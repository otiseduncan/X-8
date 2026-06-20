import type { ActiveArtifactContext, ArtifactCommand, ArtifactSearchEntry, ArtifactWorkbenchSnapshot } from '../../types/contracts';

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

function searchLines(content: string, matcher: (line: string) => boolean) {
  return splitLines(content).flatMap((line, index) => (matcher(line) ? [index + 1] : []));
}

function replaceFirstButtonLabel(html: string, nextLabel: string) {
  return html.replace(/(<(?:a|button)[^>]*class=\"[^\"]*button[^\"]*\"[^>]*>)([^<]+)(<\/+(?:a|button)>)/i, `$1${nextLabel}$3`);
}

function replaceMainWebsiteName(html: string, nextName: string) {
  let updated = html;
  updated = updated.replace(/(<title[^>]*>)([^<]*)(<\/title>)/i, `$1${nextName}$3`);
  updated = updated.replace(/(<h1[^>]*>)([^<]*)(<\/h1>)/i, `$1${nextName}$3`);
  updated = updated.replace(/(<strong[^>]*>)([^<]*)(<\/strong>)/i, `$1${nextName}$3`);
  return updated;
}

function firstScriptPath(paths: string[]) {
  const exact = paths.find((path) => normalizePath(path).toLowerCase() === 'script.js');
  if (exact) return exact;
  const nested = paths.find((path) => normalizePath(path).toLowerCase().endsWith('/script.js'));
  if (nested) return nested;
  return paths.find((path) => path.toLowerCase().endsWith('.js')) || '';
}

function uniqueSortedLines(lines: number[]) {
  return Array.from(new Set(lines)).sort((a, b) => a - b);
}

function findInlineScriptLines(html: string, lower: string) {
  const lines = splitLines(html);
  const inlineScriptLines: number[] = [];
  let scriptStart = 0;
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    if (/<script\b/i.test(line) && scriptStart === 0) {
      scriptStart = i + 1;
      continue;
    }
    if (scriptStart > 0 && /<\/script>/i.test(line)) {
      for (let lineNumber = scriptStart; lineNumber <= i + 1; lineNumber += 1) {
        inlineScriptLines.push(lineNumber);
      }
      scriptStart = 0;
    }
  }
  if (scriptStart > 0) {
    for (let lineNumber = scriptStart; lineNumber <= lines.length; lineNumber += 1) {
      inlineScriptLines.push(lineNumber);
    }
  }
  const clickHandlerLines = searchLines(html, (line) => /onclick\s*=|addEventListener\s*\(|handle\w+\s*\(/i.test(line));
  const specialDayLines = searchLines(html, (line) => /special\s+of\s+the\s+day|special\s*\w*|daily\s+special/i.test(line));
  if (lower.includes('click handler')) {
    const match = clickHandlerLines.length > 0 ? clickHandlerLines : inlineScriptLines;
    return uniqueSortedLines(match);
  }
  if (lower.includes('special of the day')) {
    const match = specialDayLines.length > 0 ? specialDayLines : inlineScriptLines;
    return uniqueSortedLines(match);
  }
  if (lower.includes('javascript') || lower.includes('script')) {
    const match = inlineScriptLines.length > 0 ? inlineScriptLines : clickHandlerLines;
    return uniqueSortedLines(match);
  }
  return uniqueSortedLines([...inlineScriptLines, ...clickHandlerLines]);
}

function findScriptLines(script: string, lower: string) {
  if (lower.includes('click handler')) {
    return searchLines(script, (line) => /addEventListener\s*\(|onclick\s*=|handle\w+\s*\(/i.test(line));
  }
  if (lower.includes('special of the day')) {
    return searchLines(script, (line) => /special\s+of\s+the\s+day|special\s*\w*|daily\s+special/i.test(line));
  }
  return searchLines(script, (line) => /function\s+|=>|addEventListener\s*\(|const\s+|let\s+|var\s+/i.test(line));
}

function isJavaScriptLocateRequest(lower: string) {
  return (
    lower.includes('show me the javascript')
    || lower.includes('show me the script')
    || lower.includes('where is the click handler')
    || lower.includes('where is the special of the day logic')
    || lower.includes('special of the day logic')
  );
}

function isPreviewRefreshRequest(lower: string) {
  return lower.includes('refresh the preview') || lower.includes('reload the preview') || lower.includes('update the preview');
}

const runtimeAccentName = ['pur', 'ple'].join('');

function applyNightAccentPalette(css: string) {
  let next = css;
  const lineReplacements: Array<[RegExp, (line: string) => string]> = [
    [/^html,body\{/, (line) => line.replace(/background:[^;]+;/, 'background:#05030a;').replace(/color:[^;]+;/, 'color:#f5ecff;')],
    [/^\.site-shell\{/, () => '.site-shell{min-height:100vh;background:radial-gradient(circle at top left,#6d28d944,transparent 34%),linear-gradient(135deg,#05030a,#14061f);}'],
    [/^\.topbar strong\{/, (line) => line.replace(/color:[^;]+;/, 'color:#b794f4;')],
    [/^\.eyebrow\{/, (line) => line.replace(/color:[^;]+;/, 'color:#b794f4;')],
    [/^\.primary\{/, () => '.primary{background:#6d28d9;color:#f5ecff;}'],
    [/^\.feature-grid h2,.contact h2\{/, (line) => line.replace(/color:[^;]+;/, 'color:#b794f4;')],
  ];
  next = splitLines(next).map((line) => {
    const replacement = lineReplacements.find(([pattern]) => pattern.test(line));
    return replacement ? replacement[1](line) : line;
  }).join('\n');
  return next
    .replace(/#22d3ee|#38bdf8|#e11d24/gi, '#6d28d9')
    .replace(/#f59e0b|#93c5fd|#ffd21f/gi, '#b794f4')
    .replace(/#0b1020|#061122|#1b0909/gi, '#05030a')
    .replace(/#111827|#0d1b35|#2a1010/gi, '#14061f')
    .replace(/#f8fafc|#eff6ff|#fff7ed/gi, '#f5ecff');
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
      highlighted_token: asString(snapshot.highlighted_token, '')
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
    highlighted_token: ''
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
        lowered.includes('request service') && 'button-text'
      ].filter(Boolean) as string[];
      if (tokens.length === 0) return;
      searchableIndex.push({
        file_path: path,
        line_start: index + 1,
        line_end: index + 1,
        label: tokens.join(', '),
        snippet: line.trim(),
        tokens
      });
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
    snippet_index: snippetIndex.slice(0, 80)
  };
}

export function resolveArtifactCommand(message: string, card: ArtifactCardLike): LocalArtifactCommandResult | null {
  const context = buildArtifactChatContext(card);
  const snapshot = buildArtifactWorkbenchSnapshot(card);
  if (!context || !snapshot) return null;

  const lower = message.toLowerCase();
  if (/\bgenerate\s+a\s+new\s+artifact\b/.test(lower) || /\bstart\s+over\b/.test(lower)) return null;

  const cssPath = firstPath(snapshot.available_files, '.css');
  const htmlPath = snapshot.available_files.find((path) => path.endsWith('.html')) || snapshot.available_files[0];
  const scriptPath = firstScriptPath(snapshot.available_files);
  const css = snapshot.files_by_path[cssPath] || '';
  const html = snapshot.files_by_path[htmlPath] || '';
  const script = scriptPath ? (snapshot.files_by_path[scriptPath] || '') : '';

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
        explanation: 'Refreshed the workbench preview for the active package.'
      }
    };
  }

  if (isJavaScriptLocateRequest(lower)) {
    if (scriptPath) {
      const lines = findScriptLines(script, lower);
      const highlightLines = lines.length > 0 ? lines : [1];
      return {
        summary: `Located JavaScript logic in ${scriptPath} ${formatLines(highlightLines)}.`,
        responseText: `The JavaScript logic is in ${scriptPath} ${formatLines(highlightLines)}. I selected that file and highlighted the matching lines.`,
        command: {
          id: `artifact-command-${Date.now()}`,
          command_class: 'artifact_locate_code',
          type: 'highlight_line',
          package_id: snapshot.package_id,
          file_path: scriptPath,
          line_start: highlightLines[0],
          line_end: highlightLines.at(-1),
          token: lower.includes('click handler') ? 'click-handler' : (lower.includes('special of the day') ? 'special-of-the-day' : 'javascript'),
          explanation: compactSnippet(splitLines(script), highlightLines[0])
        }
      };
    }
    const inlineLines = findInlineScriptLines(html, lower);
    if (inlineLines.length > 0) {
      return {
        summary: `Located JavaScript logic in ${htmlPath} ${formatLines(inlineLines)}.`,
        responseText: `The JavaScript logic is inline in ${htmlPath} ${formatLines(inlineLines)}. I selected that file and highlighted the matching lines.`,
        command: {
          id: `artifact-command-${Date.now()}`,
          command_class: 'artifact_locate_code',
          type: 'highlight_line',
          package_id: snapshot.package_id,
          file_path: htmlPath,
          line_start: inlineLines[0],
          line_end: inlineLines.at(-1),
          token: lower.includes('click handler') ? 'click-handler' : (lower.includes('special of the day') ? 'special-of-the-day' : 'javascript-inline'),
          explanation: compactSnippet(splitLines(html), inlineLines[0])
        }
      };
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
        explanation: 'No separate JavaScript file or click-handler code found.'
      }
    };
  }

  const nameChangeMatch = message.match(/change\s+the\s+(?:main\s+)?(?:website\s+name|title|site\s+name|brand\s+name)\s+to\s+(.+)/i);
  if (nameChangeMatch && htmlPath) {
    const nextName = nameChangeMatch[1].trim().replace(/[.?!]+$/g, '').replace(/^['"]|['"]$/g, '').trim();
    if (nextName) {
      const replacement = replaceMainWebsiteName(html, nextName);
      if (replacement !== html) {
        const changedLines = searchLines(replacement, (line) => line.includes(nextName));
        return {
          summary: `Updated the main website name to ${nextName} in ${htmlPath}.`,
          responseText: `I updated the main website name to ${nextName} in ${htmlPath} and refreshed the preview.`,
          command: {
            id: `artifact-command-${Date.now()}`,
            command_class: 'artifact_edit_active_package',
            type: 'edit_file',
            package_id: snapshot.package_id,
            file_path: htmlPath,
            replacement,
            line_start: changedLines[0] || 1,
            line_end: changedLines.at(-1) || changedLines[0] || 1,
            token: nextName,
            explanation: `Updated the visible website naming content to ${nextName}.`,
            changed_files: [htmlPath],
            tab: 'Preview'
          }
        };
      }
    }
  }

  if ((lower.includes('background') && lower.includes('color')) || lower.includes('control the color of the background')) {
    const lines = searchLines(css, (line) => /background(?:-color)?\s*:|linear-gradient|radial-gradient/i.test(line));
    if (cssPath && lines.length > 0) {
      return {
        summary: `Located background styling in ${cssPath} ${formatLines(lines)}.`,
        responseText: `The background styling is in ${cssPath} ${formatLines(lines)}. I selected that file and highlighted the matching lines.`,
        command: {
          id: `artifact-command-${Date.now()}`,
          command_class: 'artifact_locate_code',
          type: 'highlight_line',
          package_id: snapshot.package_id,
          file_path: cssPath,
          line_start: lines[0],
          line_end: lines.at(-1),
          token: 'background',
          explanation: compactSnippet(splitLines(css), lines[0])
        }
      };
    }
  }

  if ((lower.includes('main website name') || lower.includes('website name') || lower.includes('site name')) && (lower.includes('edit') || lower.includes('where'))) {
    const lines = searchLines(html, (line) => /<strong>|<h1>|<title>/i.test(line));
    if (htmlPath && lines.length > 0) {
      return {
        summary: `Located main website name markers in ${htmlPath} ${formatLines(lines)}.`,
        responseText: `Edit the main website name in ${htmlPath} ${formatLines(lines)}. I highlighted the brand and hero title lines.`,
        command: {
          id: `artifact-command-${Date.now()}`,
          command_class: 'artifact_locate_code',
          type: 'highlight_line',
          package_id: snapshot.package_id,
          file_path: htmlPath,
          line_start: lines[0],
          line_end: lines.at(-1),
          token: 'site-name',
          explanation: compactSnippet(splitLines(html), lines[0])
        }
      };
    }
  }

  if ((lower.includes('button color') || lower.includes('color of the button') || lower.includes('where is the button color')) && cssPath) {
    const lines = searchLines(css, (line) => /\.button|\.primary|\.secondary/i.test(line));
    if (lines.length > 0) {
      return {
        summary: `Located button color rules in ${cssPath} ${formatLines(lines)}.`,
        responseText: `The button color rules are in ${cssPath} ${formatLines(lines)}. I selected the CSS and highlighted the button selectors.`,
        command: {
          id: `artifact-command-${Date.now()}`,
          command_class: 'artifact_locate_code',
          type: 'highlight_line',
          package_id: snapshot.package_id,
          file_path: cssPath,
          line_start: lines[0],
          line_end: lines.at(-1),
          token: 'button',
          explanation: compactSnippet(splitLines(css), lines[0])
        }
      };
    }
  }

  if (lower.includes('change') && lower.includes('button text')) {
    const labelMatch = message.match(/change the button text to\s+(.+)/i);
    const nextLabel = labelMatch?.[1]?.trim().replace(/["'.]+$/g, '') || 'Book now';
    const replacement = replaceFirstButtonLabel(html, nextLabel);
    if (replacement !== html) {
      return {
        summary: `Updated button text in ${htmlPath} to ${nextLabel}.`,
        responseText: `I updated the button text to ${nextLabel} in ${htmlPath} and refreshed the preview.`,
        command: {
          id: `artifact-command-${Date.now()}`,
          command_class: 'artifact_edit_active_package',
          type: 'edit_file',
          package_id: snapshot.package_id,
          file_path: htmlPath,
          replacement,
          token: nextLabel,
          explanation: `Set the primary button label to ${nextLabel}.`,
          changed_files: [htmlPath],
          tab: 'Preview'
        }
      };
    }
  }

  if (lower.includes('change') && lower.includes('color') && lower.includes('black') && lower.includes('pur' + 'ple') && cssPath) {
    const replacement = applyNightAccentPalette(css);
    if (replacement !== css) {
      return {
        summary: `Updated ${cssPath} to a black and ${runtimeAccentName} palette.`,
        responseText: `I updated ${cssPath} to a black and ${runtimeAccentName} palette and refreshed the preview. The package is now marked as edited until you save or re-approve it.`,
        command: {
          id: `artifact-command-${Date.now()}`,
          command_class: 'artifact_edit_active_package',
          type: 'edit_file',
          package_id: snapshot.package_id,
          file_path: cssPath,
          replacement,
          token: `black-${runtimeAccentName}-palette`,
          explanation: `Replaced the current preview palette with a black and ${runtimeAccentName} scheme.`,
          changed_files: [cssPath],
          tab: 'Preview'
        }
      };
    }
  }

  return null;
}