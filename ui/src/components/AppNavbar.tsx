import { AppShell, Avatar, Group, NavLink, Stack, Text } from '@mantine/core';
import { SvgIcon } from './SvgIcon';
import type { HistoryItem } from '../types';

interface AppNavbarProps {
  active: string;
  onNavigate: (id: string) => void;
  historyItems: HistoryItem[];
  onSelectHistory: (id: number) => void;
}

const icons = {
  search: 'M15.5 14h-.79l-.28-.27A6.471 6.471 0 0016 9.5 6.5 6.5 0 109.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z',
  history: 'M13 3a9 9 0 00-9 9H1l3.89 3.89.07.14L9 12H6c0-3.87 3.13-7 7-7s7 3.13 7 7-3.13 7-7 7c-1.93 0-3.68-.79-4.94-2.06l-1.42 1.42A8.954 8.954 0 0013 21a9 9 0 000-18zm-1 5v5l4.28 2.54.72-1.21-3.5-2.08V8H12z',
};

const ASSETS = {
  brand: '/assets/senai-brand.svg',
  logoReduction: '/assets/logo-light-reduction.png',
  logoFull: '/assets/logo-full.svg',
};

const navItems = [
  { label: 'Nova Pesquisa', icon: icons.search, id: 'nova-pesquisa' },
  { label: 'Histórico', icon: icons.history, id: 'historico' },
];

export function AppNavbar({ active, onNavigate, historyItems, onSelectHistory }: AppNavbarProps) {
  return (
    <AppShell.Navbar p="md" style={{ background: '#1d1c22' }}>
      <Stack gap="lg" h="100%">
        {/* Logo DT */}
        <Group justify="center" pt="sm">
          <img src={ASSETS.logoFull} alt="DT" className="logo-sidebar" />
        </Group>

        {/* Section label */}
        <Text size="xs" c="#9b9b9b" fw={500}>PESQUISA</Text>

        {/* Nav items */}
        <Stack gap={4}>
          {navItems.map((item) => (
            <NavLink
              key={item.id}
              label={item.label}
              active={active === item.id}
              onClick={() => onNavigate(item.id)}
              leftSection={<SvgIcon path={item.icon} size={18} />}
              styles={{
                root: {
                  borderRadius: 8,
                  height: 38,
                  '&[data-active]': {
                    backgroundColor: 'rgba(221, 28, 74, 0.3)',
                  },
                },
              }}
            />
          ))}
        </Stack>

        {/* History list (only when historico tab is active) */}
        {active === 'historico' && (
          <Stack gap={4} mt="xs" style={{ overflowY: 'auto', flex: 1 }}>
            {historyItems.length === 0 ? (
              <Text size="xs" c="#5E6267" ta="center" mt="sm">Nenhuma pesquisa ainda</Text>
            ) : (
              historyItems.map((item) => {
                const dateStr = item.created_at
                  ? new Date(item.created_at).toLocaleDateString('pt-BR', {
                      day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
                    })
                  : '';
                return (
                  <NavLink
                    key={item.id}
                    label={item.topic.length > 40 ? item.topic.substring(0, 40) + '...' : item.topic}
                    description={dateStr}
                    onClick={() => onSelectHistory(item.id)}
                    styles={{ root: { borderRadius: 8 } }}
                  />
                );
              })
            )}
          </Stack>
        )}

        {/* Spacer + attribution */}
        <Group gap="md" mt="auto" pt="md" style={{ borderTop: '1px solid #2a2d34' }}>
          <Avatar size={36} radius="xl" color="distrito">DT</Avatar>
          <Stack gap={1}>
            <Text size="sm" fw={600} c="#fcfcfc">Distrito Tecnológico</Text>
            <Text size="xs" c="#9b9b9b">SENAI-SP</Text>
          </Stack>
        </Group>
      </Stack>
    </AppShell.Navbar>
  );
}
