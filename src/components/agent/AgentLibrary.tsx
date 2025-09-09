import React, { useState } from 'react';
import {
  Card,
  CardHeader,
  CardContent,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  ListItemAvatar,
  Avatar,
  Typography,
  Chip,
  TextField,
  InputAdornment,
  Stack,
  Box,
  Tooltip
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import SchemaOutlinedIcon from '@mui/icons-material/SchemaOutlined';
import AddCircleOutlineIcon from '@mui/icons-material/AddCircleOutline';
import { AgentTemplate } from '../../types/schema';
import { AgentType } from '../../types/enums';
import { formatAgentType, formatLLMProvider } from '../../utils/formatters';

interface AgentLibraryProps {
  templates: AgentTemplate[];
  onAddAgent: (template: AgentTemplate) => void;
}

export const AgentLibrary: React.FC<AgentLibraryProps> = ({
  templates,
  onAddAgent
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');

  const getAgentTypeColor = (type: AgentType): string => {
    switch (type) {
      case AgentType.NPC_MANAGER:
        return '#8B4513';
      case AgentType.OPINION:
        return '#9C27B0';
      case AgentType.REPUTATION:
        return '#FF5722';
      case AgentType.SOCIAL_STANCE:
        return '#2196F3';
      case AgentType.MEMORY:
        return '#4CAF50';
      case AgentType.CONTEXT:
        return '#FF9800';
      default:
        return '#607D8B';
    }
  };

  const filteredTemplates = templates.filter(template => {
    const matchesSearch = template.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         template.description.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesCategory = selectedCategory === 'all' || template.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  const categories = ['all', ...new Set(templates.map(t => t.category).filter((cat): cat is string => Boolean(cat)))];

  return (
    <Card className="h-full">
      <CardHeader 
        title={
          <Stack direction="row" alignItems="center" spacing={1}>
            <SchemaOutlinedIcon className="text-primary-main" />
            <Typography variant="h6">
              Agent Library
            </Typography>
          </Stack>
        }
      />
      <CardContent className="p-0 h-full flex flex-col" sx={{ minHeight: 0 }}>
        {/* Search and Filters */}
        <Box className="p-4 space-y-3">
          <TextField
            placeholder="Search agents..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            fullWidth
            size="small"
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon />
                </InputAdornment>
              ),
            }}
          />
          
          {/* Category Filters */}
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            {categories.map((category) => (
              <Chip
                key={category}
                label={category === 'all' ? 'All' : category}
                onClick={() => setSelectedCategory(category)}
                color={selectedCategory === category ? 'primary' : 'default'}
                size="small"
                variant={selectedCategory === category ? 'filled' : 'outlined'}
              />
            ))}
          </Stack>
        </Box>

        {/* Agent Templates List */}
        <Box className="flex-1 overflow-auto">
          <List dense>
            {filteredTemplates.map((template) => (
              <ListItem key={template.id} disablePadding>
                <ListItemButton
                  onClick={() => onAddAgent(template)}
                  className="mx-2 mb-2 rounded-lg border border-grey-700 hover:border-primary-main transition-colors"
                >
                  <ListItemAvatar>
                    <Avatar
                      sx={{ 
                        bgcolor: getAgentTypeColor(template.type),
                        width: 40,
                        height: 40
                      }}
                    >
                      <SchemaOutlinedIcon />
                    </Avatar>
                  </ListItemAvatar>
                  
                  <ListItemText
                    primary={
                      <Stack direction="row" alignItems="center" spacing={1}>
                        <Typography variant="subtitle2" className="font-semibold">
                          {template.name}
                        </Typography>
                        <Tooltip title="Add to Network">
                          <AddCircleOutlineIcon 
                            fontSize="small" 
                            className="text-primary-main opacity-0 group-hover:opacity-100 transition-opacity"
                          />
                        </Tooltip>
                      </Stack>
                    }
                    primaryTypographyProps={{ component: 'span' }}
                    secondary={
                      <Box className="space-y-1">
                        <Typography variant="body2" color="text.secondary" className="text-xs">
                          {template.description}
                        </Typography>
                        <Stack direction="row" spacing={1} alignItems="center">
                          <Chip
                            label={formatAgentType(template.type)}
                            size="small"
                            variant="outlined"
                            sx={{ 
                              borderColor: getAgentTypeColor(template.type),
                              color: getAgentTypeColor(template.type)
                            }}
                          />
                          <Typography variant="caption" color="text.secondary">
                            {formatLLMProvider(template.defaultConfig.llmProvider)}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {template.defaultConfig.model}
                          </Typography>
                        </Stack>
                      </Box>
                    }
                    secondaryTypographyProps={{ component: 'div' }}
                  />
                </ListItemButton>
              </ListItem>
            ))}
          </List>

          {/* Empty State */}
          {filteredTemplates.length === 0 && (
            <Box className="flex items-center justify-center h-32">
              <Stack alignItems="center" spacing={1}>
                <Typography variant="body2" color="text.secondary">
                  No agents found
                </Typography>
                {searchTerm && (
                  <Typography variant="caption" color="text.secondary">
                    Try adjusting your search terms
                  </Typography>
                )}
              </Stack>
            </Box>
          )}
        </Box>

        {/* Quick Stats */}
        <Box className="p-4 border-t border-grey-700">
          <Stack direction="row" justifyContent="space-between" alignItems="center">
            <Typography variant="caption" color="text.secondary">
              {filteredTemplates.length} of {templates.length} agents
            </Typography>
            <Stack direction="row" spacing={1}>
              {Object.values(AgentType).slice(0, 3).map((type) => (
                <Box
                  key={type}
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: getAgentTypeColor(type) }}
                  title={formatAgentType(type)}
                />
              ))}
            </Stack>
          </Stack>
        </Box>
      </CardContent>
    </Card>
  );
};