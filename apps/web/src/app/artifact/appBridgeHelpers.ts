import type { ChatCard, ChatMessage } from '../AssistantComponents';
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

export async function handleArtifactBridgeCommand(args: {
  text: string;
  artifactCard: ChatCard;
  setActiveArtifactPackageId: (id: string) => void;
  setLatestResult: (value: string) => void;
  updateCard: (cardId: string, patch: Partial<ChatCard>) => void;
  appendAssistantBridgeResponse: (text: string, cards: ChatCard[]) => Promise<void>;
  makeId: () => string;
}) {
  const { appendAssistantBridgeResponse, artifactCard, makeId, setActiveArtifactPackageId, setLatestResult, text, updateCard } = args;
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
  await appendAssistantBridgeResponse(resolved.responseText, [{
    id: makeId(),
    type: 'receipt',
    title: `Artifact command: ${command.command_class}`,
    status: 'handled',
    summary: resolved.summary,
    payload: { command_class: command.command_class, file_path: command.file_path, changed_files: command.changed_files || [] },
    collapsed: false
  }]);
  return true;
}