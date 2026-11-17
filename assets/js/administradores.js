const SESSION_KEY = "sgo.authenticatedUser";
const USER_ID_KEY = "sgo.authenticatedUserId";
const state = { users: [], selectedUserId: Number(sessionStorage.getItem(USER_ID_KEY)) || 0, selectedUser: null, access: null, sectors: [], selectedSectorId: 0, selectedSector: null, initialModules: [] };
const permissionIcons = { "Visualizar": "eye", "Criar / Incluir": "file-plus-2", "Editar": "pencil", "Excluir": "trash-2", "Aprovar / Finalizar": "badge-check", "Imprimir": "printer", "Exportar": "download", "Anexar Arquivos": "paperclip", "Comentários": "message-square" };
const screenLabels = { users: "Usuários", "new-user": "Usuários / Novo usuário", "edit-user": "Usuários / Editar usuário", "user-details": "Usuários / Detalhes do usuário", "access-overview": "Acessos e Permissões / Visão Geral", sectors: "Acessos e Permissões", modules: "Acessos e Permissões", permissions: "Acessos e Permissões", "sector-list": "Setores", "new-sector": "Setores / Novo setor", "edit-sector": "Setores / Editar setor", "sector-modules": "Setores / Telas do setor" };
const userScreens = new Set(["users", "new-user", "edit-user", "user-details"]);
const accessScreens = new Set(["access-overview", "sectors", "modules", "permissions"]);
const sectorScreens = new Set(["sector-list", "new-sector", "edit-sector", "sector-modules"]);

