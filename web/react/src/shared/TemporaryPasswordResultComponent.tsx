export function TemporaryPasswordResultComponent({ id, password }: { id: string; password: string }) {
  return <div className="temporary-password-result">
    <input id={id} type="text" readOnly value={password} />
    <p>Copy it now. It will not be shown again.</p>
  </div>;
}
