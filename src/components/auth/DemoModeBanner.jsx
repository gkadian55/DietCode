import React from 'react';
import { Info } from 'lucide-react';
import { SignUpButton } from '@clerk/react';
import { useAuth } from '@clerk/react';

export const DemoModeBanner = () => {
  const { isLoaded, isSignedIn } = useAuth();

  if (!isLoaded || isSignedIn) return null;

  return (
    <div className="demo-mode-banner" role="status">
      <Info size={15} />
      <span>
        <strong>Demo mode:</strong> you can explore with simulations. Sign in to run live models and use credits.
      </span>
      <SignUpButton mode="modal">
        <button type="button" className="demo-mode-signup">Sign up for live execution</button>
      </SignUpButton>
    </div>
  );
};
