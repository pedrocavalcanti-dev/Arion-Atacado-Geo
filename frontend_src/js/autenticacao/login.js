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
  let requestedIndex = activeIndex;
  let transitionRequest = 0;
  let timer = 0;
  let hovered = false;
  let focused = false;
  let interacting = false;
  let touchStart = null;
  const imageLoads = new WeakMap();

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
    if (!image) return Promise.resolve(true);
    const target = image.dataset.imageSrc;
    const fallback = image.dataset.fallbackSrc;
    if (!target || target === fallback || image.dataset.imageReady === "true") return Promise.resolve(true);
    if (imageLoads.has(image)) return imageLoads.get(image);

    const preload = new Image();
    const imageLoad = new Promise((resolve) => {
      preload.onload = () => {
        image.src = target;
        image.classList.remove("is-fallback");
        const decoded = typeof image.decode === "function" ? image.decode() : Promise.resolve();
        decoded.then(() => {
          image.dataset.imageReady = "true";
          resolve(true);
        }).catch(() => {
          image.src = fallback || image.src;
          image.classList.add("is-fallback");
          resolve(false);
        });
      };
      preload.onerror = () => {
        image.src = fallback || image.src;
        image.classList.add("is-fallback");
        resolve(false);
      };
    });
    imageLoads.set(image, imageLoad);
    preload.src = target;
    return imageLoad;
  }

  async function showSlide(nextIndex, announce = true) {
    requestedIndex = (nextIndex + slides.length) % slides.length;
    const request = ++transitionRequest;
    clearTimer();
    const imageReady = await prepareImage(slides[requestedIndex]);
    if (request !== transitionRequest) return;
    if (!imageReady) {
      requestedIndex = activeIndex;
      scheduleAutoplay();
      return;
    }

    activeIndex = requestedIndex;
    slides.forEach((slide, index) => {
      const active = index === activeIndex;
      slide.classList.toggle("is-active", active);
      slide.setAttribute("aria-hidden", String(!active));
      slide.setAttribute("aria-label", `${index + 1} de ${slides.length}: ${slide.dataset.slideLabel || "ARION OPS"}`);
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

  previous.addEventListener("click", () => showSlide(requestedIndex - 1));
  next.addEventListener("click", () => showSlide(requestedIndex + 1));
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
      showSlide(requestedIndex + (deltaX < 0 ? 1 : -1));
    }
  }, { passive: true });

  showSlide(activeIndex, false);
})();
