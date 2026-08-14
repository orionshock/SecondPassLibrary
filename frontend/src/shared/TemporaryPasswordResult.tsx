import { UserInlineIdentity } from "./users/UserInlineIdentity";

export function TemporaryPasswordResult({ id, username, password }: { id: string; username: string; password: string }) {
  return <div className="temporary-password-result">
    <UserInlineIdentity username={username} />
    <textarea id={id} rows={2} readOnly value={`Username: ${username}\nPassword: ${password}`} />
    <p>Copy it now. It will not be shown again.</p>
  </div>;
}
