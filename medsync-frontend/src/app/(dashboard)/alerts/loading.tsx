import { ListSkeleton } from "@/components/ui/skeleton";

export default function AlertsLoading() {
  return (
    <div className="space-y-6">
      <div className="h-8 w-48 animate-pulse rounded-md bg-slate-200 dark:bg-slate-800" />
      <ListSkeleton rows={5} showAvatar />
    </div>
  );
}
