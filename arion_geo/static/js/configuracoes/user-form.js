(() => {
  const init = () => document.querySelectorAll('[data-user-access-form]').forEach((form) => {
    const mode = form.querySelector('[name="scope_mode"]');
    const custom = form.querySelector('[data-scope-custom]');
    const all = form.querySelector('[data-scope-all-hint]');
    const list = form.querySelector('[data-project-list]');
    const search = form.querySelector('[data-project-search]');
    const count = form.querySelector('[data-project-count]');
    const boxes = () => [...(list?.querySelectorAll('input[type="checkbox"]') || [])];
    const update = () => {
      const isCustom = mode?.value === 'custom';
      if (custom) custom.hidden = !isCustom;
      if (all) all.hidden = isCustom;
      if (count) { const n = boxes().filter((box) => box.checked).length; count.textContent = `${n} projeto${n === 1 ? '' : 's'} selecionado${n === 1 ? '' : 's'}`; }
    };
    mode?.addEventListener('change', update);
    list?.addEventListener('change', update);
    search?.addEventListener('input', () => { const q = search.value.trim().toLocaleLowerCase('pt-BR'); list?.querySelectorAll('li').forEach((li) => { li.hidden = !li.textContent.toLocaleLowerCase('pt-BR').includes(q); }); });
    form.querySelector('[data-project-clear]')?.addEventListener('click', () => { boxes().forEach((box) => { box.checked = false; }); update(); });
    form.querySelector('[data-project-select-visible]')?.addEventListener('click', () => { list?.querySelectorAll('li:not([hidden]) input[type="checkbox"]').forEach((box) => { box.checked = true; }); update(); });
    update();
  });
  document.addEventListener('DOMContentLoaded', init);
  if (document.readyState !== 'loading') init();
})();
