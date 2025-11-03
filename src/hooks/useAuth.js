import { useCallback, useEffect, useMemo, useRef, useState } from "react";

// Simple auth hook for PoC
// - begin(address): POST /claim to get a session and send OTP memo
// - verify(code): POST /verify-code with { address, code, session } and store cookie
// - me(): GET /me (uses cookie)
// - logout(): POST /logout
export default function useAuth() {
  const API_BASE = import.meta.env.VITE_AUTH_API_BASE || "http://127.0.0.1:8000";

  const [address, setAddress] = useState("");
  const [session, setSession] = useState("");
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const controllerRef = useRef(null);

  useEffect(() => {
    return () => {
      if (controllerRef.current) controllerRef.current.abort();
    };
  }, []);

  const begin = useCallback(async (addr) => {
    setError("");
    setLoading(true);
    try {
      controllerRef.current = new AbortController();
      const res = await fetch(`${API_BASE}/claim`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ address: addr }),
        signal: controllerRef.current.signal,
      });
      if (!res.ok) {
        const data = await safeJson(res);
        throw new Error(data?.error || `claim_failed_${res.status}`);
      }
      const data = await res.json();
      setSession(data.session || "");
      return data;
    } catch (e) {
      setError(e?.message || "claim_failed");
      return null;
    } finally {
      setLoading(false);
    }
  }, [API_BASE]);

  const verify = useCallback(async (code) => {
    setError("");
    setLoading(true);
    try {
      if (!address) throw new Error("missing_address");
      if (!session) throw new Error("missing_session");
      controllerRef.current = new AbortController();
      const res = await fetch(`${API_BASE}/verify-code`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ address, code, session }),
        signal: controllerRef.current.signal,
      });
      const data = await safeJson(res);
      if (!res.ok || !data?.ok) {
        throw new Error(data?.error || `verify_failed_${res.status}`);
      }
      // Cookie is set by server; now fetch identity
      await me();
      setIsAuthenticated(true);
      return true;
    } catch (e) {
      setError(e?.message || "verify_failed");
      return false;
    } finally {
      setLoading(false);
    }
  }, [API_BASE, address, session]);

  const me = useCallback(async () => {
    try {
      controllerRef.current = new AbortController();
      const res = await fetch(`${API_BASE}/me`, {
        method: "GET",
        credentials: "include",
        signal: controllerRef.current.signal,
      });
      if (!res.ok) throw new Error("unauthorized");
      const data = await res.json();
      setAddress(data?.address || "");
      setIsAuthenticated(!!data?.address);
      return data?.address || "";
    } catch (e) {
      return "";
    }
  }, [API_BASE]);

  const logout = useCallback(async () => {
    try {
      controllerRef.current = new AbortController();
      await fetch(`${API_BASE}/logout`, {
        method: "POST",
        credentials: "include",
        signal: controllerRef.current.signal,
      });
    } catch {}
    setIsAuthenticated(false);
    setAddress("");
    setSession("");
  }, [API_BASE]);

  return useMemo(() => ({
    address,
    session,
    isAuthenticated,
    loading,
    error,
    begin,
    verify,
    me,
    logout,
    setAddress, // exposed for caller to set before verify
    setSession,
  }), [address, session, isAuthenticated, loading, error, begin, verify, me, logout]);
}

async function safeJson(res) {
  try { return await res.json(); } catch { return null; }
}