export async function init({ call, toast, escapeHtml }) {
  const body = document.getElementById('members-table-body');
  const observationBody = document.getElementById('observations-table-body');
  let activeSessionId = null;

  const renderContacts = async (search = '') => {
    const members = await call('list_members', search);
    document.getElementById('member-count-label').textContent = `${members.length} saved contact record${members.length === 1 ? '' : 's'}`;
    body.innerHTML = members.length ? members.map(member => `<tr><td><div class="table-primary-cell"><span class="member-avatar">${escapeHtml((member.display_name || member.phone).slice(0,1).toUpperCase())}</span><strong>${escapeHtml(member.display_name || 'Unnamed contact')}</strong></div></td><td class="mono-cell">${escapeHtml(member.phone)}</td><td><span class="consent-pill consent-${escapeHtml(member.consent_status)}">${escapeHtml(member.consent_status)}</span></td><td>${member.group_count}</td><td>${escapeHtml(member.source)}</td></tr>`).join('') : '<tr><td colspan="5" class="table-empty">No contact records. Import a consent-tracked CSV when needed.</td></tr>';
  };

  const renderObservations = async () => {
    const rows = await call('list_member_observations', '');
    document.getElementById('observation-count-label').textContent = `${rows.length} reviewed visible-list observation${rows.length === 1 ? '' : 's'}`;
    observationBody.innerHTML = rows.length ? rows.map(row => `<tr><td>${escapeHtml(row.group_name)}</td><td>${escapeHtml(row.display_name || 'Name not legible')}</td><td class="mono-cell">${escapeHtml(row.phone || 'Not shown')}</td><td>${Number(row.confidence).toFixed(1)}%</td><td>${row.pages_seen}</td><td>${escapeHtml(row.last_seen_at)}</td></tr>`).join('') : '<tr><td colspan="6" class="table-empty">No reviewed observations saved yet.</td></tr>';
  };

  const authorized = () => document.getElementById('ocr-capture-authorization').checked;
  const acknowledge = async () => {
    if (!authorized()) throw new Error('Confirm the group/data authorization statement first.');
    await call('acknowledge_authorization', true);
  };

  const renderReview = (data) => {
    const root = document.getElementById('ocr-review');
    root.classList.remove('hidden');
    const candidates = data.candidates || [];
    root.innerHTML = `<div class="ocr-review-head"><div><strong>Session review queue</strong><small>${data.pages_captured} page(s) captured · ${candidates.length} unique candidate(s). Review every row before saving.</small></div></div>
      <div class="ocr-candidate-list">${candidates.length ? candidates.map((item, index) => `<label class="ocr-candidate"><input type="checkbox" data-capture-key="${escapeHtml(item.capture_key)}" checked><span><strong>${escapeHtml(item.display_name || 'Name not legible')}</strong><small>${escapeHtml(item.phone || 'Phone number not visible')} · OCR ${Number(item.confidence || 0).toFixed(1)}% · seen on ${item.pages_seen} page(s)</small></span></label>`).join('') : '<p class="empty-inline">No participant candidates detected on the captured pages. Make sure the participant list is visible and try another screen.</p>'}</div>
      <details class="ocr-raw"><summary>View latest page OCR text</summary><pre>${escapeHtml(data.page_text || '')}</pre></details>
      <div class="heading-actions"><button class="button button-primary" id="save-member-observations" ${candidates.length ? '' : 'disabled'}>Save selected observations</button></div>`;
    document.getElementById('save-member-observations')?.addEventListener('click', async () => {
      const keys = [...root.querySelectorAll('[data-capture-key]:checked')].map(box => box.dataset.captureKey);
      if (!keys.length) { toast('Select at least one OCR observation.', 'info'); return; }
      if (!confirm(`Save ${keys.length} reviewed observation(s) for “${data.group_name}” to the local database? This does not grant consent for outreach.`)) return;
      try {
        await acknowledge();
        const result = await call('save_member_capture', activeSessionId, keys, true);
        activeSessionId = null;
        document.getElementById('capture-status').textContent = 'Session saved and closed. Start another session to capture a different group.';
        document.getElementById('capture-member-page').disabled = true;
        document.getElementById('discard-member-capture').disabled = true;
        root.classList.add('hidden');
        await renderObservations();
        toast(`${result.saved} selected observation(s) saved/merged in ${result.group_name}.`);
      } catch (error) { toast(error.message, 'error'); }
    });
  };

  document.getElementById('member-search').addEventListener('input', event => renderContacts(event.target.value).catch(error => toast(error.message, 'error')));
  document.getElementById('import-members').addEventListener('click', () => document.getElementById('csv-file').click());
  document.getElementById('csv-file').addEventListener('change', async event => {
    const file = event.target.files?.[0]; if (!file) return;
    try { const result = await call('import_contacts_csv', await file.text()); await renderContacts(); toast(`Imported ${result.imported} contacts. ${result.warnings.length} warning(s).`, result.warnings.length ? 'info' : 'success'); }
    catch (error) { toast(error.message, 'error'); }
    finally { event.target.value = ''; }
  });
  document.getElementById('export-members').addEventListener('click', async () => {
    try {
      const csv = await call('export_members_csv');
      const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
      const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'whatsapp-workspace-contacts.csv'; anchor.click(); URL.revokeObjectURL(url);
      toast('Contact CSV exported.');
    } catch (error) { toast(error.message, 'error'); }
  });

  document.getElementById('start-member-capture').addEventListener('click', async () => {
    const groupName = document.getElementById('ocr-group-name').value.trim();
    if (!groupName) { toast('Enter the WhatsApp group name first.', 'error'); return; }
    if (!confirm(`Start a visible-screen OCR review session for “${groupName}”? Only capture a group you are authorized to review.`)) return;
    try {
      await acknowledge();
      const session = await call('start_member_capture', groupName, true);
      activeSessionId = session.session_id;
      document.getElementById('capture-status').textContent = `Active group: ${session.group_name}. Open its participant list, then capture the visible page.`;
      document.getElementById('capture-member-page').disabled = false;
      document.getElementById('discard-member-capture').disabled = false;
      document.getElementById('ocr-review').classList.add('hidden');
      toast('Visible-list OCR session started.');
    } catch (error) { toast(error.message, 'error'); }
  });

  document.getElementById('capture-member-page').addEventListener('click', async event => {
    if (!activeSessionId) { toast('Start a capture session first.', 'error'); return; }
    const button = event.currentTarget; button.disabled = true; button.textContent = 'Capturing visible page…';
    try {
      await acknowledge();
      const result = await call('capture_member_page', activeSessionId, true);
      document.getElementById('capture-status').textContent = `Captured ${result.pages_captured} page(s). ${result.new_candidates_on_page} new candidate(s) on this page; ${result.candidate_count} unique candidate(s) in the session. Manually scroll down in WhatsApp before capturing the next page.`;
      renderReview(result);
      toast(`Page ${result.pages_captured} captured; ${result.candidate_count} unique candidate(s) in review.`,'info');
    } catch (error) { toast(error.message, 'error'); }
    finally { button.disabled = !activeSessionId; button.textContent = 'Capture visible page'; }
  });

  document.getElementById('discard-member-capture').addEventListener('click', async () => {
    if (!activeSessionId) return;
    if (!confirm('Discard this in-memory OCR session? Nothing pending will be saved.')) return;
    try {
      await call('discard_member_capture', activeSessionId);
      activeSessionId = null;
      document.getElementById('capture-member-page').disabled = true;
      document.getElementById('discard-member-capture').disabled = true;
      document.getElementById('capture-status').textContent = 'Session discarded. No pending OCR data was saved.';
      document.getElementById('ocr-review').classList.add('hidden');
      toast('OCR session discarded.', 'info');
    } catch (error) { toast(error.message, 'error'); }
  });

  document.getElementById('export-observations').addEventListener('click', async () => {
    try {
      const csv = await call('export_member_observations_csv', '');
      const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
      const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'whatsapp-group-observations.csv'; anchor.click(); URL.revokeObjectURL(url);
      toast('Reviewed observation CSV exported.');
    } catch (error) { toast(error.message, 'error'); }
  });

  await Promise.all([renderContacts(), renderObservations()]);
}
