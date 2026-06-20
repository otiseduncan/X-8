# XV8 V8.1 Studio Operator Plan

## Mission

XV8 must evolve from a functional beta assistant into a local AI workstation with:

1. Empty-start chat UX
2. IDE/code review surface
3. Artifact preview surface
4. Project Builder sandbox writes
5. Web research
6. Image generation
7. Email/text drafting and approval-gated sending
8. Local system/body awareness
9. Honest integration truth
10. Shared permission model

## Required permission states

- read_only
- preview_only
- draft_only
- approval_required
- sandbox_write_allowed
- blocked
- unavailable
- not_configured
- disabled

## V8.1 operator body zones

### Green zone

Allowed with no extra confirmation when configured:

- runtime/
- runtime/generated-projects/
- configured sandbox output path
- generated media folder
- approved temporary preview files

### Yellow zone

Allowed only through proposal/approval flow:

- repo source files
- Docker files
- config files
- Git operations
- package files
- test files

### Red zone

Blocked or requires explicit destructive confirmation:

- Windows system folders
- secrets
- .env
- SSH keys
- browser credentials
- unrelated drives/folders
- destructive delete
- external sends
- auto commit/push

## V8.1 capability lanes

### 1. Empty chat start

App must load with a blank new-chat canvas.
History can exist in a side panel but must not auto-load old transcript into the main chat.

### 2. IDE/code workspace

Required UI:
- file tree
- file viewer
- line numbers
- copy button
- edit button
- save/apply through approval flow
- diff viewer
- generated file cards
- preview in chat
- open generated file
- rollback/receipt metadata

### 3. Artifact preview

Rules:
- generate / preview / show = preview in chat
- build / write / create / export = sandbox write
- mentioning README.md as an output file must not route to README viewer

### 4. Web research

Required:
- internet/search adapter
- source cards
- checked-at timestamp
- citations/links
- unavailable/not_configured status if offline
- no fake research

### 5. Local system body

Read-only scan:
- drives
- free/used space
- CPU/RAM/GPU if available
- Docker status
- Git status
- local bridge status
- Ollama/model status
- generated project folders
- network summary where safe

### 6. Email/text

Drafting is allowed.
Sending requires approval and live connector configuration.

### 7. Image generation

Required:
- ComfyUI/image backend status
- prompt UI/API
- model availability status
- job receipt
- generated image gallery/output path
- no fake generation

## Done criteria

V8.1 is done when:

- XV8 opens to empty chat
- can inspect local system read-only
- can display/edit/copy generated code
- can preview generated artifacts in chat
- can write approved projects to sandbox
- can research the web with honest sources
- can draft emails/texts
- can honestly report send unavailable or approval-required
- can generate images if backend exists
- can honestly report image backend unavailable if missing
- never silently mutates protected files
- never fakes capability status
