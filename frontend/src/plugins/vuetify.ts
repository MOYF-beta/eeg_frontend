import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';

export const vuetify = createVuetify({
  components,
  directives,
  theme: {
    defaultTheme: 'light',
    themes: {
      light: {
        dark: false,
        colors: {
          background: '#F3F5FA',
          surface: '#FFFFFF',
          'surface-variant': '#EBEFF7',
          'surface-bright': '#FFFFFF',
          primary: '#2E62D9',
          'primary-darken-1': '#1E4FBE',
          secondary: '#0E9488',
          'secondary-darken-1': '#0B7A70',
          accent: '#7C4DFF',
          error: '#D32F2F',
          info: '#0277BD',
          success: '#2E9E5B',
          warning: '#E08A00',
          'on-background': '#1A2233',
          'on-surface': '#1A2233',
        },
      },
      dark: {
        dark: true,
        colors: {
          background: '#0E131F',
          surface: '#171E2E',
          'surface-variant': '#222B40',
          'surface-bright': '#28334B',
          primary: '#7AA2FF',
          'primary-darken-1': '#5B8AF5',
          secondary: '#2DD4BF',
          'secondary-darken-1': '#14B8A6',
          accent: '#A78BFA',
          error: '#F87171',
          info: '#38BDF8',
          success: '#4ADE80',
          warning: '#FBBF24',
          'on-background': '#E4E9F4',
          'on-surface': '#E4E9F4',
        },
      },
    },
  },
});