function escapeHtml(value = "") { return String(value).replace(/[&<>"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[character]); }
function initials(name = "") { return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "?"; }
function userAvatarContent(user) { return user.avatar ? `<img class="uploaded-avatar-photo" src="${escapeHtml(user.avatar)}" alt="" />` : initials(user.name); }
function sectorIconContent(icon) { return String(icon).startsWith("data:image/") ? `<img class="sector-custom-icon" src="${escapeHtml(icon)}" alt="" />` : `<i data-lucide="${escapeHtml(icon || "building-2")}"></i>`; }
function displayDate(value) { if (!value) return "Nunca"; const date = new Date(value.replace(" ", "T")); return Number.isNaN(date.getTime()) ? value : date.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }); }
function refreshIcons() { if (window.lucide) window.lucide.createIcons(); }
function applyHeaderProfile(user) {
  if (!user) return;
  sessionStorage.setItem("sgo.authenticatedUserName", user.name);
  sessionStorage.setItem("sgo.authenticatedUserProfile", user.profile);
  document.querySelector(".profile-copy strong").textContent = user.name;
  document.querySelector(".profile-copy small").textContent = user.profile;
  const avatar = document.querySelector(".profile-avatar");
  avatar.innerHTML = user.avatar
    ? `<img class="uploaded-avatar-photo" src="${escapeHtml(user.avatar)}" alt="" />`
    : initials(user.name);
}
function selectedUser() { return state.users.find((user) => user.id === state.selectedUserId); }
function maintenanceRequiredMessage(user = selectedUser()) { return `Ative a manutenção de ${user?.name || "este usuário"} antes de realizar alterações.`; }
function canModifySelectedUser() { return Boolean(selectedUser()?.maintenance); }
function requireSelectedUserMaintenance() {
  if (canModifySelectedUser()) return true;
  showToast(maintenanceRequiredMessage(), true);
  return false;
}

async function api(path, options = {}) {
  const response = await fetch(path, { credentials: "same-origin", ...options, headers: { "Content-Type": "application/json", ...(options.headers || {}) } });
  const result = await response.json().catch(() => ({}));
  if (response.status === 401) {
    sessionStorage.clear();
    window.location.replace("../index.html");
    throw new Error("Sessão expirada.");
  }
  if (response.status === 403) {
    window.location.replace("../home/?access=denied");
    throw new Error(result.error || "Acesso não autorizado.");
  }
  if (!response.ok) throw new Error(result.error || "Não foi possível concluir a operação.");
  return result;
}

function showToast(message, error = false) {
  const toast = document.querySelector("#toast");
  toast.lastChild.textContent = message;
  toast.style.background = error ? "#c92f40" : "#118557";
  toast.hidden = false;
  window.setTimeout(() => { toast.hidden = true; }, 2800);
}

async function showScreen(name) {
  document.querySelectorAll(".screen").forEach((screen) => screen.classList.toggle("is-active", screen.dataset.screen === name));
  document.querySelectorAll(".nav-item").forEach((item) => {
    const activeMenu = userScreens.has(name) ? "users" : (accessScreens.has(name) ? "access-overview" : (sectorScreens.has(name) ? "sector-list" : name));
    item.classList.toggle("is-active", item.dataset.menuScreen === activeMenu);
  });
  document.querySelector("#breadcrumb-current").textContent = screenLabels[name];
  history.replaceState(null, "", `#${name}`);
  window.scrollTo({ top: 0, behavior: "smooth" });
  if (name === "edit-user") await populateEditForm();
  if (name === "user-details") await renderDetails();
  if (name === "access-overview") await loadOverview();
  if (accessScreens.has(name) && name !== "access-overview") await loadAccess();
  if (name === "sector-list") await loadSectors();
  if (name === "new-sector") prepareNewSectorForm();
  if (name === "edit-sector") await loadSectorEditForm();
  if (name === "sector-modules") await loadSectorModules();
}

function renderUsers() {
  const term = document.querySelector("#user-search").value.trim().toLocaleLowerCase("pt-BR");
  const profile = document.querySelector("#profile-filter").value;
  const status = document.querySelector("#status-filter").value;
  const users = state.users.filter((user) => `${user.name} ${user.email}`.toLocaleLowerCase("pt-BR").includes(term) && (!profile || user.profile === profile) && (!status || user.status === status));
  document.querySelector("#user-rows").innerHTML = users.length ? users.map((user) => `
    <div class="user-table table-row" data-user-id="${user.id}"><span class="user-cell"><b>${initials(user.name)}</b><span><button class="user-name-button" type="button" data-action="details" data-id="${user.id}">${escapeHtml(user.name)}</button><small>${escapeHtml(user.email)}</small></span></span><span>${escapeHtml(user.sector)}</span><span><em class="badge ${user.profile === "Supervisor" ? "purple" : "blue"}">${escapeHtml(user.profile)}</em></span><span><em class="badge ${user.maintenance ? "amber" : (user.status === "Ativo" ? "green" : "red")}">${user.maintenance ? "Em manutenção" : escapeHtml(user.status)}</em></span><span>${displayDate(user.last_access)}</span><span class="row-actions"><button data-action="edit" data-id="${user.id}" ${user.maintenance ? "" : "disabled"} title="${user.maintenance ? "Editar usuário" : "Ative a manutenção para editar"}" aria-label="Editar ${escapeHtml(user.name)}"><i data-lucide="pencil"></i></button><span class="user-row-menu"><button class="user-action-trigger" type="button" aria-label="Ações de ${escapeHtml(user.name)}" aria-expanded="false"><i data-lucide="ellipsis-vertical"></i></button><span class="user-action-popover" hidden><button type="button" data-action="details" data-id="${user.id}"><i data-lucide="eye"></i>Ver detalhes</button><button type="button" data-action="edit" data-id="${user.id}" ${user.maintenance ? "" : "disabled"} title="${user.maintenance ? "" : "Ative a manutenção para editar"}"><i data-lucide="pencil"></i>Editar usuário</button><button class="${user.maintenance ? "release-action" : "maintenance-action"}" type="button" data-maintenance-user="${user.id}" data-maintenance-enabled="${user.maintenance ? "false" : "true"}"><i data-lucide="${user.maintenance ? "play" : "wrench"}"></i>${user.maintenance ? "Liberar usuário" : "Ativar manutenção"}</button></span></span></span></div>`).join("") : '<p class="database-empty">Nenhum usuário encontrado.</p>';
  document.querySelectorAll("#user-rows .table-row").forEach((row) => {
    const user = users.find((item) => item.id === Number(row.dataset.userId));
    if (user) row.querySelector(".user-cell > b").innerHTML = userAvatarContent(user);
  });
  document.querySelector(".table-footer > span").textContent = `Mostrando ${users.length} de ${state.users.length} usuários`;
  refreshIcons();
}

async function loadUsers() {
  const result = await api("../api/users");
  state.users = result.users;
  if (!state.users.some((user) => user.id === state.selectedUserId)) state.selectedUserId = state.users[0]?.id || 0;
  renderUsers();
  populateUserSelects();
  populateSectorResponsibleSelects();
}

function populateUserSelects() {
  document.querySelectorAll(".access-toolbar > label:first-child select").forEach((select) => {
    select.innerHTML = state.users.map((user) => `<option value="${user.id}" ${user.id === state.selectedUserId ? "selected" : ""}>${escapeHtml(user.name)}</option>`).join("");
  });
}

function populateSectorResponsibleSelects() {
  document.querySelectorAll(".sector-responsible-select").forEach((select) => {
    const current = select.value;
    select.innerHTML = '<option value="">Selecione o responsável</option>' + state.users.map((user) => `<option value="${escapeHtml(user.name)}">${escapeHtml(user.name)}</option>`).join("");
    select.value = current;
  });
}

async function populateEditForm() {
  if (!state.selectedUserId) return;
  const { user } = await api(`../api/users/${state.selectedUserId}`);
  if (!user.maintenance) {
    showToast(maintenanceRequiredMessage(user), true);
    await showScreen("user-details");
    return;
  }
  const form = document.querySelector("#edit-user-form");
  ["name", "email", "cpf", "phone", "profile", "sector", "status"].forEach((field) => { if (form.elements[field]) form.elements[field].value = user[field] || ""; });
}

function userDetailsHtml(user) {
  const sectors = user.sectors || [], accesses = user.access_logs || [], audits = user.audit_logs || [];
  return `<div class="details-top-grid"><section class="detail-card"><h2><i data-lucide="user-round"></i>Dados do usuário</h2><div class="detail-person"><span class="detail-avatar">${initials(user.name)}</span><span><strong>${escapeHtml(user.name)}</strong><em><i></i>${escapeHtml(user.status)}</em><small><i data-lucide="mail"></i>${escapeHtml(user.email)}</small><small><i data-lucide="phone"></i>${escapeHtml(user.phone || "Não informado")}</small></span></div><dl><div><dt>Perfil</dt><dd>${escapeHtml(user.profile)}</dd></div><div><dt>Setor principal</dt><dd>${escapeHtml(user.sector)}</dd></div><div><dt>Data de cadastro</dt><dd>${displayDate(user.created_at)}</dd></div><div><dt>Último acesso</dt><dd>${displayDate(user.last_access)}</dd></div><div><dt>Status do acesso</dt><dd><em class="detail-status"><i></i>${escapeHtml(user.status)}</em></dd></div></dl></section><section class="detail-card"><h2><i data-lucide="folder"></i>Setores liberados</h2><ul class="released-list">${sectors.length ? sectors.map((sector) => `<li><span><i data-lucide="folder"></i>${escapeHtml(sector.name)}</span><b><i data-lucide="check"></i></b></li>`).join("") : "<li>Nenhum setor liberado.</li>"}</ul></section><section class="detail-card"><h2><i data-lucide="monitor"></i>Resumo de acesso</h2><ul class="released-list screen-counts"><li><span>Setores liberados</span><b>${sectors.length}</b></li><li><span>Acessos registrados</span><b>${accesses.length}</b></li><li><span>Alterações recentes</span><b>${audits.length}</b></li></ul></section></div><div class="details-bottom-grid"><section class="detail-card activity-card"><h2><i data-lucide="clock-3"></i>Últimos acessos</h2>${accesses.length ? accesses.map((log) => `<div class="activity-row"><time>${displayDate(log.accessed_at)}</time><span>${escapeHtml(log.ip_address)}</span><em>${log.success ? "Sucesso" : "Falha"}</em></div>`).join("") : '<p class="database-empty">Nenhum acesso registrado.</p>'}</section><section class="detail-card activity-card changes-card"><h2><i data-lucide="history"></i>Alterações recentes</h2>${audits.length ? audits.map((log) => `<div class="activity-row"><time>${displayDate(log.created_at)}</time><span>${escapeHtml(log.action)}</span><strong>${escapeHtml(log.actor)}</strong></div>`).join("") : '<p class="database-empty">Nenhuma alteração registrada.</p>'}</section></div>`;
}

async function renderDetails() {
  if (!state.selectedUserId) return;
  const { user } = await api(`../api/users/${state.selectedUserId}`);
  state.selectedUser = user;
  document.querySelector("#user-details-content").innerHTML = userDetailsHtml(user);
  document.querySelector("#user-details-content .detail-avatar").innerHTML = userAvatarContent(user);
  const deleteButton = document.querySelector("#delete-user-button");
  deleteButton.hidden = user.username === "admin";
  deleteButton.disabled = !user.maintenance;
  deleteButton.title = user.maintenance ? "Excluir usuário" : "Ative a manutenção para excluir";
  const editButton = document.querySelector("#edit-user-button");
  editButton.disabled = !user.maintenance;
  editButton.title = user.maintenance ? "Editar usuário" : "Ative a manutenção para editar";
  const maintenanceButton = document.querySelector("#maintenance-user-button");
  maintenanceButton.dataset.maintenanceUser = user.id;
  maintenanceButton.dataset.maintenanceEnabled = String(!user.maintenance);
  maintenanceButton.classList.toggle("is-active", Boolean(user.maintenance));
  maintenanceButton.innerHTML = `<i data-lucide="${user.maintenance ? "play" : "wrench"}"></i><span>${user.maintenance ? "Liberar usuário" : "Ativar manutenção"}</span>`;
  document.querySelector("#delete-user-name").textContent = user.name;
  refreshIcons();
}

async function loadOverview() {
  const { overview } = await api("../api/access/overview");
  [overview.users, overview.profiles, overview.sectors, overview.modules].forEach((value, index) => { document.querySelectorAll(".access-stats strong")[index].textContent = value; });
  const panel = document.querySelector(".access-summary"), footer = panel.querySelector("footer");
  panel.querySelectorAll(".summary-table:not(.summary-head)").forEach((row) => row.remove());
  overview.profile_summary.forEach((item) => {
    const row = document.createElement("div");
    row.className = "summary-table";
    row.innerHTML = `<strong>${escapeHtml(item.profile)}</strong><span>— <i><b style="width:0"></b></i></span><span>— <i><b style="width:0"></b></i></span><em>${item.users} usuário(s)</em><button type="button" aria-label="Mais informações sobre ${escapeHtml(item.profile)}"><i data-lucide="ellipsis-vertical"></i></button>`;
    panel.insertBefore(row, footer);
  });
  footer.firstChild.textContent = `Mostrando ${overview.profile_summary.length} perfis `;
  refreshIcons();
}

function renderAccess() {
  if (!state.access) return;
  const locked = !canModifySelectedUser();
  document.querySelector("#sector-list").innerHTML = state.access.sectors.map((sector) => `<label class="sector-row"><input type="checkbox" data-id="${sector.id}" ${sector.enabled ? "checked" : ""} ${locked ? "disabled" : ""}/>${sectorIconContent(sector.icon)}<span>${escapeHtml(sector.name)}</span><em class="${sector.enabled ? "" : "inactive"}">${sector.enabled ? "Ativo" : "Inativo"}</em></label>`).join("");
  document.querySelector("#module-list").innerHTML = state.access.modules.map((module) => `<div class="module-row"><span class="module-info"><i><i data-lucide="${module.icon}"></i></i><span><strong>${escapeHtml(module.name)}</strong></span></span><label class="switch"><input type="checkbox" data-id="${module.id}" ${module.enabled ? "checked" : ""} ${locked ? "disabled" : ""}/><span></span></label></div>`).join("");
  document.querySelector("#permission-grid").innerHTML = state.access.permissions.map((permission) => `<label class="permission-card ${permission.allowed ? "" : "is-denied"}"><i><i data-lucide="${permissionIcons[permission.action] || "shield"}"></i></i><span><strong>${escapeHtml(permission.action)}</strong></span><select data-action="${escapeHtml(permission.action)}" ${locked ? "disabled" : ""}><option value="1" ${permission.allowed ? "selected" : ""}>Permitido</option><option value="0" ${permission.allowed ? "" : "selected"}>Negado</option></select></label>`).join("");
  document.querySelectorAll(".access-screen:not([data-screen='access-overview']) .access-work-panel").forEach((panel) => {
    let notice = panel.querySelector(".maintenance-lock-notice");
    if (!notice) { notice = document.createElement("div"); notice.className = "maintenance-lock-notice"; panel.prepend(notice); }
    notice.hidden = !locked;
    notice.innerHTML = `<i data-lucide="lock-keyhole"></i><span><strong>Alterações bloqueadas</strong>Ative a manutenção de ${escapeHtml(selectedUser()?.name || "este usuário")} para modificar acessos e permissões.</span>`;
  });
  document.querySelector("#save-permissions").disabled = locked;
  refreshIcons();
}

let accessRequestSequence = 0;
function setAccessLoading(loading) {
  document.querySelectorAll(".access-work-panel").forEach((panel) => {
    panel.classList.toggle("is-loading", loading);
    panel.setAttribute("aria-busy", String(loading));
  });
  document.querySelectorAll(".access-toolbar > label:first-child select").forEach((select) => { select.disabled = loading; });
}

async function loadAccess(announce = false) {
  if (!state.selectedUserId) return;
  const requestedUserId = state.selectedUserId;
  const requestSequence = ++accessRequestSequence;
  setAccessLoading(true);
  try {
    const { access } = await api(`../api/users/${requestedUserId}/access`);
    if (requestSequence !== accessRequestSequence || requestedUserId !== state.selectedUserId) return;
    state.access = access;
    populateUserSelects();
    renderAccess();
    if (announce) {
      const user = state.users.find((item) => item.id === requestedUserId);
      showToast(`Permissões de ${user?.name || "usuário"} carregadas.`);
    }
  } finally {
    if (requestSequence === accessRequestSequence) setAccessLoading(false);
  }
}
async function saveSectors() { if (!requireSelectedUserMaintenance()) return false; const ids = [...document.querySelectorAll("#sector-list input:checked")].map((input) => Number(input.dataset.id)); await api(`../api/users/${state.selectedUserId}/access`, { method: "PUT", body: JSON.stringify({ sector_ids: ids }) }); return true; }
async function saveModules() { if (!requireSelectedUserMaintenance()) return false; const ids = [...document.querySelectorAll("#module-list input:checked")].map((input) => Number(input.dataset.id)); await api(`../api/users/${state.selectedUserId}/access`, { method: "PUT", body: JSON.stringify({ module_ids: ids }) }); return true; }
async function savePermissions() { if (!requireSelectedUserMaintenance()) return; const permissions = Object.fromEntries([...document.querySelectorAll("#permission-grid select")].map((select) => [select.dataset.action, select.value === "1"])); await api(`../api/users/${state.selectedUserId}/access`, { method: "PUT", body: JSON.stringify({ module_id: state.access.module_id, permissions }) }); showToast("Permissões salvas com sucesso."); }

function renderSectorRows() {
  const term = document.querySelector("#sector-search").value.trim().toLocaleLowerCase("pt-BR");
  const status = document.querySelector("#sector-status-filter").value;
  const category = document.querySelector("#sector-category-filter").value;
  const sectors = state.sectors.filter((sector) => `${sector.name} ${sector.description}`.toLocaleLowerCase("pt-BR").includes(term) && (!status || sector.status === status) && (!category || sector.category === category));
  document.querySelector("#sector-rows").innerHTML = sectors.length ? sectors.map((sector) => `<div class="sector-admin-table sector-table-row" data-sector-id="${sector.id}"><span><i><i data-lucide="${escapeHtml(sector.icon)}"></i></i>${escapeHtml(sector.name)}</span><span class="sector-description" title="${escapeHtml(sector.description)}">${escapeHtml(sector.description)}</span><span><em class="sector-status ${sector.status === "Ativo" ? "" : "inactive"}">${escapeHtml(sector.status)}</em></span><span>${sector.module_count}</span><span class="sector-action"><button class="sector-action-trigger" type="button" aria-label="Ações de ${escapeHtml(sector.name)}" aria-expanded="false"><i data-lucide="ellipsis-vertical"></i></button><span class="sector-action-menu" hidden><button type="button" data-sector-action="modules" data-sector-id="${sector.id}"><i data-lucide="panels-top-left"></i>Gerenciar telas</button><button type="button" data-sector-action="edit" data-sector-id="${sector.id}"><i data-lucide="pencil"></i>Editar setor</button><button class="delete-sector-action" type="button" data-sector-action="delete" data-sector-id="${sector.id}"><i data-lucide="trash-2"></i>Excluir setor</button></span></span></div>`).join("") : '<p class="database-empty">Nenhum setor encontrado.</p>';
  document.querySelectorAll("#sector-rows .sector-table-row").forEach((row) => {
    const sector = sectors.find((item) => item.id === Number(row.dataset.sectorId));
    if (sector) row.querySelector("span:first-child > i").innerHTML = sectorIconContent(sector.icon);
  });
  document.querySelector("#sector-table-count").textContent = `Mostrando ${sectors.length} de ${state.sectors.length} setores`;
  refreshIcons();
}

async function loadSectors() {
  const { sectors } = await api("../api/sectors");
  state.sectors = sectors;
  if (!state.sectors.some((sector) => sector.id === state.selectedSectorId)) state.selectedSectorId = state.sectors[0]?.id || 0;
  renderSectorRows();
}

function renderInitialModules() {
  document.querySelector("#initial-module-list").innerHTML = state.initialModules.length
    ? state.initialModules.map((name, index) => `<li><span><i data-lucide="grip-vertical"></i>${escapeHtml(name)}</span><button type="button" data-remove-initial-module="${index}" aria-label="Remover ${escapeHtml(name)}"><i data-lucide="trash-2"></i></button></li>`).join("")
    : '<li class="empty-initial-modules">Nenhuma tela adicionada.</li>';
  refreshIcons();
}

function prepareNewSectorForm() {
  const form = document.querySelector("#new-sector-form");
  if (!form.dataset.prepared) {
    form.reset();
    delete form.dataset.icon;
    document.querySelector("#new-sector-icon-preview").innerHTML = '<i data-lucide="image"></i>';
    state.initialModules = [];
    renderInitialModules();
    form.dataset.prepared = "true";
  }
  populateSectorResponsibleSelects();
}

function sectorFormData(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  delete data.iconFile;
  if (form.dataset.icon) data.icon = form.dataset.icon;
  return data;
}

async function loadSectorEditForm() {
  if (!state.selectedSectorId) return void await showScreen("sector-list");
  const { sector } = await api(`../api/sectors/${state.selectedSectorId}`);
  state.selectedSector = sector;
  const form = document.querySelector("#edit-sector-form");
  populateSectorResponsibleSelects();
  ["name", "description", "category", "status", "responsible"].forEach((field) => { if (form.elements[field]) form.elements[field].value = sector[field] || ""; });
  form.dataset.icon = sector.icon;
  document.querySelector("#edit-sector-icon-preview").innerHTML = sectorIconContent(sector.icon);
  refreshIcons();
}

function renderSectorModules() {
  const sector = state.selectedSector;
  document.querySelector("#sector-modules-title").textContent = `Telas do setor: ${sector.name}`;
  const modules = sector.modules || [];
  document.querySelector("#sector-module-rows").innerHTML = modules.length ? modules.map((module, index) => `<div class="sector-module-table module-sector-row" data-module-id="${module.id}"><span><i data-lucide="grip-vertical"></i></span><span><i><i data-lucide="${escapeHtml(module.icon)}"></i></i>${escapeHtml(module.name)}</span><span>${escapeHtml(module.category)}</span><span class="module-order"><button type="button" data-move-module="up" ${index === 0 ? "disabled" : ""} aria-label="Mover para cima"><i data-lucide="chevron-up"></i></button><button type="button" data-move-module="down" ${index === modules.length - 1 ? "disabled" : ""} aria-label="Mover para baixo"><i data-lucide="chevron-down"></i></button></span><span><em class="sector-status ${module.status === "Ativo" ? "" : "inactive"}">${escapeHtml(module.status)}</em></span><span class="module-permission-switch"><label class="switch"><input type="checkbox" data-module-permission ${module.permission_enabled ? "checked" : ""}/><span></span></label><small>${module.permission_enabled ? "Disponível" : "Bloqueado"}</small></span><span><button class="module-delete" type="button" data-delete-module aria-label="Excluir ${escapeHtml(module.name)}"><i data-lucide="trash-2"></i></button></span></div>`).join("") : '<p class="database-empty">Nenhuma tela cadastrada neste setor.</p>';
  refreshIcons();
}

async function loadSectorModules() {
  if (!state.selectedSectorId) return void await showScreen("sector-list");
  const { sector } = await api(`../api/sectors/${state.selectedSectorId}`);
  state.selectedSector = sector;
  renderSectorModules();
}

async function moveModule(moduleId, direction) {
  const modules = state.selectedSector.modules;
  const index = modules.findIndex((module) => module.id === moduleId);
  const otherIndex = direction === "up" ? index - 1 : index + 1;
  if (index < 0 || otherIndex < 0 || otherIndex >= modules.length) return;
  const first = modules[index], second = modules[otherIndex];
  await Promise.all([
    api(`../api/modules/${first.id}`, { method: "PUT", body: JSON.stringify({ display_order: second.display_order }) }),
    api(`../api/modules/${second.id}`, { method: "PUT", body: JSON.stringify({ display_order: first.display_order }) }),
  ]);
  await loadSectorModules();
}

document.addEventListener("click", async (event) => {
  try {
    const menu = event.target.closest("[data-menu-screen]"), action = event.target.closest("[data-action]"), go = event.target.closest("[data-go]");
    const userTrigger = event.target.closest(".user-action-trigger");
    const maintenanceAction = event.target.closest("[data-maintenance-user]");
    const sectorTrigger = event.target.closest(".sector-action-trigger");
    const sectorAction = event.target.closest("[data-sector-action]");
    const removeInitialModule = event.target.closest("[data-remove-initial-module]");
    const moduleRow = event.target.closest(".module-sector-row");
    if (sectorTrigger) {
      const popover = sectorTrigger.nextElementSibling;
      const willOpen = popover.hidden;
      document.querySelectorAll(".sector-action-menu").forEach((item) => { item.hidden = true; });
      document.querySelectorAll(".sector-action-trigger").forEach((item) => item.setAttribute("aria-expanded", "false"));
      popover.hidden = !willOpen;
      sectorTrigger.setAttribute("aria-expanded", String(willOpen));
      return;
    }
    if (sectorAction) {
      const sectorId = Number(sectorAction.dataset.sectorId);
      const sector = state.sectors.find((item) => item.id === sectorId);
      if (sectorAction.dataset.sectorAction === "delete") {
        if (!window.confirm(`Excluir o setor ${sector?.name || "selecionado"} e todas as telas vinculadas?`)) return;
        await api(`../api/sectors/${sectorId}`, { method: "DELETE" });
        await loadSectors();
        showToast("Setor excluído com sucesso.");
        return;
      }
      state.selectedSectorId = sectorId;
      return void await showScreen(sectorAction.dataset.sectorAction === "edit" ? "edit-sector" : "sector-modules");
    }
    if (removeInitialModule) {
      state.initialModules.splice(Number(removeInitialModule.dataset.removeInitialModule), 1);
      renderInitialModules();
      return;
    }
    if (moduleRow && event.target.closest("[data-move-module]")) {
      await moveModule(Number(moduleRow.dataset.moduleId), event.target.closest("[data-move-module]").dataset.moveModule);
      return;
    }
    if (moduleRow && event.target.closest("[data-delete-module]")) {
      const module = state.selectedSector.modules.find((item) => item.id === Number(moduleRow.dataset.moduleId));
      if (!window.confirm(`Excluir a tela ${module?.name || "selecionada"}?`)) return;
      await api(`../api/modules/${moduleRow.dataset.moduleId}`, { method: "DELETE" });
      await loadSectorModules();
      showToast("Tela excluída com sucesso.");
      return;
    }
    if (userTrigger) {
      const popover = userTrigger.nextElementSibling;
      const willOpen = popover.hidden;
      document.querySelectorAll(".user-action-popover").forEach((item) => { item.hidden = true; });
      document.querySelectorAll(".user-action-trigger").forEach((item) => item.setAttribute("aria-expanded", "false"));
      popover.hidden = !willOpen;
      userTrigger.setAttribute("aria-expanded", String(willOpen));
      return;
    }
    if (maintenanceAction) {
      const userId = Number(maintenanceAction.dataset.maintenanceUser);
      const enabled = maintenanceAction.dataset.maintenanceEnabled === "true";
      const user = state.users.find((item) => item.id === userId);
      const verb = enabled ? "ativar o modo de manutenção para" : "liberar o acesso de";
      if (!window.confirm(`Deseja ${verb} ${user?.name || "este usuário"}?`)) return;
      await api(`../api/users/${userId}/maintenance`, { method: "PUT", body: JSON.stringify({ enabled }) });
      if (enabled && userId === Number(sessionStorage.getItem(USER_ID_KEY))) return void forceMaintenanceLogout();
      await loadUsers();
      if (document.querySelector('.screen.is-active')?.dataset.screen === "user-details") await renderDetails();
      showToast(enabled ? `${user.name} entrou em manutenção.` : `${user.name} foi liberado para login.`);
      return;
    }
    if (menu) return void await showScreen(menu.dataset.menuScreen);
    if (action && action.dataset.id) { state.selectedUserId = Number(action.dataset.id); if (action.dataset.action === "edit" && !requireSelectedUserMaintenance()) return; return void await showScreen(action.dataset.action === "edit" ? "edit-user" : "user-details"); }
    if (go) { const current = document.querySelector(".screen.is-active")?.dataset.screen; if (go.dataset.go === "edit-user" && !requireSelectedUserMaintenance()) return; if (current === "sectors" && go.dataset.go === "modules" && canModifySelectedUser()) await saveSectors(); if (current === "modules" && go.dataset.go === "permissions" && canModifySelectedUser()) await saveModules(); return void await showScreen(go.dataset.go); }
  } catch (error) { showToast(error.message, true); }
});

document.addEventListener("click", (event) => {
  if (event.target.closest(".user-row-menu") || event.target.closest(".sector-action")) return;
  document.querySelectorAll(".user-action-popover").forEach((item) => { item.hidden = true; });
  document.querySelectorAll(".user-action-trigger").forEach((item) => item.setAttribute("aria-expanded", "false"));
  document.querySelectorAll(".sector-action-menu").forEach((item) => { item.hidden = true; });
  document.querySelectorAll(".sector-action-trigger").forEach((item) => item.setAttribute("aria-expanded", "false"));
});

document.querySelector("#sector-list").addEventListener("change", (event) => { const status = event.target.closest(".sector-row")?.querySelector("em"); if (status) { status.textContent = event.target.checked ? "Ativo" : "Inativo"; status.classList.toggle("inactive", !event.target.checked); } });
document.querySelector("#permission-grid").addEventListener("change", (event) => event.target.closest(".permission-card")?.classList.toggle("is-denied", event.target.value === "0"));
document.addEventListener("change", async (event) => {
  if (!event.target.matches(".access-toolbar > label:first-child select")) return;
  state.selectedUserId = Number(event.target.value);
  try { await loadAccess(true); } catch (error) { showToast(error.message, true); setAccessLoading(false); }
});
document.querySelector("#save-permissions").addEventListener("click", () => savePermissions().catch((error) => showToast(error.message, true)));
[document.querySelector("#user-search"), document.querySelector("#profile-filter"), document.querySelector("#status-filter")].forEach((control) => control.addEventListener("input", renderUsers));
[document.querySelector("#sector-search"), document.querySelector("#sector-status-filter"), document.querySelector("#sector-category-filter")].forEach((control) => control.addEventListener("input", renderSectorRows));
document.querySelector("#add-initial-module").addEventListener("click", () => {
  const input = document.querySelector("#initial-module-name");
  const name = input.value.trim();
  if (!name) return void showToast("Informe o nome da tela.", true);
  if (state.initialModules.some((item) => item.toLocaleLowerCase("pt-BR") === name.toLocaleLowerCase("pt-BR"))) return void showToast("Esta tela já foi adicionada.", true);
  state.initialModules.push(name);
  input.value = "";
  renderInitialModules();
});
document.querySelector("#initial-module-name").addEventListener("keydown", (event) => { if (event.key === "Enter") { event.preventDefault(); document.querySelector("#add-initial-module").click(); } });
function configureSectorIconUpload(inputSelector, formSelector, previewSelector) {
  const input = document.querySelector(inputSelector);
  const form = document.querySelector(formSelector);
  const preview = document.querySelector(previewSelector);
  input.addEventListener("change", () => {
    const file = input.files[0];
    if (!file) return;
    if (!["image/svg+xml", "image/png"].includes(file.type)) {
      input.value = "";
      return void showToast("Selecione um arquivo SVG ou PNG.", true);
    }
    if (file.size > 750 * 1024) {
      input.value = "";
      return void showToast("O ícone deve ter no máximo 750 KB.", true);
    }
    const reader = new FileReader();
    reader.addEventListener("load", () => {
      form.dataset.icon = reader.result;
      preview.innerHTML = `<img src="${reader.result}" alt="Pré-visualização do ícone" />`;
    });
    reader.readAsDataURL(file);
  });
}
configureSectorIconUpload("#new-sector-icon", "#new-sector-form", "#new-sector-icon-preview");
configureSectorIconUpload("#edit-sector-icon", "#edit-sector-form", "#edit-sector-icon-preview");
document.querySelector("#save-new-sector").addEventListener("click", async () => {
  const form = document.querySelector("#new-sector-form");
  if (!form.reportValidity()) return;
  if (!form.dataset.icon) return void showToast("Selecione um ícone SVG ou PNG para o setor.", true);
  try {
    const data = { ...sectorFormData(form), modules: state.initialModules };
    const { sector } = await api("../api/sectors", { method: "POST", body: JSON.stringify(data) });
    state.selectedSectorId = sector.id;
    form.reset();
    delete form.dataset.prepared;
    state.initialModules = [];
    await showScreen("sector-list");
    showToast("Setor criado com sucesso.");
  } catch (error) { showToast(error.message, true); }
});
document.querySelector("#save-edit-sector").addEventListener("click", async () => {
  const form = document.querySelector("#edit-sector-form");
  if (!form.reportValidity()) return;
  try {
    await api(`../api/sectors/${state.selectedSectorId}`, { method: "PUT", body: JSON.stringify(sectorFormData(form)) });
    await showScreen("sector-list");
    showToast("Setor atualizado com sucesso.");
  } catch (error) { showToast(error.message, true); }
});
const moduleCreateForm = document.querySelector("#module-create-form");
document.querySelector("#show-module-form").addEventListener("click", () => { moduleCreateForm.hidden = false; moduleCreateForm.elements.name.focus(); });
document.querySelector("#cancel-module-form").addEventListener("click", () => { moduleCreateForm.hidden = true; moduleCreateForm.reset(); });
moduleCreateForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!moduleCreateForm.reportValidity()) return;
  try {
    await api(`../api/sectors/${state.selectedSectorId}/modules`, { method: "POST", body: JSON.stringify(sectorFormData(moduleCreateForm)) });
    moduleCreateForm.reset();
    moduleCreateForm.hidden = true;
    await loadSectorModules();
    showToast("Tela adicionada com sucesso.");
  } catch (error) { showToast(error.message, true); }
});
document.querySelector("#sector-module-rows").addEventListener("change", async (event) => {
  if (!event.target.matches("[data-module-permission]")) return;
  const row = event.target.closest(".module-sector-row");
  try {
    await api(`../api/modules/${row.dataset.moduleId}`, { method: "PUT", body: JSON.stringify({ permission_enabled: event.target.checked }) });
    row.querySelector(".module-permission-switch small").textContent = event.target.checked ? "Disponível" : "Bloqueado";
  } catch (error) { event.target.checked = !event.target.checked; showToast(error.message, true); }
});
document.querySelectorAll(".toggle-password").forEach((button) => button.addEventListener("click", () => { const input = button.parentElement.querySelector("input"); input.type = input.type === "password" ? "text" : "password"; button.setAttribute("aria-label", input.type === "password" ? "Mostrar senha" : "Ocultar senha"); }));

