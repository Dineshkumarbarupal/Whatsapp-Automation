export async function init({ call, toast, escapeHtml }) {
  const body = document.getElementById('groups-table-body');
  const render = async (search = '') => {
    const groups = await call('list_groups', search);
    document.getElementById('group-count-label').textContent = `${groups.length} group record${groups.length === 1 ? '' : 's'}`;
    document.getElementById('nav-group-count').textContent = groups.length;
    body.innerHTML = groups.length ? groups.map(group => `<tr><td><div class="table-primary-cell"><span class="group-avatar">${escapeHtml(group.name.slice(0, 1).toUpperCase())}</span><strong>${escapeHtml(group.name)}</strong></div></td><td>${escapeHtml(group.description || '—')}</td><td><span class="count-pill">${group.member_count}</span></td><td><span class="status-pill status-local">${escapeHtml(group.whatsapp_status)}</span></td><td>${escapeHtml(group.created_at)}</td></tr>`).join('') : '<tr><td colspan="5" class="table-empty">No groups yet. Create your first local group record.</td></tr>';
  };
  document.getElementById('new-group-button').addEventListener('click', async () => {
    const name = prompt('Enter a name for this local group record:');
    if (!name?.trim()) return;
    const description = prompt('Optional description:') || '';
    try { await call('create_group_record', name.trim(), description); await render(document.getElementById('group-search').value); await toast('Local group record created.'); }
    catch (error) { toast(error.message, 'error'); }
  });
  document.getElementById('group-search').addEventListener('input', (event) => render(event.target.value).catch(error => toast(error.message, 'error')));
  await render();
}
