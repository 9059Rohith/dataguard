"use strict";

globalThis.DataGuardArchive = (() => {
  const catalog = globalThis.DataGuardArchiveCatalog;
  const preference = matchMedia("(prefers-reduced-motion: reduce)");
  const easing = "cubic-bezier(.22, .68, .27, 1)";
  let observer;
  const animations = new Set();

  function stopMotion() {
    observer?.disconnect();
    observer = undefined;
    for (const animation of animations) animation.cancel();
    animations.clear();
  }

  function enter(element, { delay = 0, distance = 10, duration = 500 } = {}) {
    if (!element?.animate || preference.matches) return;
    const animation = element.animate(
      [
        { opacity: 0.86, transform: `translateY(${distance}px)` },
        { opacity: 1, transform: "translateY(0)" },
      ],
      { delay, duration, easing },
    );
    animations.add(animation);
    animation.onfinish = animation.oncancel = () =>
      animations.delete(animation);
  }

  function artwork(entry, className) {
    const frame = document.createElement("div");
    frame.className = className;
    frame.setAttribute("aria-hidden", "true");
    frame.dataset.archiveArt = entry.file;
    const image = document.createElement("img");
    image.alt = "";
    image.width = 640;
    image.height = 440;
    image.decoding = "async";
    image.loading = entry.placement === "hero" ? "eager" : "lazy";
    if (entry.placement === "hero") image.fetchPriority = "high";
    image.src = `/archive-art/${entry.file}`;
    frame.append(image);
    return frame;
  }

  function mount(main, page) {
    stopMotion();
    const heading = main.querySelector(".page-heading");
    const entries = catalog.filter((entry) => entry.route === page);
    const hero = entries.find((entry) => entry.placement === "hero");
    if (!heading || !hero) return;

    const copy = heading.firstElementChild;
    const actions = heading.querySelector(".heading-actions, .impact-stamp");
    heading.classList.add("archive-hero");
    copy.classList.add("archive-copy");
    actions?.classList.add("archive-actions");
    const plate = artwork(hero, "archive-plate");
    heading.append(plate);
    const landscape = entries.find((entry) => entry.placement === "landscape");
    if (landscape) heading.append(artwork(landscape, "archive-landscape"));

    for (const entry of entries) {
      if (!entry.placement.startsWith(".")) continue;
      const panel = main.querySelector(entry.placement);
      if (!panel) continue;
      panel.classList.add("archive-panel");
      panel.prepend(artwork(entry, "archive-panel-art"));
    }

    if (preference.matches) return;
    enter(copy.querySelector("h1"), { distance: 11, duration: 510 });
    enter(copy.querySelector("p"), { delay: 55, distance: 7, duration: 480 });
    enter(actions, { delay: 90, distance: 6, duration: 440 });
    enter(plate, { delay: 35, distance: 13, duration: 620 });
    if ("IntersectionObserver" in globalThis) {
      observer = new IntersectionObserver(
        (items, active) => {
          for (const item of items) {
            if (!item.isIntersecting) continue;
            enter(item.target, { distance: 12, duration: 560 });
            active.unobserve(item.target);
          }
        },
        { threshold: 0.08 },
      );
      const sections = [...main.children].filter((element) =>
        element.matches(
          "section, .panel, .split, .archive-panel, .register-layout, .check-summary, .connection-grid, .settings-layout, .capture-timeline, .impact-policies",
        ),
      );
      for (const section of sections) observer.observe(section);
    }
  }

  preference.addEventListener("change", (event) => {
    if (event.matches) stopMotion();
  });
  return { mount };
})();
