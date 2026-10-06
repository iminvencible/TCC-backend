import {
  api,
  esc,
  date,
  empty,
  panel,
  field,
  submit,
  action,
  notify,
  json,
  alertCard,
} from "./ui.js";
import { stationView } from "./stations.js";
import { drawMap } from "./map.js";

const page = document.querySelector("#page");
let user,
  map,
  navigationVersion = 0;
const professional = () => user.role === "METEOROLOGIST";
const nav = [
  ["dashboard", "Painel", "◫"],
  ["alerts", "Alertas", "◉"],
  ["map", "Mapa e previsão", "◎"],
  ["stations", "Estações INMET", "⌁"],
  ["reports", "Relatos", "▤"],
  ["users", "Usuários e equipe", "♙"],
];
const copy = {
  dashboard: ["Painel meteorológico", "Situação atual das regiões monitoradas"],
  alerts: ["Alertas", "Avisos oficiais e comunicados da equipe"],
  map: ["Mapa e previsão", "Áreas de aviso e previsões por localidade"],
  stations: ["Estações INMET", "Observações, temperatura e histórico BDMEP"],
  reports: ["Relatos", "Revise as ocorrências enviadas pela comunidade"],
  users: ["Usuários e equipe", "Gerencie contas e credencie meteorologistas"],
};
const views = {
  dashboard,
  alerts,
  map: mapView,
  stations: stationView,
  reports,
  users,
};

async function dashboard(host) {
  const [summary, alerts] = await Promise.all([
    api("/dashboard"),
    api("/alerts"),
  ]);
  host.innerHTML = `<div class="panel kpis">${[
    ["Alertas ativos", summary.active_alerts],
    ["Avisos INMET", summary.official_alerts],
    ["Relatos pendentes", summary.pending_reports],
    ["Estações cadastradas", summary.stations],
  ]
    .map(
      ([label, value]) =>
        `<div class="kpi"><span class="kpi-n">${value}</span><span class="kpi-l">${label}</span></div>`,
    )
    .join(
      "",
    )}</div><div class="dash"><div class="stack">${panel("Visão do território", '<div id="console-map" class="console-map"></div><p class="hint">As áreas indicam avisos. Pontos indicam previsões, sem inferir risco regional.</p>', '<a class="btn" href="#map">Ampliar mapa</a>')}${panel("Atividade recente", summary.activity.length ? `<ul class="log">${summary.activity.map((e) => `<li><span class="lb"></span>${esc(activityLabel(e.action))}<time>${date(e.created_at)}</time></li>`).join("")}</ul>` : empty("Nenhuma atividade registrada."))}</div><div class="stack">${panel("Atenção nas próximas horas", alerts.slice(0, 3).map(alertCard).join("") || empty("Nenhum alerta ativo na consulta."))}${panel("Observações de estações", `<p class="hint">Última medição armazenada</p><h3>${date(summary.latest_observation_at)}</h3><p class="hint">${summary.latest_observation_at ? "Confira a data antes de usar a medição." : "Atualize o catálogo e consulte uma estação para começar."}</p><a class="btn" href="#stations">Consultar INMET</a>`)}</div></div>`;
  document.querySelector("#sync-status").textContent =
    `Consultado às ${new Date(summary.generated_at).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}`;
  map = await drawMap(host.querySelector("#console-map"));
}

function activityLabel(value) {
  return (
    {
      INMET_STATIONS_SYNCED: "Catálogo INMET atualizado",
      INMET_OBSERVATIONS_SYNCED: "Medições INMET atualizadas",
      BDMEP_IMPORTED: "Histórico BDMEP importado",
      ALERT_REVIEWED: "Alerta revisado",
      METEOROLOGIST_CREATED: "Meteorologista credenciado",
      USER_ROLE_CHANGED: "Permissão de conta atualizada",
      USER_DEACTIVATED: "Conta desativada",
      INMET_WARNINGS_SYNCED: "Avisos INMET sincronizados",
    }[value] || "Registro de operação"
  );
}

