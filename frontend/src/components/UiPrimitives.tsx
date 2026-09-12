import { cloneElement, forwardRef, isValidElement, type ButtonHTMLAttributes, type ReactElement, type ReactNode } from "react";

import "./UiPrimitives.css";

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
        <h1>{title}</h1>
        {description ? <div className="page-description">{description}</div> : null}
      </div>
      {actions ? <div className="page-actions">{actions}</div> : null}
    </header>
  );
}

export function Surface({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <section className="surface">
      {title ? <h2 className="surface-title">{title}</h2> : null}
      {children}
    </section>
  );
}

type ButtonSize = "small" | "medium";
type ButtonTone = "primary" | "secondary" | "danger";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  size?: ButtonSize;
  tone?: ButtonTone;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className = "", size = "medium", tone = "primary", ...props },
  ref,
) {
  return <button ref={ref} className={`button button--${size} button--${tone} ${className}`.trim()} {...props} />;
});

export function IconButton({
  className = "",
  size = "small",
  tone = "secondary",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  size?: ButtonSize;
  tone?: ButtonTone | "success";
}) {
  return <button className={`icon-button icon-button--${size} icon-button--${tone} ${className}`.trim()} {...props} />;
}

export function FormField({
  label,
  htmlFor,
  error,
  children,
}: {
  label: string;
  htmlFor: string;
  error?: string;
  children: ReactNode;
}) {
  const errorId = `${htmlFor}-error`;
  let control = children;
  if (error && isValidElement(children)) {
    const child = children as ReactElement<{ "aria-describedby"?: string; "aria-invalid"?: boolean | "true" | "false" }>;
    control = cloneElement(child, {
      "aria-describedby": [child.props["aria-describedby"], errorId].filter(Boolean).join(" "),
      "aria-invalid": true,
    });
  }
  return (
    <div className="form-field">
      <label htmlFor={htmlFor}>{label}</label>
      {control}
      {error ? <span id={errorId} className="field-error">{error}</span> : null}
    </div>
  );
}

export function ErrorPanel({ children }: { children: ReactNode }) {
  return <div className="error-panel" role="alert">{children}</div>;
}

export function Badge({ children, tone = "default" }: { children: ReactNode; tone?: "default" | "accent" | "success" }) {
  return <span className={`badge badge--${tone}`}>{children}</span>;
}

export function KeyValueList({ items }: { items: Array<{ label: string; value: ReactNode }> }) {
  return (
    <dl className="key-value-list">
      {items.map(({ label, value }) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}
