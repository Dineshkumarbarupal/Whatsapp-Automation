(() => {
  const pageNames = { dashboard: 'Overview', groups: 'Groups', members: 'Members', automation: 'GUI automation', settings: 'Settings' };
  const componentCache = {};
  let activeUser = null;
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
    const html = await fetch(path).then(response => { if (!response.ok) throw new Error('Could not load ' + path); return response.text(); });
    document.getElementById(id).innerHTML = html;
  };
  const loadPage = async (page) => {
    if (!pageNames[page]) page = 'dashboard';
    const content = document.getElementById('content-root');
    content.innerHTML = '<div class="boot-state"><span class="loader"></span><p>Opening ' + escapeHtml(pageNames[page]) + '…</p></div>';
    try {
      const html = await fetch('../template/' + page + '.html').then(r => { if (!r.ok) throw new Error('Page could not be loaded.'); return r.text(); });
      content.innerHTML = html;
      document.getElementById('current-page-name').textContent = pageNames[page];
      document.querySelectorAll('.nav-link').forEach(link => link.classList.toggle('active', link.dataset.page === page));
      history.replaceState({ page }, '', '#' + page);
      const module = await import('./' + page + '.js');
      if (typeof module.init === 'function') await module.init({ call, toast, escapeHtml, navigate: loadPage });
      content.focus({ preventScroll: true });
    } catch (error) {
      content.innerHTML = '<section class="panel error-panel"><h2>Unable to open this page</h2><p>' + escapeHtml(error.message) + '</p><button class="button button-primary" id="retry-page">Try again</button></section>';
      document.getElementById('retry-page')?.addEventListener('click', () => loadPage(page));
    }
  };

  const updateProfile = (user) => {
    activeUser = user;
    const initials = String(user.full_name || 'User').trim().split(/\s+/).slice(0, 2).map(part => part.charAt(0)).join('').toUpperCase();
    const avatar = document.getElementById('profile-avatar');
    const name = document.getElementById('profile-name');
    const email = document.getElementById('profile-email');
    const topName = document.getElementById('current-user-name');
    if (avatar) avatar.textContent = initials;
    if (name) name.textContent = user.full_name;
    if (email) email.textContent = user.email;
    if (topName) topName.textContent = user.full_name;
  };

  const startWorkspace = async (user, message) => {
    document.body.classList.remove('auth-mode');
    document.getElementById('auth-root').innerHTML = '';
    updateProfile(user);
    const requested = location.hash.slice(1);
    await loadPage(pageNames[requested] ? requested : 'dashboard');
    if (message) await toast(message, 'success');
  };

  const renderAuthScreen = async (authState) => {
    document.body.classList.add('auth-mode');
    const root = document.getElementById('auth-root');
    const html = await fetch('../template/auth.html').then(r => {
      if (!r.ok) throw new Error('Sign-in screen could not be loaded.');
      return r.text();
    });
    root.innerHTML = html;
    let signupMode = !authState.has_accounts;
    const nameField = document.getElementById('auth-name-field');
    const confirmField = document.getElementById('auth-confirm-field');
    const nameInput = document.getElementById('auth-name');
    const confirmInput = document.getElementById('auth-confirm');
    const passwordInput = document.getElementById('auth-password');
    const emailInput = document.getElementById('auth-email');
    const alertBox = document.getElementById('auth-alert');
    const submit = document.getElementById('auth-submit');
    const toggle = document.getElementById('auth-mode-toggle');

    const setMode = (signup) => {
      signupMode = signup;
      document.getElementById('auth-eyebrow').textContent = signup ? 'GET STARTED' : 'WELCOME BACK';
      document.getElementById('auth-title').textContent = signup ? 'Create your account' : 'Sign in to workspace';
      document.getElementById('auth-subtitle').textContent = signup
        ? 'Set up a local account to unlock this workspace.'
        : 'Enter your local account details to continue.';
      nameField.classList.toggle('hidden', !signup);
      confirmField.classList.toggle('hidden', !signup);
      nameInput.required = signup;
      confirmInput.required = signup;
      passwordInput.autocomplete = signup ? 'new-password' : 'current-password';
      submit.innerHTML = signup ? 'Create local account <span>→</span>' : 'Sign in <span>→</span>';
      document.getElementById('auth-switch-copy').firstChild.textContent = signup
        ? 'Already have an account? ' : 'New to this workspace? ';
      toggle.textContent = signup ? 'Sign in' : 'Create account';
      alertBox.hidden = true;
      alertBox.textContent = '';
    };
    setMode(signupMode);
    document.getElementById('auth-switch-copy').classList.toggle('hidden', authState.has_accounts);
    toggle.addEventListener('click', () => setMode(!signupMode));
    document.getElementById('auth-form').addEventListener('submit', async (event) => {
      event.preventDefault();
      alertBox.hidden = true;
      submit.disabled = true;
      submit.textContent = signupMode ? 'Creating account…' : 'Signing in…';
      try {
        const result = signupMode
          ? await call('register_account', nameInput.value, emailInput.value, passwordInput.value, confirmInput.value)
          : await call('login_account', emailInput.value, passwordInput.value);
        await startWorkspace(result.user, signupMode ? 'Local account created.' : 'Signed in successfully.');
      } catch (error) {
        alertBox.textContent = error.message || 'Could not sign in. Please try again.';
        alertBox.hidden = false;
        submit.disabled = false;
        submit.innerHTML = signupMode ? 'Create local account <span>→</span>' : 'Sign in <span>→</span>';
      }
    });
    emailInput.focus();
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
      document.getElementById('logout-button').addEventListener('click', async () => {
        const button = document.getElementById('logout-button');
        button.disabled = true;
        try {
          await call('logout_account');
          activeUser = null;
          await renderAuthScreen({ has_accounts: true });
          await toast('You have been signed out.', 'info');
        } catch (error) {
          await toast(error.message, 'error');
          button.disabled = false;
        }
      });
      document.getElementById('global-search').addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && event.target.value.trim()) {
          loadPage('members');
          setTimeout(() => { const input = document.getElementById('member-search'); if (input) { input.value = event.target.value; input.dispatchEvent(new Event('input')); } }, 250);
        }
      });
      const authState = await call('get_auth_state');
      if (authState.authenticated) await startWorkspace(authState.user);
      else await renderAuthScreen(authState);
    } catch (error) {
      document.getElementById('content-root').innerHTML = '<div class="error-panel"><h2>Workspace startup error</h2><p>' + escapeHtml(error.message) + '</p></div>';
    }
  }
  window.WAWorkspace = { call, toast, escapeHtml, loadPage };
  document.addEventListener('DOMContentLoaded', boot);
})();
