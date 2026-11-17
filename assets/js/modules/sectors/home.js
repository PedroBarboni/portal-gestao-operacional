import { api, clearLocalSession } from "../../core/api.js";
import { escapeHtml, initials } from "../../core/html.js";

const params = new URLSearchParams(window.location.search);
const requestedSlug = params.get("setor");
const moduleGrid = document.querySelector("#module-grid");
const pageTitle = document.querySelector("#sector-title");
const pageDescription = document.querySelector("#sector-description");
const breadcrumb = document.querySelector("#sector-breadcrumb");

function iconContent(icon) {
  if (String(icon).startsWith("data:image/")) return `<img class="sector-custom-icon" src="${escapeHtml(icon)}" alt="" />`;
  return `<i data-lucide="${escapeHtml(icon || "panel-top")}" aria-hidden="true"></i>`;
}

function applyUser(user) {
  document.querySelector(".user-copy strong").textContent = user.name;
  document.querySelector(".user-copy small").textContent = user.profile;
  document.querySelector(".avatar").innerHTML = user.avatar
    ? `<img class="uploaded-avatar-photo" src="${escapeHtml(user.avatar)}" alt="" />`
    : initials(user.name);
}

function renderModules(modules) {
  if (!modules.length) {
    moduleGrid.innerHTML = '<p class="module-empty">Nenhuma tela foi liberada para você neste setor.</p>';
    return;
  }
  moduleGrid.innerHTML = modules.map((module) => `
    <article class="module-card${module.implemented ? "" : " is-unavailable"}">
      <span class="module-icon">${iconContent(module.icon)}</span>
      <div><h2>${escapeHtml(module.name)}</h2><p>${escapeHtml(module.description || module.category || "Tela do setor")}</p></div>
      <span class="module-status">${module.implemented ? "Acessar" : "Em desenvolvimento"}</span>
    </article>`).join("");
  if (window.lucide) window.lucide.createIcons();
}

async function initialize() {
  if (!requestedSlug) {
    window.location.replace("../home/");
    return;
  }
  try {
    const { user } = await api("../api/auth/me");
    applyUser(user);
    const { access } = await api(`../api/users/${user.id}/access`);
    const sector = access.sectors.find((item) => item.slug === requestedSlug && item.status === "Ativo");
    if (!sector || !sector.enabled) {
      window.location.replace("../home/?access=denied");
      return;
    }
    pageTitle.textContent = sector.name;
    pageDescription.textContent = sector.description;
    breadcrumb.textContent = sector.name;
    document.title = `${sector.name} | PGO`;
    renderModules(access.modules.filter((module) => module.sector_id === sector.id && module.enabled && module.status === "Ativo"));
  } catch (error) {
    moduleGrid.innerHTML = `<p class="module-empty">${escapeHtml(error.message)}</p>`;
  }
}

document.querySelector("#logout-button").addEventListener("click", async () => {
  try { await fetch("../api/auth/logout", { method: "POST", credentials: "same-origin" }); } finally {
    clearLocalSession();
    window.location.replace("../index.html");
  }
});

initialize();

