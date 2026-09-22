document.addEventListener("DOMContentLoaded", async () => {
  const list = document.querySelector("#alert-list");
  const count = document.querySelector("#active-count");
  const location = document.querySelector("#confirmed-location");
  let signedIn = true;
  try {
    const user = await PrevClima.request("/users/me");
    PrevClima.applyTheme(user);
    location.textContent = user.city && user.state
      ? `Localização confirmada: ${user.city}, ${user.state}`
      : "Alertas ativos para todas as áreas";
  } catch (error) {
    signedIn = error.status !== 401;
    location.textContent = "Alertas ativos para todas as áreas";
  }

  function paragraph(text, className) {
    const node = document.createElement("p");
    if (className) node.className = className;
    node.textContent = text;
    return node;
  }

  function render(alert) {
    const card = document.createElement("article");
    card.className = "alert-card";
    card.dataset.severity = alert.severity;

    const summary = document.createElement("button");
    summary.type = "button";
    summary.className = "alert-summary";
    summary.setAttribute("aria-expanded", "false");
    const icon = document.createElement("strong");
    icon.textContent = "!";
    const info = document.createElement("div");
    info.append(paragraph(PrevClima.severityName(alert.severity).toUpperCase(), "alert-level"));
    const title = document.createElement("h2");
    title.className = "alert-title";
    title.textContent = `${alert.is_demo ? "DEMO - " : ""}${alert.title}`;
    info.append(title, paragraph(alert.area_name, "muted"));
    const issued = new Date(alert.issued_at);
    const timeText = `Emitido ${PrevClima.relativeTime(issued)} · válido até ${new Date(alert.valid_until).toLocaleString("pt-BR")}`;
    info.append(paragraph(timeText, "alert-time"));
    const read = paragraph(alert.is_read ? "Lido" : "Abrir", alert.is_read ? "read-label" : "muted");
    summary.append(icon, info, read);

    const detail = document.createElement("div");
    detail.className = "alert-detail";
    detail.append(paragraph(alert.message));
    const source = paragraph(`Origem: ${alert.source_name}`, "data-source");
    detail.append(source);
    if (alert.source_url && alert.source_url.startsWith("https://")) {
      const sourceLink = document.createElement("a");
      sourceLink.href = alert.source_url;
      sourceLink.target = "_blank";
      sourceLink.rel = "noopener noreferrer";
      sourceLink.textContent = "Abrir fonte oficial";
      sourceLink.className = "helper";
      detail.append(sourceLink);
    }
    const recommendations = document.createElement("div");
    recommendations.className = "recommendations";
    const heading = document.createElement("strong");
    heading.textContent = "Recomendações";
    const items = document.createElement("ul");
    alert.recommendations.forEach((text) => {
      const item = document.createElement("li");
      item.textContent = text;
      items.append(item);
    });
    recommendations.append(heading, items);
    detail.append(recommendations);
    card.append(summary, detail);

    summary.addEventListener("click", async () => {
      card.classList.toggle("open");
      summary.setAttribute("aria-expanded", String(card.classList.contains("open")));
      if (signedIn && !alert.is_read) {
        try {
          await PrevClima.request(`/alerts/${alert.id}/read`, { method: "POST" });
          alert.is_read = true;
          read.className = "read-label";
          read.textContent = "Lido";
        } catch (error) {
          read.textContent = error.message;
        }
      }
    });
    return card;
  }

  try {
    const alerts = await PrevClima.request("/alerts?active=true");
    count.textContent = `${alerts.length} ativo${alerts.length === 1 ? "" : "s"}`;
    list.replaceChildren();
    if (!alerts.length) list.append(paragraph("Nenhum alerta ativo no momento.", "empty"));
    else alerts.forEach((alert) => list.append(render(alert)));
  } catch (error) {
    count.textContent = "Indisponível";
    list.replaceChildren(paragraph(error.message, "error"));
  }
});
