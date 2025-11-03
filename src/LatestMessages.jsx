import React, { useEffect, useRef, useState } from "react";
import { supabase } from "./supabase";

const API_BASE = import.meta.env.VITE_DEVTOOL_API_BASE || "http://127.0.0.1:9011";
const SCAN_ADDR = import.meta.env.VITE_SCAN_ADDR || "u1qzt502u9fwh67s7an0e202c35mm0h534jaa648t4p2r6mhf30guxjjqwlkmvthahnz5myz2ev7neff5pmveh54xszv9njcmu5g2eent82ucpd3lwyzkmyrn6rytwsqefk475hl5tl4tu8yehc0z8w9fcf4zg6r03sq7lldx0uxph7c0lclnlc4qjwhu2v52dkvuntxr8tmpug3jntvm";

function formatTs(ts) {
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

export default function LatestMessages() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [sinceSec, setSinceSec] = useState(600);
  const [minZec, setMinZec] = useState(0.0005);
  const [dirFilter, setDirFilter] = useState("all"); // all | in | out
  const timerRef = useRef(null);

  async function fetchMemos() {
    setLoading(true);
    setError("");
    try {
      const schema = import.meta.env.VITE_SUPABASE_SCHEMA || "zda";
      const table = import.meta.env.VITE_MEMO_TABLE || "zecbook";
      const fromArg = supabase.schema ? table : `${schema}.${table}`;
      const client = supabase.schema ? supabase.schema(schema) : supabase;
      const { data, error } = await client
        .from(fromArg)
        .select("txid, ts, amount, memo_hex, memo_text, to_address, height")
        .order("ts", { ascending: false })
        .limit(100);
      if (error) throw error;
      const cutoffMs = Date.now() - sinceSec * 1000;
      const rows = Array.isArray(data) ? data : [];
      const enriched = rows.map((d) => {
        const amt = typeof d.amount === "number" ? d.amount : parseFloat(d.amount || "0");
        const incoming = !!SCAN_ADDR && d.to_address === SCAN_ADDR;
        return { ...d, amount: amt, incoming };
      });
      const filtered = enriched.filter((d) => {
        const t = Date.parse(d.ts);
        const timeOk = isNaN(t) ? true : t >= cutoffMs;
        const amtOk = isNaN(d.amount) ? true : d.amount >= minZec;
        const dirOk = dirFilter === "all" ? true : (dirFilter === "in" ? d.incoming : !d.incoming);
        return timeOk && amtOk && dirOk;
      });
      setItems(filtered);
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }

  async function scanNow() {
    setLoading(true);
    setError("");
    try {
      // Persist both directions to Supabase via adapter list-all
      const url = `${API_BASE}/list-all?addr=${encodeURIComponent(SCAN_ADDR)}&since=${sinceSec}&min=${minZec}&persist=1&persist_mode=all`;
      const res = await fetch(url);
      const j = await res.json();
      if (!j.ok) throw new Error(j.error || "scan_failed");
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      await fetchMemos();
      setLoading(false);
    }
  }

  useEffect(() => {
    // First load
    fetchMemos();
    // Poll every 15s
    timerRef.current = setInterval(fetchMemos, 15000);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [sinceSec, minZec, dirFilter]);

  return (
    <div className="p-4 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-semibold">Latest Messages</h1>
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-600">Scan window (sec)</label>
          <input
            type="number"
            value={sinceSec}
            min={60}
            step={60}
            onChange={(e) => setSinceSec(parseInt(e.target.value || "600", 10))}
            className="border rounded px-2 py-1 w-28"
          />
          <label className="text-sm text-gray-600 ml-2">Min ZEC</label>
          <input
            type="number"
            value={minZec}
            min={0}
            step={0.0001}
            onChange={(e) => setMinZec(parseFloat(e.target.value || "0.0005"))}
            className="border rounded px-2 py-1 w-24"
          />
          <div className="ml-2 flex items-center gap-1">
            <span className="text-sm text-gray-600">Direction</span>
            <select
              value={dirFilter}
              onChange={(e) => setDirFilter(e.target.value)}
              className="border rounded px-2 py-1"
            >
              <option value="all">All</option>
              <option value="in">Incoming</option>
              <option value="out">Outgoing</option>
            </select>
          </div>
          <button
            onClick={fetchMemos}
            className="bg-blue-600 text-white rounded px-3 py-1"
            disabled={loading}
          >
            {loading ? "Refreshing..." : "Refresh"}
          </button>
          <button
            onClick={scanNow}
            className="bg-green-600 text-white rounded px-3 py-1"
            disabled={loading}
          >
            {loading ? "Scanning..." : "Scan Now"}
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 p-2 rounded mb-3">
          {error}
        </div>
      )}

      {items.length === 0 && !loading && (
        <div className="text-gray-600">No memos found in window.</div>
      )}

      <ul className="space-y-3">
        {items.map((m) => (
          <li key={`${m.txid}-${(m.memo_hex || "").slice(0,8)}`} className="border rounded p-3">
            <div className="flex items-center justify-between">
              <div className="text-sm text-gray-600">{formatTs(m.ts)}</div>
              <div className="text-xs px-2 py-0.5 rounded bg-gray-100 border">
                {m.amount} ZEC {m.incoming ? "IN" : "OUT"}
              </div>
            </div>
            <div className="mt-1 text-sm">
              <span className="font-mono text-gray-700">{m.txid}</span>
            </div>
            <div className="mt-1 text-xs text-gray-600 break-all">
              To: <span className="font-mono">{m.to_address || "(unknown)"}</span>
            </div>
            <div className="mt-2 text-sm text-gray-800 whitespace-pre-wrap break-words">
              {m.memo_text || "(memo undecodable)"}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}