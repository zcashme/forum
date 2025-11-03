import React, { useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_DEVTOOL_API_BASE || "http://127.0.0.1:9011";
const ADDR = import.meta.env.VITE_SCAN_ADDR || "";

function fmtTs(ts) {
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

function TxRow({ o }) {
  const dir = o.incoming ? "IN" : "OUT";
  const memo = o.memo_text || (o.memo_hex ? "(undecodable memo)" : "");
  return (
    <tr className="border-b">
      <td className="px-2 py-1 text-xs text-gray-700 font-mono truncate" title={o.txid}>{o.txid}</td>
      <td className="px-2 py-1 text-xs text-gray-600">{fmtTs(o.ts)}</td>
      <td className="px-2 py-1 text-xs text-gray-600">{o.height ?? "-"}</td>
      <td className="px-2 py-1 text-xs">{o.amount} ZEC</td>
      <td className="px-2 py-1 text-xs">
        <span className={`inline-block px-2 py-0.5 rounded border text-[11px] ${o.incoming ? "bg-green-50 border-green-300 text-green-700" : "bg-blue-50 border-blue-300 text-blue-700"}`}>{dir}</span>
      </td>
      <td className="px-2 py-1 text-xs break-all font-mono">{o.to_address || ""}</td>
      <td className="px-2 py-1 text-xs break-words">{memo}</td>
    </tr>
  );
}

export default function AccountTransactions() {
  const [outputs, setOutputs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [minZec, setMinZec] = useState(0);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const url = `${API_BASE}/list-all?addr=${encodeURIComponent(ADDR)}&min=${minZec}`;
      const res = await fetch(url);
      const j = await res.json();
      if (!j.ok) throw new Error(j.error || "adapter_error");
      const outs = Array.isArray(j.outputs) ? j.outputs : [];
      setOutputs(outs);
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [minZec]);

  const incomingCount = outputs.filter((o) => o.incoming).length;
  const outgoingCount = outputs.length - incomingCount;

  return (
    <div className="p-4 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-3">
        <h1 className="text-xl font-semibold">Account Transactions</h1>
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-600">Min ZEC</label>
          <input
            type="number"
            value={minZec}
            min={0}
            step={0.0001}
            onChange={(e) => setMinZec(parseFloat(e.target.value || "0"))}
            className="border rounded px-2 py-1 w-28"
          />
          <button
            onClick={load}
            className="bg-blue-600 text-white rounded px-3 py-1"
            disabled={loading}
          >
            {loading ? "Loading..." : "Refresh"}
          </button>
        </div>
      </div>

      <div className="text-xs text-gray-700 mb-2">
        Address: <span className="font-mono break-all">{ADDR || "(not set)"}</span>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 p-2 rounded mb-3 text-sm">
          {error}
        </div>
      )}

      <div className="flex items-center gap-3 text-sm text-gray-700 mb-2">
        <span>Total outputs: {outputs.length}</span>
        <span>Incoming: {incomingCount}</span>
        <span>Outgoing: {outgoingCount}</span>
      </div>

      <div className="overflow-x-auto border rounded">
        <table className="min-w-full text-left">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-2 py-1 text-xs">TXID</th>
              <th className="px-2 py-1 text-xs">Time</th>
              <th className="px-2 py-1 text-xs">Height</th>
              <th className="px-2 py-1 text-xs">Amount</th>
              <th className="px-2 py-1 text-xs">Dir</th>
              <th className="px-2 py-1 text-xs">To Address</th>
              <th className="px-2 py-1 text-xs">Memo</th>
            </tr>
          </thead>
          <tbody>
            {outputs.map((o) => (
              <TxRow key={`${o.txid}-${o.to_address}-${o.memo_hex || "nomemo"}`} o={o} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}