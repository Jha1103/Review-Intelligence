(function () {
  'use strict';

  window.DEMO_DATA = window.DEMO_DATA || {};

  // ---------------------------------------------------------------------------
  // Verified execution evidence (sanitized, no credentials or private data)
  // All data derived from verified local n8n executions. No invented data.
  // ---------------------------------------------------------------------------
  window.DEMO_DATA.EVIDENCE = {
    reject: {
      runId: 'execution_26',
      scenario: 'reject',
      title: 'Reject — zero external writes',
      description:
        'Approval gate returned Reject. Workflow stopped before the MCP Client. append_to_doc: not invoked. create_email_draft: not invoked. Google Docs: unchanged. Gmail: no draft created.',
      meta: ['scenario: reject', 'external writes: 0', 'audit: blocked'],
      stoppedAtNode: 'gate',
      steps: [
        'sheets',
        'validate',
        'batches',
        'gemini',
        'validate2',
        'generate',
        'format',
        'wait',
        'gate',
      ],
    },
    approve: {
      runId: 'groww_27',
      scenario: 'approve',
      title: 'Approve — full delivery',
      description:
        'Approval gate returned Approve. MCP Client invoked append_to_doc (Execution #30) then create_email_draft via Gmail-only recovery. Both actions completed successfully.',
      meta: ['scenario: approve', 'doc_status: done', 'draft_status: done', 'email sent: no'],
      steps: [
        'sheets',
        'validate',
        'batches',
        'gemini',
        'validate2',
        'generate',
        'format',
        'wait',
        'gate',
        'compute',
        'mcpClient',
        'mcpServer',
        'googleDocs',
        'gmail',
      ],
    },
  };

  // ---------------------------------------------------------------------------
  // MCP tool records (sanitized — no raw responses invented)
  // If the exact MCP response was not captured, "Raw response not available" is shown.
  // ---------------------------------------------------------------------------
  window.DEMO_DATA.MCP_RECORDS = {
    append_to_doc: {
      tool: 'append_to_doc',
      server: 'MCP Server Trigger (bearerAuth)',
      operation: 'append_to_doc',
      request: {
        documentId: 'REDACTED_DOC_ID',
        action: 'insert',
        text: '<redacted payload>',
      },
      response: 'Raw response not available.',
      responseNote: 'Verified audit outcome: doc_status=done.',
      audit:
        'Execution #30: MCP Client — append_to_doc ran successfully. Execution #31: Mark append_to_doc Done succeeded.',
    },
    create_email_draft: {
      tool: 'create_email_draft',
      server: 'MCP Server Trigger (bearerAuth)',
      operation: 'create (draft only, never send)',
      request: {
        resource: 'draft',
        subject: 'Groww — Customer Fee Explainer (DRAFT)',
        body: 'INTERNAL DRAFT — NOT SENT — weekly pulse + fee explainer',
      },
      response: 'Raw response not available.',
      responseNote: 'Verified audit outcome: draft_status=done, email_sent=false.',
      audit:
        'Gmail-only recovery created one unsent draft. Separate from the original append execution.',
    },
  };

  // ---------------------------------------------------------------------------
  // Workflow node definitions (positions in pixels)
  // ---------------------------------------------------------------------------
  window.DEMO_DATA.NODES = [
    { id: 'sheets', label: 'Google Sheets', sub: 'Get row(s) in sheet', icon: '☷', x: 60, y: 210 },
    {
      id: 'validate',
      label: 'Validate Review Dataset',
      sub: 'Code — 1,000 reviews',
      icon: '✦',
      x: 270,
      y: 210,
    },
    { id: 'batches', label: 'Generate Batches', sub: '4 × 25 reviews', icon: '📦', x: 480, y: 210 },
    {
      id: 'gemini',
      label: 'Gemini Classification',
      sub: 'Message a model',
      icon: '✦',
      x: 690,
      y: 210,
    },
    {
      id: 'validate2',
      label: 'Validate Classifications',
      sub: 'Code — deterministic checks',
      icon: '✦',
      x: 900,
      y: 210,
    },
    {
      id: 'generate',
      label: 'Product Pulse + Fee Explainer',
      sub: 'Gemini drafts',
      icon: '📝',
      x: 60,
      y: 340,
    },
    {
      id: 'format',
      label: 'Format & Validate',
      sub: 'Code — ≤250 words / ≤6 bullets',
      icon: '✦',
      x: 270,
      y: 340,
    },
    {
      id: 'wait',
      label: 'Human Approval',
      sub: 'Wait form — Approve / Reject',
      icon: '⏸',
      x: 480,
      y: 340,
      approval: true,
    },
    { id: 'gate', label: 'Approval Gate', sub: 'If — Approve / Reject', icon: '🚦', x: 690, y: 340 },
    {
      id: 'compute',
      label: 'Compute Approval Record',
      sub: 'Code — SHA-256 hash',
      icon: '🔐',
      x: 900,
      y: 340,
    },
    {
      id: 'mcpClient',
      label: 'MCP Client — Delivery Actions',
      sub: 'append_to_doc / create_email_draft',
      icon: '⇄',
      x: 60,
      y: 450,
      mcp: true,
    },
    {
      id: 'mcpServer',
      label: 'MCP Server Trigger',
      sub: 'Authenticated tools',
      icon: '🔌',
      x: 270,
      y: 450,
      mcp: true,
    },
    {
      id: 'googleDocs',
      label: 'Google Docs',
      sub: 'Append structured entry',
      icon: '📄',
      x: 480,
      y: 450,
    },
    {
      id: 'gmail',
      label: 'Gmail Draft',
      sub: 'Create draft — never send',
      icon: '✉',
      x: 690,
      y: 450,
    },
  ];

  // ---------------------------------------------------------------------------
  // Scenario definitions (step sequences)
  // ---------------------------------------------------------------------------
  window.DEMO_DATA.SCENARIOS = {
    reject: {
      id: 'reject',
      steps: [
        'sheets',
        'validate',
        'batches',
        'gemini',
        'validate2',
        'generate',
        'format',
        'wait',
        'gate',
      ],
      stoppedAt: 'gate',
      finalNode: 'gate',
    },
    approve: {
      id: 'approve',
      steps: [
        'sheets',
        'validate',
        'batches',
        'gemini',
        'validate2',
        'generate',
        'format',
        'wait',
        'gate',
        'compute',
        'mcpClient',
        'mcpServer',
        'googleDocs',
        'gmail',
      ],
      stoppedAt: 'gmail',
      finalNode: 'gmail',
    },
  };
})();
