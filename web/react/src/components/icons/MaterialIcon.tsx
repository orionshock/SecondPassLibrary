import "./MaterialIcon.css";

export interface MaterialIconProps {
  name: string;
  label?: string;
  title?: string;
  size?: number | string;
  className?: string;
}

export function MaterialIcon({
  name,
  label,
  title,
  size,
  className = "",
}: MaterialIconProps) {
  const accessible = Boolean(label);
  return (
    <span
      className={`material-symbols-outlined material-icon ${className}`.trim()}
      aria-hidden={accessible ? undefined : true}
      aria-label={label}
      role={accessible ? "img" : undefined}
      title={title ?? label}
      style={size === undefined ? undefined : { fontSize: size }}
    >
      {name}
    </span>
  );
}
