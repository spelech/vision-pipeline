import { useRef } from 'react';
import { StatusStat } from './StatusStat';
import { Upload } from 'lucide-react';

interface DashboardProps {
  queueLength: number;
  onUpload: (event: React.ChangeEvent<HTMLInputElement>) => void;
}

export function Dashboard({ queueLength, onUpload }: DashboardProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  return (
    <aside className="lg:col-span-4 space-y-6">
      <div className="glass rounded-[2rem] p-8 space-y-6">
        <div className="flex items-center justify-between">
          <h3 className="label-apple">Actions</h3>
        </div>
        
        <button 
          onClick={() => fileInputRef.current?.click()}
          className="w-full bg-blue-600 hover:bg-blue-500 text-white p-6 rounded-3xl transition-all shadow-lg shadow-blue-500/20 active:scale-[0.98] group flex flex-col items-center gap-3"
        >
          <div className="w-12 h-12 bg-white/20 rounded-2xl flex items-center justify-center group-hover:scale-110 transition-transform">
            <Upload className="w-6 h-6" />
          </div>
          <div className="text-center">
            <span className="block text-sm font-black uppercase tracking-widest">Upload Asset</span>
            <span className="text-[10px] text-white/60 font-medium tracking-normal mt-1 block">Process image with AI</span>
          </div>
          <input 
            type="file" 
            ref={fileInputRef}
            onChange={onUpload}
            className="hidden" 
            accept="image/*"
            multiple
          />
        </button>
      </div>

      <div className="glass rounded-[2rem] p-8 space-y-6 sticky top-32">
        <h3 className="label-apple">Status Dashboard</h3>
        <div className="grid grid-cols-2 gap-4">
          <StatusStat label="Queue" value={queueLength} color="text-white" />
          <StatusStat label="Active" value={0} color="text-blue-500" />
        </div>
      </div>
    </aside>
  );
}
