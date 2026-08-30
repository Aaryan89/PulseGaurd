import React, { useEffect, useState } from "react";
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Link,
  useParams,
} from "react-router-dom";
import axios from "axios";
import { Activity, ShieldAlert, ShieldCheck, Settings } from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceArea,
} from "recharts";
import { CostDashboard } from "./pages/CostDashboard";

const Navbar = () => (
  <nav className="bg-slate-900 text-white p-4">
    <div className="max-w-6xl mx-auto flex justify-between items-center">
      <div className="flex items-center space-x-2">
        <ShieldCheck className="w-6 h-6 text-blue-400" />
        <span className="text-xl font-bold">PulseGuard</span>
      </div>
      <div className="flex space-x-6">
        <Link to="/" className="hover:text-blue-300">
          Merchants
        </Link>
        <Link to="/cost" className="hover:text-blue-300">
          Cost Curve
        </Link>
      </div>
    </div>
  </nav>
);

const MerchantList = () => {
  const [merchants, setMerchants] = useState<any[]>([]);

  useEffect(() => {
    axios
      .get("/api/merchants")
      .then((res) => setMerchants(res.data));
  }, []);

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Merchant Overview</h1>
        <button
          onClick={() => {
            axios
              .post("/api/refresh")
              .then(() =>
                alert(
                  "Pipeline refreshing in background. Reload page in a few seconds.",
                ),
              );
          }}
          className="bg-blue-600 text-white px-4 py-2 rounded shadow hover:bg-blue-700"
        >
          Refresh Synthetic Data
        </button>
      </div>

      <div className="bg-white rounded-lg shadow border border-gray-200 overflow-hidden mb-8">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200 text-gray-600 text-sm">
              <th className="p-4 font-medium">Merchant ID</th>
              <th className="p-4 font-medium">Risk Status</th>
              <th className="p-4 font-medium">Total Txns</th>
              <th className="p-4 font-medium">Flagged Windows</th>
              <th className="p-4 font-medium">Last Flag</th>
            </tr>
          </thead>
          <tbody>
            {merchants.map((m) => (
              <tr
                key={m.merchant_id}
                className="border-b border-gray-100 hover:bg-gray-50"
              >
                <td className="p-4 text-blue-600 font-medium">
                  <div className="flex items-center space-x-2">
                    <Link to={`/merchant/${m.merchant_id}`}>{m.merchant_id}</Link>
                    {m.is_new && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-purple-100 text-purple-700 uppercase">
                        Cold Start
                      </span>
                    )}
                  </div>
                </td>
                <td className="p-4">
                  {m.status === "normal" && (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                      Normal
                    </span>
                  )}
                  {m.status === "watch" && (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                      Watch
                    </span>
                  )}
                  {m.status === "flagged" && (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                      Flagged
                    </span>
                  )}
                </td>
                <td className="p-4 text-gray-600">{m.total_transactions}</td>
                <td className="p-4 text-gray-600">{m.flagged_windows}</td>
                <td className="p-4 text-gray-500 text-sm">
                  {m.last_flag ? new Date(m.last_flag).toLocaleString() : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <RecentActions />
    </div>
  );
};

const RecentActions = () => {
  const [actions, setActions] = useState<any[]>([]);

  useEffect(() => {
    axios
      .get("/api/webhooks/recent")
      .then((res) => setActions(res.data));
    // Optional: could poll every few seconds, but since refresh is manual, once on load is fine.
  }, []);

  if (actions.length === 0) return null;

  return (
    <div className="bg-white rounded-lg shadow border border-gray-200 overflow-hidden">
      <div className="bg-slate-50 border-b border-gray-200 p-4">
        <h2 className="text-lg font-bold text-slate-800">
          Recent Actions Taken (Auto-Responder Webhooks)
        </h2>
      </div>
      <div className="p-4">
        <div className="space-y-4">
          {actions.map((action, idx) => (
            <div
              key={idx}
              className="border border-gray-100 bg-gray-50 p-4 rounded-md flex items-start justify-between"
            >
              <div>
                <div className="flex items-center space-x-2 mb-1">
                  <span
                    className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold ${
                      action.tier === "block"
                        ? "bg-red-100 text-red-800"
                        : "bg-orange-100 text-orange-800"
                    }`}
                  >
                    {action.tier.toUpperCase()}
                  </span>
                  <span className="font-mono text-sm text-gray-600">
                    {action.transaction_id}
                  </span>
                  <span className="text-sm text-gray-500">
                    ({action.merchant_id})
                  </span>
                </div>
                <p className="text-sm text-gray-700">{action.reason}</p>
              </div>
              <div className="text-right text-xs text-gray-400">
                {new Date(action.fired_at).toLocaleTimeString()}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

const MerchantDetail = () => {
  const { id } = useParams();
  const [timeline, setTimeline] = useState<any>(null);
  const [flags, setFlags] = useState<any>(null);
  const [webhooks, setWebhooks] = useState<any[]>([]);

  // Replay State
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [currentTimeIndex, setCurrentTimeIndex] = useState(-1);

  useEffect(() => {
    axios
      .get(`/api/merchants/${id}/timeline`)
      .then((res) => setTimeline(res.data));
    axios
      .get(`/api/merchants/${id}/flags`)
      .then((res) => setFlags(res.data));
    axios
      .get(`/api/webhooks/recent`)
      .then((res) => setWebhooks(res.data.filter((w: any) => w.merchant_id === id)));
  }, [id]);

  useEffect(() => {
    if (!isPlaying || !timeline?.timeline) return;

    const fullTimeline = timeline.timeline;
    const interval = setInterval(() => {
      setCurrentTimeIndex((prev) => {
        // If starting fresh
        if (prev === -1) return 0;
        // If reached end
        if (prev >= fullTimeline.length - 1) {
          setIsPlaying(false);
          return prev;
        }
        return prev + 1;
      });
    }, 1000 / playbackSpeed);

    return () => clearInterval(interval);
  }, [isPlaying, playbackSpeed, timeline]);

  if (!timeline || !flags) return <div className="p-8">Loading...</div>;

  const fullTimeline = timeline.timeline;
  const effectiveIndex = currentTimeIndex === -1 ? fullTimeline.length - 1 : currentTimeIndex;
  const currentTimestampStr = fullTimeline[effectiveIndex]?.timestamp;
  const currentTimestamp = new Date(currentTimestampStr).getTime();

  // Filter Data based on Replay Time
  const displayTimeline = fullTimeline.slice(0, effectiveIndex + 1);
  const displayWindows = timeline.flagged_windows.filter(
    (fw: any) => new Date(fw.timestamp).getTime() <= currentTimestamp
  );
  const displayAuditLog = flags.audit_log.filter((log: string) => {
    const match = log.match(/at (.*)$/);
    if (match) {
      return new Date(match[1]).getTime() <= currentTimestamp;
    }
    return true;
  });
  const displayTransactions = flags.flagged_transactions.filter(
    (txn: any) => new Date(txn.window).getTime() <= currentTimestamp
  );
  
  // Find webhooks matching the displayed transactions
  const displayTxnIds = new Set(displayTransactions.map((t: any) => t.transaction_id));
  const displayWebhooks = webhooks.filter((w: any) => displayTxnIds.has(w.transaction_id));

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-8">
      <div>
        <Link
          to="/"
          className="text-blue-600 hover:underline mb-2 inline-block"
        >
          &larr; Back to Overview
        </Link>
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center space-x-4">
            <h1 className="text-3xl font-bold">{id} Risk Detail</h1>
            {timeline.is_new && (
              <div className="bg-purple-100 text-purple-800 px-3 py-1 rounded-full text-sm font-medium flex items-center shadow-sm">
                <span className="mr-2">Cold Start Mode ({timeline.tier} Prior)</span>
                <div className="w-16 h-2 bg-purple-200 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-purple-600" 
                    style={{ width: `${Math.max(5, timeline.blend_progress * 100)}%` }}
                  ></div>
                </div>
              </div>
            )}
          </div>
          
          {/* Replay Controls */}
          <div className="flex items-center space-x-4 bg-gray-100 px-4 py-2 rounded-lg shadow-inner">
            <div className="text-sm font-bold text-gray-700">Replay Mode:</div>
            <button
              onClick={() => {
                if (currentTimeIndex === fullTimeline.length - 1) {
                  setCurrentTimeIndex(0);
                }
                setIsPlaying(!isPlaying);
              }}
              className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1 rounded text-sm font-medium shadow"
            >
              {isPlaying ? "Pause" : "Play"}
            </button>
            <div className="flex items-center space-x-1 border border-gray-300 rounded overflow-hidden">
              {[1, 4, 10].map(speed => (
                <button
                  key={speed}
                  onClick={() => setPlaybackSpeed(speed)}
                  className={`px-2 py-1 text-xs font-bold ${playbackSpeed === speed ? 'bg-blue-100 text-blue-800' : 'bg-white text-gray-600 hover:bg-gray-50'}`}
                >
                  {speed}x
                </button>
              ))}
            </div>
            <button
              onClick={() => { setIsPlaying(false); setCurrentTimeIndex(-1); }}
              className="text-sm text-gray-500 hover:text-gray-800 font-medium ml-2"
            >
              Reset
            </button>
          </div>
        </div>
      </div>

      <div className="bg-white p-6 rounded-lg shadow border border-gray-200">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-bold">
            Volume & Ticket Size Timeline
          </h2>
          {currentTimeIndex !== -1 && (
            <div className="text-sm font-mono bg-blue-50 text-blue-800 px-2 py-1 rounded border border-blue-100">
              {new Date(currentTimestamp).toLocaleString()}
            </div>
          )}
        </div>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={displayTimeline}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="timestamp"
                tickFormatter={(val) =>
                  new Date(val).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })
                }
              />
              <YAxis yAxisId="left" />
              <YAxis yAxisId="right" orientation="right" />
              <Tooltip
                labelFormatter={(val) => new Date(val).toLocaleString()}
              />
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="volume"
                stroke="#3b82f6"
                dot={false}
                name="Volume (txns/hr)"
                isAnimationActive={false}
              />
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="ticket_size"
                stroke="#10b981"
                dot={false}
                name="Avg Ticket Size (₹)"
                isAnimationActive={false}
              />
              {displayWindows.map((fw: any, idx: number) => (
                <ReferenceArea
                  key={idx}
                  yAxisId="left"
                  x1={fw.timestamp}
                  x2={new Date(
                    new Date(fw.timestamp).getTime() + 3600000,
                  ).toISOString()} // 1 hour wide
                  fill="#ef4444"
                  fillOpacity={0.2}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="bg-white p-6 rounded-lg shadow border border-gray-200">
        <h2 className="text-lg font-bold mb-4">
          Flagged Anomalies & Webhooks
        </h2>
        {displayAuditLog.length > 0 && (
          <div className="mb-6 bg-red-50 p-4 rounded text-red-900 border border-red-100">
            <h3 className="font-bold mb-2">Stage 1 Audit Log:</h3>
            <ul className="list-disc pl-5 space-y-1 text-sm">
              {displayAuditLog.slice(-10).map((log: string, i: number) => (
                <li key={i}>{log}</li>
              ))}
            </ul>
          </div>
        )}

        <table className="w-full text-left border-collapse text-sm">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="p-3 font-medium">Transaction ID</th>
              <th className="p-3 font-medium">Window</th>
              <th className="p-3 font-medium">Isolation Score</th>
              <th className="p-3 font-medium">Action Tier</th>
              <th className="p-3 font-medium">Reason (Feature Drivers)</th>
            </tr>
          </thead>
          <tbody>
            {displayTransactions.slice(0, 50).map((txn: any) => {
              const webhook = displayWebhooks.find(w => w.transaction_id === txn.transaction_id);
              const tier = webhook ? webhook.tier : "allow";
              return (
                <tr key={txn.transaction_id} className={`border-b border-gray-100 ${webhook ? 'bg-orange-50' : ''}`}>
                  <td className="p-3 font-mono text-xs">{txn.transaction_id}</td>
                  <td className="p-3">{new Date(txn.window).toLocaleString()}</td>
                  <td className="p-3 font-medium text-red-600">
                    {txn.score.toFixed(3)}
                  </td>
                  <td className="p-3">
                    {tier === 'block' && <span className="bg-red-100 text-red-800 px-2 py-0.5 rounded text-xs font-bold uppercase">Block</span>}
                    {tier === 'review' && <span className="bg-yellow-100 text-yellow-800 px-2 py-0.5 rounded text-xs font-bold uppercase">Review</span>}
                    {tier === 'allow' && <span className="text-gray-400 text-xs">Allow</span>}
                  </td>
                  <td className="p-3 text-gray-700">
                    {txn.reason || "Unknown anomaly"}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        {displayTransactions.length === 0 && (
          <div className="text-center p-8 text-gray-500">
            No transactions flagged yet.
          </div>
        )}
      </div>

      {displayWebhooks.length > 0 && (
        <div className="bg-white rounded-lg shadow border border-gray-200 overflow-hidden">
          <div className="bg-slate-50 border-b border-gray-200 p-4 flex justify-between items-center">
            <h2 className="text-lg font-bold text-slate-800">
              Auto-Responder Webhooks Sent
            </h2>
            <span className="bg-blue-100 text-blue-800 text-xs font-bold px-2 py-1 rounded-full">
              {displayWebhooks.length} Actions
            </span>
          </div>
          <div className="p-4 space-y-4">
            {displayWebhooks.map((action: any, idx: number) => (
              <div
                key={idx}
                className="border border-gray-100 bg-gray-50 p-4 rounded-md flex items-start justify-between"
              >
                <div>
                  <div className="flex items-center space-x-2 mb-1">
                    <span
                      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold ${
                        action.tier === "block"
                          ? "bg-red-100 text-red-800"
                          : "bg-orange-100 text-orange-800"
                      }`}
                    >
                      {action.tier.toUpperCase()}
                    </span>
                    <span className="font-mono text-sm text-gray-600">
                      {action.transaction_id}
                    </span>
                  </div>
                  <p className="text-sm text-gray-700">{action.reason}</p>
                </div>
                <div className="text-right text-xs font-mono text-gray-400">
                  SENT: {new Date(action.fired_at).toLocaleTimeString()}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default function App() {
  return (
    <Router>
      <div className="min-h-screen bg-gray-50 flex flex-col">
        <Navbar />
        <main className="flex-1">
          <Routes>
            <Route path="/" element={<MerchantList />} />
            <Route path="/merchant/:id" element={<MerchantDetail />} />
            <Route path="/cost" element={<CostDashboard />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}
