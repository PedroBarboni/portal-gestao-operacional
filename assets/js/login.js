const loginForm = document.querySelector("#login-form");
const usernameInput = document.querySelector("#username");
const passwordInput = document.querySelector("#password");
const passwordToggle = document.querySelector("#password-toggle");
const rememberInput = document.querySelector("#remember");
const forgotPasswordLink = document.querySelector("#forgot-password");
const formMessage = document.querySelector("#form-message");
const submitButton = loginForm.querySelector(".submit-button");
const submitLabel = submitButton.querySelector(".button-label");

const STORAGE_KEY = "sgo.rememberedUser";
const SESSION_KEY = "sgo.authenticatedUser";

function setFieldError(input, message) {
  const fieldGroup = input.closest(".field-group");
  const errorElement = fieldGroup.querySelector(".field-error");

  fieldGroup.classList.toggle("has-error", Boolean(message));
  errorElement.textContent = message;
  input.setAttribute("aria-invalid", message ? "true" : "false");
}

function setFormMessage(message, type = "info") {
  formMessage.textContent = message;
  formMessage.dataset.type = type;
}

function setLoading(isLoading) {
  submitButton.disabled = isLoading;
  submitLabel.textContent = isLoading ? "Validando acesso..." : "Entrar no PGO";
}

function validateForm() {
  let isValid = true;
  setFieldError(usernameInput, "");
  setFieldError(passwordInput, "");

  if (!usernameInput.value.trim()) {
    setFieldError(usernameInput, "Informe seu usuário.");
    isValid = false;
  }

  if (!passwordInput.value) {
    setFieldError(passwordInput, "Informe sua senha.");
    isValid = false;
  }

  if (!isValid) loginForm.querySelector('[aria-invalid="true"]')?.focus();
  return isValid;
}

passwordToggle.addEventListener("click", () => {
  const isVisible = passwordInput.type === "text";
  passwordInput.type = isVisible ? "password" : "text";
  passwordToggle.setAttribute("aria-pressed", String(!isVisible));
  passwordToggle.setAttribute("aria-label", isVisible ? "Mostrar senha" : "Ocultar senha");
  passwordInput.focus();
});

usernameInput.addEventListener("input", () => {
  setFieldError(usernameInput, "");
  setFormMessage("");
});

passwordInput.addEventListener("input", () => {
  setFieldError(passwordInput, "");
  setFormMessage("");
});

forgotPasswordLink.addEventListener("click", (event) => {
  event.preventDefault();
  setFormMessage("Entre em contato com o suporte para recuperar seu acesso.");
});

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  setFormMessage("");
  if (!validateForm()) return;

  setLoading(true);
  try {
    const username = usernameInput.value.trim().toLowerCase();
    const response = await fetch("./api/auth/login", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password: passwordInput.value }),
    });
    const result = await response.json();
    if (!response.ok) {
      setFormMessage(result.error || "Não foi possível validar o acesso.", "error");
      passwordInput.select();
      return;
    }

    if (rememberInput.checked) localStorage.setItem(STORAGE_KEY, username);
    else localStorage.removeItem(STORAGE_KEY);

    sessionStorage.setItem(SESSION_KEY, result.user.username);
    sessionStorage.setItem("sgo.authenticatedUserId", String(result.user.id));
    sessionStorage.setItem("sgo.authenticatedUserName", result.user.name);
    sessionStorage.setItem("sgo.authenticatedUserProfile", result.user.profile);
    setFormMessage("Acesso validado. Redirecionando...", "success");
    await new Promise((resolve) => window.setTimeout(resolve, 250));
    window.location.href = "./home/";
  } finally {
    setLoading(false);
  }
});

const rememberedUser = localStorage.getItem(STORAGE_KEY);
if (rememberedUser) {
  usernameInput.value = rememberedUser;
  rememberInput.checked = true;
}

if (new URLSearchParams(window.location.search).get("maintenance") === "1") {
  setFormMessage("Seu usuário está em manutenção. Entre em contato com o suporte ou aguarde a conclusão da manutenção.", "error");
}

fetch("./api/auth/me", { credentials: "same-origin" }).then((response) => {
  if (response.ok) window.location.replace("./home/");
}).catch(() => {});
