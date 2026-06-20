export function userDisplayName(user) {
  if (!user) return "";
  const firstName = user.first_name ? String(user.first_name).trim() : "";
  const lastName = user.last_name ? String(user.last_name).trim() : "";
  return [firstName, lastName].filter(Boolean).join(" ");
}

export function userHandle(user) {
  if (!user || !user.username) return "";
  const username = String(user.username).trim();
  return username ? `<@${username}>` : "";
}

export function userIdentityText(user, options = {}) {
  const includeEmail = options.includeEmail === true;
  const displayName = userDisplayName(user);
  const handle = userHandle(user);
  const email = includeEmail && user && user.email ? String(user.email).trim() : "";
  const parts = [displayName, handle, email].filter(Boolean);
  return parts.length ? parts.join(" • ") : "Unknown user";
}

function appendIdentityPiece(container, className, text) {
  if (!text) return;
  const piece = document.createElement("span");
  piece.className = `user-identity__piece ${className}`;
  piece.textContent = text;
  container.appendChild(piece);
}

export function renderUserIdentity(user, options = {}) {
  const container = document.createElement(options.element || "span");
  container.className = "user-identity";
  if (options.className) container.classList.add(String(options.className));

  const icon = document.createElement("span");
  icon.className = "material-symbols-outlined user-identity__icon";
  icon.setAttribute("aria-hidden", "true");
  icon.textContent = "person";
  container.appendChild(icon);

  const displayName = userDisplayName(user);
  const handle = userHandle(user);
  const email =
    options.includeEmail === true && user && user.email
      ? String(user.email).trim()
      : "";

  if (!displayName && !handle) {
    appendIdentityPiece(
      container,
      "user-identity__display-name",
      "Unknown user"
    );
    return container;
  }

  appendIdentityPiece(
    container,
    "user-identity__display-name",
    displayName
  );
  appendIdentityPiece(container, "user-identity__handle", handle);
  appendIdentityPiece(container, "user-identity__email", email);
  return container;
}
