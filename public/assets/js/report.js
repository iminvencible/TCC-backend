document.addEventListener("DOMContentLoaded", async () => {
  const form = document.querySelector("#report-form");
  const message = document.querySelector("#report-message");
  const history = document.querySelector("#report-history");

  function localDateTime(date) {
    const offset = date.getTimezoneOffset();
    return new Date(date.getTime() - offset * 60000).toISOString().slice(0, 16);
  }

  function renderHistory(items) {
    history.replaceChildren();
    if (!items.length) {
      const empty = document.createElement("p");
      empty.className = "empty";
      empty.textContent = "Você ainda não enviou relatos.";
      history.append(empty);
      return;
    }
    items.forEach((item) => {
      const article = document.createElement("article");
      article.className = "content-card report-history-card";
      const status = document.createElement("span");
      const description = document.createElement("p");
      const date = document.createElement("small");
      status.className = `report-status status-${item.status.toLowerCase()}`;
      status.textContent = item.status === "PENDING" ? "Em análise" : item.status === "APPROVED" ? "Aprovado" : "Rejeitado";
      description.textContent = item.description;
      date.textContent = new Date(item.occurred_at).toLocaleString("pt-BR");
      article.append(status, description, date);
      history.append(article);
    });
  }

  async function loadHistory() {
    renderHistory(await PrevClima.request("/reports/me"));
  }

  try {
    const user = await PrevClima.request("/users/me");
    PrevClima.applyTheme(user);
    if (user.latitude !== null && user.longitude !== null) {
      form.latitude.value = user.latitude;
      form.longitude.value = user.longitude;
    }
    form.elements["occurred-at"].value = localDateTime(new Date());
    await loadHistory();
  } catch (error) {
    if (error.status === 401) window.location.replace("/?next=/relato.html");
    else message.textContent = error.message;
    return;
  }

  document.querySelector("#use-location").addEventListener("click", () => {
    if (!navigator.geolocation) {
      message.textContent = "Geolocalização indisponível neste navegador.";
      return;
    }
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        form.latitude.value = coords.latitude.toFixed(6);
        form.longitude.value = coords.longitude.toFixed(6);
        message.textContent = "Localização preenchida.";
        message.className = "success";
      },
      () => { message.textContent = "Não foi possível obter sua localização."; },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 300000 },
    );
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = form.querySelector("button[type='submit']");
    message.className = "error";
    message.textContent = "";
    PrevClima.setBusy(button, true);
    try {
      await PrevClima.request("/reports", {
        method: "POST",
        body: JSON.stringify({
          description: form.description.value.trim(),
          occurred_at: new Date(form.elements["occurred-at"].value).toISOString(),
          latitude: Number(form.latitude.value),
          longitude: Number(form.longitude.value),
          image_url: form.elements["image-url"].value.trim() || null,
        }),
      });
      message.className = "success";
      message.textContent = "Relato enviado para análise.";
      form.description.value = "";
      form.elements["image-url"].value = "";
      await loadHistory();
    } catch (error) {
      message.textContent = error.message;
    } finally {
      PrevClima.setBusy(button, false);
    }
  });
});
