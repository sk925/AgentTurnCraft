import type { ThemeConfig } from 'antd';

export const antdTheme: ThemeConfig = {
  token: {
    colorPrimary: '#b7791f',
    colorSuccess: '#2d6a4f',
    colorWarning: '#c45c26',
    colorError: '#9b2226',
    colorBgLayout: 'transparent',
    colorBgElevated: '#fffdf9',
    colorBorder: '#e6dfd3',
    colorText: '#1a1c24',
    colorTextSecondary: '#5c5f72',
    fontFamily: '"Karla", system-ui, -apple-system, sans-serif',
    fontFamilyCode: '"IBM Plex Mono", ui-monospace, monospace',
    borderRadiusLG: 12,
    motionDurationMid: '0.2s',
  },
  components: {
    Layout: {
      headerHeight: 60,
      headerBg: 'rgba(255,253,247,0.72)',
      headerPadding: '0 28px',
      bodyBg: 'transparent',
    },
    Menu: {
      collapsedWidth: 64,
      itemBorderRadius: 8,
      itemMarginInline: 10,
      itemHeight: 44,
    },
    Table: {
      headerBg: '#f7f4ed',
      headerColor: '#3d3f4d',
      cellPaddingBlockMD: 12,
      rowHoverBg: 'rgba(183,121,31,0.06)',
    },
    Card: {
      paddingLG: 22,
    },
    Button: {
      fontWeight: 600,
    },
    Modal: {
      borderRadiusLG: 14,
    },
    Tag: {
      borderRadiusSM: 6,
    },
  },
};
