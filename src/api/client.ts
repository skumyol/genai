/* Simple API client for Flask backend */

export type CreateSessionPayload = {
  user_id: string;
  name?: string;
  status?: string;
  current_day?: number;
  time_period?: string;
  game_state?: string;
  character?: Record<string, any>;
  messages?: any[];
  seed_settings_version?: string;
};

const API_BASE = (import.meta as any).env?.VITE_API_BASE || 'http://localhost:8000/api';

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data?.ok === false) {
    throw new Error(data?.error || `HTTP ${res.status}`);
  }
  return (data?.data ?? data) as T;
}

export async function ensureUserId(): Promise<string> {
  let userId = localStorage.getItem('user_id');
  if (!userId) {
    try {
      const response = await fetch(`${API_BASE}/users`, { method: 'POST' });
      const data = await response.json();
      userId = data.user_id;
      if (userId) {
        localStorage.setItem('user_id', userId);
      }
    } catch (e) {
      // If the backend is not available, we'll need to wait for it
      console.warn('Backend not available for user creation:', e);
      throw new Error('Unable to create user ID - backend service unavailable');
    }
  }
  return userId || 'user_unknown';
}

export async function ensureUserSessions(userId: string): Promise<{ test0_session_id: string; test_sessions: string[] }> {
  try {
    // Get user's existing sessions
    const existingSessions = await listSessionsFiltered({ user_id: userId });
    
    const testSessions: string[] = [];
    let test0SessionId = '';
    
    // Check for Test 0 (fresh world)
    let test0Session = existingSessions.find((s: any) => 
      s.name?.includes('Test 0') || 
      (s.game_settings?.experiment?.experiment_no === 0)
    );
    
    if (!test0Session) {
      // Create Test 0 session
      const res = await createSession({ 
        user_id: userId, 
        name: 'Test 0: Fresh World' 
      } as any);
      test0SessionId = res.session_id;
      // Tag as Test 0
      await saveSession(test0SessionId, { 
        experiment: { 
          type: 'user', 
          user_id: userId, 
          experiment_no: 0, 
          scenario_source_session_id: 'default' 
        } 
      } as any);
    } else {
      test0SessionId = test0Session.session_id;
    }
    
    testSessions.push(test0SessionId);
    
    // Check for Test 1-6 sessions
    for (let i = 1; i <= 6; i++) {
      let testSession = existingSessions.find((s: any) => 
        s.name?.includes(`Test ${i}`) || 
        (s.game_settings?.experiment?.experiment_no === i)
      );
      
      if (testSession) {
        testSessions.push(testSession.session_id);
      } else {
        // Mark that Test i needs to be created when accessed
        testSessions.push('');
      }
    }
    
    return { test0_session_id: test0SessionId, test_sessions: testSessions };
  } catch (e) {
    console.warn('Failed to ensure user sessions:', e);
    throw e;
  }
}

export async function getUserTestSession(userId: string, testIndex: number, sourceSessionId?: string): Promise<string> {
  try {
    // Generate consistent session ID format: userid_test_x
    const sessionId = `${userId}_test_${testIndex}`;
    const testLabel = testIndex === 0 ? 'Test 0: Fresh World' : `Test ${testIndex}`;
    
    // Check if session already exists
    const existingSessions = await listSessionsFiltered({ user_id: userId });
    let existingSession = existingSessions.find((s: any) => 
      s.session_id === sessionId ||
      s.name === testLabel || 
      (s.game_settings?.experiment?.experiment_no === testIndex)
    );
    
    if (existingSession) {
      return existingSession.session_id;
    }
    
    // Create new session with consistent ID
    if (testIndex === 0) {
      // Fresh world session
      const res = await createSession({ 
        session_id: sessionId,
        user_id: userId, 
        name: testLabel 
      } as any);
      await saveSession(sessionId, { 
        experiment: { 
          type: 'user', 
          user_id: userId, 
          experiment_no: testIndex, 
          scenario_source_session_id: 'default' 
        } 
      } as any);
      return sessionId;
    } else {
      // Test session from checkpoint
      if (!sourceSessionId) {
        throw new Error(`Test ${testIndex} requires a source session ID`);
      }
      
      const res = await createSession({
        session_id: sessionId,
        user_id: userId,
        name: testLabel,
        status: 'started',
        seed_settings_version: 'v1'
      } as any);
      
      // Import checkpoint
      await importIntoSession({ 
        source_session_id: sourceSessionId, 
        target_session_id: sessionId, 
        user_id: userId, 
        experiment_no: testIndex 
      });
      
      // Tag the session
      await saveSession(sessionId, { 
        experiment: { 
          type: 'user', 
          user_id: userId, 
          experiment_no: testIndex, 
          scenario_source_session_id: sourceSessionId 
        } 
      } as any);
      
      return sessionId;
    }
  } catch (e) {
    console.warn(`Failed to get/create test session ${testIndex}:`, e);
    throw e;
  }
}

