document.addEventListener("DOMContentLoaded", async () => {
  const list = document.querySelector("#education-list");

  function card(item) {
    const article = document.createElement("article");
    article.className = "content-card";
    const title = document.createElement("h2");
    const body = document.createElement("p");
    const source = document.createElement("a");
    title.textContent = item.title;
    body.textContent = item.body;
    source.textContent = "Consultar fonte oficial";
    source.target = "_blank";
    source.rel = "noopener noreferrer";
    if (/^https?:\/\//.test(item.reference_url)) source.href = item.reference_url;
    if (item.media_url && /^\/assets\/img\/safety-[a-z]+\.svg$/.test(item.media_url)) {
      const picture = document.createElement("img");
      picture.src = item.media_url; picture.alt = ""; picture.width = 200; picture.height = 140;
      picture.loading = "lazy"; article.append(picture);
    }
    article.append(title, body, source);
    return article;
  }

  try {
    const items = await PrevClima.request("/education");
    list.replaceChildren();
    if (!items.length) {
      const empty = document.createElement("p");
      empty.className = "empty";
      empty.textContent = "Nenhuma informação foi publicada ainda.";
      list.append(empty);
    } else items.forEach((item) => list.append(card(item)));
  } catch (error) {
    list.textContent = error.message;
    list.className = "error";
  }
});
