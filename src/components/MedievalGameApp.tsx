import React, { useState, useEffect, useMemo, useRef } from 'react';
import { Provider } from 'react-redux';
import { ThemeProvider, CssBaseline } from '@mui/material';
import { Stack, Button, AppBar, Toolbar, Typography, IconButton, Container, Box, Chip, Tooltip } from '@mui/material';
import PersonOutlinedIcon from '@mui/icons-material/PersonOutlined';
import SettingsOutlinedIcon from '@mui/icons-material/SettingsOutlined';
// import HistoryOutlinedIcon from '@mui/icons-material/HistoryOutlined';
import SportsEsportsOutlinedIcon from '@mui/icons-material/SportsEsportsOutlined';
import EditIcon from '@mui/icons-material/Edit';

import { store } from '../store/gameStore';
import { useGameStore } from '../hooks/useGameStore';
import medievalTheme from '../theme/medievalTheme';
// Load study guide content from repository (fallbacks in runtime if not found)
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore
import defaultGuideMd from '../../USER_STUDY_GUIDE.md?raw';

import { NPCPanel } from './npc/NPCPanel';
import { ChatInterface } from './chat/ChatInterface';
import { GameControls } from './game/GameControls';
import { ChatFilters } from './filters/ChatFilters';
import { CharacterCreationModal } from './modals/CharacterCreationModal';
// import { LoadSessionModal } from './modals/LoadSessionModal';
import { AdminPanel } from './modals/AdminPanel';
import { ExperimentGuideModal } from './modals/ExperimentGuideModal';
import { NPCDetailsModal } from './modals/NPCDetailsModal';
import { QuestionnaireModal } from './questionnaire/QuestionnaireModal';

import { mockQuery } from '../data/medievalGameMockData';
import { GameState, TimePeriod, MessageType, NPCStatus, StudyPhase } from '../types/enums';
import { Message, NPC, Character } from '../types/schema';
import { ensureUserId, ensureUserSessions, getUserTestSession, setActiveSession, createSession, fetchSettings, getSession, getSessionMessages, getSessionNPCs, startGame, stopGame, saveSession, listSelfRuns, importIntoSession, sendPlayerChatWithStats, cloneSessionForUser, listSessionsFiltered, listBaseSessionsFiltered, resetUserSessions, getSessionDayPeriods, getActiveSession } from '../api/client';
import { useQuestionnaire } from '../hooks/useQuestionnaire';

