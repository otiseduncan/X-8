import type { ChatCard, ChatMessage } from '../AssistantComponents';
import type { LocalArtifactCommandResult } from './commandBridge';
import { resolveArtifactCommand } from './commandBridge';

export function findActiveArtifactCard(messages: ChatMessage[], activeArtifactPackageId: string) {
  const ordered = [...messages].reverse();
  for (const message of ordered) {
    const cards = [...(message.cards || [])].reverse();
    for (const card of cards) {
      if (card.type !== 'artifact') continue;
      if (activeArtifactPackageId && card.id !== activeArtifactPackageId) continue;
      return card;
    }
  }
  return ordered.flatMap((message) => message.cards || []).reverse().find((card) => card.type === 'artifact');
}

const knownColors: Record<string, string> = {
  '#ffd21f': 'yellow (#ffd21f)',
  '#1b0909': 'black (#1b0909)',
  '#0b3b8f': 'blue (#0b3b8f)',
  '#e11d24': 'red (#e11d24)',
  '#2a1010': 'deep red (#2a1010)',
  '#1b1200': 'near-black (#1b1200)',
  '#ffffff': 'white (#ffffff)'
};

function normalizeHex(value: string) {
  const lower = value.toLowerCase();
  return /^#[0-9a-f]{8}$/.test(lower) ? lower.slice(0, 7) : lower;
}

function extractCompactColorList(value: string) {
  const matches = value.match(/#[0-9a-f]{6}(?:[0-9a-f]{2})?/gi) || [];
  const unique = Array.from(new Set(matches.map((match) => normalizeHex(match))));
  if (unique.length === 0) return '';
  const mapped = unique.map((hex) => knownColors[hex] || hex).slice(0, 4);
  if (mapped.length === 1) return mapped[0];
  if (mapped.length === 2) return `${mapped[0]} and ${mapped[1]}`;
  return `${mapped.slice(0, -1).join(', ')}, and ${mapped.at(-1)}`;
}

function compactBridgeResponse(resolved: LocalArtifactCommandResult) {
  const { command } = resolved;
  if (command.command_class !== 'artifact_ask_followup') {
    return resolved.responseText;
  }

  const base = resolved.summary
    .replace(/\.\s*Awaiting revision instruction\.?$/i, '')
    .replace(/Awaiting revision instruction\.?$/i, '')
    .trim();

  const colors = extractCompactColorList(resolved.responseText);
  if (colors) {
    return `${base}. Current colors include ${colors}. ${command.summary || 'What would you like to change it to?'}`;
  }

  return `${base}. ${command.summary || 'What would you like to change it to?'}`;
}

export async function handleArtifactBridgeCommand(args: {
  text: string;
  artifactCard: ChatCard;
  setActiveArtifactPackageId: (id: string) => void;
  setLatestResult: (value: string) => void;
  updateCard: (cardId: string, patch: Partial<ChatCard>) => void;
  appendAssistantBridgeResponse: (text: string, cards: ChatCard[]) => Promise<void>;
}) {
  const { appendAssistantBridgeResponse, artifactCard, setActiveArtifactPackageId, setLatestResult, text, updateCard } = args;
  const resolved = resolveArtifactCommand(text, artifactCard);
  if (!resolved) return false;
  const payload = artifactCard.payload || {};
  const bridgePayload = typeof payload.artifactBridge === 'object' && payload.artifactBridge !== null ? payload.artifactBridge as Record<string, unknown> : {};
  const command = resolved.command;
  updateCard(artifactCard.id, {
    payload: {
      ...payload,
      artifactBridge: {
        ...bridgePayload,
        command
      }
    }
  });
  setActiveArtifactPackageId(artifactCard.id);
  setLatestResult(resolved.summary);
  await appendAssistantBridgeResponse(compactBridgeResponse(resolved), []);
  return true;
}