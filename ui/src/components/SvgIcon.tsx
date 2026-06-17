interface SvgIconProps {
  path: string;
  size?: number;
}

export function SvgIcon({ path, size = 20 }: SvgIconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      style={{ flexShrink: 0 }}
    >
      <path d={path} />
    </svg>
  );
}
