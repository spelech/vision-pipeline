import { useCallback, useEffect, useMemo, useState } from 'react';

interface GmailStatusPayload {
  oauth_configured?: boolean;
  connected?: boolean;
  receipt_wrangler_configured?: boolean;
  processed_message_count?: number;
}

interface GmailMessage {
  message_id: string;
  subject?: string;
  from?: string;
  sent_at?: string;
  has_attachments?: boolean;
}

interface ReceiptsTabProps {
  onToast: (message: string, type?: 'success' | 'error' | 'info') => void;
}

async function parseJsonSafe<T>(response: Response): Promise<T> {
  const text = await response.text();
  try {
    return JSON.parse(text) as T;
  } catch {
    return {} as T;
  }
}

export function ReceiptsTab({ onToast }: ReceiptsTabProps) {
  const [status, setStatus] = useState<GmailStatusPayload>({});
  const [loadingStatus, setLoadingStatus] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [messages, setMessages] = useState<GmailMessage[]>([]);
  const [selectedMessageIds, setSelectedMessageIds] = useState<string[]>([]);
  const [preset, setPreset] = useState('default');
  const [maxResults, setMaxResults] = useState(25);

  const selectedCount = selectedMessageIds.length;

  const sortedMessages = useMemo(
    () => [...messages].sort((a, b) => String(b.sent_at || '').localeCompare(String(a.sent_at || ''))),
    [messages],
  );

  const loadStatus = useCallback(async () => {
    setLoadingStatus(true);
    try {
      const response = await fetch('/api/gmail/status');
      const payload = await parseJsonSafe<GmailStatusPayload>(response);
      setStatus(payload || {});
    } catch (error) {
      console.error(error);
      onToast('Failed to load Gmail status', 'error');
    } finally {
      setLoadingStatus(false);
    }
  }, [onToast]);

  const searchMessages = async () => {
    setLoadingMessages(true);
    try {
      const response = await fetch('/api/gmail/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ preset, max_results: maxResults }),
      });
      const payload = await parseJsonSafe<{ messages?: GmailMessage[] }>(response);
      const nextMessages = Array.isArray(payload.messages) ? payload.messages : [];
      setMessages(nextMessages);
      setSelectedMessageIds([]);
      onToast(`Loaded ${nextMessages.length} Gmail receipts`, 'info');
    } catch (error) {
      console.error(error);
      onToast('Failed to search Gmail receipts', 'error');
    } finally {
      setLoadingMessages(false);
    }
  };

  const withSelection = async (
    endpoint: string,
    successMessage: string,
    extraBody: Record<string, unknown> = {},
  ) => {
    if (!selectedMessageIds.length) {
      onToast('Select at least one receipt first', 'info');
      return;
    }

    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_ids: selectedMessageIds, ...extraBody }),
      });
      const payload = await parseJsonSafe<{ detail?: string }>(response);
      if (!response.ok) {
        onToast(payload.detail || 'Action failed', 'error');
        return;
      }
      onToast(successMessage, 'success');
      await loadStatus();
    } catch (error) {
      console.error(error);
      onToast('Action failed', 'error');
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadStatus();
  }, [loadStatus]);

  return (
    <div className="space-y-8">
      <header className="flex justify-between items-end">
        <div>
          <h2 className="text-4xl font-extrabold tracking-tight mb-2">Receipts</h2>
          <p className="text-white/40 font-medium italic">Search Gmail receipts and selectively sync to Receipt Wrangler or direct ingest.</p>
        </div>
        <button
          type="button"
          onClick={() => void loadStatus()}
          className="bg-white/5 hover:bg-white/10 px-4 py-2 rounded-xl text-[10px] font-black tracking-widest uppercase"
        >
          {loadingStatus ? 'Refreshing...' : 'Refresh Status'}
        </button>
      </header>

      <div className="glass rounded-[2rem] p-6 border border-white/10 grid grid-cols-1 md:grid-cols-4 gap-4">
        <div>
          <p className="text-[10px] uppercase tracking-widest text-white/40">OAuth</p>
          <p className="text-sm font-bold mt-1">{status.oauth_configured ? 'Configured' : 'Missing'}</p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-widest text-white/40">Connection</p>
          <p className="text-sm font-bold mt-1">{status.connected ? 'Connected' : 'Not connected'}</p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-widest text-white/40">Receipt Wrangler</p>
          <p className="text-sm font-bold mt-1">{status.receipt_wrangler_configured ? 'Configured' : 'Missing'}</p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-widest text-white/40">Processed</p>
          <p className="text-sm font-bold mt-1">{Number(status.processed_message_count || 0)}</p>
        </div>
      </div>

      <div className="glass rounded-[2rem] p-6 border border-white/10 grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="space-y-2">
          <label className="text-xs font-bold text-white/50 tracking-wider">Preset</label>
          <select
            value={preset}
            onChange={(event) => setPreset(event.target.value)}
            className="w-full bg-white/5 border border-white/10 rounded-2xl px-4 py-3 text-sm text-white focus:outline-none"
          >
            <option className="bg-black text-white" value="default">Default</option>
            <option className="bg-black text-white" value="orders">Orders</option>
            <option className="bg-black text-white" value="invoices">Invoices</option>
            <option className="bg-black text-white" value="wide">Wide</option>
          </select>
        </div>
        <div className="space-y-2">
          <label className="text-xs font-bold text-white/50 tracking-wider">Max Results</label>
          <input
            type="number"
            min={1}
            max={100}
            value={maxResults}
            onChange={(event) => setMaxResults(Number(event.target.value) || 25)}
            className="w-full bg-white/5 border border-white/10 rounded-2xl px-4 py-3 text-sm text-white focus:outline-none"
          />
        </div>
        <div className="md:col-span-2 flex flex-wrap items-end gap-3">
          <button
            type="button"
            onClick={() => void searchMessages()}
            className="btn-apple rounded-xl px-4 py-3 text-[10px] font-black uppercase tracking-widest"
          >
            {loadingMessages ? 'Searching...' : 'Search Gmail'}
          </button>
          <button
            type="button"
            onClick={() => {
              if (selectedMessageIds.length === messages.length) {
                setSelectedMessageIds([]);
              } else {
                setSelectedMessageIds(messages.map((message) => message.message_id));
              }
            }}
            className="bg-white/5 hover:bg-white/10 rounded-xl px-4 py-3 text-[10px] font-black uppercase tracking-widest"
          >
            {selectedCount === messages.length && messages.length > 0 ? 'Unselect All' : 'Select All'}
          </button>
          <span className="text-[10px] text-white/50 uppercase tracking-widest self-center">Selected: {selectedCount}</span>
        </div>
      </div>

      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={() => void withSelection('/api/gmail/ingest-direct', 'Direct ingestion started', { mark_processed: true })}
          className="bg-blue-600 hover:bg-blue-500 rounded-xl px-4 py-3 text-[10px] font-black uppercase tracking-widest"
        >
          Ingest Selected Direct
        </button>
        <button
          type="button"
          onClick={() => void withSelection('/api/gmail/receipt-wrangler-sync', 'Synced selected to Receipt Wrangler')}
          className="bg-emerald-600 hover:bg-emerald-500 rounded-xl px-4 py-3 text-[10px] font-black uppercase tracking-widest"
        >
          Sync Selected to Receipt Wrangler
        </button>
        <button
          type="button"
          onClick={() => void withSelection('/api/gmail/mark-processed', 'Marked selected as processed')}
          className="bg-white/10 hover:bg-white/20 rounded-xl px-4 py-3 text-[10px] font-black uppercase tracking-widest"
        >
          Mark Selected Processed
        </button>
      </div>

      <div className="space-y-3">
        {sortedMessages.map((message) => {
          const isSelected = selectedMessageIds.includes(message.message_id);
          return (
            <label
              key={message.message_id}
              className={`glass rounded-2xl border px-5 py-4 flex items-start gap-4 cursor-pointer transition-all ${
                isSelected ? 'border-blue-500/50 bg-blue-500/10' : 'border-white/10 hover:border-white/20'
              }`}
            >
              <input
                type="checkbox"
                checked={isSelected}
                onChange={(event) => {
                  if (event.target.checked) {
                    setSelectedMessageIds((prev) => [...prev, message.message_id]);
                  } else {
                    setSelectedMessageIds((prev) => prev.filter((id) => id !== message.message_id));
                  }
                }}
                className="mt-1"
              />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-bold truncate">{message.subject || 'No subject'}</p>
                <p className="text-xs text-white/50 truncate mt-1">{message.from || 'Unknown sender'}</p>
                <p className="text-[10px] text-white/40 uppercase tracking-widest mt-2">
                  {message.sent_at ? new Date(message.sent_at).toLocaleString() : 'No date'}
                  {message.has_attachments ? ' · Attachment' : ''}
                </p>
              </div>
            </label>
          );
        })}
        {messages.length === 0 && (
          <div className="glass p-8 rounded-[2rem] border border-white/10 text-center text-sm text-white/40">
            No receipt messages loaded yet. Use Search Gmail to fetch candidate receipts.
          </div>
        )}
      </div>
    </div>
  );
}
