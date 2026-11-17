const SESSION_KEY = "sgo.authenticatedUser";
const USER_ID_KEY = "sgo.authenticatedUserId";

const searchInput = document.querySelector("#sector-search");
const sectorGrid = document.querySelector("#sector-grid");
const sectorCount = document.querySelector("#sector-count");
const profileMenuButton = document.querySelector("#profile-menu-button");
const profileMenu = document.querySelector("#profile-menu");
const logoutLink = document.querySelector("#logout-link");
let sectorCards = [];

function escapeHtml(value = "") {
  return String(value).replace(/[&<>"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[character]);
}

function normalizeText(value) {
  return String(value).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

function userInitials(name = "") {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "?";
}

function refreshIcons() {
  if (window.lucide) window.lucide.createIcons();
}

function clearLocalSession() {
  [SESSION_KEY, USER_ID_KEY, "sgo.authenticatedUserName", "sgo.authenticatedUserProfile"].forEach((key) => sessionStorage.removeItem(key));
}

async function api(path, options = {}) {
  const response = await fetch(path, { credentials: "same-origin", ...options });
  const result = await response.json().catch(() => ({}));
  if (response.status === 401) {
    clearLocalSession();
    window.location.replace("../index.html");
    throw new Error("Sessão expirada.");
  }
  if (!response.ok) throw new Error(result.error || "Não foi possível concluir a operação.");
  return result;
}

function applyUserProfile(user, permissions) {
  sessionStorage.setItem(SESSION_KEY, user.username);
  sessionStorage.setItem(USER_ID_KEY, String(user.id));
  sessionStorage.setItem("sgo.authenticatedUserName", user.name);
  sessionStorage.setItem("sgo.authenticatedUserProfile", user.profile);
  document.querySelector(".user-copy strong").textContent = user.name;
  document.querySelector(".user-copy small").textContent = user.profile;
  document.querySelector(".dropdown-name strong").textContent = user.name;
  document.querySelector(".dropdown-name small").textContent = user.profile;
  document.querySelector("#welcome-title").textContent = `Olá, ${user.name.split(" ")[0]}`;
  const administrationLink = profileMenu.querySelector('a[href="../administradores/"]');
  if (administrationLink) administrationLink.hidden = !permissions.includes("administration.access");
  document.querySelectorAll(".avatar, .dropdown-avatar").forEach((avatar) => {
    avatar.innerHTML = user.avatar
      ? `<img class="uploaded-avatar-photo" src="${escapeHtml(user.avatar)}" alt="" />`
      : userInitials(user.name);
  });
}

function iconContent(icon, enabled) {
  if (!enabled) return '<i data-lucide="lock" aria-hidden="true"></i>';
  if (String(icon).startsWith("data:image/")) return `<img class="sector-custom-icon" src="${escapeHtml(icon)}" alt="" />`;
  return `<i data-lucide="${escapeHtml(icon || "building-2")}" aria-hidden="true"></i>`;
}

function renderSectors(sectors) {
  const cards = sectors.filter((sector) => sector.status === "Ativo").map((sector) => {
    const enabled = Boolean(sector.enabled);
    const href = enabled ? `../setores/?setor=${encodeURIComponent(sector.slug)}` : "#";
    return `<a class="sector-card${enabled ? "" : " is-locked"}" href="${href}"
      data-sector="${escapeHtml(`${sector.name} ${sector.description}`)}" aria-disabled="${!enabled}">
      <div class="card-body">
        <span class="icon-wrapper">${iconContent(sector.icon, enabled)}</span>
        <span class="card-copy"><strong>${escapeHtml(sector.name)}</strong><small>${escapeHtml(sector.description)}</small></span>
        <span class="access-badge"><i></i>${enabled ? "Liberado" : "Acesso não liberado"}</span>
      </div>
      <span class="card-footer"><strong>${enabled ? "Acessar setor" : "Acesso bloqueado"}</strong><i data-lucide="arrow-right" aria-hidden="true"></i></span>
    </a>`;
  }).join("");
  sectorGrid.innerHTML = `${cards}<p class="empty-state" id="empty-state" hidden>Nenhum setor encontrado.</p>`;
  sectorCards = [...sectorGrid.querySelectorAll(".sector-card")];
  sectorCards.filter((card) => card.classList.contains("is-locked")).forEach((card) => {
    card.addEventListener("click", (event) => event.preventDefault());
  });
  refreshIcons();
  updateSectorCount();
}

function updateSectorCount() {
  const visibleCards = sectorCards.filter((card) => !card.hidden);
  const available = visibleCards.filter((card) => !card.classList.contains("is-locked")).length;
  document.querySelector("#empty-state").hidden = visibleCards.length !== 0;
  sectorCount.textContent = `${available} ${available === 1 ? "setor disponível" : "setores disponíveis"}`;
}

async function initialize() {
  try {
    const { user, permissions } = await api("../api/auth/me");
    applyUserProfile(user, permissions);
    const { access } = await api(`../api/users/${user.id}/access`);
    renderSectors(access.sectors);
  } catch (error) {
    sectorCount.textContent = "Acessos indisponíveis";
  }
}

searchInput.addEventListener("input", () => {
  const term = normalizeText(searchInput.value.trim());
  sectorCards.forEach((card) => { card.hidden = !normalizeText(card.dataset.sector).includes(term); });
  updateSectorCount();
});

function setProfileMenu(open) {
  profileMenu.hidden = !open;
  profileMenuButton.setAttribute("aria-expanded", String(open));
}

profileMenuButton.addEventListener("click", () => setProfileMenu(profileMenuButton.getAttribute("aria-expanded") !== "true"));
document.addEventListener("click", (event) => { if (!event.target.closest(".profile-menu-container")) setProfileMenu(false); });
document.addEventListener("keydown", (event) => { if (event.key === "Escape" && !profileMenu.hidden) { setProfileMenu(false); profileMenuButton.focus(); } });

logoutLink.addEventListener("click", async (event) => {
  event.preventDefault();
  try { await fetch("../api/auth/logout", { method: "POST", credentials: "same-origin" }); } finally {
    clearLocalSession();
    window.location.replace("../index.html");
  }
});

async function checkSessionStatus() {
  try {
    const { session } = await api("../api/session/status");
    if (!session.exists || !session.active || session.maintenance) {
      clearLocalSession();
      window.location.replace(`../index.html${session.maintenance ? "?maintenance=1" : ""}`);
    }
  } catch { /* O helper trata sessões inválidas. */ }
}

window.addEventListener("pageshow", (event) => { if (event.persisted) initialize(); });
initialize();
window.setInterval(checkSessionStatus, 15000);
