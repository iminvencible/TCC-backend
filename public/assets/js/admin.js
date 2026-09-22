document.addEventListener("DOMContentLoaded", async () => {
  const createForm = document.querySelector("#staff-form");
  const searchForm = document.querySelector("#user-search-form");
  const list = document.querySelector("#users-list");
  const createMessage = document.querySelector("#staff-message");
  const usersMessage = document.querySelector("#users-message");

  function paragraph(text, className = "") {
    const element = document.createElement("p");
    element.className = className;
    element.textContent = text;
    return element;
  }

  try {
    const user = await PrevClima.request("/users/me");
    if (user.role !== "ADMIN") {
      window.location.replace(user.role === "METEOROLOGIST" ? "/profissional.html" : "/inicio.html");
      return;
    }
    PrevClima.applyTheme(user);
  } catch (_error) {
    window.location.replace("/meteorologista.html?next=/admin.html");
    return;
  }

  function accountCard(user) {
    const card = document.createElement("article");
    card.className = "account-card";
    const heading = document.createElement("h3");
    heading.textContent = user.name;
    const badge = document.createElement("span");
    badge.className = "role-badge";
    badge.textContent = PrevClima.roleName(user.role);
    const meta = document.createElement("div");
    meta.className = "account-meta";
    [user.email, user.public_code, user.city && user.state ? `${user.city}, ${user.state}` : "Localização não informada"].forEach((text) => meta.append(paragraph(text)));
    card.append(heading, badge, meta);
    if (user.role !== "ADMIN") {
      const actions = document.createElement("div");
      actions.className = "inline-actions";
      const select = document.createElement("select");
      select.setAttribute("aria-label", `Função de ${user.name}`);
      [["USER", "Usuário"], ["METEOROLOGIST", "Meteorologista"]].forEach(([value, label]) => {
        const option = new Option(label, value, false, user.role === value);
        select.add(option);
      });
      const save = document.createElement("button");
      save.type = "button";
      save.className = "button secondary";
      save.textContent = "Salvar função";
      save.addEventListener("click", async () => {
        PrevClima.setBusy(save, true);
        try {
          await PrevClima.request(`/admin/users/${user.id}/role`, {
            method: "PATCH",
            body: JSON.stringify({ role: select.value }),
          });
          await loadUsers();
        } catch (error) {
          usersMessage.textContent = error.message;
          PrevClima.setBusy(save, false);
        }
      });
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "button reject";
      remove.textContent = "Desativar conta";
      remove.addEventListener("click", async () => {
        if (!window.confirm(`Desativar a conta de ${user.name}?`)) return;
        PrevClima.setBusy(remove, true);
        try {
          await PrevClima.request(`/admin/users/${user.id}`, { method: "DELETE" });
          await loadUsers();
        } catch (error) {
          usersMessage.textContent = error.message;
          PrevClima.setBusy(remove, false);
        }
      });
      actions.append(select, save, remove);
      card.append(actions);
    }
    return card;
  }

  async function loadUsers() {
    usersMessage.textContent = "";
    const search = document.querySelector("#user-search").value.trim();
    try {
      const users = await PrevClima.request(`/admin/users${search ? `?search=${encodeURIComponent(search)}` : ""}`);
      list.replaceChildren();
      if (!users.length) list.append(paragraph("Nenhuma conta encontrada.", "empty"));
      else users.forEach((user) => list.append(accountCard(user)));
    } catch (error) {
      list.replaceChildren(paragraph(error.message, "error"));
    }
  }

  createForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = createForm.querySelector("button[type='submit']");
    createMessage.textContent = "";
    createMessage.className = "error";
    PrevClima.setBusy(button, true);
    try {
      const user = await PrevClima.request("/admin/users", {
        method: "POST",
        body: JSON.stringify({
          name: createForm.elements["staff-name"].value.trim(),
          email: createForm.elements["staff-email"].value.trim(),
          password: createForm.elements["staff-password"].value,
          role: createForm.elements["staff-role"].value,
          city: null,
          state: null,
        }),
      });
      createMessage.className = "success";
      createMessage.textContent = `Conta de ${user.name} criada.`;
      createForm.reset();
      await loadUsers();
    } catch (error) {
      createMessage.textContent = error.message;
    } finally {
      PrevClima.setBusy(button, false);
    }
  });
  searchForm.addEventListener("submit", (event) => { event.preventDefault(); loadUsers(); });
  document.querySelector("#admin-logout").addEventListener("click", async () => {
    try { await PrevClima.request("/auth/logout", { method: "POST" }); } finally { window.location.assign("/"); }
  });
  loadUsers();
});
