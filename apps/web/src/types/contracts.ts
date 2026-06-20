export type CapabilityStatus = 'implemented' | 'available' | 'disabled' | 'not_configured' | 'stubbed' | 'unavailable' | 'blocked';

export interface Capability {
  name: string;
  status: CapabilityStatus;
  summary: string;
  requires_approval: boolean;
}

export interface IntegrationStatus {
  name: string;
  status: CapabilityStatus;
  live?: boolean;
  reason?: string;
  required_config?: string[];
  safe_actions?: string[];
  blocked_actions?: string[];
  last_checked?: string;
  receipt?: Record<string, unknown>;
  summary: string;
}

export interface TeamSeat {
  name: string;
  responsibility: string;
  output_style: string;
}

export interface Receipt {
  id: string;
  action: string;
  status: string;
  summary: string;
  metadata?: Record<string, unknown>;
}

export interface FileEntry {
  path: string;
  kind: 'file' | 'directory';
  size: number;
}

export interface FileRead {
  path: string;
  content: string;
  line_count: number;
}

export interface PatchProposal {
  path: string;
  diff: string;
  proposed_content: string;
  mutated: boolean;
  approval?: {
    id: string;
    action: string;
    risk: string;
    status: string;
    intent: {
      summary: string;
      files_affected: string[];
      before_after_summary: string;
    };
    rollback_hint: {
      summary: string;
    };
  };
  receipt: Receipt;
}

export interface AttachmentReference {
  attachment_id: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  status: string;
  extracted_text?: string;
  content_extractable?: boolean;
}

export interface PromptReceipt {
  receipt_id: string;
  action_type: string;
  status: string;
  model: string;
  limitations: string[];
}

export interface ChatRoleMessage {
  role: 'assistant' | 'user';
  content: string;
  cards: Record<string, unknown>[];
}

export interface ChatResponse {
  session_id: string;
  message_id: string;
  assistant_message: ChatRoleMessage;
  receipt: PromptReceipt;
  attachments: AttachmentReference[];
}

export interface SessionSummary {
  session_id: string;
  title: string;
  updated_at: string;
}

export interface SessionDetail {
  session_id: string;
  title: string;
  messages: Array<{
    message_id: string;
    role: 'assistant' | 'user';
    content: string;
    cards: Record<string, unknown>[];
    attachments?: AttachmentReference[];
  }>;
  receipts: Array<Record<string, unknown>>;
}

export interface ResultEnvelope<T> {
  ok: boolean;
  status: string;
  data: T;
  message: string;
  receipts: Receipt[];
}
