// Medieval-themed UI configuration with retro gaming elements
import { createTheme } from '@mui/material/styles';

const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#A0522D', // Lighter brown for better visibility
      light: '#CD853F',
      dark: '#8B4513',
      contrastText: '#FFFFFF'
    },
    secondary: {
      main: '#FFD700', // Brighter gold for better visibility
      light: '#FFFF00',
      dark: '#DAA520',
      contrastText: '#000000'
    },
    background: {
      default: '#1A1A1A', // Darker background for better contrast
      paper: '#2D2D2D' // Lighter cards for better contrast
    },
    text: {
      primary: '#FFFFFF', // Pure white for maximum readability
      secondary: '#E0E0E0' // Light gray for secondary text with good contrast
    },
    success: {
      main: '#4CAF50', // Brighter green for better visibility
      contrastText: '#FFFFFF'
    },
    warning: {
      main: '#FF9800', // Brighter orange for better visibility
      contrastText: '#FFFFFF'
    },
    error: {
      main: '#F44336', // Brighter red for better visibility
      contrastText: '#FFFFFF'
    },
    grey: {
      50: '#F8F8FF',
      100: '#F5F5DC',
      200: '#E6E6FA',
      300: '#D3D3D3',
      400: '#A9A9A9',
      500: '#808080',
      600: '#696969',
      700: '#556B2F',
      800: '#2F4F4F',
      900: '#1C1C1C'
    }
  },
  typography: {
    fontFamily: '"Cinzel", "Times New Roman", serif',
    fontSize: 14,
    fontWeightLight: 300,
    fontWeightRegular: 400,
    fontWeightMedium: 500,
    fontWeightBold: 700,
    h1: {
      fontFamily: '"Cinzel", serif',
      fontWeight: 700,
      fontSize: '2.5rem'
    },
    h2: {
      fontFamily: '"Cinzel", serif', 
      fontWeight: 600,
      fontSize: '2rem'
    },
    h3: {
      fontFamily: '"Cinzel", serif',
      fontWeight: 600,
      fontSize: '1.5rem'
    },
    body1: {
      fontFamily: '"Cormorant Garamond", serif',
      fontSize: '1rem',
      lineHeight: 1.6
    },
    body2: {
      fontFamily: '"Cormorant Garamond", serif',
      fontSize: '0.875rem',
      lineHeight: 1.5
    },
    button: {
      fontFamily: '"Cinzel", serif',
      fontWeight: 600,
      textTransform: 'uppercase',
      letterSpacing: '0.5px'
    }
  },
  shape: {
    borderRadius: 8
  },
  shadows: [
    'none',
    '0px 2px 4px rgba(0,0,0,0.3)',
    '0px 4px 8px rgba(0,0,0,0.3)',
    '0px 6px 12px rgba(0,0,0,0.3)',
    '0px 8px 16px rgba(0,0,0,0.3)',
    '0px 10px 20px rgba(0,0,0,0.3)',
    '0px 12px 24px rgba(0,0,0,0.3)',
    '0px 14px 28px rgba(0,0,0,0.3)',
    '0px 16px 32px rgba(0,0,0,0.3)',
    '0px 18px 36px rgba(0,0,0,0.3)',
    '0px 20px 40px rgba(0,0,0,0.3)',
    '0px 22px 44px rgba(0,0,0,0.3)',
    '0px 24px 48px rgba(0,0,0,0.3)',
    '0px 26px 52px rgba(0,0,0,0.3)',
    '0px 28px 56px rgba(0,0,0,0.3)',
    '0px 30px 60px rgba(0,0,0,0.3)',
    '0px 32px 64px rgba(0,0,0,0.3)',
    '0px 34px 68px rgba(0,0,0,0.3)',
    '0px 36px 72px rgba(0,0,0,0.3)',
    '0px 38px 76px rgba(0,0,0,0.3)',
    '0px 40px 80px rgba(0,0,0,0.3)',
    '0px 42px 84px rgba(0,0,0,0.3)',
    '0px 44px 88px rgba(0,0,0,0.3)',
    '0px 46px 92px rgba(0,0,0,0.3)',
    '0px 48px 96px rgba(0,0,0,0.3)'
  ]
});

export default theme;