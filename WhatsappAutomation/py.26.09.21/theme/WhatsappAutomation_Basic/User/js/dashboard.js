export async function init({ call, escapeHtml }) {
  const data = await call('get_dashboard_stats');
  const cards = [
    ['Groups', data.groups, 'Local group records', '▦', 'violet'],
    ['Members', data.members, 'Saved contact records', '◎', 'blue'],
    ['Group links', data.linked_members, 'Member-to-group links', '⌁', 'green'],
    ['Automation runs', data.automation_runs, 'Recorded GUI runs', '⌘', 'amber']
  ];
  const template = window.WAWorkspace.statTemplate();
  document.getElementById('dashboard-stats').innerHTML = cards.map(([label, value, foot, icon, tone]) =>
    template.replace('{{label}}', label).replace('{{value}}', escapeHtml(value)).replace('{{foot}}', foot).replace('{{icon}}', icon).replace('{{tone}}', tone)
  ).join('');
  const events = await call('get_recent_activity');
  const root = document.getElementById('activity-list');
  if (!events.length) { root.innerHTML = '<div class="empty-state"><span>◷</span><strong>No activity yet</strong><p>Your workspace activity will appear here.</p></div>'; return; }
  root.innerHTML = events.map(item => `<div class="activity-item"><span class="activity-marker ${item.status === 'error' ? 'danger' : ''}"></span><div class="activity-copy"><strong>${escapeHtml(item.event_type.replaceAll('_', ' '))}</strong><p>${escapeHtml(item.details || item.status)}</p></div><time>${escapeHtml(item.created_at)}</time></div>`).join('');
}
