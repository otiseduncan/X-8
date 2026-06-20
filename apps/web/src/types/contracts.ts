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

export type ArtifactCommandType = 'select_file' | 'highlight_line' | 'edit_file' | 'refresh_preview' | 'select_tab' | 'explain_location';

export interface ArtifactCommand {
  id: string;
  command_class:
    | 'artifact_locate_code'
    | 'artifact_explain_code'
    | 'artifact_highlight_line'
    | 'artifact_edit_active_package'
    | 'artifact_preview_refresh'
    | 'artifact_select_file'
    | 'artifact_select_tab';
  type: ArtifactCommandType;
  package_id: string;
  file_path?: string;
  line_start?: number;
  line_end?: number;
  token?: string;
  replacement?: string;
  explanation?: string;
  changed_files?: string[];
  tab?: string;
}

export interface ArtifactSearchEntry {
  file_path: string;
  line_start: number;
  line_end: number;
  label: string;
  snippet: string;
  tokens: string[];
}

export interface ArtifactWorkbenchSnapshot {
  package_id: string;
  title: string;
  package_type: string;
  active_file_path: string;
  active_tab: string;
  active_preview_path: string;
  available_files: string[];
  files_by_path: Record<string, string>;
  saved_files_by_path: Record<string, string>;
  dirty_by_path: Record<string, boolean>;
  approval_state: string;
  highlighted_file_path: string;
  highlighted_line_start: number;
  highlighted_line_end: number;
  highlighted_token: string;
}

export interface ActiveArtifactContext {
  package_id: string;
  title: string;
  package_type: string;
  active_file_path: string;
  active_tab: string;
  available_files: string[];
  searchable_index: ArtifactSearchEntry[];
  snippet_index: string[];
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
