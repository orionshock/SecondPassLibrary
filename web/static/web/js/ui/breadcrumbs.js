import { escapeHtml } from "../layout.js";

export function setBreadcrumbs(crumbs, root = document) {
  const nav = root.querySelector('nav[aria-label="Breadcrumb"]');
  if (!nav) return;
  const list = nav.querySelector(".breadcrumbs__list");
  if (!list) return;

  const visibleCrumbs = Array.isArray(crumbs)
    ? crumbs
        .map((crumb) => ({
          label: crumb && crumb.label != null ? String(crumb.label).trim() : "",
          href: crumb && crumb.href != null ? String(crumb.href).trim() : "",
          current: !!(crumb && crumb.current),
        }))
        .filter((crumb) => crumb.label)
    : [];
  if (!visibleCrumbs.length) return;

  const finalIndex = visibleCrumbs.length - 1;
  const html = visibleCrumbs
    .map((crumb, index) => {
      const isCurrent = crumb.current || index === finalIndex;
      const content =
        !isCurrent && crumb.href
          ? `<a class="breadcrumbs__link" href="${escapeHtml(crumb.href)}">${escapeHtml(crumb.label)}</a>`
          : escapeHtml(crumb.label);
      return `<li class="breadcrumbs__item${isCurrent ? " breadcrumbs__current" : ""}"${isCurrent ? ' aria-current="page"' : ""}>${content}</li>`;
    })
    .join("");

  list.innerHTML = html;
  nav.classList.toggle("breadcrumbs--single", visibleCrumbs.length === 1);
  nav.classList.toggle("breadcrumbs--trail", visibleCrumbs.length > 1);
}
