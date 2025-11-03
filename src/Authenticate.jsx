import React, { useEffect, useState } from "react";
import useAuth from "./hooks/useAuth";

export default function Authenticate() {
  const {
    address,
    session,
    isAuthenticated,
    loading,
    error,
    begin,
    verify,
    me,
    logout,
    setAddress,
  } = useAuth();

  const [addrInput, setAddrInput] = useState("");
  const [codeInput, setCodeInput] = useState("");
  const [claimInfo, setClaimInfo] = useState(null);

  useEffect(() => {
    // try to fetch identity on mount (if cookie already set)
    me().catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onBegin = async () => {
    const addr = addrInput.trim();
    if (!addr) return;
    setAddress(addr);
    const info = await begin(addr);
    setClaimInfo(info);
  };

  const onVerify = async () => {
    const ok = await verify(codeInput.trim());
    if (ok) {
      setCodeInput("");
    }
  };

  return (
    <div className="max-w-lg mx-auto p-6">
      <h1 className="text-2xl font-bold mb-2">Authenticate with Zcash</h1>
      <p className="text-gray-600 mb-6">
        Enter your Zcash address, click "Request Code" to get a one-time code sent to your wallet's encrypted memo. Then paste the code below to verify.
      </p>

      {/* Address input */}
      <label className="block text-sm font-medium text-gray-700 mb-1">Zcash Address</label>
      <input
        className="w-full border rounded px-3 py-2 mb-3"
        placeholder="u1..."
        value={addrInput}
        onChange={(e) => setAddrInput(e.target.value)}
      />

      <div className="flex items-center gap-3 mb-4">
        <button
          onClick={onBegin}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded"
          disabled={loading}
        >
          Request Code
        </button>
        <button
          onClick={() => me()}
          className="bg-gray-100 hover:bg-gray-200 text-gray-800 px-3 py-2 rounded border"
        >
          Check Identity
        </button>
        <button
          onClick={logout}
          className="bg-gray-100 hover:bg-gray-200 text-gray-800 px-3 py-2 rounded border"
        >
          Logout
        </button>
      </div>

      {claimInfo && (
        <div className="mb-4 text-sm text-gray-700">
          <div>Session ID: <span className="font-mono">{claimInfo.session}</span></div>
          <div>Expiry Time: {claimInfo.expiry}</div>
          <div className="mt-2 text-gray-500">
            Note: In dev mode, you can find the OTP code in <code>logs/audit.log</code> under
          </div>
        </div>
      )}

      {/* Code input */}
      <label className="block text-sm font-medium text-gray-700 mb-1">OTP Code</label>
      <input
        className="w-full border rounded px-3 py-2 mb-3"
        placeholder="Enter OTP from wallet memo"
        value={codeInput}
        onChange={(e) => setCodeInput(e.target.value)}
      />

      <button
        onClick={onVerify}
        className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded"
        disabled={loading || !codeInput.trim()}
      >
        Verify OTP
      </button>

      {/* Status */}
      <div className="mt-6">
        <div className="text-sm">
          Status: {loading ? (
            <span className="text-gray-500">Processing...</span>
          ) : isAuthenticated ? (
            <span className="text-green-700">Authenticated</span>
          ) : (
            <span className="text-gray-700">Not Authenticated</span>
          )}
        </div>
        <div className="mt-1 text-sm">Current Address：<span className="font-mono">{address || "(None)"}</span></div>
        {error && <div className="mt-2 text-red-600 text-sm">Error：{String(error)}</div>}
      </div>

      <div className="mt-8 text-sm text-gray-600">
        Need to view Bob's received Memo? Go to the <a href="/messages" className="text-blue-600 underline">Latest Messages</a> page.
      </div>
    </div>
  );
}
