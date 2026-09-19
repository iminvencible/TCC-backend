document.addEventListener("DOMContentLoaded", async () => {
  const list = document.querySelector("#alert-list");
  const count = document.querySelector("#active-count");
  const location = document.querySelector("#confirmed-location");
  let signedIn = true;
  try {
    const user = await PrevClima.request("/users/me");
    PrevClima.applyTheme(user);
    location.textContent = user.city && user.state
      ? `Localizacao confirmada: ${user.city}, ${user.state}`
      : "Alertas ativos para todas as areas";
  } catch (error) {
    signedIn = error.status !== 401;
    location.textContent = "Alertas ativos para todas as areas";
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

    const summary = document.createElement("div");
    summary.className = "alert-summary";
    const icon = document.createElement("strong");
    icon.textContent = "!";
    const info = document.createElement("div");
    info.append(paragraph(alert.severity, "alert-level"));
    const title = document.createElement("h2");
    title.className = "alert-title";
    title.textContent = `${alert.is_demo ? "DEMO - " : ""}${alert.title}`;
    info.append(title, paragraph(alert.area_name, "muted"));
    const issued = new Date(alert.issued_at);
    const elapsedMinutes = Math.max(0, Math.floor((Date.now() - issued.getTime()) / 60000));
    const timeText = elapsedMinutes < 60
      ? `Emitido ha ${elapsedMinutes} min`
      : `Emitido em ${issued.toLocaleString("pt-BR")}`;
    info.append(paragraph(timeText, "alert-time"));
    const read = paragraph(alert.is_read ? "Lido" : "Abrir", alert.is_read ? "read-label" : "muted");
    summary.append(icon, info, read);

    const detail = document.createElement("div");
    detail.className = "alert-detail";
    detail.append(paragraph(alert.message));
    const recommendations = document.createElement("div");
    recommendations.className = "recommendations";
    const heading = document.createElement("strong");
    heading.textContent = "Recomendacoes";
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
    count.textContent = "Indisponivel";
    list.replaceChildren(paragraph(error.message, "error"));
  }
});
