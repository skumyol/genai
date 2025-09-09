import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Stack,
  IconButton,
  Typography
} from '@mui/material';
import CloseOutlinedIcon from '@mui/icons-material/CloseOutlined';
import PersonOutlinedIcon from '@mui/icons-material/PersonOutlined';
import { CharacterClass, Alignment } from '../../types/enums';
import { Character } from '../../types/schema';

interface CharacterCreationModalProps {
  open: boolean;
  onClose: () => void;
  onCreateCharacter: (character: Omit<Character, 'id' | 'createdAt'>) => void;
}

export const CharacterCreationModal: React.FC<CharacterCreationModalProps> = ({
  open,
  onClose,
  onCreateCharacter
}) => {
  const [formData, setFormData] = useState<{
    name: string;
    characterClass: CharacterClass;
    background: string;
    alignment: Alignment;
    origin: string;
    age: string; // keep as string for input control; parse to number on submit
    traitsText: string; // comma-separated values -> string[] on submit
    skillsText: string; // comma-separated values -> string[] on submit
  }>({
    name: '',
    characterClass: CharacterClass.WARRIOR,
    background: '',
    alignment: Alignment.TRUE_NEUTRAL,
    origin: '',
    age: '',
    traitsText: '',
    skillsText: ''
  });

  const [errors, setErrors] = useState({
    name: false,
    background: false
  });

  const handleInputChange = (field: string, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    if (errors[field as keyof typeof errors]) {
      setErrors(prev => ({ ...prev, [field]: false }));
    }
  };

  const validateForm = () => {
    const newErrors = {
      name: !formData.name.trim(),
      background: !formData.background.trim()
    };
    setErrors(newErrors);
    return !Object.values(newErrors).some(Boolean);
  };

  const handleSubmit = () => {
    if (!validateForm()) return;

    const payload: Omit<Character, 'id' | 'createdAt'> = {
      name: formData.name.trim(),
      characterClass: formData.characterClass,
      background: formData.background.trim(),
      // optional fields added conditionally below
    } as any;

    if (formData.alignment) {
      (payload as any).alignment = formData.alignment;
    }
    if (formData.origin.trim()) {
      (payload as any).origin = formData.origin.trim();
    }
    if (formData.age.trim()) {
      const ageNum = parseInt(formData.age, 10);
      if (!Number.isNaN(ageNum) && ageNum > 0) {
        (payload as any).age = ageNum;
      }
    }
    const toList = (text: string) => text.split(',').map(s => s.trim()).filter(Boolean);
    const traits = toList(formData.traitsText);
    if (traits.length) (payload as any).traits = traits;
    const skills = toList(formData.skillsText);
    if (skills.length) (payload as any).skills = skills;

    onCreateCharacter(payload);
    handleClose();
  };

  const handleClose = () => {
    setFormData({
      name: '',
      characterClass: CharacterClass.WARRIOR,
      background: '',
      alignment: Alignment.TRUE_NEUTRAL,
      origin: '',
      age: '',
      traitsText: '',
      skillsText: ''
    });
    setErrors({
      name: false,
      background: false
    });
    onClose();
  };

  const isFormValid = formData.name.trim() && formData.background.trim();

  return (
    <Dialog 
      open={open} 
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      className="backdrop-blur-sm"
    >
      <DialogTitle>
        <Stack direction="row" alignItems="center" justifyContent="space-between">
          <Stack direction="row" alignItems="center" spacing={1}>
            <PersonOutlinedIcon />
            <Typography variant="h2">
              Create Character
            </Typography>
          </Stack>
          <IconButton onClick={handleClose} size="small">
            <CloseOutlinedIcon />
          </IconButton>
        </Stack>
      </DialogTitle>

      <DialogContent>
        <Stack spacing={3} className="mt-2">
          <TextField
            label="Character Name"
            value={formData.name}
            onChange={(e) => handleInputChange('name', e.target.value)}
            error={errors.name}
            helperText={errors.name ? 'Character name is required' : ''}
            fullWidth
            required
            placeholder="Enter your character's name"
          />

          <FormControl fullWidth required>
            <InputLabel>Character Class</InputLabel>
            <Select
              value={formData.characterClass}
              onChange={(e) => handleInputChange('characterClass', e.target.value)}
              label="Character Class"
            >
              {Object.values(CharacterClass).map((characterClass) => (
                <MenuItem key={characterClass} value={characterClass}>
                  {characterClass.charAt(0).toUpperCase() + characterClass.slice(1)}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControl fullWidth>
            <InputLabel>Alignment</InputLabel>
            <Select
              value={formData.alignment}
              onChange={(e) => handleInputChange('alignment', e.target.value as Alignment)}
              label="Alignment"
            >
              {Object.values(Alignment).map((al) => (
                <MenuItem key={al} value={al}>
                  {al.replace('_', ' ').replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase())}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <TextField
            label="Origin"
            value={formData.origin}
            onChange={(e) => handleInputChange('origin', e.target.value)}
            fullWidth
            placeholder="Village, city, or land of origin"
          />

          <TextField
            label="Background"
            value={formData.background}
            onChange={(e) => handleInputChange('background', e.target.value)}
            error={errors.background}
            helperText={errors.background ? 'Background is required' : 'Describe your character\'s history and motivations'}
            fullWidth
            required
            multiline
            rows={4}
            placeholder="Tell us about your character's past, motivations, and personality..."
          />

          <TextField
            label="Age"
            type="number"
            value={formData.age}
            onChange={(e) => handleInputChange('age', e.target.value)}
            fullWidth
            inputProps={{ min: 1 }}
          />

          <TextField
            label="Traits (comma-separated)"
            value={formData.traitsText}
            onChange={(e) => handleInputChange('traitsText', e.target.value)}
            fullWidth
            placeholder="brave, curious, honorable"
            helperText="Enter a list of personality traits"
          />

          <TextField
            label="Skills (comma-separated)"
            value={formData.skillsText}
            onChange={(e) => handleInputChange('skillsText', e.target.value)}
            fullWidth
            placeholder="swordsmanship, herbalism, diplomacy"
            helperText="Enter a list of skills"
          />
        </Stack>
      </DialogContent>

      <DialogActions className="p-6">
        <Button onClick={handleClose} color="secondary">
          Cancel
        </Button>
        <Button 
          onClick={handleSubmit}
          variant="contained"
          color="primary"
          disabled={!isFormValid}
        >
          Create Character
        </Button>
      </DialogActions>
    </Dialog>
  );
};