import { hasRegionalLocation, alertCard, node } from './mobile-common.js';
const user = await window.MobileSession;
if (user) {
  const list = document.querySelector('#mobile-alerts'), status = document.querySelector('#alerts-status'), button = document.querySelector('#mobile-refresh');
  let busy = false;
  async function load() {
    if (busy) return;
    busy = true; PrevClima.setBusy(button, true);
    try {
      if (!await hasRegionalLocation(user)) {
        list.replaceChildren(node('p', 'Salve sua localização em São Paulo no perfil para consultar os avisos que atingem sua área.', 'mobile-list-state'));
        status.textContent = 'Localização necessária para personalizar os avisos.'; return;
      }
      const rows = await PrevClima.request('/alerts');
      const current = rows.filter((row) => Date.parse(row.valid_until) > Date.now());
      list.replaceChildren(...current.map(alertCard));
      if (!current.length) list.append(node('p', 'Nenhum aviso vigente disponível para sua localização.', 'mobile-list-state'));
      status.textContent = `Atualizado às ${new Date().toLocaleTimeString('pt-BR', {hour:'2-digit',minute:'2-digit'})} · ${current.length} aviso(s)`;
    } catch (error) {
      list.replaceChildren(node('p', error.message + ' Tente atualizar novamente.', 'mobile-list-state'));
      status.textContent = 'Consulta não concluída. Não é possível confirmar os avisos.';
    } finally { busy = false; PrevClima.setBusy(button, false); }
  }
  button.addEventListener('click', load);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) load(); });
  const timer = setInterval(() => { if (!document.hidden) load(); }, 60000);
  window.addEventListener('pagehide', () => clearInterval(timer), {once:true});
  await load();
}
