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
  <nav className="bg-pg-bg border-b border-pg-border text-pg-text p-4">
    <div className="max-w-6xl mx-auto flex justify-between items-center">
      <div className="flex items-center space-x-3">
        <ShieldCheck className="w-5 h-5 text-pg-cyan" />
        <span className="text-xl font-bold tracking-tight">PULSEGUARD</span>
      </div>
      <div className="flex space-x-6 text-sm font-medium">
        <Link to="/" className="text-pg-muted hover:text-pg-text transition-colors">
          MERCHANTS
        </Link>
        <Link to="/cost" className="text-pg-muted hover:text-pg-text transition-colors">
          COST CURVE
        </Link>
      </div>
    </div>
  </nav>
);

const MerchantList = () => {
  const [merchants, setMerchants] = useState<any[]>([]);
  const [razorpayError, setRazorpayError] = useState<string | null>(null);
  const [isFiring, setIsFiring] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  useEffect(() => {
    axios
      .get("/api/merchants")
      .then((res) => setMerchants(res.data));
  }, []);

  const handleFireLiveTxn = async () => {
    try {
      setRazorpayError(null);
      const amount = prompt("Enter test amount (in paise):", "150000");
      if (!amount) return;
      
      setIsFiring(true);
      const { data: order } = await axios.post("/api/razorpay/create-test-order", { amount: parseInt(amount, 10) });
      
      const options = {
        key: order.key_id,
        amount: order.amount,
        currency: order.currency,
        name: "PulseGuard Demo",
        description: "Test Transaction",
        order_id: order.order_id,
        handler: async function (response: any) {
          try {
            const ingestRes = await axios.post("/api/razorpay/ingest-test-payment", {
              payment_id: response.razorpay_payment_id,
              merchant_id: "M_001"
            });
            if (ingestRes.data.flagged) {
               alert(`Transaction ingested! Flagged as anomaly. Score: ${ingestRes.data.score.toFixed(2)}`);
            } else {
               alert(`Transaction ingested! Passed normal. (Not flagged)`);
            }
            
            const merchantsRes = await axios.get("/api/merchants");
            setMerchants(merchantsRes.data);
          } catch (err: any) {
            setRazorpayError("Couldn't reach Razorpay to verify payment. Please check your network and try again.");
          } finally {
            setIsFiring(false);
          }
        },
        modal: {
            ondismiss: function() {
                setIsFiring(false);
            }
        },
        prefill: {
          name: "Demo User",
          email: "demo@pulseguard.test",
          contact: "9999999999"
        },
        theme: {
          color: "#38BDF8"
        }
      };
      const rzp = new (window as any).Razorpay(options);
      rzp.open();
    } catch (error: any) {
      setIsFiring(false);
      setRazorpayError("Couldn't reach Razorpay to create order. Please check your network and try again.");
    }
  };

  return (
    <div className="p-8 max-w-6xl mx-auto">
      {razorpayError && (
        <div className="mb-6 p-4 border border-pg-crimson/50 bg-pg-crimson/10 flex items-center justify-between font-mono text-sm">
          <div className="flex items-center text-pg-crimson">
            <ShieldAlert className="w-5 h-5 mr-3" />
            {razorpayError}
          </div>
          <button 
            onClick={handleFireLiveTxn} 
            className="px-3 py-1 bg-transparent border border-pg-crimson text-pg-crimson hover:bg-pg-crimson/20 transition-colors"
          >
            [RETRY]
          </button>
        </div>
      )}
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Risk Overview</h1>
        <div className="space-x-4">
          <button
            onClick={handleFireLiveTxn}
            disabled={isFiring}
            className={`bg-transparent border border-pg-cyan text-pg-cyan hover:bg-pg-cyan/10 px-4 py-2 text-sm font-mono transition-colors ${isFiring ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            {isFiring ? "[FIRING...]" : "[FIRE_LIVE_TXN]"}
          </button>
          <button
            onClick={() => {
              if (isRefreshing) return;
              setIsRefreshing(true);
              axios
                .post("/api/refresh")
                .then(() => {
                  alert(
                    "Pipeline refreshing in background. Reload page in a few seconds.",
                  );
                  setTimeout(() => setIsRefreshing(false), 5000);
                })
                .catch(() => setIsRefreshing(false));
            }}
            disabled={isRefreshing}
            className={`bg-transparent border border-pg-border text-pg-text hover:border-pg-cyan hover:text-pg-cyan px-4 py-2 text-sm font-mono transition-colors ${isRefreshing ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            {isRefreshing ? "[REFRESHING...]" : "[REFRESH_SYNTHETICS]"}
          </button>
        </div>
      </div>

      <div className="bg-pg-surface border border-pg-border mb-8">
        <table className="w-full text-left border-collapse font-mono text-sm">
          <thead>
            <tr className="border-b border-pg-border text-pg-muted bg-[#121820]">
              <th className="p-4 font-normal">MERCHANT_ID</th>
              <th className="p-4 font-normal">STATUS</th>
              <th className="p-4 font-normal">VOL_30D</th>
              <th className="p-4 font-normal">FLAGS</th>
              <th className="p-4 font-normal">LAST_EVENT</th>
            </tr>
          </thead>
          <tbody>
            {Array.isArray(merchants) && merchants.map((m) => (
              <tr
                key={m.merchant_id}
                className="border-b border-pg-border hover:bg-[#1C2531] transition-colors"
              >
                <td className="p-4 text-pg-cyan">
                  <div className="flex items-center space-x-2">
                    <Link to={`/merchant/${m.merchant_id}`} className="hover:underline">{m.merchant_id}</Link>
                    {m.is_new && (
                      <span className="inline-flex items-center px-1.5 py-0.5 text-[10px] bg-transparent border border-purple-500 text-purple-400">
                        COLD_START
                      </span>
                    )}
                  </div>
                </td>
                <td className="p-4">
                  {m.status === "normal" && (
                    <span className="inline-flex items-center px-2 py-0.5 text-xs text-pg-cyan border border-pg-cyan/30 bg-pg-cyan/10">
                      NORMAL
                    </span>
                  )}
                  {m.status === "watch" && (
                    <span className="inline-flex items-center px-2 py-0.5 text-xs text-pg-amber border border-pg-amber/30 bg-pg-amber/10">
                      REVIEW
                    </span>
                  )}
                  {m.status === "flagged" && (
                    <span className="inline-flex items-center px-2 py-0.5 text-xs text-pg-crimson border border-pg-crimson/30 bg-pg-crimson/10">
                      BLOCK
                    </span>
                  )}
                </td>
                <td className="p-4 text-pg-text">{m.total_transactions}</td>
                <td className="p-4 text-pg-text">{m.flagged_windows}</td>
                <td className="p-4 text-pg-muted text-xs">
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
  }, []);

  if (actions.length === 0) return null;

  return (
    <div className="bg-pg-surface border border-pg-border">
      <div className="border-b border-pg-border p-4 bg-[#121820]">
        <h2 className="text-sm font-mono text-pg-muted">
          RECENT_ACTIONS (AUTO_RESPONDER)
        </h2>
      </div>
      <div className="p-4 space-y-2">
        {Array.isArray(actions) && actions.map((action, idx) => (
          <div
            key={idx}
            className="border border-pg-border bg-pg-bg p-3 flex items-start justify-between font-mono text-sm"
          >
            <div>
              <div className="flex items-center space-x-3 mb-1">
                <span
                  className={`inline-flex items-center px-2 py-0.5 text-xs ${
                    action.tier === "block"
                      ? "text-pg-crimson border border-pg-crimson/30 bg-pg-crimson/10"
                      : "text-pg-amber border border-pg-amber/30 bg-pg-amber/10"
                  }`}
                >
                  {action.tier.toUpperCase()}
                </span>
                <span className="text-pg-text">{action.id}</span>
                <span className="text-pg-muted">({action.merchant_id})</span>
              </div>
              <p className="text-xs text-pg-muted font-sans mt-2">{action.reason}</p>
            </div>
            <div className="text-right text-xs text-pg-muted">
              {new Date(action.fired_at).toLocaleTimeString()}
            </div>
          </div>
        ))}
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

    // We'll just return the series data for the frontend to chart
    const fullTimeline = timeline.timeline;
    const effectiveIndex = currentTimeIndex === -1 ? fullTimeline.length - 1 : currentTimeIndex;
    const currentTimestampStr = fullTimeline[effectiveIndex]?.created_at;
    const currentTimestamp = new Date(currentTimestampStr).getTime();

    // Filter Data based on Replay Time
    const displayTimeline = fullTimeline.slice(0, effectiveIndex + 1).map((point: any) => ({
      ...point,
      ticket_size: point.ticket_size / 100.0
    }));
  const displayWindows = timeline.flagged_windows.filter(
    (fw: any) => new Date(fw.created_at).getTime() <= currentTimestamp
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
  const displayTxnIds = new Set(displayTransactions.map((t: any) => t.id));
  const displayWebhooks = webhooks.filter((w: any) => displayTxnIds.has(w.id));

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-6">
      <div>
        <Link
          to="/"
          className="text-pg-cyan hover:underline mb-4 inline-block text-sm font-mono"
        >
          &larr; BACK_TO_OVERVIEW
        </Link>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-4">
            <h1 className="text-2xl font-bold font-mono tracking-tight">{id}_RISK_DETAIL</h1>
            {timeline.is_new && (
              <div className="bg-transparent border border-purple-500 text-purple-400 px-2 py-0.5 text-xs font-mono flex items-center">
                <span className="mr-2">COLD_START_MODE ({timeline.tier.toUpperCase()})</span>
                <div className="w-16 h-1 bg-[#121820] overflow-hidden ml-2">
                  <div 
                    className="h-full bg-purple-500" 
                    style={{ width: `${Math.max(5, timeline.blend_progress * 100)}%` }}
                  ></div>
                </div>
              </div>
            )}
          </div>
          
          {/* Replay Controls */}
          <div className="flex items-center space-x-4 bg-pg-surface border border-pg-border px-4 py-2 font-mono text-sm">
            <div className="text-pg-muted">REPLAY_MODE:</div>
            <button
              onClick={() => {
                if (currentTimeIndex === fullTimeline.length - 1) {
                  setCurrentTimeIndex(0);
                }
                setIsPlaying(!isPlaying);
              }}
              className="bg-transparent border border-pg-cyan text-pg-cyan hover:bg-pg-cyan/10 px-3 py-1 transition-colors"
            >
              {isPlaying ? "[PAUSE]" : "[PLAY]"}
            </button>
            <div className="flex items-center space-x-1">
              {[1, 4, 10].map(speed => (
                <button
                  key={speed}
                  onClick={() => setPlaybackSpeed(speed)}
                  className={`px-2 py-1 text-xs border ${playbackSpeed === speed ? 'border-pg-cyan text-pg-cyan bg-pg-cyan/10' : 'border-pg-border text-pg-muted hover:text-pg-text'}`}
                >
                  {speed}X
                </button>
              ))}
            </div>
            <button
              onClick={() => { setIsPlaying(false); setCurrentTimeIndex(-1); }}
              className="text-pg-muted hover:text-pg-text ml-2"
            >
              [RESET]
            </button>
          </div>
        </div>
      </div>

      <div className="bg-pg-surface border border-pg-border">
        <div className="flex justify-between items-center p-4 border-b border-pg-border bg-[#121820]">
          <h2 className="text-sm font-mono text-pg-muted">
            VOLUME_AND_TICKET_SIZE
          </h2>
          {currentTimeIndex !== -1 && (
            <div className="text-xs font-mono text-pg-cyan bg-pg-cyan/10 border border-pg-cyan/30 px-2 py-0.5">
              T={new Date(currentTimestamp).toISOString()}
            </div>
          )}
        </div>
        <div className="h-72 p-4">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={displayTimeline}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2D3748" vertical={false} />
              <XAxis
                dataKey="created_at"
                stroke="#94A3B8"
                tick={{fill: '#94A3B8', fontSize: 12, fontFamily: 'JetBrains Mono'}}
                tickFormatter={(val) =>
                  new Date(val).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })
                }
              />
              <YAxis yAxisId="left" stroke="#94A3B8" tick={{fill: '#94A3B8', fontSize: 12, fontFamily: 'JetBrains Mono'}} />
              <YAxis yAxisId="right" orientation="right" stroke="#94A3B8" tick={{fill: '#94A3B8', fontSize: 12, fontFamily: 'JetBrains Mono'}} />
              <Tooltip
                contentStyle={{ backgroundColor: '#1A2027', borderColor: '#2D3748', color: '#E2E8F0', fontFamily: 'JetBrains Mono' }}
                labelFormatter={(val) => new Date(val).toLocaleString()}
              />
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="volume"
                stroke="#38BDF8"
                dot={false}
                name="Volume (txns/hr)"
                isAnimationActive={false}
                strokeWidth={2}
              />
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="ticket_size"
                stroke="#94A3B8"
                dot={false}
                name="Avg Ticket Size (₹)"
                isAnimationActive={false}
                strokeWidth={2}
              />
              {displayWindows.map((fw: any, idx: number) => (
                <ReferenceArea
                  key={idx}
                  yAxisId="left"
                  x1={fw.created_at}
                  x2={new Date(
                    new Date(fw.created_at).getTime() + 3600000,
                  ).toISOString()}
                  fill="#E11D48"
                  fillOpacity={0.15}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="bg-pg-surface border border-pg-border">
        <div className="p-4 border-b border-pg-border bg-[#121820]">
          <h2 className="text-sm font-mono text-pg-muted">
            FLAGGED_ANOMALIES_STAGE_2
          </h2>
        </div>
        
        <div className="p-4">
          {displayAuditLog.length > 0 && (
            <div className="mb-6 bg-[#1A1016] p-4 border border-pg-crimson/30">
              <h3 className="font-mono text-sm text-pg-crimson mb-2">STAGE_1_REGIME_BREAK_LOG:</h3>
              <ul className="list-disc pl-5 space-y-1 font-mono text-xs text-pg-text">
                {displayAuditLog.slice(-10).map((log: string, i: number) => (
                  <li key={i}>{log}</li>
                ))}
              </ul>
            </div>
          )}

          <table className="w-full text-left border-collapse font-mono text-sm">
            <thead>
              <tr className="border-b border-pg-border text-pg-muted bg-[#121820]">
                <th className="p-3 font-normal">TXN_ID</th>
                <th className="p-3 font-normal">WINDOW</th>
                <th className="p-3 font-normal">SCORE</th>
                <th className="p-3 font-normal">ACTION</th>
                <th className="p-3 font-normal">FEATURE_DRIVERS</th>
              </tr>
            </thead>
            <tbody>
              {displayTransactions.slice(0, 50).map((txn: any) => {
                const webhook = displayWebhooks.find(w => w.id === txn.id);
                const tier = webhook ? webhook.tier : "allow";
                return (
                  <tr key={txn.id} className={`border-b border-pg-border ${webhook ? 'bg-[#2D1A16]' : 'hover:bg-[#1C2531]'}`}>
                    <td className="p-3 text-pg-cyan">{txn.id}</td>
                    <td className="p-3 text-pg-text">{new Date(txn.window).toLocaleString()}</td>
                    <td className="p-3 font-medium text-pg-crimson">
                      {txn.score.toFixed(3)}
                    </td>
                    <td className="p-3">
                      {tier === 'block' && <span className="text-pg-crimson border border-pg-crimson/30 bg-pg-crimson/10 px-2 py-0.5 text-xs">BLOCK</span>}
                      {tier === 'review' && <span className="text-pg-amber border border-pg-amber/30 bg-pg-amber/10 px-2 py-0.5 text-xs">REVIEW</span>}
                      {tier === 'allow' && <span className="text-pg-muted text-xs">ALLOW</span>}
                    </td>
                    <td className="p-3 text-pg-text text-xs">
                      {txn.reason || "Unknown anomaly"}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          {displayTransactions.length === 0 && (
            <div className="text-center p-8 text-pg-muted font-mono text-sm">
              [NO_ANOMALIES_DETECTED]
            </div>
          )}
        </div>
      </div>

      {displayWebhooks.length > 0 && (
        <div className="bg-pg-surface border border-pg-border">
          <div className="border-b border-pg-border p-4 bg-[#121820] flex justify-between items-center">
            <h2 className="text-sm font-mono text-pg-muted">
              WEBHOOK_NOTIFICATIONS_SENT
            </h2>
            <span className="text-pg-cyan border border-pg-cyan/30 bg-pg-cyan/10 text-xs px-2 py-0.5 font-mono">
              COUNT: {displayWebhooks.length}
            </span>
          </div>
          <div className="p-4 space-y-2">
            {displayWebhooks.map((action: any, idx: number) => (
              <div
                key={idx}
                className="border border-pg-border bg-pg-bg p-3 flex items-start justify-between font-mono text-sm"
              >
                <div>
                  <div className="flex items-center space-x-3 mb-1">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 text-xs ${
                        action.tier === "block"
                          ? "text-pg-crimson border border-pg-crimson/30 bg-pg-crimson/10"
                          : "text-pg-amber border border-pg-amber/30 bg-pg-amber/10"
                      }`}
                    >
                      {action.tier.toUpperCase()}
                    </span>
                    <span className="text-pg-text">{action.id}</span>
                  </div>
                  <p className="text-xs text-pg-muted font-sans mt-2">{action.reason}</p>
                </div>
                <div className="text-right text-xs text-pg-muted">
                  {new Date(action.fired_at).toLocaleTimeString()}
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
      <div className="min-h-screen bg-pg-bg text-pg-text flex flex-col">
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
