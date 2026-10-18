(function () {
  'use strict';

  // ---------------------------------------------------------------------------
  // Verified execution evidence (sanitized, no credentials or private data)
  // ---------------------------------------------------------------------------
  const EVIDENCE = {
    reject: {
      runId: 'execution_26',
      scenario: 'reject',
      title: 'Reject — zero external writes',
      description: 'Approval gate returned Reject. Workflow stopped before the MCP Client. append_to_doc: not invoked. create_email_draft: not invoked. Google Docs: unchanged. Gmail: no draft created.',
      meta: ['scenario: reject', 'external writes: 0', 'audit: blocked'],
      stoppedAtNode: 'Wait (human approval)',
    },
    approve: {
      runId: 'groww_27',
      scenario: 'approve',
      title: 'Approve — full delivery',
      description: 'Approval gate returned Approve. MCP Client invoked append_to_doc (Execution #30) then create_email_draft via Gmail-only recovery. Both actions completed successfully.',
      meta: ['scenario: approve', 'doc_status: done', 'draft_status: done', 'email sent: no'],
    },
  };

  // MCP tool records (sanitized)
  const MCP_RECORDS = {
    append_to_doc: {
      tool: 'append_to_doc',
      operation: 'update',
      auth: 'bearerAuth (n8n credential)',
      request: JSON.stringify(
        {
          documentId: 'REDACTED_DOC_ID',
          action: 'insert',
          text: '{{ JSON.stringify(JSON.parse($json.payload_json), null, 2) + "\\n\\n" }}',
        },
        null,
        2
      ),
      response: JSON.stringify(
        {
          status: 'success',
          doc_status: 'done',
          entry_appended: true,
          dated_entry: true,
        },
        null,
        2
      ),
      audit: 'Verified — append_to_doc (Execution #30) then Mark Done (Execution #31)',
    },
    create_email_draft: {
      tool: 'create_email_draft',
      operation: 'create (draft only, never send)',
      auth: 'bearerAuth (n8n credential)',
      request: JSON.stringify(
        {
          resource: 'draft',
          subject: 'Groww — Customer Fee Explainer (DRAFT)',
          body: 'INTERNAL DRAFT — NOT SENT — weekly pulse + fee explainer',
        },
        null,
        2
      ),
      response: JSON.stringify(
        {
          status: 'success',
          draft_status: 'done',
          draft_created: true,
          email_sent: false,
        },
        null,
        2
      ),
      audit: 'Verified — Gmail-only recovery created one unsent draft',
    },
  };

  // ---------------------------------------------------------------------------
  // Workflow node definitions
  // ---------------------------------------------------------------------------
  const NODES = [
    {
      id: 'sheets',
      label: 'Google Sheets',
      sub: 'Get row(s) in sheet',
      icon: '☷',
      x: 60,
      y: 210,
    },
    {
      id: 'validate',
      label: 'Validate Review Dataset',
      sub: 'Code — 1,000 reviews',
      icon: '✦',
      x: 270,
      y: 210,
    },
    {
      id: 'batches',
      label: 'Generate Batches',
      sub: '4 × 25 reviews',
      icon: '📦',
      x: 480,
      y: 210,
    },
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
    {
      id: 'gate',
      label: 'Approval Gate',
      sub: 'If — Approve / Reject',
      icon: '🚦',
      x: 690,
      y: 340,
    },
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
  const SCENARIOS = {
    reject: {
      id: 'reject',
      steps: [
        'sheets', 'validate', 'batches', 'gemini', 'validate2', 'generate', 'format', 'wait', 'gate',
      ],
      stoppedAt: 'gate',
      finalNode: 'gate',
    },
    approve: {
      id: 'approve',
      steps: [
        'sheets', 'validate', 'batches', 'gemini', 'validate2', 'generate', 'format', 'wait', 'gate', 'compute', 'mcpClient', 'mcpServer', 'googleDocs', 'gmail',
      ],
      stoppedAt: 'gmail',
      finalNode: 'gmail',
    },
  };

  // ---------------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------------
  let state = {
    scenario: null,
    currentStepIndex: -1,
    isPlaying: false,
    isPaused: false,
    speed: 1.5,
    nodeStates: {},
    animationTimer: null,
  };

  // Initialize node states
  NODES.forEach((n) => {
    state.nodeStates[n.id] = 'idle';
  });

  // ---------------------------------------------------------------------------
  // DOM elements
  // ---------------------------------------------------------------------------
  const els = {
    scenarioReject: document.getElementById('scenario-reject'),
    scenarioApprove: document.getElementById('scenario-approve'),
    btnRestart: document.getElementById('btn-restart'),
    btnPause: document.getElementById('btn-pause'),
    btnPlay: document.getElementById('btn-play'),
    btnRunDemo: document.getElementById('run-demo-btn'),
    timelineLabel: document.getElementById('timeline-label'),
    speedSelect: document.getElementById('speed-select'),
    modeLabel: document.getElementById('mode-label'),
    badgeDot: document.getElementById('badge-dot'),
    workflowNodes: document.getElementById('workflow-nodes'),
    workflowSvg: document.getElementById('workflow-svg'),
    inspectorToolName: document.getElementById('inspector-tool-name'),
    inspectorToolDisplay: document.getElementById('inspector-tool-display'),
    inspectorOperation: document.getElementById('inspector-operation'),
    inspectorAuth: document.getElementById('inspector-auth'),
    inspectorRequest: document.getElementById('inspector-request'),
    inspectorResponse: document.getElementById('inspector-response'),
    inspectorAudit: document.getElementById('inspector-audit'),
    inspectorBadge: document.getElementById('inspector-badge'),
    canvasBadge: document.getElementById('canvas-badge'),
  };

  // ---------------------------------------------------------------------------
  // Render workflow canvas
  // ---------------------------------------------------------------------------
  function renderCanvas() {
    els.workflowNodes.innerHTML = '';
    els.workflowSvg.innerHTML = '';

    // Draw connection lines
    const drawLine = (x1, y1, x2, y2) => {
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', x1 + 85);
      line.setAttribute('y1', y1 + 47);
      line.setAttribute('x2', x2);
      line.setAttribute('y2', y2 + 47);
      line.setAttribute('stroke', '#2a3637');
      line.setAttribute('stroke-width', '2');
      line.setAttribute('class', 'conn-line');
      els.workflowSvg.appendChild(line);
      return line;
    };

    // Horizontal connections
    const hConn = (x1, x2, y) => drawLine(x1, y, x2, y);
    // Vertical connections
    const vConn = (x, y1, y2) => drawLine(x, y1, x, y2);

    // Row 1 horizontal chain
    hConn(60 + 170, 270, 210 + 47);
    hConn(270 + 170, 480, 210 + 47);
    hConn(480 + 170, 690, 210 + 47);
    hConn(690 + 170, 900, 210 + 47);
    // Row 2 horizontal chain
    hConn(60 + 170, 270, 340 + 47);
    hConn(270 + 170, 480, 340 + 47);
    hConn(480 + 170, 690, 340 + 47);
    hConn(690 + 170, 900, 340 + 47);
    // Row 3 horizontal chain
    hConn(60 + 170, 270, 450 + 47);
    hConn(270 + 170, 480, 450 + 47);
    hConn(480 + 170, 690, 450 + 47);
    hConn(690 + 170, 900, 450 + 47);
    // Vertical connections between rows
    vConn(60 + 85, 210 + 95, 340);
    vConn(480 + 85, 340 + 95, 450);

    // Render nodes
    NODES.forEach((node) => {
      const el = document.createElement('div');
      el.className = `workflow-node ${state.nodeStates[node.id] || 'idle'}${node.mcp ? ' mcp' : ''}${node.approval ? ' approval' : ''}`;
      el.id = `node-${node.id}`;
      el.dataset.nodeId = node.id;
      el.style.left = `${node.x}px`;
      el.style.top = `${node.y}px`;

      el.innerHTML = `
        <div class="node-icon ${node.mcp ? 'mcp' : node.approval ? 'approval' : ''}">${node.icon}</div>
        <div class="node-label">
          <div style="font-weight:700;color:#e5eee5;font-size:12px">${node.label}</div>
          <div style="font-size:10px;color:#8ba8a1">${node.sub}</div>
        </div>
      `;

      el.addEventListener('click', () => selectNode(node.id));
      els.workflowNodes.appendChild(el);
    });
  }

  // ---------------------------------------------------------------------------
  // Node state management
  // ---------------------------------------------------------------------------
  function setNodeState(id, status) {
    state.nodeStates[id] = status;
    const el = document.getElementById(`node-${id}`);
    if (!el) return;
    el.className = `workflow-node ${status}${getNodeMeta(id).mcp ? ' mcp' : ''}${getNodeMeta(id).approval ? ' approval' : ''}`;
  }

  function getNodeMeta(id) {
    return NODES.find((n) => n.id === id) || {};
  }

  function selectNode(id) {
    // Clear previous selection
    document.querySelectorAll('.workflow-node').forEach((el) => el.classList.remove('selected'));
    const el = document.getElementById(`node-${id}`);
    if (el) el.classList.add('selected');

    const meta = getNodeMeta(id);
    const stateVal = state.nodeStates[id] || 'idle';

    // Populate inspector
    els.inspectorToolName.textContent = meta.label || '—';
    els.inspectorToolDisplay.textContent = meta.sub || '—';
    els.inspectorOperation.textContent = stateVal;
    els.inspectorBadge.textContent = stateVal.toUpperCase();

    if (meta.mcp && MCP_RECORDS[meta.label]) {
      const rec = MCP_RECORDS[meta.label];
      els.inspectorRequest.textContent = rec.request;
      els.inspectorResponse.textContent = rec.response;
      els.inspectorAudit.textContent = rec.audit;
      els.inspectorAuth.textContent = rec.auth;
    } else {
      els.inspectorRequest.textContent = '—';
      els.inspectorResponse.textContent = '—';
      els.inspectorAudit.textContent = 'No MCP call';
      els.inspectorAuth.textContent = 'n/a';
    }
  }

  // ---------------------------------------------------------------------------
  // Demo execution engine
  // ---------------------------------------------------------------------------
  function resetDemo() {
    if (state.animationTimer) {
      clearTimeout(state.animationTimer);
      state.animationTimer = null;
    }
    state.isPlaying = false;
    state.isPaused = false;
    state.currentStepIndex = -1;
    NODES.forEach((n) => {
      state.nodeStates[n.id] = 'idle';
    });
    renderCanvas();
    updateControls();
    els.timelineLabel.textContent = 'Select a scenario to begin';
    els.modeLabel.textContent = 'Idle';
    els.badgeDot.classList.remove('active');
    els.canvasBadge.textContent = 'IDLE';
    selectNode(null);
  }

  function startScenario(scenarioId) {
    resetDemo();
    state.scenario = SCENARIOS[scenarioId];
    const ev = EVIDENCE[scenarioId];
    els.modeLabel.textContent = ev.title;
    els.badgeDot.classList.add('active');
    els.canvasBadge.textContent = scenarioId.toUpperCase();
    els.timelineLabel.textContent = `Scenario: ${ev.title}`;

    // Highlight selected scenario card
    document.querySelectorAll('.scenario-card').forEach((c) => c.classList.remove('selected'));
    document.getElementById(`scenario-${scenarioId}`).classList.add('selected');

    // Enable controls
    els.btnPlay.disabled = false;
    els.btnPause.disabled = true;
    els.btnRestart.disabled = false;

    // Start at first node
    advanceToNext();
  }

  function advanceToNext() {
    if (!state.scenario) return;
    if (state.currentStepIndex >= state.scenario.steps.length - 1) {
      // Finished
      state.isPlaying = false;
      updateControls();
      els.timelineLabel.textContent = 'Execution complete';
      return;
    }

    state.currentStepIndex++;
    const nodeId = state.scenario.steps[state.currentStepIndex];
    const meta = getNodeMeta(nodeId);

    setNodeState(nodeId, 'running');
    selectNode(nodeId);

    // Scroll node into view
    const el = document.getElementById(`node-${nodeId}`);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'center' });

    els.timelineLabel.textContent = `Executing: ${meta.label}`;

    // Auto-advance after delay
    const delay = Math.max(600, 1200 / state.speed);
    state.animationTimer = setTimeout(() => {
      setNodeState(nodeId, 'done');
      state.animationTimer = setTimeout(advanceToNext, 400 / state.speed);
    }, delay);
  }

  function playPause() {
    if (!state.scenario) return;
    if (state.isPaused) {
      state.isPaused = false;
      els.btnPause.disabled = false;
      els.btnPlay.disabled = true;
      els.timelineLabel.textContent = 'Resuming...';
      state.animationTimer = setTimeout(advanceToNext, 600 / state.speed);
    } else {
      state.isPaused = true;
      els.btnPause.disabled = true;
      els.btnPlay.disabled = false;
      els.timelineLabel.textContent = 'Paused';
    }
    updateControls();
  }

  function updateControls() {
    const hasScenario = !!state.scenario;
    const atEnd = state.scenario && state.currentStepIndex >= state.scenario.steps.length - 1;

    els.btnRestart.disabled = !hasScenario;
    els.btnPlay.disabled = !hasScenario || state.isPlaying || atEnd;
    els.btnPause.disabled = !hasScenario || !state.isPlaying || state.isPaused || atEnd;
  }

  // ---------------------------------------------------------------------------
  // Event listeners
  // ---------------------------------------------------------------------------
  els.scenarioReject.addEventListener('click', () => startScenario('reject'));
  els.scenarioApprove.addEventListener('click', () => startScenario('approve'));

  els.btnRunDemo.addEventListener('click', () => {
    // Default to approve scenario when clicking hero button
    startScenario('approve');
  });

  els.btnRestart.addEventListener('click', () => {
    if (state.scenario) startScenario(state.scenario.id);
  });

  els.btnPause.addEventListener('click', () => {
    if (state.animationTimer) clearTimeout(state.animationTimer);
    playPause();
  });

  els.btnPlay.addEventListener('click', () => {
    if (state.animationTimer) clearTimeout(state.animationTimer);
    playPause();
  });

  els.speedSelect.addEventListener('change', () => {
    state.speed = parseFloat(els.speedSelect.value);
  });

  // Initialize
  renderCanvas();
  resetDemo();

  // Expose for debugging
  window.__reviewPulse = { NODES, SCENARIOS, EVIDENCE, state };
})();