import { hasRegionalLocation } from './mobile-common.js';
let user = await window.MobileSession;
if (user) {
  const form = document.querySelector('#mobile-profile-form'), message = document.querySelector('#profile-message'), gps = document.querySelector('#mobile-gps');
  let coordinates = { latitude: user.latitude, longitude: user.longitude };
  const fields = form.elements;
  function render() {
    document.querySelector('#profile-email').textContent = user.email;
    fields.namedItem('name').value = user.name;
    fields.namedItem('city').value = user.city || '';
    for (const field of ['weather_notifications','alert_sound','dark_theme']) fields.namedItem(field).checked = Boolean(user[field]);
    document.querySelector('#location-status').textContent = coordinates.latitude == null ? 'Nenhuma coordenada salva. O GPS é opcional, mas necessário para avisos geográficos.' : 'Localização salva para os avisos. Você pode atualizá-la ou removê-la.';
    PrevClima.applyTheme(user);
  }
  render();
  gps.disabled = !navigator.geolocation;
  gps.addEventListener('click', async () => {
    PrevClima.setBusy(gps, true); message.textContent = 'Obtendo sua localização…';
    try {
      const {coords} = await new Promise((resolve,reject) => navigator.geolocation.getCurrentPosition(resolve,reject,{enableHighAccuracy:false,timeout:15000,maximumAge:300000}));
      const next = {latitude:coords.latitude,longitude:coords.longitude};
      if (!await hasRegionalLocation(next)) { message.textContent = 'A localização está fora de São Paulo. Os avisos deste aplicativo cobrem somente o estado.'; return; }
      // Save location immediately; preserve unsaved name and preferences in the form.
      user = await PrevClima.request('/users/me',{method:'PATCH',body:JSON.stringify(next)});
      coordinates = next;
      document.querySelector('#location-status').textContent = 'Localização GPS salva com sucesso.';
      message.textContent = 'Sua localização está pronta para receber avisos.';
    } catch (error) { message.textContent = error.message || 'Não foi possível acessar o GPS. Confira a permissão de localização e tente novamente.'; }
    finally { PrevClima.setBusy(gps,false); }
  });
  document.querySelector('#mobile-clear-gps').addEventListener('click', async (event) => {
    PrevClima.setBusy(event.currentTarget,true);
    try {
      user = await PrevClima.request('/users/me',{method:'PATCH',body:JSON.stringify({latitude:null,longitude:null})});
      coordinates = {latitude:null,longitude:null};
      document.querySelector('#location-status').textContent = 'Coordenadas removidas. Os avisos geográficos ficam pausados até salvar outra localização.';
      message.textContent = 'Localização removida.';
    } catch (error) { message.textContent = error.message; }
    finally { PrevClima.setBusy(document.querySelector('#mobile-clear-gps'),false); }
  });
  form.addEventListener('submit', async (event) => {
    event.preventDefault(); const button = form.querySelector('[type="submit"]'); PrevClima.setBusy(button,true);
    const city = fields.namedItem('city').value.trim();
    const changedCity = city !== (user.city || '');
    const payload = { name:fields.namedItem('name').value.trim(), city:city || null, state:city ? 'SP' : null,
      ...(changedCity ? {latitude:null,longitude:null} : coordinates) };
    for (const field of ['weather_notifications','alert_sound','dark_theme']) payload[field] = fields.namedItem(field).checked;
    try {
      user = await PrevClima.request('/users/me',{method:'PATCH',body:JSON.stringify(payload)});
      coordinates = {latitude:user.latitude,longitude:user.longitude}; render();
      message.textContent = changedCity ? 'Perfil salvo. A cidade mudou: atualize o GPS para personalizar os avisos.' : 'Perfil e preferências salvos.';
    } catch(error) { message.textContent = error.message; }
    finally { PrevClima.setBusy(button,false); }
  });
  document.querySelector('#mobile-logout').addEventListener('click', async (event) => {
    PrevClima.setBusy(event.currentTarget,true);
    try { await PrevClima.request('/auth/logout',{method:'POST'}); location.assign('/mobile/'); }
    catch(error) { message.textContent = error.message; PrevClima.setBusy(document.querySelector('#mobile-logout'),false); }
  });
}
