import type React from 'react';

interface CameraCaptureModalProps {
  cameraOpen: boolean;
  cameraError: string;
  cameraVideoRef: React.RefObject<HTMLVideoElement | null>;
  onClose: () => void;
  onCapture: () => void;
}

export function CameraCaptureModal({
  cameraOpen,
  cameraError,
  cameraVideoRef,
  onClose,
  onCapture,
}: CameraCaptureModalProps) {
  if (!cameraOpen) return null;

  return (
    <div className="fixed inset-0 z-[1400] bg-black/90 backdrop-blur-xl flex items-center justify-center p-6">
      <div className="glass w-full max-w-3xl rounded-[3rem] p-6 space-y-6 border border-white/10">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-2xl font-black tracking-tight">Camera Capture</h3>
            <p className="text-sm text-white/40">Take a photo and send it through the selected pipeline.</p>
          </div>
          <button onClick={onClose} className="w-12 h-12 rounded-2xl bg-white/5 text-xl">✕</button>
        </div>

        <div className="bg-black rounded-[2rem] overflow-hidden border border-white/10">
          <video ref={cameraVideoRef} className="w-full max-h-[60vh] object-cover" playsInline muted autoPlay />
        </div>

        {cameraError && <p className="text-sm text-red-300">{cameraError}</p>}

        <div className="flex gap-3 justify-end">
          <button onClick={onClose} className="px-5 py-3 rounded-2xl bg-white/5 text-[10px] font-black uppercase tracking-widest">
            Cancel
          </button>
          <button onClick={onCapture} className="btn-apple px-6 py-3 rounded-2xl text-[10px] font-black uppercase tracking-widest">
            Capture and Process
          </button>
        </div>
      </div>
    </div>
  );
}
