import { cn } from "@/lib/utils";

const PALETTE = [
  "bg-[#E8EEFF] text-[#3563F5] dark:bg-[#3563F5]/20 dark:text-[#9DB4FF]",
  "bg-[#E9F9EF] text-[#16A34A] dark:bg-[#16A34A]/20 dark:text-[#6EE7A0]",
  "bg-[#FFF4E0] text-[#B45309] dark:bg-[#F59E0B]/20 dark:text-[#FCD34D]",
  "bg-[#FDECEC] text-[#DC2626] dark:bg-[#EF4444]/20 dark:text-[#FCA5A5]",
  "bg-[#EFEAFE] text-[#7C3AED] dark:bg-[#7C3AED]/25 dark:text-[#C4B5FD]",
  "bg-[#E6F6FA] text-[#0E7490] dark:bg-[#0E7490]/30 dark:text-[#67E8F9]",
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