const deleteModal = document.querySelector("#delete-user-modal");
const confirmDeleteButton = document.querySelector("#confirm-delete-user");
function setDeleteModal(open) {
  deleteModal.hidden = !open;
  if (open) confirmDeleteButton.focus();
}
document.querySelector("#delete-user-button").addEventListener("click", () => { if (requireSelectedUserMaintenance()) setDeleteModal(true); });
document.querySelector("#cancel-delete-user").addEventListener("click", () => setDeleteModal(false));
deleteModal.addEventListener("click", (event) => { if (event.target === deleteModal) setDeleteModal(false); });
document.addEventListener("keydown", (event) => { if (event.key === "Escape" && !deleteModal.hidden) setDeleteModal(false); });
confirmDeleteButton.addEventListener("click", async () => {
  if (!state.selectedUser || state.selectedUser.username === "admin") return;
  confirmDeleteButton.disabled = true;
  try {
    await api(`../api/users/${state.selectedUserId}`, { method: "DELETE" });
    const deletedName = state.selectedUser.name;
    setDeleteModal(false);
    state.selectedUser = null;
    state.selectedUserId = 0;
    await loadUsers();
    await showScreen("users");
    showToast(`${deletedName} foi excluído com sucesso.`);
  } catch (error) {
    showToast(error.message, true);
  } finally {
    confirmDeleteButton.disabled = false;
  }
});