export async function setActiveSession(userId: string, sessionId: string): Promise<void> {
  return http(`/user/${encodeURIComponent(userId)}/active_session`, {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId })
  });
}

export async function getActiveSession(userId: string): Promise<{ active_session_id: string }> {
  return http(`/user/${encodeURIComponent(userId)}/active_session`);
}

export async function initUserDataset(userId: string): Promise<{ db_path: string; created: boolean }> {
  // In current implementation, this is a no-op that uses centralized DB
  // Return mock result to maintain compatibility
  return { db_path: '', created: false };
}

export async function switchUserDataset(userId: string): Promise<string> {
  // In current implementation, this is a no-op that uses centralized DB  
  // Return empty string to maintain compatibility
  return '';
}

export async function fetchSettings(): Promise<{ settings: any; updated_at: string }>{
  return http(`/settings`);
}

export async function resetSettings(): Promise<{ reset: boolean; updated_at: string }>{
  return http(`/settings/reset`, { method: 'POST' });
}

export async function saveSettings(settings: any): Promise<{ updated_at: string }>{
  return http(`/settings`, { method: 'POST', body: JSON.stringify({ settings }) });
}

export async function listSessions(user_id: string): Promise<any[]> {
  return http(`/sessions?user_id=${encodeURIComponent(user_id)}`);
}

export async function listSessionsFiltered(params: { user_id?: string; experiment_no?: number | string; exp_type?: string; role?: string } = {}): Promise<any[]> {
  const q: string[] = [];
  if (params.user_id) q.push(`user_id=${encodeURIComponent(params.user_id)}`);
  if (params.experiment_no !== undefined) q.push(`experiment_no=${encodeURIComponent(String(params.experiment_no))}`);
  if (params.exp_type) q.push(`exp_type=${encodeURIComponent(params.exp_type)}`);
  if (params.role) q.push(`role=${encodeURIComponent(params.role)}`);
  const qs = q.length ? `?${q.join('&')}` : '';
  return http(`/sessions${qs}`);
}

export async function listBaseSessionsFiltered(params: { user_id?: string; experiment_no?: number | string; exp_type?: string; role?: string; experiment_name?: string; variant_id?: string } = {}): Promise<any[]> {
  const q: string[] = [];
  if (params.user_id) q.push(`user_id=${encodeURIComponent(params.user_id)}`);
  if (params.experiment_no !== undefined) q.push(`experiment_no=${encodeURIComponent(String(params.experiment_no))}`);
  if (params.exp_type) q.push(`exp_type=${encodeURIComponent(params.exp_type)}`);
  if (params.role) q.push(`role=${encodeURIComponent(params.role)}`);
  if (params.experiment_name) q.push(`experiment_name=${encodeURIComponent(params.experiment_name)}`);
  if (params.variant_id) q.push(`variant_id=${encodeURIComponent(params.variant_id)}`);
  const qs = q.length ? `?${q.join('&')}` : '';
  return http(`/sessions_base${qs}`);
}

export async function createSession(payload: CreateSessionPayload): Promise<{ session_id: string }>{
  return http(`/sessions`, { method: 'POST', body: JSON.stringify(payload) });
}

export async function getSession(session_id: string): Promise<any> {
  return http(`/sessions/${encodeURIComponent(session_id)}`);
}

export async function getSessionNPCs(session_id: string): Promise<{ npcs: Array<{ name: string; role?: string; story?: string }> }>{
  return http(`/sessions/${encodeURIComponent(session_id)}/npcs`);
}

export async function getSessionMessages(session_id: string, limit = 200): Promise<{ messages: Array<{
  message_id: string,
  dialogue_id: string,
  sender: string,
  receiver: string,
  message_text: string,
  timestamp: string,
  day: number,
  time_period: string,
}>}> {
  return http(`/sessions/${encodeURIComponent(session_id)}/messages?limit=${encodeURIComponent(String(limit))}`);
}

