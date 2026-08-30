import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer, Label, BarChart, Bar, Legend } from 'recharts';
import { formatCurrency } from '../utils/currency';

export const CostDashboard = () => {
  const [data, setData] = useState<any>(null);
  const [selectedSegment, setSelectedSegment] = useState<string>('Blended');
  const [currency, setCurrency] = useState<'INR' | 'USD'>('INR');
  
  const EXCHANGE_RATE = 1 / 83.0; // Fixed illustrative rate: 1 INR = ~0.012 USD

  useEffect(() => {
    axios.get('/api/cost-curve').then(res => setData(res.data));
  }, []);

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
    const converted = currency === 'USD' ? val * EXCHANGE_RATE : val;
    return formatCurrency(converted, currency);
  };
  
  const formatCompactAmount = (val: number) => {
    const converted = currency === 'USD' ? val * EXCHANGE_RATE : val;
    if (converted >= 100000) {
      return (converted / 100000).toFixed(1) + 'L';
    } else if (converted >= 1000) {
      return (converted / 1000).toFixed(0) + 'k';
    }
    return converted.toFixed(0);
  };

  return (
    <div className="max-w-6xl p-8 mx-auto space-y-8">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="mb-2 text-3xl font-bold">Financial Impact & Cost Curve</h1>
          <p className="text-gray-600">Optimizing for the lowest expected loss (false negatives + false positives)</p>
        </div>
        <div className="flex items-center space-x-6">
          <div className="flex items-center p-1 space-x-2 bg-gray-100 rounded">
            <button 
              className={`px-3 py-1 rounded ${currency === 'INR' ? 'bg-white shadow font-bold' : 'text-gray-500'}`}
              onClick={() => setCurrency('INR')}
            >
              ₹ INR
            </button>
            <button 
              className={`px-3 py-1 rounded ${currency === 'USD' ? 'bg-white shadow font-bold' : 'text-gray-500'}`}
              onClick={() => setCurrency('USD')}
            >
              $ USD
            </button>
          </div>
          
          <div className="flex items-center space-x-2">
            <label className="font-medium text-gray-700">Merchant Tier:</label>
            <select 
              value={selectedSegment} 
              onChange={e => setSelectedSegment(e.target.value)}
              className="p-2 bg-white border-gray-300 rounded shadow-sm"
            >
              <option value="Blended">Blended (All Merchants)</option>
              <option value="Low Volume">Low Volume</option>
              <option value="Medium Volume">Medium Volume</option>
              <option value="High Volume">High Volume</option>
            </select>
          </div>
        </div>
      </div>
      
      {!displayOptimal ? (
        <div className="p-8 text-yellow-800 rounded bg-yellow-50">No anomalous transactions were flagged in this tier. Cost is entirely missed fraud.</div>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-6">
            <div className="p-6 bg-white border border-gray-200 rounded-lg shadow">
              <div className="text-sm font-medium text-gray-500">Expected Operating Cost ({selectedSegment})</div>
              <div className="mt-2 text-3xl font-bold">{formatAmount(displayOptimal.total_cost)}</div>
              {selectedSegment === 'Blended' && data.bootstrap && (
                <div className="mt-2 text-sm font-medium text-green-600">
                  90% CI: [{formatAmount(data.bootstrap.ci_lower_90)}, {formatAmount(data.bootstrap.ci_upper_90)}]
                </div>
              )}
            </div>
            
            {selectedSegment === 'Blended' ? (
              <div className="p-6 bg-white border border-gray-200 rounded-lg shadow">
                <div className="text-sm font-medium text-gray-500">Baseline (Doing Nothing)</div>
                <div className="mt-2 text-3xl font-bold text-red-600">{formatAmount(baseline_cost)}</div>
                <div className="mt-2 text-sm text-gray-500">100% missed fraud chargebacks</div>
              </div>
            ) : (
              <div className="p-6 bg-white border border-gray-200 rounded-lg shadow">
                <div className="text-sm font-medium text-gray-500">Model Metrics</div>
                <div className="grid grid-cols-2 mt-2 text-sm gap-y-2">
                  <div><span className="text-gray-500">Precision:</span> <span className="ml-1 font-medium">{displayOptimal.precision.toFixed(3)}</span></div>
                  <div><span className="text-gray-500">Recall:</span> <span className="ml-1 font-medium">{displayOptimal.recall.toFixed(3)}</span></div>
                </div>
              </div>
            )}
            
            <div className="p-6 bg-white border border-purple-200 rounded-lg shadow">
              <div className="text-sm font-bold text-purple-600">System Performance (Latency)</div>
              <div className="mt-2 text-sm text-gray-700">
                <div className="flex items-center justify-between mb-1">
                  <span>Single Txn (p95)</span>
                  <span className="px-1 font-mono text-purple-800 bg-gray-100 rounded">996ms</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Batch Window (p95)</span>
                  <span className="px-1 font-mono text-purple-800 bg-gray-100 rounded">658ms</span>
                </div>
              </div>
              <div className="mt-2 text-xs text-gray-500">End-to-end (Stage 1 + Stage 2 IF scoring)</div>
            </div>
            
            {displayTiered && (
              <div className="p-6 bg-white border border-blue-200 rounded-lg shadow">
                <div className="text-sm font-bold text-blue-600">Tiered Action Policy (Allow/Review/Block)</div>
                <div className="mt-1 text-2xl font-bold text-blue-900">{formatAmount(displayTiered.total_cost)}</div>
                <div className="mt-1 text-xs text-gray-600">
                  Savings vs Binary: {formatAmount(displayOptimal.total_cost - displayTiered.total_cost)}
                </div>
                <div className="mt-1 text-xs text-gray-500">
                  Low: {displayTiered.lower_threshold.toFixed(2)} | Upp: {displayTiered.upper_threshold.toFixed(2)}
                </div>
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 gap-8 md:grid-cols-2">
            <div className="p-6 bg-white border border-gray-200 rounded-lg shadow">
              <h2 className="mb-4 text-xl font-bold">Cost Curve ({selectedSegment})</h2>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={displayCurve} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis 
                      dataKey="threshold" 
                      type="number" 
                      domain={['dataMin', 'dataMax']} 
                      tickFormatter={(val) => val.toFixed(2)}
                    >
                      <Label value="Anomaly Score Threshold" offset={-10} position="insideBottom" />
                    </XAxis>
                    <YAxis 
                      tickFormatter={(val) => (currency === 'INR' ? '₹' : '$') + formatCompactAmount(val)} 
                      width={80}
                    />
                    <Tooltip 
                      formatter={(value: number) => [formatAmount(value), 'Total Cost']}
                      labelFormatter={(label: number) => `Threshold: ${label.toFixed(3)}`}
                    />
                    <Line type="monotone" dataKey="total_cost" stroke="#3b82f6" strokeWidth={3} dot={false} />
                    <ReferenceLine x={displayOptimal.threshold} stroke="#ef4444" strokeDasharray="5 5" label={{ value: 'Optimal', position: 'top', fill: '#ef4444' }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            {selectedSegment === 'Blended' && naive_optimal && (
              <div className="p-6 bg-white border border-gray-200 rounded-lg shadow">
                <h2 className="mb-4 text-xl font-bold">Naive Baseline vs. Our Detector</h2>
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={comparisonData} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} />
                      <XAxis dataKey="name" />
                      <YAxis 
                        tickFormatter={(val) => (currency === 'INR' ? '₹' : '$') + formatCompactAmount(val)} 
                        width={80}
                      />
                      <Tooltip formatter={(value: number) => formatAmount(value)} />
                      <Legend />
                      <Bar dataKey="Naive Baseline" fill="#9ca3af" name="Naive Baseline (Optimal)" />
                      <Bar dataKey="Our Detector" fill="#10b981" name="Our Detector" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <div className="mt-4 text-lg font-bold text-center text-green-700">
                  Savings vs Naive: {formatAmount(naive_optimal.total_cost - data.optimal.total_cost)}
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
};

