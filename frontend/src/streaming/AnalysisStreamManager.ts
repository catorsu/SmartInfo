/**
 * @file AnalysisStreamManager.ts
 * @description Manages streaming of news analysis content from the backend.
 * This singleton class handles multiple concurrent streams, allows components
 * to subscribe to updates for specific news items, and manages the lifecycle
 * of these streams (initiation, reading, completion, error handling).
 *
 * @file_purpose To provide a centralized service for handling real-time
 *               streaming of text-based analysis data, ensuring efficient
 *               resource management and consistent state updates to subscribers.
 */
import * as newsService from '@/services/newsService';

/**
 * @interface StreamState
 * @description Defines the state for a single analysis stream associated with a news item.
 * It includes the stream reader, content buffer, status flags, error information,
 * and a set of subscribers interested in updates for this stream.
 */
interface StreamState {
  reader: ReadableStreamDefaultReader<Uint8Array> | null; // The underlying stream reader. Typed for Uint8Array as per typical stream usage.
  content: string;                                        // Accumulated content from the stream.
  isStreaming: boolean;                                   // True if the stream is currently active and reading data.
  isComplete: boolean;                                    // True if the stream has finished (successfully or with error).
  error: string | null;                                   // Stores an error message if the stream encountered an issue.
  subscribers: Set<(stateUpdate: Omit<StreamState, 'reader' | 'subscribers'>) => void>; // Set of callback functions to notify on state changes.
}

/**
 * @class AnalysisStreamManager
 * @description Manages multiple analysis streams for different news items.
 * It allows components to subscribe to stream updates for a specific news item ID,
 * initiates streams on demand, reads data in the background, and notifies
 * subscribers of content updates, completion, or errors. This class is
 * implemented as a singleton.
 *
 * @property {Map<number, StreamState>} activeStreams - A map storing the state of
 *           active or completed streams, keyed by news item ID.
 */
class AnalysisStreamManager {
  private activeStreams = new Map<number, StreamState>();

