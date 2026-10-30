(() => {
  "use strict";

  const carousel = document.querySelector("[data-login-carousel]");
  if (!carousel) return;

  const slides = Array.from(carousel.querySelectorAll("[data-login-slide]"));
  const dots = Array.from(carousel.querySelectorAll("[data-login-go-to]"));
  const previous = carousel.querySelector("[data-login-previous]");
  const next = carousel.querySelector("[data-login-next]");
  if (slides.length < 2 || !previous || !next) return;

  const autoplayDelay = 7000;
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  let activeIndex = Math.max(0, slides.findIndex((slide) => slide.classList.contains("is-active")));
  let timer = 0;
  let hovered = false;
  let focused = false;
  let interacting = false;
  let touchStart = null;

  function clearTimer() {
    window.clearTimeout(timer);
    timer = 0;
  }

  function isPaused() {
    return hovered || focused || interacting || document.hidden || reducedMotion.matches;
  }

  function scheduleAutoplay() {
    clearTimer();
    if (isPaused()) return;
    timer = window.setTimeout(() => showSlide(activeIndex + 1, false), autoplayDelay);
  }

  function prepareImage(slide) {
    const image = slide.querySelector("img[data-image-src]");
    if (!image || image.dataset.imageAttempted) return;
    const target = image.dataset.imageSrc;
    const fallback = image.dataset.fallbackSrc;
    if (!target || target === fallback) return;

    image.dataset.imageAttempted = "true";
    const preload = new Image();
    preload.onload = () => {
      image.src = target;
      image.classList.remove("is-fallback");
    };
    preload.onerror = () => {
      image.src = fallback || image.src;
      image.classList.add("is-fallback");
    };
    preload.src = target;
  }

  function showSlide(requestedIndex, announce = true) {
    activeIndex = (requestedIndex + slides.length) % slides.length;
    slides.forEach((slide, index) => {
      const active = index === activeIndex;
      slide.classList.toggle("is-active", active);
      slide.setAttribute("aria-hidden", String(!active));
      slide.setAttribute("aria-label", `${index + 1} de ${slides.length}`);
      if (active) prepareImage(slide);
    });
    dots.forEach((dot, index) => {
      const active = index === activeIndex;
      dot.classList.toggle("is-active", active);
      if (active) dot.setAttribute("aria-current", "true");
      else dot.removeAttribute("aria-current");
    });
    carousel.setAttribute("aria-live", announce ? "polite" : "off");
    scheduleAutoplay();
  }

  function markInteraction() {
    interacting = true;
    clearTimer();
  }

  function releaseInteraction() {
    interacting = false;
    scheduleAutoplay();
  }

  previous.addEventListener("click", () => showSlide(activeIndex - 1));
  next.addEventListener("click", () => showSlide(activeIndex + 1));
  dots.forEach((dot) => {
    dot.addEventListener("click", () => showSlide(Number(dot.dataset.loginGoTo)));
  });

  carousel.addEventListener("pointerenter", () => {
    hovered = true;
    clearTimer();
  });
  carousel.addEventListener("pointerleave", () => {
    hovered = false;
    scheduleAutoplay();
  });
  carousel.addEventListener("pointerdown", markInteraction);
  carousel.addEventListener("pointerup", releaseInteraction);
  carousel.addEventListener("pointercancel", releaseInteraction);
  carousel.addEventListener("focusin", () => {
    focused = true;
    clearTimer();
  });
  carousel.addEventListener("focusout", (event) => {
    if (!carousel.contains(event.relatedTarget)) {
      focused = false;
      scheduleAutoplay();
    }
  });
  document.addEventListener("visibilitychange", scheduleAutoplay);
  reducedMotion.addEventListener?.("change", scheduleAutoplay);

  carousel.addEventListener("touchstart", (event) => {
    const touch = event.changedTouches[0];
    if (touch && !event.target.closest("button")) {
      touchStart = { x: touch.clientX, y: touch.clientY };
    }
  }, { passive: true });
  carousel.addEventListener("touchend", (event) => {
    const touch = event.changedTouches[0];
    if (!touch || !touchStart) return;
    const deltaX = touch.clientX - touchStart.x;
    const deltaY = touch.clientY - touchStart.y;
    touchStart = null;
    if (Math.abs(deltaX) >= 48 && Math.abs(deltaX) > Math.abs(deltaY)) {
      showSlide(activeIndex + (deltaX < 0 ? 1 : -1));
    }
  }, { passive: true });

  showSlide(activeIndex, false);
})();
