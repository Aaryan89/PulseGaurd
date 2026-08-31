import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer, Label, BarChart, Bar, Legend } from 'recharts';
import { formatCurrency } from '../utils/currency';

export const CostDashboard = () => {
  const [data, setData] = useState<any>(null);
  const [selectedSegment, setSelectedSegment] = useState<string>('Blended');
  const [currency, setCurrency] = useState<'INR' | 'USD'>('INR');
  
  const EXCHANGE_RATE = 1 / 83.0; // Fixed illustrative rate: 1 INR = ~0.012 USD

  const [fnMultiplier, setFnMultiplier] = useState<number>(1.15);
  const [fpMultiplier, setFpMultiplier] = useState<number>(0.02);

  useEffect(() => {
    const handler = setTimeout(() => {
      axios.get(`/api/cost-curve?fn_multiplier=${fnMultiplier}&fp_multiplier=${fpMultiplier}`).then(res => setData(res.data));
    }, 300);
    return () => clearTimeout(handler);
  }, [fnMultiplier, fpMultiplier]);

  if (!data || !data.curve) return <div className="p-8">Loading Cost Data...</div>;

  const { baseline_cost, naive_optimal, tiered_optimal, segments } = data;
  
  const displayCurve = selectedSegment === 'Blended' ? data.curve : (segments[selectedSegment]?.curve || []);
  const displayOptimal = selectedSegment === 'Blended' ? data.optimal : (segments[selectedSegment]?.optimal || null);
  const displayTiered = selectedSegment === 'Blended' ? tiered_optimal : (segments[selectedSegment]?.tiered_optimal || null);

  const comparisonData = [
    {
      name: 'Total Cost',
      'Naive Baseline': naive_optimal?.total_cost || 0,
      'Our Detector': data.optimal.total_cost,
    }
  ];

  const formatAmount = (val: number) => {
    const majorUnit = val / 100.0;
    const converted = currency === 'USD' ? majorUnit * EXCHANGE_RATE : majorUnit;
    return formatCurrency(converted, currency);
  };
  
  const formatCompactAmount = (val: number) => {
    const majorUnit = val / 100.0;
    const converted = currency === 'USD' ? majorUnit * EXCHANGE_RATE : majorUnit;
    if (converted >= 10000000) {
      return (converted / 10000000).toFixed(1) + 'Cr';
    } else if (converted >= 100000) {
      return (converted / 100000).toFixed(1) + 'L';
    } else if (converted >= 1000) {
      return (converted / 1000).toFixed(0) + 'k';
    }
    return converted.toFixed(0);
  };

  return (
    <div className="max-w-6xl p-8 mx-auto space-y-6 text-pg-text">
      <div className="flex items-end justify-between pb-4 border-b border-pg-border">
        <div>
          <h1 className="mb-1 font-mono text-2xl font-bold tracking-tight">FINANCIAL_IMPACT_AND_COST_CURVE</h1>
          <p className="text-sm text-pg-muted">Optimizing for the lowest expected loss (false negatives + false positives)</p>
        </div>
        <div className="flex items-center space-x-6">
          <div className="flex items-center p-1 space-x-1 border border-pg-border bg-pg-surface">
            <button 
              className={`px-3 py-1 text-xs font-mono font-bold transition-colors ${currency === 'INR' ? 'bg-[#2D3748] text-white' : 'text-pg-muted hover:text-pg-text'}`}
              onClick={() => setCurrency('INR')}
            >
              INR
            </button>
            <button 
              className={`px-3 py-1 text-xs font-mono font-bold transition-colors ${currency === 'USD' ? 'bg-[#2D3748] text-white' : 'text-pg-muted hover:text-pg-text'}`}
              onClick={() => setCurrency('USD')}
            >
              USD
            </button>
          </div>
          
          <div className="flex items-center space-x-3">
            <label className="font-mono text-xs text-pg-muted">MERCHANT_TIER:</label>
            <select 
              value={selectedSegment} 
              onChange={e => setSelectedSegment(e.target.value)}
              className="px-3 py-1 font-mono text-sm border bg-pg-surface border-pg-border text-pg-text focus:outline-none focus:border-pg-cyan"
            >
              <option value="Blended">BLENDED_ALL</option>
              <option value="Low Volume">LOW_VOLUME</option>
              <option value="Medium Volume">MEDIUM_VOLUME</option>
              <option value="High Volume">HIGH_VOLUME</option>
            </select>
          </div>
        </div>
      </div>
      
      {!displayOptimal ? (
        <div className="p-6 font-mono text-sm border text-pg-amber border-pg-amber/30 bg-pg-amber/10">
          [NO_ANOMALOUS_TRANSACTIONS_FLAGGED_IN_TIER]
        </div>
      ) : (
        <>
          {/* Top Metrics Row */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
            <div className="flex flex-col justify-between p-5 border bg-pg-surface border-pg-border">
              <div className="mb-2 font-mono text-xs text-pg-muted">EXPECTED_OPERATING_COST</div>
              <div>
                <div className="font-mono text-2xl font-bold text-pg-cyan">{formatAmount(displayOptimal.total_cost)}</div>
                {selectedSegment === 'Blended' && data.bootstrap && (
                  <div className="text-[10px] font-mono text-pg-muted mt-1">
                    90% CI: [{formatAmount(data.bootstrap.ci_lower_90)}, {formatAmount(data.bootstrap.ci_upper_90)}]
                  </div>
                )}
              </div>
            </div>
            
            {selectedSegment === 'Blended' ? (
              <div className="flex flex-col justify-between p-5 border bg-pg-surface border-pg-border">
                <div className="mb-2 font-mono text-xs text-pg-muted">BASELINE_NO_DETECTOR</div>
                <div>
                  <div className="font-mono text-2xl font-bold text-pg-crimson">{formatAmount(baseline_cost)}</div>
                  <div className="text-[10px] font-mono text-pg-muted mt-1">100% MISSED FRAUD (CHARGEBACKS)</div>
                </div>
              </div>
            ) : (
              <div className="flex flex-col justify-between p-5 border bg-pg-surface border-pg-border">
                <div className="mb-2 font-mono text-xs text-pg-muted">MODEL_METRICS</div>
                <div className="grid grid-cols-2 font-mono text-sm">
                  <div><span className="text-pg-muted">PREC:</span> <span className="text-pg-text">{displayOptimal.precision.toFixed(3)}</span></div>
                  <div><span className="text-pg-muted">REC:</span> <span className="text-pg-text">{displayOptimal.recall.toFixed(3)}</span></div>
                </div>
              </div>
            )}
            
            <div className="flex flex-col justify-between p-5 border bg-pg-surface border-pg-border">
              <div className="mb-2 font-mono text-xs text-pg-muted">LATENCY_P95</div>
              <div className="space-y-1 font-mono text-sm">
                <div className="flex items-center justify-between pb-1 border-b border-pg-border/50">
                  <span className="text-pg-muted">SINGLE_TXN</span>
                  <span className="text-pg-cyan">996ms</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-pg-muted">BATCH_WINDOW</span>
                  <span className="text-pg-cyan">658ms</span>
                </div>
              </div>
            </div>
            
            {displayTiered ? (
              <div className="relative flex flex-col justify-between p-5 overflow-hidden border bg-pg-surface border-pg-amber/50">
                <div className="absolute top-0 right-0 w-16 h-16 transform rotate-45 translate-x-8 -translate-y-8 bg-pg-amber/10"></div>
                <div className="relative z-10 mb-2 font-mono text-xs text-pg-amber">TIERED_POLICY_COST (A/R/B)</div>
                <div className="relative z-10">
                  <div className="font-mono text-xl font-bold text-pg-text">{formatAmount(displayTiered.total_cost)}</div>
                  <div className="text-[10px] font-mono text-pg-muted mt-1">
                    SAVINGS VS BINARY: <span className="text-pg-amber">{formatAmount(displayOptimal.total_cost - displayTiered.total_cost)}</span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="p-5 border bg-pg-surface border-pg-border"></div>
            )}
          </div>

          {/* Signature Element: The Interactive Cost Curve */}
          <div className="overflow-hidden border bg-pg-bg border-pg-border">
            <div className="bg-[#121820] border-b border-pg-border p-4 flex justify-between items-center">
              <h2 className="font-mono text-sm tracking-widest text-pg-muted">COST_OPTIMIZATION_CURVE</h2>
              <div className="text-xs font-mono text-pg-cyan border border-pg-cyan/30 bg-pg-cyan/10 px-2 py-0.5">
                OPTIMAL_THRESHOLD: {displayOptimal.threshold.toFixed(2)}
              </div>
            </div>
            
            {/* The Chart */}
            <div className="p-6 h-96">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={displayCurve} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorCost" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#38BDF8" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#38BDF8" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2D3748" vertical={false} />
                  <XAxis 
                    dataKey="threshold" 
                    type="number" 
                    domain={['dataMin', 'dataMax']} 
                    tick={{fill: '#94A3B8', fontSize: 12, fontFamily: 'JetBrains Mono'}}
                    stroke="#94A3B8"
                    tickFormatter={(val) => val.toFixed(2)}
                  >
                  </XAxis>
                  <YAxis 
                    tickFormatter={(val) => (currency === 'INR' ? '₹' : '$') + formatCompactAmount(val)} 
                    width={95}
                    tick={{fill: '#94A3B8', fontSize: 12, fontFamily: 'JetBrains Mono'}}
                    stroke="#94A3B8"
                  />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#1A2027', borderColor: '#2D3748', color: '#E2E8F0', fontFamily: 'JetBrains Mono', fontSize: '12px' }}
                    formatter={(value: number) => [formatAmount(value), 'TOTAL_COST']}
                    labelFormatter={(label: number) => `THRESHOLD: ${label.toFixed(3)}`}
                  />
                  <Area 
                    type="monotone" 
                    dataKey="total_cost" 
                    stroke="#38BDF8" 
                    fill="url(#colorCost)"
                    strokeWidth={2} 
                    dot={false}
                    isAnimationActive={false} 
                  />
                  <ReferenceLine 
                    x={displayOptimal.threshold} 
                    stroke="#38BDF8" 
                    strokeDasharray="4 4" 
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            
            {/* The Integrated Control Rail */}
            <div className="border-t border-pg-border bg-[#121820] p-4 flex flex-col md:flex-row gap-8">
              <div className="flex flex-col justify-center flex-1">
                <div className="flex items-center justify-between mb-3">
                  <span className="font-mono text-xs text-pg-muted">CHARGEBACK_FEE_RATE (FN_COST)</span>
                  <span className="font-mono text-sm font-bold text-pg-crimson">{fnMultiplier.toFixed(2)}X</span>
                </div>
                <input 
                  type="range" 
                  min="1.0" max="3.0" step="0.05"
                  value={fnMultiplier}
                  onChange={(e) => setFnMultiplier(parseFloat(e.target.value))}
                  className="w-full"
                />
              </div>
              <div className="hidden w-px bg-pg-border md:block"></div>
              <div className="flex flex-col justify-center flex-1">
                <div className="flex items-center justify-between mb-3">
                  <span className="font-mono text-xs text-pg-muted">CHURN_RISK_RATE (FP_COST)</span>
                  <span className="font-mono text-sm font-bold text-pg-amber">{fpMultiplier.toFixed(3)}X</span>
                </div>
                <input 
                  type="range" 
                  min="0.0" max="0.1" step="0.005"
                  value={fpMultiplier}
                  onChange={(e) => setFpMultiplier(parseFloat(e.target.value))}
                  className="w-full"
                />
              </div>
              <div className="flex items-center">
                <button 
                  onClick={() => { setFnMultiplier(1.15); setFpMultiplier(0.02); }}
                  className="h-10 px-4 py-2 font-mono text-xs transition-colors bg-transparent border border-pg-border text-pg-muted hover:border-pg-cyan hover:text-pg-cyan whitespace-nowrap"
                >
                  [RESET_PARAMS]
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

