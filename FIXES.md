# Fixes for Game Data and Questionnaire Issues

This document summarizes the changes made to fix the issues with game data initialization, user data handling, questionnaire storage, and chat system improvements.

## Recent Updates (September 8, 2025)

### 6. Chat System Converted from SSE to Direct Request-Response

**Problem**: Chat history was showing messages in the middle due to SSE (Server-Sent Events) broadcasting entire conversation history, causing confusion about message origins.

**Solution**: Converted the chat system from SSE to a simple request-response model:

- **Removed SSE Dependencies**: 
  - Removed `openGameStream` function from API client
  - Removed all SSE event listeners and stream management code
  - Removed `streamRef` and SSE message handling functions

- **Updated Chat Flow**:
  - User sends a message via `sendPlayerChatWithStats`
  - API returns direct response in the same request
  - Frontend immediately displays user message and NPC response
  - Minimal database refresh to sync any additional messages

- **Benefits**:
  - Clear message flow: user message → immediate response
  - No confusion from historical messages appearing mid-conversation
  - Simpler debugging and maintenance
  - Reduced complexity in frontend state management

### 7. Frontend Build Issues Fixed

**Problem**: HMR (Hot Module Replacement) errors due to:
- Invalid Tailwind CSS syntax using `@utility` directives
- Incorrect PostCSS configuration
- Missing Tailwind configuration file

**Solutions**:
- **Fixed CSS**: Converted all `@utility` directives to standard CSS classes
- **Updated PostCSS**: Changed from `@tailwindcss/postcss` to `tailwindcss` plugin
- **Added Tailwind Config**: Created proper `tailwind.config.js` file
- **Updated CSS Import**: Changed from `@import "tailwindcss"` to standard `@tailwind` directives

---

## Original Fixes

## 1. Main Game Data Initialization

We created a new `db_init.py` file that contains a function to initialize the `main_game_data` table. This ensures that the table is properly created and populated with default values when the application starts.

```python
def init_main_game_data(db_path, default_settings_path=None, agent_settings_path=None):
    # Creates the main_game_data table if it doesn't exist
    # Inserts a default row if the table is empty
```

This function is imported and called during application initialization in `app.py`.

## 2. Questionnaire Storage as Separate CSV Files

We split the single `questionarrie.csv` file into multiple separate CSV files:

- `public/questionnaire_pre_game.csv`
- `public/questionnaire_session_1.csv`
- `public/questionnaire_session_2.csv`
- `public/questionnaire_final_compare.csv`

This improves modularity and makes it easier to maintain the questionnaires.

We updated the questionnaire parser to load from these separate files:

```typescript
export async function loadQuestionnaireFromCSV(): Promise<Questionnaire[]> {
  const questionnaires: Questionnaire[] = [];
  const files = [
    'questionnaire_pre_game.csv',
    'questionnaire_session_1.csv',
    'questionnaire_session_2.csv', 
    'questionnaire_final_compare.csv'
  ];
  
  // Load from each file and combine the results
  // Fall back to the original questionarrie.csv if needed
}
```

## 3. Auto-Assignment of User ID in Questionnaires

We modified the frontend questionnaire submission to automatically include the user ID with each response:

```typescript
// In handleQuestionnaireComplete
const userId = localStorage.getItem('user_id') || '';
const enrichedResponses = currentResponses.map(response => ({
  ...response,
  userId
}));
```

We also updated the backend API to extract and use this user ID:

```python
# Extract user_id from response if present and not already set
if not user_id and responses:
    for resp in responses:
        if isinstance(resp, dict) and resp.get('userId'):
            user_id = str(resp.get('userId'))
            break
```

## 4. Improved Reset Functionality

We enhanced the `reset_user_sessions` endpoint to properly clear all user-related data from all tables:

- Sessions
- Conversations
- Metrics
- Questionnaire responses
- NPC memories
- Messages
- Dialogues
- Days
- User events

We enabled foreign key constraints and added proper error handling and logging.

## 5. Main Game Data Creation for New Users

We ensured that `main_game_data` entries are created for new users when questionnaire responses are submitted:

```python
# Ensure main_game_data exists for this user
try:
    mgd = memory_agent.db_manager.get_main_game_data(user_id)
    if not mgd:
        memory_agent.db_manager.create_main_game_data(user_id=user_id)
except Exception as e:
    print(f"Error ensuring main_game_data: {e}")
```

These changes should resolve the issues with user data initialization, questionnaire handling, and reset functionality.
