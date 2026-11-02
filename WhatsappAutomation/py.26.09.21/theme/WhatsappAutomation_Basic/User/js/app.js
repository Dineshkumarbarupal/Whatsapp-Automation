(() => {
  const pageNames = { dashboard: 'Overview', groups: 'Groups', members: 'Members', automation: 'GUI automation', settings: 'Settings' };
  const componentCache = {};
  const call = async (name, ...args) => {
    if (!window.eel || typeof window.eel[name] !== 'function') throw new Error('Desktop bridge is not ready. Restart the application.');
    const result = await window.eel[name](...args)();
    if (!result || result.ok !== true) throw new Error(result?.message || 'The operation failed.');
    return result.data;
  };
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
  const toast = async (message, kind = 'success') => {
    const root = document.getElementById('toast-root');
    if (!componentCache.toast) componentCache.toast = await fetch('../component/toast.html').then(r => r.text());
    const symbols = { success: '✓', error: '!', info: 'i' };
    const html = componentCache.toast.replace('{{kind}}', kind).replace('{{symbol}}', symbols[kind] || 'i').replace('{{message}}', escapeHtml(message));
    const wrapper = document.createElement('div'); wrapper.innerHTML = html;
    const node = wrapper.firstElementChild; root.appendChild(node);
    node.querySelector('.toast-close').addEventListener('click', () => node.remove());
    setTimeout(() => node.remove(), 4800);
  };
  const loadComponent = async (id, path) => {
    const html = await fetch(path).then(response => { if (!response.ok) throw new Error(`Could not load ${path}`); return response.text(); });
    document.getElementById(id).innerHTML = html;
  };
  const loadPage = async (page) => {
    if (!pageNames[page]) page = 'dashboard';
    const content = document.getElementById('content-root');
    content.innerHTML = '<div class="boot-state"><span class="loader"></span><p>Opening ' + escapeHtml(pageNames[page]) + '…</p></div>';
    try {
      const html = await fetch(`../template/${page}.html`).then(r => { if (!r.ok) throw new Error('Page could not be loaded.'); return r.text(); });
      content.innerHTML = html;
      document.getElementById('current-page-name').textContent = pageNames[page];
      document.querySelectorAll('.nav-link').forEach(link => link.classList.toggle('active', link.dataset.page === page));
      history.replaceState({ page }, '', `#${page}`);
      const module = await import(`./${page}.js`);
      if (typeof module.init === 'function') await module.init({ call, toast, escapeHtml, navigate: loadPage });
      content.focus({ preventScroll: true });
    } catch (error) {
      content.innerHTML = `<section class="panel error-panel"><h2>Unable to open this page</h2><p>${escapeHtml(error.message)}</p><button class="button button-primary" id="retry-page">Try again</button></section>`;
      document.getElementById('retry-page')?.addEventListener('click', () => loadPage(page));
    }
  };

  async function boot() {
    try {
      await Promise.all([loadComponent('sidebar-root', '../component/sidebar.html'), loadComponent('topbar-root', '../component/topbar.html')]);
      componentCache.stat = await fetch('../component/stat_card.html').then(r => r.text());
      document.addEventListener('click', (event) => {
        const nav = event.target.closest('[data-page], [data-nav]');
        if (nav) loadPage(nav.dataset.page || nav.dataset.nav);
      });
      document.getElementById('theme-toggle').addEventListener('click', () => {
        document.body.classList.toggle('light-theme');
        toast(document.body.classList.contains('light-theme') ? 'Light theme enabled.' : 'Dark theme enabled.', 'info');
      });
      document.getElementById('help-button').addEventListener('click', () => toast('Use the GUI automation page for the supervised WhatsApp workflow. See README.md for setup.', 'info'));
      document.getElementById('global-search').addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && event.target.value.trim()) {
          loadPage('members');
          setTimeout(() => { const input = document.getElementById('member-search'); if (input) { input.value = event.target.value; input.dispatchEvent(new Event('input')); } }, 250);
        }
      });
      const requested = location.hash.slice(1);
      await loadPage(pageNames[requested] ? requested : 'dashboard');
    } catch (error) {
      document.getElementById('content-root').innerHTML = `<div class="error-panel"><h2>Workspace startup error</h2><p>${escapeHtml(error.message)}</p></div>`;
    }
  }
  window.WAWorkspace = { call, toast, escapeHtml, loadPage, statTemplate: () => componentCache.stat };
  document.addEventListener('DOMContentLoaded', boot);
})();
