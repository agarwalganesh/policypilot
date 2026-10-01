/**
 * PolicyPilot — Chat Page JavaScript
 * Handles conversation management, message rendering, streaming, and source preview
 */

const CHAT = {
  currentConversationId: null,
  isLoading: false,

  async init() {
    if (!APP.requireAuth()) return;

    this.bindEvents();
    await this.loadConversations();

    // Auto-resize textarea
    const textarea = document.getElementById('query-input');
    textarea.addEventListener('input', () => {
      textarea.style.height = 'auto';
      textarea.style.height = Math.min(textarea.scrollHeight, 180) + 'px';
      const len = textarea.value.length;
      document.getElementById('char-count').textContent = `${len}/2000`;
      document.getElementById('send-btn').disabled = len < 2 || this.isLoading;
    });
  },

  bindEvents() {
    // New chat
    document.getElementById('new-chat-btn').addEventListener('click', () => this.newChat());

    // Send button
    document.getElementById('send-btn').addEventListener('click', () => this.sendMessage());

    // Enter to send (Shift+Enter for newline)
    document.getElementById('query-input').addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (!this.isLoading && document.getElementById('query-input').value.trim().length >= 2) {
          this.sendMessage();
        }
      }
    });

    // Suggestion buttons
    document.querySelectorAll('.suggestion-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const q = btn.dataset.q;
        document.getElementById('query-input').value = q;
        document.getElementById('query-input').dispatchEvent(new Event('input'));
        this.sendMessage();
      });
    });

    // Sidebar collapse
    document.getElementById('collapse-btn')?.addEventListener('click', () => {
      document.getElementById('sidebar').classList.toggle('collapsed');
    });
    document.getElementById('sidebar-toggle-btn')?.addEventListener('click', () => {
      document.getElementById('sidebar').classList.toggle('mobile-open');
    });

    // Source panel close
    document.getElementById('close-source-panel')?.addEventListener('click', () => {
      document.getElementById('source-panel').classList.remove('open');
    });

    // Conversation search
    document.getElementById('conv-search')?.addEventListener('input', (e) => {
      this.filterConversations(e.target.value);
    });
  },

  newChat() {
    this.currentConversationId = null;
    document.getElementById('messages-area').innerHTML = `
      <div class="welcome-state" id="welcome-state">
        <div class="welcome-icon">
          <svg viewBox="0 0 64 64" fill="none"><rect width="64" height="64" rx="16" fill="url(#wg2)"/><path d="M14 20h24a8 8 0 010 16H14V20z" fill="white" opacity="0.9"/><path d="M14 36h12v12H14V36z" fill="white" opacity="0.6"/><circle cx="44" cy="44" r="8" fill="white" opacity="0.8"/><defs><linearGradient id="wg2" x1="0" y1="0" x2="64" y2="64"><stop offset="0%" stop-color="#6366f1"/><stop offset="100%" stop-color="#8b5cf6"/></linearGradient></defs></svg>
        </div>
        <h2 class="welcome-title">New Conversation</h2>
        <p class="welcome-subtitle">Ask anything about Physics Wallah's company policies.</p>
      </div>`;
    document.getElementById('chat-title').textContent = 'New Conversation';
    document.getElementById('query-input').focus();
    document.querySelectorAll('.conv-item').forEach(el => el.classList.remove('active'));
  },

  async loadConversations() {
    try {
      const res = await APP.apiFetch('/chat/conversations');
      const convs = await res.json();
      this.renderConversationList(convs);
    } catch (err) {
      console.error('Failed to load conversations:', err);
    }
  },

  renderConversationList(convs) {
    const list = document.getElementById('conversations-list');
    if (!convs.length) {
      list.innerHTML = `<p style="padding:12px;font-size:12px;color:var(--text-tertiary);text-align:center;">No conversations yet</p>`;
      return;
    }
    list.innerHTML = convs.map(c => `
      <div class="conv-item ${c.id === this.currentConversationId ? 'active' : ''}"
           data-id="${c.id}" title="${APP.escapeHtml(c.title || 'Conversation')}">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>
        <span>${APP.escapeHtml((c.title || 'New Chat').substring(0, 32))}</span>
      </div>
    `).join('');

    list.querySelectorAll('.conv-item').forEach(item => {
      item.addEventListener('click', () => this.loadConversation(item.dataset.id, item.querySelector('span').textContent));
    });
  },

  filterConversations(query) {
    document.querySelectorAll('.conv-item').forEach(item => {
      const visible = item.querySelector('span').textContent.toLowerCase().includes(query.toLowerCase());
      item.style.display = visible ? '' : 'none';
    });
  },

  async loadConversation(convId, title) {
    this.currentConversationId = convId;
    document.getElementById('chat-title').textContent = title;
    document.querySelectorAll('.conv-item').forEach(el => {
      el.classList.toggle('active', el.dataset.id === convId);
    });

    const area = document.getElementById('messages-area');
    area.innerHTML = `<div class="conv-skeleton" style="margin:20px;height:80px;"></div>`;

    try {
      const res = await APP.apiFetch(`/chat/conversations/${convId}/messages`);
      const msgs = await res.json();
      area.innerHTML = '';
      msgs.forEach(m => this.appendMessage(m.role, m.content, m.sources, m.decision, m.confidence, m.created_at));
      this.scrollToBottom();
    } catch (err) {
      APP.toast('Failed to load conversation', 'error');
    }
  },

  async sendMessage() {
    const input = document.getElementById('query-input');
    const query = input.value.trim();
    if (!query || this.isLoading) return;

    // Hide welcome state
    document.getElementById('welcome-state')?.remove();

    // Add user message
    this.appendMessage('user', query);

    // Clear input
    input.value = '';
    input.style.height = 'auto';
    document.getElementById('char-count').textContent = '0/2000';
    document.getElementById('send-btn').disabled = true;

    // Show loading
    const loadingId = this.appendLoadingMessage();
    this.setLoading(true);

    try {
      const res = await APP.apiFetch('/chat/stream', {
        method: 'POST',
        body: JSON.stringify({
          query,
          conversation_id: this.currentConversationId,
          stream: true,
        }),
      });

      if (!res.ok) {
        throw new Error(`Server error: ${res.status}`);
      }

      await this.handleStream(res, loadingId);

    } catch (err) {
      this.removeLoadingMessage(loadingId);
      this.appendMessage('assistant', `⚠️ Error: ${err.message}. Please try again.`, [], 'REFUSE');
      APP.toast(err.message, 'error');
    } finally {
      this.setLoading(false);
    }

    await this.loadConversations();
  },

  async handleStream(res, loadingId) {
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let fullText = '';
    let sources = [];
    let decision = 'ANSWER';
    let confidence = 0;
    let convId = this.currentConversationId;

    // Replace loading with streaming bubble
    this.removeLoadingMessage(loadingId);
    const streamId = `msg-${Date.now()}`;
    const msgWrapper = document.createElement('div');
    msgWrapper.className = 'message-wrapper assistant';
    msgWrapper.id = streamId;
    msgWrapper.innerHTML = `
      <div class="message-avatar assistant">P</div>
      <div class="message-content">
        <div class="message-bubble" id="${streamId}-bubble"></div>
      </div>`;
    document.getElementById('messages-area').appendChild(msgWrapper);

    const bubble = document.getElementById(`${streamId}-bubble`);

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split('\n').filter(l => l.startsWith('data: '));

      for (const line of lines) {
        try {
          const data = JSON.parse(line.slice(6));
          if (data.type === 'token') {
            fullText += data.content;
            bubble.innerHTML = APP.renderMarkdown(fullText);
            this.scrollToBottom();
          } else if (data.type === 'done') {
            sources = data.sources || [];
            decision = data.decision || 'ANSWER';
            confidence = data.confidence || 0;
            convId = data.conversation_id || convId;
            debugInfo = data.debug_info || null;
          }
        } catch (e) { /* ignore parse errors */ }
      }
    }

    this.currentConversationId = convId;

    // Apply decision styling
    if (decision === 'REFUSE') {
      bubble.classList.add('refuse');
    }

    // Add metadata + citations
    const meta = document.createElement('div');
    meta.className = 'message-meta';
    const confLevel = confidence > 0.75 ? 'high' : confidence > 0.45 ? 'medium' : 'low';
    meta.innerHTML = `
      <span class="message-time">${APP.formatTime(new Date().toISOString())}</span>
      ${decision !== 'REFUSE' ? `<span class="confidence-pill ${confLevel}">${Math.round(confidence * 100)}% confidence</span>` : ''}
      <span class="decision-badge ${decision}">${decision}</span>
    `;
    msgWrapper.querySelector('.message-content').appendChild(meta);

    // Developer Diagnostic Panel
    if (debugInfo) {
      const diag = document.createElement('div');
      diag.className = 'developer-diag-panel';
      diag.innerHTML = `
        <div class="diag-header">🛠️ Developer RAG Diagnostics</div>
        <div class="diag-grid">
          <div><span class="diag-label">Retrieval:</span> <strong>${debugInfo.retrieval_success ? '✓' : '✗'}</strong></div>
          <div><span class="diag-label">Chunks retrieved:</span> <strong>${debugInfo.chunks_retrieved}</strong></div>
          <div><span class="diag-label">Evidence:</span> <span class="diag-pill ${debugInfo.evidence_status.toLowerCase()}">${debugInfo.evidence_status}</span></div>
          <div><span class="diag-label">Corrective RAG:</span> <strong>${debugInfo.corrective_rag_used ? 'USED' : 'NOT USED'}</strong></div>
          <div><span class="diag-label">Retries:</span> <strong>${debugInfo.retry_count}</strong></div>
          <div><span class="diag-label">Decision:</span> <span class="decision-badge ${debugInfo.decision}">${debugInfo.decision}</span></div>
        </div>
      `;
      msgWrapper.querySelector('.message-content').appendChild(diag);
    }

    // Citations
    if (sources.length > 0 && decision !== 'REFUSE') {
      const citBlock = document.createElement('div');
      citBlock.className = 'citations-block';
      citBlock.innerHTML = `
        <div class="citations-header">📚 Sources</div>
        ${sources.map((s, i) => `
          <div class="citation-item" data-source='${JSON.stringify(s).replace(/'/g, "&#39;")}'>
            <span>📄</span>
            <div>
              <div class="citation-doc">${APP.escapeHtml(s.document_name)}</div>
              <div class="citation-info">
                ${s.page ? `Page ${s.page}` : ''}
                ${s.section ? ` · §${s.section}` : ''}
                ${s.version ? ` · v${s.version}` : ''}
              </div>
            </div>
          </div>
        `).join('')}
      `;
      citBlock.querySelectorAll('.citation-item').forEach(item => {
        item.addEventListener('click', () => {
          const src = JSON.parse(item.dataset.source.replace(/&#39;/g, "'"));
          this.showSourcePreview(src);
        });
      });
      msgWrapper.querySelector('.message-content').appendChild(citBlock);
    }

    this.scrollToBottom();
  },

  appendMessage(role, content, sources = [], decision = 'ANSWER', confidence = null, timestamp = null) {
    const area = document.getElementById('messages-area');
    const wrapper = document.createElement('div');
    wrapper.className = `message-wrapper ${role}`;

    const isRefuse = decision === 'REFUSE';
    const confLevel = confidence > 0.75 ? 'high' : confidence > 0.45 ? 'medium' : 'low';

    wrapper.innerHTML = `
      <div class="message-avatar ${role}">${role === 'user' ? (APP.user?.name?.[0] || 'U') : 'P'}</div>
      <div class="message-content">
        <div class="message-bubble ${isRefuse ? 'refuse' : ''}">
          ${APP.renderMarkdown(content)}
        </div>
        ${confidence !== null || timestamp ? `
          <div class="message-meta">
            ${timestamp ? `<span class="message-time">${APP.formatTime(timestamp)}</span>` : ''}
            ${confidence !== null && role === 'assistant' && !isRefuse ? `<span class="confidence-pill ${confLevel}">${Math.round(confidence * 100)}% confidence</span>` : ''}
            ${role === 'assistant' ? `<span class="decision-badge ${decision}">${decision}</span>` : ''}
          </div>` : ''}
      </div>`;

    area.appendChild(wrapper);
    this.scrollToBottom();
  },

  appendLoadingMessage() {
    const id = `loading-${Date.now()}`;
    const area = document.getElementById('messages-area');
    const wrapper = document.createElement('div');
    wrapper.className = 'message-wrapper assistant';
    wrapper.id = id;
    wrapper.innerHTML = `
      <div class="message-avatar assistant">P</div>
      <div class="message-content">
        <div class="message-bubble">
          <div class="typing-indicator">
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
          </div>
          <div class="agent-status" id="${id}-status">Analyzing query...</div>
        </div>
      </div>`;
    area.appendChild(wrapper);
    this.scrollToBottom();

    // Simulate agent progress messages
    const steps = ['Analyzing query...', 'Checking access permissions...', 'Searching policy documents...', 'Evaluating evidence...', 'Generating answer...'];
    let step = 0;
    this._loadingTimer = setInterval(() => {
      step = (step + 1) % steps.length;
      const el = document.getElementById(`${id}-status`);
      if (el) el.textContent = steps[step];
    }, 1800);

    return id;
  },

  removeLoadingMessage(id) {
    clearInterval(this._loadingTimer);
    document.getElementById(id)?.remove();
  },

  setLoading(loading) {
    this.isLoading = loading;
    const dot = document.getElementById('status-dot');
    const text = document.getElementById('status-text');
    if (loading) {
      dot?.classList.add('loading');
      if (text) text.textContent = 'Processing...';
    } else {
      dot?.classList.remove('loading');
      if (text) text.textContent = 'Ready';
    }
  },

  showSourcePreview(source) {
    const panel = document.getElementById('source-panel');
    const content = document.getElementById('source-panel-content');

    content.innerHTML = `
      <div class="source-doc-name">${APP.escapeHtml(source.document_name)}</div>
      <div class="source-meta">
        ${source.page ? `📑 Page ${source.page}` : ''}
        ${source.version ? ` · v${source.version}` : ''}
        ${source.effective_date ? ` · Effective: ${source.effective_date}` : ''}
        ${source.source_file ? `<br><span style="font-size:10px;opacity:0.7;">File: ${source.source_file}</span>` : ''}
      </div>
      ${source.relevant_text ? `
        <div class="citations-header" style="margin-bottom:8px;">Relevant Extract</div>
        <div class="source-text-block">${APP.escapeHtml(source.relevant_text)}</div>
      ` : '<p style="color:var(--text-tertiary);font-size:13px;">No text preview available.</p>'}
    `;

    panel.classList.add('open');
  },

  scrollToBottom() {
    const area = document.getElementById('messages-area');
    area.scrollTop = area.scrollHeight;
  },
};

document.addEventListener('DOMContentLoaded', () => CHAT.init());
