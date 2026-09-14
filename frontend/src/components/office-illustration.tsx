export function OfficeIllustration() {
  return (
    <div className="relative overflow-hidden rounded-3xl border border-white/10 bg-zinc-950/70 p-6">
      <p className="mb-4 text-[11px] uppercase tracking-[0.2em] text-zinc-500">
        Product visual — not a live office
      </p>
      <div className="relative grid h-64 grid-cols-6 grid-rows-4 gap-2">
        <div className="col-span-2 row-span-2 rounded-xl bg-gradient-to-br from-violet-500/20 to-transparent ring-1 ring-white/10">
          <p className="p-3 text-xs text-zinc-400">Reception</p>
        </div>
        <div className="col-span-2 rounded-xl bg-cyan-400/10 ring-1 ring-cyan-400/20">
          <p className="p-3 text-xs text-cyan-100/80">CEO</p>
        </div>
        <div className="col-span-2 rounded-xl bg-white/5 ring-1 ring-white/10">
          <p className="p-3 text-xs text-zinc-400">Meeting</p>
        </div>
        <Desk label="Maya" />
        <Desk label="Adam" />
        <Desk label="Sara" />
        <Desk label="Omar" />
        <div className="col-span-3 rounded-xl bg-white/5 ring-1 ring-white/10">
          <p className="p-3 text-xs text-zinc-400">Research</p>
        </div>
        <div className="col-span-3 rounded-xl bg-white/5 ring-1 ring-white/10">
          <p className="p-3 text-xs text-zinc-400">Engineering</p>
        </div>
      </div>
      <p className="mt-4 text-sm text-zinc-500">
        The 3D office (Phase 6) will only move when real backend events arrive.
      </p>
    </div>
  );
}

function Desk({ label }: { label: string }) {
  return (
    <div className="flex items-end rounded-xl bg-zinc-900 ring-1 ring-white/10">
      <div className="m-2 h-8 w-8 rounded-full bg-gradient-to-br from-cyan-300 to-violet-400" />
      <p className="pb-3 text-xs text-zinc-300">{label}</p>
    </div>
  );
}
