export function DjangoAdminAction({ enabled }: { enabled: boolean }) {
  if (!enabled) return null;
  return <a className="button" href="/admin/">Django Admin / Service Hatch</a>;
}
