// frontend/src/streaming/AnalysisStreamManager.ts
import * as newsService from '@/services/newsService';

interface StreamState {
  reader: ReadableStreamDefaultReader<Uint8Array> | null; // Explicitly type Uint8Array for clarity
  content: string;
  isStreaming: boolean;
  isComplete: boolean;
  error: string | null;
  subscribers: Set<(stateUpdate: Omit<StreamState, 'reader' | 'subscribers'>) => void>;
}

class AnalysisStreamManager {
  private activeStreams = new Map<number, StreamState>();

  private async _readStreamInBackground(newsItemId: number): Promise<void> {
    const state = this.activeStreams.get(newsItemId);
    if (!state || !state.reader) {
      console.error(`[AnalysisStreamManager] No reader for newsItemId ${newsItemId} to read in background.`);
      if (state) { // If state exists but reader doesn't, update state to reflect error
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
          console.log(`[AnalysisStreamManager] Stream completed successfully for newsItemId ${newsItemId}`);
          state.isStreaming = false;
          state.isComplete = true;
          state.reader = null; // Release reader
          this._notifySubscribers(newsItemId);
          break;
        }
        const chunk = decoder.decode(value, { stream: true }); // stream: true is important for multi-byte chars
        state.content += chunk;
        // console.log(`[AnalysisStreamManager] Received chunk for ${newsItemId}:`, chunk.length, "chars");
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

  private _notifySubscribers(newsItemId: number): void {
    const state = this.activeStreams.get(newsItemId);
    if (!state) return;

    const { reader, subscribers, ...stateUpdate } = state;
    // console.log(`[AnalysisStreamManager] Notifying ${subscribers.size} subscribers for newsItemId ${newsItemId} with isStreaming: ${stateUpdate.isStreaming}, isComplete: ${stateUpdate.isComplete}`);
    subscribers.forEach(callback => {
      try {
        callback(stateUpdate);
      } catch (err) {
        console.error('[AnalysisStreamManager] Error in subscriber callback:', err);
        // Potentially remove faulty subscriber or add more robust error handling
      }
    });
  }

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
      // subscribers set is preserved
    } else { // Create new state
      console.log(`[AnalysisStreamManager] NewsItemId ${newsItemId}: Creating new stream state.`);
      streamState = {
        reader: null,
        content: '',
        isStreaming: true, // Will be set to true before API call
        isComplete: false,
        error: null,
        subscribers: new Set(),
      };
      this.activeStreams.set(newsItemId, streamState);
    }

    // Notify subscribers that streaming is about to start (or has been re-initiated)
    // This sets the UI to a loading/streaming state immediately.
    this._notifySubscribers(newsItemId);

    try {
      console.log(`[AnalysisStreamManager] NewsItemId ${newsItemId}: Calling newsService.streamAnalysis.`);
      // The plan specifies `force=true` to the backend service.
      const response = await newsService.streamAnalysis(newsItemId, true); // Renaming for clarity, this is the Response object

      if (!response.body) { // Check if the body exists
        throw new Error('Invalid stream response from newsService: Response body is null.');
      }
      // getReader() is a method of ReadableStream, which is response.body
      streamState.reader = response.body.getReader();

      // The state is already set to isStreaming=true. Notify subscribers again if anything changed,
      // though _readStreamInBackground will handle subsequent notifications.
      // this._notifySubscribers(newsItemId); // Potentially redundant if no state change before read starts.

      // Start reading in the background - DO NOT await this.
      // This ensures initiateStream returns quickly.
      this._readStreamInBackground(newsItemId).catch(bgError => {
        console.error(`[AnalysisStreamManager] NewsItemId ${newsItemId}: Unhandled promise rejection from _readStreamInBackground:`, bgError);
        // This catch is a safety net. _readStreamInBackground should handle its own errors and update state.
        // If it reaches here, it means an unexpected error occurred in the async process.
        if (this.activeStreams.has(newsItemId)) { // Check if state still exists for this item
          const currentState = this.activeStreams.get(newsItemId)!; // Should exist
          currentState.error = currentState.error || 'Background read process failed unexpectedly.';
          currentState.isStreaming = false;
          currentState.isComplete = true;
          this._notifySubscribers(newsItemId);
        }
      });

    } catch (error: any) {
      console.error(`[AnalysisStreamManager] NewsItemId ${newsItemId}: Failed to initiate stream API call:`, error);
      if (streamState) { // Ensure streamState is defined
        streamState.error = error.message || 'Failed to start stream.';
        streamState.isStreaming = false;
        streamState.isComplete = true; // Mark as complete on failure
        streamState.reader = null; // Ensure reader is cleared
        this._notifySubscribers(newsItemId);
      }
    }
  }

  public subscribe(newsItemId: number, callback: (stateUpdate: Omit<StreamState, 'reader' | 'subscribers'>) => void): void {
    let state = this.activeStreams.get(newsItemId);
    if (!state) {
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

    const { reader, subscribers, ...stateUpdate } = state;
    try {
      callback(stateUpdate); // Immediately provide current state
    } catch (err) {
      console.error('[AnalysisStreamManager] Error in initial subscriber callback for ' + newsItemId + ':', err);
    }
  }

  public unsubscribe(newsItemId: number, callback: (stateUpdate: Omit<StreamState, 'reader' | 'subscribers'>) => void): void {
    const state = this.activeStreams.get(newsItemId);
    if (state && state.subscribers.has(callback)) {
      state.subscribers.delete(callback);
      console.log(`[AnalysisStreamManager] NewsItemId ${newsItemId}: Subscriber removed. Total subscribers: ${state.subscribers.size}`);
      // Optional: Consider cleanup if no subscribers and stream is complete/idle
      // if (state.subscribers.size === 0 && !state.isStreaming && (state.isComplete || !state.content)) {
      //   this.clearStreamState(newsItemId); // or this.activeStreams.delete(newsItemId)
      //   console.log(`[AnalysisStreamManager] NewsItemId ${newsItemId}: Cleared stream state as no subscribers and stream inactive.`);
      // }
    } else {
      // console.warn(`[AnalysisStreamManager] NewsItemId ${newsItemId}: Attempted to unsubscribe a non-existent callback.`);
    }
  }

  public getStreamStateSnapshot(newsItemId: number): Omit<StreamState, 'reader' | 'subscribers'> | null {
    const state = this.activeStreams.get(newsItemId);
    if (!state) {
      return null;
    }
    const { reader, subscribers, ...snapshot } = state;
    return snapshot;
  }

  // Method to clear/reset a stream entry, as considered in the plan
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

// Export a singleton instance of the manager
const analysisStreamManager = new AnalysisStreamManager();
export default analysisStreamManager;