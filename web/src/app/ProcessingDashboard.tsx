import type { PipelineStageId } from './types';
import { getPipelineStageStatus } from './pipelineStageStatus';

interface ProcessingDashboardProps {
  processingFile: File | null;
  processingFileUrl: string;
  processingSessionId: string | null;
  processingLogs: string[];
  processingError: string | null;
  onDismissError: () => void;
}

export function ProcessingDashboard({
  processingFile,
  processingFileUrl,
  processingSessionId,
  processingLogs,
  processingError,
  onDismissError,
}: ProcessingDashboardProps) {
  if (!processingFile) return null;

  const stages: Array<{ id: PipelineStageId; label: string; icon: string }> = [
    { id: 'barcode', label: 'Barcode Scanning', icon: '🔍' },
    { id: 'vision', label: 'Vision Identification', icon: '🤖' },
    { id: 'search', label: 'Web Enrichment', icon: '🌐' },
    { id: 'refine', label: 'Data Refinement', icon: '🧠' },
    { id: 'sync', label: 'Services Integration', icon: '🔌' },
  ];

  return (
    <div className="glass rounded-[2rem] p-6 sm:p-8 border border-white/10 animate-in fade-in duration-500 space-y-6">
      <div className="flex flex-col md:flex-row gap-8">
        <div className="w-full md:w-1/3 flex flex-col items-center justify-center">
          <p className="label-apple mb-4">Ingested Image</p>
          <div className="relative w-full max-w-[280px] aspect-square rounded-2xl overflow-hidden bg-black/40 border border-white/10 shadow-inner">
            {processingFileUrl && (
              <img src={processingFileUrl} className="w-full h-full object-contain" alt="Processing preview" />
            )}
            {!processingError && (
              <div className="absolute left-0 w-full h-[3px] bg-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.8)] animate-scan" />
            )}
            <div className="absolute inset-0 bg-cyan-500/5 animate-pulse mix-blend-overlay" />
          </div>
          {processingError ? (
            <button
              type="button"
              onClick={onDismissError}
              className="mt-6 bg-red-600/20 hover:bg-red-600/30 text-red-200 border border-red-500/30 px-6 py-3 rounded-xl text-[10px] font-black tracking-widest uppercase transition-all"
            >
              Dismiss Error
            </button>
          ) : (
            <div className="mt-4 flex items-center gap-2 text-cyan-400/80 text-[10px] font-black tracking-widest uppercase animate-pulse">
              <span className="w-2 h-2 rounded-full bg-cyan-400" />
              Pipeline Processing...
            </div>
          )}
        </div>

        <div className="flex-1 flex flex-col space-y-6">
          <div>
            <p className="label-apple">Pipeline Stages</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {stages.map((stage) => {
                const status = getPipelineStageStatus(processingLogs, stage.id);
                return (
                  <div
                    key={stage.id}
                    className={`flex items-center gap-3 p-4 rounded-2xl border transition-all duration-300 ${
                      status === 'active'
                        ? 'bg-cyan-950/20 border-cyan-500/40 shadow-[0_0_15px_rgba(6,182,212,0.05)]'
                        : status === 'completed'
                          ? 'bg-green-950/10 border-green-500/20'
                          : 'bg-white/5 border-white/5 opacity-50'
                    }`}
                  >
                    <span className="text-xl shrink-0">{stage.icon}</span>
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-bold text-white leading-tight truncate">{stage.label}</p>
                      <p
                        className={`text-[9px] font-black uppercase tracking-wider mt-1 ${
                          status === 'active'
                            ? 'text-cyan-400 animate-pulse'
                            : status === 'completed'
                              ? 'text-green-400'
                              : 'text-white/30'
                        }`}
                      >
                        {status === 'active' ? 'Processing' : status === 'completed' ? 'Completed' : 'Pending'}
                      </p>
                    </div>
                    <div className="shrink-0">
                      {status === 'active' ? (
                        <div className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-ping" />
                      ) : status === 'completed' ? (
                        <div className="w-2.5 h-2.5 rounded-full bg-green-500 flex items-center justify-center text-[7px] text-black font-black">
                          ✓
                        </div>
                      ) : (
                        <div className="w-2.5 h-2.5 rounded-full bg-white/10" />
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="flex-1 flex flex-col space-y-2 min-h-[180px]">
            <div className="flex justify-between items-center">
              <p className="label-apple">Real-Time Pipeline Logs</p>
              {processingSessionId && (
                <span className="text-[9px] font-mono text-white/30 font-bold uppercase tracking-wider">
                  ID: {processingSessionId}
                </span>
              )}
            </div>
            <div className="flex-1 bg-black/60 rounded-2xl border border-white/5 p-4 font-mono text-[11px] text-white/70 overflow-y-auto max-h-[220px] space-y-1.5 scrollbar-thin scrollbar-thumb-white/10 no-scrollbar">
              {processingLogs.length === 0 ? (
                <p className="text-white/20 italic animate-pulse">Initializing pipeline session...</p>
              ) : (
                processingLogs.map((log, index) => (
                  <div key={index} className="leading-relaxed border-l border-white/5 pl-2 hover:bg-white/5 transition-colors">
                    <span className="text-white/30 mr-2">[{index + 1}]</span>
                    <span
                      className={
                        log.includes('❌') || log.includes('⚠️')
                          ? 'text-red-400'
                          : log.includes('✨') || log.includes('🏁')
                            ? 'text-green-400 font-semibold'
                            : 'text-white/80'
                      }
                    >
                      {log}
                    </span>
                  </div>
                ))
              )}
              {processingError && (
                <div className="mt-2 p-2 bg-red-950/20 border border-red-500/30 rounded-lg text-red-300 font-bold">
                  ⚠️ Error: {processingError}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
