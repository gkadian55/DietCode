import React, { useEffect, useState } from 'react';
import { CreditCard, Loader2, RefreshCw, Wallet, X } from 'lucide-react';
import { useDagStore } from '../../store/useDagStore';

export const BillingControl = () => {
  const {
    billingBalance,
    billingLoading,
    billingError,
    refreshBillingBalance,
    createBillingCheckout
  } = useDagStore();
  const [isOpen, setIsOpen] = useState(false);
  const [amountInr, setAmountInr] = useState('500');

  useEffect(() => {
    if (isOpen) refreshBillingBalance();
  }, [isOpen, refreshBillingBalance]);

  const handleCheckout = async () => {
    const amount = Number(amountInr);
    if (!Number.isFinite(amount) || amount <= 0) return;
    await createBillingCheckout(amount);
  };

  return (
    <div className="billing-control">
      <button
        type="button"
        className="billing-trigger"
        onClick={() => setIsOpen((open) => !open)}
        title="View balance and add credits"
      >
        <Wallet size={14} />
        <span>{billingBalance === null ? 'Credits' : `$${Number(billingBalance).toFixed(2)}`}</span>
      </button>

      {isOpen && (
        <div className="billing-popover">
          <div className="billing-popover-header">
            <div>
              <div className="billing-title">DietCode Credits</div>
              <div className="billing-subtitle">Test payments via Stripe</div>
            </div>
            <button type="button" className="window-btn" onClick={() => setIsOpen(false)} title="Close credits">
              <X size={13} />
            </button>
          </div>

          <div className="billing-balance-row">
            <span>Current balance</span>
            <strong>{billingBalance === null ? '--' : `$${Number(billingBalance).toFixed(2)}`}</strong>
            <button type="button" className="billing-refresh" onClick={refreshBillingBalance} disabled={billingLoading} title="Refresh balance">
              <RefreshCw size={13} className={billingLoading ? 'spin-animation' : ''} />
            </button>
          </div>

          <label className="billing-label" htmlFor="billing-amount">Top-up amount (INR)</label>
          <select id="billing-amount" className="billing-input" value={amountInr} onChange={(event) => setAmountInr(event.target.value)}>
            <option value="500">₹500 → $5.00</option>
            <option value="1000">₹1,000 → $10.00</option>
            <option value="2000">₹2,000 → $20.00</option>
          </select>

          <button type="button" className="btn btn-primary billing-checkout" onClick={handleCheckout} disabled={billingLoading}>
            {billingLoading ? <Loader2 size={13} className="spin-animation" /> : <CreditCard size={13} />}
            {billingLoading ? 'Opening checkout...' : 'Add credits'}
          </button>

          {billingError && <div className="billing-error">{billingError}</div>}
          <div className="billing-note">Test mode only. Balance updates after the verified webhook.</div>
        </div>
      )}
    </div>
  );
};
