// Notifications exist only while a visible page is open; no background push claim.
document.addEventListener("DOMContentLoaded", () => {
  let busy = false, audio = null, currentUser = null;
  const banner = document.createElement("aside");
  banner.className = "weather-notification";
  banner.hidden = true;
  banner.setAttribute("aria-live", "polite");
  banner.innerHTML = '<strong>Novo alerta na sua região</strong><p></p><a href="/alertas.html">Ver alertas</a><button type="button" aria-label="Fechar notificação">Fechar</button>';
  document.body.append(banner);
  banner.querySelector("button").onclick = () => { banner.hidden = true; };
  function unlock() {
    if (!audio && window.AudioContext) audio = new window.AudioContext();
    if (audio?.state === "suspended") audio.resume().catch(() => {});
  }
  document.addEventListener("pointerdown", unlock, { once: true });
  document.addEventListener("keydown", unlock, { once: true });
  function sound() {
    if (!audio || audio.state !== "running") return;
    const oscillator = audio.createOscillator(), gain = audio.createGain();
    oscillator.connect(gain); gain.connect(audio.destination);
    oscillator.frequency.value = 660;
    gain.gain.setValueAtTime(0.08, audio.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audio.currentTime + 0.35);
    oscillator.start(); oscillator.stop(audio.currentTime + 0.35);
  }
  async function poll() {
    if (busy || document.hidden) return;
    busy = true;
    try {
      currentUser = await PrevClima.request("/users/me");
      if (!currentUser.weather_notifications) { banner.hidden = true; return; }
      const rows = await PrevClima.request("/notifications");
      const key = `prevclima-seen-alerts-${currentUser.id}`;
      let seen;
      try { seen = new Set(JSON.parse(sessionStorage.getItem(key) || "[]")); } catch (_) { seen = new Set(); }
      const fresh = rows.filter((row) => !seen.has(row.id) && Date.parse(row.valid_until) > Date.now());
      if (banner.dataset.id && !rows.some((row) => String(row.id) === banner.dataset.id)) banner.hidden = true;
      if (fresh.length) {
        banner.querySelector("p").textContent = fresh.map((row) => row.title).join(" · ");
        banner.dataset.id = String(fresh[0].id); banner.hidden = false;
        fresh.forEach((row) => seen.add(row.id));
        try { sessionStorage.setItem(key, JSON.stringify([...seen].slice(-500))); } catch (_) { /* Storage can be disabled. */ }
        if (currentUser.alert_sound) sound();
      }
    } catch (error) { if (error.status === 401) banner.hidden = true; }
    finally { busy = false; }
  }
  const interval = setInterval(poll, 30000);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) poll(); });
  window.addEventListener("pagehide", () => clearInterval(interval), { once: true });
  poll();
});
