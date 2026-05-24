

interface StatusStatProps {
  label: string;
  value: number;
  color: string;
}

export function StatusStat({ label, value, color }: StatusStatProps) {
  return (
    <div className="bg-white/5 rounded-2xl p-4">
      <div className={`text-2xl font-black ${color}`}>{value}</div>
      <div className="text-[9px] uppercase tracking-widest text-white/30">{label}</div>
    </div>
  );
}
