document.addEventListener("DOMContentLoaded", async () => {
  const form = document.querySelector("#alert-form");
  const queue = document.querySelector("#review-queue");
  const message = document.querySelector("#alert-form-message");
  const reportCount = document.querySelector("#pending-report-total");
  const alertReviewList = document.querySelector("#alert-review-list");
  const alertReviewMessage = document.querySelector("#alert-review-message");

  function paragraph(text, className = "") {
    const element = document.createElement("p");
    element.className = className;
    element.textContent = text;
    return element;
  }

  async function requireProfessional() {
    try {
      const user = await PrevClima.request("/users/me");
      if (user.role !== "METEOROLOGIST") {
        window.location.replace("/inicio.html");
        return null;
      }
      PrevClima.applyTheme(user);
      document.querySelector("#professional-role").textContent = PrevClima.roleName(user.role);
      return user;
    } catch (_error) {
      window.location.replace("/meteorologista.html?next=/profissional.html");
      return null;
    }
  }

  function reportCard(report) {
    const card = document.createElement("article");
    card.className = "review-card";
    const title = document.createElement("h3");
    title.textContent = `Relato #${report.id}`;
    const meta = paragraph(new Date(report.occurred_at).toLocaleString("pt-BR"), "muted");
    const description = paragraph(report.description);
    const coordinates = paragraph(`${Number(report.latitude).toFixed(4)}, ${Number(report.longitude).toFixed(4)}`, "helper");
    const notes = document.createElement("textarea");
    notes.placeholder = "Observação da revisão (opcional)";
    notes.setAttribute("aria-label", "Observação da revisão");
    const actions = document.createElement("div");
    actions.className = "inline-actions";
    [ ["APPROVED", "Aprovar", "approve"], ["REJECTED", "Rejeitar", "reject"] ].forEach(([status, label, css]) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `button ${css}`;
      button.textContent = label;
      button.addEventListener("click", async () => {
        PrevClima.setBusy(button, true);
        try {
          await PrevClima.request(`/reports/${report.id}/review`, {
            method: "PATCH",
            body: JSON.stringify({ status, review_notes: notes.value.trim() || null }),
          });
          await loadReports();
        } catch (error) {
          actions.append(paragraph(error.message, "error"));
          PrevClima.setBusy(button, false);
        }
      });
      actions.append(button);
    });
    card.append(title, meta, description, coordinates);
    if (report.image_url) {
      const imageLink = document.createElement("a");
      imageLink.href = report.image_url;
      imageLink.target = "_blank";
      imageLink.rel = "noopener noreferrer";
      imageLink.textContent = "Abrir imagem enviada";
      imageLink.className = "helper";
      card.append(imageLink);
    }
    card.append(notes, actions);
    return card;
  }

  async function loadReports() {
    try {
      const reports = await PrevClima.request("/reports/review-queue");
      reportCount.textContent = reports.length;
      queue.replaceChildren();
      if (!reports.length) queue.append(paragraph("Nenhum relato aguarda análise.", "empty"));
      else reports.forEach((report) => queue.append(reportCard(report)));
    } catch (error) {
      queue.replaceChildren(paragraph(error.message, "error"));
    }
  }

  async function loadAlerts() {
    try {
      const alerts = await PrevClima.request("/alerts/review-queue");
      document.querySelector("#active-alert-total").textContent = alerts.filter((alert) => alert.validation_status === "ACTIVE").length;
      alertReviewList.replaceChildren();
      if (!alerts.length) {
        alertReviewList.append(paragraph("Nenhum aviso ativo para revisar.", "empty"));
        return;
      }
      alerts.forEach((alert) => alertReviewList.append(alertReviewCard(alert)));
    } catch (_error) {
      document.querySelector("#active-alert-total").textContent = "--";
      alertReviewList.replaceChildren(paragraph("Não foi possível carregar os avisos.", "error"));
    }
  }

  function alertReviewCard(alert) {
    const card = document.createElement("article");
    card.className = "review-card";
    const title = document.createElement("h3");
    title.textContent = alert.title;
    const statusLabel = {
      ACTIVE: "Ativo",
      FALSE_ALARM: "Alarme falso",
      NEEDS_CORRECTION: "Pendente de correção",
    }[alert.validation_status] || alert.validation_status;
    const meta = paragraph(`${PrevClima.severityName(alert.severity)} · ${alert.area_name} · ${alert.source_name} · ${statusLabel}`, "muted");
    const reason = document.createElement("textarea");
    reason.placeholder = "Justificativa obrigatória (mínimo de 10 caracteres)";
    reason.setAttribute("aria-label", `Justificativa para revisar ${alert.title}`);
    const actions = document.createElement("div");
    actions.className = "inline-actions";
    const choices = alert.validation_status === "ACTIVE"
      ? [["FALSE_ALARM", "Marcar alarme falso"], ["NEEDS_CORRECTION", "Marcar para correção"]]
      : [["ACTIVE", "Reativar aviso"]];
    choices.forEach(([status, label]) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = status === "FALSE_ALARM" ? "button reject" : "button secondary";
      button.textContent = label;
      button.addEventListener("click", async () => {
        alertReviewMessage.textContent = "";
        if (reason.value.trim().length < 10) {
          alertReviewMessage.textContent = "Informe uma justificativa com pelo menos 10 caracteres.";
          alertReviewMessage.className = "error";
          return;
        }
        PrevClima.setBusy(button, true);
        try {
          await PrevClima.request(`/alerts/${alert.id}/review`, {
            method: "POST",
            body: JSON.stringify({ validation_status: status, reason: reason.value.trim() }),
          });
          alertReviewMessage.textContent = "Revisão registrada com sucesso.";
          alertReviewMessage.className = "success";
          await loadAlerts();
        } catch (error) {
          alertReviewMessage.textContent = error.message;
          alertReviewMessage.className = "error";
          PrevClima.setBusy(button, false);
        }
      });
      actions.append(button);
    });
    card.append(title, meta, paragraph(alert.message), reason, actions);
    return card;
  }

  if (!await requireProfessional()) return;
  const initialExpiry = new Date(Date.now() + 3 * 60 * 60 * 1000);
  form.elements["valid-until"].value = new Date(initialExpiry.getTime() - initialExpiry.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  await Promise.all([loadReports(), loadAlerts()]);

  document.querySelector("#refresh-reports").addEventListener("click", loadReports);
  document.querySelector("#refresh-alert-review").addEventListener("click", loadAlerts);
  document.querySelector("#sync-inmet").addEventListener("click", async (event) => {
    const button = event.currentTarget;
    alertReviewMessage.textContent = "";
    PrevClima.setBusy(button, true);
    try {
      const result = await PrevClima.request("/integrations/inmet/sync-warnings", { method: "POST" });
      alertReviewMessage.textContent = result.synced
        ? `${result.message}: ${result.imported} importado(s), ${result.skipped} ignorado(s).`
        : `${result.message}. Os avisos já armazenados continuam disponíveis.`;
      alertReviewMessage.className = result.synced ? "success" : "error";
      await loadAlerts();
    } catch (error) {
      alertReviewMessage.textContent = error.message;
      alertReviewMessage.className = "error";
    } finally {
      PrevClima.setBusy(button, false);
    }
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = form.querySelector("button[type='submit']");
    message.textContent = "";
    message.className = "error";
    PrevClima.setBusy(button, true);
    try {
      await PrevClima.request("/alerts", {
        method: "POST",
        body: JSON.stringify({
          title: form.elements["alert-title"].value.trim(),
          message: form.elements["alert-message"].value.trim(),
          event_type: form.elements["event-type"].value,
          severity: form.severity.value,
          area_name: form.elements["area-name"].value.trim(),
          latitude: Number(form.elements["alert-latitude"].value),
          longitude: Number(form.elements["alert-longitude"].value),
          radius_km: Number(form.elements["radius-km"].value),
          recommendations: form.recommendations.value.split("\n").map((item) => item.trim()).filter(Boolean),
          valid_until: new Date(form.elements["valid-until"].value).toISOString(),
        }),
      });
      message.className = "success";
      message.textContent = "Alerta publicado com sucesso.";
      form.reset();
      await loadAlerts();
    } catch (error) {
      message.textContent = error.message;
    } finally {
      PrevClima.setBusy(button, false);
    }
  });

  document.querySelector("#professional-logout").addEventListener("click", async () => {
    try { await PrevClima.request("/auth/logout", { method: "POST" }); } finally { window.location.assign("/"); }
  });
});
