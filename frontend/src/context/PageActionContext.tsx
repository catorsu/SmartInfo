import React, { createContext, useState, useContext, useCallback, ReactNode } from 'react';

interface PageActionContextType {
  registerShowFetchModal: (handler: (() => void) | null) => void;
  triggerShowFetchModal: () => void;
  registerShowTaskDrawer: (handler: (() => void) | null) => void;
  triggerShowTaskDrawer: () => void;
  // registerShowSettingsModal will NOT be needed here if Settings is global via MainLayout state
}

const PageActionContext = createContext<PageActionContextType | undefined>(undefined);

export const PageActionProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [showFetchModalHandler, setShowFetchModalHandler] = useState<(() => void) | null>(null);
  const [showTaskDrawerHandler, setShowTaskDrawerHandler] = useState<(() => void) | null>(null);

  const registerShowFetchModal = useCallback((handler: (() => void) | null) => {
    setShowFetchModalHandler(() => handler); // Ensure new function reference for re-render
  }, []);

  const triggerShowFetchModal = useCallback(() => {
    if (showFetchModalHandler) {
      showFetchModalHandler();
    } else {
      console.warn('triggerShowFetchModal called, but no handler registered.');
    }
  }, [showFetchModalHandler]);

  const registerShowTaskDrawer = useCallback((handler: (() => void) | null) => {
    setShowTaskDrawerHandler(() => handler);
  }, []);

  const triggerShowTaskDrawer = useCallback(() => {
    if (showTaskDrawerHandler) {
      showTaskDrawerHandler();
    } else {
      console.warn('triggerShowTaskDrawer called, but no handler registered.');
    }
  }, [showTaskDrawerHandler]);

  return (
    <PageActionContext.Provider value={{ 
      registerShowFetchModal, 
      triggerShowFetchModal,
      registerShowTaskDrawer,
      triggerShowTaskDrawer
    }}>
      {children}
    </PageActionContext.Provider>
  );
};

export const usePageActions = (): PageActionContextType => {
  const context = useContext(PageActionContext);
  if (!context) {
    throw new Error('usePageActions must be used within a PageActionProvider');
  }
  return context;
};