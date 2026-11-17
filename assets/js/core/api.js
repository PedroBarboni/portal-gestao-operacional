"""Cliente HTTP compartilhado pelas páginas modulares do PGO.""";

export function clearLocalSession() {
  ["sgo.authenticatedUser", "sgo.authenticatedUserId", "sgo.authenticatedUserName", "sgo.authenticatedUserProfile"]
    .forEach((key) => sessionStorage.removeItem(key));
}

export async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const result = await response.json().catch(() => ({}));
  if (response.status === 401) {
    clearLocalSession();
    window.location.replace("../index.html");
    throw new Error("Sessão expirada.");
  }
  if (!response.ok) throw new Error(result.error || "Não foi possível concluir a operação.");
  return result;
}