async function alerts(host) {
  const data = await api(
    professional() ? "/alerts/review-queue?limit=200" : "/alerts",
  );
  host.innerHTML = `<div class="toolbar"><label class="grow">Buscar aviso<input id="alert-search" class="field" placeholder="Título ou região"></label>${professional() ? '<button id="warning-sync" class="btn">Sincronizar INMET</button><button id="new-alert" class="btn primary">+ Emitir alerta</button>' : ""}</div><div id="alert-list" class="stack"></div>`;
  function render() {
    const q = host
      .querySelector("#alert-search")
      .value.toLocaleLowerCase("pt-BR");
    const filtered = data.filter((a) =>
      `${a.title} ${a.area_name}`.toLocaleLowerCase("pt-BR").includes(q),
    );
    host.querySelector("#alert-list").innerHTML =
      filtered
        .map(
          (a) =>
            `<div>${alertCard(a)}${professional() ? `<form class="review-form row" data-id="${a.id}"><span class="hint">Situação: ${esc({ ACTIVE: "Ativo", FALSE_ALARM: "Alarme falso", NEEDS_CORRECTION: "Requer correção" }[a.validation_status])}</span><label class="sr" for="status-${a.id}">Nova situação</label><select class="field" id="status-${a.id}" name="validation_status"><option value="NEEDS_CORRECTION">Requer correção</option><option value="FALSE_ALARM">Alarme falso</option><option value="ACTIVE">Ativo</option></select><input class="field" aria-label="Motivo da revisão" name="reason" minlength="10" maxlength="2000" required placeholder="Motivo da revisão (mín. 10 caracteres)"><button class="btn" type="submit">Salvar revisão</button></form>` : ""}</div>`,
        )
        .join("") || empty("Nenhum aviso encontrado.");
    host.querySelectorAll(".review-form").forEach((form) =>
      submit(form, async (payload) => {
        await api(`/alerts/${form.dataset.id}/review`, json("POST", payload));
        notify("Revisão salva com histórico.");
        await navigate();
      }),
    );
  }
  render();
  host.querySelector("#alert-search").addEventListener("input", render);
  host.querySelector("#warning-sync")?.addEventListener("click", (event) =>
    action(event.currentTarget, async () => {
      const result = await api("/integrations/inmet/sync-warnings", {
        method: "POST",
      });
      await alerts(host);
      notify(result.message, !result.synced);
    }),
  );
  host.querySelector("#new-alert")?.addEventListener("click", newAlert);
}

function newAlert() {
  const dialog = document.querySelector("#editor");
  dialog.innerHTML = `<form id="alert-editor" class="stack"><div class="row spread"><h2>Emitir alerta</h2><button class="btn" type="button" id="close-editor">Fechar</button></div><div class="form-grid">${field("Título", "title", "text", 'required minlength="3" maxlength="140"')}${field("Região", "area_name", "text", 'required minlength="2" maxlength="160"')}<label>Evento<select class="field" name="event_type"><option value="SEVERE_STORM">Tempestade severa</option><option value="HEAVY_RAIN">Chuva intensa</option><option value="WINDSTORM">Vendaval</option><option value="TORNADO">Tornado</option></select></label><label>Gravidade<select class="field" name="severity"><option value="MODERATE">Moderado</option><option value="HIGH">Alto</option><option value="CRITICAL">Crítico</option><option value="LOW">Baixo</option></select></label><label class="full">Mensagem<textarea class="field" name="message" minlength="10" maxlength="5000" required></textarea></label>${field("Latitude", "latitude", "number", 'required min="-90" max="90" step="any"')}${field("Longitude", "longitude", "number", 'required min="-180" max="180" step="any"')}${field("Raio (km)", "radius_km", "number", 'required min="0.1" max="1000" step="any"')}${field("Válido até", "valid_until", "datetime-local", "required")}<label class="full">Recomendações (uma por linha)<textarea class="field" name="recommendations" required maxlength="3600"></textarea></label></div><p class="hint">O aviso será publicado no site e no aplicativo. A área é definida pelas coordenadas e pelo raio.</p><p id="editor-error" class="error" role="alert"></p><button class="btn primary" type="submit">Publicar alerta</button></form>`;
  dialog.querySelector("#close-editor").onclick = () => dialog.close();
  submit(dialog.querySelector("form"), async (data) => {
    try {
      await api(
        "/alerts",
        json("POST", {
          ...data,
          latitude: Number(data.latitude),
          longitude: Number(data.longitude),
          radius_km: Number(data.radius_km),
          valid_until: new Date(data.valid_until).toISOString(),
          recommendations: data.recommendations
            .split("\n")
            .map((s) => s.trim())
            .filter(Boolean),
        }),
      );
      dialog.close();
      await navigate();
      notify("Alerta publicado.");
    } catch (error) {
      dialog.querySelector("#editor-error").textContent = error.message;
    }
  });
  dialog.showModal();
}

