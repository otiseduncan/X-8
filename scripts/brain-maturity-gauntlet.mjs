#!/usr/bin/env node
/**
 * Brain Maturity Gauntlet Runner
 * Runs Q&A cases from tests/fixtures/brain_maturity_qa.json against the API
 * Usage (inside container or with API running):
 *   node scripts/brain-maturity-gauntlet.mjs [--base-url http://localhost:8000] [--category identity_persona]
 */

import { readFileSync, writeFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const FIXTURE_PATH = join(__dirname, '../tests/fixtures/brain_maturity_qa.json');
const REPORT_DIR = join(__dirname, '../runtime/reports');

const args = process.argv.slice(2);
const baseUrl = (() => {
  const idx = args.indexOf('--base-url');
  return idx >= 0 ? args[idx + 1] : 'http://x8-api:8000';
})();
const filterCategory = (() => {
  const idx = args.indexOf('--category');
  return idx >= 0 ? args[idx + 1] : null;
})();
const filterIds = (() => {
  const idx = args.indexOf('--ids');
  return idx >= 0 ? args[idx + 1].split(',') : null;
})();

let cases = JSON.parse(readFileSync(FIXTURE_PATH, 'utf8'));
if (filterCategory) cases = cases.filter(c => c.category === filterCategory);
if (filterIds) cases = cases.filter(c => filterIds.includes(c.id));

const CATEGORY_ORDER = [
  'identity_persona', 'communication_style', 'memory_capture', 'memory_recall',
  'memory_forget', 'correction', 'active_focus', 'instruction_override',
  'capability_truth', 'local_body_honesty', 'chat_history', 'routing',
  'safety', 'knowledge_richness', 'fallback_quality', 'decision_trace',
  'deterministic_no_limitation_card', 'reasonable_ambiguity'
];

async function postChat(message, sessionId, priorMessages) {
  const body = { message };
  if (sessionId) body.session_id = sessionId;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30000);
  try {
    const response = await fetch(`${baseUrl}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    clearTimeout(timeout);
    if (!response.ok) return { error: `HTTP ${response.status}` };
    return response.json();
  } catch (e) {
    clearTimeout(timeout);
    return { error: String(e) };
  }
}

async function seedMemory(sessionId, seedText) {
  return postChat(`remember that ${seedText}`, sessionId);
}

function scoreCase(testCase, result) {
  const scores = [];
  const issues = [];

  if (result.error) {
    return { pass: false, issues: [`API error: ${result.error}`] };
  }

  const content = result.data?.assistant_message?.content ?? '';
  const cards = result.data?.assistant_message?.cards ?? [];
  const trace = result.data?.decision_trace ?? {};
  const receiptStatus = result.status ?? '';
  const lane = trace.selected_route ?? result.data?.decision_trace?.selected_route ?? '';
  const cardTitles = cards.map(c => c.title ?? '');
  const cardSummaries = cards.map(c => JSON.stringify(c));
  const allText = content + ' ' + cardTitles.join(' ') + ' ' + cardSummaries.join(' ');

  // Route check
  if (testCase.expected_route) {
    if (lane === testCase.expected_route) {
      scores.push('route:pass');
    } else {
      scores.push('route:fail');
      issues.push(`Expected route "${testCase.expected_route}", got "${lane}"`);
    }
  }

  // Status check
  if (testCase.expected_status && testCase.expected_status !== 'any') {
    if (receiptStatus === testCase.expected_status) {
      scores.push('status:pass');
    } else {
      scores.push('status:fail');
      issues.push(`Expected status "${testCase.expected_status}", got "${receiptStatus}"`);
    }
  }

  // Expected content
  for (const expected of (testCase.expected_response_contains ?? [])) {
    if (allText.toLowerCase().includes(expected.toLowerCase())) {
      scores.push(`contains:"${expected}":pass`);
    } else {
      scores.push(`contains:"${expected}":fail`);
      issues.push(`Expected text to contain "${expected}"`);
    }
  }

  // Forbidden content
  for (const forbidden of (testCase.forbidden_response_contains ?? [])) {
    if (!allText.toLowerCase().includes(forbidden.toLowerCase())) {
      scores.push(`forbidden:"${forbidden}":pass`);
    } else {
      scores.push(`forbidden:"${forbidden}":fail`);
      issues.push(`Response must not contain "${forbidden}"`);
    }
  }

  // Decision trace fields
  for (const field of (testCase.expected_decision_trace_fields ?? [])) {
    if (field in trace) {
      scores.push(`trace:${field}:pass`);
    } else {
      scores.push(`trace:${field}:fail`);
      issues.push(`Decision trace missing field "${field}"`);
    }
  }

  // Kernel limitations card check (cards that contain "Kernel limitations" when not expected)
  const hasKernelLimitCard = cardTitles.some(t => t === 'Kernel limitations');
  if (testCase.category === 'deterministic_no_limitation_card' && hasKernelLimitCard) {
    issues.push('Has "Kernel limitations" card on deterministic route');
    scores.push('no_limitation_card:fail');
  } else if (testCase.category === 'deterministic_no_limitation_card') {
    scores.push('no_limitation_card:pass');
  }

  const pass = issues.length === 0;
  return { pass, issues, scores, lane, content: content.slice(0, 200) };
}

async function run() {
  console.log(`\n=== Brain Maturity Gauntlet Runner ===`);
  console.log(`Base URL: ${baseUrl}`);
  console.log(`Cases: ${cases.length}`);
  if (filterCategory) console.log(`Filter: category=${filterCategory}`);
  console.log();

  const results = [];
  const byCategory = {};

  for (const testCase of cases) {
    process.stdout.write(`  [${testCase.id}] ${testCase.user_message.slice(0, 60).padEnd(62)}`);

    let sessionId = null;

    // Seed memory if needed
    if (testCase.memory_seed) {
      const seedResult = await postChat(`remember that ${testCase.memory_seed}`, null, []);
      sessionId = seedResult.data?.session_id ?? null;
      process.stdout.write(`(seeded) `);
    }

    const result = await postChat(testCase.user_message, sessionId, testCase.prior_context ?? []);
    const score = scoreCase(testCase, result);

    if (score.pass) {
      process.stdout.write('PASS\n');
    } else {
      process.stdout.write(`FAIL\n`);
      for (const issue of score.issues) {
        console.log(`    ✗ ${issue}`);
      }
    }

    results.push({
      id: testCase.id,
      category: testCase.category,
      user_message: testCase.user_message,
      pass: score.pass,
      issues: score.issues,
      lane: score.lane,
      response_preview: score.content,
      scoring_notes: testCase.scoring_notes ?? '',
    });

    if (!byCategory[testCase.category]) byCategory[testCase.category] = { pass: 0, fail: 0, total: 0 };
    byCategory[testCase.category].total++;
    if (score.pass) byCategory[testCase.category].pass++;
    else byCategory[testCase.category].fail++;
  }

  const totalPass = results.filter(r => r.pass).length;
  const totalFail = results.filter(r => !r.pass).length;
  const totalPct = results.length > 0 ? Math.round(100 * totalPass / results.length) : 0;

  console.log(`\n=== Category Scorecard ===`);
  const cats = [...new Set(results.map(r => r.category))].sort((a, b) => {
    const ai = CATEGORY_ORDER.indexOf(a);
    const bi = CATEGORY_ORDER.indexOf(b);
    return (ai < 0 ? 99 : ai) - (bi < 0 ? 99 : bi);
  });
  for (const cat of cats) {
    const s = byCategory[cat] ?? { pass: 0, fail: 0, total: 0 };
    const pct = s.total > 0 ? Math.round(100 * s.pass / s.total) : 0;
    const bar = s.fail > 0 ? '✗' : '✓';
    console.log(`  ${bar} ${cat.padEnd(35)} ${String(s.pass).padStart(3)}/${s.total}  ${pct}%`);
  }

  console.log(`\n=== Total: ${totalPass}/${results.length} (${totalPct}%) ===\n`);

  if (totalFail > 0) {
    console.log(`=== Failures ===`);
    for (const r of results.filter(r => !r.pass)) {
      console.log(`  [${r.id}] ${r.user_message.slice(0, 60)}`);
      console.log(`    Route: ${r.lane}`);
      for (const issue of r.issues) {
        console.log(`    ✗ ${issue}`);
      }
      if (r.response_preview) {
        console.log(`    Response: ${r.response_preview.slice(0, 120).replace(/\n/g, ' ')}`);
      }
    }
    console.log();
  }

  // Write report
  const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
  const reportPath = join(REPORT_DIR, `brain-maturity-${ts}.json`);
  const mdPath = join(REPORT_DIR, `brain-maturity-${ts}.md`);

  const reportData = {
    timestamp: new Date().toISOString(),
    base_url: baseUrl,
    filter_category: filterCategory,
    total: results.length,
    passed: totalPass,
    failed: totalFail,
    pass_pct: totalPct,
    by_category: byCategory,
    results,
  };

  try {
    writeFileSync(reportPath, JSON.stringify(reportData, null, 2));

    let md = `# Brain Maturity Gauntlet Report\n\nGenerated: ${new Date().toISOString()}\n\n`;
    md += `## Summary\n\n- Total: ${results.length}\n- Passed: ${totalPass}\n- Failed: ${totalFail}\n- Pass rate: ${totalPct}%\n\n`;
    md += `## Category Scorecard\n\n| Category | Pass | Total | % |\n|---|---|---|---|\n`;
    for (const cat of cats) {
      const s = byCategory[cat];
      const pct = s.total > 0 ? Math.round(100 * s.pass / s.total) : 0;
      md += `| ${cat} | ${s.pass} | ${s.total} | ${pct}% |\n`;
    }
    if (totalFail > 0) {
      md += `\n## Failures\n\n`;
      for (const r of results.filter(r => !r.pass)) {
        md += `### [${r.id}] ${r.user_message.slice(0, 80)}\n- Route: \`${r.lane}\`\n`;
        for (const issue of r.issues) md += `- ✗ ${issue}\n`;
        if (r.response_preview) md += `- Response: \`${r.response_preview.slice(0, 120)}\`\n`;
        md += '\n';
      }
    }
    writeFileSync(mdPath, md);
    console.log(`Report: ${reportPath}`);
    console.log(`Report MD: ${mdPath}`);
  } catch (e) {
    console.log(`(Could not write report: ${e.message})`);
  }

  process.exit(totalFail > 0 ? 1 : 0);
}

run().catch(e => { console.error(e); process.exit(1); });
