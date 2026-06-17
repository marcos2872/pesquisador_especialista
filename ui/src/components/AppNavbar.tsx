import { AppShell, Avatar, Group, NavLink, Stack, Text } from '@mantine/core';
import { SvgIcon } from './SvgIcon';
import type { HistoryItem } from '../types';

interface AppNavbarProps {
  active: string;
  onNavigate: (id: string) => void;
  historyItems: HistoryItem[];
  onSelectHistory: (id: number) => void;
  onDeleteHistory: (id: number) => void;
}

const icons = {
  search: 'M15.5 14h-.79l-.28-.27A6.471 6.471 0 0016 9.5 6.5 6.5 0 109.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z',
  delete: 'M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zm2.46-7.12l1.41-1.41L12 12.59l2.12-2.12 1.41 1.41L13.41 14l2.12 2.12-1.41 1.41L12 15.41l-2.12 2.12-1.41-1.41L10.59 14l-2.13-2.12zM15.5 4l-1-1h-5l-1 1H5v2h14V4z',
};

const ASSETS = {
  brand: '/assets/senai-brand.svg',
  logoReduction: '/assets/logo-light-reduction.png',
  logoFull: '/assets/logo-full.svg',
};

const navItems = [
  { label: 'Nova Pesquisa', icon: icons.search, id: 'nova-pesquisa' },
];

export function AppNavbar({ active, onNavigate, historyItems, onSelectHistory, onDeleteHistory }: AppNavbarProps) {
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
                  '&[dataActive]': {
                    backgroundColor: 'rgba(221, 28, 74, 0.3)',
                  },
                },
              }}
            />
          ))}
        </Stack>

        {/* Sessions list (always visible) */}
        <Text size="xs" c="#9b9b9b" fw={500} mt="xs">SESSÕES</Text>
        <Stack gap={4} style={{ overflowY: 'auto', flex: 1 }}>
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
                  <Group key={item.id} gap={0} wrap="nowrap" style={{ borderRadius: 8 }} align="stretch">
                    <NavLink
                      label={item.topic.length > 40 ? item.topic.substring(0, 40) + '...' : item.topic}
                      description={dateStr}
                      onClick={() => onSelectHistory(item.id)}
                      style={{ flex: 1, borderRadius: 8 }}
                    />
                    <div
                      onClick={() => onDeleteHistory(item.id)}
                      style={{
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        padding: '0 10px',
                        color: '#5E6267',
                        borderTopRightRadius: 8,
                        borderBottomRightRadius: 8,
                      }}
                      onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.color = '#D72042'; }}
                      onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.color = '#5E6267'; }}
                      title="Remover do histórico"
                    >
                      <SvgIcon path={icons.delete} size={14} />
                    </div>
                  </Group>
                );
              })
            )}
          </Stack>

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