  /**
   * @function _readStreamInBackground
   * @description Asynchronously reads data from an active stream in the background.
   * It decodes Uint8Array chunks into text and appends to the stream's content buffer.
   * Notifies subscribers on each new chunk and on stream completion or error.
   * This method is not meant to be awaited by its caller (`initiateStream`) to
   * allow `initiateStream` to return quickly.
   *
   * @param {number} newsItemId - The ID of the news item whose stream is being read.
   * @returns {Promise<void>} A promise that resolves when the stream reading is complete or an error occurs.
   * @sideeffect Modifies the `content`, `isStreaming`, `isComplete`, `error`, and `reader`
   *             properties of the `StreamState` for the given `newsItemId`.
   *             Calls `_notifySubscribers` to propagate state changes.
   *             Releases the stream reader on completion or cancellation.
   * @private
   */
  private async _readStreamInBackground(newsItemId: number): Promise<void> {
    const state = this.activeStreams.get(newsItemId);
    if (!state || !state.reader) {
      console.error(`[AnalysisStreamManager] No reader for newsItemId ${newsItemId} to read in background.`);
      // If state exists but reader doesn't, update state to reflect error
      if (state) {
        state.isStreaming = false;
        state.isComplete = true; // Consider it "complete" in a failed way
        state.error = state.error || "Reader was not available when background reading was supposed to start.";
        this._notifySubscribers(newsItemId);
      }
      return;
    }

    console.log(`[AnalysisStreamManager] Starting background read for newsItemId ${newsItemId}`);
    try {
      const reader = state.reader;
      const decoder = new TextDecoder(); // UTF-8 by default
      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          state.isStreaming = false;
          state.isComplete = true;
          state.reader = null; // Release reader
          this._notifySubscribers(newsItemId);
          break;
        }
        // `stream: true` is important for multi-byte characters that might be split across chunks.
        const chunk = decoder.decode(value, { stream: true });
        state.content += chunk;
        this._notifySubscribers(newsItemId);
      }
    } catch (error: any) {
      console.error(`[AnalysisStreamManager] Error reading stream for newsItemId ${newsItemId}:`, error);
      if (state) { // Ensure state still exists
        state.error = error.message || 'An unknown error occurred during streaming.';
        state.isStreaming = false;
        state.isComplete = true; // Mark as complete even on error
        if (state.reader) { // Attempt to release reader if it still exists
          try {
            await state.reader.cancel(state.error);
          } catch (cancelError) {
            console.warn(`[AnalysisStreamManager] Error cancelling reader on stream error for ${newsItemId}:`, cancelError);
          }
          state.reader = null;
        }
        this._notifySubscribers(newsItemId);
      }
    }
  }

  /**
   * @function _notifySubscribers
   * @description Notifies all subscribers for a given news item's stream about state changes.
   * It passes a snapshot of the current stream state (excluding the reader and subscribers list itself)
   * to each registered callback.
   *
   * @param {number} newsItemId - The ID of the news item whose subscribers should be notified.
   * @returns {void}
   * @sideeffect Invokes callback functions provided by subscribers.
   * @private
   */
  private _notifySubscribers(newsItemId: number): void {
    const state = this.activeStreams.get(newsItemId);
    if (!state) return;

    const { reader, subscribers, ...stateUpdate } = state;
    subscribers.forEach(callback => {
      try {
        callback(stateUpdate);
      } catch (err) {
        console.error('[AnalysisStreamManager] Error in subscriber callback:', err);
        // Potentially remove faulty subscriber or add more robust error handling in a production system.
      }
    });
  }

  /**
   * @function initiateStream
   * @description Initiates or restarts an analysis stream for a given news item.
   * If a stream for the item is already active and `forceRestart` is false, it connects
   * to the existing stream. If the stream was previously completed successfully and
   * `forceRestart` is false, it notifies with the completed state. Otherwise, it
   * (re)initiates the stream by calling the backend service and starts reading
   * data in the background via `_readStreamInBackground`.
   *
   * @param {number} newsItemId - The ID of the news item for which to initiate the stream.
   * @param {boolean} [forceRestart=false] - If true, cancels any existing stream (active or completed)
   *                                       and starts a new one.
   * @returns {Promise<void>} A promise that resolves quickly once the stream initiation
   *                          process has started (background reading is non-blocking).
   * @sideeffect Makes an API call to `newsService.streamAnalysis`.
   *             Modifies the `StreamState` for the `newsItemId` in `activeStreams`.
   *             May cancel an existing stream reader.
   *             Calls `_notifySubscribers` to update UI about the new stream state.
   *             Starts `_readStreamInBackground` which has further side effects.
   * @example
   * analysisStreamManager.initiateStream(123); // Initiates stream for news item 123
   * analysisStreamManager.initiateStream(123, true); // Forces restart of stream for news item 123
   */
  public async initiateStream(newsItemId: number, forceRestart: boolean = false): Promise<void> {
    let streamState = this.activeStreams.get(newsItemId);

    if (streamState && streamState.isStreaming && !forceRestart) {
      console.log(`[AnalysisStreamManager] NewsItemId ${newsItemId}: Connecting to existing active stream.`);
      this._notifySubscribers(newsItemId); // Ensure new subscriber gets current (streaming) state
      return;
    }

    if (streamState && streamState.isComplete && !streamState.error && !forceRestart) {
      console.log(`[AnalysisStreamManager] NewsItemId ${newsItemId}: Stream previously completed successfully. Not restarting unless forced.`);
      this._notifySubscribers(newsItemId); // Ensure new subscriber gets current (completed) state
      return;
    }

    // If we are here, it means:
    // 1. No streamState exists for newsItemId.
    // 2. streamState exists but is not streaming AND (it's not complete OR it errored OR forceRestart is true).
    // 3. streamState exists and is streaming BUT forceRestart is true.

    console.log(`[AnalysisStreamManager] NewsItemId ${newsItemId}: Initiating stream. Force restart: ${forceRestart}.`);

    if (streamState && streamState.reader) {
      console.log(`[AnalysisStreamManager] NewsItemId ${newsItemId}: Attempting to cancel existing reader.`);
      try {
        await streamState.reader.cancel('New stream initiation requested (force or restart).');
        console.log(`[AnalysisStreamManager] NewsItemId ${newsItemId}: Existing reader cancelled.`);
      } catch (cancelError) {
        console.warn(`[AnalysisStreamManager] NewsItemId ${newsItemId}: Error cancelling existing reader:`, cancelError);
      }
      streamState.reader = null;
    }

    if (streamState) { // Reset existing state for the new stream
      console.log(`[AnalysisStreamManager] NewsItemId ${newsItemId}: Resetting existing stream state.`);
      streamState.content = '';
      streamState.isStreaming = true;
      streamState.isComplete = false;
      streamState.error = null;
      // `subscribers` set is preserved for existing subscribers.
    } else { // Create new state
      console.log(`[AnalysisStreamManager] NewsItemId ${newsItemId}: Creating new stream state.`);
      streamState = {
        reader: null,
        content: '',
        isStreaming: true, // Will be set to true before API call.
        isComplete: false,
        error: null,
        subscribers: new Set(),
      };
      this.activeStreams.set(newsItemId, streamState);
    }

    // Notify subscribers that streaming is about to start (or has been re-initiated).
    // This sets the UI to a loading/streaming state immediately.
    this._notifySubscribers(newsItemId);

    try {
      console.log(`[AnalysisStreamManager] NewsItemId ${newsItemId}: Calling newsService.streamAnalysis.`);
      // The `force` parameter here is passed to the backend service.
      const response = await newsService.streamAnalysis(newsItemId, true); // `response` is the Fetch API Response object.

      if (!response.body) { // Check if the response body (ReadableStream) exists.
        throw new Error('Invalid stream response from newsService: Response body is null.');
      }
      // `getReader()` is a method of ReadableStream, which is `response.body`.
      streamState.reader = response.body.getReader();

      // The state is already set to isStreaming=true.
      // `_readStreamInBackground` will handle subsequent notifications.

      // Start reading in the background - DO NOT await this.
      // This ensures `initiateStream` returns quickly to the caller.
      this._readStreamInBackground(newsItemId).catch(bgError => {
        // This catch is a safety net. `_readStreamInBackground` should handle its own errors and update state.
        // If it reaches here, it means an unexpected error occurred in the async background process.
        console.error(`[AnalysisStreamManager] NewsItemId ${newsItemId}: Unhandled promise rejection from _readStreamInBackground:`, bgError);
        if (this.activeStreams.has(newsItemId)) { // Check if state still exists for this item.
          const currentState = this.activeStreams.get(newsItemId)!; // Should exist if we're in this catch.
          currentState.error = currentState.error || 'Background read process failed unexpectedly.';
          currentState.isStreaming = false;
          currentState.isComplete = true;
          this._notifySubscribers(newsItemId);
        }
      });

    } catch (error: any) {
      console.error(`[AnalysisStreamManager] NewsItemId ${newsItemId}: Failed to initiate stream API call:`, error);
      if (streamState) { // Ensure streamState is defined.
        streamState.error = error.message || 'Failed to start stream.';
        streamState.isStreaming = false;
        streamState.isComplete = true; // Mark as complete on failure.
        streamState.reader = null; // Ensure reader is cleared.
        this._notifySubscribers(newsItemId);
      }
    }
  }

  /**
   * @function subscribe
   * @description Subscribes a callback function to receive updates for a specific news item's stream.
   * If no stream state exists for the item, a new basic state is created.
   * The callback is immediately invoked with the current state upon subscription.
   *
   * @param {number} newsItemId - The ID of the news item to subscribe to.
   * @param {(stateUpdate: Omit<StreamState, 'reader' | 'subscribers'>) => void} callback - The function
   *        to be called with stream state updates.
   * @returns {void}
   * @sideeffect Adds the callback to the `subscribers` set for the given `newsItemId`.
   *             May create a new `StreamState` entry in `activeStreams`.
   * @example
   * const handleUpdate = (update) => console.log(update.content);
   * analysisStreamManager.subscribe(123, handleUpdate);
   */
  public subscribe(newsItemId: number, callback: (stateUpdate: Omit<StreamState, 'reader' | 'subscribers'>) => void): void {
    let state = this.activeStreams.get(newsItemId);
    if (!state) {
      // Create a default initial state if none exists for this newsItemId.
      state = {
        reader: null,
        content: '',
        isStreaming: false,
        isComplete: false,
        error: null,
        subscribers: new Set(),
      };
      this.activeStreams.set(newsItemId, state);
      console.log(`[AnalysisStreamManager] NewsItemId ${newsItemId}: New basic state created on first subscribe.`);
    }
    state.subscribers.add(callback);
    console.log(`[AnalysisStreamManager] NewsItemId ${newsItemId}: Subscriber added. Total subscribers: ${state.subscribers.size}`);

    // Immediately provide current state to the new subscriber.
    const { reader, subscribers, ...stateUpdate } = state;
    try {
      callback(stateUpdate);
    } catch (err) {
      console.error('[AnalysisStreamManager] Error in initial subscriber callback for ' + newsItemId + ':', err);
    }
  }

  /**
   * @function unsubscribe
   * @description Unsubscribes a callback function from a news item's stream updates.
   *
   * @param {number} newsItemId - The ID of the news item to unsubscribe from.
   * @param {(stateUpdate: Omit<StreamState, 'reader' | 'subscribers'>) => void} callback - The callback
   *        function to remove.
   * @returns {void}
   * @sideeffect Removes the callback from the `subscribers` set for the given `newsItemId`.
   * @example
   * analysisStreamManager.unsubscribe(123, handleUpdate);
   */
  public unsubscribe(newsItemId: number, callback: (stateUpdate: Omit<StreamState, 'reader' | 'subscribers'>) => void): void {
    const state = this.activeStreams.get(newsItemId);
    if (state && state.subscribers.has(callback)) {
      state.subscribers.delete(callback);
      console.log(`[AnalysisStreamManager] NewsItemId ${newsItemId}: Subscriber removed. Total subscribers: ${state.subscribers.size}`);
      // Optional: Consider cleanup if no subscribers and stream is complete/idle.
      // This logic is commented out but shows a potential optimization.
      // if (state.subscribers.size === 0 && !state.isStreaming && (state.isComplete || !state.content)) {
      //   this.clearStreamState(newsItemId);
      //   console.log(`[AnalysisStreamManager] NewsItemId ${newsItemId}: Cleared stream state as no subscribers and stream inactive.`);
      // }
    } else {
      // console.warn(`[AnalysisStreamManager] NewsItemId ${newsItemId}: Attempted to unsubscribe a non-existent callback.`);
    }
  }

  /**
   * @function getStreamStateSnapshot
   * @description Retrieves a snapshot of the current state for a given news item's stream,
   * excluding the internal reader and subscribers list.
   *
   * @param {number} newsItemId - The ID of the news item.
   * @returns {Omit<StreamState, 'reader' | 'subscribers'> | null} The current stream state snapshot,
   *          or null if no state exists for the item.
   * @example
   * const snapshot = analysisStreamManager.getStreamStateSnapshot(123);
   * if (snapshot) console.log(snapshot.content);
   */
  public getStreamStateSnapshot(newsItemId: number): Omit<StreamState, 'reader' | 'subscribers'> | null {
    const state = this.activeStreams.get(newsItemId);
    if (!state) {
      return null;
    }
    const { reader, subscribers, ...snapshot } = state;
    return snapshot;
  }

  /**
   * @function clearStreamState
   * @description Clears and resets the stream state for a specific news item.
   * If an active stream reader exists, it attempts to cancel it.
   * Removes the stream entry from `activeStreams`.
   *
   * @param {number} newsItemId - The ID of the news item whose stream state should be cleared.
   * @returns {void}
   * @sideeffect Cancels active stream reader if present.
   *             Removes the `StreamState` entry from `activeStreams`.
   * @example
   * analysisStreamManager.clearStreamState(123);
   */
  public clearStreamState(newsItemId: number): void {
    const state = this.activeStreams.get(newsItemId);
    if (state) {
      if (state.reader) {
        console.log(`[AnalysisStreamManager] NewsItemId ${newsItemId}: Clearing stream state, cancelling active reader.`);
        state.reader.cancel('Stream state explicitly cleared').catch(e =>
          console.warn(`[AnalysisStreamManager] NewsItemId ${newsItemId}: Error cancelling reader on clearStreamState: ${e.message}`)
        );
      }
      this.activeStreams.delete(newsItemId);
      console.log(`[AnalysisStreamManager] NewsItemId ${newsItemId}: Stream state cleared.`);
    }
  }
}

// Export a singleton instance of the manager for global use across the application.
const analysisStreamManager = new AnalysisStreamManager();
export default analysisStreamManager;