async function mapView(host) {
  host.innerHTML = panel(
    "Mapa meteorológico",
    '<div id="console-map" class="console-map large"></div><p class="hint">Avisos oficiais do INMET e avisos manuais. Previsões pontuais do Open-Meteo são identificadas separadamente.</p>',
  );
  map = await drawMap(host.querySelector("#console-map"));
}

async function reports(host) {
  const data = await api("/reports/review-queue");
  host.innerHTML =
    data
      .map((r) =>
        panel(
          `Relato #${r.id}`,
          `<p>${esc(r.description)}</p><p class="hint">${date(r.occurred_at)} · ${esc(r.latitude)}, ${esc(r.longitude)}</p><form class="report-review form-grid" data-id="${r.id}"><label>Resultado<select class="field" name="status"><option value="APPROVED">Aprovado</option><option value="REJECTED">Rejeitado</option></select></label><label>Observação<input class="field" name="review_notes" maxlength="2000"></label><button type="submit" class="btn primary">Concluir revisão</button></form>`,
        ),
      )
      .join("") || empty("Nenhum relato aguarda análise.");
  host.classList.add("stack");
  host.querySelectorAll(".report-review").forEach((form) =>
    submit(form, async (data) => {
      await api(
        `/reports/${form.dataset.id}/review`,
        json("PATCH", { ...data, review_notes: data.review_notes || null }),
      );
      await reports(host);
      notify("Relato revisado.");
    }),
  );
}

async function users(host) {
  host.innerHTML = `<div class="two">${panel("Credenciar meteorologista", `<form id="staff-form" class="stack">${field("Nome completo", "name", "text", 'required minlength="2" maxlength="120"')}${field("E-mail", "email", "email", "required")}${field("Senha temporária", "password", "password", 'required minlength="8" maxlength="128" autocomplete="new-password"')}<p class="hint">Use maiúscula, minúscula, número e símbolo.</p><button class="btn primary" type="submit">Criar conta</button></form>`)}${panel("Contas ativas", '<form id="user-search" class="row"><input class="field" name="search" aria-label="Nome, e-mail ou código" placeholder="Nome, e-mail ou código"><button type="submit" class="btn">Buscar</button></form><div id="accounts" class="stack"></div><div class="row"><button id="previous-users" class="btn">Anterior</button><button id="next-users" class="btn">Próximas</button></div>')}</div>`;
  let offset = 0,
    search = "";
  async function load() {
    const data = await api(
      `/admin/users?limit=20&offset=${offset}&search=${encodeURIComponent(search)}`,
    );
    host.querySelector("#previous-users").disabled = offset === 0;
    host.querySelector("#next-users").disabled = data.length < 20;
    host.querySelector("#accounts").innerHTML =
      data
        .map(
          (u) =>
            `<article class="data-card"><div class="row spread"><strong>${esc(u.name)}</strong><span class="pill pri">${esc(PrevClima.roleName(u.role))}</span></div><p>${esc(u.email)}</p><p class="hint">${esc(u.public_code)}</p>${u.role !== "ADMIN" ? `<div class="row"><select class="field" aria-label="Função de ${esc(u.name)}" data-role="${u.id}"><option value="USER" ${u.role === "USER" ? "selected" : ""}>Usuário</option><option value="METEOROLOGIST" ${u.role === "METEOROLOGIST" ? "selected" : ""}>Meteorologista</option></select><button class="btn" data-save="${u.id}">Salvar função</button><button class="btn danger" data-disable="${u.id}">Desativar</button></div>` : ""}</article>`,
        )
        .join("") || empty("Nenhuma conta encontrada.");
    host.querySelectorAll("[data-save]").forEach(
      (button) =>
        (button.onclick = () =>
          action(button, async () => {
            await api(
              `/admin/users/${button.dataset.save}/role`,
              json("PATCH", {
                role: host.querySelector(`[data-role="${button.dataset.save}"]`)
                  .value,
              }),
            );
            await load();
            notify("Função atualizada; sessões anteriores revogadas.");
          })),
    );
    host.querySelectorAll("[data-disable]").forEach(
      (button) =>
        (button.onclick = () =>
          action(button, async () => {
            if (!confirm("Desativar esta conta e revogar suas sessões?"))
              return;
            await api(`/admin/users/${button.dataset.disable}`, {
              method: "DELETE",
            });
            await load();
            notify("Conta desativada.");
          })),
    );
  }
  submit(host.querySelector("#staff-form"), async (data) => {
    await api("/admin/users", json("POST", { ...data, role: "METEOROLOGIST" }));
    host.querySelector("#staff-form").reset();
    offset = 0;
    await load();
    notify("Meteorologista credenciado.");
  });
  submit(host.querySelector("#user-search"), async (data) => {
    search = data.search.trim();
    offset = 0;
    await load();
  });
  host.querySelector("#previous-users").onclick = (event) =>
    action(event.currentTarget, async () => {
      offset = Math.max(0, offset - 20);
      await load();
    });
  host.querySelector("#next-users").onclick = (event) =>
    action(event.currentTarget, async () => {
      offset += 20;
      await load();
    });
  await load();
}

