export const formatCurrency = (amount: number, currencyCode: 'INR' | 'USD' = 'INR'): string => {
  return amount.toLocaleString('en-IN', {
    style: 'currency',
    currency: currencyCode,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
};
