import {
  api,
  esc,
  date,
  metric,
  empty,
  panel,
  field,
  submit,
  action,
  notify,
  json,
} from "./ui.js";

export async function stationView(host, { readOnly = false } = {}) {
  host.innerHTML = `<div class="toolbar"><p class="grow hint">Medições observadas pelo INMET. Horários exibidos no seu fuso local.</p><button id="catalog-sync" class="btn primary">Atualizar catálogo</button></div>
    <div class="two"><div class="stack">${panel("Estações meteorológicas", `<form id="station-filter" class="row">${field("UF", "state", "text", 'maxlength="2" placeholder="SP"')}<button type="submit" class="btn">Filtrar</button></form><label>Estação<select id="station-select" class="field"><option value="">Selecione uma estação</option></select></label><p id="station-meta" class="hint"></p><form id="station-sync" class="form-grid">${field("De", "start", "date", "required")}${field("Até", "end", "date", "required")}<button class="btn primary" type="submit">Consultar INMET</button></form>`)}
    ${panel("Importar histórico BDMEP", `<p class="hint">Aceita o JSON de get_dados() do INMET-API-REST e o CSV do INMET-API-temperature. Dados históricos permanecem identificados como BDMEP.</p><form id="history-import" class="form-grid"><label>Formato<select name="format" class="field"><option value="temperature-csv">INMET-API-temperature · CSV</option><option value="rest-json">INMET-API-REST · JSON</option></select></label><label>Período do arquivo<select class="field" name="period"><option value="HOURLY">Horário / DAYFULL</option><option value="DAILY">Diário</option><option value="MONTHLY">Mensal</option></select></label><label class="full">Arquivo<input name="file" type="file" accept=".csv,.json" required></label><button class="btn" type="submit">Importar registros</button></form>`)}</div>
    ${panel("Histórico de observações", '<div id="observations">Selecione uma estação para consultar.</div>')}</div>`;
  const select = host.querySelector("#station-select");
  const syncForm = host.querySelector("#station-sync");
  syncForm.elements.start.value = new Date(Date.now() - 86400000)
    .toISOString()
    .slice(0, 10);
  syncForm.elements.end.value = new Date().toISOString().slice(0, 10);
  let stations = [];
  async function loadStations(state = "") {
    const previous = select.value;
    stations = await api(
      `/stations?limit=1000${state ? `&state=${encodeURIComponent(state)}` : ""}`,
    );
    select.innerHTML =
      '<option value="">Selecione uma estação</option>' +
      stations
        .map(
          (s) =>
            `<option value="${esc(s.code)}">${esc(s.name)} · ${esc(s.state)} · ${esc(s.code)}</option>`,
        )
        .join("");
    select.value = stations.some((s) => s.code === previous) ? previous : "";
    if (!select.value && stations.length)
      host.querySelector("#observations").innerHTML = empty(
        "Selecione uma estação para consultar.",
      );
    if (!stations.length)
      host.querySelector("#observations").innerHTML = empty(
        readOnly
          ? "Nenhuma estação disponível no momento."
          : "Catálogo vazio. Atualize o catálogo ou importe um arquivo BDMEP.",
      );
  }
  async function loadObservations() {
    if (!select.value) {
      host.querySelector("#station-meta").textContent = "";
      host.querySelector("#observations").innerHTML = empty("Selecione uma estação para consultar.");
      return;
    }
    const station = stations.find((s) => s.code === select.value);
    host.querySelector("#station-meta").textContent =
      `${station.kind === "AUTOMATIC" ? "Automática" : "Convencional"} · ${station.latitude ?? "—"}, ${station.longitude ?? "—"}`;
    const data = await api(
      `/stations/${encodeURIComponent(select.value)}/observations?limit=100`,
    );
    const latest = data[0];
    host.querySelector("#observations").innerHTML = data.length
      ? `<p class="hint">Até 100 registros mais recentes · ${latest.source === "BDMEP" ? "Histórico BDMEP" : "INMET"}${Date.now() - new Date(latest.observed_at) > 86400000 ? " · Dados anteriores às últimas 24 h" : ""}</p><div class="table-scroll"><table><thead><tr><th>Observação</th><th>Período</th><th>°C</th><th>Umidade</th><th>Chuva</th><th>Vento</th></tr></thead><tbody>${data.map((o) => `<tr><td>${date(o.observed_at)}<small>${esc(o.source)}</small></td><td>${esc({ HOURLY: "Horário", DAILY: "Diário", MONTHLY: "Mensal" }[o.period])}</td><td>${metric(o.temperature_c)}</td><td>${metric(o.humidity, "%")}</td><td>${metric(o.precipitation_mm, " mm")}</td><td>${metric(o.wind_ms, " m/s")}</td></tr>`).join("")}</tbody></table></div>`
      : empty(
          readOnly
            ? "Nenhuma medição disponível para esta estação."
            : "Nenhuma medição salva. Consulte o INMET para o intervalo selecionado.",
        );
  }
  select.addEventListener("change", () => action(select, loadObservations));
  submit(host.querySelector("#station-filter"), async (data) => {
    await loadStations(data.state.trim().toUpperCase());
  });
  if (readOnly) {
    host.querySelector("#catalog-sync").remove();
    syncForm.remove();
    host.querySelector("#history-import").closest(".panel").remove();
    await loadStations();
    return;
  }
  host.querySelector("#catalog-sync").addEventListener("click", (event) =>
    action(event.currentTarget, async () => {
      const result = await api("/stations/sync-catalog", { method: "POST" });
      await loadStations();
      notify(
        `${result.imported} estações atualizadas; ${result.skipped} registros ignorados.`,
      );
    }),
  );
  submit(syncForm, async (data) => {
    if (!select.value) throw new Error("Selecione uma estação.");
    const result = await api(
      `/stations/${select.value}/sync`,
      json("POST", data),
    );
    await loadObservations();
    notify(
      `${result.inserted} medições novas; ${result.updated} atualizadas; ${result.skipped} ignoradas.`,
    );
  });
  submit(host.querySelector("#history-import"), async (data) => {
    if (data.file.size > 2000000)
      throw new Error("O arquivo deve ter até 2 MB.");
    const result = await api(
      "/stations/import",
      json("POST", {
        format: data.format,
        period: data.period,
        content: await data.file.text(),
      }),
    );
    await loadStations();
    notify(
      `${result.inserted} registros importados, ${result.updated} atualizados e ${result.skipped} ignorados.`,
    );
  });
  await loadStations();
}
