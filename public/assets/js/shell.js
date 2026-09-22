document.addEventListener("DOMContentLoaded", async () => {
  const navigation = document.querySelector("[data-role-navigation]");
  if (!navigation) return;

  let user = null;
  try {
    user = await PrevClima.request("/users/me");
  } catch (error) {
    if (error.status !== 401) navigation.dataset.error = "true";
  }

  const links = [
    ["/inicio.html", "Início"],
    ["/alertas.html", "Alertas"],
    ["/mapa.html", "Mapa"],
  ];
  if (user && user.role === "USER") links.push(["/perfil.html", "Perfil"]);
  if (user && user.role === "METEOROLOGIST") {
    links.push(["/profissional.html", "Painel profissional"]);
  }
  if (user && user.role === "ADMIN") links.push(["/admin.html", "Contas"]);
  if (!user) links.push(["/", "Entrar"]);

  const current = window.location.pathname;
  navigation.replaceChildren();
  links.forEach(([href, label]) => {
    const anchor = document.createElement("a");
    anchor.href = href;
    anchor.textContent = label;
    if (current === href) anchor.setAttribute("aria-current", "page");
    navigation.append(anchor);
  });

  const identity = document.querySelector("[data-role-identity]");
  if (identity) {
    identity.textContent = user ? `${user.name} · ${PrevClima.roleName(user.role)}` : "Visitante";
  }
});
