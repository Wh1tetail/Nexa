import { cn } from "@/lib/utils";

const PALETTE = [
  "bg-[#E8EEFF] text-[#3563F5]",
  "bg-[#E9F9EF] text-[#16A34A]",
  "bg-[#FFF4E0] text-[#B45309]",
  "bg-[#FDECEC] text-[#DC2626]",
  "bg-[#EFEAFE] text-[#7C3AED]",
  "bg-[#E6F6FA] text-[#0E7490]",
];

export function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("");
}

export function Avatar({ name, className }: { name: string; className?: string }) {
  const hash = [...name].reduce((a, c) => a + c.charCodeAt(0), 0);
  return (
    <span
      aria-hidden
      className={cn(
        "inline-flex size-9 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
        PALETTE[hash % PALETTE.length],
        className,
      )}
    >
      {initials(name)}
    </span>
  );
}
