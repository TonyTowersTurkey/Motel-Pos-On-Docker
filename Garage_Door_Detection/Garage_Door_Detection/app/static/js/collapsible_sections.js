function storedSectionState(storageKey) {
  try {
    return window.localStorage.getItem(storageKey);
  } catch {
    return null;
  }
}

function storeSectionState(storageKey, collapsed) {
  try {
    window.localStorage.setItem(storageKey, collapsed ? "collapsed" : "expanded");
  } catch {
    // The controls still work when browser storage is unavailable.
  }
}

document.querySelectorAll("main .panel[data-collapsible-id]").forEach((panel) => {
  const heading = Array.from(panel.children).find((child) =>
    child.classList.contains("panel-heading")
  );
  const title = heading?.querySelector("h2");
  if (!heading || !title) {
    return;
  }

  const sectionId = panel.dataset.collapsibleId;
  const storageKey = `garage-door-section:${window.location.pathname}:${sectionId}`;
  const savedState = storedSectionState(storageKey);
  const startsCollapsed = savedState
    ? savedState === "collapsed"
    : panel.dataset.collapsed === "true";

  panel.classList.add("collapsible-panel");
  heading.classList.add("collapsible-panel-heading");

  const button = document.createElement("button");
  button.className = "icon-button section-collapse-toggle";
  button.type = "button";
  const chevron = document.createElement("span");
  chevron.className = "section-collapse-chevron";
  chevron.setAttribute("aria-hidden", "true");
  chevron.textContent = "▼";
  button.append(chevron);
  heading.append(button);

  function setCollapsed(collapsed, persist = true) {
    panel.classList.toggle("section-collapsed", collapsed);
    button.setAttribute("aria-expanded", String(!collapsed));
    button.setAttribute(
      "aria-label",
      `${collapsed ? "Expand" : "Collapse"} ${title.textContent.trim()}`
    );
    button.title = button.getAttribute("aria-label");
    if (persist) {
      storeSectionState(storageKey, collapsed);
    }
  }

  button.addEventListener("click", () => {
    setCollapsed(!panel.classList.contains("section-collapsed"));
  });

  setCollapsed(startsCollapsed, false);
});
