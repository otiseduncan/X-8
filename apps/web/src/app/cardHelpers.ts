import type { Receipt } from '../types/contracts';
import type { CardKind, ChatCard } from './AssistantComponents';

const id = () => `${Date.now()}-${Math.random().toString(16).slice(2)}`;

export function mapKernelCard(card: Record<string, unknown>): ChatCard | null {
  if (isNonActionableKernelLimitations(card)) return null;
  const kernelType = String(card.type || 'info');
  const type = ['info', 'status'].includes(kernelType) ? 'receipt' : (kernelType as CardKind);
  return { id: String(card.id || id()), type, title: String(card.title || 'Kernel card'), status: String(card.status || 'ok'), summary: String(card.summary || ''), payload: (card.payload || {}) as Record<string, unknown>, collapsed: kernelType === 'info' };
}

function isNonActionableKernelLimitations(card: Record<string, unknown>) {
  const title = String(card.title || '').toLowerCase();
  const status = String(card.status || '').toLowerCase();
  const payload = card.payload && typeof card.payload === 'object' ? card.payload as Record<string, unknown> : {};
  const hasActionablePayload = ['error', 'tool', 'action', 'command', 'approval_required', 'blocked_reason', 'reason']
    .some((key) => payload[key] !== undefined && payload[key] !== '');
  return title === 'kernel limitations' && !['error', 'blocked', 'failed'].includes(status) && !hasActionablePayload;
}

export function receiptCards(receipts: Receipt[] = []) {
  return receipts.map((receipt) => ({ id: id(), type: 'receipt' as CardKind, title: `Receipt: ${receipt.action}`, status: receipt.status, summary: receipt.summary, receipt, collapsed: true }));
}

export function errorCard(title: string, summary: string): ChatCard {
  return { id: id(), type: 'error', title, status: 'error', summary, receipt: { id: id(), action: title, status: 'error', summary } };
}
