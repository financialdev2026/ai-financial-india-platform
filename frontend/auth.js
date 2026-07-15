const ROLE_LEVELS = {
  viewer: 1,
  analyst: 2,
  admin: 3
};

const AUTH_STATE_KEY = "prismedge-local-auth";
const FIREBASE_SDK = "https://www.gstatic.com/firebasejs/10.12.4/firebase-app.js";
const FIREBASE_AUTH_SDK = "https://www.gstatic.com/firebasejs/10.12.4/firebase-auth.js";
const OWNER_ADMIN_EMAILS = new Set(["udaylowalekar@gmail.com"]);

window.PrismEdgeAuth = {
  mode: "local",
  user: null,
  role: "analyst",
  ROLE_LEVELS,
  can(requiredRole) {
    return ROLE_LEVELS[this.role] >= ROLE_LEVELS[requiredRole];
  }
};

function pageKind() {
  return document.body?.dataset.authPage || "dashboard";
}

function hasConfig(config) {
  return Boolean(config?.apiKey && config?.authDomain && config?.projectId && config?.appId);
}

async function loadFirebaseConfig() {
  try {
    await import("./firebase-config.js");
  } catch {
    return null;
  }
  return hasConfig(window.PRISMEDGE_FIREBASE_CONFIG) ? window.PRISMEDGE_FIREBASE_CONFIG : null;
}

async function loadFirebaseAuth(config) {
  const [{ initializeApp }, authModule] = await Promise.all([
    import(FIREBASE_SDK),
    import(FIREBASE_AUTH_SDK)
  ]);
  const app = initializeApp(config);
  const auth = authModule.getAuth(app);
  return { auth, ...authModule };
}

function setAccessCard(authState) {
  const role = document.querySelector("#activeRole");
  const detail = document.querySelector("#activeUserDetail");
  const signOutButton = document.querySelector("#signOutButton");
  if (role) {
    role.textContent = authState.mode === "firebase"
      ? `${titleCase(authState.role)}`
      : "Local Analyst";
  }
  if (detail) {
    detail.textContent = authState.user?.email || "Viewer < Analyst < Admin";
  }
  if (signOutButton) {
    signOutButton.hidden = authState.mode !== "firebase";
  }
}

function titleCase(value) {
  return String(value || "viewer").slice(0, 1).toUpperCase() + String(value || "viewer").slice(1);
}

function localFallback() {
  const saved = JSON.parse(localStorage.getItem(AUTH_STATE_KEY) || "null");
  window.PrismEdgeAuth.mode = "local";
  window.PrismEdgeAuth.role = saved?.role || "analyst";
  window.PrismEdgeAuth.user = saved?.email ? { email: saved.email } : null;
  setAccessCard(window.PrismEdgeAuth);
  return window.PrismEdgeAuth;
}

function roleFromClaims(claims) {
  if (claims?.admin) return "admin";
  if (claims?.analyst) return "analyst";
  return claims?.role || "viewer";
}

function roleForUser(user, claims) {
  const claimRole = roleFromClaims(claims);
  if (claimRole !== "viewer") return claimRole;
  return OWNER_ADMIN_EMAILS.has(String(user?.email || "").toLowerCase()) ? "admin" : "viewer";
}

async function initializeDashboardAuth(config, firebase) {
  const { auth, onAuthStateChanged, signOut } = firebase;
  onAuthStateChanged(auth, async (user) => {
    if (!user) {
      window.location.href = `login.html?next=${encodeURIComponent("index.html")}`;
      return;
    }
    const token = await user.getIdTokenResult(true);
    window.PrismEdgeAuth.mode = "firebase";
    window.PrismEdgeAuth.user = { email: user.email, uid: user.uid };
    window.PrismEdgeAuth.role = roleForUser(user, token.claims);
    setAccessCard(window.PrismEdgeAuth);
  });

  document.querySelector("#signOutButton")?.addEventListener("click", async () => {
    await signOut(auth);
    window.location.href = "login.html";
  });
}

function authMessage(text, type = "neutral") {
  const target = document.querySelector("#authMessage");
  if (!target) return;
  target.textContent = text;
  target.dataset.type = type;
}

function nextUrl() {
  const params = new URLSearchParams(window.location.search);
  return params.get("next") || "index.html";
}

async function initializeLoginPage(firebase) {
  const { auth, signInWithEmailAndPassword, onAuthStateChanged } = firebase;
  onAuthStateChanged(auth, (user) => {
    if (user) window.location.href = nextUrl();
  });
  document.querySelector("#loginForm")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    authMessage("Signing in...");
    try {
      await signInWithEmailAndPassword(auth, form.get("email"), form.get("password"));
      window.location.href = nextUrl();
    } catch (error) {
      authMessage(firebaseError(error), "error");
    }
  });
}

async function initializeSignupPage(firebase) {
  const { auth, createUserWithEmailAndPassword, updateProfile } = firebase;
  document.querySelector("#signupForm")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const password = String(form.get("password") || "");
    const confirm = String(form.get("confirmPassword") || "");
    if (password !== confirm) {
      authMessage("Passwords do not match.", "error");
      return;
    }
    authMessage("Creating account...");
    try {
      const credential = await createUserWithEmailAndPassword(auth, form.get("email"), password);
      await updateProfile(credential.user, { displayName: form.get("name") || "" });
      authMessage("Account created. Redirecting...", "success");
      window.location.href = nextUrl();
    } catch (error) {
      authMessage(firebaseError(error), "error");
    }
  });
}

function initializeLocalAuthPage() {
  const form = document.querySelector("#loginForm, #signupForm");
  form?.addEventListener("submit", (event) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    localStorage.setItem(AUTH_STATE_KEY, JSON.stringify({
      email: data.get("email"),
      role: "analyst"
    }));
    window.location.href = nextUrl();
  });
  authMessage("Firebase config not found. This page is in local development mode.", "neutral");
}

function firebaseError(error) {
  if (error?.code === "auth/operation-not-allowed") {
    return "Email/password login is disabled in Firebase. Enable Authentication -> Sign-in method -> Email/Password in the Firebase Console.";
  }
  const code = String(error?.code || "").replace("auth/", "").replaceAll("-", " ");
  return code ? `Firebase auth error: ${code}.` : "Authentication failed.";
}

async function initializeAuth() {
  const config = await loadFirebaseConfig();
  if (!config) {
    const auth = localFallback();
    if (pageKind() === "login" || pageKind() === "signup") initializeLocalAuthPage();
    return auth;
  }

  try {
    const firebase = await loadFirebaseAuth(config);
    if (pageKind() === "login") await initializeLoginPage(firebase);
    if (pageKind() === "signup") await initializeSignupPage(firebase);
    if (pageKind() === "dashboard") await initializeDashboardAuth(config, firebase);
    return window.PrismEdgeAuth;
  } catch (error) {
    authMessage(firebaseError(error), "error");
    return localFallback();
  }
}

window.PrismEdgeAuth.ready = initializeAuth();
