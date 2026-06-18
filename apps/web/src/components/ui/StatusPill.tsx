import type { CapabilityStatus } from '../../types/contracts';

export function StatusPill({ label, status }: { label: string; status: CapabilityStatus | string }) {
  return <span className={`pill ${status}`}>{label}</span>;
}
