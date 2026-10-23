document.addEventListener("DOMContentLoaded", () => {
  const input = document.querySelector("[data-integration-search]");
  if (!input) return;
  const cards = [...document.querySelectorAll("[data-integration-card]")];
  const empty = document.querySelector(".integration-search-empty");
  input.addEventListener("input", () => {
    const query = input.value.trim().toLocaleLowerCase("pt-BR");
    let visible = 0;
    cards.forEach((card) => {
      const match = card.textContent.toLocaleLowerCase("pt-BR").includes(query);
      card.hidden = !match;
      if (match) visible += 1;
    });
    if (empty) empty.hidden = visible > 0;
  });
});
