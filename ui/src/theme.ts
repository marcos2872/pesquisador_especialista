import { createTheme } from '@mantine/core';

export const theme = createTheme({
  primaryColor: 'distrito',
  colors: {
    distrito: [
      '#fef2f4', // 0  — primary-50
      '#fde6ea', // 1  — primary-100
      '#f9b8c4', // 2  — primary-200
      '#f58a9e', // 3  — primary-300
      '#e94d6a', // 4  — primary-400
      '#D72042', // 5  — primary-500  (brand)
      '#D72042', // 6  — primary-600  (CTA)
      '#b8163d', // 7  — primary-700
      '#931131', // 8  — primary-800
      '#4a0819', // 9  — primary-950
    ],
    dark: [
      '#ffffff', // 0  — text on dark / pure white
      '#9b9b9b', // 1  — text secondary
      '#6b6b6b', // 2  — text muted
      '#5E6267', // 3  — cinza médio
      '#333333', // 4  — border (stroke-neutral)
      '#2e2e2e', // 5  — surface elevated
      '#232323', // 6  — surface/card
      '#1a1a1a', // 7
      '#121212', // 8  — background
      '#000000', // 9  — pure black
    ],
  },
  fontFamily: "'DM Sans', -apple-system, system-ui, sans-serif",
  headings: { fontFamily: "'Korolev', 'Barlow', sans-serif" },
  defaultRadius: 'md',
  primaryShade: 5,
});
