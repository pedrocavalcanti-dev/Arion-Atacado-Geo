(() => {
  const init = () => {
    document.querySelectorAll('[data-scope-form]').forEach((form) => {
      const mode = form.querySelector('[name="mode"]');
      const custom = form.querySelector('[data-scope-custom]');
      const all = form.querySelector('[data-scope-all-hint]');
      const updateMode = () => {
        const isCustom = mode?.value === 'custom';
        if (custom) custom.hidden = !isCustom;
        if (all) all.hidden = isCustom;
        custom?.querySelectorAll('input, button').forEach((control) => { control.disabled = !isCustom; });
      };
      mode?.addEventListener('change', updateMode);
      updateMode();
    });

    document.querySelectorAll('[data-scope-picker]').forEach((picker) => {
      const list = picker.querySelector('[data-option-list]');
      const search = picker.querySelector('[data-option-search]');
      const count = picker.querySelector('[data-option-count]');
      const total = picker.querySelector('[data-option-total]');
      const items = () => [...(list?.querySelectorAll('li') || [])];
      const boxes = () => [...(list?.querySelectorAll('input[type="checkbox"]') || [])];
      const update = () => {
        const n = boxes().filter((box) => box.checked).length;
        const available = boxes().length;
        if (count) count.textContent = `${n} ${picker.dataset[n === 1 ? 'countSingular' : 'countPlural'] || (n === 1 ? 'selecionado' : 'selecionados')}`;
        if (total) total.textContent = `${available} disponíve${available === 1 ? 'l' : 'is'}`;
      };
      search?.addEventListener('input', () => {
        const query = search.value.trim().toLocaleLowerCase('pt-BR');
        items().forEach((item) => { item.hidden = !item.textContent.toLocaleLowerCase('pt-BR').includes(query); });
      });
      list?.addEventListener('change', update);
      picker.querySelector('[data-option-clear]')?.addEventListener('click', () => {
        boxes().forEach((box) => { box.checked = false; });
        update();
      });
      picker.querySelector('[data-option-select-visible]')?.addEventListener('click', () => {
        items().filter((item) => !item.hidden).forEach((item) => {
          const box = item.querySelector('input[type="checkbox"]');
          if (box) box.checked = true;
        });
        update();
      });
      update();
    });
  };
  document.addEventListener('DOMContentLoaded', init);
  if (document.readyState !== 'loading') init();
})();