const avatarInput = document.querySelector('#new-user-form [name="avatarFile"]');
const avatarPreview = document.querySelector("#new-avatar-preview");
function resetAvatarPreview() {
  avatarPreview.innerHTML = '<i data-lucide="user-round"></i>';
  delete document.querySelector("#new-user-form").dataset.avatar;
  refreshIcons();
}
avatarInput.addEventListener("change", () => {
  const file = avatarInput.files[0];
  if (!file) return void resetAvatarPreview();
  if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
    avatarInput.value = "";
    resetAvatarPreview();
    return void showToast("Selecione uma imagem JPG, PNG ou WebP.", true);
  }
  if (file.size > 2 * 1024 * 1024) {
    avatarInput.value = "";
    resetAvatarPreview();
    return void showToast("A foto de perfil deve ter no máximo 2 MB.", true);
  }
  const reader = new FileReader();
  reader.addEventListener("load", () => {
    document.querySelector("#new-user-form").dataset.avatar = reader.result;
    avatarPreview.innerHTML = `<img src="${reader.result}" alt="Pré-visualização da foto de perfil" />`;
  });
  reader.readAsDataURL(file);
});

function formPayload(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  delete data.avatarFile;
  return data;
}
document.querySelectorAll("[data-save-user]").forEach((button) => button.addEventListener("click", async () => {
  if (button.dataset.saveUser === "updated" && !requireSelectedUserMaintenance()) return;
  const form = button.closest(".screen").querySelector("form"); if (!form.reportValidity()) return; const data = formPayload(form);
  if (button.dataset.saveUser === "created") data.avatar = form.dataset.avatar || "";
  if (data.password !== data.confirmPassword) { form.elements.confirmPassword.setCustomValidity("As senhas precisam ser iguais."); form.elements.confirmPassword.reportValidity(); return; }
  try { if (button.dataset.saveUser === "created") { const { user } = await api("../api/users", { method: "POST", body: JSON.stringify(data) }); state.selectedUserId = user.id; form.reset(); resetAvatarPreview(); showToast("Usuário criado com sucesso."); } else { await api(`../api/users/${state.selectedUserId}`, { method: "PUT", body: JSON.stringify(data) }); showToast("Alterações salvas com sucesso."); } await loadUsers(); await showScreen("users"); } catch (error) { showToast(error.message, true); }
}));
document.querySelectorAll('[name="confirmPassword"]').forEach((input) => input.addEventListener("input", () => input.setCustomValidity("")));

