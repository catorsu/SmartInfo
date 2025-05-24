/**
 * @file PageActionContext.tsx
 * @description Context for triggering global page-level actions, like opening modals or drawers managed by MainLayout.
 *
 * @file_purpose To provide a decoupled way for child components to request actions
 *               that are handled by a higher-level layout component.
 */
import React, { createContext, useContext, ReactNode } from 'react';

/**
 * @interface PageActionContextType
 * @description Defines the actions that can be triggered globally.
 * These actions are typically implemented in MainLayout.
 */
export interface PageActionContextType {
  /**
   * @method requestOpenFetchModal
   * @description Requests the 'Fetch News' modal to be opened.
   * The MainLayout component is responsible for handling this request and managing the modal's state.
   * @sideeffect May cause MainLayout to change its state to show the Fetch News modal.
   */
  requestOpenFetchModal: () => void;

  /**
   * @method requestOpenTaskDrawer
   * @description Requests the 'Task Progress' drawer to be opened.
   * The MainLayout component is responsible for handling this request and managing the drawer's state.
   * @sideeffect May cause MainLayout to change its state to show the Task Progress drawer.
   */
  requestOpenTaskDrawer: () => void;
}

const PageActionContext = createContext<PageActionContextType | undefined>(undefined);

/**
 * @hook usePageActions
 * @description Custom hook to consume page actions from PageActionContext.
 * Throws an error if used outside of a PageActionProvider (which should be MainLayout).
 * @returns {PageActionContextType} The page action functions provided by MainLayout.
 * @example
 * const { requestOpenFetchModal } = usePageActions();
 * // In a component:
 * // <Button onClick={requestOpenFetchModal}>Show Fetch Modal</Button>
 */
export const usePageActions = (): PageActionContextType => {
  const context = useContext(PageActionContext);
  if (!context) {
    throw new Error('usePageActions must be used within a PageActionProvider (typically MainLayout)');
  }
  return context;
};

// The PageActionContext.Provider will be used directly by MainLayout.
// No separate PageActionProvider component is defined here.
export default PageActionContext;