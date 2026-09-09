import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'Semente',
  description: 'Multi-agent AI chat framework for land use and agriculture',
  lang: 'en-US',
  cleanUrls: true,
  themeConfig: {
    logo: '🌱',
    nav: [
      { text: 'Guide', link: '/guide/getting-started' },
      { text: 'Deployment', link: '/deployment/toy-app' },
      { text: 'Showcase', link: '/showcase/pasto-legal' },
    ],
    sidebar: {
      '/guide/': [
        {
          text: 'Guide',
          items: [
            { text: 'Getting Started', link: '/guide/getting-started' },
            { text: 'The Domain', link: '/guide/domain' },
            { text: 'Domain API', link: '/guide/domain-api' },
            { text: 'Manifest Reference', link: '/guide/manifest' },
            { text: 'Prompts & i18n', link: '/guide/prompts' },
            { text: 'Channels', link: '/guide/channels' },
          ],
        },
      ],
      '/deployment/': [
        {
          text: 'Deployment',
          items: [{ text: 'Toy App', link: '/deployment/toy-app' }],
        },
      ],
      '/showcase/': [
        {
          text: 'Showcase',
          items: [{ text: 'Pasto Legal', link: '/showcase/pasto-legal' }],
        },
      ],
    },
    socialLinks: [{ icon: 'github', link: 'https://github.com/semente-ai/semente' }],
    footer: {
      message: 'Extracted from Pasto Legal (LAPIG/UFG)',
      copyright: 'GPL-3.0-or-later',
    },
  },
})
