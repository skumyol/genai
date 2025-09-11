import React from 'react';
import { Card, CardContent, Stack, Slider, Typography, Button, Select, MenuItem, FormControl, InputLabel, Box } from '@mui/material';
import FilterAltOutlinedIcon from '@mui/icons-material/FilterAltOutlined';
import ClearOutlinedIcon from '@mui/icons-material/ClearOutlined';
import { TimePeriodSelector } from './TimePeriodSelector';
import { TimePeriod } from '../../types/enums';
import { NPC, ChatFilters as ChatFiltersType } from '../../types/schema';
import { formatDayNumber } from '../../utils/formatters';

interface ChatFiltersProps {
  filters: ChatFiltersType;
  onFiltersChange: (filters: Partial<ChatFiltersType>) => void;
  onClearFilters: () => void;
  maxDay: number;
  currentDay: number;
  currentTimePeriod: TimePeriod;
  npcs: NPC[];
  periods?: TimePeriod[];
}

export const ChatFilters: React.FC<ChatFiltersProps> = ({
  filters,
  onFiltersChange,
  onClearFilters,
  maxDay,
  currentDay,
  currentTimePeriod,
  npcs,
  periods
}) => {
  const hasActiveFilters = filters.selectedDay !== null || 
                          filters.selectedTimePeriod !== null || 
                          filters.selectedNPCId !== null;

  const handleDayChange = (_: Event, value: number | number[]) => {
    onFiltersChange({ selectedDay: value as number });
  };

  const dayMarks = Array.from({ length: maxDay }, (_, i) => ({
    value: i + 1,
    label: i === 0 || (i + 1) % 5 === 0 ? `${i + 1}` : ''
  }));

  return (
    <Card>
      <CardContent 
        sx={{ 
          py: { xs: 1, sm: 1.5 },
          px: { xs: 1.5, sm: 2 },
          '&:last-child': { pb: { xs: 1, sm: 1.5 } }
        }}
      >
        <Stack spacing={{ xs: 1, sm: 1.5 }}>
          {/* Inline Header Row */}
          <Stack 
            direction="row" 
            alignItems="center" 
            justifyContent="space-between"
            flexWrap="wrap"
            gap={1}
          >
            <Stack 
              direction="row" 
              alignItems="center" 
              spacing={{ xs: 0.5, sm: 1 }}
            >
              <FilterAltOutlinedIcon 
                sx={{ fontSize: { xs: '1rem', sm: '1.25rem' } }} 
              />
              <Typography 
                variant="body2" 
                fontWeight="medium"
                sx={{ fontSize: { xs: '0.75rem', sm: '0.875rem' } }}
              >
                Filters
              </Typography>
            </Stack>
            {hasActiveFilters && (
              <Button
                size="small"
                startIcon={<ClearOutlinedIcon sx={{ fontSize: { xs: '0.875rem', sm: '1rem' } }} />}
                onClick={onClearFilters}
                color="secondary"
                variant="text"
                sx={{ 
                  minWidth: 'auto', 
                  px: { xs: 0.5, sm: 1 },
                  fontSize: { xs: '0.75rem', sm: '0.875rem' }
                }}
              >
                Clear
              </Button>
            )}
          </Stack>

          {/* Controls Row - more compact */}
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} useFlexGap alignItems={{ xs: 'stretch', sm: 'center' }}>
            {/* Day Filter - more compact */}
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Stack direction="row" alignItems="center" spacing={1} mb={0.5}>
                <Typography variant="caption" color="text.secondary">
                  Day
                </Typography>
                {!!currentDay && (
                  <Typography variant="caption" color="primary">
                    (Current: {formatDayNumber(currentDay)})
                  </Typography>
                )}
              </Stack>
              <Slider
                value={filters.selectedDay ?? currentDay}
                onChange={handleDayChange}
                min={1}
                max={maxDay}
                step={1}
                valueLabelDisplay="auto"
                valueLabelFormat={formatDayNumber}
                size="small"
                sx={{ 
                  width: '100%', 
                  mx: 0,
                  '& .MuiSlider-markLabel': {
                    fontSize: '0.6rem'
                  }
                }}
              />
            </Box>

            {/* Time Period Filter - more compact */}
            <Box sx={{ minWidth: { sm: 180 } }}>
              <TimePeriodSelector
                selectedPeriod={filters.selectedTimePeriod}
                onPeriodChange={(period) => onFiltersChange({ selectedTimePeriod: period })}
                currentPeriod={currentTimePeriod}
                periods={periods}
              />
            </Box>

            {/* NPC Filter - more compact */}
            <FormControl size="small" sx={{ minWidth: { sm: 160 } }}>
              <InputLabel>NPC</InputLabel>
              <Select
                value={filters.selectedNPCId || ''}
                onChange={(e) => onFiltersChange({ selectedNPCId: (e.target.value as string) || null })}
                label="NPC"
              >
                <MenuItem value="">
                  <em>All</em>
                </MenuItem>
                {npcs.map((npc) => (
                  <MenuItem key={npc.id} value={npc.id}>
                    {npc.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Stack>

          {/* Active Filters Summary - more compact */}
          {hasActiveFilters && (
            <Box className="px-2 py-1 bg-grey-800 rounded">
              <Stack direction="row" spacing={0.5} flexWrap="wrap" alignItems="center">
                <Typography variant="caption" color="text.secondary">
                  Active:
                </Typography>
                {filters.selectedDay && (
                  <Typography variant="caption" className="bg-primary-main text-primary-contrastText px-1 py-0.5 rounded text-xs">
                    {formatDayNumber(filters.selectedDay)}
                  </Typography>
                )}
                {filters.selectedTimePeriod && (
                  <Typography variant="caption" className="bg-secondary-main text-secondary-contrastText px-1 py-0.5 rounded text-xs">
                    {filters.selectedTimePeriod}
                  </Typography>
                )}
                {filters.selectedNPCId && (
                  <Typography variant="caption" className="bg-success-main text-success-contrastText px-1 py-0.5 rounded text-xs">
                    {npcs.find(npc => npc.id === filters.selectedNPCId)?.name}
                  </Typography>
                )}
              </Stack>
            </Box>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
};