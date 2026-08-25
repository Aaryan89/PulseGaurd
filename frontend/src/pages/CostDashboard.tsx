import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer, Label } from 'recharts';

export const CostDashboard = () => {
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    axios.get('http://localhost:8000/cost-curve').then(res => setData(res.data));
  }, []);

  if (!data || !data.curve) return <div className="p-8">Loading Cost Data...</div>;

  const { curve, optimal, bootstrap, baseline_cost } = data;

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <h1 className="text-3xl font-bold mb-2">Financial Impact & Cost Curve</h1>
      <p className="text-gray-600 mb-8">Optimizing for the lowest expected loss (false negatives + false positives)</p>
      
      <div className="grid grid-cols-3 gap-6 mb-8">
        <div className="bg-white p-6 rounded-lg shadow border border-gray-200">
          <div className="text-sm text-gray-500 font-medium">Expected Operating Cost</div>
          <div className="text-3xl font-bold mt-2">${optimal.total_cost.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
          <div className="text-sm text-green-600 mt-2 font-medium">
            90% CI: [${bootstrap.ci_lower_90.toLocaleString(undefined, {maximumFractionDigits: 0})}, ${bootstrap.ci_upper_90.toLocaleString(undefined, {maximumFractionDigits: 0})}]
          </div>
        </div>
        <div className="bg-white p-6 rounded-lg shadow border border-gray-200">
          <div className="text-sm text-gray-500 font-medium">Baseline (Doing Nothing)</div>
          <div className="text-3xl font-bold mt-2 text-red-600">${baseline_cost.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
          <div className="text-sm text-gray-500 mt-2">100% missed fraud chargebacks</div>
        </div>
        <div className="bg-white p-6 rounded-lg shadow border border-gray-200">
          <div className="text-sm text-gray-500 font-medium">Model Metrics @ Optimal</div>
          <div className="mt-2 grid grid-cols-2 gap-y-2 text-sm">
            <div><span className="text-gray-500">Precision:</span> <span className="font-medium ml-1">{optimal.precision.toFixed(3)}</span></div>
            <div><span className="text-gray-500">Recall:</span> <span className="font-medium ml-1">{optimal.recall.toFixed(3)}</span></div>
            <div><span className="text-gray-500">F1 Score:</span> <span className="font-medium ml-1">{optimal.f1.toFixed(3)}</span></div>
            <div><span className="text-gray-500">Threshold:</span> <span className="font-medium ml-1">{optimal.threshold.toFixed(3)}</span></div>
          </div>
        </div>
      </div>

      <div className="bg-white p-6 rounded-lg shadow border border-gray-200 h-96">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={curve} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
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
              tickFormatter={(val) => `$${(val/1000).toFixed(0)}k`} 
              width={80}
            />
            <Tooltip 
              formatter={(value: number) => [`$${value.toLocaleString(undefined, {minimumFractionDigits: 2})}`, 'Total Cost']}
              labelFormatter={(label: number) => `Threshold: ${label.toFixed(3)}`}
            />
            <Line type="monotone" dataKey="total_cost" stroke="#3b82f6" strokeWidth={3} dot={false} />
            <ReferenceLine x={optimal.threshold} stroke="#ef4444" strokeDasharray="5 5" label={{ value: 'Optimal Threshold', position: 'top', fill: '#ef4444' }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