function formatCpf(value) { return value.replace(/\D/g, "").slice(0, 11).replace(/^(\d{3})(\d)/, "$1.$2").replace(/^(\d{3})\.(\d{3})(\d)/, "$1.$2.$3").replace(/\.(\d{3})(\d)/, ".$1-$2"); }
document.querySelectorAll('[name="cpf"]').forEach((input) => input.addEventListener("input", () => { input.value = formatCpf(input.value); }));
function formatPhone(value) { const digits = value.replace(/\D/g, "").slice(0, 11); return digits.length <= 10 ? digits.replace(/^(\d{2})(\d)/, "($1) $2").replace(/(\d{4})(\d)/, "$1-$2") : digits.replace(/^(\d{2})(\d)/, "($1) $2").replace(/(\d{5})(\d)/, "$1-$2"); }
document.querySelectorAll('[name="phone"]').forEach((input) => input.addEventListener("input", () => { input.value = formatPhone(input.value); }));

async function initialize() {
  try {
    const { user: authenticatedUser, permissions } = await api("../api/auth/me");
    if (!permissions.includes("administration.access")) {
      window.location.replace("../home/?access=denied");
      return;
    }
    state.selectedUserId ||= authenticatedUser.id;
    sessionStorage.setItem(USER_ID_KEY, String(authenticatedUser.id));
    sessionStorage.setItem(SESSION_KEY, authenticatedUser.username);
    applyHeaderProfile(authenticatedUser);
    await loadUsers();
    const available = ["users", "new-user", "edit-user", "user-details", "access-overview", "sectors", "modules", "permissions", "sector-list", "new-sector", "edit-sector", "sector-modules"];
    await showScreen(available.includes(location.hash.slice(1)) ? location.hash.slice(1) : "users"); refreshIcons();
  } catch (error) { showToast(`Erro ao carregar banco local: ${error.message}`, true); }
}
initialize();

function forceMaintenanceLogout() {
  sessionStorage.removeItem(SESSION_KEY);
  sessionStorage.removeItem(USER_ID_KEY);
  sessionStorage.removeItem("sgo.authenticatedUserName");
  sessionStorage.removeItem("sgo.authenticatedUserProfile");
  window.location.replace("../index.html?maintenance=1");
}

async function checkSessionStatus() {
  try {
    const { session } = await api("../api/session/status");
    if (!session.exists || !session.active || session.maintenance) forceMaintenanceLogout();
  } catch { /* Uma falha temporária de rede não encerra a sessão. */ }
}
window.setInterval(checkSessionStatus, 5000);
