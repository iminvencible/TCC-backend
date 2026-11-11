// Establish the mobile audience before any authenticated mobile view loads data.
window.MobileSession = (async () => {
  try {
    const { user } = await PrevClima.request('/auth/mobile-session');
    if (user.role !== 'USER') throw Object.assign(new Error('Acesso exclusivo para usuários.'), { status: 403 });
    PrevClima.applyTheme(user);
    return user;
  } catch (error) {
    if ([401, 403].includes(error.status)) location.replace('/mobile/');
    else {
      const status = document.querySelector('#mobile-session-status');
      if (status) { status.className = 'mobile-list-state'; status.textContent = 'Não foi possível verificar sua sessão. Confira a conexão e atualize a página.'; }
    }
    return null;
  }
})();
document.addEventListener('DOMContentLoaded', () => {
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('/mobile/sw.js').catch(() => {});
  document.querySelectorAll('.mobile-bottom-nav a').forEach((link) => {
    const active = new URL(link.href).pathname === location.pathname;
    link.classList.toggle('active', active);
    if (active) link.setAttribute('aria-current', 'page');
  });
});
