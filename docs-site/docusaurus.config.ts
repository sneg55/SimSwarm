import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'SimSwarm',
  tagline: 'Open-source swarm-intelligence simulation, self-hostable',
  favicon: 'img/favicon.ico',
  url: 'https://docs.simswarm.xyz',
  baseUrl: '/',
  organizationName: 'sneg55',
  projectName: 'SimSwarm',
  onBrokenLinks: 'throw',
  onBrokenMarkdownLinks: 'throw',
  i18n: {defaultLocale: 'en', locales: ['en']},

  markdown: {mermaid: true},

  presets: [
    [
      'classic',
      {
        docs: {
          routeBasePath: '/',
          sidebarPath: './sidebars.ts',
          docItemComponent: '@theme/ApiItem',
        },
        blog: false,
        theme: {customCss: './src/css/custom.css'},
      } satisfies Preset.Options,
    ],
  ],

  plugins: [
    [
      'docusaurus-plugin-openapi-docs',
      {
        id: 'api',
        docsPluginId: 'classic',
        config: {
          simswarm: {
            specPath: 'openapi.json',
            outputDir: 'docs/api',
            sidebarOptions: {groupPathsBy: 'tag'},
          },
        },
      },
    ],
  ],

  themes: [
    [
      require.resolve('@easyops-cn/docusaurus-search-local'),
      {hashed: true, indexDocs: true, docsRouteBasePath: '/'},
    ],
    'docusaurus-theme-openapi-docs',
    '@docusaurus/theme-mermaid',
  ],

  themeConfig: {
    colorMode: {defaultMode: 'dark', respectPrefersColorScheme: true},
    navbar: {
      title: 'SimSwarm',
      logo: {alt: 'SimSwarm', src: 'img/logo.svg'},
      items: [
        {type: 'docSidebar', sidebarId: 'docsSidebar', position: 'left', label: 'Docs'},
        {to: '/api/simswarm', label: 'API', position: 'left'},
        {href: 'https://simswarm.xyz', label: 'Demo', position: 'right'},
        {href: 'https://github.com/sneg55/SimSwarm', label: 'GitHub', position: 'right'},
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {title: 'Docs', items: [
          {label: 'Introduction', to: '/introduction/what-is-simswarm'},
          {label: 'Quickstart', to: '/quickstart/docker-quickstart'},
          {label: 'Self-Hosting', to: '/self-hosting/architecture'},
        ]},
        {title: 'More', items: [
          {label: 'Live Demo', href: 'https://simswarm.xyz'},
          {label: 'GitHub', href: 'https://github.com/sneg55/SimSwarm'},
        ]},
      ],
      copyright: 'SimSwarm — MIT licensed.',
    },
    prism: {theme: prismThemes.github, darkTheme: prismThemes.dracula},
  } satisfies Preset.ThemeConfig,
};

export default config;
