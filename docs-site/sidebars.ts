import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';
import apiSidebar from './docs/api/sidebar';

const sidebars: SidebarsConfig = {
  docsSidebar: [
    {type: 'category', label: 'Introduction', collapsed: false, items: [
      'introduction/what-is-simswarm',
      'introduction/why-agent-based',
      'introduction/lineage-and-differences',
      'introduction/oss-and-self-host',
    ]},
    {type: 'category', label: 'Concepts', items: [
      'concepts/simulation-lifecycle',
      'concepts/agents-and-personas',
      'concepts/environments',
      'concepts/beliefs-and-stance',
      'concepts/story-signals',
      'concepts/entity-graph',
      'concepts/reports',
    ]},
    {type: 'category', label: 'Quickstart', items: [
      'quickstart/docker-quickstart',
      'quickstart/first-simulation',
      'quickstart/explore-the-demo',
    ]},
    {type: 'category', label: 'Self-Hosting', items: [
      'self-hosting/architecture',
      'self-hosting/prerequisites',
      'self-hosting/docker-compose',
      'self-hosting/env-reference',
      'self-hosting/gpu-runner',
      'self-hosting/temporal',
      'self-hosting/neo4j',
      'self-hosting/minio',
      'self-hosting/demo-mode',
      'self-hosting/migrations',
    ]},
    {type: 'category', label: 'Engine Internals', items: [
      'engine/architecture',
      'engine/environments-and-tools',
      'engine/belief-formulation',
      'engine/stance-scoring',
      'engine/story-signals',
      'engine/relations',
      'engine/personas',
      'engine/extractors',
      'engine/graph-build',
      'engine/reports',
      'engine/sweeps',
    ]},
    {type: 'category', label: 'Architecture', items: [
      'architecture/system-overview',
      'architecture/data-flow',
      'architecture/database-schema',
      'architecture/storage',
    ]},
    {type: 'category', label: 'Contributing', items: [
      'contributing/dev-setup',
      'contributing/testing',
      'contributing/repo-structure',
      'contributing/code-style',
    ]},
  ],
  apiSidebar: [{type: 'category', label: 'API Reference', items: apiSidebar}],
};

export default sidebars;
