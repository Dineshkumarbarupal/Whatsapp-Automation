export async function init({ call, toast }) {
  const settings = await call('get_settings');
  document.getElementById('setting-theme').value = settings.theme;
  document.getElementById('setting-tesseract').value = settings.tesseract_cmd || '';
  document.getElementById('setting-language').value = settings.ocr_language || 'eng';
  document.getElementById('setting-delay').value = settings.automation_delay_seconds ?? 1;
  document.getElementById('save-settings').addEventListener('click', async () => {
    const delay = Number(document.getElementById('setting-delay').value);
    if (!Number.isFinite(delay) || delay < 0.4 || delay > 5) { toast('Action delay must be between 0.4 and 5 seconds.', 'error'); return; }
    try {
      await call('update_settings', {
        theme: document.getElementById('setting-theme').value,
        tesseract_cmd: document.getElementById('setting-tesseract').value.trim(),
        ocr_language: document.getElementById('setting-language').value.trim() || 'eng',
        automation_delay_seconds: delay
      });
      toast('Settings saved.');
    } catch (error) { toast(error.message, 'error'); }
  });
}