async function navigate() {
  const version = ++navigationVersion;
  const key = location.hash.slice(1) || "dashboard";
  const allowed = nav.filter(
    ([key]) => key !== (professional() ? "users" : "reports"),
  );
  if (!allowed.some(([name]) => name === key)) {
    location.hash = "dashboard";
    return;
  }
  map?.remove();
  map = null;
  document.querySelector(".side").classList.remove("open");
  document.querySelector(".scrim").classList.remove("on");
  document.querySelector("#notice").hidden = true;
  document.querySelector("#page-title").textContent = copy[key][0];
  document.querySelector("#page-sub").textContent = copy[key][1];
  document.querySelector("#nav").innerHTML = allowed
    .map(
      ([id, label, icon]) =>
        `<a class="nav-i ${id === key ? "on" : ""}" href="#${id}" ${id === key ? 'aria-current="page"' : ""}><span aria-hidden="true">${icon}</span>${label}</a>`,
    )
    .join("");
  const host = document.createElement("div");
  page.replaceChildren(host);
  host.innerHTML = empty("Carregando dados…");
  try {
    await views[key](host);
  } catch (error) {
    if (version === navigationVersion) {
      host.innerHTML = empty(error.message);
      notify(error.message, true);
    }
  }
}

async function start() {
  try {
    user = await api("/users/me");
  } catch (error) {
    if (error.status === 401) location.replace("/meteorologista.html");
    else page.innerHTML = empty(error.message);
    return;
  }
  if (!["ADMIN", "METEOROLOGIST"].includes(user.role)) {
    location.replace("/inicio.html");
    return;
  }
  document.querySelector("#identity-name").textContent = user.name;
  document.querySelector("#identity-role").textContent = PrevClima.roleName(
    user.role,
  );
  document.querySelector("#avatar").textContent = user.name
    .split(" ")
    .slice(0, 2)
    .map((s) => s[0])
    .join("");
  document.documentElement.dataset.theme = user.dark_theme ? "dark" : "light";
  document.querySelector("#theme").onclick = (event) =>
    action(event.currentTarget, async () => {
      const dark = document.documentElement.dataset.theme !== "dark";
      await api("/users/me", json("PATCH", { dark_theme: dark }));
      document.documentElement.dataset.theme = dark ? "dark" : "light";
    });
  document.querySelector("#logout").onclick = (event) =>
    action(event.currentTarget, async () => {
      await api("/auth/logout", { method: "POST" });
      location.assign("/");
    });
  document.querySelector("#menu").onclick = () => {
    document.querySelector(".side").classList.toggle("open");
    document.querySelector(".scrim").classList.toggle("on");
  };
  document.querySelector(".scrim").onclick = () => {
    document.querySelector(".side").classList.remove("open");
    document.querySelector(".scrim").classList.remove("on");
  };
  addEventListener("hashchange", navigate);
  await navigate();
}
start();