const MedievalGameContent: React.FC = () => {
  const {
    gameState,
    currentDay,
    numDays,
    currentTimePeriod,
    selectedNPCId,
    playerNpcId,
    talkTargetNpcId,
    chatFilters,
    isCharacterCreationOpen,
    isAdminPanelOpen,
    setGameState,
    setCurrentDay,
    setNumDays,
    setCurrentTimePeriod,
    setSelectedNPCId,
    setPlayerNpcId,
    setTalkTargetNpcId,
    setChatFilters,
    clearChatFilters,
    setCharacterCreationOpen,
    setAdminPanelOpen
  } = useGameStore();

  // Questionnaire system integration
  const {
    currentQuestionnaire,
    currentResponses,
    userProgress,
    isOpen: isQuestionnaireOpen,
    initializeUser,
    showQuestionnaire,
    updateQuestionResponse,
    completeQuestionnaire,
    closeQuestionnaire,
    setStudySessionId,
    advanceStudyPhase,
    resetQuestionnaire,
    
  } = useQuestionnaire();

  const [npcs, setNpcs] = useState<NPC[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [playerSessionId, setPlayerSessionId] = useState<string>('');
  const [sessionId, setSessionId] = useState<string | null>(localStorage.getItem('session_id'));
  const [currentUserId, setCurrentUserId] = useState<string | null>(localStorage.getItem('user_id'));
  const [sessionName, setSessionName] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedNPCForDetails, setSelectedNPCForDetails] = useState<NPC | null>(null);
  const [settings, setSettings] = useState<any | null>(null);
  const [showGuide, setShowGuide] = useState<boolean>(false);
  const [guideContent, setGuideContent] = useState<string>(defaultGuideMd || '');
  const [selfRuns, setSelfRuns] = useState<any[]>([]);
  const [userInteractions, setUserInteractions] = useState<any[]>([]);
  // const [isLoadSessionOpen, setIsLoadSessionOpen] = useState(false);
  const [periods, setPeriods] = useState<TimePeriod[]>(Object.values(TimePeriod));
  const [currentSession, setCurrentSession] = useState<string | null>(null);
  // Live stream connection (SSE)
  const streamRef = useRef<EventSource | null>(null);
  // Timed test constraints (fast mode via ?fast=1 or localStorage.fast_test='1')
  const isFastMode = useMemo(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      return params.get('fast') === '1' || localStorage.getItem('fast_test') === '1';
    } catch {
      return false;
    }
  }, []);
  const MIN_TEST_MINUTES = isFastMode ? 0 : 15;
  const MIN_TEST_MESSAGES = isFastMode ? 1 : 20;
  const [currentTestIndex, setCurrentTestIndex] = useState<0 | 1 | null>(null);
  const [testStartAt, setTestStartAt] = useState<number | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);
  const [userMsgCount, setUserMsgCount] = useState<number>(0);
  const [sessionSurveyShown, setSessionSurveyShown] = useState<boolean>(false);
  // Admin-only features (e.g., Test 0–6 quick buttons)
  const [isAdmin, setIsAdmin] = useState<boolean>(false);

  const MAX_RENDERED_MESSAGES = 800;
  const pushMsg = (m: Message) => {
    setMessages(prev => prev.length >= MAX_RENDERED_MESSAGES ? [...prev.slice(-(MAX_RENDERED_MESSAGES - 1)), m] : [...prev, m]);
  };

  // Append an SSE payload into chat safely
  const appendSSEMessage = (d: any) => {
    try {
      const text = d?.message_text ?? d?.content ?? d?.text ?? '';
      if (!text) return;
      const npcName = (d?.npc ?? d?.sender ?? d?.speaker ?? d?.speaker_name ?? null) as string | null;
      const npc = npcName ? npcs.find(n => n.name === npcName) : undefined;
      const when = d?.timestamp ? new Date(d.timestamp) : new Date();
      const day = typeof d?.day === 'number' ? d.day : currentDay;
      const period = (d?.time_period ? String(d.time_period).toLowerCase() : currentTimePeriod) as TimePeriod;
      pushMsg({
        id: String(d?.message_id || `msg-${Date.now()}`),
        type: npcName ? MessageType.NPC : MessageType.SYSTEM,
        content: String(text),
        timestamp: when,
        day,
        timePeriod: period,
        npcId: npc ? npc.id : null,
        npcName: npcName,
      });
    } catch (err) {
      console.warn('appendSSEMessage error', err);
    }
  };

  // Helpers to map settings to UI types
  const mapPeriodsFromSettings = (s: any): TimePeriod[] => {
    // Always return all time periods regardless of settings to ensure filter works correctly
    return Object.values(TimePeriod);
  };

  const mapNPCsFromSettings = (s: any): NPC[] => {
    const templates: any[] = Array.isArray(s?.npc_templates) ? s.npc_templates : [];
    const fromTemplates = templates.map((t) => ({
      id: String(t.id || t.name || `npc-${Math.random().toString(36).slice(2,8)}`),
      name: String(t.name || t.id || 'Unknown'),
      status: NPCStatus.ONLINE as const,
      description: [t.role ? `Role: ${t.role}` : null, t.story ? String(t.story) : null].filter(Boolean).join(' — '),
      avatar: `https://i.pravatar.cc/150?u=${encodeURIComponent(t.id || t.name || Math.random())}`
    }));

    // Fallback to character_list if no templates
    if (fromTemplates.length) return fromTemplates;
    const cl = s?.character_list && typeof s.character_list === 'object' ? s.character_list : {};
    const fromCharacters: NPC[] = Object.values(cl).map((c: any) => ({
      id: `npc-${String(c.name || 'unknown').toLowerCase()}`,
      name: String(c.name || 'Unknown'),
      status: NPCStatus.ONLINE as const,
      description: [c.role ? `Role: ${c.role}` : null, c.story ? String(c.story) : null].filter(Boolean).join(' — '),
      avatar: `https://i.pravatar.cc/150?u=${encodeURIComponent(c.name || Math.random())}`
    }));
    return fromCharacters;
  };

  // Build NPCs from session data when available
  const mapNPCsFromSession = (session: any, msgs: any[]): NPC[] => {
    // Prefer character_list if present
    const cl: any[] = Array.isArray(session?.game_settings?.character_list) ? session.game_settings.character_list : [];
    if (cl.length) {
      return cl.map((c: any) => ({
        id: `npc-${String(c.name || 'unknown').toLowerCase()}`,
        name: String(c.name || 'Unknown'),
        status: NPCStatus.ONLINE as const,
        description: [c.role ? `Role: ${c.role}` : null, c.story ? String(c.story) : null].filter(Boolean).join(' — '),
        avatar: `https://i.pravatar.cc/150?u=${encodeURIComponent(c.name || Math.random())}`
      }));
    }
    // Fallback: derive distinct names from messages
    const names = new Set<string>();
    for (const m of msgs || []) {
      if (m.sender) names.add(String(m.sender));
      if (m.receiver) names.add(String(m.receiver));
    }
    return Array.from(names).filter(Boolean).map((n) => ({
      id: `npc-${n.toLowerCase()}`,
      name: n,
      status: NPCStatus.ONLINE as const,
      description: '',
      avatar: `https://i.pravatar.cc/150?u=${encodeURIComponent(n)}`
    }));
  };

  const normalizePeriod = (p: any): TimePeriod => {
    const s = String(p || '').toLowerCase();
    const allowed = new Set(Object.values(TimePeriod));
    return (allowed.has(s as TimePeriod) ? (s as TimePeriod) : TimePeriod.MORNING);
  };

  // Helper function to update message NPC IDs when NPCs are loaded
  const updateMessageNPCIds = (messages: Message[], npcs: NPC[]): Message[] => {
    return messages.map(msg => {
      if (msg.npcName && !msg.npcId) {
        const npc = npcs.find(n => n.name === msg.npcName);
        return {
          ...msg,
          npcId: npc ? npc.id : null,
          type: npc ? MessageType.NPC : msg.type
        };
      }
      return msg;
    });
  };

  const loadSession = async (sessionId: string) => {
    try {
      // Load core session info
      const res = await getSession(sessionId);
      setCurrentDay(Number(res.current_day || 1));
      setCurrentTimePeriod(normalizePeriod(res.current_time_period));
      // Track total days if available
      try {
        const total = Number(res?.game_settings?.time_config?.total_days || 0);
        if (total && total > 0) setNumDays(total);
      } catch {}
      setGameState(GameState.STOPPED);
      clearChatFilters(); // Clear filters when loading a session

      // Load NPC list first from backend session NPCs
      try {
        const npcsRes = await getSessionNPCs(sessionId);
        if (Array.isArray(npcsRes?.npcs)) {
          const mapped: NPC[] = (npcsRes.npcs || []).map((n: any) => ({
            id: `npc-${String(n.name || 'unknown').toLowerCase()}`,
            name: String(n.name || 'Unknown'),
            status: NPCStatus.ONLINE as const,
            description: [n.role ? `Role: ${n.role}` : null, n.story ? String(n.story) : null].filter(Boolean).join(' — '),
            avatar: `https://i.pravatar.cc/150?u=${encodeURIComponent(n.name || Math.random())}`
          }));
          // Always overwrite NPC list with session-backed data, even if empty
          setNpcs(mapped);
        }
      } catch {}

      // Load message history from backend (bounded) — admin only
      try {
        const hist = await getSessionMessages(sessionId, 300);
        const rawMessages = hist.messages || [];
        const loaded = rawMessages.map((m: any) => {
          // Find NPC by name to get proper ID
          const senderName = m.sender || '';
          // Do not depend on current npcs state for type; preserve sender as npcName
          return {
            id: m.message_id,
            type: senderName ? MessageType.NPC : MessageType.SYSTEM,
            content: m.message_text,
            timestamp: new Date(m.timestamp),
            day: Number(m.day || 1),
            timePeriod: String(m.time_period || '').toLowerCase() as TimePeriod,
            npcId: null,
            npcName: senderName || null
          };
        }) as Message[];
        if (isAdmin) {
          setMessages(loaded.slice(-MAX_RENDERED_MESSAGES));
        } else {
          // Hide previous messages for non-admin users
          setMessages([]);
        }
        // Derive session NPCs and update list
        const derivedNpcs = mapNPCsFromSession(res, rawMessages);
        if (derivedNpcs.length) setNpcs(derivedNpcs);
      } catch {
        setMessages([]);
      }

      // Removed SSE stream opening - using direct request-response now

      // Load available periods per selected/current day for filters
      try {
        const dp = await getSessionDayPeriods(sessionId);
        const selDay = chatFilters.selectedDay || res.current_day || 1;
        const dayEntry = (dp.days || []).find((d: any) => Number(d.day) === Number(selDay));
        const list = (dayEntry?.periods || dp.all_periods || Object.values(TimePeriod))
          .map((p: string) => String(p).toLowerCase()) as TimePeriod[];
        setPeriods(list);
      } catch {}
    } catch (error) {
      console.error('Failed to load session:', error);
    }
  };

  const normalizeGameState = (gs: any): GameState => {
    const s = String(gs || '').toLowerCase();
    const allowed = new Set(Object.values(GameState));
    return (allowed.has(s as GameState) ? (s as GameState) : GameState.STOPPED);
  };

  // Filter messages based on current filters
  const filteredMessages = useMemo(() => {
    const M = 400; // cap rendered messages for performance
    const out = messages.filter(message => {
      if (chatFilters.selectedDay && message.day !== chatFilters.selectedDay) {
        return false;
      }
      if (chatFilters.selectedTimePeriod && message.timePeriod !== chatFilters.selectedTimePeriod) {
        return false;
      }
      if (chatFilters.selectedNPCId && message.npcId !== chatFilters.selectedNPCId) {
        return false;
      }
      return true;
    });
    return out.length > M ? out.slice(-M) : out;
  }, [messages, chatFilters]);

  // Update available periods whenever selected day or session changes
  useEffect(() => {
    const run = async () => {
      const sid = localStorage.getItem('session_id') || sessionId || '';
      if (!sid) return;
      try {
        const dp = await getSessionDayPeriods(sid);
        const selDay = chatFilters.selectedDay || currentDay || 1;
        const dayEntry = (dp.days || []).find((d: any) => Number(d.day) === Number(selDay));
        const list = (dayEntry?.periods || dp.all_periods || Object.values(TimePeriod))
          .map((p: string) => String(p).toLowerCase()) as TimePeriod[];
        setPeriods(list);
        // If current selected period not available for this day, clear to 'All'
        if (chatFilters.selectedTimePeriod && !list.includes(chatFilters.selectedTimePeriod)) {
          setChatFilters({ selectedTimePeriod: null });
        }
      } catch {}
    };
    run();
  }, [sessionId, chatFilters.selectedDay]);

  const selectedNPC = npcs.find(npc => npc.id === selectedNPCId) || null;
  const playerNPC = npcs.find(npc => npc.id === playerNpcId) || null;
  const talkTargetNPC = npcs.find(npc => npc.id === talkTargetNpcId) || null;

  // Bootstrap: ensure user id and load settings from backend
  useEffect(() => {
    let mounted = true;
    (async () => {
      // Determine admin mode from localStorage or URL query
      try {
        const role = localStorage.getItem('role') || '';
        const adminFlag = localStorage.getItem('is_admin') || '';
        const params = new URLSearchParams(window.location.search);
        const qAdmin = params.get('admin');
        if (mounted) setIsAdmin(role === 'admin' || adminFlag === '1' || qAdmin === '1');
      } catch {}

      try {
        const uid = await ensureUserId();
        setCurrentUserId(uid);
        
        // Initialize questionnaire system for this user
        initializeUser(uid);
        
        // Ensure user has their default Test 0 session
        await ensureUserSessions(uid);
        
        // Check if there's a saved session in localStorage
        const savedSessionId = localStorage.getItem('session_id');
        let shouldLoadDefaultSession = true;
        
        if (savedSessionId) {
          try {
            // Verify the saved session exists and belongs to this user
            const session = await getSession(savedSessionId);
            if (session && session.game_settings?.experiment?.user_id === uid) {
              // Set as active session in backend
              await setActiveSession(uid, savedSessionId);
              
              // Load the saved session
              setSessionId(savedSessionId);
              if (session?.name) setSessionName(String(session.name));
              
              try {
            const hist = await getSessionMessages(savedSessionId, 300);
                const loaded = (hist.messages || []).map((m: any) => {
                  const senderName = m.sender || '';
                  const npc = npcs.find(n => n.name === senderName) || null;
                  
                  return {
                    id: m.message_id,
                    type: npc ? MessageType.NPC : MessageType.SYSTEM,
                    content: m.message_text,
                    timestamp: new Date(m.timestamp),
                    day: Number(m.day || 1),
                    timePeriod: String(m.time_period || '').toLowerCase() as TimePeriod,
                    npcId: npc ? npc.id : null,
                    npcName: senderName || null
                  };
                }) as Message[];
                if (isAdmin) {
                  setMessages(loaded.slice(-MAX_RENDERED_MESSAGES));
                } else {
                  setMessages([]);
                }
              } catch {
                setMessages([]);
              }
              
              setCurrentDay(Number(session.current_day ?? 1));
              setCurrentTimePeriod(normalizePeriod(session.current_time_period));
              setGameState(normalizeGameState(session.game_settings?.client_state?.game_state));
              clearChatFilters(); // Clear filters when loading saved session
              // Removed SSE stream opening - using direct request-response now
              shouldLoadDefaultSession = false;
            }
          } catch (e) {
            console.warn('Saved session not valid, will load default:', e);
            localStorage.removeItem('session_id');
          }
        }
        
        if (shouldLoadDefaultSession && isAdmin) {
          // Load the user's Test 0 session by default
          try {
            const test0SessionId = await getUserTestSession(uid, 0);
            await setActiveSession(uid, test0SessionId);
            localStorage.setItem('session_id', test0SessionId);
            setSessionId(test0SessionId);
            setSessionName('Test 0: Fresh World');
            // Removed SSE stream opening - using direct request-response now
            
            setMessages([{
              id: `msg-${Date.now()}`,
              type: MessageType.SYSTEM,
              content: `🏰 Admin: Loaded Test 0 (Fresh World).`,
              timestamp: new Date(),
              day: currentDay,
              timePeriod: currentTimePeriod,
              npcId: null,
              npcName: null
            }]);
          } catch (e) {
            console.warn('Failed to load default Test 0 session (admin):', e);
          }
        }

        // Note: session auto-switch logic already exists elsewhere in the app flow.
      } catch (error: unknown) {
        console.warn('ensureUserId failed:', error);
      }
      
      try {
        const res = await fetchSettings();
        if (mounted) {
          setSettings(res.settings);
          // Apply world calendar settings
          const p = mapPeriodsFromSettings(res.settings);
          setPeriods(p);
          const hasSession = !!localStorage.getItem('session_id');
          if (!hasSession && p.length) {
            setCurrentTimePeriod(p[0]);
          }
          // Do NOT initialize NPCs from settings; NPCs should only come from DB when a session loads
          // Load USER_STUDY_GUIDE.md for guide modal content
          try {
            const resp = await fetch('/USER_STUDY_GUIDE.md');
            if (resp.ok) {
              const txt = await resp.text();
              setGuideContent(txt);
            }
          } catch {}
        }
      } catch (error: unknown) {
        console.warn('fetchSettings failed, using local defaults:', error);
        if (mounted) {
          // Do not set mock NPCs; leave empty until a session loads
          setPeriods(Object.values(TimePeriod));
        }
      }
      
      // Load available self-run experiments as tests (for fallback)
      try {
        const runs = await listSelfRuns();
        if (mounted && Array.isArray(runs)) setSelfRuns(runs);
      } catch (e) {
        console.warn('listSelfRuns failed:', e);
      }
    })();
    return () => { mounted = false; };
  }, []);

  // Update message NPC IDs when NPCs are loaded
  useEffect(() => {
    if (npcs.length > 0) {
      setMessages(prev => updateMessageNPCIds(prev, npcs));
    }
  }, [npcs]);

  // Ensure NPCs load whenever the active session changes
  useEffect(() => {
    // Reset selections and chat when switching sessions so UI reflects the new session
    setSelectedNPCId(null);
    setPlayerNpcId(null);
    setTalkTargetNpcId(null);
    setMessages([]);

    (async () => {
      const sid = sessionId || localStorage.getItem('session_id');
      if (!sid) return;
      try {
        const npcsRes = await getSessionNPCs(sid);
        if (Array.isArray(npcsRes?.npcs)) {
          const mapped: NPC[] = (npcsRes.npcs || []).map((n: any) => ({
            id: `npc-${String(n.name || 'unknown').toLowerCase()}`,
            name: String(n.name || 'Unknown'),
            status: NPCStatus.ONLINE as const,
            description: [n.role ? `Role: ${n.role}` : null, n.story ? String(n.story) : null].filter(Boolean).join(' — '),
            avatar: `https://i.pravatar.cc/150?u=${encodeURIComponent(n.name || Math.random())}`
          }));
          setNpcs(mapped);
        }
      } catch {}
    })();
  }, [sessionId]);

  // Show demographics first (pre-game questionnaire)
  useEffect(() => {
    if (!userProgress || isQuestionnaireOpen) return;
    if (userProgress.currentPhase === StudyPhase.PRE_GAME && !userProgress.completedQuestionnaires.includes('questionnaire_pre_game')) {
      showQuestionnaire(StudyPhase.PRE_GAME);
    }
  }, [userProgress, isQuestionnaireOpen, showQuestionnaire]);

  // Test timer tick
  useEffect(() => {
    if (!testStartAt) return;
    const id = setInterval(() => setElapsedSeconds(Math.floor((Date.now() - testStartAt) / 1000)), 1000);
    return () => clearInterval(id);
  }, [testStartAt]);

  // Auto-advance tests when thresholds met (2 sequential tests per phase)
  useEffect(() => {
    if (!userProgress || isQuestionnaireOpen) return;
    if (currentTestIndex === null || testStartAt === null) return;
    const timeOk = elapsedSeconds >= (MIN_TEST_MINUTES * 60);
    const msgOk = userMsgCount >= MIN_TEST_MESSAGES;
    if (timeOk && msgOk) {
      // If first test in this part is done, start second test
      if (currentTestIndex === 0) {
        startTest(1);
      } else if (currentTestIndex === 1 && !sessionSurveyShown) {
        setSessionSurveyShown(true);
        // End of part: open appropriate questionnaire
        if (userProgress.currentPhase === StudyPhase.SESSION_1) {
          showQuestionnaire(StudyPhase.SESSION_1);
        } else if (userProgress.currentPhase === StudyPhase.SESSION_2) {
          showQuestionnaire(StudyPhase.SESSION_2);
        }
      }
    }
  }, [elapsedSeconds, userMsgCount, sessionSurveyShown, currentTestIndex, testStartAt, userProgress, isQuestionnaireOpen, showQuestionnaire]);

  // (parts removed) — tests are time/message gated

  // Update session IDs for questionnaire tracking
  useEffect(() => {
    if (sessionId && userProgress) {
      const currentPhase = userProgress.currentPhase;
      if (currentPhase === StudyPhase.SESSION_1 && !userProgress.sessionIds.session1) {
        setStudySessionId('session1', sessionId);
      } else if (currentPhase === StudyPhase.SESSION_2 && !userProgress.sessionIds.session2) {
        setStudySessionId('session2', sessionId);
      }
    }
  }, [sessionId, userProgress, setStudySessionId]);

  // Start a planned test by importing a base checkpoint into a user session
  const startTest = async (index: 0 | 1) => {
    try {
      const uid = await ensureUserId();
      // Plans by phase: 2 tests per part
      const plans: Record<string, { sources: string[]; labels: string[]; testIndexes: number[] }> = {
        [StudyPhase.SESSION_1]: {
          sources: ['exp_gpt5_all_gpt5_rep_on', 'exp_gpt5_all_gpt5_rep_off'],
          labels:  ['GPT‑5 — Rep ON',               'GPT‑5 — Rep OFF'],
          testIndexes: [1, 2]
        },
        [StudyPhase.SESSION_2]: {
          sources: ['exp_mixed_social_1b_game_8b_mixed_rep_on', 'exp_mixed_social_1b_game_8b_mixed_rep_off'],
          labels:  ['Mixed — Rep ON',                            'Mixed — Rep OFF'],
          testIndexes: [3, 4]
        }
      } as any;
      const phase = userProgress?.currentPhase || StudyPhase.SESSION_1;
      const plan = plans[phase];
      const sourceSessionId = plan.sources[index];
      const testLabel = plan.labels[index];
      const testIndex = plan.testIndexes[index];

      const sid = await getUserTestSession(uid, testIndex, sourceSessionId);
      await setActiveSession(uid, sid);
      localStorage.setItem('session_id', sid);
      setSessionId(sid);
      setSessionName(`User Test ${testIndex} — ${testLabel}`);
      setCurrentTestIndex(index);
      // Phase stays as-is; this function is called after phase has been set
      setUserMsgCount(0);
      setSessionSurveyShown(false);
      setTestStartAt(Date.now());
      setElapsedSeconds(0);
      setMessages([]);
      clearChatFilters(); // Clear filters when starting a new test
      // Removed SSE stream opening - using direct request-response now
      try {
        const session = await getSession(sid);
        if (session) {
          setCurrentDay(Number(session.current_day ?? 1));
          setCurrentTimePeriod(normalizePeriod(session.current_time_period));
          setGameState(normalizeGameState(session.game_settings?.client_state?.game_state));
        }
        const hist = await getSessionMessages(sid, 300);
        const loaded = (hist.messages || []).map((m: any) => {
          const senderName = m.sender || '';
          const npc = npcs.find(n => n.name === senderName) || null;
          
          return {
            id: m.message_id,
            type: npc ? MessageType.NPC : MessageType.SYSTEM,
            content: m.message_text,
            timestamp: new Date(m.timestamp),
            day: Number(m.day || 1),
            timePeriod: String(m.time_period || '').toLowerCase() as TimePeriod,
            npcId: npc ? npc.id : null,
            npcName: senderName || null
          };
        }) as Message[];
        if (isAdmin && loaded.length) setMessages(loaded.slice(-MAX_RENDERED_MESSAGES));
      } catch {}
    } catch (e) {
      console.warn('Failed to start test', index + 1, e);
    }
  };

  // Game control handlers
  const handleStartGame = async () => {
    try {
      setIsLoading(true);
      // Immediate UI feedback
      setGameState(GameState.RUNNING);
      const userId = await ensureUserId();
      // ensure a session exists
      let sessionId = localStorage.getItem('session_id');
      if (!sessionId) {
        const defaultName = `Run ${new Date().toLocaleString()}`;
        const res = await createSession({
          user_id: userId,
          name: defaultName,
          status: 'started',
          current_day: currentDay,
          time_period: currentTimePeriod,
          game_state: gameState,
          messages,
          seed_settings_version: settings?.version || 'v1',
        } as any);
        sessionId = res.session_id;
        localStorage.setItem('session_id', sessionId);
        setSessionId(sessionId);
        setSessionName(defaultName);
      }

      // start backend loop
      const startRes = await startGame(sessionId!, numDays);
      // Log a system message to confirm backend accepted start
      setMessages(prev => [
        ...prev,
        {
          id: `msg-${Date.now()}`,
          type: MessageType.SYSTEM,
          content: `🔧 Start requested (session ${sessionId}). Backend acknowledged: ${startRes?.started ? 'yes' : 'no'}`,
          timestamp: new Date(),
          day: currentDay,
          timePeriod: currentTimePeriod,
          npcId: null,
          npcName: null
        }
      ]);

      // Game stream removed - using direct request-response now
      // No system chat line; UI shows DB-backed content only
    } catch (error: unknown) {
      console.warn('Failed to start game:', error);
      // No system chat line
    } finally {
      setIsLoading(false);
    }
  };

  const handleStopGame = async () => {
    try {
      setIsLoading(true);
      const sid = localStorage.getItem('session_id');
      if (sid) {
        await stopGame(sid);
      }
      // Stream handling removed - using direct request-response now
      setGameState(GameState.STOPPED);
      // No system chat line
    } catch (error: unknown) {
      console.warn('Failed to stop game:', error);
      // No system chat line
    } finally {
      setIsLoading(false);
    }
  };

  const handleContinueGame = () => {
    setGameState(GameState.RUNNING);
    // No system chat line
  };

  const handlePauseGame = () => {
    setGameState(GameState.PAUSED);
    // No system chat line
  };

  const handleResetGame = async () => {
    try {
      await fetch('http://localhost:8000/api/settings/reset', { method: 'POST' });
      await fetchSettings();
      setGameState(GameState.STOPPED);
      setCurrentDay(1);
      setMessages([]);
    } catch (error) {
      console.error('Failed to reset game:', error);
    }
  };

  const handleResetAll = async () => {
    try {
      if (!currentUserId) {
        console.warn('No current user ID for reset');
        return;
      }

      // Confirm action
      if (!window.confirm('This will reset ALL sessions and user data. Are you sure?')) {
        return;
      }

      // Reset user sessions on backend
      await resetUserSessions(currentUserId);
      
      // Clear frontend state
      setGameState(GameState.STOPPED);
      setCurrentDay(1);
      setMessages([]);
      setSessionId(null);
      setSessionName(null);
      // Clear questionnaire/user study progress state
      try { resetQuestionnaire(); } catch {}
      
      // Clear localStorage
      localStorage.removeItem('session_id');
      localStorage.removeItem('user_id');
      
      // Re-initialize user
      const newUserId = await ensureUserId();
      setCurrentUserId(newUserId);
      
      console.log('All sessions and user data reset successfully');
    } catch (error) {
      console.error('Failed to reset all sessions:', error);
      alert('Failed to reset sessions. Please try again.');
    }
  };

  const handleNewGame = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: `Session ${new Date().toISOString()}` })
      });
      if (response.ok) {
        const session = await response.json();
        setCurrentSession(session.id);
        await loadSession(session.id);
      }
    } catch (error) {
      console.error('Failed to create new game:', error);
    }
  };

  // Player chat send via backend
  const handleSendMessage = async (content: string, keystrokes?: number, approxTokens?: number) => {
    if (!playerNPC || !talkTargetNPC) return;
    if (playerNPC.id === talkTargetNPC.id) return;
    const sid = localStorage.getItem('session_id');
    if (!sid) {
      setMessages(prev => [...prev, {
        id: `msg-${Date.now()}`,
        type: MessageType.SYSTEM,
        content: `⚠️ Create or resume a session before chatting.`,
        timestamp: new Date(), day: currentDay, timePeriod: currentTimePeriod, npcId: null, npcName: null
      }]);
      return;
    }

    try {
      const approx_tokens = Math.ceil(content.trim().split(/\s+/).filter(Boolean).length * 1.3);
      
      // Add user message to UI first
      const userMessage: Message = {
        id: `msg-${Date.now()}-user`,
        type: MessageType.USER,
        content: content,
        timestamp: new Date(),
        day: currentDay,
        timePeriod: currentTimePeriod,
        npcId: playerNPC.id,
        npcName: playerNPC.name
      };
      pushMsg(userMessage);
      
      // Send chat and get direct response
      const response = await sendPlayerChatWithStats({ 
        session_id: sid, 
        as_npc: playerNPC.name, 
        to_npc: talkTargetNPC.name, 
        message: content, 
        keystrokes, 
        approx_tokens 
      });
      
      // If there's a response in the API result, display it immediately
      if (response && response.response) {
        const npcResponse: Message = {
          id: `msg-${Date.now()}-npc`,
          type: MessageType.NPC,
          content: response.response.message || response.response.text || 'No response',
          timestamp: new Date(),
          day: currentDay,
          timePeriod: currentTimePeriod,
          npcId: talkTargetNPC.id,
          npcName: talkTargetNPC.name
        };
        pushMsg(npcResponse);
      }
      
      // Also refresh DB messages for admins; non-admins keep only the current conversation context
      if (isAdmin) {
        try {
          const hist = await getSessionMessages(sid, 50); // Get fewer messages to avoid old ones
          const loaded = (hist.messages || []).slice(-10).map((m: any) => ({
            id: m.message_id || `msg-${Date.now()}-${Math.random()}`,
            type: MessageType.NPC, // will be corrected by updateMessageNPCIds below
            content: m.message_text,
            timestamp: new Date(m.timestamp),
            day: m.day,
            timePeriod: String(m.time_period || '').toLowerCase() as TimePeriod,
            npcId: null,
            npcName: m.sender || null
          })) as Message[];
          
          // Only add new messages that aren't already in our current messages
          const currentMessageIds = new Set(messages.map(m => m.id));
          const newMessages = loaded.filter(m => !currentMessageIds.has(m.id));
          if (newMessages.length > 0) {
            setMessages(prev => [...prev, ...updateMessageNPCIds(newMessages, npcs)]);
          }
        } catch {}
      }
      
      // Track user chat count for current timed test
      setUserMsgCount((c) => c + 1);
      
    } catch (e) {
      setMessages(prev => [...prev, {
        id: `msg-${Date.now()}`,
        type: MessageType.SYSTEM,
        content: `❌ Failed to send chat: ${String((e as any)?.message || e)}`,
        timestamp: new Date(), day: currentDay, timePeriod: currentTimePeriod, npcId: null, npcName: null
      }]);
    }
  };

  const handleCreateCharacter = async (characterData: Omit<Character, 'id' | 'createdAt'>) => {
    const newCharacter: Character = {
      ...characterData,
      id: `char-${Date.now()}`,
      createdAt: new Date()
    };

    console.log('Created character:', newCharacter);

    const systemMessage: Message = {
      id: `msg-${Date.now()}`,
      type: MessageType.SYSTEM,
      content: `🏰 Welcome to the realm, ${newCharacter.name}${newCharacter.role ? ` the ${newCharacter.role}` : ''}! Your legend begins now.`,
      timestamp: new Date(),
      day: currentDay,
      timePeriod: currentTimePeriod,
      npcId: null,
      npcName: null
    };

    // snapshot messages including the welcome system message
    const messagesSnapshot = [...messages, systemMessage];
    setMessages(messagesSnapshot);

    // create a backend session tied to this user & character
    try {
      setIsLoading(true);
      const userId = await ensureUserId();
      const defaultName = `Run ${new Date().toLocaleString()}`;
      const res = await createSession({
        user_id: userId,
        name: defaultName,
        status: 'started',
        current_day: currentDay,
        time_period: currentTimePeriod,
        game_state: gameState,
        character: newCharacter,
        messages: messagesSnapshot,
        seed_settings_version: settings?.version || 'v1',
      } as any);
      localStorage.setItem('session_id', res.session_id);
      setSessionId(res.session_id);
      setSessionName(defaultName);
    } catch (error: unknown) {
      console.warn('Failed to create session:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRenameSession = async () => {
    try {
      const sid = localStorage.getItem('session_id');
      if (!sid) return;
      const newName = window.prompt('Enter new session name', sessionName || '')?.trim();
      if (!newName || newName === sessionName) return;
      await saveSession(sid, { name: newName } as any);
      setSessionName(newName);
    } catch (e) {
      console.warn('Rename failed:', e);
    }
  };

  const handleNPCDoubleClick = (npc: NPC) => {
    setSelectedNPCForDetails(npc);
  };

  const handleStartChatFromDetails = (npcId: string) => {
    setSelectedNPCId(npcId);
  };

  // Player UI actions
  const handlePlayAs = (npc: NPC) => {
    setPlayerNpcId(npc.id);
    if (talkTargetNpcId && talkTargetNpcId === npc.id) setTalkTargetNpcId(null);
    setMessages(prev => [...prev, {
      id: `msg-${Date.now()}`,
      type: MessageType.SYSTEM,
      content: `🧍 You are now playing as ${npc.name}. Choose someone to talk to.`,
      timestamp: new Date(),
      day: currentDay,
      timePeriod: currentTimePeriod,
      npcId: null,
      npcName: null
    }]);
  };

  const handleTalk = (npc: NPC) => {
    if (!playerNPC) {
      setMessages(prev => [...prev, {
        id: `msg-${Date.now()}`,
        type: MessageType.SYSTEM,
        content: `⚠️ Select an NPC with "Play as" before talking.`,
        timestamp: new Date(), day: currentDay, timePeriod: currentTimePeriod, npcId: null, npcName: null
      }]);
      return;
    }
    if (playerNPC.id === npc.id) {
      setMessages(prev => [...prev, {
        id: `msg-${Date.now()}`,
        type: MessageType.SYSTEM,
        content: `⚠️ You can’t talk to yourself. Pick another NPC.`,
        timestamp: new Date(), day: currentDay, timePeriod: currentTimePeriod, npcId: null, npcName: null
      }]);
      return;
    }
    setTalkTargetNpcId(npc.id);
    setSelectedNPCId(npc.id);
    setMessages(prev => [...prev, {
      id: `msg-${Date.now()}`,
      type: MessageType.SYSTEM,
      content: `💬 Talking to ${npc.name} as ${playerNPC.name}.`,
      timestamp: new Date(), day: currentDay, timePeriod: currentTimePeriod, npcId: null, npcName: null
    }]);
  };

  // Questionnaire handlers
  const handleQuestionnaireComplete = () => {
    // Persist questionnaire responses to backend ux_metrics for analysis
    try {
      if (currentQuestionnaire && currentResponses) {
        const userId = localStorage.getItem('user_id') || '';
        const session_id = sessionId || localStorage.getItem('session_id') || '';
        
        // Auto-assign user ID to questionnaire responses
        const enrichedResponses = currentResponses.map(response => ({
          ...response,
          userId
        }));
        
        fetch(((import.meta as any).env?.VITE_API_BASE || 'http://localhost:8000/api') + '/questionnaire/submit', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_id: userId,
            session_id,
            questionnaire_id: currentQuestionnaire.id,
            phase: currentQuestionnaire.phase,
            responses: enrichedResponses
          })
        }).catch((err) => {
          console.error('Failed to submit questionnaire:', err);
        });
      }
    } catch (error) {
      console.error('Error in questionnaire submission:', error);
    }

    completeQuestionnaire();
    
    // Advance to next phase if appropriate
    if (userProgress && currentQuestionnaire) {
      const currentPhase = currentQuestionnaire.phase;
      if (currentPhase === StudyPhase.PRE_GAME) {
        advanceStudyPhase(StudyPhase.SESSION_1);
        // Show guide; on close Session 1 test will auto-start
        setShowGuide(true);
      } else if (currentPhase === StudyPhase.SESSION_1) {
        advanceStudyPhase(StudyPhase.SESSION_2);
        // Start first mixed test for Session 2
        startTest(0);
      } else if (currentPhase === StudyPhase.SESSION_2) {
        advanceStudyPhase(StudyPhase.FINAL_COMPARE);
        // Show final comparison survey
        showQuestionnaire(StudyPhase.FINAL_COMPARE);
      }
    }
  };

  const handleQuestionnaireClose = () => {
    // Only allow closing if it's not a required questionnaire or if it's already completed
    const canClose = !currentQuestionnaire?.required || 
      (userProgress?.completedQuestionnaires.includes(currentQuestionnaire?.id || '') || false);
    
    if (canClose) {
      closeQuestionnaire();
    }
  };

  // Stream cleanup removed - no longer using SSE

  return (
    <Box className="h-screen bg-background-default flex flex-col overflow-hidden">
      {/* Enhanced Header */}
      <AppBar position="static" color="primary" className="medieval-shadow flex-shrink-0">
        <Toolbar className="min-h-[56px]">
          <SportsEsportsOutlinedIcon className="mr-2" />
          <Typography variant="h1" className="flex-1 text-center" sx={{ fontSize: '1.75rem' }}>
            🏰 NarrativeHive
          </Typography>
          <Stack direction="row" spacing={1} alignItems="center">
            {/* Test 0-6 buttons (admin only) */}
            {isAdmin && [0, 1, 2, 3, 4, 5, 6].map((testIndex) => (
              <Button
                key={testIndex}
                size="small"
                variant="contained"
                color={testIndex === 0 ? "primary" : "secondary"}
                onClick={async () => {
                  try {
                    const uid = await ensureUserId();
                    
                    let sourceSessionId = '';
                    if (testIndex > 0) {
                      // For Test 1-6, get source session from quick_tests or selfRuns
                      const quickTests = (settings as any)?.ui?.quick_tests || [];
                      if (quickTests[testIndex - 1]?.source_session_id) {
                        sourceSessionId = quickTests[testIndex - 1].source_session_id;
                      } else if (selfRuns[testIndex - 1]?.session_id) {
                        sourceSessionId = selfRuns[testIndex - 1].session_id;
                      } else {
                        setMessages(prev => [...prev, {
                          id: `msg-${Date.now()}`,
                          type: MessageType.SYSTEM,
                          content: `❌ Test ${testIndex} not available - no checkpoint configured`,
                          timestamp: new Date(),
                          day: currentDay,
                          timePeriod: currentTimePeriod,
                          npcId: null,
                          npcName: null
                        }]);
                        return;
                      }
                    }
                    
                    // Get or create the test session
                    const sessionId = await getUserTestSession(uid, testIndex, sourceSessionId);
                    
                    // Set as active session in backend
                    await setActiveSession(uid, sessionId);
                    
                    // Switch to this session in frontend
                    localStorage.setItem('session_id', sessionId);
                    setSessionId(sessionId);
                    setSessionName(`Test ${testIndex}${testIndex === 0 ? ': Fresh World' : ''}`);
                    
                    // Load session data and messages
                    setMessages([]);
                    // Stream opening removed - using direct request-response now
                    
                    try {
                      const session = await getSession(sessionId);
                      if (session) {
                        setCurrentDay(Number(session.current_day ?? 1));
                        setCurrentTimePeriod(normalizePeriod(session.current_time_period));
                        setGameState(normalizeGameState(session.game_settings?.client_state?.game_state));
                      }
                      
                      const hist = await getSessionMessages(sessionId, 300);
                      const loaded = (hist.messages || []).map((m: any) => ({
                        id: m.message_id,
                        type: MessageType.NPC,
                        content: m.message_text,
                        timestamp: new Date(m.timestamp),
                        day: m.day,
                        timePeriod: String(m.time_period || '').toLowerCase() as TimePeriod,
                        npcId: null,
                        npcName: m.sender || null
                      })) as Message[];
        if (isAdmin && loaded.length) setMessages(loaded.slice(-MAX_RENDERED_MESSAGES));
                    } catch {}
                    
                    setMessages(prev => [...prev, {
                      id: `msg-${Date.now()}`,
                      type: MessageType.SYSTEM,
                      content: `🔬 Loaded Test ${testIndex}${testIndex === 0 ? ' (Fresh World)' : ''}`,
                      timestamp: new Date(),
                      day: currentDay,
                      timePeriod: currentTimePeriod,
                      npcId: null,
                      npcName: null
                    }]);
                  } catch (e) {
                    console.warn(`Test ${testIndex} failed:`, e);
                    setMessages(prev => [...prev, {
                      id: `msg-${Date.now()}`,
                      type: MessageType.SYSTEM,
                      content: `❌ Failed to load Test ${testIndex}: ${e instanceof Error ? e.message : String(e)}`,
                      timestamp: new Date(),
                      day: currentDay,
                      timePeriod: currentTimePeriod,
                      npcId: null,
                      npcName: null
                    }]);
                  }
                }}
              >
                Test {testIndex}
              </Button>
            ))}
            {/* Study timer & message count */}
            {userProgress && (userProgress.currentPhase === StudyPhase.SESSION_1 || userProgress.currentPhase === StudyPhase.SESSION_2) && (
              <Chip
                size="small"
                color="info"
                label={`Study: ${userProgress.currentPhase === StudyPhase.SESSION_1 ? 'Session 1' : 'Session 2'} • ${Math.floor(elapsedSeconds/60)}:${String(elapsedSeconds%60).padStart(2,'0')} • ${userMsgCount} msgs`}
              />
            )}
            {isFastMode && (
              <Chip size="small" color="success" variant="outlined" label="Fast mode" />
            )}

            {sessionId && (
            <Stack direction="row" spacing={1} alignItems="center" className="mr-2">
                {/* Show user id (short) */}
                <Chip size="small" variant="outlined" color="default" label={`User: ${currentUserId ? currentUserId.replace('user', '') : 'unknown'}`} />
                {playerNPC && (
                  <Chip size="small" color="primary" label={`Playing as: ${playerNPC.name}`} />
                )}
                <Button size="medium" variant="outlined" color='secondary' onClick={() => setShowGuide(true)}>Guide</Button>
                <Tooltip title={sessionName ? `Session: ${sessionName}` : 'Session ID'}>
                  <Chip
                    size="small"
                    label={`ID: ${String(sessionId)}`}
                    variant="outlined"
                    color="default"
                  />
                </Tooltip>
                <Tooltip title="Rename session">
                  <span>
                    <IconButton color="inherit" size="small" onClick={handleRenameSession}>
                      <EditIcon fontSize="small" />
                    </IconButton>
                  </span>
                </Tooltip>
              </Stack>
            )}
            <IconButton 
              color="inherit" 
              onClick={() => setCharacterCreationOpen(true)}
              title="Create Character"
              className="hover:scale-110 transition-transform"
              size="small"
            >
              <PersonOutlinedIcon />
            </IconButton>
            {/* Load Session removed for user flow */}
            <IconButton 
              color="inherit" 
              onClick={() => setAdminPanelOpen(true)}
              title="Admin Panel"
              className="hover:scale-110 transition-transform"
              size="small"
            >
              <SettingsOutlinedIcon />
            </IconButton>
          </Stack>
        </Toolbar>
      </AppBar>

      <Box 
        className="flex-1 flex flex-col overflow-hidden"
        sx={{ height: 'calc(100vh - 64px)' }} // Account for AppBar height
      >
        {/* (Removed) Top filters on desktop; mobile filters remain within layout */}

        {/* Main Game Layout */}
        <Box 
          className="flex-1 grid gap-2 px-4 overflow-hidden"
          sx={{
            pb: { xs: '260px', md: 2 },
            height: '100%',
            gridTemplateColumns: {
              xs: '1fr', // Mobile: single column
              sm: '1fr', // Small tablets: single column
              md: '320px 1fr', // Medium: sidebar + main
              lg: '360px 1fr', // Large: sidebar + main
              xl: '400px 1fr' // Extra large: wider sidebar
            },
            gridTemplateRows: {
              xs: 'auto minmax(0, 1fr)', // Mobile: controls, chat (with min height 0)
              sm: 'auto minmax(0, 1fr)', // Small: same as mobile
              md: '1fr', // Medium+: single row
              lg: '1fr',
              xl: '1fr'
            },
            gridTemplateAreas: {
              xs: `
                "controls"
                "chat"
              `,
              sm: `
                "controls"
                "chat"
              `,
              md: `
                "sidebar main"
              `,
              lg: `
                "sidebar main"
              `,
              xl: `
                "sidebar main"
              `
            }
          }}
        >
          {/* Mobile Controls (only visible on mobile) */}
          <Box 
            sx={{ 
              gridArea: 'controls',
              display: { xs: 'block', md: 'none' }
            }}
          >
            {isAdmin && (
            <GameControls
              gameState={gameState}
              currentDay={currentDay}
              currentTimePeriod={currentTimePeriod}
              numDays={numDays}
              onNumDaysChange={setNumDays}
              onStart={handleStartGame}
              onStop={handleStopGame}
              onPause={handlePauseGame}
              onContinue={handleContinueGame}
              onReset={handleResetGame}
              onNewGame={handleNewGame}
              onResetAll={handleResetAll}
              isLoading={false}
              sessionId={sessionId || undefined}
              sessionName={sessionName || undefined}
              onRenameSession={handleRenameSession}
            />)}
            {/* Mobile Filters below controls */}
            {isAdmin && (
              <Box className="mt-2">
                <ChatFilters
                  filters={chatFilters}
                  onFiltersChange={setChatFilters}
                  onClearFilters={clearChatFilters}
                  maxDay={Math.max(Number(numDays || currentDay), ...messages.map(m => m.day || 1), currentDay)}
                  currentDay={currentDay}
                  currentTimePeriod={currentTimePeriod}
                  npcs={npcs}
                  periods={periods}
                />
              </Box>
            )}
          </Box>

          {/* Left Sidebar (Desktop) */}
          <Box 
            sx={{ 
              gridArea: 'sidebar',
              display: { xs: 'none', md: 'flex' },
              flexDirection: 'column',
              gap: 1,
              overflow: 'hidden'
            }}
          >
            <Box className="flex-shrink-0">
              {isAdmin && (
              <GameControls
                gameState={gameState}
                currentDay={currentDay}
                currentTimePeriod={currentTimePeriod}
                numDays={numDays}
                onNumDaysChange={setNumDays}
                onStart={handleStartGame}
                onStop={handleStopGame}
                onPause={handlePauseGame}
                onContinue={handleContinueGame}
                onReset={handleResetGame}
                onNewGame={handleNewGame}
                onResetAll={handleResetAll}
                isLoading={false}
                sessionId={sessionId || undefined}
                sessionName={sessionName || undefined}
                onRenameSession={handleRenameSession}
              />)}
            </Box>
            
            <Box className="flex-1 min-h-0 overflow-hidden">
              {sessionId ? (
                <NPCPanel
                  npcs={npcs}
                  selectedNPCId={selectedNPCId}
                  onNPCSelect={setSelectedNPCId}
                  onNPCDoubleClick={handleNPCDoubleClick}
                  onPlayAs={handlePlayAs}
                  onTalk={handleTalk}
                  activePlayerNpcId={playerNPC?.id || null}
                  activeTalkTargetId={talkTargetNPC?.id || null}
                />
              ) : null}
            </Box>
          </Box>

          {/* Main Chat Area */}
          <Box 
            sx={{ 
              gridArea: { xs: 'chat', md: 'main' },
              height: '100%',
              minHeight: { xs: '0', md: '0' },
              maxHeight: { xs: 'calc(100vh - 200px)', md: '100%' }, // Limit mobile height
              display: 'flex',
              flexDirection: 'column',
              gap: 2,
              overflow: 'hidden'
            }}
          >
            {/* Desktop Filters */}
            {isAdmin && (
            <Box 
              sx={{ 
                display: { xs: 'none', md: 'block' },
                flexShrink: 0
              }}
            >
              <ChatFilters
                filters={chatFilters}
                onFiltersChange={setChatFilters}
                onClearFilters={clearChatFilters}
                maxDay={Math.max(Number(numDays || currentDay), ...messages.map(m => m.day || 1), currentDay)}
                currentDay={currentDay}
                currentTimePeriod={currentTimePeriod}
                npcs={npcs}
                periods={periods}
              />
            </Box>
            )}
            
            <Box sx={{ flex: 1, minHeight: 0, display: 'flex' }}>
              <Box sx={{ flex: 1, minHeight: 0 }}>
                <ChatInterface
                  messages={filteredMessages}
                  selectedNPC={talkTargetNPC || selectedNPC}
                  onSendMessage={handleSendMessage}
                  isLoading={isLoading || !playerNPC || !talkTargetNPC || (playerNPC?.id === talkTargetNPC?.id)}
                />
              </Box>
            </Box>
          </Box>
        </Box>

        {/* Mobile NPC Panel (only visible on mobile) */}
        <Box 
          sx={{ 
            display: { xs: 'block', md: 'none' },
            height: '250px',
            px: 4,
            pb: 2
          }}
        >
          {sessionId ? (
            <NPCPanel
              npcs={npcs}
              selectedNPCId={selectedNPCId}
              onNPCSelect={setSelectedNPCId}
              onNPCDoubleClick={handleNPCDoubleClick}
              onPlayAs={handlePlayAs}
              onTalk={handleTalk}
              activePlayerNpcId={playerNPC?.id || null}
              activeTalkTargetId={talkTargetNPC?.id || null}
            />
          ) : null}
        </Box>
      </Box>

      {/* Modals */}
      <CharacterCreationModal
        open={isCharacterCreationOpen}
        onClose={() => setCharacterCreationOpen(false)}
        onCreateCharacter={handleCreateCharacter}
      />


      <AdminPanel
        open={isAdminPanelOpen}
        onClose={() => setAdminPanelOpen(false)}
        npcs={npcs}
      />

      <ExperimentGuideModal
        open={showGuide}
        onClose={() => { 
          setShowGuide(false);
          try { localStorage.setItem('guide_dismissed', '1'); } catch {}
          if (userProgress && userProgress.currentPhase === StudyPhase.SESSION_1 && currentTestIndex === null) {
            startTest(0);
          }
        }}
        content={guideContent || (settings as any)?.prompts?.experimentGuide}
      />

      <NPCDetailsModal
        open={!!selectedNPCForDetails}
        onClose={() => setSelectedNPCForDetails(null)}
        npc={selectedNPCForDetails}
        onStartChat={handleStartChatFromDetails}
      />

      <QuestionnaireModal
        open={isQuestionnaireOpen}
        questionnaire={currentQuestionnaire}
        responses={currentResponses}
        onResponseChange={updateQuestionResponse}
        onComplete={handleQuestionnaireComplete}
        onClose={handleQuestionnaireClose}
        allowClose={!currentQuestionnaire?.required || 
          (userProgress?.completedQuestionnaires.includes(currentQuestionnaire?.id || '') || false)}
      />
    </Box>
  );
};

export const MedievalGameApp: React.FC = () => {
  return (
    <Provider store={store}>
      <ThemeProvider theme={medievalTheme}>
        <CssBaseline />
        <MedievalGameContent />
      </ThemeProvider>
    </Provider>
  );
};
