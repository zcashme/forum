import React, { useEffect, useRef, useState } from "react";
import { supabase } from "./supabase";

const SCAN_ADDR = import.meta.env.VITE_SCAN_ADDR || "u1qzt502u9fwh67s7an0e202c35mm0h534jaa648t4p2r6mhf30guxjjqwlkmvthahnz5myz2ev7neff5pmveh54xszv9njcmu5g2eent82ucpd3lwyzkmyrn6rytwsqefk475hl5tl4tu8yehc0z8w9fcf4zg6r03sq7lldx0uxph7c0lclnlc4qjwhu2v52dkvuntxr8tmpug3jntvm";

function extractPlainText(s) {
  if (!s) return "";
  if (s.startsWith("Memo::Text(")) {
    const start = s.indexOf("(\"");
    const end = s.lastIndexOf("\")");
    if (start !== -1 && end !== -1 && end > start + 2) {
      const inner = s.slice(start + 2, end);
      return inner.replace(/\\\"/g, '"');
    }
    // Fallback: strip the prefix
    return s.replace(/^Memo::Text\(/, "").replace(/\)$/g, "").replace(/^[\"']|[\"']$/g, "");
  }
  return ""; // for Memo::Empty or other variants
}

function formatTs(ts) {
  try { return new Date(ts).toLocaleString(); } catch { return ts; }
}

export default function AnonymousBoard() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const timerRef = useRef(null);

  async function loadMessages() {
    setLoading(true);
    setError("");
    try {
      const schema = import.meta.env.VITE_SUPABASE_SCHEMA || "zda";
      const table = import.meta.env.VITE_MEMO_TABLE || "zecbook";
      const fromArg = supabase.schema ? table : `${schema}.${table}`;
      const client = supabase.schema ? supabase.schema(schema) : supabase;

      const { data, error } = await client
        .from(fromArg)
        .select("ts, memo_text, to_address, txid")
        .order("ts", { ascending: false })
        .limit(500);
      if (error) throw error;

      const rows = Array.isArray(data) ? data : [];
      // Map to plain text; include empties so counts match DB
      const mapped = rows.map((r) => ({
        ...r,
        plain: extractPlainText(r.memo_text) || "(empty memo)",
      }));
      setItems(mapped);
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadMessages();
    timerRef.current = setInterval(loadMessages, 15000);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, []);

  return (
    <div className="p-4 max-w-3xl mx-auto">
      <h1 className="text-xl font-semibold mb-2">Anonymous Message Board</h1>
      <p className="text-sm text-gray-700 mb-3">
        Send a transaction with a memo to address:
        <span className="font-mono ml-1">{SCAN_ADDR || "(set VITE_SCAN_ADDR)"}</span>.
        This page shows all records from the database in plain text.
      </p>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 p-2 rounded mb-3">
          {error}
        </div>
      )}

      {loading && (
        <div className="text-gray-600 mb-2">Loading…</div>
      )}

      <ul className="space-y-3">
        {items.map((m, idx) => (
          <li key={`${m.txid}-${idx}`} className="border rounded p-2 bg-white">
            <div className="flex items-center justify-between text-xs text-gray-600 mb-1">
              <span>{formatTs(m.ts)}</span>
              <span className="font-mono">{(m.to_address || "").slice(0, 16)}…</span>
            </div>
            <pre className="text-sm text-gray-800 whitespace-pre-wrap break-words">{m.plain}</pre>
          </li>
        ))}
        {items.length === 0 && !loading && (
          <div className="text-gray-600">No messages yet.</div>
        )}
      </ul>
    </div>
  );
}