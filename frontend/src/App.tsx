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
      .get("http://localhost:8000/merchants")
      .then((res) => setMerchants(res.data));
  }, []);

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Merchant Overview</h1>
        <button
          onClick={() => {
            axios
              .post("http://localhost:8000/refresh")
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
                  <Link to={`/merchant/${m.merchant_id}`}>{m.merchant_id}</Link>
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
      .get("http://localhost:8000/webhooks/recent")
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

  useEffect(() => {
    axios
      .get(`http://localhost:8000/merchants/${id}/timeline`)
      .then((res) => setTimeline(res.data));
    axios
      .get(`http://localhost:8000/merchants/${id}/flags`)
      .then((res) => setFlags(res.data));
  }, [id]);

  if (!timeline || !flags) return <div className="p-8">Loading...</div>;

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-8">
      <div>
        <Link
          to="/"
          className="text-blue-600 hover:underline mb-2 inline-block"
        >
          &larr; Back to Overview
        </Link>
        <h1 className="text-3xl font-bold">{id} Risk Detail</h1>
      </div>

      <div className="bg-white p-6 rounded-lg shadow border border-gray-200">
        <h2 className="text-lg font-bold mb-4">
          Volume & Ticket Size Timeline
        </h2>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={timeline.timeline}>
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
              />
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="ticket_size"
                stroke="#10b981"
                dot={false}
                name="Avg Ticket Size (₹)"
              />
              {timeline.flagged_windows.map((fw: any, idx: number) => (
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
          Flagged Anomalies (Stage 2 Isolation Forest)
        </h2>
        <div className="mb-6 bg-red-50 p-4 rounded text-red-900 border border-red-100">
          <h3 className="font-bold mb-2">Stage 1 Audit Log:</h3>
          <ul className="list-disc pl-5 space-y-1 text-sm">
            {flags.audit_log.slice(0, 10).map((log: string, i: number) => (
              <li key={i}>{log}</li>
            ))}
            {flags.audit_log.length > 10 && (
              <li>...and {flags.audit_log.length - 10} more regime breaks</li>
            )}
          </ul>
        </div>

        <table className="w-full text-left border-collapse text-sm">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="p-3 font-medium">Transaction ID</th>
              <th className="p-3 font-medium">Window</th>
              <th className="p-3 font-medium">Isolation Score</th>
              <th className="p-3 font-medium">Reason (Feature Drivers)</th>
            </tr>
          </thead>
          <tbody>
            {flags.flagged_transactions.slice(0, 50).map((txn: any) => (
              <tr key={txn.transaction_id} className="border-b border-gray-100">
                <td className="p-3 font-mono text-xs">{txn.transaction_id}</td>
                <td className="p-3">{new Date(txn.window).toLocaleString()}</td>
                <td className="p-3 font-medium text-red-600">
                  {txn.score.toFixed(3)}
                </td>
                <td className="p-3 text-gray-700">
                  {txn.reason || "Unknown anomaly"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {flags.flagged_transactions.length > 50 && (
          <div className="text-center p-4 text-gray-500 text-sm">
            Showing 50 of {flags.flagged_transactions.length} transactions
          </div>
        )}
      </div>
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
