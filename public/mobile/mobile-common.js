import { containsPoint, loadStateBoundary } from '/assets/js/sao-paulo-map.js';
export function node(tag, text, className) {
  const element = document.createElement(tag); element.textContent = text;
  if (className) element.className = className;
  return element;
}
export async function hasRegionalLocation(user) {
  if (user.latitude == null || user.longitude == null) return false;
  const boundary = await loadStateBoundary();
  return containsPoint(boundary.features[0].geometry, Number(user.latitude), Number(user.longitude));
}
export function alertCard(alert) {
  const card = node('article', ''); card.dataset.severity = alert.severity;
  card.append(node('small', PrevClima.severityName(alert.severity)), node('h2', alert.title), node('p', alert.message || alert.area_name), node('span', alert.area_name));
  if (alert.recommendations) card.append(node('p', `Orientações: ${alert.recommendations}`));
  card.append(node('span', `Válido até ${new Date(alert.valid_until).toLocaleString('pt-BR')}`), node('span', `Fonte: ${alert.source_name || 'PrevClima'}`));
  try {
    const url = new URL(alert.source_url);
    if (url.protocol === 'https:' && !url.username && !url.password) {
      const link = node('a', 'Consultar fonte ↗'); link.href = url.href; link.target = '_blank'; link.rel = 'noopener noreferrer'; card.append(link);
    }
  } catch (_) { /* A source link is optional. */ }
  return card;
}
