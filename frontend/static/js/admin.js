/**
 * PolicyPilot — Admin Dashboard JavaScript
 */

const ADMIN = {
  async init() {
    if (!APP.requireAdmin()) return;
    this.bindEvents();
    await Promise.all([this.loadAnalytics(), this.loadDocuments(), this.loadAuditLogs()]);
  },

  bindEvents() {
    document.getElementById('upload-btn')?.addEventListener('click', () => {
      document.getElementById('upload-modal').style.display = 'flex';
    });
    document.getElementById('close-upload-modal')?.addEventListener('click', () => {
      document.getElementById('upload-modal').style.display = 'none';
    });
    document.getElementById('cancel-upload')?.addEventListener('click', () => {
      document.getElementById('upload-modal').style.display = 'none';
    });
    document.getElementById('upload-form')?.addEventListener('submit', (e) => this.handleUpload(e));

    // File input
    const fileInput = document.getElementById('file-input');
    const dropZone = document.getElementById('file-drop-zone');
    fileInput?.addEventListener('change', () => {
      const f = fileInput.files[0];
      if (f) document.getElementById('file-name').textContent = f.name;
    });
    dropZone?.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('drag-over'); });
    dropZone?.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
    dropZone?.addEventListener('drop', (e) => {
      e.preventDefault(); dropZone.classList.remove('drag-over');
      const f = e.dataTransfer.files[0];
      if (f) { fileInput.files = e.dataTransfer.files; document.getElementById('file-name').textContent = f.name; }
    });

    // Filters
    document.getElementById('category-filter')?.addEventListener('change', () => this.loadDocuments());
    document.getElementById('status-filter')?.addEventListener('change', () => this.loadDocuments());
    document.getElementById('decision-filter')?.addEventListener('change', () => this.loadAuditLogs());
  },

  async loadAnalytics() {
    try {
      const res = await APP.apiFetch('/admin/analytics');
      const data = await res.json();

      const metrics = [
        { icon: '📄', label: 'Total Documents', value: data.total_documents, bg: '#eef2ff' },
        { icon: '✅', label: 'Active Policies', value: data.active_policies, bg: '#ecfdf5' },
        { icon: '📦', label: 'Archived', value: data.archived_policies, bg: '#f3f4f6' },
        { icon: '💬', label: 'Total Queries', value: data.total_queries, bg: '#eff6ff' },
        { icon: '✔️', label: 'Answered', value: data.answered_queries, bg: '#ecfdf5' },
        { icon: '🚫', label: 'Refused', value: data.refused_queries, bg: '#fff7ed' },
        { icon: '⚡', label: 'Avg Latency', value: data.avg_latency_ms ? `${data.avg_latency_ms}ms` : 'N/A', bg: '#faf5ff' },
        { icon: '🎯', label: 'Success Rate', value: data.retrieval_success_rate ? `${data.retrieval_success_rate}%` : 'N/A', bg: '#ecfdf5' },
      ];

      document.getElementById('metrics-grid').innerHTML = metrics.map(m => `
        <div class="metric-card">
          <div class="metric-icon" style="background:${m.bg}">${m.icon}</div>
          <div class="metric-value">${m.value}</div>
          <div class="metric-label">${m.label}</div>
        </div>
      `).join('');
    } catch (err) {
      APP.toast('Failed to load analytics', 'error');
    }
  },

  async loadDocuments() {
    const tbody = document.getElementById('docs-tbody');
    tbody.innerHTML = `<tr><td colspan="7" class="table-loading">Loading...</td></tr>`;
    try {
      const res = await APP.apiFetch('/documents');
      let docs = await res.json();

      const cat = document.getElementById('category-filter')?.value;
      const status = document.getElementById('status-filter')?.value;
      if (cat) docs = docs.filter(d => d.category === cat);
      if (status) docs = docs.filter(d => d.status === status);

      if (!docs.length) {
        tbody.innerHTML = `<tr><td colspan="7" class="table-loading">No documents found</td></tr>`;
        return;
      }

      tbody.innerHTML = docs.map(d => `
        <tr>
          <td><strong>${APP.escapeHtml(d.name)}</strong></td>
          <td>${d.category || '—'}</td>
          <td>${d.active_version || '—'}</td>
          <td><span class="status-badge ${d.status || 'archived'}">${d.status || 'no version'}</span></td>
          <td>${d.chunk_count || 0}</td>
          <td>${d.indexed ? '<span class="indexed-yes">✓ Yes</span>' : '<span class="indexed-no">No</span>'}</td>
          <td>
            <div class="table-actions">
              <button class="table-action-btn" title="View" onclick="ADMIN.viewDocument('${d.id}')">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
              </button>
              <button class="table-action-btn" title="Re-index" onclick="ADMIN.reindexDocument('${d.id}')">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/></svg>
              </button>
              <button class="table-action-btn danger" title="Archive" onclick="ADMIN.archiveDocument('${d.id}')">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="21 8 21 21 3 21 3 8"/><rect x="1" y="3" width="22" height="5"/><line x1="10" y1="12" x2="14" y2="12"/></svg>
              </button>
            </div>
          </td>
        </tr>
      `).join('');
    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="7" class="table-loading">Failed to load documents</td></tr>`;
    }
  },

  async loadAuditLogs() {
    const tbody = document.getElementById('audit-tbody');
    tbody.innerHTML = `<tr><td colspan="5" class="table-loading">Loading...</td></tr>`;
    try {
      const decision = document.getElementById('decision-filter')?.value;
      const url = `/admin/audit-logs?per_page=50${decision ? `&decision=${decision}` : ''}`;
      const res = await APP.apiFetch(url);
      const data = await res.json();

      if (!data.items?.length) {
        tbody.innerHTML = `<tr><td colspan="5" class="table-loading">No audit logs yet</td></tr>`;
        return;
      }

      tbody.innerHTML = data.items.map(log => `
        <tr>
          <td>${APP.formatDate(log.created_at)}</td>
          <td title="${APP.escapeHtml(log.query)}">${APP.escapeHtml(log.query.substring(0, 60))}${log.query.length > 60 ? '...' : ''}</td>
          <td><span class="status-badge ${log.decision === 'ANSWER' ? 'active' : 'archived'}">${log.decision || '—'}</span></td>
          <td>${log.retry_count}</td>
          <td>${log.latency_ms ? `${log.latency_ms}ms` : '—'}</td>
        </tr>
      `).join('');
    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="5" class="table-loading">Failed to load logs</td></tr>`;
    }
  },

  async handleUpload(e) {
    e.preventDefault();
    const fileInput = document.getElementById('file-input');
    if (!fileInput.files[0]) { APP.toast('Please select a file', 'error'); return; }

    const btn = document.getElementById('upload-submit-btn');
    btn.disabled = true;
    btn.querySelector('span').textContent = 'Uploading & Indexing...';

    const fd = new FormData();
    fd.append('file', fileInput.files[0]);
    fd.append('name', document.getElementById('up-name').value || fileInput.files[0].name);
    fd.append('version', document.getElementById('up-version').value || '1.0');
    fd.append('category', document.getElementById('up-category').value);
    fd.append('status', document.getElementById('up-status').value);
    fd.append('notes', document.getElementById('up-notes').value);

    try {
      const res = await fetch('/documents/upload', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${APP.token}` },
        body: fd,
      });
      const data = await res.json();

      if (res.ok) {
        APP.toast(`✅ Uploaded: ${data.chunk_count} chunks indexed`, 'success');
        document.getElementById('upload-modal').style.display = 'none';
        document.getElementById('upload-form').reset();
        document.getElementById('file-name').textContent = 'Max 50MB';
        await Promise.all([this.loadDocuments(), this.loadAnalytics()]);
      } else {
        APP.toast(data.error || 'Upload failed', 'error');
      }
    } catch (err) {
      APP.toast('Upload failed: ' + err.message, 'error');
    } finally {
      btn.disabled = false;
      btn.querySelector('span').textContent = 'Upload & Index';
    }
  },

  async reindexDocument(docId) {
    if (!confirm('Re-index this document? This will delete and rebuild all chunks.')) return;
    try {
      const res = await APP.apiFetch(`/documents/${docId}/reindex`, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        APP.toast(`Re-indexed: ${data.chunk_count} chunks`, 'success');
        await this.loadDocuments();
      } else {
        APP.toast(data.error || 'Re-index failed', 'error');
      }
    } catch (err) { APP.toast('Re-index failed', 'error'); }
  },

  async archiveDocument(docId) {
    if (!confirm('Archive this document? It will no longer be used for policy answers.')) return;
    try {
      const res = await APP.apiFetch(`/documents/${docId}/archive`, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        APP.toast('Document archived', 'success');
        await this.loadDocuments();
      }
    } catch (err) { APP.toast('Archive failed', 'error'); }
  },

  async viewDocument(docId) {
    window.open(`/documents/${docId}`, '_blank');
  },
};

document.addEventListener('DOMContentLoaded', () => ADMIN.init());
