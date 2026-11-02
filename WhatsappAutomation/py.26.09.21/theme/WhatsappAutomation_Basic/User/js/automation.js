export async function init({ call, toast }) {
  const openButton = document.getElementById('open-whatsapp');
  const authorization = () => document.getElementById('operator-authorization').checked;
  const parseNumbers = (raw) => raw.split(/[\\s,;]+/).map(value => value.trim()).filter(Boolean);
  const enableAuthorization = async () => {
    if (!authorization()) throw new Error('Confirm the authorization statement before running this action.');
    await call('acknowledge_authorization', true);
  };
  openButton.addEventListener('click', async () => {
    openButton.disabled = true;
    try { const result = await call('open_whatsapp_web'); toast(result.message, 'info'); }
    catch (error) { toast(error.message, 'error'); }
    finally { openButton.disabled = false; }
  });
  document.getElementById('create-group-form').addEventListener('submit', async event => {
    event.preventDefault();
    const name = document.getElementById('wa-group-name').value.trim();
    const numbers = parseNumbers(document.getElementById('wa-group-participants').value);
    if (!confirm(`Start the visible WhatsApp group-creation sequence for “${name}” with ${numbers.length} participant(s)? Keep your hands off the keyboard and mouse until it completes.`)) return;
    try {
      await enableAuthorization();
      const result = await call('create_whatsapp_group', name, numbers, true);
      toast(result.message, 'success');
    } catch (error) { toast(error.message, 'error'); }
  });
  document.getElementById('add-members-form').addEventListener('submit', async event => {
    event.preventDefault();
    const numbers = parseNumbers(document.getElementById('add-participants').value);
    if (!confirm(`Add ${numbers.length} participant(s) to the currently open WhatsApp group? Verify the group first.`)) return;
    try {
      await enableAuthorization();
      const result = await call('add_members_to_current_group', numbers, true);
      toast(result.message, 'success');
    } catch (error) { toast(error.message, 'error'); }
  });
}
