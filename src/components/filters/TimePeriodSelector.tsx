import React from 'react';
import { ToggleButtonGroup, ToggleButton, Typography } from '@mui/material';
import { TimePeriod } from '../../types/enums';
import { formatTimePeriod } from '../../utils/formatters';

interface TimePeriodSelectorProps {
  selectedPeriod: TimePeriod | null;
  onPeriodChange: (period: TimePeriod | null) => void;
  currentPeriod?: TimePeriod;
  periods?: TimePeriod[];
}

export const TimePeriodSelector: React.FC<TimePeriodSelectorProps> = ({
  selectedPeriod,
  onPeriodChange,
  currentPeriod,
  periods
}) => {
  const timePeriods = periods ?? Object.values(TimePeriod);

  const ALL = '__all__';
  const groupValue = (selectedPeriod ?? ALL) as any;

  const handleChange = (_: React.MouseEvent<HTMLElement>, newValue: any) => {
    if (newValue === ALL) {
      onPeriodChange(null);
    } else if (newValue) {
      onPeriodChange(newValue as TimePeriod);
    } else {
      // Clicking the selected button in exclusive mode can set undefined
      onPeriodChange(null);
    }
  };

  return (
    <div className="space-y-2">
      <Typography variant="body2" color="text.secondary">
        Time Period
      </Typography>
      <ToggleButtonGroup
        value={groupValue}
        exclusive
        onChange={handleChange}
        aria-label="time period filter"
        size="small"
        className="flex flex-wrap gap-1"
      >
        {/* All periods (no filter) */}
        <ToggleButton
          value={ALL}
          aria-label="All"
          className={`px-3 py-1 text-xs ${selectedPeriod === null ? 'ring-2 ring-secondary-main' : ''}`}
        >
          All
        </ToggleButton>
        {timePeriods.map((period) => (
          <ToggleButton
            key={period}
            value={period}
            aria-label={formatTimePeriod(period)}
            className={`px-3 py-1 text-xs ${
              currentPeriod === period ? 'ring-2 ring-secondary-main' : ''
            }`}
          >
            {formatTimePeriod(period)}
          </ToggleButton>
        ))}
      </ToggleButtonGroup>
    </div>
  );
};
