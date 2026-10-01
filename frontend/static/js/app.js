/**
 * PolicyPilot — Shared App JavaScript
 * Auth guards, theme management, toast notifications, shared utilities
 */

const APP = {
  API: '',
  token: null,
  user: null,

  init() {
    this.token = localStorage.getItem('pp_token');
    const userStr = localStorage.getItem('pp_user');
    this.user = userStr ? JSON.parse(userStr) : null;

    // Apply saved theme
    const savedTheme = localStorage.getItem('pp_theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);

    // Theme toggle
    const toggleBtn = document.getElementById('theme-toggle');
    if (toggleBtn) {
      toggleBtn.addEventListener('click', this.toggleTheme.bind(this));
    }

    // Logout
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
      logoutBtn.addEventListener('click', this.logout.bind(this));
    }

    // Populate user info in sidebar
    if (this.user) {
      this.populateUserInfo();
    }
  },

  requireAuth() {
    if (!this.token || !this.user) {
      window.location.href = '/login';
      return false;
    }
    return true;
  },

  requireAdmin() {
    if (!this.requireAuth()) return false;
    if (!['admin', 'hr'].includes(this.user.role)) {
      window.location.href = '/chat';
      return false;
    }
    return true;
  },

  populateUserInfo() {
    const u = this.user;
    const nameEl = document.getElementById('user-name');
    const avatarEl = document.getElementById('user-avatar');
    const roleEl = document.getElementById('user-role');
    const adminLink = document.getElementById('admin-link');

    if (nameEl) nameEl.textContent = u.name;
    if (avatarEl) avatarEl.textContent = u.name[0].toUpperCase();
    if (roleEl) {
      roleEl.textContent = u.role;
      roleEl.className = `user-role-badge ${u.role}`;
    }
    if (adminLink && ['admin', 'hr'].includes(u.role)) {
      adminLink.style.display = 'flex';
    }
  },

  async apiFetch(path, options = {}) {
    const headers = {
      'Content-Type': 'application/json',
      ...(this.token ? { 'Authorization': `Bearer ${this.token}` } : {}),
      ...(options.headers || {}),
    };

    const res = await fetch(this.API + path, { ...options, headers });

    if (res.status === 401) {
      this.logout();
      throw new Error('Session expired. Please log in again.');
    }

    return res;
  },

  toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('pp_theme', next);
  },

  logout() {
    localStorage.removeItem('pp_token');
    localStorage.removeItem('pp_user');
    window.location.href = '/login';
  },

  toast(message, type = 'info', duration = 4000) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
      <span class="toast-dot"></span>
      <span>${message}</span>
    `;

    container.appendChild(toast);
    setTimeout(() => {
      toast.style.animation = 'slideIn 0.2s ease reverse';
      setTimeout(() => toast.remove(), 200);
    }, duration);
  },

  formatTime(iso) {
    const d = new Date(iso);
    return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  },

  formatDate(iso) {
    const d = new Date(iso);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  },

  escapeHtml(text) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
  },

  // Simple markdown renderer for assistant messages
  renderMarkdown(text) {
    if (!text) return '';
    let html = this.escapeHtml(text);
    // Bold: **text**
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    // Headers: # text (only inline for chat)
    html = html.replace(/^### (.*$)/gm, '<strong class="md-h3">$1</strong>');
    html = html.replace(/^## (.*$)/gm, '<strong class="md-h2">$1</strong>');
    // Bullet points
    html = html.replace(/^[•\-] (.*$)/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>');
    // Numbered lists
    html = html.replace(/^\d+\. (.*$)/gm, '<li>$1</li>');
    // Line breaks
    html = html.replace(/\n\n/g, '</p><p>');
    html = html.replace(/\n/g, '<br>');
    // Citations separator
    html = html.replace(/---\n/g, '<hr class="citation-sep">');
    return `<p>${html}</p>`;
  },
};

// Initialize on all pages
document.addEventListener('DOMContentLoaded', () => APP.init());
