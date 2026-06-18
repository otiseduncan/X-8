import { useEffect, useState } from 'react';
import type { ChatCard, ChatMessage, StoredChatSession } from './AssistantComponents';

const STORAGE_KEY = 'x8.localChatHistory.v1';
const MAX_SESSIONS = 20;

function readHistory(): StoredChatSession[] {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || '[]');
    return Array.isArray(parsed) ? parsed.slice(0, MAX_SESSIONS) : [];
  } catch {
    return [];
  }
}

function sanitizeCard(card: ChatCard): ChatCard {
  return {
    id: card.id,
    type: card.type,
    title: card.title,
    status: card.status,
    summary: card.summary,
    collapsed: card.collapsed
  };
}

function sanitizeMessage(message: ChatMessage): ChatMessage {
  return {
    id: message.id,
    role: message.role,
    text: message.text,
    createdAt: message.createdAt,
    attachments: message.attachments?.map((attachment) => ({
      attachment_id: attachment.attachment_id,
      filename: attachment.filename,
      mime_type: attachment.mime_type,
      size_bytes: attachment.size_bytes,
      status: attachment.status
    })),
    cards: message.cards?.map(sanitizeCard)
  };
}

function titleFor(messages: ChatMessage[], createdAt: string) {
  const firstUser = messages.find((message) => message.role === 'user' && message.text.trim());
  return firstUser?.text.trim().slice(0, 64) || `Chat ${new Date(createdAt).toLocaleString()}`;
}

export function useLocalChatHistory(activeId: string, messages: ChatMessage[]) {
  const [sessions, setSessions] = useState<StoredChatSession[]>(() => readHistory());

  useEffect(() => {
    const now = new Date().toISOString();
    setSessions((current) => {
      const existing = current.find((session) => session.id === activeId);
      const createdAt = existing?.createdAt || messages[0]?.createdAt || now;
      const nextSession: StoredChatSession = {
        id: activeId,
        title: titleFor(messages, createdAt),
        createdAt,
        updatedAt: now,
        messages: messages.map(sanitizeMessage)
      };
      const next = [nextSession, ...current.filter((session) => session.id !== activeId)].slice(0, MAX_SESSIONS);
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  }, [activeId, messages]);

  function deleteSession(id: string) {
    setSessions((current) => {
      const next = current.filter((session) => session.id !== id);
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  }

  return { sessions, deleteSession };
}
