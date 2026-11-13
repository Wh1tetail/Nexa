import { cn } from "@/lib/utils";

function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("animate-pulse rounded-lg bg-[hsl(220_30%_94%)]", className)} {...props} />;
}

export { Skeleton };
