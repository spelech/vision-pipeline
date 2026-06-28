import type { ToastState } from './types';

interface ToastBannerProps {
  toast: ToastState | null;
}

export function ToastBanner({ toast }: ToastBannerProps) {
  if (!toast) return null;

  return (
    <div className="fixed bottom-32 left-1/2 -translate-x-1/2 z-[2000] animate-in fade-in slide-in-from-bottom-4 duration-300">
      <div
        className={`px-8 py-4 rounded-[2rem] shadow-2xl flex items-center gap-4 border backdrop-blur-3xl ${
          toast.type === 'error'
            ? 'bg-red-500/20 border-red-500/50 text-red-200'
            : toast.type === 'success'
              ? 'bg-green-500/20 border-green-500/50 text-green-200'
              : 'bg-blue-500/20 border-blue-500/50 text-blue-100'
        }`}
      >
        <span className="text-sm font-black uppercase tracking-widest select-text cursor-text">{toast.message}</span>
      </div>
    </div>
  );
}
