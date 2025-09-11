import React from 'react';
import { Card, CardHeader, CardContent, Stack, Button, Typography, Chip, Divider, TextField, IconButton, Tooltip } from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import StopIcon from '@mui/icons-material/Stop';
import PauseIcon from '@mui/icons-material/Pause';
import RefreshIcon from '@mui/icons-material/Refresh';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import { GameState, TimePeriod } from '../../types/enums';
import { formatGameState, formatTimePeriod, formatDayNumber } from '../../utils/formatters';

interface GameControlsProps {
  gameState: GameState;
  currentDay: number;
  currentTimePeriod: TimePeriod;
  numDays?: number;
  onNumDaysChange?: (value: number) => void;
  onStart: () => void;
  onStop: () => void;
  onPause: () => void;
  onContinue: () => void;
  onReset: () => void;
  onNewGame: () => void;
  onResetAll?: () => void;
  isLoading?: boolean;
  sessionId?: string;
  sessionName?: string;
  onRenameSession?: () => void;
}

export const GameControls: React.FC<GameControlsProps> = ({
  gameState,
  currentDay,
  currentTimePeriod,
  numDays,
  onNumDaysChange,
  onStart,
  onStop,
  onPause,
  onContinue,
  onReset,
  onNewGame,
  onResetAll,
  isLoading = false,
  sessionId,
  sessionName,
  onRenameSession,
}) => {
  const getStatusColor = (state: GameState) => {
    switch (state) {
      case GameState.RUNNING:
        return 'success';
      case GameState.PAUSED:
        return 'warning';
      default:
        return 'error';
    }
  };

  return (
    <Card>
      <CardHeader 
        title={
          <Typography 
            variant="h3" 
            className="text-center"
            sx={{ 
              fontSize: { xs: '1rem', sm: '1.25rem', md: '1.5rem' },
              fontWeight: { xs: 600, sm: 700 }
            }}
          >
            Game Controls
          </Typography>
        }
        action={
          sessionId ? (
            <Stack direction="row" spacing={1} alignItems="center">
              <Tooltip title={sessionName ? `Session: ${sessionName}` : 'Session ID'}>
                <Chip
                  size="small"
                  label={`ID: ${String(sessionId)}`}
                  variant="outlined"
                  color="default"
                  sx={{ 
                    display: { xs: 'none', sm: 'inline-flex' },
                    fontSize: { sm: '0.75rem' }
                  }}
                />
              </Tooltip>
            </Stack>
          ) : null
        }
        sx={{ 
          py: { xs: 1, sm: 2 },
          '& .MuiCardHeader-action': {
            m: 0,
            alignSelf: 'center'
          }
        }}
      />
      <Divider />
      <CardContent className="py-3">
        <Stack spacing={2}>
          {/* Game Status */}
          <div className="text-center space-y-2">
            <Chip
              label={formatGameState(gameState)}
              color={getStatusColor(gameState)}
              variant="filled"
              className="font-semibold"
            />
            <div className="flex items-center gap-2">
              <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: 'nowrap' }}>
                {formatDayNumber(currentDay)} - {formatTimePeriod(currentTimePeriod)}
              </Typography>
            </div>
          </div>

          {/* Num Days Control */}
          {typeof numDays === 'number' && onNumDaysChange && (
            <Stack direction="row" spacing={1} alignItems="center" justifyContent="center">
              <Typography variant="body2" color="text.secondary">Days:</Typography>
              <TextField
                type="number"
                size="small"
                value={numDays}
                inputProps={{ min: Math.max(1, currentDay), max: 365 }}
                onChange={(e) => {
                  const v = parseInt(e.target.value || '0', 10);
                  if (!Number.isNaN(v)) {
                    const clamped = Math.min(365, Math.max(currentDay, v));
                    onNumDaysChange(clamped);
                  }
                }}
                sx={{ width: 96 }}
              />
            </Stack>
          )}

          {/* Control Buttons */}
          <Stack direction="row" spacing={1} justifyContent="center">
            {gameState === GameState.STOPPED ? (
              <>
                <Button
                  variant="contained"
                  color="primary"
                  startIcon={<PlayArrowIcon />}
                  onClick={onStart}
                  disabled={isLoading}
                  sx={{ minWidth: 120 }}
                >
                  Start Game
                </Button>
                <Button
                  variant="outlined"
                  color="secondary"
                  startIcon={<RefreshIcon />}
                  onClick={onReset}
                  disabled={isLoading}
                  size="small"
                >
                  Reset
                </Button>
                {onResetAll && (
                  <Button
                    variant="outlined"
                    color="error"
                    startIcon={<RestartAltIcon />}
                    onClick={onResetAll}
                    disabled={isLoading}
                    size="small"
                  >
                    Reset All
                  </Button>
                )}
                <Button
                  variant="outlined"
                  color="primary"
                  startIcon={<AddIcon />}
                  onClick={onNewGame}
                  disabled={isLoading}
                  size="small"
                >
                  New
                </Button>
              </>
            ) : (
              <>
                {gameState === GameState.RUNNING ? (
                  <Button
                    variant="contained"
                    color="warning"
                    startIcon={<PauseIcon />}
                    onClick={onPause}
                    disabled={isLoading}
                  >
                    Pause
                  </Button>
                ) : (
                  <Button
                    variant="contained"
                    color="success"
                    startIcon={<PlayArrowIcon />}
                    onClick={onContinue}
                    disabled={isLoading}
                  >
                    Continue
                  </Button>
                )}
                <Button
                  variant="contained"
                  color="error"
                  startIcon={<StopIcon />}
                  onClick={onStop}
                  disabled={isLoading}
                >
                  Stop
                </Button>
              </>
            )}
          </Stack>
        </Stack>
      </CardContent>
    </Card>
  );
};