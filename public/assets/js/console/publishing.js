import { api, esc, date, field, json, notify } from "./ui.js";
import { polygonEditor } from "./polygon-editor.js";

function localTime(value) {
  const d = value ? new Date(value) : new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}
export function openPublisher(kind, refresh, item = null) {
  const forecast = kind === "forecast";
  const dialog = document.querySelector("#editor");
  dialog.innerHTML = `<form class="stack"><div class="row spread"><h2>${item ? "Editar previsão" : forecast ? "Emitir previsão de tempo severo" : "Emitir alerta"}</h2><button class="btn" type="button" data-close>Fechar</button></div>
    <div data-draft><div class="form-grid">
    ${field("Região", "area_name", "text", 'required minlength="2" maxlength="160"')}
    ${forecast ? "" : '<label>Tipo<select class="field" name="event_type"><option value="SEVERE_STORM">Tempestade Severa</option><option value="TORNADO">Tornado</option></select></label>'}
    <label>Nível<select class="field" name="severity"><option value="LOW">Baixo</option><option value="MODERATE">Moderado</option><option value="HIGH">Alto</option><option value="CRITICAL">Crítico</option></select></label>
    ${forecast ? field("Data de emissão", "issued_at", "datetime-local", 'required') : ""}
    ${field("Válido até", "valid_until", "datetime-local", 'required')}
    <label class="full">Descrição<textarea class="field" name="description" required minlength="10" maxlength="5000"></textarea></label>
    </div><div data-polygon></div></div>
    <section data-review hidden><h3>Confira antes de publicar</h3><p data-summary class="publication-summary"></p><button class="btn" type="button" data-back>Voltar e corrigir</button></section>
    <p class="hint">${forecast ? "A previsão só poderá ser alterada ou excluída nos 30 minutos seguintes à publicação. Editar não reinicia o prazo." : "O alerta publicado não poderá ser editado ou excluído. As orientações de proteção são definidas pelo tipo de alerta."}</p>
    <p data-error class="error" role="alert"></p><button class="btn primary" type="submit">Conferir informações</button></form>`;
  const form = dialog.querySelector("form");
  form.elements.valid_until.value = localTime(item?.valid_until || Date.now() + 3600000);
  if (forecast) form.elements.issued_at.value = localTime(item?.issued_at);
  if (item) for (const key of ["area_name", "severity", "description"]) form.elements[key].value = item[key];
  let payload = null, busy = false;
  dialog.querySelector("[data-close]").onclick = () => { if (!busy) dialog.close(); };
  dialog.showModal();
  const drawing = polygonEditor(dialog.querySelector("[data-polygon]"), item?.polygon);
  dialog.addEventListener("close", () => drawing.destroy(), { once: true });
  dialog.querySelector("[data-back]").onclick = () => {
    payload = null;
    dialog.querySelector("[data-draft]").hidden = false;
    dialog.querySelector("[data-review]").hidden = true;
    form.querySelector('[type="submit"]').textContent = "Conferir informações";
  };
  form.onsubmit = async (event) => {
    event.preventDefault();
    if (busy) return;
    const error = dialog.querySelector("[data-error]"); error.textContent = "";
    try {
      if (!payload) {
        const data = Object.fromEntries(new FormData(form));
        if (new Date(data.valid_until) <= new Date()) throw new Error("A validade deve estar no futuro.");
        const polygon = drawing.geometry();
        payload = forecast ? {
          ...data, polygon, issued_at: new Date(data.issued_at).toISOString(), valid_until: new Date(data.valid_until).toISOString(),
        } : {
          area_name: data.area_name, severity: data.severity, event_type: data.event_type,
          title: `${PrevClima.eventName(data.event_type)} — ${data.area_name}`.slice(0, 140),
          message: data.description, polygon, valid_until: new Date(data.valid_until).toISOString(),
        };
        dialog.querySelector("[data-summary]").textContent = `${data.area_name}\n${forecast ? "Previsão de tempo severo" : PrevClima.eventName(data.event_type)} · ${PrevClima.severityName(data.severity)}\n${forecast ? `Emissão: ${date(payload.issued_at)}\n` : ""}Até ${date(payload.valid_until)}\n${polygon.coordinates[0].length - 1} vértices na área desenhada\n\n${data.description}`;
        dialog.querySelector("[data-draft]").hidden = true;
        dialog.querySelector("[data-review]").hidden = false;
        form.querySelector('[type="submit"]').textContent = item ? "Salvar alterações" : "Tudo certo — publicar";
        return;
      }
      busy = true;
      form.querySelectorAll("button").forEach((b) => { b.disabled = true; });
      const endpoint = forecast ? `/severe-forecasts${item ? `/${item.id}` : ""}` : "/alerts";
      await api(endpoint, json(item ? "PATCH" : "POST", payload));
      dialog.close();
      await refresh();
      notify(item ? "Previsão atualizada." : "Publicado com sucesso.");
    } catch (failure) { error.textContent = failure.message; }
    finally { busy = false; form.querySelectorAll("button").forEach((b) => { b.disabled = false; }); }
  };
}

export async function forecastList(host, refresh) {
  const rows = await api("/severe-forecasts");
  host.innerHTML = rows.length ? rows.map((f) => `<article class="panel stack"><div class="row spread"><h3>${esc(f.area_name)}</h3><span class="pill">${esc(PrevClima.severityName(f.severity))}</span></div><p>${esc(f.description)}</p><p class="hint">Emissão: ${date(f.issued_at)} · Válida até ${date(f.valid_until)}<br>Edição permitida até ${date(f.editable_until)}</p><div class="row"><button class="btn" data-edit="${f.id}" ${Date.parse(f.editable_until) <= Date.now() ? "disabled" : ""}>Editar</button><button class="btn danger" data-delete="${f.id}" ${Date.parse(f.editable_until) <= Date.now() ? "disabled" : ""}>Excluir</button></div></article>`).join("") : '<p class="hint">Nenhuma previsão de tempo severo publicada.</p>';
  host.querySelectorAll("[data-edit]").forEach((b) => { b.onclick = () => openPublisher("forecast", refresh, rows.find((f) => f.id === Number(b.dataset.edit))); });
  host.querySelectorAll("[data-delete]").forEach((b) => { b.onclick = async () => {
    if (!window.confirm("Excluir esta previsão de tempo severo?")) return;
    b.disabled = true;
    try { await api(`/severe-forecasts/${b.dataset.delete}`, { method: "DELETE" }); await refresh(); notify("Previsão excluída."); }
    catch (error) { notify(error.message, true); b.disabled = false; }
  }; });
}
