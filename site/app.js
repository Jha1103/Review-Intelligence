(function () {
  'use strict';

  // ---------------------------------------------------------------------------
  // Demo data (sanitized, no credentials or private data)
  // All data derived from verified local n8n executions. No invented data.
  // ---------------------------------------------------------------------------
  const EVIDENCE = window.DEMO_DATA.EVIDENCE;
  const MCP_RECORDS = window.DEMO_DATA.MCP_RECORDS;
  const NODES = window.DEMO_DATA.NODES;
  const SCENARIOS = window.DEMO_DATA.SCENARIOS;

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

  // Inspector tab elements (lazy-loaded)
  let inspectorTabs, inspectorTabPanels;

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
  // Render workflow canvas
  // ---------------------------------------------------------------------------
  function renderCanvas() {
    els.workflowNodes.innerHTML = '';
    els.workflowSvg.innerHTML = '';

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

    const hConn = (x1, x2, y) => drawLine(x1, y, x2, y);
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
      el.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          selectNode(node.id);
        }
      });
      el.tabIndex = 0;
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
    document.querySelectorAll('.workflow-node').forEach((el) => el.classList.remove('selected'));
    const el = document.getElementById(`node-${id}`);
    if (el) el.classList.add('selected');

    const meta = getNodeMeta(id);
    const stateVal = state.nodeStates[id] || 'idle';

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

    document.querySelectorAll('.scenario-card').forEach((c) => c.classList.remove('selected'));
    document.getElementById(`scenario-${scenarioId}`).classList.add('selected');

    els.btnPlay.disabled = false;
    els.btnPause.disabled = true;
    els.btnRestart.disabled = false;

    advanceToNext();
  }

  function advanceToNext() {
    if (!state.scenario) return;
    if (state.currentStepIndex >= state.scenario.steps.length - 1) {
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

    const el = document.getElementById(`node-${nodeId}`);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'center' });

    els.timelineLabel.textContent = `Executing: ${meta.label}`;

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

  // Keyboard navigation
  document.addEventListener('keydown', (e) => {
    // Only handle when focus is not inside an input/textarea/select
    if (e.target.tagName.match(/^(INPUT|TEXTAREA|SELECT)$/i)) return;

    if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
      e.preventDefault();
      const isReject = e.key === 'ArrowLeft';
      const targetId = isReject ? 'scenario-reject' : 'scenario-approve';
      const btn = document.getElementById(targetId);
      if (btn) {
        btn.classList.add('selected');
        const otherId = isReject ? 'scenario-approve' : 'scenario-reject';
        document.getElementById(otherId).classList.remove('selected');
        startScenario(isReject ? 'reject' : 'approve');
      }
    }

    if (e.key === ' ') {
      e.preventDefault();
      if (!state.scenario) return;
      if (state.animationTimer) clearTimeout(state.animationTimer);
      playPause();
    }
  });

  // Initialize
  renderCanvas();
  resetDemo();

  // Mobile navigation toggle. The button exists in the markup but was
  // never wired up, so the menu could not be opened on small screens.
  const menuToggle = document.getElementById('menu-toggle');
  const mobileNav = document.getElementById('mobile-nav');
  if (menuToggle && mobileNav) {
    const setNav = (open) => {
      mobileNav.hidden = !open;
      menuToggle.setAttribute('aria-expanded', String(open));
      menuToggle.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
      menuToggle.textContent = open ? '\u2715' : '\u2630';
    };
    menuToggle.addEventListener('click', () => setNav(mobileNav.hidden));
    mobileNav.addEventListener('click', (e) => {
      if (e.target.tagName === 'A') setNav(false);
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !mobileNav.hidden) setNav(false);
    });
    // Leaving mobile width should never strand the panel open.
    window.matchMedia('(min-width: 861px)').addEventListener('change', (e) => {
      if (e.matches) setNav(false);
    });
  }

  // Expose for debugging
  window.__reviewPulse = { NODES, SCENARIOS, EVIDENCE, state };
})();