export async function getSessionDayPeriods(session_id: string): Promise<{ days: Array<{ day: number, periods: string[] }>, all_days: number[], all_periods: string[] }>{
  return http(`/sessions/${encodeURIComponent(session_id)}/day_periods`);
}

export async function saveSession(session_id: string, payload: Partial<CreateSessionPayload>): Promise<{ session_id: string; updated_at: string }>{
  return http(`/sessions/${encodeURIComponent(session_id)}/save`, { method: 'POST', body: JSON.stringify(payload) });
}

export async function getNetwork(): Promise<any> {
  return http(`/network`);
}

export async function saveNetwork(network: any): Promise<{ updated_at: string }>{
  return http(`/network`, { method: 'POST', body: JSON.stringify({ network }) });
}

// Game loop controls (SSE)
export async function startGame(session_id: string, num_days: number): Promise<{ started: boolean }>{
  const user_id = localStorage.getItem('user_id') || undefined;
  return http(`/game/start`, { method: 'POST', body: JSON.stringify({ session_id, num_days, user_id }) });
}

export async function stopGame(session_id: string): Promise<{ stopped: boolean }>{
  return http(`/game/stop`, { method: 'POST', body: JSON.stringify({ session_id }) });
}

// Player chat: speak as an NPC to another NPC - returns direct response
export async function sendPlayerChat(params: { session_id: string; as_npc: string; to_npc: string; message: string }): Promise<{ success: boolean, dialogue_id: string, response?: any }>{
  // Optional keystrokes can be added later via overload
  return http(`/chat`, { method: 'POST', body: JSON.stringify({
    session_id: params.session_id,
    as_npc: params.as_npc,
    to_npc: params.to_npc,
    message: params.message,
  }) });
}

export async function sendPlayerChatWithStats(params: { session_id: string; as_npc: string; to_npc: string; message: string; keystrokes?: number; approx_tokens?: number }): Promise<{ success: boolean, dialogue_id: string, response?: any }>{
  const user_id = localStorage.getItem('user_id') || undefined;
  return http(`/chat`, { method: 'POST', body: JSON.stringify({
    session_id: params.session_id,
    as_npc: params.as_npc,
    to_npc: params.to_npc,
    message: params.message,
    keystrokes: params.keystrokes ?? undefined,
    approx_tokens: params.approx_tokens ?? undefined,
    user_id,
  }) });
}

export async function getUserStats(): Promise<any> {
  return http(`/user/stats`);
}

// Experiments
export async function fetchExperiments(): Promise<any> {
  return http(`/experiments`);
}

export async function applyExperiment(variant_id: string): Promise<any> {
  return http(`/experiments/apply`, { method: 'POST', body: JSON.stringify({ variant_id }) });
}

export async function listSelfRuns(): Promise<any[]> {
  return http(`/sessions?exp_type=self`);
}

export async function cloneSessionForUser(source_session_id: string, user_id: string, experiment_no: number): Promise<{ session_id: string, experiment: any }>{
  return http(`/experiments/clone_session`, {
    method: 'POST',
    body: JSON.stringify({ source_session_id, user_id, experiment_no })
  });
}

// Metrics
export async function listMetrics(): Promise<Array<{file:string, experiment_id:string, session_id:string, size:number, modified:number, type:string}>> {
  return http(`/metrics`);
}

export async function fetchMetricsSummary(experiment_id: string, session_id: string): Promise<any> {
  return http(`/metrics/summary?experiment_id=${encodeURIComponent(experiment_id)}&session_id=${encodeURIComponent(session_id)}`);
}

// Admin
export async function reinitDatabase(): Promise<{ reinitialized: boolean, counts: Record<string, number | null> }>{
  return http(`/admin/reinit_db`, { method: 'POST', body: JSON.stringify({}) });
}

export async function importIntoSession(params: { source_session_id: string; target_session_id: string; user_id?: string; experiment_no?: number }): Promise<{ ok: boolean }>{
  return http(`/experiments/import_into_session`, { method: 'POST', body: JSON.stringify(params) });
}

export async function resetUserSessions(userId: string): Promise<{ success: boolean }> {
  return http(`/user/${userId}/reset_sessions`, { method: 'POST' });
}
