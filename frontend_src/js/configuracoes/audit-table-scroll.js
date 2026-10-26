(() => {
  const topScroller = document.querySelector(".audit-table-scroll-top");
  const tableScroller = document.querySelector(".audit-table-wrap");
  const table = tableScroller?.querySelector(".audit-table");
  const spacer = topScroller?.querySelector(".audit-table-scroll-top-spacer");

  if (!topScroller || !tableScroller || !table || !spacer) return;

  const updateScroller = () => {
    spacer.style.width = `${Math.max(table.scrollWidth, tableScroller.clientWidth)}px`;
    const hasOverflow = tableScroller.scrollWidth > tableScroller.clientWidth + 1;
    topScroller.hidden = !hasOverflow;

    if (!hasOverflow) {
      topScroller.scrollLeft = 0;
      tableScroller.scrollLeft = 0;
    }
  };

  topScroller.addEventListener("scroll", () => {
    if (tableScroller.scrollLeft !== topScroller.scrollLeft) {
      tableScroller.scrollLeft = topScroller.scrollLeft;
    }
  });

  tableScroller.addEventListener("scroll", () => {
    if (topScroller.scrollLeft !== tableScroller.scrollLeft) {
      topScroller.scrollLeft = tableScroller.scrollLeft;
    }
  });

  updateScroller();

  if ("ResizeObserver" in window) {
    const resizeObserver = new ResizeObserver(updateScroller);
    resizeObserver.observe(tableScroller);
    resizeObserver.observe(table);
  } else {
    window.addEventListener("resize", updateScroller);
  }
})();
